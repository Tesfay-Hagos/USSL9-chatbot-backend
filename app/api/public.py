"""
Public API — Unauthenticated endpoints for the chatbot widget.

Used by the public-facing chat UI to fetch categories/stores.
"""

import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import store_registry
from app.services.store_manager import StoreManager

router = APIRouter()
logger = logging.getLogger(__name__)


class PublicStoreInfo(BaseModel):
    """Store info for public chatbot category picker."""

    domain: str
    display_name: str
    description: str = ""
    is_initial: bool = False


async def _ensure_gemini_store(manager: StoreManager, domain: str, description: str) -> None:
    """
    Verify a store exists in Gemini; auto-create it if missing.
    Runs in the background — never raises, never blocks the response.
    """
    try:
        store = await manager.resolve_store(domain)
        if not store:
            logger.warning(f"Public store '{domain}' missing from Gemini — auto-creating")
            store = await manager.create_store(domain, description)
            await store_registry.update_gemini_name(domain, store.name)
            logger.info(f"Auto-created Gemini store for public domain '{domain}'")
    except Exception as e:
        logger.warning(f"Gemini health check for public store '{domain}' failed (non-critical): {e}")


@router.get("/stores", response_model=list[PublicStoreInfo])
async def list_public_stores():
    """
    List stores visible in the public chatbot (is_public=True).
    No authentication required — used by the chat widget for category selection.

    Also verifies each store exists in Gemini on every call and auto-creates
    any missing ones in the background (graceful — never blocks the response).
    """
    records = await store_registry.list_public_stores()

    # Fire-and-forget Gemini health check for each public store
    manager = StoreManager()
    if manager.client:
        tasks = [
            _ensure_gemini_store(manager, r.id, r.description or "")
            for r in records
        ]
        asyncio.gather(*tasks, return_exceptions=True)

    return [
        PublicStoreInfo(
            domain=r.id,
            display_name=r.display_name,
            description=r.description or "",
            is_initial=r.is_initial,
        )
        for r in records
    ]
