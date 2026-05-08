"""
Pipeline Health Checker — runs every 10 minutes.

Checks:
  - Records processed since last check
  - GPU worker heartbeat
  - CPU worker pool status
  - Active scraper sources
  - Disk space
  - Error rate
  - Qdrant collection size

Writes one-line JSON to _logs/checker.jsonl.
Triggers DIY recovery on failures.
Feeds the hourly Reporter.
"""

import json, datetime, os, sqlite3, shutil, time
from pathlib import Path
import requests

from pipeline.paths import LOGS, CHECKPOINTS, QDRANT_PATH, _BASE as RAW_BASE
from pipeline.api_guard import status_report as _api_status

CHECKER_LOG   = LOGS / "checker.jsonl"
HEARTBEAT_FILE = LOGS / "gpu_heartbeat.json"
CHECKPOINT_DB  = CHECKPOINTS / "pipeline.db"
OLLAMA_URL     = "http://localhost:11434"
QDRANT_URL     = "http://localhost:6333"

DISK_WARN_GB   = 200
DISK_PAUSE_GB  = 50
ERROR_RATE_WARN = 5.0   # percent


def _total_embedded() -> int:
    """Count records with status='embedded' in checkpoint DB."""
    if not CHECKPOINT_DB.exists():
        return 0
    try:
        con = sqlite3.connect(CHECKPOINT_DB)
        cur = con.execute("SELECT COUNT(*) FROM records WHERE status='embedded'")
        return cur.fetchone()[0]
    except Exception:
        return 0


def _records_since(since_ts: str) -> int:
    """Count records embedded after since_ts."""
    if not CHECKPOINT_DB.exists():
        return 0
    try:
        con = sqlite3.connect(CHECKPOINT_DB)
        cur = con.execute(
            "SELECT COUNT(*) FROM records WHERE status='embedded' AND embedded_at > ?",
            (since_ts,)
        )
        return cur.fetchone()[0]
    except Exception:
        return 0


def _gpu_alive() -> bool:
    """Check GPU worker heartbeat — last embed within 3 minutes."""
    if not HEARTBEAT_FILE.exists():
        return False
    try:
        data = json.loads(HEARTBEAT_FILE.read_text())
        last = datetime.datetime.fromisoformat(data.get("last_embed", "2000-01-01"))
        return (datetime.datetime.utcnow() - last).total_seconds() < 180
    except Exception:
        return False


def _ollama_alive() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _qdrant_count() -> int:
    """Get actual count from Qdrant collection if running."""
    try:
        r = requests.get(f"{QDRANT_URL}/collections/raw_records_v01", timeout=5)
        if r.status_code == 200:
            return r.json().get("result", {}).get("vectors_count", 0)
    except Exception:
        pass
    return _total_embedded()   # fallback to DB count


def _disk_free_gb() -> float:
    total, used, free = shutil.disk_usage(str(RAW_BASE))
    return free / (1024 ** 3)


def _active_sources() -> list[str]:
    """Which source folders have been modified in the last 15 minutes."""
    cutoff = time.time() - 900
    active = []
    for folder in RAW_BASE.iterdir():
        if folder.is_dir() and not folder.name.startswith("_"):
            try:
                mtime = max(f.stat().st_mtime for f in folder.rglob("*") if f.is_file())
                if mtime > cutoff:
                    active.append(folder.name)
            except ValueError:
                pass
    return active


def _error_rate_pct() -> float:
    """Error rate from last 10 minutes of checker log."""
    if not CHECKER_LOG.exists():
        return 0.0
    lines = CHECKER_LOG.read_text(encoding="utf-8").splitlines()[-2:]
    if len(lines) < 2:
        return 0.0
    try:
        prev = json.loads(lines[0])
        curr = json.loads(lines[1])
        delta_records = (curr.get("total_embedded", 0) - prev.get("total_embedded", 0))
        delta_errors  = (curr.get("total_errors", 0)   - prev.get("total_errors", 0))
        if delta_records + delta_errors == 0:
            return 0.0
        return round(delta_errors / (delta_records + delta_errors) * 100, 2)
    except Exception:
        return 0.0


