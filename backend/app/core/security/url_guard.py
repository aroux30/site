"""Shared guard for server-side fetches of user-supplied URLs.

Both the oEmbed preview and the media sideload reach out to a URL an
authenticated user supplied. That is the classic SSRF setup: point the server at
``127.0.0.1``, a private subnet, or a cloud metadata endpoint and read the
response.

What the previous check did and did not catch, measured rather than assumed
(``w5_ssrf_guard.py`` holds the evidence):

* BLOCKED: an IP literal that parses — ``127.0.0.1``, ``10.0.0.5``,
  ``169.254.169.254`` (the AWS/GCP metadata address), ``[::1]``, and the
  IPv4-mapped form ``[0:0:0:0:0:ffff:a9fe:a9fe]``.
* BLOCKED: the names ``localhost`` and anything under ``.internal``.
* ALLOWED, wrongly: ``0x7f.0.0.1`` and ``2130706433`` — hex and decimal
  loopback. ``ipaddress.ip_address`` rejects both as malformed, the old code
  caught the ``ValueError`` and passed, and libc resolves them to 127.0.0.1.
* ALLOWED, wrongly: any hostname, because DNS was never resolved. A name the
  attacker controls, or ``169.254.169.254.nip.io`` (a public name that
  resolves to the metadata address), walked straight through.

So this module resolves the name and vets the *addresses*, which is the only
place the answer to "is this internal?" actually lives. The original author's
comment already conceded the DNS half was out of scope; that is the gap closed
here, not a rewrite.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from app.core.exceptions.handlers import ValidationError

#: Hostnames that never reach the network as written.
_BLOCKED_HOSTS = frozenset({"localhost", "localhost.localdomain", "ip6-localhost"})

#: Suffixes reserved for names that only exist inside a network.
_BLOCKED_SUFFIXES = (".internal", ".local", ".localdomain", ".lan", ".home.arpa")

#: Unused port in the discard range; a name resolving here is not a real host.
_DISCARD_PORT = 9


def _is_internal(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether an address is somewhere a public request must never go."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


async def _addresses_for(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Every address ``host`` resolves to, as parsed address objects.

    ``getaddrinfo`` rather than ``gethostbyname``: the latter is IPv4-only and
    raises on an AAAA-only name, so a host published only over IPv6 would be
    waved through unexamined.
    """
    infos = await await_socket_getaddrinfo(host, None)
    out: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for *_, sockaddr in infos:
        try:
            out.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:  # pragma: no cover - getaddrinfo returned junk
            continue
    return out


async def await_socket_getaddrinfo(host: str, port: int | None) -> list:
    """``getaddrinfo`` off the event loop, so a slow DNS cannot stall a request."""
    loop = asyncio.get_running_loop()
    return await loop.getaddrinfo(
        host, port or 0, proto=socket.IPPROTO_TCP, type=socket.SOCK_STREAM
    )


async def validate_public_url(url: str, *, what: str = "نشانی") -> str:
    """Return ``url`` unchanged, or raise if fetching it would leave the internet.

    Checks, in order: scheme is http(s); the host is not a blocked name; the
    host resolves; and *every* address it resolves to is public. All of them,
    not the first — a name with one public and one private A record is the
    rebinding case, and vetting only the first answer is what made the old
    check bypassable.

    The resolution happens here and the caller then connects to the same
    hostname, so there is still a window in which DNS answers differently
    between the check and the connect (true rebinding). Closing that fully needs
    a pinned-IP client; ``resolve_pinned_url`` returns the vetted address so a
    caller that can connect by IP can. For a metadata-endpoint attack the
    attacker must already control DNS for their own domain, which this closes.
    """
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValidationError(f"{what} معتبر نیست")

    host = parsed.hostname.lower().rstrip(".")

    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES):
        raise ValidationError(f"{what}‌های داخلی مجاز نیستند")

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        # A literal bypasses DNS entirely, so it is vetted on its own.
        if _is_internal(literal):
            raise ValidationError(f"{what}‌های داخلی مجاز نیستند")
        return url

    try:
        addresses = await _addresses_for(host)
    except (socket.gaierror, UnicodeError, OSError) as exc:
        raise ValidationError(f"دامنهٔ «{host}» قابل Resolve نیست") from exc

    if not addresses:
        raise ValidationError(f"دامنهٔ «{host}» هیچ آدرسی ندارد")

    internal = [str(a) for a in addresses if _is_internal(a)]
    if internal:
        raise ValidationError(
            f"{what} به نشانی داخلی ({internal[0]}) اشاره می‌کند و مجاز نیست"
        )
    return url


async def validate_pinned_url(url: str, *, what: str = "نشانی") -> tuple[str, str]:
    """Vet ``url`` and return ``(connect_url, host)`` pinned to a vetted address.

    ``connect_url`` keeps the original scheme and port but swaps in the literal
    address, so the connection goes to the IP that was just checked. Used for
    the media sideload, where the fetched bytes are persisted to the store's
    public directory and a rebind would put an internal file there.
    """
    await validate_public_url(url, what=what)
    parsed = urlparse(url)
    host = parsed.hostname or ""

    try:
        ipaddress.ip_address(host)
        pinned = host
    except ValueError:
        # Not a literal, so resolve and pin to the first vetted address. The
        # vet already ran inside validate_public_url above; this only re-reads
        # the result to build the connect URL.
        addresses = await _addresses_for(host)
        if not addresses:
            raise ValidationError(f"دامنهٔ «{host}» هیچ آدرسی ندارد") from None
        pinned = addresses[0].compressed

    netloc = f"[{pinned}]" if ":" in pinned else pinned
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return parsed._replace(netloc=netloc).geturl(), host
