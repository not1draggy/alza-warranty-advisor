"""Typed application errors and the handlers that render them as JSON."""

from enum import StrEnum

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_var

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for errors that map onto a stable API error code."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: dict | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"
    message = "The request could not be validated."


class UnsafeInput(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "unsafe_input"
    message = "The submitted text was rejected by the input guard."


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource does not exist."


class Unauthorized(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Authentication is required."


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The resource already exists."


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down."


class ProviderReason(StrEnum):
    """Why a provider call could not be made.

    A rejected key and an unreachable host both stop the analysis, but only one
    of them is fixed by editing the environment. Collapsing them into one
    message sends the operator looking in the wrong place.
    """

    NOT_CONFIGURED = "not_configured"  # no key set at all
    REJECTED_CREDENTIALS = "rejected_credentials"  # the key was refused
    MODEL_UNAVAILABLE = "model_unavailable"  # the key works, the model name does not
    QUOTA_EXHAUSTED = "quota_exhausted"  # billing or credit limit
    RATE_LIMITED = "rate_limited"  # transient, retry later
    UNREACHABLE = "unreachable"  # network or upstream outage
    BAD_RESPONSE = "bad_response"  # reached it, could not use the answer

    @property
    def is_configuration(self) -> bool:
        """True when an operator has to change something for this to work."""
        return self in {
            ProviderReason.NOT_CONFIGURED,
            ProviderReason.REJECTED_CREDENTIALS,
            ProviderReason.MODEL_UNAVAILABLE,
            ProviderReason.QUOTA_EXHAUSTED,
        }


class ProviderUnavailable(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "provider_unavailable"
    message = "An upstream provider is not configured or not reachable."

    def __init__(
        self,
        message: str | None = None,
        *,
        reason: ProviderReason = ProviderReason.UNREACHABLE,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.reason = reason


def _payload(code: str, message: str, details: dict | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    request_id = request_id_var.get()
    if request_id:
        body["error"]["request_id"] = request_id
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app_error", code=exc.code, message=exc.message)
        else:
            logger.info("app_error", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code, content=_payload(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"field": ".".join(str(part) for part in err["loc"][1:]), "reason": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_payload(
                "validation_failed", "One or more fields are invalid.", {"fields": fields}
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found"}.get(
            exc.status_code, "http_error"
        )
        return JSONResponse(status_code=exc.status_code, content=_payload(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_payload("internal_error", "An unexpected error occurred."),
        )
