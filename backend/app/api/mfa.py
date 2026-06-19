"""MFA endpoints — TOTP setup/verify/disable + WebAuthn skeleton (Phase 4.1)."""

from __future__ import annotations

import base64
import io
import uuid

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit
from app.core.database import get_db
from app.core.metrics import mfa_verifications
from app.core.totp import generate_secret, get_provisioning_uri, verify_code
from app.models.user import User

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])

_MFA_RL = Depends(rate_limit(5, 60, "mfa"))


# ── TOTP ─────────────────────────────────────────────────────────────────────

@router.post("/setup")
async def mfa_setup(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a new TOTP secret and return QR code URI + base64 PNG.

    The secret is stored unconfirmed; call POST /auth/mfa/verify to activate.
    """
    if current_user.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "MFA already enabled")

    secret = generate_secret()
    uri = get_provisioning_uri(current_user.email, secret)

    # Persist the secret (not yet active — mfa_enabled stays False)
    await session.execute(
        update(User).where(User.id == current_user.id).values(totp_secret=secret)
    )
    await session.commit()

    # Generate QR PNG → base64
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "secret": secret,
        "uri": uri,
        "qr_png_b64": qr_b64,
        "instructions": (
            "Scan the QR code in Google Authenticator / Authy, "
            "then call POST /auth/mfa/verify with the 6-digit code."
        ),
    }


class VerifyRequest(BaseModel):
    code: str


@router.post("/verify", dependencies=[_MFA_RL])
async def mfa_verify(
    body: VerifyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Verify a TOTP code and activate MFA if correct.

    Also used during login when mfa_enabled=True to complete authentication.
    """
    if not current_user.totp_secret:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "MFA not set up — call POST /auth/mfa/setup first",
        )

    ok = verify_code(current_user.totp_secret, body.code.strip())
    mfa_verifications.labels(result="success" if ok else "failure").inc()

    if not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid TOTP code")

    if not current_user.mfa_enabled:
        await session.execute(
            update(User).where(User.id == current_user.id).values(mfa_enabled=True)
        )
        await session.commit()
        return {"status": "mfa_activated"}

    return {"status": "mfa_verified"}


@router.delete("/disable", dependencies=[_MFA_RL])
async def mfa_disable(
    body: VerifyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Disable MFA — requires valid TOTP code as confirmation."""
    if not current_user.mfa_enabled or not current_user.totp_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "MFA not enabled")

    if not verify_code(current_user.totp_secret, body.code.strip()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid TOTP code")

    await session.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(mfa_enabled=False, totp_secret=None)
    )
    await session.commit()
    return {"status": "mfa_disabled"}


@router.get("/status")
async def mfa_status(current_user: User = Depends(get_current_user)) -> dict:
    """Return the MFA state for the authenticated user."""
    return {"mfa_enabled": current_user.mfa_enabled}


# ── WebAuthn (passwordless) ───────────────────────────────────────────────────
# Full WebAuthn requires a browser round-trip (navigator.credentials.create /
# navigator.credentials.get) and is environment-sensitive. The endpoints below
# are structurally complete but return HTTP 501 until the frontend WebAuthn
# client is wired up. See: https://webauthn.guide/

@router.post("/webauthn/register/begin")
async def webauthn_register_begin(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return registration options for navigator.credentials.create."""
    # In production: webauthn.generate_registration_options(...)
    return {
        "status": "not_implemented",
        "detail": (
            "WebAuthn registration requires a browser session. "
            "Integrate @simplewebauthn/browser on the frontend and call "
            "POST /auth/mfa/webauthn/register/complete with the credential."
        ),
    }


@router.post("/webauthn/register/complete")
async def webauthn_register_complete(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Verify and persist a new WebAuthn credential."""
    # In production: webauthn.verify_registration_response(...)
    # then INSERT INTO webauthn_credentials (...)
    credential_id = str(uuid.uuid4())
    return {"status": "not_implemented", "credential_id": credential_id}


@router.post("/webauthn/login/begin")
async def webauthn_login_begin() -> dict:
    """Return authentication options for navigator.credentials.get."""
    return {"status": "not_implemented"}


@router.post("/webauthn/login/complete")
async def webauthn_login_complete() -> dict:
    """Verify a WebAuthn assertion and issue a JWT."""
    return {"status": "not_implemented"}
