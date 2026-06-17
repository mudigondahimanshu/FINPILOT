# FinPilot — AI-Powered Personal Finance Copilot

> Personal finance OS that learns you, predicts your future, and teaches you to trade smarter.

## Progress Tracker

**Current Phase:** Phase 1 — MVP
**Last Updated:** 2026-06-17

> ⚠️ **Educational use only. Paper trading only. Not financial advice.**

---

## PHASE 1: Foundation & MVP
### 1.1 Project Setup
- [x] Initialize monorepo structure
- [x] Setup Next.js 14 frontend (TypeScript, Tailwind, shadcn/ui)
- [x] Setup FastAPI backend (Python, async, Pydantic)
- [x] Setup PostgreSQL + TimescaleDB
- [x] Setup Redis
- [x] Docker Compose for full local dev
- [x] Environment variables + secrets management
- [x] GitHub Actions CI/CD skeleton
- [ ] Validate: All services start with `docker compose up`  ⛔ _blocked: Docker not installed on this machine (see DEVLOG)_

### 1.2 Authentication System
- [x] User registration (email + password, bcrypt hash)
- [x] User login → JWT access token (15min) + refresh token (7d)
- [x] OAuth2 Google login  _(Authorization Code flow + double-submit CSRF state cookie; dormant until creds set)_
- [x] Protected routes middleware (frontend + backend)  _(Next.js middleware cookie gate + in-app RequireAuth guard; backend RLS guard)_
- [x] JWT refresh flow  _(with refresh-token rotation)_
- [x] Logout + token invalidation (Redis blacklist)
- [x] Row-Level Security (RLS) policies on Postgres  _(users table; GUC-based, FORCE RLS)_
- [ ] Validate: Auth flow E2E test passes  _(test written + wired into CI w/ Postgres+Redis; runs there / under Docker)_

### 1.3 Database Schema
- [ ] Users table
- [ ] Accounts table (bank accounts)
- [ ] Transactions table (TimescaleDB)
- [ ] Categories table
- [ ] Budgets table
- [ ] Portfolios table
- [ ] Trades table
- [ ] Audit log table
- [ ] Alembic migrations working
- [ ] Validate: Schema applied, migrations reversible

### 1.4 Transaction Management
- [ ] CSV upload and parsing
- [ ] Manual transaction entry
- [ ] Transaction list UI with filters (date, category, amount)
- [ ] Spending by category breakdown
- [ ] Monthly trend chart (Recharts)
- [ ] Budget alerts (email when over limit)
- [ ] Subscription detector (recurring charge identification)
- [ ] Validate: 1000 transactions load in < 1s

### 1.5 Dashboard (Phase 1)
- [ ] Dark/light theme toggle (default dark)
- [ ] Savings rate widget
- [ ] Monthly spending summary card
- [ ] Category breakdown (donut chart)
- [ ] Recent transactions list
- [ ] Budget progress bars
- [ ] Responsive layout (desktop + mobile)
- [ ] Validate: Lighthouse score > 85

---

## PHASE 2: Algorithms Engine

### 2.1 Market Data Integration
- [ ] Integrate yfinance (free) for NSE/BSE stock data
- [ ] Integrate Finnhub API (free tier) for real-time quotes
- [ ] OHLC data stored in TimescaleDB
- [ ] Ticker search with autocomplete (Trie data structure)
- [ ] Stock detail page (price, chart, fundamentals)
- [ ] WebSocket for live price feed
- [ ] Redis pub/sub for fan-out to multiple clients
- [ ] Validate: Live price updates in < 500ms

### 2.2 Paper Trading Engine
- [ ] Virtual portfolio (default ₹1,00,000 capital)
- [ ] Buy/sell order forms
- [ ] Order matching engine (priority queue — min/max heap)
- [ ] Trade execution at live market price
- [ ] P&L calculation (unrealized + realized)
- [ ] Trade history table
- [ ] Portfolio holdings breakdown
- [ ] Watchlist management
- [ ] Validate: Order matching engine unit tests pass (O(log n) complexity verified)

### 2.3 Portfolio Optimizer
- [ ] Markowitz Modern Portfolio Theory implementation
- [ ] Efficient frontier calculation
- [ ] Sharpe ratio maximization (quadratic optimization)
- [ ] Suggested allocation by risk tolerance
- [ ] Risk score (0-100) for current portfolio
- [ ] Rebalancing suggestions
- [ ] Validate: Optimizer produces valid allocations (weights sum to 1, non-negative)

