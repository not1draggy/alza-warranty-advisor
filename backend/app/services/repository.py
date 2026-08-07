"""Persistence helpers for products, evidence links, analyses and history."""

import hashlib
import re
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.identify import lookup_key
from app.agents.types import ExtractedFailureMode, ProductIdentity
from app.db.models import (
    Analysis,
    Category,
    FailureMode,
    FailureModeCitation,
    Manufacturer,
    Product,
    RepairCostEstimate,
    SearchHistory,
    Source,
)
from app.schemas.analysis import AnalysisRequest, AnalysisResult
from app.schemas.common import ValueOrigin

_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    return _SLUG.sub("-", value.lower()).strip("-")


def fingerprint(request: AnalysisRequest) -> str:
    raw = (
        f"{request.query.lower().strip()}|{request.warranty_years}|"
        f"{round(request.warranty_price, 2)}|{request.currency}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _get_or_create_manufacturer(
    session: AsyncSession, name: str | None
) -> Manufacturer | None:
    if not name or not name.strip():
        return None
    slug = slugify(name)
    existing = await session.scalar(sa.select(Manufacturer).where(Manufacturer.slug == slug))
    if existing:
        return existing
    record = Manufacturer(name=name.strip()[:160], slug=slug[:160])
    session.add(record)
    await session.flush()
    return record


async def _get_or_create_category(session: AsyncSession, name: str | None) -> Category | None:
    if not name or not name.strip():
        return None
    slug = slugify(name)
    existing = await session.scalar(sa.select(Category).where(Category.slug == slug))
    if existing:
        return existing
    record = Category(name=name.strip()[:160], slug=slug[:160])
    session.add(record)
    await session.flush()
    return record


async def upsert_product(session: AsyncSession, identity: ProductIdentity) -> Product:
    key = lookup_key(identity.manufacturer, identity.model_number, identity.display_name)[:255]
    product = await session.scalar(sa.select(Product).where(Product.lookup_key == key))

    manufacturer = await _get_or_create_manufacturer(session, identity.manufacturer)
    category = await _get_or_create_category(session, identity.category)

    if product is None:
        product = Product(lookup_key=key, display_name=identity.display_name[:255])
        session.add(product)

    product.display_name = identity.display_name[:255]
    product.manufacturer_id = manufacturer.id if manufacturer else None
    product.category_id = category.id if category else None
    product.model_number = (identity.model_number or None) and identity.model_number[:160]
    product.release_year = identity.release_year
    product.specifications = identity.specifications
    product.aliases = identity.aliases
    product.identification_confidence = identity.confidence
    await session.flush()
    return product


async def persist_failure_modes(
    session: AsyncSession,
    *,
    product: Product,
    modes: list[ExtractedFailureMode],
    sources_by_index: dict[int, Source],
) -> None:
    """Replace the product's failure-mode catalogue with the latest extraction."""
    existing = (
        await session.scalars(sa.select(FailureMode).where(FailureMode.product_id == product.id))
    ).all()
    by_slug = {record.slug: record for record in existing}

    for mode in modes:
        record = by_slug.pop(mode.slug, None)
        if record is None:
            record = FailureMode(product_id=product.id, slug=mode.slug[:160])
            session.add(record)

        record.name = mode.name[:255]
        record.component = (mode.component or None) and mode.component[:160]
        record.description = mode.description
        record.annual_probability = mode.annual_probability
        record.probability_is_estimated = mode.probability_origin is not ValueOrigin.SOURCED
        record.repair_difficulty = (mode.repair_difficulty or None) and mode.repair_difficulty[:32]
        record.typical_repair_days = mode.typical_repair_days
        record.parts_availability = (mode.parts_availability or None) and mode.parts_availability[
            :32
        ]
        record.confidence = mode.confidence
        await session.flush()

        await session.execute(
            sa.delete(RepairCostEstimate).where(RepairCostEstimate.failure_mode_id == record.id)
        )
        primary_source = next(
            (sources_by_index[i] for i in mode.source_indices if i in sources_by_index), None
        )
        session.add(
            RepairCostEstimate(
                failure_mode_id=record.id,
                source_id=primary_source.id if primary_source else None,
                currency=mode.cost.currency[:3],
                parts_cost=mode.cost.parts_cost,
                labor_cost=mode.cost.labor_cost,
                total_min=mode.cost.minimum,
                total_typical=mode.cost.typical,
                total_max=mode.cost.maximum,
                is_estimated=mode.cost.origin is not ValueOrigin.SOURCED,
                note=mode.cost.note,
            )
        )

        await session.execute(
            sa.delete(FailureModeCitation).where(FailureModeCitation.failure_mode_id == record.id)
        )
        for index in dict.fromkeys(mode.source_indices):
            source = sources_by_index.get(index)
            if source is not None:
                session.add(FailureModeCitation(failure_mode_id=record.id, source_id=source.id))

    for stale in by_slug.values():
        await session.delete(stale)
    await session.flush()


