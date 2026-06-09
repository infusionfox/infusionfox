"""Ketamine CRI calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.ketamine import (
    KETAMINE_CATALOG_ENTRY,
    KETAMINE_DOSE_RANGES,
    KETAMINE_STOCK_MG_PER_ML,
    KetamineDoseUnit,
    KetamineIndication,
    KetamineInputs,
    KetamineSpecies,
    compute_ketamine,
    get_ketamine_dose_range,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _coerce_dose_unit(value: str) -> KetamineDoseUnit:
    try:
        return KetamineDoseUnit(value)
    except ValueError:
        return KetamineDoseUnit.UG_PER_KG_PER_MIN


def _coerce_indication(value: str) -> KetamineIndication:
    try:
        return KetamineIndication(value)
    except ValueError:
        return KetamineIndication.SURGICAL


def _coerce_species(value: str) -> KetamineSpecies:
    try:
        return KetamineSpecies(value)
    except ValueError:
        return KetamineSpecies.DOG


@router.get("/ketamine", response_class=HTMLResponse)
async def ketamine_page(request: Request):
    templates = request.app.state.templates
    indication = KetamineIndication.SURGICAL
    species = KetamineSpecies.DOG
    dose_range = get_ketamine_dose_range(indication)
    # No precomputed result on initial load — user must enter weight.
    inputs = KetamineInputs(
        weight_value=1.0,  # placeholder, not displayed; template uses weight_value="" below
        weight_unit=WeightUnit.LB,
        dose_value=dose_range.default_ug_per_kg_per_min,
        dose_unit=KetamineDoseUnit.UG_PER_KG_PER_MIN,
        indication=indication,
        species=species,
    )
    return templates.TemplateResponse(
        "ketamine.html",
        {
            "request": request,
            "meta": KETAMINE_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "stock_mg_per_ml": KETAMINE_STOCK_MG_PER_ML,
            "dose_ranges": KETAMINE_DOSE_RANGES,
        },
    )


@router.post("/ketamine/compute", response_class=HTMLResponse)
async def ketamine_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    dose_value: str = Form(""),
    dose_unit: str = Form("ug/kg/min"),
    indication: str = Form("surgical"),
    species: str = Form("dog"),
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

    inputs = KetamineInputs(
        weight_value=weight,
        weight_unit=wu,
        dose_value=dose,
        dose_unit=_coerce_dose_unit(dose_unit),
        indication=_coerce_indication(indication),
        species=_coerce_species(species),
    )
    result = compute_ketamine(inputs)
    return templates.TemplateResponse(
        "partials/ketamine_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
