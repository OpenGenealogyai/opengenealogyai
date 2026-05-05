"""
File-based task queue manager for OpenGenealogyAI agents.
Implements atomic claim, cost enforcement, retry logic, dependency resolution.
"""
import os, json, datetime, shutil
from pathlib import Path

QUEUE_ROOT = Path(__file__).parent.parent / "queue"


def _queue_path(subdir: str, filename: str) -> Path:
    return QUEUE_ROOT / subdir / filename


def load_task(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_task(task: dict, path: str | Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2)


def claim_task(task_path: str | Path, agent_id: str) -> tuple[bool, str | None]:
    """
    Atomically move task from inbox to processing.
    Returns (True, new_path) on success, (False, None) if another agent claimed it.
    """
    task_path = Path(task_path)
    fname = task_path.name
    dest = QUEUE_ROOT / "processing" / fname
    try:
        task_path.rename(dest)
        return True, str(dest)
    except (FileNotFoundError, FileExistsError, PermissionError):
        return False, None


def complete_task(task: dict, processing_path: str | Path, result: dict):
    """Mark task done with result."""
    task["status"] = "done"
    task["result"] = result
    task["completed_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    processing_path = Path(processing_path)
    done_path = QUEUE_ROOT / "done" / processing_path.name
    save_task(task, processing_path)
    processing_path.rename(done_path)


def fail_task(task: dict, processing_path: str | Path, error: str, cost_usd: float = 0.0):
    """Handle task failure with retry logic."""
    task["error_message"] = error
    task["cost_usd"] = task.get("cost_usd", 0.0) + cost_usd
    task["retry_count"] = task.get("retry_count", 0) + 1
    processing_path = Path(processing_path)

    if task["retry_count"] >= task.get("max_retries", 3):
        task["status"] = "failed"
        dest = QUEUE_ROOT / "dead" / processing_path.name
        save_task(task, processing_path)
        processing_path.rename(dest)
    else:
        task["status"] = "pending"
        dest = QUEUE_ROOT / "inbox" / processing_path.name
        save_task(task, processing_path)
        processing_path.rename(dest)


def check_cost_cap(task: dict, current_cost_usd: float) -> bool:
    """Return False and set escalated status if cost cap exceeded."""
    cap = task.get("cost_cap_usd", 0.50)
    if current_cost_usd > cap:
        task["status"] = "escalated"
        task["escalation_reason"] = (
            f"Cost ${current_cost_usd:.4f} exceeded cap ${cap:.2f}"
        )
        return False
    return True


def can_dispatch(task: dict) -> bool:
    """Return True only if all dependency tasks are in done/."""
    for dep_id in task.get("depends_on", []):
        pattern = f"{dep_id}.json"
        done_path = QUEUE_ROOT / "done" / pattern
        if not done_path.exists():
            return False
    return True


def list_pending_tasks() -> list[dict]:
    """Return all tasks in inbox that have no unmet dependencies."""
    inbox = QUEUE_ROOT / "inbox"
    tasks = []
    for f in inbox.glob("*.json"):
        try:
            task = load_task(f)
            if can_dispatch(task):
                task["_path"] = str(f)
                tasks.append(task)
        except Exception:
            continue
    return sorted(tasks, key=lambda t: -t.get("priority", 5))


def daily_cost_total() -> float:
    """Sum cost_usd for all tasks completed today."""
    today = datetime.datetime.utcnow().date().isoformat()
    total = 0.0
    for subdir in ["done", "dead"]:
        for f in (QUEUE_ROOT / subdir).glob("*.json"):
            try:
                task = load_task(f)
                completed = task.get("completed_at", "")
                if completed.startswith(today):
                    total += task.get("cost_usd", 0.0)
            except Exception:
                continue
    return total
