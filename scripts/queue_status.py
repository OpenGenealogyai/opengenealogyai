"""
Print counts and oldest unclaimed task age for all queue directories.
Also detects stalled tasks (in processing/ over 4 hours) and alerts.
"""
import json, datetime
from pathlib import Path

QUEUE_ROOT = Path(__file__).parent.parent / "queue"
STALL_THRESHOLD_HOURS = 4

def load_task(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def oldest_age_minutes(directory: Path) -> float | None:
    oldest = None
    for f in directory.glob("*.json"):
        task = load_task(f)
        ts_str = task.get("created_at", "")
        if not ts_str:
            continue
        try:
            ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 60
            if oldest is None or age > oldest:
                oldest = age
        except Exception:
            continue
    return oldest

def stalled_tasks(processing_dir: Path) -> list[str]:
    stalled = []
    for f in processing_dir.glob("*.json"):
        task = load_task(f)
        started = task.get("started_at", "")
        if not started:
            continue
        try:
            ts = datetime.datetime.fromisoformat(started.replace("Z", "+00:00"))
            age_hours = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 3600
            if age_hours > STALL_THRESHOLD_HOURS:
                stalled.append(f"{f.name} (stalled {age_hours:.1f}h)")
        except Exception:
            continue
    return stalled

def main():
    print("=== OpenGenealogyAI Queue Status ===")
    print(f"{'Directory':<20} {'Count':>6}  {'Oldest (min)':>12}")
    print("-" * 44)

    for subdir in ["inbox", "processing", "done", "failed", "dead"]:
        d = QUEUE_ROOT / subdir
        files = list(d.glob("*.json"))
        count = len(files)
        age = oldest_age_minutes(d)
        age_str = f"{age:.0f}" if age is not None else "—"
        print(f"  {subdir:<18} {count:>6}  {age_str:>12}")

    stalled = stalled_tasks(QUEUE_ROOT / "processing")
    if stalled:
        print(f"\n⚠️  STALLED TASKS (>{STALL_THRESHOLD_HOURS}h in processing):")
        for s in stalled:
            print(f"    {s}")
        print("  Action: move to failed/ and re-queue")
    else:
        print(f"\n  No stalled tasks (threshold: {STALL_THRESHOLD_HOURS}h)")

if __name__ == "__main__":
    main()
