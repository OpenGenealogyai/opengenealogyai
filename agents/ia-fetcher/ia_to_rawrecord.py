"""
Convert Internet Archive item metadata + text to a valid RawRecord JSON.
Validates output against the schema before returning.
"""
import json, re, uuid, datetime, subprocess, sys
from pathlib import Path

SCHEMA_VALIDATOR = Path(__file__).parent.parent.parent / "schemas" / "validators" / "validate-raw-record.js"

RECORD_TYPE_HINTS = {
    "death": "death_certificate",
    "birth": "birth_certificate",
    "marriage": "marriage_certificate",
    "census": "census_row",
    "parish": "parish_register",
    "probate": "probate_record",
    "will": "probate_record",
    "military": "military_record",
    "pension": "military_record",
    "immigration": "immigration_record",
    "passenger": "immigration_record",
    "naturalization": "naturalization_record",
    "land": "land_deed",
    "deed": "land_deed",
    "gravestone": "gravestone",
    "obituary": "obituary",
    "newspaper": "newspaper_article",
    "photo": "photograph",
    "bible": "family_bible",
    "court": "court_record",
    "tax": "tax_record",
}

def infer_record_type(title: str, description: str, hint: str | None = None) -> str:
    if hint and hint in set(RECORD_TYPE_HINTS.values()):
        return hint
    text = (title + " " + description).lower()
    for keyword, rtype in RECORD_TYPE_HINTS.items():
        if keyword in text:
            return rtype
    return "other"

def infer_year_range(date_str: str) -> tuple[int | None, int | None]:
    if not date_str:
        return None, None
    years = re.findall(r"\b(1[0-9]{3}|20[0-2][0-9])\b", date_str)
    if not years:
        return None, None
    ints = sorted(int(y) for y in years)
    return ints[0], ints[-1]

def is_potentially_living(year_min: int | None) -> bool:
    if year_min is None:
        return True
    current_year = datetime.datetime.now().year
    return year_min > (current_year - 110)

def ia_to_rawrecord(
    ia_item: dict,
    record_type_hint: str | None = None,
    redistribution_license: str = "public-domain",
    extractor_id: str = "extractor-agent-haiku-001",
    text_content: str | None = None,
) -> dict:
    title = ia_item.get("title", "")
    description = ia_item.get("description", "")
    date_str = ia_item.get("date", "")
    source_url = ia_item.get("source_url", "")
    identifier = ia_item.get("identifier", "")

    record_type = infer_record_type(title, description, record_type_hint)
    year_min, year_max = infer_year_range(date_str)
    living_flag = is_potentially_living(year_min)

    # Transcription: use text_content if available, else title + description
    transcription = text_content[:2000] if text_content else f"{title}. {description}"[:500]

    record = {
        "record_id": str(uuid.uuid4()),
        "schema_version": "0.1",
        "record_type": record_type,
        "redistribution_license": redistribution_license,
        "is_living_flag": living_flag,
        "source_url": source_url if source_url.startswith("http") else f"https://archive.org/details/{identifier}",
        "digital_object_id": identifier,
        "repository": "Internet Archive",
        "collection": ia_item.get("collection_id", ""),
        "transcription": transcription,
        "language": "en",
        "extraction_confidence": 0.60,
        "extracted_by": extractor_id,
        "extracted_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sensitive_data_redacted": False,
    }

    if year_min is not None:
        record["record_date"] = {
            "year_min": year_min,
            "year_max": year_max if year_max else year_min,
            "date_type": "exact" if year_min == year_max else "range",
        }

    # Minimal persons_mentioned (will be enriched by Extractor agent's full OCR pass)
    subjects = ia_item.get("subject", [])
    if subjects:
        record["persons_mentioned"] = [
            {"name_as_written": s, "role": "subject"}
            for s in (subjects if isinstance(subjects, list) else [subjects])
        ][:5]

    return record

def validate_rawrecord(record: dict) -> tuple[bool, list[str]]:
    """Run AJV validator on the record."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(record, f)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ["node", str(SCHEMA_VALIDATOR), tmp_path],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return True, []
        errors = [line.strip() for line in result.stdout.splitlines() if "FAIL" in line or line.strip().startswith("/")]
        return False, errors
    finally:
        os.unlink(tmp_path)

def main():
    if len(sys.argv) < 2:
        print("Usage: python ia_to_rawrecord.py <ia-item.json>")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        ia_item = json.load(f)
    record = ia_to_rawrecord(ia_item)
    valid, errors = validate_rawrecord(record)
    if valid:
        print(json.dumps(record, indent=2))
    else:
        print(f"VALIDATION FAILED: {errors}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
