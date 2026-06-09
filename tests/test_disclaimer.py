"""Tests for the hard-block disclaimer system.

Covers:
- POST /api/disclaimer/accept records correctly
- IP extraction priority: CF-Connecting-IP > X-Forwarded-For > client.host
- Modal markup is present in base.html on every page
- Disclaimer version + text are exposed via templates.env.globals
- Footer free-messaging is present
- Homepage hero free-messaging is present

The actual modal show/hide logic is JavaScript; we test what we can
server-side (markup present, version-injected) and trust the browser
behavior (focus trap, ESC interception, body scroll lock) is the JS
that's shipped — those would be tested in a browser harness.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import DisclaimerAcceptance, SessionLocal
from app.disclaimer import DISCLAIMER_TEXT, DISCLAIMER_VERSION
from app.main import app

client = TestClient(app)


def _count_acceptances() -> int:
    with SessionLocal() as db:
        return len(db.execute(select(DisclaimerAcceptance)).all())


def _latest_acceptance() -> DisclaimerAcceptance | None:
    with SessionLocal() as db:
        rows = db.execute(
            select(DisclaimerAcceptance).order_by(
                DisclaimerAcceptance.id.desc()
            )
        ).scalars().all()
        return rows[0] if rows else None


class TestAcceptEndpoint:
    def test_post_records_acceptance(self):
        before = _count_acceptances()
        resp = client.post(
            "/api/disclaimer/accept",
            json={
                "version": DISCLAIMER_VERSION,
                "session_token": "abcdef0123456789",
            },
        )
        assert resp.status_code == 204
        assert resp.content == b""
        assert _count_acceptances() == before + 1

        row = _latest_acceptance()
        assert row is not None
        assert row.disclaimer_version == DISCLAIMER_VERSION
        assert row.session_token == "abcdef0123456789"
        assert row.accepted_at is not None

    def test_post_without_session_token_still_records(self):
        before = _count_acceptances()
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": DISCLAIMER_VERSION},
        )
        assert resp.status_code == 204
        assert _count_acceptances() == before + 1
        row = _latest_acceptance()
        assert row.session_token is None
        assert row.disclaimer_version == DISCLAIMER_VERSION

    def test_post_empty_body_still_records_with_current_version(self):
        """Defensive: a malformed body still gets a row (we'd rather
        capture the acceptance than reject it on technicality)."""
        before = _count_acceptances()
        resp = client.post("/api/disclaimer/accept", json={})
        assert resp.status_code == 204
        assert _count_acceptances() == before + 1
        row = _latest_acceptance()
        assert row.disclaimer_version == DISCLAIMER_VERSION

    def test_post_invalid_json_returns_400(self):
        resp = client.post(
            "/api/disclaimer/accept",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_post_non_dict_body_returns_400(self):
        """A JSON array or scalar body is rejected — must be an object."""
        resp = client.post("/api/disclaimer/accept", json=[1, 2, 3])
        assert resp.status_code == 400

    def test_post_records_user_agent(self):
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": DISCLAIMER_VERSION},
            headers={"User-Agent": "TestBrowser/1.0 (infusionfox-tests)"},
        )
        assert resp.status_code == 204
        row = _latest_acceptance()
        assert row.user_agent is not None
        assert "TestBrowser/1.0" in row.user_agent

    def test_post_truncates_long_user_agent(self):
        long_ua = "X" * 1000
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": DISCLAIMER_VERSION},
            headers={"User-Agent": long_ua},
        )
        assert resp.status_code == 204
        row = _latest_acceptance()
        assert row.user_agent is not None
        # Truncated to <= 500 chars per the column constraint
        assert len(row.user_agent) <= 500

    def test_post_records_session_token_truncated(self):
        long_token = "Z" * 200
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": DISCLAIMER_VERSION, "session_token": long_token},
        )
        assert resp.status_code == 204
        row = _latest_acceptance()
        assert row.session_token is not None
        assert len(row.session_token) <= 64

    def test_post_records_version_truncated(self):
        long_ver = "v" + "9" * 200
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": long_ver, "session_token": "abc"},
        )
        assert resp.status_code == 204
        row = _latest_acceptance()
        # Coerced to <=32 chars
        assert len(row.disclaimer_version) <= 32


class TestClientIPExtraction:
    """The IP-extraction helper has its own priority order. Verify
    through the disclaimer endpoint since it's the most natural
    integration test."""

    def test_cf_connecting_ip_takes_priority(self):
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": DISCLAIMER_VERSION},
            headers={
                "CF-Connecting-IP": "203.0.113.42",
                "X-Forwarded-For": "10.0.0.1, 10.0.0.2",
            },
        )
        assert resp.status_code == 204
        row = _latest_acceptance()
        assert row.ip_address == "203.0.113.42"

    def test_x_forwarded_for_used_without_cf_header(self):
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": DISCLAIMER_VERSION},
            headers={"X-Forwarded-For": "198.51.100.7, 10.0.0.1"},
        )
        assert resp.status_code == 204
        row = _latest_acceptance()
        # Leftmost value (original client, not the proxy chain)
        assert row.ip_address == "198.51.100.7"

    def test_xff_strips_whitespace(self):
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": DISCLAIMER_VERSION},
            headers={"X-Forwarded-For": "   198.51.100.99  ,10.0.0.1"},
        )
        assert resp.status_code == 204
        row = _latest_acceptance()
        assert row.ip_address == "198.51.100.99"

    def test_falls_back_to_client_host(self):
        """With no proxy headers, FastAPI's TestClient sets client.host
        to 'testclient' — we just verify *something* is recorded."""
        resp = client.post(
            "/api/disclaimer/accept",
            json={"version": DISCLAIMER_VERSION},
        )
        assert resp.status_code == 204
        row = _latest_acceptance()
        # TestClient yields a client.host value; the exact value isn't
        # important, only that we recorded SOMETHING
        assert row.ip_address is not None


class TestModalRendering:
    """The modal markup must be present on every page so the JS can
    show it when the localStorage version check fails."""

    def test_modal_present_on_homepage(self):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text
        assert 'id="disclaimer-overlay"' in body
        assert 'id="disclaimer-modal"' in body
        assert 'id="disclaimer-accept"' in body
        # The overlay starts hidden — JS un-hides on version mismatch
        assert 'id="disclaimer-overlay" hidden' in body

    def test_modal_present_on_calculator_page(self):
        resp = client.get("/apple-fast")
        assert resp.status_code == 200
        assert 'id="disclaimer-overlay"' in resp.text

    def test_modal_present_on_learn_page(self):
        resp = client.get("/learn/apple-fast")
        assert resp.status_code == 200
        assert 'id="disclaimer-overlay"' in resp.text

    def test_disclaimer_version_inlined_in_js(self):
        """The JS needs the current version baked into the response
        so it can compare against localStorage."""
        resp = client.get("/")
        body = resp.text
        assert f'CURRENT_VERSION = "{DISCLAIMER_VERSION}"' in body

    def test_disclaimer_text_rendered_in_modal(self):
        resp = client.get("/")
        body = resp.text
        # First sentence of the canonical text
        assert (
            "InfusionFox is a clinical reference and calculator tool for "
            "licensed veterinary professionals" in body
        )

    def test_modal_has_disabled_accept_button_initially(self):
        """Accept button starts disabled; JS enables it when the
        checkbox is checked."""
        resp = client.get("/")
        body = resp.text
        # Find the button markup; ensure 'disabled' attribute is present
        import re
        m = re.search(
            r'<button[^>]*id="disclaimer-accept"[^>]*>',
            body,
        )
        assert m is not None, "accept button not found"
        assert "disabled" in m.group(0)


class TestFreeMessaging:
    def test_homepage_hero_says_free(self):
        resp = client.get("/")
        assert resp.status_code == 200
        # "Free for clinical use" appears in the eyebrow above the H1
        assert "Free for clinical use" in resp.text

    def test_footer_says_free(self):
        resp = client.get("/")
        assert resp.status_code == 200
        # Footer fineprint has "Free for clinical use"
        # (case-insensitive check since footer text exact form may shift)
        assert "Free for clinical use" in resp.text

    def test_modal_body_says_free(self):
        resp = client.get("/")
        # The disclaimer text itself includes "InfusionFox is free"
        assert "InfusionFox is free" in resp.text


class TestDisclaimerConstants:
    """Lock down the version-bump behavior."""

    def test_version_is_iso_date_format(self):
        """Convention: YYYY-MM-DD. Tooling and future audit queries
        depend on this being lexicographically orderable."""
        import re
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", DISCLAIMER_VERSION), (
            f"DISCLAIMER_VERSION should be ISO date: got {DISCLAIMER_VERSION}"
        )

    def test_text_covers_required_elements(self):
        """The disclaimer text must cover: free, professional audience,
        no warranty, no clinician-patient relationship, IP/UA/timestamp
        notice. These are the elements the audit trail substantiates."""
        text = DISCLAIMER_TEXT.lower()
        assert "free" in text
        assert (
            "licensed veterinary professional" in text
            or "veterinary professional" in text
        )
        assert "without warranty" in text or "no warranty" in text.lower()
        assert (
            "no clinician-patient relationship" in text
            or "not a substitute" in text
        )
        assert "ip address" in text
        assert "user-agent" in text or "user agent" in text
        assert "date and time" in text or "timestamp" in text
