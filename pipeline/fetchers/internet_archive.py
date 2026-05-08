"""
Internet Archive Fetcher — Core Genealogy Collections.

Fetches all collections listed in agents/ia-fetcher/ia_collections.json.
Rate: 1 req/sec (IA's polite-use guideline).
For each item: 1 search request + 1 metadata request.
Output: RAW.internet_archive/{collection_id}/ — one JSON file per item.

On 429: back off 30 min.
On 403: skip collection, log for Garlon.
"""

import json, time, sqlite3
from pathlib import Path

import requests

from pipeline.paths import RAW, LOGS, CHECKPOINTS
from pipeline.throttle import wait_for_internet

IA_SEARCH_URL   = "https://archive.org/advancedsearch.php"
IA_METADATA_URL = "https://archive.org/metadata"
OUT_DIR         = RAW.internet_archive

PAUSE_FILE    = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB = CHECKPOINTS / "pipeline.db"

# Path relative to repo root — ia_collections.json is maintained by agents/ia-fetcher
COLLECTIONS_FILE = Path(__file__).resolve().parents[2] / "agents" / "ia-fetcher" / "ia_collections.json"

REQUEST_DELAY = 0.3   # seconds
PAGE_SIZE     = 100

USER_AGENT = "OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)"
HEADERS    = {"User-Agent": USER_AGENT}


# ── Database ────────────────────────────────────────────────────────────────────

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


# ── HTTP helpers ─────────────────────────────────────────────────────────────────

def _get(session: requests.Session, url: str, params=None) -> requests.Response | None:
    for attempt in range(3):
        try:
            wait_for_internet()
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                print("[IA] 429 — backing off 30 min")
                time.sleep(1800)
                return None
            if r.status_code == 403:
                print(f"[IA] 403 on {url} — skipping")
                raise RuntimeError("403")
            r.raise_for_status()
            return r
        except RuntimeError:
            raise
        except Exception as e:
            wait = 2 ** attempt
            print(f"[IA] Error (attempt {attempt + 1}/3): {e} — retry in {wait}s")
            time.sleep(wait)
    return None


def _search_collection(session: requests.Session, collection_id: str, page: int) -> dict | None:
    r = _get(session, IA_SEARCH_URL, params={
        "q":      f"collection:{collection_id}",
        "output": "json",
        "rows":   PAGE_SIZE,
        "page":   page,
        "fl[]":   ["identifier", "title", "description", "year", "subject", "creator", "date"],
        "sort[]": "identifier asc",
    })
    return r.json() if r else None


def _fetch_metadata(session: requests.Session, identifier: str) -> dict:
    try:
        wait_for_internet()
        r = session.get(f"{IA_METADATA_URL}/{identifier}", timeout=15)
        if r.status_code == 200:
            return r.json().get("metadata", {})
    except Exception:
        pass
    return {}


# ── Text builder ─────────────────────────────────────────────────────────────────

def _first(val) -> str:
    """Return the first element if val is a list, or val itself as string."""
    if isinstance(val, list):
        return str(val[0]) if val else ""
    return str(val) if val else ""


def _join(val, limit=5) -> str:
    if isinstance(val, list):
        return ", ".join(str(v) for v in val[:limit])
    return str(val) if val else ""


def _build_text(doc: dict, meta: dict) -> str:
    parts = []

    title = _first(doc.get("title") or meta.get("title", ""))
    if title:
        parts.append(title)

    desc = _first(doc.get("description") or meta.get("description", ""))
    if desc:
        parts.append(desc[:500])

    creator = _join(doc.get("creator") or meta.get("creator", ""))
    if creator:
        parts.append(f"Creator: {creator}")

    subject = _join(doc.get("subject") or meta.get("subject", ""))
    if subject:
        parts.append(f"Subject: {subject}")

    year = _first(doc.get("year") or meta.get("year", ""))
    if year:
        parts.append(f"Year: {year}")

    return " | ".join(p for p in parts if p)


def _parse_year(doc: dict, meta: dict):
    raw = doc.get("year") or meta.get("year")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    try:
        return int(str(raw)[:4]) if raw else None
    except (ValueError, TypeError):
        return None


# ── Main entry ───────────────────────────────────────────────────────────────────

def run():
    print("[IA] Fetcher starting")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    try:
        collections = json.loads(COLLECTIONS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[IA] Could not load collections file ({COLLECTIONS_FILE}): {e}")
        return

    print(f"[IA] Processing {len(collections)} collections")
    session = requests.Session()
    session.headers.update(HEADERS)

    total_saved = 0

    for coll in collections:
        coll_id   = coll.get("id", "")
        coll_name = coll.get("name", coll_id)
        rec_type  = coll.get("record_type", "other")

        if not coll_id:
            continue

        if PAUSE_FILE.exists():
            print("[IA] PAUSE_DOWNLOADS — waiting 60s")
            time.sleep(60)

        print(f"[IA] Collection: {coll_name} ({coll_id})")
        coll_dir = OUT_DIR / coll_id
        coll_dir.mkdir(exist_ok=True)

        page       = 1
        coll_count = 0
        total      = None

        while True:
            if PAUSE_FILE.exists():
                print("[IA] PAUSE_DOWNLOADS — waiting 60s")
                time.sleep(60)
                continue

            try:
                data = _search_collection(session, coll_id, page)
            except RuntimeError:
                print(f"[IA] Skipping collection {coll_id} (blocked)")
                break

            if not data:
                break

            response = data.get("response", {})
            docs     = response.get("docs", [])
            if total is None:
                total = response.get("numFound", 0)

            if not docs:
                break

            for doc in docs:
                identifier = doc.get("identifier", "")
                if not identifier:
                    continue

                url = f"https://archive.org/details/{identifier}"
                if _already_done(con, url):
                    continue

                time.sleep(REQUEST_DELAY)

                try:
                    meta = _fetch_metadata(session, identifier)
                except RuntimeError:
                    meta = {}

                text = _build_text(doc, meta)
                if not text.strip():
                    continue

                title = _first(doc.get("title") or meta.get("title", identifier))
                year  = _parse_year(doc, meta)

                record = {
                    "url":         url,
                    "source":      "internet_archive",
                    "record_type": rec_type,
                    "title":       title,
                    "text":        text,
                    "year":        year,
                    "collection":  coll_id,
                }

                out_file = coll_dir / f"{identifier}.json"
                out_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

                con.execute(
                    "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
                    (url, "internet_archive", "fetched", None),
                )
                con.commit()
                coll_count += 1
                total_saved += 1

            start = (page - 1) * PAGE_SIZE
            if total is not None and start + len(docs) >= total:
                break

            page += 1
            print(f"[IA] {coll_id}: page {page}, {coll_count} saved of ~{total or '?'}")
            time.sleep(REQUEST_DELAY)

        print(f"[IA] {coll_id}: done — {coll_count} records")

    print(f"[IA] All collections done — {total_saved:,} total records")


if __name__ == "__main__":
    run()
