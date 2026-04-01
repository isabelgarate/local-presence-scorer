from __future__ import annotations
from datetime import datetime, timezone

UTC = timezone.utc
from pydantic import BaseModel, computed_field


class LocalScore(BaseModel):
    """Score derived from Google Business Profile data."""

    rating_component: float
    review_count_component: float
    category_match_component: float
    website_component: float
    profile_completeness_component: float

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> float:
        return round(
            0.35 * self.rating_component
            + 0.30 * self.review_count_component
            + 0.15 * self.category_match_component
            + 0.10 * self.website_component
            + 0.10 * self.profile_completeness_component,
            4,
        )


class InstagramScore(BaseModel):
    """Score for a single Instagram profile."""
    follower_component: float
    engagement_component: float

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> float:
        return round(0.50 * self.follower_component + 0.50 * self.engagement_component, 4)


class FacebookScore(BaseModel):
    """Score for a single Facebook page."""
    follower_component: float
    engagement_component: float

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> float:
        return round(0.50 * self.follower_component + 0.50 * self.engagement_component, 4)


class TikTokScore(BaseModel):
    """Score for a single TikTok profile."""
    follower_component: float
    views_component: float   # TikTok is more views-driven than engagement

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> float:
        return round(0.40 * self.follower_component + 0.60 * self.views_component, 4)


class SocialScore(BaseModel):
    """
    Combined social score across all platforms.

    Weights: Instagram 0.40 · Facebook 0.35 · TikTok 0.25
    Missing platforms redistribute weight proportionally.
    """
    instagram: InstagramScore | None = None
    facebook: FacebookScore | None = None
    tiktok: TikTokScore | None = None

    _WEIGHTS: dict[str, float] = {"instagram": 0.40, "facebook": 0.35, "tiktok": 0.25}

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> float:
        present: dict[str, float] = {}
        if self.instagram:
            present["instagram"] = self.instagram.total
        if self.facebook:
            present["facebook"] = self.facebook.total
        if self.tiktok:
            present["tiktok"] = self.tiktok.total
        if not present:
            return 0.0
        weight_sum = sum(self._WEIGHTS[k] for k in present)
        return round(sum(self._WEIGHTS[k] * v / weight_sum for k, v in present.items()), 4)

    @property
    def platforms_found(self) -> list[str]:
        found = []
        if self.instagram:
            found.append("instagram")
        if self.facebook:
            found.append("facebook")
        if self.tiktok:
            found.append("tiktok")
        return found


class ActivityScore(BaseModel):
    """Combined posting activity score across all platforms."""

    instagram_posts_component: float = 0.0   # posts last 30d
    instagram_reels_component: float = 0.0
    facebook_posts_component: float = 0.0
    tiktok_videos_component: float = 0.0

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> float:
        # Average of all non-zero components, weighted by platform
        ig = 0.35 * (0.5 * self.instagram_posts_component + 0.5 * self.instagram_reels_component)
        fb = 0.35 * self.facebook_posts_component
        tt = 0.30 * self.tiktok_videos_component
        return round(ig + fb + tt, 4)


def _grade(score: float) -> str:
    if score >= 0.80:
        return "A"
    if score >= 0.65:
        return "B"
    if score >= 0.50:
        return "C"
    if score >= 0.35:
        return "D"
    return "F"


class TotalScore(BaseModel):
    """Full digital presence score for a business."""

    place_id: str
    business_name: str
    local_score: LocalScore | None = None
    social_score: SocialScore | None = None
    activity_score: ActivityScore | None = None
    total: float = 0.0
    grade: str = "F"
    computed_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: object) -> None:
        if self.computed_at is None:
            object.__setattr__(self, "computed_at", datetime.now(UTC))
        if self.grade == "F" and self.total > 0:
            object.__setattr__(self, "grade", _grade(self.total))
