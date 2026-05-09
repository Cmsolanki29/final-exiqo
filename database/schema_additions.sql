-- Phase 6 additions: EMI Trap Detector + Subscription Graveyard

CREATE TABLE IF NOT EXISTS emi_records (
  id              SERIAL PRIMARY KEY,
  user_id         INTEGER REFERENCES users(id),
  merchant        VARCHAR(200),
  detected_amount DECIMAL(12,2),
  payment_date    INTEGER,
  category        VARCHAR(50),
  emi_type        VARCHAR(50),
  months_detected INTEGER DEFAULT 0,
  is_active       BOOLEAN DEFAULT TRUE,
  first_detected  DATE,
  last_detected   DATE,
  created_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, merchant)
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id                SERIAL PRIMARY KEY,
  user_id           INTEGER REFERENCES users(id),
  merchant          VARCHAR(200),
  amount            DECIMAL(12,2),
  billing_cycle     VARCHAR(20),
  category          VARCHAR(50),
  status            VARCHAR(20),
  usage_score       INTEGER,
  last_used_days    INTEGER,
  monthly_cost      DECIMAL(12,2),
  times_charged     INTEGER DEFAULT 0,
  first_charged     DATE,
  last_charged      DATE,
  UNIQUE(user_id, merchant)
);

-- EMI seed transactions (Jan 2025 - May 2026)
WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  1,
  (month_start + interval '4 day')::date,
  time '10:00',
  4200,
  'DEBIT',
  'Car loan EMI auto debit',
  'HDFC Car Loan EMI',
  'Finance & Investment',
  'Auto Debit',
  FALSE, 0, 'LOW', FALSE,
  10, EXTRACT(DOW FROM (month_start + interval '4 day'))::int, EXTRACT(DOW FROM (month_start + interval '4 day'))::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 1
    AND t.merchant = 'HDFC Car Loan EMI'
    AND t.transaction_date = (m.month_start + interval '4 day')::date
    AND t.amount = 4200
);

WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  1,
  (month_start + interval '9 day')::date,
  time '10:15',
  2800,
  'DEBIT',
  'Phone installment monthly EMI',
  'Bajaj Finserv EMI',
  'Finance & Investment',
  'Auto Debit',
  FALSE, 0, 'LOW', FALSE,
  10, EXTRACT(DOW FROM (month_start + interval '9 day'))::int, EXTRACT(DOW FROM (month_start + interval '9 day'))::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 1
    AND t.merchant = 'Bajaj Finserv EMI'
    AND t.transaction_date = (m.month_start + interval '9 day')::date
    AND t.amount = 2800
);

WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  1,
  (month_start + interval '17 day')::date,
  time '10:25',
  9500,
  'DEBIT',
  'Personal loan EMI monthly repayment',
  'ICICI Personal Loan EMI',
  'Finance & Investment',
  'Auto Debit',
  FALSE, 0, 'LOW', FALSE,
  10, EXTRACT(DOW FROM (month_start + interval '17 day'))::int, EXTRACT(DOW FROM (month_start + interval '17 day'))::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 1
    AND t.merchant = 'ICICI Personal Loan EMI'
    AND t.transaction_date = (m.month_start + interval '17 day')::date
    AND t.amount = 9500
);

WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  1,
  (month_start + interval '12 day')::date,
  time '08:45',
  (1500 + ((EXTRACT(MONTH FROM month_start)::int % 3) * 120)),
  'DEBIT',
  'Credit card minimum due payment',
  'Credit Card MIN DUE',
  'Finance & Investment',
  'Card',
  FALSE, 0, 'LOW', FALSE,
  8, EXTRACT(DOW FROM (month_start + interval '12 day'))::int, EXTRACT(DOW FROM (month_start + interval '12 day'))::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 1
    AND t.merchant = 'Credit Card MIN DUE'
    AND t.transaction_date = (m.month_start + interval '12 day')::date
);

WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  2,
  month_start,
  time '09:20',
  28000,
  'DEBIT',
  'Home loan EMI monthly payment',
  'SBI Home Loan EMI',
  'Finance & Investment',
  'Auto Debit',
  FALSE, 0, 'LOW', FALSE,
  9, EXTRACT(DOW FROM month_start)::int, EXTRACT(DOW FROM month_start)::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 2
    AND t.merchant = 'SBI Home Loan EMI'
    AND t.transaction_date = m.month_start
    AND t.amount = 28000
);

WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  2,
  (month_start + interval '6 day')::date,
  time '09:35',
  12500,
  'DEBIT',
  'Car finance EMI payment',
  'Tata Capital Car',
  'Finance & Investment',
  'Auto Debit',
  FALSE, 0, 'LOW', FALSE,
  9, EXTRACT(DOW FROM (month_start + interval '6 day'))::int, EXTRACT(DOW FROM (month_start + interval '6 day'))::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 2
    AND t.merchant = 'Tata Capital Car'
    AND t.transaction_date = (m.month_start + interval '6 day')::date
    AND t.amount = 12500
);

WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  2,
  (month_start + interval '11 day')::date,
  time '08:30',
  5000,
  'DEBIT',
  'Credit card minimum due',
  'HDFC Credit Card',
  'Finance & Investment',
  'Card',
  FALSE, 0, 'LOW', FALSE,
  8, EXTRACT(DOW FROM (month_start + interval '11 day'))::int, EXTRACT(DOW FROM (month_start + interval '11 day'))::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 2
    AND t.merchant = 'HDFC Credit Card'
    AND t.transaction_date = (m.month_start + interval '11 day')::date
    AND t.amount = 5000
);

WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  3,
  (month_start + interval '1 day')::date,
  time '09:10',
  45000,
  'DEBIT',
  'Housing loan EMI payment',
  'LIC Housing Loan',
  'Finance & Investment',
  'Auto Debit',
  FALSE, 0, 'LOW', FALSE,
  9, EXTRACT(DOW FROM (month_start + interval '1 day'))::int, EXTRACT(DOW FROM (month_start + interval '1 day'))::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 3
    AND t.merchant = 'LIC Housing Loan'
    AND t.transaction_date = (m.month_start + interval '1 day')::date
    AND t.amount = 45000
);

WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  3,
  (month_start + interval '14 day')::date,
  time '09:25',
  22000,
  'DEBIT',
  'BMW auto finance installment',
  'BMW Financial',
  'Finance & Investment',
  'Auto Debit',
  FALSE, 0, 'LOW', FALSE,
  9, EXTRACT(DOW FROM (month_start + interval '14 day'))::int, EXTRACT(DOW FROM (month_start + interval '14 day'))::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 3
    AND t.merchant = 'BMW Financial'
    AND t.transaction_date = (m.month_start + interval '14 day')::date
    AND t.amount = 22000
);

-- Subscription seed transactions (monthly/yearly)
WITH m AS (
  SELECT generate_series(date '2025-01-01', date '2026-05-01', interval '1 month')::date AS month_start
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  x.user_id,
  (m.month_start + (x.day_offset || ' day')::interval)::date,
  time '07:30',
  x.amount,
  'DEBIT',
  x.description,
  x.merchant,
  x.category,
  'Card',
  FALSE, 0, 'LOW', FALSE,
  7, EXTRACT(DOW FROM (m.month_start + (x.day_offset || ' day')::interval))::int,
  EXTRACT(DOW FROM (m.month_start + (x.day_offset || ' day')::interval))::int IN (0, 6),
  FALSE
FROM m
JOIN (
  VALUES
    (1, 'Netflix India', 649::numeric, 12, 'OTT subscription', 'Entertainment'),
    (1, 'Spotify Premium', 119::numeric, 15, 'Music subscription', 'Entertainment'),
    (1, 'Swiggy One', 299::numeric, 4, 'Food membership', 'Food & Dining'),
    (1, 'Zee5 Premium', 599::numeric, 20, 'OTT subscription', 'Entertainment'),
    (1, 'CultFit', 999::numeric, 2, 'Gym membership', 'Healthcare'),
    (1, 'Adobe Creative', 1675::numeric, 25, 'Creative cloud plan', 'Bills & Utilities'),
    (1, 'LinkedIn Premium', 2299::numeric, 18, 'Career subscription', 'Finance & Investment'),
    (2, 'Hotstar Premium', 899::numeric, 8, 'OTT yearly add-on', 'Entertainment'),
    (2, 'LinkedIn Premium', 2299::numeric, 19, 'Career subscription', 'Finance & Investment'),
    (2, 'Apple iCloud', 75::numeric, 6, 'Cloud storage', 'Bills & Utilities'),
    (2, 'Audible India', 199::numeric, 11, 'Audiobook subscription', 'Entertainment'),
    (3, 'Netflix India', 649::numeric, 13, 'OTT subscription', 'Entertainment'),
    (3, 'Hotstar Premium', 899::numeric, 7, 'OTT subscription', 'Entertainment'),
    (3, 'Google One', 210::numeric, 9, 'Cloud storage', 'Bills & Utilities'),
    (3, 'iCloud+', 299::numeric, 6, 'Cloud storage', 'Bills & Utilities'),
    (3, 'Dropbox', 950::numeric, 21, 'Cloud storage', 'Bills & Utilities'),
    (3, 'LinkedIn Premium', 2299::numeric, 10, 'Career subscription', 'Finance & Investment'),
    (3, 'Coursera Plus', 3499::numeric, 14, 'Learning plan', 'Education'),
    (3, 'Cult.fit', 1499::numeric, 3, 'Fitness plan', 'Healthcare'),
    (3, 'Headspace', 999::numeric, 17, 'Meditation app', 'Healthcare')
) AS x(user_id, merchant, amount, day_offset, description, category) ON TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = x.user_id
    AND t.merchant = x.merchant
    AND t.transaction_date = (m.month_start + (x.day_offset || ' day')::interval)::date
    AND ABS(t.amount - x.amount) < 0.01
);

