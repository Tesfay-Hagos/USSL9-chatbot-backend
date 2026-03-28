"""
SQLAlchemy ORM Models for ULSS 9 Chatbot

Tables: store_registry, documents, corrections, chat_logs.
PostgreSQL-native, pgvector-ready for future embedding storage.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class AdminUser(Base):
    """Admin users — login via email, password reset supported."""

    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), default="")  # e.g. "Admin"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<AdminUser email={self.email!r}>"


class StoreRecord(Base):
    """Database-backed store registry (replaces in-memory ULSS9_STORES)."""

    __tablename__ = "store_registry"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # domain slug
    gemini_store_name: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)  # show in public chatbot
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    documents: Mapped[list["DocumentRecord"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<StoreRecord id={self.id!r} display_name={self.display_name!r}>"


class DocumentRecord(Base):
    """Document metadata tracked in DB alongside Gemini."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # UUID hex
    store_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("store_registry.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    gemini_doc_name: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(50), default="attachment")
    url: Mapped[str | None] = mapped_column(String(2000))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    store: Mapped["StoreRecord"] = relationship(back_populates="documents")

    def __repr__(self) -> str:
        return f"<DocumentRecord id={self.id!r} filename={self.filename!r}>"


class CorrectionRecord(Base):
    """Admin-managed response corrections — injected into Gemini stores."""

    __tablename__ = "corrections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_response: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, default="general_info")
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    gemini_doc_name: Mapped[str | None] = mapped_column(String(500))
    injection_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | injected | failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<CorrectionRecord id={self.id!r} domain={self.domain!r} status={self.injection_status!r}>"


class ChatLogRecord(Base):
    """Chat interaction logs — IP is hashed, no user-identifying data stored."""

    __tablename__ = "chat_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ip_hash: Mapped[str | None] = mapped_column(String(16))
    conversation_id: Mapped[str | None] = mapped_column(String(100), index=True)
    domain: Mapped[str | None] = mapped_column(String(100))
    stores_used: Mapped[str | None] = mapped_column(Text)  # JSON array
    language: Mapped[str] = mapped_column(String(5), default="it")
    message_text: Mapped[str | None] = mapped_column(Text)   # user query
    response_text: Mapped[str | None] = mapped_column(Text)  # bot response
    message_length: Mapped[int | None] = mapped_column(Integer)
    response_length: Mapped[int | None] = mapped_column(Integer)
    has_sources: Mapped[bool] = mapped_column(Boolean, default=False)
    correction_applied: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<ChatLogRecord id={self.id!r} domain={self.domain!r}>"


class ScrapedPageRecord(Base):
    """
    Persistent manifest of every URL successfully scraped.

    Enables resume-on-restart: a new scrape job loads this set first and
    skips any URL already present, so only new/missing pages are re-fetched.
    The content_hash allows detecting stale pages if we want to force-refresh
    specific URLs in the future.
    """

    __tablename__ = "scraped_pages"

    url: Mapped[str] = mapped_column(String(2000), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str | None] = mapped_column(String(32))   # md5 hex of extracted text
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    batch_file: Mapped[str | None] = mapped_column(String(500))    # batch .md filename
    job_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_scraped_pages_job_id", "job_id"),
    )

    def __repr__(self) -> str:
        return f"<ScrapedPageRecord url={self.url!r} job={self.job_id!r}>"
