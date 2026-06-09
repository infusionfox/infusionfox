"""Client IP extraction.

InfusionFox is deployed behind Cloudflare Tunnel, which means:
- Direct ``request.client.host`` is the local tunnel daemon address
  (usually 127.0.0.1), NOT the user's actual IP.
- Cloudflare sets ``CF-Connecting-IP`` with the original client IP.
- ``X-Forwarded-For`` is also set, but may contain multiple values
  (proxy chain); the leftmost value is the original client.

In other deployments (no Cloudflare in front) we still want to honor
``X-Forwarded-For`` if present (other reverse proxies set it) and
fall back to ``request.client.host`` as a last resort.

Returns ``None`` if no IP can be determined (e.g. test client with
no host set).
"""

from __future__ import annotations

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """Extract the originating client IP, honoring proxy headers.

    Priority:
        1. ``CF-Connecting-IP`` (Cloudflare Tunnel — production)
        2. ``X-Forwarded-For`` leftmost value (other reverse proxies)
        3. ``request.client.host`` (direct connection)
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    xff = request.headers.get("x-forwarded-for")
    if xff:
        # XFF is "client, proxy1, proxy2"; leftmost is the original client
        return xff.split(",")[0].strip()

    return request.client.host if request.client else None
