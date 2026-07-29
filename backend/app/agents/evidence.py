"""Evidence agent: plan queries, search, verify sources, store them for retrieval."""

from dataclasses import dataclass

from app.agents.guard import sanitise_evidence
from app.agents.prompts import QUERY_PLANNER_SCHEMA, QUERY_PLANNER_SYSTEM
from app.agents.types import ProductIdentity
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.schemas.common import SourceType
from app.services.llm.base import LLMProvider
from app.services.rag import DocumentInput
from app.services.search.base import SearchResult
from app.services.search.registry import SearchRouter
from app.services.source_quality import assess_source

logger = get_logger(__name__)

MIN_EVIDENCE_CHARS = 120
MAX_DOCUMENTS = 20
# Never let one website dominate the evidence set.
MAX_PER_DOMAIN = 3


@dataclass(slots=True)
class VerifiedSource:
    url: str
    domain: str
    title: str
    content: str
    source_type: SourceType
    quality_score: float
    published_at: object | None = None


def fallback_queries(identity: ProductIdentity) -> list[str]:
    """Deterministic query plan, used when no model is available."""
    name = identity.search_name
    category = identity.category or "device"
    return [
        f"{name} repair cost",
        f"{name} common faults",
        f"{name} service manual fault",
        f"{name} spare parts price",
        f"{category} repair labour cost service",
        f"{name} reliability failure rate",
    ]


class EvidenceAgent:
    def __init__(self, llm: LLMProvider, search: SearchRouter) -> None:
        self._llm = llm
        self._search = search

    @property
    def search_configured(self) -> bool:
        return self._search.configured

    async def plan_queries(self, identity: ProductIdentity) -> list[str]:
        try:
            payload = await self._llm.complete_json(
                system=QUERY_PLANNER_SYSTEM,
                user=(
                    f"PRODUCT: {identity.search_name}\n"
                    f"CATEGORY: {identity.category or 'unknown'}\n"
                    f"RELEASE YEAR: {identity.release_year or 'unknown'}\n\n"
                    "Write the search queries."
                ),
                schema=QUERY_PLANNER_SCHEMA,
                max_tokens=800,
                effort="low",
            )
        except ProviderUnavailable:
            return fallback_queries(identity)

        queries = [str(q).strip() for q in payload.get("queries", []) if str(q).strip()]
        return queries[:7] or fallback_queries(identity)

    async def gather(self, queries: list[str]) -> list[VerifiedSource]:
        results = await self._search.search_many(queries)
        return self.verify(results)

    def verify(self, results: list[SearchResult]) -> list[VerifiedSource]:
        """Score, filter and diversify raw search results."""
        scored: list[tuple[float, VerifiedSource]] = []
        for result in results:
            content = self._extract_content(result)
            if len(content) < MIN_EVIDENCE_CHARS:
                continue
            assessment = assess_source(
                domain=result.domain,
                url=result.url,
                title=result.title,
                snippet=result.snippet,
                published_at=result.published_at,
            )
            if not assessment.accepted:
                continue
            scored.append(
                (
                    assessment.quality_score,
                    VerifiedSource(
                        url=result.url,
                        domain=result.domain,
                        title=result.title[:500],
                        content=content,
                        source_type=assessment.source_type,
                        quality_score=assessment.quality_score,
                        published_at=result.published_at,
                    ),
                )
            )

        scored.sort(key=lambda item: item[0], reverse=True)

        selected: list[VerifiedSource] = []
        per_domain: dict[str, int] = {}
        for _, source in scored:
            used = per_domain.get(source.domain, 0)
            if used >= MAX_PER_DOMAIN:
                continue
            per_domain[source.domain] = used + 1
            selected.append(source)
            if len(selected) >= MAX_DOCUMENTS:
                break
        return selected

    @staticmethod
    def _extract_content(result: SearchResult) -> str:
        raw = result.extra.get("raw_content") or ""
        body = raw if len(raw) > len(result.snippet) else result.snippet
        return sanitise_evidence(f"{result.title}. {body}".strip())


def to_document_inputs(sources: list[VerifiedSource]) -> list[DocumentInput]:
    return [
        DocumentInput(
            url=source.url,
            domain=source.domain,
            title=source.title,
            content=source.content,
            source_type=source.source_type,
            quality_score=source.quality_score,
            published_at=source.published_at,  # type: ignore[arg-type]
        )
        for source in sources
    ]
