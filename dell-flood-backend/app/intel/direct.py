"""Direct HTTP reads Aegis makes itself (RSS/CAP, IMD API). Every hop is SSRF-checked."""
from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.intel.sources import Resolver, default_resolver, url_rejection

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3


class DirectFetchError(Exception):
    def __init__(self, message: str, *, timeout: bool = False):
        super().__init__(message)
        self.timeout = timeout


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
