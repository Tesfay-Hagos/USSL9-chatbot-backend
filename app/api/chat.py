"""
ULSS 9 Chatbot - Chat API Endpoints

When domain is None: backend selects store(s) from the user message via Gemini, then RAG over those stores.
When domain is set: single-store RAG (backward compatibility).
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.agents.univr_agent import UniVRAgent
from app.config import ALLOW_ENGLISH, GEMINI_API_KEY, ULSS9_STORES
from app.services.extra_stores import get_extra_description
from app.services.store_manager import StoreManager
from app.services.store_selector import select_stores_for_query

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize the agent (singleton)
agent = UniVRAgent()


class ChatRequest(BaseModel):
    """Chat request schema."""
    message: str
    domain: Optional[str] = None  # If set, use this single store; if None, select stores by query
    conversation_id: Optional[str] = None
    language: Optional[str] = None  # "it" or "en"; used only if ALLOW_ENGLISH is True


class ChatResponse(BaseModel):
    """Chat response schema."""
    response: str
    sources: list[dict] = []
    links: list[dict] = []
    stores_used: list[str] = []
    domain: Optional[str] = None
    suggested_questions: list[str] = []  # 2–3 follow-up questions in the same language


class DomainInfo(BaseModel):
    """Domain (store) information schema."""
    domain: str
    display_name: str
    document_count: int


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the chatbot and get a response.

    If domain is provided: use that single store for RAG.
    If domain is None: select relevant store(s) from the message via Gemini, then RAG over those stores.
    """
    try:
        logger.info(f"Chat request: domain={request.domain}, message={request.message[:50]}...")

        # Normalize language: only "en" or "it"; enforce Italian if English not allowed
        lang = (request.language or "it").strip().lower()
        if lang not in ("en", "it"):
            lang = "it"
        if not ALLOW_ENGLISH:
            lang = "it"

        if request.domain:
            # Single store (legacy / testing)
            result = await agent.chat(
                message=request.message,
                domain=request.domain,
                language=lang,
            )
        else:
            # ULSS 9 flow: store selection (four initial + extra from API) then multi-store RAG
            store_manager = StoreManager()
            existing_stores = await store_manager.list_stores()
            initial_ids = {s["id"] for s in ULSS9_STORES}
            extra_stores = [
                {
                    "id": s.domain,
                    "description": get_extra_description(s.domain) or s.display_name or s.domain,
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
            )

        if "demo mode" in result.get("response", "").lower() or "⚠️" in result.get("response", ""):
            logger.warning(f"Received demo response. Client initialized: {agent.client is not None}")

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
    """Get list of stores: four initial (Allegato A) + any added via API, with document_count."""
    try:
        store_manager = StoreManager()
        existing = await store_manager.list_stores()
        by_domain = {s.domain: s for s in existing}

        result = []
        for s in ULSS9_STORES:
            sid = s["id"]
            info = by_domain.get(sid)
            doc_count = info.document_count if info else 0
            result.append(
                DomainInfo(
                    domain=sid,
                    display_name=f"ulss9-{sid}",
                    document_count=doc_count,
                )
            )
        for s in existing:
            if s.domain not in {x["id"] for x in ULSS9_STORES}:
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
WELCOME_IT = {
    "message": "👋 Benvenuto nell'assistente ULSS 9 Scaligera. Scrivi una domanda per trovare informazioni sul sito aulss9.veneto.it.",
    "suggestions": [
        "Quali sono gli orari del punto prelievi di Legnago?",
        "Dove si trova l'Ospedale Magalini di Villafranca?",
        "Come prenotare una visita specialistica?",
    ],
}
WELCOME_EN = {
    "message": "👋 Welcome to the ULSS 9 Scaligera assistant. Ask a question to find information on the aulss9.veneto.it website.",
    "suggestions": [
        "What are the opening hours of the Legnago blood draw point?",
        "Where is Magalini Hospital in Villafranca?",
        "How do I book a specialist visit?",
    ],
}


@router.get("/welcome")
async def get_welcome_message(lang: Optional[str] = Query(None, description="Language: it or en")):
    """Get a welcome message and 3 generic suggestions in the requested language."""
    try:
        store_manager = StoreManager()
        stores = await store_manager.list_stores()
        domain_names = [store.domain for store in stores]
    except Exception:
        domain_names = []

    lang = (lang or "it").strip().lower()
    if lang not in ("en", "it") or not ALLOW_ENGLISH:
        lang = "it"
    content = WELCOME_EN if lang == "en" else WELCOME_IT

    return {
        "message": content["message"],
        "available_domains": domain_names,
        "suggestions": content["suggestions"],
        "languages": ["it", "en"] if ALLOW_ENGLISH else ["it"],
    }


@router.get("/agent/status")
async def get_agent_status():
    """Diagnostic endpoint to check agent initialization status."""
    from app.config import GEMINI_API_KEY
    
    status = {
        "api_key_set": bool(GEMINI_API_KEY),
        "api_key_length": len(GEMINI_API_KEY) if GEMINI_API_KEY else 0,
        "client_initialized": agent.client is not None,
        "client_type": type(agent.client).__name__ if agent.client else None,
    }
    
    # Try to test the client if it exists
    if agent.client:
        try:
            # Simple test - just check if we can list stores
            stores = list(agent.client.file_search_stores.list())
            status["client_working"] = True
            status["stores_accessible"] = len(stores)
        except Exception as e:
            status["client_working"] = False
            status["client_error"] = str(e)
    
    return status


@router.get("/agent/test")
async def test_agent():
    """Test endpoint to make a simple chat call and see what happens."""
    try:
        logger.info("Testing agent with simple message...")
        result = await agent.chat("Hello, this is a test", domain=None)
        return {
            "success": True,
            "response_length": len(result.get("response", "")),
            "is_demo": "demo mode" in result.get("response", "").lower() or "⚠️" in result.get("response", ""),
            "response_preview": result.get("response", "")[:200],
            "sources_count": len(result.get("sources", []))
        }
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.get("/suggestions/{domain}")
async def get_domain_suggestions(domain: str):
    """
    Generate suggested questions for a specific domain.
    
    Uses Gemini with File Search to analyze documents and suggest relevant questions.
    """
    try:
        # Use the agent to generate suggestions based on document content
        result = await agent.chat(
            message="""Based on the documents in this knowledge base, generate exactly 5 specific, 
            helpful questions that a student might want to ask. 
            Return ONLY the questions, one per line, without numbering or bullet points.
            Make them specific to the actual content available, not generic questions.
            Questions should be in the same language as the documents (Italian or English).""",
            domain=domain
        )
        
        # Parse the response into individual questions
        response_text = result.get("response", "")
        questions = [
            q.strip() 
            for q in response_text.strip().split("\n") 
            if q.strip() and len(q.strip()) > 10
        ][:5]  # Limit to 5 questions
        
        # Fallback if parsing fails
        if not questions:
            questions = [
                "What information is available in this section?",
                "What are the key deadlines I should know about?",
                "What documents are required?",
                "Who can I contact for more information?",
                "What are the eligibility requirements?"
            ]
        
        return {
            "domain": domain,
            "suggestions": questions
        }
        
    except Exception as e:
        logger.error(f"Error generating suggestions for {domain}: {e}")
        # Return fallback suggestions on error
        return {
            "domain": domain,
            "suggestions": [
                "What information is available in this section?",
                "What are the key deadlines I should know about?",
                "What documents are required?",
                "Who can I contact for more information?",
                "What are the eligibility requirements?"
            ]
        }

