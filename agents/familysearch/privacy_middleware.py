"""
Privacy middleware for OpenGenealogyAI open endpoints.

Contract (per Qwen 3 review 2026-05-05):
  - is_living_flag=True  → PrivacyBlock(http_status=404)  — existence never confirmed
  - redistribution_license="tier2-private" AND is_living=False → PrivacyBlock(http_status=403)
    Rationale: deceased tier2-private records DO exist; 403 is semantically correct.
    404 is reserved for living persons only (existence must not be confirmed).
  - Privacy gate runs BEFORE authentication — tier2 restrictions are orthogonal to auth.
  - Blocked requests logged (reason + path only — never protected field values).

Usage:
    from agents.familysearch.privacy_middleware import privacy_gate, PrivacyBlock

    record = get_record_metadata(record_id)
    try:
        privacy_gate(record, request_path="/api/records/" + record_id)
    except PrivacyBlock as e:
        if e.http_status == 404:
            return http_404()
        return http_403()

    return record_data
"""

import json, datetime
from pathlib import Path

AUDIT_LOG = Path(__file__).parent.parent.parent / "logs" / "privacy_blocks.jsonl"

TIER2_LICENSE = "tier2-private"
OPEN_LICENSES = {"CC0", "CC-BY", "CC-BY-SA", "public-domain"}


class PrivacyBlock(Exception):
    """
    Raised when a record must not be returned on open endpoints.

    http_status:
      404 — living person (existence must not be confirmed)
      403 — deceased but tier2-private (record exists, access denied)
    """

    def __init__(self, reason: str, record_id: str = "", http_status: int = 404):
        super().__init__(reason)
        self.reason = reason
        self.record_id = record_id
        self.http_status = http_status


def _log_block(record_id: str, reason: str, request_path: str, http_status: int):
    """Write a privacy block audit event. Never logs protected field values."""
    AUDIT_LOG.parent.mkdir(exist_ok=True)
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": "privacy_block",
        "record_id": record_id,
        "reason": reason,
        "http_status": http_status,
        "request_path": request_path,
    }
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # audit failure must never expose data


def privacy_gate(record: dict, request_path: str = "") -> None:
    """
    Check whether a record may be returned on an open endpoint.
    Run this BEFORE authentication checks (per Qwen design review).

    Raises PrivacyBlock with http_status=404 for living persons,
    http_status=403 for deceased tier2-private records.

    Parameters
    ----------
    record : dict
        RawRecord or Person dict. Must contain at minimum
        'record_id', 'is_living_flag' (or 'is_living'), and 'redistribution_license'.
    request_path : str
        The API path being requested, for audit logging only.
    """
    record_id = record.get("record_id") or record.get("person_id") or "unknown"
    license_val = record.get("redistribution_license", "")
    is_living = record.get("is_living_flag", record.get("is_living", False))

    if is_living:
        # 404: existence of living persons must never be confirmed
        _log_block(record_id, "is_living", request_path, 404)
        raise PrivacyBlock("not found", record_id, http_status=404)

    if license_val == TIER2_LICENSE:
        # 403: record exists but access is denied (Qwen recommendation: deceased tier2 = 403)
        _log_block(record_id, "tier2-private", request_path, 403)
        raise PrivacyBlock("forbidden", record_id, http_status=403)

    if license_val and license_val not in OPEN_LICENSES:
        _log_block(record_id, f"unknown-license:{license_val}", request_path, 403)
        raise PrivacyBlock("forbidden", record_id, http_status=403)


def privacy_gate_batch(records: list[dict], request_path: str = "") -> list[dict]:
    """
    Filter a list of records, silently dropping any that fail the privacy gate.
    Use for search results where disclosing the count is safe.

    Returns only records that pass.
    """
    safe = []
    for r in records:
        try:
            privacy_gate(r, request_path)
            safe.append(r)
        except PrivacyBlock:
            pass
    return safe


def assert_open_license(record: dict, request_path: str = "") -> None:
    """Convenience alias — same as privacy_gate but named for intent."""
    privacy_gate(record, request_path)
