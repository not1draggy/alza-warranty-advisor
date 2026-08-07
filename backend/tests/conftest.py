"""Test fixtures.

Integration tests run against SQLite so the suite needs no external services. The
model layer declares SQLite variants for the JSONB and pgvector columns, so the same
mappings are exercised; only vector similarity search is Postgres-only and it has a
keyword fallback that the tests cover instead.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app
from app.services.cache import Cache
from app.services.embeddings import EmbeddingService
from app.services.llm.registry import LLMRouter
from app.services.search.registry import SearchRouter
from tests.fakes import FakeLLM, FakeSearchProvider


@pytest.fixture
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_search_results() -> list[dict]:
    return []


@pytest.fixture
async def client(engine, settings, fake_llm, fake_search_results) -> AsyncIterator[AsyncClient]:
    app = create_app()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = override_session

    cache = Cache(None)
    http_client = httpx.AsyncClient()
    app.state.settings = settings
    app.state.redis = None
    app.state.cache = cache
    app.state.http_client = http_client
    app.state.llm = LLMRouter([fake_llm])
    app.state.search = SearchRouter(
        [FakeSearchProvider(fake_search_results)], cache, ttl_seconds=60, max_results=20
    )
    app.state.embeddings = EmbeddingService(settings)
    app.state.rate_limiter = RateLimiter(None, limit_per_minute=1000, burst=100)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    await http_client.aclose()
