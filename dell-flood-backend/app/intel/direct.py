"""Direct HTTP reads Aegis makes itself (RSS/CAP, IMD API). Every hop is SSRF-checked."""
from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.intel.sources import Resolver, default_resolver, is_public_ip, url_rejection

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3


class DirectFetchError(Exception):
    def __init__(self, message: str, *, timeout: bool = False):
        super().__init__(message)
        self.timeout = timeout


def peer_rejection(response: httpx.Response, allowlisted_domain: bool = False) -> str | None:
    """Why the address this response actually came from is unsafe, or None.

    url_rejection resolves DNS before connecting; the name can re-resolve to a
    private address by connect time, so the connected peer is checked as well.
    """
    try:
        stream = response.extensions.get("network_stream")
        peer = stream.get_extra_info("server_addr") if stream is not None else None
    except Exception:
        peer = None
    if not peer:
        return None if allowlisted_domain else "unverifiable"
    try:
        if is_public_ip(str(peer[0])):
            return None
        if allowlisted_domain:
            return None
        return "private_address"
    except (ValueError, OSError):
        return None if allowlisted_domain else "unverifiable"


def safe_get(
    http: httpx.Client,
    url: str,
    domains: tuple[str, ...],
    *,
    resolver: Resolver = default_resolver,
    headers: dict[str, str] | None = None,
) -> tuple[str, str]:
    """GET `url`, following at most MAX_REDIRECTS redirects, each re-checked against the allowlist.

    Returns (final_url, text). Raises DirectFetchError on any rejection or failure.
    """
    current = url
    origin = httpx.URL(url).host
    for _ in range(MAX_REDIRECTS + 1):
        problem = url_rejection(current, domains, resolver)
        if problem:
            raise DirectFetchError(f"url rejected: {problem}")
        hop = httpx.URL(current)
        credentialed = hop.scheme == "https" and hop.host == origin
        try:
            with http.stream("GET", current, headers=headers if credentialed else None,
                             follow_redirects=False) as response:
                peer_problem = peer_rejection(response, allowlisted_domain=True)
                if peer_problem:
                    raise DirectFetchError(f"peer rejected: {peer_problem}")
                if response.is_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        raise DirectFetchError("redirect without location")
                    current = urljoin(current, location)
                    continue
                if response.status_code >= 400:
                    raise DirectFetchError(f"HTTP {response.status_code}")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise DirectFetchError("response too large")
                    chunks.append(chunk)
                body = b"".join(chunks)
                return current, body.decode(response.encoding or "utf-8", errors="replace")
        except httpx.TimeoutException:
            raise DirectFetchError("timeout", timeout=True) from None
        except httpx.TransportError as exc:
            raise DirectFetchError(f"transport error: {type(exc).__name__}") from None
    raise DirectFetchError("too many redirects")
