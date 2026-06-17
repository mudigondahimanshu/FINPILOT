"""Async SQLAlchemy engine + session factory and declarative base."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models (defined in app/models)."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a scoped async session."""
    async with SessionLocal() as session:
        yield session


async def set_rls_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Scope this transaction to one user (RLS `app.user_id`). Self-access only."""
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )


async def set_auth_ctx(session: AsyncSession) -> None:
    """Enable the controlled RLS bypass for pre-auth lookups (login/registration)."""
    await session.execute(text("SELECT set_config('app.auth_ctx', 'on', true)"))
