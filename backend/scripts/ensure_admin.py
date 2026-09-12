"""Ensure a superuser admin account exists on startup.

Reads ADMIN_PHONE and ADMIN_PASSWORD from .env file.
Creates the admin user if it doesn't exist; skips if already present.

Usage::

    python scripts/ensure_admin.py
"""

from __future__ import annotations

import asyncio
import re

import app.modules.rbac.domain.models  # noqa: F401  — must be imported before User for relationship resolution

from sqlalchemy.exc import IntegrityError

from app.core.config.settings import get_settings
from app.core.database.session import async_session_factory
from app.core.security.password import hash_password
from app.modules.users.domain.models import User, UserProfile


async def ensure_admin() -> None:
    """Create admin superuser from env vars; skip if already present."""
    settings = get_settings()

    raw_phone: str = getattr(settings, "ADMIN_PHONE", "09120000000")
    admin_phone: str = re.sub(r"\D", "", raw_phone).strip()
    admin_password: str = getattr(settings, "ADMIN_PASSWORD", "Admin@123456").strip()

    if len(admin_phone) != 11 or not admin_phone.startswith("09"):
        print("WARN: ADMIN_PHONE invalid (must be 09xxxxxxxxx)")
        return

    if len(admin_password) < 8:
        print("WARN: ADMIN_PASSWORD must be at least 8 characters")
        return

    hashed = hash_password(admin_password)

    async with async_session_factory() as db:
        try:
            admin = User(
                phone=admin_phone,
                password_hash=hashed,
                is_active=True,
                is_verified=True,
                is_superuser=True,
            )
            db.add(admin)
            await db.flush()

            profile = UserProfile(user_id=admin.id)
            db.add(profile)
            await db.commit()

            print(f"OK: Admin superuser created: phone={admin_phone}")
            print(f"    Password: {admin_password}")
            print("    NOTE: Change password from admin panel after first login!")
        except IntegrityError:
            await db.rollback()
            print(f"OK: Admin user {admin_phone} already exists — skipping")


if __name__ == "__main__":
    asyncio.run(ensure_admin())
