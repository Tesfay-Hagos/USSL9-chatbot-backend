"""
Database-backed Store Registry Service

Replaces the in-memory ULSS9_STORES list with a persistent PostgreSQL/SQLite table.
Seeds the four Allegato A stores on first run.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update

from app.config import ULSS9_STORES
from app.core.database import get_db
from app.core.models import DocumentRecord, StoreRecord

logger = logging.getLogger(__name__)


# ── Store CRUD ──────────────────────────────────────


async def seed_initial_stores() -> None:
    """Seed the initial public store if it doesn't exist yet."""
    async with get_db() as db:
        for store_def in ULSS9_STORES:
            existing = await db.get(StoreRecord, store_def["id"])
            if not existing:
                record = StoreRecord(
                    id=store_def["id"],
                    display_name=store_def.get("display_name", store_def["id"]),
                    description=store_def.get("description", ""),
                    is_initial=True,
                    is_public=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                db.add(record)
                logger.info("Seeded initial store: %s", store_def["id"])
    logger.info("Store registry seeding complete")


async def register_store(
    domain: str,
    display_name: str,
    description: str = "",
    gemini_store_name: str | None = None,
    is_initial: bool = False,
    is_public: bool = True,
) -> StoreRecord:
    """Register a store in the database (or update if exists)."""
    now = datetime.now(UTC)
    async with get_db() as db:
        existing = await db.get(StoreRecord, domain)
        if existing:
            existing.display_name = display_name
            existing.description = description or existing.description
            existing.gemini_store_name = gemini_store_name or existing.gemini_store_name
            existing.is_public = is_public
            existing.updated_at = now
            await db.flush()
            return existing
        record = StoreRecord(
            id=domain,
            gemini_store_name=gemini_store_name,
            display_name=display_name,
            description=description,
            is_initial=is_initial,
            is_public=is_public,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        await db.flush()
        return record


async def get_store(domain: str) -> StoreRecord | None:
    """Get a store by domain id."""
    async with get_db() as db:
        return await db.get(StoreRecord, domain)


async def list_stores() -> list[StoreRecord]:
    """List all registered stores."""
    async with get_db() as db:
        result = await db.execute(
            select(StoreRecord).order_by(StoreRecord.is_initial.desc(), StoreRecord.id)
        )
        return list(result.scalars().all())


async def list_public_stores() -> list[StoreRecord]:
    """List stores visible in the public chatbot (is_public=True)."""
    async with get_db() as db:
        result = await db.execute(
            select(StoreRecord)
            .where(StoreRecord.is_public.is_(True))
            .order_by(StoreRecord.is_initial.desc(), StoreRecord.id)
        )
        return list(result.scalars().all())


async def delete_store(domain: str) -> bool:
    """Delete a store from the registry."""
    async with get_db() as db:
        result = await db.execute(
            delete(StoreRecord).where(StoreRecord.id == domain)
        )
        return result.rowcount > 0


async def update_gemini_name(domain: str, gemini_store_name: str) -> None:
    """Update the Gemini resource name for a store."""
    async with get_db() as db:
        await db.execute(
            update(StoreRecord)
            .where(StoreRecord.id == domain)
            .values(gemini_store_name=gemini_store_name, updated_at=datetime.now(UTC))
        )


async def update_store_visibility(domain: str, is_public: bool) -> bool:
    """Update is_public for a store. Returns True if updated."""
    async with get_db() as db:
        result = await db.execute(
            update(StoreRecord)
            .where(StoreRecord.id == domain)
            .values(is_public=is_public, updated_at=datetime.now(UTC))
        )
        return result.rowcount is not None and result.rowcount > 0


# ── Document CRUD ──────────────────────────────────


async def register_document(
    store_id: str,
    filename: str,
    gemini_doc_name: str | None = None,
    title: str | None = None,
    source_type: str = "attachment",
    url: str | None = None,
    metadata_json: str = "{}",
) -> DocumentRecord:
    """Register a document in the database."""
    doc_id = uuid.uuid4().hex
    now = datetime.now(UTC)
    async with get_db() as db:
        record = DocumentRecord(
            id=doc_id,
            store_id=store_id,
            filename=filename,
            gemini_doc_name=gemini_doc_name,
            title=title,
            source_type=source_type,
            url=url,
            metadata_json=metadata_json,
            uploaded_at=now,
        )
        db.add(record)
        await db.flush()
        return record


async def get_document_by_filename(store_id: str, filename: str) -> DocumentRecord | None:
    """Get a document by store and filename."""
    async with get_db() as db:
        result = await db.execute(
            select(DocumentRecord)
            .where(DocumentRecord.store_id == store_id, DocumentRecord.filename == filename)
        )
        return result.scalars().first()


async def list_documents(store_id: str) -> list[DocumentRecord]:
    """List all documents in a store."""
    async with get_db() as db:
        result = await db.execute(
            select(DocumentRecord)
            .where(DocumentRecord.store_id == store_id)
            .order_by(DocumentRecord.uploaded_at.desc())
        )
        return list(result.scalars().all())


async def delete_document(doc_id: str) -> bool:
    """Delete a document from the registry."""
    async with get_db() as db:
        result = await db.execute(
            delete(DocumentRecord).where(DocumentRecord.id == doc_id)
        )
        return result.rowcount > 0


async def delete_document_by_filename(store_id: str, filename: str) -> bool:
    """Delete a document by store and filename."""
    async with get_db() as db:
        result = await db.execute(
            delete(DocumentRecord)
            .where(DocumentRecord.store_id == store_id, DocumentRecord.filename == filename)
        )
        return result.rowcount > 0
