"""
HathiTrust Fetcher — genealogy books in the public domain.

Strategy:
  1. Query the HathiTrust Catalog full-text search API for each genealogy
     subject term to collect a list of HTIDs (HathiTrust item IDs).
  2. For each HTID, fetch brief metadata from the Volumes API.
  3. If the item is in the public domain (full text available), fetch the
     first 2 000 characters of OCR text from the PageTurner plain-text API.
  4. Write one JSON file per item.

Rate: 1 request every 10 seconds.
On 429: back off 30 minutes.

Output: RAW directory for hathitrust (if not in paths, uses fallback dir).
Checkpoint: records table in pipeline.db, keyed by item URL.
"""

import json, time, sqlite3, hashlib, re
from pathlib import Path

import requests

from pipeline.paths import RAW, LOGS, CHECKPOINTS

# ── Constants ────────────────────────────────────────────────────────────────

# HathiTrust endpoints
SEARCH_URL  = "https://catalog.hathitrust.org/Search/Home"
VOLUME_URL  = "https://catalog.hathitrust.org/api/volumes/brief/json/"
FULLTEXT_URL = "https://babel.hathitrust.org/cgi/pt"
ITEM_URL_TPL = "https://babel.hathitrust.org/cgi/pt?id={htid}"

# OUT_DIR: use RAW.hathitrust if it exists, otherwise fall back
_RAW_HT = getattr(RAW, "hathitrust", None)
OUT_DIR = _RAW_HT if _RAW_HT is not None else (CHECKPOINTS.parent / "rawdata" / "hathitrust")

PAUSE_FILE    = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB = CHECKPOINTS / "pipeline.db"

REQUEST_DELAY = 5   # seconds between requests
MAX_RETRIES   = 3
FULLTEXT_CHARS = 2000

