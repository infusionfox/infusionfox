"""Admin authentication.

InfusionFox relies on Cloudflare Access (or an equivalent edge SSO) sitting
in front of /admin/* routes. Cloudflare Access sets two headers on
authenticated requests:

  - ``Cf-Access-Authenticated-User-Email``: the user's email
  - ``Cf-Access-Jwt-Assertion``: signed JWT proving Access processed it

For the first cut we trust the email header AND require its value to be
in an env-var allowlist. This is belt-and-suspenders against the
threat of someone bypassing Cloudflare (which would require direct
network access to the container, itself a network compromise). The
JWT verification path is a future hardening if needed.

Environment variables:

  - ``INFUSIONFOX_ADMIN_EMAILS`` (production) — comma-separated allowlist
    of email addresses permitted to access /admin/* via Cloudflare Access.
    Example: ``INFUSIONFOX_ADMIN_EMAILS="tim@example.com,vet@example.com"``

  - ``INFUSIONFOX_ADMIN_TRUSTED_NETWORKS`` (optional) — comma-separated
    CIDR ranges that are allowed direct access to /admin/* without
    Cloudflare Access. Only applies when the request did NOT come through
    Cloudflare (no Cf-Connecting-IP header). Example for LAN + Tailscale:
    ``INFUSIONFOX_ADMIN_TRUSTED_NETWORKS="192.168.25.0/24,100.64.0.0/10"``

  - ``INFUSIONFOX_ADMIN_OPEN`` (dev/test only) — when set to "1", admin
    routes serve without any check. A loud warning is logged at startup.
    NEVER set this in production.

If none of these are configured, admin routes return 403 for everyone.
"""

from __future__ import annotations

import ipaddress
import logging
import os

from fastapi import HTTPException, Request

_log = logging.getLogger(__name__)


def _allowlist() -> set[str]:
    raw = os.environ.get("INFUSIONFOX_ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    raw = os.environ.get("INFUSIONFOX_ADMIN_TRUSTED_NETWORKS", "")
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            _log.warning(
                "INFUSIONFOX_ADMIN_TRUSTED_NETWORKS: invalid CIDR %r, skipping",
                entry,
            )
    return networks


def _open_mode() -> bool:
    return os.environ.get("INFUSIONFOX_ADMIN_OPEN", "").strip() == "1"


def warn_if_open_mode() -> None:
    """Call at app startup to log a warning if open mode is enabled.

    Open mode is a development convenience — it lets you hit /admin/
    locally without Cloudflare Access configured. In production this
    should never be on; the startup warning is a backstop in case
    someone forgets to unset it.
    """
    if _open_mode():
        _log.warning(
            "INFUSIONFOX_ADMIN_OPEN=1 is set — admin routes are NOT "
            "protected. This is only safe for local development. "
            "Unset this env var in production."
        )


def _ip_in_trusted_network(ip_str: str) -> bool:
    if not ip_str:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in _trusted_networks())


def require_admin(request: Request) -> str:
    """FastAPI dependency: gate admin routes.

    Returns the resolved identity (lowercased email, or a
    ``trusted-network:<ip>`` marker) on success. Raises 403 on failure.

    Resolution order:
        1. If ``INFUSIONFOX_ADMIN_OPEN=1``, allow everything.
        2. If the request is NOT from Cloudflare (no Cf-Connecting-IP
           header) and the client IP is in INFUSIONFOX_ADMIN_TRUSTED_NETWORKS,
           allow. This is the LAN/Tailscale bypass.
        3. Otherwise, require the Cloudflare Access email header AND
           require its value to be in INFUSIONFOX_ADMIN_EMAILS.
        4. If neither config is set, every request 403s.
    """
    if _open_mode():
        email_raw = request.headers.get("cf-access-authenticated-user-email", "")
        return email_raw.strip().lower() or "dev-mode"

    # Trusted-network bypass. Only applies when the request did not come
    # through Cloudflare — we use the presence of the Cf-Connecting-IP
    # header as the signal (Cloudflare always sets it, and strips any
    # client-supplied value, so it can't be spoofed by external attackers).
    from_cloudflare = bool(request.headers.get("cf-connecting-ip"))
    if not from_cloudflare:
        client_ip = request.client.host if request.client else ""
        if _ip_in_trusted_network(client_ip):
            return f"trusted-network:{client_ip}"

    email_raw = request.headers.get("cf-access-authenticated-user-email", "")
    email = email_raw.strip().lower()

    if not email:
        raise HTTPException(
            status_code=403,
            detail="Admin access requires authentication via Cloudflare Access.",
        )

    allowed = _allowlist()
    if not allowed:
        # No allowlist configured. Refuse everyone — even authenticated
        # Access users — until an admin email is explicitly configured.
        raise HTTPException(
            status_code=403,
            detail=(
                "No admin emails are configured for this deployment. "
                "Set INFUSIONFOX_ADMIN_EMAILS to enable admin access."
            ),
        )

    if email not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Email {email_raw!r} is not authorized for admin access.",
        )

    return email
