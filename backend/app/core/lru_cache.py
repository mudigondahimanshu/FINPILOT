"""Thread-safe LRU cache implemented with an OrderedDict.

O(1) get and put using Python's ordered dict move_to_end.
Used to cache market-data API responses (quotes, OHLC) in-process.
Redis handles cross-process caching; this handles hot in-process paths.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """Capacity-bounded LRU cache with optional TTL (seconds)."""

    def __init__(self, capacity: int, ttl: float | None = None) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._cap = capacity
        self._ttl = ttl
        self._store: OrderedDict[K, tuple[V, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            if key not in self._store:
                return None
            value, ts = self._store[key]
            if self._ttl is not None and time.monotonic() - ts > self._ttl:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def put(self, key: K, value: V) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, time.monotonic())
            if len(self._store) > self._cap:
                self._store.popitem(last=False)  # evict LRU

    def delete(self, key: K) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __contains__(self, key: object) -> bool:
        return self.get(key) is not None  # type: ignore[arg-type]


# Module-level caches used by market_service.
quote_cache: LRUCache[str, dict] = LRUCache(capacity=500, ttl=60.0)
ohlc_cache: LRUCache[str, list] = LRUCache(capacity=100, ttl=300.0)
fundamentals_cache: LRUCache[str, dict] = LRUCache(capacity=200, ttl=3600.0)
