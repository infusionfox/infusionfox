"""Blood gas interpretation calculator routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.blood_gas import (
    BLOOD_GAS_CATALOG_ENTRY,
    CAT_ARTERIAL,
    CAT_VENOUS,
    DOG_ARTERIAL,
    DOG_VENOUS,
    Acuity,
    BloodGasInputs,
    SampleType,
    Species,
    compute_blood_gas,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


# Reference range hints shown inline under each numeric input. All four
# combinations are rendered server-side; CSS `:has()` selectors on the
# form show only the active species + sample pair. Avoids a JS handler
# and avoids re-rendering the form on every radio change.
_REF_RANGES = {
    "dog-arterial": DOG_ARTERIAL,
    "dog-venous": DOG_VENOUS,
    "cat-arterial": CAT_ARTERIAL,
    "cat-venous": CAT_VENOUS,
}


@router.get("/blood-gas", response_class=HTMLResponse)
async def blood_gas_page(request: Request):
    templates = request.app.state.templates
    # Initial GET renders empty input fields and no computed result. The
    # placeholder partial prompts the user to enter pH, PCO2, and HCO3-.
    # Showing a pre-populated "normal" result on load risks giving a
    # clinician a misleading impression that the calculator has read
    # their patient's values when it hasn't.
    inputs = BloodGasInputs(
        species=Species.DOG,
        sample=SampleType.ARTERIAL,
        acuity=Acuity.ACUTE,
    )
    return templates.TemplateResponse(
        "blood_gas.html",
        {
            "request": request,
            "meta": BLOOD_GAS_CATALOG_ENTRY,
            "inputs": inputs,
            "result": None,
            "pH_value": "",
            "pco2_value": "",
            "hco3_value": "",
            "na_value": "",
            "cl_value": "",
            "alb_value": "",
            "ref_ranges": _REF_RANGES,
        },
    )


@router.post("/blood-gas/compute", response_class=HTMLResponse)
async def blood_gas_compute(
    request: Request,
    species: str = Form("dog"),
    sample: str = Form("arterial"),
    acuity: str = Form("acute"),
    pH: str = Form(""),
    pco2_mm_hg: str = Form(""),
    hco3_meq_per_l: str = Form(""),
    na_meq_per_l: str = Form(""),
    cl_meq_per_l: str = Form(""),
    albumin_g_per_dl: str = Form(""),
):
    templates = request.app.state.templates

    # pH/PCO2/HCO3- are required; if any is missing or invalid, render
    # the placeholder instead of a half-computed result.
    pH_val = parse_positive_float(pH)
    pco2_val = parse_positive_float(pco2_mm_hg)
    hco3_val = parse_positive_float(hco3_meq_per_l)
    if pH_val is None or pco2_val is None or hco3_val is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": (
                    "Enter pH, PCO₂, and HCO₃⁻ to interpret the blood gas."
                ),
            },
        )

    # Na, Cl, and albumin are optional. parse_float_with_default returns
    # 0.0 when the field is empty, which the compute function treats as
    # "not provided" (anion gap and the Figge correction get skipped).
    na_val = parse_float_with_default(na_meq_per_l, 0.0)
    cl_val = parse_float_with_default(cl_meq_per_l, 0.0)
    alb_val = parse_float_with_default(albumin_g_per_dl, 0.0)

    try:
        sp = Species(species)
    except ValueError:
        sp = Species.DOG
    try:
        smp = SampleType(sample)
    except ValueError:
        smp = SampleType.ARTERIAL
    try:
        ac = Acuity(acuity)
    except ValueError:
        ac = Acuity.ACUTE

    inputs = BloodGasInputs(
        species=sp,
        sample=smp,
        acuity=ac,
        pH=pH_val,
        pco2_mm_hg=pco2_val,
        hco3_meq_per_l=hco3_val,
        na_meq_per_l=na_val,
        cl_meq_per_l=cl_val,
        albumin_g_per_dl=alb_val,
    )
    result = compute_blood_gas(inputs)

    return templates.TemplateResponse(
        "partials/blood_gas_result.html",
        {"request": request, "inputs": inputs, "result": result},
    )
