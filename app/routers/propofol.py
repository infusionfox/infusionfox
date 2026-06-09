"""Propofol TIVA / status epilepticus calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.propofol import (
    INDUCTION_TABLE_CAT,
    INDUCTION_TABLE_DOG,
    PROPOFOL_CATALOG_ENTRY,
    PROPOFOL_DOSE_RANGES,
    PROPOFOL_STOCK_MG_PER_ML,
    PropofolIndication,
    PropofolInputs,
    PropofolSpecies,
    compute_propofol,
    get_propofol_dose_range,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _coerce_indication(value: str) -> PropofolIndication:
    try:
        return PropofolIndication(value)
    except ValueError:
        return PropofolIndication.TIVA_MAINTENANCE


def _coerce_species(value: str) -> PropofolSpecies:
    try:
        return PropofolSpecies(value)
    except ValueError:
        return PropofolSpecies.DOG


def _default_dose_for(indication: PropofolIndication, species: PropofolSpecies) -> float:
    dr = get_propofol_dose_range(indication, species)
    if dr is not None:
        return dr.default_mg_per_kg_per_min
    # Fallback (TIVA cat, invalid combo): show the dog default so the form
    # is populated; the warning will explain why no rate is computed.
    fallback = get_propofol_dose_range(indication, PropofolSpecies.DOG)
    return fallback.default_mg_per_kg_per_min if fallback else 0.3


@router.get("/propofol", response_class=HTMLResponse)
async def propofol_page(request: Request):
    templates = request.app.state.templates
    indication = PropofolIndication.TIVA_MAINTENANCE
    species = PropofolSpecies.DOG
    inputs = PropofolInputs(
        weight_value=1.0,  # placeholder, not displayed
        weight_unit=WeightUnit.LB,
        dose_mg_per_kg_per_min=_default_dose_for(indication, species),
        indication=indication,
        species=species,
    )
    return templates.TemplateResponse(
        "propofol.html",
        {
            "request": request,
            "meta": PROPOFOL_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "stock_mg_per_ml": PROPOFOL_STOCK_MG_PER_ML,
            "dose_ranges": PROPOFOL_DOSE_RANGES,
            "induction_table_dog": INDUCTION_TABLE_DOG,
            "induction_table_cat": INDUCTION_TABLE_CAT,
        },
    )


@router.post("/propofol/compute", response_class=HTMLResponse)
async def propofol_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    dose_mg_per_kg_per_min: str = Form(""),
    indication: str = Form("tiva_maintenance"),
    species: str = Form("dog"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    dose = parse_positive_float(dose_mg_per_kg_per_min)
    if weight is None or dose is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    ind = _coerce_indication(indication)
    sp = _coerce_species(species)

    inputs = PropofolInputs(
        weight_value=weight,
        weight_unit=wu,
        dose_mg_per_kg_per_min=dose,
        indication=ind,
        species=sp,
    )
    result = compute_propofol(inputs)
    return templates.TemplateResponse(
        "partials/propofol_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
