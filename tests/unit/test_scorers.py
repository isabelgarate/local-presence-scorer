"""Unit tests for scorer classes."""

import pytest

from local_scorer.models.business import BusinessProfile, InstagramData
from local_scorer.scorers.local_scorer import LocalScorer
from local_scorer.scorers.social_scorer import SocialScorer
from local_scorer.scorers.total_scorer import TotalScorer


@pytest.fixture
def full_profile() -> BusinessProfile:
    return BusinessProfile(
        place_id="abc123",
        name="La Trattoria",
        rating=4.7,
        review_count=350,
        primary_category="Italian Restaurant",
        all_categories=["italian_restaurant", "restaurant"],
        website="https://latrattoria.es",
        phone="+34 91 123 45 67",
        address="Calle Gran Vía 1, Madrid",
        opening_hours_present=True,
        photos_count=12,
        business_status="OPERATIONAL",
    )


@pytest.fixture
def minimal_profile() -> BusinessProfile:
    return BusinessProfile(
        place_id="xyz",
        name="Bar Sin Nombre",
        rating=None,
        review_count=None,
    )


@pytest.fixture
def instagram_data() -> InstagramData:
    return InstagramData(
        handle="latrattoria_madrid",
        followers=3500,
        following=200,
        post_count=180,
        avg_likes_last_n=120.0,
        avg_comments_last_n=15.0,
        posts_last_30_days=12,
        reels_last_30_days=4,
        is_business_account=True,
    )


class TestLocalScorer:
    def test_full_profile_high_score(self, full_profile):
        scorer = LocalScorer()
        result = scorer.score(full_profile, query="italian restaurant")
        assert result.total > 0.7
        assert result.rating_component > 0.8
        assert result.website_component == 1.0
        assert result.profile_completeness_component == 1.0

    def test_minimal_profile_low_score(self, minimal_profile):
        scorer = LocalScorer()
        result = scorer.score(minimal_profile)
        assert result.total < 0.2
        assert result.rating_component == 0.0

    def test_total_is_weighted_sum(self, full_profile):
        scorer = LocalScorer()
        ls = scorer.score(full_profile)
        expected = (
            0.35 * ls.rating_component
            + 0.30 * ls.review_count_component
            + 0.15 * ls.category_match_component
            + 0.10 * ls.website_component
            + 0.10 * ls.profile_completeness_component
        )
        assert ls.total == pytest.approx(expected, abs=1e-4)


class TestSocialScorer:
    def test_social_score(self, instagram_data):
        scorer = SocialScorer()
        result = scorer.score_social(instagram_data)
        assert 0.0 < result.total < 1.0
        assert result.follower_component > 0.0

    def test_activity_score(self, instagram_data):
        scorer = SocialScorer()
        result = scorer.score_activity(instagram_data)
        assert result.posts_frequency_component == pytest.approx(12 / 30)
        assert result.reels_component == pytest.approx(4 / 10)

    def test_zero_followers(self):
        scorer = SocialScorer()
        data = InstagramData(handle="test", followers=0)
        result = scorer.score_social(data)
        assert result.total == 0.0


class TestTotalScorer:
    def test_all_present(self, full_profile, instagram_data):
        local_scorer = LocalScorer()
        social_scorer = SocialScorer()
        total_scorer = TotalScorer()

        local = local_scorer.score(full_profile, query="italian")
        social = social_scorer.score_social(instagram_data)
        activity = social_scorer.score_activity(instagram_data)

        result = total_scorer.score("abc123", "La Trattoria", local, social, activity)

        expected = 0.50 * local.total + 0.35 * social.total + 0.15 * activity.total
        assert result.total == pytest.approx(expected, abs=1e-4)
        assert result.grade in ("A", "B", "C", "D", "F")

    def test_local_only_weight_redistribution(self, full_profile):
        scorer = LocalScorer()
        total_scorer = TotalScorer()

        local = scorer.score(full_profile, query="italian")
        result = total_scorer.score("abc123", "Name", local, None, None)

        # With only local, total should equal local.total (weight redistributed to 1.0)
        assert result.total == pytest.approx(local.total, abs=1e-4)

    def test_no_scores_returns_zero(self):
        total_scorer = TotalScorer()
        result = total_scorer.score("id", "Name", None, None, None)
        assert result.total == 0.0
        assert result.grade == "F"

    def test_grade_thresholds(self):
        total_scorer = TotalScorer()
        from local_scorer.models.scores import LocalScore

        def make_local(v: float) -> LocalScore:
            return LocalScore(
                rating_component=v,
                review_count_component=v,
                category_match_component=v,
                website_component=v,
                profile_completeness_component=v,
            )

        assert total_scorer.score("id", "n", make_local(1.0), None, None).grade == "A"
        assert total_scorer.score("id", "n", make_local(0.70), None, None).grade in ("A", "B")
        assert total_scorer.score("id", "n", make_local(0.0), None, None).grade == "F"
