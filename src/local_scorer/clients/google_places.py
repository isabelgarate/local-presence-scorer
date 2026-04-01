from __future__ import annotations
"""Google Places API (New) client.

Docs: https://developers.google.com/maps/documentation/places/web-service/op-overview
"""

import logging
from typing import Any

from ..config import settings
from ..models.business import BusinessProfile
from .base import RateLimitedClient, UpstreamError

logger = logging.getLogger(__name__)

PLACES_BASE_URL = "https://places.googleapis.com"

# Fields we request in Place Details — keeps response small and controls billing tier
PLACE_DETAILS_FIELDS = ",".join([
    "id",
    "displayName",
    "rating",
    "userRatingCount",
    "primaryTypeDisplayName",
    "types",
    "websiteUri",
    "nationalPhoneNumber",
    "formattedAddress",
    "regularOpeningHours",
    "photos",
    "businessStatus",
    "location",
    "editorialSummary",
])

# Fields for text search (lighter, cheaper)
TEXT_SEARCH_FIELDS = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.rating",
    "places.userRatingCount",
    "places.primaryTypeDisplayName",
    "places.businessStatus",
    "places.websiteUri",
])


class GooglePlacesClient:
    def __init__(self) -> None:
        self._client = RateLimitedClient(
            base_url=PLACES_BASE_URL,
            rate_limit=settings.google_rate_limit,
        )
        self._api_key = settings.google_places_api_key

    async def __aenter__(self) -> "GooglePlacesClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.close()

    async def text_search(
        self,
        query: str,
        location_bias: str | None = None,
        max_results: int = 5,
        lat: float | None = None,
        lng: float | None = None,
        radius_meters: float = 1000.0,
    ) -> list[BusinessProfile]:
        """Search for businesses using free-text query.

        If lat/lng are provided, biases results to that location within radius_meters.
        """
        body: dict[str, Any] = {
            "textQuery": query,
            "maxResultCount": min(max_results, 20),
            "languageCode": "es",
        }
        if lat is not None and lng is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius_meters,
                }
            }
        # Otherwise location is embedded in the query string ("X in Madrid")

        response = await self._client.post(
            "/v1/places:searchText",
            json=body,
            headers={
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": TEXT_SEARCH_FIELDS,
            },
        )
        data = response.json()
        places = data.get("places", [])
        logger.debug("text_search(%r) returned %d places", query, len(places))
        return [self._parse_place(p) for p in places]

    async def place_details(self, place_id: str) -> BusinessProfile:
        """Fetch full details for a known place_id."""
        # place_id format: "places/ChIJ..." — strip prefix if raw ID passed
        resource = place_id if place_id.startswith("places/") else f"places/{place_id}"

        response = await self._client.get(
            f"/v1/{resource}",
            headers={
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": PLACE_DETAILS_FIELDS,
            },
        )
        data = response.json()
        return self._parse_place(data, full=True)

    def _parse_place(self, data: dict[str, Any], full: bool = False) -> BusinessProfile:
        raw_id = data.get("id", "")
        # API returns id as bare "ChIJ..." but sometimes prefixed
        place_id = raw_id.replace("places/", "") if raw_id else raw_id

        location = data.get("location", {})
        photos = data.get("photos", [])
        opening_hours = data.get("regularOpeningHours", {})

        # Categories
        primary_type = data.get("primaryTypeDisplayName", {})
        primary_category = (
            primary_type.get("text") if isinstance(primary_type, dict) else primary_type
        )
        types = data.get("types", [])

        # Extract social handles directly from GBP social media links
        ig_handle, fb_handle, tt_handle = self._parse_social_links(
            data.get("socialMediaLinks", []),
            data.get("websiteUri", ""),
        )

        return BusinessProfile(
            place_id=place_id,
            name=data.get("displayName", {}).get("text", "") if isinstance(data.get("displayName"), dict) else data.get("displayName", ""),
            rating=data.get("rating"),
            review_count=data.get("userRatingCount"),
            primary_category=primary_category,
            all_categories=types,
            website=data.get("websiteUri"),
            phone=data.get("nationalPhoneNumber"),
            address=data.get("formattedAddress"),
            opening_hours_present=bool(opening_hours.get("periods")),
            photos_count=len(photos),
            business_status=data.get("businessStatus"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            instagram_handle=ig_handle,
            facebook_handle=fb_handle,
            tiktok_handle=tt_handle,
            social_resolution_confidence=1.0 if any([ig_handle, fb_handle, tt_handle]) else 0.0,
        )

    def _parse_social_links(
        self,
        social_links: list[dict[str, Any]],
        website_uri: str,
    ) -> tuple[str | None, str | None, str | None]:
        """Extract Instagram, Facebook and TikTok handles from GBP social media links."""
        import re
        _IG = re.compile(r"instagram\.com/([A-Za-z0-9_.]{1,30})/?", re.I)
        _FB = re.compile(r"facebook\.com/([A-Za-z0-9_./-]{1,80})/?", re.I)
        _TT = re.compile(r"tiktok\.com/@([A-Za-z0-9_.]{1,30})/?", re.I)

        ig = fb = tt = None

        all_urls = [link.get("uri", "") for link in social_links]
        # Also check the website URI itself (some businesses link Instagram as their site)
        if website_uri:
            all_urls.append(website_uri)

        for url in all_urls:
            if not ig:
                m = _IG.search(url)
                if m and m.group(1).lower() not in {"p", "explore", "reel", "reels", "stories"}:
                    ig = m.group(1).rstrip("/")
            if not fb:
                m = _FB.search(url)
                if m:
                    seg = m.group(1).split("/")[0].lower()
                    if seg not in {"pages", "groups", "events", "login", "sharer", "share"}:
                        fb = m.group(1).rstrip("/")
            if not tt:
                m = _TT.search(url)
                if m and m.group(1).lower() not in {"discover", "trending"}:
                    tt = m.group(1).rstrip("/")

        if ig or fb or tt:
            logger.debug("GBP social links found — ig=%s fb=%s tt=%s", ig, fb, tt)

        return ig, fb, tt
