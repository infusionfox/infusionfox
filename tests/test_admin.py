"""Admin dashboard tests.

Covers:
- Auth gating via Cf-Access-Authenticated-User-Email header + allowlist
- Dashboard renders with counts and recent activity
- Disclaimer acceptances list with pagination and CSV export
- Feedback list with filters and CSV export
- Feedback detail view loads
- Status update appends admin note with timestamp + actor stamp,
  sets resolved_at when status moves to resolved/ignored
- 404 on unknown feedback id
"""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.db import (
    DisclaimerAcceptance,
    Feedback,
    FeedbackKind,
    FeedbackStatus,
    SessionLocal,
)
from app.disclaimer import DISCLAIMER_VERSION
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures: auth env + seed data
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_allowlist(monkeypatch):
    """Configure an admin email allowlist for one test."""
    monkeypatch.setenv("INFUSIONFOX_ADMIN_EMAILS", "tim@example.com,vet@example.com")
    monkeypatch.delenv("INFUSIONFOX_ADMIN_OPEN", raising=False)


@pytest.fixture
def admin_open_mode(monkeypatch):
    """Enable the development bypass for one test."""
    monkeypatch.setenv("INFUSIONFOX_ADMIN_OPEN", "1")
    monkeypatch.delenv("INFUSIONFOX_ADMIN_EMAILS", raising=False)


