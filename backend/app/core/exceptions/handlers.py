"""Custom exception hierarchy and FastAPI exception handlers.

All application-level errors inherit from :class:`AppException` so they can be
caught by a single handler and serialised into a consistent JSON envelope.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

# ── Base Exception ────────────────────────────────────────────────────────


class AppException(Exception):  # noqa: N818  # established public base-exception name across the codebase
    """Base exception for all domain / application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        detail: str = "An unexpected error occurred",
        *,
        error_code: str | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail
        if error_code is not None:
            self.error_code = error_code
        self.headers = headers
        self.extra = extra or {}
        super().__init__(self.detail)


# ── Concrete Exceptions ──────────────────────────────────────────────────


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"

    def __init__(self, resource: str = "Resource", detail: str | None = None, **kw: Any) -> None:
        super().__init__(detail or f"{resource} not found", **kw)


class UnauthorizedError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "UNAUTHORIZED"

    def __init__(self, detail: str = "Authentication required", **kw: Any) -> None:
        super().__init__(detail, headers={"WWW-Authenticate": "Bearer"}, **kw)


class ForbiddenError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"

    def __init__(self, detail: str = "Permission denied", **kw: Any) -> None:
        super().__init__(detail, **kw)


class ValidationError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"

    def __init__(self, detail: str = "Validation failed", **kw: Any) -> None:
        super().__init__(detail, **kw)


class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"

    def __init__(self, detail: str = "Resource already exists", **kw: Any) -> None:
        super().__init__(detail, **kw)


class RateLimitError(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(
        self, detail: str = "Too many requests, please try again later", **kw: Any
    ) -> None:
        super().__init__(detail, **kw)


class PaymentError(AppException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    error_code = "PAYMENT_ERROR"

    def __init__(self, detail: str = "Payment processing failed", **kw: Any) -> None:
        super().__init__(detail, **kw)


# ── Handlers ──────────────────────────────────────────────────────────────


def _error_response(
    status_code: int,
    error_code: str,
    detail: str,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "success": False,
        "error": {
            "code": error_code,
            "message": detail,
        },
    }
    if extra:
        body["error"]["details"] = extra
    return JSONResponse(status_code=status_code, content=body, headers=headers)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        detail=exc.detail,
        extra=exc.extra,
        headers=exc.headers,
    )


async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = []
    for err in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        detail="Request validation failed",
        extra={"errors": errors},
    )


async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    import structlog

    logger = structlog.get_logger()
    await logger.aerror("unhandled_exception", exc_type=type(exc).__name__, detail=str(exc))
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_ERROR",
        detail="An unexpected internal error occurred",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)  # type: ignore[arg-type]


async def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        error_code="RATE_LIMIT_EXCEEDED",
        detail=f"تعداد درخواست‌ها بیش از حد مجاز است: {exc.detail}",
        headers={"Retry-After": "60"},
    )
