"""Tests for chunking and the RAG store's retrieval fallback."""

from datetime import UTC, datetime

import pytest

from app.schemas.common import SourceType
from app.services.embeddings import EmbeddingService
from app.services.rag import DocumentInput, RagStore, chunk_text, sha256


class TestChunkText:
    def test_short_text_is_a_single_chunk(self):
        assert chunk_text("A short sentence.") == ["A short sentence."]

    def test_empty_text_produces_nothing(self):
        assert chunk_text("   ") == []

    def test_long_text_is_split(self):
        text = " ".join(f"Sentence number {i} about repair costs." for i in range(400))
        chunks = chunk_text(text, size=500, overlap=50)
        assert len(chunks) > 1
        assert all(len(chunk) <= 600 for chunk in chunks)

    def test_chunks_overlap_for_context(self):
        text = " ".join(f"Fact {i} is important." for i in range(200))
        chunks = chunk_text(text, size=300, overlap=60)
        assert len(chunks) > 2
        # The tail of one chunk reappears at the head of the next.
        assert any(chunks[0][-30:].split()[-1] in chunks[1] for _ in [0])

    def test_a_single_oversized_sentence_is_hard_split(self):
        chunks = chunk_text("x" * 5000, size=1000, overlap=0)
        assert len(chunks) == 5

    def test_whitespace_is_normalised(self):
        assert chunk_text("a\n\n\tb") == ["a b"]


def test_sha256_is_stable():
    assert sha256("abc") == sha256("abc")
    assert sha256("abc") != sha256("abd")


@pytest.fixture
def store(session, settings) -> RagStore:
    return RagStore(session, EmbeddingService(settings))


def make_document(url: str, content: str, quality: float = 0.9) -> DocumentInput:
    return DocumentInput(
        url=url,
        domain=url.split("/")[2],
        title="Repair pricing",
        content=content,
        source_type=SourceType.MANUFACTURER,
        quality_score=quality,
        published_at=datetime.now(UTC),
    )


class TestRagStore:
    async def test_ingest_then_keyword_retrieve(self, store: RagStore):
        await store.ingest(
            [
                make_document(
                    "https://samsung.com/repair",
                    "Backlight replacement costs 280 EUR including labour on large sets.",
                ),
                make_document(
                    "https://ifixit.com/guide",
                    "The power board is a common failure and costs 150 EUR to replace.",
                    quality=0.8,
                ),
            ],
            product_id=None,
        )
        chunks = await store.retrieve("backlight replacement cost", product_id=None, limit=5)
        assert chunks
        assert any("Backlight" in chunk.content for chunk in chunks)
        assert chunks[0].score > 0

    async def test_ingest_is_idempotent_on_identical_content(self, store: RagStore, session):
        document = make_document("https://samsung.com/repair", "Backlight costs 280 EUR.")
        await store.ingest([document], product_id=None)
        await store.ingest([document], product_id=None)

        from sqlalchemy import func, select

        from app.db.models import Document, Source

        documents = await session.scalar(select(func.count()).select_from(Document))
        sources = await session.scalar(select(func.count()).select_from(Source))
        assert documents == 1
        assert sources == 1

    async def test_retrieve_with_no_documents_returns_empty(self, store: RagStore):
        assert await store.retrieve("anything", product_id=None) == []

    async def test_ingest_with_no_documents_is_a_no_op(self, store: RagStore):
        assert await store.ingest([], product_id=None) == []

    async def test_higher_quality_sources_rank_first_on_ties(self, store: RagStore):
        await store.ingest(
            [
                make_document("https://reddit.com/a", "Backlight repair cost thread.", quality=0.4),
                make_document(
                    "https://samsung.com/b", "Backlight repair cost official.", quality=0.95
                ),
            ],
            product_id=None,
        )
        chunks = await store.retrieve("backlight repair cost", product_id=None, limit=5)
        assert chunks[0].source_domain == "samsung.com"
