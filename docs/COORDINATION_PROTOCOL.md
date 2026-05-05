# Agent Coordination Protocol

**Version**: 0.1  
**Governs**: All task handoffs between agents in the OpenGenealogyAI pipeline

---

## Queue Directory Structure

```
queue/
  inbox/      <- Orchestrator writes new tasks here
  processing/ <- Agent atomically claims task by moving here
  done/       <- Agent writes result here on success
  failed/     <- Agent writes here on error or rejection
  dead/       <- Tasks that failed max_retries times
```

## Atomic Task Claim

To prevent two Haiku instances from double-processing the same task:

```python
import os, shutil

def claim_task(task_path: str, agent_id: str) -> bool:
    """
    Atomically move a task from inbox to processing.
    Returns True if claim succeeded, False if another agent got it first.
    """
    fname = os.path.basename(task_path)
    dest = f"queue/processing/{fname}"
    try:
        # os.rename is atomic on POSIX and Windows (same drive)
        os.rename(task_path, dest)
        return True
    except (FileNotFoundError, FileExistsError, PermissionError):
        return False  # Another agent claimed it first
```

**Rule**: An agent only processes a task after `claim_task()` returns `True`. If it returns `False`, the agent skips and polls again.

## Task Lifecycle

```
inbox/<task_id>.json
  -> [Agent calls os.rename] ->
processing/<task_id>.json
  -> [Agent writes result into task JSON] ->
  -> [On success]: done/<task_id>.json
  -> [On failure]: failed/<task_id>.json
  -> [On max_retries exceeded]: dead/<task_id>.json
```

## Cost Enforcement

Before writing any result, the agent checks:

```python
def check_cost_cap(task: dict, current_cost_usd: float) -> bool:
    cap = task.get("cost_cap_usd", 0.50)
    if current_cost_usd > cap:
        task["status"] = "escalated"
        task["escalation_reason"] = f"Cost ${current_cost_usd:.4f} exceeded cap ${cap:.2f}"
        return False
    return True
```

If cost cap exceeded: move task to failed/, set status=escalated.

## Inter-Agent Signaling

Agents do NOT call each other directly. The Orchestrator watches queue/done/ and dispatches the next agent:

```
Extractor -> done/<id>-raw-record.json
Orchestrator sees it -> creates new task for Validator
Validator -> done/<id>-validation.json
Orchestrator sees it -> creates new task for Critic
...
Judge -> verdict APPROVE -> Orchestrator creates Integrator task
Judge -> verdict REJECT -> Orchestrator creates retry task for Extractor (or marks failed)
```

## Retry Logic

```python
def handle_failure(task: dict, error: str, queue_dir: str):
    task["retry_count"] = task.get("retry_count", 0) + 1
    task["error_message"] = error
    if task["retry_count"] >= task.get("max_retries", 3):
        task["status"] = "failed"
        move_to(task, f"{queue_dir}/dead/")
    else:
        task["status"] = "pending"
        move_to(task, f"{queue_dir}/inbox/")  # Re-queue for retry
```

## Dependency Resolution

Tasks with `depends_on` arrays are only eligible for dispatch when all dependencies are in done/:

```python
def can_dispatch(task: dict, queue_dir: str) -> bool:
    for dep_id in task.get("depends_on", []):
        if not os.path.exists(f"{queue_dir}/done/{dep_id}.json"):
            return False
    return True
```

## Cost Report

The Orchestrator aggregates cost from all done/ and failed/ task files at midnight UTC:

```python
total = sum(t.get("cost_usd", 0) for t in all_tasks_today)
if total > 50.0:
    alert_slack("HARD STOP: daily cost cap $50 exceeded")
    sys.exit(1)
```

## Context Isolation

Each agent runs in its own subprocess with no shared memory:
- Agents communicate only through task JSON files
- No agent imports another agent's module
- No shared global state

## Human Gate Integration

When Conflict Resolver escalates to HG-7:
1. Write `queue/inbox/human-gate-<person_id>.json` with full context
2. Post Slack notification: "Human review needed: <person_id>"
3. Poll `queue/inbox/human-gate-<person_id>-approved.json` every 30 min
4. If file appears, continue processing; if not in 72h, mark escalated
