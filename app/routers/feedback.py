"""
Feedback routes.

POST /feedback — anyone can submit. Anonymous; optional contact_email.

There is no admin triage UI in the app. Read the feedback table
directly with sqlite3 when triaging:

    sqlite3 data/infusionfox.db "SELECT id, kind, created_at, page_url,
        SUBSTR(message, 1, 80) FROM feedback ORDER BY created_at DESC LIMIT 50"
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session as DBSession

from app.db import Feedback, FeedbackKind, get_db
from app.util.client_ip import get_client_ip as _client_ip

router = APIRouter()


@router.post("/feedback", response_class=HTMLResponse)
async def submit_feedback(
    request: Request,
    message: str = Form(...),
    kind: str = Form("other"),
    page_url: str = Form(""),
    contact_email: str = Form(""),
    db: DBSession = Depends(get_db),
):
    """Accept feedback. Returns a small confirmation partial suitable for
    HTMX swap into the feedback button's popover."""
    templates = request.app.state.templates

    message = message.strip()
    if not message:
        return templates.TemplateResponse(
            "partials/feedback_result.html",
            {"request": request, "ok": False, "error": "Please enter a message."},
        )
    if len(message) > 5000:
        message = message[:5000]

    try:
        kind_enum = FeedbackKind(kind)
    except ValueError:
        kind_enum = FeedbackKind.OTHER

    fb = Feedback(
        page_url=(page_url or request.headers.get("referer", ""))[:500] or None,
        kind=kind_enum,
        message=message,
        contact_email=contact_email.strip() or None,
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
        ip_address=_client_ip(request),
    )
    db.add(fb)
    db.commit()

    return templates.TemplateResponse(
        "partials/feedback_result.html",
        {
            "request": request,
            "ok": True,
            "is_dose_concern": kind_enum == FeedbackKind.DOSE_CONCERN,
        },
    )
