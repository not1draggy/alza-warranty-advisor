"""Regression tests for defects found during self-review."""

import pytest
from httpx import AsyncClient

from app.core.rate_limit import RateLimiter
from tests.fakes import sample_search_payload
from tests.test_api import ANALYSIS_PATH, analysis_body


@pytest.fixture
def fake_search_results() -> list[dict]:
    return sample_search_payload()


class TestRateLimitScope:
    async def test_scope_is_not_caller_controlled(self, client: AsyncClient):
        """A query parameter must not be able to select a fresh rate-limit bucket."""
        response = await client.get("/api/v1/health?scope=anything")
        assert response.status_code == 200

        schema = (await client.get("/openapi.json")).json()
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                if method not in {"get", "post"}:
                    continue
                names = {p["name"] for p in operation.get("parameters", [])}
                assert "scope" not in names, f"{method.upper()} {path} exposes 'scope'"

    async def test_counts_accumulate_per_identity(self):
        limiter = RateLimiter(None, limit_per_minute=2, burst=0)
        first = await limiter.check("1.2.3.4")
        second = await limiter.check("1.2.3.4")
        third = await limiter.check("1.2.3.4")
        assert first.allowed and second.allowed
        assert not third.allowed
        assert third.retry_after_seconds > 0

    async def test_different_identities_have_separate_budgets(self):
        limiter = RateLimiter(None, limit_per_minute=1, burst=0)
        assert (await limiter.check("1.1.1.1")).allowed
        assert (await limiter.check("2.2.2.2")).allowed

    async def test_local_window_stays_bounded(self):
        limiter = RateLimiter(None, limit_per_minute=1, burst=0)
        for index in range(60_001):
            await limiter.check(f"host-{index}")
        # The eviction pass runs once the ceiling is crossed; the map must not
        # simply keep growing with every distinct caller.
        assert len(limiter._local.counts) <= 50_001


class TestCitationResolution:
    async def test_citation_rows_persist_for_evidence_stored_by_an_earlier_run(
        self, client: AsyncClient, session, fake_search_results: list[dict]
    ):
        """Retrieval can surface passages ingested by a previous analysis.

        Those sources are not part of the current request's ingest, so the
        evidence links written to the database must be resolved against the whole
        store. Here the second run searches up an entirely different page while
        retrieval still returns passages stored the first time; if resolution
        only looked at this run's ingest, the citation rows would be dropped.
        """
        import sqlalchemy as sa

        from app.db.models import FailureModeCitation, RepairCostEstimate

        first = await client.post(ANALYSIS_PATH, json=analysis_body())
        assert first.status_code == 200

        # The provider now returns a page the first run never saw.
        fake_search_results.clear()
        fake_search_results.append(
            {
                "url": "https://www.rtings.com/tv/reviews/samsung/nu8000",
                "title": "Samsung NU8000 long-term reliability",
                "snippet": (
                    "Owners report panel and power issues after three years; an "
                    "out-of-warranty repair is typically quoted around 300 EUR "
                    "including parts and labour at an authorised centre."
                ),
                "extra": {},
            }
        )

        second = await client.post(ANALYSIS_PATH, json=analysis_body(warranty_price=120.0))
        assert second.status_code == 200
        assert second.json()["from_cache"] is False

        citations = await session.scalar(
            sa.select(sa.func.count()).select_from(FailureModeCitation)
        )
        assert citations > 0, "evidence links were dropped for previously stored sources"

        linked_costs = await session.scalar(
            sa.select(sa.func.count())
            .select_from(RepairCostEstimate)
            .where(RepairCostEstimate.source_id.isnot(None))
        )
        assert linked_costs > 0, "repair prices lost their source link"

    async def test_analysis_citations_carry_stored_source_ids(self, client: AsyncClient):
        payload = (await client.post(ANALYSIS_PATH, json=analysis_body())).json()
        cited = [c for mode in payload["failure_modes"] for c in mode["citations"]]
        assert cited
        for citation in cited:
            assert citation["url"].startswith("https://")
            # A resolved database identifier, not a URL fallback or a placeholder.
            assert not citation["source_id"].startswith(("http", "chunk-"))


class TestProductSearchEscaping:
    async def test_wildcard_query_does_not_match_everything(self, client: AsyncClient):
        await client.post(ANALYSIS_PATH, json=analysis_body())

        wildcard = await client.get("/api/v1/products", params={"q": "%%"})
        assert wildcard.status_code == 200
        assert wildcard.json() == []

        real = await client.get("/api/v1/products", params={"q": "samsung"})
        assert len(real.json()) == 1
