from __future__ import annotations
"""Multi-platform social resolver.

Resolution order:
  Tier 1 — Handles already extracted from Google Business Profile (socialMediaLinks)
  Tier 2 — Scrape the business website for social links
  Tier 3 — Give up; no handle found (no name guessing — too unreliable)
"""

import json
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ..models.business import BusinessProfile

logger = logging.getLogger(__name__)

_PATTERNS = {
    "instagram": re.compile(r"instagram\.com/([A-Za-z0-9_.]{1,30})/?", re.I),
    "facebook": re.compile(r"facebook\.com/([A-Za-z0-9_./-]{1,80})/?", re.I),
    "tiktok": re.compile(r"tiktok\.com/@([A-Za-z0-9_.]{1,30})/?", re.I),
}
_REJECT = {
    "instagram": {"p", "explore", "reel", "reels", "stories", "tv", "accounts", ""},
    "facebook": {"pages", "groups", "events", "marketplace", "login", "sharer", "share", "dialog", "plugins", ""},
    "tiktok": {"discover", "trending", "following", "foryou", ""},
}


class SocialResolver:
    """
    Given a BusinessProfile (which may already have handles from GBP),
    fill in any missing handles by scraping the business website.
    """

    async def resolve_all(self, profile: BusinessProfile) -> dict[str, tuple[str | None, float]]:
        """
        Returns dict: {'instagram': (handle|None, confidence), 'facebook': ..., 'tiktok': ...}

        Confidence:
          1.0 = came directly from Google Business Profile
          0.9 = found by scraping the business website
          0.0 = not found
        """
        results: dict[str, tuple[str | None, float]] = {
            "instagram": (profile.instagram_handle, 1.0) if profile.instagram_handle else (None, 0.0),
            "facebook": (profile.facebook_handle, 1.0) if profile.facebook_handle else (None, 0.0),
            "tiktok": (profile.tiktok_handle, 1.0) if profile.tiktok_handle else (None, 0.0),
        }

        # Tier 2: scrape website for missing handles
        missing = [p for p, (h, _) in results.items() if h is None]
        if missing and profile.website:
            logger.debug("Scraping %s for social links (%s missing)", profile.website, missing)
            scraped = await self._scrape_website(profile.website)
            for platform in missing:
                if platform in scraped:
                    results[platform] = (scraped[platform], 0.9)
                    logger.debug("Website found @%s on %s", scraped[platform], platform)

        found = {p: h for p, (h, _) in results.items() if h}
        if found:
            logger.info("Social handles for '%s': %s", profile.name, found)
        else:
            logger.info("No social handles found for '%s'", profile.name)

        return results

    async def _scrape_website(self, website: str) -> dict[str, str]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; LocalScorer/1.0)"},
            ) as client:
                response = await client.get(website)
                return self._parse_html(response.text)
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.debug("Website scrape failed for %s: %s", website, exc)
            return {}

    def _parse_html(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        found: dict[str, str] = {}

        # <a href="...">
        for tag in soup.find_all("a", href=True):
            for platform, pattern in _PATTERNS.items():
                if platform not in found:
                    handle = self._extract(platform, pattern, tag["href"])
                    if handle:
                        found[platform] = handle

        # JSON-LD sameAs
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

        return found

    def _extract(self, platform: str, pattern: re.Pattern, url: str) -> str | None:
        match = pattern.search(url)
        if not match:
            return None
        raw = match.group(1).strip("/").split("?")[0].split("#")[0]
        first = raw.split("/")[0].lower()
        if first in _REJECT[platform]:
            return None
        return raw or None
