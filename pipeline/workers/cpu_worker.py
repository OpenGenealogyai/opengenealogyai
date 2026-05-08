"""
CPU Worker Pool — spaCy NER + RawRecord schema conversion + validator stack.

10-process pool scanning source directories for unprocessed raw files.
Each worker: reads text → spaCy NER → build extraction record →
  run all 5 Phase 1 validators → PASS→embed queue | REJECT→log | QUARANTINE→quarantine dir.

RED LINE: no record enters the embed queue without clearing all validators.
"""

import json, datetime, time, uuid, sqlite3, sys, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline.paths import RAW, LOGS, CHECKPOINTS

# Thread-local spaCy model — loaded once per thread, not per file
_thread_local = threading.local()

def _get_nlp():
    if not hasattr(_thread_local, "nlp"):
        try:
            import spacy
            try:
                _thread_local.nlp = spacy.load("en_core_web_sm")
            except OSError:
                _thread_local.nlp = spacy.blank("en")
        except ImportError:
            _thread_local.nlp = None
    return _thread_local.nlp

# Validators live in the data root project, not the code root
_VALIDATOR_ROOT = Path("D:/AI/Companies/open-genealogical-ai")
if str(_VALIDATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_VALIDATOR_ROOT))

EMBED_QUEUE_DIR = CHECKPOINTS / "embed_queue"
CHECKPOINT_DB   = CHECKPOINTS / "pipeline.db"
LOW_QUALITY_DIR = CHECKPOINTS / "low_quality"
PAUSE_FILE      = LOGS / "PAUSE_DOWNLOADS"

NUM_WORKERS   = 10
SCAN_INTERVAL = 30  # seconds between directory scans
BATCH_CAP     = 5000  # max files per processing round to bound memory and commit time

_VALID_RECORD_TYPES = {
    "person", "birth", "death", "marriage", "census_row",
    "immigration_record", "land_patent", "newspaper_article",
    "military_record", "probate", "other",
}
_RECORD_TYPE_MAP = {
    "book":             "other",
    "item":             "other",
    "archival_record":  "other",
    "newspaper_page":   "newspaper_article",
    "photograph":       "other",
    "text":             "other",
    "image":            "other",
}

def _norm_record_type(rt: str) -> str:
    if rt in _VALID_RECORD_TYPES:
        return rt
    return _RECORD_TYPE_MAP.get(rt.lower() if rt else "", "other")

SOURCE_DIRS: dict[str, Path] = {
    "wikidata":            RAW.wikidata,
    "chronicling_america": RAW.chronicling,
    "internet_archive":    RAW.internet_archive,
    "blm_land_patents":    RAW.blm_land_patents,
    "open_library":        RAW.open_library,
    "dpla":                RAW.dpla,
}


# ── Database helpers ────────────────────────────────────────────────────────────

