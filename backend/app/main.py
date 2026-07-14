"""FinPilot FastAPI application factory."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import auth, budgets, goals, health, mfa, ml, overview, transactions
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.metrics import instrument_app

configure_logging(level="INFO" if settings.environment == "production" else "DEBUG")

_DEFAULT_JWT_SECRET = "dev-only-change-me"  # noqa: S105 (the known dev default, not a secret)


def create_app() -> FastAPI:
    if (
        settings.environment == "production"
        and settings.jwt_secret_key == _DEFAULT_JWT_SECRET
    ):
        msg = "JWT_SECRET_KEY must be set in production (generate: openssl rand -hex 32)"
        raise RuntimeError(msg)

    app = FastAPI(
        title="FinPilot API",
        version=__version__,
        description="AI-powered personal finance copilot. Educational only — not financial advice.",
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if settings.environment == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

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
    app.include_router(budgets.router)
    app.include_router(goals.router)
    app.include_router(overview.router)
    app.include_router(ml.router)

    # Prometheus /metrics endpoint
    instrument_app(app)

    @app.on_event("startup")
    async def warm_copilot() -> None:
        # Load the 90 MB embedding model off the request path so the first
        # copilot question answers fast. No-op when embeddings are disabled.
        import threading  # noqa: PLC0415

        from app.ml.rag import preload_embedder  # noqa: PLC0415

        threading.Thread(target=preload_embedder, daemon=True).start()

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
