"""
OpenLibrary Fetcher — genealogy books via Open Library search API.

Sweeps Open Library's /search.json endpoint for each genealogy subject,
paginating through all results. Cycles through all subjects indefinitely
so newly-added books are eventually captured.

Rate: 1 request every 5 seconds.
On 429: back off 30 minutes.

Output: open_library rawdata directory — one JSON file per book.
Checkpoint: records table in pipeline.db, keyed by OpenLibrary item URL.
"""

import json, time, sqlite3, hashlib, re
from pathlib import Path

import requests

from pipeline.paths import RAW, LOGS, CHECKPOINTS

# ── Constants ────────────────────────────────────────────────────────────────

SEARCH_URL  = "https://openlibrary.org/search.json"
ITEM_URL_TPL = "https://openlibrary.org{key}"

# OUT_DIR: fall back gracefully if RAW.open_library doesn't exist
_RAW_OL = getattr(RAW, "open_library", None)
OUT_DIR = _RAW_OL if _RAW_OL is not None else (CHECKPOINTS.parent / "rawdata" / "open_library")

PAUSE_FILE    = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB = CHECKPOINTS / "pipeline.db"

LIMIT         = 100
REQUEST_DELAY = 1   # seconds
MAX_RETRIES   = 3

SUBJECTS = [
    "genealogy",
    "biography",
    "vital records",
    "census",
    "obituaries",
    "immigration",
    "naturalization",
    "land records",
    "probate records",
    "military records",
    "cemetery records",
    "church records",
    "passenger lists",
]

FIELDS = (
    "key,title,author_name,first_publish_year,subject,place,description,"
    "isbn,publisher,language"
)

USER_AGENT = "OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)"
HEADERS    = {"User-Agent": USER_AGENT, "Accept": "application/json"}


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


def _mark_fetched(con: sqlite3.Connection, url: str, source: str = "open_library"):
    con.execute(
        "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
        (url, source, "fetched", None),
    )
    con.commit()


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get_json(session: requests.Session, params: dict) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(SEARCH_URL, params=params, timeout=30)
            if r.status_code == 429:
                print("[OPENLIBRARY] 429 — backing off 30 min")
                time.sleep(1800)
                return None
            if r.status_code == 403:
                print("[OPENLIBRARY] 403 — check User-Agent / ToS")
                raise RuntimeError("403 from Open Library")
            if r.status_code != 200:
                wait = 2 ** attempt * 5
                print(f"[OPENLIBRARY] HTTP {r.status_code} (attempt {attempt + 1}) — retry in {wait}s")
                time.sleep(wait)
                continue
            return r.json()
        except RuntimeError:
            raise
        except Exception as e:
            wait = 2 ** attempt * 5
            print(f"[OPENLIBRARY] Error (attempt {attempt + 1}): {e} — retry in {wait}s")
            time.sleep(wait)
    return None


# ── Parsing ───────────────────────────────────────────────────────────────────

def _coerce_str(val) -> str:
    """Safely convert a value that might be a list or dict to a string."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        parts = []
        for v in val:
            if isinstance(v, str):
                parts.append(v.strip())
            elif isinstance(v, dict):
                parts.append(str(v.get("value", "") or "").strip())
        return "; ".join(p for p in parts if p)
    if isinstance(val, dict):
        return str(val.get("value", "") or "").strip()
    return str(val).strip()


def _parse_doc(doc: dict) -> dict | None:
    key = doc.get("key", "")
    if not key:
        return None

    url = ITEM_URL_TPL.format(key=key)

    title        = _coerce_str(doc.get("title"))
    author_names = doc.get("author_name", [])
    author_str   = "; ".join(author_names) if isinstance(author_names, list) else str(author_names)

    subjects = doc.get("subject", [])
    subject_str = "; ".join(subjects[:30]) if isinstance(subjects, list) else str(subjects)

    places = doc.get("place", [])
    place_str = "; ".join(places[:10]) if isinstance(places, list) else str(places)

    description = _coerce_str(doc.get("description"))

    year_raw = doc.get("first_publish_year")
    year: int | None = None
    if year_raw:
        try:
            year = int(year_raw)
        except (ValueError, TypeError):
            pass

    text_parts = [p for p in [
        title,
        f"Author: {author_str}"      if author_str   else "",
        f"Subjects: {subject_str}"   if subject_str  else "",
        f"Place: {place_str}"        if place_str    else "",
        description,
    ] if p]
    text = " | ".join(text_parts)

    return {
        "url":         url,
        "source":      "open_library",
        "record_type": "book",
        "title":       title,
        "text":        text,
        "year":        year,
        "key":         key,
        "author":      author_str,
        "subjects":    subjects if isinstance(subjects, list) else [],
        "place":       place_str,
        "description": description,
    }


# ── Main entry ────────────────────────────────────────────────────────────────

def run():
    """Runs forever — called by the orchestrator subprocess."""
    print("[OPENLIBRARY] Fetcher starting")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    session = requests.Session()
    session.headers.update(HEADERS)

    total_saved = 0
    cycle = 0

    while True:
        cycle += 1
        print(f"[OPENLIBRARY] Starting cycle {cycle} — {len(SUBJECTS)} subjects")

        for subject in SUBJECTS:
            offset     = 0
            term_saved = 0

            while True:
                if PAUSE_FILE.exists():
                    print("[OPENLIBRARY] PAUSE_DOWNLOADS set — waiting 60s")
                    time.sleep(60)
                    continue

                params = {
                    "subject": subject,
                    "fields":  FIELDS,
                    "limit":   LIMIT,
                    "offset":  offset,
                }

                data = _get_json(session, params)
                if data is None:
                    print(f"[OPENLIBRARY] No data for subject='{subject}' offset={offset} — skipping")
                    break

                docs = data.get("docs", [])
                if not docs:
                    break  # end of results for this subject

                for doc in docs:
                    record = _parse_doc(doc)
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
                        print(f"[OPENLIBRARY] {total_saved:,} records saved "
                              f"(subject='{subject}' offset={offset})")

                if len(docs) < LIMIT:
                    break  # last page

                offset += LIMIT
                time.sleep(REQUEST_DELAY)

            print(f"[OPENLIBRARY] Subject '{subject}': {term_saved} new records this cycle")
            time.sleep(REQUEST_DELAY)

        print(f"[OPENLIBRARY] Cycle {cycle} complete — {total_saved:,} total records saved — restarting")
        time.sleep(REQUEST_DELAY * 6)


if __name__ == "__main__":
    run()
