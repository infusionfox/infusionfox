"""Mannitol osmotherapy calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import WeightUnit
from app.calculators.mannitol import (
    INDICATION_PROFILES,
    MANNITOL_CATALOG_ENTRY,
    MannitolIndication,
    MannitolInputs,
    compute_mannitol,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


@router.get("/mannitol", response_class=HTMLResponse)
async def mannitol_page(request: Request):
    templates = request.app.state.templates
    # Initial GET renders empty input fields and no computed result.
    # Defaults shown in the form are for display only; the form will
    # not produce a result until the user enters a weight (Safety Rule
    # #8).
    inputs = MannitolInputs(indication=MannitolIndication.CEREBRAL_EDEMA)
    return templates.TemplateResponse(
        "mannitol.html",
        {
            "request": request,
            "meta": MANNITOL_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "dose_value": "",
            "duration_value": "",
            "indication_profiles": INDICATION_PROFILES,
        },
    )


@router.post("/mannitol/compute", response_class=HTMLResponse)
async def mannitol_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    indication: str = Form("cerebral_edema"),
    dose_g_per_kg: str = Form(""),
    concentration_percent: str = Form("20"),
    duration_min: str = Form(""),
):
    templates = request.app.state.templates

    # Weight is required. If missing, render the empty-state placeholder.
    weight_val = parse_positive_float(weight_value)
    dose_val = parse_positive_float(dose_g_per_kg)
    duration_val_float = parse_positive_float(duration_min)
    if weight_val is None or dose_val is None or duration_val_float is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": (
                    "Enter patient weight, dose, and infusion duration "
                    "to see the result."
                ),
            },
        )

    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    try:
        ind = MannitolIndication(indication)
    except ValueError:
        ind = MannitolIndication.CEREBRAL_EDEMA

    try:
        conc_pct = int(concentration_percent)
        if conc_pct not in (20, 25):
            conc_pct = 20
    except (TypeError, ValueError):
        conc_pct = 20

    inputs = MannitolInputs(
        weight_value=weight_val,
        weight_unit=wu,
        indication=ind,
        dose_g_per_kg=dose_val,
        concentration_percent=conc_pct,
        duration_min=int(duration_val_float),
    )
    result = compute_mannitol(inputs)

    return templates.TemplateResponse(
        "partials/mannitol_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
