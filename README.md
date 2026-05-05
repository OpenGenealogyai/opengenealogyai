# OpenGenealogyAI

**The first genealogy standard that models uncertainty honestly.**

OpenGenealogyAI is an open-source, AI-native genealogy standard and platform. Every relationship, date, and name carries a confidence score (0.0-1.0) and source attribution. Multiple possible parents are the norm. No fact is ever overwritten - new evidence creates new assertions.

## Why This Exists

FamilySearch, Ancestry, and GEDCOM all force you to pick *one* answer. But genealogy is probabilistic. When you find Abraham Lincoln's grandfather was "probably" Mordecai but you only have a family bible and one census row, the honest answer is `confidence: 0.55` - not a forced merge into a single "correct" person.

OpenGenealogyAI treats uncertainty as a first-class citizen.

## Schemas (v0.1)

| Schema | Purpose | Spec |
|--------|---------|------|
| [RawRecord](schemas/raw-record.schema.json) | Source documents, exactly as found | [AJV validator](schemas/validators/validate-raw-record.js) |
| [Person](schemas/person.schema.json) | Probabilistic identity with confidence-scored assertions | [AJV validator](schemas/validators/validate-person.js) |
| [TaskQueue](schemas/task-queue.schema.json) | Distributed agent work queue | [AJV validator](schemas/validators/validate-task-queue.js) |

All schemas use JSON Schema 2020-12 with permanent `$id` URLs.

## Validate a Record

```bash
npm install
node schemas/validators/validate-raw-record.js path/to/your-record.json
node schemas/validators/validate-person.js path/to/your-person.json
```

## Key Concepts

- **Confidence score**: 0.0-1.0 on every assertion. Never forced to 1.0.
- **Assertion model**: Every fact has `source_record_id`, `asserted_by`, `asserted_at`. Nothing is overwritten.
- **Tier-1 (open)**: CC0/public-domain records, redistributable, searchable.
- **Tier-2 (private)**: FamilySearch OAuth, user-only, never in the open dataset.
- **Judge-agent**: Validates all assertions before they enter the system. Built before any producer agent.
- **Conflict protocol**: Two competing parent assertions coexist with `conflict_flag: true` on the lower-confidence one.

## Agent Architecture

Six agents coordinate to build probabilistic family trees from public records:

| Agent | Model | Role |
|-------|-------|------|
| Orchestrator | Sonnet | Dispatches tasks, manages queue |
| Extractor | Haiku (parallel) | Fetches and transcribes source records |
| Validator | Sonnet | Checks schema conformance |
| Critic | Sonnet | Reviews evidence quality |
| Judge | Sonnet | Approves assertions before write |
| Integrator | Sonnet | Commits to SQLite + Qdrant |
| Conflict Resolver | Opus | Resolves low-confidence conflicts |

See [CONFLICT_PROTOCOL.md](docs/CONFLICT_PROTOCOL.md) for how conflicts are handled.

## Data Sources (Tier-1)

- [Internet Archive](https://archive.org) - millions of public-domain genealogy records
- [Wikidata](https://wikidata.org) - CC0
- US Census pre-1927 - public domain
- User-contributed records under CC-BY-SA 4.0

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) - schemas and tooling.  
Data licensing varies by record - see `redistribution_license` field.
