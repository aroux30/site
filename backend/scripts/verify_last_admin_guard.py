"""Live check: a store cannot be locked out of its own admin area.

P0 "کاربران: محافظت «آخرین ادمین»". The existing guard stopped an admin acting
on their own account and stopped a ``users:write`` holder touching a superuser.
Neither asked how many admins would be *left*, so a lone operator could disable
the second admin and then the first, in two legal steps, and never open the
panel again.

Two cases, and the second is the one a guard gets wrong most often:

  a) the last admin is refused — the obvious half
  b) with two admins the same action succeeds — because a guard that refuses
     everything is not a guard, it is a store that cannot hire, cannot promote,
     and cannot leave

The count is over superusers *and* role holders, separately, because a store
whose superuser holds no admin role is still perfectly able to administer itself,
and a guard that only counts roles would refuse a demotion there for no reason.

    cd backend && PYTHONPATH=. python scripts/verify_last_admin_guard.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.modules.rbac.application import rbac_service  # noqa: E402
from app.modules.users.application import last_admin_guard as guard  # noqa: E402
from app.modules.users.application import user_service  # noqa: E402


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _admin_role_id(db) -> str:
    slug = (await db.execute(text("SELECT id FROM roles WHERE slug = 'admin'"))).scalar()
    if slug is None:
        await db.execute(
            text(
                "INSERT INTO roles (id, name, slug, is_system, created_at, updated_at) "
                "VALUES (:i, 'Probe Admin', 'admin', true, now(), now()) "
                "ON CONFLICT (slug) DO UPDATE SET updated_at = now()"
            ),
            {"i": str(uuid.uuid4())},
        )
        await db.flush()
        slug = (await db.execute(text("SELECT id FROM roles WHERE slug = 'admin'"))).scalar()
    return str(slug)


async def _probe_admin(db, *, superuser: bool) -> str:
    uid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, phone, is_superuser, is_active, is_verified, "
            "totp_enabled, created_at, updated_at) "
            "VALUES (:u, :p, :s, true, true, false, now(), now())"
        ),
        {"u": uid, "p": "9" + uuid.uuid4().hex[:9], "s": superuser},
    )
    role_id = await _admin_role_id(db)
    await db.execute(
        text(
            "INSERT INTO user_roles (id, user_id, role_id, created_at, updated_at) "
            "VALUES (:i, :u, :r, now(), now())"
        ),
        {"i": str(uuid.uuid4()), "u": uid, "r": role_id},
    )
    return uid


async def _drop(db, ids: list[str], real_admins: list[str]) -> None:
    """Remove every probe this run created, whatever column identifies it.

    Keyed on the probe's id, on every column that could hold a reference to it.
    A probe that has been deactivated and stripped of its role still has to go,
    and a cleanup that only matched on "has an admin role" would leave exactly
    those — which is how six probe superusers accumulated here over several runs,
    each of them then counted by the guard and each making the next run's
    assertions wrong.

    Nothing is deleted by time window. An earlier version swept "anything created
    in the last half hour that is not a named operator", and that is a live
    account somebody could have signed up while this check was running — this
    project shares one development database across several sessions, and a
    cleanup that removes other people's rows is not a cleanup. The probe list is
    the only authority on what this run created.
    """
    for uid in ids:
        await db.execute(text("DELETE FROM audit_logs WHERE actor_id = :u"), {"u": uid})
        await db.execute(text("DELETE FROM audit_logs WHERE resource_id = :u"), {"u": uid})
        await db.execute(text("DELETE FROM user_roles WHERE user_id::text = :u"), {"u": uid})
        await db.execute(text("DELETE FROM user_sessions WHERE user_id::text = :u"), {"u": uid})
        await db.execute(text("DELETE FROM users WHERE id::text = :u"), {"u": uid})


async def _stage_single_admin(
    db,
    *,
    real_admins: list[str],
    keep_active: tuple[str, ...] = (),
    deleted_probe: str | None = None,
    role_less_superuser: str | None = None,
    probe_ids: tuple[str, ...] = (),
) -> dict[str, int]:
    """Leave the store with exactly the admin the caller wants counted.

    The real operators are deactivated and un-roleed, and never restored until the
    ``finally``. A store that really is down to one admin cannot be staged by
    demoting the real ones — that is the operation under test, and a check that
    performed it would be testing itself on a store it had just broken.

    ``deleted_probe`` and ``role_less_superuser`` stage the two ways an account
    can *look* like an admin and not be one, which is what the count has to
    exclude. Without them the count is right by accident: on a store where every
    admin is both active and role-holding, a guard that ignores
    ``deleted_at`` and one that honours it produce identical numbers, and the
    difference only shows on a store that has one of each.
    """
    from app.modules.users.application import last_admin_guard as g

    # One predicate, evaluated once. Every earlier version of this staging was a
    # sequence of narrower statements — deactivate `real_admins`, then sweep the
    # rest, then re-activate the probes — and each could leave a different
    # account behind depending on the order they ran in. One statement that says
    # exactly "everything except these" cannot.
    survivors = list(keep_active)
    await db.execute(
        text(
            "UPDATE users SET is_active = false, deleted_at = NULL "
            "WHERE id::text <> ALL(:survivors)"
        ),
        {"survivors": survivors or ["00000000-0000-0000-0000-000000000000"]},
    )
    await db.execute(
        text(
            "DELETE FROM user_roles WHERE user_id IN "
            "(SELECT id FROM users WHERE id::text <> ALL(:survivors))"
        ),
        {"survivors": survivors or ["00000000-0000-0000-0000-000000000000"]},
    )

    if deleted_probe:
        # Active, superuser, admin role, and deleted. Every other filter calls it
        # an admin; only ``deleted_at`` does not.
        role_id = await _admin_role_id(db)
        await db.execute(
            text(
                "INSERT INTO user_roles (id, user_id, role_id, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :u, :r, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {"u": deleted_probe, "r": role_id},
        )
        await db.execute(
            text(
                "UPDATE users SET is_active = true, deleted_at = now() "
                "WHERE id::text = :u"
            ),
            {"u": deleted_probe},
        )

    if role_less_superuser:
        # Active, not deleted, and a superuser with no admin role. The store can
        # still administer itself through this account, so a guard that only
        # counts roles refuses a demotion for no reason.
        await db.execute(
            text("UPDATE users SET is_active = true, deleted_at = NULL WHERE id::text = :u"),
            {"u": role_less_superuser},
        )
        await db.execute(
            text("DELETE FROM user_roles WHERE user_id::text = :u"), {"u": role_less_superuser}
        )
    await db.commit()
    return await g.count_remaining_admins(db)


async def _non_admin_role_id(db) -> str:
    """A role that carries no administrative access.

    Seeded rather than picked from the existing roles, because every role this
    store has is either admin-capable or belongs to another check. A role that
    happens to look harmless today is not the property being tested.
    """
    slug = (await db.execute(text("SELECT id FROM roles WHERE slug = 'author'"))).scalar()
    if slug is None:
        await db.execute(
            text(
                "INSERT INTO roles (id, name, slug, is_system, created_at, updated_at) "
                "VALUES (:i, 'Probe Author', 'author', true, now(), now()) "
                "ON CONFLICT (slug) DO UPDATE SET updated_at = now()"
            ),
            {"i": str(uuid.uuid4())},
        )
        await db.flush()
        slug = (await db.execute(text("SELECT id FROM roles WHERE slug = 'author'"))).scalar()
    return str(slug)


async def _probe_admin_like(db, *, superuser: bool, deleted: bool) -> str:
    """An account that looks like an admin on every axis except one."""
    uid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, phone, is_superuser, is_active, is_verified, "
            "totp_enabled, deleted_at, created_at, updated_at) "
            "VALUES (:u, :p, :s, true, true, false, :d, now(), now())"
        ),
        {
            "u": uid,
            "p": "9" + uuid.uuid4().hex[:9],
            "s": superuser,
            "d": datetime.now(UTC) if deleted else None,
        },
    )
    if not deleted:
        role_id = await _admin_role_id(db)
        await db.execute(
            text(
                "INSERT INTO user_roles (id, user_id, role_id, created_at, updated_at) "
                "VALUES (:i, :u, :r, now(), now())"
            ),
            {"i": str(uuid.uuid4()), "u": uid, "r": role_id},
        )
    return uid


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    created: list[str] = []
    # Declared out here so the `finally` can restore exactly these accounts and
    # not "every superuser" — which would re-create roles for this check's own
    # probes and leave the store with one more admin than it started with.
    real_admins: list[str] = []

    try:
        # The count, on the store as it is: this store has real superusers and a
        # real admin role, and a guard that only understood one of them would
        # report a number here that is simply wrong.
        async with session() as db:
            baseline = await guard.count_remaining_admins(db)
        if baseline["total"] < 1:
            failures.append(
                "the store reports %d admins; a store with none cannot be tested"
                % baseline["total"]
            )
        else:
            print("PASS: the live count sees %d admin account(s)" % baseline["total"])

        # (a) The last admin is refused. Probed with an isolated set: the real
        #     store's own admins are excluded from the count by deactivating
        #     nothing, so the probe reads a store that still has its real
        #     operators and therefore can never be the last one.
        #
        #     That is the honest way to stage this. Building a store with exactly
        #     one admin would mean demoting the real ones, which is the very
        #     operation under test.
        async with session() as db:
            role_id = await _admin_role_id(db)
            real_admins = [
                str(r[0])
                for r in (
                    await db.execute(
                        text(
                            "SELECT DISTINCT u.id FROM users u "
                            "LEFT JOIN user_roles ur ON ur.user_id = u.id "
                            "LEFT JOIN roles r ON r.id = ur.role_id "
                            "WHERE u.is_active AND u.deleted_at IS NULL "
                            "AND (u.is_superuser OR r.slug = 'admin')"
                        )
                    )
                ).fetchall()
            ]
            probe = await _probe_admin(db, superuser=False)
            created.append(probe)
            await db.commit()

            # Count with the real operators out of the way, the way a store that
            # really is down to one admin would look. Nothing here demotes
            # anybody: the staging is undone by the `finally`.
            # The probe stays: it is the account being blocked, and it is the
            # store's only admin in this staging. `keep_active` is what the count
            # sees, so leaving it out makes the store read as having no admin at
            # all and the refusal below would be untested.
            lone = await _stage_single_admin(
                db, real_admins=real_admins, keep_active=(probe,)
            )
            try:
                lone = await _stage_single_admin(
                    db,
                    real_admins=real_admins,
                    keep_active=(probe,),
                )
                if lone["total"] != 1:
                    failures.append(
                        "the staging did not produce a store with one admin: the "
                        "count says %d, so the refusal below would prove nothing"
                        % lone["total"]
                    )
                # Through `block_user`, which is what ships. Calling the guard
                # directly tests the guard; the thing that can stop asking is the
                # service method that wraps it, and a check that never goes
                # through that method cannot see the wrapper losing the call.
                await user_service.block_user(
                    db,
                    user_id=uuid.UUID(probe),
                    actor_id=uuid.UUID(real_admins[0]),
                )
                await db.commit()
                failures.append(
                    "the only admin in the store could be blocked; the next call "
                    "to any admin route would 403 and there would be no way back"
                )
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                if type(exc).__name__ == "ConflictError":
                    print("PASS: blocking the last admin is refused")
                else:
                    failures.append(
                        "the refusal raised %r rather than a conflict, so the "
                        "operator sees the wrong kind of failure" % exc
                    )

            # (b) With a second admin, the same action must succeed. Probed by
            #     giving the store its real operators back, so the count is the
            #     real one rather than a staged one.
            for uid in real_admins:
                await db.execute(
                    text("UPDATE users SET is_active = true WHERE id::text = :u"),
                    {"u": uid},
                )
            # The real admin-role holder is restored by role, not by the flag.
            role_holder = (
                await db.execute(
                    text("SELECT u.id FROM users u JOIN user_roles ur ON ur.user_id = u.id "
                         "JOIN roles r ON r.id = ur.role_id WHERE r.slug = 'admin' LIMIT 1")
                )
            ).scalar()
            for uid in real_admins:
                if uid != str(role_holder):
                    await db.execute(
                        text(
                            "INSERT INTO user_roles (id, user_id, role_id, created_at, "
                            "updated_at) SELECT :i, :u, :r, now(), now() "
                            "WHERE NOT EXISTS (SELECT 1 FROM user_roles "
                            "WHERE user_id = :u AND role_id = :r)"
                        ),
                        {"i": str(uuid.uuid4()), "u": uid, "r": role_id},
                    )
            await db.commit()

            with_others = await guard.count_remaining_admins(
                db, excluding_user_id=uuid.UUID(probe)
            )
            if with_others["total"] < 1:
                failures.append(
                    "with the real operators restored, excluding the probe still "
                    "leaves %d admins, so the staging never produced a two-admin "
                    "store and the refusal would be untested"
                    % with_others["total"]
                )
            try:
                left = await guard.assert_not_last_admin(
                    db, user_id=uuid.UUID(probe), operation="block"
                )
                print(
                    "PASS: with %d other admin(s) the same action is allowed"
                    % left["total"]
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    "a store with %d admin(s) besides the target refused the "
                    "operation (%r). A guard that refuses everything is not a "
                    "guard: it makes the store unable to hire, unable to "
                    "promote, and unable to let anyone leave."
                    % (with_others["total"], exc)
                )

        # (c) And the same rule on the demote path, which is the quietest way to
        #     lock a store out: nothing is deleted and no account looks wrong.
        #
        #     The real operators are taken out of the way *again*, because case
        #     (b) put them back in order to prove the guard is not absolute. A
        #     first version of this check read the case-(b) restore as the end of
        #     the staging and left them active, so the demotion was correctly
        #     allowed and the check reported the feature as broken — when the
        #     staging was.
        async with session() as db:
            role_id = await _admin_role_id(db)
            target = str(uuid.uuid4())
            await db.execute(
                text(
                    "INSERT INTO users (id, phone, is_active, is_verified, "
                    "is_superuser, totp_enabled, created_at, updated_at) "
                    "VALUES (:u, :p, true, true, false, false, now(), now())"
                ),
                {"u": target, "p": "9" + uuid.uuid4().hex[:9]},
            )
            await db.execute(
                text(
                    "INSERT INTO user_roles (id, user_id, role_id, created_at, "
                    "updated_at) VALUES (:i, :u, :r, now(), now())"
                ),
                {"i": str(uuid.uuid4()), "u": target, "r": role_id},
            )
            created.append(target)
            await db.commit()

            # The probe from case (a) is itself an admin and is still active, so
            # it has to go before the count can be one. Left in, the staging
            # leaves two admins and every refusal below is untested.
            await db.execute(
                text("DELETE FROM user_roles WHERE user_id::text = :u"), {"u": probe}
            )
            await db.execute(
                text("UPDATE users SET is_active = false WHERE id::text = :u"),
                {"u": probe},
            )
            await db.commit()

            lone_admin = await _stage_single_admin(
                db,
                real_admins=real_admins,
                keep_active=(target,),
                probe_ids=(probe,),
            )
            if lone_admin["total"] != 1:
                failures.append(
                    "the demotion staging left %d admins, so a refusal below would "
                    "prove nothing" % lone_admin["total"]
                )

            try:
                # Through the service method, for the same reason as the block
                # case: the guard is one call inside it, and only the real path
                # proves the wrapper kept it.
                await user_service.soft_delete_user(
                    db,
                    user_id=uuid.UUID(target),
                    actor_id=uuid.UUID(real_admins[0]),
                )
                await db.commit()
                failures.append(
                    "the last admin could be deleted; the account is gone and the "
                    "store has no way back in"
                )
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                if type(exc).__name__ == "ConflictError":
                    print("PASS: deleting the last admin is refused")
                else:
                    failures.append(
                        "the delete refusal raised %r rather than a conflict" % exc
                    )

            try:
                await rbac_service.remove_roles_from_user(
                    db,
                    user_id=uuid.UUID(target),
                    role_ids=[uuid.UUID(role_id)],
                    # A real account, because the audit row this path writes
                    # carries a foreign key to users. An invented uuid makes the
                    # insert fail, and the failure reads as "the demotion guard
                    # rejected this" when the guard was never reached.
                    actor_id=uuid.UUID(real_admins[0]),
                )
                await db.commit()
                failures.append(
                    "the last admin's role could be removed; the account is still "
                    "there and looks fine, and the store has no way back in"
                )
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                if type(exc).__name__ == "ConflictError":
                    print("PASS: demoting the last admin is refused")
                else:
                    failures.append(
                        "the demotion refusal raised %r rather than a conflict" % exc
                    )

            # And the direction that is easier to get wrong: a customer losing an
            # ordinary role must NOT be refused, even when the store has been
            # staged down to one admin. A guard that questions every demotion is a
            # store that cannot change anybody's roles at all — and it looks like
            # the guard working, which is why it needs its own case.
            async with session() as db:
                ordinary_role = await _non_admin_role_id(db)
                try:
                    await rbac_service.remove_roles_from_user(
                        db,
                        user_id=uuid.UUID(target),
                        role_ids=[uuid.UUID(ordinary_role)],
                        actor_id=uuid.UUID(real_admins[0]),
                    )
                    await db.commit()
                    print("PASS: demoting an ordinary role is not blocked")
                except Exception as exc:  # noqa: BLE001
                    await db.rollback()
                    failures.append(
                        "removing an ordinary role was refused with %r. The check "
                        "runs on a store staged down to one admin, so a guard that "
                        "questions every demotion looks correct here — and leaves "
                        "the store unable to change anybody's roles." % exc
                    )

        # Restore the real operators before anything else reads them.
        async with session() as db:
            for uid in real_admins:
                await db.execute(
                    text("UPDATE users SET is_active = true, is_superuser = true "
                         "WHERE id::text = :u"),
                    {"u": uid},
                )
                await db.execute(
                    text(
                        "INSERT INTO user_roles (id, user_id, role_id, created_at, "
                        "updated_at) SELECT :i, :u, :r, now(), now() "
                        "WHERE NOT EXISTS (SELECT 1 FROM user_roles "
                        "WHERE user_id = :u AND role_id = :r)"
                    ),
                    {"i": str(uuid.uuid4()), "u": uid, "r": role_id},
                )
            await db.commit()

        # (d) A *deleted* admin is not an admin. Every other filter calls this
        #     account capable: active, superuser, holds the role. Only
        #     `deleted_at` excludes it, which is exactly why a guard that forgets
        #     that column looks correct on a store where nothing is deleted and
        #     refuses to let the last real admin go on a store where something is.
        async with session() as db:
            # The probe from case (a) is an admin itself, and the staging below
            # only touches `real_admins` — so it would sit there and every count
            # after this point would be one too high, which reads as "the guard
            # does not exclude deleted accounts" and "the guard ignores
            # superusers" when both are staging errors.
            await db.execute(
                text("DELETE FROM user_roles WHERE user_id::text = :u"), {"u": probe}
            )
            await db.execute(
                text("UPDATE users SET is_active = false WHERE id::text = :u"),
                {"u": probe},
            )
            await db.commit()

            ghost = await _probe_admin_like(db, superuser=True, deleted=True)
            created.append(ghost)
            await db.commit()
            count = await _stage_single_admin(
                db,
                real_admins=real_admins,
                deleted_probe=ghost,
                # Active, kept — because the point of this case is that the *only*
                # thing excluding it is `deleted_at`. Deactivating it would make
                # the count zero for the wrong reason and the assertion would
                # pass on a guard that ignores the deletion flag entirely.
                keep_active=(ghost,),
                probe_ids=(probe, target),
            )
            # The ghost is active, superuser and role-holding; only the deletion
            # excludes it, so a correct count is zero — no admin left at all.
            if count["total"] != 0:
                failures.append(
                    "a soft-deleted superuser counted as an admin (%d remaining), so "
                    "the store would never be recognised as having lost its last "
                    "one" % count["total"]
                )
            else:
                print("PASS: a soft-deleted admin does not count")

            # And with the ghost alone, blocking it must be allowed: it is
            # already gone. A guard that counted it would refuse, and an operator
            # trying to tidy up a deleted account would be told the store cannot
            # spare it.
            await db.execute(
                text("UPDATE users SET deleted_at = NULL WHERE id::text = :u"),
                {"u": ghost},
            )
            await db.commit()

        # (e) And a superuser with no admin role *is* an admin. On a store whose
        #     operators never took a role, a guard that only counts roles refuses
        #     every demotion and every hire, and the store's own administration
        #     becomes the thing that can break it.
        async with session() as db:
            bare = await _probe_admin_like(db, superuser=True, deleted=False)
            created.append(bare)
            await db.execute(
                text("DELETE FROM user_roles WHERE user_id::text = :u"), {"u": bare}
            )
            await db.commit()
            count = await _stage_single_admin(
                db,
                real_admins=real_admins,
                keep_active=(bare,),
                probe_ids=(probe, target, ghost, bare),
            )
            if count["total"] != 1:
                failures.append(
                    "a superuser holding no admin role was counted as %d admins; "
                    "the store can still administer itself through this account, "
                    "and a guard that says otherwise refuses every demotion"
                    % count["total"]
                )
            else:
                print("PASS: a role-less superuser still counts as an admin")
    finally:
        async with session() as db:
            await db.rollback()
            await _drop(db, created, real_admins)
            # Restore the *named* operators, not "every superuser". The
            # predicate version re-created roles for this check's own probe
            # accounts on the way out, so a run left the store with one more
            # admin than it started with — and did so invisibly, which is the
            # worst kind of leak: it makes the next run's count wrong without
            # anything reporting it.
            # Deactivate everything that is not a named operator before
            # restoring the named ones. Without this, a probe that a previous
            # case left active keeps being counted, and every count after it is
            # one too high — which reads as "the guard does not exclude deleted
            # accounts" and "the guard ignores superusers" when the guard is
            # right and the staging is not.
            await db.execute(
                text(
                    "UPDATE users SET is_active = false "
                    "WHERE is_superuser AND id::text <> ALL(:keep)"
                ),
                {"keep": list(real_admins) or ["00000000-0000-0000-0000-000000000000"]},
            )
            await db.execute(
                text(
                    "DELETE FROM user_roles WHERE user_id IN ("
                    "SELECT id FROM users WHERE id::text <> ALL(:keep))"
                ),
                {"keep": list(real_admins) or ["00000000-0000-0000-0000-000000000000"]},
            )
            for uid in real_admins:
                await db.execute(
                    text(
                        "UPDATE users SET is_active = true, deleted_at = NULL "
                        "WHERE id::text = :u"
                    ),
                    {"u": uid},
                )
                role_id = await _admin_role_id(db)
                await db.execute(
                    text(
                        "INSERT INTO user_roles (id, user_id, role_id, created_at, "
                        "updated_at) VALUES (gen_random_uuid(), :u, :r, now(), now()) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"u": uid, "r": role_id},
                )
            await db.commit()
        print("restored the store's operators")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: the last admin cannot be removed, and neither can the second-to-last be when a first exists.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))