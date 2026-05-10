-- Onboarding: persist verified mobile on users (link-bank flow)
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(20);

COMMENT ON COLUMN users.mobile_number IS 'Verified mobile from OTP flow; used for bank linking.';
