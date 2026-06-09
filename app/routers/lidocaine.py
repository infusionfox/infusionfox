"""Lidocaine CRI calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.lidocaine import (
    LIDOCAINE_CATALOG_ENTRY,
    LIDOCAINE_DEFAULT_DOSE_MG_PER_KG_PER_HR,
    LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR,
    LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR,
    LIDOCAINE_PLUMBS_HIGH_COMBO_MG_PER_KG_PER_HR,
    LIDOCAINE_STOCK_MG_PER_ML,
    LidocaineDoseUnit,
    LidocaineInputs,
    LidocaineSpecies,
    compute_lidocaine,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _coerce_dose_unit(value: str) -> LidocaineDoseUnit:
    try:
        return LidocaineDoseUnit(value)
    except ValueError:
        return LidocaineDoseUnit.MG_PER_KG_PER_HR


@router.get("/lidocaine", response_class=HTMLResponse)
async def lidocaine_page(request: Request):
    templates = request.app.state.templates
    inputs = LidocaineInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        dose_value=LIDOCAINE_DEFAULT_DOSE_MG_PER_KG_PER_HR,
        dose_unit=LidocaineDoseUnit.MG_PER_KG_PER_HR,
        species=LidocaineSpecies.DOG,
    )
    return templates.TemplateResponse(
        "lidocaine.html",
        {
            "request": request,
            "meta": LIDOCAINE_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "stock_mg_per_ml": LIDOCAINE_STOCK_MG_PER_ML,
            "dose_min": LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR,
            "dose_max": LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR,
            "dose_high_combo": LIDOCAINE_PLUMBS_HIGH_COMBO_MG_PER_KG_PER_HR,
        },
    )


@router.post("/lidocaine/compute", response_class=HTMLResponse)
async def lidocaine_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    dose_value: str = Form(""),
    dose_unit: str = Form("mg/kg/hr"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    dose = parse_positive_float(dose_value)
    if weight is None or dose is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = LidocaineInputs(
        weight_value=weight,
        weight_unit=wu,
        dose_value=dose,
        dose_unit=_coerce_dose_unit(dose_unit),
        species=LidocaineSpecies.DOG,
    )
    result = compute_lidocaine(inputs)
    return templates.TemplateResponse(
        "partials/lidocaine_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
