# MaxDNA — Storage, Search & Use Architecture

**Status:** Planning. Schema is drafted (`schemas/dna.schema.json`). Collection
has not begun. This document is the contract for how MaxDNA will be stored,
queried, and used to strengthen ancestor assertions.

**Audience:** Contributors implementing the DNA pipeline. Read the schema first,
then this.

---

## The premise

OpenGenealogyAI's DNA layer is not designed for the same job as 23andMe,
Ancestry, or MyHeritage. Those services optimize for **"find your living
cousin."** We optimize for the opposite question:

> **If two living people share DNA, what does that tell us about their dead
> ancestors 200 years ago?**

Shared DNA between living people is **lateral evidence for historical
assertions**. A 50cM match between two Maxwell-line descendants is not a social
discovery — it's a probabilistic constraint on who their shared great-great-
grandparent was. Combined with both family trees, it narrows the search space
for unknown ancestors and updates the confidence of known ones.

---

## Why DNA does NOT go into a vector database

DNA records are mostly numeric and structured. Vector embeddings (the
`nomic-embed-text` model that powers people-search) work because names and
places have **semantic similarity** — "William" embeds close to "Will" and "Wm"
because the model has seen all three in similar contexts. That logic does not
extend to:

| DNA data | Why embedding fails |
|---|---|
| `shared_cm: 850` | A text embedder sees "850" the same as "850 dollars" or "850 miles." It has no concept of centimorgans. |
| `chromosome: 7, start_cm: 45, end_cm: 62` | Range data. Needs B-tree or GiST indexes. Cosine similarity is meaningless here. |
| `haplogroup_y: R-M269` | Hierarchical tree (R → R-M269 → R-L21 → R-DF13). Needs tree-aware indexes (Postgres `ltree`). |
| `match_kit_hash: abc123...` | A SHA-256 hash. By design, has zero semantic structure. |

Forcing structured numeric data through a text-embedding model produces results
that look like search but are 30% the precision of a proper index. **Use the
right tool.**

---

## Storage: Postgres for everything structural

Five tables in Postgres. All foreign-keyed to `person_id` (the MaxPerson UUID)
so DNA evidence joins cleanly with the rest of the standard.

### `dna_kits` — one row per DNA test
```
dna_id (PK)             person_id (FK MaxPerson)    test_type
kit_id_hash (UNIQUE)    test_provider                consent_status
haplogroup_y            haplogroup_mt                endogamy_flag
endogamy_population     asserted_at                  ...

INDEX: person_id
INDEX: kit_id_hash
INDEX: haplogroup_y, haplogroup_mt
```

### `dna_matches` — one row per match between two kits
```
match_id (PK)             kit_a_hash             kit_b_hash
shared_cm                 longest_segment_cm     segment_count
inferred_relationship     match_source           asserted_at

INDEX: (kit_a_hash, shared_cm DESC)
INDEX: (kit_b_hash, shared_cm DESC)
INDEX: shared_cm        ← range queries
```

### `dna_segments` — one row per shared chromosomal segment
```
segment_id (PK)         match_id (FK)          chromosome
start_cm                end_cm                 snp_count
start_position          end_position           build_version

INDEX: GiST (chromosome, [start_cm, end_cm])    ← range/overlap queries
INDEX: match_id
```

### `dna_evidence_chains` — derived: DNA evidence supporting a specific MaxPerson
```
chain_id (PK)              mrca_person_id (FK MaxPerson)
kit_a_hash                 kit_b_hash               shared_cm
path_length_generations    likelihood               confidence_delta
created_at

INDEX: mrca_person_id   ← "show me all DNA evidence supporting John Maxwell"
```

This is the join table that makes DNA evidence visible in MaxPerson views.
The chain-inference worker writes here.

### `haplogroup_tree` — Y-DNA and mtDNA reference tree
```
haplogroup (PK)         parent_haplogroup       ltree_path
                                                e.g. R.M269.L21.DF13

INDEX: GiST ltree_path  ← "all descendants of haplogroup R-M269"
```

Populated once from ISOGG / YFull public trees, refreshed quarterly.

---

## Search: Qdrant gets exactly one DNA collection

There is one DNA query where vector similarity is the right answer: matching
people by **ethnic admixture profile**. Everything else stays in Postgres.

### `admixture_v` (Qdrant collection)
```
point_id   = dna_id
vector     = 25-dim float (Irish, German, English, Italian, Polish, ...)
payload    = { person_id, kit_id_hash, person_name, top_3_regions }
```

**Use:** "Find people with similar ethnic background." ~50ms across millions of
kits.

**Skip:** every other DNA query. Use Postgres.

