# Schemas — OpenGenealogyAI

This directory contains the three machine-readable JSON schemas that define the standard.

## Schemas

| File | Description | Version |
|------|-------------|---------|
| `raw-record.schema.json` | A single original source document | v0.1 |
| `person.schema.json` | A probabilistic identity record | v0.1 |
| `task-queue.schema.json` | A distributed work queue task | v0.1 |

## Validation

```bash
npx ajv-cli validate -s schemas/raw-record.schema.json -d test/fixtures/raw-record-sample.json
npx ajv-cli validate -s schemas/person.schema.json -d test/fixtures/person-sample.json
npx ajv-cli validate -s schemas/task-queue.schema.json -d test/fixtures/task-queue-sample.json
```

## Schema IDs

Schema $id URLs are permanent once published. Do not change them without human gate HG-6 approval.

- `https://opengenealogyai.org/schemas/v0.1/raw-record.schema.json`
- `https://opengenealogyai.org/schemas/v0.1/person.schema.json`
- `https://opengenealogyai.org/schemas/v0.1/task-queue.schema.json`
