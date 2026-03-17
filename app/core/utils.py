"""
Shared Utility Functions for ULSS 9 Chatbot API

Common helpers used across multiple API route modules.
"""

from fastapi import Request

from app.config import TRUST_PROXY


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting proxy headers if configured."""
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
    return request.client.host if request.client else "unknown"
