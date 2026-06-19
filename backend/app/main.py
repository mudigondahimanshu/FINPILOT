"""FinPilot FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import auth, health, market, mfa, ml, optimizer, portfolio, transactions
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.metrics import instrument_app

configure_logging(level="INFO" if settings.environment == "production" else "DEBUG")


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
    app.include_router(auth.router)
    app.include_router(mfa.router)
    app.include_router(transactions.router)
    app.include_router(market.router)
    app.include_router(portfolio.router)
    app.include_router(optimizer.router)
    app.include_router(ml.router)

    # Prometheus /metrics endpoint
    instrument_app(app)

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
