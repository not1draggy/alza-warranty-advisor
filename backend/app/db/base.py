"""Declarative base and shared column types."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

# JSONB on PostgreSQL, plain JSON elsewhere (tests).
JSONColumn = JSONB().with_variant(sa.JSON(), "sqlite")

# pgvector on PostgreSQL, JSON elsewhere. Vector search is guarded by dialect.
EmbeddingColumn = Vector(get_settings().embedding_dimensions).with_variant(sa.JSON(), "sqlite")


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=new_uuid)
