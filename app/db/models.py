"""
InfusionFox data model.

Currently a minimal schema: user-submitted feedback is the only persisted
data. Authentication, billing, entitlements, and CE tracking lived here in
earlier versions but were removed when those concerns were outsourced to
infrastructure (Cloudflare Zero Trust for the closed beta; hosted auth
provider later). See git history if you need to recover any of that.

- SQLite by default, Postgres-compatible by design.
- All timestamps are naive UTC. The database stores UTC only; display
  conversion happens at the view layer. SQLite has no timezone support
  internally, so we keep Python datetimes naive to avoid TypeError on
  comparison with values read back from the DB.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Return the current UTC time as a *naive* datetime.

    datetime.utcnow() is deprecated in 3.12+; this is the modern equivalent.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Feedback — anonymous user-submitted feedback (bug reports, suggestions,
# clinical concerns about dose ranges, etc.)
# ---------------------------------------------------------------------------


class FeedbackStatus(str, enum.Enum):
    NEW = "new"
    SEEN = "seen"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class FeedbackKind(str, enum.Enum):
    BUG = "bug"
    SUGGESTION = "suggestion"
    MISSING_DRUG = "missing_drug"
    DOSE_CONCERN = "dose_concern"  # flagged so these get triaged first
    OTHER = "other"


class Feedback(Base):
    """User-submitted feedback. Purposefully simple — goal is low-friction
    capture, not a ticketing system. All submissions are anonymous; we
    capture an optional contact_email if the submitter wants a reply.

    There is no admin triage UI in the app right now — read the feedback
    table directly with sqlite3 when triaging."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # The page the submitter was on — helps reproduce issues
    page_url: Mapped[str | None] = mapped_column(String(500))

    kind: Mapped[FeedbackKind] = mapped_column(
        Enum(FeedbackKind), nullable=False, default=FeedbackKind.OTHER
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional contact for follow-up; the submission flow always
    # presents the email field since there are no signed-in users.
    contact_email: Mapped[str | None] = mapped_column(String(320))

    status: Mapped[FeedbackStatus] = mapped_column(
        Enum(FeedbackStatus), nullable=False, default=FeedbackStatus.NEW
    )
    admin_note: Mapped[str | None] = mapped_column(Text)

    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# DisclaimerAcceptance — legal audit trail for the hard-block modal.
#
# Every accepted disclaimer is one row. When auth returns we'll add a
# nullable user_id column and backfill linkage where we can; the row
# itself stays as the authoritative legal record.
#
# Privacy posture: this is the ONE place in infusionfox that intentionally
# logs PII (IP). It's disclosed in the disclaimer text itself, which
# the user reads BEFORE the row is written. No analytics, no tracking
# elsewhere — this table exists solely to substantiate "user X accepted
# version V on date D" if ever asked.
# ---------------------------------------------------------------------------


class DisclaimerAcceptance(Base):
    __tablename__ = "disclaimer_acceptances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # The DISCLAIMER_VERSION constant in app/disclaimer.py at the time
    # of acceptance. Bumping that constant invalidates prior acceptances
    # at the client (localStorage) layer; this table preserves the
    # historical record of which version each user accepted.
    disclaimer_version: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )

    # Originating IP per app/util/client_ip.py (CF-Connecting-IP first).
    # Nullable because in pathological cases (e.g. test client without
    # any host info) we can still record the acceptance.
    ip_address: Mapped[str | None] = mapped_column(String(64), index=True)

    # Browser User-Agent string, truncated to 500 chars at write time.
    user_agent: Mapped[str | None] = mapped_column(String(500))

    # An opaque random token the client generates and stores in
    # localStorage alongside the version. Lets us correlate multiple
    # accepted versions from the same device if needed for audit work.
    # Not a security token — just an opaque correlation key.
    session_token: Mapped[str | None] = mapped_column(String(64), index=True)

    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
