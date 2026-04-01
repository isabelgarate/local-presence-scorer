from __future__ import annotations
"""Multi-platform social resolver.

Finds Instagram, Facebook and TikTok handles from a business profile
using the same tiered approach: GBP data → website scrape → name heuristic.
"""

import json
import logging
import re
import unicodedata
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Regex patterns per platform
_PATTERNS = {
    "instagram": re.compile(
        r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,30})/?",
        re.IGNORECASE,
    ),
    "facebook": re.compile(
        r"(?:https?://)?(?:www\.)?facebook\.com/([A-Za-z0-9_./-]{1,80})/?",
        re.IGNORECASE,
    ),
    "tiktok": re.compile(
        r"(?:https?://)?(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]{1,30})/?",
        re.IGNORECASE,
    ),
}

# Facebook paths that are not page handles
_FB_REJECT = {"pages", "groups", "events", "marketplace", "watch", "login", "sharer", "share", "dialog", "plugins"}
# Instagram paths that are not handles
_IG_REJECT = {"p", "explore", "reel", "reels", "stories", "tv", "accounts", ""}
# TikTok paths that are not handles
_TT_REJECT = {"discover", "trending", "following", "foryou", ""}


def _slugify(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s]", "", name).strip().lower()
    return re.sub(r"\s+", ".", name)


class SocialResolver:
    """Resolves Instagram, Facebook and TikTok handles for a business."""

    async def resolve_all(
        self,
        name: str,
        website: str | None,
        google_data: dict[str, Any] | None = None,
    ) -> dict[str, tuple[str | None, float]]:
        """
        Returns dict with keys 'instagram', 'facebook', 'tiktok'.
        Each value is (handle | None, confidence: 0.0–1.0).
        """
        results: dict[str, tuple[str | None, float]] = {
            "instagram": (None, 0.0),
            "facebook": (None, 0.0),
            "tiktok": (None, 0.0),
        }

        # Tier 1: Google Places data
        if google_data:
            for platform, (handle, _) in results.items():
                found = self._from_google_data(platform, google_data)
                if found:
                    results[platform] = (found, 1.0)

        # Tier 2: Website scrape (single HTTP request, parse all platforms)
        missing = [p for p, (h, _) in results.items() if h is None]
        if website and missing:
            scraped = await self._from_website(website)
            for platform in missing:
                if platform in scraped:
                    results[platform] = (scraped[platform], 0.9)

        # Tier 3: Name heuristic for still-missing platforms
        slug = _slugify(name) if name else ""
        for platform, (handle, _) in results.items():
            if handle is None and slug and len(slug) >= 3:
                results[platform] = (slug, 0.3)

        return results

    # ── Tier 1 ──────────────────────────────────────────────────────────────

    def _from_google_data(self, platform: str, data: dict[str, Any]) -> str | None:
        pattern = _PATTERNS[platform]
        for key in ("websiteUri", "website", "url"):
            url = data.get(key, "")
            if url:
                handle = self._extract(platform, pattern, url)
                if handle:
                    return handle
        for link in data.get("socialMediaLinks", []):
            handle = self._extract(platform, pattern, link.get("uri", ""))
            if handle:
                return handle
        return None

    # ── Tier 2 ──────────────────────────────────────────────────────────────

    async def _from_website(self, website: str) -> dict[str, str]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; LocalScorer/1.0)"},
            ) as client:
                response = await client.get(website)
                html = response.text
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.debug("Website fetch failed for %s: %s", website, exc)
            return {}

        return self._extract_from_html(html)

    def _extract_from_html(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        found: dict[str, str] = {}

        # Strategy A: <a href="...">
        for tag in soup.find_all("a", href=True):
            for platform, pattern in _PATTERNS.items():
                if platform not in found:
                    handle = self._extract(platform, pattern, tag["href"])
                    if handle:
                        found[platform] = handle

        # Strategy B: JSON-LD sameAs
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    same_as = item.get("sameAs", [])
                    if isinstance(same_as, str):
                        same_as = [same_as]
                    for url in same_as:
                        for platform, pattern in _PATTERNS.items():
                            if platform not in found:
                                handle = self._extract(platform, pattern, url)
                                if handle:
                                    found[platform] = handle
            except (json.JSONDecodeError, AttributeError):
                continue

        # Strategy C: meta tags
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            for platform, pattern in _PATTERNS.items():
                if platform not in found:
                    handle = self._extract(platform, pattern, content)
                    if handle:
                        found[platform] = handle

        return found

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _extract(self, platform: str, pattern: re.Pattern, url: str) -> str | None:
        match = pattern.search(url)
        if not match:
            return None
        raw = match.group(1).strip("/").split("?")[0].split("#")[0]

        if platform == "instagram" and raw.lower() in _IG_REJECT:
            return None
        if platform == "tiktok" and raw.lower() in _TT_REJECT:
            return None
        if platform == "facebook":
            first_segment = raw.split("/")[0].lower()
            if first_segment in _FB_REJECT:
                return None

        return raw if raw else None
