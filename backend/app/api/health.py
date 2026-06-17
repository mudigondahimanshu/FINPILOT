"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by Docker, CI, and the frontend."""
    return {"status": "ok", "service": "finpilot-backend", "version": __version__}
