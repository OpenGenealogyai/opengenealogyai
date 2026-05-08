"""
NARA Catalog Fetcher — National Archives and Records Administration.

Sweeps the NARA Catalog API v2 for genealogy-relevant record items using
a set of subject search terms. Paginates each term fully before moving to
the next term, then restarts the cycle indefinitely so newly-added records
are eventually captured.

Rate: 1 request every 8 seconds.
On 429: back off 30 minutes.

Output: RAW.nara/ — one JSON file per catalog item, named by naId.
Checkpoint: records table in pipeline.db, keyed by catalog URL.
"""

import json, time, sqlite3, hashlib
from pathlib import Path

import requests

from pipeline.paths import RAW, LOGS, CHECKPOINTS

# ── Constants ────────────────────────────────────────────────────────────────

SEARCH_URL     = "https://catalog.archives.gov/api/v2/records/search"
RECORD_URL_TPL = "https://catalog.archives.gov/id/{naId}"

# Use RAW.nara if the attribute exists; fall back gracefully.
_RAW_NARA = getattr(RAW, "nara", None)
OUT_DIR = _RAW_NARA if _RAW_NARA is not None else (CHECKPOINTS.parent / "rawdata" / "nara_catalog")

PAUSE_FILE    = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB = CHECKPOINTS / "pipeline.db"

LIMIT         = 100         # results per page
REQUEST_DELAY = 3           # seconds between requests
MAX_RETRIES   = 3

SEARCH_TERMS = [
    "census",
    "passenger list",
    "pension",
    "military service",
    "naturalization",
    "vital records",
    "probate",
    "land record",
]

USER_AGENT = "OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


# ── Database ──────────────────────────────────────────────────────────────────

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


def _already_done(con: sqlite3.Connection, url: str) -> bool:
    return con.execute("SELECT 1 FROM records WHERE url=?", (url,)).fetchone() is not None


def _mark_fetched(con: sqlite3.Connection, url: str, source: str = "nara_catalog"):
    con.execute(
        "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
        (url, source, "fetched", None),
    )
    con.commit()


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get_json(session: requests.Session, url: str, params: dict) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                print("[NARA] 429 rate-limited — backing off 30 min")
                time.sleep(1800)
                return None
            if r.status_code == 403:
                print("[NARA] 403 — check credentials / ToS")
                raise RuntimeError("403 from NARA API")
            if r.status_code != 200:
                wait = 2 ** attempt * 5
                print(f"[NARA] HTTP {r.status_code} (attempt {attempt + 1}) — retry in {wait}s")
                time.sleep(wait)
                continue
            return r.json()
        except RuntimeError:
            raise
        except Exception as e:
            wait = 2 ** attempt * 5
            print(f"[NARA] Exception (attempt {attempt + 1}): {e} — retry in {wait}s")
            time.sleep(wait)
    return None


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_result(item: dict) -> dict | None:
    """Extract a flat record from a NARA API result item."""
    naid = item.get("naId") or item.get("naID") or item.get("id")
    if not naid:
        return None

    title       = item.get("title", "")
    description = item.get("description", "")
    scope_note  = item.get("scopeAndContentNote", "")

    # Date range — may be a list of dicts or strings
    date_range = item.get("dateRangeArray", [])
    dates: list[str] = []
    if isinstance(date_range, list):
        for d in date_range:
            if isinstance(d, dict):
                s = d.get("inclusiveStartYear") or d.get("start") or ""
                e = d.get("inclusiveEndYear") or d.get("end") or ""
                if s or e:
                    dates.append(f"{s}–{e}" if (s and e) else str(s or e))
            elif isinstance(d, str):
                dates.append(d)
    date_str = "; ".join(dates) if dates else ""

    # Year from first date entry
    year: int | None = None
    if dates:
        import re
        m = re.search(r'\b(1[0-9]{3}|20[0-2][0-9])\b', dates[0])
        if m:
            year = int(m.group(1))

    # Location info
    location = item.get("locationArray", [])
    location_str = ""
    if isinstance(location, list) and location:
        parts = []
        for loc in location:
            if isinstance(loc, dict):
                n = loc.get("name") or loc.get("city") or ""
                if n:
                    parts.append(n)
        location_str = "; ".join(parts)

    text_parts = [p for p in [title, description, scope_note] if p]
    if location_str:
        text_parts.append(f"Location: {location_str}")
    if date_str:
        text_parts.append(f"Dates: {date_str}")
    text = " | ".join(text_parts)

    url = RECORD_URL_TPL.format(naId=naid)

    return {
        "url":          url,
        "source":       "nara_catalog",
        "record_type":  "archival_record",
        "title":        title,
        "text":         text,
        "year":         year,
        "naid":         str(naid),
        "description":  description,
        "scope_note":   scope_note,
        "date_range":   date_str,
        "location":     location_str,
    }


# ── Main entry ────────────────────────────────────────────────────────────────

def run():
    """Runs forever — called by the orchestrator subprocess."""
    print("[NARA] Fetcher starting")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    session = requests.Session()
    session.headers.update(HEADERS)

    total_saved = 0
    cycle = 0

    while True:
        cycle += 1
        print(f"[NARA] Starting cycle {cycle} — {len(SEARCH_TERMS)} search terms")

        for term in SEARCH_TERMS:
            offset = 0
            term_saved = 0

            while True:
                # Pause check
                if PAUSE_FILE.exists():
                    print("[NARA] PAUSE_DOWNLOADS set — waiting 60s")
                    time.sleep(60)
                    continue

                params = {
                    "q":           term,
                    "resultTypes": "item",
                    "limit":       LIMIT,
                    "offset":      offset,
                }

                data = _get_json(session, SEARCH_URL, params)
                if data is None:
                    print(f"[NARA] No data for term='{term}' offset={offset} — skipping page")
                    break

                # NARA v2 wraps results in body.hits.hits or opaResponse.results.result
                hits = []
                try:
                    # Try v2 structure
                    body = data.get("body") or data
                    hits = (
                        body.get("hits", {}).get("hits", [])
                        or body.get("results", {}).get("result", [])
                        or body.get("items", [])
                        or []
                    )
                except Exception:
                    pass

                if not hits:
                    # Try flat list
                    if isinstance(data, list):
                        hits = data
                    else:
                        print(f"[NARA] No hits for term='{term}' offset={offset} — end of results")
                        break

                for raw_item in hits:
                    # v2 may nest under _source
                    item = raw_item.get("_source", raw_item) if isinstance(raw_item, dict) else {}
                    record = _parse_result(item)
                    if not record:
                        continue

                    url = record["url"]
                    if _already_done(con, url):
                        continue

                    file_id  = hashlib.md5(url.encode()).hexdigest()
                    out_file = OUT_DIR / f"{file_id}.json"
                    out_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
                    _mark_fetched(con, url)
                    term_saved  += 1
                    total_saved += 1

                    if total_saved % 50 == 0:
                        print(f"[NARA] {total_saved:,} records saved (term='{term}' offset={offset})")

                if len(hits) < LIMIT:
                    break  # last page

                offset += LIMIT
                time.sleep(REQUEST_DELAY)

            print(f"[NARA] Term '{term}': {term_saved} new records this cycle")
            time.sleep(REQUEST_DELAY)

        print(f"[NARA] Cycle {cycle} complete — {total_saved:,} total records saved — restarting")
        time.sleep(REQUEST_DELAY * 5)  # brief pause between full cycles


if __name__ == "__main__":
    run()
