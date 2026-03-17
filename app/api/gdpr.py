"""
GDPR Data Subject Rights API (Article 15 + Article 17)

Provides admin endpoints for:
- Right to Access (Article 15): export all data linked to a hashed IP
- Right to Erasure (Article 17): delete all data linked to a hashed IP
- Data Processing Register (Article 30): machine-readable processing record
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.auth import require_admin
from app.config import (
    AUDIT_RETENTION_DAYS,
    LOG_RETENTION_DAYS,
)
from app.core.audit import _hash_ip, log_admin_action
from app.core.database import get_db
from app.core.models import ChatLogRecord
from app.core.utils import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter()





# ── Schemas ──


class DataAccessResponse(BaseModel):
    """GDPR Article 15 — Data Subject Access response."""
    ip_hash: str
    record_count: int
    records: list[dict]
    exported_at: str


class DataErasureResponse(BaseModel):
    """GDPR Article 17 — Right to Erasure response."""
    ip_hash: str
    records_deleted: int
    erased_at: str


class DataAccessRequest(BaseModel):
    """Request body for DSR lookup by raw IP (hashed server-side)."""
    ip_address: str = Field(min_length=3, max_length=45, description="IP address to look up (will be hashed)")


class ProcessingActivity(BaseModel):
    """Article 30 — Record of Processing Activities entry."""
    activity: str
    purpose: str
    legal_basis: str
    data_categories: list[str]
    retention_period: str
    recipients: list[str]


# ── Article 15: Right to Access ──


@router.post("/gdpr/access", response_model=DataAccessResponse)
async def data_subject_access(
    body: DataAccessRequest,
    request: Request,
    username: str = Depends(require_admin),
):
    """
    Export all data linked to a given IP address (GDPR Article 15).

    The IP is hashed server-side using the same salt as audit logs,
    then all matching chat logs are returned. No message content is stored.
    """
    ip_hash = _hash_ip(body.ip_address)

    from sqlalchemy import select
    async with get_db() as db:
        result = await db.execute(
            select(ChatLogRecord)
            .where(ChatLogRecord.ip_hash == ip_hash)
            .order_by(ChatLogRecord.created_at.desc())
        )
        records = result.scalars().all()

    log_admin_action(
        username, "gdpr_access_request",
        details={"ip_hash": ip_hash, "records_found": len(records)},
        ip=get_client_ip(request),
        correlation_id=getattr(request.state, "correlation_id", None),
    )

    return DataAccessResponse(
        ip_hash=ip_hash,
        record_count=len(records),
        records=[
            {
                "id": r.id,
                "domain": r.domain,
                "language": r.language,
                "message_length": r.message_length,
                "response_length": r.response_length,
                "has_sources": r.has_sources,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
        exported_at=datetime.now(UTC).isoformat(),
    )


# ── Article 17: Right to Erasure ──


@router.post("/gdpr/erasure", response_model=DataErasureResponse)
async def data_subject_erasure(
    body: DataAccessRequest,
    request: Request,
    username: str = Depends(require_admin),
):
    """
    Delete all data linked to a given IP address (GDPR Article 17).

    Permanently removes all chat log records matching the hashed IP.
    """
    ip_hash = _hash_ip(body.ip_address)

    from sqlalchemy import delete
    async with get_db() as db:
        result = await db.execute(
            delete(ChatLogRecord).where(ChatLogRecord.ip_hash == ip_hash)
        )
        deleted = result.rowcount

    log_admin_action(
        username, "gdpr_erasure_request",
        details={"ip_hash": ip_hash, "records_deleted": deleted},
        ip=get_client_ip(request),
        correlation_id=getattr(request.state, "correlation_id", None),
    )

    return DataErasureResponse(
        ip_hash=ip_hash,
        records_deleted=deleted,
        erased_at=datetime.now(UTC).isoformat(),
    )


# ── Article 30: Record of Processing Activities ──


@router.get("/gdpr/processing-register", response_model=list[ProcessingActivity])
async def processing_register(username: str = Depends(require_admin)):
    """
    Machine-readable register of data processing activities (GDPR Article 30).

    Returns a structured list of all personal data processing performed
    by the ULSS 9 chatbot system.
    """
    return [
        ProcessingActivity(
            activity="Chat interaction logging",
            purpose="Operational analytics, service quality monitoring",
            legal_basis="Legitimate interest (Article 6(1)(f))",
            data_categories=["Hashed IP address", "Domain", "Language", "Message length"],
            retention_period=f"{LOG_RETENTION_DAYS} days (auto-purge)",
            recipients=["System administrators"],
        ),
        ProcessingActivity(
            activity="Admin audit logging",
            purpose="Security, accountability, compliance",
            legal_basis="Legal obligation (Article 6(1)(c))",
            data_categories=["Hashed IP address", "Admin username", "Action type"],
            retention_period=f"{AUDIT_RETENTION_DAYS} days",
            recipients=["System administrators", "DPO"],
        ),
        ProcessingActivity(
            activity="Session token issuance",
            purpose="API access control and abuse prevention",
            legal_basis="Legitimate interest (Article 6(1)(f))",
            data_categories=["Client IP (not stored)", "Token nonce (ephemeral)"],
            retention_period="Stateless — no server-side storage",
            recipients=["None (client-side only)"],
        ),
        ProcessingActivity(
            activity="Chat response generation (RAG)",
            purpose="Provide healthcare information to citizens",
            legal_basis="Public interest (Article 6(1)(e))",
            data_categories=["User query (not stored)", "Response text (not stored)"],
            retention_period="Not retained — processed in memory only",
            recipients=["Google Gemini API (data processor)"],
        ),
    ]
