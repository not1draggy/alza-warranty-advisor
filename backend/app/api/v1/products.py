"""Product lookup: what the system already knows about a product."""

import sqlalchemy as sa
from fastapi import APIRouter, Query
from pydantic import Field

from app.api.deps import SessionDep
from app.core.errors import NotFound
from app.db.models import FailureMode, Manufacturer, Product, RepairCostEstimate
from app.schemas.common import DomainModel

router = APIRouter(prefix="/products", tags=["products"])


class ProductSummary(DomainModel):
    id: str
    display_name: str
    manufacturer: str | None = None
    model_number: str | None = None
    release_year: int | None = None
    identification_confidence: float = 0.0


class KnownFailureMode(DomainModel):
    slug: str
    name: str
    component: str | None = None
    annual_probability: float
    probability_is_estimated: bool
    currency: str = "EUR"
    typical_cost: float | None = None
    confidence: float = 0.0


class ProductDetail(ProductSummary):
    specifications: dict = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    failure_modes: list[KnownFailureMode] = Field(default_factory=list)


@router.get("", response_model=list[ProductSummary], summary="Search known products")
async def search_products(
    session: SessionDep,
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[ProductSummary]:
    # Escape LIKE metacharacters so a query of "%" does not match everything.
    escaped = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    rows = (
        await session.execute(
            sa.select(Product, Manufacturer)
            .outerjoin(Manufacturer, Manufacturer.id == Product.manufacturer_id)
            .where(
                sa.or_(
                    sa.func.lower(Product.display_name).like(pattern, escape="\\"),
                    sa.func.lower(Product.lookup_key).like(pattern, escape="\\"),
                    sa.func.lower(sa.func.coalesce(Product.model_number, "")).like(
                        pattern, escape="\\"
                    ),
                )
            )
            .order_by(Product.identification_confidence.desc())
            .limit(limit)
        )
    ).all()
    return [
        ProductSummary(
            id=product.id,
            display_name=product.display_name,
            manufacturer=manufacturer.name if manufacturer else None,
            model_number=product.model_number,
            release_year=product.release_year,
            identification_confidence=product.identification_confidence,
        )
        for product, manufacturer in rows
    ]


@router.get("/{product_id}", response_model=ProductDetail, summary="Known repair profile")
async def read_product(product_id: str, session: SessionDep) -> ProductDetail:
    product = await session.get(Product, product_id)
    if product is None:
        raise NotFound("No product with that id exists.")

    manufacturer = (
        await session.get(Manufacturer, product.manufacturer_id)
        if product.manufacturer_id
        else None
    )
    rows = (
        await session.execute(
            sa.select(FailureMode, RepairCostEstimate)
            .outerjoin(RepairCostEstimate, RepairCostEstimate.failure_mode_id == FailureMode.id)
            .where(FailureMode.product_id == product_id)
            .order_by(FailureMode.annual_probability.desc())
        )
    ).all()

    return ProductDetail(
        id=product.id,
        display_name=product.display_name,
        manufacturer=manufacturer.name if manufacturer else None,
        model_number=product.model_number,
        release_year=product.release_year,
        identification_confidence=product.identification_confidence,
        specifications=product.specifications,
        aliases=product.aliases,
        failure_modes=[
            KnownFailureMode(
                slug=mode.slug,
                name=mode.name,
                component=mode.component,
                annual_probability=mode.annual_probability,
                probability_is_estimated=mode.probability_is_estimated,
                currency=cost.currency if cost else "EUR",
                typical_cost=cost.total_typical if cost else None,
                confidence=mode.confidence,
            )
            for mode, cost in rows
        ],
    )
