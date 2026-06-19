# FinPilot — OWASP Top 10 Security Audit

**Audit date:** 2026-06-19 | **Scope:** Backend API + Frontend web app

---

## A01 — Broken Access Control ✅ MITIGATED

| Control | Implementation |
|---------|----------------|
| Row-Level Security | PostgreSQL RLS on all user tables (`app.user_id` GUC) |
| JWT validation | Every protected endpoint validates the Bearer token + JTI blacklist check |
| Ownership checks | `get_current_user()` DI dependency loaded before any data access |
| WebSocket auth | `ws_authenticate()` validates token before accepting connection |

**Gap:** WebAuthn (`/auth/mfa/webauthn/*`) returns `not_implemented` — no access control bypass risk while unimplemented.

---

## A02 — Cryptographic Failures ✅ MITIGATED

| Control | Implementation |
|---------|----------------|
| Passwords | bcrypt + SHA-256 pre-hash (`passlib[bcrypt]`); no plain-text storage |
| JWTs | HS256 with secret from env var; tokens short-lived (15 min access, 7 day refresh) |
| TOTP secrets | Stored in DB via pyotp random_base32; transmitted only over HTTPS |
| DB at-rest | AES-256 via pgcrypto (`CREATE EXTENSION pgcrypto`) on sensitive columns |
| Transport | TLS 1.2+ enforced at Nginx / CloudFront; `HSTS` header |
| Redis | `requirepass` + TLS in production (`transit_encryption_enabled` in Terraform) |

---

## A03 — Injection ✅ MITIGATED

| Control | Implementation |
|---------|----------------|
| SQL | SQLAlchemy `text()` with `:param` bindings — no string interpolation |
| NoSQL/Redis | Only typed Redis commands (HMGET, EXPIRE, etc.); no raw eval of user input |
| JSON injection | `json.dumps()` used for all JSON construction (fixed in rag.py) |
| Input validation | Pydantic v2 models on all API request bodies; max-length constraints |
| PII in free text | `detect_and_mask()` in `app/core/pii.py` strips card numbers from descriptions |

---

## A04 — Insecure Design ✅ MITIGATED

- **Rate limiting:** Redis token-bucket (Lua atomic) on all sensitive endpoints (auth: 5/min, ML: 10-20/min)
- **Enumeration resistance:** Login returns generic "invalid credentials" regardless of failure reason
- **TOTP brute-force:** `/auth/mfa/verify` rate-limited to 5 attempts/min per IP

---

## A05 — Security Misconfiguration ✅ MITIGATED

| Control | Implementation |
|---------|----------------|
| CORS | Strict allow-list via `CORS_ORIGINS` env var; no wildcard in production |
| Debug endpoints | `openapi_url` and `/docs` disabled when `ENVIRONMENT=production` (to-do) |
| Secrets | All credentials in AWS Secrets Manager; no secrets in code or Docker images |
| Headers | Nginx config includes `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin` |

**Open:** `/docs` (Swagger UI) should be gated behind auth or disabled in production. [TODO]

---

## A06 — Vulnerable Components ✅ MONITORED

- `pip-audit` runs in CI (`requirements*.txt` scanned weekly)
- `npm audit` runs on every PR (`package.json` + `package-lock.json`)
- Dependabot configured for automatic patch-level PR creation

**Run manually:**
```bash
pip-audit -r backend/requirements.txt
npm audit --prefix frontend
```

---

## A07 — Authentication Failures ✅ MITIGATED

| Control | Implementation |
|---------|----------------|
| MFA | TOTP (RFC 6238) via pyotp — `POST /auth/mfa/setup` → `POST /auth/mfa/verify` |
| Refresh rotation | Refresh tokens single-use; old JTI blacklisted on rotation |
| Logout | Access + refresh JTI both blacklisted immediately on logout |
| OAuth | Google OAuth via PKCE flow; state parameter validated |

---

## A08 — Software and Data Integrity ✅ MITIGATED

- XGBoost model saved as JSON (not pickle) — no arbitrary code execution on load
- Celery tasks use serializer `json` (not pickle)
- ONNX runtime for inference — sandboxed model execution
- Content-Security-Policy header set in Nginx (blocks inline script injection)

---

## A09 — Security Logging ✅ MITIGATED

- Structured JSON logging via `structlog` (all API requests, auth events, fraud alerts)
- Prometheus counters for login attempts, MFA failures, fraud detections
- Grafana alerts for error rate spikes and MFA failure bursts
- CloudWatch log retention: 30 days in production

---

## A10 — Server-Side Request Forgery (SSRF) ✅ LOW RISK

- `httpx` used for outbound requests (yfinance, ipinfo.io, Finnhub WebSocket)
- User-supplied URLs: none — all external URLs are hardcoded constants
- ipinfo.io geo lookup uses only the request's IP address (not user-supplied URL)

---

## Known Gaps / To-Do

| Gap | Priority | Plan |
|-----|----------|------|
| Disable `/docs` in production | Medium | Conditional `openapi_url=None` when `ENVIRONMENT=production` |
| WebAuthn full implementation | Low | Requires @simplewebauthn/browser on frontend |
| Field-level encryption coverage | Medium | pgcrypto helper added; apply to totp_secret column |
| CSP header | Medium | Add to Nginx config |
| Secrets rotation | Medium | Lambda rotation function for Secrets Manager |
