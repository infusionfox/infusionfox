"""Calcium gluconate (hyperkalemia membrane stabilization) calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.ca_gluconate import (
    CA_GLUCONATE_CATALOG_ENTRY,
    DOSE_DEFAULT_ML_PER_KG,
    DURATION_DEFAULT_MIN,
    CaGluconateInputs,
    CaGluconateSpecies,
    compute_ca_gluconate,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> CaGluconateSpecies:
    try:
        return CaGluconateSpecies(value)
    except ValueError:
        return CaGluconateSpecies.CAT


@router.get("/ca-gluconate-hyperK", response_class=HTMLResponse)
async def ca_gluconate_page(request: Request):
    templates = request.app.state.templates
    inputs = CaGluconateInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=CaGluconateSpecies.CAT,
        dose_ml_per_kg=DOSE_DEFAULT_ML_PER_KG,
        duration_min=DURATION_DEFAULT_MIN,
    )
    return templates.TemplateResponse(
        "ca_gluconate.html",
        {
            "request": request,
            "meta": CA_GLUCONATE_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
        },
    )


@router.post("/ca-gluconate-hyperK/compute", response_class=HTMLResponse)
async def ca_gluconate_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("cat"),
    dose_ml_per_kg: str = Form(str(DOSE_DEFAULT_ML_PER_KG)),
    duration_min: str = Form(str(DURATION_DEFAULT_MIN)),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    dose = parse_float_with_default(dose_ml_per_kg, DOSE_DEFAULT_ML_PER_KG)
    duration = parse_float_with_default(duration_min, DURATION_DEFAULT_MIN)
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = CaGluconateInputs(
        weight_value=weight,
        weight_unit=wu,
        species=_coerce_species(species),
        dose_ml_per_kg=dose,
        duration_min=duration,
    )
    result = compute_ca_gluconate(inputs)
    return templates.TemplateResponse(
        "partials/ca_gluconate_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
