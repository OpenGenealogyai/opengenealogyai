"""
walker_status.py — Quick status check for the Deep Ancestor Walker.

Usage:
    python scripts/walker_status.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR       = Path(__file__).resolve().parent.parent
DATA_DIR       = BASE_DIR / "data" / "famous_people"
THROTTLE_DIR   = BASE_DIR / "_throttle"

PROGRESS_FILE  = DATA_DIR / "_progress.json"
QUEUE_FILE     = DATA_DIR / "_ancestor_queue.json"
STATS_FILE     = DATA_DIR / "_walker_stats.json"
DEPTHS_FILE    = THROTTLE_DIR / "ancestor_depths.json"

ESTIMATED_TOTAL = 2_000_000


def load_json(path: Path, default):
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def main():
    progress = load_json(PROGRESS_FILE, [])
    queue    = load_json(QUEUE_FILE, [])
    stats    = load_json(STATS_FILE, {})
    depths   = load_json(DEPTHS_FILE, {})

    total_dl  = len(progress)
    queue_sz  = len(queue)
    pct       = round(total_dl / ESTIMATED_TOTAL * 100, 1)
    rate      = stats.get("records_per_hour", 0)
    eta       = stats.get("estimated_hours_remaining", "?")
    last_upd  = stats.get("last_updated", "never")

    # Parse last_updated for display
    if last_upd and last_upd != "never":
        try:
            dt = datetime.fromisoformat(last_upd)
            last_upd = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            pass

    # Deepest generation from depths file
    deepest_gen = 0
    deepest_qid = ""
    for qid, d in depths.items():
        if d > deepest_gen:
            deepest_gen = d
            deepest_qid = qid

    print()
    print("=== Deep Ancestor Walker Status ===")
    print(f"Downloaded:  {total_dl:>12,} records")
    print(f"Queue:       {queue_sz:>12,} pending")
    print(f"Progress:    {pct:>11.1f}% of estimated {ESTIMATED_TOTAL:,} records")
    print(f"Rate:        {rate:>12,} records/hour")
    if isinstance(eta, (int, float)):
        print(f"ETA:         ~{eta:.0f} hours")
    else:
        print(f"ETA:         {eta}")
    print(f"Last update: {last_upd}")
    if deepest_gen > 0:
        print(f"Deepest gen: {deepest_gen} ({deepest_qid})")
    print()

    # Check if walker is likely running
    log_file = BASE_DIR / "_logs" / "deep_ancestor_walker.log"
    if log_file.exists():
        import os
        mtime = os.path.getmtime(log_file)
        now = datetime.now().timestamp()
        age_min = (now - mtime) / 60
        if age_min < 5:
            print(f"Walker status: RUNNING (log updated {age_min:.1f} min ago)")
        elif age_min < 60:
            print(f"Walker status: IDLE or PAUSED (log last updated {age_min:.0f} min ago)")
        else:
            print(f"Walker status: STOPPED (log last updated {age_min/60:.1f} hours ago)")
    else:
        print("Walker status: NEVER RUN (no log file found)")
    print()


if __name__ == "__main__":
    main()
