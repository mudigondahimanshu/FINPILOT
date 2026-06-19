"""Market data service: yfinance fetch, OHLC storage, live quotes, fundamentals."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lru_cache import fundamentals_cache, ohlc_cache, quote_cache
from app.core.moving_average import exponential_moving_average, simple_moving_average
from app.core.trie import ticker_trie
from app.models.ohlc import OHLC

log = logging.getLogger(__name__)

# yfinance is a heavy import; do it lazily so the app starts even if the
# package isn't installed (e.g. during unit tests that don't need it).
_yf: Any = None


def _get_yf() -> Any:
    global _yf  # noqa: PLW0603
    if _yf is None:
        import yfinance as yf  # noqa: PLC0415

        _yf = yf
    return _yf


# ── Quote ─────────────────────────────────────────────────────────────────────

async def get_quote(symbol: str) -> dict:
    """Return a live-ish quote for *symbol*, cached 60 s in-process."""
    key = symbol.upper()
    cached = quote_cache.get(key)
    if cached is not None:
        return cached

    result = await asyncio.to_thread(_fetch_quote_sync, key)
    if result:
        quote_cache.put(key, result)
    return result


def _fetch_quote_sync(symbol: str) -> dict:
    yf = _get_yf()
    ticker = yf.Ticker(symbol)
    info = ticker.fast_info
    try:
        price = float(getattr(info, "last_price", None) or 0)
        prev_close = float(getattr(info, "previous_close", None) or price)
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 4),
            "volume": int(getattr(info, "three_month_average_volume", 0) or 0),
            "market_cap": getattr(info, "market_cap", None),
            "currency": getattr(info, "currency", "INR"),
            "exchange": getattr(info, "exchange", ""),
            "fetched_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        log.warning("quote fetch failed for %s: %s", symbol, exc)
        return {"symbol": symbol, "error": str(exc)}


# ── OHLC ─────────────────────────────────────────────────────────────────────

async def get_ohlc(
    symbol: str,
    interval: str = "1d",
    period: str = "1y",
    session: AsyncSession | None = None,
) -> list[dict]:
    """Return OHLC candles, pulling from DB first then yfinance if stale."""
    key = f"{symbol}:{interval}:{period}"
    cached = ohlc_cache.get(key)
    if cached is not None:
        return cached

    # Try DB first (last 365 days of daily candles).
    if session is not None:
        rows = await _load_ohlc_from_db(session, symbol, interval)
        if rows:
            ohlc_cache.put(key, rows)
            return rows

    # Fallback: fetch from yfinance and (optionally) persist.
    rows = await asyncio.to_thread(_fetch_ohlc_sync, symbol, interval, period)
    if session is not None and rows:
        await _upsert_ohlc(session, symbol, interval, rows)
    ohlc_cache.put(key, rows)
    return rows


async def _load_ohlc_from_db(session: AsyncSession, symbol: str, interval: str) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(days=365)
    stmt = (
        select(OHLC)
        .where(OHLC.symbol == symbol, OHLC.interval == interval, OHLC.timestamp >= cutoff)
        .order_by(OHLC.timestamp)
    )
    result = await session.execute(stmt)
    return [_ohlc_to_dict(o) for o in result.scalars()]


def _fetch_ohlc_sync(symbol: str, interval: str, period: str) -> list[dict]:
    yf = _get_yf()
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    rows = []
    for ts, row in df.iterrows():
        rows.append({
            "timestamp": ts.isoformat(),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row.get("Volume", 0)),
        })
    return rows


async def _upsert_ohlc(session: AsyncSession, symbol: str, interval: str, rows: list[dict]) -> None:
    if not rows:
        return
    import uuid  # noqa: PLC0415
    values = [
        {
            "id": uuid.uuid4(),
            "timestamp": datetime.fromisoformat(r["timestamp"]),
            "symbol": symbol,
            "interval": interval,
            "open": Decimal(str(r["open"])),
            "high": Decimal(str(r["high"])),
            "low": Decimal(str(r["low"])),
            "close": Decimal(str(r["close"])),
            "volume": r["volume"],
        }
        for r in rows
    ]
    stmt = pg_insert(OHLC).values(values).on_conflict_do_nothing(
        index_elements=["symbol", "interval", "timestamp"]
    )
    await session.execute(stmt)
    await session.commit()


def _ohlc_to_dict(o: OHLC) -> dict:
    return {
        "timestamp": o.timestamp.isoformat(),
        "open": float(o.open),
        "high": float(o.high),
        "low": float(o.low),
        "close": float(o.close),
        "volume": o.volume,
    }


# ── Moving averages overlay ────────────────────────────────────────────────────

def add_moving_averages(ohlc_rows: list[dict]) -> dict:
    """Attach SMA-20, SMA-50, EMA-20 arrays to a candle series."""
    closes = [Decimal(str(r["close"])) for r in ohlc_rows]
    return {
        "candles": ohlc_rows,
        "sma20": [float(v) if v is not None else None for v in simple_moving_average(closes, 20)],
        "sma50": [float(v) if v is not None else None for v in simple_moving_average(closes, 50)],
        "ema20": [float(v) if v is not None else None for v in exponential_moving_average(closes, 20)], # noqa: E501
    }


# ── Fundamentals ──────────────────────────────────────────────────────────────

async def get_fundamentals(symbol: str) -> dict:
    key = symbol.upper()
    cached = fundamentals_cache.get(key)
    if cached is not None:
        return cached

    result = await asyncio.to_thread(_fetch_fundamentals_sync, key)
    if result:
        fundamentals_cache.put(key, result)
    return result


def _fetch_fundamentals_sync(symbol: str) -> dict:
    yf = _get_yf()
    info = yf.Ticker(symbol).info
    fields = [
        "longName", "sector", "industry", "country", "website",
        "marketCap", "trailingPE", "forwardPE", "priceToBook",
        "dividendYield", "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
        "averageVolume", "longBusinessSummary",
    ]
    return {k: info.get(k) for k in fields}


# ── Autocomplete ──────────────────────────────────────────────────────────────

def search_tickers(query: str, limit: int = 10) -> list[dict]:
    """Prefix search via the in-memory Trie — O(k) where k = len(query)."""
    raw = ticker_trie.search(query, limit=limit * 2)
    # Filter out the name-index keys (they have "__" injected).
    return [r for r in raw if "__" not in r["symbol"]][:limit]
