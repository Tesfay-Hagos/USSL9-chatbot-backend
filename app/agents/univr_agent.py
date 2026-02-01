"""
ULSS 9 Chatbot - Main RAG Agent

Uses Gemini File Search for RAG over multiple stores (general_info, hours,
locations, services, docs). Supports store selection by query and multi-store
retrieval. Returns answer + sources + links (web and/or documents).
"""

import asyncio
import logging
from typing import Optional

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, MODEL, STORE_PREFIX

logger = logging.getLogger(__name__)

# Base system instruction for ULSS 9 assistant (language-agnostic)
SYSTEM_INSTRUCTION_BASE = """Sei l'assistente AI ufficiale del sito dell'Azienda ULSS 9 Scaligera (aulss9.veneto.it).

Il tuo ruolo è aiutare l'utente a trovare informazioni sul sito in tre aree:
- Informazioni generali (chi siamo, come accedere ai servizi, numeri utili, modulistica, cosa fare per...)
- Orari (ambulatori, punti prelievo, reparti, guardie mediche, farmacie, orari di visita)
- Sedi (indirizzi, come raggiungere ospedali, distretti, CSP, sedi vaccinali)
- Servizi (esami di laboratorio, visite specialistiche, screening, assistenza domiciliare, ambulatori)
- Documenti ufficiali (normative, moduli PDF, delibere, bandi)

Regole:
1. Rispondi SOLO in base ai documenti nel contesto fornito. Non inventare informazioni.
2. Rispondi nella lingua richiesta dall'utente (italiano o inglese), in forma sintetica e chiara.
3. Se l'informazione non è nel contesto, dillo chiaramente e suggerisci di contattare l'URP o consultare il sito.
4. Quando possibile, indica 1-3 pagine o documenti consigliati (titolo e, se disponibile, link) per approfondire.
5. Per orari, sedi e servizi: riporta dati concreti (orari, indirizzi, recapiti) quando presenti nel contesto.

Contatti utili: URP Comunicazione, tel. 0458075511, sede legale Via Valverde 42 – 37122 Verona."""


