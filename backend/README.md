# SmartSpend Analytics — Phase 2 API

## Prerequisites

- PostgreSQL with Phase 1 schema and seed data (`smartspend_db`)
- Python 3.11+ (tested on 3.13)
- Project root `.env` with `DB_*` variables and `OPENAI_API_KEY` for AI routes

## Install

```bash
cd backend
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload --port 8000
```

Open **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)

## Endpoints overview

- `GET /` — API metadata and route list  
- `GET /health` — status + DB connectivity  
- `GET /api/users`, `GET /api/users/{user_id}` — demo users  
- `GET /api/dashboard/{user_id}` — combined dashboard payload  
- `GET /api/ml/status` — which user models are loaded in memory  
- `GET /api/anomalies/{user_id}/patterns` — velocity, recurrence, spikes, merchants, time habits, savings trajectory  
- `GET /api/anomalies/{user_id}/alerts` — unread alerts (then marks them read)  
- `GET|POST` transaction, analysis, anomaly, health-score, and insights routes under `/api/...` (see `/` or `/docs`)

### ML validation script

From `backend/`:

```bash
python -m services.ml_model_test
```

From repo root (`Exiqo phase2/`):

```bash
python -m backend.services.ml_model_test
```

## Notes

- Run this server from the **`backend`** directory so imports (`models`, `routes`, `services`, `db`) resolve correctly.
- CORS is open for local React (`localhost:3000` or any origin).
- On startup the API trains Isolation Forest models per user and runs detection on rows with `ml_processed = FALSE`.
