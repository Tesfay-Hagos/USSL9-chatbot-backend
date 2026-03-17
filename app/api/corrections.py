"""
Admin API — Corrections CRUD + Chat Log Viewer

Admin-only endpoints for managing response corrections (with Gemini store
injection) and viewing anonymised chat interaction logs.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.auth import require_admin
from app.core.audit import log_admin_action
from app.core.utils import get_client_ip
from app.services import chat_logger, corrections

logger = logging.getLogger(__name__)

router = APIRouter()





# ── Schemas ──


class CreateCorrectionRequest(BaseModel):
    query_pattern: str = Field(min_length=3, max_length=1000)
    corrected_response: str = Field(min_length=1, max_length=5000)
    domain: str = Field(
        min_length=1, max_length=100,
        description="Target store domain (e.g. general_info, hours)",
    )


class UpdateCorrectionRequest(BaseModel):
    query_pattern: str | None = Field(None, min_length=3, max_length=1000)
    corrected_response: str | None = Field(None, min_length=1, max_length=5000)
    domain: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None


class CorrectionResponse(BaseModel):
    id: str
    query_pattern: str
    corrected_response: str
    domain: str
    created_by: str
    is_active: bool
    injection_status: str
    gemini_doc_name: str | None
    created_at: str
    updated_at: str


class ChatLogResponse(BaseModel):
    id: str
    ip_hash: str | None
    domain: str | None
    stores_used: str | None
    language: str
    message_text: str | None
    response_text: str | None
    message_length: int | None
    response_length: int | None
    has_sources: bool
    correction_applied: str | None
    created_at: str


class PaginatedChatLogs(BaseModel):
    logs: list[ChatLogResponse]
    total: int
    limit: int
    offset: int


# ── Corrections Endpoints ──


@router.post("/corrections", response_model=CorrectionResponse)
async def create_correction(
    body: CreateCorrectionRequest,
    request: Request,
    username: str = Depends(require_admin),
):
    """
    Create a new response correction.

    The correction is written to the DB and injected as a Q&A document
    into the specified Gemini store for multilingual semantic retrieval.
    """
    record = await corrections.create_correction(
        query_pattern=body.query_pattern,
        corrected_response=body.corrected_response,
        domain=body.domain,
        created_by=username,
    )
    log_admin_action(
        username, "create_correction",
        details={"pattern": body.query_pattern[:50], "domain": body.domain},
        ip=get_client_ip(request),
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return _correction_to_response(record)


@router.get("/corrections", response_model=list[CorrectionResponse])
async def list_all_corrections(
    active_only: bool = Query(False),
    username: str = Depends(require_admin),
):
    """List all corrections with their injection status."""
    records = await corrections.list_corrections(active_only=active_only)
    return [_correction_to_response(r) for r in records]


@router.put("/corrections/{correction_id}", response_model=CorrectionResponse)
async def update_correction(
    correction_id: str,
    body: UpdateCorrectionRequest,
    request: Request,
    username: str = Depends(require_admin),
):
    """
    Update an existing correction.

    If content changes, the injected document is re-uploaded to Gemini.
    If deactivated, the injected document is removed from the store.
    """
    success = await corrections.update_correction(
        correction_id=correction_id,
        query_pattern=body.query_pattern,
        corrected_response=body.corrected_response,
        domain=body.domain,
        is_active=body.is_active,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Correction not found")

    record = await corrections.get_correction(correction_id)
    log_admin_action(
        username, "update_correction",
        resource=correction_id,
        ip=get_client_ip(request),
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return _correction_to_response(record)


@router.delete("/corrections/{correction_id}")
async def delete_correction(
    correction_id: str,
    request: Request,
    username: str = Depends(require_admin),
):
    """
    Delete a correction.

    Also removes the injected Q&A document from the Gemini store.
    """
    success = await corrections.delete_correction(correction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Correction not found")

    log_admin_action(
        username, "delete_correction",
        resource=correction_id,
        ip=get_client_ip(request),
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return {"success": True, "message": "Correction deleted and injection removed"}


# ── Chat Log Viewer ──


@router.get("/chat-logs", response_model=PaginatedChatLogs)
async def get_chat_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    domain: str | None = Query(None),
    language: str | None = Query(None),
    username: str = Depends(require_admin),
):
    """View anonymised chat logs with pagination and filtering."""
    logs, total = await chat_logger.list_chat_logs(
        limit=limit, offset=offset, domain=domain, language=language,
    )
    return PaginatedChatLogs(
        logs=[_chatlog_to_response(log) for log in logs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/chat-logs/purge")
async def purge_chat_logs(
    request: Request,
    username: str = Depends(require_admin),
):
    """Purge chat logs older than LOG_RETENTION_DAYS."""
    deleted = await chat_logger.purge_old_logs()
    log_admin_action(
        username, "purge_chat_logs",
        details={"deleted": deleted},
        ip=get_client_ip(request),
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return {"success": True, "deleted": deleted}


# ── Helpers ──


def _correction_to_response(record) -> CorrectionResponse:
    return CorrectionResponse(
        id=record.id,
        query_pattern=record.query_pattern,
        corrected_response=record.corrected_response,
        domain=record.domain,
        created_by=record.created_by,
        is_active=record.is_active,
        injection_status=record.injection_status,
        gemini_doc_name=record.gemini_doc_name,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


def _chatlog_to_response(record) -> ChatLogResponse:
    return ChatLogResponse(
        id=record.id,
        ip_hash=record.ip_hash,
        domain=record.domain,
        stores_used=record.stores_used,
        language=record.language,
        message_text=record.message_text,
        response_text=record.response_text,
        message_length=record.message_length,
        response_length=record.response_length,
        has_sources=record.has_sources,
        correction_applied=record.correction_applied,
        created_at=record.created_at.isoformat(),
    )
