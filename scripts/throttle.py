"""
CLI throttle control for OpenGenealogyAI pipeline (v3, 0-10 scale).

Usage:
    python scripts/throttle.py gpu 0              # pause GPU
    python scripts/throttle.py internet 0         # pause internet
    python scripts/throttle.py cpu 3              # set cpu to 3
    python scripts/throttle.py claude 0           # no API spend
    python scripts/throttle.py gpu 10 internet 8  # set multiple
    python scripts/throttle.py status             # show all 4 dials
    python scripts/throttle.py let-it-rip         # all to 10
    python scripts/throttle.py zoom               # internet=0,gpu=2,cpu=0,claude=0
    python scripts/throttle.py off                # all to 0
"""

import sys
from pathlib import Path

# Make sure pipeline package is importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.throttle import write_throttle, read_throttle, status_line

DIALS = ("internet", "gpu", "cpu", "claude")

# ── level descriptions ─────────────────────────────────────────────────────────

def _level_label(level: int) -> str:
    if level == 0:
        return "PAUSED"
    if level <= 3:
        return "slow"
    if level <= 6:
        return "medium"
    if level <= 9:
        return "fast"
    return "full speed"


def _dial_desc(dial: str, level: int) -> str:
    """Human-readable description for a dial at a given level."""
    if dial == "internet":
        if level == 0:
            return "PAUSED — no downloads or web fetches"
        if level <= 3:
            return f"slow — {_level_label(level)} (long delays between requests)"
        if level <= 6:
            return f"medium — moderate request rate"
        if level <= 9:
            return f"fast — short delays between requests"
        return "full speed — no delay between requests"

    if dial == "gpu":
        if level == 0:
            return "PAUSED — GPU workers blocked"
        if level <= 3:
            return f"slow — {_level_label(level)} (long sleep between batches)"
        if level <= 6:
            return f"medium — moderate batch rate"
        if level <= 9:
            return f"fast — short sleep between batches"
        return "full speed — no sleep between batches"

    if dial == "cpu":
        if level == 0:
            return "idle priority — background processes throttled to minimum"
        if level <= 1:
            return "idle priority — background processes throttled to minimum"
        if level <= 3:
            return "below-normal priority — reduced CPU scheduling"
        return "normal process priority"

    if dial == "claude":
        if level == 0:
            return "OFF — no API calls"
        if level <= 3:
            return "minimal — no councils or subagents"
        if level <= 6:
            return "normal — councils allowed"
        if level <= 9:
            return "high — councils and subagents enabled"
        return "full API access (councils, subagents enabled)"

    return _level_label(level)


# ── status command ─────────────────────────────────────────────────────────────

def cmd_status() -> None:
    t = read_throttle()
    print("=== Pipeline Throttle Status ===")
    for dial in DIALS:
        lvl = t.get(dial, 10)
        desc = _dial_desc(dial, lvl)
        print(f"  {dial:<8} : {lvl:>2}/10  {desc}")
    print()
    print("Shortcuts:")
    print("  let-it-rip  -> all 10    zoom -> internet=0,gpu=2,cpu=0,claude=0")
    print("  off         -> all 0")
    print()
    print("Set: python scripts/throttle.py <dial> <0-10>  [<dial> <0-10> ...]")


# ── set command ────────────────────────────────────────────────────────────────

def cmd_set(values: dict) -> None:
    """Write dial values and print confirmation."""
    write_throttle(**values)
    for dial, lvl in values.items():
        desc = _dial_desc(dial, lvl)
        print(f"{dial} set to {lvl}/10 — {desc}")


# ── parse args ─────────────────────────────────────────────────────────────────

PRESET_ALIASES = {
    "zoom", "skype", "anydesk", "screenshare",
}
RESUME_ALIASES = {
    "let-it-rip", "resume",
}
PAUSE_ALIASES = {
    "off", "pause", "sleep",
}


def parse_args(argv: list) -> tuple:
    """Returns (command, values_dict).
    command is one of: 'status', 'preset', 'set'
    values_dict: keys are dial names, values are int levels (for 'set'/'preset')
    """
    if not argv or argv[0].lower() == "status":
        return ("status", {})

    first = argv[0].lower()

    if first in RESUME_ALIASES:
        return ("set", {"internet": 10, "gpu": 10, "cpu": 10, "claude": 10})

    if first in PAUSE_ALIASES:
        return ("set", {"internet": 0, "gpu": 0, "cpu": 0, "claude": 0})

    if first in PRESET_ALIASES:
        return ("set", {"internet": 0, "gpu": 2, "cpu": 0, "claude": 0})

    # Pair-based parsing: dial value [dial value ...]
    values = {}
    errors = []
    i = 0
    while i < len(argv):
        token = argv[i].lower()
        if token in DIALS:
            if i + 1 >= len(argv):
                errors.append(f"Missing value after '{token}'")
                i += 1
                continue
            raw = argv[i + 1]
            try:
                val = int(raw)
            except ValueError:
                errors.append(f"Invalid value for {token}: '{raw}' — must be 0-10")
                i += 2
                continue
            if not (0 <= val <= 10):
                errors.append(f"Value out of range for {token}: {val} — must be 0-10")
                i += 2
                continue
            values[token] = val
            i += 2
        else:
            errors.append(
                f"Unknown argument: '{argv[i]}' — valid dials: {', '.join(DIALS)}"
            )
            i += 1

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not values:
        print(
            "ERROR: No valid settings provided.\n"
            f"  Usage: python scripts/throttle.py <dial> <0-10>\n"
            f"  Dials: {', '.join(DIALS)}\n"
            f"  Or: status | let-it-rip | off | zoom",
            file=sys.stderr,
        )
        sys.exit(1)

    return ("set", values)


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        cmd_status()
        return

    command, values = parse_args(argv)
    if command == "status":
        cmd_status()
    else:
        cmd_set(values)


if __name__ == "__main__":
    main()
