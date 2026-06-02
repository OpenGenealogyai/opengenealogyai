-- ============================================================================
-- MAXGEN — Postgres DDL — Migration 002 (life events + place registry mirror)
-- ============================================================================
-- Adds the mirror tables backing MaxPerson.event_assertions[] and
-- MaxPerson.place_registry[] (both already defined in person.schema.json v1.3+).
-- The JSON MaxPerson remains the source of truth; these tables exist for FK
-- targets, JOINs, sorting, and the portal's Life-Story / Migration views.
--
-- This is the canonical home for migration/residence/census/land/military
-- events. There is NO separate "vital_events" table — that would fork the
-- standard and break GEDCOM round-trip. Conform to this shape.
--
-- Additive only. Safe to re-run (IF NOT EXISTS guards).
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- TABLE — person_events  (mirror of MaxPerson.event_assertions[])
-- One row per event assertion. Multiple, possibly conflicting, rows per person
-- are normal — each carries its own source and confidence (probabilistic model).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person_events (
    event_pk          BIGSERIAL PRIMARY KEY,
    person_id         UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    event_type        TEXT NOT NULL CHECK (event_type IN (
                          'baptism','christening','confirmation','bar_bat_mitzvah',
                          'immigration','emigration','naturalization','residence',
                          'census_enumeration','burial','cremation','military_service',
                          'will','probate','land_grant','education','ordination',
                          'divorce','other')),
    event_type_other  TEXT,                 -- free-text label when event_type='other'
    year_min          INTEGER CHECK (year_min IS NULL OR year_min BETWEEN 1000 AND 2100),
    year_max          INTEGER CHECK (year_max IS NULL OR year_max BETWEEN 1000 AND 2100),
    month             INTEGER CHECK (month IS NULL OR month BETWEEN 1 AND 12),
    day               INTEGER CHECK (day   IS NULL OR day   BETWEEN 1 AND 31),
    date_type         TEXT CHECK (date_type IS NULL OR date_type IN ('exact','estimated','calculated','range')),
    place_as_written  TEXT,                 -- join key into place_registry
    description       TEXT,                 -- per-event narrative (the "story" of this event)
    confidence        REAL CHECK (confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0),
    source_record_id  UUID,                 -- the MaxRecord proving this event
    asserted_by       TEXT,
    asserted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_event_year_order CHECK (year_min IS NULL OR year_max IS NULL OR year_min <= year_max)
);

CREATE INDEX IF NOT EXISTS idx_person_events_person ON person_events (person_id);
CREATE INDEX IF NOT EXISTS idx_person_events_type   ON person_events (event_type);
CREATE INDEX IF NOT EXISTS idx_person_events_years  ON person_events (year_min, year_max);

COMMENT ON TABLE person_events IS
    'Mirror of MaxPerson.event_assertions[]. Canonical home for migration/residence/census/land/military/probate events. No parallel vital_events table — conform here to keep the standard unforked and GEDCOM-portable.';

-- ----------------------------------------------------------------------------
-- TABLE — place_registry  (mirror of MaxPerson.place_registry[])
-- Resolves free-text place strings to stable gazetteer IDs and, crucially,
-- handles places whose name/jurisdiction changed over time via historical_polity
-- + valid-year range (e.g. "Kentucky County, Virginia" 1776–1786 -> "Bourbon
-- County, KY" after). Feeds the portal Migration map.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS place_registry (
    place_pk            BIGSERIAL PRIMARY KEY,
    place_as_written    TEXT NOT NULL,      -- the join key (matches person_events.place_as_written)
    geonames_id         TEXT,
    wikidata_qid        TEXT CHECK (wikidata_qid IS NULL OR wikidata_qid ~ '^Q[0-9]+$'),
    historical_polity   TEXT,               -- sovereign entity at the relevant time
    modern_country_code TEXT CHECK (modern_country_code IS NULL OR modern_country_code ~ '^[A-Z]{2}$'),
    valid_from_year     INTEGER CHECK (valid_from_year IS NULL OR valid_from_year BETWEEN 1000 AND 2100),
    valid_to_year       INTEGER CHECK (valid_to_year   IS NULL OR valid_to_year   BETWEEN 1000 AND 2100),
    latitude            DOUBLE PRECISION CHECK (latitude  IS NULL OR latitude  BETWEEN -90 AND 90),
    longitude           DOUBLE PRECISION CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    confidence          REAL CHECK (confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0)
);

CREATE INDEX IF NOT EXISTS idx_place_registry_place ON place_registry (place_as_written);

COMMENT ON TABLE place_registry IS
    'Mirror of MaxPerson.place_registry[]. Normalizes places and represents historical jurisdiction changes (historical_polity + valid year range). Drives the Migration map.';

INSERT INTO schema_migrations (version, description) VALUES
    ('002_events_places', 'Life-event + place-registry mirror tables backing MaxPerson.event_assertions[] and place_registry[] (migration/residence support)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
