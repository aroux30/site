"""Wave 5 #65 — prove the upload read is capped, not merely documented.

Run:  cd backend && PYTHONIOENCODING=utf-8 python ../scripts/wp-parity/w5_upload_cap.py

The bug this replaces: ``await file.read()`` buffered the whole body before any
size check, so the ceiling was enforced only after the allocation it was meant to
prevent. A 20-file batch could buffer 2 GB in one request.

These checks are behavioural. A fake UploadFile records how many bytes it was
ASKED for, so "we stopped early" is measurable rather than asserted.

Every check drives the PUBLIC entry point ``MediaService.upload_file``, never
``_read_capped`` directly. An earlier version of this file called the helper
straight, and the whole suite stayed green when the helper was replaced with a
plain ``await file.read()`` — the tests were measuring the helper, not the
behaviour the routes actually get. Same trap as
``a-gate-must-be-able-to-fail``.
"""

import asyncio
import io
import sys
import uuid
from typing import Any

sys.path.insert(0, r"C:\Users\Administrator\Desktop\site\backend")

from app.core.exceptions.handlers import ValidationError  # noqa: E402
from app.modules.media.application.media_service import (  # noqa: E402
    MAX_BATCH_FILES,
    MAX_MEDIA_FILE_SIZE_BYTES,
    MediaService,
)

MB = 1024 * 1024
results: list[tuple[str, bool, str]] = []


class FakeUpload:
    """Stands in for UploadFile.

    ``requested_total`` is what proves the cap: a full-body read asks for the
    whole payload, a capped read stops as soon as it passes the ceiling.
    """

    def __init__(
        self,
        size: int,
        content_type: str = "image/jpeg",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._buf = io.BytesIO(b"\xff\xd8\xff\xe0" + b"x" * size)
        self.content_type = content_type
        self.filename = "probe.jpg"
        self.headers = headers or {}
        self.requested_total = 0

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._buf.getbuffer())
        self.requested_total += size
        return self._buf.read(size)


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}")


async def _try_upload(
    file: FakeUpload, max_bytes: int | None
) -> tuple[bool, int, str]:
    """Drive the real upload path. Returns (ok, bytes_requested, detail)."""
    from sqlalchemy.ext.asyncio import AsyncSession

    db: Any = AsyncSession  # never touched: every path below raises before use
    try:
        await MediaService.upload_file(
            db,  # type: ignore[arg-type]
            file=file,  # type: ignore[arg-type]
            uploader_id=uuid.UUID(int=1),
            max_bytes=max_bytes,
        )
        return True, file.requested_total, "accepted"
    except ValidationError as exc:
        return (
            False,
            file.requested_total,
            str(getattr(exc, "error_code", exc)),
        )
    except Exception as exc:  # reached a DB call — also proves we streamed first
        return False, file.requested_total, f"{type(exc).__name__}: {exc}"


async def main() -> int:
    # 1. A small body under the cap gets past the size guard. It will then
    #    fail on the (deliberately fake) DB, which is fine — reaching that
    #    point IS the proof the size check let it through.
    f = FakeUpload(1024)
    ok, asked, detail = await _try_upload(f, 10 * MB)
    check(
        "a small upload passes the size guard",
        "FILE_TOO_LARGE" not in detail,
        f"size guard said {detail!r} after requesting {asked:,} bytes",
    )

    # 2. A body past the cap is refused.
    f = FakeUpload(20 * MB)
    ok, asked, detail = await _try_upload(f, 10 * MB)
    check(
        "an oversize upload is refused",
        not ok and detail == "FILE_TOO_LARGE",
        f"outcome={detail!r} after requesting {asked:,} bytes",
    )

    # 3. THE POINT OF THE CHANGE: the refusal happens early, so a huge body is
    #    never buffered against a small cap. This is the assertion that fails
    #    when the capped read is replaced by a plain full-body read.
    huge = 200 * MB
    f = FakeUpload(huge)
    ok, asked, detail = await _try_upload(f, 10 * MB)
    check(
        "refusal happens before the body is buffered",
        asked < huge,
        f"asked for {asked:,} of {huge:,} bytes "
        f"({asked / huge:.1%} of the payload) — the rest is never read",
    )

    # 4. A false Content-Length cannot buy extra bytes.
    f = FakeUpload(20 * MB, headers={"content-length": "1"})
    ok, asked, detail = await _try_upload(f, 10 * MB)
    check(
        "a false Content-Length cannot buy extra bytes",
        not ok and detail == "FILE_TOO_LARGE",
        f"outcome={detail!r} — the streaming check, not the header, held",
    )

    # 5. An honest oversize Content-Length is refused with ZERO bytes read.
    f = FakeUpload(20 * MB, headers={"content-length": str(20 * MB)})
    ok, asked, detail = await _try_upload(f, 10 * MB)
    check(
        "an honest Content-Length short-circuits the read",
        asked == 0,
        f"refused after requesting {asked} bytes (header short-circuit)",
    )

    # 6. A batch of 20 oversize files cannot each be buffered in full. This is
    #    the "2 GB in one request" shape from the original finding.
    per_file = 100 * MB
    total_asked = 0
    refused = 0
    for _ in range(MAX_BATCH_FILES):
        f = FakeUpload(per_file)
        ok, asked, detail = await _try_upload(f, 10 * MB)
        total_asked += asked
        if detail == "FILE_TOO_LARGE":
            refused += 1
    check(
        "a full batch never buffers its whole payload",
        total_asked < MAX_BATCH_FILES * per_file,
        f"{MAX_BATCH_FILES} x {per_file // MB}MB files: asked for "
        f"{total_asked / MB:.0f}MB total instead of "
        f"{MAX_BATCH_FILES * per_file / MB:.0f}MB "
        f"({refused}/{MAX_BATCH_FILES} refused early)",
    )

    # 7. The global ceiling is still a real ceiling.
    check(
        "the global ceiling is unchanged",
        MAX_MEDIA_FILE_SIZE_BYTES == 100 * MB,
        f"MAX_MEDIA_FILE_SIZE_BYTES = {MAX_MEDIA_FILE_SIZE_BYTES // MB}MB",
    )

    print()
    failed = [r for r in results if not r[1]]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("FAILED: " + ", ".join(r[0] for r in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
