"""
Pipeline Monitor — hourly metrics report.

Runs as a standalone process (NOT a child of the orchestrator) so it keeps
recording even if the orchestrator dies.

Samples GPU util + CPU util + RSS every 60s into a 1-hour ring buffer.
Every 60 min on the wall clock, writes one ✅ or ⚠️ row to:
  rawdata/_logs/hourly_reports.md

Run: python -m pipeline.monitor

Stop: Ctrl+C — flushes a final row before exit.
"""

import os, sys, time, datetime, signal, sqlite3
from collections import deque
from pathlib import Path

import psutil
import requests

from pipeline.paths import LOGS, CHECKPOINTS

# Reconfigure stdout to UTF-8 so emoji prints don't crash on Windows cp1252.
# Belt and suspenders: also wrap print calls below in try/except.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def safe_print(msg: str):
    """Print that never crashes the process on encoding errors."""
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"), flush=True)
        except Exception:
            pass

REPORT_FILE   = LOGS / "hourly_reports.md"
PID_FILE      = LOGS / "monitor.pid"
ORCH_PID_FILE = LOGS / "orchestrator.pid"
START_FILE    = LOGS / "pipeline_start.txt"
QDRANT_URL    = "http://localhost:6333"
COLLECTION    = "raw_records_v01"
DB_PATH       = CHECKPOINTS / "pipeline.db"

SAMPLE_INTERVAL_S = 60
REPORT_INTERVAL_S = 60 * 60      # one hour
GPU_LOW_THRESHOLD = 40           # % — below this is ⚠️ if queue > 1000

# Ring buffer for samples — 1 hour at 60s = 60 entries
_samples = deque(maxlen=60)

# pynvml setup — fall back to nvidia-smi subprocess if unavailable
_NVML = None
try:
    import pynvml
    pynvml.nvmlInit()
    _NVML = pynvml.nvmlDeviceGetHandleByIndex(0)
except Exception as e:
    safe_print(f"[MONITOR] pynvml unavailable ({e}); will use nvidia-smi fallback")


def _gpu_util_percent() -> int:
    if _NVML:
        try:
            return pynvml.nvmlDeviceGetUtilizationRates(_NVML).gpu
        except Exception:
            pass
    # Fallback
    import subprocess
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return int(out.stdout.strip().split("\n")[0])
    except Exception:
        return 0


def _cpu_percent() -> float:
    return psutil.cpu_percent(interval=None)


def _system_ram_used_gb() -> float:
    return psutil.virtual_memory().used / 1024**3


def _embedded_count() -> int:
    if not DB_PATH.exists():
        return 0
    try:
        con = sqlite3.connect(str(DB_PATH))
        n = con.execute("SELECT COUNT(*) FROM records WHERE status='embedded'").fetchone()[0]
        con.close()
        return n
    except Exception:
        return 0


def _downloaded_count() -> int:
    """Total rows in the records table — anything we've at least fetched."""
    if not DB_PATH.exists():
        return 0
    try:
        con = sqlite3.connect(str(DB_PATH))
        n = con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        con.close()
        return n
    except Exception:
        return 0


def _qdrant_points() -> int:
    try:
        r = requests.get(f"{QDRANT_URL}/collections/{COLLECTION}", timeout=5)
        return r.json().get("result", {}).get("points_count", 0)
    except Exception:
        return -1   # signals Qdrant DOWN


def _orchestrator_state() -> tuple[str, str]:
    """Return (state_str, uptime_str)."""
    if not ORCH_PID_FILE.exists():
        return ("DOWN", "—")
    try:
        pid = int(ORCH_PID_FILE.read_text().strip())
        if not psutil.pid_exists(pid):
            return ("DOWN", "—")
        if not START_FILE.exists():
            return ("RUNNING", "?")
        start = datetime.datetime.fromisoformat(START_FILE.read_text().strip())
        uptime = datetime.datetime.utcnow() - start
        h, rem = divmod(uptime.total_seconds(), 3600)
        m = rem // 60
        return ("RUNNING", f"{int(h)}h {int(m)}m")
    except Exception:
        return ("UNKNOWN", "—")


def _embed_queue_size() -> int:
    qdir = CHECKPOINTS / "embed_queue"
    if not qdir.exists():
        return 0
    try:
        n = 0
        for _ in qdir.iterdir():
            n += 1
            if n > 200_000:   # cheap cap
                break
        return n
    except Exception:
        return 0


