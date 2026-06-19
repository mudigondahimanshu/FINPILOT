"""Trie for O(k) ticker prefix search, where k = prefix length.

Stores (symbol, name, exchange) tuples.  The root is pre-seeded with a curated
NSE/BSE universe so the endpoint works offline (no external API call needed for
autocomplete).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _Node:
    children: dict[str, _Node] = field(default_factory=dict)
    results: list[dict] = field(default_factory=list)  # leaf payloads


class TickerTrie:
    """Case-insensitive prefix trie for ticker autocomplete."""

    def __init__(self) -> None:
        self._root = _Node()

    def insert(self, symbol: str, name: str, exchange: str) -> None:
        key = symbol.upper()
        node = self._root
        for ch in key:
            node = node.children.setdefault(ch, _Node())
        # Store payload only at the terminal node to keep traversal lean.
        node.results.append({"symbol": key, "name": name, "exchange": exchange})

    def search(self, prefix: str, limit: int = 10) -> list[dict]:
        """Return up to `limit` matches for the given prefix."""
        node = self._root
        for ch in prefix.upper():
            node = node.children.get(ch)  # type: ignore[assignment]
            if node is None:
                return []
        return self._collect(node, limit)

    def _collect(self, node: _Node, limit: int) -> list[dict]:
        out: list[dict] = []
        stack = [node]
        while stack and len(out) < limit:
            cur = stack.pop()
            out.extend(cur.results)
            stack.extend(cur.children.values())
        return out[:limit]


# ── Pre-seeded NSE / BSE universe ────────────────────────────────────────────
# yfinance appends ".NS" for NSE and ".BO" for BSE.
_SEED: list[tuple[str, str, str]] = [
    ("RELIANCE.NS", "Reliance Industries", "NSE"),
    ("TCS.NS", "Tata Consultancy Services", "NSE"),
    ("HDFCBANK.NS", "HDFC Bank", "NSE"),
    ("INFY.NS", "Infosys", "NSE"),
    ("ICICIBANK.NS", "ICICI Bank", "NSE"),
    ("HINDUNILVR.NS", "Hindustan Unilever", "NSE"),
    ("SBIN.NS", "State Bank of India", "NSE"),
    ("BAJFINANCE.NS", "Bajaj Finance", "NSE"),
    ("BHARTIARTL.NS", "Bharti Airtel", "NSE"),
    ("KOTAKBANK.NS", "Kotak Mahindra Bank", "NSE"),
    ("LT.NS", "Larsen & Toubro", "NSE"),
    ("WIPRO.NS", "Wipro", "NSE"),
    ("HCLTECH.NS", "HCL Technologies", "NSE"),
    ("AXISBANK.NS", "Axis Bank", "NSE"),
    ("ASIANPAINT.NS", "Asian Paints", "NSE"),
    ("MARUTI.NS", "Maruti Suzuki", "NSE"),
    ("SUNPHARMA.NS", "Sun Pharmaceutical", "NSE"),
    ("TITAN.NS", "Titan Company", "NSE"),
    ("ADANIENT.NS", "Adani Enterprises", "NSE"),
    ("ADANIPORTS.NS", "Adani Ports", "NSE"),
    ("ULTRACEMCO.NS", "UltraTech Cement", "NSE"),
    ("ONGC.NS", "Oil & Natural Gas Corporation", "NSE"),
    ("NTPC.NS", "NTPC", "NSE"),
    ("POWERGRID.NS", "Power Grid Corporation", "NSE"),
    ("M&M.NS", "Mahindra & Mahindra", "NSE"),
    ("TATAMOTORS.NS", "Tata Motors", "NSE"),
    ("TATASTEEL.NS", "Tata Steel", "NSE"),
    ("JSWSTEEL.NS", "JSW Steel", "NSE"),
    ("COALINDIA.NS", "Coal India", "NSE"),
    ("DRREDDY.NS", "Dr. Reddy's Laboratories", "NSE"),
    ("CIPLA.NS", "Cipla", "NSE"),
    ("DIVISLAB.NS", "Divi's Laboratories", "NSE"),
    ("INDUSINDBK.NS", "IndusInd Bank", "NSE"),
    ("BAJAJFINSV.NS", "Bajaj Finserv", "NSE"),
    ("GRASIM.NS", "Grasim Industries", "NSE"),
    ("HDFCLIFE.NS", "HDFC Life Insurance", "NSE"),
    ("SBILIFE.NS", "SBI Life Insurance", "NSE"),
    ("TECHM.NS", "Tech Mahindra", "NSE"),
    ("NESTLEIND.NS", "Nestle India", "NSE"),
    ("BRITANNIA.NS", "Britannia Industries", "NSE"),
    ("HINDALCO.NS", "Hindalco Industries", "NSE"),
    ("BPCL.NS", "Bharat Petroleum", "NSE"),
    ("HEROMOTOCO.NS", "Hero MotoCorp", "NSE"),
    ("EICHERMOT.NS", "Eicher Motors", "NSE"),
    ("APOLLOHOSP.NS", "Apollo Hospitals", "NSE"),
    ("TATACONSUM.NS", "Tata Consumer Products", "NSE"),
    ("PIDILITIND.NS", "Pidilite Industries", "NSE"),
    ("HAVELLS.NS", "Havells India", "NSE"),
    ("SIEMENS.NS", "Siemens India", "NSE"),
    ("NIFTY50.NS", "Nifty 50 Index", "NSE"),
    ("SENSEX.BO", "BSE Sensex", "BSE"),
    ("^NSEI", "Nifty 50", "INDEX"),
    ("^BSESN", "BSE Sensex", "INDEX"),
]


def build_ticker_trie() -> TickerTrie:
    trie = TickerTrie()
    for symbol, name, exchange in _SEED:
        trie.insert(symbol, name, exchange)
        # Also index by name words so "Reliance" → RELIANCE.NS
        for word in name.split():
            if len(word) > 2:
                trie.insert(word + "__" + symbol, name, exchange)
    return trie


# Module-level singleton built once at import time.
ticker_trie: TickerTrie = build_ticker_trie()
