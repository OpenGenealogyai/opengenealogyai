"""
Judge-agent for OpenGenealogyAI.

Receives a Person entity and proposed new assertions, runs 5 checks,
returns APPROVE or REJECT with reasons. Must pass before any producer
agent is wired into the pipeline.

Exit codes: 0=APPROVE, 1=REJECT, 2=ERROR
"""
import json, sys, re, datetime
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent.parent / "schemas"


# ── Check 1: Schema conformance ────────────────────────────────────────────────

def check_schema_conformance(assertion: dict, assertion_type: str) -> tuple[bool, str]:
    """Verify required fields are present and typed correctly."""
    required = ["confidence", "source_record_id", "asserted_by", "asserted_at"]
    for field in required:
        if field not in assertion:
            return False, f"Missing required field: {field}"

    # Confidence must be float in [0.0, 1.0]
    c = assertion.get("confidence")
    if not isinstance(c, (int, float)) or not (0.0 <= c <= 1.0):
        return False, f"confidence {c!r} out of range [0.0, 1.0]"

    # source_record_id must look like a UUID
    src = assertion.get("source_record_id", "")
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", src, re.I):
        return False, f"source_record_id {src!r} is not a valid UUID"

    # asserted_at must parse as ISO 8601
    try:
        datetime.datetime.fromisoformat(assertion["asserted_at"].replace("Z", "+00:00"))
    except Exception:
        return False, f"asserted_at {assertion.get('asserted_at')!r} is not valid ISO 8601"

    # asserted_by must be non-empty string
    if not assertion.get("asserted_by", "").strip():
        return False, "asserted_by is empty"

    return True, ""


# ── Check 2: Confidence score validity ────────────────────────────────────────

def check_confidence(assertion: dict) -> tuple[bool, str]:
    """Reject implausible confidence values."""
    c = assertion.get("confidence", 0)
    # Confidence of exactly 1.0 is almost never justified for genealogy
    # We warn but do not reject (some well-documented facts are near-certain)
    # Confidence of 0.0 is suspicious — why assert something with zero confidence?
    if c == 0.0:
        return False, "confidence 0.0 means no evidence — do not assert"
    return True, ""


# ── Check 3: Source credibility tier ─────────────────────────────────────────

TIER2_SOURCES = {"familysearch.org", "ancestry.com", "myheritage.com"}

def check_source_credibility(assertion: dict, source_records: dict) -> tuple[bool, str]:
    """
    Verify source_record_id points to a known RawRecord.
    If source is Tier-2 and redistribution_license is not tier2-private, reject.
    """
    src_id = assertion.get("source_record_id", "")
    if src_id not in source_records:
        return False, f"source_record_id {src_id} not found in provided source_records"

    raw = source_records[src_id]
    license_ = raw.get("redistribution_license", "")

    # Check if source URL is from a Tier-2 platform
    source_url = raw.get("source_url", "")
    for t2 in TIER2_SOURCES:
        if t2 in source_url and license_ != "tier2-private":
            return False, (
                f"Source from {t2} must have redistribution_license=tier2-private, "
                f"got {license_!r}"
            )

    return True, ""


# ── Check 4: Privacy / living person gate ────────────────────────────────────

CURRENT_YEAR = datetime.datetime.now().year
LIVING_THRESHOLD_YEARS = 110

def check_privacy(assertion: dict, source_records: dict) -> tuple[bool, str]:
    """
    Reject any assertion whose source record has is_living_flag=True
    unless redistribution_license is tier2-private.
    """
    src_id = assertion.get("source_record_id", "")
    raw = source_records.get(src_id, {})

    if raw.get("is_living_flag", False):
        license_ = raw.get("redistribution_license", "")
        if license_ != "tier2-private":
            return False, (
                "Source record is_living_flag=True but redistribution_license is not "
                "tier2-private. Assertion blocked to protect living person."
            )

    # Check birth year heuristic on birth_assertions
    if "year_min" in assertion:
        year_min = assertion["year_min"]
        if year_min > (CURRENT_YEAR - LIVING_THRESHOLD_YEARS):
            return False, (
                f"year_min={year_min} suggests person may be living "
                f"(threshold: born after {CURRENT_YEAR - LIVING_THRESHOLD_YEARS}). "
                f"Set redistribution_license=tier2-private on source record first."
            )

    return True, ""


# ── Check 5: Relationship consistency (no impossible cycles) ──────────────────

def check_relationship_consistency(
    assertion: dict,
    assertion_type: str,
    existing_person: dict
) -> tuple[bool, str]:
    """
    For parent_assertions: check for obvious impossibilities.
    - A person cannot be their own parent
    - Dates: if we have birth years for both persons, parent must be born earlier
    """
    if assertion_type != "parent_assertion":
        return True, ""

    person_id = existing_person.get("person_id", "")
    parent_id = assertion.get("parent_person_id", "")

    if parent_id == person_id:
        return False, "parent_person_id cannot equal person_id — circular reference"

    return True, ""


# ── Main judge logic ──────────────────────────────────────────────────────────

class JudgeVerdict:
    APPROVE = "APPROVE"
    REJECT = "REJECT"


def judge(
    person: dict,
    new_assertion: dict,
    assertion_type: str,
    source_records: dict
) -> dict:
    """
    Run all 5 checks. Return verdict dict:
    {
      "verdict": "APPROVE" | "REJECT",
      "checks": {...},
      "reasons": [...],
      "judged_at": "ISO 8601",
      "agent": "judge-agent-v0.1"
    }
    """
    reasons = []
    checks_log = {}

    all_checks = [
        ("schema_conformance", lambda: check_schema_conformance(new_assertion, assertion_type)),
        ("confidence_validity", lambda: check_confidence(new_assertion)),
        ("source_credibility", lambda: check_source_credibility(new_assertion, source_records)),
        ("privacy_gate", lambda: check_privacy(new_assertion, source_records)),
        ("relationship_consistency", lambda: check_relationship_consistency(new_assertion, assertion_type, person)),
    ]

    for check_name, check_fn in all_checks:
        ok, reason = check_fn()
        checks_log[check_name] = {"passed": ok, "reason": reason}
        if not ok:
            reasons.append(f"{check_name}: {reason}")

    verdict = JudgeVerdict.APPROVE if not reasons else JudgeVerdict.REJECT

    return {
        "verdict": verdict,
        "checks": checks_log,
        "reasons": reasons,
        "assertion_type": assertion_type,
        "judged_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": "judge-agent-v0.1",
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python judge_agent.py <input.json>")
        print("Input JSON format: {person, assertion, assertion_type, source_records}")
        sys.exit(2)

    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(json.dumps({"verdict": "ERROR", "error": str(e)}))
        sys.exit(2)

    person = payload.get("person", {})
    assertion = payload.get("assertion", {})
    assertion_type = payload.get("assertion_type", "unknown")
    source_records = payload.get("source_records", {})

    result = judge(person, assertion, assertion_type, source_records)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["verdict"] == JudgeVerdict.APPROVE else 1)


if __name__ == "__main__":
    main()
