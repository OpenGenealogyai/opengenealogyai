# MAXGEN Schemas — Reference

The Maxwell Genealogy Standard is defined by four machine-readable JSON schemas.
Everything in OpenGenealogyAI is built on these four files.

| Schema | File | What it represents | License |
|---|---|---|---|
| **MaxRecord** | `schemas/raw-record.schema.json` | A single original source document, exactly as found | per-record (CC0 / CC-BY / CC-BY-SA / public-domain / tier2-private) |
| **MaxPerson** | `schemas/person.schema.json` | A probabilistic individual identity synthesized from one or more MaxRecords | inherits from sources |
| **MaxTask** | `schemas/task-queue.schema.json` | A unit of distributed work for contributor agents | n/a (internal) |
| **MaxDNA** | `schemas/dna.schema.json` | DNA test metadata and match assertions linked to a MaxPerson | **always tier2-private** |

**Standard version:** MAXGEN v1.2
**Schema namespace:** `https://opengenealogyai.org/schemas/maxgen/v1/`
**Author:** Garlon Maxwell
**License of the standard itself:** CC0 (public domain)

---

## Why four schemas, not one

Every other genealogy format crams sources, people, and uncertainty into a single
table and forces "one true answer." MAXGEN deliberately separates them so that
**evidence (MaxRecord)** and **interpretation (MaxPerson)** can disagree, evolve
independently, and stay traceable.

```
                  MaxRecord
                  (a document)
                      │
                      │  cited_by
                      ▼
                  MaxPerson  ◄────── MaxDNA
                  (a person)         (DNA test linked to that person)
                      │
                      │  triggers
                      ▼
                  MaxTask
                  (work to extract / verify / re-embed)
```

The arrows are foreign keys. Every assertion in MaxPerson has at least one
`source_record_id` pointing at a real MaxRecord. Every MaxDNA points at the
MaxPerson it belongs to.

---

## MaxRecord — what was found, exactly

A MaxRecord is **one original source document** captured exactly as it appears.
No interpretation. No "we think this means X." Just the document.

**Required fields:** `record_id`, `record_type`, `redistribution_license`,
`source_url`, `extraction_confidence`, `is_living_flag`

**Record types** (24 enumerated): birth/death/marriage certificates, census rows,
parish registers, probate records, military records, immigration records,
naturalization records, land deeds, land patents, gravestones, obituaries,
newspaper articles, photographs, family bibles, court records, tax records,
Wikidata entities, OpenLibrary works, DPLA items, and `other`.

**License values:** `CC0`, `CC-BY`, `CC-BY-SA`, `public-domain`, `tier2-private`.
Anything tier2-private never appears on open endpoints.

**Living-person rule:** `is_living_flag: true` forces 404 on every public endpoint
regardless of license. No exceptions.

---

## MaxPerson — what we think the document means

A MaxPerson is a **probabilistic identity** built from one or more MaxRecords.
No assertion is ever overwritten. When new evidence arrives, it becomes a new
assertion with its own confidence score; the old one stays.

**The key design choice:** every claim about a person — their name, birth year,
parents, spouse, occupation — is stored as an **array of assertions**. Not one
parent, but a list of `parent_assertions[]` each with a confidence score, a
source, and a timestamp.

```json
"father_assertions": [
  { "father_person_id": "...john-maxwell...",   "confidence": 0.6, "source_record_id": "..." },
  { "father_person_id": "...robert-maxwell...", "confidence": 0.4, "source_record_id": "..." }
]
```

Both fathers survive. The viewer shows both. Downstream tools (search, DNA
confidence boost, family-tree rendering) can use whichever interpretation they
need. Future evidence may shift the confidence — it never erases the older claim.

**Other assertion arrays:** `name_assertions`, `birth_assertions`,
`death_assertions`, `mother_assertions`, `child_assertions`,
`spouse_assertions`, `occupation_assertions`.

**External cross-refs:** `external_ids` is a flexible map for linking to
Wikidata QIDs, FamilySearch PIDs, FindAGrave IDs, WikiTree IDs, etc.

---

## MaxTask — distributed work coordination

When a MaxRecord arrives that needs extraction, or a MaxPerson assertion needs
verification, or a batch of records needs embedding — a MaxTask is created.