### 2.4 DSA Showcase
- [ ] Order book: min/max heap with O(log n) insertion/deletion
- [ ] Ticker autocomplete: Trie with prefix search
- [ ] Moving averages: Monotonic queue (sliding window)
- [ ] LRU cache for market data
- [ ] Graph: Transaction adjacency list for fraud
- [ ] Validate: All data structures benchmarked and documented

---

## PHASE 3: AI Brain

### 3.1 Transaction Classifier (ML)
- [ ] Feature engineering (amount, merchant name, time)
- [ ] XGBoost classifier for 15+ spending categories
- [ ] Training pipeline (Python script)
- [ ] Inference endpoint in FastAPI
- [ ] Auto-categorize on transaction upload
- [ ] Confidence score display in UI
- [ ] Manual override (user corrects → feeds training data)
- [ ] Validate: > 90% accuracy on test set

### 3.2 Forecasting (Deep Learning)
- [ ] LSTM model for spend forecasting (30-day horizon)
- [ ] ARIMA baseline (compare with LSTM)
- [ ] Stock price forecasting (LSTM + Transformer)
- [ ] Confidence intervals on predictions
- [ ] ONNX export for fast inference
- [ ] Forecast dashboard widget (30-day spend projection)
- [ ] Validate: RMSE < 15% on hold-out set

### 3.3 Sentiment Analysis
- [ ] Integrate FinBERT (Hugging Face)
- [ ] News headline scraper (RSS: Economic Times, Mint, Bloomberg)
- [ ] Sentiment score per stock
- [ ] News feed with sentiment badges in trading UI
- [ ] Validate: Sentiment labels match human evaluation on 100 samples

### 3.4 Fraud Detection
- [ ] Transaction graph builder (nodes = users/merchants, edges = transfers)
- [ ] BFS/DFS connected components (detect mule networks)
- [ ] Cycle detection (money laundering patterns)
- [ ] Isolation Forest for behavior anomaly scoring
- [ ] Velocity checks (N trades in T seconds)
- [ ] Geolocation anomaly (unusual login country/time)
- [ ] Real-time fraud alert (< 200ms)
- [ ] Validate: 0 false negatives on synthetic attack dataset

### 3.5 RAG Copilot
- [ ] Document ingestion pipeline (SEBI regulations, financial PDFs)
- [ ] Text chunking + embedding (text-embedding-3-small or local)
- [ ] Store embeddings in pgvector
- [ ] Semantic retrieval (top-5 relevant chunks per query)
- [ ] Fine-tune 7B Mistral with LoRA on financial Q&A dataset
- [ ] RAG chain (LangChain: retrieve → condition LLM → answer with citations)
- [ ] Chat UI with conversation history
- [ ] Reasoning display ("I said this because...")
- [ ] Thumbs up/down feedback logging
- [ ] Validate: Grounded answers on 20 financial Q&A test cases

### 3.6 Online Learning System
- [ ] Log every recommendation + user action (accept/reject)
- [ ] Contextual bandit for recommendation (explore/exploit)
- [ ] Weekly retraining pipeline (Celery + cron)
- [ ] Per-user preference embedding (vector in Postgres)
- [ ] A/B testing framework (10% test vs 90% control)
- [ ] Model versioning (save checkpoints, tag by date)
- [ ] Validate: Recommendation acceptance rate improves week-over-week (simulated)

---

## PHASE 4: Security + Production

### 4.1 Security Hardening
- [ ] MFA: TOTP (Google Authenticator)
- [ ] Passwordless: WebAuthn (biometric/security key)
- [ ] PII tokenization (credit card → tok_xxx, SSN → hash)
- [ ] Field-level encryption (pgcrypto on sensitive columns)
- [ ] CORS hardening (allow-list only)
- [ ] Rate limiting: Redis token bucket (100 req/min per user)
- [ ] Input validation: Pydantic + Zod schemas everywhere
- [ ] SQL injection prevention: parameterized queries only
- [ ] OWASP Top 10 audit
- [ ] Dependency vulnerability scan (pip-audit + npm audit)
- [ ] Validate: OWASP ZAP scan passes

