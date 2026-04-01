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
    ) -> list[BusinessProfile]:
        """Search for businesses using free-text query."""
        body: dict[str, Any] = {
            "textQuery": query,
            "maxResultCount": min(max_results, 20),
            "languageCode": "es",
        }
        if location_bias:
            # Location bias as a text string — Google geocodes it
            body["locationBias"] = {"circle": {"center": {"text": location_bias}, "radius": 50000.0}}

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
        )
