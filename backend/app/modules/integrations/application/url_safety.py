"""Outbound URL safety for webhook delivery.

A webhook endpoint URL is operator-supplied data, and the delivery worker
fetches it from inside the cluster. Without a check, an operator (or anyone
who reaches the endpoint-create API) can point a webhook at the metadata
service, at loopback, or at another container's admin port, and the worker
will faithfully POST the payload there — classic SSRF.

Two layers, because either one alone is insufficient:

- ``validate_public_url`` runs at the API edge, when an endpoint is created
  or edited, so a bad URL is rejected while the operator is present to see
  the error. It resolves the hostname and inspects every answer.
- ``resolve_pinned_ip`` runs again immediately before each delivery. The
  first check cannot be trusted at delivery time: between "URL saved
  yesterday" and "request sent today" DNS can be re-pointed at an internal
  address (DNS rebinding), so the address that will actually be connected to
  is what must be checked.

Both refuse private, loopback, link-local, reserved, multicast and
unspecified addresses, and refuse non-HTTP(S) schemes and non-standard
ports. IPv4-mapped IPv6 (``::ffff:10.0.0.1``) is unwrapped first — the
``ipaddress`` module would otherwise see a global-looking v6 address and
wave through an internal v4 one.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.exceptions.handlers import ValidationError

#: Ports a webhook may target. Anything else (SSH, Postgres, Redis, the
#: Docker socket's TCP shim) is an internal service, not a webhook receiver.
ALLOWED_PORTS: frozenset[int] = frozenset({80, 443, 8080, 8443})
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

#: Set of networks no outbound delivery may reach. Listed explicitly rather
#: than relying on ``is_private`` alone so the intent survives a Python
#: upgrade that changes classification.
_BLOCKED_V4 = (
    ipaddress.ip_network("0.0.0.0/8"),  # "this network"
    ipaddress.ip_network("10.0.0.0/8"),  # RFC1918
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("169.254.0.0/16"),  # link-local incl. 169.254.169.254 metadata
    ipaddress.ip_network("172.16.0.0/12"),  # RFC1918
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.ip_network("192.88.99.0/24"),  # 6to4 relay anycast
    ipaddress.ip_network("192.168.0.0/16"),  # RFC1918
    ipaddress.ip_network("198.18.0.0/15"),  # benchmarking
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),  # multicast
    ipaddress.ip_network("240.0.0.0/4"),  # reserved / broadcast
)
_BLOCKED_V6 = (
    ipaddress.ip_network("::/128"),  # unspecified
    ipaddress.ip_network("::1/128"),  # loopback
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped (unwrapped before use)
    ipaddress.ip_network("64:ff9b::/96"),  # IPv4/IPv6 translation
    ipaddress.ip_network("100::/64"),  # discard-only
    ipaddress.ip_network("2001:db8::/32"),  # documentation
    ipaddress.ip_network("fc00::/7"),  # unique local
    ipaddress.ip_network("fe80::/10"),  # link-local
    ipaddress.ip_network("ff00::/8"),  # multicast
)

_MSG_BLOCKED = "نشانی وب‌هوک به یک شبکه داخلی یا رزرو‌شده اشاره می‌کند و مجاز نیست"


def _unwrap(addr: ipaddress.IPv4Address | ipaddress.IPv6Address):  # type: ignore[no-untyped-def]
    """Collapse an IPv4-mapped IPv6 address to the IPv4 address it wraps.

    ``::ffff:10.0.0.1`` must be judged as ``10.0.0.1``; checking the v6 form
    against the v6 table would find it "not blocked" and pass it through.
    """
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def _is_blocked(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    addr = _unwrap(addr)
    table = _BLOCKED_V4 if addr.version == 4 else _BLOCKED_V6
    return any(addr in net for net in table)


def _parse(url: str) -> tuple[str, str, int]:
    """Return (scheme, host, port), rejecting anything malformed or odd."""
    try:
        parts = urlsplit(url.strip())
    except ValueError as exc:  # e.g. a bad IPv6 literal
        raise ValidationError("نشانی وب‌هوک قابل تجزیه نیست") from exc

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValidationError("نشانی وب‌هوک باید با http یا https شروع شود")
    host = parts.hostname
    if not host:
        raise ValidationError("نشانی وب‌هوک نام میزبان ندارد")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValidationError("پورت وب‌هوک معتبر نیست") from exc
    # urlsplit leaves the default port implicit; normalise it so the allow
    # list below is a single, complete check.
    if port is None:
        port = 443 if scheme == "https" else 80
    if port not in ALLOWED_PORTS:
        raise ValidationError(f"پورت {port} برای وب‌هوک مجاز نیست (۸۰، ۴۴۳، ۸۰۸۰، ۸۴۳۳)")
    return scheme, host, port


def validate_public_url(url: str) -> str:
    """Validate a webhook URL at the API edge; return it unchanged if safe.

    Resolution happens here so the operator gets an immediate, specific error
    instead of a webhook that fails silently on first delivery.
    """
    _scheme, host, _port = _parse(url)

    # A bare IP literal needs no lookup — judge it directly.
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _is_blocked(literal):
            raise ValidationError(_MSG_BLOCKED)
        return url

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValidationError("نام میزبان وب‌هوک قابل تشخیص نیست (DNS)") from exc

    if not infos:
        raise ValidationError("نام میزبان وب‌هوک به هیچ نشانی تبدیل نشد")

    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if _is_blocked(addr):
            raise ValidationError(_MSG_BLOCKED)
    return url


def resolve_pinned_ip(host: str) -> str:
    """Resolve ``host`` again at delivery time and return one vetted IP.

    Re-checking here (not only at save time) is what closes DNS rebinding: a
    hostname that resolved to a public address when the endpoint was saved
    may resolve to ``127.0.0.1`` when the delivery fires. The returned address
    is the one the caller should connect to, so there is no second resolution
    for an attacker to race.
    """
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _is_blocked(literal):
            raise ValidationError(_MSG_BLOCKED)
        return str(literal)

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValidationError("نام میزبان وب‌هوک قابل تشخیص نیست (DNS)") from exc

    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not _is_blocked(addr):
            return str(addr)
    raise ValidationError(_MSG_BLOCKED)
