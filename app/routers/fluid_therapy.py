"""DKA fluid therapy calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.fluid_therapy import (
    DEHYDRATION_BANDS,
    FLUID_THERAPY_CATALOG_ENTRY,
    MAINTENANCE_DEFAULT_MLPKG_HR,
    REHYDRATION_DEFAULT_HR,
    FluidTherapyInputs,
    FluidTherapySpecies,
    compute_fluid_therapy,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


def _coerce_species(value: str) -> FluidTherapySpecies:
    try:
        return FluidTherapySpecies(value)
    except ValueError:
        return FluidTherapySpecies.DOG


@router.get("/fluid-therapy", response_class=HTMLResponse)
async def fluid_therapy_page(request: Request):
    templates = request.app.state.templates
    inputs = FluidTherapyInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        species=FluidTherapySpecies.DOG,
        in_shock=False,
        dehydration_band_key="euhydrated",
        rehydration_window_hr=REHYDRATION_DEFAULT_HR,
        maintenance_mlpkg_hr=MAINTENANCE_DEFAULT_MLPKG_HR,
        ongoing_losses_ml_per_hr=0.0,
    )
    return templates.TemplateResponse(
        "fluid_therapy.html",
        {
            "request": request,
            "meta": FLUID_THERAPY_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "dehydration_bands": DEHYDRATION_BANDS,
        },
    )


@router.post("/fluid-therapy/compute", response_class=HTMLResponse)
async def fluid_therapy_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    species: str = Form("dog"),
    in_shock: str = Form(""),
    dehydration_band_key: str = Form("euhydrated"),
    rehydration_window_hr: int = Form(REHYDRATION_DEFAULT_HR),
    maintenance_mlpkg_hr: str = Form(str(MAINTENANCE_DEFAULT_MLPKG_HR)),
    ongoing_losses_ml_per_hr: str = Form("0.0"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    maint = parse_float_with_default(maintenance_mlpkg_hr, MAINTENANCE_DEFAULT_MLPKG_HR)
    losses = parse_float_with_default(ongoing_losses_ml_per_hr, 0.0)
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB

    inputs = FluidTherapyInputs(
        weight_value=weight,
        weight_unit=wu,
        species=_coerce_species(species),
        in_shock=(in_shock == "yes"),
        dehydration_band_key=dehydration_band_key,
        rehydration_window_hr=rehydration_window_hr,
        maintenance_mlpkg_hr=maint,
        ongoing_losses_ml_per_hr=losses,
    )
    result = compute_fluid_therapy(inputs)
    return templates.TemplateResponse(
        "partials/fluid_therapy_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
