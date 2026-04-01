from __future__ import annotations
"""FastAPI dependency injection."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from ..clients.google_places import GooglePlacesClient
from ..clients.instagram import InstagramClient
from ..config import settings
from ..services.compare_service import CompareService
from ..services.recommendation_service import RecommendationService
from ..services.search_service import SearchService


def get_places_client() -> GooglePlacesClient:
    return GooglePlacesClient()


def get_instagram_client() -> InstagramClient | None:
    if not settings.rapidapi_key:
        return None
    try:
        return InstagramClient()
    except ValueError:
        return None


def get_search_service(
    places: Annotated[GooglePlacesClient, Depends(get_places_client)],
    instagram: Annotated[InstagramClient | None, Depends(get_instagram_client)],
) -> SearchService:
    return SearchService(places, instagram)


def get_compare_service(
    places: Annotated[GooglePlacesClient, Depends(get_places_client)],
    instagram: Annotated[InstagramClient | None, Depends(get_instagram_client)],
) -> CompareService:
    return CompareService(places, instagram)


def get_recommendation_service() -> RecommendationService:
    return RecommendationService()
