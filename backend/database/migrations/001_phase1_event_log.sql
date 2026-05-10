-- Phase 1: Event log table for Redis Streams durability.
-- Every scored transaction publishes an event; this table survives Redis restarts.
-- Topic constants match services/event_bus/publisher.py TOPICS.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS events (
    id            UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic         TEXT          NOT NULL,
    payload       JSONB         NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    processed_at  TIMESTAMPTZ   NULL,
    retry_count   INTEGER       NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_topic_created
    ON events (topic, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_unprocessed
    ON events (processed_at, created_at)
    WHERE processed_at IS NULL;

COMMENT ON TABLE events IS
    'Durable event log backing Redis Streams. Consumers write processed_at when done.';
COMMENT ON COLUMN events.payload IS 'Full JSON payload; mirrors what is published to Redis Stream.';
COMMENT ON COLUMN events.retry_count IS 'Incremented on failed consumer processing; dead-letter at 3.';
