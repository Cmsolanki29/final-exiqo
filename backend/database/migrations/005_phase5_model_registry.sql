-- Phase 5: MLOps — model registry tracking, drift reports, shadow predictions.
--
-- model_deployments: mirrors MLflow stage transitions with SmartSpend-specific
--   metadata (traffic_percentage for canary, promoted_by for audit trail).
--
-- drift_reports: PSI and KL divergence computed hourly per feature.
--   alert_triggered = TRUE when PSI > DRIFT_PSI_ALERT_THRESHOLD (0.25).
--
-- shadow_predictions: every transaction scored by BOTH production and shadow models.
--   The shadow score is invisible to users; it's used by ShadowLogger.evaluate_shadow()
--   to gate canary promotion.  feature_hash allows correlation with feature_snapshots.

CREATE TABLE IF NOT EXISTS model_deployments (
    id                  BIGSERIAL       PRIMARY KEY,
    model_name          VARCHAR(255)    NOT NULL,
    version             VARCHAR(50)     NOT NULL,
    stage               VARCHAR(20)     NOT NULL
                        CHECK (stage IN ('shadow','canary','production','archived')),
    traffic_percentage  INTEGER         NOT NULL DEFAULT 0
                        CHECK (traffic_percentage BETWEEN 0 AND 100),
    promoted_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    promoted_by         VARCHAR(255)    DEFAULT NULL,   -- admin user id
    metrics             JSONB           NOT NULL DEFAULT '{}',
    UNIQUE (model_name, version, stage)
);

CREATE INDEX IF NOT EXISTS idx_model_deployments_name_stage
    ON model_deployments (model_name, stage);

COMMENT ON TABLE model_deployments IS
    'Phase 5: tracks which model versions are in which deployment stage with canary traffic %';

CREATE TABLE IF NOT EXISTS drift_reports (
    id              BIGSERIAL       PRIMARY KEY,
    feature_name    VARCHAR(255)    NOT NULL,
    psi_value       DOUBLE PRECISION NOT NULL,
    kl_divergence   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    computed_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    alert_triggered BOOLEAN         NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_drift_reports_feature_time
    ON drift_reports (feature_name, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_drift_reports_alerts
    ON drift_reports (alert_triggered, computed_at DESC)
    WHERE alert_triggered = TRUE;

COMMENT ON TABLE drift_reports IS
    'Phase 5: hourly PSI drift monitoring results per feature.';

CREATE TABLE IF NOT EXISTS shadow_predictions (
    id              BIGSERIAL       PRIMARY KEY,
    transaction_id  BIGINT          DEFAULT NULL,   -- nullable: logged before DB insert possible
    prod_score      INTEGER         NOT NULL,
    shadow_score    INTEGER         NOT NULL,
    prod_action     VARCHAR(20)     NOT NULL,
    shadow_action   VARCHAR(20)     NOT NULL,
    feature_hash    VARCHAR(64)     DEFAULT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shadow_predictions_txn_id
    ON shadow_predictions (transaction_id)
    WHERE transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_shadow_predictions_created_at
    ON shadow_predictions (created_at DESC);

COMMENT ON TABLE shadow_predictions IS
    'Phase 5: dual-scored transactions for shadow/canary evaluation.  Shadow score is never returned to users.';
