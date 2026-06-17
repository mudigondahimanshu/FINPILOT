"""Google OAuth2 (Authorization Code flow).

Dormant until GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are set in the environment.
CSRF is handled by the router via a double-submit `oauth_state` cookie.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import set_auth_ctx
from app.models.user import User
from app.services.auth_service import AuthError

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def build_authorization_url(state: str) -> str:
    """URL to redirect the browser to Google's consent screen."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> str:
    """Exchange an authorization code for a Google access token."""
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(_GOOGLE_TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise AuthError("google token exchange failed", status_code=401)
    token = resp.json().get("access_token")
    if not token:
        raise AuthError("google token exchange returned no token", status_code=401)
    return token


async def fetch_userinfo(google_access_token: str) -> dict:
    """Fetch the user's Google profile (sub, email, name, email_verified)."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
        )
    if resp.status_code != 200:
        raise AuthError("failed to fetch google profile", status_code=401)
    return resp.json()


async def find_or_create_user(session: AsyncSession, info: dict) -> User:
    """Look up by google_sub, link to an existing email, or create a new user."""
    sub = info.get("sub")
    email = (info.get("email") or "").lower()
    if not sub or not email:
        raise AuthError("incomplete google profile", status_code=401)

    await set_auth_ctx(session)

    # 1. Existing Google-linked account.
    existing = await session.execute(select(User).where(User.google_sub == sub))
    user = existing.scalar_one_or_none()
    if user is not None:
        return user

    # 2. Existing local account with the same email → link it.
    by_email = await session.execute(select(User).where(User.email == email))
    user = by_email.scalar_one_or_none()
    if user is not None:
        user.google_sub = sub
        if not user.is_verified and info.get("email_verified"):
            user.is_verified = True
        await session.commit()
        await session.refresh(user)
        return user

    # 3. Brand-new Google user.
    user = User(
        email=email,
        full_name=info.get("name"),
        auth_provider="google",
        google_sub=sub,
        is_verified=bool(info.get("email_verified")),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
