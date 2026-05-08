"""
FamousPeopleFetcher — Downloads genealogy data from Wikidata for famous people.
NO embedding, NO GPU, NO Ollama. Pure HTTP requests -> JSON files on disk.

Usage:
    python scripts/famous_people_fetcher.py
"""

import json
import os
import time
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from pipeline.throttle import wait_for_internet, internet_level, internet_concurrency  # noqa: E402
DATA_DIR = BASE_DIR / "data" / "famous_people"
SEED_FILE = BASE_DIR / "data" / "famous" / "seed_list.json"
PROGRESS_FILE = DATA_DIR / "_progress.json"
LOG_DIR = BASE_DIR / "_logs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = LOG_DIR / "famous_people_download.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("FamousPeopleFetcher")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = (
    "OpenGenealogyAI-FamousPeopleFetcher/1.0 "
    "(https://opengenealogyai.org; research@opengenealogyai.org)"
)
MAX_GENERATIONS = 5
RATE_LIMIT_SLEEP = 1.0      # seconds between requests
RETRY_429_SLEEP = 60        # seconds to wait on HTTP 429

# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------

def load_progress() -> set:
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_progress(done: set) -> None:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(done), f, indent=2)

# ---------------------------------------------------------------------------
# Wikidata query
# ---------------------------------------------------------------------------

SPARQL_TEMPLATE = """
SELECT ?person ?personLabel ?birthDate ?birthPlace ?birthPlaceLabel
       ?deathDate ?deathPlace ?deathPlaceLabel
       ?father ?fatherLabel ?fatherBirth ?fatherDeath
       ?mother ?motherLabel ?motherBirth ?motherDeath
       ?occupation ?occupationLabel ?nationality ?nationalityLabel
WHERE {{
  BIND(wd:{QID} AS ?person)
  OPTIONAL {{ ?person wdt:P569 ?birthDate }}
  OPTIONAL {{ ?person wdt:P19  ?birthPlace }}
  OPTIONAL {{ ?person wdt:P570 ?deathDate }}
  OPTIONAL {{ ?person wdt:P20  ?deathPlace }}
  OPTIONAL {{ ?person wdt:P22  ?father .
              OPTIONAL {{ ?father wdt:P569 ?fatherBirth }}
              OPTIONAL {{ ?father wdt:P570 ?fatherDeath }} }}
  OPTIONAL {{ ?person wdt:P25  ?mother .
              OPTIONAL {{ ?mother wdt:P569 ?motherBirth }}
              OPTIONAL {{ ?mother wdt:P570 ?motherDeath }} }}
  OPTIONAL {{ ?person wdt:P106 ?occupation }}
  OPTIONAL {{ ?person wdt:P27  ?nationality }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}
LIMIT 1
"""


