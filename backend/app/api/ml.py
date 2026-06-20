"""Phase 3 AI Brain — REST routes for all ML features."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit
from app.core.database import get_db
from app.ml import ab_testing, classifier, forecaster, fraud_detector, rag, sentiment, user_context
from app.ml import user_preferences as user_prefs
from app.ml.bandit import log_feedback, recommend
from app.models.user import User
from app.services import transaction_service

router = APIRouter(prefix="/ml", tags=["ml"])


# ── 3.1 Classifier ────────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    description: str
    amount: float
    date: str = "2026-01-01"


@router.post("/classify")
async def classify_transaction(
    body: ClassifyRequest,
    _: User = Depends(get_current_user),
) -> dict:
    """Predict spending category for a single transaction."""
    import asyncio  # noqa: PLC0415
    return await asyncio.to_thread(
        classifier.predict, body.description, body.amount, body.date
    )


@router.post("/classify/batch")
async def classify_batch(
    rows: list[ClassifyRequest],
    _: User = Depends(get_current_user),
) -> list[dict]:
    """Classify up to 200 transactions in a single XGBoost call."""
    if len(rows) > 200:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Max 200 rows per batch")
    import asyncio  # noqa: PLC0415
    return await asyncio.to_thread(
        classifier.predict_batch,
        [{"description": r.description, "amount": r.amount, "date": r.date} for r in rows],
    )


@router.post("/classify/auto", dependencies=[Depends(rate_limit(10, 60, "auto_classify"))])
async def auto_classify_history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Classify the user's un-categorised transactions and apply the predictions."""
    rows = await transaction_service.list_uncategorised(session, current_user.id)
    if not rows:
        return {"classified": 0, "message": "All transactions already categorised"}
    predictions = await classify_batch(
        [ClassifyRequest(description=r["description"], amount=float(r["amount"]), date=str(r["date"])) for r in rows], # noqa: E501
        current_user,
    )
    updated = await transaction_service.apply_classifications(session, current_user.id, rows, predictions) # noqa: E501
    return {"classified": updated}


# ── 3.2 Forecasting ───────────────────────────────────────────────────────────