-- Arjun yearly Prime charges (two cycles for yearly detection)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  2,
  d::date,
  time '07:45',
  1499,
  'DEBIT',
  'Amazon Prime yearly renewal',
  'Amazon Prime',
  'Entertainment',
  'Card',
  FALSE, 0, 'LOW', FALSE,
  7, EXTRACT(DOW FROM d)::int, EXTRACT(DOW FROM d)::int IN (0, 6), FALSE
FROM (VALUES (date '2025-01-03'), (date '2026-01-03')) AS y(d)
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 2
    AND t.merchant = 'Amazon Prime'
    AND t.transaction_date = y.d
    AND ABS(t.amount - 1499) < 0.01
);

-- Priya extra Swiggy food orders (to make Swiggy One usage clearly active)
WITH d AS (
  SELECT generate_series(date '2026-04-01', date '2026-05-31', interval '3 day')::date AS txn_date
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  1,
  d.txn_date,
  time '20:10',
  320 + (EXTRACT(DAY FROM d.txn_date)::int % 7) * 35,
  'DEBIT',
  'Dinner order',
  'Swiggy',
  'Food & Dining',
  'UPI',
  FALSE, 0, 'LOW', FALSE,
  20, EXTRACT(DOW FROM d.txn_date)::int, EXTRACT(DOW FROM d.txn_date)::int IN (0, 6), FALSE
FROM d
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 1
    AND t.merchant = 'Swiggy'
    AND t.transaction_date = d.txn_date
    AND t.description = 'Dinner order'
);

-- Priya occasional fitness activity so CultFit lands in suspicious zone, not dead.
WITH d AS (
  SELECT generate_series(date '2026-04-05', date '2026-05-20', interval '14 day')::date AS txn_date
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description,
  merchant, category, payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT
  1,
  d.txn_date,
  time '18:40',
  250,
  'DEBIT',
  'Gym cafe and protein bar',
  'CultFit Cafe',
  'Healthcare',
  'UPI',
  FALSE, 0, 'LOW', FALSE,
  18, EXTRACT(DOW FROM d.txn_date)::int, EXTRACT(DOW FROM d.txn_date)::int IN (0, 6), FALSE
FROM d
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t
  WHERE t.user_id = 1
    AND t.merchant = 'CultFit Cafe'
    AND t.transaction_date = d.txn_date
    AND t.description = 'Gym cafe and protein bar'
);

-- Keep Priya subscription set aligned for demo (6 core subscriptions).
DELETE FROM transactions
WHERE user_id = 1
  AND merchant = 'Spotify Premium'
  AND description = 'Music subscription'
  AND transaction_date BETWEEN date '2025-01-01' AND date '2026-05-31';

-- Day 2 additions: Dark Pattern Detector
CREATE TABLE IF NOT EXISTS dark_patterns (
  id                SERIAL PRIMARY KEY,
  user_id           INTEGER REFERENCES users(id),
  merchant          VARCHAR(200),
  pattern_type      VARCHAR(50),
  description       TEXT,
  amount_involved   DECIMAL(12,2),
  potential_loss    DECIMAL(12,2),
  detected_date     DATE,
  evidence          JSONB,
  status            VARCHAR(20) DEFAULT 'ACTIVE',
  action_taken      TEXT,
  created_at        TIMESTAMP DEFAULT NOW()
);

