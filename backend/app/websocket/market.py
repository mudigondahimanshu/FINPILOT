"""WebSocket endpoint: live price feed via Redis pub/sub fan-out.

Architecture:
  ┌────────────┐   publish    ┌───────┐   subscribe   ┌──────────────┐
  │ price pump │ ──────────▶ │ Redis │ ─────────────▶ │ WS handler   │
  │ (yfinance) │             │ ch:   │               │ (per client) │
  └────────────┘             │ mkt:  │               └──────────────┘
                             │ {sym} │
                             └───────┘

The pump runs as a background asyncio task started on app startup.
Each connected WebSocket client subscribes to requested symbols;
the handler relays Redis messages to the client.
If Finnhub credentials are set, the pump is backed by Finnhub's WS feed;
otherwise it polls yfinance every 5 s (sufficient for paper trading).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.services import market_service

log = logging.getLogger(__name__)

_POLL_INTERVAL = 5.0  # seconds between yfinance polls (fallback mode)
_REDIS_CHANNEL_PREFIX = "mkt:"

# Active subscriptions: symbol → set of queues (one per connected client).
_subscriptions: dict[str, set[asyncio.Queue]] = {}
_pump_task: asyncio.Task | None = None


# ── Connection manager ────────────────────────────────────────────────────────

class _ConnectionManager:
    def __init__(self) -> None:
        self._active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._active.discard(ws)

    async def send(self, ws: WebSocket, data: dict) -> None:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            self.disconnect(ws)


manager = _ConnectionManager()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

async def live_price_ws(websocket: WebSocket) -> None:
    """
    Client sends: {"action": "subscribe", "symbols": ["RELIANCE.NS", "TCS.NS"]}
    Server pushes: {"symbol": "RELIANCE.NS", "price": 2850.5, "ts": 1718000000}
    """
    await manager.connect(websocket)
    queues: list[asyncio.Queue] = []
    symbols: list[str] = []

    try:
        # Wait for the subscribe message.
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        symbols = [s.upper() for s in msg.get("symbols", [])][:10]  # cap 10 symbols

        # Register a queue per symbol.
        for sym in symbols:
            q: asyncio.Queue = asyncio.Queue(maxsize=50)
            queues.append(q)
            _subscriptions.setdefault(sym, set()).add(q)

        # Ensure the pump is running.
        _ensure_pump(symbols)

        # Relay loop: pull from queue → send to client.
        while True:
            # Wait for any queue to have data (fan-in via gather).
            done, _ = await asyncio.wait(
                [asyncio.ensure_future(q.get()) for q in queues],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=30.0,
            )
            for fut in done:
                try:
                    payload = fut.result()
                    await manager.send(websocket, payload)
                except Exception:
                    log.debug("WS relay error")

    except (TimeoutError, WebSocketDisconnect):
        pass
    finally:
        for sym, q in zip(symbols, queues, strict=False):
            _subscriptions.get(sym, set()).discard(q)
        manager.disconnect(websocket)


# ── Price pump ────────────────────────────────────────────────────────────────

def _ensure_pump(symbols: list[str]) -> None:
    global _pump_task  # noqa: PLW0603
    if _pump_task is None or _pump_task.done():
        _pump_task = asyncio.create_task(_pump_loop())


async def _pump_loop() -> None:
    """Poll yfinance for every subscribed symbol every _POLL_INTERVAL seconds."""
    log.info("Market price pump started (poll interval: %ss)", _POLL_INTERVAL)
    while True:
        symbols = list(_subscriptions.keys())
        if not symbols:
            await asyncio.sleep(_POLL_INTERVAL)
            continue

        tasks = [market_service.get_quote(sym) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for sym, result in zip(symbols, results, strict=False):
            if isinstance(result, Exception) or not isinstance(result, dict):
                continue
            payload = {
                "symbol": sym,
                "price": result.get("price"),
                "change": result.get("change"),
                "change_pct": result.get("change_pct"),
                "ts": int(time.time()),
            }
            # Fan-out to all subscribers for this symbol.
            for q in list(_subscriptions.get(sym, set())):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass  # slow consumer — drop the tick

        await asyncio.sleep(_POLL_INTERVAL)


# ── Redis pub/sub integration (optional, used when Redis is reachable) ─────────

async def publish_price(symbol: str, data: dict) -> None:
    """Called by Finnhub WS adapter (if configured) to fan-out via Redis."""
    try:
        from app.core.redis_client import get_redis  # noqa: PLC0415

        r = await get_redis()
        await r.publish(f"{_REDIS_CHANNEL_PREFIX}{symbol}", json.dumps(data))
    except Exception as exc:
        log.debug("Redis publish failed: %s", exc)


async def start_redis_subscriber(symbol: str, queues: set[asyncio.Queue]) -> None:
    """Subscribe to a Redis channel and relay messages to local queues."""
    try:
        from app.core.redis_client import get_redis  # noqa: PLC0415

        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(f"{_REDIS_CHANNEL_PREFIX}{symbol}")
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            payload = json.loads(message["data"])
            for q in list(queues):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass
    except Exception as exc:
        log.debug("Redis subscriber error for %s: %s", symbol, exc)


# ── Finnhub WebSocket adapter (dormant unless key is set) ─────────────────────

async def start_finnhub_feed(symbols: list[str]) -> None:
    """Connect to Finnhub's WS feed and publish quotes to Redis."""
    if not settings.finnhub_configured:
        return
    try:
        import websockets  # noqa: PLC0415

        uri = f"wss://ws.finnhub.io?token={settings.finnhub_api_key}"
        async with websockets.connect(uri) as ws:
            for sym in symbols:
                await ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("type") != "trade":
                    continue
                for trade in msg.get("data", []):
                    await publish_price(
                        trade["s"],
                        {
                            "symbol": trade["s"],
                            "price": trade["p"],
                            "volume": trade["v"],
                            "ts": int(trade["t"] / 1000),
                        },
                    )
    except Exception as exc:
        log.warning("Finnhub feed error: %s", exc)
