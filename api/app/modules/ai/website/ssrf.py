from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
    "host.docker.internal",
    "kubernetes.default",
    "kubernetes.default.svc",
    "kubernetes.default.svc.cluster.local",
}

BLOCKED_HOST_SUFFIXES = (
    ".local",
    ".internal",
    ".localhost",
    ".localdomain",
    ".cluster.local",
    ".svc",
    ".home",
    ".lan",
)

BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("2001:db8::/32"),
]


class UnsafeUrlError(ValueError):
    pass


def normalize_product_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        raise UnsafeUrlError("empty")
    if "://" not in text:
        text = "https://" + text
    return text


def parse_public_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("scheme")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("userinfo")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("host")
    host = host.strip(".").lower()
    if not host:
        raise UnsafeUrlError("host")
    if _blocked_hostname(host):
        raise UnsafeUrlError("hostname")
    ip = _as_ip(host)
    if ip is not None:
        ensure_public_ip(ip)
    return parsed.geturl(), host


def _blocked_hostname(host: str) -> bool:
    if host in BLOCKED_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES)


def _as_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def ensure_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise UnsafeUrlError("private_ip")
    for network in BLOCKED_NETWORKS:
        if ip in network:
            raise UnsafeUrlError("private_ip")


async def ensure_public_host(host: str) -> None:
    ip = _as_ip(host)
    if ip is not None:
        ensure_public_ip(ip)
        return
    if _blocked_hostname(host):
        raise UnsafeUrlError("hostname")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError("dns") from exc
    if not infos:
        raise UnsafeUrlError("dns")
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        resolved = _as_ip(sockaddr[0])
        if resolved is None:
            continue
        ensure_public_ip(resolved)
