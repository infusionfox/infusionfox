"""
Search routes for InfusionFox.

Three endpoints:

  GET  /search                  - Full results page (bookmarkable)
  GET  /search/dropdown         - HTMX fragment for the header widget
                                  dropdown (top 5-7 results)
  GET  /api/search.json         - JSON API for any external client

The page and dropdown render the same underlying SearchResult list
through different templates. The JSON endpoint exists primarily for
programmatic access (browser bookmarklets, future mobile clients,
etc.) and is not consumed by the in-app widget.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.db.session import engine
from app.search.query import search

router = APIRouter()

# Reasonable caps. The header dropdown shows the top few; the full
# page shows up to 50.
_DROPDOWN_LIMIT = 7
_PAGE_LIMIT = 50


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = Query("", max_length=200)):
    """Full search results page. Bookmarkable URL with ?q=<query>."""
    templates = request.app.state.templates
    query = (q or "").strip()
    results = search(engine, query, limit=_PAGE_LIMIT) if query else []
    grouped = _group_by_display_category(results)

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": query,
            "results": results,
            "grouped": grouped,
            "result_count": len(results),
        },
    )


@router.get("/search/dropdown", response_class=HTMLResponse)
async def search_dropdown(request: Request, q: str = Query("", max_length=200)):
    """HTMX fragment for the header widget. Returns the dropdown list HTML."""
    templates = request.app.state.templates
    query = (q or "").strip()
    results = search(engine, query, limit=_DROPDOWN_LIMIT) if query else []

    return templates.TemplateResponse(
        "partials/search_dropdown.html",
        {
            "request": request,
            "query": query,
            "results": results,
            "see_all_url": f"/search?q={query}" if query else "/search",
        },
    )


@router.get("/api/search.json")
async def search_json(q: str = Query("", max_length=200), limit: int = Query(10, ge=1, le=50)):
    """JSON API. Returns the same data the templates render."""
    query = (q or "").strip()
    results = search(engine, query, limit=limit) if query else []
    return JSONResponse(
        {
            "query": query,
            "count": len(results),
            "results": [
                {
                    "slug": r.slug,
                    "type": r.type,
                    "title": r.title,
                    "url": r.url,
                    "category": r.category,
                    "display_category": r.display_category,
                    "blurb": r.blurb,
                    "rank": r.rank,
                }
                for r in results
            ],
        }
    )


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------


def _group_by_display_category(results):
    """Group results by display_category, preserving first-seen order."""
    groups: dict[str, list] = {}
    for r in results:
        groups.setdefault(r.display_category or r.category or "Other", []).append(r)
    return groups
