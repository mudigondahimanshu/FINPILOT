"""Unit tests for password hashing and JWT logic (no DB/Redis needed)."""

from __future__ import annotations

import time

import pytest
from app.core import security


def test_password_hash_roundtrip() -> None:
    hashed = security.hash_password("Sup3rSecret!")
    assert hashed != "Sup3rSecret!"
    assert security.verify_password("Sup3rSecret!", hashed)
    assert not security.verify_password("wrong", hashed)


def test_access_and_refresh_token_types() -> None:
    access, jti_a = security.create_access_token("user-1")
    refresh, jti_r = security.create_refresh_token("user-1")
    assert jti_a != jti_r

    pa = security.decode_token(access, expected_type="access")
    pr = security.decode_token(refresh, expected_type="refresh")
    assert pa["sub"] == "user-1" and pa["type"] == "access"
    assert pr["sub"] == "user-1" and pr["type"] == "refresh"


def test_wrong_expected_type_rejected() -> None:
    access, _ = security.create_access_token("user-1")
    with pytest.raises(ValueError):
        security.decode_token(access, expected_type="refresh")


def test_tampered_token_rejected() -> None:
    access, _ = security.create_access_token("user-1")
    with pytest.raises(ValueError):
        security.decode_token(access + "x", expected_type="access")


def test_token_has_exp_in_future() -> None:
    access, _ = security.create_access_token("user-1")
    payload = security.decode_token(access)
    assert payload["exp"] > time.time()
