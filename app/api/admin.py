"""
UniVR Chatbot - Admin API Endpoints

Manage File Search Stores (domains) and documents.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.api.auth import require_admin
from app.config import ULSS9_STORES
from app.services.extra_stores import set_extra_description
from app.services.store_manager import StoreManager, StoreInfo

logger = logging.getLogger(__name__)

router = APIRouter()

# Data directory for uploaded files
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============ Schemas ============

class CreateStoreRequest(BaseModel):
    """Request to create a new store/domain."""
    domain: str
    description: str = ""


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


class DocumentInfo(BaseModel):
    """Document information schema."""
    name: str
    display_name: str
    metadata: dict = {}


# ============ Store Management ============

@router.post("/stores", response_model=CreateStoreResponse)
async def create_store(request: CreateStoreRequest, _: str = Depends(require_admin)):
    """
    Create a new File Search Store (category) for RAG.
    Use for stores beyond the four initial areas (Allegato A).
    Saves the description so store selection can include this category.
    """
    try:
        store_manager = StoreManager()
        store = await store_manager.create_store(request.domain, request.description)
        if request.description:
            set_extra_description(request.domain, request.description)
        return CreateStoreResponse(
            success=True,
            domain=request.domain,
            store_name=store.name,
            message=f"Store for domain '{request.domain}' created successfully"
        )
    except Exception as e:
        logger.error(f"Create store error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores", response_model=list[StoreInfo])
async def list_stores(_: str = Depends(require_admin)):
    """List all available stores/domains."""
    try:
        store_manager = StoreManager()
        stores = await store_manager.list_stores()
        return stores
    except Exception as e:
        logger.error(f"List stores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/stores/{domain}")
async def delete_store(domain: str, _: str = Depends(require_admin)):
    """Delete a store and all its documents."""
    try:
        store_manager = StoreManager()
        success = await store_manager.delete_store(domain)

        if not success:
            raise HTTPException(status_code=404, detail=f"Store '{domain}' not found")

        return {"success": True, "message": f"Store '{domain}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete store error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stores/delete-all")
async def delete_all_stores(_: str = Depends(require_admin)):
    """
    Delete all File Search Stores (with the app's STORE_PREFIX) from Gemini.
    Use this to clear everything before creating the 4 ULSS 9 stores.
    """
    try:
        store_manager = StoreManager()
        stores = await store_manager.list_stores()
        deleted = []
        for s in stores:
            try:
                ok = await store_manager.delete_store(s.domain)
                if ok:
                    deleted.append(s.domain)
                    logger.info(f"Deleted store: {s.domain}")
            except Exception as e:
                logger.warning(f"Failed to delete store {s.domain}: {e}")
        return {
            "success": True,
            "message": f"Deleted {len(deleted)} store(s) from Gemini.",
            "deleted": deleted,
        }
    except Exception as e:
        logger.error(f"Delete all stores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stores/ulss9/create-all")
async def create_all_ulss9_stores(_: str = Depends(require_admin)):
    """Create the four initial stores from Allegato A (idempotent). Others can be added via POST /stores."""
    try:
        store_manager = StoreManager()
        created = []
        for s in ULSS9_STORES:
            domain = s["id"]
            desc = s.get("description", "")
            store = await store_manager.create_store(domain, desc)
            created.append({"domain": domain, "store_name": store.name})
        return {"success": True, "message": "ULSS 9 stores ensured", "stores": created}
    except Exception as e:
        logger.error(f"Create all ULSS9 stores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Document Management ============

@router.post("/stores/{domain}/upload", response_model=UploadResponse)
async def upload_document(
    domain: str,
    file: UploadFile = File(...),
    _: str = Depends(require_admin),
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


@router.get("/stores/{domain}/documents", response_model=list[DocumentInfo])
async def list_documents(domain: str):
    """List all documents in a domain's store."""
    try:
        store_manager = StoreManager()
        documents = await store_manager.list_documents(domain)
        return documents
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/stores/{domain}/documents/{doc_name:path}")
async def delete_document(domain: str, doc_name: str, _: str = Depends(require_admin)):
    """Delete a document from a domain's store."""
    try:
        store_manager = StoreManager()
        success = await store_manager.delete_document(domain, doc_name)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"success": True, "message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
