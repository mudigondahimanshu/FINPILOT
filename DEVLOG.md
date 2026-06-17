# FinPilot Dev Log

## 2026-06-17 — Task In Progress: 1.2 Authentication System (backend core)

**What was built:**
- `User` ORM model + Alembic migration `0001_users` with Postgres **Row-Level Security**
  (GUC `app.user_id` for self-access, `app.auth_ctx` controlled bypass for pre-auth
  lookups, `FORCE ROW LEVEL SECURITY` so policies bind even the table owner).
- Security core: bcrypt (cost 12) password hashing + JWT access (15m) / refresh (7d)
  with `jti` claims for revocation.
- Redis helpers: JWT blacklist + atomic **token-bucket rate limiter** (Lua).
- Auth service (register / authenticate, user-enumeration-resistant) + Pydantic v2
  schemas (password strength validation).
- Routes: `POST /auth/register`, `/login`, `/refresh` (rotating), `/logout`
  (blacklists access + refresh), `GET /auth/me`. Refresh token in an httpOnly,
  SameSite=Strict cookie; rate limit 5/min per IP on register/login.
- `get_current_user` dependency (decodes access token, checks blacklist, scopes the
  DB session to the user via RLS GUC).
- Tests: `test_security.py` (DB-free unit), `test_auth_flow.py` (E2E, skipped unless
  `FINPILOT_INTEGRATION=1`). CI now provisions Postgres + Redis, runs `alembic upgrade
  head`, and executes the integration test.

**Tech used:**
- `bcrypt` (direct) + SHA-256 pre-hash (Django `bcrypt_sha256` pattern); `python-jose`
  for JWT; `redis.asyncio`; SQLAlchemy 2 async; Alembic.

**Why this approach:**
- **Dropped `passlib`** — running the unit tests revealed passlib 1.7.4 is broken with
  bcrypt 4.x (`module 'bcrypt' has no attribute '__about__'` + a spurious 72-byte
  error). Switched to the `bcrypt` lib directly with a SHA-256 pre-hash: keeps cost 12,
  removes the 72-byte ceiling, and drops an unmaintained dependency.
- Refresh-token rotation + blacklist gives real logout/invalidation semantics.
- RLS via session GUCs keeps a single DB role while enforcing per-user isolation.

**Tests passed / validation run (locally, Python 3.14 venv):**
- ruff: **All checks passed**.
- mypy: **Success, no issues** (19 files).
- pytest: **7 passed, 1 skipped** (integration auto-skips without DB/Redis).
- App imports cleanly with auth router mounted (verified via TestClient).

**Issues/notes:**
- passlib→bcrypt swap (above) was a real bug caught by running tests, not just compiling.
- E2E auth validation (`test_auth_flow`) requires the stack; it runs in CI (Postgres+Redis
  services) and will run locally once Docker is up.
- B008 (Depends-in-defaults) is FastAPI-idiomatic → whitelisted in ruff config rather
  than rewritten.
- **Still TODO in 1.2:** OAuth2 Google login, frontend auth UI + protected-route
  middleware. Order note: introduced the `users` table here (Task 1.3 will add the rest).

---

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
- Directory structure verified against the brief (all paths present, 75 files committed).
- JSON validated (`package.json`, `tsconfig.json`, `components.json`, `.eslintrc.json`) — all parse.
- Python backend syntax validated — `py_compile` passes on every `backend/**/*.py`.
- `git init` + clean initial commit; verified no `.env`, `.claude/`, `.remember/`, or brief staged.
- ⏳ YAML parse of `docker-compose.yml` / `ci.yml` deferred — `pyyaml` not installed and pip network is sandboxed here. Files are standard; will validate when Docker is available.
- ⛔ **Could NOT run `docker compose up`** — Docker is not installed on this machine (`docker: command not found`). This is the one Phase 1.1 validation gate that is blocked. Frontend/backend dependency installs (`npm install`, `pip install`) were not run this turn either (heavy; intended to run inside Docker).

**Issues/notes:**
- **Docker missing** → the headline 1.1 validation ("all services start with docker compose up") cannot be executed here. Need the user to either install Docker Desktop or approve running services natively (native Postgres/Redis + uvicorn + next dev).
- Local Python is **3.14**; brief specifies **3.11**. Fine for scaffolding, but ML wheels (torch/xgboost) and some libs may lack 3.14 builds — backend container pins 3.11 to stay on the supported track.

---
