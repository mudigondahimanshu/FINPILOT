# FinPilot — System Architecture

> Educational personal-finance OS. Paper trading only. Not financial advice.

## 1. High-Level System Diagram

```
                              ┌──────────────────────────────┐
                              │           Clients            │
                              │  Web (Next.js)  Mobile (RN)  │
                              └───────────────┬──────────────┘
                                              │ HTTPS / WSS
                                              ▼
                    ┌──────────────────────────────────────────────┐
                    │            FastAPI Backend (async)            │
                    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
                    │  │  Auth  │ │  Txns  │ │ Trading│ │Copilot │  │
                    │  │  JWT   │ │  CSV   │ │ Orders │ │  RAG   │  │
                    │  └────────┘ └────────┘ └────────┘ └────────┘  │
                    │  REST + GraphQL + WebSocket (/ws/prices)      │
                    └───┬───────────┬───────────┬───────────┬───────┘
                        │           │           │           │
            ┌───────────▼──┐  ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────────┐
            │ PostgreSQL15 │  │   Redis   │ │  ML    │ │  Algorithms  │
            │ + TimescaleDB│  │ cache /   │ │ Service│ │  (in-proc)   │
            │ + pgvector   │  │ pub-sub / │ │ ONNX / │ │  order-book  │
            │              │  │ blacklist │ │ XGB /  │ │  optimizer   │
            │ users, txns, │  │ rate-lim  │ │ LSTM / │ │  fraud-graph │
            │ OHLC, embeds │  │           │ │ FinBERT│ │              │
            └──────────────┘  └─────┬─────┘ └───┬────┘ └──────────────┘
                                    │           │
                              ┌─────▼───────────▼─────┐
                              │  Celery Worker(s)     │
                              │  retraining, alerts,  │
                              │  RSS sentiment scrape │
                              └───────────────────────┘

        External (free) APIs: yfinance · Finnhub · Alpha Vantage · RSS news
        LLM: Mistral-7B (LoRA) + LangChain RAG over pgvector
```

## 2. Services & Responsibilities

| Service | Responsibility | Key tech |
|---------|----------------|----------|
| **frontend** | Web UI, dashboards, trading, copilot chat | Next.js 14, React 18, TS, Tailwind, shadcn/ui, TanStack Query, Recharts/D3 |
| **backend** | REST/GraphQL/WS API, auth, business logic | FastAPI, Pydantic v2, SQLAlchemy 2 async, asyncpg |
| **db** | OLTP + time-series + vector store | PostgreSQL 15, TimescaleDB, pgvector |
| **redis** | Cache, pub/sub price fan-out, JWT blacklist, rate-limit token bucket, Celery broker | Redis 7 |
| **worker** | Async jobs: weekly retrain, budget/fraud alerts, RSS sentiment | Celery |
| **ml** | Model training + inference (classifier, forecasting, anomaly, sentiment, RAG, LLM) | PyTorch, XGBoost, scikit-learn, ONNX, LangChain |
| **algorithms** | Pure DSA/DAA: order matching, portfolio optimizer, fraud graph, data structures | Python (heapq, NetworkX, cvxpy) |

## 3. Data Flow — Core Loop

1. **Onboard** → user enters salary, spend, goals (REST → Postgres).
2. **Ingest** → CSV upload / manual entry → parse → XGBoost classifier auto-categorizes → stored in TimescaleDB hypertable `transactions`.
3. **Analyze** → LSTM spend forecast + portfolio risk score; donut/trend charts on dashboard.
4. **Paper trade** → live quote (yfinance/Finnhub via Redis-cached) → order matching engine (min/max heaps) → virtual fills → P&L.
5. **Copilot** → query → embed → pgvector top-5 retrieval → LLM grounded answer + citations + "educational only" disclaimer.
6. **Learn** → log recommendation + accept/reject → contextual bandit → weekly Celery retrain → per-user preference embedding.
7. **Protect** → every login/trade/transfer → fraud graph (BFS/DFS/cycles) + Isolation Forest + velocity/geo checks → real-time alert.

## 4. Security Architecture (summary)

- **AuthN:** bcrypt (cost 12) passwords, JWT access (15m) + refresh (7d), OAuth2 Google, MFA TOTP, WebAuthn (Phase 4).
- **AuthZ:** Postgres Row-Level Security per user; FastAPI dependency guards.
- **Secrets:** `.env` locally, AWS Secrets Manager in prod. Never in code.
- **Data:** PII tokenization, pgcrypto field-level encryption, parameterized SQL only.
- **Transport:** cookies `httpOnly`/`secure`/`sameSite=Strict`; CORS allow-list.
- **Abuse:** Redis token-bucket rate limiting (5/min auth per IP, 100/min per user).
- **Audit:** append-only `audit_log` of sensitive actions. No PII in logs.

## 5. Environments

- **Local:** `docker compose up` → all services on one host network.
- **Cloud (AWS):** ECS (backend, ml, worker), S3+CloudFront (frontend), RDS Postgres Multi-AZ, ElastiCache Redis, Secrets Manager. Terraform-managed. (Phase 4)
- **Observability:** Prometheus + Grafana, structured JSON logs (ELK/CloudWatch), drift detection on ML inputs. (Phase 4)

## 6. Repository Layout

See `README.md` "PROJECT FOLDER STRUCTURE". Monorepo with independent service roots; shared contracts via OpenAPI (`docs/api`) and typed clients in `frontend/lib`.

## 7. Key Algorithm Notes

- **Order matching:** dual heaps — buy max-heap, sell min-heap; match when `best_bid >= best_ask`; O(log n) insert/match.
- **Portfolio optimizer:** Markowitz mean-variance via cvxpy; maximize Sharpe; weights ≥ 0, Σw = 1.
- **Fraud graph:** NetworkX `G=(V,E)`; BFS connected components (mule nets), DFS cycle detection (laundering), betweenness centrality (hubs).
- **LSTM forecast:** 2-layer LSTM (128u, dropout 0.2), 30-day window in → 30-day out + ±1σ; Adam/MSE, early stop; ONNX CPU inference < 500ms.
