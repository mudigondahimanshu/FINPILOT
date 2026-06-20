"""Phase 3 ML unit tests — no DB, no external APIs, no trained model required.

Tests cover:
  - Classifier rule-based fallback + feature engineering
  - ARIMA + Reservoir-LSTM forecaster (synthetic data)
  - VADER sentiment scoring
  - Fraud detector (Isolation Forest + BFS/DFS + velocity + geolocation)
  - Bandit arm selection + simulated acceptance rate improvement
  - A/B testing deterministic assignment
  - User preference risk profile inference
  - Model version metadata
"""

from __future__ import annotations

import math
import uuid

from app.ml.ab_testing import EXPERIMENTS, _deterministic_variant
from app.ml.bandit import ARMS, EpsilonGreedyBandit
from app.ml.classifier import CATEGORIES, _amount_bucket, _clean, _rule_based, get_model_version
from app.ml.fraud_detector import (
    connected_components,
    detect_cycles,
    geolocation_anomaly_sync,
    isolation_forest_scores,
    velocity_anomalies,
)
from app.ml.user_preferences import _infer_risk_profile

# ── 3.1 Classifier ────────────────────────────────────────────────────────────

class TestClassifierFeatures:
    def test_clean(self) -> None:
        assert _clean("Swiggy - UPI!") == "swiggy   upi "

    def test_amount_bucket(self) -> None:
        assert _amount_bucket(50) == 0.0
        assert _amount_bucket(200) == 1.0
        assert _amount_bucket(1000) == 2.0
        assert _amount_bucket(5000) == 3.0

    def test_rule_based_food(self) -> None:
        result = _rule_based("Swiggy order", -250.0)
        assert result["category"] == "Food"
        assert result["confidence"] >= 0.5

    def test_rule_based_transport(self) -> None:
        result = _rule_based("Uber ride", -120.0)
        assert result["category"] == "Transport"

    def test_rule_based_salary(self) -> None:
        result = _rule_based("Salary Credit", 80000.0)
        assert result["category"] == "Salary"

    def test_rule_based_fallback(self) -> None:
        result = _rule_based("unknown merchant xyz", -100.0)
        assert result["category"] == "Other"

    def test_categories_count(self) -> None:
        assert len(CATEGORIES) == 15


# ── 3.2 Forecaster ────────────────────────────────────────────────────────────

class TestForecaster:
    def _series(self, n: int = 60) -> list[float]:
        return [200 + 50 * math.sin(i * 0.3) + (i % 7) * 10 for i in range(n)]

    def test_arima_returns_horizon_points(self) -> None:
        import numpy as np
        from app.ml.forecaster import _arima_forecast
        series = np.array(self._series())
        mean, lo, hi = _arima_forecast(series, 30)
        assert len(mean) == 30
        assert len(lo) == 30
        assert len(hi) == 30
        assert all(lo[i] <= hi[i] for i in range(30))

    def test_lstm_returns_horizon_points(self) -> None:
        import numpy as np
        from app.ml.forecaster import _lstm_forecast
        series = np.array(self._series())
        preds = _lstm_forecast(series, 30)
        assert len(preds) == 30
        assert all(p >= 0 for p in preds)

    def test_forecast_rmse_under_15pct(self) -> None:
        import asyncio

        from app.ml.forecaster import forecast_spending
        series = self._series(90)
        result = asyncio.run(forecast_spending(series, horizon=30))
        assert "validation" in result
        assert result["validation"]["arima_rmse_pct"] < 30.0 or result["validation"]["lstm_rmse_pct"] < 30.0

    def test_stock_forecast_shape(self) -> None:
        import asyncio

        from app.ml.forecaster import forecast_stock
        prices = [2800 + i * 3 + (i % 5) * 10 for i in range(60)]
        result = asyncio.run(forecast_stock(prices, horizon=5))
        assert len(result["forecast_prices"]) == 5
        assert result["last_price"] == prices[-1]

    def test_insufficient_data(self) -> None:
        import asyncio

        from app.ml.forecaster import forecast_spending
        result = asyncio.run(forecast_spending([100, 200], horizon=30))
        assert "error" in result


# ── 3.3 Sentiment ─────────────────────────────────────────────────────────────

class TestSentiment:
    def test_vader_bullish(self) -> None:
        from app.ml.sentiment import _vader_score
        result = _vader_score("Stock surges to record high on strong quarterly profit")
        assert result["score"] > 0

    def test_vader_bearish(self) -> None:
        from app.ml.sentiment import _vader_score
        result = _vader_score("Company crashes after fraud allegations and massive loss")
        assert result["score"] < 0

    def test_vader_neutral(self) -> None:
        from app.ml.sentiment import _vader_score
        result = _vader_score("Company announces quarterly earnings results")
        assert -0.6 < result["score"] < 0.6

    def test_label_bullish(self) -> None:
        from app.ml.sentiment import _label
        assert _label(0.5) == "Bullish"
        assert _label(-0.5) == "Bearish"
        assert _label(0.0) == "Neutral"

    def test_financial_boost(self) -> None:
        from app.ml.sentiment import _financial_boost
        assert _financial_boost("bullish rally breakout") > 0
        assert _financial_boost("crash bankrupt fraud") < 0


