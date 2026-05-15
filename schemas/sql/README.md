# Postgres DDL — `schemas/sql/`

Numbered SQL migrations for the OpenGenealogyAI Postgres layer. Each file is
idempotent within its own scope and tracked in the `schema_migrations` table.

| File | What | Status |
|---|---|---|
| `001_init.sql` | persons mirror + 5 DNA tables + haplogroup_tree + 11 enum types + GiST/ltree extensions | Drafted (not executed) |

## Six-Brain approval

Architecture approved 2026-05-15 12:55. Pass-1 verdicts split (PROCEED /
PROCEED WITH CAUTION / DO NOT PROCEED). Pass-2 adversarial round converged on
**PROCEED WITH CAUTION** with the following amendments, all reflected in
`001_init.sql`:

1. **Six tables, not five** — added `persons` mirror so `dna_kits.person_id`
   has a real FK target (Strategist amendment, Engineer concurred in Pass 2)
2. **HMAC-SHA-256 with system salt** for `kit_id_hash`, documented in
   `docs/DNA_ARCHITECTURE.md`. Schema regex unchanged (still `[a-f0-9]{64}`).
3. **`raw_genotype_stored` locked to FALSE** via CHECK constraint
4. **`redistribution_license` locked to `tier2-private`** on `dna_kits` via
   CHECK constraint
5. **No alembic** — numbered SQL migrations are sufficient at this scale
6. **No row-level security** in 001 — schema is designed so RLS can be added
   later without migration

## Three operator gates before any collection starts

These gates do NOT block writing or even executing this DDL. They block the
first INSERT into `dna_kits`:

| Gate | Verified by | How |
|---|---|---|
| Encryption at rest | OS / disk | BitLocker on data volume; verify with `manage-bde -status` |
| Backup pipeline | Operations | `pg_dump → GPG → Backblaze B2` rehearsed with dummy data; recovery tested |
| Localhost-only | `postgresql.conf` | `listen_addresses = 'localhost'` and `pg_hba.conf` rejects non-local |

## Execution

This DDL has NOT been executed. Execution is CLI-tier per
`council-protocol/SKILL.md` and requires explicit Garlon approval as a
separate step. When approved:

```bash
# Create database (one-time)
createdb -O opengenealogyai_app opengenealogyai

# Run migration
psql -d opengenealogyai -f schemas/sql/001_init.sql

# Verify
psql -d opengenealogyai -c "SELECT version, applied_at FROM schema_migrations;"
```

## Adding new migrations

```
schemas/sql/
├── 001_init.sql          ← creates everything above
├── 002_*.sql             ← future
├── ...
```

Each new migration inserts its own row into `schema_migrations` so re-running
is safe. Migrations are forward-only — to roll back, write `003_revert_002.sql`.

## What's NOT in this layer

- **MaxPerson source-of-truth.** The JSON files / Qdrant payload remain
  authoritative for the full assertion arrays. `persons` is a denormalized
  mirror with top-confidence values only, kept in sync by the MaxPerson ingest
  pipeline.
- **MaxRecord storage.** Source documents live in their existing storage
  (Internet Archive, repo JSON files). Postgres only references them by UUID
  in `dna_kits.source_records[]`.
- **Embedding vectors.** Qdrant holds the people-search and admixture vectors.
  Postgres holds the structural data. They are separate stores by design.
- **App-level cascade logic.** The 30-day withdrawal cascade is intentionally
  NOT a database trigger — it runs as a scheduled app job so the
  noisy-OR confidence recomputation can be properly logged.
