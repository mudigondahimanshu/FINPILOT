"""Transaction business logic: CRUD, CSV import, aggregations, budget checks."""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import set_auth_ctx, set_rls_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.transaction import (
    BudgetStatus,
    CategorySpend,
    CsvUploadResult,
    MonthlyTrend,
    SpendingSummary,
    TransactionCreate,
    TransactionUpdate,
)

# ── CRUD ──────────────────────────────────────────────────────────────────────

async def list_transactions(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 50,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category_id: uuid.UUID | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    search: str | None = None,
) -> tuple[list[Transaction], int]:
    await set_rls_user(session, user_id)
    base = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .options(selectinload(Transaction.category))
    )
    if date_from:
        base = base.where(Transaction.date >= date_from)
    if date_to:
        base = base.where(Transaction.date <= date_to)
    if category_id:
        base = base.where(Transaction.category_id == category_id)
    if amount_min is not None:
        base = base.where(Transaction.amount >= amount_min)
    if amount_max is not None:
        base = base.where(Transaction.amount <= amount_max)
    if search:
        base = base.where(Transaction.description.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_q)).scalar_one()

    items_q = (
        base.order_by(Transaction.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(items_q)).scalars().all()
    return list(rows), total


async def get_transaction(
    session: AsyncSession, user_id: uuid.UUID, txn_id: uuid.UUID
) -> Transaction | None:
    await set_rls_user(session, user_id)
    q = (
        select(Transaction)
        .where(Transaction.id == txn_id, Transaction.user_id == user_id)
        .options(selectinload(Transaction.category))
    )
    return (await session.execute(q)).scalar_one_or_none()


async def create_transaction(
    session: AsyncSession, user_id: uuid.UUID, data: TransactionCreate
) -> Transaction:
    await set_rls_user(session, user_id)
    txn = Transaction(user_id=user_id, **data.model_dump())
    session.add(txn)
    await session.commit()
    await session.refresh(txn)
    return txn


async def update_transaction(
    session: AsyncSession,
    user_id: uuid.UUID,
    txn_id: uuid.UUID,
    data: TransactionUpdate,
) -> Transaction | None:
    txn = await get_transaction(session, user_id, txn_id)
    if txn is None:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(txn, field, value)
    await session.commit()
    await session.refresh(txn)
    return txn


async def delete_transaction(
    session: AsyncSession, user_id: uuid.UUID, txn_id: uuid.UUID
) -> bool:
    txn = await get_transaction(session, user_id, txn_id)
    if txn is None:
        return False
    await session.delete(txn)
    await session.commit()
    return True


# ── CSV import ────────────────────────────────────────────────────────────────

# Required CSV columns (case-insensitive). Optional: category, notes, merchant.
_REQUIRED = {"date", "amount", "description"}
_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]


def _parse_date(raw: str) -> datetime | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


async def _resolve_category(
    session: AsyncSession, user_id: uuid.UUID, name: str | None
) -> uuid.UUID | None:
    if not name:
        return None
    await set_auth_ctx(session)
    q = select(Category.id).where(
        func.lower(Category.name) == name.lower(),
        (Category.user_id == user_id) | (Category.user_id.is_(None)),
    )
    return (await session.execute(q)).scalar_one_or_none()


async def import_csv(
    session: AsyncSession, user_id: uuid.UUID, content: bytes
) -> CsvUploadResult:
    text_io = io.StringIO(content.decode("utf-8-sig"))
    reader = csv.DictReader(text_io)

    if reader.fieldnames is None:
        return CsvUploadResult(imported=0, skipped=0, errors=["Empty file or missing header row"])

    headers = {h.strip().lower() for h in reader.fieldnames}
    missing = _REQUIRED - headers
    if missing:
        return CsvUploadResult(
            imported=0, skipped=0,
            errors=[f"Missing required columns: {', '.join(sorted(missing))}"]
        )

    await set_rls_user(session, user_id)
    imported, skipped, errors = 0, 0, []

    for i, row in enumerate(reader, start=2):
        norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        date = _parse_date(norm.get("date", ""))
        if date is None:
            errors.append(f"Row {i}: unparseable date '{norm.get('date')}'")
            skipped += 1
            continue
        try:
            amount = Decimal(norm["amount"].replace(",", ""))
        except InvalidOperation:
            errors.append(f"Row {i}: invalid amount '{norm.get('amount')}'")
            skipped += 1
            continue

        description = norm.get("description", "").strip()
        if not description:
            errors.append(f"Row {i}: empty description")
            skipped += 1
            continue

        category_id = await _resolve_category(session, user_id, norm.get("category"))
        txn = Transaction(
            user_id=user_id,
            date=date,
            amount=amount,
            description=description,
            notes=norm.get("notes") or None,
            merchant=norm.get("merchant") or None,
            category_id=category_id,
            currency=norm.get("currency", "INR")[:3].upper() or "INR",
            source="csv_import",
        )
        session.add(txn)
        imported += 1

    if imported:
        await session.commit()

    return CsvUploadResult(imported=imported, skipped=skipped, errors=errors[:20])


