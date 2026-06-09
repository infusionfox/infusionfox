"""Methadone calculator route."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import WeightUnit
from app.calculators.methadone import (
    METHADONE_STOCK_MG_PER_ML,
    MethadoneInputs,
    MethadoneSpecies,
    calculate,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


@router.get("/methadone", response_class=HTMLResponse)
async def methadone_page(request: Request):
    # Initial page load: present the calculator with no patient weight
    # and no precomputed result. The user must enter a weight before any
    # dose appears. This prevents accidentally accepting the previous
    # patient's default — a safety measure.
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "methadone.html",
        {
            "request": request,
            "result": None,
            "weight_value": "",
            "weight_unit": "lb",
        },
    )


@router.post("/methadone/compute", response_class=HTMLResponse)
async def methadone_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    stock_mg_per_ml: str = Form(str(METHADONE_STOCK_MG_PER_ML)),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    stock = parse_positive_float(stock_mg_per_ml)
    if weight is None or stock is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB
    try:
        sp = MethadoneSpecies(species)
    except ValueError:
        sp = MethadoneSpecies.DOG

    inputs = MethadoneInputs(
        weight_value=weight,
        weight_unit=wu,
        species=sp,
        stock_mg_per_ml=stock,
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/methadone_result.html",
        {
            "request": request,
            "result": result,
            "weight_value": weight,
            "weight_unit": weight_unit,
        },
    )
