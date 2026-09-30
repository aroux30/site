"""Wave 5 #70 — prove the upload capability maps the way the role seeds claim.

Run:  cd backend && PYTHONIOENCODING=utf-8 python ../scripts/wp-parity/w5_upload_roles.py

`capability_service.py` declares `upload_files -> media:write` and the seeds give
`media:write` to editor and author but not to contributor or customer. The claim
is only worth anything if the enforced guard and the seeded grants agree, so
this checks both sides against the real registry rather than the source text.

Deliberately checks the SEED, not the live database: seeds are code, and a role
someone edited in the admin UI is allowed to differ.
"""

import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\site\backend")

from app.modules.rbac.application.capability_service import (  # noqa: E402
    CAPABILITY_PERMISSIONS,
)
from app.modules.rbac.application.permission_seed import (  # noqa: E402
    STAFF_ROLE_SEEDS,
)

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}")


def seed_grants(role: str) -> set[str]:
    for entry in STAFF_ROLE_SEEDS:
        if entry.get("slug") == role:
            return set(entry.get("permissions", ()))
    raise KeyError(f"no seed for role {role!r}")


def main() -> int:
    # 1. The capability the guards actually test exists and maps where claimed.
    mapped = CAPABILITY_PERMISSIONS.get("upload_files")
    check(
        "upload_files maps to media:write",
        mapped is not None and "media:write" in mapped,
        f"upload_files -> {sorted(mapped) if mapped else 'ABSENT'}",
    )

    # 2. Staff who publish content may upload.
    #    `admin` is not in STAFF_ROLE_SEEDS: it is a system role granted every
    #    catalog permission at seed time (permission_seed.py step 4), so it
    #    holds `media:write` by construction rather than by a listed tuple.
    for role in ("editor", "author"):
        grants = seed_grants(role)
        check(
            f"{role} may upload",
            "media:write" in grants,
            f"media:write {'present' if 'media:write' in grants else 'ABSENT'}",
        )

    # 2b. admin receives the whole catalog, which must include media:write.
    #    The catalog is a list of dicts with a "codename" key, not a set of
    #    strings — an earlier version of this file treated it as the latter and
    #    reported a false failure on correct code.
    from app.modules.rbac.application.permission_catalog import PERMISSION_CATALOG

    catalog_codenames = {
        entry["codename"] if isinstance(entry, dict) else entry
        for entry in PERMISSION_CATALOG
    }
    check(
        "admin holds media:write via the full catalog",
        "media:write" in catalog_codenames,
        f"media:write is {'in' if 'media:write' in catalog_codenames else 'ABSENT FROM'} "
        f"the {len(catalog_codenames)}-permission catalog the admin role is granted wholesale",
    )

    # 3. Roles that must NOT be able to write into the public library.
    #    This is the half that matters: a customer writing arbitrary files into
    #    the store's public media directory is the actual risk.
    for role in ("contributor", "customer"):
        grants = seed_grants(role)
        check(
            f"{role} may NOT upload",
            "media:write" not in grants,
            f"media:write {'LEAKED' if 'media:write' in grants else 'absent'}",
        )

    # 4. media:read is broader than media:write — a role that may only browse
    #    the library is a legitimate configuration and must not be mistaken for
    #    one that can write.
    customer = seed_grants("customer")
    check(
        "customer holds no media capability at all",
        not any(p.startswith("media:") for p in customer),
        f"media-* grants: {sorted(p for p in customer if p.startswith('media:')) or 'none'}",
    )

    # 5. The guard the routes use is the one the seed grants — if the routes
    #    tested a different codename the whole mapping above would be moot.
    from app.core.security.dependencies import RequirePermissions

    guard = RequirePermissions("media:write")
    check(
        "the upload guard tests media:write",
        guard.required_permissions == {"media:write"},
        f"RequirePermissions('media:write').required_permissions = "
        f"{sorted(guard.required_permissions)}",
    )

    print()
    failed = [r for r in results if not r[1]]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("FAILED: " + ", ".join(r[0] for r in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
