"""End-to-end auth flow test.

Requires a live Postgres (migrated) + Redis. Skipped unless FINPILOT_INTEGRATION=1
so the default unit suite stays green without infrastructure. CI sets the flag and
provides the services (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("FINPILOT_INTEGRATION") != "1",
    reason="integration test; set FINPILOT_INTEGRATION=1 with DB+Redis available",
)


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_full_auth_flow(client) -> None:  # type: ignore[no-untyped-def]
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret1"

    # Register
    r = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert r.status_code == 201, r.text
    access = r.json()["access_token"]
    assert r.cookies.get("refresh_token")

    # Authenticated /me
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == email

    # Duplicate registration rejected
    dup = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert dup.status_code == 409

    # Login
    login = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    assert login.json()["access_token"]

    # Wrong password rejected
    bad = await client.post(
        "/auth/login", json={"email": email, "password": "wrongpass1"}
    )
    assert bad.status_code == 401

    # Refresh rotates and yields a usable access token
    refreshed = await client.post("/auth/refresh")
    assert refreshed.status_code == 200
    access3 = refreshed.json()["access_token"]

    # Logout revokes the current access token
    out = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access3}"}
    )
    assert out.status_code == 204

    # Revoked token no longer works
    after = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access3}"}
    )
    assert after.status_code == 401
