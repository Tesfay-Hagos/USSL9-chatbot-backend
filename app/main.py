"""
ULSS 9 Chatbot — Enterprise FastAPI Application

Production-ready backend for European government deployment.
GDPR-aware, audit logging, structured logging, security headers, rate limiting,
HMAC session tokens, email OTP password reset, PostgreSQL-backed store registry,
corrections system, anonymised chat logs, Prometheus metrics, EU AI Act compliance.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import admin, auth, chat
from app.api.v1 import api_router
from app.config import (
    ALLOWED_ORIGINS,
    APP_ENV,
    CORS_ALLOW_CREDENTIALS,
    DEBUG,
    ENVIRONMENT,
    GEMINI_API_KEY,
    HEALTH_CHECK_PATH,
    READINESS_CHECK_PATH,
    ULSS9_STORES,
)
from app.core.database import close_db, init_db
from app.core.errors import global_exception_handler
from app.core.logging_config import setup_logging
from app.core.metrics import PrometheusMiddleware, metrics_endpoint
from app.core.middleware import (
    CorrelationIdMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    SessionTokenMiddleware,
)
from app.services.admin_seed import seed_admin_user
from app.services.store_manager import StoreManager
from app.services.store_registry import seed_initial_stores, update_gemini_name

# Configure logging first
setup_logging()
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Determine if we should show docs
_show_docs = DEBUG or ENVIRONMENT != "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    logger.info(
        "Starting ULSS 9 Chatbot",
        extra={"env": APP_ENV, "environment": ENVIRONMENT, "debug": DEBUG},
    )

    # Initialize database (create tables, seed initial stores and admin)
    await init_db()
    await seed_initial_stores()
    await seed_admin_user()
    logger.info("Database initialised and stores seeded")

    # Ensure the four initial Gemini File Search Stores exist (idempotent)
    if GEMINI_API_KEY:
        try:
            store_manager = StoreManager()
            if store_manager.client:
                for store_def in ULSS9_STORES:
                    store = await store_manager.create_store(
                        store_def["id"], store_def.get("description", "")
                    )
                    await update_gemini_name(store_def["id"], store.name)
                logger.info("Gemini stores ensured at startup")
        except Exception as e:
            logger.warning(f"Gemini store init failed (non-critical, retry via admin): {e}")

    api_key_status = "set" if GEMINI_API_KEY else "not_set"
    logger.info(
        "Configuration loaded",
        extra={"api_key": api_key_status, "agent_ready": chat.agent.client is not None},
    )

    yield

    # Shutdown
    await close_db()
    logger.info("ULSS 9 Chatbot shutting down")


# Create FastAPI app
app = FastAPI(
    title="ULSS 9 Chatbot",
    description="RAG-based assistant for Azienda ULSS 9 Scaligera. Enterprise-ready for European government deployment.",
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/docs" if _show_docs else None,
    redoc_url="/redoc" if _show_docs else None,
)

# Global exception handler
app.add_exception_handler(Exception, global_exception_handler)

# Middleware order: last added = first executed (reverse of registration order)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SessionTokenMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# CORS - strict allowlist for production
origins = ["*"] if "*" in ALLOWED_ORIGINS else ALLOWED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With", "X-Session-Token", "X-Correlation-ID"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# API routes
# v1 router is the canonical source — includes admin, corrections, session,
# password-reset, gdpr, transparency all under /api/v1/*
app.include_router(api_router, prefix="/api/v1")

# Prometheus metrics endpoint (outside routers for direct scraping)
app.add_route("/metrics", metrics_endpoint, methods=["GET"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main chat interface."""
    return templates.TemplateResponse(request, "index.html")


@app.get(HEALTH_CHECK_PATH)
async def health_check():
    """Liveness probe - is the process running?"""
    return {"status": "healthy", "app": "ulss9-chatbot", "version": "2.2.0"}


@app.get(READINESS_CHECK_PATH)
async def readiness_check():
    """Readiness probe - can the app serve traffic? (Gemini client, etc.)"""
    ready = bool(GEMINI_API_KEY)
    return {
        "status": "ready" if ready else "degraded",
        "gemini_configured": ready,
        "agent_initialized": chat.agent.client is not None,
    }
