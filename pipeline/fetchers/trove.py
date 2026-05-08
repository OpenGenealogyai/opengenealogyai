"""
Trove Australia Fetcher — newspapers 1800–1954.

License: ingest-only — store embeddings + source URI only. NO raw text stored.
Rate limit: 40 req/min → one request every 1.5 seconds.
Covers both checked-out chunks:
  trove-australia-1800-1900  (YEAR_START=1800, YEAR_END=1900)
  trove-australia-1901-1954  (YEAR_START=1901, YEAR_END=1954)

Writes one JSON file per article to RAW.trove/{zone}/
Records have transcription=null per Rule 7 (ingest-only).
"""

import json, time, sqlite3, hashlib
from pathlib import Path

import requests

from pipeline.paths import RAW, LOGS, CHECKPOINTS
from pipeline.throttle import wait_for_internet

TROVE_API_URL = "https://api.trove.nla.gov.au/v3"
OUT_DIR       = RAW.trove

PAUSE_FILE    = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB = CHECKPOINTS / "pipeline.db"

REQUEST_DELAY = 1.5   # seconds — 40 req/min
PAGE_SIZE     = 100

YEAR_START = 1800
YEAR_END   = 1954

USER_AGENT = "OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)"


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

def _get_session(api_key: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept":     "application/json",
    })
    if api_key:
        s.headers["X-API-KEY"] = api_key
    return s


def _search_page(session: requests.Session, year_start: int, year_end: int,
                 bulk_harvest_token: str | None, start: int) -> dict | None:
    params = {
        "q":          f"date:[{year_start} TO {year_end}]",
        "category":   "newspaper",
        "encoding":   "json",
        "n":          PAGE_SIZE,
        "s":          start,
        "include":    "articleText",
        "sortby":     "dateAsc",
    }
    if bulk_harvest_token:
        params["bulkHarvest"] = "true"

    url = f"{TROVE_API_URL}/result"
    for attempt in range(3):
        try:
            wait_for_internet()
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                print("[TROVE] 429 — backing off 5 min")
                time.sleep(300)
                return None
            if r.status_code == 403:
                print("[TROVE] 403 — check API key")
                raise RuntimeError("403")
            if r.status_code == 401:
                print("[TROVE] 401 — invalid or missing API key (set TROVE_API_KEY in .env)")
                raise RuntimeError("401")
            r.raise_for_status()
            return r.json()
        except RuntimeError:
            raise
        except Exception as e:
            wait = 2 ** attempt
            print(f"[TROVE] Error (attempt {attempt + 1}/3): {e} — retry in {wait}s")
            time.sleep(wait)
    return None


# ── Record builder — NO transcription stored (ingest-only license) ──────────────

def _build_record(article: dict, zone: str) -> dict | None:
    """Build an ingest-only record (embeddings + URI only per Trove ToS)."""
    article_id = article.get("id") or article.get("identifier", "")
    if not article_id:
        return None

    url = f"https://trove.nla.gov.au/newspaper/article/{article_id}"

    title    = article.get("heading") or article.get("title") or ""
    date_str = article.get("date") or ""
    newspaper_title = article.get("title") or article.get("newspaper", {}).get("title", "")
    newspaper_place = article.get("newspaper", {}).get("place", "") if isinstance(article.get("newspaper"), dict) else ""

    try:
        year = int(date_str[:4]) if date_str and len(date_str) >= 4 else None
    except ValueError:
        year = None

    # Build text from metadata only — no OCR/article body stored
    # This text is used for embedding; the raw text is never stored per license
    meta_parts = []
    if title:
        meta_parts.append(title)
    if newspaper_title:
        meta_parts.append(f"Published in: {newspaper_title}")
    if newspaper_place:
        meta_parts.append(f"Location: {newspaper_place}")
    if date_str:
        meta_parts.append(f"Date: {date_str}")
    if article.get("category"):
        meta_parts.append(f"Category: {article['category']}")

    embed_text = " | ".join(p for p in meta_parts if p)
    if not embed_text:
        return None

    return {
        "url":                   url,
        "source":                "trove",
        "record_type":           "newspaper_notice",
        "title":                 title,
        "text":                  embed_text,   # metadata-only text for embedding
        "transcription":         None,          # ingest-only: never store raw text
        "redistribution_license": "ingest-only",
        "year":                  year,
        "date_as_written":       date_str,
        "state":                 newspaper_place,
        "zone":                  zone,
    }


# ── Main entry ───────────────────────────────────────────────────────────────────

def run():
    import os
    api_key = os.environ.get("TROVE_API_KEY", "")
    if not api_key:
        print("[TROVE] WARNING: TROVE_API_KEY not set in .env — requests may fail")

    print(f"[TROVE] Fetcher starting — years {YEAR_START}–{YEAR_END}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    session = _get_session(api_key)

    decade_dirs: dict[str, Path] = {}
    total_saved = 0
    start       = 0

    while True:
        if PAUSE_FILE.exists():
            print("[TROVE] PAUSE_DOWNLOADS — waiting 60s")
            time.sleep(60)
            continue

        data = _search_page(session, YEAR_START, YEAR_END, bulk_harvest_token=api_key, start=start)
        if not data:
            break

        response   = data.get("response", {})
        zone_data  = response.get("zone", []) or []

        articles = []
        zone_name = "newspaper"
        for zone in zone_data:
            zone_name = zone.get("name", "newspaper")
            records   = zone.get("records", {}) or {}
            items     = records.get("article") or records.get("item") or []
            if isinstance(items, dict):
                items = [items]
            articles.extend(items)

        total = None
        for zone in zone_data:
            t = zone.get("records", {}).get("total")
            if t is not None:
                total = int(t)
                break

        if not articles:
            break

        for article in articles:
            url = f"https://trove.nla.gov.au/newspaper/article/{article.get('id', '')}"
            if _already_done(con, url):
                continue

            record = _build_record(article, zone_name)
            if not record:
                continue

            # Bucket into decade subdirectories
            year = record.get("year") or 0
            decade = f"{(year // 10) * 10}s" if year else "unknown"
            if decade not in decade_dirs:
                d = OUT_DIR / decade
                d.mkdir(exist_ok=True)
                decade_dirs[decade] = d

            article_id = str(article.get("id") or hashlib.md5(url.encode()).hexdigest()[:12])
            out_file   = decade_dirs[decade] / f"{article_id}.json"
            out_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

            con.execute(
                "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
                (url, "trove", "fetched", None),
            )
            con.commit()
            total_saved += 1

        start += len(articles)

        if start % 5000 == 0 or total and start >= total:
            print(f"[TROVE] {total_saved:,} saved | offset {start}/{total or '?'}")

        if total is not None and start >= total:
            break

        time.sleep(REQUEST_DELAY)

    print(f"[TROVE] Done — {total_saved:,} records saved (metadata-only, ingest-only license)")


if __name__ == "__main__":
    run()
