from __future__ import annotations
from datetime import datetime, timezone

UTC = timezone.utc
from fastapi import APIRouter
from pydantic import BaseModel

from ...config import settings
from ... import __version__

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    services: dict[str, bool]
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.environment,
        services={
            "google_places": bool(settings.google_places_api_key),
            "instagram": bool(settings.rapidapi_key),
        },
        timestamp=datetime.now(UTC),
    )
