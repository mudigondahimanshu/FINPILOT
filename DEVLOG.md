# FinPilot Dev Log

## 2026-06-17 — Task Completed: 1.1 Project Setup (scaffolding)

**What was built:**
- Full monorepo directory structure (`frontend/`, `backend/`, `ml/`, `algorithms/`, `infra/`, `docs/`) exactly per the brief.
- Root docs: `README.md` (master checklist), `DEVLOG.md`, `ARCHITECTURE.md`.
- `.env.example` (all service secrets templated), `.gitignore`, `.dockerignore`.
- `docker-compose.yml` for full local dev: TimescaleDB+pgvector Postgres, Redis, backend (FastAPI), frontend (Next.js), Celery worker.
- DB init script enabling `timescaledb` + `vector` extensions.
- Next.js 14 frontend scaffold: App Router, TypeScript, Tailwind, theme tokens (dark default), Inter + JetBrains Mono fonts, indigo `#6366F1` accent, base UI primitives, landing page with required disclaimer.
- FastAPI backend scaffold: async app factory, Pydantic-v2 settings, structured config, health endpoint, CORS, router layout (`api/`, `core/`, `models/`, `schemas/`, `services/`, `websocket/`).
- Dockerfiles per service (frontend, backend, worker).
- GitHub Actions CI skeleton (frontend lint/typecheck/build + backend ruff/mypy/pytest).
- `git init` with initial scaffolding commit.

**Tech used:**
- Next.js 14.2 (App Router), React 18, TypeScript 5, Tailwind CSS 3, next-themes for theme toggle.
- FastAPI, Pydantic v2 / pydantic-settings, Uvicorn, SQLAlchemy 2 (async), asyncpg.
- TimescaleDB image (`timescale/timescaledb-ha:pg15`) which bundles pgvector; Redis 7.
- Docker Compose v2 spec.

**Why this approach:**
- Hand-wrote scaffold files (instead of `create-next-app`) to bake in the brief's exact design tokens and avoid interactive generators.
- `timescaledb-ha` Postgres image gives TimescaleDB + pgvector in one container — satisfies both the time-series (OHLC/transactions) and vector (RAG) requirements from a single DB service.
- Async SQLAlchemy + asyncpg chosen to match FastAPI's async-first design and the brief's "async" requirement.

**Tests passed / validation run:**
- Directory structure verified against the brief (all paths present).
- `docker-compose.yml`, `package.json`, `tsconfig.json` validated as parseable.
- ⛔ **Could NOT run `docker compose up`** — Docker is not installed on this machine (`docker: command not found`). This is the one Phase 1.1 validation gate that is blocked. Frontend/backend dependency installs (`npm install`, `pip install`) were not run this turn either (heavy; intended to run inside Docker).

**Issues/notes:**
- **Docker missing** → the headline 1.1 validation ("all services start with docker compose up") cannot be executed here. Need the user to either install Docker Desktop or approve running services natively (native Postgres/Redis + uvicorn + next dev).
- Local Python is **3.14**; brief specifies **3.11**. Fine for scaffolding, but ML wheels (torch/xgboost) and some libs may lack 3.14 builds — backend container pins 3.11 to stay on the supported track.

---
