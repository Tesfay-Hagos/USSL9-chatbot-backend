"""
Extra stores added via API – persist descriptions for store selection.

Initial stores are the four from Allegato A (config.ULSS9_STORES).
Stores created via POST /api/admin/stores are "extra"; their descriptions
are saved here so the store selector can include them.
"""

import json
import logging
from pathlib import Path

from app.config import ULSS9_STORES

logger = logging.getLogger(__name__)

# Persist in data/store_descriptions.json
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DESCRIPTIONS_FILE = BASE_DIR / "data" / "store_descriptions.json"

INITIAL_IDS = {s["id"] for s in ULSS9_STORES}


def _load_descriptions() -> dict[str, str]:
    """Load domain -> description for extra stores."""
    if not DESCRIPTIONS_FILE.exists():
        return {}
    try:
        data = json.loads(DESCRIPTIONS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Could not load store_descriptions: {e}")
        return {}


def _save_descriptions(descriptions: dict[str, str]) -> None:
    """Save domain -> description for extra stores."""
    DESCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DESCRIPTIONS_FILE.write_text(
        json.dumps(descriptions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_extra_description(domain: str) -> str | None:
    """Return saved description for a store added via API, or None."""
    return _load_descriptions().get(domain)


def set_extra_description(domain: str, description: str) -> None:
    """Save description for a store (used when creating store via API)."""
    if domain in INITIAL_IDS:
        return  # do not overwrite initial store descriptions
    desc = _load_descriptions()
    desc[domain] = description
    _save_descriptions(desc)


def list_extra_store_ids() -> list[str]:
    """Return domain ids that have a saved description (extra stores)."""
    return list(_load_descriptions().keys())
