# MAXGEN Schema Changelog

Version history for the four MAXGEN schemas: **MaxRecord**, **MaxPerson**,
**MaxTask**, **MaxDNA**.

## Versioning policy — LOCKSTEP (as of v1.3)

All four schemas share **one MAXGEN version number**. When any schema changes,
the whole standard's version increments and every schema's `schema_version`
const is stamped with the new number — even schemas that did not change in that
release.

This is the model used by HL7 FHIR releases and GEDCOM versions: you adopt
"MAXGEN v1.3" as a set, not schema-by-schema. It makes compatibility trivial to
reason about and makes version skew (different schemas reporting different
versions) impossible by construction.

- **Major version** (`v1` → `v2`): breaking changes. New `$id` URL namespace
  (`/schemas/maxgen/v2/`). Requires Human Gate HG-6.
- **Minor version** (`v1.2` → `v1.3`): additive, backward-compatible. Same `$id`
  URL; `schema_version` const bumped across all schemas; all fixtures
  re-stamped and re-validated.

Before v1.3, schemas versioned independently, which produced confusing skew
(MaxTask sat at 0.1 while MaxPerson reached 1.2). v1.3 ended that by adopting
lockstep and bringing every schema to the same number.

---

## v1.4 — 2026-05-17

**Theme:** Photos as a first-class field. A face transforms genealogy from data
to story; previous versions had no model for portraits and that was a real gap
for end-user engagement. Garlon-requested.

### MaxPerson
- **`photo_assertions[]`** — portraits and snapshots OF this person (NOT
  gravestones or documents — those stay on MaxRecord). Each photo carries:
  - `photo_id`, `url`, `thumbnail_url`, `storage_tier`
    (internet_archive / local_private / contributor_upload / external)
  - `caption`, `year_min/max`, `place_as_written`, `photographer`, `license`
  - `is_primary` — designate ONE photo as the profile image (ties broken by
    confidence then most-recent `asserted_at`)
  - `confidence` — is this actually this person? (same scale as other
    assertions; see CONFIDENCE_CALIBRATION.md)
  - `subject_role` enum (solo / group / wedding / family / military /
    occupational / unknown) so UI knows whether to auto-crop
  - `face_bounding_box` (normalized 0–1 coords) — optional, for auto-cropping
    group photos to the subject's face in cards and pedigree nodes
  - `alt_text` — accessibility (screen-reader description)
  - `ia_id` — Internet Archive identifier when stored there
  - `source_record_id` — optional link back to a MaxRecord (e.g. obituary with
    a portrait)
- Living-subject photos inherit `tier2-private` regardless of declared
  `license`, per the existing privacy gate.
- Photography min year set to 1839 (invention of the technology).

### Lockstep version bump (no content change)
- MaxRecord, MaxTask, MaxDNA all bumped to `schema_version: "1.4"` per the
  lockstep policy. Their descriptions now note "schema content stable since
  vX.X; version stamp follows lockstep MAXGEN release versioning."

### Fixtures
- 58 fixtures re-stamped to v1.4; 62/62 validate against new schemas.

---

## v1.3 — 2026-05-17

**Theme:** Scale-readiness for the 1.5B-person dedup roadmap, plus lockstep
versioning. All additive — no breaking changes. Approved via six-brain review
2026-05-17 (option A: additive batch).

### MaxPerson
- **Merge/dedup provenance model** (the headline change):
  - `merge_history[]` — entities absorbed INTO this one, each with
    `merge_confidence`, `merge_method` (exact_external_id / probabilistic_match
    / manual / dna_confirmed), `match_signals`, `merged_by`, `merged_at`,
    `reverted_at`. A merge is a reversible assertion, never a deletion.
  - `duplicate_of` — when this entity was absorbed, points to the survivor.
  - `merge_status` — active / merged_away / split_pending.
  - Design principle: nothing is destroyed on merge. The absorbed entity
    persists with `merge_status='merged_away'`, preserving append-only history
    and full reversibility.
- **`event_assertions[]`** — long-tail life events (baptism, immigration,
  naturalization, residence, census, burial, military_service, will, probate,
  etc.) with an `event_type` enum. First-class birth/death/marriage stay
  separate (most-queried). Adding a new event kind no longer needs a schema bump.
- **`place_registry[]`** — gazetteer normalization. Resolves free-text
  `place_as_written` strings to GeoNames / Wikidata QID / lat-long without
  modifying every assertion (avoids a mass backfill). Handles historical
  polities ("Austria-Hungary 1880") via `historical_polity` + valid-year range.
