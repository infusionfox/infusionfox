"""Status epilepticus hub for feline patients — interactive workflow tool with weight-based dosing."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


@dataclass
class StatusDrug:
    name: str
    stock: str
    dose_label: str
    dose_per_kg_mg: float
    volume_per_kg_ml: float
    route: str
    step: str
    note: str = ""


# Feline-specific status epilepticus protocol
CAT_STATUS_DRUGS: list[StatusDrug] = [
    # ---- Step 1: First-line benzodiazepine ----
    StatusDrug(
        name="Diazepam (IV)",
        stock="5 mg/mL",
        dose_label="0.5 mg/kg IV",
        dose_per_kg_mg=0.5,
        volume_per_kg_ml=0.1,
        route="IV",
        step="step1",
        note="Single bolus or up to 3 doses (5 min apart). The historical hepatic necrosis concern in cats was specifically with oral repeated dosing, not acute IV bolus.",
    ),
    StatusDrug(
        name="Midazolam (IV/IM/IN)",
        stock="5 mg/mL",
        dose_label="0.2 mg/kg",
        dose_per_kg_mg=0.2,
        volume_per_kg_ml=0.04,
        route="IV / IM / IN",
        step="step1",
        note="Often preferred over diazepam in cats. Intranasal route excellent when no IV. Repeat up to 3 times.",
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
        note="Preferred AED loading. Reduce to 30 mg/kg if cardiovascular concern. Maintenance: 20 mg/kg q8h IV/PO.",
    ),
    StatusDrug(
        name="Phenobarbital IV",
        stock="65 mg/mL",
        dose_label="4–6 mg/kg",
        dose_per_kg_mg=6.0,
        volume_per_kg_ml=0.092,
        route="IV slow bolus over 5–10 min",
        step="step2",
        note="Volume shown is for 6 mg/kg. Repeat to total 16–24 mg/kg max. Cats clear phenobarbital more slowly than dogs. Extended sedation common.",
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
        note="Volume per HOUR shown is for 0.3 mg/kg/hr midpoint. Generally well tolerated in cats. Wean over hours.",
    ),
    StatusDrug(
        name="Propofol CRI",
        stock="10 mg/mL",
        dose_label="0.1–0.25 mg/kg/min",
        dose_per_kg_mg=0.15,
        volume_per_kg_ml=0.9,
        route="IV CRI",
        step="step3",
        note="Volume per HOUR shown is for 0.15 mg/kg/min midpoint (= 9 mg/kg/hr). Cats are more prone to oxidative injury (Heinz bodies) with prolonged propofol. Limit to ≤24 hr where possible. Intubate.",
    ),
    StatusDrug(
        name="Ketamine bolus",
        stock="100 mg/mL",
        dose_label="2 mg/kg IV",
        dose_per_kg_mg=2.0,
        volume_per_kg_ml=0.02,
        route="IV bolus",
        step="step3",
        note="Last-resort bolus. Avoid in cats with HCM. May be followed by ketamine CRI 2–10 µg/kg/min.",
    ),
    # ---- Always-do supportive ----
    StatusDrug(
        name="50% dextrose (if hypoglycemic)",
        stock="0.5 g/mL",
        dose_label="0.5–1 mL/kg of 50%, diluted 1:4 with saline",
        dose_per_kg_mg=500.0,
        volume_per_kg_ml=1.0,
        route="IV slow bolus",
        step="supportive",
        note="Only if BG < 60 mg/dL. Always dilute 1:4 with 0.9% NaCl. Volume shown is undiluted 50% dextrose at 1 mL/kg.",
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
    for drug in CAT_STATUS_DRUGS:
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
        sources=CAT_STATUS_SOURCES,
    )


def _to_kg(value: float, unit: str) -> float:
    return value / 2.2046 if unit == "lb" else value


@router.get("/status-feline", response_class=HTMLResponse)
async def status_feline_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "status_feline.html",
        {
            "request": request,
            "result": None,
            "weight_value": "",
            "weight_unit": "lb",
        },
    )


@router.post("/status-feline/compute", response_class=HTMLResponse)
async def status_feline_compute(
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
        "partials/status_feline_result.html",
        {
            "request": request,
            "result": result,
            "weight_value": weight,
            "weight_unit": weight_unit,
        },
    )


CAT_STATUS_SOURCES = (
    Source(
        citation=(
            "Pakozdy A, Halasz P, Klang A. Epilepsy in cats: theory and practice. "
            "J Vet Intern Med 2014;28:255–263."
        )
    ),
    Source(
        citation=(
            "Hardy BT, Patterson EE, Cloyd JM, Hardy RM, Leppik IE. Double-masked, "
            "placebo-controlled study of intravenous levetiracetam for the "
            "treatment of status epilepticus and acute repetitive seizures in "
            "dogs. J Vet Intern Med 2012;26:334–340. (Also referenced for cat "
            "extrapolation; species-specific levetiracetam IV studies are limited.)"
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, monographs for diazepam, "
            "midazolam, levetiracetam, phenobarbital, propofol, ketamine. "
            "Bolus and CRI dosing for status epilepticus, with cat-specific "
            "cautions for propofol prolonged-use oxidative injury."
        )
    ),
    Source(
        citation=(
            "Charalambous M, Bhatti SFM, Van Ham L, et al. Intranasal midazolam "
            "versus rectal diazepam for the management of canine status "
            "epilepticus: a multicenter randomized parallel-group clinical trial. "
            "J Vet Intern Med 2017;31:1149–1158. (Foundational intranasal "
            "midazolam evidence; technique extrapolated to cats.)"
        )
    ),
)
