"""
Wikidata Fetcher — bulk dump download + genealogy person extraction.

Covers both checked-out chunks:
  wikidata-chunk-1  persons A–F
  wikidata-chunk-2  persons G–M

Downloads latest-all.json.bz2 to RAW.wikidata/ once, then streams it,
filtering for Q5 (human) instances that carry at least one genealogy property.
Writes one JSON file per person to RAW.wikidata/persons/.
"""

import bz2, json, time, sqlite3, urllib.request
from pathlib import Path

from pipeline.paths import RAW, LOGS, CHECKPOINTS

DUMP_URL  = "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"
DUMP_FILE = RAW.wikidata / "latest-all.json.bz2"
OUT_DIR   = RAW.wikidata / "persons"

PAUSE_FILE    = LOGS / "PAUSE_DOWNLOADS"
CHECKPOINT_DB = CHECKPOINTS / "pipeline.db"

USER_AGENT = "OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)"

# Both wikidata chunks are checked out — process the full A–M range
LABEL_MIN = "a"
LABEL_MAX = "n"  # exclusive

# Wikidata properties treated as genealogy-relevant
GENEALOGY_PROPS = frozenset({
    "P569", "P570",   # date of birth / death
    "P19",  "P20",    # place of birth / death
    "P22",  "P25",    # father / mother
    "P26",            # spouse
    "P40",            # child
    "P735", "P734",   # given name / family name
    "P1477",          # birth name
})


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
    row = con.execute("SELECT status FROM records WHERE url=?", (url,)).fetchone()
    return row is not None and row[0] != "failed"


# ── Dump download ────────────────────────────────────────────────────────────────

def _download_dump():
    DUMP_FILE.parent.mkdir(parents=True, exist_ok=True)

    if DUMP_FILE.exists() and DUMP_FILE.stat().st_size > 1_000_000_000:
        print(f"[WIKIDATA] Dump already on disk ({DUMP_FILE.stat().st_size / 1e9:.1f} GB) — skipping download")
        return

    print(f"[WIKIDATA] Downloading dump — this is 80+ GB and will take several hours")
    req = urllib.request.Request(DUMP_URL, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(req, timeout=3600) as resp, open(DUMP_FILE, "wb") as out:
        downloaded = 0
        last_log   = time.time()
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            if time.time() - last_log > 60:
                print(f"[WIKIDATA] Download progress: {downloaded / 1e9:.1f} GB")
                last_log = time.time()

    print(f"[WIKIDATA] Download complete: {DUMP_FILE.stat().st_size / 1e9:.1f} GB")


# ── Entity filters ───────────────────────────────────────────────────────────────

def _is_genealogy_person(entity: dict) -> bool:
    """Return True if entity is a human (Q5) with at least one genealogy property."""
    claims = entity.get("claims", {})
    is_human = any(
        c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5"
        for c in claims.get("P31", [])
    )
    if not is_human:
        return False
    return bool(GENEALOGY_PROPS & claims.keys())


def _label_in_range(entity: dict) -> bool:
    label = entity.get("labels", {}).get("en", {}).get("value", "")
    if not label:
        return False
    return LABEL_MIN <= label[0].lower() < LABEL_MAX


# ── Text builder ─────────────────────────────────────────────────────────────────

def _extract_text(entity: dict) -> str:
    parts = []

    label = entity.get("labels", {}).get("en", {}).get("value", "")
    if label:
        parts.append(label)

    desc = entity.get("descriptions", {}).get("en", {}).get("value", "")
    if desc:
        parts.append(desc)

    aliases = [a.get("value", "") for a in entity.get("aliases", {}).get("en", [])]
    if aliases:
        parts.append("Also known as: " + ", ".join(aliases[:3]))

    claims = entity.get("claims", {})
    field_labels = [
        ("P735", "Given name"),
        ("P734", "Family name"),
        ("P1477", "Birth name"),
        ("P569", "Born"),
        ("P570", "Died"),
        ("P19",  "Place of birth"),
        ("P20",  "Place of death"),
    ]
    for prop, field_label in field_labels:
        for claim in claims.get(prop, [])[:1]:
            dv  = claim.get("mainsnak", {}).get("datavalue", {})
            typ = dv.get("type")
            val = dv.get("value")
            if typ == "time" and isinstance(val, dict):
                parts.append(f"{field_label}: {val.get('time', '').lstrip('+')}")
            elif typ == "wikibase-entityid" and isinstance(val, dict):
                parts.append(f"{field_label}: {val.get('id', '')}")
            elif typ == "string" and val:
                parts.append(f"{field_label}: {val}")

    return " | ".join(p for p in parts if p)


# ── Main entry ───────────────────────────────────────────────────────────────────

def run():
    print("[WIKIDATA] Fetcher starting")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _init_db()

    _download_dump()

    print("[WIKIDATA] Streaming dump — filtering persons A–M with genealogy fields")

    count_read = count_out = count_skip = 0
    last_log = time.time()

    with bz2.open(str(DUMP_FILE), "rb") as f:
        for raw_line in f:
            if PAUSE_FILE.exists():
                print("[WIKIDATA] PAUSE_DOWNLOADS — waiting 60s")
                time.sleep(60)
                continue

            line = raw_line.strip()
            if not line or line in (b"[", b"]"):
                continue
            if line.endswith(b","):
                line = line[:-1]

            try:
                entity = json.loads(line)
            except json.JSONDecodeError:
                continue

            count_read += 1

            if not _is_genealogy_person(entity) or not _label_in_range(entity):
                count_skip += 1
                continue

            entity_id = entity.get("id", "")
            url = f"https://www.wikidata.org/wiki/{entity_id}"

            if _already_done(con, url):
                continue

            label = entity.get("labels", {}).get("en", {}).get("value", entity_id)
            text  = _extract_text(entity)

            record = {
                "url":         url,
                "source":      "wikidata",
                "record_type": "person",
                "title":       label,
                "text":        text,
                "year":        None,
            }

            out_file = OUT_DIR / f"{entity_id}.json"
            out_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

            con.execute(
                "INSERT OR IGNORE INTO records (url, source, status, quality) VALUES (?,?,?,?)",
                (url, "wikidata", "fetched", None),
            )
            con.commit()
            count_out += 1

            if time.time() - last_log > 60:
                print(
                    f"[WIKIDATA] Scanned {count_read:,} | Persons saved: {count_out:,} | "
                    f"Skipped: {count_skip:,}"
                )
                last_log = time.time()

    print(f"[WIKIDATA] Done — extracted {count_out:,} persons from {count_read:,} entities")


if __name__ == "__main__":
    run()
