"""
Tests for privacy_middleware — the living-person and tier2 privacy gate.
"""
import json, sys, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "familysearch"))
from privacy_middleware import privacy_gate, privacy_gate_batch, PrivacyBlock


def _record(is_living=False, license_val="public-domain", record_id="rec-001"):
    return {
        "record_id": record_id,
        "is_living_flag": is_living,
        "redistribution_license": license_val,
    }


class TestPrivacyGate(unittest.TestCase):

    def test_open_record_passes(self):
        """CC0 non-living record — should not raise."""
        privacy_gate(_record(is_living=False, license_val="CC0"))

    def test_public_domain_passes(self):
        privacy_gate(_record(is_living=False, license_val="public-domain"))

    def test_cc_by_sa_passes(self):
        privacy_gate(_record(is_living=False, license_val="CC-BY-SA"))

    def test_living_raises_privacyblock(self):
        with self.assertRaises(PrivacyBlock):
            privacy_gate(_record(is_living=True, license_val="CC0"))

    def test_tier2_raises_privacyblock(self):
        with self.assertRaises(PrivacyBlock):
            privacy_gate(_record(is_living=False, license_val="tier2-private"))

    def test_living_and_tier2_both_raise(self):
        """Both flags set — is_living checked first, still raises."""
        with self.assertRaises(PrivacyBlock):
            privacy_gate(_record(is_living=True, license_val="tier2-private"))

    def test_unknown_license_raises(self):
        with self.assertRaises(PrivacyBlock):
            privacy_gate(_record(is_living=False, license_val="some-commercial-license"))

    def test_privacyblock_message_is_generic(self):
        """The exception message must not reveal WHY the record was blocked."""
        try:
            privacy_gate(_record(is_living=True))
            self.fail("Expected PrivacyBlock")
        except PrivacyBlock as e:
            self.assertEqual(str(e), "not found")

    def test_person_dict_is_living_field(self):
        """Person records use 'is_living' not 'is_living_flag'."""
        person = {
            "person_id": "P001",
            "is_living": True,
            "redistribution_license": "public-domain",
        }
        with self.assertRaises(PrivacyBlock):
            privacy_gate(person)

    def test_audit_log_written_on_block(self):
        """A blocked request must write an audit log entry."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "privacy_blocks.jsonl"
            import privacy_middleware as pm
            original = pm.AUDIT_LOG
            pm.AUDIT_LOG = log_path
            try:
                with self.assertRaises(PrivacyBlock):
                    privacy_gate(_record(is_living=True, record_id="test-123"),
                                 request_path="/api/records/test-123")
            finally:
                pm.AUDIT_LOG = original

            self.assertTrue(log_path.exists())
            entry = json.loads(log_path.read_text().strip())
            self.assertEqual(entry["record_id"], "test-123")
            self.assertEqual(entry["reason"], "is_living")
            self.assertEqual(entry["request_path"], "/api/records/test-123")
            # Audit log must NOT contain any protected data
            self.assertNotIn("transcription", entry)
            self.assertNotIn("persons_mentioned", entry)

    def test_audit_log_reason_tier2(self):
        """Tier2 blocks log reason 'tier2-private'."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "privacy_blocks.jsonl"
            import privacy_middleware as pm
            original = pm.AUDIT_LOG
            pm.AUDIT_LOG = log_path
            try:
                with self.assertRaises(PrivacyBlock):
                    privacy_gate(_record(is_living=False, license_val="tier2-private",
                                         record_id="fs-abc"))
            finally:
                pm.AUDIT_LOG = original
            entry = json.loads(log_path.read_text().strip())
            self.assertEqual(entry["reason"], "tier2-private")


class TestPrivacyGateBatch(unittest.TestCase):

    def test_filters_living_records(self):
        records = [
            _record(is_living=False, license_val="CC0", record_id="r1"),
            _record(is_living=True,  license_val="CC0", record_id="r2"),
            _record(is_living=False, license_val="CC0", record_id="r3"),
        ]
        safe = privacy_gate_batch(records)
        ids = [r["record_id"] for r in safe]
        self.assertIn("r1", ids)
        self.assertNotIn("r2", ids)
        self.assertIn("r3", ids)

    def test_filters_tier2_records(self):
        records = [
            _record(license_val="public-domain", record_id="r1"),
            _record(license_val="tier2-private",  record_id="r2"),
        ]
        safe = privacy_gate_batch(records)
        self.assertEqual(len(safe), 1)
        self.assertEqual(safe[0]["record_id"], "r1")

    def test_empty_input_returns_empty(self):
        self.assertEqual(privacy_gate_batch([]), [])

    def test_all_blocked_returns_empty(self):
        records = [_record(is_living=True) for _ in range(5)]
        self.assertEqual(privacy_gate_batch(records), [])



class TestHttpStatusCodes(unittest.TestCase):
    """Per Qwen 3 review: living=404 (existence denied), deceased tier2=403 (access denied)."""

    def test_living_person_is_404(self):
        try:
            privacy_gate(_record(is_living=True))
            self.fail("Expected PrivacyBlock")
        except PrivacyBlock as e:
            self.assertEqual(e.http_status, 404,
                             "Living persons must return 404 — existence must not be confirmed")

    def test_deceased_tier2_is_403(self):
        try:
            privacy_gate(_record(is_living=False, license_val="tier2-private"))
            self.fail("Expected PrivacyBlock")
        except PrivacyBlock as e:
            self.assertEqual(e.http_status, 403,
                             "Deceased tier2-private records exist but are restricted — 403 is correct")

    def test_unknown_license_is_403(self):
        try:
            privacy_gate(_record(is_living=False, license_val="commercial-restricted"))
            self.fail("Expected PrivacyBlock")
        except PrivacyBlock as e:
            self.assertEqual(e.http_status, 403)

    def test_audit_log_includes_http_status(self):
        """Audit log must record the HTTP status so ops can distinguish living vs access blocks."""
        import tempfile
        log_path = Path(tempfile.mktemp(suffix=".jsonl"))
        import privacy_middleware as pm
        original = pm.AUDIT_LOG
        pm.AUDIT_LOG = log_path
        try:
            with self.assertRaises(PrivacyBlock):
                privacy_gate(_record(is_living=False, license_val="tier2-private",
                                     record_id="fs-deceased"))
        finally:
            pm.AUDIT_LOG = original

        entry = json.loads(log_path.read_text().strip())
        self.assertEqual(entry["http_status"], 403)
        log_path.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()

