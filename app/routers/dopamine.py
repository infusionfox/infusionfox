"""Dopamine preparation worksheet, the 6×kg method.

This calculator is dopamine-specific (not in the generic engine-drug routes).
The standard SINGLE_DRUG_CRI form takes a fixed concentration as input; the
6×kg method instead derives concentration from patient weight, so the page
layout and inputs are different.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.dopamine_prep import (
    DOPAMINE_PREP_CATALOG_ENTRY,
    DopaminePrepInputs,
    DopamineSpecies,
    compute_dopamine_preparation,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


@router.get("/dopamine", response_class=HTMLResponse)
async def dopamine_page(request: Request):
    templates = request.app.state.templates
    inputs = DopaminePrepInputs(
        species=DopamineSpecies.DOG,
        weight_value=1.0,  # placeholder, not displayed
        weight_unit=WeightUnit.LB,
        target_dose_ug_per_kg_per_min=5.0,
    )
    return templates.TemplateResponse(
        "dopamine.html",
        {
            "request": request,
            "meta": DOPAMINE_PREP_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
        },
    )


@router.post("/dopamine/compute", response_class=HTMLResponse)
async def dopamine_compute(
    request: Request,
    species: str = Form("dog"),
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    target_dose_ug_per_kg_per_min: str = Form(""),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    target_dose = parse_positive_float(target_dose_ug_per_kg_per_min)
    if weight is None or target_dose is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        sp = DopamineSpecies(species)
    except ValueError:
        sp = DopamineSpecies.DOG
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB
    inputs = DopaminePrepInputs(
        species=sp,
        weight_value=weight,
        weight_unit=wu,
        target_dose_ug_per_kg_per_min=target_dose,
    )
    result = compute_dopamine_preparation(inputs)
    return templates.TemplateResponse(
        "partials/dopamine_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
