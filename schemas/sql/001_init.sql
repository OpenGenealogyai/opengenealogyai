-- ============================================================================
-- MAXGEN v1.2 — Postgres DDL — Migration 001 (initial)
-- ============================================================================
-- Author:        OpenGenealogyAI
-- Date:          2026-05-15
-- Six-brain:     Approved 2026-05-15 12:55 (passes 1+2 converged on PROCEED
--                WITH CAUTION; this DDL reflects the consensus amendments)
-- Schema URLs:   https://opengenealogyai.org/schemas/maxgen/v1/
--
-- This migration creates the persons mirror, the four DNA tables, and the
-- haplogroup reference tree. It does NOT load data. Execution of this file
-- requires explicit Garlon approval per the CLI-tier policy.
--
-- Three operator gates MUST be verified BEFORE any data is inserted:
--   1. Volume encryption at rest is enabled and verified
--   2. pg_dump → GPG → off-site backup pipeline is tested with dummy data
--   3. postgresql.conf has listen_addresses = 'localhost' (no exposed port)
--
-- Run with:  psql -d opengenealogyai -f schemas/sql/001_init.sql
-- ============================================================================

\set ON_ERROR_STOP on
BEGIN;

-- ----------------------------------------------------------------------------
-- Extensions
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- HMAC-SHA-256 for kit_id hashing
CREATE EXTENSION IF NOT EXISTS ltree;        -- Haplogroup tree (R.M269.L21...)
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- GiST on (chromosome, cm_range)

-- ----------------------------------------------------------------------------
-- Enum types (mirror the JSON Schema enums; CHECK constraints enforce locks)
-- ----------------------------------------------------------------------------
CREATE TYPE license_tier AS ENUM (
    'CC0', 'CC-BY', 'CC-BY-SA', 'public-domain', 'tier2-private'
);

CREATE TYPE dna_test_type AS ENUM (
    'autosomal', 'y_dna', 'mt_dna', 'x_dna', 'whole_genome', 'combined'
);

CREATE TYPE dna_test_provider AS ENUM (
    '23andme', 'ancestrydna', 'ftdna', 'myheritage',
    'livingdna', 'tellmegen', 'nebula', 'dante_labs',
    'gedmatch_upload', 'wikitree_linked', 'opensnp', 'yfull',
    'academic_research', 'other'
);

CREATE TYPE consent_state AS ENUM (
    'subject_explicit_opt_in',
    'guardian_consent',
    'public_dataset_redistribution_allowed',
    'deceased_pre_2000',
    'withdrawn',
    'pending'
);

CREATE TYPE relationship_inferred AS ENUM (
    'identical_twin', 'parent_child', 'full_sibling',
    'half_sibling', 'grandparent', 'aunt_uncle',
    'first_cousin', 'first_cousin_once_removed',
    'second_cousin', 'second_cousin_once_removed',
    'third_cousin', 'fourth_cousin', 'fifth_or_more_distant',
    'endogamous_unclear', 'unknown'
);

CREATE TYPE cm_map AS ENUM (
    'hapmap', 'decode', 'aabb', 'shapeit4', 'unknown'
);

CREATE TYPE phasing AS ENUM (
    'maternal', 'paternal', 'both', 'unphased', 'unknown'
);

CREATE TYPE chromosome_id AS ENUM (
    '1','2','3','4','5','6','7','8','9','10','11','12',
    '13','14','15','16','17','18','19','20','21','22',
    'X','Y','MT'
);

CREATE TYPE build_id AS ENUM ('GRCh37', 'GRCh38');

CREATE TYPE match_source_origin AS ENUM (
    '23andme', 'ancestrydna', 'ftdna', 'myheritage',
    'gedmatch', 'wikitree_dna_connections', 'user_uploaded', 'other'
);

-- ============================================================================
-- TABLE 1 — persons (mirror of MaxPerson)
-- ----------------------------------------------------------------------------
-- The authoritative MaxPerson record remains the JSON / Qdrant payload. This
-- table is a denormalized mirror that exists ONLY to make Postgres-side JOINs
-- (DNA ↔ person) cheap. Sync from MaxPerson source-of-truth on every upsert.
--
-- Per six-brain Strategist + Engineer Pass-2 agreement: this mirror is
-- required, otherwise dna_kits.person_id is a dangling UUID and we lose the
-- entire "Postgres for joins" premise of this architecture.
-- ============================================================================
CREATE TABLE persons (
    person_id           UUID PRIMARY KEY,
    -- Denormalized display fields (top-confidence assertion only; full
    -- assertion arrays live in the JSON source of truth)
    display_name        TEXT,
    surname             TEXT,
    given_names         TEXT,
    birth_year_min      INTEGER CHECK (birth_year_min IS NULL OR birth_year_min BETWEEN 1000 AND 2100),
    birth_year_max      INTEGER CHECK (birth_year_max IS NULL OR birth_year_max BETWEEN 1000 AND 2100),
    death_year_min      INTEGER,
    death_year_max      INTEGER,
    birth_place         TEXT,
    death_place         TEXT,
    -- Policy fields
    is_living_flag      BOOLEAN NOT NULL DEFAULT FALSE,
    redistribution_license license_tier NOT NULL DEFAULT 'CC0',
    -- Provenance
    source_uri          TEXT,        -- where the JSON MaxPerson is canonically stored
    asserted_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- The is_living default policy (per DNA_ARCHITECTURE.md) is enforced at
    -- ingest time, not as a DB default — because we need MaxPerson birth/death
    -- data to compute it. The ingest agent MUST set this correctly.
    CONSTRAINT chk_birth_year_order CHECK (birth_year_min IS NULL OR birth_year_max IS NULL OR birth_year_min <= birth_year_max)
);

