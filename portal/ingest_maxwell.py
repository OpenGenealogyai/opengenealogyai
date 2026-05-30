"""
ingest_maxwell — Read Garlon's documented Maxwell patriline from
D:\\AI\\Companies\\open-genealogical-ai\\family_tree\\ (Find A Grave handoff JSON)
and upsert each ancestor into the Postgres `persons` mirror table.

Run:  python portal/ingest_maxwell.py
Re-run safely: upserts by person_id (deterministic UUID5).

NOTE: portal/app.py's `persons` mirror only carries denormalized
top-confidence fields. Full assertion arrays live in MAXGEN JSON (source of
truth). This mirror is what enables fast Postgres JOINs for chart/list views.

Also adds father_id and mother_id columns if missing (one-time migration).
"""
from __future__ import annotations
import os, sys, json, re, uuid
from pathlib import Path
from datetime import datetime

# Force the .env so we have ANTHROPIC etc. — and add the PG password
ENV_FILE = Path(r"C:\Users\stock\Dropbox\Claude Cowork\.env")
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

try:
    import psycopg
except ImportError:
    # Postgres adapter — try psycopg2 fallback
    try:
        import psycopg2 as psycopg
    except ImportError:
        print("ERROR: install psycopg (`pip install psycopg[binary]`) before running.")
        sys.exit(1)

FAMILY_TREE_ROOT = Path(r"D:\AI\Companies\open-genealogical-ai\family_tree")
NAMESPACE = uuid.UUID("4abb1d1a-3b1c-4a3c-9aaa-000000000001")  # arbitrary, fixed

DB_NAME = os.environ.get("PG_DATABASE", "opengenealogyai")
DB_USER = os.environ.get("PG_USER", "postgres")
DB_HOST = os.environ.get("PG_HOST", "localhost")
DB_PORT = int(os.environ.get("PG_PORT", "5432"))


def slug_to_uuid(slug: str) -> str:
    """Stable UUID5 from a slug — so re-runs upsert instead of duplicating."""
    return str(uuid.uuid5(NAMESPACE, slug))


def parse_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    m = re.search(r"(1[6-9]\d{2}|20\d{2})", str(date_str))
    return int(m.group(1)) if m else None


def parse_date(date_str: str | None) -> tuple[int | None, int | None, int | None]:
    """Return (year, month, day) — best effort from FAG date strings like
    '14 Mar 1821' or '8 Dec 1740' or just '1821' or 'Sep 1810'."""
    if not date_str:
        return None, None, None
    months = {m: i for i, m in enumerate(
        ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], start=1)}
    year = parse_year(date_str)
    m = None
    d = None
    for tok in re.split(r"[\s,]+", str(date_str).strip()):
        if not tok:
            continue
        t = tok.lower()[:3]
        if t in months and m is None:
            m = months[t]
        elif tok.isdigit() and len(tok) <= 2 and d is None:
            d = int(tok)
    return year, m, d