The existing `people` collection (current people-search vector index, ~1.5M
points) is untouched by DNA. People search keeps working exactly as it does.

---

## The six queries the system must answer fast

| # | Query | Where | Index | Speed |
|---|---|---|---|---|
| 1 | All matches >50cM with this kit | Postgres | `dna_matches(kit_a_hash, shared_cm)` | <5ms |
| 2 | Kits sharing chromosome 7 between 45–62cM | Postgres | GiST on `dna_segments` | <20ms |
| 3 | All DNA evidence supporting John Maxwell | Postgres | `dna_evidence_chains.mrca_person_id` | <5ms |
| 4 | Y-DNA descendants of haplogroup R-M269 | Postgres | ltree GiST | <10ms |
| 5 | People with similar ethnic mix | Qdrant | cosine on 25-d | <50ms |
| 6 | "Find Maxwells in Kentucky 1810" (existing) | Qdrant | existing 768-d people index | <200ms |

---

## The write pipeline (when DNA data arrives)

```
Raw DNA metadata arrives (WikiTree API, OpenSNP, user upload)
            │
            ▼
    ┌───────────────────────┐
    │ 1. Hash kit_id         │
    │ 2. Validate consent    │
    │ 3. Lock license tier2  │
    └──────────┬─────────────┘
               │
               ▼
    Insert: dna_kits, dna_matches, dna_segments
               │
               ▼
    Compute 25-d admixture vector  →  Qdrant admixture_v
               │
               ▼
    Chain inference worker:
       For each match pair:
         - Walk both MaxPerson trees to expected depth
         - Find MRCA candidates by fuzzy match
         - Compute P(observed_cm | tree_path_length)
         - Write row to dna_evidence_chains
               │
               ▼
    MaxPerson confidence recompute:
       For each assertion in MaxPerson:
         - Read dna_evidence_chains where mrca_person_id = this person
         - Apply noisy-OR aggregation
         - Update assertion confidence
```

---

## The read pipeline (when a user views Richard Maxwell)

```
GET /person/{richard-maxwell-id}
            │
            ├─► Postgres: persons WHERE person_id = ...
            │
            ├─► Postgres: persons WHERE id IN richard.father_assertions
            │
            ├─► Postgres: dna_evidence_chains WHERE mrca_person_id IN candidates
            │      │
            │      └─► Noisy-OR aggregate per father candidate
            │
            └─► Render:
                   Father: John Maxwell   0.91   ← 1 census + 3 DNA chains
                          Robert Maxwell  0.09   ← 1 marriage doc, no DNA
```

---

## How DNA strengthens MaxPerson confidence

### Two distinct use cases

**Confirmatory** — strengthen an existing assertion.
Example: "John is Richard's father" already has documentary confidence 0.6.
Three independent living-person DNA chains pass cleanly through John (their
shared cM matches the expected range for the path length through John).
Each chain adds a small Bayesian boost. Confidence climbs to 0.85.

**Generative** — propose new candidate ancestors when current ones are unknown.
Example: Richard Maxwell's father is unknown. A 50cM DNA match arrives whose
documented tree includes Samuel Maxwell (1750). 50cM ≈ 4th cousin ≈ shared
3rd-great-grandparent. Samuel's sons (born ~1775-1795) are the right generation
to be Richard's father. The system proposes them as candidates at low
confidence (0.3) pending document verification.

### The math (noisy-OR over independent chains)

For one assertion `R` (e.g. "John is Richard's father"):

```
prior(R)            = 0.6   (from documents)
DNA chains          = [boost 0.08, boost 0.06, boost 0.04]

posterior(R) = 1 − (1 − prior) × ∏(1 − boost_i)
            = 1 − (0.4) × (0.92 × 0.94 × 0.96)
            = 0.67
```

Each independent DNA pair behaves as a separate witness. More chains, more
evidence, diminishing returns. Three chains take confidence from 0.6 to ~0.85;
a tenth chain barely moves the number.

### Where the math breaks (and what to do about it)

| Failure mode | What happens | Mitigation |
|---|---|---|
| **Endogamy** (Acadian, Ashkenazi, Mennonite, etc.) | Everyone in the founding population shares ~50cM with everyone else | `dna_kits.endogamy_flag` set; require 3+ independent triangulations before any boost is applied |
| **NPE** (non-paternity event) | Surname says Maxwell, Y-DNA disagrees | Cross-check Y-DNA haplogroup against the surname project before boosting paternal-line assertions |
| **Adoption / illegitimacy** | Documented tree doesn't match biological reality | Same — Y-DNA cross-check exposes the disconnect |
| **False matches** | Algorithmic noise at <7cM | Discard segments under 7cM from chain inference |
| **Wrong tree on one side** | Living person's tree has errors 5 generations back | Score tree quality (source counts, doc citations) alongside cM in likelihood computation |

