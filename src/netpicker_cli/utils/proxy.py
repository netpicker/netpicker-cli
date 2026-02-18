"""
CIDR-aware no_proxy / NO_PROXY handling for httpx.

httpx (and httpcore) only support exact hostnames, IP addresses, and domain
suffixes in the ``no_proxy`` environment variable.  CIDR notation such as
``10.0.0.0/8`` is silently ignored, which causes requests to private hosts
to be incorrectly routed through the proxy.

This module resolves that by:
1. Parsing ``no_proxy`` / ``NO_PROXY`` entries that contain CIDR blocks.
2. Resolving the target hostname to an IP address.
3. Returning the appropriate ``proxy`` argument to pass to ``httpx.Client``
   so that the proxy is explicitly bypassed when the target falls inside a
   listed CIDR range.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

from ..utils.logging import get_logger

logger = get_logger(__name__)


def _get_no_proxy_entries() -> list[str]:
    """Return the comma-separated entries from ``no_proxy`` or ``NO_PROXY``."""
    raw = os.environ.get("no_proxy") or os.environ.get("NO_PROXY") or ""
    return [e.strip() for e in raw.split(",") if e.strip()]


def _parse_cidr_networks(entries: list[str]) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Extract valid CIDR network objects from no_proxy entries."""
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in entries:
        # Only attempt to parse entries that look like CIDR notation
        if "/" in entry:
            try:
                networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                # Not a valid CIDR – leave it for httpx to handle as a hostname pattern
                pass
    return networks


def _parse_plain_ips(entries: list[str]) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Extract plain IP addresses (no CIDR) from no_proxy entries."""
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for entry in entries:
        if "/" not in entry:
            try:
                ips.append(ipaddress.ip_address(entry))
            except ValueError:
                pass  # hostname – handled natively by httpx
    return ips


@lru_cache(maxsize=64)
def _resolve_host(hostname: str) -> Optional[str]:
    """Resolve *hostname* to an IP address string, or ``None`` on failure."""
    try:
        return socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)[0][4][0]
    except (socket.gaierror, OSError, IndexError):
        return None


def _host_from_url(url: str) -> str:
    """Extract the hostname from *url*, stripping port if present."""
    parsed = urlparse(url)
    host = parsed.hostname or parsed.path
    # urlparse may return None for unusual inputs; fall back to raw string
    return host or url


def should_bypass_proxy(base_url: str) -> bool:
    """
    Return ``True`` if *base_url*'s host matches any CIDR or IP entry in
    ``no_proxy`` / ``NO_PROXY`` that httpx would otherwise ignore.

    This does **not** re-check plain hostname/domain-suffix entries – httpx
    already handles those correctly.
    """
    entries = _get_no_proxy_entries()
    if not entries:
        return False

    # Check for wildcard
    if "*" in entries:
        return True

    networks = _parse_cidr_networks(entries)
    plain_ips = _parse_plain_ips(entries)

    # If there are no CIDR networks and no plain IPs to check, let httpx
    # handle it natively (hostnames, domain suffixes, etc.)
    if not networks and not plain_ips:
        return False

    hostname = _host_from_url(base_url)

    # Try to interpret the hostname directly as an IP
    target_ip: Optional[ipaddress.IPv4Address | ipaddress.IPv6Address] = None
    try:
        target_ip = ipaddress.ip_address(hostname)
    except ValueError:
        # It's a DNS name – resolve it
        resolved = _resolve_host(hostname)
        if resolved:
            try:
                target_ip = ipaddress.ip_address(resolved)
            except ValueError:
                pass

    if target_ip is None:
        logger.debug("Could not resolve %s to an IP; skipping CIDR proxy-bypass check", hostname)
        return False

    # Check plain IP matches
    if target_ip in plain_ips:
        logger.debug("Host %s (%s) matches plain IP in no_proxy", hostname, target_ip)
        return True

    # Check CIDR matches
    for net in networks:
        if target_ip in net:
            logger.debug(
                "Host %s (%s) is inside no_proxy CIDR %s – bypassing proxy",
                hostname,
                target_ip,
                net,
            )
            return True

    return False


def proxy_arg_for(base_url: str) -> Optional[str]:
    """
    Return the ``proxy`` keyword argument to pass to ``httpx.Client``.

    * ``None`` → let httpx use its default env-var proxy detection.
    * ``""``   → explicitly disable the proxy for this client (empty string
      is not valid; we return a sentinel that the caller interprets).

    In practice the caller should do::

        bypass = should_bypass_proxy(base_url)
        client = httpx.Client(..., proxy=None if not bypass else ...)
    """
    # This is a convenience wrapper; callers can also use should_bypass_proxy
    # directly for clarity.
    return None
