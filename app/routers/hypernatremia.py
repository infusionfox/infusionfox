"""Hypernatremia calculator routes (one-off, not in engine-drug routes)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.hypernatremia import (
    DEFAULT_PREVIOUS_NA,
    DEFAULT_REPLACEMENT_HOURS,
    HYPERNA_CATALOG_ENTRY,
    HyperNaInputs,
    HyperNaMechanism,
    compute_hypernatremia,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


@router.get("/hypernatremia", response_class=HTMLResponse)
async def hypernatremia_page(request: Request):
    templates = request.app.state.templates
    inputs = HyperNaInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        patient_na_meq_per_l=160.0,
        previous_na_meq_per_l=DEFAULT_PREVIOUS_NA,
        mechanism=HyperNaMechanism.PURE_WATER_LOSS,
        replacement_hours=DEFAULT_REPLACEMENT_HOURS,
        maintenance_ml_per_hr=0.0,
    )
    return templates.TemplateResponse(
        "hypernatremia.html",
        {
            "request": request,
            "meta": HYPERNA_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "DEFAULT_PREVIOUS_NA": DEFAULT_PREVIOUS_NA,
        },
    )


@router.post("/hypernatremia/compute", response_class=HTMLResponse)
async def hypernatremia_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    patient_na_meq_per_l: str = Form(""),
    previous_na_meq_per_l: str = Form(str(DEFAULT_PREVIOUS_NA)),
    mechanism: str = Form("pure_water_loss"),
    replacement_hours: str = Form(str(DEFAULT_REPLACEMENT_HOURS)),
    maintenance_ml_per_hr: str = Form("0.0"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    patient_na = parse_positive_float(patient_na_meq_per_l)
    if weight is None or patient_na is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    previous_na = parse_float_with_default(previous_na_meq_per_l, DEFAULT_PREVIOUS_NA)
    replace_hr = parse_float_with_default(replacement_hours, DEFAULT_REPLACEMENT_HOURS)
    maint_rate = parse_float_with_default(maintenance_ml_per_hr, 0.0)
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB
    try:
        mech = HyperNaMechanism(mechanism)
    except ValueError:
        mech = HyperNaMechanism.PURE_WATER_LOSS

    inputs = HyperNaInputs(
        weight_value=weight,
        weight_unit=wu,
        patient_na_meq_per_l=patient_na,
        previous_na_meq_per_l=previous_na,
        mechanism=mech,
        replacement_hours=replace_hr,
        maintenance_ml_per_hr=maint_rate,
    )
    result = compute_hypernatremia(inputs)

    return templates.TemplateResponse(
        "partials/hypernatremia_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
