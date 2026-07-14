# FinPilot — AI-Powered Personal Finance Copilot

> Understand your money, hit your savings goals, and catch subscription creep —
> with explainable AI grounded in your own data.

> ⚠️ **Educational use only. Not financial advice.**

## What it does

| Page | What you get |
|---|---|
| **Overview** | One dashboard for everything: net cash flow with a 30-day spending pulse, income vs expenses, budgets, goals, upcoming subscription charges |
| **Spending** | Transactions with CSV import, ML auto-categorisation (XGBoost + rules), filters and charts |
| **Budgets** | Per-category monthly limits with live utilisation and over-budget alerts |
| **Goals** | Named savings targets with progress rings, pace-based completion projections, and required-monthly-savings math |
| **Subscriptions** | Recurring payments detected automatically from your history — cadence, next charge date, and price-increase alerts |
| **AI Insights** | Personal copilot (RAG over your own finances), 30-day spend forecast (ARIMA + Reservoir-LSTM ensemble), fraud guard (Isolation Forest + graph analysis) |

### The copilot needs no API key

Answers are grounded in each user's actual spending, budgets, goals, and
subscriptions. Out of the box it composes answers locally — no key, no cost.
Setting **one** optional server-side key upgrades generation quality
(providers tried in order): `GROQ_API_KEY` (free) → `GEMINI_API_KEY` (free) →
`ANTHROPIC_API_KEY` → `OLLAMA_URL` (self-hosted). End users only ever sign in.

## Stack

- **Frontend** — Next.js 14 (TypeScript, Tailwind, Recharts), in-memory access
  token + httpOnly refresh cookie
- **Backend** — FastAPI (async SQLAlchemy 2, Pydantic v2), JWT with rotation +
  Redis blacklist, TOTP MFA, Postgres row-level security on every user table
- **Data** — PostgreSQL (+ TimescaleDB and pgvector when available; degrades
  gracefully to plain Postgres on managed hosts), Redis
- **ML** — XGBoost classifier, ARIMA + Reservoir-LSTM forecaster, Isolation
  Forest + BFS/DFS graph fraud detection, sentence-transformer embeddings for
  RAG (local, 90 MB), ε-greedy recommendation bandit, drift detection

## Run it locally

```bash
cp .env.example .env   # fill JWT_SECRET_KEY; everything else optional
docker compose up --build
```

Frontend at http://localhost:3000, API + docs at http://localhost:8000/docs.
Migrations apply automatically on boot.

### Without Docker

```bash
# backend
cd backend && pip install -r requirements-dev.txt
alembic upgrade head && uvicorn app.main:app --reload
# frontend
cd frontend && npm install && npm run dev
```

## Deploy free

The repo ships a [Render blueprint](render.yaml) — Postgres, Redis, and the
API on Render's free tier, frontend on Vercel. Walkthrough in
[docs/RENDER_DEPLOY.md](docs/RENDER_DEPLOY.md).

## Sign in with Google (optional)

Create an OAuth client (steps in [.env.example](.env.example)), set
`GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`, and the button on the login and
register pages activates automatically.

## Quality gates

CI runs on every push: ruff + mypy + pytest (backend, against live
Postgres/Redis), ESLint + tsc + vitest + production build (frontend), an OWASP
ZAP baseline scan, and Playwright E2E against the full Docker stack.

```bash
# backend checks
cd backend && ruff check . && mypy app/ && pytest
# frontend checks
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Security posture

Refresh-token rotation with Redis revocation, Postgres RLS on every user
table, double-submit CSRF state on OAuth, strict CORS allow-list, security
headers (nosniff, frame-deny, HSTS in production), rate limiting on every
sensitive endpoint, PII masking in logs, and a production boot guard that
refuses default secrets. Details in [docs/SECURITY.md](docs/SECURITY.md).
