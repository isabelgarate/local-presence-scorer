from __future__ import annotations
from pydantic import BaseModel, HttpUrl, Field


class BusinessProfile(BaseModel):
    """Raw profile data fetched from Google Places."""

    place_id: str
    name: str
    rating: float | None = None          # 1.0–5.0
    review_count: int | None = None
    primary_category: str | None = None
    all_categories: list[str] = []
    website: str | None = None
    phone: str | None = None
    address: str | None = None
    opening_hours_present: bool = False
    photos_count: int = 0
    business_status: str | None = None   # OPERATIONAL, CLOSED_TEMPORARILY, CLOSED_PERMANENTLY
    latitude: float | None = None
    longitude: float | None = None

    # Resolved after Instagram lookup
    instagram_handle: str | None = None
    instagram_resolution_confidence: float = 0.0  # 0.0–1.0


class InstagramData(BaseModel):
    """Social data fetched from Instagram via RapidAPI."""

    handle: str
    followers: int = 0
    following: int = 0
    post_count: int = 0
    avg_likes_last_n: float = 0.0
    avg_comments_last_n: float = 0.0
    posts_last_30_days: int = 0
    reels_last_30_days: int = 0
    is_verified: bool = False
    is_business_account: bool = False
    bio: str | None = None


# ─── Request models ──────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Business type or name, e.g. 'italian restaurant'")
    location: str = Field(..., min_length=2, description="City or address, e.g. 'Austin, TX'")
    max_results: int = Field(default=5, ge=1, le=20)


class ScoreRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Business name")
    location: str = Field(..., min_length=2, description="City or address")
    include_instagram: bool = Field(default=True)


class CompareBusinessInput(BaseModel):
    name: str
    location: str


class CompareRequest(BaseModel):
    businesses: list[CompareBusinessInput] = Field(..., min_length=2, max_length=10)
    include_instagram: bool = Field(default=True)