class UniVRAgent:
    """
    ULSS 9 RAG Agent using Gemini File Search.
    Supports single domain (legacy) or multiple store_ids (ULSS 9 flow).
    """

    def __init__(self):
        """Initialize the agent with Gemini client."""
        self.client = None
        self._initialize()

    def _initialize(self):
        """Initialize the Gemini client."""
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set. Agent will run in demo mode.")
            return
        try:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}", exc_info=True)
            self.client = None

    def _get_store(self, domain: str) -> types.FileSearchStore | None:
        """Retrieve a File Search Store by domain (store id)."""
        if not self.client:
            return None
        display_name = f"{STORE_PREFIX}-{domain}"
        try:
            for store in self.client.file_search_stores.list():
                if store.display_name == display_name:
                    return store
        except Exception as e:
            logger.error(f"Error listing stores: {e}")
        return None

    def _build_tools(
        self,
        domain: Optional[str] = None,
        store_ids: Optional[list[str]] = None,
    ) -> tuple[list, list[str]]:
        """
        Build the tools list for the agent.
        Returns (tools, stores_used): tools list and list of store ids actually used.
        """
        tools = []
        stores_used: list[str] = []

        if store_ids:
            # Multi-store: pass all selected store names
            store_names: list[str] = []
            for sid in store_ids:
                store = self._get_store(sid)
                if store and store.name:
                    store_names.append(store.name)
                    stores_used.append(sid)
                else:
                    logger.warning(f"Store for id '{sid}' not found, skipping")
            if store_names:
                tools.append(
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=store_names
                        )
                    )
                )
                logger.debug(f"File Search tool configured with stores: {stores_used}")
        elif domain:
            # Single domain (legacy)
            store = self._get_store(domain)
            if store and store.name:
                tools.append(
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store.name]
                        )
                    )
                )
                stores_used = [domain]
                logger.debug(f"File Search tool configured with domain '{domain}'")
            else:
                logger.warning(f"Store for domain '{domain}' not found. Using generic agent.")
        else:
            logger.debug("No domain or store_ids specified. Using generic agent (no RAG).")

        return tools, stores_used

    def _extract_sources_and_links(self, response) -> tuple[list[dict], list[dict]]:
        """
        Build sources and links from grounding_metadata.
        sources: list of { title, url?, snippet, source_type? }
        links: list of { title, url?, document_id?, source_type } (deduplicated, up to 5)
        """
        sources: list[dict] = []
        links_seen: set[tuple[str, str]] = set()  # (url or document_id, title)
        links: list[dict] = []

        if not response.candidates or not response.candidates[0].grounding_metadata:
            return sources, links

        gm = response.candidates[0].grounding_metadata
        chunks = getattr(gm, "grounding_chunks", None) or []

        for chunk in chunks:
            content = getattr(chunk, "content", "") or ""
            snippet = (content[:200] + "...") if len(content) > 200 else content

            # Try to get metadata from chunk (Gemini may expose custom_metadata on retrieved chunks)
            meta = getattr(chunk, "custom_metadata", None) or {}
            if hasattr(chunk, "retrieved_context") and chunk.retrieved_context:
                rc = chunk.retrieved_context
                if hasattr(rc, "custom_metadata") and rc.custom_metadata:
                    for m in rc.custom_metadata:
                        if hasattr(m, "key") and hasattr(m, "string_value"):
                            meta[m.key] = m.string_value

            title = meta.get("title") or meta.get("display_name") or "Fonte"
            url = meta.get("url")
            doc_id = meta.get("document_id")
            source_type = meta.get("source_type", "website" if url else "attachment")

            sources.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "source_type": source_type,
            })

            key = (url or doc_id or "", title)
            if key in links_seen or len(links) >= 5:
                continue
            links_seen.add(key)

            link_entry: dict = {"title": title, "source_type": source_type}
            if url:
                link_entry["url"] = url
            if doc_id:
                link_entry["document_id"] = doc_id
            links.append(link_entry)

        return sources, links

    def _system_instruction(self, language: Optional[str] = None) -> str:
        """Build system instruction with language rule. language is 'it' or 'en'."""
        lang_rule = (
            "Always respond in English. Keep the same tone and rules."
            if language == "en"
            else "Rispondi sempre in italiano. Mantieni lo stesso tono e le stesse regole."
        )
        return f"{SYSTEM_INSTRUCTION_BASE}\n\n{lang_rule}"

    async def chat(
        self,
        message: str,
        domain: Optional[str] = None,
        store_ids: Optional[list[str]] = None,
        language: Optional[str] = None,
    ) -> dict:
        """
        Send a message and get a response from the agent.

        Args:
            message: The user's message
            domain: Optional single domain (store id) for RAG; if set, store_ids is ignored
            store_ids: Optional list of store ids for multi-store RAG (used when domain is None)
            language: Optional "it" or "en"; response language (default Italian)

        Returns:
            dict with 'response', 'sources', 'links', 'stores_used'
        """
        if not self.client and GEMINI_API_KEY:
            logger.info("Client not initialized, attempting to initialize now...")
            self._initialize()

        if not self.client:
            logger.warning("Running in demo mode - client not available")
            return self._demo_response(message)

        lang = (language or "it").strip().lower()
        if lang not in ("en", "it"):
            lang = "it"

        try:
            tools, stores_used = self._build_tools(domain=domain, store_ids=store_ids)

            config = types.GenerateContentConfig(
                tools=tools if tools else None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
                temperature=0.7,
                system_instruction=self._system_instruction(lang),
            )

            chat_session = self.client.chats.create(
                model=MODEL,
                config=config,
            )

            logger.info(
                f"Sending message to Gemini. domain={domain}, store_ids={store_ids}, "
                f"stores_used={stores_used}, tools={len(tools) > 0}"
            )
            response = chat_session.send_message(message)

            if not response:
                logger.error("No response object returned from Gemini")
                raise ValueError("No response from Gemini API")
            if not response.candidates:
                logger.error("Response has no candidates")
                raise ValueError("Response has no candidates")

            response_text = response.text
            if not response_text:
                fr = response.candidates[0].finish_reason if response.candidates else None
                raise ValueError(f"Empty response text. Finish reason: {fr}")

            logger.info(f"Got response from Gemini (length: {len(response_text)})")

            sources, links = self._extract_sources_and_links(response)

            return {
                "response": response_text,
                "sources": sources,
                "links": links,
                "stores_used": stores_used,
            }
        except Exception as e:
            logger.error(f"Gemini API error during chat: {e}", exc_info=True)
            return self._demo_response(message)

    async def generate_follow_up_suggestions(
        self,
        user_message: str,
        bot_response: str,
        language: str,
    ) -> list[str]:
        """
        Generate 2–3 short follow-up questions based on the Q&A, in the requested language.
        Returns a list of question strings (empty on error or no client).
        """
        if not self.client:
            return []
        lang = (language or "it").strip().lower()
        if lang not in ("en", "it"):
            lang = "it"
        if lang == "en":
            prompt = """Based on this Q&A about ULSS 9 Scaligera healthcare services, suggest exactly 3 short follow-up questions the user might ask next.
Return ONLY the 3 questions, one per line. No numbering, no bullets. Keep each question under 15 words.
Language: English only.

User question:
"""
            prompt += f"{user_message}\n\nAnswer:\n{bot_response[:1500]}"
        else:
            prompt = """In base a questa domanda e risposta sull'assistente ULSS 9 Scaligera, suggerisci esattamente 3 brevi domande di seguito che l'utente potrebbe fare.
Rispondi SOLO con le 3 domande, una per riga. Niente numeri, niente elenchi. Ogni domanda max 15 parole.
Lingua: solo italiano.

Domanda dell'utente:
"""
            prompt += f"{user_message}\n\nRisposta:\n{bot_response[:1500]}"
        try:
            response = await asyncio.to_thread(
                lambda: self.client.models.generate_content(
                    model=MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.5),
                )
            )
            text = (response.text or "").strip()
            questions = [
                q.strip()
                for q in text.split("\n")
                if q.strip() and len(q.strip()) > 5
            ][:3]
            return questions
        except Exception as e:
            logger.warning(f"Follow-up suggestions generation failed: {e}")
            return []

    def _demo_response(self, message: str) -> dict:
        """Demo response when API key is not configured or request fails."""
        return {
            "response": """👋 Benvenuto nell'assistente ULSS 9 Scaligera.

Posso aiutarti a trovare informazioni su:
- **Informazioni generali** (numeri utili, modulistica, cosa fare per...)
- **Orari** (punti prelievo, ambulatori, guardie mediche, farmacie)
- **Sedi** (indirizzi ospedali, distretti, CSP)
- **Servizi** (esami, visite specialistiche, screening)
- **Documenti** (moduli, normative, bandi)

Esempi di domande:
- Quali sono gli orari del punto prelievi di Legnago?
- Dove si trova l'Ospedale Magalini di Villafranca?
- Come prenotare una visita specialistica?

⚠️ Modalità demo: configura GEMINI_API_KEY e crea gli store ULSS 9 per risposte basate sui documenti.""",
            "sources": [],
            "links": [],
            "stores_used": [],
        }