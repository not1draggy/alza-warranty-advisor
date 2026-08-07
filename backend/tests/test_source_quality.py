"""Tests for source classification and quality scoring."""

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.common import SourceType
from app.services.source_quality import (
    assess_source,
    classify_domain,
    quality_label,
    recency_multiplier,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)


class TestClassifyDomain:
    @pytest.mark.parametrize(
        ("domain", "expected"),
        [
            ("samsung.com", SourceType.MANUFACTURER),
            ("support.samsung.com", SourceType.MANUFACTURER),
            ("ifixit.com", SourceType.REPAIR_PROFESSIONAL),
            ("partselect.com", SourceType.PARTS_CATALOG),
            ("consumerreports.org", SourceType.RELIABILITY_REPORT),
            ("reddit.com", SourceType.COMMUNITY),
            ("alza.cz", SourceType.RETAILER),
            ("some-unknown-blog.example", SourceType.UNKNOWN),
        ],
    )
    def test_known_domains(self, domain: str, expected: SourceType):
        assert classify_domain(domain) is expected

    def test_path_hints_classify_unknown_domains(self):
        assert (
            classify_domain("electro-repairs.de", "https://electro-repairs.de/service-manual/tv")
            is SourceType.REPAIR_PROFESSIONAL
        )

    def test_forum_paths_are_community(self):
        assert (
            classify_domain("hifi.example", "https://hifi.example/forum/tv-repair")
            is SourceType.COMMUNITY
        )


class TestRecency:
    def test_recent_content_is_not_penalised(self):
        assert recency_multiplier(NOW - timedelta(days=200), now=NOW) == 1.0

    def test_old_content_is_discounted(self):
        assert recency_multiplier(NOW - timedelta(days=365 * 9), now=NOW) < 0.7

    def test_unknown_date_is_mildly_discounted(self):
        assert 0.8 <= recency_multiplier(None, now=NOW) < 1.0

    def test_naive_datetimes_are_handled(self):
        naive = datetime(2025, 1, 1)  # deliberately naive
        assert recency_multiplier(naive, now=NOW) > 0


class TestAssessSource:
    def test_manufacturer_source_scores_highest(self):
        assessment = assess_source(
            domain="samsung.com",
            url="https://samsung.com/support/repair-pricing",
            title="Repair pricing",
            snippet="Backlight replacement costs 280 EUR including labour and service.",
            published_at=NOW - timedelta(days=100),
            now=NOW,
        )
        assert assessment.accepted
        assert assessment.source_type is SourceType.MANUFACTURER
        assert assessment.quality_score >= 0.9

    def test_community_source_is_accepted_but_ranked_lower(self):
        manufacturer = assess_source(
            domain="samsung.com",
            url="https://samsung.com/support",
            snippet="Repair price list for televisions with service costs shown in EUR.",
            now=NOW,
        )
        community = assess_source(
            domain="reddit.com",
            url="https://reddit.com/r/tv/comments/x",
            snippet="My set failed after two years, the repair shop quoted a price to fix it.",
            now=NOW,
        )
        assert community.accepted
        assert community.quality_score < manufacturer.quality_score

    def test_blocked_domains_are_rejected(self):
        assessment = assess_source(
            domain="best-coupon-deals.example",
            url="https://best-coupon-deals.example/tv",
            snippet="Cheap prices on televisions with a promo code for every purchase today.",
            now=NOW,
        )
        assert not assessment.accepted
        assert assessment.quality_score == 0.0

    def test_empty_domain_is_rejected(self):
        assert not assess_source(domain="", url="not-a-url", now=NOW).accepted

    def test_thin_snippets_are_penalised(self):
        rich = assess_source(
            domain="ifixit.com",
            url="https://ifixit.com/Guide/1",
            snippet="Backlight strip replacement costs about 280 EUR including labour charges.",
            now=NOW,
        )
        thin = assess_source(
            domain="ifixit.com", url="https://ifixit.com/Guide/2", snippet="TV repair.", now=NOW
        )
        assert thin.quality_score < rich.quality_score

    def test_score_stays_within_bounds(self):
        assessment = assess_source(
            domain="samsung.com",
            url="https://samsung.com/x",
            title="EUR price repair cost service",
            snippet="repair replace fault failure service price cost EUR " * 10,
            published_at=NOW,
            now=NOW,
        )
        assert 0.0 <= assessment.quality_score <= 1.0


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.95, "Excellent"), (0.7, "Good"), (0.5, "Fair"), (0.2, "Weak")],
)
def test_quality_label(score: float, expected: str):
    assert quality_label(score) == expected
