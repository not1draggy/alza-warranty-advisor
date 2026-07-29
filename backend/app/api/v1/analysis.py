"""Warranty analysis endpoints — synchronous and server-sent-event streaming."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    OptionalUserDep,
    OrchestratorDep,
    RateLimitDep,
    SessionDep,
)
from app.core.errors import AppError, NotFound
from app.core.logging import get_logger
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisStage,
    HistoryEntry,
    HistoryPage,
)
from app.schemas.common import Verdict
from app.services import repository

logger = get_logger(__name__)
router = APIRouter(tags=["analysis"])


@router.post(
    "/analyses",
    response_model=AnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Analyse whether an extended warranty is worth buying",
)
async def create_analysis(
    payload: AnalysisRequest,
    orchestrator: OrchestratorDep,
    user: OptionalUserDep,
    _: RateLimitDep,
) -> AnalysisResult:
    return await orchestrator.analyze(payload, user_id=user.id if user else None)


@router.post(
    "/analyses/stream",
    summary="Analyse with live progress (Server-Sent Events)",
    response_class=StreamingResponse,
)
async def stream_analysis(
    payload: AnalysisRequest,
    orchestrator: OrchestratorDep,
    user: OptionalUserDep,
    _: RateLimitDep,
) -> StreamingResponse:
    async def event_source() -> AsyncIterator[bytes]:
        try:
            async for event in orchestrator.stream(payload, user_id=user.id if user else None):
                if isinstance(event, AnalysisStage):
                    yield _sse("stage", event.model_dump(mode="json"))
                else:
                    yield _sse("result", event.model_dump(mode="json"))
        except AppError as exc:
            yield _sse("error", {"code": exc.code, "message": exc.message})
        except Exception:  # the stream must always terminate cleanly
            logger.exception("analysis_stream_failed")
            yield _sse(
                "error",
                {"code": "internal_error", "message": "The analysis could not be completed."},
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisResult,
    summary="Fetch a previously generated analysis",
)
async def read_analysis(analysis_id: str, session: SessionDep) -> AnalysisResult:
    record = await repository.get_analysis(session, analysis_id)
    if record is None:
        raise NotFound("No analysis with that id exists.")
    result = AnalysisResult.model_validate(record.payload)
    result.from_cache = True
    return result


@router.get("/history", response_model=HistoryPage, summary="Recent searches")
async def read_history(
    session: SessionDep,
    user: OptionalUserDep,
    session_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> HistoryPage:
    rows, total = await repository.list_history(
        session,
        user_id=user.id if user else None,
        session_id=None if user else session_id,
        limit=limit,
        offset=offset,
    )
    items = [
        HistoryEntry(
            id=entry.id,
            created_at=entry.created_at,
            query=entry.query,
            warranty_years=entry.warranty_years,
            warranty_price=entry.warranty_price,
            currency=entry.currency,
            analysis_id=entry.analysis_id,
            verdict=Verdict(analysis.verdict) if analysis else None,
            risk_score=analysis.risk_score if analysis else None,
            confidence=analysis.confidence if analysis else None,
            product_name=product.display_name if product else None,
        )
        for entry, analysis, product in rows
    ]
    return HistoryPage(items=items, total=total)


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()
