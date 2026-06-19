"""Order book implemented with two heaps: max-heap for bids, min-heap for asks.

Insertion and deletion: O(log n).  Best bid/ask peek: O(1).
Used by the paper-trading matching engine in Phase 2.2.
"""

from __future__ import annotations

import heapq
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


@dataclass(order=True)
class _Order:
    # Heap key: for bids we negate price so the best (highest) bid comes first.
    _key: tuple  # (neg_price_or_price, sequence, order_id)
    order_id: str = field(compare=False)
    symbol: str = field(compare=False)
    side: Literal["buy", "sell"] = field(compare=False)
    price: Decimal = field(compare=False)
    quantity: Decimal = field(compare=False)
    filled: Decimal = field(compare=False, default=Decimal("0"))
    cancelled: bool = field(compare=False, default=False)

    @property
    def remaining(self) -> Decimal:
        return self.quantity - self.filled


@dataclass
class Fill:
    buy_order_id: str
    sell_order_id: str
    symbol: str
    quantity: Decimal
    price: Decimal


class OrderBook:
    """Price-time priority order book for a single symbol."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._bids: list[_Order] = []  # max-heap (negated price)
        self._asks: list[_Order] = []  # min-heap
        self._seq = 0
        self._orders: dict[str, _Order] = {}

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def add_limit(
        self,
        side: Literal["buy", "sell"],
        price: Decimal,
        quantity: Decimal,
        order_id: str | None = None,
    ) -> tuple[str, list[Fill]]:
        """Add a limit order and immediately match against opposite side."""
        oid = order_id or str(uuid.uuid4())
        seq = self._next_seq()
        if side == "buy":
            key = (-float(price), seq, oid)
            heap = self._bids
        else:
            key = (float(price), seq, oid)
            heap = self._asks
        order = _Order(
            _key=key,
            order_id=oid,
            symbol=self.symbol,
            side=side,
            price=price,
            quantity=quantity,
        )
        heapq.heappush(heap, order)
        self._orders[oid] = order
        fills = self._match()
        return oid, fills

    def add_market(
        self,
        side: Literal["buy", "sell"],
        quantity: Decimal,
        order_id: str | None = None,
    ) -> tuple[str, list[Fill]]:
        """Market order: fill at best available price, or cancel remainder."""
        oid = order_id or str(uuid.uuid4())
        opp_heap = self._asks if side == "buy" else self._bids
        fills: list[Fill] = []
        remaining = quantity
        while opp_heap and remaining > 0:
            best = opp_heap[0]
            if best.cancelled:
                heapq.heappop(opp_heap)
                continue
            fill_qty = min(remaining, best.remaining)
            fill = Fill(
                buy_order_id=oid if side == "buy" else best.order_id,
                sell_order_id=best.order_id if side == "buy" else oid,
                symbol=self.symbol,
                quantity=fill_qty,
                price=best.price,
            )
            fills.append(fill)
            best.filled += fill_qty
            remaining -= fill_qty
            if best.remaining == 0:
                heapq.heappop(opp_heap)
        return oid, fills

    def cancel(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None:
            return False
        order.cancelled = True
        return True

    def _match(self) -> list[Fill]:
        fills: list[Fill] = []
        while self._bids and self._asks:
            best_bid = self._bids[0]
            best_ask = self._asks[0]
            # Lazy-delete cancelled/fully-filled orders.
            if best_bid.cancelled or best_bid.remaining == 0:
                heapq.heappop(self._bids)
                continue
            if best_ask.cancelled or best_ask.remaining == 0:
                heapq.heappop(self._asks)
                continue
            if best_bid.price < best_ask.price:
                break
            fill_qty = min(best_bid.remaining, best_ask.remaining)
            fill_price = best_ask.price  # price of the resting order
            fills.append(
                Fill(
                    buy_order_id=best_bid.order_id,
                    sell_order_id=best_ask.order_id,
                    symbol=self.symbol,
                    quantity=fill_qty,
                    price=fill_price,
                )
            )
            best_bid.filled += fill_qty
            best_ask.filled += fill_qty
            if best_bid.remaining == 0:
                heapq.heappop(self._bids)
            if best_ask.remaining == 0:
                heapq.heappop(self._asks)
        return fills

    @property
    def best_bid(self) -> Decimal | None:
        for o in self._bids:
            if not o.cancelled and o.remaining > 0:
                return o.price
        return None

    @property
    def best_ask(self) -> Decimal | None:
        for o in self._asks:
            if not o.cancelled and o.remaining > 0:
                return o.price
        return None

    def depth(self, levels: int = 5) -> dict:
        bids: dict[Decimal, Decimal] = {}
        asks: dict[Decimal, Decimal] = {}
        for o in self._bids:
            if not o.cancelled and o.remaining > 0:
                bids[o.price] = bids.get(o.price, Decimal(0)) + o.remaining
        for o in self._asks:
            if not o.cancelled and o.remaining > 0:
                asks[o.price] = asks.get(o.price, Decimal(0)) + o.remaining
        return {
            "bids": sorted(bids.items(), reverse=True)[:levels],
            "asks": sorted(asks.items())[:levels],
        }
