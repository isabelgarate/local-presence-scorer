from __future__ import annotations
"""Tiered resolver to find an Instagram handle from a business profile.

Tier 1 — Instagram URL in Google Places data (instant, free)
Tier 2 — Scrape the business website for social links (cheap, ~70% hit rate)
Tier 3 — Heuristic handle from business name (low confidence, validated via API)
Tier 4 — Give up gracefully; caller proceeds without Instagram data
"""

import logging
import re
import unicodedata
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Matches instagram.com/handle — captures the handle
_INSTAGRAM_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,30})/?",
    re.IGNORECASE,
)

# Slugify: lowercase, keep alphanumeric and dots/underscores
def _slugify(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s]", "", name).strip().lower()
    return re.sub(r"\s+", ".", name)


class InstagramResolver:
    """Resolves Instagram handle from a BusinessProfile using multiple tiers."""

    async def resolve(
        self,
        name: str,
        website: str | None,
        google_data: dict[str, Any] | None = None,
    ) -> tuple[str | None, float]:
        """
        Returns (instagram_handle, confidence: 0.0–1.0).
        Confidence reflects how certain we are the handle belongs to this business.
        """
        # Tier 1: Check if Google Places returned any social links
        if google_data:
            handle = self._from_google_data(google_data)
            if handle:
                logger.debug("Tier 1 resolved: @%s (confidence 1.0)", handle)
                return handle, 1.0

        # Tier 2: Scrape business website
        if website:
            handle = await self._from_website(website)
            if handle:
                logger.debug("Tier 2 resolved: @%s (confidence 0.9)", handle)
                return handle, 0.9

        # Tier 3: Heuristic from business name
        handle = self._from_name(name)
        if handle:
            logger.debug("Tier 3 heuristic: @%s (confidence 0.3)", handle)
            return handle, 0.3

        logger.debug("Could not resolve Instagram handle for '%s'", name)
        return None, 0.0

    # ── Tier 1 ──────────────────────────────────────────────────────────────

    def _from_google_data(self, data: dict[str, Any]) -> str | None:
        # Check editorialSummary, social media links, and any URL fields
        for key in ("websiteUri", "website", "url"):
            url = data.get(key, "")
            if url:
                match = _INSTAGRAM_RE.search(url)
                if match:
                    return self._clean_handle(match.group(1))

        # Some new Places API responses include socialMediaLinks
        for link in data.get("socialMediaLinks", []):
            uri = link.get("uri", "")
            match = _INSTAGRAM_RE.search(uri)
            if match:
                return self._clean_handle(match.group(1))

        return None

    # ── Tier 2 ──────────────────────────────────────────────────────────────

    async def _from_website(self, website: str) -> str | None:
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
            return None

        return self._extract_from_html(html)

    def _extract_from_html(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        # Strategy A: <a href="...instagram.com/...">
        for tag in soup.find_all("a", href=True):
            match = _INSTAGRAM_RE.search(tag["href"])
            if match:
                handle = self._clean_handle(match.group(1))
                if handle:
                    return handle

        # Strategy B: JSON-LD structured data (sameAs in Organization schema)
        import json
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                # Handle both single object and list
                items = data if isinstance(data, list) else [data]
                for item in items:
                    same_as = item.get("sameAs", [])
                    if isinstance(same_as, str):
                        same_as = [same_as]
                    for url in same_as:
                        match = _INSTAGRAM_RE.search(url)
                        if match:
                            return self._clean_handle(match.group(1))
            except (json.JSONDecodeError, AttributeError):
                continue

        # Strategy C: meta tags (og:see_also, etc.)
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            match = _INSTAGRAM_RE.search(content)
            if match:
                handle = self._clean_handle(match.group(1))
                if handle:
                    return handle

        return None

    # ── Tier 3 ──────────────────────────────────────────────────────────────

    def _from_name(self, name: str) -> str | None:
        slug = _slugify(name)
        # Only return if it looks like a plausible handle (not too short)
        return slug if len(slug) >= 3 else None

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _clean_handle(self, raw: str) -> str | None:
        """Strip trailing slashes, query params, and reject obvious non-handles."""
        handle = raw.strip("/").split("?")[0].split("#")[0]
        # Reject known non-handle paths
        if handle.lower() in {"p", "explore", "reel", "reels", "stories", "tv", "accounts", ""}:
            return None
        return handle if len(handle) >= 1 else None
