"""
Response Corrections Service

Admin-managed corrections injected into Gemini stores as structured Q&A documents.
Gemini's multilingual semantic retrieval handles matching across all languages.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update

from app.core.database import get_db
from app.core.models import CorrectionRecord
from app.services.correction_injector import inject_correction, remove_injection

logger = logging.getLogger(__name__)


async def create_correction(
    query_pattern: str,
    corrected_response: str,
    domain: str,
    created_by: str,
) -> CorrectionRecord:
    """
    Create a new correction and inject it into the relevant Gemini store.

    1. Write to DB with injection_status='pending'
    2. Upload Q&A document to Gemini store
    3. Update injection_status to 'injected' or 'failed'
    """
    now = datetime.now(UTC)
    correction_id = uuid.uuid4().hex

    async with get_db() as db:
        record = CorrectionRecord(
            id=correction_id,
            query_pattern=query_pattern,
            corrected_response=corrected_response,
            domain=domain,
            created_by=created_by,
            is_active=True,
            injection_status="pending",
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        await db.flush()

    # Inject into Gemini store (non-blocking — we already committed the DB record)
    gemini_doc_name = await inject_correction(
        correction_id=correction_id,
        query_pattern=query_pattern,
        corrected_response=corrected_response,
        domain=domain,
    )

    # Update injection status
    status = "injected" if gemini_doc_name else "failed"
    async with get_db() as db:
        await db.execute(
            update(CorrectionRecord)
            .where(CorrectionRecord.id == correction_id)
            .values(
                injection_status=status,
                gemini_doc_name=gemini_doc_name,
                updated_at=datetime.now(UTC),
            )
        )

    # Re-fetch updated record
    async with get_db() as db:
        record = await db.get(CorrectionRecord, correction_id)
    return record


async def list_corrections(active_only: bool = False) -> list[CorrectionRecord]:
    """List all corrections, optionally filtered to active only."""
    async with get_db() as db:
        stmt = select(CorrectionRecord).order_by(CorrectionRecord.created_at.desc())
        if active_only:
            stmt = stmt.where(CorrectionRecord.is_active.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())


async def get_correction(correction_id: str) -> CorrectionRecord | None:
    """Get a single correction by ID."""
    async with get_db() as db:
        return await db.get(CorrectionRecord, correction_id)


async def update_correction(
    correction_id: str,
    query_pattern: str | None = None,
    corrected_response: str | None = None,
    domain: str | None = None,
    is_active: bool | None = None,
) -> bool:
    """
    Update an existing correction.

    If query_pattern or corrected_response changes, re-inject the document.
    If is_active is set to False, remove the injected document.
    Returns True if found and updated.
    """
    # Get current record first
    async with get_db() as db:
        current = await db.get(CorrectionRecord, correction_id)
        if not current:
            return False

    values: dict = {"updated_at": datetime.now(UTC)}
    needs_reinjection = False

    if query_pattern is not None:
        values["query_pattern"] = query_pattern
        needs_reinjection = True
    if corrected_response is not None:
        values["corrected_response"] = corrected_response
        needs_reinjection = True
    if domain is not None:
        values["domain"] = domain
        needs_reinjection = True
    if is_active is not None:
        values["is_active"] = is_active

    # If deactivating, remove injection
    if is_active is False and current.gemini_doc_name:
        await remove_injection(
            gemini_doc_name=current.gemini_doc_name,
            domain=current.domain,
            correction_id=correction_id,
        )
        values["gemini_doc_name"] = None
        values["injection_status"] = "pending"
        needs_reinjection = False

    async with get_db() as db:
        result = await db.execute(
            update(CorrectionRecord)
            .where(CorrectionRecord.id == correction_id)
            .values(**values)
        )

    # Re-inject if content changed and correction is active
    if needs_reinjection and (is_active is not False):
        # Remove old injection first
        if current.gemini_doc_name:
            await remove_injection(
                gemini_doc_name=current.gemini_doc_name,
                domain=current.domain,
                correction_id=correction_id,
            )

        target_domain = domain or current.domain
        target_pattern = query_pattern or current.query_pattern
        target_response = corrected_response or current.corrected_response

        gemini_doc_name = await inject_correction(
            correction_id=correction_id,
            query_pattern=target_pattern,
            corrected_response=target_response,
            domain=target_domain,
        )

        status = "injected" if gemini_doc_name else "failed"
        async with get_db() as db:
            await db.execute(
                update(CorrectionRecord)
                .where(CorrectionRecord.id == correction_id)
                .values(injection_status=status, gemini_doc_name=gemini_doc_name)
            )

    return result.rowcount > 0


async def delete_correction(correction_id: str) -> bool:
    """
    Delete a correction and remove its injected document from Gemini.
    Returns True if found and deleted.
    """
    # Get record first for cleanup
    async with get_db() as db:
        record = await db.get(CorrectionRecord, correction_id)
        if not record:
            return False

    # Remove from Gemini if injected
    if record.gemini_doc_name:
        await remove_injection(
            gemini_doc_name=record.gemini_doc_name,
            domain=record.domain,
            correction_id=correction_id,
        )

    # Delete from DB
    async with get_db() as db:
        result = await db.execute(
            delete(CorrectionRecord).where(CorrectionRecord.id == correction_id)
        )
        return result.rowcount > 0
