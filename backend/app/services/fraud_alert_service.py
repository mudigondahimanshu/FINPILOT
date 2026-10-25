"""Persist user review choices for fraud alerts."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import set_rls_user
from app.models.fraud_alert_decision import FraudAlertChoice, FraudAlertDecision
from app.models.transaction import Transaction


async def get_decisions(
    session: AsyncSession, user_id: uuid.UUID, transaction_ids: list[uuid.UUID]
) -> dict[str, str]:
    if not transaction_ids:
        return {}
    await set_rls_user(session, user_id)
    rows = (
        await session.execute(
            select(FraudAlertDecision).where(
                FraudAlertDecision.user_id == user_id,
                FraudAlertDecision.transaction_id.in_(transaction_ids),
            )
        )
    ).scalars()
    return {str(row.transaction_id): row.decision for row in rows}


async def save_decision(
    session: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
    decision: FraudAlertChoice,
) -> bool:
    """Save a choice, returning False when the transaction is not owned by the user."""
    await set_rls_user(session, user_id)
    transaction_exists = await session.scalar(
        select(Transaction.id).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    if transaction_exists is None:
        return False

    row = await session.get(FraudAlertDecision, (user_id, transaction_id))
    if row is None:
        row = FraudAlertDecision(
            user_id=user_id,
            transaction_id=transaction_id,
            decision=decision,
        )
        session.add(row)
    else:
        row.decision = decision
    await session.commit()
    return True