def sparql_query(qid: str) -> dict | None:
    """Execute a SPARQL query for a single Wikidata QID. Returns first result row or None."""
    query = SPARQL_TEMPLATE.format(QID=qid)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    }
    params = {"query": query, "format": "json"}

    while True:
        try:
            wait_for_internet()
            resp = requests.get(
                WIKIDATA_SPARQL,
                params=params,
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 429:
                log.warning("HTTP 429 — rate limited. Sleeping %ds ...", RETRY_429_SLEEP)
                time.sleep(RETRY_429_SLEEP)
                continue
            resp.raise_for_status()
            results = resp.json().get("results", {}).get("bindings", [])
            return results[0] if results else None
        except requests.RequestException as exc:
            log.error("Request error for %s: %s", qid, exc)
            return None


def _val(row: dict, key: str) -> str | None:
    """Extract a plain string value from a SPARQL result binding."""
    cell = row.get(key)
    if cell is None:
        return None
    return cell.get("value")


def _qid_from_uri(uri: str | None) -> str | None:
    """Convert a Wikidata entity URI to a bare QID, e.g. Q303."""
    if not uri:
        return None
    return uri.rsplit("/", 1)[-1] if uri.startswith("http") else uri


def _date_value(row: dict, key: str) -> str | None:
    raw = _val(row, key)
    if not raw:
        return None
    # Wikidata returns ISO 8601: +1935-01-08T00:00:00Z — strip the leading +
    return raw.lstrip("+").split("T")[0]

# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------

def build_record(
    qid: str,
    row: dict,
    is_living: bool = False,
    famous_descendant: str | None = None,
) -> dict:
    name = _val(row, "personLabel") or qid
    father_uri = _val(row, "father")
    mother_uri = _val(row, "mother")

    return {
        "schema_version": "0.1",
        "record_type": "person",
        "source": "wikidata",
        "source_id": qid,
        "source_url": f"https://www.wikidata.org/wiki/{qid}",
        "contributor": {
            "name": "FamousPeopleFetcher/1.0",
            "type": "automated",
        },
        "privacy": {
            "is_living": is_living,
            "famous_descendant": famous_descendant,
        },
        "extracted": {
            "name": name,
            "birth_date": _date_value(row, "birthDate"),
            "birth_place": _val(row, "birthPlaceLabel"),
            "death_date": _date_value(row, "deathDate"),
            "death_place": _val(row, "deathPlaceLabel"),
            "occupation": _val(row, "occupationLabel"),
            "nationality": _val(row, "nationalityLabel"),
            "father_qid": _qid_from_uri(father_uri),
            "father_name": _val(row, "fatherLabel"),
            "father_birth": _date_value(row, "fatherBirth"),
            "father_death": _date_value(row, "fatherDeath"),
            "mother_qid": _qid_from_uri(mother_uri),
            "mother_name": _val(row, "motherLabel"),
            "mother_birth": _date_value(row, "motherBirth"),
            "mother_death": _date_value(row, "motherDeath"),
        },
        "confidence": 0.95,
        "embedded_at": None,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }


def save_record(record: dict) -> None:
    qid = record["source_id"]
    out_path = DATA_DIR / f"{qid}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Ancestor walker (recursive up to MAX_GENERATIONS)
# ---------------------------------------------------------------------------

def fetch_and_save(
    qid: str,
    done: set,
    generation: int = 0,
    is_living: bool = False,
    famous_descendant: str | None = None,
) -> int:
    """
    Fetch a person from Wikidata, save to disk, and recursively walk parents.
    Returns count of new records saved.
    """
    if qid in done:
        return 0
    if generation > MAX_GENERATIONS:
        return 0

    wait_for_internet()
    row = sparql_query(qid)

    if row is None:
        log.warning("  No data returned for %s (gen %d)", qid, generation)
        done.add(qid)   # mark so we don't retry endlessly
        save_progress(done)
        return 0

    record = build_record(qid, row, is_living=is_living, famous_descendant=famous_descendant)
    save_record(record)
    done.add(qid)
    save_progress(done)
    count = 1

    # Walk parents
    father_qid = record["extracted"].get("father_qid")
    mother_qid = record["extracted"].get("mother_qid")

    if father_qid and father_qid not in done:
        count += fetch_and_save(
            father_qid, done,
            generation=generation + 1,
            is_living=False,
            famous_descendant=famous_descendant,
        )
    if mother_qid and mother_qid not in done:
        count += fetch_and_save(
            mother_qid, done,
            generation=generation + 1,
            is_living=False,
            famous_descendant=famous_descendant,
        )

    return count

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 60)
    log.info("FamousPeopleFetcher starting — NO GPU / NO embedding")
    log.info("Output: %s", DATA_DIR)
    log.info("Throttle: level=%d  max_concurrency=%d", internet_level(), internet_concurrency())
    log.info("=" * 60)

    # Load seed list
    with open(SEED_FILE, encoding="utf-8") as f:
        seed_list = json.load(f)

    # Sort: deceased first, then living
    deceased = [p for p in seed_list if not p.get("living", False)]
    living   = [p for p in seed_list if p.get("living", False)]
    ordered  = deceased + living

    total_people = len(ordered)
    done = load_progress()
    log.info("Seed list: %d people | Already done: %d QIDs", total_people, len(done))

    total_saved = 0
    failures = []

    for idx, entry in enumerate(ordered, start=1):
        qid        = entry["wikidata_id"]
        name       = entry["famous_person"]
        is_living  = entry.get("living", False)
        anchor     = entry.get("anchor_name")
        descendant = name if is_living else None

        label = f"[{idx}/{total_people}] {name} ({qid})"

        if qid in done:
            log.info("%s -> already downloaded, skipping", label)
            continue

        log.info("%s -> fetching ...", label)

        try:
            if is_living:
                # For living celebrities: fetch them once (privacy-safe reference),
                # then walk up from their anchor ancestor
                time.sleep(RATE_LIMIT_SLEEP)
                row = sparql_query(qid)
                if row:
                    record = build_record(qid, row, is_living=True, famous_descendant=None)
                    save_record(record)
                    done.add(qid)
                    save_progress(done)
                    total_saved += 1

                # Now walk parents (deceased ancestors) up to MAX_GENERATIONS
                father_qid = record["extracted"].get("father_qid") if row else None
                mother_qid = record["extracted"].get("mother_qid") if row else None
                ancestor_count = 0

                if father_qid and father_qid not in done:
                    ancestor_count += fetch_and_save(
                        father_qid, done,
                        generation=1,
                        is_living=False,
                        famous_descendant=name,
                    )
                if mother_qid and mother_qid not in done:
                    ancestor_count += fetch_and_save(
                        mother_qid, done,
                        generation=1,
                        is_living=False,
                        famous_descendant=name,
                    )

                log.info(
                    "%s -> %d ancestors found -> saved  (anchor: %s)",
                    label, ancestor_count, anchor or "n/a",
                )
                total_saved += ancestor_count

            else:
                # Deceased: full tree walk
                saved = fetch_and_save(
                    qid, done,
                    generation=0,
                    is_living=False,
                    famous_descendant=None,
                )
                ancestors = max(0, saved - 1)
                log.info("%s -> %d ancestors found -> saved", label, ancestors)
                total_saved += saved

        except Exception as exc:
            log.error("%s -> UNEXPECTED ERROR: %s", label, exc, exc_info=True)
            failures.append({"qid": qid, "name": name, "error": str(exc)})

    # Final summary
    log.info("=" * 60)
    log.info("DONE. Total records saved: %d", total_saved)
    log.info("Failures: %d", len(failures))
    for f in failures:
        log.info("  FAIL  %s (%s): %s", f["name"], f["qid"], f["error"])
    log.info("Progress file: %s", PROGRESS_FILE)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
