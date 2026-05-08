"""
OpenGenealogyAI — Main Orchestrator

Starts all four systems as parallel processes:
  1. Checker       — health monitor, every 10 minutes
  2. Reporter      — Slack hourly report, every 60 minutes
  3. CPU Workers   — spaCy NER + schema conversion (10 processes)
  4. GPU Worker    — nomic-embed-text + Qdrant upsert
  5. Scrapers      — one process per active source

Usage:
  python -m pipeline.orchestrator
  python pipeline/orchestrator.py

Stop cleanly with Ctrl+C — checkpoint state is preserved automatically.
"""

import os, sys, time, signal, datetime, json, subprocess
from pathlib import Path
from multiprocessing import Process, Queue, Event

from pipeline.paths import LOGS, CHECKPOINTS

START_TIME_FILE = LOGS / "pipeline_start.txt"
PID_FILE        = LOGS / "orchestrator.pid"
SLACK_TOKEN     = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL   = "#pipeline-status"
SLACK_URL       = "https://slack.com/api/chat.postMessage"


# ── Slack notification ─────────────────────────────────────────────────────────

def _post_slack(message: str):
    if not SLACK_TOKEN:
        print(f"[SLACK] {message}")
        return
    try:
        import requests
        requests.post(SLACK_URL, headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        }, json={"channel": SLACK_CHANNEL, "text": message}, timeout=10)
    except Exception as e:
        print(f"[SLACK ERROR] {e}")


# ── Process runners ────────────────────────────────────────────────────────────

def _run_checker():
    """Entry point for checker subprocess."""
    from pipeline.checker import run_loop
    run_loop(interval_seconds=600)


def _run_reviewer():
    """Entry point for daily Sonnet review subprocess (every 4 hours)."""
    from pipeline.reviewer import run_loop
    run_loop(interval_seconds=14400)


def _run_reporter():
    """Entry point for reporter subprocess."""
    from pipeline.reporter import run_loop
    run_loop(interval_seconds=3600)


def _run_gpu_worker():
    """Entry point for GPU embedding worker subprocess."""
    try:
        from pipeline.workers.gpu_worker import run_loop
        run_loop()
    except ImportError:
        print("[GPU WORKER] pipeline/workers/gpu_worker.py not found yet — skipping")
        # Stay alive so the orchestrator doesn't restart us endlessly
        while True:
            time.sleep(60)


def _run_cpu_workers():
    """Entry point for CPU worker pool subprocess."""
    try:
        from pipeline.workers.cpu_worker import run_pool
        run_pool()
    except ImportError:
        print("[CPU WORKERS] pipeline/workers/cpu_worker.py not found yet — skipping")
        while True:
            time.sleep(60)


def _run_scraper(source_name: str):
    """Entry point for a single scraper subprocess."""
    module_map = {
        "wikidata":              "pipeline.fetchers.wikidata",
        "chronicling_america":   "pipeline.fetchers.chronicling",
        "internet_archive":      "pipeline.fetchers.internet_archive",
        "trove":                 "pipeline.fetchers.trove",
        "blm_land_patents":      "pipeline.fetchers.blm",
        "nara_catalog":          "pipeline.fetchers.nara_catalog",
        "hathitrust":            "pipeline.fetchers.hathitrust",
        "open_library":          "pipeline.fetchers.open_library",
        "dpla":                  "pipeline.fetchers.dpla",
        "chronicling_expanded":  "pipeline.fetchers.chronicling_expanded",
    }
    module_path = module_map.get(source_name)
    if not module_path:
        print(f"[SCRAPER] Unknown source: {source_name}")
        return

    try:
        import importlib
        mod = importlib.import_module(module_path)
        mod.run()
    except ImportError:
        print(f"[SCRAPER:{source_name}] {module_path} not found yet — skipping")
        while True:
            time.sleep(300)
    except Exception as e:
        print(f"[SCRAPER:{source_name}] Crashed: {e}")


# ── Watchdog ───────────────────────────────────────────────────────────────────

class ProcessGroup:
    """Tracks a set of named processes and restarts any that die."""

    def __init__(self):
        self._procs: dict[str, tuple[Process, callable, tuple]] = {}

    def add(self, name: str, target, args=()):
        p = Process(target=target, args=args, name=name, daemon=True)
        p.start()
        self._procs[name] = (p, target, args)
        print(f"[ORCH] Started {name} (pid={p.pid})")

    def watchdog_tick(self):
        """Restart any dead processes."""
        for name, (p, target, args) in list(self._procs.items()):
            if not p.is_alive():
                exit_code = p.exitcode
                print(f"[ORCH] {name} died (exit={exit_code}) — restarting in 10s")
                time.sleep(10)
                new_p = Process(target=target, args=args, name=name, daemon=True)
                new_p.start()
                self._procs[name] = (new_p, target, args)
                print(f"[ORCH] Restarted {name} (pid={new_p.pid})")

    def terminate_all(self):
        for name, (p, _, _) in self._procs.items():
            if p.is_alive():
                p.terminate()
                print(f"[ORCH] Stopped {name}")
        for _, (p, _, _) in self._procs.items():
            p.join(timeout=5)


# ── Source selection ───────────────────────────────────────────────────────────

