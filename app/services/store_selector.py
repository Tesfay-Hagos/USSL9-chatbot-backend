"""
ULSS 9 - Store selection by user query

Calls Gemini with the list of store descriptions and the user message
to decide which store(s) are relevant. Uses the four initial stores (Allegato A)
plus any extra stores added via API.
"""

import asyncio
import logging
from typing import Any

from google.genai import types
from pydantic import BaseModel

from app.config import GEMINI_API_KEY, MODEL, ULSS9_STORES

logger = logging.getLogger(__name__)


class StoreSelectionOutput(BaseModel):
    """Structured output from Gemini for store selection."""
    stores: list[str]
    reason: str = ""


def _build_store_list(extra_stores: list[dict] | None = None) -> tuple[list[dict], set[str]]:
    """Build full list of stores (initial + extra) and set of valid ids."""
    full_list = list(ULSS9_STORES)
    valid_ids = {s["id"] for s in ULSS9_STORES}
    if extra_stores:
        for s in extra_stores:
            sid = s.get("id") or s.get("domain")
            desc = s.get("description") or s.get("display_name", "")
            if sid and sid not in valid_ids:
                full_list.append({"id": sid, "description": desc})
                valid_ids.add(sid)
    return full_list, valid_ids


async def select_stores_for_query(
    client: Any,
    user_message: str,
    extra_stores: list[dict] | None = None,
) -> list[str]:
    """
    Given the user message, ask Gemini which store(s) are relevant.
    Uses the four initial stores (Allegato A) plus extra_stores (from API).
    Returns a list of store ids.

    Falls back to ["general_info"] if client is None or the call fails.
    """
    full_list, valid_ids = _build_store_list(extra_stores)
    if not client or not GEMINI_API_KEY:
        logger.warning("Store selector: no client or API key, using default general_info")
        return ["general_info"]

    store_list_text = "\n".join(
        f"- {s['id']}: {s['description']}" for s in full_list
    )
    prompt = f"""Sei un assistente che classifica le domande degli utenti rispetto a categorie di informazioni del sito ULSS 9 Scaligera.

Elenco delle categorie (stores) disponibili:
{store_list_text}

Domanda dell'utente: "{user_message}"

Indica quali categorie sono rilevanti per rispondere alla domanda (puoi sceglierne una o più).
Rispondi SOLO con un JSON valido con chiavi: "stores" (array di id, es. ["hours", "locations"]) e "reason" (breve motivazione in italiano)."""

    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=StoreSelectionOutput,
            temperature=0.2,
        )
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=config,
            )
        )
        parsed = response.parsed
        if not parsed or not isinstance(parsed, StoreSelectionOutput):
            logger.warning("Store selector: invalid parsed response, using general_info")
            return ["general_info"]

        # Keep only ids that exist in registry
        selected = [s for s in parsed.stores if s in valid_ids]
        if not selected:
            selected = ["general_info"]
        logger.info(f"Store selection: {selected} (reason: {parsed.reason})")
        return selected
    except Exception as e:
        logger.error(f"Store selection failed: {e}", exc_info=True)
        return ["general_info"]
