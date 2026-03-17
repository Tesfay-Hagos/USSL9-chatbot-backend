"""
HMAC Session Token for Public Widget API

Issues time-limited, HMAC-signed session tokens for the public chat widget.
The widget calls POST /api/v1/session-token once on load, then attaches the
token via X-Session-Token header on subsequent requests.

Security: tokens are stateless (no server-side storage), validated by HMAC
signature + TTL check. This prevents unauthorised API scraping without
burdening real users.
"""

import hashlib
import hmac
import logging
import secrets
import time

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import SESSION_TOKEN_TTL, WIDGET_SECRET

logger = logging.getLogger(__name__)

router = APIRouter()


class SessionTokenResponse(BaseModel):
    """Returned to public clients (widget)."""
    session_token: str
    expires_in: int  # seconds


def _sign_token(timestamp: int, nonce: str) -> str:
    """Create HMAC-SHA256 signature for session token."""
    message = f"{timestamp}:{nonce}"
    return hmac.new(
        WIDGET_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_session_token() -> tuple[str, int]:
    """Generate a signed session token. Returns (token_string, ttl)."""
    timestamp = int(time.time())
    nonce = secrets.token_hex(16)
    signature = _sign_token(timestamp, nonce)
    token = f"{timestamp}:{nonce}:{signature}"
    return token, SESSION_TOKEN_TTL


def validate_session_token(token: str) -> bool:
    """Validate an HMAC session token. Returns True if valid and not expired."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        timestamp_str, nonce, provided_sig = parts
        timestamp = int(timestamp_str)

        # Check TTL
        if time.time() - timestamp > SESSION_TOKEN_TTL:
            return False

        # Verify HMAC
        expected_sig = _sign_token(timestamp, nonce)
        return hmac.compare_digest(provided_sig, expected_sig)
    except (ValueError, TypeError):
        return False


@router.post("/session-token", response_model=SessionTokenResponse)
async def issue_session_token(request: Request):
    """
    Issue an HMAC-signed session token for the public chat widget.

    The widget should call this once on page load, then include the token
    in the X-Session-Token header for all subsequent API calls.
    """
    token, ttl = create_session_token()
    logger.info("Session token issued", extra={"ttl": ttl})
    return SessionTokenResponse(session_token=token, expires_in=ttl)
