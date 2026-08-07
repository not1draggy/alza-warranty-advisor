"""Initial schema: products, evidence, repair economics, analyses, users.

Revision ID: 0001
Revises:
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op
from app.core.config import get_settings

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = get_settings().embedding_dimensions


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "manufacturers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_manufacturers_slug", "manufacturers", ["slug"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "manufacturer_id",
            sa.String(36),
            sa.ForeignKey("manufacturers.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "category_id", sa.String(36), sa.ForeignKey("categories.id", ondelete="SET NULL")
        ),
        sa.Column("lookup_key", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("model_number", sa.String(160)),
        sa.Column("release_year", sa.Integer()),
        sa.Column("specifications", sa.JSON(), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("identification_confidence", sa.Float(), nullable=False, server_default="0"),
        *_timestamps(),
    )
    op.create_index("ix_products_lookup_key", "products", ["lookup_key"], unique=True)
    op.create_index("ix_products_model_number", "products", ["model_number"])

    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("source_type", sa.String(48), nullable=False, server_default="unknown"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_sources_url_hash", "sources", ["url_hash"], unique=True)
    op.create_index("ix_sources_domain", "sources", ["domain"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(36),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(512)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("language", sa.String(8)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_product_id", "documents", ["product_id"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"], unique=True)

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
        *_timestamps(),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_product_id", "document_chunks", ["product_id"])
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "failure_modes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("component", sa.String(160)),
        sa.Column("description", sa.Text()),
        sa.Column("annual_probability", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "probability_is_estimated", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("repair_difficulty", sa.String(32)),
        sa.Column("typical_repair_days", sa.Float()),
        sa.Column("parts_availability", sa.String(32)),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.UniqueConstraint("product_id", "slug", name="uq_failure_mode_product_slug"),
    )
    op.create_index("ix_failure_modes_product_id", "failure_modes", ["product_id"])

    op.create_table(
        "repair_cost_estimates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "failure_mode_id",
            sa.String(36),
            sa.ForeignKey("failure_modes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("parts_cost", sa.Float()),
        sa.Column("labor_cost", sa.Float()),
        sa.Column("diagnostic_fee", sa.Float()),
        sa.Column("total_min", sa.Float(), nullable=False),
        sa.Column("total_typical", sa.Float(), nullable=False),
        sa.Column("total_max", sa.Float(), nullable=False),
        sa.Column("is_estimated", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.Text()),
        *_timestamps(),
    )
    op.create_index(
        "ix_repair_cost_estimates_failure_mode_id", "repair_cost_estimates", ["failure_mode_id"]
    )
    op.create_index("ix_repair_cost_estimates_source_id", "repair_cost_estimates", ["source_id"])

    op.create_table(
        "failure_mode_citations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "failure_mode_id",
            sa.String(36),
            sa.ForeignKey("failure_modes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.String(36),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quote", sa.Text()),
        *_timestamps(),
        sa.UniqueConstraint("failure_mode_id", "source_id", name="uq_citation_mode_source"),
    )
    op.create_index(
        "ix_failure_mode_citations_failure_mode_id", "failure_mode_citations", ["failure_mode_id"]
    )
    op.create_index("ix_failure_mode_citations_source_id", "failure_mode_citations", ["source_id"])

    op.create_table(
        "analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("query", sa.String(512), nullable=False),
        sa.Column("warranty_years", sa.Integer(), nullable=False),
        sa.Column("warranty_price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("expected_repair_cost", sa.Float(), nullable=False),
        sa.Column("average_repair_cost", sa.Float(), nullable=False),
        sa.Column("worst_case_repair_cost", sa.Float(), nullable=False),
        sa.Column("failure_probability", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_level", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_analyses_fingerprint", "analyses", ["fingerprint"])
    op.create_index("ix_analyses_product_id", "analyses", ["product_id"])
    op.create_index("ix_analyses_expires_at", "analyses", ["expires_at"])

    op.create_table(
        "search_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_id", sa.String(64)),
        sa.Column("analysis_id", sa.String(36), sa.ForeignKey("analyses.id", ondelete="SET NULL")),
        sa.Column("query", sa.String(512), nullable=False),
        sa.Column("warranty_years", sa.Integer(), nullable=False),
        sa.Column("warranty_price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        *_timestamps(),
    )
    op.create_index("ix_search_history_user_id", "search_history", ["user_id"])
    op.create_index("ix_search_history_session_id", "search_history", ["session_id"])
    op.create_index("ix_search_history_analysis_id", "search_history", ["analysis_id"])


def downgrade() -> None:
    op.drop_table("search_history")
    op.drop_table("analyses")
    op.drop_table("failure_mode_citations")
    op.drop_table("repair_cost_estimates")
    op.drop_table("failure_modes")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("sources")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("manufacturers")
    op.drop_table("users")
