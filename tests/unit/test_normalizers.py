"""Unit tests for scoring normalizers — the mathematical core."""

import math
import pytest

from local_scorer.scorers.normalizers import (
    normalize_rating,
    normalize_review_count,
    normalize_category_match,
    normalize_website,
    normalize_profile_completeness,
    normalize_followers,
    normalize_engagement_rate,
    normalize_posts_frequency,
    normalize_reels,
)


class TestNormalizeRating:
    def test_perfect_rating(self):
        assert normalize_rating(5.0) == 1.0

    def test_minimum_rating(self):
        assert normalize_rating(1.0) == 0.0

    def test_midpoint(self):
        assert normalize_rating(3.0) == pytest.approx(0.5)

    def test_none_returns_zero(self):
        assert normalize_rating(None) == 0.0

    def test_clamps_above_max(self):
        assert normalize_rating(6.0) == 1.0

    def test_clamps_below_min(self):
        assert normalize_rating(0.5) == 0.0


class TestNormalizeReviewCount:
    def test_zero_reviews(self):
        assert normalize_review_count(0) == 0.0

    def test_none_reviews(self):
        assert normalize_review_count(None) == 0.0

    def test_at_cap(self):
        assert normalize_review_count(500, cap=500) == 1.0

    def test_above_cap_clamped(self):
        assert normalize_review_count(1000, cap=500) == 1.0

    def test_log_scale_midpoint(self):
        # At sqrt(cap+1) - 1 reviews we should be close to 0.5
        cap = 500
        mid = int(math.sqrt(cap + 1)) - 1
        val = normalize_review_count(mid, cap=cap)
        assert 0.4 < val < 0.6

    def test_single_review(self):
        assert 0.0 < normalize_review_count(1, cap=500) < 0.2


class TestNormalizeCategoryMatch:
    def test_primary_match(self):
        assert normalize_category_match("italian", "Italian Restaurant", []) == 1.0

    def test_secondary_match(self):
        assert normalize_category_match("pizza", "Restaurant", ["pizza_restaurant"]) == 0.5

    def test_no_match(self):
        assert normalize_category_match("italian", "Auto Repair", ["mechanic"]) == 0.0

    def test_empty_query(self):
        assert normalize_category_match("", "Italian Restaurant", []) == 0.0

    def test_case_insensitive(self):
        assert normalize_category_match("ITALIAN", "Italian Restaurant", []) == 1.0


class TestNormalizeWebsite:
    def test_with_website(self):
        assert normalize_website("https://example.com") == 1.0

    def test_without_website(self):
        assert normalize_website(None) == 0.0

    def test_empty_string(self):
        assert normalize_website("") == 0.0


class TestNormalizeProfileCompleteness:
    def test_fully_complete(self):
        score = normalize_profile_completeness(
            phone="+34 123 456 789",
            address="Calle Mayor 1",
            opening_hours_present=True,
            photos_count=5,
            website="https://example.com",
            rating=4.5,
        )
        assert score == 1.0

    def test_all_missing(self):
        score = normalize_profile_completeness(
            phone=None,
            address=None,
            opening_hours_present=False,
            photos_count=0,
            website=None,
            rating=None,
        )
        assert score == 0.0

    def test_partial(self):
        score = normalize_profile_completeness(
            phone="+34 123 456 789",
            address="Calle Mayor 1",
            opening_hours_present=False,
            photos_count=0,
            website=None,
            rating=None,
        )
        assert score == pytest.approx(2 / 6)


class TestNormalizeFollowers:
    def test_zero(self):
        assert normalize_followers(0) == 0.0

    def test_at_cap(self):
        assert normalize_followers(100_000, cap=100_000) == 1.0

    def test_above_cap(self):
        assert normalize_followers(200_000, cap=100_000) == 1.0

    def test_log_scale(self):
        # 1000 followers with 100k cap should be noticeably above 0
        val = normalize_followers(1000, cap=100_000)
        assert 0.1 < val <= 0.65


class TestNormalizeEngagementRate:
    def test_no_followers(self):
        assert normalize_engagement_rate(100.0, 10.0, 0) == 0.0

    def test_high_engagement(self):
        # 10% engagement at cap → 1.0
        assert normalize_engagement_rate(500.0, 500.0, 10_000, cap_rate=0.10) == 1.0

    def test_typical_engagement(self):
        # 2% engagement on 10k followers
        val = normalize_engagement_rate(150.0, 50.0, 10_000, cap_rate=0.10)
        assert val == pytest.approx(0.20)


class TestNormalizeActivity:
    def test_posts_at_cap(self):
        assert normalize_posts_frequency(30, cap=30) == 1.0

    def test_posts_above_cap(self):
        assert normalize_posts_frequency(50, cap=30) == 1.0

    def test_no_posts(self):
        assert normalize_posts_frequency(0) == 0.0

    def test_reels_at_cap(self):
        assert normalize_reels(10, cap=10) == 1.0
