"""
Correction Injector — Upload Q&A Documents to Gemini Stores

When a superadmin creates a correction, this service:
1. Generates a structured Q&A document from the correction
2. Writes it to a temporary file
3. Uploads it to the relevant Gemini File Search store
4. Returns the gemini_doc_name for tracking and cleanup

On deactivation/deletion, it deletes the injected document from Gemini.

Gemini's multilingual embeddings handle cross-language matching naturally —
an Italian correction document will match Romanian, English, etc. queries.
"""

import logging
import tempfile
import textwrap
from pathlib import Path

from app.services.store_manager import StoreManager

logger = logging.getLogger(__name__)


def _build_correction_document(
    query_pattern: str,
    corrected_response: str,
    correction_id: str,
    domain: str,
) -> str:
    """
    Build a structured Q&A text document from a correction.

    Format is optimised for Gemini File Search retrieval:
    - Clear question/answer structure
    - Keywords section for improved matching
    - Metadata footer for traceability
    """
    # Extract keywords from the pattern for better retrieval
    words = query_pattern.lower().split()
    keywords = [w for w in words if len(w) > 3]

    doc = textwrap.dedent(f"""\
        # Informazione Corretta — {domain.replace('_', ' ').title()}

        ## Domanda
        {query_pattern}

        ## Risposta
        {corrected_response}

        ## Parole chiave
        {', '.join(keywords)}

        ---
        Tipo: correzione
        ID correzione: {correction_id}
        Dominio: {domain}
    """)
    return doc


async def inject_correction(
    correction_id: str,
    query_pattern: str,
    corrected_response: str,
    domain: str,
) -> str | None:
    """
    Generate a Q&A document and upload it to the Gemini store.

    Returns the gemini_doc_name if successful, None if failed.
    """
    store_manager = StoreManager()

    if not store_manager.client:
        logger.error("Cannot inject correction: Gemini client not initialised")
        return None

    store = await store_manager.resolve_store(domain)
    if not store:
        logger.error(f"Cannot inject correction: store '{domain}' not found in Gemini")
        return None

    # Build the document
    doc_content = _build_correction_document(
        query_pattern, corrected_response, correction_id, domain
    )

    # Write to a temporary file for upload
    filename = f"correction_{correction_id}.md"
    tmp_path = Path(tempfile.mkdtemp()) / filename

    try:
        tmp_path.write_text(doc_content, encoding="utf-8")

        await store_manager.upload_document(
            file_path=str(tmp_path),
            domain=domain,
            source_type="correction",
            title_override=f"Correzione: {query_pattern[:80]}",
            document_id=correction_id,
        )

        logger.info(
            "Correction injected into Gemini store",
            extra={
                "correction_id": correction_id,
                "domain": domain,
                "filename": filename,
            },
        )
        # The upload returns metadata but we need the actual Gemini doc name
        # for deletion later. The store_manager stores it as doc_name.
        return filename  # used to find and delete the doc later

    except Exception as e:
        logger.error(
            f"Failed to inject correction into Gemini: {e}",
            extra={"correction_id": correction_id, "domain": domain},
        )
        return None
    finally:
        # Clean up temp file
        try:
            tmp_path.unlink(missing_ok=True)
            tmp_path.parent.rmdir()
        except OSError:
            pass


async def remove_injection(
    domain: str,
    correction_id: str,
) -> bool:
    """
    Delete an injected correction document from the Gemini store.

    Returns True if successfully deleted, False otherwise.
    """
    store_manager = StoreManager()

    if not store_manager.client:
        logger.warning("Cannot remove injection: Gemini client not initialised")
        return False

    try:
        # List documents and find the one matching this correction
        docs = await store_manager.list_documents(domain)
        target_doc_name = None
        for doc in docs:
            doc_name = doc.get("name", "")
            file_name = doc.get("display_name", "")
            # Match by correction filename pattern
            if f"correction_{correction_id}" in file_name or f"correction_{correction_id}" in doc_name:
                target_doc_name = doc_name
                break

        if not target_doc_name:
            logger.warning(
                f"Injected document not found for correction {correction_id} in domain {domain}"
            )
            return False

        deleted = await store_manager.delete_document(domain, target_doc_name)
        if deleted:
            logger.info(
                "Correction injection removed from Gemini",
                extra={"correction_id": correction_id, "domain": domain},
            )
        return deleted

    except Exception as e:
        logger.error(
            f"Failed to remove injection: {e}",
            extra={"correction_id": correction_id, "domain": domain},
        )
        return False
