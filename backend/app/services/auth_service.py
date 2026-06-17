"""Authentication business logic: registration, credential check, token issuance."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import set_auth_ctx
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenPair


class AuthError(Exception):
    """Raised for any auth failure; mapped to HTTP 4xx in the router."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    await set_auth_ctx(session)  # RLS bypass for pre-auth lookup
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    await set_auth_ctx(session)
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(session: AsyncSession, data: RegisterRequest) -> User:
    if await get_user_by_email(session, data.email):
        raise AuthError("email already registered", status_code=409)

    await set_auth_ctx(session)
    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        auth_provider="local",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    # Constant-ish behaviour: always run a verify to reduce user-enumeration timing.
    if user is None or user.hashed_password is None:
        # Hash a dummy to keep timing comparable, then fail.
        verify_password(password, hash_password("dummy-password-0"))
        raise AuthError("invalid email or password", status_code=401)
    if not verify_password(password, user.hashed_password):
        raise AuthError("invalid email or password", status_code=401)
    if not user.is_active:
        raise AuthError("account disabled", status_code=403)
    return user


def issue_token_pair(user: User) -> TokenPair:
    access, _ = create_access_token(str(user.id))
    refresh, _ = create_refresh_token(str(user.id))
    return TokenPair(access_token=access, refresh_token=refresh)
