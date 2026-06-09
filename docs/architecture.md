# Architecture

A one-page orientation for a new engineer joining infusionfox.

## Stack

- **FastAPI** as the web framework. Routers live in `app/routers/` and are auto-discovered at startup by `app/routers/__init__.py` — see "Auto-discovery" below.
- **Jinja2** for server-rendered HTML. Templates in `app/templates/`. Result panels (the things HTMX swaps in) live in `app/templates/partials/`.
- **HTMX 2.0.2** for partial-page interactivity. There is no React, Vue, or build pipeline for the frontend. See `docs/htmx-patterns.md` for the swap-target conventions.
- **SQLite** with **Alembic** migrations. Schema lives in `app/db/models.py`. Currently used for disclaimer acceptances and feedback; auth and billing are being outsourced.
- **KaTeX** for math rendering, loaded via CDN. Worked-example formulas are server-rendered as LaTeX in `<template>` blocks and KaTeX-rendered client-side.
- **Docker** for deployment. Production flow is GitHub Actions → GHCR → Watchtower → Cloudflare Tunnel. See `DEPLOYMENT.md`.

The frontend deliberately avoids a JS framework. Pages are server-rendered HTML; HTMX handles partial swaps for calculator results and worksheet updates. This keeps the surface area small and removes a build step from the deploy.

## Request flow

For most calculators, the lifecycle is:

1. **GET `/<slug>`** — renders the full page shell (header, input form, empty result panel) with `app/templates/<slug>.html`. The result panel typically has `id="result-panel"` with a placeholder.
2. **POST `/<slug>/compute`** — the form submits via HTMX (`hx-post`, `hx-target="#result-panel"`, `hx-swap="outerHTML"`). The handler computes the result, then returns `app/templates/partials/<slug>_result.html` rendered with the result. HTMX swaps it into the page.
3. **Repeat** — typing into an input fires `hx-trigger="input changed delay:250ms, change, load"` which re-submits the form and re-swaps the result panel. Math is recomputed on every input change.

A few pages deviate:
- **Anesthesia worksheet** swaps a larger wrapper (`#anesthesia-sheet-wrapper`) because changes affect more than one section, and preserves the picker DOM via `hx-preserve`. See `docs/anesthesia-worksheet.md`.
- **Reference hubs** are static pages; no HTMX, no swap.
- **Learning module pages** are static articles + a JS-driven quiz; the quiz is client-side only, no server submission.

## Auto-discovery

`app/routers/__init__.py` walks `app/routers/`, imports every module, and registers any `router = APIRouter()` it finds. To add a new calculator page, you create the router file and that's it — no edit to `main.py`. The README's "Adding a new calculator" section covers the full recipe.

## Calculator engine vs. bespoke calculators

Two patterns:

**Engine-driven CRIs** (`app/calculators/engine.py` + `app/calculators/drugs.py`):

- The engine is a generic CRI calculator — given a `CalculatorConfig` (dose ranges, stock concentration, dilution options, species rules) plus patient weight and a chosen dose, it returns pump rates, dilution recipes, titration ladders, and prep instructions.
- One `CalculatorConfig` entry in `DRUGS` (`drugs.py`) per CRI drug. Norepi, epi, dopamine-CRI, dobutamine, fentanyl all use this.
- Use this pattern when the drug fits the standard "weight × dose / concentration = rate" pump-rate calculation and the only thing that varies between drugs is the dose range, stock, and species-specific cautions.
- One config = one calculator page (route, template, and `/learn/<slug>` article all wired automatically).

**Bespoke calculators** (`app/calculators/<name>.py`):

- Their own module + router + page template + result partial.
- Use this pattern when the math has structure that doesn't fit the engine: sliding scales (insulin, hypokalemia), multi-step prep (DKB, dopamine prep), scoring tools (Cushing's, Addison's, IRIS), or multi-output protocols (anesthesia worksheet).
- Each bespoke calculator has a `compute_<name>(inputs)` function returning a result dataclass with `valid: bool` and a `sources: tuple[Source, ...]`. The `valid` flag short-circuits the template — invalid inputs render an error panel instead of fake numbers.

When in doubt: if you can express the calculator as a `CalculatorConfig` row, do that. If you can't, write a bespoke module.

## Patterns shared across calculator types

A few patterns are project standards regardless of whether the calculator is engine-driven or bespoke. They show up wherever the conditions are met, and new calculators should follow them rather than rolling their own.

