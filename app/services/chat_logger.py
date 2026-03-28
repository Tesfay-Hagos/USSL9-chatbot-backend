"""
Anonymised Chat Log Service (GDPR-compliant)

Records interaction metadata (hashed IP, domain, message length, etc.)
but NEVER stores message content. Supports auto-purge based on LOG_RETENTION_DAYS.
"""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, and_

from app.config import CHAT_LOG_ANONYMISE, LOG_RETENTION_DAYS
from app.core.audit import _hash_ip
from app.core.database import get_db
from app.core.models import ChatLogRecord

logger = logging.getLogger(__name__)


async def get_conversation_history(
    conversation_id: str,
    limit: int = 10,
) -> list[dict]:
    """
    Return the last `limit` turns for a conversation as a list of
    [{"role": "user", "content": "..."}, {"role": "model", "content": "..."}, ...]
    ordered oldest → newest, ready to pass to the Gemini chat session.
    """
    async with get_db() as db:
        stmt = (
            select(ChatLogRecord)
            .where(
                and_(
                    ChatLogRecord.conversation_id == conversation_id,
                    ChatLogRecord.message_text.isnot(None),
                    ChatLogRecord.response_text.isnot(None),
                )
            )
            .order_by(ChatLogRecord.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = list(result.scalars().all())

    # Reverse to chronological order and build alternating user/model turns
    history: list[dict] = []
    for row in reversed(rows):
        history.append({"role": "user", "content": row.message_text})
        history.append({"role": "model", "content": row.response_text})
    return history


async def log_chat(
    ip: str | None = None,
    conversation_id: str | None = None,
    domain: str | None = None,
    stores_used: list[str] | None = None,
    language: str = "it",
    message_text: str | None = None,
    response_text: str | None = None,
    message_length: int | None = None,
    response_length: int | None = None,
    has_sources: bool = False,
    correction_applied: str | None = None,
) -> None:
    """
    Record a chat interaction.

    IP is hashed (no user-identifying data). Query and response text are stored
    for admin review and correction workflows (approved by data controller).
    """
    try:
        async with get_db() as db:
            record = ChatLogRecord(
                id=uuid.uuid4().hex,
                ip_hash=_hash_ip(ip) if CHAT_LOG_ANONYMISE and ip else ip,
                conversation_id=conversation_id,
                domain=domain,
                stores_used=json.dumps(stores_used) if stores_used else None,
                language=language,
                message_text=message_text,
                response_text=response_text,
                message_length=message_length,
                response_length=response_length,
                has_sources=has_sources,
                correction_applied=correction_applied,
                created_at=datetime.now(UTC),
            )
            db.add(record)
    except Exception as e:
        logger.error("Failed to log chat", extra={"error": str(e)})


async def list_chat_logs(
    limit: int = 50,
    offset: int = 0,
    domain: str | None = None,
    language: str | None = None,
) -> tuple[list[ChatLogRecord], int]:
    """
    List chat logs with pagination and filtering.

    Returns (logs, total_count).
    """
    async with get_db() as db:
        stmt = select(ChatLogRecord).order_by(ChatLogRecord.created_at.desc())
        count_stmt = select(func.count(ChatLogRecord.id))

        if domain:
            stmt = stmt.where(ChatLogRecord.domain == domain)
            count_stmt = count_stmt.where(ChatLogRecord.domain == domain)
        if language:
            stmt = stmt.where(ChatLogRecord.language == language)
            count_stmt = count_stmt.where(ChatLogRecord.language == language)

        total = (await db.execute(count_stmt)).scalar() or 0
        result = await db.execute(stmt.limit(limit).offset(offset))
        logs = list(result.scalars().all())

        return logs, total


async def purge_old_logs() -> int:
    """
    Delete chat logs older than LOG_RETENTION_DAYS.

    Returns the number of rows deleted.
    """
    cutoff = datetime.now(UTC) - timedelta(days=LOG_RETENTION_DAYS)
    async with get_db() as db:
        result = await db.execute(
            delete(ChatLogRecord).where(ChatLogRecord.created_at < cutoff)
        )
        count = result.rowcount
        if count > 0:
            logger.info("Purged old chat logs", extra={"deleted": count, "retention_days": LOG_RETENTION_DAYS})
        return count
