from __future__ import annotations
from ..models.business import InstagramData, FacebookData, TikTokData, SocialData
from ..models.scores import (
    InstagramScore, FacebookScore, TikTokScore, SocialScore, ActivityScore,
)
from .normalizers import (
    normalize_followers,
    normalize_engagement_rate,
    normalize_posts_frequency,
    normalize_reels,
    normalize_video_views,
)
from ..config import settings


class SocialScorer:
    """Computes SocialScore and ActivityScore from multi-platform SocialData."""

    def score(self, data: SocialData) -> tuple[SocialScore, ActivityScore]:
        """Returns (SocialScore, ActivityScore) from all available platforms."""
        ig_score = self._score_instagram(data.instagram) if data.instagram else None
        fb_score = self._score_facebook(data.facebook) if data.facebook else None
        tt_score = self._score_tiktok(data.tiktok) if data.tiktok else None

        social = SocialScore(instagram=ig_score, facebook=fb_score, tiktok=tt_score)
        activity = self._score_activity(data)
        return social, activity

    def _score_instagram(self, data: InstagramData) -> InstagramScore:
        return InstagramScore(
            follower_component=normalize_followers(data.followers, cap=settings.follower_cap),
            engagement_component=normalize_engagement_rate(
                avg_likes=data.avg_likes_last_n,
                avg_comments=data.avg_comments_last_n,
                followers=data.followers,
            ),
        )

    def _score_facebook(self, data: FacebookData) -> FacebookScore:
        return FacebookScore(
            follower_component=normalize_followers(data.followers, cap=settings.follower_cap),
            engagement_component=normalize_engagement_rate(
                avg_likes=data.avg_likes_last_n,
                avg_comments=data.avg_comments_last_n,
                followers=data.followers,
            ),
        )

    def _score_tiktok(self, data: TikTokData) -> TikTokScore:
        return TikTokScore(
            follower_component=normalize_followers(data.followers, cap=settings.follower_cap),
            views_component=normalize_video_views(data.avg_views_last_n),
        )

    def _score_activity(self, data: SocialData) -> ActivityScore:
        ig = data.instagram
        fb = data.facebook
        tt = data.tiktok
        return ActivityScore(
            instagram_posts_component=normalize_posts_frequency(ig.posts_last_30_days) if ig else 0.0,
            instagram_reels_component=normalize_reels(ig.reels_last_30_days) if ig else 0.0,
            facebook_posts_component=normalize_posts_frequency(fb.posts_last_30_days, cap=20) if fb else 0.0,
            tiktok_videos_component=normalize_posts_frequency(tt.posts_last_30_days, cap=20) if tt else 0.0,
        )
