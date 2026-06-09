"""LDDST interpretation routes (one-off)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.lddst import (
    DEFAULT_8H_CUTOFF_UG_DL,
    LDDST_CATALOG_ENTRY,
    CortisolUnit,
    LDDSTInputs,
    interpret_lddst,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


@router.get("/lddst", response_class=HTMLResponse)
async def lddst_page(request: Request):
    templates = request.app.state.templates
    inputs = LDDSTInputs(
        baseline_cortisol=4.0,
        cortisol_4h=1.6,
        cortisol_8h=2.0,
        cutoff_8h=DEFAULT_8H_CUTOFF_UG_DL,
        unit=CortisolUnit.UG_PER_DL,
    )
    result = interpret_lddst(inputs)
    return templates.TemplateResponse(
        "lddst.html",
        {
            "request": request,
            "meta": LDDST_CATALOG_ENTRY,
            "inputs": inputs,
            "result": result,
            "DEFAULT_CUTOFF": DEFAULT_8H_CUTOFF_UG_DL,
        },
    )


@router.post("/lddst/compute", response_class=HTMLResponse)
async def lddst_compute(
    request: Request,
    baseline_cortisol: str = Form(""),
    cortisol_4h: str = Form(""),
    cortisol_8h: str = Form(""),
    cutoff_8h: str = Form(str(DEFAULT_8H_CUTOFF_UG_DL)),
    unit: str = Form("ug_dl"),
):
    templates = request.app.state.templates
    baseline = parse_positive_float(baseline_cortisol)
    c4h = parse_positive_float(cortisol_4h)
    c8h = parse_positive_float(cortisol_8h)
    if baseline is None or c4h is None or c8h is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": (
                    "Enter baseline, 4-hour, and 8-hour cortisol values "
                    "to interpret the test."
                ),
            },
        )
    cutoff = parse_float_with_default(cutoff_8h, DEFAULT_8H_CUTOFF_UG_DL)
    try:
        u = CortisolUnit(unit)
    except ValueError:
        u = CortisolUnit.UG_PER_DL
    inputs = LDDSTInputs(
        baseline_cortisol=baseline,
        cortisol_4h=c4h,
        cortisol_8h=c8h,
        cutoff_8h=cutoff,
        unit=u,
    )
    result = interpret_lddst(inputs)
    return templates.TemplateResponse(
        "partials/lddst_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
