from __future__ import annotations
from datetime import datetime, timezone

UTC = timezone.utc
from pydantic import BaseModel, computed_field


class LocalScore(BaseModel):
    """Score derived from Google Business Profile data."""

    rating_component: float        # 0–1, weight 0.35
    review_count_component: float  # 0–1, weight 0.30
    category_match_component: float  # 0–1, weight 0.15
    website_component: float       # 0 or 1, weight 0.10
    profile_completeness_component: float  # 0–1, weight 0.10

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


class SocialScore(BaseModel):
    """Score derived from Instagram profile data."""

    follower_component: float     # 0–1, weight 0.50
    engagement_rate_component: float  # 0–1, weight 0.50

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> float:
        return round(
            0.50 * self.follower_component
            + 0.50 * self.engagement_rate_component,
            4,
        )


class ActivityScore(BaseModel):
    """Score derived from recent posting activity."""

    posts_frequency_component: float   # 0–1, weight 0.60
    reels_component: float             # 0–1, weight 0.40

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> float:
        return round(
            0.60 * self.posts_frequency_component
            + 0.40 * self.reels_component,
            4,
        )


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
