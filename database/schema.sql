-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================
-- TABLE 1: users
-- =====================
CREATE TABLE IF NOT EXISTS users (
  id                SERIAL PRIMARY KEY,
  uuid              UUID DEFAULT uuid_generate_v4() UNIQUE,
  name              VARCHAR(100) NOT NULL,
  email             VARCHAR(100) UNIQUE NOT NULL,
  monthly_income    DECIMAL(12,2) NOT NULL,
  savings_goal      DECIMAL(12,2) DEFAULT 0,
  risk_tolerance    VARCHAR(10) DEFAULT 'MEDIUM' CHECK (risk_tolerance IN ('LOW','MEDIUM','HIGH')),
  created_at        TIMESTAMP DEFAULT NOW(),
  updated_at        TIMESTAMP DEFAULT NOW()
);

-- =====================
-- TABLE 2: transactions (core table — ML-ready)
-- =====================
CREATE TABLE IF NOT EXISTS transactions (
  id                SERIAL PRIMARY KEY,
  uuid              UUID DEFAULT uuid_generate_v4() UNIQUE,
  user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  -- Transaction details
  transaction_date  DATE NOT NULL,
  transaction_time  TIME NOT NULL,
  amount            DECIMAL(12,2) NOT NULL,
  type              VARCHAR(10) NOT NULL CHECK (type IN ('DEBIT','CREDIT')),
  description       TEXT,
  merchant          VARCHAR(200),
  category          VARCHAR(50),  -- Food, Travel, Shopping, Bills, Entertainment, Healthcare, Salary, etc.
  subcategory       VARCHAR(50),  -- e.g. Food > Swiggy, Travel > Uber
  payment_method    VARCHAR(30),  -- UPI, NEFT, IMPS, Card, Cash, NetBanking
  location          VARCHAR(200),
  balance_after     DECIMAL(12,2),
  reference_number  VARCHAR(100),

  -- ML output columns (filled by anomaly detection pipeline)
  anomaly_flag      BOOLEAN DEFAULT FALSE,
  risk_score        INTEGER DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
  risk_level        VARCHAR(10) DEFAULT 'LOW' CHECK (risk_level IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  anomaly_reason    TEXT,
  ml_processed      BOOLEAN DEFAULT FALSE,

  -- Feature columns for ML (pre-computed)
  hour_of_day       INTEGER,  -- 0-23, extracted from transaction_time
  day_of_week       INTEGER,  -- 0=Monday, 6=Sunday
  is_weekend        BOOLEAN,
  is_night_txn      BOOLEAN,  -- between 11pm-5am

  created_at        TIMESTAMP DEFAULT NOW()
);

-- Indexes for ML queries and dashboard speed
CREATE INDEX IF NOT EXISTS idx_txn_user_date ON transactions(user_id, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(user_id, category);
CREATE INDEX IF NOT EXISTS idx_txn_anomaly ON transactions(user_id, anomaly_flag) WHERE anomaly_flag = TRUE;
CREATE INDEX IF NOT EXISTS idx_txn_ml_processed ON transactions(ml_processed) WHERE ml_processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(transaction_date);

-- =====================
-- TABLE 3: alerts
-- =====================
CREATE TABLE IF NOT EXISTS alerts (
  id                SERIAL PRIMARY KEY,
  uuid              UUID DEFAULT uuid_generate_v4() UNIQUE,
  user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  transaction_id    INTEGER REFERENCES transactions(id) ON DELETE SET NULL,

  severity          VARCHAR(10) NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  alert_type        VARCHAR(50) NOT NULL,  -- DUPLICATE_CHARGE, UNUSUAL_AMOUNT, ODD_HOUR, FOREIGN_MERCHANT, etc.
  message           TEXT NOT NULL,
  detail            TEXT,

  is_read           BOOLEAN DEFAULT FALSE,
  is_resolved       BOOLEAN DEFAULT FALSE,
  resolved_at       TIMESTAMP,

  created_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_user_unread ON alerts(user_id, is_read) WHERE is_read = FALSE;

-- =====================
-- TABLE 4: monthly_summary (pre-computed for dashboard speed)
-- =====================
CREATE TABLE IF NOT EXISTS monthly_summary (
  id                SERIAL PRIMARY KEY,
  user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  month             INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
  year              INTEGER NOT NULL,

  total_income      DECIMAL(12,2) DEFAULT 0,
  total_expense     DECIMAL(12,2) DEFAULT 0,
  total_saved       DECIMAL(12,2) DEFAULT 0,
  savings_rate      DECIMAL(5,2) DEFAULT 0,  -- percentage

  -- Category breakdown (JSON for flexibility)
  category_breakdown JSONB,

  -- ML-derived columns
  health_score      INTEGER DEFAULT 0 CHECK (health_score BETWEEN 0 AND 100),
  anomaly_count     INTEGER DEFAULT 0,
  high_risk_count   INTEGER DEFAULT 0,
  top_category      VARCHAR(50),

  -- Computed at
  computed_at       TIMESTAMP DEFAULT NOW(),

  UNIQUE(user_id, month, year)
);

-- =====================
-- TABLE 5: spending_patterns (for ML baseline)
-- =====================
CREATE TABLE IF NOT EXISTS spending_patterns (
  id                SERIAL PRIMARY KEY,
  user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category          VARCHAR(50) NOT NULL,
  avg_monthly_spend DECIMAL(12,2),
  max_single_txn    DECIMAL(12,2),
  typical_merchants TEXT[],  -- array of usual merchants
  typical_hours     INTEGER[],  -- array of usual transaction hours
  last_updated      TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, category)
);
