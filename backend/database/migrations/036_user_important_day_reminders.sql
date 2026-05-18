-- Smart date reminders for Festival Planner (bell + notification pings)

ALTER TABLE user_important_days
  ADD COLUMN IF NOT EXISTS reminder_enabled BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE user_important_days
  ADD COLUMN IF NOT EXISTS remind_offsets INTEGER[] NOT NULL DEFAULT ARRAY[30, 14, 7, 3, 1];

ALTER TABLE user_important_days
  ADD COLUMN IF NOT EXISTS estimated_budget NUMERIC(12, 2);
