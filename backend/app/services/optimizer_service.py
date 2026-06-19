"""Markowitz Modern Portfolio Theory optimizer.

Implements:
- Efficient frontier via Monte Carlo (5000 random portfolios)
- Sharpe-ratio maximization using scipy.optimize.minimize (SLSQP)
- Risk score 0–100 derived from portfolio volatility
- Suggested allocations at three risk-tolerance levels (conservative/moderate/aggressive)

All heavy computation runs in a thread via asyncio.to_thread so it doesn't
block the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)

TRADING_DAYS = 252  # annualization factor


# ── Public API ────────────────────────────────────────────────────────────────

async def compute_efficient_frontier(
    symbols: list[str],
    period: str = "1y",
    n_portfolios: int = 3000,
    risk_free_rate: float = 0.065,  # RBI repo rate approx
) -> dict:
    """Return frontier portfolios + max-Sharpe + min-vol allocations."""
    return await asyncio.to_thread(
        _compute_sync, symbols, period, n_portfolios, risk_free_rate
    )


async def compute_risk_score(symbols: list[str], weights: list[float]) -> float:
    """Return a 0–100 risk score for the given weighted portfolio."""
    return await asyncio.to_thread(_risk_score_sync, symbols, weights)


# ── Sync implementations (run in thread pool) ─────────────────────────────────

def _compute_sync(
    symbols: list[str],
    period: str,
    n_portfolios: int,
    risk_free_rate: float,
) -> dict:
    try:
        import numpy as np  # noqa: PLC0415
        import yfinance as yf  # noqa: PLC0415
        from scipy.optimize import minimize  # noqa: PLC0415
    except ImportError as exc:
        return {"error": f"Missing dependency: {exc}"}

    # ── Fetch returns ─────────────────────────────────────────────────────────
    closes = yf.download(symbols, period=period, auto_adjust=True)["Close"]
    if closes.empty:
        return {"error": "No price data returned"}
    closes = closes.dropna(how="all")

    # Drop symbols with no data.
    valid_syms = [s for s in symbols if s in closes.columns and closes[s].notna().sum() > 30]
    if len(valid_syms) < 2:
        return {"error": "Need at least 2 symbols with sufficient history"}

    closes = closes[valid_syms].dropna()
    returns = closes.pct_change().dropna()
    mu = returns.mean().values * TRADING_DAYS           # annualised mean
    sigma = returns.cov().values * TRADING_DAYS         # annualised cov matrix
    n = len(valid_syms)

    # ── Monte Carlo frontier ──────────────────────────────────────────────────
    rng = np.random.default_rng(42)
    w_all = rng.dirichlet(np.ones(n), size=n_portfolios)
    port_ret = w_all @ mu
    port_vol = np.sqrt(np.einsum("ij,jk,ik->i", w_all, sigma, w_all))
    port_sharpe = (port_ret - risk_free_rate) / np.where(port_vol > 0, port_vol, np.nan)

    frontier = [
        {
            "weights": dict(zip(valid_syms, w.tolist(), strict=False)),
            "expected_return": float(r),
            "volatility": float(v),
            "sharpe": float(s),
        }
        for w, r, v, s in zip(w_all, port_ret, port_vol, port_sharpe, strict=False)
        if np.isfinite(s)
    ]

    # ── Scipy optimization ────────────────────────────────────────────────────
    def neg_sharpe(w: Any) -> float:
        r = float(w @ mu)
        v = float(np.sqrt(w @ sigma @ w))
        return -(r - risk_free_rate) / v if v > 0 else 0.0

    def port_volatility(w: Any) -> float:
        return float(np.sqrt(w @ sigma @ w))

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0.0, 1.0)] * n
    w0 = np.ones(n) / n

    max_sharpe_res = minimize(neg_sharpe, w0, method="SLSQP", bounds=bounds, constraints=constraints) # noqa: E501
    min_vol_res = minimize(port_volatility, w0, method="SLSQP", bounds=bounds, constraints=constraints) # noqa: E501

    def _fmt(res: Any) -> dict:
        w = res.x
        r = float(w @ mu)
        v = float(np.sqrt(w @ sigma @ w))
        return {
            "weights": {s: round(float(wi), 4) for s, wi in zip(valid_syms, w, strict=False)},
            "expected_annual_return": round(r, 4),
            "annual_volatility": round(v, 4),
            "sharpe_ratio": round((r - risk_free_rate) / v, 4) if v > 0 else 0.0,
        }

    # ── Risk-tolerance presets ────────────────────────────────────────────────
    conservative = _preset(valid_syms, mu, sigma, n, target_vol=0.10)
    moderate = _preset(valid_syms, mu, sigma, n, target_vol=0.18)
    aggressive = _preset(valid_syms, mu, sigma, n, target_vol=0.28)

    return {
        "symbols": valid_syms,
        "frontier": frontier[:500],  # cap for response size
        "max_sharpe": _fmt(max_sharpe_res),
        "min_volatility": _fmt(min_vol_res),
        "presets": {
            "conservative": conservative,
            "moderate": moderate,
            "aggressive": aggressive,
        },
        "risk_free_rate": risk_free_rate,
    }


def _preset(
    syms: list[str],
    mu: Any,
    sigma: Any,
    n: int,
    target_vol: float,
) -> dict:
    """Find the max-return portfolio whose volatility is ≤ target_vol."""
    try:
        import numpy as np  # noqa: PLC0415
        from scipy.optimize import minimize  # noqa: PLC0415
    except ImportError:
        return {}

    def neg_ret(w: Any) -> float:
        return -float(w @ mu)

    def vol_constraint(w: Any) -> float:
        return target_vol - float(np.sqrt(w @ sigma @ w))

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1},
        {"type": "ineq", "fun": vol_constraint},
    ]
    w0 = np.ones(n) / n
    res = minimize(neg_ret, w0, method="SLSQP", bounds=[(0.0, 1.0)] * n, constraints=constraints)
    w = res.x
    r = float(w @ mu)
    v = float(np.sqrt(w @ sigma @ w))
    return {
        "weights": {s: round(float(wi), 4) for s, wi in zip(syms, w, strict=False)},
        "expected_annual_return": round(r, 4),
        "annual_volatility": round(v, 4),
    }


async def compute_rebalance_suggestions(
    current_holdings: dict[str, float],
    target_weights: dict[str, float],
    total_value: float,
) -> list[dict]:
    """Return buy/sell suggestions to move from current to target allocation.

    current_holdings: symbol → current market value (INR)
    target_weights:   symbol → desired weight (must sum to ≈ 1.0)
    total_value:      total portfolio value in INR (cash + holdings)
    """
    suggestions = []
    all_symbols = set(current_holdings) | set(target_weights)
    for sym in sorted(all_symbols):
        current_val = current_holdings.get(sym, 0.0)
        target_val = target_weights.get(sym, 0.0) * total_value
        delta = target_val - current_val
        if abs(delta) < 10:  # ignore sub-₹10 noise
            continue
        suggestions.append({
            "symbol": sym,
            "action": "buy" if delta > 0 else "sell",
            "amount_inr": round(abs(delta), 2),
            "current_weight": round(current_val / total_value, 4) if total_value else 0.0,
            "target_weight": round(target_weights.get(sym, 0.0), 4),
            "weight_delta": round((target_val - current_val) / total_value, 4) if total_value else 0.0,  # noqa: E501
        })
    return sorted(suggestions, key=lambda x: x["amount_inr"], reverse=True)


def _risk_score_sync(symbols: list[str], weights: list[float]) -> float:
    """
    Risk score 0–100:
      0   = pure cash (0% volatility)
      100 = highly volatile concentrated single stock
    Calibrated so 15% annualised vol ≈ score 50.
    """
    try:
        import numpy as np  # noqa: PLC0415
        import yfinance as yf  # noqa: PLC0415
    except ImportError:
        return 50.0

    closes = yf.download(symbols, period="1y", auto_adjust=True)["Close"]
    if closes.empty:
        return 50.0

    closes = closes.dropna(how="all")
    valid = [s for s in symbols if s in closes.columns]
    if not valid:
        return 50.0

    closes = closes[valid].dropna()
    returns = closes.pct_change().dropna()
    cov = returns.cov().values * TRADING_DAYS
    w = np.array(weights[: len(valid)], dtype=float)
    w = w / w.sum() if w.sum() > 0 else np.ones(len(valid)) / len(valid)
    vol = float(np.sqrt(w @ cov @ w))
    # Sigmoid-like mapping: vol=0.15 → 50, vol=0.40 → ~90
    score = 100 * (1 - 1 / (1 + (vol / 0.15) ** 1.5))
    return round(min(max(score, 0.0), 100.0), 1)
