"""Insulin + dextrose for hyperkalemia calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.insulin_dextrose import (
    DEXTROSE_RATIO_DEFAULT,
    INSULIN_DEXTROSE_CATALOG_ENTRY,
    INSULIN_DOSE_DEFAULT_U_PER_KG,
    InsulinDextroseInputs,
    InsulinDextroseSpecies,
    compute_insulin_dextrose,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> InsulinDextroseSpecies:
    try:
        return InsulinDextroseSpecies(value)
    except ValueError:
        return InsulinDextroseSpecies.CAT


@router.get("/insulin-dextrose-hyperK", response_class=HTMLResponse)
async def insulin_dextrose_page(request: Request):
    templates = request.app.state.templates
    inputs = InsulinDextroseInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=InsulinDextroseSpecies.CAT,
        insulin_dose_u_per_kg=INSULIN_DOSE_DEFAULT_U_PER_KG,
        dextrose_g_per_u=DEXTROSE_RATIO_DEFAULT,
    )
    return templates.TemplateResponse(
        "insulin_dextrose.html",
        {
            "request": request,
            "meta": INSULIN_DEXTROSE_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
        },
    )


@router.post("/insulin-dextrose-hyperK/compute", response_class=HTMLResponse)
async def insulin_dextrose_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("cat"),
    insulin_dose_u_per_kg: str = Form(str(INSULIN_DOSE_DEFAULT_U_PER_KG)),
    dextrose_g_per_u: str = Form(str(DEXTROSE_RATIO_DEFAULT)),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    dose = parse_float_with_default(insulin_dose_u_per_kg, INSULIN_DOSE_DEFAULT_U_PER_KG)
    dex_ratio = parse_float_with_default(dextrose_g_per_u, DEXTROSE_RATIO_DEFAULT)
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = InsulinDextroseInputs(
        weight_value=weight,
        weight_unit=wu,
        species=_coerce_species(species),
        insulin_dose_u_per_kg=dose,
        dextrose_g_per_u=dex_ratio,
    )
    result = compute_insulin_dextrose(inputs)
    return templates.TemplateResponse(
        "partials/insulin_dextrose_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
