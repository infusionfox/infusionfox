"""
Integration smoke tests: every public GET route should render.

This catches:
  - Template syntax errors
  - Broken context variables
  - Import errors that escape the unit-test boundary
  - Routes registered but pointing at missing or broken handlers
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# All registered GET routes that don't take path parameters
PUBLIC_GET_ROUTES = [
    r.path
    for r in app.routes
    if hasattr(r, "methods")
    and "GET" in r.methods
    and "{" not in r.path
    and not r.path.startswith(("/openapi", "/docs", "/redoc"))
]


@pytest.mark.parametrize("path", PUBLIC_GET_ROUTES)
def test_get_route_loads(client, path):
    """Every GET route should return a non-server-error status.

    Acceptable responses:
        200 OK         — page rendered
        301/302/303/307 — redirect (canonicalization)
        400            — missing required query parameter
    """
    response = client.get(path, follow_redirects=False)
    assert response.status_code < 500, f"GET {path} returned {response.status_code}: {response.text[:200]}"
    # Don't accept 404 on supposedly-registered routes
    assert response.status_code != 404, (
        f"GET {path} returned 404 — route is registered but handler is missing"
    )


def test_homepage_contains_app_name(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "infusionfox" in response.text.lower()


def test_health_endpoint(client):
    """If a /healthz or /health endpoint is present, it should return 200."""
    for path in ("/healthz", "/health", "/_health"):
        response = client.get(path)
        if response.status_code == 200:
            return
    # If none are present, that's fine — this is best-effort
    pytest.skip("no health endpoint registered")
