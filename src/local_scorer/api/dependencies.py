from __future__ import annotations
"""FastAPI dependency injection."""

from typing import Annotated

from fastapi import Depends

from ..clients.google_places import GooglePlacesClient
from ..clients.instagram import InstagramClient
from ..clients.facebook import FacebookClient
from ..clients.tiktok import TikTokClient
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


def get_facebook_client() -> FacebookClient | None:
    if not settings.rapidapi_key:
        return None
    try:
        return FacebookClient()
    except ValueError:
        return None


def get_tiktok_client() -> TikTokClient | None:
    if not settings.rapidapi_key:
        return None
    try:
        return TikTokClient()
    except ValueError:
        return None


def get_search_service(
    places: Annotated[GooglePlacesClient, Depends(get_places_client)],
    instagram: Annotated[InstagramClient | None, Depends(get_instagram_client)],
    facebook: Annotated[FacebookClient | None, Depends(get_facebook_client)],
    tiktok: Annotated[TikTokClient | None, Depends(get_tiktok_client)],
) -> SearchService:
    return SearchService(places, instagram, facebook, tiktok)


def get_compare_service(
    places: Annotated[GooglePlacesClient, Depends(get_places_client)],
    instagram: Annotated[InstagramClient | None, Depends(get_instagram_client)],
    facebook: Annotated[FacebookClient | None, Depends(get_facebook_client)],
    tiktok: Annotated[TikTokClient | None, Depends(get_tiktok_client)],
) -> CompareService:
    return CompareService(places, instagram, facebook, tiktok)


def get_recommendation_service() -> RecommendationService:
    return RecommendationService()
