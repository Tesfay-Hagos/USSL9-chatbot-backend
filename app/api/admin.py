"""
UniVR Chatbot - Admin API Endpoints

Manage File Search Stores (domains) and documents.
Audit logging for GDPR / government compliance.
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
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

# Temp directory for URL preview files (cleaned up after upload or cancel)
TEMP_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


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


class DocumentPage(BaseModel):
    """Paginated document list."""
    items: list[DocumentInfo]
    total: int


class DocumentStats(BaseModel):
    """Lightweight aggregate counts for a store — no full doc list."""
    total: int
    web_count: int
    carta_count: int
    attachment_count: int
    has_medico: bool
    has_uss9: bool


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
    """Ensure the initial public store exists in Gemini (idempotent). Additional stores can be added via POST /stores."""
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
    # If set, use an already-downloaded temp file (from preview-url) instead of re-fetching
    temp_id: str | None = None


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
    import re
    from urllib.parse import unquote, urlparse

    import httpx

    url = body.url.strip()
    try:
        # If a temp_id was provided (from preview-url), use the already-downloaded file
        if body.temp_id:
            matches = list(TEMP_DIR.glob(f"{body.temp_id}_*"))
            if not matches:
                raise HTTPException(status_code=404, detail="Preview file not found — it may have expired")
            temp_file = matches[0]
            path_part = temp_file.name[len(body.temp_id) + 1:]  # strip "tempid_" prefix
            file_path = DATA_DIR / path_part
            temp_file.rename(file_path)  # move from temp to uploads
        else:
            import html as html_module

            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 ULSS9Bot/1.0"})
                resp.raise_for_status()

            content_type = resp.headers.get("content-type", "").lower()
            is_pdf = "pdf" in content_type or url.lower().endswith(".pdf")

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


# ============ URL Preview (download → inspect → confirm upload) ============

class PreviewUrlRequest(BaseModel):
    url: str


@router.post("/preview-url")
async def preview_url(
    body: PreviewUrlRequest,
    username: str = Depends(require_admin),
):
    """
    Download a URL to a temp file and return metadata for preview.
    The caller should GET /preview-file/{temp_id} in an iframe to inspect the content,
    then POST /stores/{domain}/ingest-url with temp_id to confirm, or
    DELETE /preview-file/{temp_id} to discard.
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

        parsed = urlparse(url)
        raw_name = unquote(parsed.path).rstrip("/").split("/")[-1] or "document"
        safe_name = re.sub(r"[^a-z0-9_.-]", "_", raw_name.lower())[:80] or "document"

        temp_id = uuid.uuid4().hex[:16]

        if is_pdf:
            if not safe_name.endswith(".pdf"):
                safe_name += ".pdf"
            file_bytes = resp.content
            temp_path = TEMP_DIR / f"{temp_id}_{safe_name}"
            temp_path.write_bytes(file_bytes)
            return {
                "temp_id": temp_id,
                "filename": safe_name,
                "is_pdf": True,
                "size_bytes": len(file_bytes),
                "content_type": "application/pdf",
                "text_preview": None,
            }
        else:
            if not safe_name.endswith(".md"):
                safe_name = safe_name.rsplit(".", 1)[0] + ".md" if "." in safe_name else safe_name + ".md"
            raw = resp.text
            raw = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", raw, flags=re.DOTALL | re.IGNORECASE)
            raw = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*/?>|</?(p|div|h[1-6]|li|tr)>", "\n", raw, flags=re.IGNORECASE)
            raw = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", raw, flags=re.IGNORECASE | re.DOTALL)
            raw = re.sub(r"<[^>]+>", "", raw)
            text = html_module.unescape(raw)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if not text:
                raise HTTPException(status_code=422, detail="No extractable text content found at that URL")
            file_bytes = text.encode("utf-8")
            temp_path = TEMP_DIR / f"{temp_id}_{safe_name}"
            temp_path.write_bytes(file_bytes)
            return {
                "temp_id": temp_id,
                "filename": safe_name,
                "is_pdf": False,
                "size_bytes": len(file_bytes),
                "content_type": "text/plain",
                "text_preview": text[:3000],
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch URL ({e.response.status_code})")
    except httpx.RequestError as e:
        raise HTTPException(status_code=422, detail=f"Network error: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview-file/{temp_id}")
async def serve_preview_file(temp_id: str, username: str = Depends(require_admin)):
    """Serve a temp preview file (PDF or text) for inline browser rendering."""
    matches = list(TEMP_DIR.glob(f"{temp_id}_*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Preview file not found or already used")
    f = matches[0]
    media_type = "application/pdf" if f.suffix == ".pdf" else "text/plain; charset=utf-8"
    return FileResponse(str(f), media_type=media_type, headers={"Content-Disposition": "inline"})


@router.delete("/preview-file/{temp_id}")
async def discard_preview_file(temp_id: str, username: str = Depends(require_admin)):
    """Delete a temp preview file (user cancelled)."""
    matches = list(TEMP_DIR.glob(f"{temp_id}_*"))
    for f in matches:
        f.unlink(missing_ok=True)
    return {"success": True, "deleted": len(matches)}


# ============ CartaServizi API Integration ============

class CartaServiziRequest(BaseModel):
    """Request to fetch or sync from the CartaServizi API."""
    endpoint: str  # "elenco_servizi" | "servizi_carta"
    carta: str | None = None  # required when endpoint == "servizi_carta"
    title: str | None = None  # optional title override (sync only)


async def _get_carta_servizi_token() -> str:
    """Obtain an OAuth2 client-credentials token from Cognito."""
    import httpx

    from app.config import (
        CARTA_SERVIZI_CLIENT_ID,
        CARTA_SERVIZI_CLIENT_SECRET,
        CARTA_SERVIZI_COGNITO_DOMAIN,
    )

    if not all([CARTA_SERVIZI_COGNITO_DOMAIN, CARTA_SERVIZI_CLIENT_ID, CARTA_SERVIZI_CLIENT_SECRET]):
        raise HTTPException(
            status_code=500,
            detail="CartaServizi API credentials are not configured (CARTA_SERVIZI_COGNITO_DOMAIN / CLIENT_ID / CLIENT_SECRET)",
        )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{CARTA_SERVIZI_COGNITO_DOMAIN}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CARTA_SERVIZI_CLIENT_ID,
                "client_secret": CARTA_SERVIZI_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
    return resp.json()["access_token"]


def _build_carta_url(endpoint: str, carta: str | None) -> str:
    """Build the CartaServizi endpoint URL."""
    from app.config import CARTA_SERVIZI_URL

    if not CARTA_SERVIZI_URL:
        raise HTTPException(status_code=500, detail="CARTA_SERVIZI_URL is not configured")

    if endpoint == "elenco_servizi":
        return f"{CARTA_SERVIZI_URL}/servizi"
    elif endpoint == "servizi_carta":
        if not carta:
            raise HTTPException(status_code=400, detail="'carta' is required for the servizi_carta endpoint")
        return f"{CARTA_SERVIZI_URL}/servizi/carta/{carta}"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown endpoint: {endpoint!r}")


def _strip_html(html: str) -> str:
    """Strip HTML tags from a string, replacing <br> with newlines."""
    import re
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _servizi_to_markdown(data: list | dict, endpoint: str, carta: str | None) -> tuple[str, str]:
    """Convert a CartaServizi JSON response to (title, markdown) for indexing.

    elenco_servizi response shape:
        {"columns": [...], "data": [[...], ...]}   (columnar, 743+ rows)

    servizi_carta response shape:
        {"idservizio": int, "servizio": str, "descrizione": "<html>", ..., "attivita": [...]}
    """
    if endpoint == "elenco_servizi":
        title = "Elenco Servizi - Carta dei Servizi ULSS 9 Scaligera"
        lines = [f"# {title}\n"]

        # Columnar format returned by the API: {columns, data}
        if isinstance(data, dict) and "columns" in data and "data" in data:
            cols = data["columns"]
            rows = data["data"]
            try:
                idx_id = cols.index("id")
                idx_desc = cols.index("descrizione")
                idx_padre = cols.index("padre")
                idx_idpadre = cols.index("idpadre")
                idx_area = cols.index("area") if "area" in cols else None
                idx_specialita = cols.index("specialita") if "specialita" in cols else None
                idx_presidio = cols.index("presidio") if "presidio" in cols else None
            except ValueError as exc:
                lines.append(f"*(colonna mancante: {exc})*")
                return title, "\n".join(lines)

            # Group rows by parent carta (idpadre / padre)
            from collections import defaultdict
            by_carta: dict[str, list] = defaultdict(list)
            for row in rows:
                parent = row[idx_padre] or f"id={row[idx_idpadre]}"
                by_carta[parent].append(row)

            for parent_name, parent_rows in sorted(by_carta.items()):
                lines.append(f"\n## {parent_name}")
                for row in parent_rows:
                    desc = row[idx_desc] or ""
                    area = row[idx_area] if idx_area is not None else ""
                    spec = row[idx_specialita] if idx_specialita is not None else ""
                    presidio = row[idx_presidio] if idx_presidio is not None else ""
                    parts = [f"- **{desc}**"]
                    if spec:
                        parts.append(f"specialità: {spec}")
                    if area:
                        parts.append(f"area: {area}")
                    if presidio:
                        parts.append(f"presidio: {presidio}")
                    lines.append("  ".join(parts))
        elif isinstance(data, list):
            # Fallback: list of dicts
            for item in data:
                if isinstance(item, dict):
                    name = (
                        item.get("descrizione") or item.get("nome") or
                        item.get("name") or item.get("titolo") or
                        str(item.get("id", "Servizio"))
                    )
                    lines.append(f"- {name}")
                else:
                    lines.append(f"- {item}")
        return title, "\n".join(lines)

    # servizi_carta — rich object with HTML fields
    carta_id = carta or "unknown"
    if isinstance(data, dict):
        name = (
            data.get("servizio") or data.get("nome") or data.get("name") or
            data.get("titolo") or data.get("title") or
            f"Carta {carta_id}"
        )
        title = f"Carta dei Servizi - {name}"
        lines = [f"# {title}\n"]

        html_fields = {"descrizione", "raggiungere", "accedere", "ubicazione", "altre_informazioni"}
        skip_fields = {"id", "idservizio", "immagine", "foto_presidio", "mappa", "padre",
                       "codice", "inizio", "fine", "ultima_modifica", "ses"}

        for k, v in data.items():
            if k in skip_fields or v is None or v == "":
                continue
            if k == "attivita" and isinstance(v, list):
                lines.append("\n## Attività")
                for act in v:
                    act_name = act.get("attivita") or act.get("nome") or str(act.get("id", ""))
                    presidio = act.get("presidio") or ""
                    suffix = f" ({presidio})" if presidio else ""
                    lines.append(f"- {act_name}{suffix}")
            elif k in html_fields and isinstance(v, str):
                section = k.replace("_", " ").title()
                lines.append(f"\n## {section}")
                lines.append(_strip_html(v))
            elif isinstance(v, (dict, list)):
                continue  # skip unhandled nested objects
            else:
                label = k.replace("_", " ").title()
                lines.append(f"**{label}**: {v}")

        return title, "\n".join(lines)

    title = f"Carta dei Servizi - {carta_id}"
    import json
    return title, f"# {title}\n\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"


@router.post("/stores/{domain}/fetch-api")
async def fetch_carta_servizi_preview(
    domain: str,
    body: CartaServiziRequest,
    username: str = Depends(require_admin),
):
    """
    Preview data from the CartaServizi API without writing anything to Gemini.
    The admin can review the response and then call sync-api to index it.
    """
    import httpx

    url = _build_carta_url(body.endpoint, body.carta)
    try:
        token = await _get_carta_servizi_token()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
        return {
            "success": True,
            "endpoint": body.endpoint,
            "carta": body.carta,
            "url": url,
            "data": resp.json(),
        }
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=422,
            detail=f"CartaServizi API error ({e.response.status_code}): {e.response.text[:300]}",
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=422, detail=f"Network error contacting CartaServizi API: {e}")
    except Exception as e:
        logger.error(f"CartaServizi fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stores/{domain}/sync-api", response_model=UploadResponse)
async def sync_carta_servizi(
    domain: str,
    request: Request,
    body: CartaServiziRequest,
    username: str = Depends(require_admin),
):
    """
    Fetch from the CartaServizi API, convert the response to a markdown document,
    and upload it to the domain's Gemini File Search Store.
    """
    import re

    import httpx

    url = _build_carta_url(body.endpoint, body.carta)
    try:
        token = await _get_carta_servizi_token()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()

        data = resp.json()
        title, markdown_content = _servizi_to_markdown(data, body.endpoint, body.carta)
        if body.title:
            title = body.title

        safe_name = re.sub(r"[^a-z0-9_-]", "_", title.lower())[:60].strip("_")
        filename = f"carta_servizi_{safe_name}.md"
        file_path = DATA_DIR / filename
        file_path.write_text(markdown_content, encoding="utf-8")

        store_manager = StoreManager()
        result = await store_manager.upload_document(
            str(file_path),
            domain,
            source_type="api",
            title_override=title,
            url=url,
        )
        log_admin_action(
            username, "sync_carta_servizi", resource=domain,
            details={"endpoint": body.endpoint, "carta": body.carta, "filename": filename},
            ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
        )
        return UploadResponse(
            success=True,
            filename=filename,
            domain=domain,
            message=f"CartaServizi data synced to '{domain}' store",
            document_id=result.get("document_id"),
            title=result.get("title") or title,
        )
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=422,
            detail=f"CartaServizi API error ({e.response.status_code})",
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=422, detail=f"Network error: {e}")
    except Exception as e:
        logger.error(f"CartaServizi sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{domain}/documents/stats", response_model=DocumentStats)
