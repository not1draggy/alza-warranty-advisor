"""Tests for the probability and cost mathematics."""

import math

import pytest

from app.agents.risk import (
    Economics,
    combined_failure_probability,
    compute_economics,
    compute_risk_score,
    decide_verdict,
    risk_band,
    risk_drivers,
    window_probability,
)
from app.agents.types import CostEvidence, ExtractedFailureMode
from app.schemas.common import EvidenceLevel, RiskBand, ValueOrigin, Verdict


def mode(
    slug: str,
    *,
    probability: float,
    typical: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> ExtractedFailureMode:
    return ExtractedFailureMode(
        slug=slug,
        name=slug.replace("-", " ").title(),
        annual_probability=probability,
        probability_origin=ValueOrigin.SOURCED,
        cost=CostEvidence(
            currency="EUR",
            minimum=minimum if minimum is not None else typical * 0.7,
            typical=typical,
            maximum=maximum if maximum is not None else typical * 1.5,
            origin=ValueOrigin.SOURCED,
        ),
        confidence=0.8,
        source_indices=[0],
    )


class TestWindowProbability:
    def test_single_year_equals_annual_rate(self):
        assert window_probability(0.05, 1) == pytest.approx(0.05)

    def test_compounds_over_multiple_years(self):
        # 1 - 0.95^3
        assert window_probability(0.05, 3) == pytest.approx(0.142625, abs=1e-6)

    def test_zero_years_is_zero(self):
        assert window_probability(0.5, 0) == 0.0

    def test_certain_failure_stays_bounded(self):
        assert window_probability(1.0, 5) == 1.0

    @pytest.mark.parametrize("bad", [-0.5, 1.5])
    def test_out_of_range_input_is_clamped(self, bad: float):
        value = window_probability(bad, 2)
        assert 0.0 <= value <= 1.0


class TestCombinedProbability:
    def test_independent_modes_combine(self):
        # 1 - (0.9 * 0.8) = 0.28
        assert combined_failure_probability([0.1, 0.2]) == pytest.approx(0.28)

    def test_no_modes_means_no_failure(self):
        assert combined_failure_probability([]) == 0.0

    def test_never_exceeds_one(self):
        assert combined_failure_probability([0.9, 0.9, 0.9]) <= 1.0


class TestEconomics:
    def test_expected_cost_is_probability_weighted(self):
        economics = compute_economics(
            [mode("a", probability=0.10, typical=200.0)],
            years=1,
            warranty_price=50.0,
        )
        assert economics.expected_repair_cost == pytest.approx(20.0)
        assert economics.failure_probability == pytest.approx(0.10)

    def test_average_cost_is_conditional_on_a_failure(self):
        economics = compute_economics(
            [mode("a", probability=0.10, typical=200.0)],
            years=1,
            warranty_price=50.0,
        )
        # Expected 20 EUR spread over a 10% chance -> 200 EUR when it happens.
        assert economics.average_repair_cost == pytest.approx(200.0)

    def test_worst_case_is_the_most_expensive_single_repair(self):
        economics = compute_economics(
            [
                mode("a", probability=0.10, typical=200.0, maximum=350.0),
                mode("b", probability=0.02, typical=90.0, maximum=140.0),
            ],
            years=2,
            warranty_price=60.0,
        )
        assert economics.worst_case_repair_cost == pytest.approx(350.0)

    def test_net_value_and_ratio(self):
        economics = compute_economics(
            [mode("a", probability=0.50, typical=200.0)], years=1, warranty_price=50.0
        )
        assert economics.expected_repair_cost == pytest.approx(100.0)
        assert economics.net_value == pytest.approx(50.0)
        assert economics.value_ratio == pytest.approx(2.0)

    def test_free_warranty_does_not_divide_by_zero(self):
        economics = compute_economics(
            [mode("a", probability=0.1, typical=200.0)], years=1, warranty_price=0.0
        )
        assert economics.value_ratio == 0.0
        assert math.isfinite(economics.net_value)

    def test_no_failure_modes_yields_zeroes(self):
        economics = compute_economics([], years=3, warranty_price=65.7)
        assert economics.expected_repair_cost == 0.0
        assert economics.average_repair_cost == 0.0
        assert economics.failure_probability == 0.0
        assert economics.break_even_probability is None

    def test_break_even_probability(self):
        economics = compute_economics(
            [mode("a", probability=0.10, typical=200.0)], years=1, warranty_price=50.0
        )
        # 50 EUR extension against a 200 EUR repair breaks even at a 25% chance.
        assert economics.break_even_probability == pytest.approx(0.25)

    def test_timeline_is_monotonic(self):
        economics = compute_economics(
            [mode("a", probability=0.08, typical=250.0)], years=3, warranty_price=70.0
        )
        assert [point.year for point in economics.timeline] == [1, 2, 3]
        probabilities = [point.cumulative_failure_probability for point in economics.timeline]
        costs = [point.cumulative_expected_cost for point in economics.timeline]
        assert probabilities == sorted(probabilities)
        assert costs == sorted(costs)
        assert economics.timeline[-1].cumulative_expected_cost == pytest.approx(
            economics.expected_repair_cost, abs=0.01
        )


class TestRiskScore:
    def test_score_within_bounds(self):
        economics = compute_economics(
            [mode("a", probability=0.30, typical=900.0)], years=5, warranty_price=100.0
        )
        score = compute_risk_score(economics)
        assert 0.0 <= score <= 100.0

    def test_higher_probability_raises_the_score(self):
        low = compute_risk_score(
            compute_economics(
                [mode("a", probability=0.01, typical=200.0)], years=2, warranty_price=50.0
            )
        )
        high = compute_risk_score(
            compute_economics(
                [mode("a", probability=0.20, typical=200.0)], years=2, warranty_price=50.0
            )
        )
        assert high > low

    def test_expensive_product_lowers_relative_risk(self):
        economics = compute_economics(
            [mode("a", probability=0.10, typical=300.0)], years=3, warranty_price=80.0
        )
        cheap_reference = compute_risk_score(economics, product_price=400.0)
        expensive_reference = compute_risk_score(economics, product_price=4000.0)
        assert expensive_reference < cheap_reference

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0.0, RiskBand.LOW),
            (24.9, RiskBand.LOW),
            (25.0, RiskBand.MODERATE),
            (49.9, RiskBand.MODERATE),
            (50.0, RiskBand.HIGH),
            (74.9, RiskBand.HIGH),
            (75.0, RiskBand.SEVERE),
            (100.0, RiskBand.SEVERE),
        ],
    )
    def test_bands(self, score: float, expected: RiskBand):
        assert risk_band(score) is expected

    def test_drivers_are_ranked_by_impact(self):
        modes = [
            mode("cheap-frequent", probability=0.10, typical=50.0),
            mode("costly-rare", probability=0.05, typical=600.0),
        ]
        economics = compute_economics(modes, years=3, warranty_price=80.0)
        drivers = risk_drivers(economics, modes)
        assert "Costly Rare" in drivers[0]


