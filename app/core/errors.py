"""
Consistent Error Handling for Enterprise API

Structured error responses for clients and SIEM.
"""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_response(
    status_code: int,
    detail: str,
    error_code: str | None = None,
    correlation_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a consistent error payload."""
    body: dict[str, Any] = {
        "detail": detail,
        "status": status_code,
    }
    if error_code:
        body["error_code"] = error_code
    if correlation_id:
        body["correlation_id"] = correlation_id
    if extra:
        body.update(extra)
    return body


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch exceptions and return structured error. Preserves FastAPI defaults for validation."""
    correlation_id = getattr(request.state, "correlation_id", None)
    status_code = 500
    detail = "An internal error occurred. Please try again later."
    error_code = "INTERNAL_ERROR"

    if isinstance(exc, RequestValidationError):
        # Preserve FastAPI validation error format
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "status": 422, "correlation_id": correlation_id},
        )

    if hasattr(exc, "status_code") and hasattr(exc, "detail"):
        status_code = exc.status_code
        d = exc.detail
        detail = d if isinstance(d, str) else (d.get("detail", str(d)) if isinstance(d, dict) else str(d))
        error_code = "HTTP_ERROR"

    body = error_response(status_code, detail, error_code, correlation_id)
    return JSONResponse(status_code=status_code, content=body)