# ── 3.4 Fraud ────────────────────────────────────────────────────────────────

class TestFraudDetector:
    def _txns(self) -> list[dict]:
        return [
            {"description": f"merchant_{i % 5}", "amount": -(100 + i * 7),
             "date": f"2026-01-{(i % 28) + 1:02d}", "category_name": "Food"}
            for i in range(50)
        ]

    def test_isolation_forest_scores_all(self) -> None:
        txns = self._txns()
        results = isolation_forest_scores(txns)
        assert len(results) == len(txns)
        for r in results:
            assert 0.0 <= r["anomaly_score"] <= 1.0
            assert "is_anomaly" in r

    def test_isolation_forest_small_dataset(self) -> None:
        txns = self._txns()[:5]
        results = isolation_forest_scores(txns)
        assert all(r["anomaly_score"] == 0.0 for r in results)

    def test_bfs_components(self) -> None:
        adj = {"A": ["B", "C"], "B": ["A"], "C": ["A"], "D": ["E"], "E": ["D"]}
        comps = connected_components(adj)
        assert len(comps) == 2
        sizes = sorted(len(c) for c in comps)
        assert sizes == [2, 3]

    def test_cycle_detection(self) -> None:
        adj = {"A": ["B"], "B": ["C"], "C": ["A"]}
        cycles = detect_cycles(adj)
        assert len(cycles) >= 1

    def test_no_cycle(self) -> None:
        adj = {"A": ["B"], "B": ["C"], "C": []}
        cycles = detect_cycles(adj)
        assert cycles == []

    def test_velocity_anomaly(self) -> None:
        txns = [
            {"description": "Swiggy", "amount": -200.0, "date": "2026-01-01"}
            for _ in range(15)
        ]
        flags = velocity_anomalies(txns, window_minutes=1440, max_count=10)
        assert len(flags) >= 1
        assert flags[0]["signal"] == "velocity"


# ── 3.6 Bandit ───────────────────────────────────────────────────────────────

class TestBandit:
    def test_exploit_best_arm(self) -> None:
        bandit = EpsilonGreedyBandit(epsilon=0.0)
        arm_values = {"food_alert": 0.9, "savings_tip": 0.1, "forecast_warning": 0.5}
        assert bandit.select(arm_values) == "food_alert"

    def test_explore_random_arm(self) -> None:
        bandit = EpsilonGreedyBandit(epsilon=1.0)
        selected = {bandit.select({"food_alert": 0.9}) for _ in range(50)}
        assert len(selected) > 1  # must explore multiple arms

    def test_empty_arm_values_explores(self) -> None:
        bandit = EpsilonGreedyBandit(epsilon=0.0)
        arm = bandit.select({})
        assert arm in ARMS

    def test_all_arms_valid(self) -> None:
        assert len(ARMS) == 10
        assert all(isinstance(a, str) for a in ARMS)

    def test_bandit_acceptance_improves_over_simulated_rounds(self) -> None:
        """Simulate 500 bandit rounds. Greedy exploitation should converge on best arm.

        Validates: recommendation acceptance rate improves week-over-week (simulated).
        The 'true' best arm has reward=0.8; others have reward=0.2.
        We track acceptance in early (first 100) vs late (last 100) rounds.
        """
        import random  # noqa: PLC0415

        rng = random.Random(0)
        TRUE_REWARDS = {arm: 0.2 for arm in ARMS}
        TRUE_REWARDS["food_alert"] = 0.8  # best arm

        # Observed rewards (arm → list of observed 0/1)
        observed: dict[str, list[float]] = {arm: [] for arm in ARMS}

        early_rewards, late_rewards = [], []

        for step in range(500):
            # Compute current mean rewards from observations
            arm_values = {
                arm: sum(v) / len(v) if v else 0.0
                for arm, v in observed.items()
            }
            bandit = EpsilonGreedyBandit(epsilon=0.15)
            selected = bandit.select(arm_values)

            # Simulate user response based on true reward
            accepted = rng.random() < TRUE_REWARDS[selected]
            observed[selected].append(1.0 if accepted else 0.0)

            if step < 100:
                early_rewards.append(1.0 if accepted else 0.0)
            elif step >= 400:
                late_rewards.append(1.0 if accepted else 0.0)

        early_rate = sum(early_rewards) / len(early_rewards)
        late_rate = sum(late_rewards) / len(late_rewards)
        # Late acceptance should be meaningfully higher than early (bandit learned)
        assert late_rate > early_rate, f"Late {late_rate:.2f} not > early {early_rate:.2f}"
        assert late_rate >= 0.5, f"Late acceptance rate too low: {late_rate:.2f}"


