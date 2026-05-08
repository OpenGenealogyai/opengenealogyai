"""
Chronicling America Fetcher — Civil War Era newspapers 1851–1880.

Bulk-downloads newspaper pages via the Chronicling America JSON search API.
OCR text is already served by the API — no secondary PDF/image processing needed.
Output: RAW.chronicling/pages/ — one JSON file per newspaper page.

Rate: polite (0.5s between requests). On 429: back off 30 min.
"""

import json, time, sqlite3, hashlib
from pathlib import Path

import requests

from pipeline.paths import RAW, LOGS, CHECKPOINTS
from pipeline.throttle import wait_for_internet

SEARCH_URL = "https://www.loc.gov/search/"
OUT_DIR    = RAW.chronicling / "pages"

PAUSE_FILE    = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB = CHECKPOINTS / "pipeline.db"

YEAR_START    = 1851
YEAR_END      = 1880
ROWS_PER_PAGE = 100
REQUEST_DELAY = 1.0  # seconds — LOC rate limit is strict

USER_AGENT = "OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)"
HEADERS    = {"User-Agent": USER_AGENT, "Accept": "application/json"}


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
                print("[CHRONICLING] 429 — backing off 30 min")
                time.sleep(1800)
                return None
            if r.status_code == 403:
                print("[CHRONICLING] 403 — stopping (check User-Agent / ToS)")
                raise RuntimeError("403")
            r.raise_for_status()
            return r
        except RuntimeError:
            raise
        except Exception as e:
            wait = 2 ** attempt
            print(f"[CHRONICLING] Error (attempt {attempt + 1}/3): {e} — retry in {wait}s")
            time.sleep(wait)
    return None


def _fetch_search_page(session: requests.Session, page_num: int) -> dict | None:
    r = _get(session, SEARCH_URL, params={
        "fo":   "json",
        "fa":   [f"partof:chronicling america", f"date:{YEAR_START}/{YEAR_END}"],
        "rows": ROWS_PER_PAGE,
        "sp":   page_num,
    })
    return r.json() if r else None


# ── Main entry ───────────────────────────────────────────────────────────────────

def run():
    print("[CHRONICLING] Fetcher starting — years 1851–1880")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    session = requests.Session()
    session.headers.update(HEADERS)

    first = _fetch_search_page(session, 1)
    if not first:
        print("[CHRONICLING] Could not reach API — aborting")
        return

    pagination   = first.get("pagination", {})
    total_items  = pagination.get("total", 0)
    total_pages  = pagination.get("pages", max(1, (total_items + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE))
    print(f"[CHRONICLING] {total_items:,} pages across {total_pages:,} result pages")

    count_out = 0

    for page_num in range(1, total_pages + 1):
        if PAUSE_FILE.exists():
            print("[CHRONICLING] PAUSE_DOWNLOADS — waiting 60s")
            time.sleep(60)
            continue

        data = first if page_num == 1 else _fetch_search_page(session, page_num)
        if not data:
            continue

        for item in data.get("results", []):
            item_url = item.get("url") or item.get("id", "")
            if not item_url:
                continue
            if not item_url.startswith("http"):
                item_url = "https://www.loc.gov" + item_url

            if _already_done(con, item_url):
                continue

            date_str = item.get("date", "")
            try:
                year = int(date_str[:4]) if date_str and len(date_str) >= 4 else None
            except ValueError:
                year = None

            desc = item.get("description", [])
            text = " ".join(desc) if isinstance(desc, list) else str(desc)

            title = item.get("title", "")
            if isinstance(title, list):
                title = title[0] if title else ""

            states = item.get("location_state") or item.get("state") or []
            record = {
                "url":         item_url,
                "source":      "chronicling_america",
                "record_type": "newspaper_article",
                "title":       title,
                "text":        text[:10000],
                "year":        year,
                "state":       states[0] if states else None,
            }

            file_id  = hashlib.md5(item_url.encode()).hexdigest()
            out_file = OUT_DIR / f"{file_id}.json"
            out_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

            con.execute(
                "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
                (item_url, "chronicling_america", "fetched", None),
            )
            con.commit()
            count_out += 1

        if page_num % 50 == 0:
            print(f"[CHRONICLING] Page {page_num}/{total_pages} — {count_out:,} records saved")

        time.sleep(REQUEST_DELAY)

    print(f"[CHRONICLING] Done — {count_out:,} records saved")


if __name__ == "__main__":
    run()
