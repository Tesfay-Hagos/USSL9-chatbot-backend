"""
UniVR Chatbot - Enterprise Configuration Module

Production-ready configuration with validation for European government deployment.
GDPR-aware, environment-based, 12-factor compliant.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


def _env_list(key: str, default: str = "") -> list[str]:
    val = os.getenv(key, default).strip()
    if not val:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]


# =============================================================================
# Gemini / AI
# =============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("MODEL", "gemini-2.5-flash")

# ULSS 9 public store — single general-purpose knowledge base.
ULSS9_STORES = [
    {"id": "general", "display_name": "General", "description": "Informazioni generali ULSS 9 Scaligera: servizi, orari, sedi, accesso alle cure, modulistica e assistenza ai cittadini."},
]

ALLOW_ENGLISH = _env_bool("ALLOW_ENGLISH", False)

# =============================================================================
# Application
# =============================================================================
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = _env_bool("DEBUG", False)
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" for production, "text" for dev

# =============================================================================
# Security & Auth
# =============================================================================
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# HMAC session token for public (widget) API access
WIDGET_SECRET = os.getenv("WIDGET_SECRET", "change-me-widget-secret")
SESSION_TOKEN_TTL = int(os.getenv("SESSION_TOKEN_TTL", "3600"))  # seconds

# CORS: comma-separated origins; "*" means allow all (avoid in production)
ALLOWED_ORIGINS: list[str] = _env_list("ALLOWED_ORIGINS", os.getenv("CORS_ORIGINS", "*"))
CORS_ORIGINS = ALLOWED_ORIGINS  # backward compat alias
CORS_ALLOW_CREDENTIALS = _env_bool("CORS_ALLOW_CREDENTIALS", True)

# Redis (optional — used for rate limiting and OTP storage; falls back to in-memory)
REDIS_URL = os.getenv("REDIS_URL", "")

# Rate limiting via slowapi
RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "10/minute")
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")

# Legacy rate limiting (kept for backward compat but slowapi is preferred)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# GDPR: IP hashing salt
IP_HASH_SALT = os.getenv("IP_HASH_SALT", "ulss9-default-salt-change-me")

# Environment flag: "production" disables debug routes
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Trusted proxy headers (X-Forwarded-For, X-Real-IP) for rate limiting behind load balancer
TRUST_PROXY = _env_bool("TRUST_PROXY", False)

# =============================================================================
# Audit Logging (GDPR / compliance)
# =============================================================================
AUDIT_LOG_ENABLED = _env_bool("AUDIT_LOG_ENABLED", True)
AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "")  # If set, append to file; else stdout via logger
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))

# =============================================================================
# Email / Password Reset (Brevo)
# =============================================================================
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "brevo")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@aulss9.veneto.it")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "ULSS 9 Scaligera Admin")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "600"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "3"))

# =============================================================================
# Database (PostgreSQL recommended; SQLite for dev)
# =============================================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/ulss9.db")

# Chat log retention (GDPR)
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
CONVERSATION_HISTORY_LIMIT = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "10"))
CHAT_LOG_ANONYMISE = _env_bool("CHAT_LOG_ANONYMISE", True)

# =============================================================================
# CartaServizi API (external database integration)
# =============================================================================
CARTA_SERVIZI_URL = os.getenv("CARTA_SERVIZI_URL", "")
CARTA_SERVIZI_COGNITO_DOMAIN = os.getenv("CARTA_SERVIZI_COGNITO_DOMAIN", "")
CARTA_SERVIZI_CLIENT_ID = os.getenv("CARTA_SERVIZI_CLIENT_ID", "")
CARTA_SERVIZI_CLIENT_SECRET = os.getenv("CARTA_SERVIZI_CLIENT_SECRET", "")

# =============================================================================
# Request Limits
# =============================================================================
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", str(10 * 1024 * 1024)))  # 10MB default

# =============================================================================
# Server
# =============================================================================
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
WORKERS = int(os.getenv("WORKERS", "1"))

# Graceful shutdown timeout (seconds)
SHUTDOWN_TIMEOUT = int(os.getenv("SHUTDOWN_TIMEOUT", "30"))

# =============================================================================
# Health Checks
# =============================================================================
HEALTH_CHECK_PATH = os.getenv("HEALTH_CHECK_PATH", "/health")
READINESS_CHECK_PATH = os.getenv("READINESS_CHECK_PATH", "/ready")

# =============================================================================
# Validation
# =============================================================================
def _validate_production() -> None:
    """Warn on insecure production config."""
    if APP_ENV != "production" and ENVIRONMENT != "production":
        return
    issues = []
    if not JWT_SECRET or JWT_SECRET == "change-me-in-production":
        issues.append("JWT_SECRET must be set to a strong random value")
    if not WIDGET_SECRET or WIDGET_SECRET == "change-me-widget-secret":
        issues.append("WIDGET_SECRET must be set to a strong random value (32+ bytes)")
    if not GEMINI_API_KEY:
        issues.append("GEMINI_API_KEY is required")
    if ALLOWED_ORIGINS == ["*"]:
        issues.append("ALLOWED_ORIGINS should be restricted in production (no wildcard)")
    if IP_HASH_SALT == "ulss9-default-salt-change-me":
        issues.append("IP_HASH_SALT must be set to a unique random value")
    if issues:
        import warnings
        for msg in issues:
            warnings.warn(f"Production config: {msg}", UserWarning)


# Run validation on import
_validate_production()

def validate_required_envs() -> None:
    """Ensure all strictly required environment variables are set.
    
    If any of these are missing from the environment, the application will
    refuse to start to prevent runtime errors or security vulnerabilities.
    """
    required_keys = [
        "GEMINI_API_KEY",
        "JWT_SECRET",
        "WIDGET_SECRET",
        "ADMIN_SEED_EMAIL",
        "ADMIN_SEED_PASSWORD",
    ]
    missing = [key for key in required_keys if not os.getenv(key)]

    if missing:
        raise RuntimeError(
            f"\\n{'='*70}\\n"
            f"❌ CRITICAL ERROR: Missing required environment variables!\\n"
            f"The following variables must be defined in your .env file:\\n"
            f"  {', '.join(missing)}\\n"
            f"{'='*70}\\n"
        )


# Run strict validation on import so the app crashes early if misconfigured
validate_required_envs()

