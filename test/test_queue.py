"""Test file-based queue claim/complete/fail operations."""
import sys, json, os, tempfile, shutil
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import queue_manager as Q

def setup_temp_queue():
    """Create a temp queue root for testing."""
    tmp = tempfile.mkdtemp()
    for d in ["inbox", "processing", "done", "failed", "dead"]:
        Path(tmp, d).mkdir()
    # Patch queue_manager.QUEUE_ROOT
    Q.QUEUE_ROOT = Path(tmp)
    return tmp

def make_task(tmp_queue: str, task_id: str = "test-task-001") -> Path:
    """Write a pending task to inbox."""
    task = {
        "task_id": task_id,
        "task_type": "extract_record",
        "status": "pending",
        "priority": 5,
        "cost_cap_usd": 0.50,
        "retry_count": 0,
        "max_retries": 3,
        "created_at": "2026-05-01T10:00:00Z",
        "created_by": "test"
    }
    path = Path(tmp_queue) / "inbox" / f"{task_id}.json"
    with open(path, "w") as f:
        json.dump(task, f)
    return path

def test_claim_success(tmp):
    task_path = make_task(tmp, "claim-test-001")
    ok, new_path = Q.claim_task(task_path, "agent-001")
    assert ok, "claim_task should return True"
    assert new_path is not None
    assert "processing" in new_path
    assert not task_path.exists(), "Original inbox file should be gone"
    print("PASS  test_claim_success")

def test_claim_double_claim(tmp):
    task_path = make_task(tmp, "claim-test-002")
    ok1, _ = Q.claim_task(task_path, "agent-001")
    ok2, _ = Q.claim_task(task_path, "agent-002")
    assert ok1, "First claim should succeed"
    assert not ok2, "Second claim should fail (file moved)"
    print("PASS  test_claim_double_claim")

def test_complete_task(tmp):
    task_path = make_task(tmp, "complete-test-001")
    ok, proc_path = Q.claim_task(task_path, "agent-001")
    task = Q.load_task(proc_path)
    Q.complete_task(task, proc_path, {"records_found": 5})
    assert (Path(tmp) / "done" / "complete-test-001.json").exists()
    done_task = Q.load_task(Path(tmp) / "done" / "complete-test-001.json")
    assert done_task["status"] == "done"
    assert done_task["result"]["records_found"] == 5
    print("PASS  test_complete_task")

def test_fail_with_retry(tmp):
    task_path = make_task(tmp, "fail-test-001")
    ok, proc_path = Q.claim_task(task_path, "agent-001")
    task = Q.load_task(proc_path)
    Q.fail_task(task, proc_path, "HTTP 404")
    # retry_count=1, max_retries=3, so should go back to inbox
    assert (Path(tmp) / "inbox" / "fail-test-001.json").exists(), "Should be re-queued"
    re_task = Q.load_task(Path(tmp) / "inbox" / "fail-test-001.json")
    assert re_task["retry_count"] == 1
    print("PASS  test_fail_with_retry")

def test_fail_max_retries_to_dead(tmp):
    task_path = make_task(tmp, "dead-test-001")
    # Exhaust retries
    for i in range(3):
        ok, proc_path = Q.claim_task(task_path if i == 0 else Path(tmp) / "inbox" / "dead-test-001.json", "agent-001")
        task = Q.load_task(proc_path)
        Q.fail_task(task, proc_path, f"Error attempt {i+1}")
    assert (Path(tmp) / "dead" / "dead-test-001.json").exists(), "Should be in dead/"
    print("PASS  test_fail_max_retries_to_dead")

def test_cost_cap(tmp):
    task = {"task_id": "t", "cost_cap_usd": 0.50, "status": "processing"}
    assert Q.check_cost_cap(task, 0.49) is True, "Under cap"
    assert Q.check_cost_cap(task, 0.51) is False, "Over cap"
    assert task["status"] == "escalated"
    print("PASS  test_cost_cap")

def main():
    tmp = setup_temp_queue()
    try:
        test_claim_success(tmp)
        test_claim_double_claim(tmp)
        test_complete_task(tmp)
        test_fail_with_retry(tmp)
        test_fail_max_retries_to_dead(tmp)
        test_cost_cap(tmp)
        print("\n6 passed, 0 failed")
        return 0
    except AssertionError as e:
        print(f"\nFAIL: {e}")
        return 1
    finally:
        shutil.rmtree(tmp)

if __name__ == "__main__":
    sys.exit(main())
