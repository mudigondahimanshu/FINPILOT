"""Online learning / recommendation bandit (Phase 3.6).

Epsilon-greedy contextual bandit for recommendation personalisation.
- Arms     : spending categories (15) or optimiser presets (3)
- Context  : user's spending profile (embedding or summary stats)
- Feedback : thumbs-up / thumbs-down stored in recommendation_feedback table
- Exploit  : pick arm with highest observed reward
- Explore  : with probability epsilon pick a random arm
- Retraining: Celery task (weekly) re-estimates arm values from logged feedback
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

EPSILON = float(os.getenv("BANDIT_EPSILON", "0.15"))
ARMS = [
    "food_alert", "transport_alert", "shopping_alert", "budget_exceeded",
    "savings_tip", "investment_suggestion", "subscription_review",
    "forecast_warning", "duplicate_charge", "round_amount_flag",
]


# ── Core bandit logic ─────────────────────────────────────────────────────────

class EpsilonGreedyBandit:
    """Stateless epsilon-greedy bandit; arm values loaded from DB each call."""

    def __init__(self, epsilon: float = EPSILON) -> None:
        self.epsilon = epsilon

    def select(self, arm_values: dict[str, float]) -> str:
        if random.random() < self.epsilon or not arm_values:  # noqa: S311
            return random.choice(ARMS)  # noqa: S311
        return max(arm_values, key=lambda a: arm_values[a])


_bandit = EpsilonGreedyBandit()


# ── DB helpers ────────────────────────────────────────────────────────────────

async def log_impression(
    session: AsyncSession,
    user_id: uuid.UUID,
    arm: str,
    context: dict,
) -> str:
    """Record that *arm* was shown to *user_id*; return the impression id."""
    from sqlalchemy import text  # noqa: PLC0415
    imp_id = str(uuid.uuid4())
    await session.execute(
        text(
            """
            INSERT INTO recommendation_feedback
                (id, user_id, arm, context, shown_at)
            VALUES (:id, :uid, :arm, :ctx::jsonb, :ts)
            """
        ),
        {
            "id": imp_id,
            "uid": str(user_id),
            "arm": arm,
            "ctx": str(context).replace("'", '"'),
            "ts": datetime.now(UTC),
        },
    )
    await session.commit()
    return imp_id


async def log_feedback(
    session: AsyncSession,
    impression_id: str,
    accepted: bool,
) -> None:
    """Record whether the user accepted (thumbs-up) the recommendation."""
    from sqlalchemy import text  # noqa: PLC0415
    await session.execute(
        text(
            """
            UPDATE recommendation_feedback
               SET accepted = :accepted, responded_at = :ts
             WHERE id = :id
            """
        ),
        {"accepted": accepted, "ts": datetime.now(UTC), "id": impression_id},
    )
    await session.commit()


async def get_arm_values(session: AsyncSession) -> dict[str, float]:
    """Compute average reward per arm from logged feedback."""
    from sqlalchemy import text  # noqa: PLC0415
    result = await session.execute(
        text(
            """
            SELECT arm,
                   COUNT(*) FILTER (WHERE accepted IS NOT NULL)  AS n,
                   AVG(CASE WHEN accepted THEN 1.0 ELSE 0.0 END) AS reward
              FROM recommendation_feedback
             GROUP BY arm
            """
        )
    )
    return {row.arm: float(row.reward or 0.0) for row in result.fetchall()}


# ── Recommendation API ────────────────────────────────────────────────────────

async def recommend(
    session: AsyncSession,
    user_id: uuid.UUID,
    context: dict,
) -> dict:
    """Select and log the next recommendation for *user_id*."""
    arm_values = await get_arm_values(session)
    arm = _bandit.select(arm_values)
    impression_id = await log_impression(session, user_id, arm, context)
    return {
        "impression_id": impression_id,
        "recommendation": arm,
        "explore": arm not in arm_values or random.random() < EPSILON,  # noqa: S311
    }


# ── Celery retraining task ────────────────────────────────────────────────────

def register_celery_tasks(celery_app: object) -> None:
    """Register weekly bandit summary task with the provided Celery app."""
    from celery import shared_task  # noqa: PLC0415

    @shared_task(name="bandit.weekly_summary")
    def weekly_bandit_summary() -> dict:
        return asyncio.run(_weekly_summary_async())

    return weekly_bandit_summary  # noqa: RET504


async def _weekly_summary_async() -> dict:
    """Compute per-arm acceptance rates for monitoring."""
    from app.core.database import SessionLocal  # noqa: PLC0415
    async with SessionLocal() as session:
        values = await get_arm_values(session)
    log.info("Weekly bandit summary: %s", values)
    return values
