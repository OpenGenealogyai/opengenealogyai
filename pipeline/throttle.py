"""
Throttle control for OpenGenealogyAI pipeline.

Two independent 1-10 controls:
  gpu      — embedding batch speed (1=pause, 10=full speed)
  internet — download bandwidth (1=pause, 10=full speed)

Workers call wait_for_gpu() / wait_for_internet() at natural yield points.
Control file is _throttle/throttle.json — CLI writes it atomically.
Missing or corrupt file → safe default of 5 (half speed).
"""

import json
import os
import time
import tempfile
from pathlib import Path

THROTTLE_FILE = Path(__file__).parent.parent / "_throttle" / "throttle.json"

DEFAULTS = {"gpu": 5, "internet": 5}

# Cache: (timestamp, dict)
_cache: tuple[float, dict] | None = None
_CACHE_TTL = 2.0  # seconds

# GPU level → inter-batch sleep seconds (-1 = pause)
_GPU_SLEEP = {
    1: -1,    # PAUSE
    2: 10.0,
    3: 7.0,
    4: 5.0,
    5: 3.0,
    6: 2.0,
    7: 1.0,
    8: 0.5,
    9: 0.1,
    10: 0.0,
}

# Internet level → per-request sleep seconds (-1 = pause)
_INTERNET_SLEEP = {
    1: -1,    # PAUSE
    2: 5.0,
    3: 3.0,
    4: 2.0,
    5: 1.5,
    6: 1.0,
    7: 0.5,
    8: 0.25,
    9: 0.05,
    10: 0.0,
}

# Internet level → max concurrent fetcher processes
_INTERNET_CONCURRENCY = {
    1: 0,
    2: 1,
    3: 1,
    4: 2,
    5: 2,
    6: 3,
    7: 3,
    8: 4,
    9: 4,
    10: 999,  # unlimited
}


def read_throttle() -> dict:
    """Read and validate throttle.json. Never raises. Falls back to defaults on any error.
    Caches the result for 2 seconds to avoid hammering disk."""
    global _cache
    now = time.monotonic()
    if _cache is not None:
        ts, cached = _cache
        if now - ts < _CACHE_TTL:
            return dict(cached)

    try:
        with open(THROTTLE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        gpu = int(data.get("gpu", DEFAULTS["gpu"]))
        internet = int(data.get("internet", DEFAULTS["internet"]))
        if not (1 <= gpu <= 10):
            gpu = DEFAULTS["gpu"]
        if not (1 <= internet <= 10):
            internet = DEFAULTS["internet"]
        result = {"gpu": gpu, "internet": internet}
    except Exception:
        result = dict(DEFAULTS)

    _cache = (now, result)
    return dict(result)


def _invalidate_cache() -> None:
    global _cache
    _cache = None


def gpu_level() -> int:
    """Returns current GPU throttle level (1-10)."""
    return read_throttle()["gpu"]


def internet_level() -> int:
    """Returns current Internet throttle level (1-10)."""
    return read_throttle()["internet"]


def internet_concurrency() -> int:
    """Returns max concurrent fetcher processes for current internet level."""
    level = internet_level()
    return _INTERNET_CONCURRENCY.get(level, 2)


def wait_for_gpu() -> None:
    """Sleep per GPU level mapping. If level 1, loops until level > 1."""
    level = gpu_level()
    sleep_s = _GPU_SLEEP.get(level, 3.0)

    if sleep_s == -1:
        print("[THROTTLE] GPU paused (level 1) — waiting...")
        while True:
            time.sleep(2.0)
            _invalidate_cache()
            level = gpu_level()
            if level > 1:
                print("[THROTTLE] GPU resumed (level {}) — continuing.".format(level))
                sleep_s = _GPU_SLEEP.get(level, 3.0)
                break
        # Fall through to sleep at new level
        if sleep_s > 0:
            time.sleep(sleep_s)
    elif sleep_s > 0:
        time.sleep(sleep_s)


def wait_for_internet() -> None:
    """Sleep per Internet level mapping. If level 1, loops until level > 1."""
    level = internet_level()
    sleep_s = _INTERNET_SLEEP.get(level, 1.5)

    if sleep_s == -1:
        print("[THROTTLE] Internet paused (level 1) — waiting...")
        while True:
            time.sleep(2.0)
            _invalidate_cache()
            level = internet_level()
            if level > 1:
                print("[THROTTLE] Internet resumed (level {}) — continuing.".format(level))
                sleep_s = _INTERNET_SLEEP.get(level, 1.5)
                break
        if sleep_s > 0:
            time.sleep(sleep_s)
    elif sleep_s > 0:
        time.sleep(sleep_s)


def write_throttle(gpu: int | None = None, internet: int | None = None) -> None:
    """Atomically write throttle.json. Only updates keys that are passed.
    Records updated_by='garlon-cli' and updated_at timestamp."""
    from datetime import datetime

    # Read current values first
    try:
        with open(THROTTLE_FILE, "r", encoding="utf-8") as f:
            current = json.load(f)
    except Exception:
        current = dict(DEFAULTS)

    # Merge
    if gpu is not None:
        current["gpu"] = int(gpu)
    if internet is not None:
        current["internet"] = int(internet)
    current["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    current["updated_by"] = "garlon-cli"

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


def status_line() -> str:
    """Returns a single readable status line."""
    t = read_throttle()
    g = t["gpu"]
    i = t["internet"]

    g_sleep = _GPU_SLEEP.get(g, 3.0)
    i_sleep = _INTERNET_SLEEP.get(i, 1.5)
    i_conc = _INTERNET_CONCURRENCY.get(i, 2)

    if g_sleep == -1:
        gpu_desc = "PAUSED"
    elif g_sleep == 0.0:
        gpu_desc = "0.0s/batch"
    else:
        gpu_desc = f"{g_sleep}s/batch"

    if i_sleep == -1:
        inet_desc = "PAUSED"
    elif i_sleep == 0.0:
        inet_desc = "0.0s/req, {} concurrent".format(i_conc)
    else:
        inet_desc = f"{i_sleep}s/req, {i_conc} concurrent"

    return f"Throttle: GPU={g} ({gpu_desc}) | Internet={i} ({inet_desc})"
