"""Insulin IM intermittent for DKA route."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.insulin_im_dka import (
    INSULIN_IM_CATALOG_ENTRY,
    INSULIN_IM_LOADING_DOSE_U_PER_KG,
    INSULIN_IM_STOCK_U_PER_ML,
    INSULIN_IM_TIERS,
    InsulinImInputs,
    InsulinImMode,
    InsulinImSpecies,
    compute_insulin_im,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> InsulinImSpecies:
    try:
        return InsulinImSpecies(value)
    except ValueError:
        return InsulinImSpecies.DOG


def _coerce_mode(value: str) -> InsulinImMode:
    try:
        return InsulinImMode(value)
    except ValueError:
        return InsulinImMode.LOADING


def _opt_float(value: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


@router.get("/insulin-im-dka", response_class=HTMLResponse)
async def insulin_im_dka_page(request: Request):
    templates = request.app.state.templates
    inputs = InsulinImInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=InsulinImSpecies.DOG,
        mode=InsulinImMode.LOADING,
    )
    return templates.TemplateResponse(
        "insulin_im_dka.html",
        {
            "request": request,
            "meta": INSULIN_IM_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "loading_dose_u_per_kg": INSULIN_IM_LOADING_DOSE_U_PER_KG,
            "stock_u_per_ml": INSULIN_IM_STOCK_U_PER_ML,
            "tiers": INSULIN_IM_TIERS,
        },
    )


@router.post("/insulin-im-dka/compute", response_class=HTMLResponse)
async def insulin_im_dka_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    mode: str = Form("loading"),
    previous_bg_mg_per_dl: str = Form(""),
    current_bg_mg_per_dl: str = Form(""),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = InsulinImInputs(
        weight_value=weight,
        weight_unit=wu,
        species=_coerce_species(species),
        mode=_coerce_mode(mode),
        previous_bg_mg_per_dl=_opt_float(previous_bg_mg_per_dl),
        current_bg_mg_per_dl=_opt_float(current_bg_mg_per_dl),
    )
    result = compute_insulin_im(inputs)
    return templates.TemplateResponse(
        "partials/insulin_im_dka_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
