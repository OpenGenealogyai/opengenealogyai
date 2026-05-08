"""
DeepAncestorWalker — BFS ancestry walk up to 20 generations back from all famous people.

Usage:
    python scripts/deep_ancestor_walker.py

Resumes automatically from _ancestor_queue.json if interrupted.
Progress is checkpointed every 100 records.
"""

import json
import os
import sys
import time
import logging
import tempfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from pipeline.throttle import wait_for_internet, internet_level, gpu_level, cpu_level, claude_level, status_line  # noqa: E402

DATA_DIR        = BASE_DIR / "data" / "famous_people"
LOG_DIR         = BASE_DIR / "_logs"
THROTTLE_DIR    = BASE_DIR / "_throttle"

PROGRESS_FILE   = DATA_DIR / "_progress.json"
QUEUE_FILE      = DATA_DIR / "_ancestor_queue.json"
STATS_FILE      = DATA_DIR / "_walker_stats.json"
DEPTHS_FILE     = THROTTLE_DIR / "ancestor_depths.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
THROTTLE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = LOG_DIR / "deep_ancestor_walker.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("DeepAncestorWalker")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = (
    "OpenGenealogyAI-DeepAncestorWalker/1.0 "
    "(https://opengenealogyai.org; research@opengenealogyai.org)"
)
MAX_DEPTH         = 20
RETRY_429_SLEEP   = 60
NETWORK_ERR_SLEEP = 10
CHECKPOINT_EVERY  = 100
ESTIMATED_TOTAL   = 2_000_000

import requests

# ---------------------------------------------------------------------------
# SPARQL template (same as famous_people_fetcher)
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _val(row: dict, key: str) -> str | None:
    cell = row.get(key)
    if cell is None:
        return None
    return cell.get("value")


def _qid_from_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    return uri.rsplit("/", 1)[-1] if uri.startswith("http") else uri


def _date_value(row: dict, key: str) -> str | None:
    raw = _val(row, key)
    if not raw:
        return None
    return raw.lstrip("+").split("T")[0]


