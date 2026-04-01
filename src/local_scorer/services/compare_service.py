from __future__ import annotations
"""Scores multiple businesses and returns them ranked."""

import asyncio
import logging

from ..clients.google_places import GooglePlacesClient
from ..clients.instagram import InstagramClient
from .search_service import SearchService, ScoredBusiness

logger = logging.getLogger(__name__)


class CompareService:
    def __init__(
        self,
        places_client: GooglePlacesClient,
        instagram_client: InstagramClient | None = None,
    ) -> None:
        self._service = SearchService(places_client, instagram_client)

    async def compare(
        self,
        businesses: list[tuple[str, str]],  # list of (name, location)
        include_instagram: bool = True,
    ) -> list[ScoredBusiness]:
        """Score all businesses concurrently, return sorted by total score descending."""
        tasks = [
            self._service.score_business(name, location, include_instagram)
            for name, location in businesses
        ]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[ScoredBusiness] = []
        for idx, r in enumerate(results_raw):
            name, location = businesses[idx]
            if isinstance(r, BaseException):
                logger.warning("Error scoring '%s' in '%s': %s", name, location, r)
            elif r is not None:
                results.append(r)

        results.sort(key=lambda b: b.score.total, reverse=True)
        return results
