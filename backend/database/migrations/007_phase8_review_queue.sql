-- Phase 8: Feedback Flywheel
--
-- Introduces the review_queue table that captures transactions requiring
-- human analyst review.  Populated by:
--   - DecisionEngine when action = 'review'
--   - HybridScorer counterfactual hold-out (borderline ALLOW, 1% sample)
--
-- The table is consumed by:
--   - ReviewQueueWorker (auto-assignment)
--   - routes/feedback.py (analyst resolve endpoint)
--   - retrain_feed_consumer (label accumulation for retraining trigger)

-- ------------------------------------------------------------------ --
-- review_queue
-- ------------------------------------------------------------------ --

CREATE TABLE IF NOT EXISTS review_queue (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id   INTEGER      NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    score            INTEGER      NOT NULL CHECK (score BETWEEN 0 AND 100),
    decision         JSONB        NOT NULL DEFAULT '{}',
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending'
                                  CHECK (status IN ('pending', 'in_review', 'resolved')),
    priority         VARCHAR(10)  NOT NULL DEFAULT 'normal'
                                  CHECK (priority IN ('low', 'normal', 'high')),
    assigned_to      UUID         NULL,
    assigned_at      TIMESTAMPTZ  NULL,
    resolved_at      TIMESTAMPTZ  NULL,
    resolution       VARCHAR(20)  NULL
                                  CHECK (resolution IN ('fraud', 'legitimate', 'inconclusive')),
    notes            TEXT         NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Fast lookup for queue dashboard (status + priority + time)
CREATE INDEX IF NOT EXISTS idx_review_queue_status_priority_created
    ON review_queue (status, priority DESC, created_at DESC);

-- Fast lookup by analyst assignment
CREATE INDEX IF NOT EXISTS idx_review_queue_assigned_to
    ON review_queue (assigned_to)
    WHERE assigned_to IS NOT NULL;

-- Lookup by transaction_id (prevent duplicate enqueue of same txn)
CREATE UNIQUE INDEX IF NOT EXISTS uidx_review_queue_transaction_id
    ON review_queue (transaction_id)
    WHERE status != 'resolved';

COMMENT ON TABLE review_queue IS
    'Phase 8: analyst review queue — populated by REVIEW decisions and '
    'counterfactual hold-outs, resolved by human analysts via admin API.';

COMMENT ON COLUMN review_queue.decision IS
    'Snapshot of the Decision object at decision time (action, reasons, '
    'rule_overrides, SHAP explanation).  Immutable after insert.';

COMMENT ON COLUMN review_queue.priority IS
    'low  = counterfactual hold-out sample; '
    'normal = score-based REVIEW; '
    'high  = score ≥ 70 or triggered by velocity/geo override.';