Worker agents pull tasks, run them, and write results back. MaxTask is the
internal coordination layer that lets contributors run their own agent workers
against the open standard.

Not user-facing. Documented for agent developers in `agents/definitions/*.md`.

---

## MaxDNA — DNA evidence linked to people

The newest schema. Stores DNA test metadata and match assertions in a way that
serves **genealogical research**, not "find your living cousin."

**The frame:** if two living people share DNA, then their family trees converged
on a common ancestor — and that ancestor's identity can be constrained by
combining both trees. DNA becomes lateral evidence that boosts or generates
ancestor assertions in MaxPerson.

**Four hard safety constants** (locked in the schema, not optional):

| Field | Locked to | Reason |
|---|---|---|
| `redistribution_license` | `"tier2-private"` | DNA implicates relatives who didn't consent |
| `raw_genotype_stored` | `false` | We never host raw FASTQ/VCF files |
| `kit_id_hash` | SHA-256 only | Kit numbers never stored in clear |
| `external_ids.*` | SHA-256 only | Cross-service aliases hashed too |

**Five logical sections** of a MaxDNA record:

1. **Identity** — `person_id` links to MaxPerson; test type and provider
2. **Haplogroups** — Y-DNA and mtDNA (paternal/maternal lines, deep ancestry)
3. **Ancestry composition** — admixture percentages by region
4. **Matches[]** — DNA matches with other kits, including chromosome segments
   for triangulation and inferred relationships
5. **Consent & legal** — 6-value consent enum, withdrawal tracking, evidence URL

**Detailed storage and search plan:** see [`docs/DNA_ARCHITECTURE.md`](DNA_ARCHITECTURE.md).

---

## Validation

```bash
npx ajv-cli validate -s schemas/raw-record.schema.json   -d test/fixtures/raw-record/*.json
npx ajv-cli validate -s schemas/person.schema.json       -d test/fixtures/person/*.json
npx ajv-cli validate -s schemas/task-queue.schema.json   -d test/fixtures/task-queue/*.json
npx ajv-cli validate -s schemas/dna.schema.json          -d test/fixtures/dna/*.json
```

All four schemas validate against JSON Schema Draft 2020-12.

---

## Schema IDs are permanent

The `$id` URL on each schema is a stable identifier. Once published, it never
changes. Schema upgrades (v1.2, v1.3, …) bump the `schema_version` field inside
each record but keep the same URL.

- `https://opengenealogyai.org/schemas/maxgen/v1/raw-record.schema.json`
- `https://opengenealogyai.org/schemas/maxgen/v1/person.schema.json`
- `https://opengenealogyai.org/schemas/maxgen/v1/task-queue.schema.json`
- `https://opengenealogyai.org/schemas/maxgen/v1/dna.schema.json`

Breaking changes require a Human Gate (HG-6) approval and a new major version.

---

## Versioning

| Version | Schemas | Notes |
|---|---|---|
| v1.0 | MaxRecord, MaxPerson, MaxTask | Initial release |
| v1.1 | (all three) | Added `child_assertions`, `occupation_assertions`, `external_ids` to MaxPerson; added `land_patent`, `wikidata_entity`, `open_library_work`, `dpla_item` to MaxRecord types |
| v1.2 | + MaxDNA | New schema. MaxPerson gains `dna_evidence[]` array for tracking DNA chains that touch a person. MaxDNA matches carry `cm_map_version` (HapMap/deCODE/AABB) and `phasing_status` (maternal/paternal) for cross-provider reconciliation. `common_ancestor_candidates[]` replaces the singular field — real DNA matches often have multiple plausible MRCAs and we don't force one answer. Kit ID hashing uses HMAC-SHA-256 with system salt, not plain SHA-256 (six-brain review 2026-05-15). |

---

## How to contribute changes

1. Open an issue describing the field you want to add or change
2. Justify the change against the **uncertainty-as-data** philosophy
3. Provide at least one realistic fixture that exercises the new field
4. Bump `schema_version` and update this README
5. Submit PR — review goes through the schema maintainers and one Human Gate

The schemas are the foundation of the entire stack. They get changed slowly,
deliberately, and with public review.