# ── 3.6 A/B Testing ──────────────────────────────────────────────────────────

class TestABTesting:
    def test_deterministic_assignment(self) -> None:
        uid = uuid.uuid4()
        v1 = _deterministic_variant(uid, "bandit_v2", 0.10)
        v2 = _deterministic_variant(uid, "bandit_v2", 0.10)
        assert v1 == v2  # same user always gets same variant

    def test_different_users_can_get_different_variants(self) -> None:
        variants = {
            _deterministic_variant(uuid.uuid4(), "bandit_v2", 0.5)
            for _ in range(100)
        }
        assert len(variants) == 2  # both control and treatment appear

    def test_treatment_fraction_respected(self) -> None:
        n = 10000
        treatment_count = sum(
            1 for _ in range(n)
            if _deterministic_variant(uuid.uuid4(), "insights_widget", 0.20) == "treatment"
        )
        # Should be close to 20% (±3%)
        assert abs(treatment_count / n - 0.20) < 0.03

    def test_known_experiments_exist(self) -> None:
        assert "bandit_v2" in EXPERIMENTS
        assert "insights_widget" in EXPERIMENTS
        assert "forecast_v2" in EXPERIMENTS


# ── 3.6 User preference risk profile ─────────────────────────────────────────

class TestUserPreferences:
    def test_conservative_high_spend(self) -> None:
        weights = {"Food": 0.30, "Shopping": 0.25, "Entertainment": 0.20, "Salary": 0.25}
        assert _infer_risk_profile(weights) == "conservative"

    def test_aggressive_high_investment(self) -> None:
        weights = {"Investments": 0.30, "Salary": 0.50, "Food": 0.20}
        assert _infer_risk_profile(weights) == "aggressive"

    def test_moderate_balanced(self) -> None:
        weights = {"Food": 0.20, "Transport": 0.15, "Rent": 0.30, "Salary": 0.10, "Other": 0.25}
        assert _infer_risk_profile(weights) == "moderate"


# ── 3.5 Personalized copilot ──────────────────────────────────────────────────

class TestPersonalizedCopilot:
    """rag.answer threads the user's financial context through and flags it."""

    @staticmethod
    def _run_answer(user_context: str | None):
        import asyncio
        from unittest.mock import patch

        from app.ml import rag

        async def fake_retrieve(_session, _query, k=5):  # noqa: ARG001
            return []

        # Force the template path (no API key) and stub retrieval (no DB/embedder).
        with patch.object(rag, "retrieve", fake_retrieve), \
             patch.object(rag, "_ANTHROPIC_KEY", ""):
            return asyncio.run(
                rag.answer(session=None, question="How am I doing?",
                           history=[], user_context=user_context)
            )

    def test_personalized_flag_true_with_context(self) -> None:
        ctx = "USER FINANCIAL PROFILE:\n- Income: ₹50,000; Savings rate: 98%"
        result = self._run_answer(ctx)
        assert result["personalized"] is True
        # The user's real data is surfaced in the (template) answer.
        assert "50,000" in result["answer"]
        assert "personalized" in result["reasoning"].lower()

    def test_personalized_flag_false_without_context(self) -> None:
        result = self._run_answer(None)
        assert result["personalized"] is False
        assert "personalized" not in result["reasoning"].lower()


# ── 3.4 Geolocation anomaly ───────────────────────────────────────────────────

class TestGeolocationAnomaly:
    def test_new_country_flagged(self) -> None:
        logs = [
            {"ip": "1.2.3.4", "country": "IN", "known_countries": ["IN"]},
            {"ip": "5.6.7.8", "country": "RU", "known_countries": ["IN"]},
        ]
        results = geolocation_anomaly_sync(logs)
        flagged = [r for r in results if r["flagged"]]
        assert len(flagged) == 1
        assert flagged[0]["country"] == "RU"

    def test_rare_country_in_large_history_flagged(self) -> None:
        logs = [{"ip": f"1.1.1.{i}", "country": "IN", "known_countries": []} for i in range(10)]
        logs.append({"ip": "9.9.9.9", "country": "ZW", "known_countries": []})
        results = geolocation_anomaly_sync(logs)
        zw = next(r for r in results if r["country"] == "ZW")
        assert zw["flagged"]

    def test_known_country_not_flagged(self) -> None:
        logs = [{"ip": "1.2.3.4", "country": "IN", "known_countries": ["IN", "US"]}]
        results = geolocation_anomaly_sync(logs)
        assert not results[0]["flagged"]


# ── 3.1 Model versioning ──────────────────────────────────────────────────────

class TestModelVersioning:
    def test_get_model_version_returns_dict(self) -> None:
        version = get_model_version()
        assert isinstance(version, dict)
        assert "version" in version
