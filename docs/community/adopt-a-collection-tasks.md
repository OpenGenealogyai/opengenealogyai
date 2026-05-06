# Adopt a Collection — Task Board

**Status:** Draft | **Updated:** 2026-05-05

Each row below is an unclaimed (or in-progress) collection that needs an agent run and human validation.
To claim: comment on the linked GitHub Issue. One person per collection at a time.

---

## Priority 1 — High Genealogical Value, CC0

| Collection | Records (est.) | Record Type | Claimed By | Status | Notes |
|------------|---------------|-------------|------------|--------|-------|
| illinois-statewide-death-index-1916-1950 | ~450,000 | death_certificate | — | Unclaimed | Statewide index, great for IL families |
| us-census-1880 | ~50M rows | census_row | — | Unclaimed | All public domain; large, batch in chunks |
| us-census-1900 | ~76M rows | census_row | — | Unclaimed | Includes immigration + naturalization data |
| civil-war-pension-records | ~2.3M | military_record | — | Unclaimed | Includes widows/dependents — rich relationship data |
| freedmens-bureau-records | ~1.5M | other | — | Unclaimed | Critical for African American genealogy; challenging OCR |
| pennsylvania-german-church-records | ~200,000 | parish_register | — | Unclaimed | German/Latin records; need language tagging |
| new-england-historic-genealogical-society | ~500,000 | parish_register | — | Unclaimed | NEHGS colonial records 1620–1900 |

---

## Priority 2 — Good Value, Requires License Verification

| Collection | Records (est.) | Record Type | Claimed By | Status | Notes |
|------------|---------------|-------------|------------|--------|-------|
| folger-shakespeare-library-genealogy | ~15,000 | parish_register | — | Unclaimed | British 1500–1800; license = public-domain |
| us-census-1910 | ~92M rows | census_row | — | Unclaimed | First census after Ellis Island peak |
| us-census-1920 | ~106M rows | census_row | — | Unclaimed | Last census with full data available |
| homestead-land-records-1862-1908 | ~400,000 | land_deed | — | Unclaimed | Great for Midwest/Great Plains families |
| naturalization-records-1790-1906 | ~350,000 | naturalization_record | — | Unclaimed | Pre-standard: form varies wildly |
| immigration-records-1820-1957 | ~70M | immigration_record | — | Unclaimed | Ellis Island era; many OCR variants |

---

## Priority 3 — Specialized / Lower Volume

| Collection | Records (est.) | Record Type | Claimed By | Status | Notes |
|------------|---------------|-------------|------------|--------|-------|
| california-death-records-1940-1997 | ~3M | death_certificate | — | Unclaimed | Western US coverage gap |
| southern-claims-commission-1871-1880 | ~22,000 | court_record | — | Unclaimed | Loyalty oaths; Civil War South |
| ww2-draft-cards | ~24M | military_record | — | Unclaimed | Physical descriptions; helps with photo matching |
| quaker-meeting-records | ~250,000 | parish_register | — | Unclaimed | Often most accurate pre-1800 records |
| ohio-death-certificates-1908-1944 | ~1.1M | death_certificate | — | Unclaimed | Midwest coverage |

---

## How to Complete a Collection

1. **Claim it** — comment on the GitHub Issue for this collection
2. **Fetch items** — `python agents/ia-fetcher/ia_fetcher.py --collection {id} --max 100`
3. **Convert** — `python agents/ia-fetcher/ia_to_rawrecord.py {item.json}`
4. **Validate** — `node schemas/validators/validate-raw-record.js {record.json}`
5. **Store** — place validated records in `data/raw-records/{collection-id}/`
6. **PR** — open a pull request with your extracted records + a short summary of quality/coverage

---

## Completion Criteria

A collection is "done" when:
- [x] At least 100 records extracted and schema-validated
- [x] `extraction_confidence` set realistically (not all 0.9 — use your judgment)
- [x] `is_living_flag` correctly set on all records
- [x] `redistribution_license` verified for every record
- [x] PR reviewed and merged

---

## Recognition

Every contributor who completes a collection gets:
- Credit in `CONTRIBUTORS.md`
- Their `contributor_id` embedded in every extracted record they produced
- A shoutout in the monthly community update (when we have one)
