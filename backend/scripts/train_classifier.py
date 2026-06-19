#!/usr/bin/env python3
"""Train the XGBoost transaction classifier (Phase 3.1).

Generates a synthetic labeled dataset (3 000 transactions) using merchant-
name heuristics + amount/temporal patterns, trains an XGBoost multi-class
classifier, validates accuracy on a 20% hold-out set, and exports:
  - models/classifier.json  (XGBoost native format — no pickle)
  - models/vectorizer.json  (TF-IDF vocabulary as plain JSON)
  - models/classifier.onnx  (ONNX runtime artifact for fast inference)

Run from the backend directory:
  python scripts/train_classifier.py
"""

from __future__ import annotations

import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Make 'app' importable when run from the backend/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import xgboost as xgb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

MODELS_DIR = Path(os.getenv("ML_MODELS_DIR", "models"))
MODELS_DIR.mkdir(exist_ok=True)

CATEGORIES = [
    "Food", "Transport", "Shopping", "Entertainment", "Health",
    "Utilities", "Travel", "Education", "Salary", "Investments",
    "Rent", "Insurance", "Dining", "Subscriptions", "Other",
]

# Merchant → category + typical amount range (INR)
MERCHANT_TEMPLATES: list[tuple[str, str, float, float]] = [
    ("Swiggy", "Food", 80, 600),
    ("Zomato", "Food", 100, 800),
    ("McDonald's", "Food", 150, 500),
    ("Domino's", "Food", 200, 700),
    ("Starbucks", "Dining", 300, 800),
    ("Uber", "Transport", 50, 500),
    ("Ola", "Transport", 40, 400),
    ("IRCTC", "Transport", 200, 3000),
    ("Rapido", "Transport", 30, 200),
    ("Netflix", "Subscriptions", 149, 649),
    ("Spotify", "Subscriptions", 119, 119),
    ("Amazon Prime", "Subscriptions", 999, 999),
    ("Hotstar", "Subscriptions", 299, 899),
    ("Amazon", "Shopping", 200, 5000),
    ("Flipkart", "Shopping", 300, 8000),
    ("Myntra", "Shopping", 500, 4000),
    ("Nykaa", "Shopping", 300, 3000),
    ("Apollo Pharmacy", "Health", 100, 2000),
    ("Medplus", "Health", 80, 1500),
    ("Max Healthcare", "Health", 500, 10000),
    ("Airtel", "Utilities", 299, 999),
    ("Jio", "Utilities", 149, 599),
    ("BSNL", "Utilities", 99, 499),
    ("BESCOM", "Utilities", 500, 3000),
    ("MakeMyTrip", "Travel", 2000, 30000),
    ("GoIbibo", "Travel", 1500, 25000),
    ("OYO", "Travel", 800, 5000),
    ("Udemy", "Education", 299, 4999),
    ("Coursera", "Education", 499, 3999),
    ("Byju's", "Education", 1000, 5000),
    ("Zerodha", "Investments", 500, 50000),
    ("Groww", "Investments", 1000, 100000),
    ("SBI MF", "Investments", 500, 10000),
    ("Salary Credit", "Salary", 20000, 200000),
    ("Rent Payment", "Rent", 8000, 40000),
    ("Society Charges", "Rent", 1000, 5000),
    ("LIC Premium", "Insurance", 2000, 20000),
    ("HDFC Term Plan", "Insurance", 1000, 15000),
    ("BookMyShow", "Entertainment", 200, 1500),
    ("PVR Cinemas", "Entertainment", 150, 600),
    ("Steam", "Entertainment", 100, 3000),
    ("General Store", "Other", 50, 500),
    ("ATM Withdrawal", "Other", 500, 5000),
]

rng = random.Random(42)  # noqa: S311
np_rng = np.random.default_rng(42)


def _random_date() -> str:
    start = date(2025, 1, 1)
    offset = rng.randint(0, 365)
    return (start + timedelta(days=offset)).isoformat()


def generate_dataset(n: int = 3000) -> tuple[list[str], list[float], list[str], list[str]]:
    descriptions, amounts, labels, dates = [], [], [], []
    for _ in range(n):
        tmpl = rng.choice(MERCHANT_TEMPLATES)
        desc, cat, lo, hi = tmpl
        amount = float(np_rng.uniform(lo, hi))
        amount = round(amount, -1)   # round to nearest 10
        # Add noise to description
        noise = rng.choice(["", " - UPI", " Payment", " Online", " App"])
        descriptions.append(desc + noise)
        amounts.append(-abs(amount) if cat != "Salary" else abs(amount))
        labels.append(cat)
        dates.append(_random_date())
    return descriptions, amounts, labels, dates


