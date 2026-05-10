-- Phase 4: Decision Engine — merchant risk configurations and entity blacklist.
--
-- merchant_risk_config: per-merchant decision thresholds and custom rules.
--   Each row overrides the global thresholds for a specific merchant.
--   The JSON custom_rules column supports arbitrary rule extensions (Phase 6+).
--
-- blacklisted_entities: hard-block list for users, merchants, devices, IPs, and cards.
--   Any transaction touching a blacklisted entity is blocked regardless of ML score.
--   expires_at enables time-limited blocks (e.g., 30-day device ban after chargeback).

CREATE TABLE IF NOT EXISTS merchant_risk_config (
    merchant_id          VARCHAR(255)   PRIMARY KEY,
    block_threshold      INTEGER        NOT NULL DEFAULT 80,
    challenge_threshold  INTEGER        NOT NULL DEFAULT 60,
    review_threshold     INTEGER        NOT NULL DEFAULT 40,
    custom_rules         JSONB          NOT NULL DEFAULT '{}',
    updated_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE merchant_risk_config IS
    'Per-merchant risk appetite overrides.  Populated via PATCH /api/admin/merchants/{id}/risk-config.';

COMMENT ON COLUMN merchant_risk_config.block_threshold IS
    'Scores >= this trigger BLOCK action for this merchant (default 80).';
COMMENT ON COLUMN merchant_risk_config.challenge_threshold IS
    'Scores >= this trigger CHALLENGE action (default 60).';
COMMENT ON COLUMN merchant_risk_config.review_threshold IS
    'Scores >= this trigger REVIEW action (default 40).';

CREATE TABLE IF NOT EXISTS blacklisted_entities (
    id            BIGSERIAL      PRIMARY KEY,
    entity_type   VARCHAR(20)    NOT NULL CHECK (entity_type IN ('merchant','device','ip','card','user','location')),
    entity_value  VARCHAR(512)   NOT NULL,
    reason        TEXT           NOT NULL,
    severity      VARCHAR(20)    NOT NULL DEFAULT 'HIGH'
                                 CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    added_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ    DEFAULT NULL  -- NULL = never expires
);

CREATE UNIQUE INDEX IF NOT EXISTS uidx_blacklisted_entities_type_value
    ON blacklisted_entities (entity_type, entity_value);

CREATE INDEX IF NOT EXISTS idx_blacklisted_entities_entity_type
    ON blacklisted_entities (entity_type);

CREATE INDEX IF NOT EXISTS idx_blacklisted_expires
    ON blacklisted_entities (expires_at)
    WHERE expires_at IS NOT NULL;

COMMENT ON TABLE blacklisted_entities IS
    'Hard-block entities regardless of ML score.  Checked at step 1 of the Decision Engine.';
COMMENT ON COLUMN blacklisted_entities.expires_at IS
    'NULL = permanent block.  Non-null = auto-expire after this timestamp.';
