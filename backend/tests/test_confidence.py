"""Tests for confidence scoring and evidence classification."""

import pytest

from app.agents.confidence import (
    ConfidenceReport,
    SourceSignal,
    confidence_band,
    determine_evidence_level,
    score_confidence,
)
from app.agents.types import CostEvidence, ExtractedFailureMode
from app.schemas.common import ConfidenceBand, EvidenceLevel, ValueOrigin


def make_mode(
    *, cost_origin: ValueOrigin, probability_origin: ValueOrigin, slug: str = "a"
) -> ExtractedFailureMode:
    return ExtractedFailureMode(
        slug=slug,
        name=slug,
        annual_probability=0.05,
        probability_origin=probability_origin,
        cost=CostEvidence(minimum=100, typical=200, maximum=300, origin=cost_origin),
        confidence=0.7,
    )


def signals(*pairs: tuple[str, float]) -> list[SourceSignal]:
    return [SourceSignal(domain=domain, quality_score=score) for domain, score in pairs]


class TestEvidenceLevel:
    def test_no_sources_means_no_evidence(self):
        modes = [make_mode(cost_origin=ValueOrigin.SOURCED, probability_origin=ValueOrigin.SOURCED)]
        assert determine_evidence_level(modes, []) is EvidenceLevel.NONE

    def test_no_failure_modes_means_no_evidence(self):
        assert determine_evidence_level([], signals(("samsung.com", 0.9))) is EvidenceLevel.NONE

    def test_multiple_sourced_facts_are_verified(self):
        modes = [
            make_mode(
                cost_origin=ValueOrigin.SOURCED,
                probability_origin=ValueOrigin.SOURCED,
                slug="a",
            ),
            make_mode(
                cost_origin=ValueOrigin.SOURCED,
                probability_origin=ValueOrigin.ESTIMATED,
                slug="b",
            ),
        ]
        level = determine_evidence_level(modes, signals(("samsung.com", 0.9), ("ifixit.com", 0.8)))
        assert level is EvidenceLevel.VERIFIED

    def test_thin_sourcing_is_partial(self):
        modes = [
            make_mode(cost_origin=ValueOrigin.SOURCED, probability_origin=ValueOrigin.ESTIMATED)
        ]
        assert (
            determine_evidence_level(modes, signals(("reddit.com", 0.4))) is EvidenceLevel.PARTIAL
        )

    def test_all_assumptions_from_weak_sources_is_modelled(self):
        modes = [
            make_mode(cost_origin=ValueOrigin.ESTIMATED, probability_origin=ValueOrigin.ESTIMATED)
        ]
        assert (
            determine_evidence_level(modes, signals(("reddit.com", 0.4))) is EvidenceLevel.MODELLED
        )


class TestScoreConfidence:
    def test_no_evidence_scores_zero_and_says_why(self):
        report = score_confidence(failure_modes=[], sources=[], identification_confidence=0.9)
        assert report.score == 0.0
        assert report.evidence_level is EvidenceLevel.NONE
        assert report.uncertainties

    def test_strong_evidence_scores_high(self):
        modes = [
            make_mode(
                cost_origin=ValueOrigin.SOURCED, probability_origin=ValueOrigin.SOURCED, slug=str(i)
            )
            for i in range(3)
        ]
        report = score_confidence(
            failure_modes=modes,
            sources=signals(
                ("samsung.com", 0.95),
                ("ifixit.com", 0.85),
                ("consumerreports.org", 0.9),
                ("partselect.com", 0.8),
                ("rtings.com", 0.85),
                ("which.co.uk", 0.9),
            ),
            identification_confidence=0.95,
        )
        assert report.score >= 0.85
        assert report.band is ConfidenceBand.HIGH
        assert report.independent_domains == 6
        assert report.drivers

    def test_single_weak_source_scores_low(self):
        modes = [
            make_mode(cost_origin=ValueOrigin.ESTIMATED, probability_origin=ValueOrigin.ESTIMATED)
        ]
        report = score_confidence(
            failure_modes=modes,
            sources=signals(("reddit.com", 0.35)),
            identification_confidence=0.3,
        )
        assert report.score < 0.45
        assert report.band is ConfidenceBand.LOW
        assert any("single website" in item for item in report.uncertainties)

    def test_score_is_bounded(self):
        report = score_confidence(
            failure_modes=[
                make_mode(cost_origin=ValueOrigin.SOURCED, probability_origin=ValueOrigin.SOURCED)
            ],
            sources=signals(*[(f"domain{i}.com", 1.0) for i in range(20)]),
            identification_confidence=1.0,
        )
        assert 0.0 <= report.score <= 1.0

    def test_more_independent_domains_raise_confidence(self):
        modes = [make_mode(cost_origin=ValueOrigin.SOURCED, probability_origin=ValueOrigin.SOURCED)]
        narrow = score_confidence(
            failure_modes=modes,
            sources=signals(("samsung.com", 0.9), ("samsung.com", 0.9)),
            identification_confidence=0.8,
        )
        broad = score_confidence(
            failure_modes=modes,
            sources=signals(("samsung.com", 0.9), ("ifixit.com", 0.9)),
            identification_confidence=0.8,
        )
        assert broad.score > narrow.score

    def test_report_shape(self):
        report = score_confidence(
            failure_modes=[
                make_mode(cost_origin=ValueOrigin.SOURCED, probability_origin=ValueOrigin.SOURCED)
            ],
            sources=signals(("samsung.com", 0.9)),
            identification_confidence=0.8,
        )
        assert isinstance(report, ConfidenceReport)
        assert report.source_count == 1


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, ConfidenceBand.LOW),
        (0.44, ConfidenceBand.LOW),
        (0.45, ConfidenceBand.MEDIUM),
        (0.69, ConfidenceBand.MEDIUM),
        (0.70, ConfidenceBand.HIGH),
        (1.0, ConfidenceBand.HIGH),
    ],
)
def test_confidence_bands(score: float, expected: ConfidenceBand):
    assert confidence_band(score) is expected
