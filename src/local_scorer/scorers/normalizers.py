from __future__ import annotations
"""Normalization functions: raw API values → [0.0, 1.0] components.

All functions are pure — no side effects, easily testable.
"""

import math


def normalize_rating(rating: float | None) -> float:
    """Linear rescale [1.0, 5.0] → [0.0, 1.0]. Missing = 0.0."""
    if rating is None:
        return 0.0
    return max(0.0, min(1.0, (rating - 1.0) / 4.0))


def normalize_review_count(count: int | None, cap: int = 500) -> float:
    """Log-scale normalization. count=cap → 1.0. Missing = 0.0."""
    if count is None or count <= 0:
        return 0.0
    return min(1.0, math.log(1 + count) / math.log(1 + cap))


def normalize_category_match(query: str, primary: str | None, all_categories: list[str]) -> float:
    """
    1.0 if query terms appear in primary category.
    0.5 if in secondary categories.
    0.0 otherwise.
    """
    if not query:
        return 0.0
    terms = {t.lower() for t in query.split()}

    def _match(text: str) -> bool:
        lower = text.lower()
        return any(t in lower for t in terms)

    if primary and _match(primary):
        return 1.0
    if any(_match(cat) for cat in all_categories):
        return 0.5
    return 0.0


def normalize_website(website: str | None) -> float:
    """Binary: 1.0 if website present, 0.0 otherwise."""
    return 1.0 if website else 0.0


def normalize_profile_completeness(
    phone: str | None,
    address: str | None,
    opening_hours_present: bool,
    photos_count: int,
    website: str | None,
    rating: float | None,
) -> float:
    """Fraction of optional fields present (6 total)."""
    fields = [phone, address, website, rating]
    present = sum(1 for f in fields if f is not None)
    present += int(opening_hours_present)
    present += int(photos_count > 0)
    return present / 6.0


def normalize_followers(followers: int, cap: int = 100_000) -> float:
    """Log-scale: cap followers → 1.0."""
    if followers <= 0:
        return 0.0
    return min(1.0, math.log(1 + followers) / math.log(1 + cap))


def normalize_engagement_rate(
    avg_likes: float, avg_comments: float, followers: int, cap_rate: float = 0.10
) -> float:
    """(likes + comments) / followers, capped at cap_rate → 1.0."""
    if followers <= 0:
        return 0.0
    rate = (avg_likes + avg_comments) / followers
    return min(1.0, rate / cap_rate)


def normalize_posts_frequency(posts_last_30_days: int, cap: int = 30) -> float:
    """Linear: cap posts/30d → 1.0."""
    return min(1.0, posts_last_30_days / cap)


def normalize_reels(reels_last_30_days: int, cap: int = 10) -> float:
    """Linear: cap reels/30d → 1.0."""
    return min(1.0, reels_last_30_days / cap)
