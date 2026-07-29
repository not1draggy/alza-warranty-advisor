"""Relational model for products, evidence, repair economics and analyses.

Design notes:
  * Evidence (`Source` -> `Document` -> `DocumentChunk`) is stored once and reused
    across products; embeddings live in their own table so documents stay cheap to scan.
  * Repair economics are normalised per failure mode so an analysis can be rebuilt
    from facts rather than from a frozen blob.
  * `Analysis` additionally keeps the rendered payload so a cached read is a single row.
"""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, EmbeddingColumn, JSONColumn, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(sa.String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(sa.String(120))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    searches: Mapped[list["SearchHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Manufacturer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "manufacturers"

    name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(160), unique=True, index=True, nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="manufacturer")


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(160), unique=True, index=True, nullable=False)
    # Baseline annual failure rate for the category, used only when evidence is thin
    # and always surfaced to the user as an assumption.
    baseline_annual_failure_rate: Mapped[float | None] = mapped_column(sa.Float)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (sa.Index("ix_products_lookup_key", "lookup_key", unique=True),)

    manufacturer_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("manufacturers.id", ondelete="SET NULL")
    )
    category_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("categories.id", ondelete="SET NULL")
    )

    # Normalised identity: lowercase manufacturer + model, punctuation stripped.
    lookup_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    model_number: Mapped[str | None] = mapped_column(sa.String(160), index=True)
    release_year: Mapped[int | None] = mapped_column(sa.Integer)
    specifications: Mapped[dict] = mapped_column(JSONColumn, default=dict, nullable=False)
    aliases: Mapped[list] = mapped_column(JSONColumn, default=list, nullable=False)
    identification_confidence: Mapped[float] = mapped_column(
        sa.Float, default=0.0, nullable=False
    )

    manufacturer: Mapped[Manufacturer | None] = relationship(back_populates="products")
    category: Mapped[Category | None] = relationship(back_populates="products")
    failure_modes: Mapped[list["FailureMode"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="product")


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    url: Mapped[str] = mapped_column(sa.String(2048), nullable=False)
    url_hash: Mapped[str] = mapped_column(
        sa.String(64), unique=True, index=True, nullable=False
    )
    domain: Mapped[str] = mapped_column(sa.String(255), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(sa.String(512))
    # manufacturer | authorized_service | repair_professional | parts_catalog |
    # community | reliability_report | retailer | unknown
    source_type: Mapped[str] = mapped_column(sa.String(48), default="unknown", nullable=False)
    quality_score: Mapped[float] = mapped_column(sa.Float, default=0.0, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    source_id: Mapped[str] = mapped_column(
        sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str | None] = mapped_column(sa.String(512))
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        sa.String(64), unique=True, index=True, nullable=False
    )
    language: Mapped[str | None] = mapped_column(sa.String(8))
    retrieved_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    source: Mapped[Source] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),
    )

    document_id: Mapped[str] = mapped_column(
        sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    ordinal: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingColumn)

    document: Mapped[Document] = relationship(back_populates="chunks")


class FailureMode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "failure_modes"
    __table_args__ = (
        sa.UniqueConstraint("product_id", "slug", name="uq_failure_mode_product_slug"),
    )

    product_id: Mapped[str] = mapped_column(
        sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    component: Mapped[str | None] = mapped_column(sa.String(160))
    description: Mapped[str | None] = mapped_column(sa.Text)
    # Probability that this failure occurs in a single year of ownership.
    annual_probability: Mapped[float] = mapped_column(sa.Float, default=0.0, nullable=False)
    probability_is_estimated: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, nullable=False
    )
    repair_difficulty: Mapped[str | None] = mapped_column(sa.String(32))
    typical_repair_days: Mapped[float | None] = mapped_column(sa.Float)
    parts_availability: Mapped[str | None] = mapped_column(sa.String(32))
    confidence: Mapped[float] = mapped_column(sa.Float, default=0.0, nullable=False)

    product: Mapped[Product] = relationship(back_populates="failure_modes")
    cost_estimates: Mapped[list["RepairCostEstimate"]] = relationship(
        back_populates="failure_mode", cascade="all, delete-orphan"
    )
    citations: Mapped[list["FailureModeCitation"]] = relationship(
        back_populates="failure_mode", cascade="all, delete-orphan"
    )


class RepairCostEstimate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repair_cost_estimates"

    failure_mode_id: Mapped[str] = mapped_column(
        sa.ForeignKey("failure_modes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("sources.id", ondelete="SET NULL"), index=True
    )
    currency: Mapped[str] = mapped_column(sa.String(3), default="EUR", nullable=False)
    parts_cost: Mapped[float | None] = mapped_column(sa.Float)
    labor_cost: Mapped[float | None] = mapped_column(sa.Float)
    diagnostic_fee: Mapped[float | None] = mapped_column(sa.Float)
    total_min: Mapped[float] = mapped_column(sa.Float, nullable=False)
    total_typical: Mapped[float] = mapped_column(sa.Float, nullable=False)
    total_max: Mapped[float] = mapped_column(sa.Float, nullable=False)
    is_estimated: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    note: Mapped[str | None] = mapped_column(sa.Text)

    failure_mode: Mapped[FailureMode] = relationship(back_populates="cost_estimates")
    source: Mapped[Source | None] = relationship()


class FailureModeCitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "failure_mode_citations"
    __table_args__ = (
        sa.UniqueConstraint("failure_mode_id", "source_id", name="uq_citation_mode_source"),
    )

    failure_mode_id: Mapped[str] = mapped_column(
        sa.ForeignKey("failure_modes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quote: Mapped[str | None] = mapped_column(sa.Text)

    failure_mode: Mapped[FailureMode] = relationship(back_populates="citations")
    source: Mapped[Source] = relationship()


class Analysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analyses"
    __table_args__ = (sa.Index("ix_analyses_fingerprint", "fingerprint"),)

    product_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    # Hash of (normalised query, warranty years, warranty price, currency).
    fingerprint: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    query: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    warranty_years: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    warranty_price: Mapped[float] = mapped_column(sa.Float, nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), default="EUR", nullable=False)

    verdict: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    expected_repair_cost: Mapped[float] = mapped_column(sa.Float, nullable=False)
    average_repair_cost: Mapped[float] = mapped_column(sa.Float, nullable=False)
    worst_case_repair_cost: Mapped[float] = mapped_column(sa.Float, nullable=False)
    failure_probability: Mapped[float] = mapped_column(sa.Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    evidence_level: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    payload: Mapped[dict] = mapped_column(JSONColumn, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, index=True
    )

    product: Mapped[Product | None] = relationship(back_populates="analyses")
    searches: Mapped[list["SearchHistory"]] = relationship(back_populates="analysis")


class SearchHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "search_history"

    user_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Anonymous visitors get a client-generated session id so history still works.
    session_id: Mapped[str | None] = mapped_column(sa.String(64), index=True)
    analysis_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("analyses.id", ondelete="SET NULL"), index=True
    )
    query: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    warranty_years: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    warranty_price: Mapped[float] = mapped_column(sa.Float, nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), default="EUR", nullable=False)

    user: Mapped[User | None] = relationship(back_populates="searches")
    analysis: Mapped[Analysis | None] = relationship(back_populates="searches")
