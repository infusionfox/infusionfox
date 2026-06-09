"""Status epilepticus hub for canine patients — interactive workflow tool with weight-based dosing."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


# ---------------------------------------------------------------------------
# Drug catalog for canine status epilepticus
# ---------------------------------------------------------------------------


@dataclass
class StatusDrug:
    name: str
    stock: str
    dose_label: str
    dose_per_kg_mg: float  # for label only / mg
    volume_per_kg_ml: float  # mL of stock per kg
    route: str
    step: str  # which protocol step
    note: str = ""


# Doses are canine-specific; feline doses differ where noted in feline hub.
DOG_STATUS_DRUGS: list[StatusDrug] = [
    # ---- Step 1: First-line benzodiazepine ----
    StatusDrug(
        name="Diazepam (IV)",
        stock="5 mg/mL",
        dose_label="0.5 mg/kg IV",
        dose_per_kg_mg=0.5,
        volume_per_kg_ml=0.1,
        route="IV",
        step="step1",
        note="Repeat up to 3 times (5 min apart). Avoid in known severe hepatic disease.",
    ),
    StatusDrug(
        name="Diazepam (PR)",
        stock="5 mg/mL",
        dose_label="1–2 mg/kg PR",
        dose_per_kg_mg=2.0,
        volume_per_kg_ml=0.4,
        route="PR",
        step="step1",
        note="If no IV access. Volume shown is for 2 mg/kg; halve for 1 mg/kg.",
    ),
    StatusDrug(
        name="Midazolam (IV/IM/IN)",
        stock="5 mg/mL",
        dose_label="0.2 mg/kg",
        dose_per_kg_mg=0.2,
        volume_per_kg_ml=0.04,
        route="IV / IM / IN",
        step="step1",
        note="Intranasal route (split between nostrils) is excellent when no IV access. Repeat up to 3 times.",
    ),
    # ---- Step 2: AED loading ----
    StatusDrug(
        name="Levetiracetam IV",
        stock="100 mg/mL",
        dose_label="60 mg/kg IV",
        dose_per_kg_mg=60.0,
        volume_per_kg_ml=0.6,
        route="IV slow bolus over 5 min",
        step="step2",
        note="Preferred AED loading dose. Reduce to 30 mg/kg if cardiovascular concern. Maintenance: 20 mg/kg q8h IV/PO.",
    ),
    StatusDrug(
        name="Phenobarbital IV",
        stock="65 mg/mL",
        dose_label="4–6 mg/kg",
        dose_per_kg_mg=6.0,
        volume_per_kg_ml=0.092,
        route="IV slow bolus over 5–10 min",
        step="step2",
        note="Volume shown is for 6 mg/kg. Repeat to total 16–24 mg/kg max. Slow administration prevents hypotension/respiratory depression.",
    ),
    # ---- Step 3: Refractory / anesthetic CRIs ----
    StatusDrug(
        name="Midazolam CRI",
        stock="5 mg/mL",
        dose_label="0.1–0.5 mg/kg/hr",
        dose_per_kg_mg=0.3,
        volume_per_kg_ml=0.06,
        route="IV CRI",
        step="step3",
        note="Volume per HOUR shown is for 0.3 mg/kg/hr midpoint. Titrate to effect. Wean over hours, not abruptly.",
    ),
    StatusDrug(
        name="Propofol CRI",
        stock="10 mg/mL",
        dose_label="0.1–0.25 mg/kg/min",
        dose_per_kg_mg=0.15,
        volume_per_kg_ml=0.9,
        route="IV CRI",
        step="step3",
        note="Volume per HOUR shown is for 0.15 mg/kg/min midpoint (= 9 mg/kg/hr). Intubate. Max ≈48 hr. See InfusionFox propofol calculator for detail.",
    ),
    StatusDrug(
        name="Ketamine bolus",
        stock="100 mg/mL",
        dose_label="2 mg/kg IV",
        dose_per_kg_mg=2.0,
        volume_per_kg_ml=0.02,
        route="IV bolus",
        step="step3",
        note="Last-resort bolus for refractory status. May be followed by ketamine CRI 2–10 µg/kg/min.",
    ),
    # ---- Always-do supportive ----
    StatusDrug(
        name="50% dextrose (if hypoglycemic)",
        stock="0.5 g/mL",
        dose_label="0.5–1 mL/kg of 50%, diluted 1:4 with saline",
        dose_per_kg_mg=500.0,  # mg dextrose per kg at 1 mL/kg of 50%
        volume_per_kg_ml=1.0,
        route="IV slow bolus",
        step="supportive",
        note="Only if BG < 60 mg/dL. Always dilute 1:4 with 0.9% NaCl before administration. Volume shown is undiluted 50% dextrose at 1 mL/kg.",
    ),
]


@dataclass
class StatusDose:
    drug: StatusDrug
    total_mg: float
    volume_ml: float


@dataclass
class StatusResult:
    weight_kg: float
    weight_unit: str
    doses_step1: list[StatusDose] = field(default_factory=list)
    doses_step2: list[StatusDose] = field(default_factory=list)
    doses_step3: list[StatusDose] = field(default_factory=list)
    doses_supportive: list[StatusDose] = field(default_factory=list)
    sources: tuple[Source, ...] = ()


def calculate(weight_kg: float) -> StatusResult:
    s1, s2, s3, sup = [], [], [], []
    for drug in DOG_STATUS_DRUGS:
        dose = StatusDose(
            drug=drug,
            total_mg=round(drug.dose_per_kg_mg * weight_kg, 2),
            volume_ml=round(drug.volume_per_kg_ml * weight_kg, 3),
        )
        if drug.step == "step1":
            s1.append(dose)
        elif drug.step == "step2":
            s2.append(dose)
        elif drug.step == "step3":
            s3.append(dose)
        elif drug.step == "supportive":
            sup.append(dose)
    return StatusResult(
        weight_kg=weight_kg,
        weight_unit="lb",
        doses_step1=s1,
        doses_step2=s2,
        doses_step3=s3,
        doses_supportive=sup,
        sources=STATUS_SOURCES,
    )


def _to_kg(value: float, unit: str) -> float:
    return value / 2.2046 if unit == "lb" else value


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/status-canine", response_class=HTMLResponse)
async def status_canine_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "status_canine.html",
        {
            "request": request,
            "result": None,
            "weight_value": "",
            "weight_unit": "lb",
        },
    )


@router.post("/status-canine/compute", response_class=HTMLResponse)
async def status_canine_compute(
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
        "partials/status_canine_result.html",
        {
            "request": request,
            "result": result,
            "weight_value": weight,
            "weight_unit": weight_unit,
        },
    )


STATUS_SOURCES = (
    Source(
        citation=(
            "Charalambous M, Volk HA, Tipold A, et al. Comparison of intranasal "
            "versus intravenous midazolam for management of status epilepticus "
            "in dogs: a multi-center randomized parallel-group clinical trial. "
            "J Vet Intern Med 2019;33:2709–2717."
        )
    ),
    Source(
        citation=(
            "Hardy BT, Patterson EE, Cloyd JM, Hardy RM, Leppik IE. Double-masked, "
            "placebo-controlled study of intravenous levetiracetam for the "
            "treatment of status epilepticus and acute repetitive seizures in "
            "dogs. J Vet Intern Med 2012;26:334–340."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, monographs for diazepam, "
            "midazolam, levetiracetam, phenobarbital, propofol, ketamine. "
            "Bolus and CRI dosing for status epilepticus."
        )
    ),
    Source(
        citation=(
            "Bhatti SFM, De Risio L, Muñana K, et al. International Veterinary "
            "Epilepsy Task Force consensus proposal: medical treatment of canine "
            "epilepsy in Europe. BMC Vet Res 2015;11:176. (IVETF treatment "
            "guidelines including status epilepticus protocol.)"
        )
    ),
)
