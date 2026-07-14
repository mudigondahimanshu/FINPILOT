"""Overview dashboard + subscriptions routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit
from app.core.database import get_db
from app.models.user import User
from app.services import insights_service

router = APIRouter(tags=["overview"])


@router.get("/overview", dependencies=[Depends(rate_limit(30, 60, "overview"))])
async def get_overview(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Single-call aggregate powering the overview dashboard."""
    return await insights_service.overview(session, current_user.id)


@router.get("/subscriptions", dependencies=[Depends(rate_limit(30, 60, "subscriptions"))])
async def get_subscriptions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Detected recurring payments with cadence, next-due and price-drift info."""
    return await insights_service.subscriptions(session, current_user.id)
