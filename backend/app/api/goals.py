"""Savings goals REST routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit
from app.core.database import get_db
from app.models.goal import Goal
from app.models.user import User
from app.schemas.goal import GoalContribute, GoalCreate, GoalRead, GoalUpdate
from app.services import goal_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalRead])
async def list_goals(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[GoalRead]:
    return await goal_service.list_goals(session, current_user.id)


@router.post(
    "",
    response_model=GoalRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(20, 60, "goals"))],
)
async def create_goal(
    data: GoalCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GoalRead:
    return await goal_service.create_goal(session, current_user.id, data)


async def _get_or_404(session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
    goal = await goal_service.get_goal(session, user_id, goal_id)
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    return goal


@router.patch("/{goal_id}", response_model=GoalRead)
async def update_goal(
    goal_id: uuid.UUID,
    data: GoalUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GoalRead:
    goal = await _get_or_404(session, current_user.id, goal_id)
    return await goal_service.update_goal(session, current_user.id, goal, data)


@router.post("/{goal_id}/contribute", response_model=GoalRead)
async def contribute(
    goal_id: uuid.UUID,
    data: GoalContribute,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GoalRead:
    goal = await _get_or_404(session, current_user.id, goal_id)
    return await goal_service.contribute(session, current_user.id, goal, data.amount)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_goal(
    goal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    goal = await _get_or_404(session, current_user.id, goal_id)
    await goal_service.delete_goal(session, goal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
