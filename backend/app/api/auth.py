"""Authentication routes: register, login, refresh (rotating), logout, me."""

from __future__ import annotations

import secrets
import time
import uuid

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme, get_current_user, rate_limit
from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import blacklist_jti, is_blacklisted
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserRead,
)
from app.services import auth_service, oauth_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
OAUTH_STATE_COOKIE = "oauth_state"
# Brief mandates secure cookies; relax only in local dev so http://localhost works.
_COOKIE_SECURE = settings.environment != "development"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
        # Path "/" (not "/auth") so the Next.js middleware can read presence of
        # the cookie to gate protected routes; the token itself stays httpOnly.
        path="/",
        max_age=settings.refresh_token_expire_days * 24 * 3600,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/")


async def _blacklist_remaining(payload: dict) -> None:
    ttl = int(payload["exp"]) - int(time.time())
    await blacklist_jti(payload["jti"], ttl)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(5, 60, "auth"))],
)
async def register(
    data: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    try:
        user = await auth_service.register_user(session, data)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    pair = auth_service.issue_token_pair(user)
    _set_refresh_cookie(response, pair.refresh_token)
    return AuthResponse(access_token=pair.access_token, user=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit(5, 60, "auth"))],
)
async def login(
    data: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    try:
        user = await auth_service.authenticate(session, data.email, data.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    pair = auth_service.issue_token_pair(user)
    _set_refresh_cookie(response, pair.refresh_token)
    return AuthResponse(access_token=pair.access_token, user=UserRead.model_validate(user))


@router.post(
    "/refresh",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit(30, 60, "refresh"))],
)
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> AuthResponse:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing refresh token")
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    if await is_blacklisted(payload["jti"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token revoked")

    user = await auth_service.get_user_by_id(session, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")

    # Rotation: revoke the old refresh token, issue a fresh pair.
    await _blacklist_remaining(payload)
    access, _ = create_access_token(str(user.id))
    new_refresh, _ = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, new_refresh)
    return AuthResponse(access_token=access, user=UserRead.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> Response:
    # Revoke the access token so it can't be reused before it expires.
    try:
        access_payload = decode_token(credentials.credentials, expected_type="access")
        await _blacklist_remaining(access_payload)
    except ValueError:
        pass
    # Revoke the refresh token (if present) and clear the cookie.
    if refresh_token:
        try:
            refresh_payload = decode_token(refresh_token, expected_type="refresh")
            await _blacklist_remaining(refresh_payload)
        except ValueError:
            pass
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


# ── Google OAuth2 (Authorization Code flow) ──────────────────────────────────
# Dormant until GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are set. CSRF is enforced
# via a double-submit `oauth_state` cookie compared against the `state` round-trip.


def _require_google_configured() -> None:
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google sign-in is not configured",
        )


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    """Kick off Google sign-in: set a CSRF state cookie, redirect to consent."""
    _require_google_configured()
    state = secrets.token_urlsafe(32)
    url = oauth_service.build_authorization_url(state)
    redirect = RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    redirect.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",  # must survive the cross-site redirect back from Google
        path="/auth",
        max_age=600,
    )
    return redirect


@router.get("/google/callback")
async def google_callback(
    session: AsyncSession = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
) -> RedirectResponse:
    """Handle Google's redirect: verify CSRF, exchange code, sign the user in."""
    _require_google_configured()

    def _fail(reason: str) -> RedirectResponse:
        resp = RedirectResponse(
            f"{settings.frontend_url}/login?error={reason}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
        resp.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
        return resp

    if error or not code or not state:
        return _fail("oauth_denied")
    # Double-submit CSRF check: cookie state must match the query state.
    if not oauth_state or not secrets.compare_digest(oauth_state, state):
        return _fail("oauth_state_mismatch")

    try:
        google_token = await oauth_service.exchange_code(code)
        info = await oauth_service.fetch_userinfo(google_token)
        user = await oauth_service.find_or_create_user(session, info)
    except AuthError:
        return _fail("oauth_failed")

    pair = auth_service.issue_token_pair(user)
    # Hand the access token to the SPA via the URL fragment (never sent to a
    # server, not stored in logs); the refresh token rides in its httpOnly cookie.
    redirect = RedirectResponse(
        f"{settings.frontend_url}/auth/callback#access_token={pair.access_token}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _set_refresh_cookie(redirect, pair.refresh_token)
    redirect.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
    return redirect
