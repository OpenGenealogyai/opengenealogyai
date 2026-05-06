"""
Privacy middleware for OpenGenealogyAI open endpoints.

Contract:
  - ANY record with is_living_flag=True  → raise PrivacyBlock (renders as HTTP 404)
  - ANY record with redistribution_license="tier2-private" → raise PrivacyBlock
  - Blocked requests logged without exposing protected content
  - Returns 404 (not 403/401) so existence is never confirmed

Usage:
    from agents.familysearch.privacy_middleware import privacy_gate, PrivacyBlock

    record = get_record_metadata(record_id)
    try:
        privacy_gate(record, request_path="/api/records/" + record_id)
    except PrivacyBlock:
        return http_404()   # caller converts to HTTP 404

    return record_data
"""

import json, datetime, os
from pathlib import Path

AUDIT_LOG = Path(__file__).parent.parent.parent / "logs" / "privacy_blocks.jsonl"

TIER2_LICENSE = "tier2-private"
OPEN_LICENSES = {"CC0", "CC-BY", "CC-BY-SA", "public-domain"}


class PrivacyBlock(Exception):
    """Raised when a record must not be returned on open endpoints."""

    def __init__(self, reason: str, record_id: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.record_id = record_id


def _log_block(record_id: str, reason: str, request_path: str):
    """Write a privacy block audit event. Never logs protected field values."""
    AUDIT_LOG.parent.mkdir(exist_ok=True)
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": "privacy_block",
        "record_id": record_id,
        "reason": reason,
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
    Raises PrivacyBlock if it must be withheld.

    Parameters
    ----------
    record : dict
        Partial or full RawRecord or Person dict. Must contain at minimum
        'record_id', 'is_living_flag' (or 'is_living'), and 'redistribution_license'.
    request_path : str
        The API path being requested, for audit logging only.

    Raises
    ------
    PrivacyBlock
        If the record is living or tier2-private. Caller must render HTTP 404.
    """
    record_id = record.get("record_id") or record.get("person_id") or "unknown"
    license_val = record.get("redistribution_license", "")
    is_living = record.get("is_living_flag", record.get("is_living", False))

    if is_living:
        _log_block(record_id, "is_living", request_path)
        raise PrivacyBlock("not found", record_id)

    if license_val == TIER2_LICENSE:
        _log_block(record_id, "tier2-private", request_path)
        raise PrivacyBlock("not found", record_id)

    if license_val and license_val not in OPEN_LICENSES:
        _log_block(record_id, f"unknown-license:{license_val}", request_path)
        raise PrivacyBlock("not found", record_id)


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
