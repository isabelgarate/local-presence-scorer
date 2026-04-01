from __future__ import annotations
"""Find nearby competitor businesses and score them against a target."""

import asyncio
import logging

from ..clients.google_places import GooglePlacesClient
from ..clients.instagram import InstagramClient
from ..clients.facebook import FacebookClient
from ..clients.tiktok import TikTokClient
from ..models.business import BusinessProfile, SocialData
from ..scorers.local_scorer import LocalScorer
from ..scorers.total_scorer import TotalScorer
from .search_service import SearchService, ScoredBusiness

logger = logging.getLogger(__name__)


class NearbyService:
    def __init__(
        self,
        places_client: GooglePlacesClient,
        instagram_client: InstagramClient | None = None,
        facebook_client: FacebookClient | None = None,
        tiktok_client: TikTokClient | None = None,
    ) -> None:
        self._places = places_client
        self._search = SearchService(places_client, instagram_client, facebook_client, tiktok_client)
        self._local_scorer = LocalScorer()
        self._total_scorer = TotalScorer()

    async def nearby_compare(
        self,
        name: str,
        location: str,
        radius_meters: float = 1000.0,
        max_competitors: int = 5,
        include_social: bool = False,
    ) -> tuple[ScoredBusiness | None, list[ScoredBusiness]]:
        """
        Find the target business, then search for nearby competitors
        in the same category using its coordinates.

        Returns (target, competitors) both scored, sorted by score desc.
        """
        # Step 1: find and score the target business
        target = await self._search.score_business(name, location, include_social=include_social)
        if target is None:
            return None, []

        profile = target.profile
        if profile.latitude is None or profile.longitude is None:
            logger.warning("No coordinates for '%s', falling back to text search", name)
            return target, []

        # Step 2: build a category query from the target's category
        category = profile.primary_category or "negocio"
        query = category  # e.g. "Italian Restaurant"

        logger.info(
            "Searching for '%s' near (%.4f, %.4f) within %dm",
            query, profile.latitude, profile.longitude, radius_meters,
        )

        # Step 3: search nearby using the target's coordinates
        nearby_profiles = await self._places.text_search(
            query=query,
            lat=profile.latitude,
            lng=profile.longitude,
            radius_meters=radius_meters,
            max_results=max_competitors + 3,  # fetch a few extra to filter out the target
        )

        # Step 4: score each competitor (skip the target itself)
        competitors: list[ScoredBusiness] = []
        for p in nearby_profiles:
            if p.place_id == profile.place_id:
                continue
            if len(competitors) >= max_competitors:
                break

            local = self._local_scorer.score(p, query=category)
            score = self._total_scorer.score(p.place_id, p.name, local=local, social=None, activity=None)
            competitors.append(ScoredBusiness(profile=p, instagram=None, score=score))

        # Sort competitors by score descending
        competitors.sort(key=lambda b: b.score.total, reverse=True)

        return target, competitors
