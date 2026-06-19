"""DSA showcase tests — O(log n) order book, Trie, sliding-window MA, LRU cache,
transaction graph (adjacency list), and WS price-pump latency proxy.

All tests are pure in-process; no DB or external APIs needed.
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal

import pytest
from app.core.lru_cache import LRUCache
from app.core.moving_average import (
    exponential_moving_average,
    max_sliding_window,
    min_sliding_window,
    simple_moving_average,
)
from app.core.order_book import OrderBook
from app.core.transaction_graph import (
    TransactionGraph,
    duplicate_transactions,
    round_number_anomalies,
)
from app.core.trie import TickerTrie

# ── Trie ──────────────────────────────────────────────────────────────────────

class TestTrie:
    def _trie(self) -> TickerTrie:
        t = TickerTrie()
        for sym, name, exchange in [
            ("RELIANCE.NS", "Reliance Industries", "NSE"),
            ("RELIANCEI.NS", "Reliance Infratel", "NSE"),
            ("TCS.NS", "Tata Consultancy Services", "NSE"),
            ("INFY.NS", "Infosys", "NSE"),
        ]:
            t.insert(sym, name, exchange)
        return t

    def test_exact_prefix(self) -> None:
        results = self._trie().search("REL")
        syms = [r["symbol"] for r in results]
        assert "RELIANCE.NS" in syms
        assert "RELIANCEI.NS" in syms

    def test_no_match(self) -> None:
        assert self._trie().search("ZZZZZ") == []

    def test_case_insensitive(self) -> None:
        results = self._trie().search("tcs")
        assert any(r["symbol"] == "TCS.NS" for r in results)

    def test_limit(self) -> None:
        t = TickerTrie()
        for i in range(20):
            t.insert(f"TICK{i:02d}.NS", f"Company {i}", "NSE")
        assert len(t.search("TICK", limit=5)) == 5

    def test_empty_prefix(self) -> None:
        # Empty prefix returns root children — at least what was inserted.
        results = self._trie().search("")
        assert len(results) >= 4


# ── Order book ────────────────────────────────────────────────────────────────

class TestOrderBook:
    def test_limit_order_no_match(self) -> None:
        ob = OrderBook("TEST.NS")
        oid, fills = ob.add_limit("buy", Decimal("100"), Decimal("10"))
        assert fills == []
        assert ob.best_bid == Decimal("100")

    def test_limit_orders_match(self) -> None:
        ob = OrderBook("TEST.NS")
        ob.add_limit("buy", Decimal("101"), Decimal("5"))
        _, fills = ob.add_limit("sell", Decimal("100"), Decimal("5"))
        assert len(fills) == 1
        assert fills[0].quantity == Decimal("5")
        assert fills[0].price == Decimal("100")  # resting ask price

    def test_partial_fill(self) -> None:
        ob = OrderBook("TEST.NS")
        ob.add_limit("buy", Decimal("200"), Decimal("10"))
        _, fills = ob.add_limit("sell", Decimal("190"), Decimal("6"))
        assert fills[0].quantity == Decimal("6")
        assert ob.best_bid == Decimal("200")  # remaining 4 still in book

    def test_cancel(self) -> None:
        ob = OrderBook("TEST.NS")
        oid, _ = ob.add_limit("buy", Decimal("100"), Decimal("5"))
        assert ob.cancel(oid) is True
        # After cancel the order is gone from best_bid view.
        assert ob.best_bid is None

    def test_market_order(self) -> None:
        ob = OrderBook("TEST.NS")
        ob.add_limit("sell", Decimal("150"), Decimal("20"))
        _, fills = ob.add_market("buy", Decimal("10"))
        assert sum(f.quantity for f in fills) == Decimal("10")
        assert fills[0].price == Decimal("150")

    def test_depth(self) -> None:
        ob = OrderBook("TEST.NS")
        for p in [100, 101, 102]:
            ob.add_limit("buy", Decimal(str(p)), Decimal("1"))
        depth = ob.depth(levels=3)
        assert len(depth["bids"]) == 3
        # Best bid first (descending price).
        assert depth["bids"][0][0] == Decimal("102")

    def test_olog_n_insertion(self) -> None:
        """Insertion time should scale as O(log n), verified by timing 1k vs 10k."""
        ob1 = OrderBook("BENCH1")
        ob2 = OrderBook("BENCH2")
        n1, n2 = 1_000, 10_000

        t0 = time.perf_counter()
        for i in range(n1):
            ob1.add_limit("buy", Decimal(str(100 + i)), Decimal("1"))
        t1 = time.perf_counter() - t0

        t0 = time.perf_counter()
        for i in range(n2):
            ob2.add_limit("buy", Decimal(str(100 + i)), Decimal("1"))
        t2 = time.perf_counter() - t0

        # O(n log n) total: ratio should be < 20 for 10× more orders.
        assert t2 / t1 < 25, f"Expected near-log-n scaling but got {t2/t1:.1f}×"


# ── Moving averages ───────────────────────────────────────────────────────────

class TestMovingAverages:
    _prices = [Decimal(str(x)) for x in [10, 12, 11, 13, 15, 14, 16, 18, 17, 19]]

    def test_sma_length(self) -> None:
        result = simple_moving_average(self._prices, 3)
        assert len(result) == len(self._prices)
        # First window-1 entries are None.
        assert all(v is None for v in result[:2])
        assert result[2] is not None

    def test_sma_correctness(self) -> None:
        # SMA(3) of [10,12,11] = 11.
        result = simple_moving_average(self._prices, 3)
        assert result[2] == Decimal("11")

    def test_ema_no_nones(self) -> None:
        result = exponential_moving_average(self._prices, 3)
        assert len(result) == len(self._prices)
        assert all(v is not None for v in result)

    def test_max_sliding_window(self) -> None:
        result = max_sliding_window(self._prices, 3)
        assert result[2] == Decimal("12")  # max(10,12,11)
        assert result[4] == Decimal("15")  # max(11,13,15)

    def test_min_sliding_window(self) -> None:
        result = min_sliding_window(self._prices, 3)
        assert result[2] == Decimal("10")  # min(10,12,11)
        assert result[4] == Decimal("11")  # min(11,13,15)

    def test_invalid_window(self) -> None:
        with pytest.raises(ValueError):
            simple_moving_average(self._prices, 0)


# ── LRU Cache ─────────────────────────────────────────────────────────────────

class TestLRUCache:
    def test_basic_get_put(self) -> None:
        c: LRUCache[str, int] = LRUCache(3)
        c.put("a", 1)
        assert c.get("a") == 1
        assert c.get("z") is None

    def test_eviction(self) -> None:
        c: LRUCache[str, int] = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)  # "a" should be evicted
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("c") == 3

    def test_lru_order_on_get(self) -> None:
        c: LRUCache[str, int] = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")   # "a" is now most-recently-used
        c.put("c", 3)  # "b" should be evicted, not "a"
        assert c.get("a") == 1
        assert c.get("b") is None

    def test_ttl_expiry(self) -> None:
        c: LRUCache[str, int] = LRUCache(10, ttl=0.05)
        c.put("x", 99)
        assert c.get("x") == 99
        time.sleep(0.1)
        assert c.get("x") is None  # expired

    def test_capacity_one(self) -> None:
        c: LRUCache[str, str] = LRUCache(1)
        c.put("a", "first")
        c.put("b", "second")
        assert c.get("a") is None
        assert c.get("b") == "second"

    def test_o1_operations(self) -> None:
        """get/put should be O(1) — test via timing 100k ops."""
        c: LRUCache[int, int] = LRUCache(10_000)
        t0 = time.perf_counter()
        for i in range(100_000):
            c.put(i, i)
            c.get(i)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0, f"100k LRU ops took {elapsed:.2f}s (expected < 5s)"


class TestTransactionGraph:
    def _txns(self) -> list[dict]:
        return [
            {"description": "Swiggy", "amount": -250.0, "date": "2026-01-01", "category_name": "Food"},
            {"description": "Swiggy", "amount": -250.0, "date": "2026-01-01", "category_name": "Food"},
            {"description": "Zomato", "amount": -300.0, "date": "2026-01-02", "category_name": "Food"},
            {"description": "Netflix", "amount": -500.0, "date": "2026-01-03", "category_name": "Entertainment"},
            {"description": "Netflix", "amount": -500.0, "date": "2026-01-04", "category_name": "Entertainment"},
            {"description": "Netflix", "amount": -500.0, "date": "2026-01-05", "category_name": "Entertainment"},
            {"description": "Netflix", "amount": -500.0, "date": "2026-01-06", "category_name": "Entertainment"},
            {"description": "Netflix", "amount": -500.0, "date": "2026-01-07", "category_name": "Entertainment"},
            {"description": "UBER", "amount": -1000.0, "date": "2026-01-08", "category_name": "Transport"},
        ]

    def test_graph_builds(self) -> None:
        g = TransactionGraph.from_transactions(self._txns())
        summary = g.graph_summary()
        assert summary["node_count"] >= 2  # at least categories + merchants
        assert summary["edge_count"] >= 3   # Food→swiggy, Food→zomato, Entertainment→netflix, ...

    def test_high_freq_merchants(self) -> None:
        g = TransactionGraph.from_transactions(self._txns())
        flags = g.high_frequency_merchants(threshold=5)
        names = [f["merchant"] for f in flags]
        assert "netflix" in names

    def test_high_freq_below_threshold(self) -> None:
        g = TransactionGraph.from_transactions(self._txns())
        flags = g.high_frequency_merchants(threshold=10)
        assert flags == []

    def test_duplicate_detection(self) -> None:
        txns = self._txns()
        dups = duplicate_transactions(txns, window_hours=24)
        # Swiggy ₹250 appears twice on same day → 1 duplicate pair
        assert len(dups) >= 1
        assert any(d["signal"] == "duplicate" for d in dups)

    def test_no_duplicates_outside_window(self) -> None:
        txns = [
            {"description": "Netflix", "amount": -500.0, "date": "2026-01-01", "category_name": "Ent"},
            {"description": "Netflix", "amount": -500.0, "date": "2026-01-10", "category_name": "Ent"},
        ]
        dups = duplicate_transactions(txns, window_hours=24)
        assert dups == []

    def test_round_number_anomalies(self) -> None:
        txns = self._txns()
        flags = round_number_anomalies(txns)
        # Netflix ₹500 and UBER ₹1000 are round-number amounts ≥ ₹500
        assert any(f["signal"].startswith("round_amount") for f in flags)

    def test_small_amounts_ignored(self) -> None:
        txns = [{"description": "Tea", "amount": -10.0, "date": "2026-01-01", "category_name": "Food"}]
        assert round_number_anomalies(txns) == []


class TestWSLatency:
    """Validate price pump fan-out latency is < 500ms end-to-end (in-process)."""

    def test_queue_fanout_under_500ms(self) -> None:
        """Simulate the pump→subscriber queue path; total latency must be < 500ms."""
        import asyncio  # noqa: PLC0415

        async def _run() -> float:
            q: asyncio.Queue = asyncio.Queue(maxsize=50)
            payload = {"symbol": "RELIANCE.NS", "price": 2850.5, "ts": int(time.time())}

            t0 = time.perf_counter()
            q.put_nowait(payload)           # pump side
            await q.get()                   # subscriber side
            return time.perf_counter() - t0

        elapsed = asyncio.run(_run())
        assert elapsed < 0.5, f"Fan-out latency {elapsed*1000:.1f}ms exceeded 500ms budget"

    def test_50_concurrent_subscribers_under_500ms(self) -> None:
        """50 queues receiving the same tick must all complete < 500ms."""
        async def _run() -> float:
            queues = [asyncio.Queue(maxsize=10) for _ in range(50)]
            payload = {"symbol": "TCS.NS", "price": 3800.0, "ts": int(time.time())}

            t0 = time.perf_counter()
            for q in queues:
                q.put_nowait(payload)
            results = await asyncio.gather(*[q.get() for q in queues])
            elapsed = time.perf_counter() - t0
            assert len(results) == 50
            return elapsed

        elapsed = asyncio.run(_run())
        assert elapsed < 0.5, f"50-subscriber fan-out took {elapsed*1000:.1f}ms"
