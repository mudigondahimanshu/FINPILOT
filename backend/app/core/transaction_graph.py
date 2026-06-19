"""Transaction adjacency-list graph for fraud / anomaly detection.

DSA: Directed weighted graph implemented as an adjacency list.
- Nodes  : merchant/description strings (normalised to lowercase)
- Edges  : directed from payer category → merchant, weighted by transaction count
- Algorithms:
    - duplicate_transactions : exact-amount duplicates within a time window (O(n log n))
    - high_frequency_merchants : merchants with degree > threshold (O(V + E))
    - round_number_anomalies  : amounts divisible by 100/500/1000 (O(n))
    - graph_summary           : degree stats for display
"""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any


class TransactionGraph:
    """Adjacency-list graph built from a list of transaction dicts."""

    def __init__(self) -> None:
        # adj[source_node] = {target_node: edge_weight}
        self._adj: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._node_totals: dict[str, Decimal] = defaultdict(Decimal)

    # ── Construction ──────────────────────────────────────────────────────────

    def add_transaction(self, category: str, merchant: str, amount: Decimal) -> None:
        """Add a directed edge category → merchant with the given spend."""
        src = _normalise(category)
        dst = _normalise(merchant)
        self._adj[src][dst] += 1
        self._node_totals[dst] += amount

    @classmethod
    def from_transactions(cls, transactions: list[dict]) -> TransactionGraph:
        g = cls()
        for t in transactions:
            cat = t.get("category_name") or "uncategorised"
            merch = t.get("description") or t.get("merchant") or "unknown"
            amount = Decimal(str(abs(float(t.get("amount", 0)))))
            g.add_transaction(cat, merch, amount)
        return g

    # ── Fraud / anomaly signals ───────────────────────────────────────────────

    def high_frequency_merchants(self, threshold: int = 5) -> list[dict]:
        """Return merchant nodes whose total in-degree exceeds *threshold*."""
        results = []
        in_degree: dict[str, int] = defaultdict(int)
        for targets in self._adj.values():
            for dst, count in targets.items():
                in_degree[dst] += count
        for node, deg in in_degree.items():
            if deg >= threshold:
                results.append({
                    "merchant": node,
                    "transaction_count": deg,
                    "total_spend": float(self._node_totals[node]),
                })
        return sorted(results, key=lambda x: x["transaction_count"], reverse=True)

    def graph_summary(self) -> dict:
        nodes = set(self._adj.keys())
        for targets in self._adj.values():
            nodes.update(targets.keys())
        edge_count = sum(len(t) for t in self._adj.values())
        return {"node_count": len(nodes), "edge_count": edge_count}


# ── Standalone anomaly detectors (operate on raw transaction lists) ────────────

def duplicate_transactions(
    transactions: list[dict],
    window_hours: int = 24,
) -> list[dict[str, Any]]:
    """Find transactions with the same amount + description within *window_hours*.

    Sort by (description, amount, date) then scan with a sliding pointer — O(n log n).
    """
    sorted_txns = sorted(
        transactions,
        key=lambda t: (_normalise(t.get("description", "")), t.get("amount", 0), t.get("date", "")),
    )
    duplicates: list[dict] = []
    n = len(sorted_txns)
    for i in range(n - 1):
        a = sorted_txns[i]
        b = sorted_txns[i + 1]
        if (
            _normalise(a.get("description", "")) == _normalise(b.get("description", ""))
            and a.get("amount") == b.get("amount")
            and _within_window(a.get("date", ""), b.get("date", ""), window_hours)
        ):
            duplicates.append({"transaction_a": a, "transaction_b": b, "signal": "duplicate"})
    return duplicates


def round_number_anomalies(
    transactions: list[dict],
    thresholds: tuple[int, ...] = (1000, 500, 100),
) -> list[dict[str, Any]]:
    """Flag transactions whose amount is exactly divisible by a round threshold.

    Round amounts (₹1000, ₹5000) often indicate manual / fraudulent entries.
    Returns only transactions above ₹500 to avoid flagging petty cash.
    """
    flags: list[dict] = []
    for t in transactions:
        try:
            amount = abs(float(t.get("amount", 0)))
        except (ValueError, TypeError):
            continue
        if amount < 500:
            continue
        for threshold in thresholds:
            if amount % threshold == 0:
                flags.append({**t, "signal": f"round_amount_{threshold}", "amount": amount})
                break
    return flags


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _within_window(date_a: str, date_b: str, hours: int) -> bool:
    from datetime import datetime  # noqa: PLC0415

    try:
        fmt = "%Y-%m-%d"
        da = datetime.strptime(date_a[:10], fmt)
        db = datetime.strptime(date_b[:10], fmt)
        return abs((db - da).total_seconds()) <= hours * 3600
    except ValueError:
        return False