# Sources enabled for Day 1. Add more as pipeline matures.
ACTIVE_SOURCES = [
    "wikidata",
    "chronicling_america",
    "internet_archive",
    "blm_land_patents",
    "open_library",
    "dpla",
    "chronicling_expanded",
    # hathitrust: disabled — catalog.hathitrust.org/Search/Home blocks non-browser sessions
    # Re-enable once a working discovery API is identified (OAI-PMH or data dump ingestion)
    # nara_catalog: disabled — catalog.archives.gov redeployed as a React SPA; REST API returns HTML
    # Re-enable once NARA publishes a new JSON API or we switch to their bulk data S3 download
]


# ── Startup ────────────────────────────────────────────────────────────────────

def _kill_zombie_workers():
    """Kill any leftover pipeline worker processes from a previous orchestrator run.

    Without this, a crashed orchestrator can leave child workers running (they
    still hold the GPU / SQLite). When the new orchestrator starts, two GPU
    workers fight over the GPU and both fail. This is problem #3 from the
    36-hour postmortem: "Duplicate GPU workers running simultaneously".
    """
    try:
        import psutil
    except ImportError:
        print("[ORCH] psutil not installed — skipping zombie cleanup")
        return

    own_pid = os.getpid()
    killed = 0
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] == own_pid:
                continue
            if not proc.info["name"] or "python" not in proc.info["name"].lower():
                continue
            cmdline = " ".join(proc.info.get("cmdline") or [])
            # Match anything that looks like one of our worker entry points
            if any(sig in cmdline for sig in (
                "pipeline.workers.gpu_worker",
                "pipeline.workers.cpu_worker",
                "pipeline.fetchers.",
                "pipeline.checker",
                "pipeline.reporter",
                "pipeline.reviewer",
            )):
                print(f"[ORCH] Killing zombie worker PID={proc.info['pid']} "
                      f"cmd={cmdline[:80]}")
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if killed:
        print(f"[ORCH] Cleaned up {killed} zombie workers")
        time.sleep(2)  # let OS reclaim handles
    else:
        print("[ORCH] No zombie workers found")


def _write_start_time():
    LOGS.mkdir(parents=True, exist_ok=True)
    START_TIME_FILE.write_text(datetime.datetime.utcnow().isoformat())


def _write_pid():
    LOGS.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _read_checkpoint_count() -> int:
    import sqlite3
    db = CHECKPOINTS / "pipeline.db"
    if not db.exists():
        return 0
    try:
        con = sqlite3.connect(db)
        return con.execute("SELECT COUNT(*) FROM records WHERE status='embedded'").fetchone()[0]
    except Exception:
        return 0


def _log_start(already_embedded: int):
    entry = {
        "ts":    datetime.datetime.utcnow().isoformat() + "Z",
        "event": "pipeline_start",
        "pid":   os.getpid(),
        "resuming_from": already_embedded,
        "sources": ACTIVE_SOURCES,
    }
    log_file = LOGS / "orchestrator.jsonl"
    log_file.parent.mkdir(exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    # Pre-start cleanup: kill any leftover workers from a previous run.
    # See _kill_zombie_workers docstring for context.
    _kill_zombie_workers()

    already_embedded = _read_checkpoint_count()
    _write_start_time()
    _write_pid()
    _log_start(already_embedded)

    if already_embedded > 0:
        print(f"[ORCH] Resuming from {already_embedded:,} embedded records")
        _post_slack(
            f":arrows_counterclockwise: *Pipeline restarted* — resuming from "
            f"{already_embedded:,} embedded records. "
            f"Sources: {', '.join(ACTIVE_SOURCES)}"
        )
    else:
        print("[ORCH] Fresh start — targeting 50M records in 60 days")
        _post_slack(
            ":rocket: *OpenGenealogyAI pipeline started* — targeting 50M records in 60 days.\n"
            f"Active sources: {', '.join(ACTIVE_SOURCES)}"
        )

    group = ProcessGroup()

    # Core monitoring (always-on)
    group.add("checker",  _run_checker)
    group.add("reporter", _run_reporter)
    group.add("reviewer", _run_reviewer)   # daily Sonnet review + RESUME.md update

    # Workers
    group.add("gpu_worker",  _run_gpu_worker)
    group.add("cpu_workers", _run_cpu_workers)

    # Scrapers (one process per source)
    for source in ACTIVE_SOURCES:
        group.add(f"scraper:{source}", _run_scraper, args=(source,))

    # Graceful shutdown
    shutdown = Event()

    def _on_signal(sig, frame):
        print("\n[ORCH] Shutdown signal received — stopping all processes...")
        shutdown.set()

    signal.signal(signal.SIGINT,  _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    print(f"[ORCH] All systems running. PID={os.getpid()}. Press Ctrl+C to stop.")

    try:
        while not shutdown.is_set():
            group.watchdog_tick()
            time.sleep(30)
    finally:
        group.terminate_all()
        final_count = _read_checkpoint_count()
        msg = (
            f":octagonal_sign: *Pipeline stopped cleanly* — "
            f"{final_count:,} records embedded at shutdown."
        )
        _post_slack(msg)
        print(f"[ORCH] Shutdown complete. {final_count:,} records embedded.")

        log_file = LOGS / "orchestrator.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts":    datetime.datetime.utcnow().isoformat() + "Z",
                "event": "pipeline_stop",
                "total_embedded": final_count,
            }) + "\n")

        if PID_FILE.exists():
            PID_FILE.unlink()


if __name__ == "__main__":
    main()
