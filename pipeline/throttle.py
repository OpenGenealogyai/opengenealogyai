"""
throttle.py — per-session throttle reader/writer (v3, 0-10 scale)

Four dials:
  internet — downloads, scrapers, web fetches
  gpu      — local GPU inference (Ollama, embeddings)
  cpu      — background worker process priority
  claude   — optional Anthropic API spend (councils, subagents, reviews)

0 = fully OFF/paused   10 = full speed   5 = half speed
Missing file = all 10 (full speed — opt-in design)
"""

import json
import os
import time
import tempfile
import datetime
from pathlib import Path

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

THROTTLE_FILE = Path(__file__).parent.parent / "_throttle" / "throttle.json"
ACTIVE_PIDS_FILE = THROTTLE_FILE.parent / "active_pids.json"

DEFAULTS = {"internet": 10, "gpu": 10, "cpu": 10, "claude": 10}

# Cache: (timestamp, dict)
_cache: tuple = (0.0, {})
_CACHE_TTL = 2.0  # seconds

# Sleep tables: index = level, value = seconds to sleep
# Index 0 = None (block/pause). Index 10 = 0 (no sleep).
INTERNET_SLEEP = [None, 15, 10, 5, 2, 1, 0.5, 0.3, 0.1, 0.05, 0]
GPU_SLEEP      = [None, 8,  5,  2, 1, 0.5, 0.3, 0.2, 0.1, 0.05, 0]


