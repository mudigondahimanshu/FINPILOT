"""Moving-average calculations using a monotonic deque (sliding window).

SMA and EMA in O(n) time, O(k) space for window size k.
Used for price chart overlays in the market-data endpoints.
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal


def simple_moving_average(prices: list[Decimal], window: int) -> list[Decimal | None]:
    """O(n) SMA using a sliding sum — no full re-sum per step."""
    if window <= 0:
        raise ValueError("window must be positive")
    result: list[Decimal | None] = [None] * (window - 1)
    dq: deque[Decimal] = deque()
    running = Decimal(0)
    for price in prices:
        dq.append(price)
        running += price
        if len(dq) > window:
            running -= dq.popleft()
        if len(dq) == window:
            result.append(running / window)
    return result


def exponential_moving_average(prices: list[Decimal], span: int) -> list[Decimal | None]:
    """EMA with smoothing factor α = 2/(span+1)."""
    if span <= 0:
        raise ValueError("span must be positive")
    if not prices:
        return []
    alpha = Decimal(2) / Decimal(span + 1)
    result: list[Decimal | None] = []
    ema: Decimal | None = None
    for price in prices:
        if ema is None:
            ema = price
        else:
            ema = alpha * price + (1 - alpha) * ema
        result.append(ema)
    return result


def max_sliding_window(prices: list[Decimal], window: int) -> list[Decimal | None]:
    """O(n) max sliding window via monotonic decreasing deque."""
    result: list[Decimal | None] = [None] * (window - 1)
    dq: deque[int] = deque()  # stores indices
    for i, price in enumerate(prices):
        while dq and prices[dq[-1]] <= price:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - window:
            dq.popleft()
        if i >= window - 1:
            result.append(prices[dq[0]])
    return result


def min_sliding_window(prices: list[Decimal], window: int) -> list[Decimal | None]:
    """O(n) min sliding window via monotonic increasing deque."""
    result: list[Decimal | None] = [None] * (window - 1)
    dq: deque[int] = deque()
    for i, price in enumerate(prices):
        while dq and prices[dq[-1]] >= price:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - window:
            dq.popleft()
        if i >= window - 1:
            result.append(prices[dq[0]])
    return result
