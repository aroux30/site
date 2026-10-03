"""Guard: clearing a JSONB column actually empties it.

P0 "حریم خصوصی: حذف خودکار داده‌های منقضی". Postgres JSONB has two different
empties and they are not interchangeable. The JSON value ``null`` is a real
value that ``IS NOT NULL`` matches; SQL NULL is not. So a column "cleared" by
writing JSON null is still holding its payload as far as every query in the
codebase is concerned.

The bug this guards against was live in two places at once and invisible to
every tool the project runs:

  - ``privacy_request_service.purge_expired`` cleared rows through the ORM
    attribute, which serializes ``None`` to the JSON text ``null``. The rows the
    task "purged" then failed their own ``result_payload IS NOT NULL`` filter on
    the next run and were re-selected forever, while the logs reported a count.
  - the same assignment in ``get_result`` meant a subject who downloaded their
    export left the full copy behind.

Neither ruff, mypy, nor tsc can see this: the types are right, the code is right,
and the write only misbehaves in the database. A static read of the source is
also not enough on its own, which is why the real assertion lives in
backend/scripts/verify_privacy_retention.py; this guard exists to catch the
regression at commit time, before anyone gets a database to run the live check
against.

    python scripts/wp-parity/check_jsonb_null_semantics.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MODELS = BACKEND / "app" / "modules" / "settings" / "domain" / "models.py"
SERVICE = (
    BACKEND / "app" / "modules" / "settings" / "application" / "privacy_request_service.py"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    failures: list[str] = []
    models = read(MODELS)
    service = read(SERVICE)

    if not models:
        print("FAIL: %s does not exist" % MODELS)
        return 1
    if not service:
        print("FAIL: %s does not exist" % SERVICE)
        return 1

    # 1. The column has to be wrapped. Without the wrapper, `None` means JSON
    #    null on this column and every "cleared" row is really still there.
    #    The type annotation holds brackets of its own (`dict[str, Any] | None`),
    #    so it is matched up to the `= mapped_column` rather than to the first
    #    `]` — an earlier version stopped there and reported the column missing.
    column = re.search(
        r"result_payload: Mapped\[.*?\] = mapped_column\(\s*([^,)]+)", models
    )
    if not column:
        failures.append(
            "result_payload is not declared in the model, so the JSONB null "
            "semantics cannot be checked at all"
        )
    elif "SqlNullOnNone" not in column.group(1):
        failures.append(
            "result_payload is a plain JSONB column again, so assigning None to it "
            "writes the JSON value null rather than SQL NULL -- every row the "
            "retention purge 'cleared' is still holding its payload"
        )

    # 2. The wrapper has to be real, not decorative. A `process_bind_param` that
    #    returns None is *not enough*: JSONB is itself a TypeDecorator, so the
    #    inner one runs its own bind processor first and turns None into the
    #    string 'null'. The decision has to be made in `bind_processor`, which is
    #    the only layer that sees the original Python value. An earlier version
    #    of this file did it in the wrong method and every assignment of None
    #    silently went through unchanged.
    if "class SqlNullOnNone" in models:
        body = re.search(
            r"class SqlNullOnNone\(TypeDecorator\):(.*?)\n\nclass ", models, re.S
        )
        if not body:
            failures.append("SqlNullOnNone could not be read, so it cannot be checked")
        else:
            text = body.group(1)
            if "def bind_processor" not in text:
                failures.append(
                    "SqlNullOnNone does not override bind_processor; with JSONB "
                    "underneath it, process_bind_param is never consulted and the "
                    "wrapper does nothing"
                )
            if "None if value is None" not in text:
                failures.append(
                    "SqlNullOnNone's bind_processor does not short-circuit None, so "
                    "an empty assignment is still serialized to the JSON text 'null'"
                )
            if re.search(r"def process_bind_param.*?super\(\)", text, re.S):
                failures.append(
                    "SqlNullOnNone delegates to super() for non-null values; the "
                    "JSONB dialect type raises NotImplementedError there, so the "
                    "first real payload written through this column would fail"
                )

    # 3. The purge must clear through SQL NULL rather than the ORM attribute.
    #    A bulk UPDATE is immune to the decorator entirely, which is exactly why
    #    it is the safe form -- but the check is here so a rewrite back to
    #    attribute assignment is noticed.
    #    purge_expired is the last method in the file, so it is bounded by the end
    #    of the source rather than by a following decorator: a `\n    @staticmethod`
    #    terminator silently matched nothing here and read as "the UPDATE is
    #    gone".
    purge = re.search(r"async def purge_expired\((.*)", service, re.S)
    if not purge:
        failures.append("purge_expired could not be read")
    else:
        text = purge.group(1)
        if "result_payload=null()" not in text:
            failures.append(
                "purge_expired no longer clears the payload with SQL NULL, so it "
                "depends on a JSONB column writing Python None as an empty value"
            )
        if re.search(r"row\.result_payload\s*=\s*None", text):
            failures.append(
                "purge_expired assigns None to the ORM attribute, which writes the "
                "JSON value null and leaves the row matching its own filter again"
            )

    # 4. get_result is the one place that still assigns the attribute, on
    #    purpose: it hands the payload back to the caller first. It is only safe
    #    because the column is wrapped, which is why 1 and 2 above are the real
    #    assertions and this is the reminder of what depends on them.
    read_result = re.search(r"async def get_result\(.*?\n    # ──", service, re.S)
    if not read_result:
        failures.append("get_result could not be read")
    elif re.search(r"request\.result_payload\s*=\s*None", read_result.group(0)):
        if "SqlNullOnNone" not in models:
            failures.append(
                "get_result clears the payload by assignment and there is no "
                "SqlNullOnNone on the column to make that write SQL NULL"
            )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d JSONB null-semantics link(s) are broken." % len(failures))
        return 1
    print(
        "PASS: the payload column writes SQL NULL, and both clearing paths depend "
        "on that."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
