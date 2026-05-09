# SmartSpend Analytics - Phase 1 Setup Guide

## Prerequisites
- PostgreSQL 15+
- Python 3.11+

## Setup Steps
1. **Create the database**
   ```bash
   psql -U postgres -c "CREATE DATABASE smartspend_db;"
   ```

2. **Run schema**
   ```bash
   psql -U postgres -d smartspend_db -f database/schema.sql
   ```

3. **Create local environment file**
   ```bash
   cp .env.example .env
   ```
   On Windows PowerShell:
   ```powershell
   Copy-Item .env.example .env
   ```
   Then update `.env` with your real PostgreSQL credentials.

4. **Install Python dependencies**
   ```bash
   pip install -r database/requirements.txt
   ```

5. **Seed realistic Indian financial data**
   ```bash
   python database/seed_data.py
   ```

6. **Validate Phase 1 data layer**
   ```bash
   python database/validate.py
   ```

## Expected Output (what you should see)
- Seed script logs:
  - `✅ Created user: Priya Sharma`
  - `📊 Inserted <~1500> transactions`
  - anomaly counts for each injected anomaly type
  - monthly summary and spending pattern computation messages
- Validation script logs:
  - row counts for `users`, `transactions`, `alerts`, `monthly_summary`, `spending_patterns`
  - sample transaction rows including anomaly markers and risk levels
  - anomaly type distribution (DUPLICATE_CHARGE, UNUSUAL_AMOUNT, ODD_HOUR, FOREIGN_MERCHANT, RAPID_SUCCESSION, BALANCE_SPIKE)
  - monthly summaries and category spend breakdown
  - index verification
  - final success line: `✅ Phase 1 Complete — Database ready for ML pipeline`
