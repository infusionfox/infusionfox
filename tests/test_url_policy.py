"""
URL policy and legacy-redirect tests.

After the bare-path migration, every calculator route lives at /<slug>
rather than /c/<slug>. Two invariants protect that:

  1. No registered route uses the /c/ prefix except the legacy catch-all
     in `app/routers/legacy_redirects.py`. A future PR that habitually
     types `@router.get("/c/something")` would be caught here at CI.

  2. The legacy `/c/<anything>` URL still 308-redirects to /<anything>
     for any bookmarked link from before the migration. Tests below
     cover GET, POST (method preservation matters for stale HTMX
     clients — 301/302 would convert them to GETs and break compute
     calls), and query-string preservation.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# URL pattern policy
# ---------------------------------------------------------------------------

# The single allowed /c/ route: the catch-all redirect that 308s every
# /c/<anything> to /<anything>. Any other /c/ path is a policy violation.
ALLOWED_LEGACY_PATH = "/c/{path:path}"


class TestNoLegacyPrefix:
    """No calculator route may live under /c/ after the bare-path migration."""

    def test_no_routes_outside_legacy_redirect_use_c_prefix(self):
        violations = []
        for route in app.routes:
            path = getattr(route, "path", None)
            if path is None or not path.startswith("/c/"):
                continue
            if path == ALLOWED_LEGACY_PATH:
                continue
            violations.append(path)

        assert not violations, (
            "Routes registered under /c/ prefix outside the legacy "
            f"redirect: {violations}.\n\n"
            "Calculator URLs are bare paths (/<slug>). The /c/ prefix "
            "is reserved for the catch-all redirect in "
            "app/routers/legacy_redirects.py. Move new routes to /<slug>."
        )


# ---------------------------------------------------------------------------
# Legacy /c/<x> -> /<x> redirect
# ---------------------------------------------------------------------------


class TestLegacyRedirect:
    """The /c/<anything> -> /<anything> redirect protects bookmarks and
    stale clients from breaking after the URL migration. Removing the
    redirect router silently is a known cleanup-PR failure mode; these
    tests fail loudly if that happens."""

    def test_get_legacy_engine_drug_redirects_with_308(self):
        r = client.get("/c/norepinephrine", follow_redirects=False)
        assert r.status_code == 308, f"GET /c/norepinephrine should 308-redirect, got {r.status_code}"
        assert r.headers["location"] == "/norepinephrine"

    def test_get_legacy_bespoke_route_redirects(self):
        r = client.get("/c/blood-gas", follow_redirects=False)
        assert r.status_code == 308
        assert r.headers["location"] == "/blood-gas"

    def test_post_legacy_compute_preserves_method(self):
        """POST -> POST preservation matters for stale HTMX clients. A 301
        or 302 would convert the compute POST into a GET and break the
        result-panel swap silently."""
        r = client.post(
            "/c/norepinephrine/compute",
            data={
                "weight_value": "10",
                "weight_unit": "kg",
                "dose": "0.1",
                "concentration_ug_per_ml": "16",
                "species": "dog",
            },
            follow_redirects=False,
        )
        assert r.status_code == 308, (
            f"POST /c/<x>/compute must 308 (method-preserving), got "
            f"{r.status_code}. A 301/302 would convert the request to "
            f"a GET and break HTMX compute calls from stale clients."
        )
        assert r.headers["location"] == "/norepinephrine/compute"

    def test_redirect_preserves_query_string(self):
        r = client.get("/c/blood-gas?ph=7.4&pco2=40", follow_redirects=False)
        assert r.status_code == 308
        assert r.headers["location"] == "/blood-gas?ph=7.4&pco2=40"

    def test_unknown_legacy_path_still_redirects(self):
        """The redirect is a catch-all; an unknown slug still 308s and the
        bare path will 404 on the actual handler. That's the right shape:
        the redirect doesn't know which slugs are valid, and the 404 lives
        with the calculator routes, not the redirect layer."""
        r = client.get("/c/some-deleted-thing", follow_redirects=False)
        assert r.status_code == 308
        assert r.headers["location"] == "/some-deleted-thing"

    def test_following_redirect_reaches_canonical_page(self):
        """End-to-end: following the redirect should land on a 200 page
        for a known calculator slug."""
        r = client.get("/c/norepinephrine")  # default follows redirects
        assert r.status_code == 200
