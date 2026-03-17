"""
EU AI Act Transparency Notice (Article 52)

Provides a machine- and human-readable transparency endpoint describing
the AI system's capabilities, limitations, and human oversight mechanisms.
Required for EU AI Act compliance when deploying AI in public services.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AISystemCard(BaseModel):
    """EU AI Act Article 52 — Transparency notice for the AI system."""
    system_name: str
    provider: str
    intended_purpose: str
    ai_model: str
    risk_category: str
    limitations: list[str]
    human_oversight: list[str]
    data_sources: list[str]
    transparency_measures: list[str]
    contact: str
    version: str
    last_updated: str


@router.get("/ai-transparency", response_model=AISystemCard)
async def ai_transparency_notice():
    """
    EU AI Act Article 52 — AI System Transparency Notice.

    Returns a structured card describing the AI system's purpose,
    model, risk classification, limitations, and human oversight.
    """
    return AISystemCard(
        system_name="ULSS 9 Scaligera Healthcare Information Assistant",
        provider="Azienda ULSS 9 Scaligera",
        intended_purpose=(
            "Retrieval-Augmented Generation (RAG) assistant that helps citizens "
            "find healthcare information published on aulss9.veneto.it. "
            "The system searches official documents and generates responses "
            "grounded in verified institutional sources."
        ),
        ai_model="Google Gemini (generative language model)",
        risk_category="Limited risk — informational assistant (not medical decision-making)",
        limitations=[
            "Responses are based solely on indexed documents from aulss9.veneto.it",
            "The system does NOT provide medical diagnoses, prescriptions, or clinical advice",
            "Information may be outdated if source documents have not been re-indexed",
            "The system may occasionally generate inaccurate summaries of source material",
            "Multi-language support is provided via machine translation and may contain errors",
            "The system cannot access real-time data (appointments, wait times, availability)",
        ],
        human_oversight=[
            "All source documents are uploaded and managed by authorised administrators",
            "Administrators can create response corrections to override RAG outputs",
            "An admin dashboard provides visibility into system usage and response quality",
            "Chat interaction metadata (anonymised) is logged for quality monitoring",
            "The system is supervised by ULSS 9 Scaligera's IT department",
        ],
        data_sources=[
            "Official documents published on aulss9.veneto.it",
            "Allegato A categories: general information, opening hours, locations, services",
            "Additional document categories added by administrators",
        ],
        transparency_measures=[
            "All responses cite source documents with titles and snippets",
            "Users are informed they are interacting with an AI assistant",
            "This transparency notice is publicly accessible via API",
            "Chat logs are anonymised (hashed IPs, no message content stored)",
            "GDPR Data Subject Rights endpoints are available for data access and erasure",
        ],
        contact="urp@aulss9.veneto.it",
        version="2.2.0",
        last_updated="2026-03-08",
    )
