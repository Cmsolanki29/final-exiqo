-- FraudShield schema + pattern library + demo fraud_alerts
-- Run: psql -U postgres -d smartspend_db -f database/fraud_schema.sql

CREATE TABLE IF NOT EXISTS fraud_pattern_library (
  id              SERIAL PRIMARY KEY,
  pattern_name    VARCHAR(100) UNIQUE,
  pattern_type    VARCHAR(50),
  description     TEXT,
  warning_signs   JSONB,
  hinglish_warning TEXT,
  severity        VARCHAR(10) DEFAULT 'HIGH',
  created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fraud_alerts (
  id              SERIAL PRIMARY KEY,
  user_id         INTEGER REFERENCES users(id),
  transaction_id  INTEGER REFERENCES transactions(id),
  pattern_matched VARCHAR(100),
  risk_score      INTEGER,
  amount_at_risk  DECIMAL(12,2),
  warning_message TEXT,
  hinglish_explanation TEXT,
  user_action     VARCHAR(20) DEFAULT 'PENDING',
  money_saved     DECIMAL(12,2) DEFAULT 0,
  created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fraud_education (
  id              SERIAL PRIMARY KEY,
  user_id         INTEGER REFERENCES users(id),
  pattern_type    VARCHAR(50),
  learned_at      TIMESTAMP DEFAULT NOW()
);

INSERT INTO fraud_pattern_library
  (pattern_name, pattern_type, description, warning_signs, hinglish_warning, severity)
VALUES
(
  'SBI KYC Fraud',
  'KYC_FRAUD',
  'Fake bank official calls saying KYC update needed',
  '["Unknown UPI ID", "Amount requested for verification", "Urgency created", "Night time transaction"]'::jsonb,
  $$Real banks never ask for money over UPI for KYC. If someone claims to be SBI/HDFC/ICICI and demands payment, end the call and phone your bank on the official number.$$,
  'CRITICAL'
),
(
  'Lottery Prize Fraud',
  'LOTTERY_FRAUD',
  'You won a lottery — pay processing fee to claim prize',
  '["Small credit followed by large debit request", "Unknown sender", "Round amount", "Excitement created"]'::jsonb,
  $$You only win a lottery you actually entered. A small random credit followed by a large fee request is a classic scam.$$,
  'CRITICAL'
),
(
  'UPI Collect Request Fraud',
  'UPI_COLLECT',
  'Fraudster sends UPI collect request saying money will come',
  '["Collect request from unknown", "Told money will be received", "Actually money will be sent not received"]'::jsonb,
  $$Approving a UPI collect request sends money out—it does not deposit a refund. Only approve collect requests from people and merchants you trust.$$,
  'CRITICAL'
),
(
  'Part Time Job Fraud',
  'JOB_FRAUD',
  'Work from home job — pay registration fee first',
  '["Small payment to unknown", "Description has job/work/task", "Promise of returns"]'::jsonb,
  $$Legitimate employers rarely charge upfront registration, training, or equipment fees for basic work-from-home roles. Those fees are common scam signals.$$,
  'HIGH'
),
(
  'Bank Official Fraud',
  'BANK_OFFICIAL',
  'Fake bank employee asks to transfer to safe account',
  '["Transfer to unknown account", "Large amount", "Urgency", "First time payee"]'::jsonb,
  $$A genuine bank officer will never tell you to move money to a random safe account. Hang up and visit or call your branch through official channels.$$,
  'CRITICAL'
),
(
  'Money Doubling Fraud',
  'MONEY_DOUBLING',
  'Send money and get double in 48 hours',
  '["Round amount to unknown", "First time payee", "Large amount relative to income"]'::jsonb,
  $$Money does not double overnight. Promises of guaranteed high returns in days are almost always fraud—treat them as high risk.$$,
  'CRITICAL'
)
ON CONFLICT (pattern_name) DO NOTHING;

-- Demo fraud alerts (user_id 1=Priya, 2=Arjun, 3=Kavya). Idempotent by clearing demo rows optional — use unique pattern+user for upsert not trivial; delete old demo alerts by pattern names for these users.
DELETE FROM fraud_alerts
WHERE user_id IN (1, 2, 3)
  AND pattern_matched IN (
    'KYC_FRAUD', 'LOTTERY_FRAUD', 'UPI_COLLECT', 'JOB_FRAUD', 'BANK_OFFICIAL', 'MONEY_DOUBLING'
  );

INSERT INTO fraud_alerts
  (user_id, transaction_id, pattern_matched, risk_score, amount_at_risk, warning_message, hinglish_explanation, user_action, money_saved)
VALUES
(
  1, NULL, 'KYC_FRAUD', 96, 20501.00,
  'Escalating payments to sbi-kyc-helpline@ybl — classic KYC fraud.',
  $$This matched a KYC impersonation pattern: unknown UPI, late-night pushes, and escalating amounts. Confirm with your bank and avoid similar UPI IDs.$$,
  'PENDING', 0
),
(
  1, NULL, 'LOTTERY_FRAUD', 78, 2000.00,
  'Small credit then large debit request from prize-claim-2025@upi.',
  $$Lottery-style pattern detected: small inbound credit then a larger outbound fee. The payment was blocked and funds were protected.$$,
  'BLOCKED', 2000.00
),
(
  1, NULL, 'UPI_COLLECT', 92, 3499.00,
  'Collect request from refund-amazon@okaxis — may look like refund but sends money out.',
  $$Do not approve collect requests that pretend to be refunds—they move money out, not in. Genuine Amazon refunds post to your linked account.$$,
  'PENDING', 0
),
(
  2, NULL, 'JOB_FRAUD', 72, 500.00,
  'Registration fee to parttime-work@paytm for a job offer.',
  $$Typical job scam: upfront registration fee to unknown UPI. Legitimate hiring rarely works this way—this payment should have been avoided.$$,
  'ALLOWED', 0
),
(
  2, NULL, 'BANK_OFFICIAL', 94, 25000.00,
  'Large transfer to secure-account-hdfc@upi — fake safe account scam.',
  $$Fake safe-account transfer scam. The transfer was blocked in time and funds were saved. Never move savings to random accounts on phone instructions.$$,
  'BLOCKED', 25000.00
),
(
  3, NULL, 'MONEY_DOUBLING', 91, 50000.00,
  'Money doubling promise to double-money-invest@upi.',
  $$Money doubling is always a scam. The user recognised the pattern and blocked the transfer, saving a large amount.$$,
  'BLOCKED', 50000.00
);

-- Demo transactions for Priya KYC escalation + lottery credit (matches narrative)
INSERT INTO transactions (user_id, transaction_date, transaction_time, amount, type, description, merchant, category, payment_method)
SELECT 1, '2025-10-15'::date, '23:14:00'::time, 1, 'DEBIT', 'KYC verify', 'sbi-kyc-helpline@ybl', 'Other', 'UPI'
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t WHERE t.user_id = 1 AND t.merchant = 'sbi-kyc-helpline@ybl' AND t.transaction_date = '2025-10-15' AND t.amount = 1 AND t.type = 'DEBIT'
);
INSERT INTO transactions (user_id, transaction_date, transaction_time, amount, type, description, merchant, category, payment_method)
SELECT 1, '2025-10-15'::date, '23:45:00'::time, 500, 'DEBIT', 'KYC step 2', 'sbi-kyc-helpline@ybl', 'Other', 'UPI'
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t WHERE t.user_id = 1 AND t.merchant = 'sbi-kyc-helpline@ybl' AND t.transaction_date = '2025-10-15' AND t.amount = 500 AND t.type = 'DEBIT'
);
INSERT INTO transactions (user_id, transaction_date, transaction_time, amount, type, description, merchant, category, payment_method)
SELECT 1, '2025-10-16'::date, '00:12:00'::time, 5000, 'DEBIT', 'KYC final', 'sbi-kyc-helpline@ybl', 'Other', 'UPI'
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t WHERE t.user_id = 1 AND t.merchant = 'sbi-kyc-helpline@ybl' AND t.transaction_date = '2025-10-16' AND t.amount = 5000 AND t.type = 'DEBIT'
);
INSERT INTO transactions (user_id, transaction_date, transaction_time, amount, type, description, merchant, category, payment_method)
SELECT 1, '2025-10-16'::date, '00:34:00'::time, 15000, 'DEBIT', 'KYC unlock', 'sbi-kyc-helpline@ybl', 'Other', 'UPI'
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t WHERE t.user_id = 1 AND t.merchant = 'sbi-kyc-helpline@ybl' AND t.transaction_date = '2025-10-16' AND t.amount = 15000 AND t.type = 'DEBIT'
);

INSERT INTO transactions (user_id, transaction_date, transaction_time, amount, type, description, merchant, category, payment_method)
SELECT 1, '2025-10-14'::date, '10:00:00'::time, 500, 'CREDIT', 'Prize teaser credit', 'prize-claim-2025@upi', 'Other', 'UPI'
WHERE NOT EXISTS (
  SELECT 1 FROM transactions t WHERE t.user_id = 1 AND t.merchant = 'prize-claim-2025@upi' AND t.type = 'CREDIT' AND t.amount = 500
);