-- Priya: free-trial trap
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2026-03-03', time '09:12', 1, 'DEBIT', 'Trial verification debit', 'CloudStore Pro',
       'Bills & Utilities', 'UPI', FALSE, 0, 'LOW', FALSE, 9, 2, FALSE, FALSE
WHERE NOT EXISTS (
  SELECT 1 FROM transactions
  WHERE user_id = 1 AND merchant = 'CloudStore Pro' AND transaction_date = date '2026-03-03' AND amount = 1
);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2026-04-03', time '09:20', 999, 'DEBIT', 'Auto-renewal after trial', 'CloudStore Pro',
       'Bills & Utilities', 'Card', FALSE, 0, 'LOW', FALSE, 9, 5, FALSE, FALSE
WHERE NOT EXISTS (
  SELECT 1 FROM transactions
  WHERE user_id = 1 AND merchant = 'CloudStore Pro' AND transaction_date = date '2026-04-03' AND amount = 999
);

-- Priya: duplicate charge
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2025-08-14', time '10:23', 1299, 'DEBIT', 'Electronics purchase', 'Amazon India',
       'Shopping', 'Card', FALSE, 0, 'LOW', FALSE, 10, 4, FALSE, FALSE
WHERE NOT EXISTS (
  SELECT 1 FROM transactions
  WHERE user_id = 1 AND merchant = 'Amazon India' AND transaction_date = date '2025-08-14'
    AND transaction_time = time '10:23' AND amount = 1299
);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2025-08-14', time '10:31', 1299, 'DEBIT', 'Duplicate debit', 'Amazon India',
       'Shopping', 'Card', FALSE, 0, 'LOW', FALSE, 10, 4, FALSE, FALSE
WHERE NOT EXISTS (
  SELECT 1 FROM transactions
  WHERE user_id = 1 AND merchant = 'Amazon India' AND transaction_date = date '2025-08-14'
    AND transaction_time = time '10:31' AND amount = 1299
);

-- Priya: silent price increase pattern
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2026-01-04', time '08:50', 299, 'DEBIT', 'Fitness plan basic', 'FitnessApp',
       'Healthcare', 'Card', FALSE, 0, 'LOW', FALSE, 8, 0, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 1 AND merchant = 'FitnessApp' AND transaction_date = date '2026-01-04' AND amount = 299);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2026-02-04', time '08:50', 349, 'DEBIT', 'Fitness plan revised', 'FitnessApp',
       'Healthcare', 'Card', FALSE, 0, 'LOW', FALSE, 8, 3, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 1 AND merchant = 'FitnessApp' AND transaction_date = date '2026-02-04' AND amount = 349);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2026-03-04', time '08:50', 399, 'DEBIT', 'Fitness plan revised', 'FitnessApp',
       'Healthcare', 'Card', FALSE, 0, 'LOW', FALSE, 8, 3, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 1 AND merchant = 'FitnessApp' AND transaction_date = date '2026-03-04' AND amount = 399);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2026-04-04', time '08:50', 449, 'DEBIT', 'Fitness plan revised', 'FitnessApp',
       'Healthcare', 'Card', FALSE, 0, 'LOW', FALSE, 8, 6, TRUE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 1 AND merchant = 'FitnessApp' AND transaction_date = date '2026-04-04' AND amount = 449);

-- Priya: rupee trap escalation
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2025-09-15', time '23:14', 1, 'DEBIT', 'Account verify request', 'unknown-9876543210@ybl',
       'Transfer', 'UPI', FALSE, 0, 'LOW', FALSE, 23, 1, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 1 AND merchant = 'unknown-9876543210@ybl' AND transaction_date = date '2025-09-15' AND amount = 1);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2025-09-17', time '11:10', 500, 'DEBIT', 'Second verification payment', 'unknown-9876543210@ybl',
       'Transfer', 'UPI', FALSE, 0, 'LOW', FALSE, 11, 3, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 1 AND merchant = 'unknown-9876543210@ybl' AND transaction_date = date '2025-09-17' AND amount = 500);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2025-09-20', time '12:25', 5000, 'DEBIT', 'Urgent settlement request', 'unknown-9876543210@ybl',
       'Transfer', 'UPI', FALSE, 0, 'LOW', FALSE, 12, 6, TRUE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 1 AND merchant = 'unknown-9876543210@ybl' AND transaction_date = date '2025-09-20' AND amount = 5000);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 1, date '2025-09-22', time '15:05', 15000, 'DEBIT', 'Final release payment', 'unknown-9876543210@ybl',
       'Transfer', 'UPI', FALSE, 0, 'LOW', FALSE, 15, 1, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 1 AND merchant = 'unknown-9876543210@ybl' AND transaction_date = date '2025-09-22' AND amount = 15000);

