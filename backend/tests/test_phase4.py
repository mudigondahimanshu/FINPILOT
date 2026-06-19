"""Phase 4 — security unit tests: TOTP, PII tokenization, drift detector."""

from __future__ import annotations

import hashlib
import re
import unittest


# ── TOTP ──────────────────────────────────────────────────────────────────────

class TestTOTP(unittest.TestCase):
    def setUp(self) -> None:
        import pyotp  # noqa: PLC0415
        self.pyotp = pyotp

    def test_generate_secret_is_base32(self) -> None:
        from app.core.totp import generate_secret  # noqa: PLC0415
        secret = generate_secret()
        assert re.fullmatch(r"[A-Z2-7]{32}", secret), f"bad secret: {secret}"

    def test_provisioning_uri_contains_issuer(self) -> None:
        from app.core.totp import generate_secret, get_provisioning_uri  # noqa: PLC0415
        uri = get_provisioning_uri("user@example.com", generate_secret())
        assert "FinPilot" in uri

    def test_valid_code_passes(self) -> None:
        from app.core.totp import generate_secret, verify_code  # noqa: PLC0415
        secret = generate_secret()
        code = self.pyotp.TOTP(secret).now()
        assert verify_code(secret, code) is True

    def test_wrong_code_fails(self) -> None:
        from app.core.totp import generate_secret, verify_code  # noqa: PLC0415
        secret = generate_secret()
        assert verify_code(secret, "000000") is False


# ── PII tokenization ──────────────────────────────────────────────────────────

class TestPII(unittest.TestCase):
    def test_tokenize_card_prefix(self) -> None:
        from app.core.pii import tokenize_card  # noqa: PLC0415
        token = tokenize_card("4111111111111111")
        assert token.startswith("tok_")
        assert len(token) == 28  # "tok_" + 24 hex chars

    def test_tokenize_card_deterministic(self) -> None:
        from app.core.pii import tokenize_card  # noqa: PLC0415
        assert tokenize_card("4111111111111111") == tokenize_card("4111111111111111")

    def test_tokenize_different_cards_differ(self) -> None:
        from app.core.pii import tokenize_card  # noqa: PLC0415
        assert tokenize_card("4111111111111111") != tokenize_card("5500005555555559")

    def test_mask_card_shows_last_four(self) -> None:
        from app.core.pii import mask_card  # noqa: PLC0415
        assert mask_card("4111111111111111") == "•••• •••• •••• 1111"

    def test_mask_card_handles_spaces(self) -> None:
        from app.core.pii import mask_card  # noqa: PLC0415
        assert mask_card("4111 1111 1111 1111") == "•••• •••• •••• 1111"

    def test_hash_ssn_is_sha256(self) -> None:
        from app.core.pii import hash_ssn  # noqa: PLC0415
        result = hash_ssn("1234-5678-9012")
        assert len(result) == 64
        assert result == hashlib.sha256("123456789012".encode()).hexdigest()

    def test_detect_and_mask_replaces_card(self) -> None:
        from app.core.pii import detect_and_mask  # noqa: PLC0415
        text = "charged to card 4111111111111111 today"
        masked = detect_and_mask(text)
        assert "4111111111111111" not in masked
        assert "1111" in masked

    def test_detect_and_mask_leaves_short_numbers(self) -> None:
        from app.core.pii import detect_and_mask  # noqa: PLC0415
        text = "I have 42 items costing INR 1000"
        assert detect_and_mask(text) == text


# ── Drift detector (pure functions only — no DB) ──────────────────────────────

class TestDriftDetector(unittest.TestCase):
    def test_psi_zero_for_identical_distributions(self) -> None:
        from app.ml.drift_detector import _psi  # noqa: PLC0415
        dist = [0.1] * 10
        assert _psi(dist, dist) == 0.0

    def test_psi_positive_for_shifted_distribution(self) -> None:
        from app.ml.drift_detector import _psi  # noqa: PLC0415
        expected = [0.1] * 10
        actual = [0.05] * 5 + [0.15] * 5
        assert _psi(expected, actual) > 0

    def test_kl_zero_for_identical_distributions(self) -> None:
        from app.ml.drift_detector import _kl_divergence  # noqa: PLC0415
        p = {"Food": 0.3, "Transport": 0.2, "Other": 0.5}
        assert abs(_kl_divergence(p, p)) < 1e-9

    def test_kl_positive_for_different_distributions(self) -> None:
        from app.ml.drift_detector import _kl_divergence  # noqa: PLC0415
        p = {"Food": 0.9, "Other": 0.1}
        q = {"Food": 0.1, "Other": 0.9}
        assert _kl_divergence(p, q) > 0


if __name__ == "__main__":
    unittest.main()
