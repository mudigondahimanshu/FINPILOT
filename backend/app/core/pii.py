"""PII tokenisation and masking utilities (Phase 4.1).

Provides:
  - tokenize_card  : card number → deterministic tok_<hex> token
  - mask_card      : "4111111111111111" → "•••• •••• •••• 1111"
  - hash_ssn       : SSN / Aadhaar → SHA-256 hex (one-way)
  - detect_and_mask: scan free-text and replace obvious PAN/card patterns

None of these functions store data — callers are responsible for persistence.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re

_TOKEN_KEY = os.getenv("PII_TOKEN_KEY", "finpilot-pii-hmac-key-change-in-prod").encode()

# Matches 13-19 digit card numbers (with optional spaces/dashes)
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# Matches Indian Aadhaar (12 digits) or generic SSN patterns
_SSN_RE = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")


def tokenize_card(card_number: str) -> str:
    """Return a stable, non-reversible token for a card number.

    Uses HMAC-SHA256 with the PII_TOKEN_KEY env var so tokens are
    consistent across restarts but cannot be reversed without the key.
    """
    digits = re.sub(r"[\s-]", "", card_number)
    mac = hmac.new(_TOKEN_KEY, digits.encode(), hashlib.sha256).hexdigest()[:24]
    return f"tok_{mac}"


def mask_card(card_number: str) -> str:
    """Return a display-safe masked version: •••• •••• •••• 1234."""
    digits = re.sub(r"[\s-]", "", card_number)
    visible = digits[-4:]
    return f"•••• •••• •••• {visible}"


def hash_ssn(ssn: str) -> str:
    """Return a SHA-256 hex digest of the SSN/Aadhaar for equality checks."""
    clean = re.sub(r"[\s-]", "", ssn)
    return hashlib.sha256(clean.encode()).hexdigest()


def detect_and_mask(text: str) -> str:
    """Replace card-number-like patterns in free text with masked versions."""
    def _mask(m: re.Match) -> str:
        return mask_card(m.group(0))

    text = _CARD_RE.sub(_mask, text)
    text = _SSN_RE.sub("[AADHAAR REDACTED]", text)
    return text
