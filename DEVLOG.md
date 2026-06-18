# FinPilot Dev Log

## 2026-06-18 — Task Completed: 1.3 Database Schema

**What was built:**
- **9 ORM models** (SQLAlchemy 2 async, `Mapped[]`, `TYPE_CHECKING` guards to avoid
  circular imports): `Account`, `Category`, `Transaction`, `Budget`, `Portfolio`,
  `Trade`, `AuditLog`, `Embedding`.
- **Alembic migration `0002_schema`** (revises `0001_users`):
  - All 8 tables created with FK constraints + composite indexes.
  - `transactions` promoted to a **TimescaleDB hypertable** partitioned on `date`
    (7-day chunks). Composite PK `(id, date)` required by TimescaleDB.
  - **11 system categories** seeded (Food, Transport, Shopping, Entertainment, Health,
    Utilities, Travel, Education, Salary, Investments, Other) with lucide-react icons
    and hex colours.
  - `embeddings` table: `vector(1536)` column (pgvector) + **HNSW ANN index**
    (`vector_cosine_ops`) for Phase 2 RAG. JSONB shadow column keeps the ORM import
    clean (no pgvector Python package needed at import time).
  - **RLS** on every user-owned table: `<table>_self` (app.user_id GUC) +
    `<table>_auth_ctx` bypass. Categories get a special policy allowing system rows
    (user_id IS NULL) to be globally readable.
- **Indexes**: `(user_id, date)` + `(user_id, category_id)` on transactions for the
  two dominant query patterns; per-table user_id, portfolio_id, symbol indexes.
- Back-references wired into `User` model (accounts, categories, transactions,
  budgets, portfolios, trades).

**Tech used:**
- TimescaleDB `create_hypertable()` called via raw SQL in migration.
- pgvector `vector(1536)` column + HNSW index via raw DDL.
- Alembic helpers `_enable_rls`, `_self_policy`, `_auth_ctx_policy` to DRY up the
  repeated RLS boilerplate across 7 tables.

**Why this approach:**
- Composite PK `(id, date)` on transactions: TimescaleDB requires the partition
  column in the PK; UUID-only PK would cause a constraint violation on hypertable
  creation.
- HNSW over IVFFlat for pgvector: better recall at query time without needing a
  training step (IVFFlat requires `ANALYZE` before it performs).
- JSONB shadow on `embeddings.vector_json`: lets the ORM and migration tooling
  work without the pgvector Python package installed; the real `vector` column lives
  alongside it via raw DDL.

**Tests passed / validation run (locally):**
- ruff: **All checks passed** (27 files).
- mypy: **Success, no issues** (27 files).
- pytest: **7 passed, 1 skipped**.
- Migration downgrade `0002 → 0001` (all 8 tables dropped) then upgrade back —
  **clean round-trip**.
- DB inspect: all 10 tables present; `transactions` confirmed as hypertable
  (TimescaleDB `hypertables` view); 11 system categories seeded.

---

## 2026-06-17 — Phase 1.1 + 1.2 Validation: Full Stack Operational

Docker now installed. **Both validation gates passed:**
1. **`docker compose up`** — All 5 services boot + healthy (timescaledb + redis + uvicorn w/ migrations + next dev + celery worker). Frontend responds on `:3000`, backend health on `:8000`.
2. **Auth flow E2E** — Full cycle verified: register → me (bearer) → dup-reject → login → wrong-pwd → refresh (rotate) → logout → revoke. All 8 tests passed.

Fixed in this push:
- Frontend Dockerfile: added `dev` stage; compose targets it (was missing npm install).
- Backend compose command: auto-runs `alembic upgrade head` before uvicorn (was manual).
- Created `.env` with auto-generated JWT secret (gitignored).

---

## 2026-06-17 — Task Completed: 1.2 Authentication System (OAuth + frontend)

**What was built:**
- **Google OAuth2** (Authorization Code flow): routes `GET /auth/google/login`
  (sets a short-lived httpOnly `oauth_state` cookie, redirects to consent) and
  `GET /auth/google/callback` (double-submit CSRF check via `secrets.compare_digest`,
  code→token exchange, userinfo fetch, find-or-create/link user, issues the token
  pair, hands the access token to the SPA via URL **fragment**, sets the refresh
  cookie). Dormant with a clean 503 until `GOOGLE_CLIENT_ID/SECRET` are set.
- Widened the refresh cookie `path` from `/auth` to `/` so the Next.js middleware
  can read its presence to gate routes (token stays httpOnly — never JS-readable).
- **Frontend auth (full design pass):** split-panel auth shell (atmospheric indigo
  aurora + engineering grid, staggered `rise` load animation) on the brief's tokens;
  `/login` + `/register` pages (live password-rule checklist mirroring the backend,
  inline error surfacing, Google button), `/auth/callback` token-adoption page.
- **Session plumbing:** `AuthProvider` (in-memory access token — never localStorage;
  silent refresh on mount via the httpOnly cookie; `login`/`register`/`logout`/
  `adoptToken`), `authFetch` (bearer attach + single transparent 401→refresh→retry,
  with concurrent-refresh coalescing).
- **Route protection:** `middleware.ts` (cookie-presence gate; bounces anon users to
  `/login?redirect=…`, and authed users away from auth pages) + an in-app
  `RequireAuth` guard. Protected `(app)/dashboard` shell (sidebar + topbar, user
  avatar/initials, logout) with placeholder KPI cards.

**Tech used:**
- Backend: `httpx` (async Google calls), `secrets` (state + constant-time compare),
  FastAPI `RedirectResponse`.
- Frontend: Next.js App Router route groups, `next/navigation`, React context,
  Tailwind tokens, lucide-react icons. No new dependencies added.

**Why this approach:**
- **Access token in memory, refresh in an httpOnly cookie** — XSS can't read the
  long-lived credential; CSRF is contained by SameSite=Strict + the bearer model.
- **OAuth token via URL fragment** (not query) — fragments never hit a server or
  access logs; the callback page strips it from the address bar immediately.
- **Double-submit `oauth_state` cookie** — stateless CSRF protection for the OAuth
  round-trip without server-side session storage.

**Tests passed / validation run (locally):**
- Backend — ruff: **All checks passed**; mypy: **no issues (20 files)**; pytest:
  **7 passed, 1 skipped** (integration auto-skips without DB/Redis).
- Frontend — `tsc --noEmit`: **clean**; `next lint`: **no warnings/errors**;
  `next build`: **success** (8 routes prerendered + middleware compiled).

**Issues/notes:**
- S105 false positive on `_GOOGLE_TOKEN_URL` (string contains "token") → `# noqa`.
- `useSearchParams` on `/login` is wrapped in `<Suspense>` per Next 14's CSR-bailout
  requirement so the page still prerenders.
- Full OAuth E2E (real Google round-trip) needs live credentials; the local flow is
  exercised structurally. Email/password E2E runs in CI (Postgres+Redis).

---

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
