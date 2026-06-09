"""Router for the multi-modal analgesia CRI builder."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.calculators.analgesia_builder import (
    ADJUNCT_SPECS,
    OPIOID_SPECS,
    AnalgesiaBuilderInputs,
    compute_analgesia,
)
from app.calculators.engine import Species, WeightUnit

router = APIRouter(tags=["analgesia-cri"])


# Default opioid for first-load — fentanyl is the most common ICU
# choice and matches the existing standalone /fentanyl page so users
# moving between the two see the same default.
DEFAULT_OPIOID_SLUG = "fentanyl"


def _default_doses_and_concentrations() -> tuple[dict[str, float], dict[str, float]]:
    """Build the default doses and concentrations dicts. Used by the
    GET handler to populate the form, and by the POST handler as a
    fallback when the form omits values for a drug (a freshly toggled-
    on drug whose field hasn't been touched)."""
    doses: dict[str, float] = {}
    concentrations: dict[str, float] = {}
    for spec in OPIOID_SPECS + ADJUNCT_SPECS:
        doses[spec.slug] = spec.default_dose
        concentrations[spec.slug] = spec.default_concentration_ug_per_ml
    return doses, concentrations


def _dose_range_summary(spec) -> str:  # type: ignore[no-untyped-def]
    """Pre-build a human-readable per-species range string for the
    form template. Keeps Jinja from needing access to the Species
    enum, and lets the per-drug card show "Dogs 2–10, Cats 2–10
    µg/kg/hr" inline."""
    parts = []
    dog = spec.dose_ranges.get(Species.DOG)
    cat = spec.dose_ranges.get(Species.CAT)
    if dog:
        parts.append(f"Dogs {dog.min}–{dog.max}")
    if cat:
        parts.append(f"Cats {cat.min}–{cat.max}")
    if not parts:
        return ""
    return ", ".join(parts) + f" {spec.dose_unit.value}"


def _all_dose_range_summaries() -> dict[str, str]:
    return {
        spec.slug: _dose_range_summary(spec)
        for spec in OPIOID_SPECS + ADJUNCT_SPECS
    }


@router.get("/analgesia-cri", response_class=HTMLResponse)
def get_analgesia_builder(
    request: Request,
    prep_mode: str = "per_drug",
    opioid: str = DEFAULT_OPIOID_SLUG,
    adjuncts: str = "",
) -> HTMLResponse:
    """Render the analgesia builder form with default state.

    Query parameters allow pre-selection of state — used by the
    /mlk redirect to drop users into combined-bag mode with the MLK
    protocol (morphine + ketamine + lidocaine) preselected:

      /analgesia-cri?prep_mode=combined_bag&opioid=morphine&adjuncts=ketamine,lidocaine

    The params are advisory — if an opioid slug is unknown it falls
    back to the default; unknown adjunct slugs are silently dropped.
    """
    templates = request.app.state.templates
    doses, concentrations = _default_doses_and_concentrations()

    # Normalize prep_mode — only two valid values.
    normalized_prep = "combined_bag" if prep_mode == "combined_bag" else "per_drug"

    # Validate opioid slug — must be a known opioid, or the "none"
    # sentinel for opioid-free composition. Unknown values fall back
    # to the default (fentanyl).
    valid_opioid_slugs = {s.slug for s in OPIOID_SPECS} | {"none"}
    normalized_opioid = opioid if opioid in valid_opioid_slugs else DEFAULT_OPIOID_SLUG

    # Parse adjuncts list — comma-separated. Filter to known adjuncts.
    valid_adjunct_slugs = {s.slug for s in ADJUNCT_SPECS}
    requested_adjuncts = tuple(
        slug.strip()
        for slug in adjuncts.split(",")
        if slug.strip() in valid_adjunct_slugs
    )

    return templates.TemplateResponse(
        "analgesia_cri.html",
        {
            "request": request,
            "opioid_specs": OPIOID_SPECS,
            "adjunct_specs": ADJUNCT_SPECS,
            "default_opioid_slug": normalized_opioid,
            "default_adjunct_slugs": requested_adjuncts,
            "weight_value": "",
            "weight_unit": "lb",
            "species": "dog",
            "prep_mode": normalized_prep,
            "bag_volume_ml": 500.0,
            "shared_pump_rate_ml_per_kg_per_hr": 1.0,
            "doses": doses,
            "concentrations": concentrations,
            "dose_range_summaries": _all_dose_range_summaries(),
            "result": None,
            "is_htmx_response": False,
        },
    )


def _parse_float(raw: str, fallback: float) -> float:
    """Coerce a form string to float, falling back on parse failure.

    Form fields hold strings; users may type "0.04" or paste a number
    with stray whitespace. The fallback path covers blank fields (a
    fresh toggle whose dose hasn't been edited) and malformed input.
    Validation of zero/negative values happens later in
    compute_analgesia.
    """
    if raw is None:
        return fallback
    s = raw.strip()
    if not s:
        return fallback
    try:
        return float(s)
    except ValueError:
        return fallback


@router.post("/analgesia-cri/compute", response_class=HTMLResponse)
async def post_analgesia_builder(request: Request) -> HTMLResponse:
    """Process the form and render the result panel.

    Form shape (Phase 1):
      weight_value, weight_unit, species
      opioid_slug                       (one of fentanyl/morphine/hydromorphone)
      dose_<drug_slug>                  (per-drug dose)
      concentration_<drug_slug>         (per-drug concentration in µg/mL)
      adjunct_<drug_slug>               (checkbox: "on" = selected)

    The drug-specific fields use a slug-stem pattern so adjuncts can
    grow in Phase 2 (lidocaine, dexmedetomidine) without changing the
    handler shape.
    """
    templates = request.app.state.templates
    form = await request.form()

    weight_raw = str(form.get("weight_value", "") or "")
    weight_unit_raw = str(form.get("weight_unit", "lb") or "lb")
    species_raw = str(form.get("species", "dog") or "dog")
    opioid_slug = str(form.get("opioid_slug", DEFAULT_OPIOID_SLUG) or DEFAULT_OPIOID_SLUG)
    prep_mode_raw = str(form.get("prep_mode", "per_drug") or "per_drug")
    # Only two valid prep_mode values; anything else falls back to
    # per_drug. The form radio is the only legitimate source.
    prep_mode = "combined_bag" if prep_mode_raw == "combined_bag" else "per_drug"

    weight_value = _parse_float(weight_raw, 0.0)
    weight_unit = WeightUnit.LB if weight_unit_raw == "lb" else WeightUnit.KG
    species = Species.CAT if species_raw == "cat" else Species.DOG

    # Combined-bag-mode inputs. Always parsed (so the form can carry
    # the user's chosen values across submissions even while in
    # per-drug mode), but only used by compute_analgesia in
    # combined-bag mode.
    bag_volume_ml = _parse_float(str(form.get("bag_volume_ml", "500") or "500"), 500.0)
    shared_pump_rate = _parse_float(
        str(form.get("shared_pump_rate_ml_per_kg_per_hr", "1.0") or "1.0"), 1.0
    )

    # Collect per-drug doses and concentrations. Pull defaults so a
    # newly toggled-on adjunct whose field is blank still computes.
    default_doses, default_concentrations = _default_doses_and_concentrations()
    doses: dict[str, float] = {}
    concentrations: dict[str, float] = {}
    for spec in OPIOID_SPECS + ADJUNCT_SPECS:
        dose_field = f"dose_{spec.slug}"
        conc_field = f"concentration_{spec.slug}"
        doses[spec.slug] = _parse_float(
            str(form.get(dose_field, "") or ""), default_doses[spec.slug]
        )
        concentrations[spec.slug] = _parse_float(
            str(form.get(conc_field, "") or ""),
            default_concentrations[spec.slug],
        )

    # Adjuncts: checkbox presence indicates selection. HTML checkboxes
    # only submit a value when checked; an absent field means unchecked.
    adjunct_slugs = tuple(
        spec.slug
        for spec in ADJUNCT_SPECS
        if form.get(f"adjunct_{spec.slug}") is not None
    )

    inputs = AnalgesiaBuilderInputs(
        weight_value=weight_value,
        weight_unit=weight_unit,
        species=species,
        opioid_slug=opioid_slug,
        adjunct_slugs=adjunct_slugs,
        doses=doses,
        concentrations_ug_per_ml=concentrations,
        prep_mode=prep_mode,
        bag_volume_ml=bag_volume_ml,
        shared_pump_rate_ml_per_kg_per_hr=shared_pump_rate,
    )
    result = compute_analgesia(inputs)

    # If this is an HTMX request, render only the result partial so
    # the form stays in place. Otherwise render the full page so a
    # direct POST (e.g., from a bookmark or share link) still works.
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return templates.TemplateResponse(
            "partials/analgesia_result.html",
            {
                "request": request,
                "result": result,
                "is_htmx_response": True,
            },
        )

    return templates.TemplateResponse(
        "analgesia_cri.html",
        {
            "request": request,
            "opioid_specs": OPIOID_SPECS,
            "adjunct_specs": ADJUNCT_SPECS,
            "default_opioid_slug": opioid_slug,
            "default_adjunct_slugs": adjunct_slugs,
            "weight_value": weight_raw,
            "weight_unit": weight_unit_raw,
            "species": species_raw,
            "prep_mode": prep_mode,
            "bag_volume_ml": bag_volume_ml,
            "shared_pump_rate_ml_per_kg_per_hr": shared_pump_rate,
            "doses": doses,
            "concentrations": concentrations,
            "dose_range_summaries": _all_dose_range_summaries(),
            "result": result,
            "is_htmx_response": False,
        },
    )
