"""Transaction routes: CRUD, CSV upload, aggregations, budget status, recurring."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit
from app.core.database import get_db
from app.core.transaction_graph import (
    TransactionGraph,
    duplicate_transactions,
    round_number_anomalies,
)
from app.models.user import User
from app.schemas.transaction import (
    BudgetStatus,
    CsvUploadResult,
    SpendingSummary,
    TransactionCreate,
    TransactionPage,
    TransactionRead,
    TransactionUpdate,
)
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=TransactionPage)
async def list_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    amount_min: Decimal | None = Query(default=None),
    amount_max: Decimal | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TransactionPage:
    items, total = await transaction_service.list_transactions(
        session, current_user.id,
        page=page, page_size=page_size,
        date_from=date_from, date_to=date_to,
        category_id=category_id,
        amount_min=amount_min, amount_max=amount_max,
        search=search,
    )
    return TransactionPage(
        items=[TransactionRead.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
    )


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    data: TransactionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TransactionRead:
    txn = await transaction_service.create_transaction(session, current_user.id, data)
    return TransactionRead.model_validate(txn)


@router.get("/{txn_id}", response_model=TransactionRead)
async def get_transaction(
    txn_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TransactionRead:
    txn = await transaction_service.get_transaction(session, current_user.id, txn_id)
    if txn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return TransactionRead.model_validate(txn)


@router.patch("/{txn_id}", response_model=TransactionRead)
async def update_transaction(
    txn_id: uuid.UUID,
    data: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TransactionRead:
    txn = await transaction_service.update_transaction(session, current_user.id, txn_id, data)
    if txn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return TransactionRead.model_validate(txn)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_transaction(
    txn_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    deleted = await transaction_service.delete_transaction(session, current_user.id, txn_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── CSV upload ─────────────────────────────────────────────────────────────────

@router.post(
    "/import/csv",
    response_model=CsvUploadResult,
    dependencies=[Depends(rate_limit(10, 60, "csv_import"))],
)
async def upload_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CsvUploadResult:
    if file.content_type not in ("text/csv", "text/plain", "application/octet-stream"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only CSV files accepted")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5 MB limit
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 5 MB")
    return await transaction_service.import_csv(session, current_user.id, content)


# ── Aggregations ───────────────────────────────────────────────────────────────

@router.get("/summary/spending", response_model=SpendingSummary)
async def spending_summary(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SpendingSummary:
    return await transaction_service.spending_summary(
        session, current_user.id, date_from=date_from, date_to=date_to
    )


@router.get("/summary/budgets", response_model=list[BudgetStatus])
async def budget_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[BudgetStatus]:
    return await transaction_service.budget_status(session, current_user.id)


@router.get("/summary/recurring")
async def recurring_transactions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await transaction_service.detect_recurring(session, current_user.id)


# ── Fraud / anomaly detection (graph DSA) ────────────────────────────────────

@router.get("/summary/fraud")
async def fraud_signals(
    window_hours: int = Query(default=24, ge=1, le=720),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Detect anomalous transactions using a transaction adjacency-list graph.

    Returns:
    - graph_summary        : node/edge count of the merchant graph
    - high_freq_merchants  : merchants appearing ≥ 5 times (potential fraud rings)
    - duplicate_signals    : same-amount same-merchant pairs within *window_hours*
    - round_amount_signals : suspiciously round amounts (₹1000/500/100 multiples)
    """
    rows = await transaction_service.list_all_for_fraud(session, current_user.id)
    graph = TransactionGraph.from_transactions(rows)
    return {
        "graph_summary": graph.graph_summary(),
        "high_freq_merchants": graph.high_frequency_merchants(threshold=5),
        "duplicate_signals": duplicate_transactions(rows, window_hours=window_hours),
        "round_amount_signals": round_number_anomalies(rows),
    }
