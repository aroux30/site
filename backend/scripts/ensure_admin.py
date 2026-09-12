"""Ensure a superuser admin account exists on startup.

Reads ADMIN_PHONE and ADMIN_PASSWORD from the environment (.env). Both are
REQUIRED — there is deliberately no default password, and known weak or
public defaults are refused. The password is never printed.

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

_WEAK_PASSWORDS = {"admin", "admin123", "admin@123456", "password", "12345678", "admin@123"}


async def ensure_admin() -> None:
    """Create admin superuser from env vars; skip if already present."""
    settings = get_settings()

    raw_phone: str = getattr(settings, "ADMIN_PHONE", "") or ""
    admin_phone: str = re.sub(r"\D", "", raw_phone).strip()
    admin_password: str = (getattr(settings, "ADMIN_PASSWORD", "") or "").strip()

    if not raw_phone:
        print("FATAL: ADMIN_PHONE is not set (add it to .env)")
        return
    if not admin_password:
        print("FATAL: ADMIN_PASSWORD is not set (add it to .env)")
        return

    if len(admin_phone) != 11 or not admin_phone.startswith("09"):
        print("FATAL: ADMIN_PHONE invalid (must be 09xxxxxxxxx)")
        return

    if len(admin_password) < 12:
        print("FATAL: ADMIN_PASSWORD must be at least 12 characters")
        return
    if admin_password.lower() in _WEAK_PASSWORDS:
        print("FATAL: ADMIN_PASSWORD is a known weak/default value — choose a unique one")
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
            print("    (password not displayed — set it yourself in .env)")
            print("    NOTE: Change password from admin panel after first login!")
        except IntegrityError:
            await db.rollback()
            print(f"OK: Admin user {admin_phone} already exists — skipping")


if __name__ == "__main__":
    asyncio.run(ensure_admin())
