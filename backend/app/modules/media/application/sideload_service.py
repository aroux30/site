"""Fetch a remote image into the media library (WordPress' ``media_sideload_image``).

The store's "add image from URL" path. It exists in WordPress because an
operator pasting a supplier's image URL is a normal thing to do, and the admin
media modal offers it natively.

Everything here is about not turning that into an SSRF hole or an unbounded
download:

* the URL goes through :mod:`app.core.security.url_guard`, which resolves DNS
  and refuses if **any** resolved address is internal — the preview embed path
  used to skip that half, and the comment there conceded it;
* the connection is pinned to the vetted address, so the name cannot be
  re-resolved to something else between the check and the connect;
* redirects are followed a bounded number of times and every hop is re-vetted,
  because ``http://safe.example -> 169.254.169.254`` is the same attack one hop
  later;
* the body is read in chunks and cut off at a ceiling, so a URL that lies about
  its size cannot exhaust memory;
* the bytes then go through the ordinary ``upload_file`` path, so the magic-byte
  check, the MIME allowlist and the per-category size limit all apply exactly as
  they do to a browser upload. A remote ``.jpg`` that is really a script is
  rejected the same way.
"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import UploadFile

from app.core.exceptions.handlers import ValidationError
from app.core.security.url_guard import validate_pinned_url

#: Ceiling for a fetched remote image. WordPress uses a post-filter size limit;
#: this is the same idea applied before anything is buffered.
MAX_SIDELOAD_BYTES = 10 * 1024 * 1024

#: How many redirects to follow. Each hop is re-vetted, so this is bounded
#: cost rather than an open-ended walk.
MAX_SIDELOAD_REDIRECTS = 3

_FETCH_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

#: Offered when the remote server sends no Content-Type, so ``UploadFile`` has
#: something to name the part with. The magic-byte check still decides.
_FALLBACK_CONTENT_TYPE = "application/octet-stream"


def _filename_from_url(url: str, content_type: str) -> str:
    """A safe, non-empty filename for the fetched body."""
    from urllib.parse import unquote, urlparse

    tail = urlparse(url).path.rsplit("/", 1)[-1]
    tail = unquote(tail).strip()
    if not tail or "." not in tail:
        subtype = (content_type.split("/")[-1] or "bin").split(";")[0].strip()
        tail = f"image.{subtype}" if subtype else "image.bin"
    # _sanitize_filename inside upload_file does the real scrubbing; this only
    # keeps the URL's query string and path separators out of the name.
    return tail[-120:]


async def sideload_image(
    db: Any,
    url: str,
    *,
    uploader_id: uuid.UUID | None = None,
    alt_text: str | None = None,
    folder: str | None = None,
) -> Any:
    """Download ``url`` and store it as a media asset. Returns the asset."""
    from app.modules.media.application.media_service import MediaService

    current = url.strip()
    # `trust_env=False`: this is a server-side fetch on behalf of an operator,
    # and the ambient proxy settings (on this machine, a localhost proxy on
    # 10809) must not silently take over the connection. With trust_env on,
    # httpx read the Windows registry's proxy and every sideload of an
    # ordinary https image died with a DNS error for a host that resolves
    # fine — the fetch never reached the URL guard's vetted address.
    async with httpx.AsyncClient(
        timeout=_FETCH_TIMEOUT, follow_redirects=False, trust_env=False
    ) as client:
        response = None
        for hop in range(MAX_SIDELOAD_REDIRECTS + 1):
            # Re-vet every hop. The first request goes to the pinned address so
            # the name cannot be re-resolved after the check; redirects start
            # from the Location header and go through the same guard.
            connect_url, host = await validate_pinned_url(current, what="نشانی")
            # An https request to an IP literal verifies the certificate
            # against the *IP*, which every real certificate fails
            # (`IP address mismatch`). The `sni_hostname` extension is the
            # documented way to keep SNI and certificate verification on the
            # original hostname while the TCP connection goes to the vetted
            # address — the pinning and the TLS identity check both hold.
            # The Host header carries the port when the URL names a
            # non-default one, exactly as a direct request would.
            parsed_current = urlparse(current)
            host_header = host if parsed_current.port is None else f"{host}:{parsed_current.port}"
            response = await client.get(
                connect_url,
                headers={"Host": host_header, "User-Agent": f"{_UA} (media sideload)"},
                extensions={"sni_hostname": host},
            )
            if response.is_redirect:
                if hop >= MAX_SIDELOAD_REDIRECTS:
                    raise ValidationError(
                        f"بیش از {MAX_SIDELOAD_REDIRECTS} ریدایرکت متوالی به «{current}»"
                    )
                location = response.headers.get("location")
                if not location:
                    raise ValidationError("ریدایرکت بدون مقصد")
                # Joined against the ORIGINAL URL, not the pinned connect
                # URL: a relative Location joined onto the IP literal would
                # make the next hop look like an IP-addressed request, and
                # the hostname (and with it SNI and certificate identity)
                # would be lost after the first redirect.
                current = urljoin(current, location)
                continue
            break

        if response is None:  # pragma: no cover - loop always assigns
            raise ValidationError("پاسخی دریافت نشد")
        if response.status_code >= 400:
            raise ValidationError(
                f"سرور مبدأ کد {response.status_code} برگرداند"
            )

        # Read with a ceiling rather than trusting Content-Length: a server can
        # claim any length it likes, and a chunked response carries none.
        body = await read_capped(response, cap=MAX_SIDELOAD_BYTES)

    if not body:
        raise ValidationError("پاسخ خالی بود")

    content_type = response.headers.get("content-type", _FALLBACK_CONTENT_TYPE)
    name = _filename_from_url(current, content_type)

    # Straight into the ordinary upload path: the magic-byte sniff, the MIME
    # allowlist and the per-category ceiling are all applied to the fetched
    # bytes, so nothing sideloaded can be something a direct upload could not be.
    asset = await MediaService.upload_file(
        db,
        file=UploadFile(filename=name, file=_BytesReader(body), headers=_headers(content_type)),
        uploader_id=uploader_id,
        alt_text=alt_text,
        folder=folder,
    )
    return asset


_CHUNK = 1024 * 256
_UA = "Mozilla/5.0 (compatible; store-media-sideload/1.0)"


async def read_capped(response: Any, *, cap: int = MAX_SIDELOAD_BYTES) -> bytes:
    """Read a streaming response, refusing to buffer past ``cap``.

    Content-Length is not trusted: a server can claim any length, and a
    chunked response carries none. So the ceiling is enforced while reading.

    A standalone function so the bound can be tested directly. An earlier test
    file re-implemented this loop locally and passed no matter what the
    production code did — the copy and the real thing drifted.
    """
    chunks: list[bytes] = []
    running = 0
    async for chunk in response.aiter_bytes(_CHUNK):
        running += len(chunk)
        if running > cap:
            raise ValidationError(
                f"حجم تصویر دوردست بیش از {cap // (1024 * 1024)} مگابایت است"
            )
        chunks.append(chunk)
    return b"".join(chunks)


class _BytesReader:
    """A minimal file object for ``UploadFile``, built from bytes.

    Starlette's ``UploadFile`` wants a spooled file. Building one from bytes
    keeps the sideload on the same validation path as a browser upload instead
    of a second, subtly different one.

    **Sync on purpose.** Starlette decides how to call this object by asking it
    ``getattr(file, "_rolled", True)`` — an object without that attribute is
    treated as already-rolled and its ``read``/``seek`` are called
    *synchronously* (`self.file.read(size)`, no await). The first version of
    this class defined ``async def read``, so that call returned a coroutine,
    the size check did ``len(coroutine)``, and every sideload died with a
    ``TypeError`` — visible only when the fetch succeeded, which is why the
    SNI and proxy bugs above had to be fixed before this one could even
    surface. Declaring ``_rolled = False`` and sync methods is what makes
    Starlette take its in-memory path, exactly as a real spooled file does.
    """

    #: Tells Starlette this object is in memory (the SpooledTemporaryFile
    #: contract). Absence of the attribute reads as rolled=True and switches
    #: Starlette to sync calls — which is the path this class is built for.
    _rolled = False

    def __init__(self, data: bytes) -> None:
        import io

        self._buffer = io.BytesIO(data)

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def seek(self, offset: int) -> None:
        self._buffer.seek(offset)

    def tell(self) -> int:
        return self._buffer.tell()

    def close(self) -> None:
        self._buffer.close()


def _headers(content_type: str) -> Any:
    """A minimal ``Headers`` carrying just the content type."""
    from starlette.datastructures import Headers

    return Headers({"content-type": content_type})
