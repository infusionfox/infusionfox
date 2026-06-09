"""Insulin CRI for DKA route."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.insulin_cri_dka import (
    INSULIN_CRI_BAG_VOLUME_ML,
    INSULIN_CRI_CATALOG_ENTRY,
    INSULIN_CRI_PRIME_DISCARD_ML,
    INSULIN_CRI_TIERS,
    InsulinCriCatDoseOption,
    InsulinCriInputs,
    InsulinCriSpecies,
    compute_insulin_cri,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> InsulinCriSpecies:
    try:
        return InsulinCriSpecies(value)
    except ValueError:
        return InsulinCriSpecies.DOG


def _coerce_cat_option(value: str) -> InsulinCriCatDoseOption:
    try:
        return InsulinCriCatDoseOption(value)
    except ValueError:
        return InsulinCriCatDoseOption.STANDARD_2_2


@router.get("/insulin-cri-dka", response_class=HTMLResponse)
async def insulin_cri_dka_page(request: Request):
    templates = request.app.state.templates
    inputs = InsulinCriInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=InsulinCriSpecies.DOG,
        blood_glucose_mg_per_dl=380.0,
        cat_dose_option=InsulinCriCatDoseOption.STANDARD_2_2,
    )
    return templates.TemplateResponse(
        "insulin_cri_dka.html",
        {
            "request": request,
            "meta": INSULIN_CRI_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "bag_volume_ml": INSULIN_CRI_BAG_VOLUME_ML,
            "prime_discard_ml": INSULIN_CRI_PRIME_DISCARD_ML,
            "tiers": INSULIN_CRI_TIERS,
        },
    )


@router.post("/insulin-cri-dka/compute", response_class=HTMLResponse)
async def insulin_cri_dka_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    blood_glucose_mg_per_dl: str = Form(""),
    cat_dose_option: str = Form("standard"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    bg = parse_positive_float(blood_glucose_mg_per_dl)
    if weight is None or bg is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = InsulinCriInputs(
        weight_value=weight,
        weight_unit=wu,
        species=_coerce_species(species),
        blood_glucose_mg_per_dl=bg,
        cat_dose_option=_coerce_cat_option(cat_dose_option),
    )
    result = compute_insulin_cri(inputs)
    return templates.TemplateResponse(
        "partials/insulin_cri_dka_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
            "tiers": INSULIN_CRI_TIERS,
        },
    )
