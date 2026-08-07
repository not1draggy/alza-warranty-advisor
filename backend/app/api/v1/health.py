"""Liveness, readiness and capability reporting."""

from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Response, status

from app.api.deps import CacheDep, EmbeddingsDep, LLMDep, SearchDep, SessionDep, SettingsDep

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
async def ready(session: SessionDep, cache: CacheDep, response: Response) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    try:
        await session.execute(sa.text("SELECT 1"))
        checks["database"] = True
    except Exception:  # readiness reports, it does not raise
        checks["database"] = False
    checks["cache"] = await cache.ping()

    ready_now = checks["database"]
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready_now else "degraded", "checks": checks}


@router.get("/capabilities", summary="Which providers are configured")
async def capabilities(
    settings: SettingsDep,
    llm: LLMDep,
    search: SearchDep,
    embeddings: EmbeddingsDep,
) -> dict[str, Any]:
    """Lets the UI tell the user honestly what the system can and cannot do.

    Reports provider names only — never keys.
    """
    return {
        "environment": settings.environment,
        "llm": {"configured": llm.configured, "providers": llm.provider_names},
        "search": {"configured": search.configured, "providers": search.provider_names},
        "embeddings": {"configured": embeddings.configured},
        "analysis_available": llm.configured and search.configured,
    }
