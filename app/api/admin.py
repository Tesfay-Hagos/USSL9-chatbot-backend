"""
UniVR Chatbot - Admin API Endpoints

Manage File Search Stores (domains) and documents.
Audit logging for GDPR / government compliance.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.api.auth import require_admin
from app.config import ULSS9_STORES
from app.core.audit import log_admin_action
from app.core.utils import get_client_ip
from app.services import store_registry

logger = logging.getLogger(__name__)

from app.services.store_manager import StoreInfo, StoreManager

router = APIRouter()

# Data directory for uploaded files
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============ Schemas ============

class CreateStoreRequest(BaseModel):
    """Request to create a new store/domain."""
    domain: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    description: str = Field("", max_length=500)
    is_public: bool = Field(True, description="Show in public chatbot category picker")


class CreateStoreResponse(BaseModel):
    """Response after creating a store."""
    success: bool
    domain: str
    store_name: str
    message: str


class UploadResponse(BaseModel):
    """Upload response schema."""
    success: bool
    filename: str
    domain: str
    message: str
    document_id: str | None = None
    title: str | None = None


class AdminStoreInfo(StoreInfo):
    """Store info with is_public for admin UI."""

    is_public: bool = True


class UpdateStoreVisibilityRequest(BaseModel):
    """Request to update store visibility in public chatbot."""

    is_public: bool


class DocumentInfo(BaseModel):
    """Document information schema."""
    name: str
    display_name: str
    metadata: dict = {}


# ============ Store Management ============

@router.post("/stores", response_model=CreateStoreResponse)
async def create_store(
    request: Request,
    body: CreateStoreRequest,
    username: str = Depends(require_admin),
):
    """
    Create a new File Search Store (category) for RAG.
    Use for stores beyond the four initial areas (Allegato A).
    Saves the description so store selection can include this category.
    """
    try:
        store_manager = StoreManager()
        store = await store_manager.create_store(body.domain, body.description)
        # Register in DB
        await store_registry.register_store(
            domain=body.domain,
            display_name=store.display_name or f"{body.domain}",
            description=body.description,
            gemini_store_name=store.name,
            is_public=body.is_public,
        )
        log_admin_action(
            username, "create_store", resource=body.domain,
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return CreateStoreResponse(
            success=True,
            domain=body.domain,
            store_name=store.name,
            message=f"Store for domain '{body.domain}' created successfully"
        )
    except Exception as e:
        logger.error(f"Create store error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores", response_model=list[AdminStoreInfo])
async def list_stores(username: str = Depends(require_admin)):
    """List all available stores/domains with is_public from registry."""
    try:
        store_manager = StoreManager()
        stores = await store_manager.list_stores()
        # Merge is_public from store_registry (default True if not in registry)
        registry_by_domain = {r.id: r for r in await store_registry.list_stores()}
        return [
            AdminStoreInfo(
                name=s.name,
                display_name=s.display_name,
                domain=s.domain,
                document_count=s.document_count,
                is_public=registry_by_domain[s.domain].is_public if s.domain in registry_by_domain else True,
            )
            for s in stores
        ]
    except Exception as e:
        logger.error(f"List stores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{domain}/health")
async def store_health(
    domain: str,
    username: str = Depends(require_admin),
):
    """
    Store health check for admin dashboard.
    Checks Gemini connectivity, document count, and DB sync status.
    """
    try:
        db_store = await store_registry.get_store(domain)
        store_manager = StoreManager()
        gemini_store = store_manager.get_store(domain)
        docs = await store_manager.list_documents(domain) if gemini_store else []

        return {
            "domain": domain,
            "in_database": db_store is not None,
            "in_gemini": gemini_store is not None,
            "gemini_store_name": gemini_store.name if gemini_store else None,
            "document_count": len(docs),
            "documents": [
                {"name": d.get("display_name", ""), "metadata": d.get("metadata", {})}
                for d in docs[:20]  # Limit to 20 for dashboard
            ],
            "status": "healthy" if (db_store and gemini_store) else "degraded",
        }
    except Exception as e:
        logger.error(f"Store health check error: {e}")
        return {
            "domain": domain,
            "status": "error",
            "error": str(e),
        }


@router.patch("/stores/{domain}")
async def update_store_visibility(
    domain: str,
    request: Request,
    body: UpdateStoreVisibilityRequest,
    username: str = Depends(require_admin),
):
    """Update whether a store is shown in the public chatbot."""
    try:
        updated = await store_registry.update_store_visibility(domain, body.is_public)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Store '{domain}' not found in registry")
        log_admin_action(
            username, "update_store_visibility", resource=domain,
            details={"is_public": body.is_public},
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return {"success": True, "is_public": body.is_public}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update store visibility error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/stores/{domain}")
async def delete_store(
    domain: str,
    request: Request,
    username: str = Depends(require_admin),
):
    """Delete a store and all its documents."""
    try:
        store_manager = StoreManager()
        success = await store_manager.delete_store(domain)

        if not success:
            raise HTTPException(status_code=404, detail=f"Store '{domain}' not found")
        log_admin_action(
            username, "delete_store", resource=domain,
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return {"success": True, "message": f"Store '{domain}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete store error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stores/delete-all")
async def delete_all_stores(
    request: Request,
    username: str = Depends(require_admin),
):
    """
    Delete all File Search Stores from Gemini AND all store_registry records from DB.
    On next startup, seed_initial_stores() and the lifespan Gemini creation will re-create everything.
    """
    try:
        store_manager = StoreManager()

        # 1. Delete all Gemini stores that carry our prefix
        gemini_stores = await store_manager.list_stores()
        deleted_gemini: list[str] = []
        for s in gemini_stores:
            try:
                if await store_manager.delete_store(s.domain):
                    deleted_gemini.append(s.domain)
                    logger.info(f"Deleted Gemini store: {s.domain}")
            except Exception as e:
                logger.warning(f"Failed to delete Gemini store {s.domain}: {e}")

        # 2. Delete ALL store_registry rows from DB (including is_initial ones).
        #    DocumentRecord rows cascade automatically (ondelete=CASCADE + ORM cascade).
        db_stores = await store_registry.list_stores()
        deleted_db: list[str] = []
        for s in db_stores:
            if await store_registry.delete_store(s.id):
                deleted_db.append(s.id)
                logger.info(f"Deleted DB store record: {s.id}")

        log_admin_action(
            username, "delete_all_stores",
            details={"deleted_gemini": deleted_gemini, "deleted_db": deleted_db},
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return {
            "success": True,
            "message": (
                f"Deleted {len(deleted_gemini)} Gemini store(s) and "
                f"{len(deleted_db)} DB record(s). "
                "Restart the backend to re-seed the initial stores."
            ),
            "deleted_gemini": deleted_gemini,
            "deleted_db": deleted_db,
        }
    except Exception as e:
        logger.error(f"Delete all stores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stores/ulss9/create-all")
async def create_all_ulss9_stores(
    request: Request,
    username: str = Depends(require_admin),
):
    """Create the four initial stores from Allegato A (idempotent). Others can be added via POST /stores."""
    try:
        store_manager = StoreManager()
        created = []
        for s in ULSS9_STORES:
            domain = s["id"]
            desc = s.get("description", "")
            store = await store_manager.create_store(domain, desc)
            await store_registry.update_gemini_name(domain, store.name)
            created.append({"domain": domain, "store_name": store.name})
        log_admin_action(
            username, "create_all_ulss9_stores", details={"stores": [s["id"] for s in ULSS9_STORES]},
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return {"success": True, "message": "ULSS 9 stores ensured", "stores": created}
    except Exception as e:
        logger.error(f"Create all ULSS9 stores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Overview / Stats ============

@router.get("/overview")
async def get_overview(username: str = Depends(require_admin)):
    """
    Dashboard overview: aggregates real stats from DB and Gemini.
    Returns total docs, total chat sessions, active corrections, and
    the per-day chat count for the last 7 days.
    """
    import datetime

    from sqlalchemy import func, select

    from app.core.database import get_db
    from app.core.models import ChatLogRecord, CorrectionRecord

    try:
        store_manager = StoreManager()
        stores = await store_manager.list_stores()
        total_docs = sum(s.document_count for s in stores)
        total_stores = len(stores)
    except Exception:
        total_docs = 0
        total_stores = 0

    try:
        async with get_db() as session:
            # Total chat sessions
            total_logs_result = await session.execute(select(func.count()).select_from(ChatLogRecord))
            total_logs: int = total_logs_result.scalar_one() or 0

            # Active corrections count
            active_corrections_result = await session.execute(
                select(func.count()).select_from(CorrectionRecord).where(CorrectionRecord.is_active == True)  # noqa: E712
            )
            active_corrections: int = active_corrections_result.scalar_one() or 0

            # Per-day chat volume for the last 7 days
            today = datetime.date.today()
            daily_counts: list[int] = []
            for i in range(6, -1, -1):
                day = today - datetime.timedelta(days=i)
                day_start = datetime.datetime.combine(day, datetime.time.min)
                day_end = datetime.datetime.combine(day, datetime.time.max)
                r = await session.execute(
                    select(func.count()).select_from(ChatLogRecord).where(
                        ChatLogRecord.created_at >= day_start,
                        ChatLogRecord.created_at <= day_end,
                    )
                )
                daily_counts.append(r.scalar_one() or 0)

            # Languages breakdown from last 30 days
            thirty_days_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=30)
            lang_result = await session.execute(
                select(ChatLogRecord.language, func.count().label("cnt"))
                .where(ChatLogRecord.created_at >= thirty_days_ago)
                .group_by(ChatLogRecord.language)
                .order_by(func.count().desc())
                .limit(10)
            )
            languages = [{"lang": row.language or "it", "count": row.cnt} for row in lang_result.all()]

    except Exception:
        total_logs = 0
        active_corrections = 0
        daily_counts = [0] * 7
        languages = []

    return {
        "total_documents": total_docs,
        "total_stores": total_stores,
        "total_chat_sessions": total_logs,
        "active_corrections": active_corrections,
        "chat_volume_last_7_days": daily_counts,
        "language_breakdown": languages,
    }


# ============ Document Management ============

@router.post("/stores/{domain}/upload", response_model=UploadResponse)
async def upload_document(
    domain: str,
    request: Request,
    file: UploadFile = File(...),
    username: str = Depends(require_admin),
):
    """
    Upload a document to a domain's File Search Store.
    
    If a document with the same filename exists, it will be replaced.
    """
    try:
        # Validate file type
        if not file.filename.endswith((".pdf", ".md", ".txt", ".docx")):
            raise HTTPException(
                status_code=400,
                detail="Only PDF, Markdown, TXT, and DOCX files are supported"
            )

        # Save the file locally
        file_path = DATA_DIR / file.filename
        content = await file.read()
        file_path.write_bytes(content)

        logger.info(f"Saved file: {file_path}")

        # Upload to File Search Store (attached doc: source_type=attachment, document_id for links)
        store_manager = StoreManager()
        result = await store_manager.upload_document(
            str(file_path),
            domain,
            source_type="attachment",
        )
        log_admin_action(
            username, "upload_document", resource=domain,
            details={"filename": file.filename},
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return UploadResponse(
            success=True,
            filename=file.filename,
            domain=domain,
            message=f"Document '{file.filename}' uploaded to '{domain}' domain",
            document_id=result.get("document_id"),
            title=result.get("title"),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class IngestUrlRequest(BaseModel):
    """Request to ingest a URL into a store."""
    url: str
    title: str | None = None


@router.post("/stores/{domain}/ingest-url", response_model=UploadResponse)
async def ingest_url_to_store(
    domain: str,
    request: Request,
    body: IngestUrlRequest,
    username: str = Depends(require_admin),
):
    """
    Fetch content from a URL and add it to a store.
    PDFs are downloaded directly; HTML pages are converted to text.
    """
    import html as html_module
    import re
    from urllib.parse import unquote, urlparse

    import httpx

    url = body.url.strip()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 ULSS9Bot/1.0"})
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()
        is_pdf = "pdf" in content_type or url.lower().endswith(".pdf")

        # Derive a safe filename from the URL
        parsed = urlparse(url)
        path_part = unquote(parsed.path).rstrip("/").split("/")[-1] or "page"
        path_part = re.sub(r"[^a-z0-9_.-]", "_", path_part.lower())[:60] or "page"

        if is_pdf:
            if not path_part.endswith(".pdf"):
                path_part += ".pdf"
            file_bytes = resp.content
        else:
            if not path_part.endswith(".md"):
                path_part = path_part.rsplit(".", 1)[0] + ".md" if "." in path_part else path_part + ".md"
            # Strip HTML → readable text
            raw = resp.text
            raw = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", raw, flags=re.DOTALL | re.IGNORECASE)
            raw = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*/?>|</?(p|div|h[1-6]|li|tr)>", "\n", raw, flags=re.IGNORECASE)
            raw = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", raw, flags=re.IGNORECASE | re.DOTALL)
            raw = re.sub(r"<[^>]+>", "", raw)
            text = html_module.unescape(raw)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if not text:
                raise HTTPException(status_code=422, detail="Could not extract text content from the URL")
            file_bytes = text.encode("utf-8")

        file_path = DATA_DIR / path_part
        file_path.write_bytes(file_bytes)

        store_manager = StoreManager()
        result = await store_manager.upload_document(
            str(file_path),
            domain,
            source_type="website",
            title_override=body.title,
            url=url,
        )
        log_admin_action(
            username, "ingest_url", resource=domain,
            details={"url": url, "filename": path_part},
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return UploadResponse(
            success=True,
            filename=path_part,
            domain=domain,
            message=f"URL ingested into '{domain}' store",
            document_id=result.get("document_id"),
            title=result.get("title") or body.title or path_part,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch URL ({e.response.status_code}): {url}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=422, detail=f"Network error fetching URL: {e}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{domain}/documents", response_model=list[DocumentInfo])
async def list_documents(domain: str, username: str = Depends(require_admin)):
    """List all documents in a domain's store."""
    try:
        store_manager = StoreManager()
        documents = await store_manager.list_documents(domain)
        return documents
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/stores/{domain}/documents/{doc_name:path}")
async def delete_document(
    domain: str,
    doc_name: str,
    request: Request,
    username: str = Depends(require_admin),
):
    """Delete a document from a domain's store."""
    try:
        store_manager = StoreManager()
        success = await store_manager.delete_document(domain, doc_name)

        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        log_admin_action(
            username, "delete_document", resource=domain,
            details={"doc_name": doc_name},
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return {"success": True, "message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
