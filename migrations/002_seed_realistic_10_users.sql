-- ============================================================
-- SMARTSPEND SEED DATA v2.0 — 10 USERS, 18 MONTHS HISTORY
-- File: migrations/002_seed_realistic_10_users.sql
-- Date range: 2024-12-01 → 2026-05-14
-- INTEGER user IDs (1-10), type=CREDIT/DEBIT (uppercase)
-- ============================================================

BEGIN;

-- ═════════════════════════════════════════════════════════════
-- SECTION 1 — USERS (IDs 1-10 fixed via OVERRIDING SYSTEM VALUE)
-- Password hash for "Demo@1234":
-- $2b$12$F1eHfBH6WfDrSCwt479UnuVKrkxsblBiwqTiqdleyAT0ZuVwh7JAW
-- ═════════════════════════════════════════════════════════════
INSERT INTO users (id, email, password_hash, name, monthly_income, bank, city, plan,
                   is_verified, onboarding_completed, created_at)
OVERRIDING SYSTEM VALUE VALUES
  (1,'vikram@smartspend.in',
   '$2b$12$F1eHfBH6WfDrSCwt479UnuVKrkxsblBiwqTiqdleyAT0ZuVwh7JAW',
   'Vikram Singh',   92000, 'HDFC',  'Pune',       'premium',true,true,'2024-11-15 10:00:00'),
  (2,'priya@smartspend.in',
   '$2b$12$F1eHfBH6WfDrSCwt479UnuVKrkxsblBiwqTiqdleyAT0ZuVwh7JAW',
   'Priya Mehta',    75000, 'ICICI', 'Mumbai',     'premium',true,true,'2024-11-18 11:30:00'),
  (3,'rahul@smartspend.in',
   '$2b$12$F1eHfBH6WfDrSCwt479UnuVKrkxsblBiwqTiqdleyAT0ZuVwh7JAW',
   'Rahul Sharma',   45000, 'Axis',  'Bengaluru',  'free',   true,true,'2024-12-01 09:15:00'),
  (4,'ananya@smartspend.in',
   '$2b$12$F1eHfBH6WfDrSCwt479UnuVKrkxsblBiwqTiqdleyAT0ZuVwh7JAW',
   'Ananya Iyer',   140000, 'SBI',   'Chennai',    'premium',true,true,'2024-10-20 14:00:00'),
  (5,'karan@smartspend.in',
   '$2b$12$F1eHfBH6WfDrSCwt479UnuVKrkxsblBiwqTiqdleyAT0ZuVwh7JAW',
   'Karan Malhotra', 60000, 'Kotak', 'Delhi',      'premium',true,true,'2024-12-05 08:45:00'),
  (6,'ghost1@internal.in','$2a$10$disabled',
   'Arjun Patel',    50000, 'HDFC',  'Hyderabad',  'free',   false,true,'2024-11-01 10:00:00'),
  (7,'ghost2@internal.in','$2a$10$disabled',
   'Neha Gupta',     20000, 'PNB',   'Jaipur',     'free',   false,true,'2024-11-10 12:00:00'),
  (8,'ghost3@internal.in','$2a$10$disabled',
   'Rohan Kumar',    45000, 'Axis',  'Ahmedabad',  'free',   false,true,'2024-12-01 09:00:00'),
  (9,'ghost4@internal.in','$2a$10$disabled',
   'Kavya Reddy',   100000, 'ICICI', 'Kolkata',    'free',   false,true,'2024-11-05 11:00:00'),
  (10,'ghost5@internal.in','$2a$10$disabled',
   'Siddharth Joshi',50000, 'Kotak', 'Lucknow',    'free',   false,true,'2024-12-10 10:30:00');

-- Reset the sequence so new signups start at id=11
SELECT setval('users_id_seq', 10, true);

-- ═════════════════════════════════════════════════════════════
-- SECTION 2 — EMIs (rich schema for computed layer)
-- ═════════════════════════════════════════════════════════════
INSERT INTO emis (id, user_id, loan_name, lender, principal_amount, emi_amount,
                  tenure_months, paid_months, start_date, next_due_date,
                  interest_rate, loan_type, status) VALUES
  -- Vikram
  (gen_random_uuid(),1,'iPhone 15 Pro Max','HDFC Bank',85000,7083,12,8,
   '2025-09-05','2026-06-05',0,'consumer_durable','active'),
  (gen_random_uuid(),1,'MacBook Air M2','HDFC Bank',140000,8916,24,3,
   '2026-02-05','2026-06-05',12.5,'consumer_durable','active'),
  -- Priya
  (gen_random_uuid(),2,'Home Renovation Loan','ICICI Bank',400000,15000,36,16,
   '2025-01-05','2026-06-05',11.5,'personal','active'),
  (gen_random_uuid(),2,'Honda Activa 6G','ICICI Bank',65000,4200,18,6,
   '2025-11-05','2026-06-05',9.5,'vehicle','active'),
  (gen_random_uuid(),2,'Personal Loan - Medical','ICICI Bank',75000,6800,12,2,
   '2026-03-06','2026-06-06',14.0,'personal','active'),
  -- Rahul
  (gen_random_uuid(),3,'Dell XPS Laptop','Axis Bank',35000,3200,12,5,
   '2025-12-05','2026-06-05',0,'consumer_durable','active'),
  -- Ananya
  (gen_random_uuid(),4,'Hyundai Creta SX','SBI Bank',800000,22000,60,18,
   '2024-11-05','2026-06-05',8.75,'vehicle','active'),
  -- Karan
  (gen_random_uuid(),5,'Sony Alpha A7 III','Kotak Bank',90000,5500,18,4,
   '2026-01-05','2026-06-05',10.5,'consumer_durable','active'),
  -- Ghost1 Arjun
  (gen_random_uuid(),6,'Bajaj Pulsar 150','HDFC Bank',75000,2800,30,14,
   '2025-03-05','2026-06-05',9.0,'vehicle','active'),
  -- Ghost3 Rohan
  (gen_random_uuid(),8,'Samsung Galaxy S24','Axis Bank',45000,3900,12,4,
   '2026-01-05','2026-06-05',0,'consumer_durable','active'),
  -- Ghost4 Kavya
  (gen_random_uuid(),9,'Maruti Swift ZXI','ICICI Bank',600000,18500,48,10,
   '2025-07-05','2026-06-05',8.5,'vehicle','active'),
  (gen_random_uuid(),9,'Education Loan - MBA','ICICI Bank',500000,12000,60,6,
   '2025-11-05','2026-06-05',10.0,'education','active'),
  -- Ghost5 Siddharth
  (gen_random_uuid(),10,'Home Furniture Set','Kotak Bank',60000,2500,24,8,
   '2025-09-05','2026-06-05',12.0,'consumer_durable','active');

-- ═════════════════════════════════════════════════════════════
-- SECTION 3 — SUBSCRIPTIONS (backend-compatible: merchant, billing_day)
-- ═════════════════════════════════════════════════════════════
INSERT INTO subscriptions (id, user_id, merchant, amount, billing_day, next_billing_date,
  category, status, sub_lifecycle, monthly_cost, times_charged, first_charged,
  last_charged, intelligence_category, is_pro) VALUES
  -- Vikram (id 1-6)
  (1,1,'Spotify Premium',       119, 14,'2026-06-14','music',       'active','active',119, 17,'2024-01-14','2026-05-14','entertainment',false),
  (2,1,'YouTube Premium',       129, 18,'2026-06-18','video',       'active','active',129, 29,'2023-06-18','2026-05-18','entertainment',false),
  (3,1,'ChatGPT Plus',         1999, 22,'2026-06-22','productivity', 'active','active',1999,19,'2023-11-22','2026-05-22','productivity', true),
  (4,1,'LinkedIn Premium',      999,  8,'2026-06-08','career',       'active','active',999, 26,'2024-03-08','2026-05-08','productivity', true),
  (5,1,'Canva Pro',             499, 11,'2026-05-22','design',       'active','active',499, 24,'2024-05-11','2026-05-11','productivity', true),
  (6,1,'Amazon Prime',          125, 20,'2026-06-20','shopping',     'active','active',125, 32,'2023-09-20','2026-05-20','shopping',    false),
  -- Priya (id 7-10)
  (7,2,'Netflix',               649,  7,'2026-06-07','video',        'active','active',649, 38,'2023-04-07','2026-05-07','entertainment',false),
  (8,2,'Spotify Family',        179, 15,'2026-06-15','music',        'active','active',179, 27,'2024-02-15','2026-05-15','entertainment',false),
  (9,2,'Amazon Prime',          125, 25,'2026-06-25','shopping',     'active','active',125, 43,'2022-11-25','2026-05-25','shopping',    false),
  (10,2,'Zepto Pass',            49, 12,'2026-06-12','grocery',      'active','active',49,  11,'2025-06-12','2026-05-12','grocery',     false),
  -- Rahul (id 11-12)
  (11,3,'Netflix Mobile',       199, 10,'2026-06-10','video',        'active','active',199, 14,'2025-03-10','2026-05-10','entertainment',false),
  (12,3,'JioSaavn Pro',          99, 20,'2026-06-20','music',        'active','active',99,  22,'2024-07-20','2026-05-20','entertainment',false),
  -- Ananya (id 13-17)
  (13,4,'Netflix 4K',           649,  5,'2026-06-05','video',        'active','active',649, 45,'2022-08-05','2026-05-05','entertainment',true),
  (14,4,'Spotify Premium',      119, 12,'2026-06-12','music',        'active','active',119, 53,'2021-12-12','2026-05-12','entertainment',false),
  (15,4,'Amazon Prime',         125, 25,'2026-06-25','shopping',     'active','active',125, 57,'2021-07-25','2026-05-25','shopping',    false),
  (16,4,'Adobe Creative Cloud',1675, 18,'2026-06-18','design',       'active','active',1675,40,'2023-01-18','2026-05-18','productivity', true),
  (17,4,'Zepto Pass',            49,  3,'2026-06-03','grocery',      'active','active',49,  16,'2025-01-03','2026-05-03','grocery',     false),
  -- Karan (id 18-20)
  (18,5,'Netflix',              649,  8,'2026-06-08','video',        'active','active',649, 31,'2023-10-08','2026-05-08','entertainment',false),
  (19,5,'YouTube Premium',      129, 22,'2026-06-22','video',        'active','active',129, 25,'2024-04-22','2026-05-22','entertainment',false),
  (20,5,'Amazon Prime',         125, 16,'2026-06-16','shopping',     'active','active',125, 47,'2022-06-16','2026-05-16','shopping',    false),
  -- Ghost1 Arjun (id 21-23)
  (21,6,'Hotstar Premium',      299,  6,'2026-06-06','video',        'active','active',299, 23,'2024-06-06','2026-05-06','entertainment',false),
  (22,6,'Swiggy One',           149, 14,'2026-06-14','food',         'active','active',149, 15,'2025-02-14','2026-05-14','food',        false),
  (23,6,'Spotify Premium',      119, 22,'2026-06-22','music',        'active','active',119, 20,'2024-09-22','2026-05-22','entertainment',false),
  -- Ghost2 Neha (id 24)
  (24,7,'Spotify Premium',      119, 18,'2026-06-18','music',        'active','active',119, 16,'2025-01-18','2026-05-18','entertainment',false),
  -- Ghost3 Rohan (id 25-26)
  (25,8,'Hotstar Premium',      299,  9,'2026-06-09','video',        'active','active',299, 20,'2024-09-09','2026-05-09','entertainment',false),
  (26,8,'Swiggy One',           149, 19,'2026-06-19','food',         'active','active',149, 14,'2025-03-19','2026-05-19','food',        false),
  -- Ghost4 Kavya (id 27-30)
  (27,9,'Netflix 4K',           649,  4,'2026-06-04','video',        'active','active',649, 49,'2022-04-04','2026-05-04','entertainment',true),
  (28,9,'Amazon Prime',         125, 17,'2026-06-17','shopping',     'active','active',125, 56,'2021-09-17','2026-05-17','shopping',    false),
  (29,9,'Spotify Premium',      119, 23,'2026-06-23','music',        'active','active',119, 35,'2023-06-23','2026-05-23','entertainment',false),
  (30,9,'Duolingo Plus',        533, 11,'2026-06-11','education',    'active','active',533, 18,'2024-11-11','2026-05-11','education',   true),
  -- Ghost5 Siddharth (id 31-33)
  (31,10,'Hotstar Premium',     299, 13,'2026-06-13','video',        'active','active',299, 19,'2024-10-13','2026-05-13','entertainment',false),
  (32,10,'Zepto Pass',           49, 21,'2026-06-21','grocery',      'active','active',49,  13,'2025-04-21','2026-05-21','grocery',     false),
  (33,10,'Amazon Prime',        125, 27,'2026-05-27','shopping',     'active','active',125, 38,'2023-03-27','2026-05-27','shopping',    false);

