"""Alfaxalone calculator route."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.alfaxalone import (
    AlfaxaloneInputs,
    AlfaxaloneMode,
    AlfaxalonePremed,
    AlfaxaloneSpecies,
    calculate,
)
from app.calculators.engine import WeightUnit
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


def _build_inputs(
    weight_value: float,
    weight_unit: str,
    species: str,
    premedicated: str,
    mode: str,
    cri_rate: float | None,
) -> AlfaxaloneInputs:
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB
    try:
        sp = AlfaxaloneSpecies(species)
    except ValueError:
        sp = AlfaxaloneSpecies.DOG
    try:
        pm = AlfaxalonePremed(premedicated)
    except ValueError:
        pm = AlfaxalonePremed.PREMEDICATED
    try:
        md = AlfaxaloneMode(mode)
    except ValueError:
        md = AlfaxaloneMode.INDUCTION

    return AlfaxaloneInputs(
        weight_value=weight_value,
        weight_unit=wu,
        species=sp,
        premedicated=pm,
        mode=md,
        cri_rate_mg_per_kg_per_hr=cri_rate,
    )


@router.get("/alfaxalone", response_class=HTMLResponse)
async def alfaxalone_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "alfaxalone.html",
        {
            "request": request,
            "result": None,
            "weight_value": "",
            "weight_unit": "lb",
        },
    )


@router.post("/alfaxalone/compute", response_class=HTMLResponse)
async def alfaxalone_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    premedicated: str = Form("premedicated"),
    mode: str = Form("induction"),
    cri_rate: str = Form("6.0"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    cri = parse_float_with_default(cri_rate, 6.0)
    inputs = _build_inputs(weight, weight_unit, species, premedicated, mode, cri)
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/alfaxalone_result.html",
        {
            "request": request,
            "result": result,
            "weight_value": weight,
            "weight_unit": weight_unit,
        },
    )
