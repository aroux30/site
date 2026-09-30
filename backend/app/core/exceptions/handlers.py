"""Custom exception hierarchy and FastAPI exception handlers.

All application-level errors inherit from :class:`AppException` so they can be
caught by a single handler and serialised into a consistent JSON envelope.
"""

from __future__ import annotations

import time
from collections import deque
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

    # Whether this pause is warranted is the whole question, because the cost of
    # pausing is a 503 for every visitor on every path for an hour (240, then
    # 1440, on repeat). A single unhandled exception inside one request is NOT
    # evidence of that: the process is alive, its dependencies answered, and
    # every other route still works. WordPress's equivalent pauses the failing
    # plugin for the admin who triggered it, not the whole site.
    #
    # So only a genuine infrastructure failure pauses, and the signal is
    # repeated *distinct* 500s inside a short window — a flapping dependency or
    # a broken import, which a 503 page actually helps with. The first 500 is
    # logged and served; the storefront keeps taking orders.
    if _is_infrastructure_failure(exc):
        from app.core.exceptions.recovery_mode import RecoveryMode

        state = RecoveryMode.pause(reference=None)
        logger.aerror("recovery_mode_entered", reference=state.get("reference"))
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_ERROR",
        detail="An unexpected internal error occurred",
    )


#: Exception types that mean "the app itself is broken", not "this request was".
#: A database or Redis driver error fits: the next request will hit it too.
_INFRASTRUCTURE_FAILURE_NAMES: frozenset[str] = frozenset(
    {
        # Database is down, pool exhausted, or a statement cannot even be sent.
        "OperationalError",
        "InterfaceError",
        "ConnectionDoesNotExist",
        "ConnectionFailure",
        "CannotConnectNowError",
        "TooManyConnectionsError",
        # Redis (revocation denylist, cache, outbox locks) is unreachable.
        "ConnectionError",
        "RedisError",
        "TimeoutError",
        "RedisConnectionError",
    }
)

#: DBAPI subclasses that are the *request's* fault, not an outage. Every one of
#: them inherits ``DBAPIError``/``DatabaseError``, so they cannot be excluded
#: from the set above — the MRO walk would reinstate them through the parent.
#: They are checked first and win, because a duplicate key or a bad statement
#: is one endpoint's input handling: a single buggy import route must not be
#: able to pause the whole store by raising one of these 25 times.
_REQUEST_FAULT_DB_NAMES: frozenset[str] = frozenset(
    {
        "IntegrityError",  # duplicate key, FK violation, check violation
        "ProgrammingError",  # unknown column/table — a bad query in our code
        "DataError",  # value out of range for the column type
        "NotSupportedError",
    }
)

#: Rolling window and threshold for the escalation above.
_ERROR_BURST_WINDOW_SECONDS = 120
_ERROR_BURST_THRESHOLD = 25
#: Distinct exception types, so one endpoint failing 100 times does not count as
#: a burst if the rest of the site is healthy.
_ERROR_BURST_MIN_DISTINCT = 3

#: ``(monotonic timestamp, exception type name)``. A deque, not a dict keyed by
#: type: the count is what matters and old entries must expire. append/popleft
#: are atomic under the GIL and this runs on the event loop, so no lock.
_recent_errors: deque[tuple[float, str]] = deque()


def _is_infrastructure_failure(exc: Exception) -> bool:
    """Whether ``exc`` justifies pausing the site for an hour.

    Returns False for the common case, which is a bug in one handler: a bad
    attribute, a missing key, a failed response model. Those deserve a 500 on
    the endpoint that caused them and nothing more.
    """
    # A request-fault DB error is never infrastructure, no matter how many of
    # them accumulate. Checked before the MRO walk because these classes
    # inherit DBAPIError, which the walk would otherwise count as an outage.
    for base in type(exc).__mro__:
        if base.__name__ in _REQUEST_FAULT_DB_NAMES:
            return False

    # Walk the MRO rather than testing the concrete class: SQLAlchemy and
    # redis-py both wrap their drivers, so what a handler catches is rarely the
    # class named in the set. Written as an explicit loop because the shorter
    # ``any(...)`` form kept returning the wrong branch here, and a negated
    # rewrite of it was no better.
    is_infra = False
    for base in type(exc).__mro__:
        if base.__name__ in _INFRASTRUCTURE_FAILURE_NAMES:
            is_infra = True
            break
    if is_infra is False:
        return False

    # An infrastructure-class error is not automatically site-wide, so require
    # corroboration: more than one kind of failure, repeatedly, in a short
    # window. A single dropped connection during a rolling restart must not cost
    # the store an hour of 503s.
    now = time.monotonic()
    cutoff = now - _ERROR_BURST_WINDOW_SECONDS
    while _recent_errors and _recent_errors[0][0] < cutoff:
        _recent_errors.popleft()
    _recent_errors.append((now, type(exc).__name__))
    distinct = {name for _, name in _recent_errors}
    return len(_recent_errors) >= _ERROR_BURST_THRESHOLD and len(distinct) >= (
        _ERROR_BURST_MIN_DISTINCT
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application."""
    # Starlette types handler callbacks contravariantly as Callable[[Request, Exception], ...];
    # handlers taking a specific exception subclass are safe at runtime but rejected by mypy.
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)


async def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        error_code="RATE_LIMIT_EXCEEDED",
        detail=f"تعداد درخواست‌ها بیش از حد مجاز است: {exc.detail}",
        headers={"Retry-After": "60"},
    )
