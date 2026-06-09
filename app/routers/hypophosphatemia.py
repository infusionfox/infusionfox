"""Hypophosphatemia / KPhos CRI calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.hypophosphatemia import (
    HYPOPHOSPHATEMIA_CATALOG_ENTRY,
    HYPOPHOSPHATEMIA_TIERS,
    HypophosphatemiaInputs,
    KPhosSpecies,
    compute_hypophosphatemia,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> KPhosSpecies:
    try:
        return KPhosSpecies(value)
    except ValueError:
        return KPhosSpecies.DOG


@router.get("/hypophosphatemia", response_class=HTMLResponse)
async def hypophosphatemia_page(request: Request):
    templates = request.app.state.templates
    inputs = HypophosphatemiaInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=KPhosSpecies.DOG,
        serum_p_mg_per_dl=1.2,  # moderate default
        concurrent_kcl_meq_per_kg_per_hr=0.0,
    )
    return templates.TemplateResponse(
        "hypophosphatemia.html",
        {
            "request": request,
            "meta": HYPOPHOSPHATEMIA_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "tiers": HYPOPHOSPHATEMIA_TIERS,
        },
    )


@router.post("/hypophosphatemia/compute", response_class=HTMLResponse)
async def hypophosphatemia_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    serum_p_mg_per_dl: str = Form(""),
    concurrent_kcl_meq_per_kg_per_hr: str = Form("0.0"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    serum_p = parse_positive_float(serum_p_mg_per_dl)
    if weight is None or serum_p is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    concurrent_kcl = parse_float_with_default(concurrent_kcl_meq_per_kg_per_hr, 0.0)
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = HypophosphatemiaInputs(
        weight_value=weight,
        weight_unit=wu,
        species=_coerce_species(species),
        serum_p_mg_per_dl=serum_p,
        concurrent_kcl_meq_per_kg_per_hr=concurrent_kcl,
    )
    result = compute_hypophosphatemia(inputs)
    return templates.TemplateResponse(
        "partials/hypophosphatemia_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