-- Arjun dark patterns
WITH m AS (
  SELECT generate_series(date '2025-10-05', date '2026-05-05', interval '1 month')::date AS d
)
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 2, d, time '07:10', 399, 'DEBIT', 'Magazine renewal', 'MagzterGold', 'Entertainment',
       'Card', FALSE, 0, 'LOW', FALSE, 7, EXTRACT(DOW FROM d)::int, EXTRACT(DOW FROM d)::int IN (0, 6), FALSE
FROM m
WHERE NOT EXISTS (SELECT 1 FROM transactions t WHERE t.user_id = 2 AND t.merchant = 'MagzterGold' AND t.transaction_date = m.d AND t.amount = 399);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 2, date '2026-02-10', time '02:30', 1, 'DEBIT', 'KYC verification', 'sbi-kyc-update@paytm', 'Transfer',
       'UPI', FALSE, 0, 'LOW', FALSE, 2, 2, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 2 AND merchant = 'sbi-kyc-update@paytm' AND transaction_date = date '2026-02-10' AND amount = 1);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 2, date '2026-03-10', time '09:02', 799, 'DEBIT', 'Auto-renew after trial', 'VPNSecure', 'Bills & Utilities',
       'Card', FALSE, 0, 'LOW', FALSE, 9, 2, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 2 AND merchant = 'VPNSecure' AND transaction_date = date '2026-03-10' AND amount = 799);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 2, date '2026-02-10', time '09:00', 1, 'DEBIT', 'Trial activation', 'VPNSecure', 'Bills & Utilities',
       'Card', FALSE, 0, 'LOW', FALSE, 9, 2, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 2 AND merchant = 'VPNSecure' AND transaction_date = date '2026-02-10' AND amount = 1);

-- Kavya dark patterns
INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 3, date '2026-01-15', time '10:30', 3499, 'DEBIT', 'Fashion purchase', 'Myntra', 'Shopping',
       'Card', FALSE, 0, 'LOW', FALSE, 10, 4, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 3 AND merchant = 'Myntra' AND transaction_date = date '2026-01-15' AND transaction_time = time '10:30' AND amount = 3499);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 3, date '2026-01-15', time '10:42', 3499, 'DEBIT', 'Duplicate fashion debit', 'Myntra', 'Shopping',
       'Card', FALSE, 0, 'LOW', FALSE, 10, 4, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 3 AND merchant = 'Myntra' AND transaction_date = date '2026-01-15' AND transaction_time = time '10:42' AND amount = 3499);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 3, date '2025-12-01', time '11:12', 1, 'DEBIT', 'Wallet verify', 'TradingApp', 'Finance & Investment',
       'UPI', FALSE, 0, 'LOW', FALSE, 11, 1, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 3 AND merchant = 'TradingApp' AND transaction_date = date '2025-12-01' AND amount = 1);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 3, date '2025-12-18', time '11:20', 500, 'DEBIT', 'Margin unlock', 'TradingApp', 'Finance & Investment',
       'UPI', FALSE, 0, 'LOW', FALSE, 11, 4, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 3 AND merchant = 'TradingApp' AND transaction_date = date '2025-12-18' AND amount = 500);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 3, date '2026-01-04', time '11:35', 5000, 'DEBIT', 'High leverage activation', 'TradingApp', 'Finance & Investment',
       'UPI', FALSE, 0, 'LOW', FALSE, 11, 0, TRUE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 3 AND merchant = 'TradingApp' AND transaction_date = date '2026-01-04' AND amount = 5000);

INSERT INTO transactions (
  user_id, transaction_date, transaction_time, amount, type, description, merchant, category,
  payment_method, anomaly_flag, risk_score, risk_level, ml_processed,
  hour_of_day, day_of_week, is_weekend, is_night_txn
)
SELECT 3, date '2026-01-15', time '08:05', 2, 'DEBIT', 'Prize claim verification', 'prize-claim-2025@upi', 'Transfer',
       'UPI', FALSE, 0, 'LOW', FALSE, 8, 4, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM transactions WHERE user_id = 3 AND merchant = 'prize-claim-2025@upi' AND transaction_date = date '2026-01-15' AND amount = 2);