async def get_document_stats(domain: str, username: str = Depends(require_admin)):
    """
    Lightweight aggregate counts for a store.
    Used by coverage tiles and content checklist — no full doc list sent over the wire.
    Result is served from the same in-memory cache as the paginated list endpoint.
    """
    try:
        store_manager = StoreManager()
        return await store_manager.get_document_stats(domain)
    except Exception as e:
        logger.error(f"Document stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{domain}/documents", response_model=DocumentPage)
async def list_documents(
    domain: str,
    limit: int = 50,
    offset: int = 0,
    username: str = Depends(require_admin),
):
    """
    Paginated document list for a store.
    The full list is fetched from Gemini once and cached for 60 s, so
    subsequent page requests (prev/next) are served instantly from cache.
    Cache is invalidated on every upload or delete.
    """
    try:
        store_manager = StoreManager()
        return await store_manager.list_documents_page(domain, limit=limit, offset=offset)
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


# ============ Website Scraper ============

class ScrapeSingleUrlRequest(BaseModel):
    """Request to scrape a single URL and upload it to Gemini."""
    url: str = Field(description="The URL to scrape.")
    target_store: str = Field(
        "general",
        description="Domain of the store to upload the scraped document into.",
    )


class ScrapeSingleUrlResponse(BaseModel):
    """Result of a single-URL scrape."""
    status: str          # "scraped" | "already_scraped" | "skipped" | "error"
    url: str
    title: str | None = None
    filename: str | None = None
    topic: str | None = None
    uploaded: bool
    message: str