def read_throttle() -> dict:
    """Read and validate throttle.json. Never raises. Falls back to DEFAULTS on any error.
    2-second disk cache. Clamps all values to 0-10 int."""
    global _cache
    now = time.monotonic()
    ts, cached = _cache
    if cached and (now - ts) < _CACHE_TTL:
        return dict(cached)

    try:
        with open(THROTTLE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = {}
        for key, default in DEFAULTS.items():
            try:
                val = int(data.get(key, default))
            except (TypeError, ValueError):
                val = default
            result[key] = max(0, min(10, val))
    except Exception:
        result = dict(DEFAULTS)

    _cache = (now, result)
    return dict(result)


def _invalidate_cache() -> None:
    global _cache
    _cache = (0.0, {})


def write_throttle(**kwargs) -> None:
    """Atomic write via temp file + os.replace(). Merges with current values.
    Only updates keys passed in kwargs that are in DEFAULTS.
    Adds updated_at (ISO timestamp) and updated_by (from kwargs, default 'skill-write')."""
    updated_by = kwargs.pop("updated_by", "skill-write")

    # Read current values first
    try:
        with open(THROTTLE_FILE, "r", encoding="utf-8") as f:
            current = json.load(f)
    except Exception:
        current = dict(DEFAULTS)

    # Merge only known dial keys
    for key in DEFAULTS:
        if key in kwargs:
            try:
                val = int(kwargs[key])
            except (TypeError, ValueError):
                continue
            current[key] = max(0, min(10, val))

    current["updated_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    current["updated_by"] = updated_by

    # Atomic write via temp file
    THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=THROTTLE_FILE.parent, prefix=".throttle_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        os.replace(tmp_path, THROTTLE_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    _invalidate_cache()


# ── accessor functions ─────────────────────────────────────────────────────────

def internet_level() -> int:
    """Returns current internet throttle level (0-10)."""
    return read_throttle()["internet"]


def gpu_level() -> int:
    """Returns current GPU throttle level (0-10)."""
    return read_throttle()["gpu"]


def cpu_level() -> int:
    """Returns current CPU throttle level (0-10)."""
    return read_throttle()["cpu"]


def claude_level() -> int:
    """Returns current Claude API throttle level (0-10)."""
    return read_throttle()["claude"]


# ── wait helpers ───────────────────────────────────────────────────────────────

def wait_for_internet() -> None:
    """Sleep per internet level mapping. If level 0, loops until level > 0."""
    while True:
        lvl = internet_level()
        if lvl == 0:
            print("[THROTTLE] Internet paused (level 0) — waiting...", flush=True)
            time.sleep(2)
            _invalidate_cache()
            continue
        s = INTERNET_SLEEP[lvl]
        if s and s > 0:
            time.sleep(s)
        return


def wait_for_gpu() -> None:
    """Sleep per GPU level mapping. If level 0, loops until level > 0."""
    while True:
        lvl = gpu_level()
        if lvl == 0:
            print("[THROTTLE] GPU paused (level 0) — waiting...", flush=True)
            time.sleep(2)
            _invalidate_cache()
            continue
        s = GPU_SLEEP[lvl]
        if s and s > 0:
            time.sleep(s)
        return


# ── concurrency helper ─────────────────────────────────────────────────────────

def internet_concurrency() -> int:
    """Returns max concurrent fetcher processes for current internet level.
    0→0, 1→1, 2→1, 3→1, 4→2, 5→2, 6→3, 7→3, 8→4, 9→4, 10→999"""
    _CONCURRENCY = [0, 1, 1, 1, 2, 2, 3, 3, 4, 4, 999]
    lvl = internet_level()
    return _CONCURRENCY[lvl]


# ── claude spend gate ──────────────────────────────────────────────────────────

def claude_allowed(operation: str = "general_api") -> bool:
    """Gate for Anthropic API spend.

    operation: 'council' | 'subagent' | 'big_goal_review' | 'general_api'

    lvl 0             → False always
    'council',
    'subagent'        → lvl >= 4
    'big_goal_review' → lvl >= 2
    'general_api'     → lvl >= 2
    """
    lvl = claude_level()
    if lvl == 0:
        return False
    if operation in ("council", "subagent"):
        return lvl >= 4
    # big_goal_review and general_api
    return lvl >= 2


# ── PID registry ───────────────────────────────────────────────────────────────

def register_pid(label: str = "") -> None:
    """Write current process PID to active_pids.json with label + registered_at."""
    if not _PSUTIL:
        return
    pid = os.getpid()
    try:
        try:
            with open(ACTIVE_PIDS_FILE, "r", encoding="utf-8") as f:
                pids = json.load(f)
        except Exception:
            pids = {}
        pids[str(pid)] = {
            "label": label,
            "registered_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        ACTIVE_PIDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=ACTIVE_PIDS_FILE.parent, prefix=".pids_tmp_", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(pids, f, indent=2)
            os.replace(tmp_path, ACTIVE_PIDS_FILE)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:
        pass  # never raise from pid registration


def apply_cpu_throttle() -> None:
    """Read active_pids.json and apply Windows priority class per cpu level.
    Auto-removes stale PIDs. Silently skips if psutil not available.

    Priority map:
      cpu 0-1  → IDLE_PRIORITY_CLASS
      cpu 2-3  → BELOW_NORMAL_PRIORITY_CLASS
      cpu 4-10 → NORMAL_PRIORITY_CLASS (never elevate above normal)
    """
    if not _PSUTIL:
        return
    lvl = cpu_level()
    if lvl <= 1:
        priority = psutil.IDLE_PRIORITY_CLASS
    elif lvl <= 3:
        priority = psutil.BELOW_NORMAL_PRIORITY_CLASS
    else:
        priority = psutil.NORMAL_PRIORITY_CLASS

    try:
        with open(ACTIVE_PIDS_FILE, "r", encoding="utf-8") as f:
            pids = json.load(f)
    except Exception:
        return

    stale = []
    for pid_str in list(pids.keys()):
        try:
            pid = int(pid_str)
            proc = psutil.Process(pid)
            proc.nice(priority)
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
            stale.append(pid_str)
        except Exception:
            pass

    if stale:
        for pid_str in stale:
            pids.pop(pid_str, None)
        try:
            ACTIVE_PIDS_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=ACTIVE_PIDS_FILE.parent, prefix=".pids_tmp_", suffix=".json"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(pids, f, indent=2)
                os.replace(tmp_path, ACTIVE_PIDS_FILE)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception:
            pass


# ── status line ────────────────────────────────────────────────────────────────

def status_line() -> str:
    """Returns a single readable status line."""
    t = read_throttle()
    return (
        f"Throttle: internet={t['internet']}  gpu={t['gpu']}  "
        f"cpu={t['cpu']}  claude={t['claude']}"
    )