CREATE INDEX idx_persons_surname     ON persons (lower(surname));
CREATE INDEX idx_persons_birth_year  ON persons (birth_year_min, birth_year_max);
CREATE INDEX idx_persons_is_living   ON persons (is_living_flag) WHERE is_living_flag = TRUE;

COMMENT ON TABLE persons IS
    'Mirror of MaxPerson JSON records. Used for FK targets and JOINs only; the JSON file is the source of truth for the full assertion arrays.';

-- ============================================================================
-- TABLE 2 — dna_kits  (one row per DNA test)
-- ============================================================================
CREATE TABLE dna_kits (
    dna_id                  UUID PRIMARY KEY,
    schema_version          TEXT NOT NULL DEFAULT '1.2'  CHECK (schema_version = '1.2'),
    person_id               UUID NOT NULL REFERENCES persons(person_id) ON DELETE RESTRICT,
    -- Identity
    test_type               dna_test_type NOT NULL,
    test_provider           dna_test_provider,
    test_year_min           INTEGER CHECK (test_year_min IS NULL OR test_year_min BETWEEN 1995 AND 2050),
    test_year_max           INTEGER CHECK (test_year_max IS NULL OR test_year_max BETWEEN 1995 AND 2050),
    test_month              INTEGER CHECK (test_month IS NULL OR test_month BETWEEN 1 AND 12),
    -- HMAC-SHA-256 of kit ID with system salt (NOT plain SHA-256); see
    -- docs/DNA_ARCHITECTURE.md for the salt management policy.
    kit_id_hash             CHAR(64) NOT NULL UNIQUE CHECK (kit_id_hash ~ '^[a-f0-9]{64}$'),
    kit_source              TEXT NOT NULL,
    -- Haplogroups
    haplogroup_y            TEXT CHECK (haplogroup_y IS NULL OR haplogroup_y ~ '^[A-Z][A-Za-z0-9\-]*$'),
    haplogroup_mt           TEXT CHECK (haplogroup_mt IS NULL OR haplogroup_mt ~ '^[A-Z][A-Za-z0-9\-]*$'),
    haplogroup_y_confidence NUMERIC(4,3) CHECK (haplogroup_y_confidence IS NULL OR haplogroup_y_confidence BETWEEN 0 AND 1),
    haplogroup_mt_confidence NUMERIC(4,3) CHECK (haplogroup_mt_confidence IS NULL OR haplogroup_mt_confidence BETWEEN 0 AND 1),
    -- Ancestry composition stored as JSONB (small array, no need to normalize)
    -- The 25-dim float vector goes to Qdrant; this is the structured copy.
    ancestry_composition    JSONB,
    -- Endogamy
    endogamy_flag           BOOLEAN NOT NULL DEFAULT FALSE,
    endogamy_population     TEXT,
    -- Privacy
    is_living_flag          BOOLEAN NOT NULL,
    redistribution_license  license_tier NOT NULL CHECK (redistribution_license = 'tier2-private'),
    raw_genotype_stored     BOOLEAN NOT NULL CHECK (raw_genotype_stored = FALSE),
    external_raw_data_location TEXT,
    -- Consent
    consent_status          consent_state NOT NULL,
    consented_at            TIMESTAMPTZ,
    consent_evidence_url    TEXT,
    withdrawal_requested_at TIMESTAMPTZ,
    -- External IDs (hashed cross-service aliases): JSONB map
    external_ids            JSONB DEFAULT '{}'::jsonb,
    -- Source records (array of MaxRecord UUIDs)
    source_records          UUID[] DEFAULT '{}',
    -- Provenance
    asserted_by             TEXT NOT NULL,
    asserted_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes                   TEXT
);