class ScrapeWebRequest(BaseModel):
    """Request to start a full website scrape job."""
    max_pages: int | None = Field(
        None,
        description="Limit the number of sitemap URLs to process. Omit for all ~1871 pages.",
        ge=1,
        le=2000,
    )
    target_store: str = Field(
        "general",
        description="Domain of the store to upload scraped documents into.",
    )


class ScrapeJobResponse(BaseModel):
    """Status of a running or finished scrape job."""
    job_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    total_urls: int
    scraped: int
    skipped: int
    resumed: int = 0
    uploaded: int
    errors: list[str]
    current_url: str
    store_counts: dict[str, int]
    target_store: str = "general"


@router.post("/scrape-web/start", response_model=ScrapeJobResponse)
async def start_scrape_web(
    request: Request,
    body: ScrapeWebRequest,
    username: str = Depends(require_admin),
):
    """
    Start a background job that crawls the ULSS9 sitemap, extracts page content
    with trafilatura, and uploads batched markdown documents to the "general"
    Gemini File Search store.

    Returns immediately with a job_id. Poll GET /scrape-web/status/{job_id}
    to track progress.
    """
    from app.services.web_scraper import start_scrape_job

    job = start_scrape_job(max_pages=body.max_pages, target_store=body.target_store)
    log_admin_action(
        username, "scrape_web_start", resource=body.target_store,
        details={"job_id": job.job_id, "max_pages": body.max_pages, "target_store": body.target_store},
        ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
    )
    return ScrapeJobResponse(
        job_id=job.job_id,
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        total_urls=job.total_urls,
        scraped=job.scraped,
        skipped=job.skipped,
        resumed=job.resumed,
        uploaded=job.uploaded,
        errors=job.errors,
        current_url=job.current_url,
        store_counts=job.store_counts,
        target_store=job.target_store,
    )


