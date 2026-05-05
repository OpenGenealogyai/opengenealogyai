# Contributing to OpenGenealogyAI

OpenGenealogyAI is an open standard. The most valuable contributions are:

1. **Schema improvements** - Issues and PRs on the JSON schemas
2. **Record fixtures** - Real public-domain genealogy records in RawRecord format
3. **Validator improvements** - Better error messages, edge case coverage
4. **Agent definitions** - New extractor agents for new source types

## Getting Started

```bash
git clone https://github.com/garlonmaxwell-stack/opengenealogyai
cd opengenealogyai
npm install
node schemas/validators/validate-raw-record.js test/fixtures/raw-record/
```

## Submitting a Record Fixture

1. Create a valid RawRecord JSON file (see [schemas/raw-record.schema.json](schemas/raw-record.schema.json))
2. Validate it: `node schemas/validators/validate-raw-record.js your-record.json`
3. Place it in `test/fixtures/raw-record/` with a descriptive name
4. Open a PR

**Requirements for fixtures:**
- Must be Tier-1 (CC0, public-domain, or CC-BY) - no Tier-2 data in this repo
- Must have `is_living_flag: false` unless explicitly testing that case
- Must include a real `source_url` pointing to an actual archive

## Schema Changes

Schema changes require:
- Updated validator
- At least 3 new fixtures exercising the new field
- Bump to `schema_version` (minor version for additive, major for breaking)

Permanent `$id` URLs (`https://opengenealogyai.org/schemas/v0.1/...`) are immutable once published. Breaking changes get a new version path.

## Code of Conduct

Be kind. This is genealogy - people are researching real families, including their own.
