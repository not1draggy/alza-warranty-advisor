"""Provider adapters: response parsing and failover behaviour."""

import httpx
import pytest

from app.core.config import get_settings
from app.core.errors import ProviderUnavailable
from app.services.llm.base import LLMProvider, UnavailableLLM
from app.services.llm.registry import LLMRouter
from app.services.search.providers import GoogleCseProvider, SerpApiProvider, TavilyProvider

TAVILY_RESPONSE = {
    "results": [
        {
            "url": "https://ifixit.com/a",
            "title": "Backlight repair",
            "content": "Costs 280 EUR.",
            "published_date": "2025-04-01T00:00:00Z",
            "score": 0.91,
            "raw_content": "Full article body about backlight repair pricing.",
        },
        {"title": "Missing url", "content": "ignored"},
    ]
}

SERPAPI_RESPONSE = {
    "organic_results": [
        {"link": "https://samsung.com/a", "title": "Service pricing", "snippet": "150 EUR"},
        {"link": "https://reddit.com/b", "title": "Thread", "snippet": "my TV died"},
    ]
}

GOOGLE_RESPONSE = {
    "items": [{"link": "https://which.co.uk/a", "title": "Reliability", "snippet": "8% fail"}]
}


def stub_client(payload: dict) -> httpx.AsyncClient:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    return httpx.AsyncClient(transport=transport)


@pytest.fixture
def configured_settings(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    monkeypatch.setenv("SERPAPI_API_KEY", "serpapi-key")
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "google-key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "engine-id")
    get_settings.cache_clear()
    settings = get_settings()
    yield settings
    get_settings.cache_clear()


class TestTavily:
    async def test_parses_results_and_keeps_raw_content(self, configured_settings):
        async with stub_client(TAVILY_RESPONSE) as http:
            results = await TavilyProvider(configured_settings, http).search("q", limit=10)
        assert len(results) == 1
        assert results[0].url == "https://ifixit.com/a"
        assert results[0].domain == "ifixit.com"
        assert results[0].raw_score == 0.91
        assert results[0].published_at is not None
        assert results[0].extra["raw_content"].startswith("Full article")

    async def test_unconfigured_provider_returns_nothing(self, settings):
        async with stub_client(TAVILY_RESPONSE) as http:
            provider = TavilyProvider(settings, http)
            assert provider.configured is False
            assert await provider.search("q", limit=5) == []


class TestSerpApi:
    async def test_ranks_by_position(self, configured_settings):
        async with stub_client(SERPAPI_RESPONSE) as http:
            results = await SerpApiProvider(configured_settings, http).search("q", limit=10)
        assert [r.url for r in results] == ["https://samsung.com/a", "https://reddit.com/b"]
        assert results[0].raw_score > results[1].raw_score


class TestGoogleCse:
    async def test_requires_both_key_and_engine_id(self, settings, monkeypatch):
        monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "google-key")
        get_settings.cache_clear()
        partial = get_settings()
        async with stub_client(GOOGLE_RESPONSE) as http:
            assert GoogleCseProvider(partial, http).configured is False
        get_settings.cache_clear()

    async def test_parses_items(self, configured_settings):
        async with stub_client(GOOGLE_RESPONSE) as http:
            results = await GoogleCseProvider(configured_settings, http).search("q", limit=10)
        assert results[0].domain == "which.co.uk"


class FlakyLLM(LLMProvider):
    def __init__(self, name: str, *, fails: bool) -> None:
        self.name = name
        self._fails = fails
        self.calls = 0

    @property
    def configured(self) -> bool:
        return True

    async def complete_json(self, **_kwargs) -> dict:
        self.calls += 1
        if self._fails:
            raise ProviderUnavailable(f"{self.name} is down")
        return {"ok": self.name}

    async def complete_text(self, **_kwargs) -> str:
        self.calls += 1
        if self._fails:
            raise ProviderUnavailable(f"{self.name} is down")
        return self.name


class TestLLMRouter:
    async def test_uses_the_first_healthy_provider(self):
        primary = FlakyLLM("primary", fails=False)
        secondary = FlakyLLM("secondary", fails=False)
        router = LLMRouter([primary, secondary])
        assert await router.complete_json(system="s", user="u", schema={}) == {"ok": "primary"}
        assert secondary.calls == 0

    async def test_falls_through_when_the_primary_is_down(self):
        primary = FlakyLLM("primary", fails=True)
        secondary = FlakyLLM("secondary", fails=False)
        router = LLMRouter([primary, secondary])
        assert await router.complete_json(system="s", user="u", schema={}) == {"ok": "secondary"}
        assert primary.calls == 1

    async def test_all_providers_down_raises(self):
        router = LLMRouter([FlakyLLM("a", fails=True), FlakyLLM("b", fails=True)])
        with pytest.raises(ProviderUnavailable):
            await router.complete_json(system="s", user="u", schema={})

    async def test_no_providers_is_reported_clearly(self):
        router = LLMRouter([])
        assert router.configured is False
        with pytest.raises(ProviderUnavailable, match="No language model is configured"):
            await router.complete_text(system="s", user="u")

    async def test_provider_names_are_exposed_for_diagnostics(self):
        router = LLMRouter([FlakyLLM("primary", fails=False)])
        assert router.provider_names == ["primary"]


class TestUnavailableLLM:
    async def test_always_raises_with_the_configured_reason(self):
        provider = UnavailableLLM("no key")
        assert provider.configured is False
        with pytest.raises(ProviderUnavailable, match="no key"):
            await provider.complete_json()
        with pytest.raises(ProviderUnavailable, match="no key"):
            await provider.complete_text()
