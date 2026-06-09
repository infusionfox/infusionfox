"""Intravenous Lipid Emulsion (ILE) protocol calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.ile import (
    ILE_CATALOG_ENTRY,
    IleInputs,
    IleSpecies,
    compute_ile,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> IleSpecies:
    try:
        return IleSpecies(value)
    except ValueError:
        return IleSpecies.DOG


@router.get("/ile", response_class=HTMLResponse)
async def ile_page(request: Request):
    templates = request.app.state.templates
    inputs = IleInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=IleSpecies.DOG,
    )
    return templates.TemplateResponse(
        "ile.html",
        {
            "request": request,
            "meta": ILE_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
        },
    )


@router.post("/ile/compute", response_class=HTMLResponse)
async def ile_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        # Safety Rule #8 — no output before input. Return the same
        # placeholder used by the engine drugs.
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )

    try:
        unit_enum = WeightUnit(weight_unit)
    except ValueError:
        unit_enum = WeightUnit.LB

    inputs = IleInputs(
        weight_value=weight,
        weight_unit=unit_enum,
        species=_coerce_species(species),
    )
    result = compute_ile(inputs)

    return templates.TemplateResponse(
        "partials/ile_result.html",
        {
            "request": request,
            "meta": ILE_CATALOG_ENTRY,
            "result": result,
        },
    )
