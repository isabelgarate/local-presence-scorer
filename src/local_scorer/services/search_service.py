from __future__ import annotations
"""Orchestrates: search → place details → Instagram enrichment → scoring."""

import logging
from dataclasses import dataclass

from ..clients.google_places import GooglePlacesClient
from ..clients.instagram import InstagramClient
from ..models.business import BusinessProfile, InstagramData
from ..models.scores import TotalScore
from ..resolvers.instagram_resolver import InstagramResolver
from ..scorers.local_scorer import LocalScorer
from ..scorers.social_scorer import SocialScorer
from ..scorers.total_scorer import TotalScorer

logger = logging.getLogger(__name__)


@dataclass
class ScoredBusiness:
    profile: BusinessProfile
    instagram: InstagramData | None
    score: TotalScore


class SearchService:
    def __init__(
        self,
        places_client: GooglePlacesClient,
        instagram_client: InstagramClient | None = None,
    ) -> None:
        self._places = places_client
        self._instagram = instagram_client
        self._resolver = InstagramResolver()
        self._local_scorer = LocalScorer()
        self._social_scorer = SocialScorer()
        self._total_scorer = TotalScorer()

    async def search(
        self,
        query: str,
        location: str,
        max_results: int = 5,
        include_instagram: bool = True,
    ) -> list[ScoredBusiness]:
        """Search businesses and score them (local score only, fast)."""
        full_query = f"{query} in {location}"
        profiles = await self._places.text_search(full_query, location_bias=location, max_results=max_results)

        results = []
        for profile in profiles:
            local = self._local_scorer.score(profile, query=query)
            score = self._total_scorer.score(profile.place_id, profile.name, local=local, social=None, activity=None)
            results.append(ScoredBusiness(profile=profile, instagram=None, score=score))

        return results

    async def score_business(
        self,
        name: str,
        location: str,
        include_instagram: bool = True,
    ) -> ScoredBusiness | None:
        """Full score: search → first match → details → Instagram → score."""
        query = f"{name} {location}"
        profiles = await self._places.text_search(query, location_bias=location, max_results=1)

        if not profiles:
            logger.info("No Google Places result for '%s' in '%s'", name, location)
            return None

        profile = profiles[0]

        # Fetch richer details
        try:
            profile = await self._places.place_details(profile.place_id)
        except Exception as exc:
            logger.warning("Place details failed for %s: %s", profile.place_id, exc)

        instagram_data: InstagramData | None = None

        if include_instagram and self._instagram:
            handle, confidence = await self._resolver.resolve(
                name=profile.name,
                website=profile.website,
            )
            if handle:
                profile.instagram_handle = handle
                profile.instagram_resolution_confidence = confidence

                ig_profile = await self._instagram.get_profile(handle)
                if ig_profile:
                    posts = await self._instagram.get_recent_posts(handle)
                    avg_likes, avg_comments, posts_30d, reels_30d = (
                        self._instagram.compute_activity_metrics(posts)
                    )
                    ig_profile.avg_likes_last_n = avg_likes
                    ig_profile.avg_comments_last_n = avg_comments
                    ig_profile.posts_last_30_days = posts_30d
                    ig_profile.reels_last_30_days = reels_30d
                    instagram_data = ig_profile

        local = self._local_scorer.score(profile, query=name)
        social = self._social_scorer.score_social(instagram_data) if instagram_data else None
        activity = self._social_scorer.score_activity(instagram_data) if instagram_data else None
        total = self._total_scorer.score(profile.place_id, profile.name, local, social, activity)

        return ScoredBusiness(profile=profile, instagram=instagram_data, score=total)
