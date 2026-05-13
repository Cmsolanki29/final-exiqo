-- Phase 1 extensions (SmartSpend canonical): category dimension + savings ledger + usage helper.
-- Prerequisite: 021_subscription_intelligence.sql (app_usage_signals, subscriptions intel columns,
--   scheduled_reminders, reminder_outcomes) and 022_subscription_intelligence_platform.sql.
--
-- Does NOT recreate subscriptions / connected_apps / usage tables — those live in 021–022.
-- Replaces the spec filename 005_subscription_intelligence.sql (005 is reserved for phase5 MLOps).

CREATE TABLE IF NOT EXISTS subscription_categories (
  id SERIAL PRIMARY KEY,
  category_key VARCHAR(100) NOT NULL UNIQUE,
  category_description TEXT,
  parent_category VARCHAR(100),
  substitutable BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscription_categories_parent
  ON subscription_categories (parent_category)
  WHERE parent_category IS NOT NULL;

INSERT INTO subscription_categories (category_key, category_description, parent_category, substitutable)
VALUES
  ('streaming_video', 'Video streaming platforms (Netflix, Amazon Prime Video, etc.)', 'streaming', TRUE),
  ('music_streaming', 'Music streaming services (Spotify, YouTube Music, Apple Music)', 'streaming', TRUE),
  ('productivity_tools', 'Productivity and workflow tools (Notion, Asana, Trello)', NULL, TRUE),
  ('cloud_storage', 'Cloud storage services (Google Drive, Dropbox, iCloud)', NULL, TRUE),
  ('design_tools', 'Design and creative tools (Canva, Figma, Adobe Creative Cloud)', NULL, TRUE),
  ('ai_tools', 'AI and language models (ChatGPT, Claude, Copilot)', NULL, TRUE),
  ('professional_networking', 'Professional networking platforms (LinkedIn Premium)', NULL, FALSE),
  ('fitness', 'Fitness and health apps (Cult.fit, Headspace)', NULL, FALSE),
  ('news_media', 'News and magazine subscriptions (Times Prime, Medium)', NULL, TRUE),
  ('gaming', 'Gaming subscriptions (Xbox Game Pass, PlayStation Plus)', NULL, FALSE),
  ('vpn_security', 'VPN and security tools (NordVPN, 1Password)', NULL, TRUE),
  ('communication', 'Communication tools (Slack, Zoom Pro, Microsoft Teams)', NULL, FALSE),
  ('education', 'Learning platforms (Coursera, Udemy, Duolingo Plus)', NULL, TRUE),
  ('food_delivery', 'Food delivery memberships (Zomato Gold, Swiggy One)', NULL, FALSE),
  ('e_commerce', 'E-commerce memberships (Amazon Prime, Flipkart Plus)', NULL, FALSE)
ON CONFLICT (category_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS user_subscription_savings (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  month DATE NOT NULL,
  subscriptions_cancelled INTEGER NOT NULL DEFAULT 0,
  subscriptions_downgraded INTEGER NOT NULL DEFAULT 0,
  amount_saved NUMERIC(12, 2) NOT NULL DEFAULT 0,
  waste_prevented_monthly NUMERIC(12, 2) NOT NULL DEFAULT 0,
  waste_prevented_yearly NUMERIC(12, 2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, month)
);

CREATE INDEX IF NOT EXISTS idx_user_sub_savings_user_month
  ON user_subscription_savings (user_id, month DESC);

CREATE OR REPLACE FUNCTION intel_update_user_subscription_savings()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  subscription_cost NUMERIC(12, 2);
  bucket DATE;
BEGIN
  IF NEW.user_action IS DISTINCT FROM 'cancel_now' THEN
    RETURN NEW;
  END IF;

  SELECT COALESCE(NULLIF(monthly_cost, 0), NULLIF(amount, 0), 0)
  INTO subscription_cost
  FROM subscriptions
  WHERE id = NEW.subscription_id;

  IF subscription_cost IS NULL THEN
    subscription_cost := 0;
  END IF;

  bucket := date_trunc('month', CURRENT_DATE)::DATE;

  INSERT INTO user_subscription_savings (
    user_id, month, subscriptions_cancelled, amount_saved,
    waste_prevented_monthly, waste_prevented_yearly, updated_at
  )
  VALUES (
    NEW.user_id, bucket, 1, subscription_cost,
    subscription_cost, subscription_cost * 12, NOW()
  )
  ON CONFLICT (user_id, month) DO UPDATE SET
    subscriptions_cancelled = user_subscription_savings.subscriptions_cancelled + 1,
    amount_saved = user_subscription_savings.amount_saved + EXCLUDED.amount_saved,
    waste_prevented_monthly = user_subscription_savings.waste_prevented_monthly + EXCLUDED.waste_prevented_monthly,
    waste_prevented_yearly = user_subscription_savings.waste_prevented_yearly + EXCLUDED.waste_prevented_yearly,
    updated_at = NOW();

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tr_intel_savings_on_cancel ON reminder_outcomes;
CREATE TRIGGER tr_intel_savings_on_cancel
  AFTER INSERT ON reminder_outcomes
  FOR EACH ROW
  EXECUTE PROCEDURE intel_update_user_subscription_savings();

CREATE OR REPLACE FUNCTION calculate_usage_change(
  p_user_id INTEGER,
  p_subscription_id INTEGER,
  p_current_period_days INTEGER DEFAULT 30,
  p_comparison_period_days INTEGER DEFAULT 30
)
RETURNS TABLE (
  current_usage_hours NUMERIC,
  previous_usage_hours NUMERIC,
  change_percentage NUMERIC
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  pkg VARCHAR(255);
  cur_start DATE;
  cur_end DATE;
  p_start DATE;
  p_end DATE;
  cur_m NUMERIC;
  prev_m NUMERIC;
BEGIN
  SELECT NULLIF(trim(linked_app_package), '')
  INTO pkg
  FROM subscriptions
  WHERE id = p_subscription_id AND user_id = p_user_id;

  IF pkg IS NULL THEN
    current_usage_hours := 0;
    previous_usage_hours := 0;
    change_percentage := 0;
    RETURN NEXT;
    RETURN;
  END IF;

  cur_end := CURRENT_DATE;
  cur_start := CURRENT_DATE - p_current_period_days;
  p_end := cur_start;
  p_start := cur_start - p_comparison_period_days;

  SELECT COALESCE(SUM(usage_minutes), 0)::NUMERIC / 60.0 INTO cur_m
  FROM app_usage_signals
  WHERE user_id = p_user_id
    AND app_package = pkg
    AND signal_date >= cur_start
    AND signal_date < cur_end;

  SELECT COALESCE(SUM(usage_minutes), 0)::NUMERIC / 60.0 INTO prev_m
  FROM app_usage_signals
  WHERE user_id = p_user_id
    AND app_package = pkg
    AND signal_date >= p_start
    AND signal_date < p_end;

  current_usage_hours := cur_m;
  previous_usage_hours := prev_m;
  IF prev_m = 0 THEN
    change_percentage := 0;
  ELSE
    change_percentage := ((cur_m - prev_m) / prev_m) * 100;
  END IF;
  RETURN NEXT;
END;
$$;
