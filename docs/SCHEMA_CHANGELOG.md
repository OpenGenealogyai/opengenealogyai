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

## v1.6 — 2026-06-02

**Theme:** Cross-database identity — merge the same person across FamilySearch,
WikiTree, Ancestry, Wikidata, Find a Grave, etc. **Additive / backward-compatible**
(all four schemas stamped `1.6`; 65/65 fixtures pass). Reviewed by three-brain
council (engineer + strategist + Opus operator + jury): unanimous **PROCEED WITH
CAUTION** — design endorsed, with one required privacy guardrail (below).

### MaxPerson — `external_id_assertions[]` (new)
Scored, sourced, **reversible** links from this *conclusion-person* to the same
individual as represented in an external database (a *persona*). Implements the
GEDCOM X persona/conclusion model and mirrors Wikidata `sameAs` practice, but with
genealogy-grade confidence + provenance. Each entry: `system` (open string — ANY
database works), `external_id`, `url`, `confidence` (0–1), `match_method`
(`exact_id_from_source` | `probabilistic_match` | `dna_confirmed` | `hub_crosswalk`
| `manual`), `match_signals{}`, `status` (`active` | `disputed` | `retracted`),
`asserted_by`/`asserted_at`, `retracted_at`.

Key properties:
- **Multiple entries per system are allowed** — external DBs (esp. FamilySearch)
  hold duplicate profiles for one person.
- **Wrong links are retracted (status), never deleted** — auditable, reversible.
- **Never forces one "truth"** — a link is a scored claim, not a fiat merge; this is
  the substrate an AI scorer reads/writes when reconciling across databases.
- Real-world notes baked into the field docs: Ancestry IDs are tree-scoped
  (`tree_id:person_id`); FamilySearch PIDs can become redirects; Wikidata QID is the
  best join hub (P6577 FamilySearch, P2949 WikiTree, P535 Find a Grave → `hub_crosswalk`).

### `external_ids` (existing) → now a denormalized mirror
The flat `{system → id}` map is retained as a top-confidence-per-system convenience
mirror of `external_id_assertions[]`. The merge model (`merge_history` with
`merge_method: exact_external_id`, reversible) is unchanged.

### PRIVACY GUARDRAIL (normative — required by council before publish)
For any record where `is_living = TRUE` (tier2-private), `external_id_assertions`
**MUST NOT** appear in any public share, export, embedding, API response, or commit.
A cross-system identity crosswalk is a powerful de-anonymization vector — strip these
for living subjects like every other tier2-private field. This contract is written
into the field's own schema description so it travels with the standard. (Living
fixture `valid-living-person-tier2.json` carries no external_id_assertions,
demonstrating the gate.)

### Lockstep + fixtures
MaxRecord, MaxTask, MaxDNA stamped `schema_version: "1.6"`. +1 fixture
(`valid-v16-cross-db-identity` — multiple FamilySearch IDs incl. a duplicate, a
WikiTree + Wikidata hub crosswalk, and one `disputed` Ancestry link). 65/65 validate.

---

## v1.5 — 2026-06-02

**Theme:** MaxTask becomes a real distributed-work unit — structured results, a
color-coded verdict vocabulary, and the neutral half of a contributor model
(quality + privacy). **Additive / backward-compatible** — all new fields are
optional; pre-1.5 tasks validate unchanged. Lockstep: all four schemas stamped
`1.5`. 64/64 fixtures pass. Reviewed by three-brain council (verdict: PROCEED
WITH CAUTION — *split economics out of the standard*; see below).

### MaxTask — structured `result` (replaces the free-form blob)
A client-readable result object: `description`, `hypothesis_tested`,
`why_this_matters`, `what_we_did_and_result`, `how_results_affect_goal`,
`what_we_did_with_results`, `next_step`, `confidence`,
`next_directions_suggested[]`, and `steps[]` — **one entry per search performed**
(`action`, `source`, `source_url`, `query`, `found`, `verdict`, `confidence`).
`additionalProperties` stays `true` for extensibility.

### MaxTask — `verdict` enum + UI colors (new `$defs/verdict`)
`key_finding` (GREEN, confirmed/found), `usable` (BLUE, usable lead),
`inconclusive` (AMBER, mixed), **`ruled_out` (RED — a *disproof*: definitively
NOT the right person/record)**, `dead_end` (GREY — searched, found nothing),
`infra` (GREY — support task). `ruled_out` is deliberately distinct from
`dead_end`: a disproof is information; an empty search is not.

### MaxTask — neutral contributor / quality fields (IN the standard)
`parent_task_id`, `acceptance_criteria[]` (objective conditions defining a
complete result), `min_confidence`, `evidence_required[]` (proof a worker must
return — anti-low-effort/anti-fabrication), `contributor{contributor_id,
contributor_type ∈ first_party_ai|third_party_ai|human|organization,
display_name, claimed_at}`, `deadline`, and an independent `review{reviewed_by
(MUST differ from contributor — enforced at app layer), review_verdict ∈
accepted|rework|rejected, quality_score, rejection_reason (incl.
fabricated_or_hallucinated, privacy_violation), review_notes, reviewed_at}`.
These describe *work and quality*, which is neutral, so they belong in the open
standard.