@pytest.fixture
def no_admin_config(monkeypatch):
    """No allowlist, no bypass — the safe default for a fresh deployment."""
    monkeypatch.delenv("INFUSIONFOX_ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("INFUSIONFOX_ADMIN_OPEN", raising=False)


def _admin_headers(email: str = "tim@example.com") -> dict[str, str]:
    return {"Cf-Access-Authenticated-User-Email": email}


@pytest.fixture
def seed_feedback():
    """Insert a couple of feedback rows for dashboard/list tests.

    Returns the inserted feedback IDs for tests that need to fetch
    them directly.
    """
    with SessionLocal() as db:
        rows = [
            Feedback(
                page_url="/apple-fast",
                kind=FeedbackKind.DOSE_CONCERN,
                message="The albumin band looks off on the >3.5 entry.",
                contact_email="reporter@example.com",
                status=FeedbackStatus.NEW,
                user_agent="TestBrowser/1.0",
                ip_address="198.51.100.10",
            ),
            Feedback(
                page_url="/blood-gas",
                kind=FeedbackKind.SUGGESTION,
                message="Add Stewart-style strong ion difference.",
                status=FeedbackStatus.SEEN,
                user_agent="TestBrowser/1.0",
                ip_address="198.51.100.11",
            ),
            Feedback(
                page_url="/dopamine",
                kind=FeedbackKind.BUG,
                message="The mL/hr field doesn't update on weight change.",
                status=FeedbackStatus.RESOLVED,
                user_agent="TestBrowser/1.0",
                ip_address="198.51.100.12",
            ),
        ]
        for r in rows:
            db.add(r)
        db.commit()
        ids = [r.id for r in rows]
    return ids


@pytest.fixture
def seed_disclaimer_acceptances():
    """Insert disclaimer rows directly via the DB for predictable counts.

    The disclaimer test file POSTs through the endpoint and may have
    left rows behind; here we add a small known set so dashboard
    queries return meaningful results.
    """
    with SessionLocal() as db:
        rows = [
            DisclaimerAcceptance(
                disclaimer_version=DISCLAIMER_VERSION,
                ip_address="203.0.113.1",
                user_agent="SeedAgent/1.0",
                session_token="seed-token-1",
            ),
            DisclaimerAcceptance(
                disclaimer_version=DISCLAIMER_VERSION,
                ip_address="203.0.113.2",
                user_agent="SeedAgent/1.0",
                session_token="seed-token-2",
            ),
            DisclaimerAcceptance(
                disclaimer_version="2026-01-01",  # older version
                ip_address="203.0.113.3",
                user_agent="SeedAgent/1.0",
                session_token="seed-token-3",
            ),
        ]
        for r in rows:
            db.add(r)
        db.commit()


# ---------------------------------------------------------------------------
# Auth gating
# ---------------------------------------------------------------------------


class TestAuthGating:
    def test_dashboard_403_without_header(self, admin_allowlist):
        resp = client.get("/admin/")
        assert resp.status_code == 403

    def test_dashboard_403_when_header_not_in_allowlist(self, admin_allowlist):
        resp = client.get(
            "/admin/",
            headers=_admin_headers("attacker@example.com"),
        )
        assert resp.status_code == 403

    def test_dashboard_403_when_no_allowlist_configured(self, no_admin_config):
        """Safe default: with no env vars set, every request 403s
        even with the header. Forces the operator to explicitly
        configure admin emails before exposure."""
        resp = client.get(
            "/admin/",
            headers=_admin_headers("tim@example.com"),
        )
        assert resp.status_code == 403

    def test_dashboard_200_when_allowed(self, admin_allowlist):
        resp = client.get(
            "/admin/",
            headers=_admin_headers("tim@example.com"),
        )
        assert resp.status_code == 200

    def test_dashboard_200_with_second_allowlisted_email(self, admin_allowlist):
        resp = client.get(
            "/admin/",
            headers=_admin_headers("vet@example.com"),
        )
        assert resp.status_code == 200

    def test_dashboard_200_in_open_mode_without_header(self, admin_open_mode):
        """Open mode skips the header check entirely. Dev-only escape hatch."""
        resp = client.get("/admin/")
        assert resp.status_code == 200

    def test_email_is_case_insensitive(self, admin_allowlist):
        resp = client.get(
            "/admin/",
            headers=_admin_headers("TIM@example.COM"),
        )
        assert resp.status_code == 200

    def test_all_admin_routes_gated(self, no_admin_config):
        """Every admin route must require auth, not just the dashboard."""
        paths = [
            "/admin/",
            "/admin/disclaimer-acceptances",
            "/admin/disclaimer-acceptances/export.csv",
            "/admin/feedback",
            "/admin/feedback/export.csv",
            "/admin/feedback/1",
        ]
        for path in paths:
            resp = client.get(path)
            assert resp.status_code == 403, (
                f"{path} should require admin auth but returned {resp.status_code}"
            )

    def test_status_post_also_gated(self, no_admin_config):
        resp = client.post(
            "/admin/feedback/1/status",
            data={"status": "resolved"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Dashboard rendering
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_dashboard_shows_disclaimer_total(
        self, admin_allowlist, seed_disclaimer_acceptances
    ):
        resp = client.get("/admin/", headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.text
        # The seed adds at least 3 rows; total should be visible
        assert "Disclaimer acceptances" in body

    def test_dashboard_shows_feedback_kinds(
        self, admin_allowlist, seed_feedback
    ):
        resp = client.get("/admin/", headers=_admin_headers())
        body = resp.text
        # Feedback section labels
        assert "Feedback by kind" in body
        # At least one of the seeded kinds appears
        assert "dose_concern" in body or "suggestion" in body or "bug" in body

    def test_dashboard_highlights_dose_concern(
        self, admin_allowlist, seed_feedback
    ):
        """A NEW dose_concern row should produce the highlight count."""
        resp = client.get("/admin/", headers=_admin_headers())
        body = resp.text
        assert "dose-concern" in body or "dose_concern" in body

    def test_dashboard_has_links_to_lists_and_exports(
        self, admin_allowlist
    ):
        resp = client.get("/admin/", headers=_admin_headers())
        body = resp.text
        assert "/admin/disclaimer-acceptances" in body
        assert "/admin/disclaimer-acceptances/export.csv" in body
        assert "/admin/feedback" in body
        assert "/admin/feedback/export.csv" in body

    def test_dashboard_shows_signed_in_email(self, admin_allowlist):
        resp = client.get(
            "/admin/",
            headers=_admin_headers("tim@example.com"),
        )
        assert "tim@example.com" in resp.text


# ---------------------------------------------------------------------------
# Disclaimer acceptances list + CSV export
# ---------------------------------------------------------------------------


class TestDisclaimerList:
    def test_list_renders(self, admin_allowlist, seed_disclaimer_acceptances):
        resp = client.get(
            "/admin/disclaimer-acceptances",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.text
        # Header + at least one seeded IP appear
        assert "Disclaimer acceptances" in body
        assert "203.0.113.1" in body or "203.0.113.2" in body

    def test_list_supports_pagination_params(self, admin_allowlist):
        resp = client.get(
            "/admin/disclaimer-acceptances?page=1&per_page=10",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200

    def test_list_clamps_huge_per_page(self, admin_allowlist):
        """per_page > 200 should be clamped to 200, not blow up."""
        resp = client.get(
            "/admin/disclaimer-acceptances?per_page=99999",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200

    def test_csv_export_content_type(
        self, admin_allowlist, seed_disclaimer_acceptances
    ):
        resp = client.get(
            "/admin/disclaimer-acceptances/export.csv",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        assert ".csv" in resp.headers["content-disposition"]

    def test_csv_export_header_row(
        self, admin_allowlist, seed_disclaimer_acceptances
    ):
        resp = client.get(
            "/admin/disclaimer-acceptances/export.csv",
            headers=_admin_headers(),
        )
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) >= 1
        header = rows[0]
        assert header == [
            "id",
            "accepted_at_utc",
            "disclaimer_version",
            "ip_address",
            "user_agent",
            "session_token",
        ]

    def test_csv_export_has_data_rows(
        self, admin_allowlist, seed_disclaimer_acceptances
    ):
        resp = client.get(
            "/admin/disclaimer-acceptances/export.csv",
            headers=_admin_headers(),
        )
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        # Header + at least the 3 seeded rows
        assert len(rows) >= 4


# ---------------------------------------------------------------------------
# Feedback list + filters + CSV
# ---------------------------------------------------------------------------


class TestFeedbackList:
    def test_list_renders(self, admin_allowlist, seed_feedback):
        resp = client.get(
            "/admin/feedback",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.text
        # Seeded message snippets visible
        assert "albumin band" in body or "Stewart" in body or "mL/hr" in body

    def test_filter_by_status_new(self, admin_allowlist, seed_feedback):
        resp = client.get(
            "/admin/feedback?status=new",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.text
        # NEW row's message should appear
        assert "albumin band" in body
        # RESOLVED row's message should NOT (since filter excludes it)
        # NB: list may show truncated previews — check on a unique phrase
        assert "mL/hr field" not in body

    def test_filter_by_kind_dose_concern(self, admin_allowlist, seed_feedback):
        resp = client.get(
            "/admin/feedback?kind=dose_concern",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.text
        assert "albumin band" in body
        # bug row excluded
        assert "mL/hr field" not in body

    def test_invalid_filter_silently_ignored(self, admin_allowlist):
        resp = client.get(
            "/admin/feedback?status=bogus&kind=alsobogus",
            headers=_admin_headers(),
        )
        # Invalid filter values fall through to no-filter; not an error
        assert resp.status_code == 200

    def test_csv_export(self, admin_allowlist, seed_feedback):
        resp = client.get(
            "/admin/feedback/export.csv",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        header = rows[0]
        assert header[0] == "id"
        assert "message" in header
        assert "ip_address" in header
        # At least the 3 seeded rows
        assert len(rows) >= 4


# ---------------------------------------------------------------------------
# Feedback detail + status update
# ---------------------------------------------------------------------------


class TestFeedbackDetail:
    def test_detail_loads(self, admin_allowlist, seed_feedback):
        feedback_id = seed_feedback[0]  # the dose_concern NEW row
        resp = client.get(
            f"/admin/feedback/{feedback_id}",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.text
        assert "albumin band looks off" in body
        # Status select with current value selected
        assert 'value="new"' in body or "new" in body

    def test_detail_404_for_unknown_id(self, admin_allowlist):
        resp = client.get(
            "/admin/feedback/9999999",
            headers=_admin_headers(),
        )
        assert resp.status_code == 404

    def test_status_update_changes_status(
        self, admin_allowlist, seed_feedback
    ):
        feedback_id = seed_feedback[0]
        resp = client.post(
            f"/admin/feedback/{feedback_id}/status",
            data={"status": "seen", "admin_note": ""},
            headers=_admin_headers("tim@example.com"),
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/admin/feedback/{feedback_id}"

        # Verify the row was actually updated
        with SessionLocal() as db:
            row = db.get(Feedback, feedback_id)
            assert row.status == FeedbackStatus.SEEN

    def test_status_resolved_sets_resolved_at(
        self, admin_allowlist, seed_feedback
    ):
        feedback_id = seed_feedback[0]
        resp = client.post(
            f"/admin/feedback/{feedback_id}/status",
            data={"status": "resolved"},
            headers=_admin_headers("tim@example.com"),
            follow_redirects=False,
        )
        assert resp.status_code == 303
        with SessionLocal() as db:
            row = db.get(Feedback, feedback_id)
            assert row.status == FeedbackStatus.RESOLVED
            assert row.resolved_at is not None

    def test_status_update_appends_admin_note_with_stamp(
        self, admin_allowlist, seed_feedback
    ):
        feedback_id = seed_feedback[1]
        resp = client.post(
            f"/admin/feedback/{feedback_id}/status",
            data={
                "status": "seen",
                "admin_note": "Investigating the strong-ion-difference request.",
            },
            headers=_admin_headers("tim@example.com"),
            follow_redirects=False,
        )
        assert resp.status_code == 303

        with SessionLocal() as db:
            row = db.get(Feedback, feedback_id)
            assert row.admin_note is not None
            assert "Investigating the strong-ion-difference request." in row.admin_note
            # Stamp format: "[YYYY-MM-DD HH:MM UTC by email] note"
            assert "tim@example.com" in row.admin_note
            assert "UTC" in row.admin_note

    def test_status_update_multiple_notes_accumulate(
        self, admin_allowlist, seed_feedback
    ):
        """Repeated status updates append notes rather than overwriting."""
        feedback_id = seed_feedback[2]
        client.post(
            f"/admin/feedback/{feedback_id}/status",
            data={"status": "seen", "admin_note": "First triage pass."},
            headers=_admin_headers("tim@example.com"),
            follow_redirects=False,
        )
        client.post(
            f"/admin/feedback/{feedback_id}/status",
            data={"status": "resolved", "admin_note": "Fixed in v1.2."},
            headers=_admin_headers("tim@example.com"),
            follow_redirects=False,
        )

        with SessionLocal() as db:
            row = db.get(Feedback, feedback_id)
            assert "First triage pass." in row.admin_note
            assert "Fixed in v1.2." in row.admin_note

    def test_invalid_status_value_returns_400(
        self, admin_allowlist, seed_feedback
    ):
        feedback_id = seed_feedback[0]
        resp = client.post(
            f"/admin/feedback/{feedback_id}/status",
            data={"status": "totally-made-up"},
            headers=_admin_headers("tim@example.com"),
            follow_redirects=False,
        )
        assert resp.status_code == 400

    def test_status_update_404_for_unknown_id(self, admin_allowlist):
        resp = client.post(
            "/admin/feedback/9999999/status",
            data={"status": "seen"},
            headers=_admin_headers("tim@example.com"),
            follow_redirects=False,
        )
        assert resp.status_code == 404
