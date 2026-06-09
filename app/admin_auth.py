"""Admin authentication.

InfusionFox relies on Cloudflare Access (or an equivalent edge SSO) sitting
in front of /admin/* routes. Cloudflare Access sets two headers on
authenticated requests:

  - ``Cf-Access-Authenticated-User-Email``: the user's email
  - ``Cf-Access-Jwt-Assertion``: signed JWT proving Access processed it

For the first cut we trust the email header AND require its value to be
in an env-var allowlist. This is belt-and-suspenders against the
threat of someone bypassing Cloudflare (which would require direct
network access to the container — itself a network compromise). The
JWT verification path is a future hardening if needed.

Environment variables:

  - ``INFUSIONFOX_ADMIN_EMAILS`` (production) — comma-separated allowlist
    of email addresses permitted to access /admin/*. Example:
    ``INFUSIONFOX_ADMIN_EMAILS="tim@example.com,vet@example.com"``

  - ``INFUSIONFOX_ADMIN_OPEN`` (dev/test only) — when set to "1", admin
    routes serve without the header check. A loud warning is logged
    at startup. NEVER set this in production; Cloudflare Access alone
    is not the line of defense — the header check is.

If neither var is set, admin routes return 403 for everyone.
"""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Request

_log = logging.getLogger(__name__)


def _allowlist() -> set[str]:
    raw = os.environ.get("INFUSIONFOX_ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


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
            "protected by the email header check. This is only safe "
            "for local development. Unset this env var in production."
        )


def require_admin(request: Request) -> str:
    """FastAPI dependency: gate admin routes by Cloudflare Access email.

    Returns the authenticated email (lowercased) on success.
    Raises 403 on failure.

    Resolution order:
        1. If ``INFUSIONFOX_ADMIN_OPEN=1``, returns the header value if
           present or "dev-mode" if not (no allowlist check).
        2. If the email header is missing, 403.
        3. If ``INFUSIONFOX_ADMIN_EMAILS`` is set, the header value must
           appear in it. Otherwise 403.
        4. If ``INFUSIONFOX_ADMIN_EMAILS`` is empty (not configured),
           every request 403s. This is the safe default for a fresh
           deployment that hasn't configured an admin yet.
    """
    email_raw = request.headers.get("cf-access-authenticated-user-email", "")
    email = email_raw.strip().lower()

    if _open_mode():
        return email or "dev-mode"

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