SEARCH_TERMS = [
    "genealogy",
    "family history",
    "vital records",
    "cemetery",
    "obituary",
    "ancestors",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OpenGenealogyAI/1.0"
HEADERS    = {
    "User-Agent":      USER_AGENT,
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


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


def _mark_fetched(con: sqlite3.Connection, url: str, source: str = "hathitrust"):
    con.execute(
        "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
        (url, source, "fetched", None),
    )
    con.commit()


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(session: requests.Session, url: str, params: dict | None = None,
         accept_non200: bool = False) -> requests.Response | None:
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                print("[HATHITRUST] 429 — backing off 30 min")
                time.sleep(1800)
                return None
            if r.status_code == 403:
                print("[HATHITRUST] 403 — check User-Agent / ToS")
                raise RuntimeError("403 from HathiTrust")
            if not accept_non200:
                r.raise_for_status()
            return r
        except RuntimeError:
            raise
        except Exception as e:
            wait = 2 ** attempt * 5
            print(f"[HATHITRUST] Error (attempt {attempt + 1}): {e} — retry in {wait}s")
            time.sleep(wait)
    return None


# ── Search: collect HTIDs via catalog search ──────────────────────────────────

def _search_catalog(session: requests.Session, query: str, page: int = 1) -> list[str]:
    """
    Use HathiTrust catalog full-text search JSON endpoint.
    Returns a list of HTIDs found on this result page.
    """
    params = {
        "lookfor":            query,
        "type":               "subject",
        "filter[]":           "availability:full_text",
        "view":               "list",
        "format":             "json",
        "page":               page,
        "limit":              20,
    }
    r = _get(session, SEARCH_URL, params=params, accept_non200=True)
    if not r:
        return []

    try:
        data = r.json()
    except Exception:
        return []

    htids: list[str] = []
    records = data.get("records", {})
    for record_id, rec in records.items():
        # Each catalog record may contain multiple HathiTrust items
        items = rec.get("items", [])
        for item in items:
            htid = item.get("htid", "")
            if htid:
                htids.append(htid)
        # Also try extracting from recordURL
        if not items:
            url_field = rec.get("recordURL", "")
            m = re.search(r'[?&]id=([^&]+)', url_field)
            if m:
                htids.append(m.group(1))

    return htids


# ── Volume metadata ───────────────────────────────────────────────────────────

def _fetch_volume_meta(session: requests.Session, htid: str) -> dict | None:
    """Fetch brief volume metadata from the Volumes API."""
    # htid must be URL-encoded for the path component
    encoded = htid.replace("/", "%2F").replace("+", "%2B")
    url = f"{VOLUME_URL}htid:{encoded}.json"
    r = _get(session, url, accept_non200=True)
    if not r or r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None


def _parse_volume(htid: str, vol_data: dict) -> dict:
    """Extract flat metadata from the Volumes API response."""
    # vol_data is a dict keyed by the query id; dig into the first entry
    record = {}
    for key, val in vol_data.items():
        record = val
        break

    rec_data = record.get("records", {})
    items    = record.get("items", [])

    title       = ""
    author      = ""
    date        = ""
    subjects: list[str] = []
    is_public   = False

    # Get metadata from the records dict
    for rec_id, rec in rec_data.items():
        title   = rec.get("titles", [""])[0] if rec.get("titles") else ""
        author  = rec.get("authors", {}).get("main", "")
        date    = rec.get("publishDates", [""])[0] if rec.get("publishDates") else ""
        subjects = rec.get("subjects", [])
        break

    # Check public-domain status from items list
    for item in items:
        if item.get("htid") == htid:
            rights = item.get("usRightsString", "") or item.get("rightsCode", "")
            if rights.lower() in ("pd", "pdus", "ic-world", "public domain", "pd-us"):
                is_public = True
            break

    year: int | None = None
    if date:
        m = re.search(r'\b(1[0-9]{3}|20[0-2][0-9])\b', str(date))
        if m:
            year = int(m.group(1))

    return {
        "title":      title,
        "author":     author,
        "date":       date,
        "year":       year,
        "subjects":   subjects if isinstance(subjects, list) else [str(subjects)],
        "is_public":  is_public,
    }


# ── Full-text snippet (public domain only) ────────────────────────────────────

def _fetch_fulltext_snippet(session: requests.Session, htid: str) -> str:
    """Attempt to retrieve first FULLTEXT_CHARS characters of page-1 OCR."""
    try:
        r = session.get(
            FULLTEXT_URL,
            params={"id": htid, "seq": "1", "skin": "mobile", "view": "plaintext"},
            timeout=30,
        )
        if r.status_code == 200 and r.text:
            text = re.sub(r'\s+', ' ', r.text).strip()
            return text[:FULLTEXT_CHARS]
    except Exception:
        pass
    return ""


# ── Main entry ────────────────────────────────────────────────────────────────

def run():
    """Runs forever — called by the orchestrator subprocess."""
    print("[HATHITRUST] Fetcher starting")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    session = requests.Session()
    session.headers.update(HEADERS)

    total_saved = 0
    cycle = 0

    while True:
        cycle += 1
        print(f"[HATHITRUST] Starting cycle {cycle} — {len(SEARCH_TERMS)} terms")

        for term in SEARCH_TERMS:
            page     = 1
            term_saved = 0
            consecutive_empty = 0

            while True:
                if PAUSE_FILE.exists():
                    print("[HATHITRUST] PAUSE_DOWNLOADS set — waiting 60s")
                    time.sleep(60)
                    continue

                htids = _search_catalog(session, term, page=page)
                time.sleep(REQUEST_DELAY)

                if not htids:
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        break
                    page += 1
                    continue

                consecutive_empty = 0

                for htid in htids:
                    item_url = ITEM_URL_TPL.format(htid=htid)

                    if _already_done(con, item_url):
                        continue

                    if PAUSE_FILE.exists():
                        print("[HATHITRUST] PAUSE_DOWNLOADS set — waiting 60s")
                        time.sleep(60)

                    vol_data = _fetch_volume_meta(session, htid)
                    time.sleep(REQUEST_DELAY)

                    if vol_data is None:
                        # Still checkpoint it to avoid repeated failed lookups
                        _mark_fetched(con, item_url)
                        continue

                    meta = _parse_volume(htid, vol_data)

                    fulltext = ""
                    if meta["is_public"]:
                        fulltext = _fetch_fulltext_snippet(session, htid)
                        time.sleep(REQUEST_DELAY)

                    subject_str = "; ".join(meta["subjects"])
                    text_parts = [p for p in [
                        meta["title"],
                        f"Author: {meta['author']}" if meta["author"] else "",
                        f"Subjects: {subject_str}" if subject_str else "",
                        fulltext,
                    ] if p]
                    text = " | ".join(text_parts)

                    record = {
                        "url":         item_url,
                        "source":      "hathitrust",
                        "record_type": "book",
                        "title":       meta["title"],
                        "text":        text,
                        "year":        meta["year"],
                        "htid":        htid,
                        "author":      meta["author"],
                        "date":        meta["date"],
                        "subjects":    meta["subjects"],
                        "is_public":   meta["is_public"],
                    }

                    file_id  = hashlib.md5(item_url.encode()).hexdigest()
                    out_file = OUT_DIR / f"{file_id}.json"
                    out_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
                    _mark_fetched(con, item_url)
                    term_saved  += 1
                    total_saved += 1

                    if total_saved % 50 == 0:
                        print(f"[HATHITRUST] {total_saved:,} records saved (term='{term}' page={page})")

                page += 1

            print(f"[HATHITRUST] Term '{term}': {term_saved} new records this cycle")

        print(f"[HATHITRUST] Cycle {cycle} complete — {total_saved:,} total records saved — restarting")
        time.sleep(REQUEST_DELAY * 6)


if __name__ == "__main__":
    run()