### MaxTask — `contributor_eligibility` PRIVACY GATE (IN the standard)
Enum `first_party_only | any_contributor`, **default `first_party_only`
(fail-closed)**. MUST be `first_party_only` whenever a task concerns a living
person (tier2-private): living-subject tasks are never dispatched to
third-party/human/organization contributors, and any externally dispatched
result must be scrubbed of tier2-private PII.

### Payment/economics are DELIBERATELY NOT in the standard
Per three-brain council (strategist + operator): an open standard must stay
**neutral** — a common work/quality language, not a business model. Hard-coding
`payout`, `list_price_usd`, or a revenue split into the public standard would
(a) fragment adoption (forces everyone into one business model), (b) publish a
portable fraud/sybil blueprint, and (c) push legal/tax burden (worker
classification, KYC/AML, 1099) onto every adopter. So payment lives in the
implementer's **product layer** (The Probable Pedigree) under the open
`extensions{}` namespace — never in core. MaxTask gains an `extensions` object
(`additionalProperties: true`) documenting this. This matches the locked
two-brand architecture (OpenGenealogyAI = standard; The Probable Pedigree =
product). Collusion-resistance, KYC, and worker-classification are the
implementer's responsibility.

### Lockstep version bump (no content change)
MaxRecord, MaxPerson, MaxDNA stamped `schema_version: "1.5"` per lockstep policy.

### Fixtures
+2 task-queue fixtures (`valid-v15-ruled-out`, `valid-v15-marketplace-paid` —
the latter shows `payout` living under `extensions`). 64/64 validate.

---

## v1.4 addendum — 2026-06-02 (NO schema version bump)

**Theme:** Migration / life-event storage clarified, and a biography convention.
This is a **documentation + infrastructure** release. The JSON Schema files did
**not** change — everything here uses fields that already exist. No `schema_version`
bump; no Human Gate. Approved by three-brain council (operator: PROCEED WITH
CAUTION — gate the public commit by diff-inspection).

### Migration & life events live in `event_assertions[]` — do NOT add a `vital_events` table
A contributor session proposed a new flat `vital_events` table for
migration/residence data. **Rejected — it would fork the standard.** The canonical
home already exists: `MaxPerson.event_assertions[]` (since v1.3), whose `event_type`
enum already covers `immigration`, `emigration`, `naturalization`, `residence`,
`census_enumeration`, `land_grant`, `military_service`, `will`, `probate`, `burial`,
etc. A person's migration story = an ordered set of these assertions, each with its
own `year_min/max`, `place_as_written`, `description` (the narrative), `confidence`,
and `source_record_id`.

Places whose name/jurisdiction changed over time (e.g. "Kentucky County, Virginia"
→ "Bourbon County, KY" after 1786) are represented in `place_registry[]` via
`historical_polity` + `valid_from_year`/`valid_to_year` + lat/long — something a
flat events table cannot express. The enum maps 1:1 to GEDCOM tags
(RESI/EMIG/IMMI/CENS/NATU/PROB/WILL/MILI), preserving round-trip.

**Mapping for anyone migrating a `vital_events`-style table:**
`event_type`→`event_type` · `event_date`/`event_year`/`±tol`→`year_min`+`year_max`+`month`+`day`+`date_type` · `event_place`→`place_as_written` · `source_*`→`source_record_id` · `confidence`→`confidence` · `notes`→`description`.

### `bio_summary` — a per-person hover biography (via `extensions`, not a core field)
A short prose biography shown on profile/hover. Stored as **`extensions.bio_summary`**
(string) plus **`extensions.bio_summary_ai_generated`** (boolean — a biography is
narrative, not a sourced assertion, so we mark machine-written ones). Uses the
`extensions{}` open namespace (added v1.3) by design: no schema bump, no Human Gate.
Promote to a first-class `biography_assertions[]` in a future version if it proves out.

### Postgres / portal mirror — migration `002_events_places.sql`
Added additive mirror tables backing the two JSON fields above:
- `person_events` — mirror of `event_assertions[]` (FK → `persons`, `ON DELETE CASCADE`).
- `place_registry` — mirror of `place_registry[]` (historical polity + valid years + lat/long).
- Portal SQLite `persons` gains `bio_summary` + `bio_summary_ai_generated` columns.
JSON MaxPerson remains the source of truth; mirrors exist for JOINs, sorting, and the
portal Life-Story / Migration views.

### Privacy / repo invariant (reaffirmed)
Family-tree **data rows are never committed to the public GitHub repo** — only schemas,
docs, and migration scripts. Living people (`is_living = TRUE` ⇔ `tier2-private`) never
appear in public commits, indexes, or embeddings.

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
