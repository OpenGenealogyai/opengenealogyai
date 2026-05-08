"""
FamilySearch Ancestry Walker
Walks Abraham Lincoln's ancestor tree up to 5 generations using the FamilySearch API.
Saves each person as a MAXGEN-compatible RawRecord JSON file.

Usage:
    python scripts/familysearch_walker.py

Credentials: set FS_USERNAME and FS_PASSWORD in .env
"""

import os
import sys
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.throttle import wait_for_internet  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
FS_USERNAME = os.getenv("FS_USERNAME", "")
FS_PASSWORD = os.getenv("FS_PASSWORD", "")

FS_BASE = "https://api.familysearch.org"
FS_AUTH_URL = f"{FS_BASE}/cis-web/oauth2/v3/token"

LINCOLN_ID = "KWC9-JNP"
MAX_GENERATIONS = 5
RATE_LIMIT_DELAY = 1.0  # seconds between requests

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "familysearch"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fs_walker")


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_access_token(username: str, password: str) -> str:
    """Authenticate via FamilySearch OAuth2 username/password flow."""
    if not username or not password:
        raise ValueError(
            "FS_USERNAME and FS_PASSWORD must be set in .env before running this script."
        )

    log.info("Authenticating with FamilySearch...")
    wait_for_internet()
    resp = requests.post(
        FS_AUTH_URL,
        data={
            "grant_type": "password",
            "client_id": "WCQY-7J1Q-GKVV-7DNM",  # FamilySearch public research client
            "username": username,
            "password": password,
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in auth response: {resp.text}")
    log.info("Authentication successful.")
    return token


# ── API helpers ───────────────────────────────────────────────────────────────

def fs_get(session: requests.Session, path: str) -> dict | None:
    """
    GET a FamilySearch API path. Returns parsed JSON or None on expected failures
    (404, 410 — person not found or no longer available; 451 — living/private).
    Raises on unexpected errors.
    """
    url = f"{FS_BASE}{path}"
    try:
        wait_for_internet()
        resp = session.get(url, timeout=30)
        if resp.status_code in (404, 410):
            log.debug("Person not found: %s", path)
            return None
        if resp.status_code == 451:
            log.debug("Living/private person, skipping: %s", path)
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        log.warning("Timeout fetching %s", url)
        return None
    except requests.exceptions.ConnectionError as exc:
        log.warning("Network error fetching %s: %s", url, exc)
        return None
    except requests.exceptions.HTTPError as exc:
        log.warning("HTTP error fetching %s: %s", url, exc)
        return None


def make_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/x-fs-v1+json",
    })
    return session


# ── Person extraction ─────────────────────────────────────────────────────────

def _fact_value(facts: list[dict], fact_type: str, field: str) -> str:
    """Extract a field from a typed fact list."""
    for f in facts or []:
        if f.get("type", "").endswith(fact_type):
            if field == "date":
                d = f.get("date", {})
                return d.get("original") or d.get("formal") or ""
            if field == "place":
                p = f.get("place", {})
                return p.get("original") or p.get("description") or ""
    return ""


def fetch_person(session: requests.Session, person_id: str) -> dict | None:
    """Fetch person details. Returns a normalized dict or None."""
    data = fs_get(session, f"/platform/tree/persons/{person_id}")
    if not data:
        return None

    persons = data.get("persons", [])
    if not persons:
        return None

    p = persons[0]
    names = p.get("names", [])
    display = p.get("display", {})

    # Prefer display fields (already normalized by FS), fall back to facts
    full_name = display.get("name") or ""
    if not full_name and names:
        for n in names:
            if n.get("preferred"):
                parts = n.get("nameForms", [{}])[0]
                full_name = parts.get("fullText", "")
                break
        if not full_name and names:
            parts = names[0].get("nameForms", [{}])[0]
            full_name = parts.get("fullText", "")

    facts = p.get("facts", [])
    birth_date = display.get("birthDate") or _fact_value(facts, "Birth", "date")
    birth_place = display.get("birthPlace") or _fact_value(facts, "Birth", "place")
    death_date = display.get("deathDate") or _fact_value(facts, "Death", "date")
    death_place = display.get("deathPlace") or _fact_value(facts, "Death", "place")
    gender = p.get("gender", {}).get("type", "").split("/")[-1].lower()

    is_living = p.get("living", False)

    return {
        "id": person_id,
        "name": full_name or "Unknown",
        "birth_date": birth_date or "",
        "birth_place": birth_place or "",
        "death_date": death_date or "",
        "death_place": death_place or "",
        "gender": gender or "unknown",
        "is_living": is_living,
    }


def fetch_parents(session: requests.Session, person_id: str) -> list[str]:
    """Return list of parent Person IDs for the given person."""
    data = fs_get(session, f"/platform/tree/persons/{person_id}/parents")
    if not data:
        return []

    parent_ids = []
    for rel in data.get("childAndParentsRelationships", []):
        for key in ("father", "mother"):
            ref = rel.get(key)
            if ref:
                pid = ref.get("resourceId") or ref.get("resource", "").split("/")[-1]
                if pid:
                    parent_ids.append(pid)
    return parent_ids


# ── Record serialization ──────────────────────────────────────────────────────