@router.get("/scrape-web/status/{job_id}", response_model=ScrapeJobResponse)
async def get_scrape_status(
    job_id: str,
    username: str = Depends(require_admin),
):
    """Poll the status of a running or finished scrape job."""
    from app.services.web_scraper import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Scrape job '{job_id}' not found")
    return ScrapeJobResponse(
        job_id=job.job_id,
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        total_urls=job.total_urls,
        scraped=job.scraped,
        skipped=job.skipped,
        resumed=job.resumed,
        uploaded=job.uploaded,
        errors=job.errors,
        current_url=job.current_url,
        store_counts=job.store_counts,
        target_store=job.target_store,
    )


@router.get("/scrape-web/jobs", response_model=list[ScrapeJobResponse])
async def list_scrape_jobs(username: str = Depends(require_admin)):
    """List all scrape jobs (running and finished) for this server session."""
    from app.services.web_scraper import list_jobs

    return [
        ScrapeJobResponse(
            job_id=j.job_id,
            status=j.status,
            started_at=j.started_at,
            finished_at=j.finished_at,
            total_urls=j.total_urls,
            scraped=j.scraped,
            skipped=j.skipped,
            resumed=j.resumed,
            uploaded=j.uploaded,
            errors=j.errors,
            current_url=j.current_url,
            store_counts=j.store_counts,
            target_store=j.target_store,
        )
        for j in list_jobs()
    ]


