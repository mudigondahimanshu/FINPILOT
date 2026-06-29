"""Paper-trading portfolio service.

Responsibilities:
- Ensure every user has exactly one Portfolio row (auto-created on first use).
- Execute buy/sell orders via the OrderBook matching engine.
- Calculate holdings from trade history (FIFO cost basis).
- Compute unrealized + realized P&L using live quotes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import set_rls_user
from app.core.order_book import OrderBook
from app.models.portfolio import Portfolio, Trade
from app.schemas.portfolio import Holding, PortfolioSummary, TradeCreate, TradeRead
from app.services import market_service

# In-process order book registry: symbol → OrderBook.
# Resets on server restart (acceptable for paper trading).
_order_books: dict[str, OrderBook] = {}


def _get_order_book(symbol: str) -> OrderBook:
    if symbol not in _order_books:
        _order_books[symbol] = OrderBook(symbol)
    return _order_books[symbol]


# ── Portfolio bootstrap ───────────────────────────────────────────────────────

async def get_or_create_portfolio(session: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    """Return the user's portfolio, creating it (₹1,00,000 cash) if absent."""
    await set_rls_user(session, user_id)
    result = await session.execute(
        select(Portfolio).where(Portfolio.user_id == user_id).limit(1)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        portfolio = Portfolio(
            id=uuid.uuid4(),
            user_id=user_id,
            name="My Portfolio",
            cash_balance=Decimal("100000"),
            currency="INR",
        )
        session.add(portfolio)
        await session.commit()
        await session.refresh(portfolio)
    return portfolio


# ── Order execution ───────────────────────────────────────────────────────────

async def execute_order(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: TradeCreate,
) -> TradeRead:
    """Place a paper trade, match it via the OrderBook, update cash balance."""
    await set_rls_user(session, user_id)
    portfolio = await get_or_create_portfolio(session, user_id)
    symbol = data.symbol.upper()

    # Resolve execution price.
    if data.price is not None:
        exec_price = data.price
    else:
        quote = await market_service.get_quote(symbol)
        exec_price = Decimal(str(quote.get("price", 0)))
        if exec_price <= 0:
            raise ValueError(f"Could not fetch live price for {symbol}")

    # Match via order book (market order for simplicity in paper mode).
    ob = _get_order_book(symbol)
    _oid, fills = ob.add_market(data.side, data.quantity)

    # If the book is empty (no real counterparties), simulate a fill at exec_price.
    if not fills:
        from app.core.order_book import Fill  # noqa: PLC0415
        fills = [Fill(
            buy_order_id=_oid if data.side == "buy" else "sim",
            sell_order_id="sim" if data.side == "buy" else _oid,
            symbol=symbol,
            quantity=data.quantity,
            price=exec_price,
        )]

    filled_qty = sum((f.quantity for f in fills), Decimal("0"))
    avg_price = sum((f.price * f.quantity for f in fills), Decimal("0")) / filled_qty
    cash_delta = (-avg_price * filled_qty) if data.side == "buy" else (avg_price * filled_qty)

    # Guard: insufficient cash for buy.
    if data.side == "buy" and portfolio.cash_balance + cash_delta < 0:
        raise ValueError("Insufficient cash balance")

    portfolio.cash_balance += cash_delta

    trade = Trade(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        user_id=user_id,
        symbol=symbol,
        exchange="NSE",
        side=data.side,
        quantity=filled_qty,
        price=avg_price,
        cash_delta=cash_delta,
        status="filled",
        notes=data.notes,
        executed_at=datetime.now(UTC),
    )
    session.add(trade)
    await session.commit()
    await session.refresh(trade)
    return TradeRead.model_validate(trade)  # type: ignore[attr-defined]


# ── Holdings & P&L ────────────────────────────────────────────────────────────

async def get_portfolio_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> PortfolioSummary:
    await set_rls_user(session, user_id)
    portfolio = await get_or_create_portfolio(session, user_id)

    # Load all trades.
    result = await session.execute(
        select(Trade)
        .where(Trade.user_id == user_id)
        .order_by(Trade.executed_at)
    )
    trades = result.scalars().all()

    # FIFO cost-basis aggregation.
    holdings: dict[str, dict] = {}
    realized_pnl = Decimal("0")

    for t in trades:
        sym = t.symbol
        if sym not in holdings:
            holdings[sym] = {"qty": Decimal("0"), "cost": Decimal("0"), "fifo": []}

        if t.side == "buy":
            holdings[sym]["qty"] += t.quantity
            holdings[sym]["cost"] += t.price * t.quantity
            holdings[sym]["fifo"].append([t.quantity, t.price])
        else:
            # FIFO sell
            sell_qty = t.quantity
            sell_proceeds = t.price * t.quantity
            cost_of_sold = Decimal("0")
            fifo = holdings[sym]["fifo"]
            while sell_qty > 0 and fifo:
                lot_qty, lot_price = fifo[0]
                take = min(sell_qty, lot_qty)
                cost_of_sold += take * lot_price
                sell_qty -= take
                fifo[0][0] -= take
                if fifo[0][0] == 0:
                    fifo.pop(0)
            holdings[sym]["qty"] -= t.quantity
            holdings[sym]["cost"] -= cost_of_sold
            realized_pnl += sell_proceeds - cost_of_sold

    # Fetch current quotes for open positions.
    open_syms = [s for s, h in holdings.items() if h["qty"] > 0]
    quotes: dict[str, Decimal] = {}
    if open_syms:
        import asyncio  # noqa: PLC0415
        quote_results = await asyncio.gather(
            *[market_service.get_quote(s) for s in open_syms], return_exceptions=True
        )
        for sym, qr in zip(open_syms, quote_results, strict=False):
            if isinstance(qr, dict) and "price" in qr:
                quotes[sym] = Decimal(str(qr["price"]))

    holding_list: list[Holding] = []
    total_invested = Decimal("0")
    total_market_value = Decimal("0")
    total_unrealized = Decimal("0")

    for sym, h in holdings.items():
        qty = h["qty"]
        if qty <= 0:
            continue
        avg_cost = h["cost"] / qty if qty else Decimal("0")
        current_price = quotes.get(sym)
        market_value = current_price * qty if current_price else None
        unrealized = (market_value - h["cost"]) if market_value is not None else None
        unrealized_pct = (
            (unrealized / h["cost"] * 100) if unrealized is not None and h["cost"] > 0 else None
        )
        total_invested += h["cost"]
        if market_value:
            total_market_value += market_value
        if unrealized is not None:
            total_unrealized += unrealized

        holding_list.append(
            Holding(
                symbol=sym,
                quantity=qty,
                avg_cost=avg_cost,
                current_price=current_price,
                unrealized_pnl=unrealized,
                unrealized_pnl_pct=unrealized_pct,
                market_value=market_value,
            )
        )

    return PortfolioSummary(
        portfolio=portfolio,
        holdings=holding_list,
        total_invested=total_invested,
        market_value=total_market_value if open_syms else None,
        unrealized_pnl=total_unrealized if open_syms else None,
        realized_pnl=realized_pnl,
        total_pnl=(total_unrealized + realized_pnl) if open_syms else realized_pnl,
    )


# ── Trade history ─────────────────────────────────────────────────────────────

async def list_trades(
    session: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[TradeRead]:
    await set_rls_user(session, user_id)
    result = await session.execute(
        select(Trade)
        .where(Trade.user_id == user_id)
        .order_by(Trade.executed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [TradeRead.model_validate(t) for t in result.scalars()]  # type: ignore[attr-defined]