- **`extensions`** object — designated `additionalProperties:true` namespace for
  experimental fields, so new ideas don't require a schema bump while the rest
  of the schema stays strict.
- **Fix:** birth/death/occupation `year_max` 2025 → 2100.

### MaxRecord, MaxTask, MaxDNA
- `schema_version` const bumped to `1.3` (lockstep; content unchanged this
  release except the version stamp).
- MaxTask jumped 0.1 → 1.3 (was the worst skew offender).

### Tooling
- All 62 fixtures re-stamped to `1.3` and re-validated (62 PASS / 0 FAIL).

### Companion docs
- ✅ **[`CONFIDENCE_CALIBRATION.md`](CONFIDENCE_CALIBRATION.md)** — defines the
  anchored confidence scale, per-assertion scoring procedure, noisy-OR
  corroboration (+ independence rule), conflict handling, the
  `composite_confidence` formula, and cross-agent calibration via a gold set.
  (Completed 2026-05-17.)

### Deferred to later work (not in v1.3)
- Atomicity enforcement for bidirectional-sync — an implementation task in the
  Postgres `persons`-mirror transaction layer, not a schema change.
- Gazetteer integration — populating `place_registry` from GeoNames / Wikidata
  (the field exists now; population happens after the embedding run stabilizes).

---

## v1.2 — 2026-05-15

**Theme:** DNA layer + Max* naming + symmetric-relationship discipline.

### Naming
- Renamed `MXRecord` → **MaxRecord**, `MXPerson` → **MaxPerson**,
  `TaskQueue` → **MaxTask** (Garlon preference: "Max" not "MX").
- MaxTask moved into the `maxgen/v1` `$id` namespace (was legacy `v0.1`).

### MaxDNA (new schema)
- Created `dna.schema.json` — DNA test metadata + match assertions linked to a
  MaxPerson. Purpose: strengthen ancestor confidence, not living-cousin
  discovery.
- Hard-locked safety constants: `redistribution_license` = `tier2-private`,
  `raw_genotype_stored` = `false`, `kit_id_hash` / `external_ids` = HMAC-SHA-256
  (64-hex regex).
- Six-brain review 2026-05-15 added 9 amendments: `shared_cm` max → 7000,
  `longest_segment_cm` max → 285, `cm_map_version`, `phasing_status`,
  `common_ancestor_candidates[]` (replacing the singular field), HMAC (not plain
  SHA-256), `is_living_flag` default policy.

### MaxPerson
- Added `dna_evidence[]` — DNA chains touching this person as candidate MRCA;
  feeds noisy-OR confidence boosting.
- `spouse_assertions` expanded: explicit bidirectional-sync requirement, plus
  `end_year_min/max`, `end_reason` (divorce / annulment / death_of_spouse /
  separation), `marriage_place_as_written`, `relationship_type` (marriage /
  civil_union / domestic_partnership / common_law), `conflict_flag`.
- `parent_assertions` — bidirectional-sync warning added (was only documented
  on the `child_assertions` side).

---

## v1.1 — (pre-2026-05-15)

**Theme:** Richer person assertions + more record types.

### MaxPerson
- Added `child_assertions[]` (bidirectional with `parent_assertions`).
- Added `occupation_assertions[]` (for disambiguation when name + date aren't
  enough).
- Added `external_ids` map (cross-source dedup: wikidata_qid, familysearch_pid,
  findagrave_id, ia_id, ssdi_id).

### MaxRecord
- Added record types: `land_patent`, `wikidata_entity`, `open_library_work`,
  `dpla_item`.

---

## v1.0 — initial release

- Three schemas: MaxRecord (source documents), MaxPerson (probabilistic
  identities), MaxTask (distributed work queue).
- Core design: uncertainty-as-data. Every claim is an assertion with confidence
  + source + timestamp. Nothing is ever overwritten. Multiple possible parents
  coexist.
- Evidence/interpretation split: MaxRecord = what the document says, MaxPerson =
  what we think it means, linked by `source_record_id`.
- Privacy by design: living-person 404 gate, most-restrictive-license
  propagation.

---

## Schema `$id` URLs (permanent)

These never change within a major version:

- `https://opengenealogyai.org/schemas/maxgen/v1/raw-record.schema.json`
- `https://opengenealogyai.org/schemas/maxgen/v1/person.schema.json`
- `https://opengenealogyai.org/schemas/maxgen/v1/task-queue.schema.json`
- `https://opengenealogyai.org/schemas/maxgen/v1/dna.schema.json`

A breaking change creates `/schemas/maxgen/v2/` and requires Human Gate HG-6.
