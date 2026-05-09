# SmartSpend Analytics

### AI-driven financial insights and risk monitoring

> Built for hackathon demo | Replace with your event and team name.

## Problem statement

Digital transactions create large volumes of data, but most users get **no actionable intelligence** from it.

**We address three gaps:**

1. **Data without insight** — Raw exports and PDFs do not explain health, risk, or next steps.
2. **Reactive fraud** — Losses are often discovered after money leaves the account.
3. **Low financial self-awareness** — People lack a simple view of savings rate, EMI load, and leakages.

## What we built

**SmartSpend Analytics** turns PostgreSQL transaction history into dashboards, ML anomaly flags, rule-based fraud checks, and optional AI (OpenAI / Groq) explanations — tuned for Indian context (UPI, EMI, festivals, ₹).

## Features

### Core

| Feature | Description |
|--------|-------------|
| Dashboard | Period-aware overview, charts, merchants, transactions |
| ML anomaly detection | Isolation Forest flags suspicious transactions |
| Health score | 0–100 score with grade and breakdown |
| AI insights | GPT-powered monthly narrative and tips (optional API key) |
| Scenario simulator | “What if” projections on savings and health |

### Advanced

| Feature | Description |
|--------|-------------|
| EMI trap detector | Debt-to-income vs RBI-style safe band |
| Subscription graveyard | Unused / low-usage recurring spend |
| Dark pattern detector | Billing tricks, rupee-trap escalation |
| FraudShield | Pre-send transaction check + alert workflow |
| Festival planner | Upcoming Indian festivals and savings targets |
| Purchase planner | Goal milestones, EMI vs cash, sacrifice hints |

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   React     │────▶│  FastAPI    │────▶│ PostgreSQL  │
│  (CRA)      │     │  REST API   │     │  + seeds    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │Isolation │ │ OpenAI / │ │  Rules + │
       │  Forest  │ │   Groq   │ │ patterns │
       └──────────┘ └──────────┘ └──────────┘
```

- **Frontend:** `frontend/` — React 18, Recharts, Lucide, Axios (`http://localhost:8000/api`).
- **Backend:** `backend/` — FastAPI, scikit-learn, pandas, psycopg2, OpenAI SDK (Groq-compatible base URL).
- **Database:** `database/` — SQL schema and demo seeds.

## Prerequisites

- **Node.js** (LTS) and **npm**
- **Python** 3.11+ (3.13 supported with pinned wheels)
- **PostgreSQL** 14+

## Environment

Copy `.env.example` to `.env` at the **project root** (same folder as `backend/` and `frontend/`).

| Variable | Required | Purpose |
|----------|----------|---------|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Yes | PostgreSQL |
| `OPENAI_API_KEY` | No | `/api/insights` and GPT features |
| `GROQ_API_KEY` | No | Fraud / purchase / festival AI text (graceful fallbacks if missing) |

## Database setup

1. Create database (e.g. `smartspend_db`).
2. Run SQL in order (adjust paths for your OS):

```bash
psql -U postgres -d smartspend_db -f database/schema.sql
# Then any additions your team uses, e.g.:
psql -U postgres -d smartspend_db -f database/schema_additions.sql
psql -U postgres -d smartspend_db -f database/festival_purchase_schema.sql
psql -U postgres -d smartspend_db -f database/fraud_schema.sql
```

## Run locally

**Terminal 1 — API**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/docs** for Swagger.

**Terminal 2 — Web**

```bash
cd frontend
npm install
npm start
```

App defaults to **http://localhost:3000** and expects the API on **port 8000** (`frontend/src/services/api.js`).

## Production build

```bash
cd frontend
npm run build
```

Serve `frontend/build` behind your static host or CDN; point API URL to your deployed FastAPI origin.

## API highlights

- `GET /api/users` — Demo users
- `GET /api/transactions/{user_id}` — Filter by month/year/category
- `GET /api/insights/{user_id}` — AI bundle (month/year)
- `POST /api/fraud-shield/{user_id}/check-transaction` — Live fraud check
- `GET /api/purchases/{user_id}`, `GET /api/festivals/{user_id}` — Planners

Full list: **Swagger `/docs`**.

## Demo tips (hackathon)

1. Pick **user 1** from the navbar; switch month/year to show trends.
2. Open **FraudShield → Check transaction** and run the built-in quick tests (KYC, lottery, collect).
3. Show **Purchase planner** milestone timeline and **Festival** urgency strip.
4. Mention **graceful degradation**: app works without OpenAI/Groq keys using fallbacks.

## License / credits

Replace this section with your team’s license and acknowledgements (OpenAI, Groq, datasets, mentors).

---

**SmartSpend Analytics** — ship the story: *from raw transactions to decisions before money is lost.*
