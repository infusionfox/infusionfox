"""
IRIS CKD staging calculator for dogs and cats.

Implements the IRIS (International Renal Interest Society) 2023 staging
guidelines, using fasting blood creatinine plus optional SDMA, with
substaging by UPC and systolic blood pressure.

Source: International Renal Interest Society. IRIS Staging of CKD,
modified 2023. http://www.iris-kidney.com/guidelines/staging.html
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source
from app.routers._form_parsing import parse_float_with_default

router = APIRouter()


# ---------------------------------------------------------------------------
# IRIS staging tables (2023)
# ---------------------------------------------------------------------------
#
# Stage cutoffs are based on creatinine; SDMA is supplementary. When both are
# available, the patient is staged at the worse of the two.

# Creatinine thresholds (mg/dL). Per IRIS 2023, stage ranges are inclusive
# at the upper end (Stage 2: 1.4 to 2.8 mg/dL inclusive, Stage 3: 2.9 to
# 5.0 inclusive, Stage 4: >5.0). The `_stage_for` lookup uses `lo <= v < hi`,
# so the table's `hi` values are shifted by 0.1 to keep stage 2 inclusive of
# 2.8 and stage 3 inclusive of 5.0.
DOG_CREATININE_STAGES = [
    (1, 0.0, 1.4),    # Stage 1: <1.4 (with other CKD evidence)
    (2, 1.4, 2.9),    # Stage 2: 1.4 to 2.8 inclusive
    (3, 2.9, 5.1),    # Stage 3: 2.9 to 5.0 inclusive
    (4, 5.1, 999.0),  # Stage 4: >5.0
]

CAT_CREATININE_STAGES = [
    (1, 0.0, 1.6),    # Stage 1: <1.6
    (2, 1.6, 2.9),    # Stage 2: 1.6 to 2.8 inclusive
    (3, 2.9, 5.1),    # Stage 3: 2.9 to 5.0 inclusive
    (4, 5.1, 999.0),  # Stage 4: >5.0
]

# SDMA thresholds (µg/dL). Same inclusive-upper-end convention.
# IRIS 2023 cat SDMA: stage 3 is 26-38, stage 4 is >38 (NOT 45, a common
# spec-doc copy error). Shifted by 1 µg/dL since IRIS SDMA values are
# integer-aligned in the source table.
DOG_SDMA_STAGES = [
    (1, 0.0, 18.0),    # Stage 1: <18
    (2, 18.0, 36.0),   # Stage 2: 18 to 35 inclusive
    (3, 36.0, 55.0),   # Stage 3: 36 to 54 inclusive
    (4, 55.0, 9999.0), # Stage 4: >54
]

CAT_SDMA_STAGES = [
    (1, 0.0, 18.0),    # Stage 1: <18
    (2, 18.0, 26.0),   # Stage 2: 18 to 25 inclusive
    (3, 26.0, 39.0),   # Stage 3: 26 to 38 inclusive (was incorrectly 25-45)
    (4, 39.0, 9999.0), # Stage 4: >38 (was incorrectly ≥45)
]


def _stage_for(value: float, table: list) -> int:
    """Return IRIS stage for a value using the given threshold table."""
    if value <= 0:
        return 0
    for stage, lo, hi in table:
        if lo <= value < hi:
            return stage
    return 4


# UPC substaging (same for dogs and cats). Per IRIS 2023, the upper bound
# of borderline is inclusive: dog UPC 0.5 is Borderline (not Proteinuric);
# cat UPC 0.4 is Borderline. Use <= at the upper boundary.
def _upc_substage(upc: float, species: str) -> tuple[str, str]:
    """Return (label, abbreviation) for UPC substage."""
    if species == "cat":
        if upc < 0.2:
            return ("Non-proteinuric", "NP")
        elif upc <= 0.4:
            return ("Borderline proteinuric", "BP")
        else:
            return ("Proteinuric", "P")
    else:  # dog
        if upc < 0.2:
            return ("Non-proteinuric", "NP")
        elif upc <= 0.5:
            return ("Borderline proteinuric", "BP")
        else:
            return ("Proteinuric", "P")


# Blood pressure substaging
def _bp_substage(sbp: float) -> tuple[str, str, str]:
    """Return (label, abbreviation, target_organ_damage_risk) for SBP substage."""
    if sbp == 0:
        return ("Not measured", "—", "")
    if sbp < 140:
        return ("Normotensive", "N", "Minimal risk")
    elif sbp < 160:
        return ("Prehypertensive", "P", "Low risk")
    elif sbp < 180:
        return ("Hypertensive", "H", "Moderate risk")
    else:
        return ("Severely hypertensive", "S", "High risk")


# Stage descriptions (clinical narratives, paraphrased from IRIS guidelines)
STAGE_DESCRIPTIONS = {
    1: (
        "Non-azotemic. CKD diagnosed on the basis of other findings: "
        "persistent renal proteinuria, abnormal renal imaging, abnormal "
        "kidney palpation, persistently dilute urine in the absence of "
        "another cause, or persistently elevated SDMA above the reference "
        "interval. Clinical signs typically absent."
    ),
    2: (
        "Mild renal azotemia. Clinical signs absent or mild. The lower "
        "creatinine values within this stage may not yet exceed the "
        "laboratory reference interval."
    ),
    3: (
        "Moderate renal azotemia. Many systemic clinical signs may be "
        "present. The 2019 IRIS update split this into early Stage 3 (less "
        "advanced) and late Stage 3 (more advanced) for treatment "
        "stratification, particularly in dogs."
    ),
    4: (
        "Severe renal azotemia. Many systemic clinical signs and uremic "
        "complications likely. Risk for crisis is high; aggressive "
        "supportive care typically required."
    ),
}


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class IrisInputs:
    species: str = "dog"
    # Default 0 (not yet entered) rather than a clinically plausible
    # value. Pre-populating with 1.0 violated Safety Rule #8 (calculators
    # NEVER show output before the clinician enters values) — the form
    # loaded with creatinine 1.0 → engine staged the patient at Stage 1
    # → result panel displayed "Stage 1" before any user interaction.
    creatinine_mg_dl: float = 0.0
    sdma_ug_dl: float = 0.0  # 0 = not measured
    upc: float = 0.0  # 0 = not measured
    sbp_mmhg: float = 0.0  # 0 = not measured


@dataclass
class IrisResult:
    inputs: IrisInputs
    stage_creatinine: int
    stage_sdma: int
    final_stage: int
    stage_description: str
    upc_label: str
    upc_abbrev: str
    bp_label: str
    bp_abbrev: str
    bp_organ_risk: str
    # Whether the clinician has entered enough data to stage the patient.
    # False on the initial form load (no creatinine yet); True once
    # creatinine > 0 has been submitted. Gates the result panel display.
    computed: bool = False
    sources: tuple[Source, ...] = ()


def calculate(inputs: IrisInputs) -> IrisResult:
    species = inputs.species if inputs.species in ("dog", "cat") else "dog"

    # Safety Rule #8: don't display output before the clinician enters
    # values. Either creatinine OR SDMA is sufficient to stage — IRIS
    # 2023 guidelines stage by the worse of the two markers, and
    # SDMA-only staging is clinically valid when creatinine isn't
    # available (or when SDMA reflects renal function earlier in
    # subclinical CKD).
    if inputs.creatinine_mg_dl <= 0 and inputs.sdma_ug_dl <= 0:
        return IrisResult(
            inputs=inputs,
            stage_creatinine=0,
            stage_sdma=0,
            final_stage=0,
            stage_description="",
            upc_label="Not measured",
            upc_abbrev="—",
            bp_label="",
            bp_abbrev="",
            bp_organ_risk="",
            computed=False,
            sources=IRIS_SOURCES,
        )

    cr_table = DOG_CREATININE_STAGES if species == "dog" else CAT_CREATININE_STAGES
    sdma_table = DOG_SDMA_STAGES if species == "dog" else CAT_SDMA_STAGES

    stage_cr = _stage_for(inputs.creatinine_mg_dl, cr_table) if inputs.creatinine_mg_dl > 0 else 0
    stage_sdma = _stage_for(inputs.sdma_ug_dl, sdma_table) if inputs.sdma_ug_dl > 0 else 0

    # Final stage = worse of creatinine and SDMA. If only one is
    # measured, that one alone determines the stage.
    if stage_cr > 0 and stage_sdma > 0:
        final_stage = max(stage_cr, stage_sdma)
    elif stage_cr > 0:
        final_stage = stage_cr
    else:
        final_stage = stage_sdma

    upc_label, upc_abbrev = _upc_substage(inputs.upc, species) if inputs.upc > 0 else ("Not measured", "—")
    bp_label, bp_abbrev, bp_risk = _bp_substage(inputs.sbp_mmhg)

    return IrisResult(
        inputs=inputs,
        stage_creatinine=stage_cr,
        stage_sdma=stage_sdma,
        final_stage=final_stage,
        stage_description=STAGE_DESCRIPTIONS.get(final_stage, ""),
        upc_label=upc_label,
        upc_abbrev=upc_abbrev,
        bp_label=bp_label,
        bp_abbrev=bp_abbrev,
        bp_organ_risk=bp_risk,
        computed=True,
        sources=IRIS_SOURCES,
    )


IRIS_SOURCES = (
    Source(
        citation=(
            "International Renal Interest Society. IRIS Staging of CKD "
            "(modified 2023). http://www.iris-kidney.com/guidelines/staging.html"
        ),
        url="http://www.iris-kidney.com/guidelines/staging.html",
    ),
    Source(
        citation=(
            "Polzin DJ. Chronic kidney disease in small animals. "
            "Vet Clin North Am Small Anim Pract 2011;41:15–30."
        )
    ),
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/iris-staging", response_class=HTMLResponse)
async def iris_page(request: Request):
    templates = request.app.state.templates
    inputs = IrisInputs()
    result = calculate(inputs)
    return templates.TemplateResponse(
        "iris_staging.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


@router.post("/iris-staging/compute", response_class=HTMLResponse)
async def iris_compute(
    request: Request,
    species: str = Form("dog"),
    # Default 0.0 (not entered) on the POST path too. The HTMX `load`
    # trigger fires an empty submission immediately on page load;
    # without this default, the empty submission would fall back to
    # the old 1.0 default and re-trigger the Safety Rule #8 violation
    # (fake "Stage 1" headline before the clinician has entered data).
    creatinine_mg_dl: str = Form("0.0"),
    sdma_ug_dl: str = Form("0.0"),
    upc: str = Form("0.0"),
    sbp_mmhg: str = Form("0.0"),
):
    templates = request.app.state.templates
    inputs = IrisInputs(
        species=species,
        creatinine_mg_dl=parse_float_with_default(creatinine_mg_dl, 0.0),
        sdma_ug_dl=parse_float_with_default(sdma_ug_dl, 0.0),
        upc=parse_float_with_default(upc, 0.0),
        sbp_mmhg=parse_float_with_default(sbp_mmhg, 0.0),
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/iris_staging_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


IRIS_STAGING_CATALOG_ENTRY = {
    "slug": "iris-staging",
    "display_name": "IRIS CKD staging",
    "short_name": "IRIS",
    "category": "Endocrine & Metabolic",
    "kind": "diagnostic_score",
    "mechanism_summary": (
        "International Renal Interest Society staging for chronic kidney "
        "disease in dogs and cats. Stage 1–4 from creatinine and SDMA, "
        "substaged by UPC (proteinuria) and systolic blood pressure."
    ),
}
