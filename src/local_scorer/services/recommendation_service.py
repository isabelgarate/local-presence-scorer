from __future__ import annotations
"""Generates actionable improvement recommendations from a scored business."""

from ..models.scores import TotalScore
from ..models.recommendations import (
    Recommendation,
    RecommendationArea,
    Priority,
    RecommendationSet,
)


_THRESHOLDS = {
    "rating": 0.60,
    "reviews": 0.40,
    "completeness": 0.67,
    "website": 0.5,
    "instagram": None,  # special: handle absence
    "engagement": 0.40,
    "activity": 0.30,
}


class RecommendationService:
    def generate(self, score: TotalScore) -> RecommendationSet:
        recs: list[Recommendation] = []

        if score.local_score:
            ls = score.local_score

            if ls.rating_component < _THRESHOLDS["rating"]:
                recs.append(Recommendation(
                    area=RecommendationArea.RATING,
                    priority=Priority.HIGH,
                    title="Improve your Google rating",
                    description=(
                        "Your current rating is below 4.0. Actively request reviews from satisfied "
                        "customers after each interaction. Respond professionally to negative reviews."
                    ),
                    impact_estimate="+up to 20 pts on local score",
                ))

            if ls.review_count_component < _THRESHOLDS["reviews"]:
                recs.append(Recommendation(
                    area=RecommendationArea.REVIEWS,
                    priority=Priority.HIGH,
                    title="Grow your review count",
                    description=(
                        "Businesses with more reviews rank higher and convert better. "
                        "Share your Google Maps link with customers via WhatsApp or email."
                    ),
                    impact_estimate="+up to 15 pts on local score",
                ))

            if ls.profile_completeness_component < _THRESHOLDS["completeness"]:
                recs.append(Recommendation(
                    area=RecommendationArea.PROFILE_COMPLETENESS,
                    priority=Priority.MEDIUM,
                    title="Complete your Google Business Profile",
                    description=(
                        "Missing info: phone, opening hours, photos, or address. "
                        "A complete profile increases trust and improves local ranking."
                    ),
                    impact_estimate="+up to 8 pts on local score",
                ))

            if ls.website_component == 0.0:
                recs.append(Recommendation(
                    area=RecommendationArea.WEBSITE,
                    priority=Priority.MEDIUM,
                    title="Add a website to your Google profile",
                    description=(
                        "Businesses with a website are perceived as more credible. "
                        "Even a simple one-page site makes a difference."
                    ),
                    impact_estimate="+5 pts on local score",
                ))

        # Instagram / social
        if score.social_score is None:
            recs.append(Recommendation(
                area=RecommendationArea.INSTAGRAM,
                priority=Priority.MEDIUM,
                title="Create or link your Instagram account",
                description=(
                    "No Instagram profile was found for this business. "
                    "Social presence directly boosts visibility and customer trust."
                ),
                impact_estimate="+up to 35 pts on total score",
            ))
        else:
            ss = score.social_score
            if ss.follower_component < 0.20:
                recs.append(Recommendation(
                    area=RecommendationArea.INSTAGRAM,
                    priority=Priority.MEDIUM,
                    title="Grow your Instagram audience",
                    description=(
                        "Your follower count is relatively low. "
                        "Post consistently, use local hashtags, and tag your location."
                    ),
                    impact_estimate="+up to 10 pts on social score",
                ))
            if ss.engagement_rate_component < _THRESHOLDS["engagement"]:
                recs.append(Recommendation(
                    area=RecommendationArea.SOCIAL_ENGAGEMENT,
                    priority=Priority.LOW,
                    title="Boost engagement on Instagram",
                    description=(
                        "Your engagement rate (likes + comments / followers) is below average. "
                        "Ask questions in captions, use Stories polls, and reply to comments quickly."
                    ),
                    impact_estimate="+up to 8 pts on social score",
                ))

        if score.activity_score and score.activity_score.posts_frequency_component < _THRESHOLDS["activity"]:
            recs.append(Recommendation(
                area=RecommendationArea.CONTENT_ACTIVITY,
                priority=Priority.LOW,
                title="Post more frequently",
                description=(
                    "You posted fewer than 10 times in the last 30 days. "
                    "Aim for 3–5 posts per week to stay visible in feeds and local searches."
                ),
                impact_estimate="+up to 6 pts on activity score",
            ))

        # Sort: high → medium → low
        priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
        recs.sort(key=lambda r: priority_order[r.priority])

        return RecommendationSet(
            place_id=score.place_id,
            business_name=score.business_name,
            recommendations=recs,
        )