@router.get(
    "/forecast/spending",
    dependencies=[Depends(rate_limit(10, 60, "forecast"))],
)
async def forecast_spending(
    days: int = Query(default=90, ge=30, le=365),
    horizon: int = Query(default=30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """30-day spend forecast: ARIMA baseline + Reservoir-LSTM ensemble."""
    series = await transaction_service.daily_spend_series(session, current_user.id, days=days)
    if len(series) < 4:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Need at least 4 days of history")
    result = await forecaster.forecast_spending(series, horizon=horizon)
    if "error" in result:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result["error"])
    return result


@router.post("/forecast/stock")
async def forecast_stock(
    symbol: str = Query(..., min_length=1, max_length=20),
    horizon: int = Query(default=5, ge=1, le=30),
    _: User = Depends(get_current_user),
) -> dict:
    """Short-horizon stock price forecast from recent OHLC data."""
    from app.services import market_service  # noqa: PLC0415
    ohlc = await market_service.get_ohlc(symbol.upper(), interval="1d", period="6mo")
    prices = [c["close"] for c in ohlc]
    if len(prices) < 6:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Insufficient price history")
    return await forecaster.forecast_stock(prices, horizon=horizon)


# ── 3.3 Sentiment ─────────────────────────────────────────────────────────────

@router.get("/sentiment/{symbol}", dependencies=[Depends(rate_limit(20, 60, "sentiment"))])
async def stock_sentiment(
    symbol: str,
    _: User = Depends(get_current_user),
) -> dict:
    """Fetch news headlines + VADER/FinBERT sentiment for a stock symbol."""
    return await sentiment.stock_sentiment(symbol.upper())


@router.post("/sentiment/text")
async def analyse_text(
    text: str = Body(..., embed=True, max_length=2000),
    _: User = Depends(get_current_user),
) -> dict:
    """Score the sentiment of arbitrary financial text."""
    return await sentiment.analyse_text(text)


# ── 3.4 Fraud ────────────────────────────────────────────────────────────────

@router.get("/fraud", dependencies=[Depends(rate_limit(5, 60, "fraud"))])
async def fraud_analysis(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Full fraud analysis: Isolation Forest + BFS graph + velocity checks."""
    rows = await transaction_service.list_all_for_fraud(session, current_user.id)
    if not rows:
        return {"message": "No transactions to analyse"}
    return await fraud_detector.full_fraud_analysis(rows)


# ── 3.5 RAG Copilot ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []


class IngestRequest(BaseModel):
    title: str
    body: str


@router.post("/copilot/chat", dependencies=[Depends(rate_limit(20, 60, "copilot"))])
async def copilot_chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Personalized RAG financial Q&A.

    Retrieves relevant knowledge-base docs, builds a snapshot of the caller's own
    finances (spending, budgets, risk profile, portfolio), then calls Claude Haiku
    so the answer is grounded in both the documents and the user's real data.
    """
    if not body.question.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Question cannot be empty")
    financial_context = await user_context.build_financial_context(session, current_user.id)
    return await rag.answer(session, body.question, body.history, financial_context)


@router.post("/copilot/ingest", dependencies=[Depends(rate_limit(5, 60, "ingest"))])
async def ingest_document(
    body: IngestRequest,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Chunk + embed a document and store in pgvector for retrieval."""
    if len(body.body) < 50:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Document too short")
    n = await rag.ingest_document(session, body.title, body.body)
    return {"chunks_inserted": n}


# ── 3.6 Recommendation bandit ─────────────────────────────────────────────────

@router.get("/recommend")
async def get_recommendation(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Epsilon-greedy recommendation arm selection."""
    return await recommend(session, current_user.id, {"user_id": str(current_user.id)})


class FeedbackRequest(BaseModel):
    impression_id: str
    accepted: bool


@router.post("/recommend/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Log thumbs-up / thumbs-down for a recommendation impression."""
    await log_feedback(session, body.impression_id, body.accepted)
    return {"status": "recorded"}


# ── 3.5 Copilot feedback (thumbs up/down on chat answers) ────────────────────

class CopilotFeedbackRequest(BaseModel):
    question: str
    answer: str
    thumbs_up: bool


@router.post("/copilot/feedback")
async def copilot_feedback(
    body: CopilotFeedbackRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Log thumbs-up / thumbs-down for a copilot answer."""
    await session.execute(
        text(
            """
            INSERT INTO copilot_feedback (id, user_id, question, answer, thumbs_up)
            VALUES (:id, :uid, :q, :a, :up)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "uid": str(current_user.id),
            "q": body.question[:2000],
            "a": body.answer[:4000],
            "up": body.thumbs_up,
        },
    )
    await session.commit()
    return {"status": "recorded"}


# ── 3.1 Manual category override (feeds classifier retraining data) ───────────

class CategoryOverrideRequest(BaseModel):
    transaction_id: str
    corrected_category: str
    description: str
    amount: float
    original_category: str | None = None


@router.post("/classify/override")
async def category_override(
    body: CategoryOverrideRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Record a manual category correction for future classifier retraining."""
    await session.execute(
        text(
            """
            INSERT INTO classifier_feedback
                (id, user_id, transaction_id, original_category,
                 corrected_category, description, amount)
            VALUES (:id, :uid, :txn_id, :orig, :corr, :desc, :amt)
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "uid": str(current_user.id),
            "txn_id": body.transaction_id,
            "orig": body.original_category,
            "corr": body.corrected_category,
            "desc": body.description[:512],
            "amt": body.amount,
        },
    )
    await session.commit()
    return {"status": "recorded", "category": body.corrected_category}


# ── 3.4 Geolocation anomaly check ─────────────────────────────────────────────

@router.get("/fraud/geo")
async def fraud_geo_check(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Check the caller's IP address for geolocation anomalies."""
    ip = request.headers.get(
        "x-forwarded-for", request.client.host if request.client else "127.0.0.1"
    )
    ip = ip.split(",")[0].strip()
    return await fraud_detector.geolocation_anomaly(ip)


# ── 3.6 User preference embedding ─────────────────────────────────────────────

@router.post("/preferences/compute")
async def compute_preferences(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Compute and store the user's spending-profile embedding."""
    return await user_prefs.compute_and_store(session, current_user.id)


@router.get("/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return the user's stored preference profile."""
    prefs = await user_prefs.get_preferences(session, current_user.id)
    if prefs is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No preference profile yet. Call POST /ml/preferences/compute first.",
        )
    return prefs


# ── 3.6 A/B testing ──────────────────────────────────────────────────────────

@router.get("/ab/{experiment}")
async def ab_variant(
    experiment: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return (and persist) this user's A/B variant for the given experiment."""
    if experiment not in ab_testing.EXPERIMENTS:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Unknown experiment '{experiment}'. Known: {list(ab_testing.EXPERIMENTS)}",
        )
    variant = await ab_testing.get_or_assign(session, current_user.id, experiment)
    return {"experiment": experiment, "variant": variant}


@router.get("/ab/{experiment}/summary", dependencies=[Depends(get_current_user)])
async def ab_summary(
    experiment: str,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return per-variant assignment counts for an experiment."""
    if experiment not in ab_testing.EXPERIMENTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown experiment '{experiment}'")
    return await ab_testing.get_experiment_summary(session, experiment)


# ── 3.6 Model versioning ──────────────────────────────────────────────────────

@router.get("/model/version", dependencies=[Depends(get_current_user)])
async def model_version() -> dict:
    """Return metadata about the currently deployed classifier version."""
    return classifier.get_model_version()


# ── 4.3 Model drift detection ─────────────────────────────────────────────────

@router.get("/model/drift", dependencies=[Depends(get_current_user)])
async def model_drift(session: AsyncSession = Depends(get_db)) -> dict:
    """Compare live transaction distribution against training baseline (KL + PSI)."""
    from app.ml import drift_detector  # noqa: PLC0415
    return await drift_detector.detect_drift(session)
