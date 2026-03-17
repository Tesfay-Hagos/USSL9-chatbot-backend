"""
Prometheus Metrics for ULSS 9 Chatbot

Exposes /metrics endpoint for Prometheus scraping. Includes:
- HTTP request count and latency (by method, path, status)
- Chat-specific metrics (corrections applied, stores used)
- System info (startup time, version)
"""

import time

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Custom registry (avoids default process/platform collectors in tests)
REGISTRY = CollectorRegistry()

# ── HTTP Metrics ──

HTTP_REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status_code"],
    registry=REGISTRY,
)

HTTP_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path_template"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY,
)

# ── Chat Metrics ──

CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total chat requests processed",
    ["domain", "language"],
    registry=REGISTRY,
)

CHAT_CORRECTIONS_APPLIED = Counter(
    "chat_corrections_applied_total",
    "Total times a correction was returned instead of RAG",
    registry=REGISTRY,
)

CHAT_RAG_LATENCY = Histogram(
    "chat_rag_duration_seconds",
    "Chat RAG processing latency",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=REGISTRY,
)

# ── System ──

APP_INFO = Info(
    "ulss9_chatbot",
    "Application metadata",
    registry=REGISTRY,
)
APP_INFO.info({"version": "2.2.0", "environment": "production"})

ACTIVE_REQUESTS = Gauge(
    "http_active_requests",
    "Number of in-flight HTTP requests",
    registry=REGISTRY,
)


def _normalise_path(path: str) -> str:
    """
    Normalise request path for metrics labels.

    Groups dynamic segments (UUIDs, IDs) to prevent label explosion.
    Example: /api/v1/admin/stores/general_info/health → /api/v1/admin/stores/{domain}/health
    """
    parts = path.strip("/").split("/")
    normalised = []
    skip_next = False
    for i, part in enumerate(parts):
        if skip_next:
            skip_next = False
            continue
        if part in ("stores", "corrections", "documents") and i + 1 < len(parts):
            normalised.append(part)
            normalised.append(f"{{{part[:-1]}}}")  # {store}, {correction}, {document}
            skip_next = True
        else:
            normalised.append(part)
    return "/" + "/".join(normalised)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        ACTIVE_REQUESTS.inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.perf_counter() - start
            path = _normalise_path(request.url.path)
            method = request.method

            HTTP_REQUEST_COUNT.labels(
                method=method, path_template=path, status_code=status
            ).inc()
            HTTP_REQUEST_LATENCY.labels(
                method=method, path_template=path
            ).observe(duration)
            ACTIVE_REQUESTS.dec()

        return response


async def metrics_endpoint(request: Request) -> Response:
    """Prometheus-compatible /metrics endpoint."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
