"""Legacy URL redirects.

Pre-migration, every calculator page lived under `/c/<slug>` (the
dispatcher pattern in `calculators.py`) or under `/c/<name>` (for
bespoke calculators that mounted under the same prefix). The migration
to bare paths means `/blood-gas`, `/insulin-cri-dka`, `/norepinephrine`,
etc. are now canonical.

This catch-all 308-redirects any GET or POST to `/c/<anything>` over to
`/<anything>`, preserving method (so HTMX POSTs still work if a stale
client hits the old URL) and query string. Remove this router once
bookmark traffic to `/c/<slug>` has dropped to zero.

The 308 status code (Permanent Redirect, preserves method) is the right
fit here — 301/302 would turn POSTs into GETs and silently break HTMX.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.api_route("/c/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_calc_redirect(path: str, request: Request) -> RedirectResponse:
    target = f"/{path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(target, status_code=308)