def person_to_raw_record(person: dict) -> dict:
    """Convert a fetched person dict to a MAXGEN RawRecord-compatible structure."""
    now_iso = datetime.now(timezone.utc).isoformat()
    person_id = person["id"]

    # Build transcription text
    lines = [f"Name: {person['name']}"]
    if person["birth_date"] or person["birth_place"]:
        lines.append(f"Born: {person['birth_date']} {person['birth_place']}".strip())
    if person["death_date"] or person["death_place"]:
        lines.append(f"Died: {person['death_date']} {person['death_place']}".strip())
    if person["gender"]:
        lines.append(f"Gender: {person['gender']}")

    return {
        "record_id": str(uuid.uuid4()),
        "schema_version": "1.0",
        "record_type": "other",
        "redistribution_license": "CC0",
        "is_living_flag": person.get("is_living", False),
        "source_url": f"https://www.familysearch.org/tree/person/details/{person_id}",
        "repository": "FamilySearch",
        "collection": "FamilySearch Family Tree",
        "digital_object_id": person_id,
        "extraction_confidence": 0.85,
        "extracted_by": "FamilySearch Walker (automated)",
        "extracted_at": now_iso,
        "language": "en",
        "transcription": "\n".join(lines),
        "persons_mentioned": [
            {
                "name_as_written": person["name"],
                "role": "subject",
                "gender_as_written": person["gender"],
            }
        ],
        "record_date": {},
        "location": {
            "place_as_written": person["birth_place"] or person["death_place"] or "",
        },
        "sensitive_data_redacted": False,
        # Extended fields (not in strict schema but useful for downstream use)
        "_familysearch_id": person_id,
        "_extracted": {
            "name": person["name"],
            "birth_date": person["birth_date"],
            "birth_place": person["birth_place"],
            "death_date": person["death_date"],
            "death_place": person["death_place"],
            "gender": person["gender"],
        },
    }


# ── Walker ────────────────────────────────────────────────────────────────────

def walk_ancestors(
    session: requests.Session,
    start_id: str,
    max_generations: int,
) -> None:
    """
    BFS walk of the ancestor tree. Prints an ASCII tree and saves JSON files.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Queue entries: (person_id, generation, indent_prefix, is_last_sibling)
    queue: list[tuple[str, int, str, bool]] = [(start_id, 0, "", True)]
    visited: set[str] = set()
    saved_count = 0

    print(f"\n=== FamilySearch Ancestry Walker — Starting from {start_id} ===\n")

    while queue:
        person_id, generation, prefix, is_last = queue.pop(0)

        if person_id in visited:
            continue
        visited.add(person_id)

        # ── Fetch person ──────────────────────────────────────────────────────
        log.debug("Fetching person %s (gen %d)", person_id, generation)
        wait_for_internet()
        person = fetch_person(session, person_id)
        time.sleep(RATE_LIMIT_DELAY)

        if person is None:
            connector = "└── " if is_last else "├── "
            print(f"{prefix}{connector}[{person_id}] (unavailable)")
            continue

        if person.get("is_living"):
            connector = "└── " if is_last else "├── "
            print(f"{prefix}{connector}[{person_id}] (living — skipped)")
            continue

        # ── Print tree node ───────────────────────────────────────────────────
        connector = "└── " if is_last else "├── "
        if generation == 0:
            label = f"{person['name']} [{person_id}]"
        else:
            birth = f"b. {person['birth_date']}" if person["birth_date"] else ""
            death = f"d. {person['death_date']}" if person["death_date"] else ""
            dates = "  " + "  ".join(filter(None, [birth, death])) if (birth or death) else ""
            label = f"{person['name']} [{person_id}]{dates}"

        print(f"{prefix}{connector}{label}")

        # ── Save JSON ─────────────────────────────────────────────────────────
        record = person_to_raw_record(person)
        out_path = OUTPUT_DIR / f"{person_id}.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, ensure_ascii=False)
        saved_count += 1
        log.debug("Saved %s", out_path)

        # ── Queue parents ─────────────────────────────────────────────────────
        if generation < max_generations:
            wait_for_internet()
            parents = fetch_parents(session, person_id)
            time.sleep(RATE_LIMIT_DELAY)

            # Build next indent
            if generation == 0:
                child_prefix = ""
            else:
                child_prefix = prefix + ("    " if is_last else "│   ")

            for i, parent_id in enumerate(parents):
                if parent_id not in visited:
                    is_last_parent = (i == len(parents) - 1)
                    queue.append((parent_id, generation + 1, child_prefix, is_last_parent))

    print(f"\n=== Done. {saved_count} records saved to {OUTPUT_DIR} ===\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not FS_USERNAME or not FS_PASSWORD:
        print(
            "ERROR: FS_USERNAME and FS_PASSWORD are not set in your .env file.\n"
            "Edit .env and add your FamilySearch credentials, then run again."
        )
        return

    try:
        token = get_access_token(FS_USERNAME, FS_PASSWORD)
    except Exception as exc:
        print(f"Authentication failed: {exc}")
        return

    session = make_session(token)

    try:
        walk_ancestors(session, LINCOLN_ID, MAX_GENERATIONS)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as exc:
        log.exception("Unexpected error: %s", exc)


if __name__ == "__main__":
    main()
