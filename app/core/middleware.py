"""
Enterprise Middleware: Correlation ID, Rate Limiting, Security Headers,
Session Token, Request Size Limit.

Production-ready middleware stack for EU government deployment.
"""

import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import (
    MAX_REQUEST_SIZE,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    TRUST_PROXY,
)

logger = logging.getLogger(__name__)

# In-memory rate limit store (use Redis in multi-instance deployments)
_rate_store: dict[str, list[float]] = defaultdict(list)

# Paths that require session token validation (public API endpoints)
SESSION_TOKEN_PATHS = {"/api/v1/chat"}

# Paths exempt from session token validation
SESSION_TOKEN_EXEMPT = {
    "/api/v1/session-token",
    "/api/v1/auth/login",
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
}


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting proxy headers if configured."""
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
    return request.client.host if request.client else "unknown"


def _rate_limit_exceeded(ip: str) -> bool:
    """Check if IP has exceeded rate limit."""
    if RATE_LIMIT_REQUESTS <= 0:
        return False
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    # Prune old entries
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(_rate_store[ip]) >= RATE_LIMIT_REQUESTS:
        return True
    _rate_store[ip].append(now)
    return False


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Add X-Correlation-ID to requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting per IP."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = _get_client_ip(request)
        if _rate_limit_exceeded(ip):
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers for European government deployment (OWASP + HSTS)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # XSS protection
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Referrer policy (privacy)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS — enforce HTTPS (2 years, include subdomains)
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains"
        )
        # Prevent Adobe cross-domain policy files
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        # Content Security Policy (relaxed for API; tighten for HTML)
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com;"
            )
        return response


class SessionTokenMiddleware(BaseHTTPMiddleware):
    """
    Validate X-Session-Token header on public chat endpoints.

    Admin endpoints use JWT via require_admin dependency, so they are exempt.
    The session token is an HMAC-signed stateless token issued by /api/v1/session-token.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path.rstrip("/")

        # Only validate on public API paths that need it
        needs_validation = path in SESSION_TOKEN_PATHS

        if needs_validation and request.method != "OPTIONS":
            token = request.headers.get("x-session-token")
            if not token:
                return Response(
                    content='{"detail":"Missing session token. Call POST /api/v1/session-token first."}',
                    status_code=401,
                    media_type="application/json",
                )
            from app.api.session import validate_session_token

            if not validate_session_token(token):
                return Response(
                    content='{"detail":"Invalid or expired session token."}',
                    status_code=401,
                    media_type="application/json",
                )

        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Reject requests with bodies exceeding MAX_REQUEST_SIZE.

    Prevents abuse via oversized uploads or payloads.
    File uploads via /admin/stores/{domain}/upload have an elevated limit (50MB).
    """

    UPLOAD_PATHS = {"/upload"}  # Substrings matched against path

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            path = request.url.path

            # Allow larger uploads for file upload endpoints
            is_upload = any(p in path for p in self.UPLOAD_PATHS)
            limit = MAX_REQUEST_SIZE * 5 if is_upload else MAX_REQUEST_SIZE

            if size > limit:
                logger.warning(
                    "Request body too large",
                    extra={"size": size, "limit": limit, "path": path},
                )
                return Response(
                    content='{"detail":"Request body too large."}',
                    status_code=413,
                    media_type="application/json",
                )

        return await call_next(request)