# ── Aggregations ──────────────────────────────────────────────────────────────

async def spending_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SpendingSummary:
    await set_rls_user(session, user_id)

    # Category breakdown — single query joining categories.
    q = (
        select(
            Transaction.category_id,
            func.coalesce(Category.name, "Uncategorised").label("cat_name"),
            func.coalesce(Category.color, "#6B7280").label("cat_color"),
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("cnt"),
        )
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(Transaction.user_id == user_id)
        .group_by(Transaction.category_id, Category.name, Category.color)
    )
    if date_from:
        q = q.where(Transaction.date >= date_from)
    if date_to:
        q = q.where(Transaction.date <= date_to)

    rows = (await session.execute(q)).all()
    by_cat: list[CategorySpend] = [
        CategorySpend(
            category_id=r.category_id,
            category_name=r.cat_name,
            category_color=r.cat_color,
            total=r.total,
            count=r.cnt,
        )
        for r in rows
    ]

    # Monthly trend — group by year-month.
    month_q = (
        select(
            func.to_char(Transaction.date, "YYYY-MM").label("month"),
            func.sum(
                text("CASE WHEN amount > 0 THEN amount ELSE 0 END")
            ).label("income"),
            func.sum(
                text("CASE WHEN amount < 0 THEN amount ELSE 0 END")
            ).label("expenses"),
        )
        .where(Transaction.user_id == user_id)
        .group_by(text("month"))
        .order_by(text("month"))
    )
    if date_from:
        month_q = month_q.where(Transaction.date >= date_from)
    if date_to:
        month_q = month_q.where(Transaction.date <= date_to)

    month_rows = (await session.execute(month_q)).all()
    trend: list[MonthlyTrend] = [
        MonthlyTrend(
            month=r.month,
            income=r.income or Decimal(0),
            expenses=r.expenses or Decimal(0),
            net=(r.income or Decimal(0)) + (r.expenses or Decimal(0)),
        )
        for r in month_rows
    ]

    total_income = sum((r.income for r in trend), Decimal(0))
    total_expenses = abs(sum((r.expenses for r in trend), Decimal(0)))
    savings_rate = (
        (total_income - total_expenses) / total_income
        if total_income > 0
        else Decimal(0)
    )

    return SpendingSummary(
        by_category=by_cat,
        monthly_trend=trend,
        total_income=total_income,
        total_expenses=total_expenses,
        savings_rate=savings_rate,
    )


# ── Budget status ─────────────────────────────────────────────────────────────

async def budget_status(
    session: AsyncSession, user_id: uuid.UUID
) -> list[BudgetStatus]:
    await set_rls_user(session, user_id)

    # Current-month boundaries (UTC).
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    budgets_q = (
        select(Budget)
        .where(Budget.user_id == user_id)
        .options(selectinload(Budget.category))
    )
    budgets = (await session.execute(budgets_q)).scalars().all()

    # Aggregate spending per category for the current month in one query.
    spend_q = (
        select(
            Transaction.category_id,
            func.sum(Transaction.amount).label("spent"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.amount < 0,
            Transaction.date >= month_start,
        )
        .group_by(Transaction.category_id)
    )
    spend_map: dict[uuid.UUID | None, Decimal] = defaultdict(Decimal)
    for row in (await session.execute(spend_q)).all():
        spend_map[row.category_id] = abs(row.spent)

    result: list[BudgetStatus] = []
    for b in budgets:
        spent = spend_map.get(b.category_id, Decimal(0))
        remaining = b.amount - spent
        utilisation = spent / b.amount if b.amount > 0 else Decimal(0)
        result.append(
            BudgetStatus(
                budget_id=b.id,
                category_name=b.category.name if b.category else "Unknown",
                period=b.period,
                budget_amount=b.amount,
                spent=spent,
                remaining=remaining,
                utilisation=utilisation,
                alert_threshold=b.alert_threshold,
                over_budget=utilisation >= 1,
            )
        )
    return result


# ── Subscription / recurring detector ────────────────────────────────────────

async def detect_recurring(
    session: AsyncSession, user_id: uuid.UUID
) -> list[dict]:
    """Flag transactions that recur monthly (same merchant/description + similar amount)."""
    await set_rls_user(session, user_id)

    # Group by normalised description; flag those appearing in ≥ 3 distinct months.
    q = text(
        """
        SELECT
            lower(trim(description)) AS norm_desc,
            merchant,
            round(avg(amount)::numeric, 2) AS avg_amount,
            count(*) AS occurrences,
            count(DISTINCT to_char(date, 'YYYY-MM')) AS distinct_months
        FROM transactions
        WHERE user_id = :uid AND amount < 0
        GROUP BY norm_desc, merchant
        HAVING count(DISTINCT to_char(date, 'YYYY-MM')) >= 3
        ORDER BY distinct_months DESC
        LIMIT 50
        """
    )
    rows = (await session.execute(q, {"uid": str(user_id)})).mappings().all()
    return [dict(r) for r in rows]