CREATE INDEX idx_dna_kits_person      ON dna_kits (person_id);
CREATE INDEX idx_dna_kits_hap_y       ON dna_kits (haplogroup_y) WHERE haplogroup_y IS NOT NULL;
CREATE INDEX idx_dna_kits_hap_mt      ON dna_kits (haplogroup_mt) WHERE haplogroup_mt IS NOT NULL;
CREATE INDEX idx_dna_kits_provider    ON dna_kits (test_provider);
CREATE INDEX idx_dna_kits_consent     ON dna_kits (consent_status);
CREATE INDEX idx_dna_kits_endogamy    ON dna_kits (endogamy_population) WHERE endogamy_flag = TRUE;

COMMENT ON TABLE dna_kits IS
    'One row per DNA test linked to a MaxPerson. Always tier2-private. Kit ID is HMAC-SHA-256 hashed with system salt before storage. Raw genotype data is NEVER stored here or anywhere we control.';

-- ============================================================================
-- TABLE 3 — dna_matches  (one row per match between two kits)
-- ============================================================================
CREATE TABLE dna_matches (
    match_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kit_a_hash               CHAR(64) NOT NULL CHECK (kit_a_hash ~ '^[a-f0-9]{64}$'),
    kit_b_hash               CHAR(64) NOT NULL CHECK (kit_b_hash ~ '^[a-f0-9]{64}$'),
    match_display_name       TEXT,
    -- Centimorgan totals (max raised to 7000 per six-brain to admit identical twins)
    shared_cm                NUMERIC(7,2) NOT NULL CHECK (shared_cm BETWEEN 0 AND 7000),
    longest_segment_cm       NUMERIC(6,2) CHECK (longest_segment_cm IS NULL OR longest_segment_cm BETWEEN 0 AND 285),
    segment_count            INTEGER CHECK (segment_count IS NULL OR segment_count >= 0),
    -- v1.2 additions
    cm_map_version           cm_map NOT NULL DEFAULT 'unknown',
    phasing_status           phasing NOT NULL DEFAULT 'unknown',
    inferred_relationship    relationship_inferred,
    relationship_confidence  NUMERIC(4,3) CHECK (relationship_confidence IS NULL OR relationship_confidence BETWEEN 0 AND 1),
    match_source             match_source_origin NOT NULL,
    -- MRCA candidates (array of {person_id, confidence, inference_method})
    -- Stored JSONB because length is small and queries are by-kit not by-MRCA
    common_ancestor_candidates JSONB DEFAULT '[]'::jsonb,
    -- Provenance
    asserted_by              TEXT NOT NULL,
    asserted_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Symmetric matches: enforce kit_a < kit_b alphabetically to avoid storing
    -- both (A,B) and (B,A) for the same pair from the same source.
    CONSTRAINT chk_kit_pair_ordered CHECK (kit_a_hash < kit_b_hash),
    -- Dedupe within a single source
    CONSTRAINT uq_match_pair UNIQUE (kit_a_hash, kit_b_hash, match_source)
);

-- Two indexes for "find all matches for kit X" (with X on either side)
CREATE INDEX idx_dna_matches_a_cm ON dna_matches (kit_a_hash, shared_cm DESC);
CREATE INDEX idx_dna_matches_b_cm ON dna_matches (kit_b_hash, shared_cm DESC);
CREATE INDEX idx_dna_matches_cm   ON dna_matches (shared_cm);
CREATE INDEX idx_dna_matches_rel  ON dna_matches (inferred_relationship);

COMMENT ON TABLE dna_matches IS
    'One row per known DNA match between two kits, per source. kit_a < kit_b enforced to dedupe symmetric pairs. common_ancestor_candidates is JSONB array: [{person_id, confidence, inference_method}, ...].';

-- ============================================================================
-- TABLE 4 — dna_segments  (one row per shared chromosomal segment)
-- ============================================================================
CREATE TABLE dna_segments (
    segment_id      BIGSERIAL PRIMARY KEY,
    match_id        UUID NOT NULL REFERENCES dna_matches(match_id) ON DELETE CASCADE,
    chromosome      chromosome_id NOT NULL,
    start_position  BIGINT,
    end_position    BIGINT,
    start_cm        NUMERIC(7,3) NOT NULL,
    end_cm          NUMERIC(7,3) NOT NULL,
    snp_count       INTEGER CHECK (snp_count IS NULL OR snp_count >= 0),
    build_version   build_id NOT NULL DEFAULT 'GRCh37',

    CONSTRAINT chk_segment_cm_order CHECK (start_cm <= end_cm),
    CONSTRAINT chk_segment_pos_order CHECK (start_position IS NULL OR end_position IS NULL OR start_position <= end_position)
);

-- GiST index for range/overlap queries: "find segments overlapping chr 7 between 45 and 62 cM"
CREATE INDEX idx_dna_segments_overlap
    ON dna_segments USING GIST (chromosome, numrange(start_cm::numeric, end_cm::numeric));