def atomic_write_json(path: Path, data) -> None:
    """Write JSON atomically via temp file + os.replace()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

# ---------------------------------------------------------------------------
# Progress / queue / stats / depths I/O
# ---------------------------------------------------------------------------

def load_progress() -> set:
    """Return set of all QIDs already downloaded (from _progress.json)."""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_progress(done: set) -> None:
    atomic_write_json(PROGRESS_FILE, sorted(done))


def load_queue() -> deque:
    """Load BFS queue from checkpoint file."""
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, encoding="utf-8") as f:
                items = json.load(f)
            return deque(items)
        except Exception:
            return deque()
    return deque()


def save_queue(queue: deque) -> None:
    atomic_write_json(QUEUE_FILE, list(queue))


def load_depths() -> dict:
    """Load {qid: min_depth} map."""
    if DEPTHS_FILE.exists():
        try:
            with open(DEPTHS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_depths(depths: dict) -> None:
    atomic_write_json(DEPTHS_FILE, depths)


def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_stats(stats: dict) -> None:
    atomic_write_json(STATS_FILE, stats)

# ---------------------------------------------------------------------------
# Bootstrap: build initial queue from existing famous_people records
# ---------------------------------------------------------------------------

def bootstrap_queue(visited: set) -> tuple[deque, dict]:
    """
    Read all famous_people records, collect parent QIDs not yet downloaded.
    Returns (queue, depths).
    Queue items: {"qid": "Q123", "depth": 1}
    Depths: {qid: 1}  (all parents start at depth 1)
    """
    log.info("Bootstrapping queue from existing famous_people records ...")
    queue_items: dict[str, int] = {}  # qid -> min depth seen

    files = [
        f for f in DATA_DIR.iterdir()
        if f.suffix == ".json" and not f.name.startswith("_") and f.stem.startswith("Q")
    ]
    log.info("Scanning %d famous_people Q-records ...", len(files))

    for fpath in files:
        try:
            rec = json.load(open(fpath, encoding="utf-8"))
        except Exception:
            continue
        ext = rec.get("extracted", {})
        for parent_key in ("father_qid", "mother_qid"):
            pqid = ext.get(parent_key)
            if pqid and pqid.startswith("Q") and pqid not in visited:
                # depth 1 = direct parent of a famous person
                existing = queue_items.get(pqid, 999)
                if 1 < existing:
                    queue_items[pqid] = 1

    queue = deque({"qid": qid, "depth": d} for qid, d in queue_items.items())
    depths = dict(queue_items)
    log.info("Bootstrap complete — %d unique parent QIDs to queue", len(queue))
    return queue, depths

# ---------------------------------------------------------------------------
# Wikidata fetch
# ---------------------------------------------------------------------------

def sparql_query(qid: str) -> dict | None:
    """
    Execute SPARQL for one QID. Returns first result row or None.
    Handles 429 (sleep+retry), 404/410/451 (skip), network errors (retry 3x).
    Returns the string "SKIP" for permanent errors to distinguish from network failures.
    """
    query = SPARQL_TEMPLATE.format(QID=qid)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    }
    params = {"query": query, "format": "json"}

    retries = 0
    while True:
        try:
            wait_for_internet()
            resp = requests.get(WIKIDATA_SPARQL, params=params, headers=headers, timeout=30)

            if resp.status_code == 429:
                log.warning("HTTP 429 — rate limited. Sleeping %ds ...", RETRY_429_SLEEP)
                time.sleep(RETRY_429_SLEEP)
                continue

            if resp.status_code in (404, 410, 451):
                log.debug("HTTP %d for %s — skipping permanently", resp.status_code, qid)
                return "SKIP"

            resp.raise_for_status()
            results = resp.json().get("results", {}).get("bindings", [])
            return results[0] if results else None

        except requests.RequestException as exc:
            retries += 1
            if retries >= 3:
                log.error("Network error for %s after 3 retries: %s", qid, exc)
                return None
            log.warning("Network error for %s (retry %d/3): %s", qid, retries, exc)
            time.sleep(NETWORK_ERR_SLEEP)

# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------

def build_ancestor_record(
    qid: str,
    row: dict,
    depth: int,
    ancestor_of: list[str],
) -> dict:
    name = _val(row, "personLabel") or qid
    father_uri = _val(row, "father")
    mother_uri = _val(row, "mother")

    # Pick the most famous descendant for the privacy label
    famous_desc = ancestor_of[0] if ancestor_of else None

    return {
        "schema_version": "0.1",
        "record_type": "ancestor",
        "source": "wikidata",
        "source_id": qid,
        "source_url": f"https://www.wikidata.org/wiki/{qid}",
        "url": f"https://www.wikidata.org/wiki/{qid}",
        "contributor": {
            "name": "DeepAncestorWalker/1.0",
            "type": "automated",
        },
        "privacy": {
            "is_living": False,
            "famous_descendant": famous_desc,
        },
        "ancestor_of": ancestor_of,
        "generation_depth": depth,
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
        "confidence": 0.90,
        "embedded_at": None,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }


def save_record(record: dict) -> None:
    qid = record["source_id"]
    out_path = DATA_DIR / f"{qid}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Stats tracking
# ---------------------------------------------------------------------------

def update_stats(stats: dict, total: int, queue_size: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    started_at = stats.get("started_at", now)

    # Compute rate
    start_dt = datetime.fromisoformat(started_at)
    now_dt = datetime.fromisoformat(now)
    elapsed_hours = max((now_dt - start_dt).total_seconds() / 3600, 0.001)
    baseline = stats.get("_baseline_count", 0)
    baseline_total = total - baseline
    rate = baseline_total / elapsed_hours if elapsed_hours > 0 else 0

    remaining = max(ESTIMATED_TOTAL - total, 0)
    eta_hours = remaining / rate if rate > 0 else 9999

    stats.update({
        "total_downloaded": total,
        "queue_size": queue_size,
        "started_at": started_at,
        "last_updated": now,
        "records_per_hour": round(rate),
        "estimated_hours_remaining": round(eta_hours, 1),
    })
    return stats

# ---------------------------------------------------------------------------
# Main BFS loop
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 60)
    log.info("Deep Ancestor Walker starting")
    log.info("Output dir: %s", DATA_DIR)
    log.info("Max depth:  %d generations", MAX_DEPTH)
    log.info("=" * 60)

    # --- Load state ---
    visited = load_progress()
    depths = load_depths()
    stats = load_stats()

    resuming = QUEUE_FILE.exists()
    if resuming:
        log.info("Resuming from checkpoint: %s", QUEUE_FILE)
        queue = load_queue()
        log.info("Checkpoint queue size: %d", len(queue))
    else:
        log.info("No checkpoint found — bootstrapping from existing records ...")
        queue, depths = bootstrap_queue(visited)
        save_depths(depths)
        save_queue(queue)

    initial_queue_size = len(queue)

    # Initialize stats baseline
    if "started_at" not in stats:
        stats["started_at"] = datetime.now(timezone.utc).isoformat()
        stats["_baseline_count"] = len(visited)
        save_stats(stats)

    t = {"internet": internet_level(), "gpu": gpu_level(), "cpu": cpu_level(), "claude": claude_level()}
    print()
    print("Deep Ancestor Walker starting")
    print(f"Already downloaded:      {len(visited):,} records")
    print(f"Initial queue:           {initial_queue_size:,} ancestor QIDs")
    print(f"Max depth:               {MAX_DEPTH} generations")
    print(f"Throttle:                internet={t['internet']}  gpu={t['gpu']}  cpu={t['cpu']}  claude={t['claude']}")
    print(f"Estimated total records: ~{ESTIMATED_TOTAL:,}")
    print()

    total_this_session = 0
    total_skipped = 0

    # Deepest gen tracking: (depth, qid, name)
    deepest = (0, "", "")

    # --- BFS loop ---
    while queue:
        item = queue.popleft()
        qid   = item["qid"]
        depth = item["depth"]

        # Skip if already visited or beyond depth limit
        if qid in visited:
            continue
        if depth > MAX_DEPTH:
            visited.add(qid)
            continue

        # Fetch from Wikidata
        result = sparql_query(qid)

        # Permanent skip
        if result == "SKIP" or result is None:
            if result == "SKIP":
                log.debug("Permanent skip: %s", qid)
            else:
                log.warning("No data returned for %s (depth=%d) — skipping", qid, depth)
            visited.add(qid)
            total_skipped += 1
            # Still checkpoint periodically
            if (total_this_session + total_skipped) % CHECKPOINT_EVERY == 0:
                save_progress(visited)
            continue

        # Build ancestor_of list: inherit from known depths file
        # Since we don't track which famous person per ancestor in the queue for memory efficiency,
        # we use a best-effort list from the record's parent chain.
        # For now, store as empty list — can be enriched by a later pass.
        ancestor_of: list[str] = []

        # Update minimum depth
        existing_depth = depths.get(qid, 999)
        if depth < existing_depth:
            depths[qid] = depth

        record = build_ancestor_record(qid, result, depth, ancestor_of)
        save_record(record)
        visited.add(qid)
        total_this_session += 1

        name = record["extracted"].get("name", qid)

        # Track deepest
        if depth > deepest[0]:
            deepest = (depth, qid, name)

        # Queue parents if within depth limit
        if depth < MAX_DEPTH:
            father_qid = record["extracted"].get("father_qid")
            mother_qid = record["extracted"].get("mother_qid")
            for parent_qid in (father_qid, mother_qid):
                if parent_qid and parent_qid.startswith("Q") and parent_qid not in visited:
                    parent_depth = depth + 1
                    # Only queue if this is a shallower path than seen before
                    existing = depths.get(parent_qid, 999)
                    if parent_depth < existing:
                        depths[parent_qid] = parent_depth
                        queue.append({"qid": parent_qid, "depth": parent_depth})

        total_so_far = len(visited)

        # Checkpoint every 100 records
        if total_this_session % CHECKPOINT_EVERY == 0:
            save_queue(queue)
            save_progress(visited)
            save_depths(depths)
            stats = update_stats(stats, total_so_far, len(queue))
            save_stats(stats)
            rate = stats.get("records_per_hour", 0)
            eta  = stats.get("estimated_hours_remaining", 0)
            log.info(
                "[%d] depth=%d | name=%s | queue=%d | skipped=%d | %s | rate=%d/hr | ETA=%.1fh",
                total_so_far, depth, name, len(queue), total_skipped, status_line(), rate, eta
            )

    # Final checkpoint
    save_queue(queue)
    save_progress(visited)
    save_depths(depths)
    stats = update_stats(stats, len(visited), len(queue))
    save_stats(stats)

    log.info("=" * 60)
    log.info("DONE. Total ever downloaded: %d", len(visited))
    log.info("Records this session:        %d", total_this_session)
    log.info("Skipped (no data):           %d", total_skipped)
    log.info("Deepest gen reached:         %d (%s — %s)", *deepest)
    log.info("Queue remaining:             %d", len(queue))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
