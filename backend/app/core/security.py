"""Password hashing (bcrypt cost 12) and JWT access/refresh tokens."""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt cost factor 12 per the brief's security rules.
# We pre-hash with SHA-256 (base64) so passwords > 72 bytes are fully covered
# (bcrypt only consumes the first 72 bytes). This is the Django bcrypt_sha256
# pattern, chosen over passlib which is unmaintained and breaks with bcrypt 4.x.
_BCRYPT_ROUNDS = 12

TokenType = Literal["access", "refresh"]


def _prehash(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(
    subject: str, token_type: TokenType, expires_delta: timedelta
) -> tuple[str, str]:
    """Return (encoded_jwt, jti). jti enables Redis blacklist on logout."""
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    encoded = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded, jti


def create_access_token(subject: str) -> tuple[str, str]:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str) -> tuple[str, str]:
    return _create_token(
        subject,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode + validate a JWT. Raises ValueError on any problem."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:  # signature/expiry/format
        raise ValueError("invalid token") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise ValueError(f"expected {expected_type} token")
    if "sub" not in payload or "jti" not in payload:
        raise ValueError("malformed token")
    return payload
