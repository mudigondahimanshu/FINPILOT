"""Paper-trading portfolio REST routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit
from app.core.database import get_db, set_rls_user
from app.core.order_book import OrderBook
from app.models.portfolio import Trade
from app.models.user import User
from app.schemas.portfolio import OrderBookDepth, PortfolioSummary, TradeCreate, TradeRead
from app.services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_order_books: dict[str, OrderBook] = {}


def _ob(symbol: str) -> OrderBook:
    if symbol not in _order_books:
        _order_books[symbol] = OrderBook(symbol)
    return _order_books[symbol]


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PortfolioSummary:
    return await portfolio_service.get_portfolio_summary(session, current_user.id)


# ── Execute order ─────────────────────────────────────────────────────────────

@router.post(
    "/order",
    response_model=TradeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(capacity=20, window_seconds=60, scope="order"))],
)
async def place_order(
    data: TradeCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TradeRead:
    try:
        return await portfolio_service.execute_order(session, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


# ── Trade history ─────────────────────────────────────────────────────────────

@router.get("/trades", response_model=list[TradeRead])
async def list_trades(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TradeRead]:
    return await portfolio_service.list_trades(session, current_user.id, limit, offset)


@router.delete("/trades/{trade_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response) # noqa: E501
async def cancel_trade(
    trade_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await set_rls_user(session, current_user.id)
    result = await session.execute(
        select(Trade).where(Trade.id == trade_id, Trade.user_id == current_user.id)
    )
    trade = result.scalar_one_or_none()
    if trade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trade not found")
    if trade.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only pending trades can be cancelled")
    trade.status = "cancelled"
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Order book depth ──────────────────────────────────────────────────────────

@router.get("/orderbook/{symbol}", response_model=OrderBookDepth)
async def order_book_depth(
    symbol: str,
    levels: int = Query(default=5, ge=1, le=20),
    _: User = Depends(get_current_user),
) -> OrderBookDepth:
    ob = _ob(symbol.upper())
    depth = ob.depth(levels)
    return OrderBookDepth(
        symbol=symbol.upper(),
        bids=[(float(p), float(q)) for p, q in depth["bids"]],
        asks=[(float(p), float(q)) for p, q in depth["asks"]],
        best_bid=float(ob.best_bid) if ob.best_bid else None,
        best_ask=float(ob.best_ask) if ob.best_ask else None,
    )
