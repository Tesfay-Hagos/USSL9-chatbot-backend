"""
Reset dashboard data — keeps only admin_users (superadmin seed).

Clears: documents, store_registry, corrections, chat_logs.
Preserves: admin_users.

Run from project root: uv run python scripts/reset_dashboard_data.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root so app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete

from app.core.database import get_db, init_db
from app.core.models import (
    AdminUser,
    ChatLogRecord,
    CorrectionRecord,
    DocumentRecord,
    StoreRecord,
)


async def main() -> None:
    """Clear all dashboard data except admin_users."""
    await init_db()

    async with get_db() as db:
        # Order matters: documents FK → store_registry; others are independent
        from sqlalchemy import select, func

        for model in (DocumentRecord, StoreRecord, CorrectionRecord, ChatLogRecord):
            result = await db.execute(delete(model))
            count = result.rowcount if result.rowcount is not None else 0
            print(f"  Deleted {model.__tablename__}: {count} row(s)")

        # Verify admin_users untouched
        admin_count = await db.scalar(select(func.count()).select_from(AdminUser))
        print(f"  admin_users preserved: {admin_count} row(s)")

    print("Dashboard reset complete. Only superadmin seed remains.")


if __name__ == "__main__":
    asyncio.run(main())
