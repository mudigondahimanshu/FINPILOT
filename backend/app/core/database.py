"""Async SQLAlchemy engine + session factory and declarative base."""

from __future__ import annotations

from collections.abc import AsyncGenerator

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
