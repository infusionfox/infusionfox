"""Admin dashboard.

Routes are all gated by ``require_admin`` (Cloudflare Access email
header + allowlist). No authentication is implemented in the app
itself; Cloudflare Access does the heavy lifting and the header check
is belt-and-suspenders defense.

Routes:

  GET  /admin/                                    dashboard
  GET  /admin/disclaimer-acceptances              paginated list
  GET  /admin/disclaimer-acceptances/export.csv   CSV export
  GET  /admin/feedback                            paginated list
  GET  /admin/feedback/{id}                       detail view
  POST /admin/feedback/{id}/status                update status
  GET  /admin/feedback/export.csv                 CSV export

Deployment:

  1. Configure Cloudflare Access on the infusionfox.com zone to require
     authentication for the /admin/* path. Allow only specific emails.
  2. Set ``INFUSIONFOX_ADMIN_EMAILS`` env var in the container to the
     same allowlist (belt-and-suspenders).
  3. Visit https://infusionfox.com/admin/ in the browser.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from app.admin_auth import require_admin
from app.db import (
    DisclaimerAcceptance,
    Feedback,
    FeedbackKind,
    FeedbackStatus,
    get_db,
)

_log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _ago(days: int) -> datetime:
    return _utcnow_naive() - timedelta(days=days)


def _paginate(
    page: int, per_page: int, total: int
) -> tuple[int, int, int, int]:
    """Return (page, per_page, offset, total_pages) clamped to legal range."""
    per_page = max(1, min(per_page, 200))
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    return page, per_page, offset, total_pages


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/admin/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: DBSession = Depends(get_db),
    _admin_email: str = Depends(require_admin),
):
    """Summary metrics + recent activity preview."""
    templates = request.app.state.templates

    # Disclaimer counts
    da_total = db.execute(
        select(func.count(DisclaimerAcceptance.id))
    ).scalar() or 0
    da_24h = db.execute(
        select(func.count(DisclaimerAcceptance.id)).where(
            DisclaimerAcceptance.accepted_at >= _ago(1)
        )
    ).scalar() or 0
    da_7d = db.execute(
        select(func.count(DisclaimerAcceptance.id)).where(
            DisclaimerAcceptance.accepted_at >= _ago(7)
        )
    ).scalar() or 0
    da_30d = db.execute(
        select(func.count(DisclaimerAcceptance.id)).where(
            DisclaimerAcceptance.accepted_at >= _ago(30)
        )
    ).scalar() or 0

    # Unique IPs in last 30 days — proxy for distinct users
    da_unique_ips_30d = db.execute(
        select(func.count(func.distinct(DisclaimerAcceptance.ip_address))).where(
            DisclaimerAcceptance.accepted_at >= _ago(30),
            DisclaimerAcceptance.ip_address.is_not(None),
        )
    ).scalar() or 0

    # Acceptances grouped by version
    da_by_version_rows = db.execute(
        select(
            DisclaimerAcceptance.disclaimer_version,
            func.count(DisclaimerAcceptance.id),
        )
        .group_by(DisclaimerAcceptance.disclaimer_version)
        .order_by(DisclaimerAcceptance.disclaimer_version.desc())
    ).all()
    da_by_version = [{"version": v, "count": c} for v, c in da_by_version_rows]

    # Feedback counts
    fb_total = db.execute(select(func.count(Feedback.id))).scalar() or 0
    fb_new = db.execute(
        select(func.count(Feedback.id)).where(
            Feedback.status == FeedbackStatus.NEW
        )
    ).scalar() or 0
    fb_dose_concern_new = db.execute(
        select(func.count(Feedback.id)).where(
            Feedback.status == FeedbackStatus.NEW,
            Feedback.kind == FeedbackKind.DOSE_CONCERN,
        )
    ).scalar() or 0

    # Feedback by kind (lifetime)
    fb_by_kind_rows = db.execute(
        select(Feedback.kind, func.count(Feedback.id))
        .group_by(Feedback.kind)
    ).all()
    fb_by_kind = sorted(
        ({"kind": k.value, "count": c} for k, c in fb_by_kind_rows),
        key=lambda r: -r["count"],
    )

    # Recent activity previews (5 each)
    recent_da = db.execute(
        select(DisclaimerAcceptance)
        .order_by(DisclaimerAcceptance.accepted_at.desc())
        .limit(5)
    ).scalars().all()
    recent_fb = db.execute(
        select(Feedback)
        .order_by(Feedback.created_at.desc())
        .limit(5)
    ).scalars().all()

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "admin_email": _admin_email,
            "da_total": da_total,
            "da_24h": da_24h,
            "da_7d": da_7d,
            "da_30d": da_30d,
            "da_unique_ips_30d": da_unique_ips_30d,
            "da_by_version": da_by_version,
            "fb_total": fb_total,
            "fb_new": fb_new,
            "fb_dose_concern_new": fb_dose_concern_new,
            "fb_by_kind": fb_by_kind,
            "recent_da": recent_da,
            "recent_fb": recent_fb,
        },
    )


# ---------------------------------------------------------------------------
# Disclaimer acceptances
# ---------------------------------------------------------------------------


@router.get(
    "/admin/disclaimer-acceptances", response_class=HTMLResponse
)
async def list_disclaimer_acceptances(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    db: DBSession = Depends(get_db),
    _admin_email: str = Depends(require_admin),
):
    templates = request.app.state.templates

    total = db.execute(
        select(func.count(DisclaimerAcceptance.id))
    ).scalar() or 0
    page, per_page, offset, total_pages = _paginate(page, per_page, total)

    rows = db.execute(
        select(DisclaimerAcceptance)
        .order_by(DisclaimerAcceptance.accepted_at.desc())
        .offset(offset)
        .limit(per_page)
    ).scalars().all()

    return templates.TemplateResponse(
        "admin/disclaimer_acceptances.html",
        {
            "request": request,
            "admin_email": _admin_email,
            "rows": rows,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    )


def _stream_disclaimer_csv(
    db: DBSession,
) -> Generator[str, None, None]:
    """Generator yielding CSV lines for disclaimer acceptances.

    Streams in batches of 500 to keep memory bounded on large tables.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id",
        "accepted_at_utc",
        "disclaimer_version",
        "ip_address",
        "user_agent",
        "session_token",
    ])
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)

    batch_size = 500
    offset = 0
    while True:
        rows = db.execute(
            select(DisclaimerAcceptance)
            .order_by(DisclaimerAcceptance.id)
            .offset(offset)
            .limit(batch_size)
        ).scalars().all()
        if not rows:
            break
        for r in rows:
            writer.writerow([
                r.id,
                r.accepted_at.isoformat() if r.accepted_at else "",
                r.disclaimer_version or "",
                r.ip_address or "",
                r.user_agent or "",
                r.session_token or "",
            ])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        offset += batch_size


