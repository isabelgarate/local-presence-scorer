from __future__ import annotations
from pydantic import BaseModel, Field


class BusinessProfile(BaseModel):
    """Raw profile data fetched from Google Places."""

    place_id: str
    name: str
    rating: float | None = None
    review_count: int | None = None
    primary_category: str | None = None
    all_categories: list[str] = []
    website: str | None = None
    phone: str | None = None
    address: str | None = None
    opening_hours_present: bool = False
    photos_count: int = 0
    business_status: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    # Resolved social handles
    instagram_handle: str | None = None
    facebook_handle: str | None = None
    tiktok_handle: str | None = None
    social_resolution_confidence: float = 0.0


class InstagramData(BaseModel):
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


class FacebookData(BaseModel):
    handle: str
    followers: int = 0        # page followers
    likes: int = 0            # page likes
    posts_last_30_days: int = 0
    avg_likes_last_n: float = 0.0
    avg_comments_last_n: float = 0.0
    is_verified: bool = False
    category: str | None = None


class TikTokData(BaseModel):
    handle: str
    followers: int = 0
    following: int = 0
    total_likes: int = 0      # total likes across all videos
    video_count: int = 0
    posts_last_30_days: int = 0
    avg_views_last_n: float = 0.0
    avg_likes_last_n: float = 0.0
    is_verified: bool = False


class SocialData(BaseModel):
    """Container for all resolved social platform data."""
    instagram: InstagramData | None = None
    facebook: FacebookData | None = None
    tiktok: TikTokData | None = None


# ─── Request models ──────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Business type or name")
    location: str = Field(..., min_length=2, description="City or address")
    max_results: int = Field(default=5, ge=1, le=20)


class ScoreRequest(BaseModel):
    name: str = Field(..., min_length=2)
    location: str = Field(..., min_length=2)
    include_social: bool = Field(default=True, description="Include Instagram, Facebook and TikTok scoring")


class CompareBusinessInput(BaseModel):
    name: str
    location: str


class CompareRequest(BaseModel):
    businesses: list[CompareBusinessInput] = Field(..., min_length=2, max_length=10)
    include_social: bool = Field(default=True)