### 4.2 Infrastructure & Deployment
- [ ] Dockerfiles for all services (frontend, backend, ml, worker)
- [ ] Docker Compose (dev + production variants)
- [ ] AWS: ECS task definitions for backend + ml
- [ ] AWS: S3 + CloudFront for frontend
- [ ] AWS: RDS Postgres (Multi-AZ)
- [ ] AWS: ElastiCache Redis
- [ ] AWS: Secrets Manager for all credentials
- [ ] Terraform scripts for all above
- [ ] Validate: Full stack deploys to AWS from scratch in < 30min

### 4.3 Monitoring & Observability
- [ ] Prometheus metrics (API latency, error rate, fraud detections)
- [ ] Grafana dashboards (system health + business metrics)
- [ ] Structured logging (JSON, ELK or CloudWatch)
- [ ] Uptime monitoring + alerting (PagerDuty or SNS)
- [ ] ML model drift detection (data distribution shift alerts)
- [ ] Validate: Alert fires within 60s of simulated outage

### 4.4 Testing
- [ ] Backend: pytest unit tests (90%+ coverage)
- [ ] Frontend: Vitest + React Testing Library
- [ ] Integration tests: API contract tests
- [ ] E2E tests: Playwright (full user flows)
- [ ] Load testing: k6 (1000 concurrent users)
- [ ] ML tests: data validation (Great Expectations)
- [ ] Validate: All test suites green in CI

### 4.5 Mobile App
- [ ] React Native (Expo) setup
- [ ] Auth screens
- [ ] Dashboard (reuse API, mobile-optimized UI)
- [ ] Trading screen
- [ ] Push notifications (fraud alerts, budget warnings)
- [ ] Validate: Runs on iOS simulator + Android emulator

---

## Quick Reference

### Tech Stack
| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, shadcn/ui |
| Charts | Recharts + D3.js |
| State | TanStack Query (React Query) |
| Backend | FastAPI, Python 3.11, Pydantic v2 |
| Auth | JWT, OAuth2, bcrypt, WebAuthn |
| Task Queue | Celery + Redis |
| Database | PostgreSQL 15 + TimescaleDB + pgvector |
| Cache | Redis |
| ML | PyTorch, XGBoost, Scikit-learn, ONNX |
| LLM | Mistral 7B (LoRA fine-tune), LangChain |
| NLP | FinBERT (Hugging Face) |
| Market Data | yfinance, Finnhub API, Alpha Vantage |
| Deployment | Docker, AWS ECS, Lambda, RDS, CloudFront |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Monitoring | Prometheus, Grafana, ELK stack |
| Testing | pytest, Vitest, Playwright, k6 |

### API Endpoints (high-level)
- `POST /auth/register` — create account
- `POST /auth/login` — get JWT tokens
- `GET /dashboard/summary` — overview stats
- `GET /transactions` — paginated transaction list
- `POST /transactions/upload` — CSV upload
- `GET /portfolio` — current holdings + P&L
- `POST /trades/order` — place paper trade
- `GET /market/quote/:ticker` — live stock quote
- `POST /copilot/chat` — RAG copilot message
- `GET /forecast/spending` — 30-day spend forecast
- `GET /forecast/risk-score` — portfolio risk score
- `WS /ws/prices` — live price WebSocket

---

## Getting Started (local dev)

```bash
# 1. Copy environment template and fill in secrets
cp .env.example .env

# 2. Start the full stack (Postgres+TimescaleDB+pgvector, Redis, backend, frontend)
docker compose up --build

# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000  (docs at /docs)
# Postgres:  localhost:5432
# Redis:     localhost:6379
```

Without Docker, run services individually — see `frontend/README` notes and `backend/` (uvicorn) instructions in `ARCHITECTURE.md`.

---

## Important Constraints

- **Paper trading only** (educational). No real payment processing or live brokerage.
- **Legal disclaimer** on every trading screen: _"This is for educational purposes only. Not financial advice."_
- Market data from **free APIs** (yfinance, Finnhub free tier, Alpha Vantage free).
- **LLM fine-tuning:** LoRA (PEFT) only, 7B model max.
- Cloud target: **AWS** primary, Azure secondary. Free tier where possible.
- **India-first** (NSE/BSE) with architecture for global expansion.