**Multi-concentration prep-card with disclosure.** Any calculator where a drug has multiple commonly-stocked concentrations (norepi, epi, dobutamine, dopamine-cri, fentanyl, hydromorphone CRI) uses the same UX: a prominent prep-card showing the current concentration in large font, with a "Use a different concentration" disclosure listing pump-safe alternatives. The router computes `default_preset` and `alt_presets` and passes them to the template; the template is uniform across all drugs. The undiluted-vial warning presets (12500 µg/mL dobutamine, 1000 µg/mL epi) are marked `pump_safe=False` on `ConcentrationPreset` and filtered out of the disclosure — they stay in the reference table as anchors but never as user-selectable options. Full details in `docs/htmx-patterns.md`.

**Worksheet per-drug concentration selectors.** The anesthesia worksheet picker offers compact per-drug `<select>` selectors next to each drug's dose input, scoped to drugs listed in `STOCK_OPTIONS` (`app/calculators/anesthesia_sheet.py`). The chosen concentration rides through `calculate()` via a `contextvars.ContextVar` so `_drug()` and emergency-drug call sites pick it up without threading a dict through 20 call sites. Validation rejects unknown values silently and falls back to defaults.

**Required form inputs must have non-empty defaults.** htmx 2.x silently blocks form submission when a required input is empty. Calculator forms must pre-fill every `required` input that isn't the patient's weight (which the user types) with a sensible default. `tests/test_form_defaults.py` enforces this across every calculator page.

**Calculators NEVER show output before the clinician enters values.** Hard safety rule. See CLAUDE.md non-negotiable #8 for the full statement and reference implementation. In summary: GET passes `result=None`; the page template gates on `{% if result %}` and falls back to `partials/_invalid_input_placeholder.html`; POST validates that required inputs are present and parseable and returns the placeholder when they aren't; form parameter defaults are `""`, not numeric sentinels; radios with semantically-valid zero values (e.g. mentation scores) start with nothing selected; `hx-trigger` never includes `load`. The canonical reference implementation is `app/routers/blood_gas.py` + `app/templates/blood_gas.html`.

## Source citations

Every numeric threshold, dose range, and scoring weight has a citation. Conventions:

- Each result dataclass exposes `sources: tuple[Source, ...]` which the template renders via `partials/_source_cite.html`.
- `SOURCES.md` tracks the canonical reference list and the per-calculator attribution table.
- Don't reproduce verbatim source text in user-facing strings; cite the source and write the note in your own words. See `SOURCES.md` for the policy.

## Database

Currently small. The main surviving tables once auth is outsourced will be disclaimer acceptances and feedback. Schema changes go through Alembic:

```bash
alembic revision --autogenerate -m "what changed"
alembic upgrade head
```

CI checks for schema drift via `alembic check`.

## Testing

`pytest` runs the full suite in ~10 seconds. The suite covers every calculator, the engine, every public GET route (integration smoke), Alembic schema sync, and template parseability. New code should come with new tests. See `CONTRIBUTING.md` for the testing discipline.

## Where things live

```
app/
  main.py                       # FastAPI app entry, mounts static + nav
  nav.py                        # Single source of truth for site navigation
  calculators/
    engine.py                   # Generic CRI engine
    drugs.py                    # CalculatorConfig per CRI drug
    utilities.py                # BSA, concentration converters
    <name>.py                   # Bespoke calculators (one per file)
    anesthesia_sheet.py         # The big one — see anesthesia-worksheet.md
  routers/
    __init__.py                 # Auto-discovery
    pages.py                    # Landing, catalogs, disclaimer
    calculators.py              # engine-drug routes, dilution helper
    <name>.py                   # One per calculator/hub
  templates/
    base.html                   # Site chrome + KaTeX + worked-example handler
    <name>.html                 # Calculator pages
    partials/<name>_result.html # HTMX swap targets
    learn/                      # Learn module index + module pages
    style-guide.md (in docs/)   # Copy style
  static/css/app.css            # Single stylesheet
  db/models.py                  # SQLAlchemy models
content/
  drugs/<slug>.md               # Articles (rendered at /learn/<slug>)
docs/
  architecture.md               # This file
  anesthesia-worksheet.md       # Anesthesia worksheet deep-dive
  htmx-patterns.md              # Swap-target conventions, hx-preserve, worked-example mechanism
  style-guide.md                # Copy style
```
