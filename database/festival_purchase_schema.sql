-- Festival Predictor + Big Purchase Planner schema
-- Run: psql -U postgres -d smartspend_db -f database/festival_purchase_schema.sql

CREATE TABLE IF NOT EXISTS festival_budgets (
  id                SERIAL PRIMARY KEY,
  user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  festival_name     VARCHAR(100) NOT NULL,
  festival_date     DATE NOT NULL,
  last_year_spent   DECIMAL(12,2) DEFAULT 0,
  planned_budget    DECIMAL(12,2) DEFAULT 0,
  saved_so_far      DECIMAL(12,2) DEFAULT 0,
  monthly_target    DECIMAL(12,2) DEFAULT 0,
  days_remaining    INTEGER,
  status            VARCHAR(20) DEFAULT 'UPCOMING',
  category_breakdown JSONB,
  created_at        TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_festival_user_name_year
  ON festival_budgets (user_id, festival_name, (EXTRACT(YEAR FROM festival_date)::int));

CREATE TABLE IF NOT EXISTS purchase_goals (
  id                SERIAL PRIMARY KEY,
  user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  item_name         VARCHAR(200) NOT NULL,
  target_amount     DECIMAL(12,2) NOT NULL,
  saved_amount      DECIMAL(12,2) DEFAULT 0,
  target_date       DATE NOT NULL,
  monthly_target    DECIMAL(12,2) DEFAULT 0,
  category          VARCHAR(50) DEFAULT 'OTHER',
  priority          VARCHAR(10) DEFAULT 'MEDIUM',
  status            VARCHAR(20) DEFAULT 'SAVING',
  best_buy_month    VARCHAR(200),
  emi_vs_cash       JSONB,
  sacrifice_plan    JSONB,
  created_at        TIMESTAMP DEFAULT NOW()
);

DELETE FROM festival_budgets WHERE user_id IN (1, 2, 3);
DELETE FROM purchase_goals WHERE user_id IN (1, 2, 3);

INSERT INTO festival_budgets
  (user_id, festival_name, festival_date, last_year_spent, category_breakdown)
VALUES
(1, 'Diwali', '2026-10-20', 28500,
 '{"Shopping/Gifts": 12000, "Food/Sweets": 5500, "Travel": 7000, "Crackers": 4000}'::jsonb),
(1, 'Holi', '2026-03-29', 8200,
 '{"Colors/Puja": 1500, "Food/Drinks": 3200, "New Clothes": 3500}'::jsonb),
(1, 'Navratri', '2026-10-02', 6500,
 '{"Clothes/Jewelry": 3500, "Food": 2000, "Events": 1000}'::jsonb),
(1, 'Christmas', '2026-12-25', 12000,
 '{"Gifts": 6000, "Food/Party": 4000, "Decoration": 2000}'::jsonb),
(1, 'Eid', '2026-03-31', 9500,
 '{"Clothes": 4500, "Food/Sweets": 3000, "Gifts": 2000}'::jsonb),
(2, 'Diwali', '2026-10-20', 65000,
 '{"Shopping/Gifts": 30000, "Food/Sweets": 12000, "Travel": 15000, "Crackers": 8000}'::jsonb),
(2, 'Christmas', '2026-12-25', 35000,
 '{"Gifts": 18000, "Food/Party": 10000, "Travel": 7000}'::jsonb),
(2, 'Holi', '2026-03-29', 15000,
 '{"Colors/Puja": 2000, "Food/Drinks": 6000, "New Clothes": 7000}'::jsonb),
(3, 'Diwali', '2026-10-20', 120000,
 '{"Shopping/Gifts": 55000, "Food/Sweets": 20000, "Travel": 30000, "Crackers": 15000}'::jsonb),
(3, 'Christmas', '2026-12-25', 75000,
 '{"Gifts": 35000, "Food/Party": 25000, "Travel": 15000}'::jsonb);

INSERT INTO purchase_goals
  (user_id, item_name, target_amount, saved_amount, target_date, category, priority,
   best_buy_month, monthly_target)
VALUES
(1, 'Honda Activa Scooty', 75000, 0, '2026-11-01', 'VEHICLE', 'HIGH',
 'October 2026 — Navratri/Dussehra sale (avg ₹5,000 off)', 8500),
(1, 'iPhone 16', 79900, 0, '2027-01-01', 'ELECTRONICS', 'MEDIUM',
 'December — Christmas sale or January sales', 6500),
(2, 'MacBook Pro M4', 199000, 0, '2026-12-01', 'ELECTRONICS', 'HIGH',
 'November — Black Friday / Great Indian Festival (up to ₹15,000 off)', 25000),
(2, 'Split AC 1.5 Ton', 45000, 0, '2026-04-01', 'APPLIANCE', 'HIGH',
 'March — before summer peak (best pre-season deals)', 15000),
(3, 'BMW Car Upgrade', 4500000, 0, '2027-06-01', 'VEHICLE', 'MEDIUM',
 'December/January — year-end dealer offers', 150000);