# ── Sampling + report writing ─────────────────────────────────────────────────
def take_sample():
    s = {
        "t":   time.time(),
        "cpu": _cpu_percent(),
        "gpu": _gpu_util_percent(),
        "ram_used_gb": _system_ram_used_gb(),
    }
    _samples.append(s)
    return s


_last_report_embedded = None
_last_report_downloaded = None


def write_report():
    global _last_report_embedded, _last_report_downloaded

    LOGS.mkdir(parents=True, exist_ok=True)

    embedded   = _embedded_count()
    downloaded = _downloaded_count()
    qdrant_pts = _qdrant_points()
    qsize      = _embed_queue_size()
    state, uptime = _orchestrator_state()

    delta_emb = embedded - _last_report_embedded if _last_report_embedded is not None else 0
    delta_dl  = downloaded - _last_report_downloaded if _last_report_downloaded is not None else 0

    if _samples:
        cpu_avg = sum(s["cpu"] for s in _samples) / len(_samples)
        gpu_avg = sum(s["gpu"] for s in _samples) / len(_samples)
        ram_avg = sum(s["ram_used_gb"] for s in _samples) / len(_samples)
    else:
        cpu_avg = gpu_avg = ram_avg = 0.0

    # Decide ✅ vs ⚠️
    alert = False
    alert_reasons = []
    if state != "RUNNING":
        alert = True; alert_reasons.append(f"orchestrator {state}")
    if gpu_avg < GPU_LOW_THRESHOLD and qsize > 1000:
        alert = True; alert_reasons.append(f"GPU underutilized ({gpu_avg:.0f}% with {qsize:,} queued)")
    if qdrant_pts == -1:
        alert = True; alert_reasons.append("Qdrant DOWN")

    mark = "⚠️" if alert else "✅"
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"## {ts}",
        f"- {mark} Total embedded:    {embedded:>10,}  (+{delta_emb:,} this hour)",
        f"- {mark} Total downloaded:  {downloaded:>10,}  (+{delta_dl:,} this hour)",
        f"- {mark} Qdrant points:     {qdrant_pts:>10,}",
        f"- {mark} Embed queue:       {qsize:>10,}",
        f"- {mark} CPU avg:           {cpu_avg:>10.0f}%",
        f"- {mark} GPU avg:           {gpu_avg:>10.0f}%",
        f"- {mark} RAM used (system): {ram_avg:>10.1f} GB",
        f"- {mark} Throughput (last hr): {delta_emb:,} records/hr",
        f"- {mark} Pipeline state:    {state} (uptime {uptime})",
    ]
    if alert_reasons:
        lines.append(f"- ⚠️ Issues: {'; '.join(alert_reasons)}")
    lines.append("")

    # Append to report file
    with open(REPORT_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Use ASCII tag in stdout to avoid Windows cp1252 codec errors;
    # the file write above is UTF-8 with full emoji.
    ascii_mark = "WARN" if alert else "OK"
    safe_print(f"[MONITOR] Wrote report at {ts} ({ascii_mark})")
    _last_report_embedded = embedded
    _last_report_downloaded = downloaded


def write_header_if_new():
    if not REPORT_FILE.exists() or REPORT_FILE.stat().st_size == 0:
        REPORT_FILE.write_text(
            "# Pipeline Hourly Reports\n\n"
            "✅ = healthy · ⚠️ = needs attention\n\n",
            encoding="utf-8",
        )


# ── Main loop ─────────────────────────────────────────────────────────────────
_stop = False
def _sigint(signum, frame):
    global _stop
    _stop = True


def main():
    signal.signal(signal.SIGINT, _sigint)
    LOGS.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    write_header_if_new()

    safe_print(f"[MONITOR] Started -- PID {os.getpid()}")
    safe_print(f"[MONITOR] Report file: {REPORT_FILE}")
    safe_print(f"[MONITOR] Sample every {SAMPLE_INTERVAL_S}s, report every {REPORT_INTERVAL_S}s")

    # Prime baseline counts at startup
    global _last_report_embedded, _last_report_downloaded
    _last_report_embedded = _embedded_count()
    _last_report_downloaded = _downloaded_count()
    psutil.cpu_percent(interval=None)   # prime non-blocking cpu_percent

    last_report = time.time()
    last_sample = 0.0

    while not _stop:
        now = time.time()
        if now - last_sample >= SAMPLE_INTERVAL_S:
            take_sample()
            last_sample = now
        if now - last_report >= REPORT_INTERVAL_S:
            write_report()
            last_report = now
        time.sleep(2)

    # Flush a final report on Ctrl+C
    safe_print("[MONITOR] Stopping -- writing final report")
    write_report()


if __name__ == "__main__":
    main()
