"""Market data REST routes + WebSocket endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit, ws_authenticate
from app.core.config import settings
from app.core.database import get_db, set_rls_user
from app.models.user import User
from app.models.watchlist import Watchlist
from app.services import market_service
from app.websocket.market import live_price_ws

router = APIRouter(prefix="/market", tags=["market"])


# ── Ticker search ─────────────────────────────────────────────────────────────

@router.get("/search")
async def search_tickers(
    q: str = Query(min_length=1, max_length=30),
    limit: int = Query(default=10, ge=1, le=30),
    _: User = Depends(get_current_user),
) -> list[dict]:
    """Prefix autocomplete via in-memory Trie — O(k) complexity."""
    return market_service.search_tickers(q, limit=limit)


# ── Quote ─────────────────────────────────────────────────────────────────────

@router.get("/quote/{symbol}")
async def get_quote(
    symbol: str,
    _: User = Depends(get_current_user),
    __: None = Depends(rate_limit(capacity=30, window_seconds=60, scope="quote")),
) -> dict:
    result = await market_service.get_quote(symbol.upper())
    if "error" in result and "price" not in result:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Quote unavailable: {result['error']}")
    return result


# ── OHLC candles ──────────────────────────────────────────────────────────────

@router.get("/ohlc/{symbol}")
async def get_ohlc(
    symbol: str,
    interval: str = Query(default="1d", pattern=r"^(1m|5m|15m|1h|1d|1wk|1mo)$"),
    period: str = Query(default="1y", pattern=r"^(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)$"),
    with_ma: bool = Query(default=True),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    candles = await market_service.get_ohlc(symbol.upper(), interval, period, session)
    if not candles:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No OHLC data found for symbol")
    if with_ma:
        return market_service.add_moving_averages(candles)
    return {"candles": candles}


# ── Fundamentals ──────────────────────────────────────────────────────────────

@router.get("/fundamentals/{symbol}")
async def get_fundamentals(
    symbol: str,
    _: User = Depends(get_current_user),
) -> dict:
    result = await market_service.get_fundamentals(symbol.upper())
    return result


# ── Watchlist ─────────────────────────────────────────────────────────────────

@router.get("/watchlist")
async def list_watchlist(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    await set_rls_user(session, current_user.id)
    result = await session.execute(
        select(Watchlist).where(Watchlist.user_id == current_user.id).order_by(Watchlist.added_at)
    )
    return [
        {"id": str(w.id), "symbol": w.symbol, "exchange": w.exchange, "added_at": w.added_at.isoformat()} # noqa: E501
        for w in result.scalars()
    ]


@router.post("/watchlist/{symbol}", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    symbol: str,
    exchange: str = Query(default="NSE"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    await set_rls_user(session, current_user.id)
    existing = await session.execute(
        select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.symbol == symbol.upper()) # noqa: E501
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Symbol already in watchlist")
    item = Watchlist(
        id=uuid.uuid4(),
        user_id=current_user.id,
        symbol=symbol.upper(),
        exchange=exchange.upper(),
        added_at=datetime.now(UTC),
    )
    session.add(item)
    await session.commit()
    return {"id": str(item.id), "symbol": item.symbol, "exchange": item.exchange}


@router.delete("/watchlist/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await set_rls_user(session, current_user.id)
    await session.execute(
        delete(Watchlist).where(
            Watchlist.user_id == current_user.id, Watchlist.symbol == symbol.upper()
        )
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/prices")
async def prices_ws(websocket: WebSocket, token: str = Query(...)) -> None:
    """Live price feed. Requires ?token=<access_token> query param.

    Origin is validated against the CORS allowlist to prevent cross-origin
    WebSocket hijacking from malicious browser pages.
    """
    # Origin check — reject cross-origin connections not in the allowlist.
    origin = websocket.headers.get("origin", "")
    allowed = settings.cors_origin_list
    if origin and origin not in allowed:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = await ws_authenticate(websocket, token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await live_price_ws(websocket)
