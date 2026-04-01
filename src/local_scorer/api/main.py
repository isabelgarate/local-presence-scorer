"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import settings
from .routers import health, search, score, compare

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Local Presence Scorer starting (env=%s)", settings.environment)
    logger.info("Google Places: configured=%s", bool(settings.google_places_api_key))
    logger.info("Instagram: configured=%s", bool(settings.rapidapi_key))
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Local Presence Scorer",
        description=(
            "Score, rank and compare local businesses' digital presence "
            "using Google Business Profile and Instagram data."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": "bad_request", "detail": str(exc)})

    # Routers
    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix, tags=["health"])
    app.include_router(search.router, prefix=prefix, tags=["search"])
    app.include_router(score.router, prefix=prefix, tags=["score"])
    app.include_router(compare.router, prefix=prefix, tags=["compare"])

    return app


app = create_app()
