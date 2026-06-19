"""A/B testing framework (Phase 3.6).

Simple deterministic 90/10 split:
  - 90% of users → "control"
  - 10% of users → "treatment"

Assignment is deterministic per (user_id, experiment) using SHA-256 hashing,
so the same user always gets the same variant. Assignments are also persisted
in `ab_assignments` for analysis.

Usage:
    variant = await get_or_assign(session, user_id, experiment="bandit_v2")
    if variant == "treatment":
        # show new recommendation strategy
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

# Experiments registry: name → treatment fraction (0.0 – 1.0)
EXPERIMENTS: dict[str, float] = {
    "bandit_v2": 0.10,          # 10% get new bandit algorithm
    "insights_widget": 0.20,    # 20% see AI insights widget on dashboard
    "forecast_v2": 0.15,        # 15% get improved forecast model
}


def _deterministic_variant(user_id: uuid.UUID, experiment: str, treatment_frac: float) -> str:
    """Assign variant deterministically via SHA-256 hashing. No DB required."""
    key = f"{user_id}:{experiment}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    # Use first 8 hex chars as a 32-bit integer → value in [0, 1)
    bucket = int(digest[:8], 16) / 0xFFFF_FFFF
    return "treatment" if bucket < treatment_frac else "control"


async def get_or_assign(
    session: AsyncSession,
    user_id: uuid.UUID,
    experiment: str,
) -> str:
    """Return the variant for *user_id* in *experiment*, persisting the assignment.

    If an assignment already exists in the DB, return it.
    Otherwise compute deterministically and persist.
    """
    from sqlalchemy import text  # noqa: PLC0415

    row = await session.execute(
        text("SELECT variant FROM ab_assignments WHERE user_id = :uid AND experiment = :exp"),
        {"uid": str(user_id), "exp": experiment},
    )
    existing = row.fetchone()
    if existing:
        return str(existing.variant)

    treatment_frac = EXPERIMENTS.get(experiment, 0.10)
    variant = _deterministic_variant(user_id, experiment, treatment_frac)

    try:
        await session.execute(
            text(
                """
                INSERT INTO ab_assignments (id, user_id, experiment, variant, assigned_at)
                VALUES (:id, :uid, :exp, :variant, :ts)
                ON CONFLICT (user_id, experiment) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "uid": str(user_id),
                "exp": experiment,
                "variant": variant,
                "ts": datetime.now(UTC),
            },
        )
        await session.commit()
    except Exception as exc:
        log.warning("A/B assignment insert failed: %s", exc)
        await session.rollback()

    return variant


async def get_experiment_summary(session: AsyncSession, experiment: str) -> dict:
    """Return per-variant counts for analysis."""
    from sqlalchemy import text  # noqa: PLC0415

    rows = await session.execute(
        text(
            """
            SELECT variant, COUNT(*) AS n
              FROM ab_assignments
             WHERE experiment = :exp
             GROUP BY variant
            """
        ),
        {"exp": experiment},
    )
    counts = {r.variant: int(r.n) for r in rows.fetchall()}
    total = sum(counts.values())
    return {
        "experiment": experiment,
        "total_assigned": total,
        "variants": counts,
        "split": {k: round(v / (total + 1e-9), 3) for k, v in counts.items()},
    }
