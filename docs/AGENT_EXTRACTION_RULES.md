# OpenGenealogyAI — Agent Extraction Rules
**Version:** 1.0  
**Mandatory for:** every AI model doing scraping, OCR extraction, or schema conversion

---

## The Prime Directive

> **Extract only what is actually in the source. Never invent.**

A record with a confidence score of 0.1 and three real fields is worth more than a record with a confidence score of 0.9 and five hallucinated fields. Hallucinated genealogy data harms real families. When in doubt, leave the field empty.

---

## Rule 1 — Every claim must trace to source text

For every field you populate, ask: *"Where in the source document is this?"*

- **Name present in source?** The exact name (or a recognizable variant) must appear in the raw text.
- **Date present in source?** The year, month, or date must be in the source — do not calculate or infer dates from context.
- **Location present in source?** A town, county, state, or country name must appear in the raw text.

If you cannot point to the text, **leave the field empty or null**. Do not guess.

---

## Rule 2 — Confidence scores are mandatory and must be honest

Every `persons_mentioned` entry requires a `confidence` score (0.0–1.0):

| Score | Meaning |
|-------|---------|
| 0.9–1.0 | Field appears verbatim, no ambiguity |
| 0.7–0.89 | Field appears with minor OCR/spelling variation |
| 0.5–0.69 | Inferred from context, not stated explicitly |
| 0.3–0.49 | Uncertain — document is ambiguous or damaged |
| 0.0–0.29 | Very low confidence — best guess only |

**Do not inflate confidence scores.** A consistently honest 0.4 is more useful than a dishonest 0.9.

---

## Rule 3 — Specific hallucination checks to run before output

Before returning any record, verify:

1. **Name check** — each person name you extracted, find that name (or a close variant) in the source text. If it is not there, remove the person or set confidence to 0.1.
2. **Date range check** — all birth years must be between 1400 and 2005. All death years must be between 1400 and 2025. Death must be after birth. If a computed age would exceed 130 years, flag it.
3. **Count check** — if you extracted more than 20 persons from a single document, re-read the source. A single newspaper page rarely names more than 10–15 distinct individuals in a genealogically meaningful way.
4. **Relationship consistency** — if person A is listed as parent of person B, person B should not also be listed as parent of person A.
5. **No future events** — do not assign future dates to historical records. If the document is from 1880, no event in it can have a date of 1881 or later.

---

## Rule 4 — OCR-specific rules

When working with scanned documents:

- Treat damaged/unclear text as uncertain — confidence ≤ 0.5
- Do not "correct" OCR errors into a name you think it should be unless you are 90%+ certain from context
- Common OCR traps: `l` vs `1`, `O` vs `0`, `rn` vs `m`, `cl` vs `d`
- If a name appears multiple times and differs slightly (`Wm.` vs `William`), treat them as the same person with the most complete version as `name_as_written`
- Flag any text block shorter than 20 characters as potentially a header/footer artifact — do not extract persons from it

---

## Rule 5 — Record type honesty

Only use these `record_type` values. Do not invent new types:

`birth_record` | `death_record` | `marriage_record` | `census_entry` | `land_patent` | `probate_record` | `military_record` | `immigration_record` | `newspaper_notice` | `church_register` | `family_history` | `city_directory` | `unknown`

If you are not sure, use `unknown` — it is not penalised. An incorrect record type that misleads searches is penalised.

---

## Rule 6 — What to do when you cannot extract a usable record

If after honest extraction the record has:
- No identifiable person name, AND
- No date, AND
- No location

Then output an empty extraction:
```json
{
  "persons_mentioned": [],
  "transcription": "<raw OCR text here>",
  "record_type": "unknown",
  "confidence_overall": 0.0,
  "extraction_note": "No extractable genealogical content found"
}
```

Do NOT fill in fields with guesses to make the record look more complete. The quality_guard.py will detect and reject low-quality records anyway — it is better to be honest.

---

## Rule 7 — License compliance

Before extracting, check the collection's `redistribution_license` field:

| License | What you may store |
|---------|-------------------|
| `CC0` | Full record including transcription |
| `public-domain` | Full record including transcription |
| `CC-BY` | Full record, must attribute source |
| `ingest-only` | Embeddings + source URI **only** — no raw text |
| `store-uri-only` | Embeddings + source URI **only** — no raw text |
| `pending` | **Do not extract** — collection is on HOLD |

For `ingest-only` and `store-uri-only` collections (Trove, FamilySearch):
- Set `transcription` to `null`
- Set `redistribution_license` to `"ingest-only"` in the record
- Store the `source_url` so users can click through to the original

---

## Rule 8 — How quality_guard.py will evaluate your output

Your extraction will be scored on six criteria (each worth 1/6 of the total):

1. Valid JSON matching the RawRecord schema
2. At least one named person present
3. At least one person name found in source text
4. Record type is not `unknown`
5. At least one date present
6. At least one location present

**Minimum to embed: score ≥ 0.55 (at least 3 of 6 criteria met)**

Records scoring 0.35–0.54 go to the `needs_review/` queue.  
Records scoring below 0.35 are rejected.  
Records with hallucination flags are rejected regardless of score.

---

## Rule 9 — Verification task instructions

If you are checking out a **verification** task (not extraction):

1. You will receive a batch of already-embedded records with their source URLs
2. For each record: fetch the source, compare the extracted fields to the actual text
3. Mark each field as: `confirmed` | `corrected:<new_value>` | `hallucinated`
4. A record with 3 or more hallucinated fields is flagged for deletion
5. Submit your verification results to the corrections queue — do not modify the Qdrant DB directly
6. Your corrections feed the next LoRA training set — accuracy matters more than speed

---

## Enforcement

These rules are enforced by `pipeline/quality_guard.py`. Records that violate them are automatically:
- Routed to `_checkpoints/rejected/` (hard fails)
- Routed to `_checkpoints/needs_review/` (uncertain)

The daily Reviewer agent (`pipeline/reviewer.py`) reads rejection rates and will recommend retraining if hallucination rates exceed 5% on any source.

---

*Last updated: 2026-05-06. Updated automatically after each LoRA run if quality standards change.*