def _init_db() -> sqlite3.Connection:
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS records (
            url         TEXT PRIMARY KEY,
            source      TEXT,
            status      TEXT,
            quality     REAL,
            embedded_at DATETIME
        )
    """)
    con.commit()
    return con


def _already_processed(con: sqlite3.Connection, url: str) -> bool:
    row = con.execute("SELECT status FROM records WHERE url=?", (url,)).fetchone()
    return row is not None


def _mark_processing(con: sqlite3.Connection, url: str, source: str):
    con.execute(
        "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
        (url, source, "processing", None),
    )
    con.commit()


# ── Worker function (runs in subprocess) ───────────────────────────────────────

def process_file(args: tuple) -> dict | None:
    """
    Process one raw file. Runs in a subprocess — must not share any state.
    Returns a RawRecord dict on success, None if the record should be skipped.
    """
    file_path_str, source_name = args
    file_path = Path(file_path_str)

    nlp = _get_nlp()

    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")

        record: dict = {}
        text = raw
        if raw.strip().startswith("{"):
            try:
                record = json.loads(raw)
                text = record.get("text", raw)
            except json.JSONDecodeError:
                pass

        text = (text or "").strip()
        if len(text) < 10:
            return None

        # spaCy NER (cap at 10k chars for throughput)
        if nlp is not None:
            doc = nlp(text[:10000])
            person_ents = [e.text for e in doc.ents if e.label_ == "PERSON"]
            date_ents   = [e.text for e in doc.ents if e.label_ in ("DATE", "TIME")]
            loc_ents    = [e.text for e in doc.ents if e.label_ in ("GPE", "LOC")]
        else:
            person_ents, date_ents, loc_ents = [], [], []

        quality = _score(text, bool(person_ents), bool(date_ents), bool(loc_ents))

        url = record.get("url") or f"file://{file_path_str}"

        # Build extraction record in validator schema format
        source_file_id = str(file_path.relative_to(
            Path("D:/AI/Companies/open-genealogical-ai/rawdata")
        )) if "rawdata" in str(file_path) else file_path.name

        extraction = {
            # Required by Layer 0
            "record_type":    _norm_record_type(record.get("record_type", "other")),
            "source_file_id": source_file_id,
            "source_quote":   text[:200].strip(),
            "source_offset":  0,
            # Identity (NER-derived)
            "given_name":     person_ents[0].split()[0] if person_ents else None,
            "surname":        person_ents[0].split()[-1] if person_ents and len(person_ents[0].split()) > 1 else None,
            "name_raw":       person_ents[0] if person_ents else None,
            # Dates
            "birth_year":     None,
            "death_year":     None,
            "event_year":     record.get("year"),
            # Places
            "birth_place":    None,
            "death_place":    None,
            "state":          record.get("state"),
        }

        # Run validator pipeline
        try:
            from validators.pipeline import validate_record, Verdict
            vr = validate_record(extraction, source_text=text)
            if vr.verdict == Verdict.REJECT:
                print(f"[CPU] REJECT {file_path.name}: {vr.all_errors[:2]}")
                return {"_verdict": "REJECT", "url": url, "source": source_name}
            if vr.verdict == Verdict.QUARANTINE:
                print(f"[CPU] QUARANTINE {file_path.name}")
                return {"_verdict": "QUARANTINE", "url": url, "source": source_name}
        except Exception as ve:
            # Validator import failure → quarantine, don't embed
            print(f"[CPU] Validator error on {file_path.name}: {ve}")
            return {"_verdict": "QUARANTINE", "url": url, "source": source_name}

        return {
            "_verdict":    "PASS",
            "url":         url,
            "source":      source_name,
            "text":        text[:5000],
            "quality":     quality,
            "record_type": record.get("record_type", "unknown"),
            "payload": {
                "title":        record.get("title", file_path.stem),
                "year":         record.get("year"),
                "names":        person_ents[:10],
                "dates":        date_ents[:5],
                "locations":    loc_ents[:5],
                "source_file":  file_path.name,
                "processed_at": datetime.datetime.utcnow().isoformat() + "Z",
            },
        }

    except Exception as e:
        print(f"[CPU] Error on {file_path.name}: {e}")
        return None


def _score(text: str, has_person: bool, has_date: bool, has_loc: bool) -> float:
    """Heuristic quality score — same formula in all subprocesses."""
    score = 0.30
    if has_person: score += 0.25
    if has_date:   score += 0.20
    if has_loc:    score += 0.15
    if len(text) > 100: score += 0.10
    return min(round(score, 3), 1.0)


# ── Queue + checkpoint writers ──────────────────────────────────────────────────

def _write_to_embed_queue(record: dict):
    EMBED_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    out = EMBED_QUEUE_DIR / f"{uuid.uuid4().hex}.json"
    out.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def _write_to_low_quality(record: dict):
    LOW_QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    out = LOW_QUALITY_DIR / f"{uuid.uuid4().hex}.json"
    out.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


# ── Scanner ─────────────────────────────────────────────────────────────────────

_TERMINAL_STATUSES = (
    "embedded", "rejected", "low_quality",
    "queued_low", "queued_medium", "queued_high",
)

def _scan_for_work(con: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return (file_path_str, source_name) for every unprocessed .txt / .json file.

    Loads only *completed* file:// URLs into a skip-set — stale 'processing'
    rows (from crashed runs) are retried rather than permanently skipped.
    O(1 bulk_load + N × set_lookup) vs old O(N × db_query).
    """
    placeholders = ",".join("?" * len(_TERMINAL_STATUSES))
    processed = {
        row[0] for row in
        con.execute(
            f"SELECT url FROM records WHERE url LIKE 'file://%' AND status IN ({placeholders})",
            _TERMINAL_STATUSES,
        )
    }
    work = []
    for source_name, source_dir in SOURCE_DIRS.items():
        if not source_dir.exists():
            continue
        for ext in ("*.txt", "*.json"):
            for f in source_dir.rglob(ext):
                if f"file://{f}" not in processed:
                    work.append((str(f), source_name))
    return work


# ── Main loop ───────────────────────────────────────────────────────────────────

def run_pool():
    """Main CPU worker pool — runs forever."""
    print(f"[CPU] Worker pool starting ({NUM_WORKERS} workers)")
    EMBED_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    LOW_QUALITY_DIR.mkdir(parents=True, exist_ok=True)

    con = _init_db()

    while True:
        work = _scan_for_work(con)

        if not work:
            time.sleep(SCAN_INTERVAL)
            continue

        work = work[:BATCH_CAP]
        print(f"[CPU] Found {len(work)} files to process")

        # Stamp all as processing in one transaction before dispatching
        con.executemany(
            "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
            [(f"file://{fp}", sn, "processing", None) for fp, sn in work],
        )
        con.commit()

        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = {pool.submit(process_file, item): item for item in work}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    record = future.result()
                    if record is None:
                        continue

                    url      = record["url"]
                    source   = record["source"]
                    file_url = f"file://{item[0]}"  # canonical file:// key
                    verdict  = record.get("_verdict", "PASS")

                    if verdict == "REJECT":
                        status = "rejected"
                    elif verdict == "QUARANTINE":
                        status = "quarantined"
                    else:
                        quality = record.get("quality", 0.0)
                        if quality >= 0.35:
                            _write_to_embed_queue(record)
                            status = ("queued_high" if quality >= 0.75
                                      else "queued_medium" if quality >= 0.55
                                      else "queued_low")
                        else:
                            _write_to_low_quality(record)
                            status = "low_quality"

                    quality = record.get("quality")

                    # HTTP URL: INSERT OR IGNORE so we never downgrade an already-
                    # terminal status (e.g. "embedded" → "queued_low").
                    con.execute(
                        "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
                        (url, source, status, quality),
                    )

                    # file:// URL: always replace so stale "processing" rows clear.
                    con.execute(
                        "INSERT OR REPLACE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
                        (file_url, source, status, quality),
                    )
                    con.commit()

                except Exception as e:
                    print(f"[CPU] Worker error on {item[0]}: {e}")

        time.sleep(5)


if __name__ == "__main__":
    run_pool()
