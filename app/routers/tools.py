"""
Utility calculator routes: weight/dose conversion, drop factor, solution prep.

These are non-drug tools, pure math, no clinical judgment. They live at
/tools/<name> rather than /<slug> to keep them visually and conceptually
separate from drug calculators.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.calculators import (
    DropFactorInputs,
    SolutionPrepInputs,
    WeightFromUnit,
    compute_bsa,
    compute_drop_factor,
    compute_solution_prep,
    convert_concentration,
    convert_dose_amount,
    convert_weight,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


# ---------------------------------------------------------------------------
# Weight conversion
# ---------------------------------------------------------------------------


@router.get("/tools/weight", response_class=HTMLResponse)
async def weight_tool(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "tools/weight.html",
        {"request": request, "value": "", "unit": "lb", "result": None},
    )


@router.post("/tools/weight/compute", response_class=HTMLResponse)
async def weight_compute(
    request: Request,
    value: str = Form(""),
    unit: str = Form("lb"),
):
    templates = request.app.state.templates
    val = parse_positive_float(value)
    if val is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        u = WeightFromUnit(unit)
    except ValueError:
        u = WeightFromUnit.LB
    result = convert_weight(val, u)
    return templates.TemplateResponse(
        "tools/partials/weight_result.html",
        {"request": request, "value": val, "unit": unit, "result": result},
    )


# ---------------------------------------------------------------------------
# Fluid rate
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Drop factor
# ---------------------------------------------------------------------------


@router.get("/tools/drop-factor", response_class=HTMLResponse)
async def drop_factor_tool(request: Request):
    templates = request.app.state.templates
    inputs = DropFactorInputs(ml_per_hour=60.0, drop_factor=15)
    result = compute_drop_factor(inputs)
    return templates.TemplateResponse(
        "tools/drop_factor.html",
        {"request": request, "inputs": inputs, "result": result},
    )


@router.post("/tools/drop-factor/compute", response_class=HTMLResponse)
async def drop_factor_compute(
    request: Request,
    ml_per_hour: str = Form(""),
    drop_factor: int = Form(15),
):
    templates = request.app.state.templates
    ml_hr = parse_positive_float(ml_per_hour)
    if ml_hr is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    inputs = DropFactorInputs(ml_per_hour=ml_hr, drop_factor=drop_factor)
    result = compute_drop_factor(inputs)
    return templates.TemplateResponse(
        "tools/partials/drop_factor_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )


# ---------------------------------------------------------------------------
# Solution preparation (D5W from concentrated dextrose, etc.)
# ---------------------------------------------------------------------------


@router.get("/tools/d5w-prep", response_class=HTMLResponse)
async def d5w_prep_tool(request: Request):
    templates = request.app.state.templates
    inputs = SolutionPrepInputs(
        target_volume_ml=1000.0,
        target_percent=5.0,
        stock_percent=50.0,
    )
    result = compute_solution_prep(inputs)
    return templates.TemplateResponse(
        "tools/d5w_prep.html",
        {"request": request, "inputs": inputs, "result": result},
    )


@router.post("/tools/d5w-prep/compute", response_class=HTMLResponse)
async def d5w_prep_compute(
    request: Request,
    target_volume_ml: str = Form(""),
    target_percent: str = Form(""),
    stock_percent: str = Form(""),
):
    templates = request.app.state.templates
    tgt_vol = parse_positive_float(target_volume_ml)
    tgt_pct = parse_positive_float(target_percent)
    stk_pct = parse_positive_float(stock_percent)
    if tgt_vol is None or tgt_pct is None or stk_pct is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    inputs = SolutionPrepInputs(
        target_volume_ml=tgt_vol,
        target_percent=tgt_pct,
        stock_percent=stk_pct,
    )
    result = compute_solution_prep(inputs)
    return templates.TemplateResponse(
        "tools/partials/d5w_prep_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )


# ===========================================================================
# Unit converter (unified: body weight / drug amount / concentration / BSA)
# ===========================================================================


@router.get("/tools/converter", response_class=HTMLResponse)
async def converter_tool(request: Request):
    templates = request.app.state.templates
    # Sensible defaults for all four sections
    weight_value = 10.0
    weight_unit = "lb"
    dose_value = 10.0
    dose_unit = "mg"
    conc_value = 5.0
    conc_unit = "percent"
    bsa_weight = 10.0
    bsa_species = "dog"

    weight_result = convert_weight(weight_value, WeightFromUnit.KG)
    dose_result = convert_dose_amount(dose_value, dose_unit)
    conc_result = convert_concentration(conc_value, conc_unit)
    bsa_result = compute_bsa(bsa_weight, bsa_species)

    return templates.TemplateResponse(
        "tools/converter.html",
        {
            "request": request,
            "weight_value": weight_value,
            "weight_unit": weight_unit,
            "weight_result_template": "tools/partials/converter_weight_result.html",
            "dose_value": dose_value,
            "dose_unit": dose_unit,
            "conc_value": conc_value,
            "conc_unit": conc_unit,
            "bsa_weight": bsa_weight,
            "bsa_species": bsa_species,
            # the partials each look for `result` in their scope:
            "weight_result": weight_result,
            "dose_result": dose_result,
            "conc_result": conc_result,
            "bsa_result": bsa_result,
        },
    )


# Each section's HTMX endpoint. The result partial expects `result` (a single
# variable name) so each handler renders only its own partial.


@router.post("/tools/converter/weight", response_class=HTMLResponse)
async def converter_weight(
    request: Request,
    value: str = Form(""),
    unit: str = Form("lb"),
    species: str = Form("dog"),
):
    templates = request.app.state.templates
    val = parse_positive_float(value)
    if val is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request, "placeholder_id": "weight-result"},
        )
    try:
        u = WeightFromUnit(unit)
    except ValueError:
        u = WeightFromUnit.KG
    result = convert_weight(val, u)
    species_clean = species if species in ("dog", "cat") else "dog"
    bsa = compute_bsa(result.kg, species_clean)
    return templates.TemplateResponse(
        "tools/partials/converter_weight_result.html",
        {"request": request, "result": result, "bsa": bsa},
    )


@router.post("/tools/converter/dose", response_class=HTMLResponse)
async def converter_dose(
    request: Request,
    value: str = Form(""),
    unit: str = Form("mg"),
):
    templates = request.app.state.templates
    val = parse_positive_float(value)
    if val is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request, "placeholder_id": "dose-result"},
        )
    try:
        result = convert_dose_amount(val, unit)
    except ValueError:
        result = convert_dose_amount(0.0, "mg")
    return templates.TemplateResponse(
        "tools/partials/converter_dose_result.html",
        {"request": request, "result": result},
    )


@router.post("/tools/converter/concentration", response_class=HTMLResponse)
async def converter_concentration_route(
    request: Request,
    value: str = Form(""),
    unit: str = Form("percent"),
):
    templates = request.app.state.templates
    val = parse_positive_float(value)
    if val is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request, "placeholder_id": "concentration-result"},
        )
    try:
        result = convert_concentration(val, unit)
    except ValueError:
        result = convert_concentration(0.0, "percent")
    return templates.TemplateResponse(
        "tools/partials/converter_concentration_result.html",
        {"request": request, "result": result},
    )


@router.post("/tools/converter/bsa", response_class=HTMLResponse)
async def converter_bsa(
    request: Request,
    weight_kg: str = Form(""),
    species: str = Form("dog"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_kg)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request, "placeholder_id": "bsa-result"},
        )
    species_clean = species if species in ("dog", "cat") else "dog"
    result = compute_bsa(weight, species_clean)
    return templates.TemplateResponse(
        "tools/partials/converter_bsa_result.html",
        {"request": request, "result": result},
    )


# Redirect legacy URLs so old bookmarks / nav links still work.
@router.get("/tools/weight-converter")
async def weight_legacy_redirect_v1():
    return RedirectResponse(url="/tools/converter#weight", status_code=301)
