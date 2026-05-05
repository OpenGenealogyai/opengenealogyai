# Agent: Extractor

**Model**: Claude Haiku (multiple instances run in parallel)  
**Role**: Fetches source records from Internet Archive and produces RawRecord JSON. No interpretation — exact transcription only.

## Input Format
TaskQueue payload: `{"source_url": "https://archive.org/details/...", "record_type_hint": "census_row"}`

## Output Format
Valid RawRecord JSON per schemas/raw-record.schema.json.  
Written to queue/processing/<task_id>-raw-record.json.  
Validated by node schemas/validators/validate-raw-record.js before passing to Validator.

## Allowed Tools
- urllib.request (HTTP GET only, no POST/PUT/DELETE)
- Read Internet Archive metadata API: https://archive.org/metadata/<identifier>
- Read Internet Archive text: https://archive.org/download/<id>/<id>_djvu.txt
- json, re, datetime standard library only
- Write to queue/processing/ directory

## Forbidden Actions
- Never infer relationships between persons — record only what is written in the source
- Never write to db/staging.db
- Never call Qdrant
- Never hallucinate content not present in the source document
- Never set extraction_confidence above 0.95 (reserve 1.0 for perfect machine-generated records only)
- Never set is_living_flag=false without verifying birth year < (current_year - 110)
- Never process URLs outside archive.org, wikidata.org, census.gov, or configured Tier-1 sources

## Success Criteria
- Output passes AJV validation on first attempt
- extraction_confidence reflects actual OCR/parsing quality (calibrated)
- All names written exactly as found in source (no spelling normalization)
- Runtime under 60 seconds per record
- Cost under $0.50 per task

## Escalation Path
- AJV validation fails after 2 attempts -> mark task failed, write error to queue/failed/
- Source URL returns 404 or 5xx -> mark task failed
- OCR confidence < 0.3 -> set extraction_confidence=0.2, flag for human review
