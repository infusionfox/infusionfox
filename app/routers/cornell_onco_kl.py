"""Cornell KL infusion calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.cornell_onco_kl import (
    BAG_SIZE_DEFAULT_LARGE,
    CORNELL_ONCO_KL_CATALOG_ENTRY,
    DURATION_DEFAULT_HR,
    CornellOncoKLInputs,
    CornellOncoKLSpecies,
    compute_cornell_onco_kl,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> CornellOncoKLSpecies:
    try:
        return CornellOncoKLSpecies(value)
    except ValueError:
        return CornellOncoKLSpecies.DOG


@router.get("/cornell-onco-kl", response_class=HTMLResponse)
async def cornell_onco_kl_page(request: Request):
    templates = request.app.state.templates
    inputs = CornellOncoKLInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=CornellOncoKLSpecies.DOG,
        bag_volume_ml=BAG_SIZE_DEFAULT_LARGE,
        duration_hr=DURATION_DEFAULT_HR,
    )
    return templates.TemplateResponse(
        "cornell_onco_kl.html",
        {
            "request": request,
            "meta": CORNELL_ONCO_KL_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
        },
    )


@router.post("/cornell-onco-kl/compute", response_class=HTMLResponse)
async def cornell_onco_kl_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    bag_volume_ml: str = Form(str(BAG_SIZE_DEFAULT_LARGE)),
    duration_hr: str = Form(str(DURATION_DEFAULT_HR)),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    bag = parse_float_with_default(bag_volume_ml, BAG_SIZE_DEFAULT_LARGE)
    duration = parse_float_with_default(duration_hr, DURATION_DEFAULT_HR)
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = CornellOncoKLInputs(
        weight_value=weight,
        weight_unit=wu,
        species=_coerce_species(species),
        bag_volume_ml=bag,
        duration_hr=duration,
    )
    result = compute_cornell_onco_kl(inputs)
    return templates.TemplateResponse(
        "partials/cornell_onco_kl_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
