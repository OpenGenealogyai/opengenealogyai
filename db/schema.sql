-- OpenGenealogyAI SQLite Staging Database Schema v0.1
-- Append-only: no assertions are ever deleted
-- Every assertion must have a corresponding judge APPROVE verdict on file

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS persons (
    person_id          TEXT PRIMARY KEY,
    name_canonical     TEXT NOT NULL,
    birth_year_min     INTEGER,
    birth_year_max     INTEGER,
    death_year_min     INTEGER,
    death_year_max     INTEGER,
    country_code       TEXT,
    redistribution_license TEXT NOT NULL DEFAULT 'public-domain',
    is_living          INTEGER NOT NULL DEFAULT 0,
    composite_confidence REAL NOT NULL DEFAULT 0.0,
    judge_approved     INTEGER NOT NULL DEFAULT 0,
    judge_approved_at  TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assertions (
    assertion_id       TEXT PRIMARY KEY,
    subject_id         TEXT NOT NULL REFERENCES persons(person_id),
    predicate          TEXT NOT NULL,
    value_json         TEXT NOT NULL,
    confidence         REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
    source_record_id   TEXT NOT NULL,
    asserted_by        TEXT NOT NULL,
    asserted_at        TEXT NOT NULL,
    conflict_flag      INTEGER NOT NULL DEFAULT 0,
    superseded_by      TEXT REFERENCES assertions(assertion_id),
    judge_verdict_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_records (
    record_id          TEXT PRIMARY KEY,
    record_type        TEXT NOT NULL,
    year_min           INTEGER,
    year_max           INTEGER,
    country_code       TEXT,
    redistribution_license TEXT NOT NULL,
    is_living_flag     INTEGER NOT NULL DEFAULT 0,
    transcription      TEXT,
    image_url          TEXT,
    source_url         TEXT NOT NULL,
    digital_object_id  TEXT,
    extraction_confidence REAL NOT NULL,
    extracted_by       TEXT,
    extracted_at       TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_cost_log (
    log_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id           TEXT NOT NULL,
    agent_type         TEXT NOT NULL CHECK(agent_type IN ('haiku','sonnet','opus','unknown')),
    task_id            TEXT,
    api_cost           REAL NOT NULL DEFAULT 0.0,
    tokens_input       INTEGER,
    tokens_output      INTEGER,
    timestamp          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_persons_birth_year ON persons(birth_year_min, birth_year_max);
CREATE INDEX IF NOT EXISTS idx_persons_country ON persons(country_code);
CREATE INDEX IF NOT EXISTS idx_persons_license ON persons(redistribution_license);
CREATE INDEX IF NOT EXISTS idx_assertions_subject ON assertions(subject_id);
CREATE INDEX IF NOT EXISTS idx_assertions_source ON assertions(source_record_id);
CREATE INDEX IF NOT EXISTS idx_raw_records_year ON raw_records(year_min, year_max);
CREATE INDEX IF NOT EXISTS idx_raw_records_country ON raw_records(country_code);
CREATE INDEX IF NOT EXISTS idx_cost_log_date ON agent_cost_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_cost_log_agent ON agent_cost_log(agent_type);
