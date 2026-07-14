"""Cross-feature aggregations: subscription detection + the overview dashboard.

Pure read-model queries over the user's transactions, budgets, and goals —
no external APIs, so every panel renders instantly and works offline.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import set_rls_user
from app.services import goal_service
from app.services import transaction_service as txn_svc

# ── Subscriptions / recurring payments ────────────────────────────────────────

async def subscriptions(session: AsyncSession, user_id: uuid.UUID) -> dict:
    """Detect recurring payments with cadence, next-due estimate and price drift.

    A merchant is "recurring" when the same normalised description appears in
    ≥ 2 distinct months with a stable amount. Cadence is estimated from the
    average gap between occurrences.
    """
    await set_rls_user(session, user_id)
    q = text(
        """
        SELECT
            lower(trim(description))                          AS norm_desc,
            max(merchant)                                     AS merchant,
            round(avg(abs(amount))::numeric, 2)               AS avg_amount,
            count(*)                                          AS occurrences,
            count(DISTINCT to_char(date, 'YYYY-MM'))          AS distinct_months,
            max(date)                                         AS last_date,
            min(date)                                         AS first_date,
            (array_agg(abs(amount) ORDER BY date DESC))[1]    AS last_amount
        FROM transactions
        WHERE user_id = :uid AND amount < 0
        GROUP BY norm_desc
        HAVING count(DISTINCT to_char(date, 'YYYY-MM')) >= 2
           AND stddev_samp(abs(amount)) IS NOT NULL
           AND stddev_samp(abs(amount)) < greatest(avg(abs(amount)) * 0.25, 50)
        ORDER BY avg_amount DESC
        LIMIT 40
        """
    )
    rows = (await session.execute(q, {"uid": str(user_id)})).mappings().all()

    items: list[dict] = []
    monthly_total = 0.0
    now = datetime.now(UTC)
    for r in rows:
        first, last = r["first_date"], r["last_date"]
        occurrences = int(r["occurrences"])
        span_days = max((last - first).days, 1)
        cadence_days = round(span_days / max(occurrences - 1, 1))
        # Snap to common billing cycles for readability.
        if 25 <= cadence_days <= 35:
            cadence, cadence_days = "monthly", 30
        elif 5 <= cadence_days <= 9:
            cadence, cadence_days = "weekly", 7
        elif 80 <= cadence_days <= 100:
            cadence, cadence_days = "quarterly", 91
        elif 330 <= cadence_days <= 400:
            cadence, cadence_days = "yearly", 365
        else:
            cadence = f"every {cadence_days} days"

        next_due = last + timedelta(days=cadence_days)
        avg_amount = float(r["avg_amount"])
        last_amount = float(r["last_amount"])
        price_change_pct = (
            round((last_amount - avg_amount) / avg_amount * 100, 1) if avg_amount else 0.0
        )
        monthly_equiv = round(avg_amount * 30 / cadence_days, 2)
        monthly_total += monthly_equiv

        # A subscription is "active" if we'd expect another charge soon.
        active = (now.date() - last).days <= cadence_days * 2

        items.append({
            "name": (r["merchant"] or r["norm_desc"]).title(),
            "avg_amount": avg_amount,
            "last_amount": last_amount,
            "price_change_pct": price_change_pct,
            "cadence": cadence,
            "occurrences": occurrences,
            "last_date": last.isoformat(),
            "next_due": next_due.isoformat(),
            "monthly_equivalent": monthly_equiv,
            "active": active,
        })

    active_items = [i for i in items if i["active"]]
    return {
        "subscriptions": items,
        "active_count": len(active_items),
        "monthly_total": round(sum(i["monthly_equivalent"] for i in active_items), 2),
        "price_increases": [
            i for i in active_items if i["price_change_pct"] >= 5.0
        ],
    }


# ── Overview dashboard ────────────────────────────────────────────────────────

async def overview(session: AsyncSession, user_id: uuid.UUID) -> dict:
    """Everything the overview dashboard needs, in one round-trip."""
    await set_rls_user(session, user_id)

    # Current + previous month income/expense in one query.
    month_q = text(
        """
        SELECT
            to_char(date, 'YYYY-MM')                                   AS month,
            sum(CASE WHEN amount > 0 THEN amount ELSE 0 END)           AS income,
            sum(CASE WHEN amount < 0 THEN abs(amount) ELSE 0 END)      AS expenses
        FROM transactions
        WHERE user_id = :uid
          AND date >= date_trunc('month', now()) - interval '1 month'
        GROUP BY 1 ORDER BY 1
        """
    )
    months = {r["month"]: r for r in
              (await session.execute(month_q, {"uid": str(user_id)})).mappings().all()}
    this_key = datetime.now(UTC).strftime("%Y-%m")
    prev_key = (datetime.now(UTC).replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    def _month(key: str) -> dict:
        r = months.get(key)
        income = float(r["income"]) if r else 0.0
        expenses = float(r["expenses"]) if r else 0.0
        return {"income": income, "expenses": expenses, "net": round(income - expenses, 2)}

    summary = await txn_svc.spending_summary(session, user_id)
    budgets = await txn_svc.budget_status(session, user_id)
    goals = await goal_service.list_goals(session, user_id)
    subs = await subscriptions(session, user_id)
    daily = await txn_svc.daily_spend_series(session, user_id, days=30)

    return {
        "this_month": _month(this_key),
        "last_month": _month(prev_key),
        "all_time": {
            "income": float(summary.total_income),
            "expenses": float(summary.total_expenses),
            "savings_rate": float(summary.savings_rate),
        },
        "by_category": [
            {"name": c.category_name, "total": float(c.total), "color": c.category_color}
            for c in summary.by_category
        ][:8],
        "monthly_trend": [
            {"month": m.month, "income": float(m.income), "expenses": float(m.expenses)}
            for m in summary.monthly_trend
        ][-6:],
        "daily_spend_30d": daily,
        "budgets": [
            {
                "category": b.category_name,
                "budget": float(b.budget_amount),
                "spent": float(b.spent),
                "utilisation": float(b.utilisation),
                "over": b.over_budget,
            }
            for b in budgets
        ],
        "goals": [
            {
                "name": g.name,
                "icon": g.icon,
                "target": float(g.target_amount),
                "saved": float(g.saved_amount),
                "progress_pct": g.progress_pct,
            }
            for g in goals
        ],
        "subscriptions": {
            "active_count": subs["active_count"],
            "monthly_total": subs["monthly_total"],
            "upcoming": sorted(
                (s for s in subs["subscriptions"] if s["active"]),
                key=lambda s: s["next_due"],
            )[:5],
            "price_increases": subs["price_increases"][:3],
        },
    }
