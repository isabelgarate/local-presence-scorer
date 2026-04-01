from __future__ import annotations
"""TikTok client via RapidAPI scraper.

Uses: tiktok-scraper7 on RapidAPI
Host: tiktok-scraper7.p.rapidapi.com
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from ..config import settings
from ..models.business import TikTokData
from .base import RateLimitedClient, UpstreamError

logger = logging.getLogger(__name__)

UTC = timezone.utc
RAPIDAPI_HOST = "tiktok-scraper7.p.rapidapi.com"
RAPIDAPI_BASE = f"https://{RAPIDAPI_HOST}"


class TikTokClient:
    def __init__(self) -> None:
        if not settings.rapidapi_key:
            raise ValueError("RAPIDAPI_KEY is required for TikTok enrichment.")
        self._client = RateLimitedClient(
            base_url=RAPIDAPI_BASE,
            rate_limit=settings.instagram_rate_limit,
            default_headers={
                "x-rapidapi-key": settings.rapidapi_key,
                "x-rapidapi-host": RAPIDAPI_HOST,
            },
        )

    async def __aenter__(self) -> "TikTokClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.close()

    async def get_profile(self, handle: str) -> TikTokData | None:
        clean = handle.lstrip("@")
        try:
            response = await self._client.get(
                "/user/info",
                params={"unique_id": clean},
            )
            data = response.json()
            return self._parse_profile(clean, data)
        except UpstreamError as exc:
            logger.warning("TikTok profile not found for @%s: %s", clean, exc)
            return None

    async def get_recent_videos(self, handle: str, limit: int = 20) -> list[dict[str, Any]]:
        clean = handle.lstrip("@")
        try:
            response = await self._client.get(
                "/user/posts",
                params={"unique_id": clean, "count": str(limit)},
            )
            data = response.json()
            return data.get("data", {}).get("videos", []) or []
        except UpstreamError:
            logger.warning("Could not fetch TikTok videos for @%s", clean)
            return []

    def _parse_profile(self, handle: str, data: dict[str, Any]) -> TikTokData:
        user = data.get("data", {}).get("user", data.get("user", {}))
        stats = data.get("data", {}).get("stats", data.get("stats", {}))
        return TikTokData(
            handle=handle,
            followers=stats.get("followerCount", 0) or 0,
            following=stats.get("followingCount", 0) or 0,
            total_likes=stats.get("heartCount", stats.get("diggCount", 0)) or 0,
            video_count=stats.get("videoCount", 0) or 0,
            is_verified=user.get("verified", False),
        )

    def compute_activity_metrics(
        self, videos: list[dict[str, Any]]
    ) -> tuple[float, float, int]:
        """Returns (avg_views, avg_likes, posts_last_30_days)."""
        if not videos:
            return 0.0, 0.0, 0

        cutoff = datetime.now(UTC) - timedelta(days=30)
        recent_count = 0
        views_total = 0
        likes_total = 0

        for video in videos:
            create_time = video.get("create_time", video.get("createTime", 0))
            try:
                ts = datetime.fromtimestamp(int(create_time), UTC) if create_time else None
            except (ValueError, OSError):
                ts = None

            stats = video.get("stats", video.get("statistics", {}))
            views_total += stats.get("playCount", stats.get("play_count", 0)) or 0
            likes_total += stats.get("diggCount", stats.get("digg_count", 0)) or 0

            if ts and ts >= cutoff:
                recent_count += 1

        n = len(videos)
        return views_total / n if n else 0.0, likes_total / n if n else 0.0, recent_count
