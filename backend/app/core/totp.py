"""TOTP helpers for MFA (RFC 6238 — same algorithm as Google Authenticator)."""

from __future__ import annotations

import pyotp

_ISSUER = "FinPilot"


def generate_secret() -> str:
    """Return a new cryptographically-random base32 TOTP secret."""
    return pyotp.random_base32()


def get_provisioning_uri(email: str, secret: str) -> str:
    """Return the otpauth:// URI to encode in a QR code."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=_ISSUER)


def verify_code(secret: str, code: str) -> bool:
    """Validate a 6-digit TOTP code. Allows ±30s clock skew (valid_window=1)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
