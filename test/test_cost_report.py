"""
Task .21: Cost reporting automation verification tests.
"""
import json, sys, unittest, tempfile, datetime
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from cost_report import collect_costs, format_report


def _write_task(directory: Path, status: str, assigned_to: str, cost: float, date: str):
    task = {
        "task_id": f"t-{assigned_to[:4]}-{cost}",
        "task_type": "extract_record",
        "status": status,
        "assigned_to": assigned_to,
        "cost_usd": cost,
        "created_at": f"{date}T10:00:00Z",
        "completed_at": f"{date}T10:05:00Z",
    }
    path = directory / f"{task['task_id']}.json"
    path.write_text(json.dumps(task), encoding="utf-8")


class TestCollectCosts(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.queue_root = Path(self.tmp) / "queue"
        for subdir in ["done", "failed", "dead", "inbox", "processing"]:
            (self.queue_root / subdir).mkdir(parents=True)
        self.today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    def test_empty_queue_returns_zeros(self):
        import cost_report as cr
        orig = cr.QUEUE_ROOT
        cr.QUEUE_ROOT = self.queue_root
        try:
            costs = collect_costs(self.today)
        finally:
            cr.QUEUE_ROOT = orig
        self.assertEqual(costs["haiku"], 0.0)
        self.assertEqual(costs["sonnet"], 0.0)
        self.assertEqual(costs["tasks_done"], 0)

    def test_haiku_costs_summed(self):
        import cost_report as cr
        _write_task(self.queue_root / "done", "done", "extractor-haiku-001", 0.25, self.today)
        _write_task(self.queue_root / "done", "done", "extractor-haiku-002", 0.15, self.today)
        orig = cr.QUEUE_ROOT
        cr.QUEUE_ROOT = self.queue_root
        try:
            costs = collect_costs(self.today)
        finally:
            cr.QUEUE_ROOT = orig
        self.assertAlmostEqual(costs["haiku"], 0.40, places=4)
        self.assertEqual(costs["tasks_done"], 2)

    def test_sonnet_costs_summed(self):
        import cost_report as cr
        _write_task(self.queue_root / "done", "done", "orchestrator-sonnet-001", 1.50, self.today)
        orig = cr.QUEUE_ROOT
        cr.QUEUE_ROOT = self.queue_root
        try:
            costs = collect_costs(self.today)
        finally:
            cr.QUEUE_ROOT = orig
        self.assertAlmostEqual(costs["sonnet"], 1.50, places=4)

    def test_different_date_excluded(self):
        import cost_report as cr
        yesterday = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1)).isoformat()
        _write_task(self.queue_root / "done", "done", "extractor-haiku-001", 5.00, yesterday)
        orig = cr.QUEUE_ROOT
        cr.QUEUE_ROOT = self.queue_root
        try:
            costs = collect_costs(self.today)
        finally:
            cr.QUEUE_ROOT = orig
        self.assertEqual(costs["haiku"], 0.0)

    def test_failed_tasks_counted_separately(self):
        import cost_report as cr
        _write_task(self.queue_root / "dead", "failed", "extractor-haiku-001", 0.05, self.today)
        orig = cr.QUEUE_ROOT
        cr.QUEUE_ROOT = self.queue_root
        try:
            costs = collect_costs(self.today)
        finally:
            cr.QUEUE_ROOT = orig
        self.assertEqual(costs["tasks_failed"], 1)


class TestFormatReport(unittest.TestCase):

    def _costs(self, haiku=0.0, sonnet=0.0, opus=0.0, done=0, failed=0):
        return {"haiku": haiku, "sonnet": sonnet, "opus": opus,
                "unknown": 0.0, "tasks_done": done, "tasks_failed": failed}

    def test_ok_status_when_under_40(self):
        costs = self._costs(haiku=5.0, done=10)
        report = format_report("2026-05-05", costs, 5.0)
        self.assertIn("[OK]", report)
        self.assertNotIn("[WARNING]", report)
        self.assertNotIn("[OVER CAP]", report)

    def test_warning_status_when_over_40(self):
        costs = self._costs(haiku=41.0, done=50)
        report = format_report("2026-05-05", costs, 41.0)
        self.assertIn("[WARNING]", report)

    def test_over_cap_status_at_50(self):
        costs = self._costs(haiku=50.0, done=60)
        report = format_report("2026-05-05", costs, 50.0)
        self.assertIn("[OVER CAP]", report)
        self.assertIn("ALERT", report)

    def test_report_contains_date(self):
        costs = self._costs()
        report = format_report("2026-05-05", costs, 0.0)
        self.assertIn("2026-05-05", report)

    def test_report_contains_all_agent_types(self):
        costs = self._costs(haiku=1.0, sonnet=2.0, opus=0.5, done=10)
        report = format_report("2026-05-05", costs, 3.5)
        self.assertIn("Haiku", report)
        self.assertIn("Sonnet", report)
        self.assertIn("Opus", report)


class TestScheduledTaskExists(unittest.TestCase):

    def test_cost_report_task_registered(self):
        """Verify the Windows Task Scheduler task was created (Task .21 gate)."""
        import subprocess
        result = subprocess.run(
            ["schtasks", "/query", "/tn", "OpenGenealogyAI-CostReport"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0,
                         "OpenGenealogyAI-CostReport task not found in Windows Task Scheduler")
        self.assertIn("CostReport", result.stdout)


if __name__ == "__main__":
    unittest.main()
