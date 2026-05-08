"""
DPLA Fetcher — Digital Public Library of America.

Sweeps the DPLA Items API for genealogy-relevant subject terms. Requires
a DPLA API key in the environment variable DPLA_API_KEY. If the key is
not configured the fetcher waits politely (300s sleep loop) rather than
crashing, so the orchestrator can restart it once the key is set.

Rate: 1 request every 5 seconds.
On 429: back off 30 minutes.

Output: dpla rawdata directory — one JSON file per item.
Checkpoint: records table in pipeline.db, keyed by item @id URL.
"""

import json, os, time, sqlite3, hashlib, re
from pathlib import Path

import requests

from pipeline.paths import RAW, LOGS, CHECKPOINTS

# ── Constants ────────────────────────────────────────────────────────────────

API_URL = "https://api.dp.la/v2/items"

# OUT_DIR: fall back gracefully if RAW.dpla doesn't exist
_RAW_DPLA = getattr(RAW, "dpla", None)
OUT_DIR = _RAW_DPLA if _RAW_DPLA is not None else (CHECKPOINTS.parent / "rawdata" / "dpla")

PAUSE_FILE    = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB = CHECKPOINTS / "pipeline.db"

PAGE_SIZE     = 100
REQUEST_DELAY = 1    # seconds
MAX_RETRIES   = 3

SEARCH_SUBJECTS = [
    "genealogy",
    "vital records",
    "obituaries",
    "census records",
    "passenger lists",
    "military records",
    "land grants",
    "probate records",
    "birth records",
    "death records",
    "marriage records",
    "immigration records",
]

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


