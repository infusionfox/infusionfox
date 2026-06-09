"""RECOVER CPR dosing calculator, weight-based doses from the 2024 RECOVER guidelines chart."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source
from app.routers._form_parsing import parse_positive_float

router = APIRouter()

WEIGHT_BREAKPOINTS = [2.5, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]


@dataclass
class CprDrug:
    name: str
    concentration: str  # e.g. "1:1000, 1mg/mL"
    dose_label: str  # e.g. "0.01 mg/kg"
    dose_per_kg: float
    unit: str  # "mL", all doses expressed as mL of stock
    category: str
    note: str = ""


# All doses expressed as mL of the stock solution listed on the RECOVER chart
CPR_DRUGS: list[CprDrug] = [
    # Arrest
    CprDrug(
        "Epinephrine", "1:1000 (1 mg/mL)", "0.01 mg/kg", 0.01, "mL", "Arrest", "IV/IO. Repeat every 3–5 min."
    ),
    CprDrug(
        "Vasopressin",
        "20 U/mL",
        "0.8 U/kg",
        0.04,
        "mL",
        "Arrest",
        "IV/IO. May substitute or alternate with epinephrine.",
    ),
    CprDrug(
        "Atropine",
        "0.4–0.54 mg/mL",
        "~0.05 mg/kg",
        0.092,
        "mL",
        "Arrest",
        "IV/IO. PEA/asystole. Administer rapidly.",
    ),
    # Anti-arrhythmic
    CprDrug(
        "Amiodarone",
        "50 mg/mL",
        "5 mg/kg",
        0.1,
        "mL",
        "Anti-arrhythmic",
        "IV/IO bolus for refractory VF/pVT.",
    ),
    CprDrug(
        "Lidocaine",
        "20 mg/mL",
        "2 mg/kg",
        0.1,
        "mL",
        "Anti-arrhythmic",
        "IV/IO bolus. Alternative to amiodarone for VF/pVT.",
    ),
    CprDrug(
        "Esmolol",
        "10 mg/mL",
        "0.5 mg/kg",
        0.05,
        "mL",
        "Anti-arrhythmic",
        "IV/IO. *Administer over 3–5 min, followed by CRI at 50 µg/kg/min.",
    ),
    # Reversal
    CprDrug(
        "Naloxone", "0.4 mg/mL", "0.04 mg/kg", 0.1, "mL", "Reversal", "IV/IO/IM/intranasal. Opioid reversal."
    ),
    CprDrug(
        "Flumazenil", "0.1 mg/mL", "0.01 mg/kg", 0.1, "mL", "Reversal", "IV/IO. Benzodiazepine reversal."
    ),
    CprDrug(
        "Atipamezole",
        "5 mg/mL",
        "100 µg/kg",
        0.02,
        "mL",
        "Reversal",
        "IM. Alpha-2 reversal. Volume = same as dexmedetomidine dose.",
    ),
]


@dataclass
class CprDose:
    drug: CprDrug
    volume_ml: float
    note: str = ""


@dataclass
class DefibEnergies:
    """Defibrillation energy doses per RECOVER 2024.

    Biphasic is recommended over monophasic. The 2024 update introduced an
    escalation strategy for biphasic external: 2 J/kg first attempt, double
    to 4 J/kg if a shockable rhythm persists and maintain for all subsequent
    shocks. Monophasic uses the legacy range; no formal escalation strategy
    is published for monophasic devices.

    Internal (open-chest) values are ranges for both waveforms.
    """

    weight_kg: float
    # Raw J values for testing/auditing.
    biphasic_first_ext_j: float  # 2 J/kg
    biphasic_escalate_ext_j: float  # 4 J/kg
    biphasic_int_low_j: float  # 0.2 J/kg
    biphasic_int_high_j: float  # 0.4 J/kg
    monophasic_ext_low_j: float  # 4 J/kg
    monophasic_ext_high_j: float  # 6 J/kg
    monophasic_int_low_j: float  # 0.5 J/kg
    monophasic_int_high_j: float  # 1 J/kg
    # Pre-formatted display strings (with units).
    biphasic_first_ext_display: str = ""
    biphasic_escalate_ext_display: str = ""
    biphasic_int_display: str = ""
    monophasic_ext_display: str = ""
    monophasic_int_display: str = ""


def _fmt_j(j: float) -> str:
    """Round joule values for display: integer when ≥ 5 J, one decimal below."""
    if j >= 5:
        return f"{round(j):d}"
    s = f"{j:.1f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _fmt_range(low: float, high: float) -> str:
    return f"{_fmt_j(low)}–{_fmt_j(high)} J"


@dataclass
class CprResult:
    weight_kg: float
    weight_unit: str
    doses: list[CprDose] = field(default_factory=list)
    defib: DefibEnergies | None = None
    sources: tuple[Source, ...] = ()


def _defib(weight_kg: float) -> DefibEnergies:
    """Compute biphasic and monophasic defibrillation energies."""
    biphasic_first = 2.0 * weight_kg
    biphasic_escalate = 4.0 * weight_kg
    biphasic_int_low = 0.2 * weight_kg
    biphasic_int_high = 0.4 * weight_kg
    mono_ext_low = 4.0 * weight_kg
    mono_ext_high = 6.0 * weight_kg
    mono_int_low = 0.5 * weight_kg
    mono_int_high = 1.0 * weight_kg
    return DefibEnergies(
        weight_kg=weight_kg,
        biphasic_first_ext_j=biphasic_first,
        biphasic_escalate_ext_j=biphasic_escalate,
        biphasic_int_low_j=biphasic_int_low,
        biphasic_int_high_j=biphasic_int_high,
        monophasic_ext_low_j=mono_ext_low,
        monophasic_ext_high_j=mono_ext_high,
        monophasic_int_low_j=mono_int_low,
        monophasic_int_high_j=mono_int_high,
        biphasic_first_ext_display=f"{_fmt_j(biphasic_first)} J",
        biphasic_escalate_ext_display=f"{_fmt_j(biphasic_escalate)} J",
        biphasic_int_display=_fmt_range(biphasic_int_low, biphasic_int_high),
        monophasic_ext_display=_fmt_range(mono_ext_low, mono_ext_high),
        monophasic_int_display=_fmt_range(mono_int_low, mono_int_high),
    )


def calculate(weight_kg: float) -> CprResult:
    doses = []
    for drug in CPR_DRUGS:
        vol = drug.dose_per_kg * weight_kg
        doses.append(CprDose(drug=drug, volume_ml=vol, note=drug.note))

    return CprResult(
        weight_kg=weight_kg,
        weight_unit="lb",
        doses=doses,
        defib=_defib(weight_kg),
        sources=CPR_SOURCES,
    )


def _to_kg(value: float, unit: str) -> float:
    return value / 2.2046 if unit == "lb" else value


@router.get("/cpr", response_class=HTMLResponse)
async def cpr_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "cpr.html",
        {
            "request": request,
            "result": None,
            "weight_value": "",
            "weight_unit": "lb",
        },
    )


@router.post("/cpr/compute", response_class=HTMLResponse)
async def cpr_compute(
    request: Request,
    weight_value: str = Form(""),
    weight_unit: str = Form("lb"),
):
    templates = request.app.state.templates
    weight = parse_positive_float(weight_value)
    if weight is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )
    weight_kg = _to_kg(weight, weight_unit)
    result = calculate(weight_kg)
    result.weight_unit = weight_unit
    return templates.TemplateResponse(
        "partials/cpr_result.html",
        {
            "request": request,
            "result": result,
            "weight_value": weight,
            "weight_unit": weight_unit,
        },
    )


CPR_SOURCES = (
    Source(
        citation=(
            "Hoehne SN, Hopper K, Epstein SE. Reassessment Campaign on Veterinary "
            "Resuscitation (RECOVER) 2024 evidence and knowledge gap analysis: "
            "Basic life support. J Vet Emerg Crit Care 2024 (and accompanying "
            "advanced life support, monitoring, post-cardiac arrest, and "
            "prevention/preparedness papers)."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, monographs for epinephrine, "
            "vasopressin, atropine, amiodarone, lidocaine, esmolol, naloxone, "
            "flumazenil, atipamezole. Stock concentrations and emergency dose "
            "conversions."
        )
    ),
)
