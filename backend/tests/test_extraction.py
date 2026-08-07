"""Guard rails applied to model output before it becomes a customer-facing number."""

from datetime import UTC, datetime

import pytest

from app.agents.extraction import MAX_ANNUAL_PROBABILITY, ExtractionAgent
from app.agents.types import ProductIdentity
from app.schemas.common import SourceType, ValueOrigin
from app.services.llm.registry import LLMRouter
from app.services.rag import RetrievedChunk
from tests.fakes import FakeLLM

IDENTITY = ProductIdentity(display_name="Samsung UE75NU8000", manufacturer="Samsung")


def chunk(index: int = 0) -> RetrievedChunk:
    return RetrievedChunk(
        content=f"Repair evidence {index}: backlight replacement costs 280 EUR.",
        score=0.9,
        source_url=f"https://samsung.com/{index}",
        source_domain="samsung.com",
        source_title="Repair pricing",
        source_type=SourceType.MANUFACTURER,
        quality_score=0.95,
        retrieved_at=datetime.now(UTC),
    )


def extraction_payload(**mode_overrides) -> dict:
    mode = {
        "slug": "backlight-failure",
        "name": "Backlight failure",
        "component": "LED backlight",
        "description": "Screen goes dark.",
        "annual_probability": 0.05,
        "probability_origin": "sourced",
        "cost": {
            "currency": "EUR",
            "minimum": 180.0,
            "typical": 280.0,
            "maximum": 420.0,
            "origin": "sourced",
            "parts_cost": None,
            "labor_cost": None,
            "note": None,
        },
        "repair_difficulty": "moderate",
        "typical_repair_days": 5,
        "parts_availability": "good",
        "confidence": 0.8,
        "source_indices": [0],
    }
    mode.update(mode_overrides)
    return {
        "evidence_sufficient": True,
        "failure_modes": [mode],
        "assumptions": [],
        "warnings": [],
    }


async def extract(payload: dict, chunks: list[RetrievedChunk] | None = None):
    agent = ExtractionAgent(LLMRouter([FakeLLM(overrides={"extraction": payload})]))
    return await agent.extract(
        identity=IDENTITY,
        chunks=chunks if chunks is not None else [chunk(0)],
        currency="EUR",
    )


class TestNormalisation:
    async def test_valid_output_passes_through(self):
        result = await extract(extraction_payload())
        assert len(result.failure_modes) == 1
        assert result.failure_modes[0].cost.typical == 280.0

    async def test_absurd_probability_is_capped(self):
        result = await extract(extraction_payload(annual_probability=0.99))
        assert result.failure_modes[0].annual_probability == MAX_ANNUAL_PROBABILITY

    async def test_inverted_cost_range_is_reordered(self):
        result = await extract(
            extraction_payload(
                cost={
                    "currency": "EUR",
                    "minimum": 500.0,
                    "typical": 200.0,
                    "maximum": 100.0,
                    "origin": "sourced",
                    "parts_cost": None,
                    "labor_cost": None,
                    "note": None,
                }
            )
        )
        cost = result.failure_modes[0].cost
        assert cost.minimum <= cost.typical <= cost.maximum

    async def test_zero_cost_entries_are_dropped(self):
        result = await extract(
            extraction_payload(
                cost={
                    "currency": "EUR",
                    "minimum": 0.0,
                    "typical": 0.0,
                    "maximum": 0.0,
                    "origin": "estimated",
                    "parts_cost": None,
                    "labor_cost": None,
                    "note": None,
                }
            )
        )
        assert result.failure_modes == []
        assert result.evidence_sufficient is False

    async def test_zero_probability_entries_are_dropped(self):
        result = await extract(extraction_payload(annual_probability=0.0))
        assert result.failure_modes == []

    async def test_hallucinated_citation_index_downgrades_provenance(self):
        result = await extract(extraction_payload(source_indices=[42]))
        mode = result.failure_modes[0]
        assert mode.source_indices == []
        assert mode.cost.origin is ValueOrigin.ESTIMATED
        assert mode.probability_origin is ValueOrigin.ESTIMATED

    async def test_duplicate_slugs_are_collapsed(self):
        payload = extraction_payload()
        payload["failure_modes"] = payload["failure_modes"] * 3
        result = await extract(payload)
        assert len(result.failure_modes) == 1

    async def test_modes_are_ranked_by_expected_impact(self):
        payload = extraction_payload()
        cheap = dict(payload["failure_modes"][0])
        cheap["slug"] = "cheap"
        cheap["name"] = "Cheap fault"
        cheap["annual_probability"] = 0.05
        cheap["cost"] = {**cheap["cost"], "typical": 50.0}
        payload["failure_modes"] = [cheap, payload["failure_modes"][0]]

        result = await extract(payload)
        assert result.failure_modes[0].slug == "backlight-failure"

    async def test_at_most_six_modes_are_kept(self):
        payload = extraction_payload()
        template = payload["failure_modes"][0]
        payload["failure_modes"] = [
            {**template, "slug": f"fault-{i}", "name": f"Fault {i}"} for i in range(12)
        ]
        result = await extract(payload)
        assert len(result.failure_modes) == 6

    async def test_missing_currency_falls_back_to_the_request_currency(self):
        result = await extract(
            extraction_payload(
                cost={
                    "currency": "",
                    "minimum": 100.0,
                    "typical": 200.0,
                    "maximum": 300.0,
                    "origin": "sourced",
                    "parts_cost": None,
                    "labor_cost": None,
                    "note": None,
                }
            )
        )
        assert result.failure_modes[0].cost.currency == "EUR"


class TestNoEvidence:
    async def test_no_chunks_means_no_model_call(self):
        llm = FakeLLM()
        agent = ExtractionAgent(LLMRouter([llm]))
        result = await agent.extract(identity=IDENTITY, chunks=[], currency="EUR")
        assert result.failure_modes == []
        assert result.evidence_sufficient is False
        assert llm.calls == []


@pytest.mark.parametrize("years", [1, 2, 3])
async def test_extraction_is_currency_stable(years: int):
    result = await extract(extraction_payload())
    assert all(mode.cost.currency == "EUR" for mode in result.failure_modes)
