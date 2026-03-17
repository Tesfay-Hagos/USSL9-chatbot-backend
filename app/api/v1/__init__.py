"""
API v1 - Versioned endpoints for enterprise deployment.

Includes: auth, chat, admin, session tokens, password reset,
corrections, GDPR data subject rights, AI transparency.
"""

from fastapi import APIRouter

from app.api import (
    admin,
    auth,
    chat,
    corrections,
    gdpr,
    password_reset,
    public,
    session,
    transparency,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(session.router, tags=["session"])
api_router.include_router(password_reset.router, prefix="/auth", tags=["password-reset"])
api_router.include_router(corrections.router, prefix="/admin", tags=["corrections"])
api_router.include_router(gdpr.router, prefix="/admin", tags=["gdpr"])
api_router.include_router(transparency.router, tags=["transparency"])
