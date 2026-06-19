"""Portfolio optimizer REST routes (Phase 2.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, rate_limit
from app.models.user import User
from app.services import optimizer_service

router = APIRouter(prefix="/optimizer", tags=["optimizer"])


class OptimizeRequest(BaseModel):
    symbols: list[str]
    period: str = "1y"
    n_portfolios: int = 3000
    risk_free_rate: float = 0.065


class RiskScoreRequest(BaseModel):
    symbols: list[str]
    weights: list[float]


@router.post(
    "/efficient-frontier",
    dependencies=[Depends(rate_limit(capacity=5, window_seconds=60, scope="optimizer"))],
)
async def efficient_frontier(
    body: OptimizeRequest,
    _: User = Depends(get_current_user),
) -> dict:
    """
    Compute the efficient frontier for the requested symbols.
    Returns Monte Carlo frontier points + max-Sharpe + min-vol allocations.
    Heavy computation runs in a thread pool — expect ~2–5s for 5 symbols.
    """
    if len(body.symbols) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Need at least 2 symbols")
    if len(body.symbols) > 15:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Maximum 15 symbols")

    result = await optimizer_service.compute_efficient_frontier(
        [s.upper() for s in body.symbols],
        period=body.period,
        n_portfolios=body.n_portfolios,
        risk_free_rate=body.risk_free_rate,
    )
    if "error" in result:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, result["error"])
    return result


@router.post("/risk-score")
async def risk_score(
    body: RiskScoreRequest,
    _: User = Depends(get_current_user),
) -> dict:
    """Return a 0–100 risk score for the given weighted portfolio."""
    if len(body.symbols) != len(body.weights):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "symbols and weights must have equal length") # noqa: E501
    score = await optimizer_service.compute_risk_score(
        [s.upper() for s in body.symbols], body.weights
    )
    return {"risk_score": score, "label": _risk_label(score)}


class RebalanceRequest(BaseModel):
    current_holdings: dict[str, float]  # symbol → current market value INR
    target_weights: dict[str, float]    # symbol → desired weight (sum ≈ 1.0)
    total_value: float                  # total portfolio value incl. cash


@router.post("/rebalance")
async def rebalance_suggestions(
    body: RebalanceRequest,
    _: User = Depends(get_current_user),
) -> dict:
    """Compute buy/sell suggestions to rebalance toward target weights."""
    weight_sum = sum(body.target_weights.values())
    if not (0.99 <= weight_sum <= 1.01):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"target_weights must sum to 1.0 (got {weight_sum:.4f})",
        )
    if body.total_value <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "total_value must be > 0")

    suggestions = await optimizer_service.compute_rebalance_suggestions(
        body.current_holdings,
        body.target_weights,
        body.total_value,
    )
    return {"suggestions": suggestions, "total_trades": len(suggestions)}


def _risk_label(score: float) -> str:
    if score < 25:
        return "Conservative"
    if score < 50:
        return "Moderate"
    if score < 75:
        return "Aggressive"
    return "Very Aggressive"
