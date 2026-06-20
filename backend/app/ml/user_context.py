"""Per-user financial context for the personalized copilot (Phase 3.5+).

Assembles a compact natural-language snapshot of the signed-in user's finances —
spending summary, top categories, inferred risk profile, budget status, and
portfolio holdings — so the RAG copilot can ground its answers in the user's
actual data instead of replying generically.

Every section is best-effort: if a query fails or the user has no data for it,
that section is skipped rather than failing the whole chat request.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.ml import user_preferences as user_prefs
from app.services import transaction_service as txn_svc

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


async def build_financial_context(session: AsyncSession, user_id: uuid.UUID) -> str:
    """Return a compact text block describing the user's finances, or "" if no data."""
    sections: list[str] = []

    sections.append(await _spending_section(session, user_id))
    sections.append(await _preferences_section(session, user_id))
    sections.append(await _budget_section(session, user_id))
    sections.append(await _portfolio_section(session, user_id))

    body = "\n".join(s for s in sections if s)
    if not body.strip():
        return ""
    return "USER FINANCIAL PROFILE (use this to personalize your answer):\n" + body


async def _spending_section(session: AsyncSession, user_id: uuid.UUID) -> str:
    try:
        summary = await txn_svc.spending_summary(session, user_id)
    except Exception as exc:
        log.debug("context: spending_summary failed: %s", exc)
        return ""
    if not summary.monthly_trend:
        return ""

    top_cats = sorted(
        (c for c in summary.by_category if c.total < 0),
        key=lambda c: c.total,
    )[:5]
    cats_str = ", ".join(
        f"{c.category_name} (₹{abs(float(c.total)):,.0f})" for c in top_cats
    )
    return (
        f"- Income (all time): ₹{float(summary.total_income):,.0f}; "
        f"Expenses: ₹{float(summary.total_expenses):,.0f}; "
        f"Savings rate: {float(summary.savings_rate) * 100:.0f}%\n"
        f"- Top spending categories: {cats_str or 'none yet'}"
    )


async def _preferences_section(session: AsyncSession, user_id: uuid.UUID) -> str:
    try:
        prefs = await user_prefs.get_preferences(session, user_id)
    except Exception as exc:
        log.debug("context: get_preferences failed: %s", exc)
        return ""
    if not prefs:
        return ""
    return f"- Inferred risk profile: {prefs.get('risk_profile', 'unknown')}"


async def _budget_section(session: AsyncSession, user_id: uuid.UUID) -> str:
    try:
        budgets = await txn_svc.budget_status(session, user_id)
    except Exception as exc:
        log.debug("context: budget_status failed: %s", exc)
        return ""
    if not budgets:
        return ""

    over = [b for b in budgets if b.over_budget]
    near = [
        b for b in budgets
        if not b.over_budget and float(b.utilisation) >= float(b.alert_threshold)
    ]
    parts = [f"- Active budgets: {len(budgets)}"]
    if over:
        parts.append(
            "over budget: " + ", ".join(f"{b.category_name}" for b in over)
        )
    if near:
        parts.append(
            "near limit: " + ", ".join(f"{b.category_name}" for b in near)
        )
    return "\n".join(parts) if len(parts) > 1 else parts[0]


async def _portfolio_section(session: AsyncSession, user_id: uuid.UUID) -> str:
    # Imported lazily: portfolio_service pulls live quotes and is heavier than the
    # transaction queries, so we keep it out of the module import path.
    try:
        from app.services import portfolio_service as pf_svc  # noqa: PLC0415

        summary = await pf_svc.get_portfolio_summary(session, user_id)
    except Exception as exc:
        log.debug("context: portfolio_summary failed: %s", exc)
        return ""

    open_holdings = [h for h in summary.holdings if float(h.quantity) > 0]
    if not open_holdings:
        return f"- Portfolio: ₹{float(summary.portfolio.cash_balance):,.0f} cash, no open positions"

    holds_str = ", ".join(
        f"{h.symbol} ({float(h.quantity):g} sh)" for h in open_holdings[:8]
    )
    pnl = summary.total_pnl
    pnl_str = f"₹{float(pnl):,.0f}" if pnl is not None else "n/a"
    return (
        f"- Portfolio: ₹{float(summary.portfolio.cash_balance):,.0f} cash; "
        f"holdings: {holds_str}; total P&L: {pnl_str}"
    )
