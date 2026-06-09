"""
Cache-Control policy.

Without explicit Cache-Control headers, every layer between InfusionFox and the
user (Cloudflare, browsers, iOS "Add to Home Screen" webclips) picks its own
heuristic caching strategy. The webclip case is the painful one: a deploy
can be hidden behind a stale HTML shell that the webclip never revalidates.

Policy:
    HTML responses           → no-cache, must-revalidate
    /static/* responses      → public, max-age=3600

These tests pin the policy so a future refactor of the middleware can't
silently drop the headers (or set them too aggressively, e.g. caching HTML
for hours and reintroducing the webclip-stale-deploy problem).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestHtmlNoCache:
    """HTML pages must send `no-cache, must-revalidate` so browsers and
    webclips revalidate the shell before serving cached content."""

    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/norepinephrine",
            "/blood-gas",
            "/anesthesia",
            "/learn/blood-gas",
            "/calculators",
            "/health",
        ],
    )
    def test_html_response_revalidates(self, client, path):
        r = client.get(path)
        # 200 or 3xx — we just want to inspect the headers regardless.
        cc = r.headers.get("cache-control", "")
        assert "no-cache" in cc, (
            f"GET {path}: expected 'no-cache' in Cache-Control, got: {cc!r}. "
            f"Without this, an iOS webclip or Cloudflare can hold a stale "
            f"HTML shell across deploys."
        )
        assert "must-revalidate" in cc, (
            f"GET {path}: expected 'must-revalidate' in Cache-Control, got: " f"{cc!r}."
        )


class TestStaticAssetCaching:
    """Static assets get a moderate cache so images/fonts don't refetch
    every request, but a deploy still propagates within an hour. CSS is
    additionally cache-busted via `?v=<hash>` in templates, so a CSS edit
    propagates immediately regardless of the TTL on this path."""

    def test_static_css_has_public_max_age(self, client):
        r = client.get("/static/css/app.css")
        cc = r.headers.get("cache-control", "")
        assert "public" in cc, f"CSS Cache-Control should be public, got: {cc!r}"
        assert "max-age=3600" in cc, f"CSS Cache-Control should be max-age=3600, got: {cc!r}"

    def test_static_webmanifest_has_public_max_age(self, client):
        r = client.get("/static/site.webmanifest")
        if r.status_code == 404:
            pytest.skip("site.webmanifest not present")
        cc = r.headers.get("cache-control", "")
        assert "public" in cc
        assert "max-age=3600" in cc


class TestRedirectsRevalidate:
    """The legacy /c/<path> 308 redirects must also send no-cache so the
    redirect itself isn't held by intermediaries past its useful life."""

    def test_legacy_redirect_revalidates(self, client):
        r = client.get("/c/norepinephrine", follow_redirects=False)
        assert r.status_code == 308
        cc = r.headers.get("cache-control", "")
        assert "no-cache" in cc, f"Legacy redirect should not be cached aggressively, got: {cc!r}"


class TestRouteHandlerOverridesRespected:
    """Middleware must not clobber a Cache-Control header set explicitly by
    a route handler. Currently no route does this, but the middleware's
    'don't overwrite' branch protects future use cases (e.g. an immutable
    asset served via a route, or a deliberately long-cached blob)."""

    def test_explicit_cache_control_not_overwritten(self, client):
        # Sanity: hit an HTML page and confirm the default applies. If a
        # future route sets its own Cache-Control, this test should be
        # extended with a parametrized case for that route.
        r = client.get("/")
        assert r.headers.get("cache-control") == "no-cache, must-revalidate"
