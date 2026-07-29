"""Deterministic stand-ins for the LLM and search providers."""

from datetime import UTC, datetime
from typing import Any

from app.services.llm.base import LLMProvider
from app.services.search.base import SearchProvider, SearchResult

DEFAULT_IDENTITY = {
    "display_name": "Samsung UE75NU8000",
    "manufacturer": "Samsung",
    "category": "Television",
    "model_number": "UE75NU8000",
    "release_year": 2018,
    "specifications": {"screen_size": "75 inch", "panel": "VA LED"},
    "aliases": ["Samsung 75NU8000"],
    "alternatives": [],
    "confidence": 0.92,
    "reasoning": "Full model number recognised.",
}

DEFAULT_QUERIES = {"queries": ["samsung nu8000 repair cost", "samsung nu8000 backlight failure"]}

DEFAULT_EXTRACTION = {
    "evidence_sufficient": True,
    "failure_modes": [
        {
            "slug": "backlight-failure",
            "name": "Backlight failure",
            "component": "LED backlight",
            "description": "The picture goes dark while sound keeps playing.",
            "annual_probability": 0.05,
            "probability_origin": "sourced",
            "cost": {
                "currency": "EUR",
                "minimum": 180.0,
                "typical": 280.0,
                "maximum": 420.0,
                "origin": "sourced",
                "parts_cost": 120.0,
                "labor_cost": 140.0,
                "note": None,
            },
            "repair_difficulty": "moderate",
            "typical_repair_days": 5,
            "parts_availability": "good",
            "confidence": 0.8,
            "source_indices": [0],
        },
        {
            "slug": "power-board-failure",
            "name": "Power board failure",
            "component": "Power supply board",
            "description": "The set will not switch on at all.",
            "annual_probability": 0.02,
            "probability_origin": "estimated",
            "cost": {
                "currency": "EUR",
                "minimum": 90.0,
                "typical": 150.0,
                "maximum": 240.0,
                "origin": "sourced",
                "parts_cost": 70.0,
                "labor_cost": 80.0,
                "note": None,
            },
            "repair_difficulty": "moderate",
            "typical_repair_days": 4,
            "parts_availability": "good",
            "confidence": 0.6,
            "source_indices": [1],
        },
    ],
    "assumptions": ["Labour is priced at a European authorised-service rate."],
    "warnings": [],
}

DEFAULT_NARRATIVE = {
    "summary": "Roughly one in five of these sets needs a repair in the three years after "
    "the manufacturer's warranty ends, and the usual fault is the screen backlight at "
    "about 280 EUR.",
    "reasons": ["The most common fault costs around 280 EUR to fix."],
}


class FakeLLM(LLMProvider):
    """Returns canned JSON keyed on which schema was requested."""

    name = "fake"

    def __init__(self, overrides: dict[str, dict] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._overrides = overrides or {}

    @property
    def configured(self) -> bool:
        return True

    async def complete_json(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        properties = set(kwargs["schema"].get("properties", {}))
        if "queries" in properties:
            return self._overrides.get("queries", DEFAULT_QUERIES)
        if "failure_modes" in properties:
            return self._overrides.get("extraction", DEFAULT_EXTRACTION)
        if "summary" in properties:
            return self._overrides.get("narrative", DEFAULT_NARRATIVE)
        return self._overrides.get("identity", DEFAULT_IDENTITY)

    async def complete_text(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "text"


class FakeSearchProvider(SearchProvider):
    name = "fake_search"

    def __init__(self, results: list[dict] | None = None) -> None:
        self._results = results if results is not None else _default_results()

    @property
    def configured(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        return [
            SearchResult(
                url=item["url"],
                title=item["title"],
                snippet=item["snippet"],
                provider=self.name,
                published_at=item.get("published_at") or datetime.now(UTC),
                raw_score=item.get("raw_score", 0.8),
                extra=item.get("extra", {}),
            )
            for item in self._results
        ][:limit]


def _default_results() -> list[dict]:
    return [
        {
            "url": "https://www.ifixit.com/Guide/Samsung+TV+backlight",
            "title": "Samsung TV backlight replacement cost",
            "snippet": (
                "Replacing the LED backlight strips on a 75-inch Samsung set costs about "
                "280 EUR in total: roughly 120 EUR for the strips and 140 EUR labour. "
                "Turnaround is about five days at an authorised service centre."
            ),
            "extra": {},
        },
        {
            "url": "https://www.samsung.com/support/tv-repair-pricing",
            "title": "Samsung service pricing for televisions",
            "snippet": (
                "Power supply board replacement for large LED televisions is priced at "
                "150 EUR including labour, with a 30 EUR diagnostic fee waived when the "
                "repair proceeds. Spare parts remain available for seven years."
            ),
            "extra": {},
        },
    ]


def sample_search_payload() -> list[dict]:
    return _default_results()
