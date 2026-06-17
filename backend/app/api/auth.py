"""Authentication routes: register, login, refresh (rotating), logout, me."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
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
from app.services import auth_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
# Brief mandates secure cookies; relax only in local dev so http://localhost works.
_COOKIE_SECURE = settings.environment != "development"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
        path="/auth",
        max_age=settings.refresh_token_expire_days * 24 * 3600,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/auth")


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
