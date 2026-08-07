"""Concrete search providers: Tavily, SerpAPI and Google Programmable Search."""

from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.search.base import SearchProvider, SearchResult

logger = get_logger(__name__)


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    for parser in (datetime.fromisoformat,):
        try:
            parsed = parser(text)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


class TavilyProvider(SearchProvider):
    name = "tavily"
    _endpoint = "https://api.tavily.com/search"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._api_key = settings.secret(settings.tavily_api_key)
        self._client = client
        self._timeout = settings.search_timeout_seconds

    @property
    def configured(self) -> bool:
        return self._api_key is not None

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        if self._api_key is None:
            return []
        response = await self._client.post(
            self._endpoint,
            json={
                "api_key": self._api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": min(limit, 20),
                "include_answer": False,
                "include_raw_content": True,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        results = []
        for item in payload.get("results", []):
            url = item.get("url")
            if not url:
                continue
            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title") or "",
                    snippet=item.get("content") or "",
                    provider=self.name,
                    published_at=_parse_date(item.get("published_date")),
                    raw_score=float(item.get("score") or 0.0),
                    extra={"raw_content": item.get("raw_content") or ""},
                )
            )
        return results


class SerpApiProvider(SearchProvider):
    name = "serpapi"
    _endpoint = "https://serpapi.com/search.json"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._api_key = settings.secret(settings.serpapi_api_key)
        self._client = client
        self._timeout = settings.search_timeout_seconds

    @property
    def configured(self) -> bool:
        return self._api_key is not None

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        if self._api_key is None:
            return []
        response = await self._client.get(
            self._endpoint,
            params={
                "api_key": self._api_key,
                "q": query,
                "engine": "google",
                "num": min(limit, 20),
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        results = []
        for position, item in enumerate(payload.get("organic_results", [])):
            url = item.get("link")
            if not url:
                continue
            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title") or "",
                    snippet=item.get("snippet") or "",
                    provider=self.name,
                    published_at=_parse_date(item.get("date")),
                    raw_score=max(0.0, 1.0 - position / max(limit, 1)),
                )
            )
        return results


class GoogleCseProvider(SearchProvider):
    name = "google_cse"
    _endpoint = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._api_key = settings.secret(settings.google_search_api_key)
        self._engine_id = settings.google_search_engine_id
        self._client = client
        self._timeout = settings.search_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._engine_id)

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        if not self.configured:
            return []
        response = await self._client.get(
            self._endpoint,
            params={
                "key": self._api_key,
                "cx": self._engine_id,
                "q": query,
                "num": min(limit, 10),
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        results = []
        for position, item in enumerate(payload.get("items", [])):
            url = item.get("link")
            if not url:
                continue
            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title") or "",
                    snippet=item.get("snippet") or "",
                    provider=self.name,
                    raw_score=max(0.0, 1.0 - position / max(limit, 1)),
                )
            )
        return results
