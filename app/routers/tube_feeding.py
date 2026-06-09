"""Tube feeding calculator routes (one-off, not in engine-drug routes)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.tube_feeding import (
    TUBE_FEEDING_CATALOG_ENTRY,
    RampLength,
    Species,
    TubeFeedingInputs,
    TubeType,
    compute_tube_feeding,
)
from app.calculators.tube_feeding_diets import DIETS, OTHER_KEY, DietForm
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _default_inputs() -> TubeFeedingInputs:
    """Initial-load defaults. The current weight is set to a placeholder
    1.0 to satisfy the dataclass type; the template renders the actual
    weight input as an empty string until the user types a value, at
    which point the form's hx-trigger fires a POST to /compute.
    """
    return TubeFeedingInputs(
        species=Species.DOG,
        tube_type=TubeType.E,
        diet_form=DietForm.CANNED,
        diet_key="hills_ad",
        current_weight_value=1.0,
        current_weight_unit=WeightUnit.LB,
        feedings_per_day=4,
        ramp_length=RampLength.THREE_DAY,
        water_added_ml=50.0,
    )


@router.get("/tube-feeding", response_class=HTMLResponse)
async def tube_feeding_page(request: Request):
    templates = request.app.state.templates
    inputs = _default_inputs()
    return templates.TemplateResponse(
        "tube_feeding.html",
        {
            "request": request,
            "meta": TUBE_FEEDING_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "diets": DIETS,
            "other_key": OTHER_KEY,
            "current_weight_value": "",
        },
    )


@router.post("/tube-feeding/compute", response_class=HTMLResponse)
async def tube_feeding_compute(
    request: Request,
    species: str = Form("dog"),
    tube_type: str = Form("e"),
    diet_form: str = Form("canned"),
    diet_key: str = Form("hills_ad"),
    patient_id: str = Form(""),
    current_weight_value: str = Form(""),
    current_weight_unit: str = Form("lb"),
    ideal_weight_value: str = Form(""),
    ideal_weight_unit: str = Form("lb"),
    bcs: str = Form(""),
    feedings_per_day: int = Form(4),
    ramp_length: int = Form(3),
    current_day: int = Form(1),
    diet_kcal_per_ml: str = Form(""),
    diet_can_size_ml: str = Form(""),
    diet_can_kcal: str = Form(""),
    water_added_ml: str = Form("50"),
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

    # Enums (with sensible fallbacks; the form prevents bad values normally).
    try:
        sp = Species(species)
    except ValueError:
        sp = Species.DOG
    try:
        tt = TubeType(tube_type)
    except ValueError:
        tt = TubeType.E
    try:
        df = DietForm(diet_form)
    except ValueError:
        df = DietForm.CANNED
    try:
        cu = WeightUnit(current_weight_unit)
    except ValueError:
        cu = WeightUnit.LB
    try:
        iu = WeightUnit(ideal_weight_unit)
    except ValueError:
        iu = WeightUnit.LB
    try:
        rl = RampLength(ramp_length)
    except ValueError:
        rl = RampLength.THREE_DAY

    bcs_int = _opt_int(bcs)
    bcs_val: int | None = bcs_int if bcs_int is not None and 1 <= bcs_int <= 9 else None

    # Water added: allow zero (e.g. clinician chooses not to dilute);
    # negative values clamp to zero in the diet resolver. Default 50 mL.
    water = _opt_float(water_added_ml)
    if water is None:
        water = 50.0

    inputs = TubeFeedingInputs(
        species=sp,
        tube_type=tt,
        diet_form=df,
        diet_key=diet_key or OTHER_KEY,
        # Trim and cap. Free text — but cap at 80 chars so a copy-paste
        # accident doesn't blow up the printable header layout.
        patient_id=(patient_id or "").strip()[:80],
        current_weight_value=current_weight,
        current_weight_unit=cu,
        ideal_weight_value=_opt_float(ideal_weight_value),
        ideal_weight_unit=iu,
        bcs=bcs_val,
        feedings_per_day=max(3, min(6, feedings_per_day)),
        ramp_length=rl,
        current_day=max(1, current_day),
        diet_kcal_per_ml=_opt_float(diet_kcal_per_ml),
        diet_can_size_ml=_opt_float(diet_can_size_ml),
        diet_can_kcal=_opt_float(diet_can_kcal),
        water_added_ml=water,
    )
    result = compute_tube_feeding(inputs)

    return templates.TemplateResponse(
        "partials/tube_feeding_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
            "diets": DIETS,
            "other_key": OTHER_KEY,
        },
    )