@router.get("/admin/disclaimer-acceptances/export.csv")
async def export_disclaimer_acceptances_csv(
    db: DBSession = Depends(get_db),
    _admin_email: str = Depends(require_admin),
):
    filename = (
        f"infusionfox-disclaimer-acceptances-{datetime.now(UTC).strftime('%Y%m%d')}.csv"
    )
    return StreamingResponse(
        _stream_disclaimer_csv(db),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


@router.get("/admin/feedback", response_class=HTMLResponse)
async def list_feedback(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    status: str = "all",
    kind: str = "all",
    db: DBSession = Depends(get_db),
    _admin_email: str = Depends(require_admin),
):
    """Paginated feedback list with optional status/kind filters."""
    templates = request.app.state.templates

    base_q = select(Feedback)
    count_q = select(func.count(Feedback.id))

    status_filter = None
    if status != "all":
        try:
            status_filter = FeedbackStatus(status)
            base_q = base_q.where(Feedback.status == status_filter)
            count_q = count_q.where(Feedback.status == status_filter)
        except ValueError:
            pass

    kind_filter = None
    if kind != "all":
        try:
            kind_filter = FeedbackKind(kind)
            base_q = base_q.where(Feedback.kind == kind_filter)
            count_q = count_q.where(Feedback.kind == kind_filter)
        except ValueError:
            pass

    total = db.execute(count_q).scalar() or 0
    page, per_page, offset, total_pages = _paginate(page, per_page, total)

    rows = db.execute(
        base_q
        .order_by(Feedback.created_at.desc())
        .offset(offset)
        .limit(per_page)
    ).scalars().all()

    return templates.TemplateResponse(
        "admin/feedback_list.html",
        {
            "request": request,
            "admin_email": _admin_email,
            "rows": rows,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "status_filter": status,
            "kind_filter": kind,
            "all_statuses": [s.value for s in FeedbackStatus],
            "all_kinds": [k.value for k in FeedbackKind],
        },
    )


def _stream_feedback_csv(db: DBSession) -> Generator[str, None, None]:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id",
        "created_at_utc",
        "kind",
        "status",
        "page_url",
        "message",
        "contact_email",
        "ip_address",
        "user_agent",
        "admin_note",
        "resolved_at_utc",
    ])
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)

    batch_size = 500
    offset = 0
    while True:
        rows = db.execute(
            select(Feedback)
            .order_by(Feedback.id)
            .offset(offset)
            .limit(batch_size)
        ).scalars().all()
        if not rows:
            break
        for r in rows:
            writer.writerow([
                r.id,
                r.created_at.isoformat() if r.created_at else "",
                r.kind.value if r.kind else "",
                r.status.value if r.status else "",
                r.page_url or "",
                r.message or "",
                r.contact_email or "",
                r.ip_address or "",
                r.user_agent or "",
                r.admin_note or "",
                r.resolved_at.isoformat() if r.resolved_at else "",
            ])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        offset += batch_size


