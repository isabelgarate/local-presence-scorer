from __future__ import annotations
from ..models.business import BusinessProfile
from ..models.scores import LocalScore
from .normalizers import (
    normalize_rating,
    normalize_review_count,
    normalize_category_match,
    normalize_website,
    normalize_profile_completeness,
)
from ..config import settings


class LocalScorer:
    """Computes LocalScore from a BusinessProfile."""

    def score(self, profile: BusinessProfile, query: str = "") -> LocalScore:
        return LocalScore(
            rating_component=normalize_rating(profile.rating),
            review_count_component=normalize_review_count(
                profile.review_count, cap=settings.review_cap
            ),
            category_match_component=normalize_category_match(
                query, profile.primary_category, profile.all_categories
            ),
            website_component=normalize_website(profile.website),
            profile_completeness_component=normalize_profile_completeness(
                phone=profile.phone,
                address=profile.address,
                opening_hours_present=profile.opening_hours_present,
                photos_count=profile.photos_count,
                website=profile.website,
                rating=profile.rating,
            ),
        )
