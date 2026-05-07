"""
Batch ingest Internet Archive genealogy collections into Qdrant.
Satisfies R5: 1,000+ records from open IA collections searchable by name+year.

Pipeline:
  1. Load curated collection list (ia_collections.json)
  2. Fetch item identifiers from each collection
  3. Convert to RawRecord (schema-validated)
  4. Build embedding payload (3-gram + Soundex stored as metadata)
  5. Upsert to Qdrant raw_records_v01 collection
  6. Log cost + progress

Usage:
  python scripts/ia_batch_ingest.py [--max-per-collection N] [--dry-run] [--collections COL1,COL2]
"""

import json, sys, os, re, time, argparse, hashlib, datetime
from pathlib import Path

# Fix root-relative imports
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "agents" / "ia-fetcher"))

from ia_fetcher import fetch_collection_items
from ia_to_rawrecord import ia_to_rawrecord, validate_rawrecord, infer_year_range

# ── Optional deps ──────────────────────────────────────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("[WARN] qdrant-client not installed — will run in --dry-run mode")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ── Config ─────────────────────────────────────────────────────────────────────
COLLECTIONS_FILE = REPO_ROOT / "agents" / "ia-fetcher" / "ia_collections.json"
sys.path.insert(0, str(REPO_ROOT))
from pipeline.paths import QDRANT_PATH as _QDRANT_PATH, LOGS as _LOGS_DIR

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_PATH = str(_QDRANT_PATH) if _QDRANT_PATH.exists() else os.environ.get("QDRANT_PATH", "")
COLLECTION_NAME = "raw_records_v01"
VECTOR_DIM = 1536
OPENAI_EMBED_MODEL = "text-embedding-3-small"
MAX_EMBED_CHARS = 1000   # truncate text before embedding
COST_PER_1K_TOKENS = 0.00002   # text-embedding-3-small price
APPROX_TOKENS_PER_RECORD = 150

LOG_FILE = _LOGS_DIR / "ia_batch_ingest.jsonl"

# ── Soundex ────────────────────────────────────────────────────────────────────
def soundex(name: str) -> str:
    name = re.sub(r"[^a-zA-Z]", "", name).upper()
    if not name:
        return "Z000"
    codes = {"BFPV": "1", "CGJKQSXYZ": "2", "DT": "3", "L": "4", "MN": "5", "R": "6"}
    first = name[0]
    result = first
    prev = "0"
    for ch in name[1:]:
        code = "0"
        for keys, val in codes.items():
            if ch in keys:
                code = val
                break
        if code != "0" and code != prev:
            result += code
        prev = code
        if len(result) == 4:
            break
    return (result + "000")[:4]


def name_to_ngrams(name: str, n: int = 3) -> list[str]:
    clean = re.sub(r"[^a-zA-Z ]", "", name).lower()
    tokens = clean.split()
    grams = []
    for token in tokens:
        padded = f"  {token}  "
        for i in range(len(padded) - n + 1):
            grams.append(padded[i:i+n])
    return grams


# ── Embedding ──────────────────────────────────────────────────────────────────
def get_embedding(text: str, client: "openai.OpenAI") -> list[float]:
    text = text[:MAX_EMBED_CHARS].replace("\n", " ")
    resp = client.embeddings.create(input=[text], model=OPENAI_EMBED_MODEL)
    return resp.data[0].embedding