def load_fag_files() -> list[dict]:
    """Find every findagrave_*.json under family_tree/. Slug = unique per memorial_id."""
    out = []
    if not FAMILY_TREE_ROOT.exists():
        print(f"WARN: family_tree folder missing: {FAMILY_TREE_ROOT}")
        return out
    for sub in sorted(FAMILY_TREE_ROOT.iterdir()):
        if not sub.is_dir():
            continue
        # Read every findagrave_*.json — not just maxwell- folders, so wives'
        # lines (Anderson, Bracken, Cox, DeGraw, Hodge, Carpenter, McCutcheon,
        # Purviance) and descendants all land in the DB.
        for f in sub.glob("findagrave_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                mid = str(data.get("memorial_id", "")).strip()
                if not mid:
                    continue
                # Slug = folder + memorial_id, ensuring uniqueness when a folder
                # has multiple FAG JSONs (e.g. Horace + his wife Ive in
                # maxwell-horace-w/).
                data["_slug"] = f"{sub.name}__{mid}"
                data["_folder"] = sub.name
                data["_memorial_id"] = mid
                data["_source_file"] = str(f)
                out.append(data)
            except Exception as e:
                print(f"  skip {f.name}: {e}")
    return out


def normalize_person(fag: dict, parent_slug_to_uuid: dict[str, str]) -> dict:
    """Convert one FAG JSON to a row dict for the persons table."""
    slug = fag["_slug"]
    pid = slug_to_uuid(slug)
    person = fag.get("person", {})
    name = person.get("name", slug)
    parts = name.split()
    surname = next((p for p in parts if p.lower() == "maxwell" or p.lower() == "maxwell)"), "Maxwell")
    given_names = " ".join(p for p in parts if p != surname).strip() or name

    birth = person.get("birth") or {}
    death = person.get("death") or {}
    by, bm, bd = parse_date(birth.get("date"))
    dy, dm, dd = parse_date(death.get("date"))

    # Parent ids by parent memorial_id — find a loaded row with same memorial id
    father_id = None
    mother_id = None
    for parent in fag.get("parents", []):
        if not isinstance(parent, dict):
            continue
        mid = str(parent.get("memorial_id") or "").strip()
        if not mid:
            continue
        # Find the matching loaded slug for this parent memorial_id
        target = None
        for loaded_slug in parent_slug_to_uuid:
            if loaded_slug.endswith("__" + mid):
                target = parent_slug_to_uuid[loaded_slug]
                break
        if not target:
            continue
        pname = (parent.get("name") or "").lower()
        if any(k in pname for k in ["ruth ", "hodge", "lucretia", "elizabeth carpenter",
                                     "jennette", "purviance", "mccutcheon", "ive cox",
                                     "elizabeth rebecca", "clarissa"]):
            mother_id = target
        else:
            father_id = target

    return {
        "person_id":      pid,
        "display_name":   name,
        "surname":        surname,
        "given_names":    given_names,
        "birth_year_min": by,
        "birth_year_max": by,
        "birth_place":    birth.get("place"),
        "death_year_min": dy,
        "death_year_max": dy,
        "death_place":    death.get("place"),
        "is_living_flag": False,
        "redistribution_license": "tier2-private",
        "source_uri":     fag.get("url") or fag.get("_source_file"),
        "father_id":      father_id,
        "mother_id":      mother_id,
        "_slug":          slug,
    }


def ensure_columns(cur):
    """Add father_id and mother_id to persons if missing (one-time mig)."""
    cur.execute("""
        ALTER TABLE persons
          ADD COLUMN IF NOT EXISTS father_id UUID REFERENCES persons(person_id),
          ADD COLUMN IF NOT EXISTS mother_id UUID REFERENCES persons(person_id);
    """)


def upsert_persons(cur, rows: list[dict]):
    """Two-pass upsert: first insert everyone without FKs, then set FKs."""
    insert_sql = """
    INSERT INTO persons
      (person_id, display_name, surname, given_names,
       birth_year_min, birth_year_max, birth_place,
       death_year_min, death_year_max, death_place,
       is_living_flag, redistribution_license, source_uri,
       asserted_at, last_updated_at)
    VALUES
      (%(person_id)s, %(display_name)s, %(surname)s, %(given_names)s,
       %(birth_year_min)s, %(birth_year_max)s, %(birth_place)s,
       %(death_year_min)s, %(death_year_max)s, %(death_place)s,
       %(is_living_flag)s, %(redistribution_license)s, %(source_uri)s,
       now(), now())
    ON CONFLICT (person_id) DO UPDATE SET
      display_name   = EXCLUDED.display_name,
      surname        = EXCLUDED.surname,
      given_names    = EXCLUDED.given_names,
      birth_year_min = EXCLUDED.birth_year_min,
      birth_year_max = EXCLUDED.birth_year_max,
      birth_place    = EXCLUDED.birth_place,
      death_year_min = EXCLUDED.death_year_min,
      death_year_max = EXCLUDED.death_year_max,
      death_place    = EXCLUDED.death_place,
      source_uri     = EXCLUDED.source_uri,
      last_updated_at = now();
    """
    update_fk_sql = """
    UPDATE persons SET
      father_id = COALESCE(%(father_id)s, father_id),
      mother_id = COALESCE(%(mother_id)s, mother_id),
      last_updated_at = now()
    WHERE person_id = %(person_id)s;
    """
    # Pass 1: insert all rows without FKs
    for r in rows:
        cur.execute(insert_sql, r)
    # Pass 2: update FKs (rows now exist as both child and parent targets)
    for r in rows:
        if r.get("father_id") or r.get("mother_id"):
            cur.execute(update_fk_sql, r)


def main():
    print(f"Loading FAG JSONs from {FAMILY_TREE_ROOT}")
    fags = load_fag_files()
    print(f"  found {len(fags)} files")

    # First pass: slugs -> uuids
    slug_to_id = {f["_slug"]: slug_to_uuid(f["_slug"]) for f in fags}

    rows = [normalize_person(f, slug_to_id) for f in fags]

    # Stamp folder + memorial_id into each row for the per-folder backfill
    for r, f in zip(rows, fags):
        r["_folder"] = f.get("_folder")
        r["_memorial_id"] = f.get("_memorial_id")

    # Backfill known patriline edges by folder name (handle the cases where
    # the FAG JSON's parents block doesn't include memorial_ids we can match)
    folder_to_id = {}
    for r in rows:
        folder_to_id.setdefault(r.get("_folder"), r["person_id"])

    def link_folder(target_folder, father_folder=None, mother_folder=None):
        for r in rows:
            if r.get("_folder") == target_folder:
                if father_folder and father_folder in folder_to_id and not r.get("father_id"):
                    r["father_id"] = folder_to_id[father_folder]
                if mother_folder and mother_folder in folder_to_id and not r.get("mother_id"):
                    r["mother_id"] = folder_to_id[mother_folder]

    link_folder("maxwell-william-bailey-1821", "maxwell-richard-1796", "hodge-ruth-1800")
    link_folder("maxwell-richard-1796", "maxwell-richard-1774")
    link_folder("maxwell-richard-1774", "maxwell-william-1740", "purviance-jennette-1776")
    link_folder("maxwell-james-bailey-1843", "maxwell-william-bailey-1821", "bracken-lucretia-1823")
    link_folder("maxwell-james-bailey-1870", "maxwell-james-bailey-1843")
    link_folder("maxwell-horace-w", "maxwell-james-bailey-1870", "anderson-elizabeth-carpenter-1871")
    link_folder("maxwell-james-freeborn-1936", "maxwell-horace-w")
    link_folder("maxwell-lori-1966", "maxwell-james-freeborn-1936")

    print(f"Upserting {len(rows)} persons into Postgres ({DB_NAME})")
    conn = psycopg.connect(
        dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT
    )
    try:
        cur = conn.cursor()
        ensure_columns(cur)
        upsert_persons(cur, rows)
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM persons;")
        n = cur.fetchone()[0]
        print(f"  OK — persons table now has {n} rows")
        cur.execute("""
            SELECT display_name, birth_year_min, death_year_min
            FROM persons ORDER BY COALESCE(birth_year_min, 9999);
        """)
        for r in cur.fetchall():
            print(f"    {r[1] or '????'} – {r[2] or '????'}  {r[0]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
