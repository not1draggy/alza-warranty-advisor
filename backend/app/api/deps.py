"""FastAPI dependency wiring."""

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.composer import ComposerAgent
from app.agents.evidence import EvidenceAgent
from app.agents.extraction import ExtractionAgent
from app.agents.identify import IdentificationAgent
from app.agents.orchestrator import AnalysisOrchestrator, OrchestratorDeps
from app.core.config import Settings, get_settings
from app.core.errors import RateLimited, Unauthorized
from app.core.rate_limit import RateLimiter
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db_session
from app.services.cache import Cache
from app.services.embeddings import EmbeddingService
from app.services.llm.registry import LLMRouter
from app.services.rag import RagStore
from app.services.search.registry import SearchRouter

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_cache(request: Request) -> Cache:
    return request.app.state.cache


def get_llm(request: Request) -> LLMRouter:
    return request.app.state.llm


def get_search(request: Request) -> SearchRouter:
    return request.app.state.search


def get_embeddings(request: Request) -> EmbeddingService:
    return request.app.state.embeddings


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


CacheDep = Annotated[Cache, Depends(get_cache)]
LLMDep = Annotated[LLMRouter, Depends(get_llm)]
SearchDep = Annotated[SearchRouter, Depends(get_search)]
EmbeddingsDep = Annotated[EmbeddingService, Depends(get_embeddings)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def client_identity(request: Request) -> str:
    """Best-effort caller identity for rate limiting."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "anonymous"


async def enforce_rate_limit(request: Request, limiter: RateLimiterDep, scope: str = "api") -> None:
    decision = await limiter.check(client_identity(request), scope)
    if not decision.allowed:
        raise RateLimited(
            "Too many requests. Please wait a moment before trying again.",
            details={"retry_after_seconds": decision.retry_after_seconds},
        )


RateLimitDep = Annotated[None, Depends(enforce_rate_limit)]


async def optional_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """Resolve the caller when a bearer token is present; anonymous otherwise."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    payload = decode_access_token(token)
    user = await session.get(User, payload.get("sub", ""))
    if user is None or not user.is_active:
        return None
    return user


async def current_user(
    user: Annotated[User | None, Depends(optional_user)],
) -> User:
    if user is None:
        raise Unauthorized("Sign in to use this endpoint.")
    return user


OptionalUserDep = Annotated[User | None, Depends(optional_user)]
CurrentUserDep = Annotated[User, Depends(current_user)]


def get_orchestrator(
    session: SessionDep,
    settings: SettingsDep,
    cache: CacheDep,
    llm: LLMDep,
    search: SearchDep,
    embeddings: EmbeddingsDep,
) -> AnalysisOrchestrator:
    return AnalysisOrchestrator(
        OrchestratorDeps(
            identification=IdentificationAgent(llm, cache),
            evidence=EvidenceAgent(llm, search),
            extraction=ExtractionAgent(llm),
            composer=ComposerAgent(llm),
            rag=RagStore(session, embeddings),
            session=session,
            settings=settings,
        )
    )


OrchestratorDep = Annotated[AnalysisOrchestrator, Depends(get_orchestrator)]
