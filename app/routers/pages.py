"""Static / landing pages."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.nav import calculator_nav_index, hub_nav_index, nav_index

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    templates = request.app.state.templates

    # Counts and a handful of representative entries to populate the
    # "What's inside" section. Counts are computed from the canonical
    # nav indexes so they stay in sync as the catalog grows. Highlights
    # are explicit so the section doesn't surface random alphabetical
    # picks; these are the entries we'd point a new user to first.
    calc_groups = calculator_nav_index()
    hub_groups = hub_nav_index()
    calc_count = sum(len(entries) for entries in calc_groups.values())
    # The anesthesia worksheet lives in hub_nav_index() because it sits
    # in the /hubs catalog, but on the homepage it gets its own
    # callout column rather than being a "reference hub". Subtract it
    # from the hub count so the displayed number matches the columns
    # below it (which describe decision-support workflows and scoring
    # tools, not the worksheet).
    hub_count = sum(len(entries) for entries in hub_groups.values())
    for entries in hub_groups.values():
        for entry in entries:
            if entry.href == "/anesthesia":
                hub_count -= 1
                break

    def _find(groups: dict, slug_suffix: str) -> dict | None:
        """Return the first nav entry whose href ends with the suffix.
        Returns None if not found so the template can degrade gracefully."""
        for entries in groups.values():
            for entry in entries:
                if entry.href.endswith(slug_suffix):
                    return entry
        return None

    calc_highlights = [
        e
        for e in (
            _find(calc_groups, "/norepinephrine"),
            _find(calc_groups, "/fluid-therapy"),
            _find(calc_groups, "/tube-feeding"),
        )
        if e is not None
    ]
    hub_highlights = [
        e
        for e in (
            _find(hub_groups, "/anaphylaxis"),
            _find(hub_groups, "/shock"),
            _find(hub_groups, "/dka"),
        )
        if e is not None
    ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "nav_groups": nav_index(),
            "calc_count": calc_count,
            "hub_count": hub_count,
            "calc_highlights": calc_highlights,
            "hub_highlights": hub_highlights,
        },
    )


@router.get("/calculators", response_class=HTMLResponse)
async def catalog(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "catalog.html",
        {
            "request": request,
            "nav_groups": calculator_nav_index(),
            "page_title": "Calculators",
            "page_eyebrow": "Catalog",
            "page_intro": (
                "Dose, rate, and bag-prep math. Enter a patient weight (or "
                "the relevant inputs) and the calculator returns numbers "
                "you can verify against your own. For clinical workflows, "
                "decision support, and scoring tools, see Reference hubs."
            ),
        },
    )


@router.get("/hubs", response_class=HTMLResponse)
async def hubs_catalog(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "catalog.html",
        {
            "request": request,
            "nav_groups": hub_nav_index(),
            "page_title": "Reference hubs",
            "page_eyebrow": "Reference",
            "page_intro": (
                "Clinical workflows, decision support, and scoring tools. "
                "Each hub gathers the relevant calculators, dose tables, "
                "and decision points for a single presentation or test. "
                "For dose / rate / bag-prep math, see Calculators."
            ),
        },
    )


@router.get("/disclaimer", response_class=HTMLResponse)
async def disclaimer(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("disclaimer.html", {"request": request})


@router.get("/install", response_class=HTMLResponse)
async def install(request: Request):
    """Install instructions for adding infusionfox to a home screen."""
    templates = request.app.state.templates
    return templates.TemplateResponse("install.html", {"request": request})
