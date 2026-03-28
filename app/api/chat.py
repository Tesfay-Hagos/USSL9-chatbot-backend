"""
ULSS 9 Chatbot - Chat API Endpoints

When domain is None: backend selects store(s) from the user message via Gemini, then RAG over those stores.
When domain is set: single-store RAG (backward compatibility).

Phase 4: correction lookup before RAG + anonymised chat logging.
"""


import logging

import jwt
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.agents.univr_agent import UniVRAgent
from app.config import JWT_ALGORITHM, JWT_SECRET, ULSS9_STORES, CONVERSATION_HISTORY_LIMIT
from app.core.utils import get_client_ip
from app.services.chat_logger import get_conversation_history, log_chat
from app.services.store_manager import StoreManager
from app.services.store_registry import list_stores as db_list_stores
from app.services.store_selector import select_stores_for_query

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize the agent (singleton)
agent = UniVRAgent()


def _resolve_caller(request: Request) -> str:
    """
    Return 'admin' if the request carries a valid admin JWT in the Authorization header,
    otherwise 'public'.  Never raises — an invalid/expired token is treated as public.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "public"
    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("sub"):
            return "admin"
    except jwt.PyJWTError:
        pass
    return "public"

# Supported languages
SUPPORTED_LANGUAGES = ['it', 'en', 'fr', 'pt', 'ro', 'es', 'sq', 'ar', 'uk', 'de']


class HistoryEntry(BaseModel):
    """A single turn in the conversation history."""
    role: str = Field(description="'user' or 'model'")
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    """Chat request schema with input validation."""
    message: str = Field(min_length=1, max_length=2000, description="User message")
    domain: str | None = Field(None, max_length=100, pattern=r"^[a-z0-9_-]+$", description="Store domain")
    conversation_id: str | None = Field(None, max_length=100, description="Conversation identifier")
    language: str | None = Field(None, max_length=5, description="Language code (it, en, fr, etc.)")
    history: list[HistoryEntry] = Field(default=[], max_length=20, description="Previous conversation turns")


class ChatResponse(BaseModel):
    """Chat response schema."""
    response: str
    sources: list[dict] = []
    links: list[dict] = []
    stores_used: list[str] = []
    domain: str | None = None
    suggested_questions: list[str] = []  # 2–3 follow-up questions in the same language


class DomainInfo(BaseModel):
    """Domain (store) information schema."""
    domain: str
    display_name: str
    document_count: int





@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, raw_request: Request):
    """
    Send a message to the chatbot and get a response.

    Flow:
    1. Check corrections DB — if a pattern matches, return cached correction.
    2. Otherwise: select store(s) → RAG → generate follow-up suggestions.
    3. Log anonymised metadata (no message content).
    """
    try:
        logger.info("Chat request", extra={"domain": request.domain, "msg_len": len(request.message), "lang": request.language})

        # Normalize language
        lang = (request.language or "it").strip().lower()
        if lang not in SUPPORTED_LANGUAGES:
            lang = "it"

        # Determine caller type: 'admin' (authenticated) or 'public' (unauthenticated widget)
        caller = _resolve_caller(raw_request)
        logger.info("Chat caller type: %s", caller)

        # Fetch conversation history if conversation_id provided
        history: list[dict] = []
        if request.conversation_id:
            try:
                history = await get_conversation_history(request.conversation_id, CONVERSATION_HISTORY_LIMIT)
            except Exception as e:
                logger.warning(f"Failed to fetch conversation history: {e}")

        if request.domain:
            # ── Single store RAG ──
            result = await agent.chat(
                message=request.message,
                domain=request.domain,
                language=lang,
                caller=caller,
                history=history or None,
            )
        else:
            # ── Step 2b: Multi-store RAG (store selection → RAG) ──
            store_manager = StoreManager()
            existing_stores = await store_manager.list_stores()
            initial_ids = {s["id"] for s in ULSS9_STORES}

            # Build extra stores list from DB registry descriptions
            db_stores = await db_list_stores()
            db_descriptions = {s.id: s.description for s in db_stores}
            extra_stores = [
                {
                    "id": s.domain,
                    "description": db_descriptions.get(s.domain) or s.display_name or s.domain,
                }
                for s in existing_stores
                if s.domain not in initial_ids
            ]
            selected_ids = await select_stores_for_query(
                agent.client,
                request.message,
                extra_stores=extra_stores if extra_stores else None,
            )
            result = await agent.chat(
                message=request.message,
                store_ids=selected_ids,
                language=lang,
                caller=caller,
                history=history or None,
            )

        if "demo mode" in result.get("response", "").lower() or "⚠️" in result.get("response", ""):
            logger.warning(f"Received demo response. Client initialized: {agent.client is not None}")

        # Follow-up suggestions
        suggested_questions: list[str] = []
        if agent.client:
            try:
                suggested_questions = await agent.generate_follow_up_suggestions(
                    user_message=request.message,
                    bot_response=result["response"],
                    language=lang,
                )
            except Exception as e:
                logger.warning(f"Follow-up suggestions failed: {e}")

        # ── Log chat interaction (hashed IP, query + response stored for admin review) ──
        try:
            response_text = result.get("response", "")
            await log_chat(
                ip=get_client_ip(raw_request),
                conversation_id=request.conversation_id,
                domain=request.domain,
                stores_used=result.get("stores_used", []),
                language=lang,
                message_text=request.message,
                response_text=response_text,
                message_length=len(request.message),
                response_length=len(response_text),
                has_sources=bool(result.get("sources")),
            )
        except Exception as e:
            logger.warning(f"Chat logging failed (non-critical): {e}")

        return ChatResponse(
            response=result["response"],
            sources=result.get("sources", []),
            links=result.get("links", []),
            stores_used=result.get("stores_used", []),
            domain=request.domain,
            suggested_questions=suggested_questions,
        )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/domains", response_model=list[DomainInfo])
async def get_domains():
    """Get list of stores from DB registry, with document counts from Gemini."""
    try:
        # Get stores from DB registry
        db_stores = await db_list_stores()
        store_manager = StoreManager()
        existing = await store_manager.list_stores()
        by_domain = {s.domain: s for s in existing}

        result = []
        for store in db_stores:
            gemini_info = by_domain.get(store.id)
            doc_count = gemini_info.document_count if gemini_info else 0
            result.append(
                DomainInfo(
                    domain=store.id,
                    display_name=store.display_name,
                    document_count=doc_count,
                )
            )

        # Also include any Gemini-only stores not yet in DB
        db_ids = {s.id for s in db_stores}
        for s in existing:
            if s.domain not in db_ids:
                result.append(
                    DomainInfo(
                        domain=s.domain,
                        display_name=s.display_name or s.domain,
                        document_count=s.document_count,
                    )
                )
        return result
    except Exception as e:
        logger.error(f"List domains error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Welcome content by language (3 generic questions for first load)
WELCOME_MESSAGES = {
    'it': {
        'message': "👋 Benvenuto nell'assistente ULSS 9 Scaligera. Scrivi una domanda per trovare informazioni sul sito aulss9.veneto.it.",
        'suggestions': [
            "Quali sono gli orari del punto prelievi di Legnago?",
            "Dove si trova l'Ospedale Magalini di Villafranca?",
            "Come prenotare una visita specialistica?",
        ],
    },
    'en': {
        'message': "👋 Welcome to the ULSS 9 Scaligera assistant. Ask a question to find information on the aulss9.veneto.it website.",
        'suggestions': [
            "What are the opening hours of the Legnago blood draw point?",
            "Where is Magalini Hospital in Villafranca?",
            "How do I book a specialist visit?",
        ],
    },
    'fr': {
        'message': "👋 Bienvenue dans l'assistant ULSS 9 Scaligera. Posez une question pour trouver des informations sur le site aulss9.veneto.it.",
        'suggestions': [
            "Quels sont les horaires du point de prélèvement de Legnago?",
            "Où se trouve l'hôpital Magalini à Villafranca?",
            "Comment réserver une visite spécialisée?",
        ],
    },
    'pt': {
        'message': "👋 Bem-vindo ao assistente ULSS 9 Scaligera. Faça uma pergunta para encontrar informações no site aulss9.veneto.it.",
        'suggestions': [
            "Quais são os horários do ponto de coleta de sangue de Legnago?",
            "Onde fica o Hospital Magalini em Villafranca?",
            "Como agendar uma consulta especializada?",
        ],
    },
    'ro': {
        'message': "👋 Bun venit la asistentul ULSS 9 Scaligera. Pune o întrebare pentru a găsi informații pe site-ul aulss9.veneto.it.",
        'suggestions': [
            "Care sunt orele punctului de recoltare sânge din Legnago?",
            "Unde se află Spitalul Magalini în Villafranca?",
            "Cum să programez o vizită la specialist?",
        ],
    },
    'es': {
        'message': "👋 Bienvenido al asistente ULSS 9 Scaligera. Haz una pregunta para encontrar información en el sitio aulss9.veneto.it.",
        'suggestions': [
            "¿Cuáles son los horarios del punto de extracción de sangre de Legnago?",
            "¿Dónde está el Hospital Magalini en Villafranca?",
            "¿Cómo reservar una visita especializada?",
        ],
    },
    'sq': {
        'message': "👋 Mirë se vini në asistentin ULSS 9 Scaligera. Bëni një pyetje për të gjetur informacion në faqen aulss9.veneto.it.",
        'suggestions': [
            "Cilat janë orët e pikës së marrjes së gjakut në Legnago?",
            "Ku ndodhet Spitali Magalini në Villafranca?",
            "Si të rezervoj një vizitë të specializuar?",
        ],
    },
    'ar': {
        'message': "👋 مرحبًا بك في مساعد ULSS 9 Scaligera. اطرح سؤالاً للعثور على معلومات على موقع aulss9.veneto.it.",
        'suggestions': [
            "ما هي ساعات عمل نقطة سحب الدم في Legnago؟",
            "أين يقع مستشفى Magalini في Villafranca؟",
            "كيف أحجز زيارة متخصصة؟",
        ],
    },
    'uk': {
        'message': "👋 Ласкаво просимо до помічника ULSS 9 Scaligera. Поставте питання, щоб знайти інформацію на сайті aulss9.veneto.it.",
        'suggestions': [
            "Які години роботи пункту забору крові в Legnago?",
            "Де знаходиться лікарня Magalini у Villafranca?",
            "Як записатися на спеціалізований прийом?",
        ],
    },
    'de': {
        'message': "👋 Willkommen beim ULSS 9 Scaligera Assistenten. Stellen Sie eine Frage, um Informationen auf der Website aulss9.veneto.it zu finden.",
        'suggestions': [
            "Was sind die Öffnungszeiten der Blutabnahmestelle in Legnago?",
            "Wo befindet sich das Magalini Krankenhaus in Villafranca?",
            "Wie buche ich einen Facharzttermin?",
        ],
    },
}


@router.get("/welcome")
async def get_welcome_message(lang: str | None = Query(None, description="Language code (it, en, fr, pt, ro, es, sq, ar, uk, de)")):
    """Get a welcome message and 3 generic suggestions in the requested language."""
    try:
        store_manager = StoreManager()
        stores = await store_manager.list_stores()
        domain_names = [store.domain for store in stores]
    except Exception:
        domain_names = []

    lang = (lang or "it").strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = "it"

    content = WELCOME_MESSAGES.get(lang, WELCOME_MESSAGES['it'])

    return {
        "message": content["message"],
        "available_domains": domain_names,
        "suggestions": content["suggestions"],
        "languages": SUPPORTED_LANGUAGES,
    }


