# E2E Tests

Run against local dev stack:

  1. Start backend:  `uvicorn main:app --host 127.0.0.1 --port 8001 --reload`  (from `backend/`)
  2. Start frontend: `PORT=3001 npm start`  (from `frontend/`)
  3. Run tests:      `npm run test:e2e`  (from `frontend/`)

Environment variables (optional):

  - `ADMIN_TOKEN`   — `X-Admin-Token` header value (default: `dev-admin-secret`)
  - `TEST_JWT`      — Bearer JWT for authenticated API calls
  - `TEST_EMAIL`    — Login email for browser tests (default: `abc@gmail.com`)
  - `TEST_PASSWORD` — Login password (default: `Pass@123`)
  - `API_BASE_URL`  — Override API base (default: `http://localhost:8001/api`)

First-time setup (if Playwright isn't installed yet):

```
npm install --save-dev @playwright/test
npx playwright install chromium
```
