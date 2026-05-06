"""
Tests for the genealogy tree builder agent.
Uses Abraham Lincoln Sr. (b. ~1744) as the primary test anchor — a real
historical figure whose parents and children are well documented.

All Qdrant and SQLite calls are mocked so tests run offline.
"""
import json, sys, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "builder"))
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "familysearch"))

from tree_builder import (
    TreeBuilder, PersonSeed, PersonCandidate, TreeResult,
    _soundex, _name_confidence, _now_iso,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────
LINCOLN_SEED = PersonSeed(
    name="Abraham Lincoln",
    birth_year=1744,
    birth_year_tolerance=10,
    birth_country="US",
)

LINCOLN_CANDIDATE = PersonCandidate(
    record_id="vc-1786-lincoln-death",
    name_as_written="Abraham Lincoln Senr",
    confidence=0.82,
    source_url="https://archive.org/details/virginia-county-records-1786",
    year_min=1744,
    year_max=1786,
    record_type="death_certificate",
    payload={"record_id": "vc-1786-lincoln-death", "year_min": 1744},
)

JOHN_CANDIDATE = PersonCandidate(
    record_id="va-tax-1750-lincoln",
    name_as_written="John Lincoln",
    confidence=0.75,
    source_url="https://archive.org/details/virginia-tax-records-1750",
    year_min=1716,
    year_max=1788,
    record_type="tax_record",
    payload={"record_id": "va-tax-1750-lincoln", "year_min": 1716},
)


class TestSoundex(unittest.TestCase):

    def test_lincoln_soundex(self):
        self.assertEqual(_soundex("Lincoln"), "L524")

    def test_variant_linkhorn_similar_code(self):
        # Linkhorn and Lincoln both start with L5 -- close but not identical Soundex
        # This is expected: standard Soundex has known gaps for historical variants;
        # our system augments with Jaro-Winkler as a tiebreaker (see VECTOR_DB_ARCHITECTURE.md)
        self.assertEqual(_soundex('Linkhorn')[0], _soundex('Lincoln')[0])   # same first letter
        self.assertEqual(_soundex('Linkhorn')[1], _soundex('Lincoln')[1])   # same first code digit

    def test_empty_string(self):
        self.assertEqual(_soundex(""), "Z000")


class TestNameConfidence(unittest.TestCase):

    def test_exact_match_is_1(self):
        self.assertAlmostEqual(_name_confidence("Abraham Lincoln", "Abraham Lincoln"), 1.0)

    def test_soundex_variant_is_high(self):
        # "Lincoln Senr" vs "Abraham Lincoln" — soundex match on Lincoln
        conf = _name_confidence("Abraham Lincoln", "Abraham Lincoln Senr")
        self.assertGreater(conf, 0.50)

    def test_unrelated_name_is_low(self):
        conf = _name_confidence("Abraham Lincoln", "George Washington")
        self.assertLess(conf, 0.50)

    def test_empty_name_returns_0(self):
        self.assertEqual(_name_confidence("", "Abraham Lincoln"), 0.0)


class TestCreatePerson(unittest.TestCase):

    def setUp(self):
        self.builder = TreeBuilder.__new__(TreeBuilder)
        self.builder.agent_id = "test-agent"
        self.builder.db_path = Path("/nonexistent/staging.db")
        self.builder.qdrant = None

    def test_creates_person_with_name_assertion(self):
        person = self.builder.create_person(
            "Abraham Lincoln", 1744, [LINCOLN_CANDIDATE]
        )
        self.assertIn("person_id", person)
        self.assertTrue(person["person_id"].startswith("P-"))
        self.assertGreater(len(person["name_assertions"]), 0)
        self.assertEqual(person["name_assertions"][0]["name_as_written"], "Abraham Lincoln Senr")

    def test_low_confidence_seed_when_no_evidence(self):
        person = self.builder.create_person("Unknown Person", 1700, [])
        assertion = person["name_assertions"][0]
        self.assertLessEqual(assertion["confidence"], 0.30)
        self.assertEqual(assertion["source_record_id"], "seed-no-evidence")

    def test_birth_assertions_added_when_year_known(self):
        person = self.builder.create_person("Abraham Lincoln", 1744, [LINCOLN_CANDIDATE])
        self.assertIn("birth_assertions", person)
        ba = person["birth_assertions"][0]
        self.assertLessEqual(ba["year_min"], 1744)
        self.assertGreaterEqual(ba["year_max"], 1744)

    def test_person_id_deterministic(self):
        id1 = self.builder._make_person_id("Abraham Lincoln", 1744)
        id2 = self.builder._make_person_id("Abraham Lincoln", 1744)
        self.assertEqual(id1, id2)

    def test_person_id_differs_on_different_birth_year(self):
        id1 = self.builder._make_person_id("Abraham Lincoln", 1744)
        id2 = self.builder._make_person_id("Abraham Lincoln", 1745)
        self.assertNotEqual(id1, id2)

    def test_is_living_false_for_historical(self):
        person = self.builder.create_person("Abraham Lincoln", 1744, [])
        self.assertFalse(person["is_living"])


class TestAssertParent(unittest.TestCase):

    def setUp(self):
        self.builder = TreeBuilder.__new__(TreeBuilder)
        self.builder.agent_id = "test-agent"
        self.builder.qdrant = None

    def test_parent_assertion_appended(self):
        subject = {"person_id": "P-SUBJECT", "parent_assertions": []}
        self.builder.assert_parent(
            subject, "P-FATHER", "John Lincoln",
            "biological", "father", 0.75, "va-tax-1750"
        )
        self.assertEqual(len(subject["parent_assertions"]), 1)
        pa = subject["parent_assertions"][0]
        self.assertEqual(pa["parent_person_id"], "P-FATHER")
        self.assertEqual(pa["relationship_type"], "biological")
        self.assertEqual(pa["parent_role"], "father")
        self.assertAlmostEqual(pa["confidence"], 0.75)

    def test_multiple_parents_allowed(self):
        subject = {"person_id": "P-SUBJECT", "parent_assertions": []}
        self.builder.assert_parent(subject, "P-FATHER", "John", "biological", "father", 0.70, "src1")
        self.builder.assert_parent(subject, "P-MOTHER", "Rebecca", "biological", "mother", 0.65, "src2")
        self.assertEqual(len(subject["parent_assertions"]), 2)


class TestBuildTree(unittest.TestCase):

    def _make_builder(self):
        builder = TreeBuilder.__new__(TreeBuilder)
        builder.agent_id = "test-agent"
        builder.db_path = Path("/nonexistent/staging.db")
        builder.qdrant = None
        return builder

    def test_build_tree_depth1_returns_one_person(self):
        builder = self._make_builder()
        with patch.object(builder, "search_records", return_value=[LINCOLN_CANDIDATE]), \
             patch.object(builder, "persist_person", return_value=True), \
             patch.object(builder, "queue_judge_task", return_value="task-file.json"):
            result = builder.build_tree(LINCOLN_SEED, depth=1)

        self.assertEqual(len(result.persons_created), 1)
        self.assertEqual(result.judge_tasks_queued, 1)
        self.assertEqual(result.seed.name, "Abraham Lincoln")

    def test_build_tree_depth2_adds_parent(self):
        builder = self._make_builder()
        call_count = [0]

        def mock_search(seed):
            call_count[0] += 1
            if call_count[0] == 1:
                return [LINCOLN_CANDIDATE]
            return [JOHN_CANDIDATE]

        with patch.object(builder, "search_records", side_effect=mock_search), \
             patch.object(builder, "persist_person", return_value=True), \
             patch.object(builder, "queue_judge_task", return_value="task.json"):
            result = builder.build_tree(LINCOLN_SEED, depth=2)

        self.assertGreaterEqual(len(result.persons_created), 2)
        self.assertGreaterEqual(result.judge_tasks_queued, 2)

    def test_summary_string(self):
        builder = self._make_builder()
        with patch.object(builder, "search_records", return_value=[]), \
             patch.object(builder, "persist_person", return_value=False), \
             patch.object(builder, "queue_judge_task", return_value="t.json"):
            result = builder.build_tree(LINCOLN_SEED, depth=1)
        summary = result.summary()
        self.assertIn("Abraham Lincoln", summary)
        self.assertIn("1744", summary)


class TestQueueJudgeTask(unittest.TestCase):

    def test_task_file_written(self):
        import tempfile
        builder = TreeBuilder.__new__(TreeBuilder)
        builder.agent_id = "test-agent"
        builder.qdrant = None

        with tempfile.TemporaryDirectory() as tmp:
            # Patch REPO_ROOT so queue writes to temp dir
            import tree_builder as tb_mod
            original_root = tb_mod.REPO_ROOT
            tb_mod.REPO_ROOT = Path(tmp)
            try:
                task_file = builder.queue_judge_task("P-TEST123")
            finally:
                tb_mod.REPO_ROOT = original_root

            task_path = Path(tmp) / "queue" / "inbox" / task_file
            self.assertTrue(task_path.exists())
            task = json.loads(task_path.read_text())
            self.assertEqual(task["task_type"], "judge_review")
            self.assertEqual(task["payload"]["person_id"], "P-TEST123")
            self.assertIn("cost_cap_usd", task)


if __name__ == "__main__":
    unittest.main()