-- Reset subscriptions sequence
SELECT setval('subscriptions_id_seq', 33, true);

-- ═════════════════════════════════════════════════════════════
-- SECTION 4 — TRANSACTIONS (18 months, all 10 users)
-- type=CREDIT/DEBIT, merchant column, integer user_id
-- ~45 transactions/month for main users
-- ═════════════════════════════════════════════════════════════
DO $$
DECLARE
  v_m        DATE;     -- month start
  v_mo       INT;      -- month 1-12
  v_yr       INT;      -- year
  v_vf       NUMERIC;  -- festival multiplier
  v_vx       NUMERIC;  -- monthly variance 0.88–1.12
  v_last_day DATE;     -- cutoff (May 14 for May 2026)
BEGIN
  FOR v_m IN
    SELECT d::DATE
    FROM generate_series('2024-12-01'::DATE,'2026-05-01'::DATE,'1 month'::INTERVAL) d
  LOOP
    v_yr  := EXTRACT(YEAR  FROM v_m)::INT;
    v_mo  := EXTRACT(MONTH FROM v_m)::INT;
    v_vf  := CASE WHEN v_mo=10 THEN 1.65 WHEN v_mo=3 THEN 1.22
                  WHEN v_mo=4 THEN 1.12  WHEN v_mo=12 THEN 1.18
                  ELSE 1.00 END;
    v_last_day := CASE WHEN v_m='2026-05-01' THEN '2026-05-14'::DATE
                       ELSE (v_m + INTERVAL '1 month - 1 day')::DATE END;

    -- ── USER 1: VIKRAM SINGH (₹92,000 · Pune) ────────────────
    v_vx := 0.88 + ((v_mo * 7 + 3) % 25)::NUMERIC / 100;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name)
    VALUES(1,v_m,'09:00:00',92000,'CREDIT','Salary Credit - Vikram Singh','HDFC Bank','salary','NEFT',true,'HDFC');

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(1,v_m+1,'10:00:00',22000,'DEBIT','Monthly Rent Kothrud','Ravi Property Management','rent','NEFT',true);

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(1,v_m+2,'11:00:00',
      ROUND(CASE WHEN v_mo IN(4,5,6) THEN 2200 WHEN v_mo IN(7,8,9) THEN 1900 ELSE 1600 END * v_vx),
      'DEBIT','Electricity Bill Pune','MSEDCL','utilities','UPI',true);

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(1,v_m+3,'11:30:00',999,'DEBIT','Internet Plan 300Mbps','JioFiber','utilities','UPI',true);

    IF v_m >= '2025-09-01' THEN
      INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
      VALUES(1,v_m+4,'09:00:00',7083,'DEBIT','EMI iPhone 15 Pro Max','HDFC Bank','emi','AutoDebit',true);
    END IF;
    IF v_m >= '2026-02-01' THEN
      INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
      VALUES(1,v_m+4,'09:05:00',8916,'DEBIT','EMI MacBook Air M2','HDFC Bank','emi','AutoDebit',true);
    END IF;

    IF v_m+7  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(1,v_m+7, '08:00:00',999, 'DEBIT','LinkedIn Premium','LinkedIn','subscription','UPI',true); END IF;
    IF v_m+10 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(1,v_m+10,'08:00:00',499, 'DEBIT','Canva Pro','Canva','subscription','UPI',true); END IF;
    IF v_m+13 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(1,v_m+13,'08:00:00',119, 'DEBIT','Spotify Premium','Spotify','subscription','UPI',true); END IF;
    IF v_m+17 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(1,v_m+17,'08:00:00',129, 'DEBIT','YouTube Premium','YouTube','subscription','UPI',true); END IF;
    IF v_m+19 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(1,v_m+19,'08:00:00',125, 'DEBIT','Amazon Prime','Amazon Prime','subscription','UPI',true); END IF;
    IF v_m+21 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(1,v_m+21,'08:00:00',1999,'DEBIT','ChatGPT Plus','OpenAI','subscription','UPI',true); END IF;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 1,v_m+day,
      ('1'||LPAD((8+day*3%12)::text,1,'0')||':00:00')::TIME,
      ROUND(base*v_vx*v_vf),'DEBIT','Food Order',merch,'food_delivery','UPI',false
    FROM (VALUES
      (1,'Swiggy',380),(3,'Zomato',445),(5,'Swiggy',290),(7,'Zomato',520),
      (9,'Swiggy',320),(11,'Zomato',410),(13,'Swiggy',480),(15,'Zomato',350),
      (17,'Swiggy',560),(19,'Zomato',300),(22,'Swiggy',430),(25,'Zomato',395)
    ) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 1,v_m+day,'10:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Ride',merch,'transport','UPI',false
    FROM (VALUES
      (2,'Ola Cabs',220),(4,'Uber',185),(6,'Ola Cabs',340),(8,'Uber',165),
      (10,'Ola Cabs',280),(12,'Rapido',95),(14,'Uber',210),(17,'Ola Cabs',250),
      (20,'Uber',195),(24,'Ola Cabs',310)
    ) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 1,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false
    FROM (VALUES (3,'BigBasket',1850),(8,'DMart',2200),(13,'Zepto',1600),(19,'BigBasket',2050),(26,'DMart',1750)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 1,v_m+day,'14:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false
    FROM (VALUES (6,'Amazon',2200),(12,'Flipkart',1800),(18,'Myntra',3200),(24,'Amazon',1500)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 1,v_m+day,'12:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Medical',merch,'medical','UPI',false
    FROM (VALUES (10,'Apollo Pharmacy',750),(22,'Practo',900)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 1,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false
    FROM (VALUES (7,'PVR Cinemas',800),(15,'BookMyShow',650),(23,'Inox',1100)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 1,v_m+day,'08:30:00'::TIME,ROUND(base*v_vx),'DEBIT','Petrol',merch,'petrol','UPI',false
    FROM (VALUES (8,'HP Petrol Kothrud',2000),(16,'BPCL Pune',1850),(24,'Indian Oil Pune',2150)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 2: PRIYA MEHTA (₹75,000 · Mumbai) ───────────────
    v_vx := 0.88 + ((v_mo * 11 + 3) % 25)::NUMERIC / 100;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name)
    VALUES(2,v_m,'09:00:00',75000,'CREDIT','Salary Credit - Priya Mehta','ICICI Bank','salary','NEFT',true,'ICICI');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(2,v_m+1,'10:00:00',28000,'DEBIT','Monthly Rent Andheri West','Andheri Housing Society','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(2,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(4,5,6) THEN 1800 WHEN v_mo IN(7,8,9) THEN 1600 ELSE 1400 END*v_vx),'DEBIT','Electricity Bill','MSEDCL Mumbai','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(2,v_m+3,'11:30:00',799,'DEBIT','Airtel Broadband','Airtel Broadband','utilities','UPI',true);

    IF v_m >= '2025-01-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(2,v_m+4,'09:00:00',15000,'DEBIT','EMI Home Renovation','ICICI Bank','emi','AutoDebit',true); END IF;
    IF v_m >= '2025-11-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(2,v_m+4,'09:05:00',4200,'DEBIT','EMI Honda Activa','ICICI Bank','emi','AutoDebit',true); END IF;
    IF v_m >= '2026-03-01' AND v_m+5 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(2,v_m+5,'09:00:00',6800,'DEBIT','EMI Personal Loan','ICICI Bank','emi','AutoDebit',true); END IF;

    IF v_m+6  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(2,v_m+6, '08:00:00',649,'DEBIT','Netflix Standard','Netflix','subscription','UPI',true); END IF;
    IF v_m+11 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(2,v_m+11,'08:00:00',49, 'DEBIT','Zepto Pass','Zepto','subscription','UPI',true); END IF;
    IF v_m+14 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(2,v_m+14,'08:00:00',179,'DEBIT','Spotify Family','Spotify','subscription','UPI',true); END IF;
    IF v_m+24 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(2,v_m+24,'08:00:00',125,'DEBIT','Amazon Prime','Amazon Prime','subscription','UPI',true); END IF;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 2,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food Order',merch,'food_delivery','UPI',false
    FROM (VALUES (2,'Zomato',360),(5,'Swiggy',420),(8,'Zomato',290),(11,'Swiggy',490),(14,'Zomato',330),(16,'Swiggy',410),(19,'Zomato',380),(21,'Swiggy',450),(24,'Zomato',310),(27,'Swiggy',395)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 2,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Transport',merch,'transport','UPI',false
    FROM (VALUES (2,'Mumbai Local',180),(4,'Ola Cabs',220),(5,'Auto Rickshaw',85),(7,'Mumbai Local',180),(9,'Uber',195),(11,'Auto Rickshaw',95),(13,'Mumbai Local',180),(15,'Ola Cabs',260),(17,'Auto Rickshaw',75),(19,'Mumbai Local',180),(22,'Uber',210),(25,'Auto Rickshaw',90)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 2,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false
    FROM (VALUES (4,'BigBasket',1650),(9,'DMart Andheri',1900),(14,'Zepto',1400),(19,'BigBasket',1750),(25,'DMart Andheri',2100)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 2,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false
    FROM (VALUES (7,'Myntra',2800),(14,'Amazon',1600),(22,'Nykaa',1200)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 2,v_m+day,'12:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Medical',merch,'medical','UPI',false
    FROM (VALUES (9,'Apollo Pharmacy Mumbai',650),(21,'Medlife',480)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 2,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false
    FROM (VALUES (8,'PVR Phoenix Mumbai',750),(19,'BookMyShow',550)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 3: RAHUL SHARMA (₹45,000 · Bengaluru) ───────────
    v_vx := 0.88 + ((v_mo * 5 + 3) % 25)::NUMERIC / 100;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name)
    VALUES(3,v_m,'09:00:00',45000,'CREDIT','Salary Credit - Rahul Sharma','Axis Bank','salary','NEFT',true,'Axis');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(3,v_m+1,'10:00:00',15000,'DEBIT','Monthly Rent Koramangala','Koramangala PG','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(3,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(4,5,6) THEN 950 WHEN v_mo IN(7,8,9) THEN 750 ELSE 700 END*v_vx),'DEBIT','Electricity Bill Bengaluru','BESCOM','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(3,v_m+3,'11:30:00',799,'DEBIT','Airtel Broadband','Airtel Broadband Bengaluru','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 3,v_m+5,'10:00:00'::TIME,239,'DEBIT','Jio Mobile Recharge','Jio Mobile','utilities','UPI',true WHERE v_m+5 <= v_last_day;

    IF v_m >= '2025-12-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(3,v_m+4,'09:00:00',3200,'DEBIT','EMI Dell XPS Laptop','Axis Bank','emi','AutoDebit',true); END IF;
    IF v_m+9  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(3,v_m+9, '08:00:00',199,'DEBIT','Netflix Mobile','Netflix','subscription','UPI',true); END IF;
    IF v_m+19 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(3,v_m+19,'08:00:00',99, 'DEBIT','JioSaavn Pro','JioSaavn','subscription','UPI',true); END IF;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 3,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food Order',merch,'food_delivery','UPI',false
    FROM (VALUES (3,'Swiggy',245),(7,'Zomato',290),(10,'Swiggy',220),(13,'Zomato',310),(17,'Swiggy',270),(20,'Zomato',195),(23,'Swiggy',285),(27,'Zomato',250)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 3,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Transport',merch,'transport','UPI',false
    FROM (VALUES (2,'Namma Metro',65),(4,'Ola Cabs',120),(6,'Namma Metro',65),(8,'Rapido',80),(10,'Namma Metro',65),(12,'Ola Cabs',145),(15,'Namma Metro',65),(18,'Rapido',90),(21,'Namma Metro',65),(25,'Ola Cabs',135)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 3,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false
    FROM (VALUES (4,'BigBasket',1200),(9,'More Supermarket',1050),(14,'Zepto',980),(20,'BigBasket',1150),(26,'DMart Bengaluru',1300)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 3,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false
    FROM (VALUES (10,'Amazon',1150),(21,'Flipkart',950)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 3,v_m+12,'12:00:00'::TIME,ROUND(480*v_vx),'DEBIT','Medical','MedPlus Bengaluru','medical','UPI',false WHERE v_m+12 <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 3,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false
    FROM (VALUES (9,'PVR Forum Bengaluru',380),(22,'BookMyShow',320)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 4: ANANYA IYER (₹1,40,000 · Chennai) ────────────
    v_vx := 0.88 + ((v_mo * 13 + 3) % 25)::NUMERIC / 100;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name)
    VALUES(4,v_m,'09:00:00',140000,'CREDIT','Salary Credit - Ananya Iyer','SBI Bank','salary','NEFT',true,'SBI');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(4,v_m+1,'10:00:00',25000,'DEBIT','Monthly Rent Chennai','Boat Club Apartments','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(4,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(4,5,6) THEN 3200 WHEN v_mo IN(3,7,8,9) THEN 2600 ELSE 2000 END*v_vx),'DEBIT','Electricity Bill Chennai','TNEB','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(4,v_m+3,'11:30:00',999,'DEBIT','JioFiber 500Mbps','JioFiber Chennai','utilities','UPI',true);

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(4,v_m+4,'09:00:00',22000,'DEBIT','EMI Hyundai Creta SX','SBI Bank','emi','AutoDebit',true);

    IF v_m+5  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(4,v_m+5, '08:00:00',649, 'DEBIT','Netflix 4K','Netflix','subscription','UPI',true); END IF;
    IF v_m+11 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(4,v_m+11,'08:00:00',119, 'DEBIT','Spotify Premium','Spotify','subscription','UPI',true); END IF;
    IF v_m+3  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(4,v_m+3, '08:05:00',49,  'DEBIT','Zepto Pass','Zepto','subscription','UPI',true); END IF;
    IF v_m+17 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(4,v_m+17,'08:00:00',1675,'DEBIT','Adobe Creative Cloud','Adobe','subscription','UPI',true); END IF;
    IF v_m+24 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(4,v_m+24,'08:00:00',125, 'DEBIT','Amazon Prime','Amazon Prime','subscription','UPI',true); END IF;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 4,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food Order',merch,'food_delivery','UPI',false
    FROM (VALUES (2,'Swiggy',480),(4,'Zomato',560),(6,'Swiggy',430),(8,'Zomato',620),(10,'Swiggy',510),(12,'Zomato',490),(15,'Swiggy',580),(17,'Zomato',445),(20,'Swiggy',660),(22,'Zomato',520),(25,'Swiggy',475),(27,'Zomato',540)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 4,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Cab',merch,'transport','UPI',false
    FROM (VALUES (3,'Ola Prime',320),(6,'Uber Premier',280),(9,'Ola Prime',350),(12,'Uber Premier',310),(16,'Ola Prime',290),(19,'Uber Premier',360),(22,'Ola Prime',305),(26,'Uber Premier',275)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 4,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false
    FROM (VALUES (3,'BigBasket',2500),(7,'Spencer''s Chennai',2200),(11,'Zepto',1800),(16,'BigBasket',2800),(21,'DMart Chennai',2400),(27,'Spencer''s Chennai',2100)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 4,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false
    FROM (VALUES (6,'Amazon',4200),(10,'Flipkart',3500),(15,'Myntra',2800),(20,'Nykaa',1900),(25,'Amazon',5500)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 4,v_m+day,'12:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Medical',merch,'medical','UPI',false
    FROM (VALUES (8,'Apollo Pharmacy Chennai',1200),(20,'Thyrocare',1800)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 4,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false
    FROM (VALUES (7,'PVR Chennai',1200),(13,'BookMyShow',2200),(19,'Escape Rooms',1800),(26,'Bowling Company',1400)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 4,v_m+day,'10:00:00'::TIME,ROUND(base*v_vx),'DEBIT','SIP Investment',merch,'investment','NEFT',true
    FROM (VALUES (5,'Zerodha - Nifty 50 SIP',10000),(10,'Groww - ELSS Fund',5000)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 4,v_m+day,'08:30:00'::TIME,ROUND(base*v_vx),'DEBIT','Petrol',merch,'petrol','UPI',false
    FROM (VALUES (7,'IOC Pump Anna Nagar',2200),(15,'HP Station Chennai',2500),(23,'BPCL Adyar',2100)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 5: KARAN MALHOTRA (₹60,000 · Delhi) ─────────────
    v_vx := 0.88 + ((v_mo * 9 + 3) % 25)::NUMERIC / 100;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name)
    VALUES(5,v_m,'09:00:00',60000,'CREDIT','Salary Credit - Karan Malhotra','Kotak Bank','salary','NEFT',true,'Kotak');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(5,v_m+1,'10:00:00',20000,'DEBIT','Monthly Rent Lajpat Nagar','Lajpat Nagar Landlord','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(5,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(5,6,7,8) THEN 1800 WHEN v_mo IN(11,12,1) THEN 1200 ELSE 1400 END*v_vx),'DEBIT','Electricity Bill Delhi','BSES Delhi','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    VALUES(5,v_m+3,'11:30:00',499,'DEBIT','ACT Fibernet','ACT Fibernet Delhi','utilities','UPI',true);

    IF v_m >= '2026-01-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(5,v_m+4,'09:00:00',5500,'DEBIT','EMI Sony Alpha A7 III','Kotak Bank','emi','AutoDebit',true); END IF;
    IF v_m+7  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(5,v_m+7, '08:00:00',649,'DEBIT','Netflix Standard','Netflix','subscription','UPI',true); END IF;
    IF v_m+15 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(5,v_m+15,'08:00:00',125,'DEBIT','Amazon Prime','Amazon Prime','subscription','UPI',true); END IF;
    IF v_m+21 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(5,v_m+21,'08:00:00',129,'DEBIT','YouTube Premium','YouTube','subscription','UPI',true); END IF;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 5,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food Order',merch,'food_delivery','UPI',false
    FROM (VALUES (2,'Swiggy',320),(5,'Zomato',280),(8,'Swiggy',380),(11,'Zomato',350),(14,'Swiggy',290),(17,'Zomato',420),(20,'Swiggy',310),(22,'Zomato',370),(24,'Swiggy',340),(27,'Zomato',300)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 5,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Transport',merch,'transport','UPI',false
    FROM (VALUES (2,'Delhi Metro',95),(4,'Ola Cabs',180),(6,'Delhi Metro',95),(8,'Uber',160),(10,'Delhi Metro',95),(13,'Ola Cabs',220),(15,'Delhi Metro',95),(18,'Rapido',85),(21,'Delhi Metro',95),(25,'Uber',175)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 5,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false
    FROM (VALUES (4,'BigBasket',1550),(9,'DMart Delhi',1800),(14,'Zepto',1300),(19,'BigBasket',1700),(25,'Nature''s Basket',2000)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 5,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false
    FROM (VALUES (8,'Amazon',2100),(16,'Flipkart',1650),(24,'Myntra',2400)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 5,v_m+11,'12:00:00'::TIME,ROUND(620*v_vx),'DEBIT','Medical','Apollo Pharmacy Delhi','medical','UPI',false WHERE v_m+11 <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 5,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false
    FROM (VALUES (7,'PVR Saket Delhi',850),(16,'BookMyShow',700),(23,'Smaaash Bowling',900)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring)
    SELECT 5,v_m+day,'08:30:00'::TIME,ROUND(base*v_vx),'DEBIT','Petrol',merch,'petrol','UPI',false
    FROM (VALUES (9,'HP Pump Lajpat Nagar',1850),(18,'BPCL Pump Delhi',1750),(26,'IOC Delhi',1900)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 6: ARJUN PATEL Ghost1 (₹50,000 · Hyderabad) ─────
    v_vx := 0.88 + ((v_mo * 3 + 3) % 25)::NUMERIC / 100;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name) VALUES(6,v_m,'09:00:00',50000,'CREDIT','Salary','HDFC Bank','salary','NEFT',true,'HDFC');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(6,v_m+1,'10:00:00',12000,'DEBIT','Rent Madhapur','Madhapur Flat Owner','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(6,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(4,5,6) THEN 1100 WHEN v_mo IN(7,8,9) THEN 950 ELSE 800 END*v_vx),'DEBIT','Electricity','TSSPDCL','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(6,v_m+3,'11:30:00',499,'DEBIT','Internet','Airtel Broadband','utilities','UPI',true);
    IF v_m >= '2025-03-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(6,v_m+4,'09:00:00',2800,'DEBIT','EMI Bajaj Pulsar','HDFC Bank','emi','AutoDebit',true); END IF;
    IF v_m+5  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(6,v_m+5, '08:00:00',299,'DEBIT','Hotstar Premium','Hotstar','subscription','UPI',true); END IF;
    IF v_m+13 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(6,v_m+13,'08:00:00',149,'DEBIT','Swiggy One','Swiggy One','subscription','UPI',true); END IF;
    IF v_m+21 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(6,v_m+21,'08:00:00',119,'DEBIT','Spotify Premium','Spotify','subscription','UPI',true); END IF;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 6,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food',merch,'food_delivery','UPI',false FROM (VALUES (2,'Swiggy',260),(5,'Zomato',300),(9,'Swiggy',240),(12,'Zomato',280),(15,'Swiggy',310),(18,'Zomato',255),(21,'Swiggy',290),(24,'Zomato',270),(27,'Swiggy',285)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 6,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Transport',merch,'transport','UPI',false FROM (VALUES (2,'HMTS Bus',50),(4,'Ola Cabs',160),(6,'HMTS Bus',50),(8,'Rapido',90),(11,'HMTS Bus',50),(14,'Ola Cabs',175),(17,'Rapido',80),(20,'Ola Cabs',140),(24,'HMTS Bus',50)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 6,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false FROM (VALUES (4,'BigBasket',1350),(10,'Ratnadeep',1200),(16,'Zepto',1050),(22,'BigBasket',1400),(27,'DMart Hyderabad',1300)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 6,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false FROM (VALUES (9,'Amazon',1450),(21,'Flipkart',1100)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 6,v_m+13,'12:00:00'::TIME,ROUND(520*v_vx),'DEBIT','Medical','MedPlus Hyderabad','medical','UPI',false WHERE v_m+13 <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 6,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false FROM (VALUES (10,'PVR Hyderabad',650),(22,'BookMyShow',500)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 6,v_m+day,'08:30:00'::TIME,ROUND(base*v_vx),'DEBIT','Petrol',merch,'petrol','UPI',false FROM (VALUES (8,'HP Pump Madhapur',1600),(20,'BPCL Hyderabad',1500)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 7: NEHA GUPTA Ghost2 (₹20,000 · Jaipur) ─────────
    v_vx := 0.88 + ((v_mo * 2 + 3) % 25)::NUMERIC / 100;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name) VALUES(7,v_m,'09:00:00',20000,'CREDIT','Salary','PNB Bank','salary','NEFT',true,'PNB');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(7,v_m+1,'10:00:00',5000,'DEBIT','PG Rent','PG Vaishali Nagar','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(7,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(4,5,6,7) THEN 550 ELSE 380 END*v_vx),'DEBIT','Electricity','JVVNL Jaipur','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(7,v_m+3,'11:30:00',199,'DEBIT','BSNL Internet','BSNL Broadband','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 7,v_m+5,'10:00:00'::TIME,179,'DEBIT','Jio Recharge','Jio Mobile','utilities','UPI',true WHERE v_m+5 <= v_last_day;
    IF v_m+17 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(7,v_m+17,'08:00:00',119,'DEBIT','Spotify Premium','Spotify','subscription','UPI',true); END IF;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 7,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food',merch,'food_delivery','UPI',false FROM (VALUES (4,'Swiggy',155),(8,'Zomato',180),(12,'Swiggy',140),(17,'Zomato',165),(22,'Swiggy',150),(26,'Zomato',175)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 7,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Transport',merch,'transport','UPI',false FROM (VALUES (2,'RSRTC Bus',45),(4,'Auto Rickshaw',80),(6,'RSRTC Bus',45),(8,'Auto Rickshaw',70),(10,'RSRTC Bus',45),(13,'Auto Rickshaw',90),(15,'RSRTC Bus',45),(18,'Auto Rickshaw',75),(21,'RSRTC Bus',45),(24,'Auto Rickshaw',85),(27,'RSRTC Bus',45)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 7,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false FROM (VALUES (5,'Bazar Store Jaipur',800),(12,'Reliance Smart',750),(19,'Zepto',700),(26,'Local Kirana',650)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 7,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false FROM (VALUES (14,'Meesho',550),(27,'Amazon',650)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 7,v_m+16,'12:00:00'::TIME,ROUND(280*v_vx),'DEBIT','Medical','Jan Aushadhi Store','medical','UPI',false WHERE v_m+16 <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 7,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false FROM (VALUES (11,'Raj Mandir Cinema',250),(24,'Local Event',180)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 8: ROHAN KUMAR Ghost3 (₹45,000 · Ahmedabad) ──────
    v_vx := 0.88 + ((v_mo * 6 + 3) % 25)::NUMERIC / 100;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name) VALUES(8,v_m,'09:00:00',45000,'CREDIT','Salary','Axis Bank','salary','NEFT',true,'Axis');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(8,v_m+1,'10:00:00',13000,'DEBIT','Rent Navrangpura','Navrangpura Flat Owner','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(8,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(4,5,6,7) THEN 1050 ELSE 780 END*v_vx),'DEBIT','Electricity','PGVCL Ahmedabad','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(8,v_m+3,'11:30:00',499,'DEBIT','JioFiber','JioFiber Ahmedabad','utilities','UPI',true);
    IF v_m >= '2026-01-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(8,v_m+4,'09:00:00',3900,'DEBIT','EMI Samsung Galaxy S24','Axis Bank','emi','AutoDebit',true); END IF;
    IF v_m+8  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(8,v_m+8, '08:00:00',299,'DEBIT','Hotstar Premium','Hotstar','subscription','UPI',true); END IF;
    IF v_m+18 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(8,v_m+18,'08:00:00',149,'DEBIT','Swiggy One','Swiggy One','subscription','UPI',true); END IF;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 8,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food',merch,'food_delivery','UPI',false FROM (VALUES (2,'Swiggy',250),(5,'Zomato',280),(8,'Swiggy',230),(11,'Zomato',300),(14,'Swiggy',260),(17,'Zomato',240),(20,'Swiggy',275),(23,'Zomato',255),(26,'Swiggy',265)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 8,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Transport',merch,'transport','UPI',false FROM (VALUES (3,'AMTS Bus',40),(5,'Ola Cabs',140),(7,'AMTS Bus',40),(9,'Rapido',85),(12,'AMTS Bus',40),(14,'Ola Cabs',155),(17,'Rapido',75),(20,'AMTS Bus',40),(23,'Ola Cabs',130),(26,'AMTS Bus',40)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 8,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false FROM (VALUES (4,'BigBasket',1200),(10,'Reliance Smart',1100),(16,'Zepto',950),(22,'DMart Ahmedabad',1300),(27,'BigBasket',1050)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 8,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false FROM (VALUES (8,'Amazon',1050),(21,'Flipkart',900)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 8,v_m+day,'12:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Medical',merch,'medical','UPI',false FROM (VALUES (12,'Apollo Pharmacy Ahmedabad',480),(24,'Generic Pharmacy',320)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 8,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false FROM (VALUES (9,'INOX Ahmedabad',450),(22,'BookMyShow',380)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 8,v_m+day,'08:30:00'::TIME,ROUND(base*v_vx),'DEBIT','Petrol',merch,'petrol','UPI',false FROM (VALUES (7,'HP Pump Ahmedabad',1400),(21,'BPCL Ahmedabad',1350)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 9: KAVYA REDDY Ghost4 (₹1,00,000 · Kolkata) ─────
    v_vx := 0.88 + ((v_mo * 15 + 3) % 25)::NUMERIC / 100;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name) VALUES(9,v_m,'09:00:00',100000,'CREDIT','Salary','ICICI Bank','salary','NEFT',true,'ICICI');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+1,'10:00:00',22000,'DEBIT','Rent Salt Lake','Salt Lake Apartment','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(4,5,6,7,8) THEN 2200 ELSE 1600 END*v_vx),'DEBIT','Electricity','CESC Kolkata','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+3,'11:30:00',799,'DEBIT','Airtel Broadband','Airtel Kolkata','utilities','UPI',true);
    IF v_m >= '2025-07-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+4,'09:00:00',18500,'DEBIT','EMI Maruti Swift','ICICI Bank','emi','AutoDebit',true); END IF;
    IF v_m >= '2025-11-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+4,'09:05:00',12000,'DEBIT','EMI Education Loan','ICICI Bank','emi','AutoDebit',true); END IF;
    IF v_m+3  <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+3, '08:05:00',649,'DEBIT','Netflix 4K','Netflix','subscription','UPI',true); END IF;
    IF v_m+10 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+10,'08:00:00',533,'DEBIT','Duolingo Plus','Duolingo','subscription','UPI',true); END IF;
    IF v_m+16 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+16,'08:00:00',125,'DEBIT','Amazon Prime','Amazon Prime','subscription','UPI',true); END IF;
    IF v_m+22 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(9,v_m+22,'08:00:00',119,'DEBIT','Spotify Premium','Spotify','subscription','UPI',true); END IF;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 9,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food',merch,'food_delivery','UPI',false FROM (VALUES (2,'Swiggy',440),(4,'Zomato',510),(6,'Swiggy',390),(8,'Zomato',550),(11,'Swiggy',470),(14,'Zomato',420),(17,'Swiggy',490),(20,'Zomato',460),(22,'Swiggy',530),(25,'Zomato',410),(27,'Swiggy',480)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 9,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Transport',merch,'transport','UPI',false FROM (VALUES (2,'Kolkata Metro',55),(4,'Ola Cabs',220),(6,'Kolkata Metro',55),(8,'Uber',195),(10,'Kolkata Metro',55),(13,'Ola Cabs',250),(16,'Kolkata Metro',55),(19,'Uber',210),(22,'Kolkata Metro',55),(25,'Ola Cabs',235)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 9,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false FROM (VALUES (4,'BigBasket',2200),(9,'Spencer''s Kolkata',2000),(14,'Zepto',1700),(20,'BigBasket',2400),(26,'DMart Kolkata',2100)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 9,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false FROM (VALUES (7,'Amazon',3200),(13,'Flipkart',2800),(20,'Myntra',2400),(26,'Amazon',4000)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 9,v_m+day,'12:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Medical',merch,'medical','UPI',false FROM (VALUES (11,'Apollo Kolkata',900),(23,'Diagnostic Centre',1500)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 9,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false FROM (VALUES (7,'INOX Kolkata',1100),(15,'BookMyShow',900),(23,'Nicco Park',1400)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 9,v_m+8,'10:00:00'::TIME,ROUND(8000*v_vx),'DEBIT','SIP Investment','Zerodha','investment','NEFT',true WHERE v_m+8 <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 9,v_m+day,'08:30:00'::TIME,ROUND(base*v_vx),'DEBIT','Petrol',merch,'petrol','UPI',false FROM (VALUES (6,'HP Pump Salt Lake',2100),(18,'IOC Kolkata',2000),(27,'BPCL Kolkata',2200)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

    -- ── USER 10: SIDDHARTH JOSHI Ghost5 (₹50,000 · Lucknow) ──
    v_vx := 0.88 + ((v_mo * 4 + 3) % 25)::NUMERIC / 100;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring,bank_name) VALUES(10,v_m,'09:00:00',50000,'CREDIT','Salary','Kotak Bank','salary','NEFT',true,'Kotak');
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(10,v_m+1,'10:00:00',11000,'DEBIT','Rent Gomti Nagar','Gomti Nagar Flat Owner','rent','NEFT',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(10,v_m+2,'11:00:00',ROUND(CASE WHEN v_mo IN(4,5,6,7,8) THEN 1200 WHEN v_mo IN(11,12,1) THEN 900 ELSE 1000 END*v_vx),'DEBIT','Electricity','LESA Lucknow','utilities','UPI',true);
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(10,v_m+3,'11:30:00',499,'DEBIT','Airtel Broadband','Airtel Lucknow','utilities','UPI',true);
    IF v_m >= '2025-09-01' THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(10,v_m+4,'09:00:00',2500,'DEBIT','EMI Home Furniture','Kotak Bank','emi','AutoDebit',true); END IF;
    IF v_m+12 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(10,v_m+12,'08:00:00',299,'DEBIT','Hotstar Premium','Hotstar','subscription','UPI',true); END IF;
    IF v_m+20 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(10,v_m+20,'08:00:00',49, 'DEBIT','Zepto Pass','Zepto','subscription','UPI',true); END IF;
    IF v_m+26 <= v_last_day THEN INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) VALUES(10,v_m+26,'08:00:00',125,'DEBIT','Amazon Prime','Amazon Prime','subscription','UPI',true); END IF;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 10,v_m+day,'13:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Food',merch,'food_delivery','UPI',false FROM (VALUES (2,'Swiggy',270),(5,'Zomato',310),(8,'Swiggy',250),(11,'Zomato',290),(14,'Swiggy',280),(17,'Zomato',265),(20,'Swiggy',300),(23,'Zomato',255),(26,'Swiggy',285)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 10,v_m+day,'09:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Transport',merch,'transport','UPI',false FROM (VALUES (3,'Ola Cabs',150),(5,'Rapido',80),(8,'Ola Cabs',165),(10,'Auto Rickshaw',70),(13,'Ola Cabs',140),(15,'Rapido',90),(18,'Ola Cabs',160),(21,'Auto Rickshaw',65),(24,'Ola Cabs',155),(27,'Rapido',85)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 10,v_m+day,'11:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Grocery',merch,'groceries','UPI',false FROM (VALUES (4,'BigBasket',1400),(9,'Zepto',1200),(15,'DMart Lucknow',1500),(21,'BigBasket',1300),(27,'Reliance Smart',1100)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 10,v_m+day,'15:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Shopping',merch,'shopping','UPI',false FROM (VALUES (7,'Amazon',1300),(18,'Flipkart',1100),(26,'Meesho',800)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 10,v_m+day,'12:00:00'::TIME,ROUND(base*v_vx),'DEBIT','Medical',merch,'medical','UPI',false FROM (VALUES (12,'MedPlus Lucknow',550),(25,'Jan Aushadhi',280)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 10,v_m+day,'19:00:00'::TIME,ROUND(base*v_vx*v_vf),'DEBIT','Entertainment',merch,'entertainment','UPI',false FROM (VALUES (10,'Wave Cinemas Lucknow',550),(22,'BookMyShow',480)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;
    INSERT INTO transactions(user_id,transaction_date,transaction_time,amount,type,description,merchant,category,payment_method,is_recurring) SELECT 10,v_m+day,'08:30:00'::TIME,ROUND(base*v_vx),'DEBIT','Petrol',merch,'petrol','UPI',false FROM (VALUES (8,'HP Pump Lucknow',1650),(20,'IOC Lucknow',1550)) AS t(day,merch,base) WHERE v_m+day <= v_last_day;

  END LOOP; -- end month loop
END $$;

-- ═════════════════════════════════════════════════════════════
-- SECTION 5 — SUBSCRIPTION USAGE LOGS (drive verdict computation)
-- ═════════════════════════════════════════════════════════════

-- Vikram: Spotify  3 sessions last 30d, 22 prior 30d → declining
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes) VALUES
  (gen_random_uuid(),1,1,'2026-05-12 20:30:00',35),(gen_random_uuid(),1,1,'2026-05-07 19:15:00',42),(gen_random_uuid(),1,1,'2026-04-30 21:00:00',28),
  (gen_random_uuid(),1,1,'2026-04-28 20:45:00',51),(gen_random_uuid(),1,1,'2026-04-25 18:30:00',38),(gen_random_uuid(),1,1,'2026-04-22 20:00:00',45),
  (gen_random_uuid(),1,1,'2026-04-19 19:30:00',33),(gen_random_uuid(),1,1,'2026-04-17 21:15:00',55),(gen_random_uuid(),1,1,'2026-04-15 20:30:00',40),
  (gen_random_uuid(),1,1,'2026-04-13 19:00:00',47),(gen_random_uuid(),1,1,'2026-04-10 20:15:00',32),(gen_random_uuid(),1,1,'2026-04-08 21:30:00',58),
  (gen_random_uuid(),1,1,'2026-04-05 19:45:00',36),(gen_random_uuid(),1,1,'2026-04-03 20:00:00',43),(gen_random_uuid(),1,1,'2026-04-01 18:30:00',39),
  (gen_random_uuid(),1,1,'2026-03-30 21:00:00',50),(gen_random_uuid(),1,1,'2026-03-28 19:15:00',44),(gen_random_uuid(),1,1,'2026-03-25 20:30:00',37),
  (gen_random_uuid(),1,1,'2026-03-23 21:15:00',52),(gen_random_uuid(),1,1,'2026-03-21 19:30:00',41),(gen_random_uuid(),1,1,'2026-03-19 20:45:00',46),
  (gen_random_uuid(),1,1,'2026-03-17 18:00:00',34),(gen_random_uuid(),1,1,'2026-03-15 20:15:00',49),(gen_random_uuid(),1,1,'2026-03-13 19:00:00',38);

-- Vikram: YouTube Premium 62 sessions last 30d → thriving
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes)
SELECT gen_random_uuid(),1,2,('2026-05-14'::TIMESTAMP-(n*10||' hours')::INTERVAL),25+(n%80)
FROM generate_series(1,62) s(n)
WHERE ('2026-05-14'::TIMESTAMP-(n*10||' hours')::INTERVAL) >= '2026-04-14';

-- Vikram: ChatGPT Plus 89 sessions → thriving
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes)
SELECT gen_random_uuid(),1,3,('2026-05-14'::TIMESTAMP-(n*8||' hours')::INTERVAL),15+(n%45)
FROM generate_series(1,89) s(n)
WHERE ('2026-05-14'::TIMESTAMP-(n*8||' hours')::INTERVAL) >= '2026-04-14';

-- Vikram: LinkedIn Premium 1 session → dormant
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes) VALUES
  (gen_random_uuid(),1,4,'2026-05-02 10:30:00',5);

-- Vikram: Canva Pro 1 session → dormant
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes) VALUES
  (gen_random_uuid(),1,5,'2026-04-28 15:00:00',12);

-- Vikram: Amazon Prime 8 sessions last 30d, 17 prior → declining
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes) VALUES
  (gen_random_uuid(),1,6,'2026-05-14 20:00:00',90),(gen_random_uuid(),1,6,'2026-05-11 19:30:00',120),(gen_random_uuid(),1,6,'2026-05-08 21:00:00',95),
  (gen_random_uuid(),1,6,'2026-05-05 20:30:00',110),(gen_random_uuid(),1,6,'2026-05-02 19:00:00',88),(gen_random_uuid(),1,6,'2026-04-28 21:30:00',105),
  (gen_random_uuid(),1,6,'2026-04-24 20:00:00',75),(gen_random_uuid(),1,6,'2026-04-20 18:30:00',100),(gen_random_uuid(),1,6,'2026-04-17 21:00:00',115),
  (gen_random_uuid(),1,6,'2026-04-14 20:30:00',92),(gen_random_uuid(),1,6,'2026-04-11 19:00:00',108),(gen_random_uuid(),1,6,'2026-04-08 21:30:00',85),
  (gen_random_uuid(),1,6,'2026-04-05 20:00:00',118),(gen_random_uuid(),1,6,'2026-04-02 19:30:00',97),(gen_random_uuid(),1,6,'2026-03-31 21:00:00',112),
  (gen_random_uuid(),1,6,'2026-03-28 20:30:00',88),(gen_random_uuid(),1,6,'2026-03-25 19:00:00',103),(gen_random_uuid(),1,6,'2026-03-22 21:30:00',95),
  (gen_random_uuid(),1,6,'2026-03-19 20:00:00',107),(gen_random_uuid(),1,6,'2026-03-16 18:30:00',82),(gen_random_uuid(),1,6,'2026-03-13 21:00:00',119),
  (gen_random_uuid(),1,6,'2026-03-10 20:30:00',90),(gen_random_uuid(),1,6,'2026-03-07 19:00:00',104),(gen_random_uuid(),1,6,'2026-03-04 21:30:00',86),
  (gen_random_uuid(),1,6,'2026-03-01 20:00:00',111);

-- Priya: Netflix thriving
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes)
SELECT gen_random_uuid(),2,7,('2026-05-14'::TIMESTAMP-(n*12||' hours')::INTERVAL),40+(n%90)
FROM generate_series(1,35) s(n)
WHERE ('2026-05-14'::TIMESTAMP-(n*12||' hours')::INTERVAL) >= '2026-04-14';

-- Rahul: Netflix active
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes)
SELECT gen_random_uuid(),3,11,('2026-05-14'::TIMESTAMP-(n*24||' hours')::INTERVAL),55+(n%70)
FROM generate_series(1,12) s(n)
WHERE ('2026-05-14'::TIMESTAMP-(n*24||' hours')::INTERVAL) >= '2026-04-14';

-- Ananya: Netflix heavy usage
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes)
SELECT gen_random_uuid(),4,13,('2026-05-14'::TIMESTAMP-(n*10||' hours')::INTERVAL),60+(n%120)
FROM generate_series(1,55) s(n)
WHERE ('2026-05-14'::TIMESTAMP-(n*10||' hours')::INTERVAL) >= '2026-04-14';

-- Karan: Netflix thriving
INSERT INTO subscription_usage(id,user_id,subscription_id,used_at,duration_minutes)
SELECT gen_random_uuid(),5,18,('2026-05-14'::TIMESTAMP-(n*14||' hours')::INTERVAL),45+(n%100)
FROM generate_series(1,30) s(n)
WHERE ('2026-05-14'::TIMESTAMP-(n*14||' hours')::INTERVAL) >= '2026-04-14';

-- Update subscription verdicts based on usage patterns
UPDATE subscriptions SET current_verdict='declining', verdict_reason='Usage dropped 86% vs prior month' WHERE id=1;
UPDATE subscriptions SET current_verdict='thriving',  verdict_reason='62 sessions in last 30 days' WHERE id=2;
UPDATE subscriptions SET current_verdict='thriving',  verdict_reason='89 sessions in last 30 days' WHERE id=3;
UPDATE subscriptions SET current_verdict='dormant',   verdict_reason='Only 1 session in last 30 days' WHERE id=4;
UPDATE subscriptions SET current_verdict='dormant',   verdict_reason='Only 1 session in last 30 days' WHERE id=5;
UPDATE subscriptions SET current_verdict='declining', verdict_reason='Usage dropped 53% vs prior month' WHERE id=6;
UPDATE subscriptions SET current_verdict='thriving',  verdict_reason='35 sessions - active usage' WHERE id=7;
UPDATE subscriptions SET current_verdict='active',    verdict_reason='Regular usage' WHERE id IN (8,9,10,11,12,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33);

-- ═════════════════════════════════════════════════════════════
-- SECTION 6 — SUBSCRIPTION CANCELLATIONS
-- ═════════════════════════════════════════════════════════════
INSERT INTO subscription_cancellations(id,user_id,service_name,monthly_amount,cancelled_at) VALUES
  (gen_random_uuid(),1,'ZEE5 Premium',299,'2026-01-15'),
  (gen_random_uuid(),1,'Hotstar Multiplex',299,'2026-02-20'),
  (gen_random_uuid(),1,'Audible Premium',199,'2026-03-10'),
  (gen_random_uuid(),2,'Cult.fit Premium',999,'2026-04-05'),
  (gen_random_uuid(),3,'Hotstar Premium',299,'2026-05-03'),
  (gen_random_uuid(),4,'Mango Music',99,'2025-08-12'),
  (gen_random_uuid(),4,'Gaana Plus',149,'2026-02-28'),
  (gen_random_uuid(),5,'ALT Balaji',99,'2025-06-18'),
  (gen_random_uuid(),6,'SonyLIV Premium',299,'2025-11-20'),
  (gen_random_uuid(),8,'Gaana Plus',149,'2026-01-14'),
  (gen_random_uuid(),9,'Zee5 Premium',299,'2025-09-08'),
  (gen_random_uuid(),10,'ALT Balaji',99,'2026-03-22');

-- ═════════════════════════════════════════════════════════════
-- SECTION 7 — PURCHASE GOALS (backend-compatible columns)
-- ═════════════════════════════════════════════════════════════
INSERT INTO purchase_goals(user_id,item_name,target_amount,saved_amount,target_date,monthly_target,category,priority,status) VALUES
  (1,'Laptop Upgrade - Lenovo X1 Carbon',85000,10200,'2026-10-11',5000,'electronics','HIGH','SAVING'),
  (1,'Family Trip to Manali',42000,5040,'2027-01-09',3000,'travel','MEDIUM','SAVING'),
  (2,'Washing Machine - Samsung Front Load',35000,8750,'2026-08-01',4000,'appliance','HIGH','SAVING'),
  (2,'Children School Fees',50000,20000,'2026-07-01',6000,'education','HIGH','SAVING'),
  (3,'Emergency Fund',50000,8500,'2026-12-31',3000,'savings','HIGH','SAVING'),
  (4,'Europe Trip Fund',320000,80000,'2027-01-15',15000,'travel','HIGH','SAVING'),
  (4,'Home Down Payment',500000,125000,'2028-06-01',15000,'property','HIGH','SAVING'),
  (5,'Photography Lens - Sigma 50mm Art',55000,11000,'2026-09-01',4000,'electronics','MEDIUM','SAVING'),
  (6,'TV Upgrade - Sony 55 inch 4K',45000,9000,'2026-11-01',3000,'electronics','MEDIUM','SAVING'),
  (9,'MBA Course Books',12000,6000,'2026-07-01',2000,'education','MEDIUM','SAVING'),
  (10,'New Refrigerator',28000,5600,'2026-10-15',2000,'appliance','MEDIUM','SAVING');

-- ═════════════════════════════════════════════════════════════
-- SECTION 8 — TRIPS & EVENTS
-- ═════════════════════════════════════════════════════════════
INSERT INTO trips_events(id,user_id,event_name,event_type,event_date,budget,saved_amount,destination,notes,status) VALUES
  (gen_random_uuid(),1,'Goa Beach Vacation','trip','2026-07-15',45000,9000,'Goa','Summer trip with friends','planned'),
  (gen_random_uuid(),2,'Kerala Backwaters Trip','trip','2026-08-20',85000,25500,'Kerala','Houseboat + Munnar','planned'),
  (gen_random_uuid(),3,'Coorg Weekend Getaway','trip','2026-09-06',12000,2000,'Coorg, Karnataka','2-day bus + resort','planned'),
  (gen_random_uuid(),4,'Europe 10-Day Tour','trip','2027-01-10',320000,80000,'Paris, London, Amsterdam','Flights booked','confirmed'),
  (gen_random_uuid(),5,'Rajasthan Heritage Tour','trip','2026-06-20',28000,7000,'Jaipur, Jodhpur, Udaipur','Road trip','planned'),
  (gen_random_uuid(),6,'Hyderabad to Ooty Trip','trip','2026-10-01',18000,3600,'Ooty, Tamil Nadu','Holiday trip','planned'),
  (gen_random_uuid(),9,'Darjeeling Tea Garden Trip','trip','2026-12-20',22000,4400,'Darjeeling, West Bengal','Year-end holiday','planned'),
  (gen_random_uuid(),10,'Varanasi Spiritual Trip','trip','2026-11-15',15000,3000,'Varanasi, UP','Spiritual retreat','planned');

-- ═════════════════════════════════════════════════════════════
-- SECTION 9 — FESTIVALS
-- ═════════════════════════════════════════════════════════════
INSERT INTO festivals(id,festival_name,festival_date,is_global) VALUES
  ('f0000001-0000-0000-0000-000000000001','Diwali',    '2024-10-31',true),
  ('f0000001-0000-0000-0000-000000000002','Diwali',    '2025-10-20',true),
  ('f0000001-0000-0000-0000-000000000003','Diwali',    '2026-10-09',true),
  ('f0000002-0000-0000-0000-000000000001','Holi',      '2025-03-14',true),
  ('f0000002-0000-0000-0000-000000000002','Holi',      '2026-03-03',true),
  ('f0000003-0000-0000-0000-000000000001','Eid al-Fitr','2025-04-03',true),
  ('f0000003-0000-0000-0000-000000000002','Eid al-Fitr','2026-03-23',true),
  ('f0000004-0000-0000-0000-000000000001','Christmas', '2024-12-25',true),
  ('f0000004-0000-0000-0000-000000000002','Christmas', '2025-12-25',true),
  ('f0000005-0000-0000-0000-000000000001','Navratri',  '2025-10-02',true),
  ('f0000006-0000-0000-0000-000000000001','Pongal',    '2025-01-14',true),
  ('f0000006-0000-0000-0000-000000000002','Pongal',    '2026-01-14',true),
  ('f0000007-0000-0000-0000-000000000001','Durga Puja','2025-10-01',true);

-- ═════════════════════════════════════════════════════════════
-- SECTION 10 — USER FESTIVAL PLANS
-- ═════════════════════════════════════════════════════════════
INSERT INTO user_festival_plans(id,user_id,festival_id,event_date,past_spend_amount,recommended_budget,is_recurring) VALUES
  (gen_random_uuid(),1,'f0000001-0000-0000-0000-000000000001','2024-10-31',28000,30000,true),
  (gen_random_uuid(),1,'f0000001-0000-0000-0000-000000000002','2025-10-20',28000,32000,true),
  (gen_random_uuid(),1,'f0000005-0000-0000-0000-000000000001','2025-10-02',4200,5000,true),
  (gen_random_uuid(),2,'f0000001-0000-0000-0000-000000000001','2024-10-31',35000,38000,true),
  (gen_random_uuid(),2,'f0000001-0000-0000-0000-000000000002','2025-10-20',35000,40000,true),
  (gen_random_uuid(),2,'f0000003-0000-0000-0000-000000000001','2025-04-03',12000,14000,true),
  (gen_random_uuid(),3,'f0000001-0000-0000-0000-000000000001','2024-10-31',8000,9000,true),
  (gen_random_uuid(),3,'f0000001-0000-0000-0000-000000000002','2025-10-20',8000,9500,true),
  (gen_random_uuid(),4,'f0000001-0000-0000-0000-000000000001','2024-10-31',52000,55000,true),
  (gen_random_uuid(),4,'f0000001-0000-0000-0000-000000000002','2025-10-20',52000,58000,true),
  (gen_random_uuid(),4,'f0000006-0000-0000-0000-000000000001','2025-01-14',15000,16000,true),
  (gen_random_uuid(),5,'f0000001-0000-0000-0000-000000000001','2024-10-31',18000,20000,true),
  (gen_random_uuid(),5,'f0000001-0000-0000-0000-000000000002','2025-10-20',18000,22000,true),
  (gen_random_uuid(),5,'f0000002-0000-0000-0000-000000000001','2025-03-14',4000,5000,true),
  (gen_random_uuid(),6,'f0000001-0000-0000-0000-000000000001','2024-10-31',12000,14000,true),
  (gen_random_uuid(),7,'f0000001-0000-0000-0000-000000000001','2024-10-31',3500, 4000,true),
  (gen_random_uuid(),9,'f0000001-0000-0000-0000-000000000001','2024-10-31',40000,45000,true),
  (gen_random_uuid(),9,'f0000007-0000-0000-0000-000000000001','2025-10-01',18000,20000,true),
  (gen_random_uuid(),10,'f0000001-0000-0000-0000-000000000001','2024-10-31',9000,11000,true);

-- ═════════════════════════════════════════════════════════════
-- SECTION 11 — FRAUD ALERTS (backend-compatible schema)
-- ═════════════════════════════════════════════════════════════
INSERT INTO fraud_alerts(user_id,pattern_matched,risk_score,amount_at_risk,warning_message,hinglish_explanation,user_action,money_saved,severity,merchant_name,reason,verdict,amount_recovered,detected_at,resolved_at) VALUES
  (1,'duplicate_charge',72,2998,'Netflix double-charged on same day from two different device sessions.',
   'Netflix ne aapko do baar charge kiya ek hi din mein - yeh galat hai!','DISMISSED',0,'MEDIUM','Netflix India',
   'Duplicate charge detected: billed twice same day','dismissed',0,'2026-03-15 02:30:00','2026-03-16 10:00:00'),
  (1,'geo_anomaly',88,4500,'Transaction from Jaipur while account primary device is in Pune. Unrecognized QR merchant.',
   'Aapke account se Jaipur mein transaction hua jab aap Pune mein the!','CONFIRMED',4500,'HIGH','Unknown Merchant Jaipur QR',
   'New city transaction + unregistered payee','confirmed_fraud',4500,'2026-04-03 14:22:00','2026-04-05 11:00:00'),
  (1,'dark_pattern',55,1299,'Meesho unverified seller - price 95% below market, possible phantom delivery.',
   'Yeh deal bahut sasta lag raha hai - dhyan rakhein!','PENDING',0,'LOW','Meesho Seller',
   'Unverified seller, suspiciously low price','pending',0,'2026-05-09 16:45:00',NULL),
  (2,'night_transfer',95,75000,'IMPS ₹75,000 at 2:47 AM from unrecognized device in Bengaluru. 3 failed OTP before success.',
   'Raat 2:47 baje ₹75,000 ka transfer - yeh fraud tha!','CONFIRMED',75000,'CRITICAL','Groww Investments',
   'Night-time large transfer from new device and city','confirmed_fraud',75000,'2026-01-08 02:47:00','2026-01-10 09:00:00'),
  (2,'new_device_purchase',45,12999,'Purchase from new Pune device. Delivery address differs from registered.',
   'Naye device se shopping - confirm karein ki aapne kiya hai.','DISMISSED',0,'LOW','Amazon Pune',
   'New device + different delivery address','dismissed',0,'2026-04-18 11:30:00','2026-04-19 14:00:00'),
  (2,'velocity_attack',82,25000,'Three rapid IMPS transfers totalling ₹25,000 within 4 minutes to unregistered payee.',
   'Chaar minute mein ₹25,000 - yeh velocity attack ho sakta hai!','PENDING',0,'HIGH','IMPS - Unknown UPI',
   'Velocity attack pattern on UPI','pending',0,'2026-05-11 19:22:00',NULL),
  (3,'counterfeit_listing',91,3499,'iPhone 14 listed at ₹3,499 - 95% below market. New seller, zero reviews.',
   'iPhone ₹3,499 mein - yeh scam hai!','CONFIRMED',3499,'HIGH','Flipkart Seller TechZone',
   'Counterfeit listing, too-good-to-be-true price','confirmed_fraud',3499,'2025-09-14 15:30:00','2025-09-16 10:00:00'),
  (4,'unauthorized_trade',93,50000,'Commodity futures trade at 11:58 PM via API. Account logged from Chennai + Hyderabad simultaneously.',
   'Raat ko API se trade - aapka account hack hua tha!','CONFIRMED',50000,'CRITICAL','Zerodha Commodity',
   'Simultaneous login from two cities + night trade','confirmed_fraud',50000,'2025-06-30 23:58:00','2025-07-02 10:00:00'),
  (4,'inflated_invoice',78,8500,'Swiggy Genie ₹8,500 for document pickup - 12x above typical pricing.',
   'Swiggy Genie ne ₹8,500 charge kiya - yeh fraud tha!','CONFIRMED',8500,'HIGH','Swiggy Genie Corporate',
   'Inflated invoice 12x above market rate','confirmed_fraud',8500,'2026-03-22 14:15:00','2026-03-24 11:00:00'),
  (5,'duplicate_booking',42,15200,'Duplicate flight booking: two identical tickets within 8 minutes, different session fingerprint.',
   'Ek hi flight ke do ticket book hue - check karein!','DISMISSED',0,'MEDIUM','Indigo Airlines',
   'Duplicate booking from different browser session','dismissed',0,'2026-01-20 16:45:00','2026-01-21 10:00:00'),
  (5,'lottery_scam',85,2200,'Payment to "Lucky Draw Prize Claim" UPI - lottery advance fee pattern.',
   'Lucky Draw ke naam pe paise mat do - yeh scam hai!','CONFIRMED',0,'HIGH','Unknown UPI Lottery',
   'Lottery advance fee fraud pattern','confirmed_fraud',0,'2026-04-28 13:30:00','2026-04-30 09:00:00'),
  (6,'tech_support_scam',90,3000,'Payment to "Microsoft Tech Support" at 3:15 AM after suspicious call.',
   'Microsoft support ke naam pe raat 3 baje payment - fraud!','CONFIRMED',3000,'HIGH','Google Pay Tech Support',
   'Tech support scam - fake Microsoft call','confirmed_fraud',3000,'2025-12-08 03:15:00','2025-12-09 10:00:00'),
  (7,'advance_fee_fraud',75,800,'Loan processing fee to unverified merchant. No loan sanctioned.',
   'Loan fee dene ke baad koi loan nahi mila - fraud!','CONFIRMED',800,'HIGH','Paytm Loan Fee',
   'Advance fee fraud targeting low-income users','confirmed_fraud',800,'2026-02-14 18:00:00','2026-02-15 11:00:00'),
  (8,'seller_fraud',80,6500,'Return fraud: merchant claimed item returned, reversed refund. User never initiated return.',
   'Seller ne jhootha return dikha ke paisa le liya!','CONFIRMED',6500,'HIGH','Amazon Seller ElectroHub',
   'Seller-side return fraud','confirmed_fraud',6500,'2026-01-18 11:30:00','2026-01-20 14:00:00');

-- ═════════════════════════════════════════════════════════════
-- SECTION 12 — DEVICE TRUST
-- ═════════════════════════════════════════════════════════════
INSERT INTO device_trust(id,user_id,device_name,device_type,city,trust_score,last_seen) VALUES
  ('d1111111-1111-1111-1111-111111111101',1,'iPhone 15 Pro Max - Vikram','mobile','Pune',100,'2026-05-14 21:30:00'),
  ('d1111111-1111-1111-1111-111111111102',1,'MacBook Air M2 - Office','laptop','Pune',100,'2026-05-14 18:00:00'),
  ('d1111111-1111-1111-1111-111111111103',1,'iPad Pro - Home','tablet','Mumbai',92,'2026-04-28 14:00:00'),
  ('d2222222-2222-2222-2222-222222222201',2,'Samsung Galaxy S23 - Priya','mobile','Mumbai',100,'2026-05-14 20:00:00'),
  ('d2222222-2222-2222-2222-222222222202',2,'HP Laptop - Work','laptop','Mumbai',98,'2026-05-13 17:30:00'),
  ('d2222222-2222-2222-2222-222222222203',2,'Unknown Android - Bengaluru','mobile','Bengaluru',45,'2026-01-08 03:05:00'),
  ('d3333333-3333-3333-3333-333333333301',3,'Redmi Note 13 - Rahul','mobile','Bengaluru',100,'2026-05-14 22:00:00'),
  ('d3333333-3333-3333-3333-333333333302',3,'Dell XPS Laptop','laptop','Bengaluru',95,'2026-05-14 19:00:00'),
  ('d4444444-4444-4444-4444-444444444401',4,'iPhone 14 Pro - Ananya','mobile','Chennai',100,'2026-05-14 21:00:00'),
  ('d4444444-4444-4444-4444-444444444402',4,'MacBook Pro 14 - Work','laptop','Chennai',100,'2026-05-14 17:00:00'),
  ('d4444444-4444-4444-4444-444444444403',4,'iPad Air - Family','tablet','Chennai',88,'2026-05-10 16:00:00'),
  ('d4444444-4444-4444-4444-444444444404',4,'Unknown PC - Hyderabad','desktop','Hyderabad',12,'2025-06-30 23:45:00'),
  ('d5555555-5555-5555-5555-555555555551',5,'OnePlus 12 - Karan','mobile','Delhi',100,'2026-05-14 20:30:00'),
  ('d5555555-5555-5555-5555-555555555552',5,'Lenovo ThinkPad - Office','laptop','Delhi',97,'2026-05-14 18:30:00'),
  ('d6666666-6666-6666-6666-666666666601',6,'Realme 12 - Arjun','mobile','Hyderabad',100,'2026-05-14 19:30:00'),
  ('d7777777-7777-7777-7777-777777777701',7,'Redmi A3 - Neha','mobile','Jaipur',100,'2026-05-14 21:00:00'),
  ('d8888888-8888-8888-8888-888888888801',8,'Samsung Galaxy A54 - Rohan','mobile','Ahmedabad',100,'2026-05-14 20:00:00'),
  ('d9999999-9999-9999-9999-999999999901',9,'iPhone 13 - Kavya','mobile','Kolkata',100,'2026-05-14 21:30:00'),
  ('daaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',10,'Poco X6 - Siddharth','mobile','Lucknow',100,'2026-05-14 20:45:00');

-- ═════════════════════════════════════════════════════════════
-- SECTION 13 — LOGIN SESSIONS (50-80 per user)
-- ═════════════════════════════════════════════════════════════
INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),1,
  CASE WHEN n%15=0 THEN 'd1111111-1111-1111-1111-111111111103'::UUID
       WHEN n%3=0  THEN 'd1111111-1111-1111-1111-111111111102'::UUID
       ELSE 'd1111111-1111-1111-1111-111111111101'::UUID END,
  CASE WHEN n%15=0 THEN 'Mumbai' ELSE 'Pune' END,
  '2024-12-01 08:00:00'::TIMESTAMP+(n*7||' hours')::INTERVAL
FROM generate_series(1,72) s(n)
WHERE '2024-12-01 08:00:00'::TIMESTAMP+(n*7||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),2,
  CASE WHEN n%4=0 THEN 'd2222222-2222-2222-2222-222222222202'::UUID ELSE 'd2222222-2222-2222-2222-222222222201'::UUID END,
  'Mumbai','2024-12-02 09:30:00'::TIMESTAMP+(n*8||' hours')::INTERVAL
FROM generate_series(1,65) s(n)
WHERE '2024-12-02 09:30:00'::TIMESTAMP+(n*8||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),3,'d3333333-3333-3333-3333-333333333301'::UUID,'Bengaluru',
  '2024-12-03 07:00:00'::TIMESTAMP+(n*9||' hours')::INTERVAL
FROM generate_series(1,58) s(n)
WHERE '2024-12-03 07:00:00'::TIMESTAMP+(n*9||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),4,'d4444444-4444-4444-4444-444444444401'::UUID,'Chennai',
  '2024-12-01 10:00:00'::TIMESTAMP+(n*6||' hours')::INTERVAL
FROM generate_series(1,85) s(n)
WHERE '2024-12-01 10:00:00'::TIMESTAMP+(n*6||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),5,'d5555555-5555-5555-5555-555555555551'::UUID,'Delhi',
  '2024-12-05 08:30:00'::TIMESTAMP+(n*8||' hours')::INTERVAL
FROM generate_series(1,62) s(n)
WHERE '2024-12-05 08:30:00'::TIMESTAMP+(n*8||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),6,'d6666666-6666-6666-6666-666666666601'::UUID,'Hyderabad',
  '2024-12-01 09:00:00'::TIMESTAMP+(n*11||' hours')::INTERVAL
FROM generate_series(1,50) s(n) WHERE '2024-12-01 09:00:00'::TIMESTAMP+(n*11||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),7,'d7777777-7777-7777-7777-777777777701'::UUID,'Jaipur',
  '2024-12-01 10:00:00'::TIMESTAMP+(n*13||' hours')::INTERVAL
FROM generate_series(1,42) s(n) WHERE '2024-12-01 10:00:00'::TIMESTAMP+(n*13||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),8,'d8888888-8888-8888-8888-888888888801'::UUID,'Ahmedabad',
  '2024-12-01 09:30:00'::TIMESTAMP+(n*12||' hours')::INTERVAL
FROM generate_series(1,48) s(n) WHERE '2024-12-01 09:30:00'::TIMESTAMP+(n*12||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),9,'d9999999-9999-9999-9999-999999999901'::UUID,'Kolkata',
  '2024-12-01 08:00:00'::TIMESTAMP+(n*9||' hours')::INTERVAL
FROM generate_series(1,60) s(n) WHERE '2024-12-01 08:00:00'::TIMESTAMP+(n*9||' hours')::INTERVAL <= '2026-05-14 23:59:59';

INSERT INTO login_sessions(id,user_id,device_id,city,logged_in_at)
SELECT gen_random_uuid(),10,'daaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::UUID,'Lucknow',
  '2024-12-10 09:00:00'::TIMESTAMP+(n*11||' hours')::INTERVAL
FROM generate_series(1,45) s(n) WHERE '2024-12-10 09:00:00'::TIMESTAMP+(n*11||' hours')::INTERVAL <= '2026-05-14 23:59:59';

-- ═════════════════════════════════════════════════════════════
-- SECTION 14 — AI INSIGHTS
-- ═════════════════════════════════════════════════════════════
INSERT INTO ai_insights(id,user_id,type,category,title,body,created_at) VALUES
  (gen_random_uuid(),1,'critical','subscription','Spotify Premium declining — 86% usage drop',
   'Your Spotify usage dropped from 22 sessions (prior month) to just 3 this month — an 86% decline. At ₹119/month you paid ₹1,428 this year. Consider pausing if trend continues.',
   '2026-05-13 09:00:00'),
  (gen_random_uuid(),1,'migration','subscription','LinkedIn + Canva both dormant — ₹1,498/month waste',
   'LinkedIn Premium (₹999) and Canva Pro (₹499) show less than 2 sessions in last 30 days. Combined monthly waste: ₹1,498. Both have free tiers that cover current usage.',
   '2026-05-10 10:30:00'),
  (gen_random_uuid(),1,'optimization','savings','Saved ₹797 by cancelling 3 subscriptions this year',
   'ZEE5 (₹299 · Jan), Hotstar (₹299 · Feb), Audible (₹199 · Mar) cancelled. Annual projected savings: ₹9,564. Active subscription spend now ₹3,970/month.',
   '2026-05-01 08:00:00'),
  (gen_random_uuid(),1,'insight','emi','MacBook EMI added — EMI burden now 18.5% of income',
   'MacBook Air EMI (₹8,916) brings total EMI to ₹16,999/month — 18.5% of income. Healthy zone (under 30%). Safe headroom for new EMI up to ₹10,601.',
   '2026-02-06 12:00:00'),
  (gen_random_uuid(),2,'critical','fraud','₹75,000 fraud resolved — funds fully recovered',
   'Fraudulent 2:47 AM IMPS transfer of ₹75,000 in January detected and reversed by ICICI. Account security upgraded. Set UPI daily limits to prevent recurrence.',
   '2026-01-10 10:00:00'),
  (gen_random_uuid(),2,'critical','emi','EMI burden at 34.7% — above safe threshold',
   'Three active EMIs total ₹26,000/month — 34.7% of ₹75,000 income. Exceeds safe 30% threshold. Avoid new loans for 12 months.',
   '2026-03-08 09:00:00'),
  (gen_random_uuid(),3,'insight','savings','Savings rate improved to 18% this month',
   'Despite laptop EMI (₹3,200), you reduced food delivery 15% and saved ₹8,100 this month — your best since tracking started. On track for ₹50,000 emergency fund by October.',
   '2026-05-02 09:00:00'),
  (gen_random_uuid(),4,'insight','investment','SIP portfolio growing — ₹2.7L invested this year',
   'Consistent ₹15,000/month SIP (Nifty 50 + ELSS) accumulated ₹2,70,000 in 2025-26. At 12% CAGR you will reach ₹35L by 2030.',
   '2026-05-05 08:00:00'),
  (gen_random_uuid(),4,'optimization','subscription','Adobe CC at ₹1,675/month — switch to annual for ₹4,020 savings',
   'Your Adobe Creative Cloud usage is 45 sessions/month — excellent. Switching to annual plan saves ₹4,020/year (20% discount). Clear optimization at your usage level.',
   '2026-04-15 10:00:00'),
  (gen_random_uuid(),5,'insight','emi','Camera EMI started — review spending to save',
   'Sony Alpha A7 III EMI (₹5,500) started. Fixed costs now ₹47,277/month (78.8% of income). Reduce discretionary by ₹3,000/month to maintain positive savings rate.',
   '2026-01-06 09:00:00'),
  (gen_random_uuid(),6,'insight','budget','Spending balanced for income level',
   'With ₹50,000 income and ₹12,000 rent (24%), you are within healthy limits. EMI at 5.6% debt burden. Monthly surplus: ₹8,000-10,000.',
   '2026-05-08 09:00:00'),
  (gen_random_uuid(),9,'critical','emi','Dual EMI burden at 30.5% of income',
   'Car EMI (₹18,500) + education loan (₹12,000) = ₹30,500/month — exactly at safe threshold. Any new loan pushes to caution zone. Focus on prepaying car loan faster.',
   '2026-05-07 09:00:00');

-- ═════════════════════════════════════════════════════════════
-- SECTION 15 — DARK PATTERN ALERTS
-- ═════════════════════════════════════════════════════════════
INSERT INTO dark_pattern_alerts(id,user_id,subscription_id,service_name,amount,alert_date,days_until_charge,alert_type,pattern_reason) VALUES
  (gen_random_uuid(),1,5,'Canva Pro',499,'2026-05-22',8,'dormant_renewal',
   'Canva Pro renews May 22. Usage: 1 session in last 30 days. Last meaningful use: April 2nd. Cancel before May 22 to avoid being charged.'),
  (gen_random_uuid(),1,NULL,'SecureVPN Pro',399,'2026-05-28',14,'trial_to_paid',
   'SecureVPN free trial ends May 28 and auto-converts to ₹399/month. No usage after day 2 of trial. Cancel now to avoid charges.'),
  (gen_random_uuid(),1,4,'LinkedIn Premium',999,'2026-06-08',25,'dormant_renewal',
   'LinkedIn Premium renews June 8. Logged in only once in last 30 days. At ₹11,988/year, 3rd most expensive subscription by annual cost.'),
  (gen_random_uuid(),1,6,'Amazon Prime Annual',1499,'2026-07-20',67,'price_hike',
   'Amazon Prime annual renews July 20. Monthly billing (₹125×12=₹1,500) costs nearly same. Evaluate whether annual vs monthly makes sense.'),
  (gen_random_uuid(),2,7,'Netflix',649,'2026-06-07',24,'price_hike',
   'Netflix Standard renews June 7. Price increased 3 times in 18 months — was ₹499 in 2023. Consider downgrading to Mobile plan (₹199) for solo usage.'),
  (gen_random_uuid(),2,NULL,'Nykaa Pink Membership',199,'2026-06-12',29,'hidden_charges',
   'Nykaa Pink auto-renewed without reminder. Benefits: 5% cashback — but spent ₹3,600 on Nykaa this year, earning ₹180 cashback. Net loss: ₹19.'),
  (gen_random_uuid(),3,NULL,'Swiggy Super Annual',1499,'2026-06-15',32,'trial_to_paid',
   'Swiggy Super annual renews June 15 at ₹1,499. At 8 orders/month avg ₹250, delivery fee savings are ₹0 vs free threshold. Net benefit negative.'),
  (gen_random_uuid(),3,11,'Netflix Mobile',199,'2026-06-10',27,'price_hike',
   'Netflix Mobile renews June 10 — 480p on one device. For ₹100 more (₹299) Basic plan offers HD. Consider if streaming has shifted to YouTube.'),
  (gen_random_uuid(),4,16,'Adobe Creative Cloud',1675,'2026-06-18',35,'price_hike',
   'Adobe CC renews June 18. Price raised 22% in 2024. Usage is strong (45 sessions/month). Switch to annual saves ₹4,020/year.'),
  (gen_random_uuid(),4,NULL,'iCloud+ 200GB',75,'2026-06-01',18,'hidden_charges',
   'iCloud+ 200GB quietly upgraded from free 5GB during iOS update. You use only 12GB. Google Photos free tier would cost ₹0/month.'),
  (gen_random_uuid(),5,18,'Netflix',649,'2026-06-08',25,'price_hike',
   'Netflix renews June 8. With YouTube Premium (₹129) active, two video services total ₹778/month. Both have strong usage — evaluate if both needed.'),
  (gen_random_uuid(),5,NULL,'Google One 100GB',130,'2026-07-05',52,'hidden_charges',
   'Google One renews July 5. Current usage 67GB. Family sharing plan (₹210/month, 200GB for 5 people) may offer better value.'),
  (gen_random_uuid(),6,21,'Hotstar Premium',299,'2026-06-06',23,'dormant_renewal',
   'Hotstar renews June 6. IPL 2026 season ended. Usage typically drops 78% post-IPL. Consider monthly billing to avoid annual lock-in.'),
  (gen_random_uuid(),9,30,'Duolingo Plus',533,'2026-06-11',28,'trial_to_paid',
   'Duolingo Plus renews June 11. 45-day streak shows commitment. However free tier has identical learning content. Plus features cost ₹6,396/year.'),
  (gen_random_uuid(),10,31,'Hotstar Premium',299,'2026-06-13',30,'dormant_renewal',
   'Hotstar renews June 13. Last session May 6 — 8 days ago. Only 3 sessions in last 30 days: ₹100/session. Consider mobile-only plan at ₹149/month.');

COMMIT;

-- ═════════════════════════════════════════════════════════════
-- SECTION 16 — VALIDATION QUERIES
-- ═════════════════════════════════════════════════════════════

-- Check 1: Transaction counts per user
SELECT u.name, COUNT(t.id) AS transaction_count
FROM users u LEFT JOIN transactions t ON u.id=t.user_id
GROUP BY u.name ORDER BY u.name;

-- Check 2: EMI burden from computed view
SELECT u.name, u.monthly_income, v.total_emi_burden, v.debt_to_income_ratio, v.status
FROM users u LEFT JOIN v_emi_dashboard v ON u.id=v.user_id
ORDER BY v.debt_to_income_ratio DESC NULLS LAST;

-- Check 3: Subscription counts
SELECT u.name, COUNT(s.id) AS subs, COALESCE(SUM(s.amount),0) AS monthly_sub_cost
FROM users u LEFT JOIN subscriptions s ON u.id=s.user_id AND s.status='active'
GROUP BY u.name ORDER BY monthly_sub_cost DESC;

-- Check 4: Financial health scores
SELECT name, total_score, savings_rate_score, expense_ratio_score, consistency_score
FROM v_financial_health ORDER BY total_score DESC;

-- Check 5: Salary = declared income (0 rows = PASS)
SELECT u.name, u.monthly_income, AVG(t.amount) AS avg_salary
FROM users u LEFT JOIN transactions t ON u.id=t.user_id
  AND t.type='CREDIT' AND t.category='salary' AND EXTRACT(DAY FROM t.transaction_date)=1
GROUP BY u.name, u.monthly_income
HAVING u.monthly_income != COALESCE(AVG(t.amount),0);

-- Check 6: Subscription savings divergence (0 rows = PASS)
SELECT u.name, v.saved_this_month, v.saved_this_year, v.saved_all_time
FROM users u LEFT JOIN v_subscription_savings v ON u.id=v.user_id
WHERE v.saved_this_month = v.saved_this_year OR v.saved_this_year = v.saved_all_time;

-- Check 7: All users have trips (0 rows = PASS)
SELECT u.name FROM users u LEFT JOIN trips_events te ON u.id=te.user_id
GROUP BY u.name HAVING COUNT(te.id)=0;

-- Check 8: Subscription verdict sampling for Vikram
SELECT s.merchant, s.amount, compute_subscription_verdict(u.id, s.id) AS verdict
FROM users u JOIN subscriptions s ON u.id=s.user_id
WHERE u.id=1 ORDER BY s.merchant;

-- FINAL VALIDATION
DO $$
DECLARE
  v_failed INT:=0; v_users INT; v_txns INT; v_subs INT; v_emis INT;
BEGIN
  SELECT COUNT(*) INTO v_users FROM users;
  SELECT COUNT(*) INTO v_txns  FROM transactions;
  SELECT COUNT(*) INTO v_subs  FROM subscriptions WHERE status='active';
  SELECT COUNT(*) INTO v_emis  FROM emis WHERE status='active';
  IF v_users != 10     THEN RAISE WARNING 'FAIL: Expected 10 users, got %', v_users;    v_failed:=v_failed+1; END IF;
  IF v_txns  < 5000    THEN RAISE WARNING 'FAIL: Too few transactions: %', v_txns;      v_failed:=v_failed+1; END IF;
  IF v_subs  < 25      THEN RAISE WARNING 'FAIL: Too few subscriptions: %', v_subs;     v_failed:=v_failed+1; END IF;
  IF v_emis  < 8       THEN RAISE WARNING 'FAIL: Too few active EMIs: %', v_emis;       v_failed:=v_failed+1; END IF;
  IF v_failed=0 THEN
    RAISE NOTICE '✅ SEED VALIDATION PASSED — users:% txns:% subs:% emis:%', v_users, v_txns, v_subs, v_emis;
  ELSE
    RAISE EXCEPTION '❌ SEED VALIDATION FAILED — % checks failed', v_failed;
  END IF;
END $$;
