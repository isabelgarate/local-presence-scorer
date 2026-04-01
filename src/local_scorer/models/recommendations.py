from enum import Enum
from pydantic import BaseModel


class RecommendationArea(str, Enum):
    RATING = "rating"
    REVIEWS = "reviews"
    PROFILE_COMPLETENESS = "profile_completeness"
    WEBSITE = "website"
    INSTAGRAM = "instagram"
    SOCIAL_ENGAGEMENT = "social_engagement"
    CONTENT_ACTIVITY = "content_activity"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Recommendation(BaseModel):
    area: RecommendationArea
    priority: Priority
    title: str
    description: str
    impact_estimate: str  # e.g. "+15 pts on local score"


class RecommendationSet(BaseModel):
    place_id: str
    business_name: str
    recommendations: list[Recommendation]
