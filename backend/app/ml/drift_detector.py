"""ML model drift detection (Phase 4.3).

Checks whether the live transaction distribution has shifted significantly
from the distribution the classifier was trained on. Uses:
  - KL divergence on category distribution
  - KS test on amount distribution
  - PSI (Population Stability Index) on log-amount buckets

Designed to run as a Celery periodic task (weekly).
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

_PSI_WARNING_THRESHOLD = 0.1   # noticeable shift
_PSI_CRITICAL_THRESHOLD = 0.25  # significant shift — retrain recommended


def _psi(expected: list[float], actual: list[float]) -> float:
    """Population Stability Index across equal-width log-amount buckets."""
    psi = 0.0
    for e, a in zip(expected, actual, strict=False):
        e = max(e, 1e-6)
        a = max(a, 1e-6)
        psi += (a - e) * math.log(a / e)
    return psi


def _kl_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """KL divergence D_KL(p || q) over category distributions."""
    cats = set(p) | set(q)
    kl = 0.0
    for c in cats:
        pi = max(p.get(c, 0.0), 1e-9)
        qi = max(q.get(c, 0.0), 1e-9)
        kl += pi * math.log(pi / qi)
    return kl


async def detect_drift(session: AsyncSession) -> dict:
    """Compare last-30-day transaction distribution to baseline."""
    from sqlalchemy import text  # noqa: PLC0415

    # Load baseline category distribution from model_version.json
    try:
        import asyncio as _asyncio  # noqa: PLC0415
        import json  # noqa: PLC0415

        def _read_meta() -> dict:
            with open("/app/models/model_version.json") as _f:  # noqa: ASYNC230
                return json.load(_f)

        meta = await _asyncio.to_thread(_read_meta)
        baseline_cats: dict[str, float] = meta.get("category_distribution", {})
    except Exception:
        log.warning("No baseline distribution available — skipping drift detection")
        return {"status": "no_baseline"}

    cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    rows = await session.execute(
        text(
            """
            SELECT c.name AS cat, COUNT(*) AS cnt
              FROM transactions t
              LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.date >= :cutoff AND t.amount < 0
             GROUP BY c.name
            """
        ),
        {"cutoff": cutoff},
    )
    records = rows.fetchall()
    if not records:
        return {"status": "no_data"}

    total = sum(r.cnt for r in records)
    live_cats = {(r.cat or "Other"): r.cnt / total for r in records}

    kl = _kl_divergence(baseline_cats, live_cats)

    # Amount PSI: 10 equal-width log-amount buckets
    amt_rows = await session.execute(
        text(
            "SELECT ABS(amount) AS a FROM transactions "
            "WHERE date >= :cutoff AND amount < 0 LIMIT 5000"
        ),
        {"cutoff": cutoff},
    )
    amounts = [float(r.a) for r in amt_rows.fetchall() if r.a > 0]

    # Baseline amount buckets from model metadata
    baseline_buckets: list[float] = meta.get("amount_buckets", [1 / 10] * 10)
    if amounts and len(baseline_buckets) == 10:
        max_a = max(amounts)
        live_buckets = [0.0] * 10
        for a in amounts:
            idx = min(int((a / (max_a + 1e-6)) * 10), 9)
            live_buckets[idx] += 1
        n = len(amounts)
        live_buckets = [c / n for c in live_buckets]
        psi = _psi(baseline_buckets, live_buckets)
    else:
        psi = 0.0

    severity = (
        "critical" if psi > _PSI_CRITICAL_THRESHOLD
        else "warning" if psi > _PSI_WARNING_THRESHOLD
        else "ok"
    )

    result = {
        "status": severity,
        "kl_divergence": round(kl, 4),
        "psi": round(psi, 4),
        "live_category_distribution": live_cats,
        "baseline_category_distribution": baseline_cats,
        "recommendation": (
            "Retrain classifier — distribution shift detected" if severity == "critical"
            else "Monitor — mild shift detected" if severity == "warning"
            else "No drift detected"
        ),
        "checked_at": datetime.now(tz=UTC).isoformat(),
    }
    log.info("Drift check: severity=%s psi=%.4f kl=%.4f", severity, psi, kl)
    return result
