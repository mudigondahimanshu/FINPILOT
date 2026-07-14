"""Budget CRUD routes. Live progress is served by /transactions/summary/budgets."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, rate_limit
from app.core.database import get_db, set_rls_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetRead, BudgetUpdate
from app.schemas.transaction import CategoryRead

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _to_read(b: Budget) -> BudgetRead:
    return BudgetRead(
        id=b.id,
        category_id=b.category_id,
        category_name=b.category.name if b.category else "Unknown",
        amount=b.amount,
        period=b.period,
        alert_threshold=b.alert_threshold,
    )


@router.get("/categories", response_model=list[CategoryRead])
async def list_categories(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[CategoryRead]:
    """System categories plus the caller's custom ones — for budget pickers."""
    await set_rls_user(session, current_user.id)
    rows = (
        (await session.execute(
            select(Category)
            .where(or_(Category.user_id.is_(None), Category.user_id == current_user.id))
            .order_by(Category.name)
        )).scalars().all()
    )
    return [CategoryRead.model_validate(c) for c in rows]


@router.get("", response_model=list[BudgetRead])
async def list_budgets(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[BudgetRead]:
    await set_rls_user(session, current_user.id)
    budgets = (
        (await session.execute(
            select(Budget)
            .where(Budget.user_id == current_user.id)
            .options(selectinload(Budget.category))
            .order_by(Budget.created_at)
        )).scalars().all()
    )
    return [_to_read(b) for b in budgets]


@router.post(
    "",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(20, 60, "budgets"))],
)
async def create_budget(
    data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BudgetRead:
    await set_rls_user(session, current_user.id)

    category = (
        (await session.execute(
            select(Category).where(
                Category.id == data.category_id,
                or_(Category.user_id.is_(None), Category.user_id == current_user.id),
            )
        )).scalar_one_or_none()
    )
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")

    existing = (
        (await session.execute(
            select(Budget).where(
                Budget.user_id == current_user.id, Budget.category_id == data.category_id
            )
        )).scalar_one_or_none()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Budget for this category already exists")

    budget = Budget(user_id=current_user.id, **data.model_dump())
    session.add(budget)
    await session.commit()
    await session.refresh(budget, ["category"])
    return _to_read(budget)


async def _get_or_404(session: AsyncSession, user_id: uuid.UUID, budget_id: uuid.UUID) -> Budget:
    await set_rls_user(session, user_id)
    budget = (
        (await session.execute(
            select(Budget)
            .where(Budget.id == budget_id, Budget.user_id == user_id)
            .options(selectinload(Budget.category))
        )).scalar_one_or_none()
    )
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Budget not found")
    return budget


@router.patch("/{budget_id}", response_model=BudgetRead)
async def update_budget(
    budget_id: uuid.UUID,
    data: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BudgetRead:
    budget = await _get_or_404(session, current_user.id, budget_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(budget, field, value)
    await session.commit()
    await session.refresh(budget, ["category"])
    return _to_read(budget)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_budget(
    budget_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    budget = await _get_or_404(session, current_user.id, budget_id)
    await session.delete(budget)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
