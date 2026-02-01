"""
UniVR Chatbot - File Search Store Manager

Handles creation, management, and document uploads for Gemini File Search Stores.
Each store represents a RAG domain (e.g., scholarships, admissions).
"""

import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import GEMINI_API_KEY, MODEL, STORE_PREFIX

logger = logging.getLogger(__name__)


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
    
    def _get_store_display_name(self, domain: str) -> str:
        """Generate store display name from domain."""
        return f"{STORE_PREFIX}-{domain}"
    
    def _extract_domain_from_display_name(self, display_name: str) -> Optional[str]:
        """Extract domain from store display name."""
        prefix = f"{STORE_PREFIX}-"
        if display_name.startswith(prefix):
            return display_name[len(prefix):]
        return None
    
    def get_store(self, domain: str) -> types.FileSearchStore | None:
        """Retrieve a store by domain name."""
        if not self.client:
            return None
        
        display_name = self._get_store_display_name(domain)
        try:
            for store in self.client.file_search_stores.list():
                if store.display_name == display_name:
                    return store
        except Exception as e:
            logger.error(f"Error finding store: {e}")
        return None
    
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
        
        display_name = self._get_store_display_name(domain)
        
        # Check if store already exists
        existing = self.get_store(domain)
        if existing:
            logger.info(f"Store '{display_name}' already exists")
            return existing
        
        # Create new store
        store = self.client.file_search_stores.create(
            config={"display_name": display_name}
        )
        logger.info(f"Created new store: {store.name} for domain '{domain}'")
        return store
    
    async def list_stores(self) -> list[StoreInfo]:
        """List all domain stores."""
        if not self.client:
            return []
        
        stores = []
        prefix = f"{STORE_PREFIX}-"
        
        try:
            for store in self.client.file_search_stores.list():
                # Only include stores with our prefix
                if store.display_name and store.display_name.startswith(prefix):
                    domain = self._extract_domain_from_display_name(store.display_name)
                    
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
                        domain=domain or "",
                        document_count=doc_count
                    ))
        except Exception as e:
            logger.error(f"Error listing stores: {e}")
        
        return stores
    
    async def delete_store(self, domain: str) -> bool:
        """Delete a store by domain."""
        if not self.client:
            return False
        
        store = self.get_store(domain)
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
        title_override: Optional[str] = None,
        url: Optional[str] = None,
        document_id: Optional[str] = None,
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

        Returns:
            dict with upload status (includes document_id for attachments)
        """
        if not self.client:
            raise ValueError("Gemini client not initialized. Check API key.")

        store = self.get_store(domain)
        if not store:
            raise ValueError(f"Store for domain '{domain}' not found. Create it first.")

        file_name = Path(file_path).name
        if source_type == "attachment" and not document_id:
            document_id = uuid.uuid4().hex

        # Upload file temporarily for metadata extraction
        logger.info(f"Uploading {file_name} for processing...")
        temp_file = self.client.files.upload(file=file_path)

        # Wait for file to be ready
        while temp_file.state.name == "PROCESSING":
            time.sleep(2)
            temp_file = self.client.files.get(name=temp_file.name)

        if temp_file.state.name != "ACTIVE":
            raise RuntimeError(f"File upload failed with state: {temp_file.state.name}")

        # Extract metadata using Gemini
        metadata = await self._extract_metadata(temp_file, domain)
        title = title_override or metadata.title

        # Check for and delete existing version (replace duplicate)
        await self._delete_existing(store, file_name)

        # Build custom_metadata: base + source_type and optional url/document_id
        custom_metadata = [
            {"key": "title", "string_value": title},
            {"key": "file_name", "string_value": file_name},
            {"key": "domain", "string_value": domain},
            {"key": "abstract", "string_value": metadata.abstract},
            {"key": "source_type", "string_value": source_type},
        ]
        if url:
            custom_metadata.append({"key": "url", "string_value": url})
        if document_id:
            custom_metadata.append({"key": "document_id", "string_value": document_id})

        # Import to File Search Store with metadata
        operation = self.client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store.name,
            file=file_path,
            config={
                "display_name": title,
                "custom_metadata": custom_metadata,
            },
        )

        # Wait for indexing to complete
        while not operation.done:
            time.sleep(3)
            operation = self.client.operations.get(operation)

        logger.info(f"Document '{file_name}' uploaded and indexed to domain '{domain}' (source_type={source_type})")

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
                    time.sleep(2)
        except Exception as e:
            logger.warning(f"Error checking for existing docs: {e}")
    
    async def list_documents(self, domain: str) -> list[dict]:
        """List all documents in a domain's store."""
        if not self.client:
            return []
        
        store = self.get_store(domain)
        if not store:
            return []
        
        documents = []
        try:
            for doc in self.client.file_search_stores.documents.list(parent=store.name):
                metadata = {}
                if doc.custom_metadata:
                    for meta in doc.custom_metadata:
                        metadata[meta.key] = meta.string_value
                
                documents.append({
                    "name": doc.name,
                    "display_name": doc.display_name,
                    "metadata": metadata
                })
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
        
        return documents
    
    async def delete_document(self, domain: str, doc_name: str) -> bool:
        """Delete a document from a domain's store."""
        if not self.client:
            return False
        
        store = self.get_store(domain)
        if not store:
            return False
        
        try:
            self.client.file_search_stores.documents.delete(
                name=doc_name,
                config={"force": True}
            )
            logger.info(f"Deleted document: {doc_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False
