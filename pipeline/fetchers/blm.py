"""
BLM Land Patents Fetcher — Eastern States.

Scrapes glorecords.blm.gov/results/tabs/default.aspx (the AJAX tab endpoint
that backs the results page). The old REST API (/BLMGeneralLandOfficeRecords/
api/patent/search) was decommissioned and returns 404.

Strategy: sweep common historical surnames × 13 eastern states.
For each (state, surname) pair, paginate until a page returns 0 data rows.

Rate: 3 req/min → 20-second delay between requests.
On 429: back off 30 minutes.
On System Error: retry up to 3 times with exponential back-off, then skip.

Output: RAW.blm_land_patents/{state}/ — one JSON file per patent.
Checkpoint: records table in pipeline.db, keyed by canonical patent URL.
Progress: blm_progress.json in CHECKPOINTS tracks (state, surname) position
  so the fetcher can resume after restart without re-querying done pairs.
"""

import json, time, re, hashlib, sqlite3
from pathlib import Path

import requests

from pipeline.paths import RAW, LOGS, CHECKPOINTS

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL    = "https://glorecords.blm.gov"
TAB_URL     = f"{BASE_URL}/results/tabs/default.aspx"
DETAIL_URL  = f"{BASE_URL}/details/patent/default.aspx"
OUT_DIR     = RAW.blm_land_patents
PAUSE_FILE  = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB    = CHECKPOINTS / "pipeline.db"
PROGRESS_FILE    = CHECKPOINTS / "blm_progress.json"

EASTERN_STATES = [
    "AL", "AR", "FL", "IA", "IL", "IN",
    "LA", "MI", "MN", "MO", "MS", "OH", "WI",
]

REQUEST_DELAY  = 22    # seconds — stay safely under 3 req/min
PAGE_SIZE      = 25    # rows per page (site default)
MAX_RETRIES    = 3

USER_AGENT = "OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept":     "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer":    f"{BASE_URL}/results/default.aspx",
}

# ── Surname sweep list ───────────────────────────────────────────────────────
# Loaded from validators/data/surnames.txt (426 common historical names).
# Supplemented with additional surnames common in 1800s land patent records.
_SURNAME_FILE = Path("D:/AI/Companies/open-genealogical-ai/validators/data/surnames.txt")

_EXTRA_SURNAMES = [
    # German/Scots-Irish/English names heavily present in eastern state patents
    "Mueller", "Schmidt", "Wagner", "Bauer", "Fischer", "Weber", "Schulz",
    "Meyer", "Krause", "Hoffmann", "Schroeder", "Zimmermann", "Braun",
    "McLaughlin", "O'Brien", "Sullivan", "Murphy", "McCarthy", "O'Connor",
    "McDonald", "Fraser", "Campbell", "MacKenzie", "MacLeod", "Buchanan",
    "Cunningham", "Fitzgerald", "Gallagher", "Kennedy", "Donnelly",
    "Carpenter", "Fletcher", "Cooper", "Turner", "Mason", "Potter",
    "Farmer", "Fisher", "Hunter", "Parker", "Wheeler", "Weaver",
    "Barker", "Fowler", "Gardner", "Haynes", "Jennings", "Lawson",
    "Nichols", "Pierce", "Ramsey", "Sanders", "Simmons", "Sparks",
    "Stephens", "Sutton", "Thornton", "Vance", "Wallace", "Walton",
    "Watkins", "Watts", "Williamson", "Willis", "Winters", "Wise",
    "Wood", "Woodward", "Yates", "York",
    # Surnames from BLM OH sample results observed in probing
    "Adams", "Anderson", "Baker", "Barkalow", "Bear", "Bevard",
    "Blackburn", "Bliss", "Boalt", "Bohn", "Bartlet", "Begges", "Bentley",
]


def _load_surnames() -> list[str]:
    names: list[str] = []
    if _SURNAME_FILE.exists():
        for line in _SURNAME_FILE.read_text(encoding="utf-8").splitlines():
            n = line.strip()
            if n and len(n) >= 3:  # site needs 2+ chars; use 3 to be safe
                names.append(n.capitalize())
    for n in _EXTRA_SURNAMES:
        cap = n.strip().capitalize()
        if cap and cap not in names:
            names.append(cap)
    # Deduplicate, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            out.append(n)
    return out


