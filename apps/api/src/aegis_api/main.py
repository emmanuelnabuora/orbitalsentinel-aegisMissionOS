"""AEGIS MissionOS API - application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import aegis_api.models  # noqa: F401 - register ORM metadata
from aegis_api.api.v1.router import api_router
from aegis_api.core.config import get_settings
from aegis_api.core.exceptions import (
    AuthError,
    ConflictError,
    NotFoundError,
    RateLimitedError,
    ValidationFailure,
)
from aegis_api.core.logging import configure_logging, get_logger
from aegis_api.middleware import RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger("aegis.startup")
    settings = get_settings()
    log.info("startup", env=settings.env, version=settings.version)
    from aegis_api.services.ingestion.wiring import build_scheduler

    scheduler = build_scheduler(settings)
    if scheduler:
        scheduler.start()
    yield
    if scheduler:
        await scheduler.stop()
    log.info("shutdown")


def _register_exception_handlers(app: FastAPI) -> None:
    mapping = {
        RateLimitedError: status.HTTP_429_TOO_MANY_REQUESTS,
        NotFoundError: status.HTTP_404_NOT_FOUND,
        ConflictError: status.HTTP_409_CONFLICT,
        AuthError: status.HTTP_401_UNAUTHORIZED,
        ValidationFailure: status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    for exc_type, code in mapping.items():

        def handler(request, exc, code=code):
            headers = {"WWW-Authenticate": "Bearer"} if code == 401 else None
            return JSONResponse({"detail": exc.message}, status_code=code, headers=headers)

        app.add_exception_handler(exc_type, handler)


def create_app() -> FastAPI:
    settings = get_settings()
    docs_enabled = settings.env in ("local", "test")

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        # No public API docs outside local - reduce recon surface
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    _register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
