"""Anesthesia drug sheet hub route."""

from __future__ import annotations

from contextlib import suppress

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.anesthesia_sheet import STOCK_OPTIONS, AnesthSpecies, calculate
from app.calculators.engine import WeightUnit
from app.routers._form_parsing import parse_positive_float

router = APIRouter()

_DOG_OPIOIDS = ["Hydromorphone", "Methadone", "Butorphanol", "Buprenorphine"]
_DOG_SEDATIVES = ["Dexmedetomidine", "Acepromazine", "Midazolam"]
_DOG_INDUCTION = ["Propofol", "Alfaxalone"]
_CAT_OPIOIDS = ["Buprenorphine", "Methadone", "Butorphanol", "Hydromorphone"]
_CAT_SEDATIVES = ["Dexmedetomidine", "Midazolam", "Acepromazine"]
_CAT_INDUCTION = ["Alfaxalone", "Propofol"]


def _compute(weight_value, weight_unit, species, patient_name, patient_age, chosen_stocks=None):
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB
    try:
        sp = AnesthSpecies(species)
    except ValueError:
        sp = AnesthSpecies.DOG
    return calculate(
        weight_value,
        wu,
        sp,
        patient_name.strip(),
        patient_age.strip(),
        chosen_stocks=chosen_stocks,
    )


def _defaults(species: str):
    if species == "cat":
        return _CAT_OPIOIDS, _CAT_SEDATIVES, _CAT_INDUCTION
    return _DOG_OPIOIDS, _DOG_SEDATIVES, _DOG_INDUCTION


def _inject_chosen_doses(result, chosen_doses: dict[str, float]):
    """Inject user-chosen doses into DrugLine objects."""
    for d in result.premed_opioids + result.premed_sedatives + result.induction_drugs:
        key = f"dose_{d.name.lower().replace(' ', '_')}"
        if key in chosen_doses and chosen_doses[key] > 0:
            # Convert from display units back to mg/kg if needed
            raw = chosen_doses[key] / d.dose_display_multiplier
            # Clamp to published range
            raw = max(d.dose_mg_per_kg_low, min(d.dose_mg_per_kg_high, raw))
            d.chosen_dose_mg_per_kg = raw


@router.get("/anesthesia", response_class=HTMLResponse)
async def anesthesia_page(request: Request, species: str = "dog"):
    # The species radios in the worksheet template point at this route
    # via hx-get="/anesthesia" + hx-target="body" + hx-swap="outerHTML",
    # so toggling species is a full page reload at the new species with
    # everything else (weight, picker selections, result panel) reset
    # to defaults. That's the safety design: a species change in real
    # practice means a different patient or a corrected chart, never
    # "I want to see what my dog state looks like as a cat." A blank
    # slate is the only state guaranteed to be free of dog-defaults
    # bleeding into cat-defaults via in-place DOM preservation.
    #
    # Compute with a placeholder weight so the sidebar (drug catalog,
    # dose ranges) can render its checkboxes — those don't depend on
    # patient weight. The main sheet wrapper renders the "Awaiting
    # input" placeholder until the user enters a real weight via the
    # form; see anesthesia_hub.html's `weight_provided` conditional.
    templates = request.app.state.templates
    species_normalized = species if species in ("dog", "cat") else "dog"
    result = _compute(1.0, "kg", species_normalized, "", "")
    opioids, sedatives, induction = _defaults(species_normalized)
    return templates.TemplateResponse(
        "anesthesia_hub.html",
        {
            "request": request,
            "result": result,
            "weight_value": "",
            "weight_unit": "lb",
            "patient_name": "",
            "patient_age": "",
            "selected_opioids": opioids,
            "selected_sedatives": sedatives,
            "selected_induction": induction,
            "active_tab": "preop",
            "weight_provided": False,
            "stock_options": STOCK_OPTIONS,
        },
    )


@router.post("/anesthesia/compute", response_class=HTMLResponse)
async def anesthesia_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    patient_name: str = Form(""),
    patient_age: str = Form(""),
    sel_opioid: list[str] = Form(default=[]),
    sel_sedative: list[str] = Form(default=[]),
    sel_induction: list[str] = Form(default=[]),
    active_tab: str = Form("preop"),
):
    templates = request.app.state.templates

    # Normalize active_tab to one of the known values so a malformed
    # form post can't break the template.
    if active_tab not in ("preop", "intraop"):
        active_tab = "preop"

    # Anesthesia worksheet: every dose on the sheet scales with weight. If the
    # field is empty or partial (mid-typing), render the placeholder rather
    # than a sheet from a stale weight — that would be a dangerous source
    # of dosing error.
    weight_numeric = parse_positive_float(weight_value)
    if weight_numeric is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_id": "anesthesia-sheet-wrapper",
                "placeholder_message": ("Enter a valid patient weight to generate the drug sheet."),
            },
        )

    # Collect any chosen stock-concentration fields (stock_hydromorphone,
    # stock_midazolam, etc.) and any chosen dose fields (dose_*).
    # Stock choices must be passed to calculate() BEFORE the result is
    # computed because they change the bag-volume and prep-recipe math.
    # Dose choices are applied after compute by adjusting the chosen
    # value on each DrugLine.
    form_data = await request.form()
    chosen_doses: dict[str, float] = {}
    chosen_stocks: dict[str, float] = {}
    for key, val in form_data.items():
        if not val:
            continue
        if key.startswith("dose_"):
            with suppress(ValueError):
                chosen_doses[key] = float(val)
        elif key.startswith("stock_"):
            drug_key = key[len("stock_") :]
            if drug_key not in STOCK_OPTIONS:
                continue
            try:
                candidate = float(val)
            except ValueError:
                continue
            # Only accept values that are an actual option for this drug.
            # Defense in depth: a stale tab or adversarial post can't
            # smuggle an arbitrary concentration into the math.
            valid_values = {opt for opt, _label in STOCK_OPTIONS[drug_key]}
            if candidate in valid_values:
                chosen_stocks[drug_key] = candidate

    result = _compute(
        weight_numeric,
        weight_unit,
        species,
        patient_name,
        patient_age,
        chosen_stocks=chosen_stocks,
    )

    _inject_chosen_doses(result, chosen_doses)

    opioids, sedatives, induction = _defaults(species)
    selected_opioids = sel_opioid if sel_opioid else opioids
    selected_sedatives = sel_sedative if sel_sedative else sedatives
    selected_induction = sel_induction if sel_induction else induction

    return templates.TemplateResponse(
        "partials/anesthesia_sheet.html",
        {
            "request": request,
            "result": result,
            "weight_value": weight_value,
            "weight_unit": weight_unit,
            "patient_name": patient_name,
            "patient_age": patient_age,
            "selected_opioids": selected_opioids,
            "selected_sedatives": selected_sedatives,
            "selected_induction": selected_induction,
            "active_tab": active_tab,
            "stock_options": STOCK_OPTIONS,
        },
    )