# ── Database ─────────────────────────────────────────────────────────────────

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


def _mark_fetched(con: sqlite3.Connection, url: str):
    con.execute(
        "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
        (url, "blm_land_patents", "fetched", None),
    )
    con.commit()


# ── Progress tracking ─────────────────────────────────────────────────────────

def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_progress(progress: dict):
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def _progress_key(state: str, surname: str) -> str:
    return f"{state}:{surname.lower()}"


# ── HTML parsing ─────────────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&[a-z#0-9]+;', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _parse_row(row_html: str) -> dict | None:
    """
    Parse a single patent <tr> into a dict.
    Table columns (from live inspection):
      0 = image link (has accession+docClass in href)
      1 = accession display
      2 = patentee names (<br>-separated)
      3 = issue date
      4 = doc number
      5 = state
      6 = meridian
      7 = twp-rng
      8 = aliquots
      9 = section number
     10 = county
    """
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.S | re.I)
    if len(cells) < 6:
        return None

    # Cell 0: image cell with href containing accession and docClass
    href_m = re.search(r'accession=([^&"\']+)&docClass=([^&"\'#\s]+)', cells[0], re.I)
    if not href_m:
        return None
    accession_raw = href_m.group(1).strip()
    doc_class     = href_m.group(2).strip()
    accession     = f"{doc_class}-{accession_raw}"

    # Cell 2: names — each patentee starts with the patentee.png icon img tag.
    # Split on that icon to separate people, then join br-separated name parts.
    names_raw = cells[2] if len(cells) > 2 else ""
    person_chunks = re.split(r'<img[^>]+alt="Patentee"[^>]*/?>',  names_raw, flags=re.I)
    names = []
    for chunk in person_chunks:
        # Join all text parts within a person chunk (surname may be on one br, given on next)
        parts = re.split(r'<br\s*/?>', chunk, flags=re.I)
        person_text = " ".join(
            _strip_html(p).strip().rstrip(',').strip()
            for p in parts
            if _strip_html(p).strip().rstrip(',').strip()
        )
        if person_text and len(person_text) > 1:
            names.append(person_text)

    # Cells 3+: date, doc#, state, meridian, twp-rng, aliquots, sec, county
    def cell(i): return _strip_html(cells[i]) if len(cells) > i else ""

    date_str  = cell(3)
    state     = cell(5)
    meridian  = cell(6)
    twp_rng   = cell(7)
    aliquots  = cell(8)
    section   = cell(9)
    county    = cell(10)

    # Parse year from date
    year: int | None = None
    date_m = re.search(r'\b(\d{4})\b', date_str)
    if date_m:
        year = int(date_m.group(1))

    # Canonical URL
    url = f"{DETAIL_URL}?accession={accession_raw}&docClass={doc_class}"

    # Primary patentee: first name in list (format: "SURNAME, GIVEN")
    primary = names[0] if names else ""
    name_parts = [p.strip() for p in primary.split(",") if p.strip()]
    surname    = name_parts[0].title() if name_parts else None
    given_name = name_parts[1].title() if len(name_parts) > 1 else None

    return {
        "url":         url,
        "accession":   accession,
        "source":      "blm_land_patents",
        "record_type": "land_patent",
        "title":       primary,
        "text":        (
            f"{primary} - Land patent in {county}, {state}. "
            f"Meridian: {meridian}. Twp-Rng: {twp_rng}. "
            f"Section: {section}. Aliquots: {aliquots}. "
            f"Issued: {date_str}. "
            f"All patentees: {'; '.join(names)}."
        ),
        "year":        year,
        "state":       state,
        "county":      county,
        "surname":     surname,
        "given_name":  given_name,
        "all_names":   names,
        "date_str":    date_str,
        "meridian":    meridian,
    }


def _parse_page(html: str) -> list[dict]:
    """Extract all patent records from a results page."""
    patents = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I)
    for row in rows:
        if 'primaryRowCell' not in row:
            continue
        patent = _parse_row(row)
        if patent:
            patents.append(patent)
    return patents


