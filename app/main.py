"""
UniVR Chatbot - Main FastAPI Application
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import chat, admin
from app.config import APP_ENV, DEBUG, GEMINI_API_KEY

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    logger.info(f"🚀 ULSS 9 Chatbot starting in {APP_ENV} mode")
    
    # Log agent initialization status
    api_key_status = "✅ Set" if GEMINI_API_KEY else "❌ Not set"
    logger.info(f"📋 Configuration: API Key {api_key_status} (length: {len(GEMINI_API_KEY) if GEMINI_API_KEY else 0})")
    logger.info(f"🤖 Agent client initialized: {chat.agent.client is not None}")
    
    yield
    logger.info("👋 ULSS 9 Chatbot shutting down")


# Create FastAPI app
app = FastAPI(
    title="ULSS 9 Chatbot",
    description="RAG-based assistant for Azienda ULSS 9 Scaligera (informazioni generali, orari, sedi, servizi, documenti)",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include API routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main chat interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint for Heroku."""
    return {"status": "healthy", "app": "ulss9-chatbot"}
