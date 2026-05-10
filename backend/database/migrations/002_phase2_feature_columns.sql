-- Phase 2: Feature store offline snapshot table.
-- The online store lives in Redis (ephemeral); this table is the durable
-- point-in-time record used for backfills, training matrix reconstruction,
-- and online/offline consistency checks.
--
-- Schema:
--   entity_type  — "user" | "device" | "ip" | "merchant" | "card"
--   entity_id    — the entity's primary key as text (user_id, device_id, etc.)
--   features     — full feature dict at compute_at time (JSONB)
--   computed_at  — when the snapshot was taken (UTC)

CREATE TABLE IF NOT EXISTS feature_snapshots (
    id           BIGSERIAL      PRIMARY KEY,
    entity_type  TEXT           NOT NULL,
    entity_id    TEXT           NOT NULL,
    features     JSONB          NOT NULL,
    computed_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- Fast lookup for point-in-time retrieval: get most-recent snapshot before
-- a given timestamp for (entity_type, entity_id).
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_entity_time
    ON feature_snapshots (entity_type, entity_id, computed_at DESC);

-- Retention: rows older than 90 days can be pruned without impacting live scoring.
-- A cron job or pg_partman should handle this in prod.
COMMENT ON TABLE feature_snapshots IS
    'Durable offline feature snapshots for point-in-time training reconstruction.';
COMMENT ON COLUMN feature_snapshots.features IS
    'Full flat feature dict, JSON-serialised. Keys match FEATURE_CATALOG names.';
