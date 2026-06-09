"""Oxygenation (P:F ratio + A-a gradient) calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.oxygenation import (
    DEFAULT_PATM_MMHG,
    DEFAULT_R,
    OXYGENATION_CATALOG_ENTRY,
    FiO2Unit,
    OxygenationInputs,
    compute_oxygenation,
)
from app.routers._form_parsing import parse_nonneg_float, parse_positive_float

router = APIRouter()


@router.get("/oxygenation", response_class=HTMLResponse)
async def oxygenation_page(request: Request):
    templates = request.app.state.templates
    inputs = OxygenationInputs()
    return templates.TemplateResponse(
        "oxygenation.html",
        {
            "request": request,
            "meta": OXYGENATION_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "pao2_value": "",
            "fio2_value": "",
            "paco2_value": "",
            "patm_value": "",
            "r_value": "",
        },
    )


@router.post("/oxygenation/compute", response_class=HTMLResponse)
async def oxygenation_compute(
    request: Request,
    pao2_mmhg: str = Form(""),
    fio2_value: str = Form(""),
    fio2_unit: str = Form("decimal"),
    paco2_mmhg: str = Form(""),
    patm_mmhg: str = Form(""),
    respiratory_quotient: str = Form(""),
):
    templates = request.app.state.templates

    pao2_val = parse_positive_float(pao2_mmhg)
    fio2_val = parse_positive_float(fio2_value)
    paco2_val = parse_positive_float(paco2_mmhg)
    if pao2_val is None or fio2_val is None or paco2_val is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": (
                    "Enter PaO₂, FiO₂, and PaCO₂ to compute the P:F "
                    "ratio and A-a gradient."
                ),
            },
        )

    # Optional values
    patm_val = parse_nonneg_float(patm_mmhg) or DEFAULT_PATM_MMHG
    r_val = parse_nonneg_float(respiratory_quotient) or DEFAULT_R

    try:
        fu = FiO2Unit(fio2_unit)
    except ValueError:
        fu = FiO2Unit.DECIMAL

    inputs = OxygenationInputs(
        pao2_mmhg=pao2_val,
        fio2_value=fio2_val,
        fio2_unit=fu,
        paco2_mmhg=paco2_val,
        patm_mmhg=patm_val,
        respiratory_quotient=r_val,
    )
    result = compute_oxygenation(inputs)

    return templates.TemplateResponse(
        "partials/oxygenation_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
