"""Stewart strong-ion blood gas interpretation routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.blood_gas import Species
from app.calculators.blood_gas_stewart import (
    BLOOD_GAS_STEWART_CATALOG_ENTRY,
    StewartInputs,
    compute,
)
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


def _parse_species(value: str) -> Species:
    return Species.CAT if (value or "").strip().lower() == "cat" else Species.DOG


@router.get("/blood-gas-stewart", response_class=HTMLResponse)
async def blood_gas_stewart_page(request: Request):
    """Initial GET — empty form, placeholder where the result would go.

    Per the calculator default-output safety rule (CLAUDE.md #8), the
    decomposition does NOT render with default-valued inputs. A
    placeholder prompt sits in the result panel until the user has
    entered the minimum useful set (pH, PCO2, HCO3, Na, Cl, albumin).
    """
    templates = request.app.state.templates
    inputs = StewartInputs()
    return templates.TemplateResponse(
        "blood_gas_stewart.html",
        {
            "request": request,
            "inputs": inputs,
            "result": None,  # placeholder renders in result panel slot
            "species_choice": "dog",
        },
    )


@router.post("/blood-gas-stewart/compute", response_class=HTMLResponse)
async def blood_gas_stewart_compute(
    request: Request,
    species: str = Form("dog"),
    base_excess: str = Form(""),
    pH: str = Form(""),
    pco2_mm_hg: str = Form(""),
    hco3_meq_per_l: str = Form(""),
    na_meq_per_l: str = Form(""),
    k_meq_per_l: str = Form(""),
    cl_meq_per_l: str = Form(""),
    lactate_mmol_per_l: str = Form(""),
    albumin_g_per_dl: str = Form(""),
    phosphate_mg_per_dl: str = Form(""),
):
    """Decompose only when the minimum useful input set is present.

    Required: pH, PCO2, HCO3, Na, Cl, albumin. Without these the BE
    components have no anchor (no chloride effect without Cl, no
    albumin effect without albumin, no SIG without HCO3). Other inputs
    (K, lactate, phosphate, explicit BE) are optional enrichments.
    """
    templates = request.app.state.templates

    pH_val = parse_positive_float(pH)
    pco2_val = parse_positive_float(pco2_mm_hg)
    hco3_val = parse_positive_float(hco3_meq_per_l)
    na_val = parse_positive_float(na_meq_per_l)
    cl_val = parse_positive_float(cl_meq_per_l)
    alb_val = parse_positive_float(albumin_g_per_dl)

    required = {
        "pH": pH_val,
        "PCO₂": pco2_val,
        "HCO₃⁻": hco3_val,
        "Na": na_val,
        "Cl": cl_val,
        "albumin": alb_val,
    }
    missing = [label for label, v in required.items() if v is None]
    if missing:
        if len(missing) == 1:
            msg = f"Enter {missing[0]} to compute the Stewart decomposition."
        elif len(missing) == 2:
            msg = f"Enter {missing[0]} and {missing[1]} to compute the Stewart decomposition."
        else:
            msg = (
                "Enter " + ", ".join(missing[:-1]) + f", and {missing[-1]} "
                "to compute the Stewart decomposition."
            )
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": msg,
            },
        )

    sp = _parse_species(species)
    inputs = StewartInputs(
        species=sp,
        base_excess=parse_float_with_default(base_excess, 0.0),
        pH=pH_val,
        pco2_mm_hg=pco2_val,
        hco3_meq_per_l=hco3_val,
        na_meq_per_l=na_val,
        k_meq_per_l=parse_float_with_default(k_meq_per_l, 0.0),
        cl_meq_per_l=cl_val,
        lactate_mmol_per_l=parse_float_with_default(lactate_mmol_per_l, 0.0),
        albumin_g_per_dl=alb_val,
        phosphate_mg_per_dl=parse_float_with_default(phosphate_mg_per_dl, 0.0),
    )
    result = compute(inputs)
    return templates.TemplateResponse(
        "partials/blood_gas_stewart_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
            "species_choice": species,
        },
    )


# Catalog entry exposed for content.py to register
__all__ = ["router", "BLOOD_GAS_STEWART_CATALOG_ENTRY"]
