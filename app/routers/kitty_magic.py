"""Kitty Magic (DKT / Triple Combination) calculator route."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import lb_to_kg
from app.calculators.kitty_magic import (
    KittyMagicInputs,
    KittyMagicLevel,
    KittyMagicOpioid,
    calculate,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()

_DEFAULT_INPUTS = KittyMagicInputs(
    weight_kg=4.5,
    opioid=KittyMagicOpioid.BUTORPHANOL,
    level=KittyMagicLevel.MODERATE,
)


def _parse_inputs(
    weight_value: float,
    weight_unit: str,
    opioid: str,
    level: str,
) -> KittyMagicInputs:
    weight_kg = lb_to_kg(weight_value) if weight_unit == "lb" else weight_value
    try:
        opioid_enum = KittyMagicOpioid(opioid)
    except ValueError:
        opioid_enum = KittyMagicOpioid.BUTORPHANOL
    try:
        level_enum = KittyMagicLevel(level)
    except ValueError:
        level_enum = KittyMagicLevel.MODERATE
    return KittyMagicInputs(weight_kg=weight_kg, opioid=opioid_enum, level=level_enum)


@router.get("/kitty-magic", response_class=HTMLResponse)
async def kitty_magic_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "kitty_magic.html",
        {
            "request": request,
            "result": None,
            "weight_value": "",
            "weight_unit": "lb",
        },
    )


@router.post("/kitty-magic/compute", response_class=HTMLResponse)
async def kitty_magic_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    opioid: str = Form("butorphanol"),
    level: str = Form("moderate"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )

    # Convert to kg for the range check.
    weight_kg_check = lb_to_kg(weight) if weight_unit == "lb" else weight

    # Kitty magic is feline-specific; the Plumb's table covers 2–8 kg.
    # Mildly out of range still computes — the calculator handles that
    # with a warning banner from the nearest band. The placeholder fires
    # only when the weight is far outside any plausible cat. 12 kg is a
    # comfortable upper bound covering large/obese cats and the heaviest
    # cat breeds while flagging dog-sized patients as wrong-calculator
    # errors. Below 1.5 kg the table doesn't extrapolate meaningfully
    # (neonates need different dosing).
    if weight_kg_check < 1.5 or weight_kg_check > 12.0:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": (
                    f"Patient weight ({weight} {weight_unit}) is outside "
                    "the kitty magic table range (2–8 kg / 4–18 lb). "
                    "This protocol is feline-specific. For larger patients, "
                    "see the anesthesia worksheet or species-appropriate sedation calculator."
                ),
            },
        )

    inputs = _parse_inputs(weight, weight_unit, opioid, level)
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/kitty_magic_result.html",
        {
            "request": request,
            "result": result,
            "weight_value": weight,
            "weight_unit": weight_unit,
        },
    )
