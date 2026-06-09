"""Energy requirements calculator routes (one-off, not in engine-drug routes)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.energy import (
    CAT_MAINTENANCE,
    DOG_MAINTENANCE,
    ENERGY_CATALOG_ENTRY,
    CaloricDensityUnit,
    EnergyInputs,
    EnergyPurpose,
    EnergySpecies,
    FoodForm,
    compute_energy_requirements,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


@router.get("/energy", response_class=HTMLResponse)
async def energy_page(request: Request):
    templates = request.app.state.templates
    inputs = EnergyInputs(
        species=EnergySpecies.DOG,
        purpose=EnergyPurpose.MAINTENANCE,
        current_weight_value=1.0,
        current_weight_unit=WeightUnit.LB,
        ideal_weight_value=None,
        bcs=None,
        maintenance_factor_key="typical_pet",
        # Default food form to dry so the page renders with the Dry segmented
        # button pre-selected. Without a default, the user had to manually
        # click Dry/Canned before the feeding-plan panel would compute.
        food_form=FoodForm.DRY,
        caloric_density=None,
        caloric_density_unit=None,
        meals_per_day=2,
    )
    return templates.TemplateResponse(
        "energy.html",
        {
            "request": request,
            "meta": ENERGY_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "current_weight_value": "",
            "dog_factors": DOG_MAINTENANCE,
            "cat_factors": CAT_MAINTENANCE,
        },
    )


@router.post("/energy/compute", response_class=HTMLResponse)
async def energy_compute(
    request: Request,
    species: str = Form("dog"),
    purpose: str = Form("maintenance"),
    current_weight_value: str = Form(""),
    current_weight_unit: str = Form("lb"),
    # Optional fields that may arrive as empty strings from the form. We accept
    # them as str and coerce ourselves, typed Optional[float|int] with
    # Form(None) rejects empty strings with 422.
    ideal_weight_value: str = Form(""),
    ideal_weight_unit: str = Form("lb"),
    bcs: str = Form(""),
    maintenance_factor_key: str = Form("typical_pet"),
    food_form: str = Form(""),
    caloric_density: str = Form(""),
    caloric_density_unit: str = Form(""),
    meals_per_day: int = Form(2),
):
    templates = request.app.state.templates
    current_weight = parse_positive_float(current_weight_value)
    if current_weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )

    def _opt_float(s: str) -> float | None:
        try:
            v = float(s)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None

    def _opt_int(s: str) -> int | None:
        try:
            return int(s)
        except (TypeError, ValueError):
            return None

    try:
        sp = EnergySpecies(species)
    except ValueError:
        sp = EnergySpecies.DOG
    try:
        pp = EnergyPurpose(purpose)
    except ValueError:
        pp = EnergyPurpose.MAINTENANCE
    try:
        cu = WeightUnit(current_weight_unit)
    except ValueError:
        cu = WeightUnit.LB
    try:
        iu = WeightUnit(ideal_weight_unit)
    except ValueError:
        iu = WeightUnit.LB

    # Optional food form / density unit
    ff: FoodForm | None = None
    if food_form:
        try:
            ff = FoodForm(food_form)
        except ValueError:
            ff = None
    cdu: CaloricDensityUnit | None = None
    if caloric_density_unit:
        try:
            cdu = CaloricDensityUnit(caloric_density_unit)
        except ValueError:
            cdu = None

    # Coerce optional numeric fields
    iw_val = _opt_float(ideal_weight_value)
    cd_val = _opt_float(caloric_density)
    bcs_int = _opt_int(bcs)
    bcs_val: int | None = bcs_int if bcs_int is not None and 1 <= bcs_int <= 9 else None

    inputs = EnergyInputs(
        species=sp,
        purpose=pp,
        current_weight_value=current_weight,
        current_weight_unit=cu,
        ideal_weight_value=iw_val,
        ideal_weight_unit=iu,
        bcs=bcs_val,
        maintenance_factor_key=maintenance_factor_key,
        food_form=ff,
        caloric_density=cd_val,
        caloric_density_unit=cdu,
        meals_per_day=max(1, meals_per_day),
    )
    result = compute_energy_requirements(inputs)

    return templates.TemplateResponse(
        "partials/energy_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
            "dog_factors": DOG_MAINTENANCE,
            "cat_factors": CAT_MAINTENANCE,
        },
    )
