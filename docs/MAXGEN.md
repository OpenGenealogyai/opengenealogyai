# MAXGEN — The Maxwell Genealogy Standard
**Version:** 1.0  
**Author:** Garlon Maxwell  
**License:** CC0 (public domain)  
**Schema URI:** `https://opengenealogyai.org/schemas/maxgen/v1/`

---

## What Is MAXGEN?

MAXGEN is an open JSON standard for representing individual genealogical identities in a way that is **honest about uncertainty**.

Every major genealogy platform today forces researchers to pick one answer. When two records disagree about who someone's father was, one record wins and the other disappears. MAXGEN rejects that model.

In MAXGEN, **every claim is an assertion** — it has a confidence score, a source, and a timestamp. Nothing is ever overwritten. Multiple possible parents can coexist. Conflicting birth years both survive. The uncertainty is the data.

---

## How MAXGEN Differs from GEDCOM

| | GEDCOM | MAXGEN |
|--|--------|--------|
| Format | Custom plaintext (.ged) | JSON (.maxgen) |
| Relationships | Single answer forced | Multiple assertions with confidence scores |
| Uncertainty | Discarded | First-class citizen |
| Source tracing | Optional | Required on every assertion |
| AI-ready | No | Yes — vector-embeddable by design |
| Living persons | No enforcement | `is_living` flag locks record, 404 on API |
| Conflicts | Overwrite | `conflict_flag` preserved |
| Dates | Single value | `year_min`/`year_max` ranges |
| Open | Controlled by GEDCOM Steering Committee | Public domain (CC0) |

---

## The Three MAXGEN Record Types

### 1. `MXPerson` — The Individual
*File: `person.schema.json`*

The core of the standard. Represents a single human identity synthesized from one or more source documents. Every field is an **assertion array** — never a single value.

```json
{
  "person_id": "uuid",
  "schema_version": "1.0",
  "is_living": false,
  "composite_confidence": 0.87,
  "name_assertions": [
    {
      "name_as_written": "William James Whitfield",
      "given_name": "William James",
      "surname": "Whitfield",
      "name_type": "birth",
      "confidence": 0.95,
      "source_record_id": "uuid",
      "asserted_by": "nomic-embed-agent-v1",
      "asserted_at": "2026-05-06T00:00:00Z"
    }
  ],
  "birth_assertions": [...],
  "death_assertions": [...],
  "parent_assertions": [...],
  "spouse_assertions": [...]
}
```

**Key design decisions:**
- `composite_confidence` — overall probability all assertions point to the same real person
- `parent_assertions` — multiple entries are normal; confidence expresses certainty, not conflict
- `conflict_flag` — marks when two assertions for the same role disagree; neither is deleted
- `is_living` — when true, the entire record returns 404 on public endpoints

### 2. `MXRecord` — The Source Document
*File: `raw-record.schema.json`*

Represents a single original historical document exactly as found — birth certificate, census row, newspaper notice, land patent, etc. No interpretation is added at this layer.

Every `MXPerson` assertion traces back to at least one `MXRecord`.

### 3. `MXTask` — The Work Queue Entry
*File: `task-queue.schema.json`*

A unit of distributed work — scraping, OCR extraction, embedding, or verification. Used by the contributor checkout system.

---

## The Confidence Score

Every assertion in MAXGEN carries a `confidence` value from 0.0 to 1.0:

| Score | Meaning |
|-------|---------|
| 0.9 – 1.0 | Field appears verbatim in source, no ambiguity |
| 0.7 – 0.89 | Minor OCR or spelling variation |
| 0.5 – 0.69 | Inferred from context, not stated explicitly |
| 0.3 – 0.49 | Ambiguous or damaged source |
| 0.0 – 0.29 | Best guess only |

Confidence scores are **mandatory and must be honest**. A consistent 0.4 is more valuable than an inflated 0.9.

---

## The Core Principle

> **An assertion with low confidence and a real source is worth more than a certain-looking answer with no source.**

MAXGEN never invents. Every field traces to a document. When the document is unclear, the confidence score says so.

---

## File Extension

MAXGEN files use the `.maxgen` extension for person records:

```
william_whitfield_1842.maxgen
```

Source documents use `.mxrecord`:

```
1880_census_ohio_p42.mxrecord
```

---

## Versioning

This is **MAXGEN v1.0**. The `schema_version` field in every record pins the version at write time, ensuring records remain readable as the standard evolves.

Breaking changes increment the major version. Additive changes increment the minor version.

---

## Why JSON?

- Human-readable and machine-readable
- Natively supported by every modern language
- Vector-embeddable — a MAXGEN record can be fed directly to an embedding model
- GitHub-friendly — diff, review, and merge genealogy records like code
- No proprietary parser required

---

## Relationship to OpenGenealogyAI

MAXGEN is the data standard. OpenGenealogyAI is the platform and database built on top of it. Anyone can implement MAXGEN independently — export from their own software, build their own tools, host their own records.

The standard belongs to everyone. The database is ours to build together.

---

## How to Contribute

The schemas live at:  
`https://github.com/opengenealogyai/opengenealogyai/tree/main/schemas/`

To propose changes: open an issue or pull request. All changes go through the standard review process before being incorporated into a new version.

---

*MAXGEN — The Maxwell Genealogy Standard. Named for Garlon Maxwell, founder of OpenGenealogyAI.*
