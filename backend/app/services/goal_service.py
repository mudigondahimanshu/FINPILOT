"""Savings goals: CRUD + progress projections from real savings history."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import set_rls_user
from app.models.goal import Goal
from app.models.transaction import Transaction
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate


async def _avg_monthly_net_savings(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """Average net savings (income - expenses) per month over the last 6 months."""
    since = datetime.now(UTC) - timedelta(days=183)
    q = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.user_id == user_id, Transaction.date >= since)
    )
    net = Decimal((await session.execute(q)).scalar_one())
    return net / 6


def _to_read(goal: Goal, monthly_savings: Decimal) -> GoalRead:
    remaining = goal.target_amount - goal.saved_amount
    progress = float(goal.saved_amount / goal.target_amount) if goal.target_amount else 0.0

    projected: date | None = None
    if remaining <= 0:
        projected = date.today()
    elif monthly_savings > 0:
        months = float(remaining / monthly_savings)
        projected = date.today() + timedelta(days=round(months * 30.44))

    monthly_needed: Decimal | None = None
    if goal.target_date and remaining > 0:
        months_left = max(
            Decimal((goal.target_date - date.today()).days) / Decimal("30.44"), Decimal("0.1")
        )
        monthly_needed = (remaining / months_left).quantize(Decimal("0.01"))

    return GoalRead(
        id=goal.id,
        name=goal.name,
        icon=goal.icon,
        target_amount=goal.target_amount,
        saved_amount=goal.saved_amount,
        target_date=goal.target_date,
        progress_pct=round(min(progress, 1.0) * 100, 1),
        projected_completion=projected,
        monthly_needed=monthly_needed,
    )


async def list_goals(session: AsyncSession, user_id: uuid.UUID) -> list[GoalRead]:
    await set_rls_user(session, user_id)
    goals = (
        (await session.execute(
            select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at)
        )).scalars().all()
    )
    monthly = await _avg_monthly_net_savings(session, user_id) if goals else Decimal(0)
    return [_to_read(g, monthly) for g in goals]


async def create_goal(session: AsyncSession, user_id: uuid.UUID, data: GoalCreate) -> GoalRead:
    await set_rls_user(session, user_id)
    goal = Goal(user_id=user_id, **data.model_dump())
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return _to_read(goal, await _avg_monthly_net_savings(session, user_id))


async def get_goal(session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal | None:
    await set_rls_user(session, user_id)
    return (
        (await session.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
        )).scalar_one_or_none()
    )


async def update_goal(
    session: AsyncSession, user_id: uuid.UUID, goal: Goal, data: GoalUpdate
) -> GoalRead:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await session.commit()
    await session.refresh(goal)
    return _to_read(goal, await _avg_monthly_net_savings(session, user_id))


async def contribute(
    session: AsyncSession, user_id: uuid.UUID, goal: Goal, amount: Decimal
) -> GoalRead:
    goal.saved_amount = max(goal.saved_amount + amount, Decimal(0))
    await session.commit()
    await session.refresh(goal)
    return _to_read(goal, await _avg_monthly_net_savings(session, user_id))


async def delete_goal(session: AsyncSession, goal: Goal) -> None:
    await session.delete(goal)
    await session.commit()
