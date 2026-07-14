"""Transaction-graph tests — adjacency list, duplicate + round-number signals.

All tests are pure in-process; no DB or external APIs needed.
"""

from __future__ import annotations

from app.core.transaction_graph import (
    TransactionGraph,
    duplicate_transactions,
    round_number_anomalies,
)


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


