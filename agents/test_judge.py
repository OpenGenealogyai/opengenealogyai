"""Run all judge-agent tests and report pass/fail."""
import subprocess, json, sys
from pathlib import Path

TEST_DIR = Path(__file__).parent.parent / "test" / "judge"
JUDGE = Path(__file__).parent / "judge_agent.py"

EXPECTED = {
    "t01-approve-valid-birth-assertion.json": "APPROVE",
    "t02-reject-zero-confidence.json": "REJECT",
    "t03-reject-missing-asserted-by.json": "REJECT",
    "t04-reject-living-person-no-tier2.json": "REJECT",
    "t05-reject-unknown-source-record.json": "REJECT",
    "t06-reject-circular-parent.json": "REJECT",
    "t07-reject-familysearch-not-tier2.json": "REJECT",
    "t08-approve-tier2-living-person.json": "APPROVE",
    "t09-reject-confidence-above-1.json": "REJECT",
    "t10-reject-birth-year-living-threshold.json": "REJECT",
}

passed = 0
failed = 0

for fname, expected_verdict in sorted(EXPECTED.items()):
    test_path = TEST_DIR / fname
    if not test_path.exists():
        print(f"MISSING  {fname}")
        failed += 1
        continue

    result = subprocess.run(
        [sys.executable, str(JUDGE), str(test_path)],
        capture_output=True, text=True
    )

    try:
        output = json.loads(result.stdout)
        actual_verdict = output.get("verdict", "ERROR")
    except Exception:
        actual_verdict = "ERROR"
        output = {}

    if actual_verdict == expected_verdict:
        print(f"PASS  {fname} -> {actual_verdict}")
        passed += 1
    else:
        print(f"FAIL  {fname}")
        print(f"      expected={expected_verdict} actual={actual_verdict}")
        if output.get("reasons"):
            print(f"      reasons: {output['reasons']}")
        failed += 1

print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