class TestVerdict:
    def _economics(self, expected: float, price: float) -> Economics:
        probability = 0.2
        typical = expected / probability
        return compute_economics(
            [mode("a", probability=probability, typical=typical)],
            years=1,
            warranty_price=price,
        )

    def test_clear_value_is_recommended(self):
        verdict, reasons = decide_verdict(
            self._economics(200.0, 100.0),
            confidence=0.8,
            evidence_level=EvidenceLevel.VERIFIED,
        )
        assert verdict is Verdict.RECOMMENDED
        assert reasons

    def test_marginal_value_is_neutral(self):
        verdict, _ = decide_verdict(
            self._economics(100.0, 100.0),
            confidence=0.8,
            evidence_level=EvidenceLevel.VERIFIED,
        )
        assert verdict is Verdict.NEUTRAL

    def test_poor_value_is_not_recommended(self):
        verdict, _ = decide_verdict(
            self._economics(40.0, 100.0),
            confidence=0.8,
            evidence_level=EvidenceLevel.VERIFIED,
        )
        assert verdict is Verdict.NOT_RECOMMENDED

    def test_no_evidence_never_produces_a_recommendation(self):
        verdict, reasons = decide_verdict(
            self._economics(500.0, 10.0), confidence=0.0, evidence_level=EvidenceLevel.NONE
        )
        assert verdict is Verdict.INSUFFICIENT_EVIDENCE
        assert reasons

    def test_low_confidence_softens_a_recommendation(self):
        verdict, reasons = decide_verdict(
            self._economics(400.0, 100.0),
            confidence=0.2,
            evidence_level=EvidenceLevel.PARTIAL,
        )
        assert verdict is Verdict.NEUTRAL
        assert any("thin" in reason for reason in reasons)

    def test_free_extension_is_always_recommended(self):
        verdict, _ = decide_verdict(
            self._economics(10.0, 0.0), confidence=0.9, evidence_level=EvidenceLevel.VERIFIED
        )
        assert verdict is Verdict.RECOMMENDED

    def test_modelled_evidence_is_disclosed(self):
        _, reasons = decide_verdict(
            self._economics(200.0, 100.0),
            confidence=0.6,
            evidence_level=EvidenceLevel.MODELLED,
        )
        assert any("category averages" in reason for reason in reasons)
