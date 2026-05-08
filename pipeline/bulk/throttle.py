"""
Pipeline-monitor session throttle reader.

Independent of pipeline.throttle (which the build-genealogy-open-source-ai
session owns). Reads a session-specific control file so user can throttle
this session without affecting the other session.

API is intentionally compatible with pipeline.throttle so workers swap
imports cleanly.

Control file:  _throttle/pipeline-monitor.json
Owner:         pipeline-monitor session
Schema:        {internet, gpu, cpu, claude}  — values 0-10
Defaults:      all 10 (full speed)
0 = paused, 10 = full speed; see throttle-skill v3 for graduations.
"""

import json
import time
import datetime
from pathlib import Path

# Repo root (parent of pipeline/) → _throttle/
THROTTLE_FILE = Path(__file__).parent.parent.parent / "_throttle" / "pipeline-monitor.json"

DEFAULTS = {"internet": 10, "gpu": 10, "cpu": 10, "claude": 10}

# Cache: avoid hammering disk every record (140k+ records/min in ingest)
_cache: tuple[float, dict] | None = None
_CACHE_TTL = 2.0   # seconds

# Sleep tables — index = level (0 → blocked, 10 → no sleep). v3 spec.
_INTERNET_SLEEP = [None, 15.0, 10.0, 5.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.0]
_GPU_SLEEP      = [None,  8.0,  5.0, 2.0, 1.0, 0.5, 0.3, 0.2, 0.1, 0.05, 0.0]


def _read_raw() -> dict:
    """Read + validate. Never raises. Returns dict with all 4 keys."""
    global _cache
    now = time.monotonic()
    if _cache is not None:
        ts, cached = _cache
        if now - ts < _CACHE_TTL:
            return dict(cached)

    try:
        with open(THROTTLE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = {}
        for k, default in DEFAULTS.items():
            v = int(data.get(k, default))
            v = max(0, min(10, v))
            result[k] = v
    except Exception:
        result = dict(DEFAULTS)

    _cache = (now, result)
    return dict(result)


def _invalidate_cache() -> None:
    global _cache
    _cache = None


def read_throttle() -> dict:
    return _read_raw()


def internet_level() -> int: return _read_raw()["internet"]
def gpu_level()      -> int: return _read_raw()["gpu"]
def cpu_level()      -> int: return _read_raw()["cpu"]
def claude_level()   -> int: return _read_raw()["claude"]


def wait_for_internet() -> None:
    """Sleep per internet level. If level 0, blocks until raised."""
    while True:
        level = internet_level()
        sleep_s = _INTERNET_SLEEP[level]
        if sleep_s is None:   # level 0 — paused
            time.sleep(2.0)
            _invalidate_cache()
            continue
        if sleep_s > 0:
            time.sleep(sleep_s)
        return


def wait_for_gpu() -> None:
    """Sleep per gpu level. If level 0, blocks until raised."""
    while True:
        level = gpu_level()
        sleep_s = _GPU_SLEEP[level]
        if sleep_s is None:   # level 0 — paused
            time.sleep(2.0)
            _invalidate_cache()
            continue
        if sleep_s > 0:
            time.sleep(sleep_s)
        return


def write_throttle(**kwargs) -> None:
    """Atomically update one or more dials. Use sparingly — typically the user's lever."""
    THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    current = _read_raw()
    for k, v in kwargs.items():
        if k in DEFAULTS:
            current[k] = max(0, min(10, int(v)))
    current["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    current["updated_by"] = kwargs.get("updated_by", "pipeline-monitor")

    tmp = THROTTLE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current, indent=2), encoding="utf-8")
    tmp.replace(THROTTLE_FILE)
    _invalidate_cache()


def status_line() -> str:
    t = _read_raw()
    return (f"PM-Throttle: internet={t['internet']} gpu={t['gpu']} "
            f"cpu={t['cpu']} claude={t['claude']}")
