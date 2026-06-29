"""Prometheus metrics (Phase 4.3).

Instruments the FastAPI app automatically via prometheus-fastapi-instrumentator
and adds custom counters for domain events.

Usage in main.py:
    from app.core.metrics import instrument_app
    instrument_app(app)
"""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# Custom domain metrics
fraud_detections = Counter(
    "finpilot_fraud_detections_total",
    "Number of fraud anomalies detected by the Isolation Forest",
)
classifier_predictions = Counter(
    "finpilot_classifier_predictions_total",
    "Number of ML category predictions made",
    ["category"],
)
rag_queries = Counter(
    "finpilot_rag_queries_total",
    "Number of RAG copilot queries",
)
mfa_verifications = Counter(
    "finpilot_mfa_verifications_total",
    "TOTP verification attempts",
    ["result"],  # "success" | "failure"
)
login_attempts = Counter(
    "finpilot_login_attempts_total",
    "Login attempt count",
    ["result"],  # "success" | "failure" | "mfa_required"
)
transaction_imports = Counter(
    "finpilot_transaction_imports_total",
    "Transactions imported (CSV or manual)",
    ["source"],  # "csv" | "manual"
)
forecast_latency = Histogram(
    "finpilot_forecast_latency_seconds",
    "End-to-end spend forecast latency",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)


def instrument_app(app: FastAPI) -> None:
    """Attach Prometheus instrumentation and expose /metrics endpoint."""
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_group_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", tags=["observability"])
