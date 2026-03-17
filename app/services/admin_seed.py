"""
Seed admin user for ULSS 9 Chatbot.

Creates the default admin if not exists. Password can be changed later via password reset.
"""

import logging
import os
import uuid

import bcrypt
from sqlalchemy import select

from app.core.database import get_db
from app.core.models import AdminUser

logger = logging.getLogger(__name__)

# Admin seed credentials from environment (not hardcoded in source)
SEED_EMAIL = os.getenv("ADMIN_SEED_EMAIL", "[EMAIL_ADDRESS]")
SEED_PASSWORD = os.getenv("ADMIN_SEED_PASSWORD", "ChangeMe@password")


async def seed_admin_user() -> None:
    """Create the default admin user if none exists."""
    async with get_db() as db:
        result = await db.execute(select(AdminUser).where(AdminUser.email == SEED_EMAIL))
        existing = result.scalars().first()
        if existing:
            logger.info("Admin user already exists: %s", SEED_EMAIL)
            return

        password_hash = bcrypt.hashpw(
            SEED_PASSWORD.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        admin = AdminUser(
            id=uuid.uuid4().hex,
            email=SEED_EMAIL,
            password_hash=password_hash,
            display_name="Admin",
            is_active=True,
        )
        db.add(admin)
        logger.info("Seeded admin user: %s", SEED_EMAIL)
    logger.info("Admin user seeding complete")
