from __future__ import annotations
from ..models.business import InstagramData
from ..models.scores import SocialScore, ActivityScore
from .normalizers import (
    normalize_followers,
    normalize_engagement_rate,
    normalize_posts_frequency,
    normalize_reels,
)
from ..config import settings


class SocialScorer:
    """Computes SocialScore and ActivityScore from InstagramData."""

    def score_social(self, data: InstagramData) -> SocialScore:
        return SocialScore(
            follower_component=normalize_followers(
                data.followers, cap=settings.follower_cap
            ),
            engagement_rate_component=normalize_engagement_rate(
                avg_likes=data.avg_likes_last_n,
                avg_comments=data.avg_comments_last_n,
                followers=data.followers,
            ),
        )

    def score_activity(self, data: InstagramData) -> ActivityScore:
        return ActivityScore(
            posts_frequency_component=normalize_posts_frequency(data.posts_last_30_days),
            reels_component=normalize_reels(data.reels_last_30_days),
        )
