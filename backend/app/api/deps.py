"""Shared FastAPI dependencies: auth guard and rate limiting."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, set_rls_user
from app.core.redis_client import is_blacklisted, rate_limit_ok
from app.core.security import decode_token
from app.models.user import User
from app.services import auth_service

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Validate the access token, reject blacklisted/expired, load the user."""
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    if await is_blacklisted(payload["jti"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token revoked"
        )

    user = await auth_service.get_user_by_id(session, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found"
        )

    # Scope subsequent queries on this session to the authenticated user (RLS).
    await set_rls_user(session, user.id)
    return user


def rate_limit(
    capacity: int, window_seconds: int, scope: str
) -> Callable[[Request], Awaitable[None]]:
    """Per-IP token-bucket limiter. Auth endpoints use 5/min per the brief."""

    async def _dep(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"{scope}:{client_ip}"
        if not await rate_limit_ok(identifier, capacity, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many requests, slow down",
            )

    return _dep
