"""Osmolar gap calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.osmolar_gap import (
    OSMOLAR_GAP_CATALOG_ENTRY,
    BunUnit,
    GlucoseUnit,
    OsmolarGapInputs,
    compute_osmolar_gap,
)
from app.routers._form_parsing import parse_nonneg_float, parse_positive_float

router = APIRouter()


@router.get("/osmolar-gap", response_class=HTMLResponse)
async def osmolar_gap_page(request: Request):
    templates = request.app.state.templates
    inputs = OsmolarGapInputs()
    return templates.TemplateResponse(
        "osmolar_gap.html",
        {
            "request": request,
            "meta": OSMOLAR_GAP_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "na_value": "",
            "glucose_value": "",
            "bun_value": "",
            "measured_osm_value": "",
            "ethanol_value": "",
        },
    )


@router.post("/osmolar-gap/compute", response_class=HTMLResponse)
async def osmolar_gap_compute(
    request: Request,
    na_meq_per_l: str = Form(""),
    glucose_value: str = Form(""),
    glucose_unit: str = Form("mg_dl"),
    bun_value: str = Form(""),
    bun_unit: str = Form("mg_dl"),
    measured_osm_mosm_per_kg: str = Form(""),
    ethanol_mg_per_dl: str = Form(""),
):
    templates = request.app.state.templates

    na_val = parse_positive_float(na_meq_per_l)
    glucose_val = parse_positive_float(glucose_value)
    bun_val = parse_positive_float(bun_value)
    if na_val is None or glucose_val is None or bun_val is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": (
                    "Enter Na, glucose, and BUN (or urea) to compute "
                    "calculated osmolality. Add a measured osmolality "
                    "from the lab to compute the osmolar gap."
                ),
            },
        )

    # Optional values
    measured_osm_val = parse_nonneg_float(measured_osm_mosm_per_kg) or 0.0
    ethanol_val = parse_nonneg_float(ethanol_mg_per_dl) or 0.0

    try:
        gu = GlucoseUnit(glucose_unit)
    except ValueError:
        gu = GlucoseUnit.MG_DL
    try:
        bu = BunUnit(bun_unit)
    except ValueError:
        bu = BunUnit.MG_DL

    inputs = OsmolarGapInputs(
        na_meq_per_l=na_val,
        glucose_value=glucose_val,
        glucose_unit=gu,
        bun_value=bun_val,
        bun_unit=bu,
        measured_osm_mosm_per_kg=measured_osm_val,
        ethanol_mg_per_dl=ethanol_val,
    )
    result = compute_osmolar_gap(inputs)

    return templates.TemplateResponse(
        "partials/osmolar_gap_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
