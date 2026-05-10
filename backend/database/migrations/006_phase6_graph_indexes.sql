-- Phase 6: Graph / Network Signals
--
-- Adds device_id, ip_address, card_token to the transactions table so that
-- graph traversals (device-sharing, IP clustering, card-sharing) have data
-- to work with.  All three columns are nullable — existing rows are unaffected.
--
-- Materialized views (refreshed hourly via APScheduler) pre-aggregate the
-- relationship counts used by GraphFeatureService so that per-user graph
-- feature computation becomes a cheap indexed lookup rather than a full table
-- scan at scoring time.
--
-- CONCURRENTLY refresh requires UNIQUE indexes on each MV.

-- ------------------------------------------------------------------ --
-- Step 1: Add nullable graph columns to transactions
-- ------------------------------------------------------------------ --

ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS device_id   VARCHAR(255) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS ip_address  VARCHAR(45)  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS card_token  VARCHAR(255) DEFAULT NULL;

-- ------------------------------------------------------------------ --
-- Step 2: Indexes for graph traversals
-- ------------------------------------------------------------------ --

CREATE INDEX IF NOT EXISTS idx_txn_device_user
    ON transactions (device_id, user_id)
    WHERE device_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_txn_ip_user
    ON transactions (ip_address, user_id)
    WHERE ip_address IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_txn_merchant_user
    ON transactions (merchant, user_id)
    WHERE merchant IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_txn_card_user
    ON transactions (card_token, user_id)
    WHERE card_token IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_txn_user_date
    ON transactions (user_id, transaction_date DESC);

-- ------------------------------------------------------------------ --
-- Step 3: Materialized views (used by GraphFeatureService)
-- ------------------------------------------------------------------ --

-- How many distinct users share each device (last 30 days)?
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_device_user_count AS
SELECT
    device_id,
    COUNT(DISTINCT user_id) AS user_count
FROM transactions
WHERE device_id  IS NOT NULL
  AND transaction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY device_id;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_mv_device_user_count
    ON mv_device_user_count (device_id);

-- How many distinct devices does each user use (last 30 days)?
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_device_count AS
SELECT
    user_id,
    COUNT(DISTINCT device_id) AS device_count
FROM transactions
WHERE device_id IS NOT NULL
  AND transaction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY user_id;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_mv_user_device_count
    ON mv_user_device_count (user_id);

-- How many distinct users share each IP (last 24 hours)?
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ip_user_count_24h AS
SELECT
    ip_address,
    COUNT(DISTINCT user_id) AS user_count
FROM transactions
WHERE ip_address IS NOT NULL
  AND transaction_date >= CURRENT_DATE - INTERVAL '1 day'
GROUP BY ip_address;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_mv_ip_user_count_24h
    ON mv_ip_user_count_24h (ip_address);

-- How many distinct IPs does each user use (last 7 days)?
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_ip_count_7d AS
SELECT
    user_id,
    COUNT(DISTINCT ip_address) AS ip_count
FROM transactions
WHERE ip_address IS NOT NULL
  AND transaction_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY user_id;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_mv_user_ip_count_7d
    ON mv_user_ip_count_7d (user_id);

-- How many distinct users share each card token (last 30 days)?
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_card_user_count AS
SELECT
    card_token,
    COUNT(DISTINCT user_id) AS user_count
FROM transactions
WHERE card_token IS NOT NULL
  AND transaction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY card_token;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_mv_card_user_count
    ON mv_card_user_count (card_token);

-- ------------------------------------------------------------------ --
-- Step 4: Auxiliary index to accelerate fraud-ring traversals
-- ------------------------------------------------------------------ --

-- Merchant-based fraud ring queries need fast lookups on (merchant, is_fraud)
CREATE INDEX IF NOT EXISTS idx_txn_merchant_fraud
    ON transactions (merchant, is_fraud)
    WHERE merchant IS NOT NULL AND is_fraud = TRUE;

COMMENT ON MATERIALIZED VIEW mv_device_user_count  IS 'Phase 6: device → user count, refreshed hourly';
COMMENT ON MATERIALIZED VIEW mv_user_device_count  IS 'Phase 6: user → device count, refreshed hourly';
COMMENT ON MATERIALIZED VIEW mv_ip_user_count_24h  IS 'Phase 6: IP → user count (24h), refreshed hourly';
COMMENT ON MATERIALIZED VIEW mv_user_ip_count_7d   IS 'Phase 6: user → IP count (7d), refreshed hourly';
COMMENT ON MATERIALIZED VIEW mv_card_user_count    IS 'Phase 6: card token → user count, refreshed hourly';
