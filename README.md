# OpenGenealogyAI

**The first genealogy standard that models uncertainty honestly.**

[![Schema v0.1](https://img.shields.io/badge/Schema-v0.1-2d6a4f)](schemas/raw-record.schema.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-b5873d)](LICENSE)
[![Data: CC0](https://img.shields.io/badge/Public_Data-CC0-1a1a2e)](https://creativecommons.org/publicdomain/zero/1.0/)
[![Tests](https://img.shields.io/badge/Tests-passing-2d6a4f)](#testing)

OpenGenealogyAI is an open-source, AI-native genealogy standard and platform. Every relationship, date, and name carries a confidence score (0.0-1.0) and source attribution. Multiple possible parents are the norm. No fact is ever overwritten — new evidence creates new assertions.

---

## Why This Exists

FamilySearch, Ancestry, and GEDCOM all force you to pick *one* answer. But genealogy is probabilistic. When you find that Abraham Lincoln's grandfather was "probably" Mordecai but you only have a family bible and one census row, the honest answer is `confidence: 0.55` — not a forced merge into a single "correct" person.

OpenGenealogyAI treats uncertainty as a first-class citizen.

**Key differentiator:** Our append-only assertion model means no edit wars. Bad data coexists with good data, labeled by confidence. A researcher can query "show me all assertions below 0.6" and reason about evidence quality.

---

## Schemas (v0.1)

All schemas use JSON Schema 2020-12 with permanent `$id` URLs at `https://opengenealogyai.org/schemas/v0.1/`.

| Schema | Purpose | Validator |
|--------|---------|-----------|
| [RawRecord](schemas/raw-record.schema.json) | Source documents exactly as found | [validate-raw-record.js](schemas/validators/validate-raw-record.js) |
| [Person](schemas/person.schema.json) | Probabilistic identity with confidence-scored assertions | [validate-person.js](schemas/validators/validate-person.js) |
| [TaskQueue](schemas/task-queue.schema.json) | Distributed agent work queue | [validate-task-queue.js](schemas/validators/validate-task-queue.js) |

### Quick Example

```json
{
  "person_id": "P-A3F7B2C1",
  "name_assertions": [
    {
      "name_as_written": "Abraham Lincoln",
      "confidence": 0.82,
      "source_record_id": "va-deed-1786-lincoln",
      "asserted_by": "extractor-haiku-001",
      "asserted_at": "2026-05-05T10:00:00Z"
    }
  ],
  "parent_assertions": [
    {
      "parent_person_id": "P-JOHN-LINCOLN",
      "relationship_type": "biological",
      "parent_role": "father",
      "confidence": 0.75,
      "conflict_flag": false,
      "source_record_id": "va-will-1788-john-lincoln",
      "asserted_by": "extractor-haiku-001",
      "asserted_at": "2026-05-05T10:00:00Z"
    }
  ],
  "redistribution_license": "public-domain",
  "is_living": false,
  "judge_approved": true
}
```

---

## Validate a Record

```bash
npm install
node schemas/validators/validate-raw-record.js path/to/your-record.json
node schemas/validators/validate-person.js path/to/your-person.json

# Validate all fixtures
node schemas/validators/validate-raw-record.js test/fixtures/raw-record/
```

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Confidence score** | 0.0–1.0 on every assertion. 0.0 = no evidence (rejected). Never forced to 1.0. |
| **Assertion model** | Every fact has `source_record_id`, `asserted_by`, `asserted_at`. Append-only. |
| **Tier-1 (open)** | CC0/public-domain records, redistributable, searchable at opengenealogyai.org |
| **Tier-2 (private)** | FamilySearch OAuth records — user-only, never in open dataset |
| **Judge-agent** | Validates all assertions before write. Built before any producer agent. |
| **Conflict protocol** | Two competing parent assertions coexist with `conflict_flag: true` on the lower-confidence one. |
| **Living persons** | `is_living_flag: true` → 404 on all open endpoints. Triple-redundant gate. |

---

## Agent Architecture

Six agents coordinate to build probabilistic family trees from public records:

| Agent | Model | Role |
|-------|-------|------|
| Orchestrator | Sonnet | Dispatches tasks, manages queue, enforces cost caps |
| Extractor | Haiku (parallel) | Fetches and transcribes source records from Internet Archive |
| Validator | Sonnet | Checks schema conformance and source credibility |
| Critic | Sonnet | Reviews evidence quality, catches overconfident assertions |
| Judge | Sonnet | Approves assertions before any write to SQLite/Qdrant |
| Integrator | Sonnet | Commits to SQLite staging.db + Qdrant vector DB |
| Conflict Resolver | Opus | Resolves conflicts with confidence gap < 0.40 |

See [CONFLICT_PROTOCOL.md](docs/CONFLICT_PROTOCOL.md) and [COORDINATION_PROTOCOL.md](docs/COORDINATION_PROTOCOL.md).

---

## Privacy Architecture

- **Living person gate**: Any person with `is_living_flag: true` returns HTTP 404 on open endpoints — not 403 (existence not confirmed)
- **Triple redundancy**: `is_living_flag` on RawRecord + `is_living` on Person + `redistribution_license: tier2-private`
- **FamilySearch data**: Always tier2-private. Never in open Qdrant or public datasets.
- **Audit log**: Every blocked request logged (reason + path only — no protected data)

See [agents/familysearch/privacy_middleware.py](agents/familysearch/privacy_middleware.py).

---

## Vector Search

Names are indexed using a hybrid approach optimized for historical spelling variants (Lincoln/Linkhorn/Lincon):
- Character 3-gram n-grams in 1536-dim vectors (OpenAI text-embedding-3-small)
- Soundex stored as payload for pre-filter
- Jaro-Winkler similarity as tiebreaker

See [VECTOR_DB_ARCHITECTURE.md](docs/architecture/VECTOR_DB_ARCHITECTURE.md).

---

## Testing

```bash
python test/test_ia_fetcher.py       # 23 tests — IA fetcher and RawRecord converter
python test/test_privacy_middleware.py  # 15 tests — living person + tier2 gate
python test/test_tree_builder.py     # 19 tests — genealogy tree builder
python test/test_integration_pipeline.py  # 12 tests — R4 acceptance criteria
python test/test_qdrant_verify.py    # 15 tests — Qdrant architecture verification
python test/test_cost_report.py      # 11 tests — daily cost report + scheduler
python test/test_judge.py            # 10 tests — judge agent (10/10 passing)
python test/test_queue.py            # 6 tests  — queue manager
```

All tests are offline-safe (Qdrant/network tests auto-skip when unavailable).

---

## Data Sources (Tier-1 Open)

- [Internet Archive](https://archive.org) — 22 curated genealogy collections (CC0/public domain)
- US Census pre-1927 — public domain
- User-contributed records under CC-BY-SA 4.0

See [docs/community/adopt-a-collection-tasks.md](docs/community/adopt-a-collection-tasks.md) to help index more collections.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/community/onboarding-guide.md](docs/community/onboarding-guide.md).

Four ways to contribute:
1. **Validate confidence scores** — review AI extractions against source documents (no coding)
2. **Adopt a collection** — index an unclaimed archive collection
3. **Write extraction rules** — add record-type parsing for specialized archives
4. **Fix bugs / add features** — standard open-source contribution

---

## Business Model

| Tier | Price | What You Get |
|------|-------|-------------|
| Free | $0 | Browse all public probabilistic trees, download JSON, search 10M+ records |
| Research | $9/mo | AI auto-builds 3+ ancestral generations in 30 min, private doc uploads, GEDCOM export |

The data is CC0 forever. You pay for agent labor, not data access.

---

## License

[MIT](LICENSE) — schemas and tooling.
Data licensing varies by record — see `redistribution_license` field on each record.
