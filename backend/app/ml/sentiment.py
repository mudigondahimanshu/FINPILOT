"""Financial sentiment analysis (Phase 3.3).

Two-tier approach:
  1. VADER (NLTK) — offline, fast, no API required.
     Augmented with a financial lexicon (bull/bear terms mapped to VADER scores).
  2. FinBERT via Hugging Face Inference API — optional, higher accuracy.
     Activated when HF_API_KEY env var is set.

RSS scraping (feedparser) pulls headlines from:
  - Economic Times RSS
  - Moneycontrol RSS
  - Mint RSS
Headlines are cached in-process for 1 hour.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

log = logging.getLogger(__name__)

_HF_API_KEY = os.getenv("HF_API_KEY", "")
_FINBERT_URL = "https://api-inference.huggingface.co/models/ProsusAI/finbert"

_headline_cache: dict[str, Any] = {}  # symbol → {"ts": float, "items": list}
_CACHE_TTL = 3600  # 1 hour

_FINANCIAL_LEXICON = {
    "bullish": 0.8, "rally": 0.7, "surge": 0.7, "breakout": 0.6, "beat": 0.5,
    "profit": 0.5, "growth": 0.5, "upgrade": 0.6, "buy": 0.4, "strong": 0.4,
    "bearish": -0.8, "crash": -0.9, "plunge": -0.8, "downgrade": -0.7,
    "loss": -0.5, "miss": -0.5, "decline": -0.5, "sell": -0.4, "weak": -0.4,
    "default": -0.9, "fraud": -1.0, "scam": -1.0, "bankrupt": -1.0,
}

RSS_FEEDS = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/business.xml",
    "https://www.livemint.com/rss/markets",
]


# ── Public API ────────────────────────────────────────────────────────────────

async def analyse_text(text: str) -> dict:
    """Return sentiment score for a single text string."""
    if _HF_API_KEY:
        result = await asyncio.to_thread(_finbert_score, text)
        if result:
            return result
    return _vader_score(text)


async def stock_sentiment(symbol: str, limit: int = 20) -> dict:
    """Fetch recent news headlines for *symbol* and return aggregate sentiment."""
    headlines = await _get_headlines(symbol, limit)
    if not headlines:
        return {"symbol": symbol, "score": 0.0, "label": "Neutral", "headlines": []}

    scored = []
    for h in headlines:
        sentiment = await analyse_text(h["title"])
        scored.append({**h, "sentiment": sentiment})

    avg_score = sum(s["sentiment"]["score"] for s in scored) / len(scored)
    return {
        "symbol": symbol,
        "score": round(avg_score, 4),
        "label": _label(avg_score),
        "headlines": scored,
    }


# ── VADER ─────────────────────────────────────────────────────────────────────

def _vader_score(text: str) -> dict:
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer  # noqa: PLC0415
        _ensure_vader()
        sia = SentimentIntensityAnalyzer()
        scores = sia.polarity_scores(text)
        # Blend VADER compound with financial lexicon
        fin_boost = _financial_boost(text)
        compound = float(np.clip(scores["compound"] + fin_boost * 0.3, -1, 1))
        return {"score": round(compound, 4), "label": _label(compound), "method": "vader"}
    except Exception as exc:
        log.warning("VADER failed: %s", exc)
        fin_score = _financial_boost(text)
        return {"score": round(fin_score, 4), "label": _label(fin_score), "method": "lexicon"}


def _financial_boost(text: str) -> float:
    words = text.lower().split()
    total = sum(_FINANCIAL_LEXICON.get(w, 0.0) for w in words)
    return float(np.clip(total / max(len(words), 1) * 5, -1, 1))


_vader_ready = False


def _ensure_vader() -> None:
    global _vader_ready  # noqa: PLW0603
    if _vader_ready:
        return
    import nltk  # noqa: PLC0415
    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)
    _vader_ready = True


# ── FinBERT (optional) ────────────────────────────────────────────────────────

def _finbert_score(text: str) -> dict | None:
    try:
        import httpx  # noqa: PLC0415
        resp = httpx.post(
            _FINBERT_URL,
            headers={"Authorization": f"Bearer {_HF_API_KEY}"},
            json={"inputs": text[:512]},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list) or not data:
            return None
        scores = {item["label"].lower(): item["score"] for item in data[0]}
        compound = scores.get("positive", 0.0) - scores.get("negative", 0.0)
        return {"score": round(compound, 4), "label": _label(compound), "method": "finbert"}
    except Exception as exc:
        log.debug("FinBERT API failed: %s", exc)
        return None


# ── RSS scraper ───────────────────────────────────────────────────────────────

async def _get_headlines(symbol: str, limit: int) -> list[dict]:
    key = symbol.upper()
    cached = _headline_cache.get(key)
    if cached and time.time() - cached["ts"] < _CACHE_TTL:
        return cached["items"][:limit]

    items = await asyncio.to_thread(_scrape_rss, key)
    _headline_cache[key] = {"ts": time.time(), "items": items}
    return items[:limit]


def _scrape_rss(symbol: str) -> list[dict]:
    try:
        import feedparser  # noqa: PLC0415
    except ImportError:
        return []

    results: list[dict] = []
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").upper()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "")
                if clean_sym in title.upper() or not clean_sym:
                    results.append({
                        "title": title,
                        "url": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "source": feed.feed.get("title", url),
                    })
        except Exception as exc:
            log.debug("RSS parse error for %s: %s", url, exc)

    # If symbol not found in any headline, return recent market headlines anyway
    if not results:
        for url in RSS_FEEDS[:1]:
            try:
                import feedparser as fp  # noqa: PLC0415
                feed = fp.parse(url)
                for entry in feed.entries[:10]:
                    results.append({
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "source": feed.feed.get("title", url),
                    })
            except Exception as _exc:
                log.debug("RSS feed error: %s", _exc)

    return results[:50]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _label(score: float) -> str:
    if score > 0.15:
        return "Bullish"
    if score < -0.15:
        return "Bearish"
    return "Neutral"


try:
    import numpy as np  # noqa: E402
except ImportError:

    class _NpShim:
        @staticmethod
        def clip(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, v))

    np = _NpShim()  # type: ignore[assignment]