def dummy_embedding(text: str) -> list[float]:
    """Deterministic placeholder when OpenAI is unavailable (dry-run / testing)."""
    h = hashlib.sha256(text.encode()).digest()
    base = [(b / 255.0) - 0.5 for b in h]
    # Extend to 1536 by repeating
    repeated = (base * (VECTOR_DIM // len(base) + 1))[:VECTOR_DIM]
    # Normalize
    norm = sum(x**2 for x in repeated) ** 0.5 or 1.0
    return [x / norm for x in repeated]


# ── Logging ────────────────────────────────────────────────────────────────────
def log_event(event: dict):
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ── Main ingest ────────────────────────────────────────────────────────────────
def build_payload(record: dict) -> dict:
    """Extract Qdrant filterable payload from RawRecord."""
    payload = {
        "record_id": record["record_id"],
        "record_type": record["record_type"],
        "redistribution_license": record["redistribution_license"],
        "is_living": record.get("is_living_flag", False),
        "repository": record.get("repository", ""),
        "language": record.get("language", "en"),
        "source_url": record.get("source_url", ""),
        "digital_object_id": record.get("digital_object_id", ""),
    }
    # Add persons for searchability
    persons = record.get("persons_mentioned", [])
    if persons:
        payload["person_names"] = [p["name_as_written"] for p in persons]
        payload["name_soundex"] = [soundex(p["name_as_written"]) for p in persons]
    else:
        payload["person_names"] = []
        payload["name_soundex"] = []

    # Date range
    rd = record.get("record_date", {})
    if rd:
        payload["year_min"] = rd.get("year_min")
        payload["year_max"] = rd.get("year_max")
    else:
        payload["year_min"] = None
        payload["year_max"] = None

    # Country from location
    loc = record.get("location", {})
    payload["country_code"] = loc.get("country_code", "")

    return payload


def ingest_batch(records: list[dict], qdrant: "QdrantClient", embed_fn, dry_run: bool) -> dict:
    """Embed and upsert a batch of RawRecords. Returns stats."""
    stats = {"ingested": 0, "skipped_living": 0, "skipped_invalid": 0, "errors": 0}

    points = []
    for record in records:
        # Skip living persons — never in public Qdrant
        if record.get("is_living_flag", True):
            stats["skipped_living"] += 1
            continue

        # Only open licenses in public collection
        if record.get("redistribution_license") not in ("CC0", "CC-BY", "CC-BY-SA", "public-domain"):
            stats["skipped_invalid"] += 1
            continue

        # Build embedding text from transcription + persons
        trans = record.get("transcription", "")
        person_str = " ".join(
            p["name_as_written"] for p in record.get("persons_mentioned", [])
        )
        embed_text = f"{person_str} {trans}".strip()[:MAX_EMBED_CHARS]

        try:
            vector = embed_fn(embed_text)
        except Exception as e:
            stats["errors"] += 1
            print(f"  [EMBED ERROR] {record['record_id']}: {e}", file=sys.stderr)
            continue

        payload = build_payload(record)
        # Use hash of record_id for numeric Qdrant point ID
        point_id = int(hashlib.sha256(record["record_id"].encode()).hexdigest()[:15], 16)
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))
        stats["ingested"] += 1

    if points and not dry_run:
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Batch ingest IA collections into Qdrant")
    parser.add_argument("--max-per-collection", type=int, default=60,
                        help="Max items to fetch per IA collection")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch + convert + validate but skip Qdrant upsert")
    parser.add_argument("--collections", type=str, default="",
                        help="Comma-separated collection IDs to process (default: all)")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Qdrant upsert batch size")
    args = parser.parse_args()

    dry_run = args.dry_run or not QDRANT_AVAILABLE

    # Load collections
    with open(COLLECTIONS_FILE, encoding="utf-8") as f:
        all_collections = json.load(f)

    if args.collections:
        filter_ids = set(args.collections.split(","))
        collections = [c for c in all_collections if c["id"] in filter_ids]
    else:
        collections = all_collections

    print(f"[START] {datetime.datetime.now().isoformat()}")
    print(f"[CONFIG] {len(collections)} collections, max {args.max_per_collection}/collection, dry_run={dry_run}")

    # Set up embedding
    if OPENAI_AVAILABLE and not dry_run:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("[WARN] OPENAI_API_KEY not set — using dummy embeddings")
            embed_fn = dummy_embedding
        else:
            oai = openai.OpenAI(api_key=api_key)
            embed_fn = lambda text: get_embedding(text, oai)
    else:
        embed_fn = dummy_embedding

    # Connect to Qdrant (embedded local path or remote server)
    qdrant = None
    if not dry_run and QDRANT_AVAILABLE:
        try:
            if QDRANT_PATH:
                from qdrant_client.models import Distance, VectorParams
                qdrant = QdrantClient(path=QDRANT_PATH)
                try:
                    qdrant.get_collection(COLLECTION_NAME)
                except Exception:
                    qdrant.create_collection(COLLECTION_NAME, vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE))
                print(f"[QDRANT] Embedded mode: {QDRANT_PATH} / {COLLECTION_NAME}")
            else:
                qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=10)
                qdrant.get_collection(COLLECTION_NAME)
                print(f"[QDRANT] Connected to {QDRANT_HOST}:{QDRANT_PORT} / {COLLECTION_NAME}")
        except Exception as e:
            print(f"[WARN] Qdrant not reachable ({e}) — switching to dry-run")
            dry_run = True

    totals = {"fetched": 0, "converted": 0, "validated": 0, "ingested": 0,
              "skipped_living": 0, "skipped_invalid": 0, "validation_errors": 0, "errors": 0}

    for col in collections:
        col_id = col["id"]
        record_type_hint = col.get("record_type")  # field name in ia_collections.json
        license_val = col.get("redistribution_license", "public-domain")
        col_year_min = col.get("year_min")
        col_year_max = col.get("year_max")

        print(f"\n[COLLECTION] {col_id} ({col.get('description', col.get('name', ''))})")

        try:
            items = fetch_collection_items(col_id, max_items=args.max_per_collection)
        except Exception as e:
            print(f"  [ERROR] Fetch failed: {e}")
            log_event({"ts": datetime.datetime.now().isoformat(), "event": "fetch_error",
                       "collection": col_id, "error": str(e)})
            continue

        totals["fetched"] += len(items)
        print(f"  Fetched {len(items)} items")

        records = []
        for item in items:
            item["collection_id"] = col_id
            record = ia_to_rawrecord(item, record_type_hint=record_type_hint,
                                     redistribution_license=license_val,
                                     collection_year_min=col_year_min,
                                     collection_year_max=col_year_max)
            totals["converted"] += 1

            # Schema validation
            valid, errors = validate_rawrecord(record)
            if not valid:
                totals["validation_errors"] += 1
                continue
            totals["validated"] += 1
            records.append(record)

        # Ingest in batches
        for i in range(0, len(records), args.batch_size):
            batch = records[i:i + args.batch_size]
            stats = ingest_batch(batch, qdrant, embed_fn, dry_run)
            for k, v in stats.items():
                totals[k] += v

        print(f"  Converted={len(records)}, ingested={sum(1 for r in records if not r.get('is_living_flag'))}")
        log_event({
            "ts": datetime.datetime.now().isoformat(),
            "event": "collection_done",
            "collection": col_id,
            "fetched": len(items),
            "records": len(records),
        })

        # Rate limit: be polite to IA
        time.sleep(0.5)

    # Summary
    print(f"\n{'='*60}")
    print(f"[DONE] {datetime.datetime.now().isoformat()}")
    print(f"  Fetched:            {totals['fetched']}")
    print(f"  Converted:          {totals['converted']}")
    print(f"  Validated:          {totals['validated']}")
    print(f"  Ingested to Qdrant: {totals['ingested']}")
    print(f"  Skipped (living):   {totals['skipped_living']}")
    print(f"  Skipped (license):  {totals['skipped_invalid']}")
    print(f"  Validation errors:  {totals['validation_errors']}")

    est_cost = (totals["ingested"] * APPROX_TOKENS_PER_RECORD / 1000) * COST_PER_1K_TOKENS
    print(f"  Est. embed cost:    ${est_cost:.4f}")

    log_event({
        "ts": datetime.datetime.now().isoformat(),
        "event": "ingest_complete",
        "totals": totals,
        "estimated_cost_usd": round(est_cost, 6),
        "dry_run": dry_run,
    })

    if totals["ingested"] < 1000 and not dry_run:
        print(f"\n[WARN] Only {totals['ingested']} records ingested (target: 1000+)")
        print("  Increase --max-per-collection or add more collections to ia_collections.json")


if __name__ == "__main__":
    main()




