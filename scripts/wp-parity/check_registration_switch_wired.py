"""The registration options must be editable AND consumed.

The failure this guards against is the one that produced `MediaAsset.post_id`:
an option seeded in `default_options.py`, shown in a settings card, and read by
nothing — so the switch looks live, the form saves, and every account is still
created. Both halves are checked, and neither alone is enough.

  * the card edits the two keys, so an operator can reach them;
  * `register()` reads both, so what they set is what happens.

And the third thing, which is the one that matters most: the privileged-role
ceiling must be a *code* refusal rather than a UI restriction. A dropdown that
hides admin while the server accepts it is not a control.

Run:  python scripts/wp-parity/check_registration_switch_wired.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CARD = os.path.join(ROOT, "frontend", "components", "admin", "user-settings-card.tsx")
SETTINGS = os.path.join(ROOT, "frontend", "app", "admin", "settings", "page.tsx")
SERVICE = os.path.join(ROOT, "backend", "app", "modules", "auth",
                       "application", "auth_service.py")
DEFAULTS = os.path.join(ROOT, "backend", "app", "modules", "settings",
                        "application", "default_options.py")

KEYS = ("registration_enabled", "registration_default_role")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (CARD, SETTINGS, SERVICE, DEFAULTS):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    card, settings, service, defaults = (read(p) for p in (CARD, SETTINGS, SERVICE, DEFAULTS))

    for key in KEYS:
        check(f"{key} is seeded", f'"{key}"' in defaults)
        check(f"{key} is editable in the settings card", key in card)

    check("the card is placed on the settings page",
          "UserSettingsCard" in settings)

    # The part that makes the switch real: the server reads it.
    check("register() reads registration_enabled",
          'SiteOptionsService.get(db, "registration_enabled"' in service)
    check("register() reads registration_default_role",
          'SiteOptionsService.get(db, "registration_default_role"' in service)
    # The ceiling is code, not UI.
    check("the privileged-role list is a module constant",
          "_PRIVILEGED_ROLES" in service)
    check("it is checked before the role is assigned",
          "if requested in _PRIVILEGED_ROLES:" in service)
    check("admin and super_admin are on it",
          '"admin"' in service and '"super_admin"' in service)

    # Order, not presence. A check that still exists but runs *after* the role
    # has been written is the shape a refactor produces, and a presence check
    # passes it. Read the positions rather than the strings: this is the third
    # time this session a gate accepted a guard that no longer runs where it
    # must.
    # `user_role = UserRole(...)` appears twice in this file — once in
    # register(), once elsewhere — and a bare find() picked the wrong one, which
    # made the ordering assertion compare against a position it should never
    # have looked at. Scoped to register() from its own step comment.
    reg_at = service.find("    # 4. Assign the configured default role.")
    check_at = service.find("if requested in _PRIVILEGED_ROLES:", reg_at)
    assign_at = service.find("user_role = UserRole(user_id=user.id, role_id=role.id)",
                             reg_at)
    check("the ceiling runs before the role is written",
          check_at != -1 and assign_at != -1 and check_at < assign_at,
          f"check at {check_at}, assignment at {assign_at} (register starts {reg_at})")

    switch_at = service.find('SiteOptionsService.get(db, "registration_enabled"')
    user_add = service.find("db.add(user)")
    check("the switch is read before the account is created",
          switch_at != -1 and user_add != -1 and switch_at < user_add,
          f"switch read at {switch_at}, user created at {user_add}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: both registration options are seeded, editable, and read by "
          "the server — and the privileged-role ceiling is code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())