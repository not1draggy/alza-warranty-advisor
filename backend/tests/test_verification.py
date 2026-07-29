"""The composer may only restate figures the pipeline actually computed."""

import pytest

from app.agents.composer import ComposerAgent
from app.agents.confidence import SourceSignal, score_confidence
from app.agents.risk import compute_economics
from app.agents.types import CostEvidence, ExtractedFailureMode, ProductIdentity
from app.agents.verification import extract_claims, verify_narrative
from app.schemas.common import ValueOrigin, Verdict
from app.services.llm.registry import LLMRouter
from tests.fakes import FakeLLM

IDENTITY = ProductIdentity(display_name="Samsung UE75NU8000", confidence=0.9)


def modes() -> list[ExtractedFailureMode]:
    return [
        ExtractedFailureMode(
            slug="backlight",
            name="Backlight failure",
            annual_probability=0.05,
            probability_origin=ValueOrigin.SOURCED,
            cost=CostEvidence(minimum=180, typical=280, maximum=420, origin=ValueOrigin.SOURCED),
            confidence=0.8,
            source_indices=[0],
        )
    ]


def economics():
    return compute_economics(modes(), years=3, warranty_price=66.0, currency="EUR")


def confidence():
    return score_confidence(
        failure_modes=modes(),
        sources=[SourceSignal(domain="samsung.com", quality_score=0.9)],
        identification_confidence=0.9,
    )


class TestExtractClaims:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("costs about 280 EUR", [280.0]),
            ("costs €280", [280.0]),
            ("a 19% chance", [19.0]),
            ("1,280 EUR for the panel", [1280.0]),
            ("between 180 EUR and 420 EUR", [180.0, 420.0]),
        ],
    )
    def test_finds_money_and_percentages(self, text: str, expected: list[float]):
        assert sorted(extract_claims(text)) == sorted(expected)

    def test_ignores_bare_integers(self):
        # "3 years" and "2 sources" are not claims about money or risk.
        assert extract_claims("over 3 years, from 2 sources") == []


class TestVerifyNarrative:
    def test_accepts_figures_that_come_from_the_analysis(self):
        text = (
            "There is roughly a 14% chance of a repair, and the usual fault costs "
            "about 280 EUR against a 66 EUR extension."
        )
        result = verify_narrative(
            text, economics=economics(), failure_modes=modes(), confidence=0.7
        )
        assert result.ok
        assert result.unsupported == []

    def test_rejects_an_invented_price(self):
        text = "The usual repair costs about 950 EUR."
        result = verify_narrative(
            text, economics=economics(), failure_modes=modes(), confidence=0.7
        )
        assert not result.ok
        assert 950.0 in result.unsupported

    def test_rejects_an_invented_probability(self):
        text = "There is a 62% chance this set needs a repair."
        result = verify_narrative(
            text, economics=economics(), failure_modes=modes(), confidence=0.7
        )
        assert not result.ok
        assert 62.0 in result.unsupported

    def test_allows_rounding_slack(self):
        # Expected spend is 39.94; the wording rounds it to 40.
        text = "Expected repair spending is about 40 EUR."
        result = verify_narrative(
            text, economics=economics(), failure_modes=modes(), confidence=0.7
        )
        assert result.ok

    def test_cost_range_endpoints_are_permitted(self):
        text = "Repairs run from 180 EUR to 420 EUR."
        result = verify_narrative(
            text, economics=economics(), failure_modes=modes(), confidence=0.7
        )
        assert result.ok


class TestComposerGuard:
    async def _compose(self, narrative: dict):
        agent = ComposerAgent(LLMRouter([FakeLLM(overrides={"narrative": narrative})]))
        return await agent.compose(
            identity=IDENTITY,
            verdict=Verdict.NOT_RECOMMENDED,
            reasons=["Expected spending is below the price of the extension."],
            economics=economics(),
            confidence=confidence(),
            failure_modes=modes(),
            years=3,
        )

    async def test_headline_comes_from_the_verdict_not_the_model(self):
        result = await self._compose(
            {"summary": "The usual fault costs about 280 EUR.", "reasons": []}
        )
        # The model cannot contradict the recommendation, because it never writes
        # the headline.
        assert result.headline == "Probably not worth it — repairs are usually cheaper"

    async def test_unsupported_figures_fall_back_to_the_deterministic_summary(self):
        result = await self._compose(
            {
                "summary": "Repairs typically cost 1,900 EUR, far above the extension.",
                "reasons": [],
            }
        )
        assert "1,900" not in result.summary
        assert "1900" not in result.summary
        # The deterministic narrative states the computed probability instead.
        assert "%" in result.summary

    async def test_supported_figures_are_kept(self):
        result = await self._compose(
            {
                "summary": "The most likely fault, the backlight, costs about 280 EUR.",
                "reasons": ["Expected spending stays under the 66 EUR extension."],
            }
        )
        assert "280 EUR" in result.summary
        assert result.reasons

    async def test_empty_summary_falls_back(self):
        result = await self._compose({"summary": "   ", "reasons": []})
        assert result.summary.strip()
