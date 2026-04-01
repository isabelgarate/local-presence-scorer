from __future__ import annotations
"""Instagram client via RapidAPI scraper.

API: instagram-api-fast-reliable-data-scraper
https://rapidapi.com/mediacrawlers-mediacrawlers-default/api/instagram-api-fast-reliable-data-scraper
"""

import logging
from datetime import datetime, timezone, timedelta

UTC = timezone.utc
from typing import Any

from ..config import settings
from ..models.business import InstagramData
from .base import RateLimitedClient, UpstreamError

logger = logging.getLogger(__name__)

RAPIDAPI_BASE = "https://instagram-api-fast-reliable-data-scraper.p.rapidapi.com"
RAPIDAPI_HOST = "instagram-api-fast-reliable-data-scraper.p.rapidapi.com"


class InstagramClient:
    def __init__(self) -> None:
        if not settings.rapidapi_key:
            raise ValueError(
                "RAPIDAPI_KEY is required for Instagram enrichment. "
                "Set it in .env or use include_instagram=False."
            )
        self._client = RateLimitedClient(
            base_url=RAPIDAPI_BASE,
            rate_limit=settings.instagram_rate_limit,
            default_headers={
                "x-rapidapi-key": settings.rapidapi_key,
                "x-rapidapi-host": RAPIDAPI_HOST,
            },
        )

    async def __aenter__(self) -> "InstagramClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.close()

    async def get_profile(self, handle: str) -> InstagramData | None:
        """Fetch profile info for an Instagram handle. Returns None if not found."""
        clean = handle.lstrip("@")
        try:
            response = await self._client.get(
                "/user/info",
                params={"username": clean},
            )
            data = response.json()
            return self._parse_profile(clean, data)
        except UpstreamError as exc:
            logger.warning("Instagram profile not found for @%s: %s", clean, exc)
            return None

    async def get_recent_posts(self, handle: str, limit: int = 30) -> list[dict[str, Any]]:
        """Fetch recent posts to compute activity metrics."""
        clean = handle.lstrip("@")
        try:
            response = await self._client.get(
                "/user/posts",
                params={"username": clean, "count": str(limit)},
            )
            data = response.json()
            return data.get("items", []) or []
        except UpstreamError:
            logger.warning("Could not fetch posts for @%s", clean)
            return []

    def _parse_profile(self, handle: str, data: dict[str, Any]) -> InstagramData:
        user = data.get("data", data.get("user", data))
        return InstagramData(
            handle=handle,
            followers=user.get("follower_count", user.get("followers", 0)) or 0,
            following=user.get("following_count", user.get("following", 0)) or 0,
            post_count=user.get("media_count", user.get("posts", 0)) or 0,
            is_verified=user.get("is_verified", False),
            is_business_account=user.get("is_business", user.get("is_professional_account", False)),
            bio=user.get("biography"),
        )

    def compute_activity_metrics(
        self, posts: list[dict[str, Any]]
    ) -> tuple[float, float, int, int]:
        """
        Returns (avg_likes, avg_comments, posts_last_30_days, reels_last_30_days).
        """
        if not posts:
            return 0.0, 0.0, 0, 0

        cutoff = datetime.now(UTC) - timedelta(days=30)
        recent = []
        reels = 0
        likes_total = 0
        comments_total = 0

        for post in posts:
            taken_at = post.get("taken_at") or post.get("timestamp", 0)
            ts = datetime.fromtimestamp(taken_at, UTC) if taken_at else None

            likes = post.get("like_count", 0) or 0
            comments = post.get("comment_count", 0) or 0
            likes_total += likes
            comments_total += comments

            is_reel = post.get("media_type") == 2 or post.get("product_type") == "clips"
            if ts and ts >= cutoff:
                recent.append(post)
                if is_reel:
                    reels += 1

        n = len(posts)
        avg_likes = likes_total / n if n else 0.0
        avg_comments = comments_total / n if n else 0.0

        return avg_likes, avg_comments, len(recent), reels
