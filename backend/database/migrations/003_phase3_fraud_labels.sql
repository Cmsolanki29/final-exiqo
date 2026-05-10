-- Phase 3: Fraud labels — adds is_fraud column to transactions and creates
-- fraud_feedback table for the labeling flywheel.
--
-- The fraud_feedback table accumulates labels from three sources:
--   'synthetic'   — injected by ml_training/synthetic_data.py for bootstrap
--   'user_report' — user says "this wasn't me" via /api/transactions/{id}/report-fraud
--   'chargeback'  — dispute ingested via /api/webhooks/chargeback
--   'analyst'     — manual review queue decision (Phase 8)
--
-- Point-in-time correctness:
--   fraud_label_at records WHEN the fraud occurred (for feature store backfill),
--   not when the label was applied.

ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS is_fraud            BOOLEAN       DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS fraud_label_source  VARCHAR(50)   DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS fraud_label_at      TIMESTAMPTZ   DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_transactions_is_fraud
    ON transactions (is_fraud) WHERE is_fraud IS NOT NULL;

CREATE TABLE IF NOT EXISTS fraud_feedback (
    id              BIGSERIAL       PRIMARY KEY,
    transaction_id  BIGINT          NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    label           BOOLEAN         NOT NULL,     -- TRUE = fraud, FALSE = legitimate
    source          VARCHAR(50)     NOT NULL,     -- 'synthetic' | 'user_report' | 'chargeback' | 'analyst'
    notes           TEXT            DEFAULT NULL,
    reviewed_by     UUID            DEFAULT NULL, -- analyst user UUID
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fraud_feedback_txn_id
    ON fraud_feedback (transaction_id);

CREATE INDEX IF NOT EXISTS idx_fraud_feedback_created_at
    ON fraud_feedback (created_at DESC);

COMMENT ON TABLE fraud_feedback IS
    'Fraud labels from all sources; feeds the XGBoost retraining pipeline.';
COMMENT ON COLUMN fraud_feedback.label IS
    'TRUE = confirmed fraud, FALSE = confirmed legitimate.';
