from __future__ import annotations
"""Orchestrates: search → place details → social enrichment → scoring."""

import asyncio
import logging
from dataclasses import dataclass, field

from ..clients.google_places import GooglePlacesClient
from ..clients.instagram import InstagramClient
from ..clients.facebook import FacebookClient
from ..clients.tiktok import TikTokClient
from ..models.business import BusinessProfile, SocialData
from ..models.scores import TotalScore
from ..resolvers.social_resolver import SocialResolver
from ..scorers.local_scorer import LocalScorer
from ..scorers.social_scorer import SocialScorer
from ..scorers.total_scorer import TotalScorer

logger = logging.getLogger(__name__)


@dataclass
class ScoredBusiness:
    profile: BusinessProfile
    social: SocialData
    score: TotalScore


class SearchService:
    def __init__(
        self,
        places_client: GooglePlacesClient,
        instagram_client: InstagramClient | None = None,
        facebook_client: FacebookClient | None = None,
        tiktok_client: TikTokClient | None = None,
    ) -> None:
        self._places = places_client
        self._instagram = instagram_client
        self._facebook = facebook_client
        self._tiktok = tiktok_client
        self._resolver = SocialResolver()
        self._local_scorer = LocalScorer()
        self._social_scorer = SocialScorer()
        self._total_scorer = TotalScorer()

    async def search(
        self,
        query: str,
        location: str,
        max_results: int = 5,
        include_social: bool = False,
    ) -> list[ScoredBusiness]:
        """Quick search — local score only."""
        full_query = f"{query} in {location}"
        profiles = await self._places.text_search(full_query, max_results=max_results)

        results = []
        for profile in profiles:
            local = self._local_scorer.score(profile, query=query)
            score = self._total_scorer.score(profile.place_id, profile.name, local=local, social=None, activity=None)
            results.append(ScoredBusiness(profile=profile, social=SocialData(), score=score))

        return results

    async def score_business(
        self,
        name: str,
        location: str,
        include_social: bool = True,
    ) -> ScoredBusiness | None:
        """Full score: search → details → social enrichment → score."""
        query = f"{name} {location}"
        profiles = await self._places.text_search(query, max_results=1)

        if not profiles:
            logger.info("No Google Places result for '%s' in '%s'", name, location)
            return None

        profile = profiles[0]

        try:
            profile = await self._places.place_details(profile.place_id)
        except Exception as exc:
            logger.warning("Place details failed for %s: %s", profile.place_id, exc)

        social_data = SocialData()

        if include_social:
            social_data = await self._enrich_social(profile)

        local = self._local_scorer.score(profile, query=name)

        has_social = any([social_data.instagram, social_data.facebook, social_data.tiktok])
        if has_social:
            social_score, activity_score = self._social_scorer.score(social_data)
        else:
            social_score, activity_score = None, None

        total = self._total_scorer.score(
            profile.place_id, profile.name, local, social_score, activity_score
        )
        return ScoredBusiness(profile=profile, social=social_data, score=total)

    async def _enrich_social(self, profile: BusinessProfile) -> SocialData:
        """Resolve handles and fetch data from all available social platforms."""
        handles = await self._resolver.resolve_all(
            name=profile.name,
            website=profile.website,
        )

        ig_handle, ig_conf = handles["instagram"]
        fb_handle, fb_conf = handles["facebook"]
        tt_handle, tt_conf = handles["tiktok"]

        # Only use heuristic handles (confidence 0.3) if confidence is > 0
        if ig_handle and ig_conf > 0:
            profile.instagram_handle = ig_handle
        if fb_handle and fb_conf > 0:
            profile.facebook_handle = fb_handle
        if tt_handle and tt_conf > 0:
            profile.tiktok_handle = tt_handle

        profile.social_resolution_confidence = max(ig_conf, fb_conf, tt_conf)

        # Fetch all platforms concurrently
        ig_data, fb_data, tt_data = await asyncio.gather(
            self._fetch_instagram(ig_handle) if ig_handle and ig_conf > 0 and self._instagram else _noop(),
            self._fetch_facebook(fb_handle) if fb_handle and fb_conf > 0 and self._facebook else _noop(),
            self._fetch_tiktok(tt_handle) if tt_handle and tt_conf > 0 and self._tiktok else _noop(),
        )

        return SocialData(instagram=ig_data, facebook=fb_data, tiktok=tt_data)

    async def _fetch_instagram(self, handle: str):  # type: ignore[return]
        if not self._instagram:
            return None
        ig = await self._instagram.get_profile(handle)
        if ig:
            posts = await self._instagram.get_recent_posts(handle)
            avg_l, avg_c, p30, r30 = self._instagram.compute_activity_metrics(posts)
            ig.avg_likes_last_n = avg_l
            ig.avg_comments_last_n = avg_c
            ig.posts_last_30_days = p30
            ig.reels_last_30_days = r30
        return ig

    async def _fetch_facebook(self, handle: str):  # type: ignore[return]
        if not self._facebook:
            return None
        fb = await self._facebook.get_page(handle)
        if fb:
            posts = await self._facebook.get_recent_posts(handle)
            avg_l, avg_c, p30 = self._facebook.compute_activity_metrics(posts)
            fb.avg_likes_last_n = avg_l
            fb.avg_comments_last_n = avg_c
            fb.posts_last_30_days = p30
        return fb

    async def _fetch_tiktok(self, handle: str):  # type: ignore[return]
        if not self._tiktok:
            return None
        tt = await self._tiktok.get_profile(handle)
        if tt:
            videos = await self._tiktok.get_recent_videos(handle)
            avg_v, avg_l, p30 = self._tiktok.compute_activity_metrics(videos)
            tt.avg_views_last_n = avg_v
            tt.avg_likes_last_n = avg_l
            tt.posts_last_30_days = p30
        return tt


async def _noop():
    return None
