"""Application entry point."""

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger, request_id_var
from app.core.rate_limit import RateLimiter
from app.db.session import dispose_engine
from app.services.cache import Cache
from app.services.embeddings import EmbeddingService
from app.services.llm.registry import build_llm_router
from app.services.search.registry import build_search_router

logger = get_logger(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, logs the outcome and applies security headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["x-request-id"] = request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_production)

    redis: Redis | None = None
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
    except Exception as exc:  # Redis is an optimisation, not a hard dependency
        logger.warning("redis_unavailable", error=str(exc))
        redis = None

    http_client = httpx.AsyncClient(
        timeout=settings.search_timeout_seconds,
        headers={"User-Agent": "WarrantyAdvisor/1.0 (+https://alza.cz)"},
        follow_redirects=True,
    )

    cache = Cache(redis)
    app.state.settings = settings
    app.state.redis = redis
    app.state.cache = cache
    app.state.http_client = http_client
    app.state.llm = build_llm_router(settings)
    app.state.search = build_search_router(settings, cache, http_client)
    app.state.embeddings = EmbeddingService(settings)
    app.state.rate_limiter = RateLimiter(
        redis,
        limit_per_minute=settings.rate_limit_per_minute,
        burst=settings.rate_limit_burst,
    )

    logger.info(
        "startup",
        environment=settings.environment,
        llm_providers=app.state.llm.provider_names,
        search_providers=app.state.search.provider_names,
        embeddings=app.state.embeddings.configured,
        cache=cache.available,
    )

    try:
        yield
    finally:
        await http_client.aclose()
        if redis is not None:
            await redis.aclose()
        await dispose_engine()
        logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_production)

    app = FastAPI(
        title=settings.project_name,
        version="1.0.0",
        description=(
            "Estimates the financial risk of owning a product after the manufacturer's "
            "warranty expires, so a customer can decide whether an extension is worth it."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
