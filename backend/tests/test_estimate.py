"""The estimate that runs when nothing could be retrieved.

Its whole reason to exist is that it may guess. The tests here are about the
conditions under which it is allowed to: never claiming a source, never
outrunning the clamps, and never speaking at all when it has nothing to say.
"""

from app.agents.estimate import (
    MAX_ESTIMATED_CONFIDENCE,
    MAX_ESTIMATED_MODES,
    EstimationAgent,
)
from app.agents.extraction import MAX_ANNUAL_PROBABILITY, MAX_TYPICAL_COST
from app.agents.types import ProductIdentity
from app.core.errors import ProviderUnavailable
from app.schemas.common import ValueOrigin
from app.services.llm.base import LLMProvider
from app.services.llm.registry import LLMRouter
from tests.fakes import FakeLLM

IDENTITY = ProductIdentity(display_name="Samsung QE55QN70F", category="Televízor", confidence=0.6)


def entry(**overrides) -> dict:
    base = {
        "slug": "panel-failure",
        "name": "Porucha panela",
        "component": "Panel",
        "description": "Pruhy na obraze.",
        "annual_probability": 0.03,
        "cost": {"currency": "EUR", "minimum": 250.0, "typical": 400.0, "maximum": 650.0},
        "repair_difficulty": "hard",
        "typical_repair_days": 7,
        "confidence": 0.4,
    }
    base.update(overrides)
    return base


def agent(payload: dict) -> EstimationAgent:
    return EstimationAgent(LLMRouter([FakeLLM(overrides={"estimation": payload})]))


async def estimate(payload: dict):
    return await agent(payload).estimate(identity=IDENTITY, currency="EUR")


class TestProvenance:
    async def test_nothing_is_ever_marked_as_sourced(self):
        result = await estimate({"product_class": "televízor", "failure_modes": [entry()]})
        mode = result.failure_modes[0]
        assert mode.cost.origin is ValueOrigin.ESTIMATED
        assert mode.probability_origin is ValueOrigin.ESTIMATED
        assert mode.source_indices == []

    async def test_a_model_claiming_a_source_is_overridden(self):
        # The schema does not offer an origin field, but a model that invents one
        # must not be able to launder an estimate into a sourced value.
        result = await estimate(
            {
                "product_class": "televízor",
                "failure_modes": [entry(probability_origin="sourced", source_indices=[0])],
            }
        )
        mode = result.failure_modes[0]
        assert mode.cost.origin is ValueOrigin.ESTIMATED
        assert mode.probability_origin is ValueOrigin.ESTIMATED
        assert mode.source_indices == []

    async def test_the_customer_is_warned_and_the_basis_is_stated(self):
        result = await estimate(
            {"product_class": "55-palcový QLED televízor", "failure_modes": [entry()]}
        )
        assert any("nevychádza zo zdrojov" in warning for warning in result.warnings)
        assert any("55-palcový QLED televízor" in item for item in result.assumptions)


class TestClamping:
    async def test_absurd_probability_is_capped(self):
        result = await estimate(
            {"product_class": "x", "failure_modes": [entry(annual_probability=0.95)]}
        )
        assert result.failure_modes[0].annual_probability == MAX_ANNUAL_PROBABILITY

    async def test_absurd_cost_is_capped(self):
        result = await estimate(
            {
                "product_class": "x",
                "failure_modes": [
                    entry(cost={"currency": "EUR", "minimum": 1, "typical": 9e9, "maximum": 9e9})
                ],
            }
        )
        assert result.failure_modes[0].cost.typical == MAX_TYPICAL_COST

    async def test_confidence_cannot_exceed_the_estimate_ceiling(self):
        result = await estimate({"product_class": "x", "failure_modes": [entry(confidence=0.99)]})
        assert result.failure_modes[0].confidence <= MAX_ESTIMATED_CONFIDENCE

    async def test_inverted_cost_range_is_reordered(self):
        result = await estimate(
            {
                "product_class": "x",
                "failure_modes": [
                    entry(cost={"currency": "EUR", "minimum": 800, "typical": 400, "maximum": 200})
                ],
            }
        )
        cost = result.failure_modes[0].cost
        assert cost.minimum <= cost.typical <= cost.maximum

    async def test_the_list_is_bounded(self):
        modes = [entry(slug=f"m{i}", name=f"Porucha {i}") for i in range(9)]
        result = await estimate({"product_class": "x", "failure_modes": modes})
        assert len(result.failure_modes) == MAX_ESTIMATED_MODES

    async def test_ranked_by_expected_impact(self):
        modes = [
            entry(
                slug="small",
                name="Malá",
                annual_probability=0.01,
                cost={"currency": "EUR", "minimum": 10, "typical": 50, "maximum": 90},
            ),
            entry(
                slug="big",
                name="Veľká",
                annual_probability=0.05,
                cost={"currency": "EUR", "minimum": 200, "typical": 500, "maximum": 900},
            ),
        ]
        result = await estimate({"product_class": "x", "failure_modes": modes})
        assert result.failure_modes[0].slug == "big"


class TestRefusal:
    async def test_zero_cost_entries_are_dropped(self):
        result = await estimate(
            {
                "product_class": "x",
                "failure_modes": [
                    entry(cost={"currency": "EUR", "minimum": 0, "typical": 0, "maximum": 0})
                ],
            }
        )
        assert result.failure_modes == []
        assert result.evidence_sufficient is False

    async def test_an_empty_answer_stays_empty(self):
        result = await estimate({"product_class": "x", "failure_modes": []})
        assert result.failure_modes == []
        assert result.evidence_sufficient is False
        # No warning either: there is nothing to warn about.
        assert result.warnings == []

    async def test_an_unavailable_model_is_not_an_error(self):
        class Dead(LLMProvider):
            name = "dead"

            @property
            def configured(self) -> bool:
                return True

            async def complete_json(self, **kwargs):
                raise ProviderUnavailable("no model")

            async def complete_text(self, **kwargs) -> str:
                raise ProviderUnavailable("no model")

        result = await EstimationAgent(LLMRouter([Dead()])).estimate(
            identity=IDENTITY, currency="EUR"
        )
        assert result.failure_modes == []
        assert result.evidence_sufficient is False
