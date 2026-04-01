from __future__ import annotations
"""Facebook page client via RapidAPI scraper.

Uses: facebook-pages-scraper on RapidAPI
Host: facebook-pages-scraper.p.rapidapi.com
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from ..config import settings
from ..models.business import FacebookData
from .base import RateLimitedClient, UpstreamError

logger = logging.getLogger(__name__)

UTC = timezone.utc
RAPIDAPI_HOST = "facebook-pages-scraper.p.rapidapi.com"
RAPIDAPI_BASE = f"https://{RAPIDAPI_HOST}"


class FacebookClient:
    def __init__(self) -> None:
        if not settings.rapidapi_key:
            raise ValueError("RAPIDAPI_KEY is required for Facebook enrichment.")
        self._client = RateLimitedClient(
            base_url=RAPIDAPI_BASE,
            rate_limit=settings.instagram_rate_limit,
            default_headers={
                "x-rapidapi-key": settings.rapidapi_key,
                "x-rapidapi-host": RAPIDAPI_HOST,
            },
        )

    async def __aenter__(self) -> "FacebookClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.close()

    async def get_page(self, handle: str) -> FacebookData | None:
        """Fetch page info for a Facebook page handle or URL slug."""
        clean = handle.lstrip("@").rstrip("/")
        try:
            response = await self._client.get(
                "/page_data",
                params={"page": clean},
            )
            data = response.json()
            return self._parse_page(clean, data)
        except UpstreamError as exc:
            logger.warning("Facebook page not found for %s: %s", clean, exc)
            return None

    async def get_recent_posts(self, handle: str, limit: int = 20) -> list[dict[str, Any]]:
        clean = handle.lstrip("@").rstrip("/")
        try:
            response = await self._client.get(
                "/page_posts",
                params={"page": clean, "count": str(limit)},
            )
            data = response.json()
            return data.get("data", []) or []
        except UpstreamError:
            logger.warning("Could not fetch Facebook posts for %s", clean)
            return []

    def _parse_page(self, handle: str, data: dict[str, Any]) -> FacebookData:
        page = data.get("data", data)
        return FacebookData(
            handle=handle,
            followers=page.get("followers_count", page.get("fan_count", 0)) or 0,
            likes=page.get("fan_count", page.get("likes", 0)) or 0,
            is_verified=page.get("verification_status") == "blue_verified" or page.get("is_verified", False),
            category=page.get("category"),
        )

    def compute_activity_metrics(
        self, posts: list[dict[str, Any]]
    ) -> tuple[float, float, int]:
        """Returns (avg_likes, avg_comments, posts_last_30_days)."""
        if not posts:
            return 0.0, 0.0, 0

        cutoff = datetime.now(UTC) - timedelta(days=30)
        recent_count = 0
        likes_total = 0
        comments_total = 0

        for post in posts:
            created = post.get("created_time", "")
            try:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None
            except ValueError:
                ts = None

            likes = post.get("likes", {}).get("summary", {}).get("total_count", 0) or 0
            comments = post.get("comments", {}).get("summary", {}).get("total_count", 0) or 0
            likes_total += likes
            comments_total += comments

            if ts and ts >= cutoff:
                recent_count += 1

        n = len(posts)
        return likes_total / n if n else 0.0, comments_total / n if n else 0.0, recent_count
