"""Hydromorphone CRI calculator route.

Form contract (post-redesign):
    Required:  weight_value, weight_unit, species
    Optional:  stock_mg_per_ml (defaults to 2 mg/mL if absent or invalid)

The cri_rate input was removed in the redesign. The species-specific
default dose (dog 0.03, cat 0.01 mg/kg/hr) drives the headline, and the
full titration ladder is rendered in the result so the clinician can see
every step.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import WeightUnit
from app.calculators.hydromorphone_cri import (
    HYDROMORPHONE_STOCK_MG_PER_ML,
    HYDROMORPHONE_STOCK_OPTIONS,
    HydromorphoneInputs,
    HydromorphoneSpecies,
    calculate,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _resolve_stock(raw: str) -> float:
    """Parse the stock-concentration form field, falling back to default.

    The default (2 mg/mL) is used when the field is missing, empty, not
    parseable, or not one of the known stock options. This is defense
    in depth: an unexpected value from a stale browser tab or adversarial
    submission shouldn't render a misleading pump-rate computation.
    """
    parsed = parse_positive_float(raw) if raw else None
    if parsed is None:
        return HYDROMORPHONE_STOCK_MG_PER_ML
    valid_options = {opt for opt, _label in HYDROMORPHONE_STOCK_OPTIONS}
    return parsed if parsed in valid_options else HYDROMORPHONE_STOCK_MG_PER_ML


@router.get("/hydromorphone-cri", response_class=HTMLResponse)
async def hydromorphone_page(request: Request) -> HTMLResponse:
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "hydromorphone_cri.html",
        {
            "request": request,
            "result": None,
            "weight_value": "",
            "weight_unit": "lb",
            "species": "dog",
            "stock_mg_per_ml": HYDROMORPHONE_STOCK_MG_PER_ML,
            "stock_options": HYDROMORPHONE_STOCK_OPTIONS,
        },
    )


@router.post("/hydromorphone-cri/compute", response_class=HTMLResponse)
async def hydromorphone_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    stock_mg_per_ml: str = Form(""),
) -> HTMLResponse:
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )

    try:
        species_enum = HydromorphoneSpecies(species)
    except ValueError:
        species_enum = HydromorphoneSpecies.DOG

    try:
        weight_unit_enum = WeightUnit(weight_unit)
    except ValueError:
        weight_unit_enum = WeightUnit.LB

    stock = _resolve_stock(stock_mg_per_ml)

    inputs = HydromorphoneInputs(
        weight_value=weight,
        weight_unit=weight_unit_enum,
        species=species_enum,
        stock_mg_per_ml=stock,
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/hydromorphone_cri_result.html",
        {
            "request": request,
            "result": result,
            "stock_options": HYDROMORPHONE_STOCK_OPTIONS,
        },
    )