async def sources_by_url(session: AsyncSession, urls: list[str]) -> dict[str, Source]:
    """Resolve stored sources for a set of URLs.

    Retrieval can surface passages from documents ingested by an earlier run, so
    citations must be resolved against the whole store rather than only against
    the sources written during this request.
    """
    unique = list(dict.fromkeys(urls))
    if not unique:
        return {}
    records = (await session.scalars(sa.select(Source).where(Source.url.in_(unique)))).all()
    return {record.url: record for record in records}


async def find_fresh_analysis(session: AsyncSession, key: str) -> Analysis | None:
    return await session.scalar(
        sa.select(Analysis)
        .where(Analysis.fingerprint == key, Analysis.expires_at > datetime.now(UTC))
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )


async def save_analysis(
    session: AsyncSession,
    *,
    key: str,
    request: AnalysisRequest,
    result: AnalysisResult,
    product_id: str | None,
    ttl_seconds: int,
) -> Analysis:
    record = Analysis(
        id=result.id,
        product_id=product_id,
        fingerprint=key,
        query=request.query[:512],
        warranty_years=request.warranty_years,
        warranty_price=request.warranty_price,
        currency=request.currency,
        verdict=result.verdict.decision.value,
        expected_repair_cost=result.economics.expected_repair_cost,
        average_repair_cost=result.economics.average_repair_cost,
        worst_case_repair_cost=result.economics.worst_case_repair_cost,
        failure_probability=result.economics.failure_probability,
        risk_score=result.risk.score,
        confidence=result.confidence.score,
        evidence_level=result.confidence.evidence_level.value,
        payload=result.model_dump(mode="json"),
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
    )
    session.add(record)
    await session.flush()
    return record


async def record_search(
    session: AsyncSession,
    *,
    request: AnalysisRequest,
    analysis_id: str | None,
    user_id: str | None,
) -> None:
    session.add(
        SearchHistory(
            user_id=user_id,
            session_id=request.session_id,
            analysis_id=analysis_id,
            query=request.query[:512],
            warranty_years=request.warranty_years,
            warranty_price=request.warranty_price,
            currency=request.currency,
        )
    )
    await session.flush()


async def list_history(
    session: AsyncSession,
    *,
    user_id: str | None,
    session_id: str | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[SearchHistory, Analysis | None, Product | None]], int]:
    if user_id is None and session_id is None:
        return [], 0

    condition = (
        SearchHistory.user_id == user_id
        if user_id is not None
        else SearchHistory.session_id == session_id
    )

    total = await session.scalar(
        sa.select(sa.func.count()).select_from(SearchHistory).where(condition)
    )
    rows = (
        await session.execute(
            sa.select(SearchHistory, Analysis, Product)
            .outerjoin(Analysis, Analysis.id == SearchHistory.analysis_id)
            .outerjoin(Product, Product.id == Analysis.product_id)
            .where(condition)
            .order_by(SearchHistory.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [(row[0], row[1], row[2]) for row in rows], int(total or 0)


async def get_analysis(session: AsyncSession, analysis_id: str) -> Analysis | None:
    return await session.get(Analysis, analysis_id)
