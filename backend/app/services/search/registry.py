"""Fan-out search across every configured provider, de-duplicated and cached."""

import asyncio
from datetime import datetime

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.cache import Cache, cache_key
from app.services.search.base import SearchProvider, SearchResult
from app.services.search.providers import GoogleCseProvider, SerpApiProvider, TavilyProvider

logger = get_logger(__name__)


def _result_to_cache(result: SearchResult) -> dict:
    return {
        "url": result.url,
        "title": result.title,
        "snippet": result.snippet,
        "provider": result.provider,
        "published_at": result.published_at.isoformat() if result.published_at else None,
        "raw_score": result.raw_score,
        "extra": result.extra,
    }


def _result_from_cache(item: dict) -> SearchResult:
    published_at = item.get("published_at")
    return SearchResult(
        url=item["url"],
        title=item.get("title", ""),
        snippet=item.get("snippet", ""),
        provider=item.get("provider", "cache"),
        published_at=datetime.fromisoformat(published_at) if published_at else None,
        raw_score=float(item.get("raw_score") or 0.0),
        extra=item.get("extra") or {},
    )


def _canonical(url: str) -> str:
    """Strip tracking noise so the same page from two providers collapses to one."""
    base = url.split("#", 1)[0]
    if "?" in base:
        head, _, query = base.partition("?")
        keep = [
            part
            for part in query.split("&")
            if part and not part.split("=", 1)[0].lower().startswith(("utm_", "gclid", "fbclid"))
        ]
        base = head + ("?" + "&".join(keep) if keep else "")
    return base.rstrip("/").lower()


class SearchRouter:
    def __init__(
        self,
        providers: list[SearchProvider],
        cache: Cache,
        *,
        ttl_seconds: int,
        max_results: int,
    ) -> None:
        self._providers = [p for p in providers if p.configured]
        self._cache = cache
        self._ttl = ttl_seconds
        self._max_results = max_results

    @property
    def configured(self) -> bool:
        return bool(self._providers)

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    async def search_many(self, queries: list[str]) -> list[SearchResult]:
        """Run several queries concurrently and merge the results."""
        if not self._providers or not queries:
            return []
        batches = await asyncio.gather(
            *(self.search(query) for query in queries), return_exceptions=True
        )
        merged: list[SearchResult] = []
        for batch in batches:
            if isinstance(batch, BaseException):
                logger.warning("search_batch_failed", error=str(batch))
                continue
            merged.extend(batch)
        return self._deduplicate(merged)

    async def search(self, query: str) -> list[SearchResult]:
        if not self._providers:
            return []

        key = cache_key("search", query, ",".join(self.provider_names), self._max_results)
        cached = await self._cache.get_json(key)
        if cached is not None:
            return [_result_from_cache(item) for item in cached]

        per_provider = max(5, self._max_results // max(1, len(self._providers)) + 4)
        outcomes = await asyncio.gather(
            *(provider.search(query, limit=per_provider) for provider in self._providers),
            return_exceptions=True,
        )

        results: list[SearchResult] = []
        for provider, outcome in zip(self._providers, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.warning(
                    "search_provider_failed", provider=provider.name, error=str(outcome)
                )
                continue
            results.extend(outcome)

        deduped = self._deduplicate(results)
        await self._cache.set_json(key, [_result_to_cache(r) for r in deduped], self._ttl)
        return deduped

    def _deduplicate(self, results: list[SearchResult]) -> list[SearchResult]:
        best: dict[str, SearchResult] = {}
        for result in results:
            if not result.url.startswith(("http://", "https://")):
                continue
            key = _canonical(result.url)
            existing = best.get(key)
            if existing is None:
                best[key] = result
                continue
            # Keep the richer record; snippets and raw content differ between providers.
            if len(result.snippet) > len(existing.snippet):
                existing.snippet = result.snippet
            if result.raw_score > existing.raw_score:
                existing.raw_score = result.raw_score
            if existing.published_at is None:
                existing.published_at = result.published_at
            if not existing.extra.get("raw_content") and result.extra.get("raw_content"):
                existing.extra["raw_content"] = result.extra["raw_content"]

        ordered = sorted(best.values(), key=lambda r: r.raw_score, reverse=True)
        return ordered[: self._max_results]


def build_search_router(
    settings: Settings, cache: Cache, client: httpx.AsyncClient
) -> SearchRouter:
    return SearchRouter(
        [
            TavilyProvider(settings, client),
            SerpApiProvider(settings, client),
            GoogleCseProvider(settings, client),
        ],
        cache,
        ttl_seconds=settings.search_cache_ttl_seconds,
        max_results=settings.max_search_results,
    )
