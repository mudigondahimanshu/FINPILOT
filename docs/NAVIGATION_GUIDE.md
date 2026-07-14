# FinPilot — Navigation Guide

A map of every page and the API surface behind it.

## Pages

### `/` — Landing
Marketing page with sign-in / register CTAs. Unauthenticated only.

### `/login`, `/register`
Email + password auth, plus "Continue with Google" when OAuth is configured.
OAuth errors land back here with a readable message. `/auth/callback`
completes the Google flow (token arrives in the URL fragment, never logged).

### `/dashboard` — Overview
Single-call dashboard (`GET /overview`):
- **Cash-flow hero** — this month's net flow typeset over the last 30 days of
  daily spending; delta vs last month; income/out/savings-rate satellites.
- **Budgets / Goals / Subscriptions panels** — top items with progress, each
  linking to its page.
- **Income vs expenses** (6 months) and **category donut**.
- Recent transactions.

### `/transactions` — Spending
Paginated transaction table with filters and search, add/edit/delete, CSV
import, ML auto-categorisation, and spending charts.
APIs: `GET/POST/PATCH/DELETE /transactions`, `POST /transactions/import/csv`,
`GET /transactions/summary/spending`, `POST /ml/classify/auto`.

### `/budgets`
Create a monthly limit per category; cards show live spent/remaining with
colour-coded progress (green → amber > 80% → red over). Edit the limit inline;
delete from the card.
APIs: `GET/POST/PATCH/DELETE /budgets`, `GET /budgets/categories`,
`GET /transactions/summary/budgets`.

### `/goals`
Savings goals with radial progress, contributions, and two projections:
*"at your pace"* (from your 6-month average net savings) and *"needed per
month"* (when a target date is set).
APIs: `GET/POST/PATCH/DELETE /goals`, `POST /goals/{id}/contribute`.

### `/subscriptions`
Recurring payments detected from transaction history (≥ 2 months, stable
amount): cadence chip, next-charge estimate, monthly-equivalent cost, and
price-increase flags. Nothing to configure.
API: `GET /subscriptions`.

### `/insights` — AI Insights
- **AI Copilot** — chat grounded in the knowledge base *and* the user's own
  spending, budgets, goals, and subscriptions. Works with zero API keys;
  optional server-side Groq/Gemini/Anthropic/Ollama upgrade.
- **Spending forecast** — 30-day ARIMA + Reservoir-LSTM ensemble with
  confidence band.
- **Fraud guard** — Isolation Forest outliers, velocity alerts, payment-cycle
  detection.
- **Subscription watch** — price-increase alerts inline.
APIs: `POST /ml/copilot/chat`, `GET /ml/forecast/spending`, `GET /ml/fraud`,
`GET /subscriptions`.

## Backend surface (summary)

| Router | Prefix | Highlights |
|---|---|---|
| auth | `/auth` | register, login, refresh (rotating), logout, me, Google OAuth |
| mfa | `/mfa` | TOTP enrol/verify |
| transactions | `/transactions` | CRUD, CSV import, summaries (spending/budgets/recurring/fraud) |
| budgets | `/budgets` | CRUD + category list |
| goals | `/goals` | CRUD + contribute |
| overview | `/overview`, `/subscriptions` | dashboard aggregate, recurring-payment detector |
| ml | `/ml` | classify, forecast, fraud, copilot, recommendations, A/B, drift |
| health | `/health` | liveness |