---

## Generational reach of DNA evidence

DNA only helps for ancestors within roughly 7 generations of a living tester:

| Generation | Relationship | Typical shared cM |
|---|---|---|
| 2 | 1st cousin | 553–1225 |
| 3 | 2nd cousin | 41–592 |
| 4 | 3rd cousin | 0–217 |
| 5 | 4th cousin | 0–117 |
| 6 | 5th cousin | 0–46 |
| 7 | 6th cousin | 0–22 (often zero) |
| 8+ | 7th cousin+ | almost always zero |

**Window of usefulness:** ancestors born approximately **1750–1925**. Beyond
that, autosomal DNA washes out and only Y-DNA / mtDNA can reach deeper (with
much less precision — they trace single lines, not whole pedigrees).

---

## Privacy — non-negotiable rules

These are baked into the schema and the API. None can be turned off.

1. **No raw genotype data is ever stored.** Not in the database, not on disk,
   not in cache. Raw FASTQ, VCF, 23andMe raw export — stays with the user or
   the test provider. MaxDNA stores derived metadata only.
2. **Kit IDs are HMAC-SHA-256 hashed before storage.** The schema's regex
   enforces 64-hex-character format. The hash function is HMAC-SHA-256 with a
   **system-wide salt held in a secrets vault**, not plain SHA-256. This matters
   because vendor kit number spaces are small enough to brute-force (AncestryDNA
   kit numbers are ~12 digits ≈ 10^12 → seconds on a GPU against plain SHA-256).
   HMAC with a secret salt closes that attack. The same salt is used for
   `external_ids.*` cross-service alias hashes. Salt rotation requires
   re-hashing all stored kit IDs; treat as a major operational event.
3. **All DNA records are `tier2-private`.** The schema locks
   `redistribution_license` to that exact value. No CC0 path for DNA. Ever.
4. **Living-subject lock.** If `is_living_flag` is true, all open endpoints
   return 404. Access requires authenticated, consented access by the subject.
   **Default policy for the flag** (applied at ingest time, not stored as
   schema default — the flag is required and must be explicit):
   - If subject's linked MaxPerson has `birth_year_max ≥ (current_year − 100)`
     AND no death record exists in MaxPerson `death_assertions` → ingest agent
     MUST set `is_living_flag: true`.
   - Manual override requires documented evidence of death (obituary, death
     certificate, gravestone with date) attached as a MaxRecord source.
5. **Explicit consent required.** `consent_status` must be one of:
   `subject_explicit_opt_in`, `guardian_consent`, `public_dataset_redistribution_allowed`,
   or `deceased_pre_2000`. Anything else (`pending`, `withdrawn`) blocks reads.
6. **Withdrawal triggers a 30-day cascade purge.** Setting
   `withdrawal_requested_at` starts a clock; after 30 days the DNA record and
   all derived `dna_evidence_chains` rows referencing it are deleted, and any
   confidence boosts applied to MaxPerson assertions are recomputed without
   the withdrawn evidence.

---

## Phased rollout

| Phase | What | Status | Notes |
|---|---|---|---|
| 0 | MaxDNA schema | ✅ Done | `schemas/dna.schema.json` |
| 0 | Postgres DDL | Not started | `dna_kits`, `dna_matches`, `dna_segments`, `dna_evidence_chains`, `haplogroup_tree` |
| 1 | WikiTree DNA license check | Blocking | Verify their API permits redistribution of DNA-connection metadata |
| 1 | Consent flow + opt-in UI | Not started | Subject explicit opt-in required before any storage |
| 2 | Confirmatory engine | Not started | DNA boosts existing MaxPerson assertions only; small confidence deltas |
| 3 | Generative engine | Not started | Propose new candidate ancestors; clearly badged as DNA-hypothesis |
| 4 | Y-DNA / mtDNA deep-time matching | Future | Surname project integration, paternal/maternal line tracing >200 years |

Each phase is a Human Gate. No phase begins until the previous one has been
validated in production with real data.

---

## What makes this approach different

Every other DNA service forces a single answer to "who is your father?" — and
hides whatever uncertainty exists. OpenGenealogyAI answers:

> Based on documentary evidence, your father is **John (0.60)** or **Robert
> (0.40)**. Based on 3 DNA chains, John explains the observed cM at likelihood
> 0.85 and Robert at 0.12. Updated posterior: **John 0.91, Robert 0.09**.

Probability all the way through. DNA is one source of evidence among many.
The standard is honest about what it knows and what it doesn't.
