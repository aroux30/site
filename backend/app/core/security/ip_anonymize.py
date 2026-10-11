"""Reduce an IP address to its network, the way WordPress does.

An IP address in an outbound notice (formerly the admin signup email) is personal data
under Article 4(1), and the notice reaches an operator's inbox — a wider
audience than the signup form. The address is masked before it is embedded:
the *network* is kept and the host is dropped — ``/24`` for IPv4, ``/64`` for
IPv6 — rather than blanking the value.

Keeping the network is the point, and so is dropping only the host. An
operator can still tell whether several signups came from one place, but can
no longer read which household a particular signup came from.

The IPv6 half is not optional. ``2001:db8:85a3::8a2e:370:7334`` identifies one
device; its ``/64`` is the address block an ISP hands to one customer, and under
the same argument that protects a household it protects that customer too. A
store that anonymizes ``203.0.113.47`` to ``203.0.113.0`` and leaves a v6 address
intact has anonymized only the easier half of its users.

Portability note: ``inet_pton``/``inet_ntop`` exist on every platform this
project runs, so the ``/64`` mask is a real subnet computation and not a string
truncation. The fallback returns the unspecified address rather than the original,
which is the conservative direction: an address that cannot be masked is lost,
it is never kept.
"""

from __future__ import annotations

import ipaddress

#: Returned for an address that cannot be parsed, rather than the input. WordPress
#: does the same for its two malformed cases and returns ``0.0.0.0``/``::``.
UNSPECIFIED_V4 = "0.0.0.0"
UNSPECIFIED_V6 = "::"

#: WordPress masks an IPv4 to its /24 (last octet zeroed) and an IPv6 to its /64.
#: Those are the two prefix lengths WordPress uses and the two this project keeps,
#: so an address masked here and one masked there are comparable.
V4_PREFIX_LEN = 24
V6_PREFIX_LEN = 64


def anonymize_ip(ip_addr: str | None) -> str:
    """Return the network ``ip_addr`` belongs to, with the host part removed.

    Returns ``0.0.0.0`` for empty input, matching WordPress, so a column that
    was never populated becomes the same value a caller would write for one it
    could not parse — a comment's address is either a masked network or the
    unspecified address, never an address.

    Handles the three shapes that reach this function in practice: a bare address,
    an address with a port (``1.2.3.4:5678``), and an IPv6 address with brackets
    and a zone index (``[2001:db8::1]:443``, ``fe80::1%eth0``). WordPress strips
    the port and the reachability scope for exactly these reasons.
    """
    if not ip_addr:
        return UNSPECIFIED_V4

    candidate = ip_addr.strip()
    if not candidate:
        return UNSPECIFIED_V4

    # A bracketed v6 address carries its port inside the brackets, and a bare one
    # may carry it after the address. Strip both before parsing, or `ipaddress`
    # rejects a string that is a perfectly good address.
    candidate = _strip_port(candidate)

    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return UNSPECIFIED_V4

    if parsed.version == 4:
        return _network_address(parsed)

    # A v4-mapped v6 address (``::ffff:203.0.113.47``) is what arrives when a v6
    # socket receives a v4 client. Masking it as v6 would emit a v6 network and
    # compare unequal to the plain form that arrives over v4, so one visitor
    # would look like two people. WordPress collapses these to v4 for the same
    # reason. `ipv4_mapped` only exists on IPv6Address, hence the isinstance
    # rather than an attribute test.
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        return _network_address(parsed.ipv4_mapped)

    return _network_address(parsed)


def _network_address(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """The masked address as a bare string, not CIDR.

    WordPress writes ``203.0.113.0`` and ``2001:db8::`` — no ``/24``, no ``/64`` —
    and this column has to compare equal to a row WordPress itself produced. The
    prefix length is a property of the column (see V4_PREFIX_LEN/V6_PREFIX_LEN),
    not something the stored value has to repeat.
    """
    prefix = V4_PREFIX_LEN if addr.version == 4 else V6_PREFIX_LEN
    return str(ipaddress.ip_network(f"{addr}/{prefix}", strict=False).network_address)


def _strip_port(candidate: str) -> str:
    """Remove a trailing port, brackets and a zone index from an address.

    Split on the last colon only for v4, where the address has no colons of its
    own; for v6 the colons belong to the address and a trailing ``:1234`` cannot
    be told apart from one by position, so it is left to the parser, which
    handles it.
    """
    if candidate.startswith("["):
        # ``[2001:db8::1]:443`` -> ``2001:db8::1``; a lone bracket is malformed
        # and is passed on unchanged so the parse fails rather than half-succeed.
        close = candidate.find("]")
        if close > 0:
            return candidate[1:close]
        return candidate

    if candidate.count(":") == 1:
        # ``1.2.3.4:5678`` -> ``1.2.3.4``. Safe because a v4 address has no
        # colons; anything with two or more is v6 and is parsed whole.
        return candidate.rsplit(":", 1)[0]

    # ``fe80::1%eth0`` -> ``fe80::1``. The zone names an interface on the
    # machine that stored the address, which identifies nothing once it is
    # elsewhere, and ``ipaddress`` rejects the percent form outright.
    percent = candidate.find("%")
    if percent > 0:
        candidate = candidate[:percent]

    return candidate