CREATE INDEX idx_dna_segments_match ON dna_segments (match_id);

COMMENT ON TABLE dna_segments IS
    'Individual shared segments for triangulation analysis. GiST index supports range-overlap queries across millions of segments.';

-- ============================================================================
-- TABLE 5 — dna_evidence_chains  (derived; MRCA inference results)
-- ============================================================================
-- Written by the nightly chain-inference worker. Reads from dna_matches +
-- persons trees, computes likelihoods, writes one row per (kit_pair, MRCA)
-- candidate. MaxPerson.dna_evidence[] (JSON) mirrors this back for the
-- person-side view.
-- ============================================================================
CREATE TABLE dna_evidence_chains (
    chain_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mrca_person_id          UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    dna_id_a                UUID NOT NULL REFERENCES dna_kits(dna_id) ON DELETE CASCADE,
    dna_id_b                UUID NOT NULL REFERENCES dna_kits(dna_id) ON DELETE CASCADE,
    shared_cm               NUMERIC(7,2) NOT NULL CHECK (shared_cm BETWEEN 0 AND 7000),
    path_length_generations INTEGER NOT NULL CHECK (path_length_generations BETWEEN 2 AND 12),
    likelihood              NUMERIC(5,4) NOT NULL CHECK (likelihood BETWEEN 0 AND 1),
    confidence_delta        NUMERIC(5,4) NOT NULL CHECK (confidence_delta BETWEEN 0 AND 0.5),
    inference_method        TEXT,        -- tree_intersection, triangulation, manual, ...
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_chain_kit_distinct CHECK (dna_id_a <> dna_id_b)
);

CREATE INDEX idx_evidence_chains_mrca ON dna_evidence_chains (mrca_person_id);
CREATE INDEX idx_evidence_chains_a    ON dna_evidence_chains (dna_id_a);
CREATE INDEX idx_evidence_chains_b    ON dna_evidence_chains (dna_id_b);

COMMENT ON TABLE dna_evidence_chains IS
    'Derived: one row per (DNA pair × candidate MRCA). Cascade-deletes when a kit is removed (withdrawal) or a person is deleted. Source-of-truth for MaxPerson.dna_evidence[] (which mirrors a subset of these columns into JSON).';

-- ============================================================================
-- TABLE 6 — haplogroup_tree  (Y-DNA and mtDNA reference tree)
-- ============================================================================
-- Populated once from ISOGG / YFull public trees, refreshed quarterly. Uses
-- ltree for fast "all descendants of R-M269" type queries.
-- ============================================================================
CREATE TABLE haplogroup_tree (
    haplogroup       TEXT PRIMARY KEY,
    parent_haplogroup TEXT REFERENCES haplogroup_tree(haplogroup) ON DELETE RESTRICT,
    ltree_path       LTREE NOT NULL,
    kind             TEXT NOT NULL CHECK (kind IN ('y_dna', 'mt_dna')),
    source           TEXT NOT NULL,    -- 'isogg', 'yfull', etc.
    refreshed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_haplogroup_path ON haplogroup_tree USING GIST (ltree_path);
CREATE INDEX idx_haplogroup_kind ON haplogroup_tree (kind);

COMMENT ON TABLE haplogroup_tree IS
    'Reference tree of Y-DNA and mtDNA haplogroups. ltree_path enables descendant queries (e.g. WHERE ltree_path <@ ''R.M269''). Refreshed quarterly from ISOGG/YFull public trees.';

-- ============================================================================
-- Triggers — updated_at maintenance
-- ============================================================================
CREATE OR REPLACE FUNCTION fn_touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_persons_updated
    BEFORE UPDATE ON persons
    FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();

-- ============================================================================
-- Withdrawal cascade — placeholder
-- ----------------------------------------------------------------------------
-- When dna_kits.withdrawal_requested_at is set, a separate scheduled job (NOT
-- a database trigger) is responsible for:
--   1. After 30 days, hard-delete the dna_kits row (CASCADE drops segments,
--      matches involving the kit, evidence_chains)
--   2. Recompute MaxPerson confidence noisy-OR without the withdrawn evidence
--   3. Update the MaxPerson JSON source of truth
-- The 30-day timer is intentionally NOT a Postgres trigger so that a manual
-- review window remains, and so the recompute job can run in app code with
-- proper logging and rollback.
-- ============================================================================

-- ============================================================================
-- Migration registry
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version       TEXT PRIMARY KEY,
    applied_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    description   TEXT
);

INSERT INTO schema_migrations (version, description) VALUES
    ('001_init', 'Initial DDL: persons mirror + dna_kits + dna_matches + dna_segments + dna_evidence_chains + haplogroup_tree');

COMMIT;
