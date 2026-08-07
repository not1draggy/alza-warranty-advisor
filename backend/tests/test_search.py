"""Search router: fan-out, de-duplication and provider isolation."""

from app.services.cache import Cache
from app.services.search.base import SearchProvider, SearchResult
from app.services.search.registry import SearchRouter


class StubProvider(SearchProvider):
    def __init__(self, name: str, results: list[SearchResult], *, fails: bool = False) -> None:
        self.name = name
        self._results = results
        self._fails = fails
        self.calls = 0

    @property
    def configured(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        self.calls += 1
        if self._fails:
            raise RuntimeError("provider exploded")
        return self._results[:limit]


def result(url: str, *, snippet: str = "snippet", score: float = 0.5, provider: str = "a"):
    return SearchResult(url=url, title="t", snippet=snippet, provider=provider, raw_score=score)


def router(providers: list[SearchProvider], *, max_results: int = 20) -> SearchRouter:
    return SearchRouter(providers, Cache(None), ttl_seconds=60, max_results=max_results)


class TestDeduplication:
    async def test_same_url_from_two_providers_collapses(self):
        a = StubProvider("a", [result("https://x.example/page")])
        b = StubProvider("b", [result("https://x.example/page", provider="b")])
        results = await router([a, b]).search("q")
        assert len(results) == 1

    async def test_trailing_slash_and_case_are_ignored(self):
        a = StubProvider("a", [result("https://X.example/Page/")])
        b = StubProvider("b", [result("https://x.example/Page")])
        assert len(await router([a, b]).search("q")) == 1

    async def test_tracking_parameters_are_stripped(self):
        a = StubProvider("a", [result("https://x.example/p?utm_source=news&id=7")])
        b = StubProvider("b", [result("https://x.example/p?id=7")])
        assert len(await router([a, b]).search("q")) == 1

    async def test_fragments_are_ignored(self):
        a = StubProvider("a", [result("https://x.example/p#section")])
        b = StubProvider("b", [result("https://x.example/p")])
        assert len(await router([a, b]).search("q")) == 1

    async def test_merge_keeps_the_richer_snippet(self):
        a = StubProvider("a", [result("https://x.example/p", snippet="short")])
        b = StubProvider("b", [result("https://x.example/p", snippet="a much longer snippet")])
        merged = await router([a, b]).search("q")
        assert merged[0].snippet == "a much longer snippet"

    async def test_merge_keeps_the_best_score(self):
        a = StubProvider("a", [result("https://x.example/p", score=0.2)])
        b = StubProvider("b", [result("https://x.example/p", score=0.9)])
        merged = await router([a, b]).search("q")
        assert merged[0].raw_score == 0.9

    async def test_non_http_urls_are_dropped(self):
        provider = StubProvider("a", [result("javascript:alert(1)"), result("https://ok.example")])
        results = await router([provider]).search("q")
        assert [r.url for r in results] == ["https://ok.example"]


class TestResilience:
    async def test_one_failing_provider_does_not_break_the_search(self):
        good = StubProvider("good", [result("https://ok.example")])
        bad = StubProvider("bad", [], fails=True)
        results = await router([good, bad]).search("q")
        assert len(results) == 1

    async def test_all_providers_failing_returns_empty(self):
        bad = StubProvider("bad", [], fails=True)
        assert await router([bad]).search("q") == []

    async def test_no_providers_means_not_configured(self):
        empty = router([])
        assert empty.configured is False
        assert await empty.search("q") == []
        assert await empty.search_many(["q"]) == []


class TestOrderingAndLimits:
    async def test_results_are_ordered_by_score(self):
        provider = StubProvider(
            "a",
            [
                result("https://low.example", score=0.1),
                result("https://high.example", score=0.9),
                result("https://mid.example", score=0.5),
            ],
        )
        results = await router([provider]).search("q")
        assert [r.url for r in results] == [
            "https://high.example",
            "https://mid.example",
            "https://low.example",
        ]

    async def test_max_results_is_enforced(self):
        provider = StubProvider(
            "a", [result(f"https://x.example/{i}", score=i / 100) for i in range(50)]
        )
        results = await router([provider], max_results=5).search("q")
        assert len(results) == 5

    async def test_search_many_merges_across_queries(self):
        provider = StubProvider("a", [result("https://x.example/1"), result("https://x.example/2")])
        results = await router([provider]).search_many(["q1", "q2", "q3"])
        assert len(results) == 2
        assert provider.calls == 3

    async def test_search_many_with_no_queries(self):
        provider = StubProvider("a", [result("https://x.example/1")])
        assert await router([provider]).search_many([]) == []