def _determine_status(gpu_alive, disk_gb, error_rate, records_10m) -> str:
    if disk_gb < DISK_PAUSE_GB:
        return "CRITICAL"
    if not gpu_alive:
        return "ERROR"
    if disk_gb < DISK_WARN_GB:
        return "WARN_DISK"
    if error_rate > ERROR_RATE_WARN:
        return "WARN_ERRORS"
    if records_10m == 0:
        return "STALLED"
    return "OK"


def _log(entry: dict):
    CHECKER_LOG.parent.mkdir(exist_ok=True)
    with open(CHECKER_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def run_check() -> dict:
    """Run a single health check cycle. Returns the health entry."""
    now = datetime.datetime.utcnow()
    ten_min_ago = (now - datetime.timedelta(minutes=10)).isoformat()

    total_embedded  = _total_embedded()
    records_10m     = _records_since(ten_min_ago)
    gpu_alive       = _gpu_alive()
    ollama_alive    = _ollama_alive()
    active_sources  = _active_sources()
    disk_gb         = _disk_free_gb()
    error_rate      = _error_rate_pct()
    qdrant_count    = _qdrant_count()
    status          = _determine_status(gpu_alive, disk_gb, error_rate, records_10m)
    api_guard       = _api_status()

    # Hourly throughput estimate
    records_per_hr = records_10m * 6
    remaining = max(0, 50_000_000 - total_embedded)
    eta_days = round(remaining / records_per_hr / 24, 1) if records_per_hr > 0 else None

    entry = {
        "ts":               now.isoformat() + "Z",
        "records_last_10m": records_10m,
        "records_per_hr":   records_per_hr,
        "total_embedded":   total_embedded,
        "qdrant_count":     qdrant_count,
        "gpu_alive":        gpu_alive,
        "ollama_alive":     ollama_alive,
        "active_sources":   active_sources,
        "disk_gb_free":     round(disk_gb, 1),
        "error_rate_pct":   error_rate,
        "eta_days":         eta_days,
        "status":           status,
        # Claude API rate-limit tracking
        "claude_paused":    api_guard["claude_paused"],
        "claude_daily_pct": api_guard["daily_pct"],
        "claude_window_pct": api_guard.get("window_used_pct", 0),
        "claude_reset_at":  api_guard.get("window_reset_at", ""),
    }
    _log(entry)

    api_note = f"  claude={'PAUSED' if api_guard['claude_paused'] else 'OK'} ({api_guard['daily_pct']:.0f}%/day)"
    print(f"[CHECK {now.strftime('%H:%M')}] {status}  "
          f"embedded={total_embedded:,}  +{records_10m}/10m  "
          f"gpu={'OK' if gpu_alive else 'DOWN'}  "
          f"disk={disk_gb:.0f}GB  err={error_rate:.1f}%{api_note}")

    return entry


def run_loop(interval_seconds: int = 600):
    """Run checker forever, every interval_seconds."""
    print(f"[CHECKER] Starting — checking every {interval_seconds//60} minutes")
    _was_paused = False
    while True:
        try:
            # Auto-resume: calling is_paused() clears the flag if reset time passed
            from pipeline.api_guard import is_paused as _api_paused
            now_paused = _api_paused()
            if _was_paused and not now_paused:
                print("[CHECKER] Claude API window reset — council back to 3-model mode")
            _was_paused = now_paused

            entry = run_check()
            if entry["status"] in ("CRITICAL", "ERROR", "STALLED"):
                _trigger_recovery(entry)
        except Exception as e:
            print(f"[CHECKER ERROR] {e}")
        time.sleep(interval_seconds)


def _trigger_recovery(entry: dict):
    """Attempt DIY recovery based on status."""
    status = entry["status"]
    print(f"[RECOVERY] Triggering recovery for: {status}")

    if status == "STALLED" and not entry["gpu_alive"]:
        # Try restarting Ollama
        print("[RECOVERY] Attempting Ollama restart...")
        os.system("ollama serve &")
        time.sleep(10)

    elif status == "CRITICAL":
        # Disk critically low — pause downloads
        print("[RECOVERY] CRITICAL disk — signaling download pause")
        pause_file = LOGS / "PAUSE_DOWNLOADS"
        pause_file.write_text("disk_critical")

    elif status == "WARN_ERRORS":
        print("[RECOVERY] High error rate — logging for review")
        # Error rate issues are logged; Reporter will surface them


if __name__ == "__main__":
    run_loop()
