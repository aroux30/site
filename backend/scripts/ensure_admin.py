"""Ensure a default admin exists — WordPress-style first-run bootstrap.

A fresh database has no operator, so the admin panel is unreachable. This
script guarantees one login exists:

    phone:    ADMIN_PHONE    (default 09120000000)
    password: ADMIN_PASSWORD (default "admin" — development demo default)

The store is phone-first: login is by phone number, not a username.

Idempotency contract (start_project.bat runs this on every launch):
- If the admin does not exist, it is created with full superuser flags,
  the ``admin`` role, and every permission in the catalog.
- If it already exists, only the flags/role are *ensured* — the password
  and phone are never touched, so changes made after the first login
  survive every subsequent run.

All database access goes through the existing service layer
(``permission_seed`` / ``rbac_service`` / ``user_service``) and plain ORM
adds — no ad-hoc queries here.

Usage: ``python scripts/ensure_admin.py`` (from backend/)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Runnable both as `python scripts/ensure_admin.py` and via -m: make the
# backend root (the parent of this folder) importable for `app.*`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config.settings import get_settings
from app.core.database.session import async_session_factory
from app.core.security.password import hash_password
from app.modules.rbac.application.permission_seed import seed_permissions
from app.modules.rbac.application.rbac_service import assign_roles_to_user, list_roles
from app.modules.users.application.user_service import get_users
from app.modules.users.domain.models import User, UserProfile

# Demo defaults: a valid Iranian mobile number so the phone-only login form
# accepts it, and the classic "admin" password the owner asked for. Override
# via ADMIN_PHONE / ADMIN_PASSWORD in backend/.env.
DEFAULT_ADMIN_PHONE = "09120000000"
DEFAULT_ADMIN_PASSWORD = "admin"


async def ensure_admin() -> int:
    settings = get_settings()
    phone = (getattr(settings, "ADMIN_PHONE", "") or DEFAULT_ADMIN_PHONE).strip()
    password = getattr(settings, "ADMIN_PASSWORD", "") or DEFAULT_ADMIN_PASSWORD

    async with async_session_factory() as db:
        # 1. Permission catalog + the `admin` role with every permission.
        stats = await seed_permissions(db)

        # 2. Is there an operator with this phone already?
        users, _total = await get_users(
            db, search=phone, include_deleted=True, page_size=50
        )
        existing = next((u for u in users if u.get("phone") == phone), None)

        if existing is None:
            # First run: create the operator account.
            user = User(
                phone=phone,
                password_hash=hash_password(password),
                is_active=True,
                is_verified=True,
                is_superuser=True,
                pending_approval=False,
            )
            db.add(user)
            await db.flush()
            db.add(
                UserProfile(user_id=user.id, first_name="مدیر", last_name="فروشگاه")
            )
            admin_user_id = user.id
            print(f"Admin created: phone={phone} password={'*' * len(password)}")
        else:
            # Ensure flags; NEVER reset the password here — a password the
            # operator changed in the panel must survive launcher re-runs.
            user = await db.get(User, existing["id"])
            user.is_active = True
            user.is_superuser = True
            user.is_verified = True
            user.pending_approval = False
            admin_user_id = existing["id"]
            print(f"Admin already present: phone={phone} (password untouched)")

        # 3. Attach the admin role if missing (actor = the admin itself; no
        #    actor_payload → the self-escalation guard stays out of bootstrap).
        roles, _ = await list_roles(db)
        admin_role = next((r for r in roles if r.slug == "admin"), None)
        roles_now = existing.get("roles", []) if existing else []
        if admin_role is not None and "admin" not in roles_now:
            await assign_roles_to_user(
                db,
                user_id=admin_user_id,
                role_ids=[admin_role.id],
                actor_id=admin_user_id,
            )
            print("Admin role attached.")
        print(
            f"Permissions: catalog={stats.total_catalog}, "
            f"granted_to_admin={len(stats.permissions_granted_to_admin)}"
        )

        await db.commit()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(ensure_admin()))
    except Exception as exc:  # noqa: BLE001 — the launcher prints and continues
        print(f"ensure_admin failed: {exc}", file=sys.stderr)
        sys.exit(1)
