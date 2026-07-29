"""Retrieval-augmented generation store.

Documents are chunked, embedded once and reused. Retrieval prefers pgvector cosine
similarity and falls back to keyword matching when embeddings are unavailable, so
the pipeline still works without an embedding provider.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.db.models import Document, DocumentChunk, Source
from app.schemas.common import SourceType
from app.services.embeddings import EmbeddingService

logger = get_logger(__name__)

CHUNK_CHARS = 1400
CHUNK_OVERLAP = 180
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9€$]+")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def chunk_text(text: str, *, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split on sentence boundaries, packing up to `size` characters per chunk."""
    normalized = " ".join(text.split())
    if not normalized:
        return []
    if len(normalized) <= size:
        return [normalized]

    sentences = _SENTENCE_BREAK.split(normalized)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {sentence}".strip()
        else:
            # A single sentence longer than the window: hard-split it.
            for start in range(0, len(sentence), size):
                chunks.append(sentence[start : start + size])
            current = ""
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk]


@dataclass(slots=True)
class RetrievedChunk:
    content: str
    score: float
    source_url: str
    source_domain: str
    source_title: str | None
    source_type: SourceType
    quality_score: float
    retrieved_at: datetime


@dataclass(slots=True)
class DocumentInput:
    url: str
    domain: str
    title: str | None
    content: str
    source_type: SourceType
    quality_score: float
    published_at: datetime | None = None


class RagStore:
    def __init__(self, session: AsyncSession, embeddings: EmbeddingService) -> None:
        self._session = session
        self._embeddings = embeddings

    @property
    def _is_postgres(self) -> bool:
        return self._session.bind is not None and self._session.bind.dialect.name == "postgresql"

    async def ingest(
        self, documents: list[DocumentInput], *, product_id: str | None
    ) -> list[Source]:
        """Persist sources, documents and chunks; embed anything not yet embedded."""
        if not documents:
            return []

        now = datetime.now(UTC)
        stored_sources: list[Source] = []
        pending_chunks: list[DocumentChunk] = []

        for doc in documents:
            url_hash = sha256(doc.url)
            source = await self._session.scalar(
                sa.select(Source).where(Source.url_hash == url_hash)
            )
            if source is None:
                source = Source(
                    url=doc.url[:2048],
                    url_hash=url_hash,
                    domain=doc.domain[:255],
                    title=(doc.title or "")[:512] or None,
                    source_type=doc.source_type.value,
                    quality_score=doc.quality_score,
                    published_at=doc.published_at,
                    retrieved_at=now,
                )
                self._session.add(source)
                await self._session.flush()
            else:
                source.quality_score = doc.quality_score
                source.source_type = doc.source_type.value
                source.retrieved_at = now
            stored_sources.append(source)

            content_hash = sha256(doc.content)
            document = await self._session.scalar(
                sa.select(Document).where(Document.content_hash == content_hash)
            )
            if document is not None:
                if product_id and document.product_id is None:
                    document.product_id = product_id
                continue

            document = Document(
                source_id=source.id,
                product_id=product_id,
                title=(doc.title or "")[:512] or None,
                content=doc.content,
                content_hash=content_hash,
                retrieved_at=now,
            )
            self._session.add(document)
            await self._session.flush()

            for ordinal, chunk in enumerate(chunk_text(doc.content)):
                record = DocumentChunk(
                    document_id=document.id,
                    product_id=product_id,
                    ordinal=ordinal,
                    content=chunk,
                )
                self._session.add(record)
                pending_chunks.append(record)

        await self._embed_chunks(pending_chunks)
        await self._session.flush()
        return stored_sources

    async def _embed_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not chunks or not self._embeddings.configured:
            return
        try:
            vectors = await self._embeddings.embed([chunk.content for chunk in chunks])
        except ProviderUnavailable as exc:
            logger.warning("embedding_skipped", error=str(exc))
            return
        for chunk, vector in zip(chunks, vectors, strict=False):
            chunk.embedding = vector

    async def retrieve(
        self, query: str, *, product_id: str | None, limit: int = 12
    ) -> list[RetrievedChunk]:
        vector = None
        if self._embeddings.configured and self._is_postgres:
            try:
                vector = await self._embeddings.embed_one(query)
            except ProviderUnavailable as exc:
                logger.warning("retrieval_embedding_failed", error=str(exc))

        if vector is not None:
            rows = await self._vector_search(vector, product_id=product_id, limit=limit)
            if rows:
                return rows
        return await self._keyword_search(query, product_id=product_id, limit=limit)

    async def _vector_search(
        self, vector: list[float], *, product_id: str | None, limit: int
    ) -> list[RetrievedChunk]:
        distance = DocumentChunk.embedding.cosine_distance(vector).label("distance")
        stmt = (
            sa.select(DocumentChunk, Source, distance)
            .join(Document, Document.id == DocumentChunk.document_id)
            .join(Source, Source.id == Document.source_id)
            .where(DocumentChunk.embedding.isnot(None))
            .order_by(distance)
            .limit(limit)
        )
        if product_id:
            stmt = stmt.where(DocumentChunk.product_id == product_id)
        result = await self._session.execute(stmt)
        return [
            _to_retrieved(chunk, source, max(0.0, 1.0 - float(dist)))
            for chunk, source, dist in result.all()
        ]

    async def _keyword_search(
        self, query: str, *, product_id: str | None, limit: int
    ) -> list[RetrievedChunk]:
        terms = {word for word in _WORD.findall(query.lower()) if len(word) > 2}
        stmt = (
            sa.select(DocumentChunk, Source)
            .join(Document, Document.id == DocumentChunk.document_id)
            .join(Source, Source.id == Document.source_id)
            .order_by(Source.quality_score.desc())
            .limit(limit * 6)
        )
        if product_id:
            stmt = stmt.where(DocumentChunk.product_id == product_id)
        rows = (await self._session.execute(stmt)).all()

        scored: list[RetrievedChunk] = []
        for chunk, source in rows:
            content_words = set(_WORD.findall(chunk.content.lower()))
            overlap = len(terms & content_words) / len(terms) if terms else 0.0
            score = 0.6 * overlap + 0.4 * source.quality_score
            if score > 0:
                scored.append(_to_retrieved(chunk, source, round(score, 4)))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]


def _to_retrieved(chunk: DocumentChunk, source: Source, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        content=chunk.content,
        score=score,
        source_url=source.url,
        source_domain=source.domain,
        source_title=source.title,
        source_type=SourceType(source.source_type),
        quality_score=source.quality_score,
        retrieved_at=source.retrieved_at,
    )