def build_features(
    descriptions: list[str],
    amounts: list[float],
    dates: list[str],
    vec: TfidfVectorizer | None = None,
) -> tuple[np.ndarray, TfidfVectorizer]:
    from app.ml.classifier import _amount_bucket, _clean  # noqa: PLC0415

    clean_desc = [_clean(d) for d in descriptions]
    if vec is None:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 3), max_features=300)
        text_feat = vec.fit_transform(clean_desc).toarray()
    else:
        text_feat = vec.transform(clean_desc).toarray()

    scalar_rows = []
    for amount, date_str in zip(amounts, dates, strict=False):
        log_amt = float(np.log1p(abs(amount)))
        bucket = _amount_bucket(abs(amount))
        is_debit = 1.0 if amount < 0 else 0.0
        try:
            d = date.fromisoformat(date_str[:10])
            dow = float(d.weekday())
            month = float(d.month)
            is_weekend = 1.0 if dow >= 5 else 0.0
        except ValueError:
            dow, month, is_weekend = 0.0, 1.0, 0.0
        scalar_rows.append([log_amt, bucket, is_debit, dow, month, is_weekend])

    scalar_feat = np.array(scalar_rows)
    return np.hstack([scalar_feat, text_feat]), vec


def main() -> None:
    print("Generating synthetic dataset…")
    descs, amts, labels, dates = generate_dataset(3000)

    from app.ml.classifier import CAT2IDX, CATEGORIES  # noqa: PLC0415
    y = np.array([CAT2IDX[lbl] for lbl in labels])

    X, vec = build_features(descs, amts, dates)
    X_train, X_test, y_train, y_test = train_test_split(  # noqa: E501
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)

    params = {
        "objective": "multi:softprob",
        "num_class": len(CATEGORIES),
        "max_depth": 6,
        "eta": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "eval_metric": "mlogloss",
        "seed": 42,
    }
    print("Training XGBoost…")
    booster = xgb.train(
        params,
        dtrain,
        num_boost_round=200,
        evals=[(dtest, "test")],
        verbose_eval=50,
    )

    # Evaluate
    proba = booster.predict(dtest)
    y_pred = proba.argmax(axis=1)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nAccuracy: {acc:.4f} ({acc*100:.1f}%)")
    print(classification_report(y_test, y_pred, target_names=CATEGORIES))

    if acc < 0.90:
        print("⚠️  Accuracy below 90% target — check synthetic data diversity.")

    # Save model in XGBoost native JSON format (no pickle)
    clf_path = MODELS_DIR / "classifier.json"
    booster.save_model(str(clf_path))
    print(f"Model saved → {clf_path}")

    # Save vectorizer vocabulary as plain JSON
    vec_path = MODELS_DIR / "vectorizer.json"
    with open(vec_path, "w") as f:
        json.dump(vec.vocabulary_, f)
    print(f"Vectorizer saved → {vec_path}")

    # ONNX export via skl2onnx (wraps the booster predict via onnxmltools)
    try:
        from onnxmltools.convert import convert_xgboost  # noqa: PLC0415
        from onnxmltools.convert.common.data_types import FloatTensorType  # noqa: PLC0415
        onnx_model = convert_xgboost(
            booster, initial_types=[("input", FloatTensorType([None, X_train.shape[1]]))]
        )
        onnx_path = MODELS_DIR / "classifier.onnx"
        with open(onnx_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        print(f"ONNX model saved → {onnx_path}")
    except Exception as exc:
        print(f"ONNX export skipped: {exc}")

    # Save model version metadata for versioning / audit trail
    from datetime import datetime as _dt  # noqa: PLC0415
    version_tag = _dt.utcnow().strftime("%Y%m%d_%H%M%S")
    version_meta = {
        "version": version_tag,
        "trained_at": _dt.utcnow().isoformat() + "Z",
        "accuracy": round(float(acc), 6),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_categories": len(CATEGORIES),
        "categories": CATEGORIES,
        "model_file": str(clf_path),
    }
    version_path = MODELS_DIR / "model_version.json"
    with open(version_path, "w") as f:
        json.dump(version_meta, f, indent=2)
    # Archive a versioned copy
    archive_path = MODELS_DIR / f"classifier_{version_tag}.json"
    import shutil  # noqa: PLC0415
    shutil.copy(str(clf_path), str(archive_path))
    print(f"Version metadata saved → {version_path}  (tag: {version_tag})")
    print(f"Archived model copy → {archive_path}")

    print("\nDone! Run the FastAPI server and POST to /ml/classify to test.")


if __name__ == "__main__":
    main()
