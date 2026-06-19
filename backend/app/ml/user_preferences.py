"""Per-user preference embedding (Phase 3.6).

Computes a 384-dim spending-profile embedding per user by:
  1. Fetching the user's recent transaction descriptions + categories.
  2. Embedding them with all-MiniLM-L6-v2 (same model as RAG).
  3. Mean-pooling across all transactions → one profile vector.
  4. Storing it in the `user_preferences` table alongside category weights
     and an inferred risk profile (conservative / moderate / aggressive).

The embedding is used by the bandit and recommendation engine to provide
contextually personalised suggestions (cosine similarity between user profile
and arm context vectors).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

_RISK_THRESHOLDS = {
    "conservative": 0.4,   # investments+savings > 40% → conservative
    "aggressive": 0.25,    # investments > 25% → aggressive
}
_INVESTMENT_CATS = {"Investments", "Salary"}
_SPEND_CATS = {"Food", "Dining", "Shopping", "Entertainment", "Transport"}


def _infer_risk_profile(category_weights: dict[str, float]) -> str:
    spend_pct = sum(category_weights.get(c, 0.0) for c in _SPEND_CATS)
    if spend_pct >= _RISK_THRESHOLDS["conservative"]:
        return "conservative"
    invest_pct = sum(category_weights.get(c, 0.0) for c in _INVESTMENT_CATS)
    if invest_pct >= _RISK_THRESHOLDS["aggressive"]:
        return "aggressive"
    return "moderate"


async def compute_and_store(
    session: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 200,
) -> dict:
    """Compute embedding + category weights for *user_id* and upsert into user_preferences."""
    from sqlalchemy import text  # noqa: PLC0415

    rows = await session.execute(
        text(
            """
            SELECT t.description, c.name AS category_name, ABS(t.amount) AS abs_amount
              FROM transactions t
              LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.user_id = :uid
               AND t.amount < 0
             ORDER BY t.date DESC
             LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    )
    txns = rows.fetchall()

    if not txns:
        return {"status": "no_data"}

    # Category spend weights
    total_spend = sum(float(r.abs_amount) for r in txns)
    cat_totals: dict[str, float] = {}
    for r in txns:
        cat = r.category_name or "Other"
        cat_totals[cat] = cat_totals.get(cat, 0.0) + float(r.abs_amount)
    cat_weights = {k: round(v / (total_spend + 1e-9), 4) for k, v in cat_totals.items()}
    risk_profile = _infer_risk_profile(cat_weights)

    # Compute embedding asynchronously
    texts = [f"{r.description} {r.category_name or ''}" for r in txns]
    embedding = await asyncio.to_thread(_embed_texts, texts)

    await session.execute(
        text(
            """
            INSERT INTO user_preferences
                (user_id, embedding, top_categories, risk_profile, updated_at)
            VALUES (:uid, :emb, :cats::jsonb, :risk, NOW())
            ON CONFLICT (user_id) DO UPDATE
               SET embedding     = EXCLUDED.embedding,
                   top_categories = EXCLUDED.top_categories,
                   risk_profile  = EXCLUDED.risk_profile,
                   updated_at    = NOW()
            """
        ),
        {
            "uid": str(user_id),
            "emb": json.dumps(embedding),
            "cats": json.dumps(cat_weights),
            "risk": risk_profile,
        },
    )
    await session.commit()
    return {
        "status": "updated",
        "risk_profile": risk_profile,
        "top_categories": dict(
            sorted(cat_weights.items(), key=lambda x: x[1], reverse=True)[:5]
        ),
        "transactions_used": len(txns),
    }


async def get_preferences(session: AsyncSession, user_id: uuid.UUID) -> dict | None:
    """Fetch stored preferences for *user_id*. Returns None if not computed yet."""
    from sqlalchemy import text  # noqa: PLC0415

    row = await session.execute(
        text(
            "SELECT top_categories, risk_profile, updated_at"
            " FROM user_preferences WHERE user_id = :uid"
        ),
        {"uid": str(user_id)},
    )
    r = row.fetchone()
    if r is None:
        return None
    return {
        "top_categories": r.top_categories or {},
        "risk_profile": r.risk_profile,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _embed_texts(texts: list[str]) -> list[float]:
    """Return mean-pooled embedding vector over *texts*."""
    try:
        import numpy as np  # noqa: PLC0415
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        model = SentenceTransformer("all-MiniLM-L6-v2")
        vecs = model.encode(texts[:200], normalize_embeddings=True, show_progress_bar=False)
        mean_vec = np.mean(vecs, axis=0)
        norm = np.linalg.norm(mean_vec)
        if norm > 0:
            mean_vec = mean_vec / norm
        return mean_vec.tolist()
    except Exception as exc:
        log.warning("Preference embedding failed: %s", exc)
        return [0.0] * 384
