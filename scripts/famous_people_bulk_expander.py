"""
FamousPeopleBulkExpander — Queries Wikidata SPARQL for 10,000 notable deceased
people with parent data, merges into seed_list.json, then launches the fetcher.

Usage:
    python scripts/famous_people_bulk_expander.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
SEED_FILE  = BASE_DIR / "data" / "famous" / "seed_list.json"
PROGRESS_FILE = BASE_DIR / "data" / "famous_people" / "_progress.json"
LOG_DIR = BASE_DIR / "_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": (
        "OpenGenealogyAI-BulkExpander/1.0 "
        "(https://opengenealogyai.org; research@opengenealogyai.org)"
    ),
}

# ---------------------------------------------------------------------------
# SPARQL query — try decreasing LIMITs on timeout
# ---------------------------------------------------------------------------

SPARQL_QUERY = """
SELECT DISTINCT ?person ?personLabel ?sitelinks WHERE {{
  ?person wdt:P31 wd:Q5 .
  ?person wdt:P570 ?death .
  {{ ?person wdt:P22 ?father }} UNION {{ ?person wdt:P25 ?mother }}
  ?person wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= 5)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}
ORDER BY DESC(?sitelinks)
LIMIT {limit}
"""

LIMITS_TO_TRY = [10000, 5000, 3000, 1000]


def run_sparql_query(limit: int) -> list[dict]:
    """Run bulk SPARQL query. Returns list of {person, personLabel, sitelinks} dicts."""
    query = SPARQL_QUERY.format(limit=limit)
    params = {"query": query, "format": "json"}
    print(f"  Querying Wikidata SPARQL (LIMIT {limit:,}) — up to 90s ...")
    resp = requests.get(SPARQL_URL, params=params, headers=HEADERS, timeout=90)
    resp.raise_for_status()
    return resp.json().get("results", {}).get("bindings", [])


def bulk_query_with_retry() -> list[dict]:
    """Try query with decreasing LIMITs until one succeeds."""
    for limit in LIMITS_TO_TRY:
        try:
            results = run_sparql_query(limit)
            print(f"  Query succeeded: {len(results):,} results at LIMIT {limit:,}")
            return results
        except requests.exceptions.Timeout:
            print(f"  Timeout at LIMIT {limit:,} — retrying with smaller limit ...")
            time.sleep(3)
        except requests.exceptions.RequestException as exc:
            print(f"  Request error at LIMIT {limit:,}: {exc}")
            time.sleep(5)
    print("  All SPARQL attempts failed.")
    return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def qid_from_uri(uri: str) -> str:
    """Convert Wikidata URI to bare QID."""
    return uri.rsplit("/", 1)[-1] if uri.startswith("http") else uri


def load_json_set(path: Path) -> set:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return set(data)
        except Exception:
            pass
    return set()


def load_seed_list(path: Path) -> list[dict]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("FamousPeopleBulkExpander")
    print("=" * 60)

    # Step 1 — Bulk SPARQL query
    print("\n[Step 1] Running bulk Wikidata SPARQL query ...")
    sparql_results = bulk_query_with_retry()
    if not sparql_results:
        print("ERROR: No results returned. Aborting.")
        sys.exit(1)

    # Step 2 — Load existing data
    print("\n[Step 2] Merging with existing seed list ...")
    existing_seed = load_seed_list(SEED_FILE)
    already_done  = load_json_set(PROGRESS_FILE)

    # Build set of QIDs already in seed list
    existing_qids = {entry.get("wikidata_id") for entry in existing_seed if entry.get("wikidata_id")}

    # Parse SPARQL results into new entries
    new_entries: list[dict] = []
    skipped_done = 0
    skipped_existing = 0

    for row in sparql_results:
        person_uri   = row.get("person", {}).get("value", "")
        label        = row.get("personLabel", {}).get("value", "")
        sitelinks_raw = row.get("sitelinks", {}).get("value", "0")

        if not person_uri:
            continue

        qid = qid_from_uri(person_uri)

        # Skip if URI didn't resolve to a QID
        if not qid.startswith("Q"):
            continue

        # Skip already-downloaded
        if qid in already_done:
            skipped_done += 1
            continue

        # Skip already in seed list
        if qid in existing_qids:
            skipped_existing += 1
            continue

        # Use QID as label if Wikidata returned the URI instead of a name
        if label == person_uri or not label:
            label = qid

        try:
            sitelinks = int(sitelinks_raw)
        except ValueError:
            sitelinks = 0

        new_entries.append({
            "famous_person": label,
            "wikidata_id": qid,
            "living": False,
            "sitelinks": sitelinks,
            "source": "bulk_query",
        })

    # Build merged list: existing entries first (preserving order), then new
    merged = existing_seed + new_entries

    # Write updated seed list
    SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEED_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    already_done_count = len(already_done)
    new_count          = len(new_entries)
    total_count        = len(merged)

    print(f"  Already downloaded (skipped): {already_done_count:,}")
    print(f"  Already in seed list (skipped): {skipped_existing:,}")
    print(f"  New people queued: {new_count:,}")
    print(f"  Total seed list: {total_count:,}")
    print(f"  Seed file written: {SEED_FILE}")

    print(f"\nFound {new_count:,} new people to download "
          f"({already_done_count:,} already done, {total_count:,} total)")

    # Step 3 — Launch fetcher in background
    print("\n[Step 3] Starting famous_people_fetcher.py in background ...")
    proc = subprocess.Popen(
        [sys.executable, "scripts/famous_people_fetcher.py"],
        cwd=str(BASE_DIR),
    )

    print(f"  Fetcher PID: {proc.pid}")
    print(f"  Log: {LOG_DIR / 'famous_people_download.log'}")

    # Step 4 — Summary
    print()
    print("=" * 60)
    print("=== Bulk Expander Complete ===")
    print(f"New people queued:   {new_count:,}")
    print(f"Already downloaded:  {already_done_count:,}")
    print(f"Total seed list:     {total_count:,}")
    print(f"Fetcher running in background — PID: {proc.pid}")
    print("Check progress: python scripts/throttle.py status")
    print("=" * 60)


if __name__ == "__main__":
    main()
