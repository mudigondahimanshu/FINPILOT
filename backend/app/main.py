"""FinPilot FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="FinPilot API",
        version=__version__,
        description="AI-powered personal finance copilot. Educational only — not financial advice.",
    )

    # CORS — strict allow-list from settings.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "name": "FinPilot API",
            "version": __version__,
            "docs": "/docs",
            "disclaimer": "Educational purposes only. Not financial advice.",
        }

    return app


app = create_app()