def _is_last_page(html: str, patents_on_page: int) -> bool:
    """True if this is the last page (no Next link, or fewer than PAGE_SIZE results)."""
    if patents_on_page == 0:
        return True
    if "Next" not in html and ">Next<" not in html and "p=next" not in html.lower():
        # Check for "Next" link pattern
        next_link = re.search(r'searchCriteria=[^"\']+\|p=(\d+)[^"\']*["\'][^>]*>Next', html, re.I)
        if not next_link:
            return True
    return False


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _fetch_page(session: requests.Session, state: str, surname: str, page: int) -> str | None:
    """Fetch one results page. Returns HTML string or None on unrecoverable error."""
    criteria = f"type=patent|st={state}|ln={surname}|sor=s|p={page}"
    url = f"{TAB_URL}?searchCriteria={criteria}"

    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, timeout=30)

            if r.status_code == 429:
                print(f"[BLM] 429 rate-limited — backing off 30 min")
                time.sleep(1800)
                continue

            if r.status_code == 403:
                raise RuntimeError(f"403 blocked on state={state} surname={surname}")

            if r.status_code != 200:
                wait = 2 ** attempt * 5
                print(f"[BLM] HTTP {r.status_code} on {state}/{surname} p{page} — retry in {wait}s")
                time.sleep(wait)
                continue

            html = r.text

            if "System Error" in html:
                wait = 2 ** attempt * 10
                print(f"[BLM] System Error on {state}/{surname} p{page} (attempt {attempt+1}) — retry in {wait}s")
                time.sleep(wait)
                continue

            return html

        except RuntimeError:
            raise
        except Exception as e:
            wait = 2 ** attempt * 5
            print(f"[BLM] Exception on {state}/{surname} p{page}: {e} — retry in {wait}s")
            time.sleep(wait)

    print(f"[BLM] Giving up on {state}/{surname} p{page} after {MAX_RETRIES} attempts")
    return None


# ── Main entry ────────────────────────────────────────────────────────────────

def run():
    print(f"[BLM] Fetcher starting — {len(EASTERN_STATES)} eastern states, surname sweep")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    session = requests.Session()
    session.headers.update(HEADERS)

    surnames = _load_surnames()
    print(f"[BLM] Surname list: {len(surnames)} names")

    progress  = _load_progress()
    total_saved = 0

    for state in EASTERN_STATES:
        if PAUSE_FILE.exists():
            print("[BLM] PAUSE_DOWNLOADS set — waiting 60s")
            time.sleep(60)

        state_dir = OUT_DIR / state.lower()
        state_dir.mkdir(exist_ok=True)
        state_saved = 0

        print(f"[BLM] State: {state}")

        for surname in surnames:
            pk = _progress_key(state, surname)
            if progress.get(pk) == "done":
                continue  # already finished this (state, surname) pair

            if PAUSE_FILE.exists():
                print("[BLM] PAUSE_DOWNLOADS set — waiting 60s")
                time.sleep(60)

            page = 1
            surname_saved = 0

            while True:
                html = _fetch_page(session, state, surname, page)
                if html is None:
                    break  # unrecoverable — skip this pair

                patents = _parse_page(html)

                for patent in patents:
                    url = patent["url"]
                    if _already_done(con, url):
                        continue

                    acc = patent["accession"].replace("/", "_").replace("\\", "_")
                    out_file = state_dir / f"{acc}.json"
                    out_file.write_text(json.dumps(patent, ensure_ascii=False), encoding="utf-8")
                    _mark_fetched(con, url)
                    surname_saved += 1
                    state_saved   += 1
                    total_saved   += 1

                is_done = _is_last_page(html, len(patents))

                if patents:
                    print(f"[BLM] {state}/{surname} p{page}: {len(patents)} patents "
                          f"(+{surname_saved} this surname, {state_saved} this state)")

                if is_done:
                    break

                page += 1
                time.sleep(REQUEST_DELAY)

            # Mark this (state, surname) pair done
            progress[pk] = "done"
            _save_progress(progress)

            if surname_saved == 0 and page == 1:
                pass  # silent skip for empty surnames (most will be empty)
            else:
                print(f"[BLM] {state}/{surname}: {surname_saved} patents saved")

            time.sleep(REQUEST_DELAY)

        print(f"[BLM] {state}: {state_saved} total patents saved")

    print(f"[BLM] All states done — {total_saved:,} total patents saved")


if __name__ == "__main__":
    run()
