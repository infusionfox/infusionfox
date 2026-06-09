"""Hypomagnesemia / MgSO4 CRI calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.hypomagnesemia import (
    HYPOMAGNESEMIA_CATALOG_ENTRY,
    HYPOMAGNESEMIA_TIERS,
    HypomagnesemiaInputs,
    MgSpecies,
    MgStockConcentration,
    compute_hypomagnesemia,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> MgSpecies:
    try:
        return MgSpecies(value)
    except ValueError:
        return MgSpecies.DOG


def _coerce_stock(value: str) -> MgStockConcentration:
    try:
        return MgStockConcentration(value)
    except ValueError:
        return MgStockConcentration.PCT_50


@router.get("/hypomagnesemia", response_class=HTMLResponse)
async def hypomagnesemia_page(request: Request):
    templates = request.app.state.templates
    inputs = HypomagnesemiaInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=MgSpecies.DOG,
        serum_mg_mg_per_dl=1.0,
        stock_concentration=MgStockConcentration.PCT_50,
    )
    return templates.TemplateResponse(
        "hypomagnesemia.html",
        {
            "request": request,
            "meta": HYPOMAGNESEMIA_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "tiers": HYPOMAGNESEMIA_TIERS,
        },
    )


@router.post("/hypomagnesemia/compute", response_class=HTMLResponse)
async def hypomagnesemia_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    serum_mg_mg_per_dl: str = Form(""),
    stock_concentration: str = Form("50pct"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    serum_mg = parse_positive_float(serum_mg_mg_per_dl)
    if weight is None or serum_mg is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = HypomagnesemiaInputs(
        weight_value=weight,
        weight_unit=wu,
        species=_coerce_species(species),
        serum_mg_mg_per_dl=serum_mg,
        stock_concentration=_coerce_stock(stock_concentration),
    )
    result = compute_hypomagnesemia(inputs)
    return templates.TemplateResponse(
        "partials/hypomagnesemia_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
