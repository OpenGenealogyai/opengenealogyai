"""
Tests for Internet Archive fetcher and RawRecord converter.
Uses mocked HTTP to avoid network calls.
"""
import json, sys, unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "ia-fetcher"))

from ia_to_rawrecord import (
    infer_record_type,
    infer_year_range,
    is_potentially_living,
    ia_to_rawrecord,
    validate_rawrecord,
)
from ia_fetcher import fetch_collection_items


class TestInferRecordType(unittest.TestCase):

    def test_death_keyword(self):
        self.assertEqual(infer_record_type("Illinois Death Records 1916", ""), "death_certificate")

    def test_census_keyword(self):
        self.assertEqual(infer_record_type("US Census 1880", "enumeration district"), "census_row")

    def test_parish_keyword(self):
        self.assertEqual(infer_record_type("German Parish Register", "baptisms"), "parish_register")

    def test_military_pension(self):
        self.assertEqual(infer_record_type("Civil War Pension Files", ""), "military_record")

    def test_explicit_hint_overrides(self):
        self.assertEqual(
            infer_record_type("Death Records", "", hint="marriage_certificate"),
            "marriage_certificate",
        )

    def test_unknown_falls_to_other(self):
        self.assertEqual(infer_record_type("Random Document 1820", ""), "other")


class TestInferYearRange(unittest.TestCase):

    def test_single_year(self):
        self.assertEqual(infer_year_range("1880"), (1880, 1880))

    def test_range_string(self):
        y_min, y_max = infer_year_range("1880-1920")
        self.assertEqual(y_min, 1880)
        self.assertEqual(y_max, 1920)

    def test_empty_returns_none(self):
        self.assertEqual(infer_year_range(""), (None, None))

    def test_non_numeric_returns_none(self):
        self.assertEqual(infer_year_range("unknown date"), (None, None))

    def test_future_year_excluded(self):
        # 2035 exceeds the regex upper bound (20[0-2][0-9] stops at 2029)
        self.assertEqual(infer_year_range("2035"), (None, None))


class TestIsLiving(unittest.TestCase):

    def test_old_record_not_living(self):
        self.assertFalse(is_potentially_living(1850))

    def test_recent_record_potentially_living(self):
        self.assertTrue(is_potentially_living(1960))  # 1960 is within 75-year window

    def test_none_defaults_to_living(self):
        self.assertTrue(is_potentially_living(None))


class TestIaToRawRecord(unittest.TestCase):

    def _sample_item(self):
        return {
            "identifier": "il-death-1916-vol1",
            "title": "Illinois Death Records 1916",
            "description": "Statewide death certificate index",
            "date": "1916",
            "subject": ["Smith, John", "Johnson, Mary"],
            "source_url": "https://archive.org/details/il-death-1916-vol1",
        }

    def test_basic_conversion(self):
        record = ia_to_rawrecord(self._sample_item())
        self.assertIn("record_id", record)
        self.assertEqual(record["record_type"], "death_certificate")
        self.assertEqual(record["redistribution_license"], "public-domain")
        self.assertFalse(record["is_living_flag"])  # 1916 birth year too old
        self.assertEqual(record["repository"], "Internet Archive")

    def test_persons_mentioned_populated(self):
        record = ia_to_rawrecord(self._sample_item())
        self.assertIn("persons_mentioned", record)
        names = [p["name_as_written"] for p in record["persons_mentioned"]]
        self.assertIn("Smith, John", names)

    def test_record_date_set_on_known_year(self):
        record = ia_to_rawrecord(self._sample_item())
        self.assertEqual(record["record_date"]["year_min"], 1916)
        self.assertEqual(record["record_date"]["year_max"], 1916)
        self.assertEqual(record["record_date"]["date_type"], "exact")

    def test_text_content_used_as_transcription(self):
        record = ia_to_rawrecord(self._sample_item(), text_content="John Smith died 1916 Cook County")
        self.assertIn("John Smith died", record["transcription"])

    def test_missing_source_url_defaults(self):
        item = self._sample_item()
        item["source_url"] = ""
        record = ia_to_rawrecord(item)
        self.assertTrue(record["source_url"].startswith("https://archive.org/details/"))


class TestValidateRawRecord(unittest.TestCase):

    def test_valid_record_passes(self):
        item = {
            "identifier": "test-valid-001",
            "title": "Marriage Records 1875",
            "description": "",
            "date": "1875",
            "subject": [],
            "source_url": "https://archive.org/details/test-valid-001",
        }
        record = ia_to_rawrecord(item, record_type_hint="marriage_certificate")

        with patch("ia_to_rawrecord.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            valid, errors = validate_rawrecord(record)
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_invalid_record_returns_errors(self):
        bad_record = {"record_id": "not-a-uuid"}
        with patch("ia_to_rawrecord.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="FAIL: missing required field record_type\n",
                stderr=""
            )
            valid, errors = validate_rawrecord(bad_record)
        self.assertFalse(valid)
        self.assertTrue(len(errors) > 0)


class TestFetchCollectionItems(unittest.TestCase):

    def test_returns_list_of_items(self):
        fake_response = json.dumps({
            "response": {
                "docs": [
                    {"identifier": "doc-001", "title": "Death Record 1916", "description": "", "date": "1916"},
                    {"identifier": "doc-002", "title": "Death Record 1917", "description": "", "date": "1917"},
                ]
            }
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("ia_fetcher.urllib.request.urlopen", return_value=mock_resp):
            items = fetch_collection_items("ILGENWEB", max_items=10)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["identifier"], "doc-001")
        self.assertTrue(items[0]["source_url"].startswith("https://archive.org/details/"))

    def test_network_error_returns_empty(self):
        with patch("ia_fetcher.urllib.request.urlopen", side_effect=Exception("timeout")):
            items = fetch_collection_items("BADCOLLECTION")
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()

