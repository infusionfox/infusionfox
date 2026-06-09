"""InfusionFox — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.calculators import drugs_by_category
from app.db import init_db
from app.logging_config import configure_logging, get_logger
from app.nav import nav_index as _nav_index
from app.observability import init_sentry
from app.routers import discover_routers

configure_logging()
_log = get_logger(__name__)

# Initialize Sentry BEFORE constructing the FastAPI app — Sentry's
# FastAPI integration patches request-handler creation at init time, so
# patches applied after `app = FastAPI(...)` would not catch handlers
# wired up during that construction. No-op if SENTRY_DSN is unset, which
# is the case for local dev and tests.
if init_sentry(release="0.2.0"):
    _log.info("Sentry initialized.")
else:
    _log.debug("Sentry not initialized (SENTRY_DSN unset).")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """App lifespan: initialize the DB and search index at startup."""
    init_db()
    _log.info("InfusionFox started. DB ready.")
    # Log a loud warning if INFUSIONFOX_ADMIN_OPEN is set — that's a
    # development-only bypass for the admin auth check.
    from app.admin_auth import warn_if_open_mode

    warn_if_open_mode()
    # Rebuild the search index from current content. Idempotent and
    # cheap (~100-300ms at current catalog size); avoids any incremental
    # indexing complexity.
    try:
        from app.db.session import engine as _engine
        from app.search import rebuild_index

        n = rebuild_index(_engine)
        _log.info("Search index rebuilt: %d entries.", n)
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("Search index rebuild failed at startup: %s", exc)
    yield


app = FastAPI(
    title="InfusionFox",
    description="Veterinary constant-rate infusion calculators and reference.",
    version="0.2.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

templates.env.globals["drug_nav"] = drugs_by_category
templates.env.globals["site_name"] = "InfusionFox"
templates.env.globals["tagline"] = "Cited. Calculated. Confirmed."

# Disclaimer text + version exposed to base.html for the hard-block
# modal. The frontend checks the user's accepted version (localStorage)
# against this value and re-fires the modal on mismatch. See
# app/disclaimer.py for the version-bump procedure and the canonical
# text.
from app.disclaimer import DISCLAIMER_TEXT, DISCLAIMER_VERSION  # noqa: E402
from app.version import APP_VERSION, LICENSE_SPDX, SOURCE_URL  # noqa: E402

templates.env.globals["disclaimer_version"] = DISCLAIMER_VERSION
templates.env.globals["disclaimer_text"] = DISCLAIMER_TEXT
templates.env.globals["app_version"] = APP_VERSION
templates.env.globals["source_url"] = SOURCE_URL
templates.env.globals["license_spdx"] = LICENSE_SPDX


# Build-time cache-busting hash for the main stylesheet.
# Templates use this as `?v={{ css_version }}` so any change to app.css
# automatically invalidates the browser cache without manual ?v=N bumps.
def _compute_static_hash(filename: str) -> str:
    import hashlib

    path = STATIC_DIR / filename
    try:
        return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()[:10]
    except OSError:
        return "dev"


templates.env.globals["css_version"] = _compute_static_hash("css/app.css")

# Make the full categorized inventory available to every template so the
# slide-in drawer (rendered in base.html) can populate without each route
# having to pass nav_groups explicitly. Note: nav_index() reads from
# module-level data structures and does not hit the database, so it's
# cheap enough to call per-request via a lazy lookup. Using a callable
# rather than caching the result keeps any future hot-reload of the nav
# index (e.g. during dev when reordering categories) reflected immediately.
templates.env.globals["drawer_nav_groups"] = _nav_index

# Pre-compute the set of clinical-background article slugs at startup so
# templates can conditionally render a "Clinical background" tab only
# when the article actually exists. Without this guard, every drug
# calculator using the standard template generates a /learn/<slug> link
# even when no article is published, producing a 404 when clicked.
def _discover_article_slugs() -> set[str]:
    content_dir = Path(__file__).resolve().parent.parent / "content"
    if not content_dir.exists():
        return set()
    return {p.stem for p in content_dir.rglob("*.md")}


templates.env.globals["available_articles"] = _discover_article_slugs()

app.state.templates = templates


_router_count = 0
for _router in discover_routers():
    app.include_router(_router)
    _router_count += 1
_log.info("Registered %d routers via auto-discovery.", _router_count)


# ---------------------------------------------------------------------------
# Cache-Control middleware
#
# Without explicit cache headers, every layer between InfusionFox and the user
# (Cloudflare, the browser, an iOS "Add to Home Screen" webclip) chooses its
# own heuristic caching strategy. The webclip case is the painful one: it
# can hold a stale HTML shell across deploys until something explicitly
# tells it to revalidate.
#
# Policy:
#   - HTML responses        → `no-cache, must-revalidate`
#       Browser can cache, but MUST send a conditional request before
#       reusing. Since we don't currently emit ETag/Last-Modified for the
#       dynamic pages, the conditional request returns 200 every time —
#       which is still cheap (the app renders in milliseconds) and removes
#       any chance of a stale HTML shell surviving a deploy.
#
#   - /static/* responses   → `public, max-age=3600`
#       One hour is a reasonable balance: images/fonts don't change often,
#       but a deploy gets reflected within an hour. CSS is already cache-
#       busted by the ?v=<hash> query string (see css_version above), so
#       a CSS change is picked up on the next HTML render regardless of
#       the static cache TTL.
#
# Note: nothing sets `no-store`. We want the browser to keep using cached
# resources between requests; we just want it to confirm with the server
# before serving stale HTML.
# ---------------------------------------------------------------------------


@app.middleware("http")
async def add_cache_control(request, call_next):
    response = await call_next(request)
    # Don't overwrite a Cache-Control header a route handler set explicitly.
    if "cache-control" in (h.lower() for h in response.headers):
        return response

    path = request.url.path
    if path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        # HTML, JSON, redirects. Everything else gets revalidate-on-load
        # so a deploy can't be hidden by a webclip's stale cache.
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}
