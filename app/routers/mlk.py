"""MLK CRI calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.calculators import WeightUnit
from app.calculators.mlk import (
    DEFAULT_BAG_VOLUME_ML,
    DEFAULT_DOSE_KETAMINE,
    DEFAULT_DOSE_LIDOCAINE,
    DEFAULT_DOSE_MORPHINE,
    DEFAULT_PUMP_RATE_ML_PER_KG_PER_HR,
    DEFAULT_STOCK_KETAMINE,
    DEFAULT_STOCK_LIDOCAINE,
    DEFAULT_STOCK_MORPHINE,
    DOSE_RANGE_KETAMINE,
    DOSE_RANGE_LIDOCAINE,
    DOSE_RANGE_MORPHINE,
    MLK_CATALOG_ENTRY,
    MlkInputs,
    MlkSpecies,
    compute_mlk,
    compute_mlk_waste,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


def _template_context(request: Request, **overrides) -> dict:
    """Common context for both POST endpoints. (The GET path now
    redirects to /analgesia-cri; this context dict supports the
    legacy POST endpoints below.) The form would have remembered its
    inputs on every render, including which custom doses and stock
    concentrations the user picked."""
    ctx = {
        "request": request,
        "meta": MLK_CATALOG_ENTRY,
        "result": None,
        "weight_value": "",
        "weight_unit": "lb",
        "pump_rate_ml_per_kg_per_hr": DEFAULT_PUMP_RATE_ML_PER_KG_PER_HR,
        "bag_volume_ml": DEFAULT_BAG_VOLUME_ML,
        "morphine_dose": DEFAULT_DOSE_MORPHINE,
        "lidocaine_dose": DEFAULT_DOSE_LIDOCAINE,
        "ketamine_dose": DEFAULT_DOSE_KETAMINE,
        "morphine_stock": DEFAULT_STOCK_MORPHINE,
        "lidocaine_stock": DEFAULT_STOCK_LIDOCAINE,
        "ketamine_stock": DEFAULT_STOCK_KETAMINE,
        "dose_range_morphine": DOSE_RANGE_MORPHINE,
        "dose_range_lidocaine": DOSE_RANGE_LIDOCAINE,
        "dose_range_ketamine": DOSE_RANGE_KETAMINE,
    }
    ctx.update(overrides)
    return ctx


@router.get("/mlk")
async def mlk_page() -> RedirectResponse:
    """MLK retired in Phase 3 — redirect to the multi-modal builder
    with combined-bag mode active and the MLK protocol (morphine +
    ketamine + lidocaine) preselected. Preserves the workflow for
    /mlk bookmarks while consolidating onto one calculator."""
    return RedirectResponse(
        url=(
            "/analgesia-cri"
            "?prep_mode=combined_bag"
            "&opioid=morphine"
            "&adjuncts=ketamine,lidocaine"
        ),
        status_code=301,
    )


def _safe_float(raw: str, default: float) -> float:
    """Parse a form field, returning the default if it's blank or unparseable.
    Used for optional inputs with sensible fallbacks (stock concentrations,
    bag volume, etc.). Negative or zero values fall through as-is and are
    handled by the compute() validation."""
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _build_inputs(
    weight: float,
    weight_unit: str,
    pump_rate_ml_per_kg_per_hr: str,
    bag_volume_ml: str,
    morphine_dose: str,
    lidocaine_dose: str,
    ketamine_dose: str,
    morphine_stock: str,
    lidocaine_stock: str,
    ketamine_stock: str,
) -> MlkInputs:
    """Build MlkInputs from raw form strings. Shared by the compute and
    waste endpoints — the waste endpoint rebuilds the same bag so the two
    forms stay independent (editing volume-given never disturbs the
    bag-builder inputs and vice versa)."""
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB
    return MlkInputs(
        weight_value=weight,
        weight_unit=wu,
        pump_rate_ml_per_kg_per_hr=_safe_float(
            pump_rate_ml_per_kg_per_hr, DEFAULT_PUMP_RATE_ML_PER_KG_PER_HR
        ),
        bag_volume_ml=_safe_float(bag_volume_ml, DEFAULT_BAG_VOLUME_ML),
        morphine_dose_mg_per_kg_per_hr=_safe_float(morphine_dose, DEFAULT_DOSE_MORPHINE),
        lidocaine_dose_mg_per_kg_per_hr=_safe_float(lidocaine_dose, DEFAULT_DOSE_LIDOCAINE),
        ketamine_dose_mg_per_kg_per_hr=_safe_float(ketamine_dose, DEFAULT_DOSE_KETAMINE),
        morphine_stock_mg_per_ml=_safe_float(morphine_stock, DEFAULT_STOCK_MORPHINE),
        lidocaine_stock_mg_per_ml=_safe_float(lidocaine_stock, DEFAULT_STOCK_LIDOCAINE),
        ketamine_stock_mg_per_ml=_safe_float(ketamine_stock, DEFAULT_STOCK_KETAMINE),
        species=MlkSpecies.DOG,
    )


@router.post("/mlk/compute", response_class=HTMLResponse)
async def mlk_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    pump_rate_ml_per_kg_per_hr: str = Form(""),
    bag_volume_ml: str = Form(""),
    morphine_dose: str = Form(""),
    lidocaine_dose: str = Form(""),
    ketamine_dose: str = Form(""),
    morphine_stock: str = Form(""),
    lidocaine_stock: str = Form(""),
    ketamine_stock: str = Form(""),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )

    inputs = _build_inputs(
        weight,
        weight_unit,
        pump_rate_ml_per_kg_per_hr,
        bag_volume_ml,
        morphine_dose,
        lidocaine_dose,
        ketamine_dose,
        morphine_stock,
        lidocaine_stock,
        ketamine_stock,
    )
    result = compute_mlk(inputs)
    return templates.TemplateResponse(
        "partials/mlk_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )


@router.post("/mlk/waste", response_class=HTMLResponse)
async def mlk_waste(
    request: Request,
    volume_given_ml: str = Form(""),
    # The same bag-builder fields are echoed into the waste form as hidden
    # inputs so the waste endpoint can rebuild the identical bag without
    # depending on the bag-builder form's state.
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    pump_rate_ml_per_kg_per_hr: str = Form(""),
    bag_volume_ml: str = Form(""),
    morphine_dose: str = Form(""),
    lidocaine_dose: str = Form(""),
    ketamine_dose: str = Form(""),
    morphine_stock: str = Form(""),
    lidocaine_stock: str = Form(""),
    ketamine_stock: str = Form(""),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        # No valid bag to compute waste against — render an empty waste
        # sub-panel so the section keeps its place in the result.
        return templates.TemplateResponse(
            "partials/mlk_waste_result.html",
            {"request": request, "waste": None},
        )

    inputs = _build_inputs(
        weight,
        weight_unit,
        pump_rate_ml_per_kg_per_hr,
        bag_volume_ml,
        morphine_dose,
        lidocaine_dose,
        ketamine_dose,
        morphine_stock,
        lidocaine_stock,
        ketamine_stock,
    )
    result = compute_mlk(inputs)

    volume_given = parse_positive_float(volume_given_ml)
    if volume_given is None:
        # Volume-given field blank or unparseable — show the waste section
        # with no result yet (prompts the user to enter a volume).
        return templates.TemplateResponse(
            "partials/mlk_waste_result.html",
            {"request": request, "waste": None},
        )

    waste = compute_mlk_waste(result, volume_given)
    return templates.TemplateResponse(
        "partials/mlk_waste_result.html",
        {"request": request, "waste": waste},
    )
