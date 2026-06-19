"""XGBoost transaction classifier (Phase 3.1).

Feature engineering:
  - log-amount, amount bucket (0-100 / 100-500 / 500-2000 / 2000+)
  - temporal: day-of-week, month, is-weekend
  - text: character 3-gram TF-IDF on description (top 300 features)

Model: XGBClassifier — 15 spending categories
Training: run backend/scripts/train_classifier.py to produce models/classifier.pkl
ONNX:     same script exports models/classifier.onnx for production serving
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

CATEGORIES = [
    "Food", "Transport", "Shopping", "Entertainment", "Health",
    "Utilities", "Travel", "Education", "Salary", "Investments",
    "Rent", "Insurance", "Dining", "Subscriptions", "Other",
]
CAT2IDX = {c: i for i, c in enumerate(CATEGORIES)}
IDX2CAT = {i: c for i, c in enumerate(CATEGORIES)}

_MODELS_DIR = Path(os.getenv("ML_MODELS_DIR", "/app/models"))
_clf_cache: Any = None
_vec_cache: Any = None


def get_model_version() -> dict:
    """Return metadata about the currently loaded model version."""
    import json as _json  # noqa: PLC0415

    meta_path = _MODELS_DIR / "model_version.json"
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                return _json.load(f)
        except Exception as exc:
            log.debug("Failed to load model_version.json: %s", exc)
    clf_path = _MODELS_DIR / "classifier.json"
    if clf_path.exists():
        mtime = clf_path.stat().st_mtime
        from datetime import datetime as _dt  # noqa: PLC0415
        return {
            "version": "unknown",
            "trained_at": _dt.fromtimestamp(mtime).isoformat(),
            "model_file": str(clf_path),
        }
    return {"version": "none", "status": "rule_based_fallback"}


# ── Public API ────────────────────────────────────────────────────────────────

def predict(description: str, amount: float, date_str: str) -> dict:
    """Return predicted category + confidence score for a single transaction."""
    clf, vec = _load_models()
    if clf is None:
        return _rule_based(description, amount)
    X = _build_feature_row(description, amount, date_str, vec)
    proba = _xgb_predict_proba(clf, X)[0]
    idx = int(np.argmax(proba))
    return {
        "category": IDX2CAT[idx],
        "confidence": round(float(proba[idx]), 4),
        "top3": [
            {"category": IDX2CAT[i], "score": round(float(p), 4)}
            for i, p in sorted(enumerate(proba), key=lambda x: -x[1])[:3]
        ],
    }


def predict_batch(rows: list[dict]) -> list[dict]:
    """Classify a list of transaction dicts in one XGBoost call."""
    clf, vec = _load_models()
    if clf is None:
        return [_rule_based(r.get("description", ""), float(r.get("amount", 0))) for r in rows]
    X = np.vstack([
        _build_feature_row(
            r.get("description", ""),
            float(r.get("amount", 0)),
            str(r.get("date", "")),
            vec,
        )
        for r in rows
    ])
    proba = _xgb_predict_proba(clf, X)
    results = []
    for p in proba:
        idx = int(np.argmax(p))
        results.append({"category": IDX2CAT[idx], "confidence": round(float(p[idx]), 4)})
    return results


# ── Feature engineering ───────────────────────────────────────────────────────

def _build_feature_row(
    description: str,
    amount: float,
    date_str: str,
    vec: Any,
) -> np.ndarray:
    from datetime import date as date_cls  # noqa: PLC0415

    # Amount features
    log_amount = float(np.log1p(abs(amount)))
    bucket = _amount_bucket(abs(amount))
    is_debit = 1.0 if amount < 0 else 0.0

    # Temporal
    try:
        d = date_cls.fromisoformat(date_str[:10])
        dow = d.weekday()
        month = d.month
        is_weekend = 1.0 if dow >= 5 else 0.0
    except ValueError:
        dow, month, is_weekend = 0, 1, 0.0

    scalar = np.array([log_amount, bucket, is_debit, float(dow), float(month), is_weekend])

    # Text features
    if vec is not None:
        text_feat = vec.transform([_clean(description)]).toarray()[0]
    else:
        text_feat = np.zeros(300)

    return np.concatenate([scalar, text_feat]).reshape(1, -1)


def _amount_bucket(amount: float) -> float:
    if amount < 100:
        return 0.0
    if amount < 500:
        return 1.0
    if amount < 2000:
        return 2.0
    return 3.0


def _clean(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower().strip())


# ── Model loading (lazy) ──────────────────────────────────────────────────────
# XGBoost is loaded via its native JSON format (xgb.Booster.load_model), NOT
# pickle, to avoid arbitrary code execution from untrusted bytes.  The TF-IDF
# vocabulary is serialised as plain JSON — both files are generated exclusively
# by scripts/train_classifier.py and stored in a server-controlled directory.

def _load_models() -> tuple[Any, Any]:
    global _clf_cache, _vec_cache  # noqa: PLW0603
    if _clf_cache is not None:
        return _clf_cache, _vec_cache
    clf_path = _MODELS_DIR / "classifier.json"   # XGBoost native JSON
    vec_path = _MODELS_DIR / "vectorizer.json"   # vocabulary as plain JSON
    if not clf_path.exists():
        log.info("classifier.json not found — using rule-based fallback")
        return None, None
    try:
        import json  # noqa: PLC0415

        import xgboost as xgb  # noqa: PLC0415
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415

        booster = xgb.Booster()
        booster.load_model(str(clf_path))
        _clf_cache = booster

        if vec_path.exists():
            with open(vec_path) as f:
                vocab = json.load(f)
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 3), max_features=300)
            vec.vocabulary_ = vocab
            # Rebuild idf_ as uniform (fine for inference with stored vocab)
            vec.idf_ = np.ones(len(vocab))
            _vec_cache = vec

        log.info("XGBoost classifier loaded from %s", clf_path)
    except Exception as exc:
        log.warning("Failed to load classifier: %s", exc)
        return None, None
    return _clf_cache, _vec_cache


def _xgb_predict_proba(booster: Any, X: np.ndarray) -> np.ndarray:
    """Run inference via xgb.Booster (not sklearn wrapper)."""
    import xgboost as xgb  # noqa: PLC0415
    dmat = xgb.DMatrix(X)
    raw = booster.predict(dmat)
    # Multi-class output is already softmax probabilities shaped (n, n_classes)
    if raw.ndim == 1:
        raw = raw.reshape(1, -1)
    return raw


# ── Rule-based fallback (when model not trained yet) ──────────────────────────

_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"swiggy|zomato|food|restaurant|cafe|pizza|burger|dunzo"), "Food"),
    (re.compile(r"uber|ola|rapido|metro|train|irctc|bus|fuel|petrol"), "Transport"),
    (re.compile(r"netflix|spotify|amazon prime|hotstar|zee5|jio cinema"), "Subscriptions"),
    (re.compile(r"salary|payroll|credit|income"), "Salary"),
    (re.compile(r"mutual fund|sip|nps|equity|zerodha|groww|coin"), "Investments"),
    (re.compile(r"airtel|jio|bsnl|electricity|water|gas|broadband"), "Utilities"),
    (re.compile(r"amazon|flipkart|myntra|ajio|nykaa|meesho"), "Shopping"),
    (re.compile(r"apollo|pharmacy|hospital|diagnostic|clinic|medplus"), "Health"),
    (re.compile(r"hotel|flight|makemytrip|goibibo|booking|airbnb"), "Travel"),
    (re.compile(r"school|college|course|udemy|coursera|byju|tuition"), "Education"),
    (re.compile(r"rent|pg|flat|housing"), "Rent"),
    (re.compile(r"insurance|lic|term|health plan|premium"), "Insurance"),
]


def _rule_based(description: str, amount: float) -> dict:
    text = description.lower()
    for pattern, category in _RULES:
        if pattern.search(text):
            return {"category": category, "confidence": 0.75}
    if amount > 0:
        return {"category": "Salary", "confidence": 0.5}
    return {"category": "Other", "confidence": 0.3}
