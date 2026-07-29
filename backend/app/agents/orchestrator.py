"""The orchestrator: one pass from a product query to a warranty recommendation.

Pipeline
--------
    guard -> cache -> identify -> plan queries -> search -> verify sources
          -> store + retrieve (RAG) -> extract repair economics
          -> quantify (probability, cost, risk, confidence, verdict)
          -> compose -> persist

Every stage is reported as it happens so the UI can show real progress rather than
a spinner. Failures inside a stage degrade the answer (lower confidence, explicit
warnings) instead of aborting the request.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.composer import ComposerAgent
from app.agents.confidence import ConfidenceReport, SourceSignal, score_confidence
from app.agents.evidence import EvidenceAgent, to_document_inputs
from app.agents.extraction import ExtractionAgent
from app.agents.guard import validate_query
from app.agents.identify import IdentificationAgent
from app.agents.risk import (
    Economics,
    compute_economics,
    compute_risk_score,
    decide_verdict,
    risk_band,
    risk_drivers,
)
from app.agents.types import ExtractedFailureMode, ProductIdentity
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.text import FAULTS, PAGES, PASSAGES, SOURCES, counted
from app.db.models import Source
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisStage,
    Citation,
    ConfidenceAssessment,
    FailureModeView,
    MoneyRange,
    ProductView,
    RiskAssessment,
    TimelinePoint,
    VerdictView,
)
from app.schemas.analysis import (
    Economics as EconomicsView,
)
from app.schemas.common import EvidenceLevel, Verdict
from app.services import repository
from app.services.rag import RagStore, RetrievedChunk

logger = get_logger(__name__)

_STAGES: list[tuple[str, str, float]] = [
    ("identify", "Určujeme presný produkt", 0.12),
    ("search", "Prehľadávame verejné zdroje o opravách", 0.30),
    ("verify", "Overujeme kvalitu zdrojov", 0.45),
    ("retrieve", "Čítame najrelevantnejšie pasáže", 0.58),
    ("extract", "Získavame poruchy a ceny opráv", 0.78),
    ("quantify", "Počítame pravdepodobnosť, náklady a riziko", 0.90),
    ("compose", "Píšeme odporúčanie", 0.97),
]


@dataclass(slots=True)
class OrchestratorDeps:
    identification: IdentificationAgent
    evidence: EvidenceAgent
    extraction: ExtractionAgent
    composer: ComposerAgent
    rag: RagStore
    session: AsyncSession
    settings: Settings


class AnalysisOrchestrator:
    def __init__(self, deps: OrchestratorDeps) -> None:
        self._deps = deps

    async def analyze(
        self, request: AnalysisRequest, *, user_id: str | None = None
    ) -> AnalysisResult:
        result: AnalysisResult | None = None
        async for event in self.stream(request, user_id=user_id):
            if isinstance(event, AnalysisResult):
                result = event
        assert result is not None, "the pipeline always yields a result"
        return result

    async def stream(
        self, request: AnalysisRequest, *, user_id: str | None = None
    ) -> AsyncIterator[AnalysisStage | AnalysisResult]:
        deps = self._deps
        request.query = validate_query(request.query)
        key = repository.fingerprint(request)

        if not request.refresh:
            cached = await repository.find_fresh_analysis(deps.session, key)
            if cached is not None:
                yield AnalysisStage(
                    stage="cache",
                    label="Používame nedávnu overenú analýzu",
                    status="done",
                    progress=1.0,
                )
                result = AnalysisResult.model_validate(cached.payload)
                result.from_cache = True
                await repository.record_search(
                    deps.session, request=request, analysis_id=cached.id, user_id=user_id
                )
                await deps.session.commit()
                yield result
                return

        warnings: list[str] = []
        assumptions: list[str] = []

        # --- identify -------------------------------------------------------
        yield _running("identify")
        identity = await deps.identification.identify(request.query)
        yield _done("identify", identity.display_name)

        # --- search ---------------------------------------------------------
        yield _running("search")
        chunks: list[RetrievedChunk] = []

        if deps.evidence.search_configured:
            queries = await deps.evidence.plan_queries(identity)
            verified = await deps.evidence.gather(queries)
            yield _done("search", f"{counted(len(verified), *PAGES)} na posúdenie")

            yield _running("verify")
            if not verified:
                warnings.append("No public repair sources passed the quality checks.")
            yield _done("verify", f"prijatých {counted(len(verified), *SOURCES)}")

            yield _running("retrieve")
            product = await repository.upsert_product(deps.session, identity)
            await deps.rag.ingest(to_document_inputs(verified), product_id=product.id)
            chunks = await deps.rag.retrieve(
                f"{identity.search_name} repair cost common failures",
                product_id=product.id,
                limit=14,
            )
            yield _done("retrieve", f"{counted(len(chunks), *PASSAGES)}")
        else:
            warnings.append(
                "No web search provider is configured, so this answer has no public "
                "sources behind it."
            )
            product = await repository.upsert_product(deps.session, identity)
            yield _done("search", "vyhľadávanie nedostupné")
            yield _done("verify", "preskočené")
            yield _done("retrieve", "preskočené")

        # --- extract --------------------------------------------------------
        yield _running("extract")
        extraction = await deps.extraction.extract(
            identity=identity, chunks=chunks, currency=request.currency
        )
        warnings.extend(extraction.warnings)
        assumptions.extend(extraction.assumptions)
        yield _done("extract", f"{counted(len(extraction.failure_modes), *FAULTS)}")

        # --- quantify -------------------------------------------------------
        yield _running("quantify")
        economics = compute_economics(
            extraction.failure_modes,
            years=request.warranty_years,
            warranty_price=request.warranty_price,
            currency=request.currency,
        )
        source_signals = [
            SourceSignal(domain=chunk.source_domain, quality_score=chunk.quality_score)
            for chunk in _unique_by_domain(chunks)
        ]
        confidence = score_confidence(
            failure_modes=extraction.failure_modes,
            sources=source_signals,
            identification_confidence=identity.confidence,
        )
        verdict, reasons = decide_verdict(
            economics, confidence=confidence.score, evidence_level=confidence.evidence_level
        )
        score = compute_risk_score(economics, product_price=request.product_price)
        if request.product_price is None and extraction.failure_modes:
            assumptions.append(
                "Riziko je hodnotené voči referenčnej hodnote 500 EUR, pretože cena "
                "produktu nebola zadaná."
            )
        yield _done("quantify", f"riziko {score:.0f}/100")

        # --- compose --------------------------------------------------------
        yield _running("compose")
        narrative = await deps.composer.compose(
            identity=identity,
            verdict=verdict,
            reasons=reasons,
            economics=economics,
            confidence=confidence,
            failure_modes=extraction.failure_modes,
            years=request.warranty_years,
        )
        yield _done("compose")

        # --- assemble and persist ------------------------------------------
        # Resolve citations against the whole store: retrieval can surface
        # passages from documents ingested by an earlier run.
        stored_sources = await repository.sources_by_url(
            deps.session, [chunk.source_url for chunk in chunks]
        )
        chunk_sources = {
            index: stored_sources[chunk.source_url]
            for index, chunk in enumerate(chunks)
            if chunk.source_url in stored_sources
        }
        result = _build_result(
            request=request,
            identity=identity,
            extraction_modes=extraction.failure_modes,
            economics=economics,
            confidence=confidence,
            verdict=verdict,
            narrative_headline=narrative.headline,
            narrative_summary=narrative.summary,
            narrative_reasons=narrative.reasons or reasons,
            risk_score=score,
            chunks=chunks,
            chunk_sources=chunk_sources,
            warnings=warnings,
            assumptions=assumptions,
        )

        await repository.persist_failure_modes(
            deps.session,
            product=product,
            modes=extraction.failure_modes,
            sources_by_index=chunk_sources,
        )
        await repository.save_analysis(
            deps.session,
            key=key,
            request=request,
            result=result,
            product_id=product.id,
            ttl_seconds=deps.settings.analysis_cache_ttl_seconds,
        )
        await repository.record_search(
            deps.session, request=request, analysis_id=result.id, user_id=user_id
        )
        await deps.session.commit()

        yield AnalysisStage(stage="done", label="Analýza dokončená", status="done", progress=1.0)
        yield result


# ---------------------------------------------------------------------------
# helpers


def _stage_meta(stage: str) -> tuple[str, float]:
    for name, label, progress in _STAGES:
        if name == stage:
            return label, progress
    return stage, 0.0


def _running(stage: str) -> AnalysisStage:
    label, progress = _stage_meta(stage)
    return AnalysisStage(stage=stage, label=label, status="running", progress=progress)


def _done(stage: str, detail: str | None = None) -> AnalysisStage:
    label, progress = _stage_meta(stage)
    return AnalysisStage(stage=stage, label=label, status="done", detail=detail, progress=progress)


def _unique_by_domain(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[str] = set()
    unique: list[RetrievedChunk] = []
    for chunk in chunks:
        if chunk.source_url in seen:
            continue
        seen.add(chunk.source_url)
        unique.append(chunk)
    return unique


def _citation_from_chunk(chunk: RetrievedChunk, source_id: str) -> Citation:
    return Citation(
        source_id=source_id,
        url=chunk.source_url,
        domain=chunk.source_domain,
        title=chunk.source_title,
        source_type=chunk.source_type,
        quality_score=chunk.quality_score,
        retrieved_at=chunk.retrieved_at,
    )


def _build_result(
    *,
    request: AnalysisRequest,
    identity: ProductIdentity,
    extraction_modes: list[ExtractedFailureMode],
    economics: Economics,
    confidence: ConfidenceReport,
    verdict: Verdict,
    narrative_headline: str,
    narrative_summary: str,
    narrative_reasons: list[str],
    risk_score: float,
    chunks: list[RetrievedChunk],
    chunk_sources: dict[int, Source],
    warnings: list[str],
    assumptions: list[str],
) -> AnalysisResult:
    citations_by_index: dict[int, Citation] = {}
    for index, chunk in enumerate(chunks):
        source = chunk_sources.get(index)
        citations_by_index[index] = _citation_from_chunk(
            chunk, source_id=source.id if source else chunk.source_url
        )

    unique_sources: dict[str, Citation] = {}
    for citation in citations_by_index.values():
        unique_sources.setdefault(citation.url, citation)

    failure_views = [
        FailureModeView(
            slug=mode.slug,
            name=mode.name,
            component=mode.component,
            description=mode.description,
            annual_probability=mode.annual_probability,
            window_probability=economics.window_probabilities.get(mode.slug, 0.0),
            probability_origin=mode.probability_origin,
            cost=MoneyRange(
                currency=mode.cost.currency,
                minimum=mode.cost.minimum,
                typical=mode.cost.typical,
                maximum=mode.cost.maximum,
                origin=mode.cost.origin,
            ),
            repair_difficulty=mode.repair_difficulty,
            typical_repair_days=mode.typical_repair_days,
            parts_availability=mode.parts_availability,
            confidence=mode.confidence,
            citations=[
                citations_by_index[i] for i in mode.source_indices if i in citations_by_index
            ],
        )
        for mode in extraction_modes
    ]

    if confidence.evidence_level is EvidenceLevel.NONE and not warnings:
        warnings.append("No repair evidence was available, so no estimate is shown.")

    return AnalysisResult(
        id=str(uuid.uuid4()),
        generated_at=datetime.now(UTC),
        from_cache=False,
        query=request.query,
        warranty_years=request.warranty_years,
        product=ProductView(
            display_name=identity.display_name,
            manufacturer=identity.manufacturer,
            category=identity.category,
            model_number=identity.model_number,
            release_year=identity.release_year,
            specifications=identity.specifications,
            aliases=identity.aliases,
            identification_confidence=identity.confidence,
            alternatives=identity.alternatives,
        ),
        verdict=VerdictView(
            decision=verdict,
            headline=narrative_headline,
            summary=narrative_summary,
            reasons=narrative_reasons,
        ),
        economics=EconomicsView(
            currency=economics.currency,
            expected_repair_cost=economics.expected_repair_cost,
            average_repair_cost=economics.average_repair_cost,
            worst_case_repair_cost=economics.worst_case_repair_cost,
            failure_probability=economics.failure_probability,
            warranty_price=economics.warranty_price,
            net_value=economics.net_value,
            value_ratio=economics.value_ratio,
            break_even_probability=economics.break_even_probability,
        ),
        risk=RiskAssessment(
            score=risk_score,
            band=risk_band(risk_score),
            drivers=risk_drivers(economics, extraction_modes),
        ),
        confidence=ConfidenceAssessment(
            score=confidence.score,
            band=confidence.band,
            evidence_level=confidence.evidence_level,
            source_count=confidence.source_count,
            independent_domains=confidence.independent_domains,
            drivers=confidence.drivers,
            uncertainties=confidence.uncertainties,
        ),
        failure_modes=failure_views,
        timeline=[
            TimelinePoint(
                year=entry.year,
                cumulative_failure_probability=entry.cumulative_failure_probability,
                cumulative_expected_cost=entry.cumulative_expected_cost,
            )
            for entry in economics.timeline
        ],
        sources=sorted(unique_sources.values(), key=lambda item: item.quality_score, reverse=True),
        assumptions=assumptions,
        warnings=warnings,
    )
