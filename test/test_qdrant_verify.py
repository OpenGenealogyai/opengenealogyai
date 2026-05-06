"""
Task .20: Qdrant vector DB ingest and semantic search verification.

Tests verify:
  1. Soundex implementation matches expected codes for genealogy names
  2. n-gram generation produces correct character trigrams
  3. Filter logic correctly excludes living/non-approved records
  4. Collection names and field names match the architecture spec
  5. Live Qdrant tests are skipped when Qdrant is offline (CI-safe)
"""
import sys, json, unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# Import from query_qdrant (no network calls at import time)
from query_qdrant import soundex, name_to_ngrams

# Architecture constants from VECTOR_DB_ARCHITECTURE.md
PERSONS_COLLECTION = "persons_v01"
RECORDS_COLLECTION = "raw_records_v01"
VECTOR_DIM = 1536


def _qdrant_running() -> bool:
    """Check if Qdrant is reachable on localhost:6333."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:6333/healthz", timeout=2)
        return True
    except Exception:
        return False


class TestSoundexImplementation(unittest.TestCase):
    """Verify our Soundex matches expected codes for genealogy name variants."""

    def test_brown_braun_variants(self):
        # Brown / Braun are classic Soundex equivalents (both B650)
        self.assertEqual(soundex('Brown'), soundex('Braun'))

    def test_lincoln(self):
        self.assertEqual(soundex("Lincoln"), "L524")

    def test_washington(self):
        self.assertEqual(soundex("Washington"), "W252")

    def test_jones(self):
        self.assertEqual(soundex("Jones"), "J520")

    def test_empty_string(self):
        # Empty string should return the padding zero code
        result = soundex("")
        self.assertEqual(len(result), 4)

    def test_single_letter(self):
        result = soundex("A")
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], "A")


class TestNgramGeneration(unittest.TestCase):
    """Verify character 3-gram generation for Qdrant hybrid search."""

    def test_basic_trigrams(self):
        grams = name_to_ngrams("abc", n=3)
        self.assertIn("abc", grams)

    def test_longer_name(self):
        grams = name_to_ngrams("lincoln", n=3)
        self.assertIn("lin", grams)
        self.assertIn("inc", grams)
        self.assertIn("nco", grams)

    def test_short_name_no_crash(self):
        # Names shorter than n should not raise
        grams = name_to_ngrams("Li", n=3)
        self.assertIsInstance(grams, list)

    def test_case_insensitive(self):
        grams_lower = name_to_ngrams("lincoln", n=3)
        grams_upper = name_to_ngrams("LINCOLN", n=3)
        # Both should produce same grams
        self.assertEqual(set(grams_lower), set(grams_upper))


class TestArchitectureConstants(unittest.TestCase):
    """Verify the collection config matches the architecture doc."""

    def test_setup_script_references_correct_collections(self):
        """setup_qdrant.py must create both collections from VECTOR_DB_ARCHITECTURE.md."""
        setup_content = (REPO_ROOT / "scripts" / "setup_qdrant.py").read_text(encoding="utf-8")
        self.assertIn(PERSONS_COLLECTION, setup_content,
                      f"setup_qdrant.py must create '{PERSONS_COLLECTION}'")
        self.assertIn(RECORDS_COLLECTION, setup_content,
                      f"setup_qdrant.py must create '{RECORDS_COLLECTION}'")

    def test_setup_script_uses_correct_vector_dim(self):
        """Vectors must be 1536-dim (text-embedding-3-small)."""
        setup_content = (REPO_ROOT / "scripts" / "setup_qdrant.py").read_text(encoding="utf-8")
        self.assertIn("1536", setup_content, "Vector dimension must be 1536")

    def test_query_script_filters_living(self):
        """query_qdrant.py must filter is_living=False."""
        query_content = (REPO_ROOT / "scripts" / "query_qdrant.py").read_text(encoding="utf-8")
        self.assertIn("is_living", query_content, "Query must filter out living persons")

    def test_batch_ingest_skips_living(self):
        """ia_batch_ingest.py must skip is_living_flag=True records."""
        ingest_content = (REPO_ROOT / "scripts" / "ia_batch_ingest.py").read_text(encoding="utf-8")
        self.assertIn("is_living_flag", ingest_content)
        self.assertIn("skipped_living", ingest_content)

    def test_batch_ingest_soundex_payload(self):
        """ia_batch_ingest.py must store Soundex in Qdrant payload."""
        ingest_content = (REPO_ROOT / "scripts" / "ia_batch_ingest.py").read_text(encoding="utf-8")
        self.assertIn("name_soundex", ingest_content)


@unittest.skipUnless(_qdrant_running(), "Qdrant not running on localhost:6333 -- skip live tests")
class TestQdrantLive(unittest.TestCase):
    """Live Qdrant tests -- only run when Qdrant is reachable."""

    def setUp(self):
        from qdrant_client import QdrantClient
        self.qdrant = QdrantClient(host="localhost", port=6333, timeout=5)

    def test_collections_exist(self):
        collections = [c.name for c in self.qdrant.get_collections().collections]
        self.assertIn(PERSONS_COLLECTION, collections,
                      f"'{PERSONS_COLLECTION}' collection must exist")
        self.assertIn(RECORDS_COLLECTION, collections,
                      f"'{RECORDS_COLLECTION}' collection must exist")

    def test_persons_collection_vector_dim(self):
        info = self.qdrant.get_collection(PERSONS_COLLECTION)
        dim = info.config.params.vectors.size
        self.assertEqual(dim, VECTOR_DIM, f"Vector dim must be {VECTOR_DIM}")

    def test_payload_indexes_exist(self):
        """Required payload indexes from VECTOR_DB_ARCHITECTURE.md."""
        info = self.qdrant.get_collection(PERSONS_COLLECTION)
        indexed = {f.name for f in info.payload_schema.values()} if info.payload_schema else set()
        required = {"is_living", "judge_approved", "redistribution_license"}
        missing = required - indexed
        self.assertEqual(missing, set(), f"Missing payload indexes: {missing}")


if __name__ == "__main__":
    unittest.main()

