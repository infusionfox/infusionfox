"""Hypokalemia / KCl supplementation calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators import WeightUnit
from app.calculators.hypokalemia import (
    HYPOKALEMIA_CATALOG_ENTRY,
    HYPOKALEMIA_SCALE,
    BagSize,
    HypokalemiaInputs,
    compute_hypokalemia,
)
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


@router.get("/hypokalemia", response_class=HTMLResponse)
async def hypokalemia_page(request: Request):
    templates = request.app.state.templates
    inputs = HypokalemiaInputs(
        weight_value=1.0,
        weight_unit=WeightUnit.LB,
        serum_k_meq_per_l=2.8,
        bag_size=BagSize.BAG_1000,
    )
    return templates.TemplateResponse(
        "hypokalemia.html",
        {
            "request": request,
            "meta": HYPOKALEMIA_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "scale_rows": HYPOKALEMIA_SCALE,
        },
    )


@router.post("/hypokalemia/compute", response_class=HTMLResponse)
async def hypokalemia_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    serum_k_meq_per_l: str = Form(""),
    bag_size: str = Form("1000"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    serum_k = parse_positive_float(serum_k_meq_per_l)
    if weight is None or serum_k is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    try:
        wu = WeightUnit(weight_unit)
    except ValueError:
        wu = WeightUnit.LB
    try:
        bs = BagSize(bag_size)
    except ValueError:
        bs = BagSize.BAG_1000

    inputs = HypokalemiaInputs(
        weight_value=weight,
        weight_unit=wu,
        serum_k_meq_per_l=serum_k,
        bag_size=bs,
    )
    result = compute_hypokalemia(inputs)
    return templates.TemplateResponse(
        "partials/hypokalemia_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
