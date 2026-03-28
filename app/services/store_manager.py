"""
UniVR Chatbot - File Search Store Manager

Handles creation, management, and document uploads for Gemini File Search Stores.
Each store represents a RAG domain (e.g., scholarships, admissions).
"""

import asyncio
import logging
import time
import uuid
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import GEMINI_API_KEY, MODEL

logger = logging.getLogger(__name__)

# ── Document list cache ────────────────────────────────────────────────────────
# Keyed by domain. Value is (fetched_at_monotonic, docs_list).
# TTL: 60s — invalidated immediately on upload/delete so it never shows stale data.
_DOC_CACHE: dict[str, tuple[float, list[dict]]] = {}
_DOC_CACHE_TTL = 60


class DocumentMetadata(BaseModel):
    """Metadata extracted from a document."""
    title: str
    department: str
    abstract: str


class StoreInfo(BaseModel):
    """Store information schema."""
    name: str
    display_name: str
    domain: str
    document_count: int = 0


class StoreManager:
    """
    Manages Gemini File Search Stores for the University chatbot.
    Each store represents a RAG domain.
    """

    def __init__(self):
        """Initialize the store manager."""
        self.client = None
        if GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                logger.debug("StoreManager: Gemini client initialized")
            except Exception as e:
                logger.error(f"StoreManager: Failed to initialize Gemini client: {e}", exc_info=True)

    def get_store(self, domain: str) -> types.FileSearchStore | None:
        """Retrieve a store by domain name by listing all stores (fallback only)."""
        if not self.client:
            return None

        try:
            for store in self.client.file_search_stores.list():
                if store.display_name == domain:
                    return store
        except Exception as e:
            logger.error(f"Error finding store: {e}")
        return None

    async def resolve_store(self, domain: str) -> types.FileSearchStore | None:
        """
        Resolve a store by domain using DB as single source of truth.

        1. Fast path: direct Gemini lookup using gemini_store_name from DB
        2. Discovery fallback: list all Gemini stores, match by display_name, update DB
        3. Returns None if not found (caller decides whether to auto-create)
        """
        if not self.client:
            return None

        # 1. Fast path — use cached Gemini resource name from DB
        from app.services import store_registry  # local import to avoid circular
        db_record = await store_registry.get_store(domain)
        if db_record and db_record.gemini_store_name:
            try:
                store = self.client.file_search_stores.get(
                    name=db_record.gemini_store_name
                )
                return store
            except Exception:
                logger.warning(
                    f"Cached gemini_store_name '{db_record.gemini_store_name}' "
                    f"for domain '{domain}' is stale — falling back to discovery"
                )

        # 2. Discovery fallback — list all stores and match by display_name
        store = self.get_store(domain)
        if store:
            try:
                await store_registry.update_gemini_name(domain, store.name)
                logger.info(f"Updated DB gemini_store_name for domain '{domain}': {store.name}")
            except Exception as e:
                logger.warning(f"Could not update gemini_store_name in DB for '{domain}': {e}")
        return store

    async def create_store(self, domain: str, description: str = "") -> types.FileSearchStore:
        """
        Create a new File Search Store for a domain.
        
        Args:
            domain: The domain identifier (e.g., 'scholarships')
            description: Optional description for the domain
            
        Returns:
            The created or existing store
        """
        if not self.client:
            raise ValueError("Gemini client not initialized. Check API key.")

        # Check if store already exists
        existing = self.get_store(domain)
        if existing:
            logger.info(f"Store '{domain}' already exists")
            return existing

        # Create new store — use domain directly as display_name
        store = self.client.file_search_stores.create(
            config={"display_name": domain}
        )
        logger.info(f"Created new store: {store.name} for domain '{domain}'")
        return store

    async def list_stores(self) -> list[StoreInfo]:
        """List all domain stores."""
        if not self.client:
            return []

        stores = []

        try:
            for store in self.client.file_search_stores.list():
                if not store.display_name:
                    continue

                # Count documents
                doc_count = 0
                try:
                    docs = list(self.client.file_search_stores.documents.list(parent=store.name))
                    doc_count = len(docs)
                except Exception:
                    pass

                stores.append(StoreInfo(
                    name=store.name,
                    display_name=store.display_name,
                    domain=store.display_name,
                    document_count=doc_count
                ))
        except Exception as e:
            logger.error(f"Error listing stores: {e}")

        return stores

    async def delete_store(self, domain: str) -> bool:
        """Delete a store by domain."""
        if not self.client:
            return False

        store = await self.resolve_store(domain)
        if not store:
            return False

        try:
            self.client.file_search_stores.delete(name=store.name, config={"force": True})
            logger.info(f"Deleted store for domain '{domain}'")
            return True
        except Exception as e:
            logger.error(f"Error deleting store: {e}")
            return False

    async def upload_document(
        self,
        file_path: str,
        domain: str,
        *,
        source_type: str = "attachment",
        title_override: str | None = None,
        url: str | None = None,
        document_id: str | None = None,
        custom_metadata: list[dict] | None = None,
    ) -> dict:
        """
        Upload a document to a domain's File Search Store.
        Replaces existing documents with the same filename.

        Args:
            file_path: Path to the file to upload
            domain: Domain (store id) to upload to
            source_type: "attachment" (uploaded doc) or "website" (ingested page)
            title_override: Use this title instead of extracted title
            url: For website source, canonical URL on aulss9.veneto.it
            document_id: Stable id for attachments (for links in chat response); generated if not set
            custom_metadata: Optional extra metadata dicts ({"key": ..., "string_value": ...})
                             appended to the base metadata. Used by the web scraper to attach
                             topic, source, etc. without changing the base upload contract.

        Returns:
            dict with upload status (includes document_id for attachments)
        """
        if not self.client:
            raise ValueError("Gemini client not initialized. Check API key.")

        store = await self.resolve_store(domain)
        if not store:
            # Only auto-create if the domain is registered in DB (seeded or created via admin)
            # If not in DB, the domain is invalid — reject it rather than silently create
            from app.services import store_registry
            db_record = await store_registry.get_store(domain)
            if not db_record:
                raise ValueError(f"Unknown store domain '{domain}'. Register it via the admin panel first.")
            logger.warning(f"Store for domain '{domain}' missing from Gemini — auto-creating")
            store = await self.create_store(domain, db_record.description)
            await store_registry.update_gemini_name(domain, store.name)

        file_name = Path(file_path).name
        if source_type == "attachment" and not document_id:
            document_id = uuid.uuid4().hex

        # Upload file temporarily for metadata extraction
        logger.info(f"Uploading {file_name} for processing...")
        temp_file = self.client.files.upload(file=file_path)

        # Wait for file to be ready
        while temp_file.state.name == "PROCESSING":
            await asyncio.sleep(2)
            temp_file = self.client.files.get(name=temp_file.name)

        if temp_file.state.name != "ACTIVE":
            raise RuntimeError(f"File upload failed with state: {temp_file.state.name}")

        # Extract metadata using Gemini
        metadata = await self._extract_metadata(temp_file, domain)
        title = title_override or metadata.title

        # Check for and delete existing version (replace duplicate)
        await self._delete_existing(store, file_name)

        # Gemini enforces a 256-char limit on every metadata string_value
        def _mv(v: str) -> str:
            return v[:256] if v else v

        # Build custom_metadata: base fields + optional url/document_id + caller extras
        built_metadata = [
            {"key": "title", "string_value": _mv(title)},
            {"key": "file_name", "string_value": _mv(file_name)},
            {"key": "domain", "string_value": _mv(domain)},
            {"key": "abstract", "string_value": _mv(metadata.abstract)},
            {"key": "source_type", "string_value": _mv(source_type)},
        ]
        if url:
            built_metadata.append({"key": "url", "string_value": _mv(url)})
        if document_id:
            built_metadata.append({"key": "document_id", "string_value": _mv(document_id)})
        if custom_metadata:
            built_metadata.extend(
                {**m, "string_value": _mv(m.get("string_value", "") or "")}
                for m in custom_metadata
            )

        # Import to File Search Store with metadata and chunking config
        operation = self.client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store.name,
            file=file_path,
            config={
                "display_name": title,
                "custom_metadata": built_metadata,
                "chunking_config": {
                    "white_space_config": {
                        "max_tokens_per_chunk": 300,
                        "max_overlap_tokens": 30,
                    }
                },
            },
        )

        while not operation.done:
            await asyncio.sleep(3)
            operation = self.client.operations.get(operation)

        logger.info(f"Document '{file_name}' uploaded and indexed to domain '{domain}' (source_type={source_type})")
        self._invalidate_doc_cache(domain)

        result = {
            "success": True,
            "filename": file_name,
            "title": title,
            "domain": domain,
            "source_type": source_type,
        }
        if document_id:
            result["document_id"] = document_id
        if url:
            result["url"] = url
        return result

    async def _extract_metadata(self, temp_file, domain: str) -> DocumentMetadata:
        """Extract metadata from a document using Gemini."""
        logger.info("Extracting metadata...")

        response = self.client.models.generate_content(
            model=MODEL,
            contents=[
                f"""Extract the following from this document:
                1. Title: The main title or subject
                2. Abstract: A brief 1-2 sentence summary
                
                The document is from the '{domain}' domain of University of Verona.
                Keep each field under 200 characters.""",
                temp_file,
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": DocumentMetadata,
            },
        )

        metadata = response.parsed
        metadata.department = domain
        # Hard-clamp even if the model ignores the character-limit instruction
        metadata.title = metadata.title[:256] if metadata.title else metadata.title
        metadata.abstract = metadata.abstract[:256] if metadata.abstract else metadata.abstract

        logger.info(f"Extracted - Title: {metadata.title}")
        return metadata

    async def _delete_existing(self, store, file_name: str):
        """Delete existing document with the same name (replace duplicate)."""
        try:
            for doc in self.client.file_search_stores.documents.list(parent=store.name):
                should_delete = False

                if doc.display_name == file_name:
                    should_delete = True
                elif doc.custom_metadata:
                    for meta in doc.custom_metadata:
                        if meta.key == "file_name" and meta.string_value == file_name:
                            should_delete = True
                            break

                if should_delete:
                    logger.info(f"Replacing existing document: {doc.display_name}")
                    self.client.file_search_stores.documents.delete(
                        name=doc.name,
                        config={"force": True}
                    )
                    await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Error checking for existing docs: {e}")

    async def delete_web_scrape_docs(self, domain: str) -> int:
        """
        Delete all web-scraped documents from a store.
        Identifies docs by: source="web_scrape", file_name starting with "web_",
        or source_type="website" (covers documents uploaded by the old batch scraper).
        Returns the number of documents deleted.
        """
        if not self.client:
            return 0
        store = await self.resolve_store(domain)
        if not store:
            return 0
        deleted = 0
        try:
            for doc in self.client.file_search_stores.documents.list(parent=store.name):
                is_web = False
                if doc.custom_metadata:
                    for meta in doc.custom_metadata:
                        k, v = meta.key, (meta.string_value or "")
                        if (k == "source" and v == "web_scrape") or \
                           (k == "source_type" and v == "website") or \
                           (k == "file_name" and v.startswith("web_")):
                            is_web = True
                            break
                if is_web:
                    try:
                        self.client.file_search_stores.documents.delete(
                            name=doc.name, config={"force": True}
                        )
                        deleted += 1
                        await asyncio.sleep(0.5)  # avoid hammering the API
                    except Exception as e:
                        logger.warning(f"Could not delete web doc '{doc.name}': {e}")
        except Exception as e:
            logger.error(f"Error deleting web scrape docs from '{domain}': {e}")
        logger.info(f"Deleted {deleted} web-scrape documents from store '{domain}'")
        if deleted:
            self._invalidate_doc_cache(domain)
        return deleted

    def _invalidate_doc_cache(self, domain: str) -> None:
        """Drop cached doc list for a domain. Called after any write operation."""
        _DOC_CACHE.pop(domain, None)

    async def _fetch_all_documents(self, domain: str) -> list[dict]:
        """
        Fetch every document for a domain from Gemini.
        Results are cached for _DOC_CACHE_TTL seconds and invalidated on
        any upload or delete so the cache never returns stale data.
        """
        entry = _DOC_CACHE.get(domain)
        if entry and (time.monotonic() - entry[0]) < _DOC_CACHE_TTL:
            return entry[1]

        if not self.client:
            return []

        store = await self.resolve_store(domain)
        if not store:
            return []

        docs: list[dict] = []
        try:
            for doc in self.client.file_search_stores.documents.list(parent=store.name):
                metadata: dict[str, str] = {}
                if doc.custom_metadata:
                    for meta in doc.custom_metadata:
                        metadata[meta.key] = meta.string_value
                docs.append({
                    "name": doc.name,
                    "display_name": doc.display_name,
                    "metadata": metadata,
                })
        except Exception as e:
            logger.error(f"Error listing documents for '{domain}': {e}")

        _DOC_CACHE[domain] = (time.monotonic(), docs)
        return docs

    async def list_documents(self, domain: str) -> list[dict]:
        """List all documents in a domain's store (cached)."""
        return await self._fetch_all_documents(domain)

    async def list_documents_page(
        self, domain: str, limit: int = 50, offset: int = 0
    ) -> dict:
        """
        Return a paginated slice of documents for a domain.
        Response: {"items": [...], "total": N}
        The full list is cached so subsequent page requests are instant.
        """
        all_docs = await self._fetch_all_documents(domain)
        return {
            "items": all_docs[offset: offset + limit],
            "total": len(all_docs),
        }

    async def get_document_stats(self, domain: str) -> dict:
        """
        Return lightweight aggregate counts for a domain — no full list sent over
        the wire. Used by the admin coverage tiles and content checklist.
        """
        all_docs = await self._fetch_all_documents(domain)

        def _fname(d: dict) -> str:
            return d.get("metadata", {}).get("file_name", "").lower()

        web_count = sum(
            1 for d in all_docs
            if _fname(d).startswith("web_") or d.get("metadata", {}).get("source") == "web_scrape"
        )
        carta_count = sum(1 for d in all_docs if _fname(d).startswith("carta_servizi_"))
        return {
            "total": len(all_docs),
            "web_count": web_count,
            "carta_count": carta_count,
            "attachment_count": len(all_docs) - web_count - carta_count,
            "has_medico": any("medico" in _fname(d) for d in all_docs),
            "has_uss9": any("uss9" in _fname(d) for d in all_docs),
        }

    async def delete_document(self, domain: str, doc_name: str) -> bool:
        """Delete a document from a domain's store."""
        if not self.client:
            return False

        store = await self.resolve_store(domain)
        if not store:
            return False

        try:
            self.client.file_search_stores.documents.delete(
                name=doc_name,
                config={"force": True}
            )
            logger.info(f"Deleted document: {doc_name}")
            self._invalidate_doc_cache(domain)
            return True
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False
