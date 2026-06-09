"""
Transfusion volume and rate calculator for dogs and cats.

Supports three products:
  - pRBC (packed red blood cells)
  - Whole blood (fresh or stored)
  - FFP (fresh frozen plasma)

For pRBC and whole blood, the calculator uses the precise formula:
  Volume = [(PCV_target - PCV_current) / PCV_donor] × blood_volume_recipient

where blood volume = 90 mL/kg (dog), 60 mL/kg (cat). PCV_donor defaults are
60% for whole blood and 80% for pRBC.

For FFP, dosing is weight-based: 10-20 mL/kg.

Sources:
  - Davidow B. Transfusion medicine in small animals. Vet Clin North Am
    Small Anim Pract 2013;43:735-756.
  - Plumb's Veterinary Drugs: blood products section.
  - ACVIM Consensus Statement on the diagnosis of immune-mediated
    hemolytic anemia (transfusion section), J Vet Intern Med 2019.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source
from app.routers._form_parsing import parse_float_with_default, parse_positive_float

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BLOOD_VOLUME_PER_KG = {"dog": 90.0, "cat": 60.0}  # mL/kg

# Default donor PCV by product type (%). User can override.
DEFAULT_DONOR_PCV = {"prbc": 80.0, "whole_blood": 60.0}


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class TransfusionInputs:
    species: str = "dog"
    weight_value: float = 22.0
    weight_unit: str = "lb"
    product: str = "prbc"  # "prbc" | "whole_blood" | "ffp"
    pcv_current: float = 18.0
    pcv_target: float = 25.0
    pcv_donor: float = 0.0  # 0 = use default
    ffp_dose_ml_kg: float = 10.0


@dataclass
class TransfusionResult:
    inputs: TransfusionInputs
    weight_kg: float
    blood_volume_ml: float  # patient's total blood volume
    total_volume_ml: float
    donor_pcv: float  # effective donor PCV (default or user-provided); 0 for FFP
    slow_trial_rate_ml_hr: float  # for first 30 min
    main_rate_ml_hr: float  # after slow trial
    main_duration_hr: float  # remaining time after slow trial
    diphenhydramine_mg: float
    diphenhydramine_ml: float  # at 50 mg/mL
    warnings: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()


def _to_kg(value: float, unit: str) -> float:
    return value / 2.2046 if unit == "lb" else value


def calculate(inputs: TransfusionInputs) -> TransfusionResult:
    species = inputs.species if inputs.species in ("dog", "cat") else "dog"
    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    blood_volume = BLOOD_VOLUME_PER_KG[species] * weight_kg

    warnings = []
    total_volume = 0.0
    donor_pcv: float = 0.0  # FFP has no donor PCV; populated for blood products below

    if inputs.product == "ffp":
        # FFP is weight-based dosing
        dose = max(5.0, min(30.0, inputs.ffp_dose_ml_kg))  # clamp to sane range
        total_volume = dose * weight_kg
        if dose < 10:
            warnings.append("FFP doses below 10 mL/kg may be insufficient for clotting factor replacement.")
        if dose > 20:
            warnings.append(
                "FFP doses above 20 mL/kg are unusual; consider whether plasma volume expansion is the actual goal."
            )
    else:
        # pRBC or whole blood
        donor_pcv = inputs.pcv_donor if inputs.pcv_donor > 0 else DEFAULT_DONOR_PCV.get(inputs.product, 60.0)

        pcv_rise_needed = inputs.pcv_target - inputs.pcv_current
        if pcv_rise_needed <= 0:
            warnings.append("Target PCV is at or below current PCV; transfusion may not be indicated.")
            total_volume = 0.0
        else:
            total_volume = (pcv_rise_needed / donor_pcv) * blood_volume

        if inputs.pcv_target > 35:
            warnings.append(
                "PCV targets above 35% are usually unnecessary; aim for clinical stability rather than reference-range PCV."
            )

        if total_volume > 22.0 * weight_kg:
            warnings.append(
                "Calculated volume exceeds 22 mL/kg, which is unusually large for a single transfusion. Consider splitting into multiple transfusions or reassessing target PCV."
            )

    # Rate calculations
    # Slow trial: 0.25 mL/kg over first 15-30 min for monitoring of acute reactions
    # Use 0.5 mL/kg/hr for the trial period (30 min trial = 0.25 mL/kg total)
    slow_trial_rate = 0.5 * weight_kg if total_volume > 0 else 0.0

    # Main rate: aim to complete within 4 hours total
    # Volume already given in slow trial = 0.25 mL/kg
    slow_trial_volume = 0.25 * weight_kg
    remaining_volume = max(0.0, total_volume - slow_trial_volume)
    main_duration = 3.5  # 4 hr total minus 30 min slow trial
    main_rate = remaining_volume / main_duration if remaining_volume > 0 else 0.0

    # Cap main rate at 10 mL/kg/hr (clinical maximum for cardiovascularly stable patients)
    max_rate = 10.0 * weight_kg
    if main_rate > max_rate:
        main_rate = max_rate
        actual_duration = remaining_volume / max_rate
        main_duration = round(actual_duration + 0.5, 1)  # +0.5 hr for slow trial
        warnings.append(
            f"Main rate capped at 10 mL/kg/hr; total transfusion will take ~{main_duration:.1f} hr. "
            "Consider splitting into multiple transfusions if hemodynamically unstable."
        )
        main_duration = actual_duration

    # Diphenhydramine premedication: 1-2 mg/kg IM (use 1 mg/kg as standard)
    diphen_mg = round(1.0 * weight_kg, 1)
    diphen_ml = round(diphen_mg / 50.0, 2)  # 50 mg/mL stock

    return TransfusionResult(
        inputs=inputs,
        weight_kg=weight_kg,
        blood_volume_ml=round(blood_volume, 1),
        total_volume_ml=round(total_volume, 1),
        donor_pcv=donor_pcv,
        slow_trial_rate_ml_hr=round(slow_trial_rate, 2),
        main_rate_ml_hr=round(main_rate, 2),
        main_duration_hr=round(main_duration, 2),
        diphenhydramine_mg=diphen_mg,
        diphenhydramine_ml=diphen_ml,
        warnings=warnings,
        sources=TRANSFUSION_SOURCES,
    )


TRANSFUSION_SOURCES = (
    Source(
        citation=(
            "Davidow B. Transfusion medicine in small animals. Vet Clin North "
            "Am Small Anim Pract 2013;43:735–756."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs: Blood products. Volume "
            "calculations for pRBC, whole blood, and fresh frozen plasma."
        )
    ),
    Source(
        citation=(
            "Garden OA, Kidd L, Mexas AM, et al. ACVIM consensus statement "
            "on the diagnosis of immune-mediated hemolytic anemia in dogs "
            "and cats. J Vet Intern Med 2019;33:313–334. (Transfusion "
            "section.)"
        )
    ),
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/transfusion", response_class=HTMLResponse)
async def transfusion_page(request: Request):
    templates = request.app.state.templates
    inputs = TransfusionInputs()
    return templates.TemplateResponse(
        "transfusion.html",
        {
            "request": request,
            "inputs": inputs,
            "result": None,
            "weight_value": "",
            "sources": TRANSFUSION_SOURCES,
        },
    )


@router.post("/transfusion/compute", response_class=HTMLResponse)
async def transfusion_compute(
    request: Request,
    species: str = Form("dog"),
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
    product: str = Form("prbc"),
    pcv_current: str = Form("18.0"),
    pcv_target: str = Form("25.0"),
    pcv_donor: str = Form("0.0"),
    ffp_dose_ml_kg: str = Form("10.0"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    cur = parse_float_with_default(pcv_current, 18.0)
    tgt = parse_float_with_default(pcv_target, 25.0)
    donor = parse_float_with_default(pcv_donor, 0.0)
    ffp = parse_float_with_default(ffp_dose_ml_kg, 10.0)
    inputs = TransfusionInputs(
        species=species,
        weight_value=weight,
        weight_unit=weight_unit,
        product=product,
        pcv_current=cur,
        pcv_target=tgt,
        pcv_donor=donor,
        ffp_dose_ml_kg=ffp,
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/transfusion_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )
