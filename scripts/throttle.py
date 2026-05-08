"""
CLI throttle control for OpenGenealogyAI pipeline.

Usage:
    python scripts/throttle.py status
    python scripts/throttle.py gpu 6
    python scripts/throttle.py internet 1
    python scripts/throttle.py gpu 10 internet 8
"""

import sys
from pathlib import Path

# Make sure pipeline package is importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.throttle import (
    write_throttle,
    status_line,
    read_throttle,
    _GPU_SLEEP,
    _INTERNET_SLEEP,
    _INTERNET_CONCURRENCY,
)

# ── human-readable descriptions ──────────────────────────────────────────────

def _gpu_desc(level: int) -> str:
    sleep = _GPU_SLEEP.get(level, 3.0)
    if sleep == -1:
        return "PAUSED — no batches will run"
    if sleep == 0.0:
        return "no sleep between embedding batches (full speed)"
    return f"{sleep}s sleep between embedding batches"


def _internet_desc(level: int) -> str:
    sleep = _INTERNET_SLEEP.get(level, 1.5)
    conc = _INTERNET_CONCURRENCY.get(level, 2)
    if sleep == -1:
        return "PAUSED — no downloads will run"
    conc_str = "unlimited" if conc == 999 else str(conc)
    if sleep == 0.0:
        return f"no sleep between requests, up to {conc_str} concurrent fetchers"
    return f"{sleep}s between requests, up to {conc_str} concurrent fetchers"


# ── status command ────────────────────────────────────────────────────────────

def cmd_status() -> None:
    t = read_throttle()
    g = t["gpu"]
    i = t["internet"]

    g_sleep = _GPU_SLEEP.get(g, 3.0)
    i_sleep = _INTERNET_SLEEP.get(i, 1.5)
    i_conc = _INTERNET_CONCURRENCY.get(i, 2)

    if g_sleep == -1:
        g_detail = "PAUSED"
    else:
        g_detail = f"{g_sleep}s sleep between embedding batches"

    if i_sleep == -1:
        i_detail = "PAUSED"
    else:
        i_conc_str = "unlimited" if i_conc == 999 else str(i_conc)
        i_detail = f"{i_sleep}s between requests, up to {i_conc_str} concurrent fetchers"

    print("=== Pipeline Throttle Status ===")
    print(f"GPU:      {g}/10  — {g_detail}")
    print(f"Internet: {i}/10  — {i_detail}")
    print()
    print("GPU levels:")
    print("  1 = PAUSED (use for local model work)")
    print("  5 = half speed (default)")
    print("  10 = full speed")
    print()
    print("Internet levels:")
    print("  1 = PAUSED (use for Skype / AnyDesk / screen sharing)")
    print("  5 = half speed")
    print("  10 = full speed")


# ── set command ───────────────────────────────────────────────────────────────

def cmd_set(gpu: int | None, internet: int | None) -> None:
    write_throttle(gpu=gpu, internet=internet)
    if gpu is not None:
        sleep = _GPU_SLEEP.get(gpu, 3.0)
        if sleep == -1:
            desc = "PAUSED — no batches will run"
        elif sleep == 0.0:
            desc = "full speed, no sleep between batches"
        else:
            desc = f"{sleep}s between batches"
        print(f"GPU throttle set to {gpu} — {desc}")
    if internet is not None:
        sleep = _INTERNET_SLEEP.get(internet, 1.5)
        conc = _INTERNET_CONCURRENCY.get(internet, 2)
        if sleep == -1:
            desc = "PAUSED — no downloads will run"
        else:
            conc_str = "unlimited" if conc == 999 else str(conc)
            if sleep == 0.0:
                desc = f"full speed, no sleep between requests, {conc_str} concurrent"
            else:
                desc = f"{sleep}s between requests, {conc_str} concurrent"
        print(f"Internet throttle set to {internet} — {desc}")


# ── parse args ────────────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> tuple[str, int | None, int | None]:
    """Returns (command, gpu_level, internet_level)."""
    if not argv or argv[0] == "status":
        return ("status", None, None)

    gpu_val: int | None = None
    internet_val: int | None = None
    errors = []

    i = 0
    while i < len(argv):
        token = argv[i].lower()
        if token in ("gpu", "internet"):
            if i + 1 >= len(argv):
                errors.append(f"Missing value after '{token}'")
                i += 1
                continue
            raw = argv[i + 1]
            try:
                val = int(raw)
            except ValueError:
                errors.append(f"Invalid value for {token}: '{raw}' — must be 1-10")
                i += 2
                continue
            if not (1 <= val <= 10):
                errors.append(f"Invalid value for {token}: {val} — must be 1-10")
                i += 2
                continue
            if token == "gpu":
                gpu_val = val
            else:
                internet_val = val
            i += 2
        else:
            errors.append(f"Unknown argument: '{argv[i]}'")
            i += 1

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if gpu_val is None and internet_val is None:
        print("ERROR: No valid settings provided. Use: gpu N, internet N, or status", file=sys.stderr)
        sys.exit(1)

    return ("set", gpu_val, internet_val)


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        cmd_status()
        return

    command, gpu_val, internet_val = parse_args(argv)
    if command == "status":
        cmd_status()
    else:
        cmd_set(gpu_val, internet_val)


if __name__ == "__main__":
    main()