# NOTE: The CSV export must be declared BEFORE the parameterized
# /admin/feedback/{feedback_id} route — FastAPI matches routes in
# declaration order, and the parameterized route would otherwise swallow
# "export.csv" as a value for feedback_id and 422 on int coercion.
@router.get("/admin/feedback/export.csv")
async def export_feedback_csv(
    db: DBSession = Depends(get_db),
    _admin_email: str = Depends(require_admin),
):
    filename = (
        f"infusionfox-feedback-{datetime.now(UTC).strftime('%Y%m%d')}.csv"
    )
    return StreamingResponse(
        _stream_feedback_csv(db),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/admin/feedback/{feedback_id}", response_class=HTMLResponse)
async def feedback_detail(
    feedback_id: int,
    request: Request,
    db: DBSession = Depends(get_db),
    _admin_email: str = Depends(require_admin),
):
    templates = request.app.state.templates
    row = db.get(Feedback, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return templates.TemplateResponse(
        "admin/feedback_detail.html",
        {
            "request": request,
            "admin_email": _admin_email,
            "row": row,
            "all_statuses": [s.value for s in FeedbackStatus],
        },
    )


@router.post("/admin/feedback/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: int,
    request: Request,
    status: str = Form(...),
    admin_note: str = Form(""),
    db: DBSession = Depends(get_db),
    admin_email: str = Depends(require_admin),
):
    """Update a feedback row's status (and optionally append an admin note)."""
    row = db.get(Feedback, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Feedback not found")

    try:
        new_status = FeedbackStatus(status)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid status: {status}"
        ) from exc

    old_status = row.status
    row.status = new_status
    if new_status in (FeedbackStatus.RESOLVED, FeedbackStatus.IGNORED):
        row.resolved_at = _utcnow_naive()
    if admin_note.strip():
        # Append note rather than overwrite, with a timestamp + actor stamp
        ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        stamp = f"[{ts} by {admin_email}] {admin_note.strip()}"
        row.admin_note = (
            f"{row.admin_note}\n{stamp}" if row.admin_note else stamp
        )
    db.commit()

    _log.info(
        "Admin %s changed feedback#%d status: %s -> %s",
        admin_email, feedback_id, old_status.value, new_status.value,
    )

    return RedirectResponse(
        url=f"/admin/feedback/{feedback_id}",
        status_code=303,  # See Other — POST/Redirect/GET
    )
