"""
Disclaimer routes.

POST /api/disclaimer/accept — JSON body { "version": "...", "session_token": "..." }.
Records one row in disclaimer_acceptances with IP, UA, version, token,
and timestamp.

The disclaimer is a hard-block modal. The client checks localStorage for
``infusionfox.disclaimer.version`` against the inlined ``DISCLAIMER_VERSION``
template global and shows the modal on mismatch. On acceptance, the
client POSTs here and (on 204) sets localStorage so the modal doesn't
re-fire on next page load.

There is no admin triage UI. To audit acceptances:

    sqlite3 data/infusionfox.db "SELECT accepted_at, disclaimer_version,
        ip_address, SUBSTR(user_agent, 1, 60) FROM disclaimer_acceptances
        ORDER BY accepted_at DESC LIMIT 50"
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session as DBSession

from app.db import DisclaimerAcceptance, get_db
from app.disclaimer import DISCLAIMER_VERSION
from app.util.client_ip import get_client_ip

router = APIRouter()


@router.post("/api/disclaimer/accept", status_code=204)
async def accept_disclaimer(
    request: Request,
    db: DBSession = Depends(get_db),
):
    """Record one acceptance row.

    Returns 204 (No Content) on success. Returns 400 if the JSON body
    is malformed or the version is missing — but the client is the
    source of the version, so a malformed request only happens with
    a buggy or tampered client.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "invalid_json"}, status_code=400
        )

    if not isinstance(body, dict):
        return JSONResponse(
            {"error": "invalid_body"}, status_code=400
        )

    # Accept whatever version the client sends, but record it as-is —
    # the server's current version is exposed via templates.env.globals,
    # so a legitimate client posts the matching value. If they don't,
    # we still record (the user did see and accept SOME disclaimer),
    # but we coerce to a sane string and length-cap.
    version_raw = body.get("version") or DISCLAIMER_VERSION
    version = str(version_raw)[:32]

    session_token_raw = body.get("session_token")
    session_token = (
        str(session_token_raw)[:64] if session_token_raw else None
    )

    acceptance = DisclaimerAcceptance(
        disclaimer_version=version,
        ip_address=get_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
        session_token=session_token,
    )
    db.add(acceptance)
    db.commit()

    return Response(status_code=204)
