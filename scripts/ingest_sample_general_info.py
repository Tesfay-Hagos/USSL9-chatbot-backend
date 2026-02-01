#!/usr/bin/env python3
"""
Ingest sample "informazioni generali" documents into the general_info store.

Run from the backend root:
  uv run python scripts/ingest_sample_general_info.py

Requires:
  - GEMINI_API_KEY in .env
  - Store "general_info" will be created if it does not exist (via create_all or create_store)

Uploads all .md and .txt files from data/ulss9_sample/general_info/ to the
general_info Gemini File Search Store so RAG can use them for answers.
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend root is on path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv
load_dotenv(BACKEND_ROOT / ".env")

from app.config import GEMINI_API_KEY
from app.services.store_manager import StoreManager


SAMPLE_DIR = BACKEND_ROOT / "data" / "ulss9_sample" / "general_info"
ALLOWED_EXTENSIONS = (".md", ".txt")


async def main() -> None:
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set. Set it in .env and try again.")
        sys.exit(1)

    if not SAMPLE_DIR.exists():
        print(f"ERROR: Sample directory not found: {SAMPLE_DIR}")
        sys.exit(1)

    files = sorted(
        f for f in SAMPLE_DIR.iterdir()
        if f.is_file()
        and f.suffix.lower() in ALLOWED_EXTENSIONS
        and f.name.lower() != "readme.md"
    )
    if not files:
        print(f"No .md or .txt files in {SAMPLE_DIR}")
        sys.exit(0)

    store_manager = StoreManager()
    if not store_manager.client:
        print("ERROR: StoreManager could not initialize Gemini client. Check API key.")
        sys.exit(1)

    # Ensure general_info store exists
    store = store_manager.get_store("general_info")
    if not store:
        print("Creating store 'general_info'...")
        await store_manager.create_store("general_info", "Informazioni generali ULSS 9")
    else:
        print("Store 'general_info' already exists.")

    print(f"Uploading {len(files)} file(s) to store 'general_info'...")
    for path in files:
        try:
            result = await store_manager.upload_document(
                str(path),
                "general_info",
                source_type="attachment",
            )
            print(f"  OK: {path.name} -> {result.get('title', path.name)}")
        except Exception as e:
            print(f"  FAIL: {path.name} - {e}")

    print("Done. You can now ask the chatbot questions about ULSS 9 (informazioni generali).")


if __name__ == "__main__":
    asyncio.run(main())