@router.post("/scrape-web/cancel/{job_id}")
async def cancel_scrape_job(
    job_id: str,
    request: Request,
    username: str = Depends(require_admin),
):
    """Cancel a running scrape job. Already-uploaded batches are kept."""
    from app.services.web_scraper import cancel_job

    cancelled = cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found or is not running",
        )
    log_admin_action(
        username, "scrape_web_cancel", resource="all_stores",
        details={"job_id": job_id},
        ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
    )


@router.get("/scrape-web/manifest")
async def get_scrape_manifest(
    limit: int = 30,
    offset: int = 0,
    username: str = Depends(require_admin),
):
    """
    Return scrape manifest: coverage stats + paginated list of scraped pages.
    Use this to audit content quality and see what has/hasn't been scraped yet.
    """
    from app.services import scrape_manifest

    stats = await scrape_manifest.get_manifest_stats()
    pages = await scrape_manifest.get_sample_pages(limit=limit, offset=offset)
    return {"stats": stats, "pages": pages}


@router.delete("/scrape-web/manifest")
async def reset_scrape_manifest(
    request: Request,
    username: str = Depends(require_admin),
):
    """
    Full reset of all web-scrape content:
      1. Delete all web_*.md files from the uploads directory on disk.
      2. Delete all web-scraped documents from every Gemini store.
      3. Delete all scraped page records from the DB manifest.
    After this, the next scrape job starts from scratch with a clean slate.
    """
    from app.services import scrape_manifest

    # 1. Delete web_*.md files from disk
    deleted_files = 0
    for f in DATA_DIR.glob("web_*.md"):
        try:
            f.unlink(missing_ok=True)
            deleted_files += 1
        except Exception as e:
            logger.warning(f"Could not delete file {f}: {e}")

    # 2. Delete web-scraped documents from all Gemini stores
    deleted_gemini = 0
    try:
        store_manager = StoreManager()
        stores = await store_manager.list_stores()
        for s in stores:
            deleted_gemini += await store_manager.delete_web_scrape_docs(s.domain)
    except Exception as e:
        logger.error(f"Error cleaning Gemini stores during manifest reset: {e}")

    # 3. Delete DB manifest records
    deleted_records = await scrape_manifest.reset_manifest()

    log_admin_action(
        username, "scrape_manifest_reset", resource="scraped_pages",
        details={
            "deleted_records": deleted_records,
            "deleted_files": deleted_files,
            "deleted_gemini_docs": deleted_gemini,
        },
        ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
    )
    return {
        "success": True,
        "deleted": deleted_records,
        "deleted_files": deleted_files,
        "deleted_gemini_docs": deleted_gemini,
    }


@router.post("/scrape-web/scrape-url", response_model=ScrapeSingleUrlResponse)
async def scrape_single_url_endpoint(
    request: Request,
    body: ScrapeSingleUrlRequest,
    username: str = Depends(require_admin),
):
    """
    Scrape a single URL, upload the result to the specified Gemini store,
    and record it in the manifest so full-site scrape jobs skip it automatically.

    Returns immediately with the outcome — no job ID needed.
    """
    from app.services.web_scraper import scrape_single_url

    result = await scrape_single_url(url=body.url, target_store=body.target_store)
    log_admin_action(
        username, "scrape_single_url", resource=body.url,
        details={"target_store": body.target_store, "status": result["status"], "uploaded": result["uploaded"]},
        ip=get_client_ip(request), correlation_id=getattr(request.state, "correlation_id", None),
    )
    return ScrapeSingleUrlResponse(**result)
