"""
FamilySearch Tier-2 record fetcher for OpenGenealogyAI.

IMPORTANT: Every record fetched from FamilySearch is marked:
  - redistribution_license: "tier2-private"
  - is_living_flag: computed from birth year (> current_year - 110) or FS data
  - These records are NEVER included in open Qdrant or public endpoints.
  - They go into a separate private staging area for the authorized user only.

FamilySearch API key fields:
  Person: GET /platform/tree/persons/{pid}
  Person search: GET /platform/tree/persons?q=givenName:John+surname:Smith

Usage:
    from agents.familysearch.fs_fetcher import FSRecordFetcher
    from agents.familysearch.fs_oauth import FSAuthSession

    session = FSAuthSession(client_id=..., redirect_uri=...)
    # ... OAuth flow ...
    fetcher = FSRecordFetcher(session)
    record = fetcher.fetch_person_as_rawrecord("LZNY-BQH")
"""

import datetime, re, uuid
from typing import Optional
from agents.familysearch.fs_oauth import FSAuthSession

TIER2_LICENSE = "tier2-private"
CURRENT_YEAR = datetime.datetime.now().year


def _is_living(birth_year: Optional[int], death_year: Optional[int]) -> bool:
    if death_year:
        return False
    if birth_year is None:
        return True  # unknown birth → assume potentially living
    return birth_year > (CURRENT_YEAR - 110)


def _extract_year(date_str: str) -> Optional[int]:
    if not date_str:
        return None
    m = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", date_str)
    return int(m.group()) if m else None


def _extract_name(person_data: dict) -> str:
    """Extract preferred display name from FS person object."""
    names = person_data.get("names", [])
    for name in names:
        if name.get("preferred"):
            parts = name.get("nameForms", [])
            if parts:
                return parts[0].get("fullText", "")
    if names:
        parts = names[0].get("nameForms", [])
        if parts:
            return parts[0].get("fullText", "")
    return ""


class FSRecordFetcher:
    """Fetch FamilySearch persons and convert to tier2-private RawRecords."""

    def __init__(self, session: FSAuthSession):
        self.session = session

    def fetch_person_raw(self, person_id: str) -> dict:
        """Fetch raw FamilySearch person JSON."""
        data = self.session.get(f"/platform/tree/persons/{person_id}")
        persons = data.get("persons", [])
        if not persons:
            raise ValueError(f"No person found for id={person_id}")
        return persons[0]

    def fetch_person_as_rawrecord(self, person_id: str) -> dict:
        """
        Fetch a FamilySearch person and return a tier2-private RawRecord.
        The caller is responsible for never exposing this through open endpoints.
        """
        person = self.fetch_person_raw(person_id)

        display = person.get("display", {})
        birth_date = display.get("birthDate", "")
        death_date = display.get("deathDate", "")
        birth_place = display.get("birthPlace", "")

        birth_year = _extract_year(birth_date)
        death_year = _extract_year(death_date)
        living = _is_living(birth_year, death_year)

        name_str = _extract_name(person)

        record = {
            "record_id": str(uuid.uuid4()),
            "schema_version": "0.1",
            "record_type": "other",
            "redistribution_license": TIER2_LICENSE,
            "is_living_flag": living,
            "source_url": f"https://www.familysearch.org/tree/person/{person_id}",
            "digital_object_id": person_id,
            "repository": "FamilySearch",
            "collection": "FamilySearch Family Tree",
            "transcription": f"{name_str} b.{birth_date} d.{death_date} {birth_place}".strip(),
            "language": "en",
            "extraction_confidence": 0.80,
            "extracted_by": "fs-fetcher-agent-001",
            "extracted_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sensitive_data_redacted": False,
        }

        if name_str:
            record["persons_mentioned"] = [{"name_as_written": name_str, "role": "subject"}]

        if birth_year:
            record["record_date"] = {
                "year_min": birth_year,
                "year_max": death_year if death_year else birth_year,
                "date_type": "estimated",
            }

        if birth_place:
            record["location"] = {"place_as_written": birth_place}

        return record

    def search_persons(self, given_name: str, surname: str, birth_year: Optional[int] = None) -> list[dict]:
        """
        Search FamilySearch for persons matching name/year.
        Returns list of tier2-private RawRecords.
        """
        q_parts = []
        if given_name:
            q_parts.append(f"givenName:{given_name}")
        if surname:
            q_parts.append(f"surname:{surname}")
        if birth_year:
            q_parts.append(f"birthLikeDate:{birth_year}")

        query = "+".join(q_parts)
        data = self.session.get(f"/platform/tree/persons?q={query}&count=20")

        records = []
        for entry in data.get("entries", []):
            pid = entry.get("id", "")
            if not pid:
                continue
            try:
                record = self.fetch_person_as_rawrecord(pid)
                records.append(record)
            except Exception:
                continue
        return records