def _mark_fetched(con: sqlite3.Connection, url: str, source: str = "dpla"):
    con.execute(
        "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
        (url, source, "fetched", None),
    )
    con.commit()


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get_json(session: requests.Session, api_key: str, term: str, page: int) -> dict | None:
    params = {
        "api_key":   api_key,
        "q":         term,
        "page_size": PAGE_SIZE,
        "page":      page,
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(API_URL, params=params, timeout=30)
            if r.status_code == 429:
                print("[DPLA] 429 — backing off 30 min")
                time.sleep(1800)
                return None
            if r.status_code == 401:
                print("[DPLA] 401 — API key invalid or revoked. Waiting 300s.")
                time.sleep(300)
                return None
            if r.status_code == 403:
                print("[DPLA] 403 — check API key / ToS")
                raise RuntimeError("403 from DPLA API")
            if r.status_code != 200:
                wait = 2 ** attempt * 5
                print(f"[DPLA] HTTP {r.status_code} (attempt {attempt + 1}) — retry in {wait}s")
                time.sleep(wait)
                continue
            return r.json()
        except RuntimeError:
            raise
        except Exception as e:
            wait = 2 ** attempt * 5
            print(f"[DPLA] Error (attempt {attempt + 1}): {e} — retry in {wait}s")
            time.sleep(wait)
    return None


# ── Parsing ───────────────────────────────────────────────────────────────────

def _coerce_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        return "; ".join(
            str(v.get("name", v) if isinstance(v, dict) else v).strip()
            for v in val if v
        )
    if isinstance(val, dict):
        return str(val.get("name", val.get("value", "")) or "").strip()
    return str(val).strip()


def _parse_item(item: dict) -> dict | None:
    url = item.get("@id", "")
    if not url:
        url = item.get("id", "")
    if not url:
        return None

    sr    = item.get("sourceResource", {})
    title = _coerce_str(sr.get("title"))
    desc  = _coerce_str(sr.get("description"))
    creator = _coerce_str(sr.get("creator"))

    # Date
    date_raw = sr.get("date", {})
    date_str = ""
    if isinstance(date_raw, dict):
        date_str = date_raw.get("displayDate", "") or date_raw.get("begin", "")
    elif isinstance(date_raw, list) and date_raw:
        first = date_raw[0]
        if isinstance(first, dict):
            date_str = first.get("displayDate", "") or first.get("begin", "")
        else:
            date_str = str(first)
    elif isinstance(date_raw, str):
        date_str = date_raw

    year: int | None = None
    if date_str:
        m = re.search(r'\b(1[0-9]{3}|20[0-2][0-9])\b', str(date_str))
        if m:
            year = int(m.group(1))

    # Subject
    subjects_raw = sr.get("subject", [])
    subjects: list[str] = []
    if isinstance(subjects_raw, list):
        for s in subjects_raw:
            name = s.get("name", "") if isinstance(s, dict) else str(s)
            if name:
                subjects.append(name.strip())
    subject_str = "; ".join(subjects[:20])

    # Type
    type_raw = sr.get("type", "")
    type_str = _coerce_str(type_raw)

    provider = _coerce_str(item.get("dataProvider"))

    text_parts = [p for p in [
        title,
        f"Creator: {creator}"          if creator      else "",
        f"Description: {desc}"         if desc         else "",
        f"Subjects: {subject_str}"     if subject_str  else "",
        f"Type: {type_str}"            if type_str     else "",
        f"Provider: {provider}"        if provider     else "",
        f"Date: {date_str}"            if date_str     else "",
    ] if p]
    text = " | ".join(text_parts)

    return {
        "url":          url,
        "source":       "dpla",
        "record_type":  type_str or "item",
        "title":        title,
        "text":         text,
        "year":         year,
        "dpla_id":      item.get("id", ""),
        "creator":      creator,
        "description":  desc,
        "subjects":     subjects,
        "date":         date_str,
        "provider":     provider,
    }


# ── API key wait loop ─────────────────────────────────────────────────────────

def _wait_for_api_key() -> str:
    """Block politely until DPLA_API_KEY is set, then return it."""
    while True:
        key = os.environ.get("DPLA_API_KEY", "").strip()
        if key:
            return key
        print(
            "[DPLA] DPLA_API_KEY environment variable is not set. "
            "Set it and restart, or the fetcher will check again in 300s."
        )
        time.sleep(300)


# ── Main entry ────────────────────────────────────────────────────────────────

def run():
    """Runs forever — called by the orchestrator subprocess."""
    print("[DPLA] Fetcher starting")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    # Wait politely for API key rather than crashing
    api_key = _wait_for_api_key()
    print(f"[DPLA] API key found — beginning fetch")

    session = requests.Session()
    session.headers.update(HEADERS)

    total_saved = 0
    cycle = 0

    while True:
        cycle += 1
        print(f"[DPLA] Starting cycle {cycle} — {len(SEARCH_SUBJECTS)} subjects")

        # Re-check API key each cycle in case it was rotated
        api_key = os.environ.get("DPLA_API_KEY", api_key).strip() or api_key

        for term in SEARCH_SUBJECTS:
            page       = 1
            term_saved = 0

            while True:
                if PAUSE_FILE.exists():
                    print("[DPLA] PAUSE_DOWNLOADS set — waiting 60s")
                    time.sleep(60)
                    continue

                data = _get_json(session, api_key, term, page)
                if data is None:
                    print(f"[DPLA] No data for term='{term}' page={page} — skipping")
                    break

                items = data.get("docs", [])
                if not items:
                    break  # end of results

                total_count = data.get("count", 0)

                for item in items:
                    record = _parse_item(item)
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
                        print(f"[DPLA] {total_saved:,} records saved "
                              f"(term='{term}' page={page}/{(total_count // PAGE_SIZE) + 1})")

                if len(items) < PAGE_SIZE:
                    break  # last page

                page += 1
                time.sleep(REQUEST_DELAY)

            print(f"[DPLA] Term '{term}': {term_saved} new records this cycle")
            time.sleep(REQUEST_DELAY)

        print(f"[DPLA] Cycle {cycle} complete — {total_saved:,} total records saved — restarting")
        time.sleep(REQUEST_DELAY * 6)


if __name__ == "__main__":
    run()
