"""
Hypoadrenocorticism (Addison's disease) pretest probability score for dogs.

A structured pretest score adapted from the variables identified in:
  - Reagan KL, Reagan BA, Gilor C. Predicting the likelihood of
    hypoadrenocorticism in dogs using signalment and routine laboratory
    results with an ensemble machine learning predictive model. J Vet
    Intern Med 2026;40:e70067 (Addison Detect Tool / ADT).
  - Bennaim M, Centola S, Ramsey IK, et al. Can we predict hypoadreno-
    corticism in dogs with resting hypocortisolemia? J Vet Intern Med
    2024;38:1546–1556.

The original ADT used random forest; this is a simplified additive
adaptation for infusionfox use, prioritizing the published high-value
predictors (Na/K ratio, signalment, lymphocyte count, eosinophil count,
and the classic clinical syndrome).

Used to triage which dogs warrant ACTH stim testing — particularly the
atypical ENEKH (eunatremic, eukalemic) cases that get missed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source
from app.routers._form_parsing import parse_float_with_default

router = APIRouter()


# ---------------------------------------------------------------------------
# Predictors (additive adaptation of ADT high-value variables)
# ---------------------------------------------------------------------------


# Na/K ratio: classical hyponatremic hyperkalemic Addison's has Na:K < 27
def na_k_ratio_points(ratio: float) -> tuple[int, str]:
    if ratio <= 0:
        return (0, "Not calculated")
    if ratio < 24:
        return (6, f"{ratio:.1f} (markedly low)")
    elif ratio < 27:
        return (4, f"{ratio:.1f} (low)")
    elif ratio < 32:
        return (1, f"{ratio:.1f} (low-normal)")
    else:
        return (0, f"{ratio:.1f} (normal)")


# Lymphocyte count (cells/µL): cortisol normally suppresses; in HOAC, count is preserved or elevated.
def lymphocyte_points(count: float) -> tuple[int, str]:
    if count <= 0:
        return (0, "Not measured")
    if count >= 5000:
        return (3, f"{count:.0f}/µL (lymphocytosis)")
    elif count >= 1500:
        return (1, f"{count:.0f}/µL (normal)")
    else:
        return (-2, f"{count:.0f}/µL (low: argues against)")


# Eosinophil count (cells/µL)
def eosinophil_points(count: float) -> tuple[int, str]:
    if count <= 0:
        return (0, "Not measured")
    if count >= 1500:
        return (2, f"{count:.0f}/µL (eosinophilia)")
    elif count >= 100:
        return (0, f"{count:.0f}/µL (normal)")
    else:
        return (-1, f"{count:.0f}/µL (eosinopenia)")


# Lack of stress leukogram (no neutrophilia, no monocytosis, with lymphocytes/eos preserved)
NO_STRESS_LEUKOGRAM_POINTS = {"yes": 2, "no": 0, "not_assessed": 0}


# Vague intermittent / chronic GI signs (waxing-waning vomiting, diarrhea, anorexia)
GI_WAXING_WANING_POINTS = {"yes": 3, "no": 0}


# Hypoglycemia
HYPOGLYCEMIA_POINTS = {"yes": 1, "no": 0, "not_recorded": 0}

# Hypercalcemia
HYPERCALCEMIA_POINTS = {"yes": 1, "no": 0, "not_recorded": 0}


# Resting cortisol — the most powerful single test
def cortisol_points(cortisol_ug_dl: float) -> tuple[int, str]:
    if cortisol_ug_dl <= 0:
        return (0, "Not measured")
    if cortisol_ug_dl < 1.0:
        return (5, f"{cortisol_ug_dl:.2f} µg/dL (very low)")
    elif cortisol_ug_dl < 2.0:
        return (3, f"{cortisol_ug_dl:.2f} µg/dL (low)")
    else:
        # > 2 µg/dL effectively rules out HOAC
        return (-8, f"{cortisol_ug_dl:.2f} µg/dL (rules out HOAC)")


# Age band
def age_points(age: float) -> tuple[int, str]:
    if age < 1.0:
        return (0, f"{age:.1f} yr (juvenile, less typical)")
    elif age <= 7.0:
        return (1, f"{age:.1f} yr (typical age range)")
    else:
        return (0, f"{age:.1f} yr (older than typical)")


BREED_POINTS = {
    "standard_poodle": 2,
    "portuguese_water": 2,
    "wheaten_terrier": 2,
    "nova_scotia": 2,  # Nova Scotia Duck Tolling Retriever
    "great_dane": 1,
    "bearded_collie": 1,
    "leonberger": 1,
    "rottweiler": 1,
    "other": 0,
}


# ---------------------------------------------------------------------------
# Probability lookup
# ---------------------------------------------------------------------------


def score_to_likelihood(score: int) -> tuple[int, str, str]:
    if score <= 0:
        return (
            3,
            "Very low",
            "Hypoadrenocorticism is unlikely. Investigate other causes of the presenting signs.",
        )
    elif score <= 3:
        return (
            12,
            "Low",
            "Pretest probability is low but not negligible. Addison's "
            "is the great pretender. Consider a baseline cortisol "
            "(>2 µg/dL effectively rules out HOAC).",
        )
    elif score <= 6:
        return (
            35,
            "Moderate",
            "Reasonable pretest probability. Baseline cortisol is a "
            "sensible first step; if low, proceed to ACTH stimulation.",
        )
    elif score <= 9:
        return (
            65,
            "High",
            "High pretest probability. ACTH stimulation testing is "
            "indicated. If the patient is unstable, treat empirically "
            "while testing.",
        )
    else:
        return (
            88,
            "Very high",
            "Very high pretest probability. This is likely "
            "Addison's. ACTH stimulation testing is confirmatory; "
            "begin empiric treatment if the patient is unstable.",
        )


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class AddisonsInputs:
    age: float = 4.0
    breed: str = "other"
    na_k_ratio: float = 0.0
    lymphocytes_per_ul: float = 0.0
    eosinophils_per_ul: float = 0.0
    no_stress_leukogram: str = "not_assessed"
    gi_waxing_waning: str = "no"
    hypoglycemia: str = "not_recorded"
    hypercalcemia: str = "not_recorded"
    resting_cortisol_ug_dl: float = 0.0


@dataclass
class ScoreComponent:
    label: str
    value_str: str
    points: int


@dataclass
class AddisonsResult:
    inputs: AddisonsInputs
    components: list[ScoreComponent] = field(default_factory=list)
    total_score: int = 0
    likelihood_pct: int = 0
    band_label: str = ""
    recommendation: str = ""
    # Whether the clinician has entered at least one clinical finding.
    # False on initial form load (only signalment defaults present);
    # True once any lab value, symptom, or assessment has been entered.
    # Gates the result panel headline so we don't display a fake "12%"
    # pretest probability before there's clinical data to score.
    computed: bool = False
    sources: tuple[Source, ...] = ()


def _yn(v):
    return {"yes": "Yes", "no": "No", "not_recorded": "Not recorded", "not_assessed": "Not assessed"}.get(
        v, v
    )


def _has_clinical_data(inputs: AddisonsInputs) -> bool:
    """True when the clinician has entered any clinical finding.

    Signalment (age, breed) doesn't count — those are demographics, not
    clinical assessments. The threshold is: any lab value > 0, or any
    assessment radio moved off its "not assessed / not recorded" default.
    GI waxing/waning defaults to "no" so a "yes" indicates positive
    finding; an unchanged "no" doesn't count as touched (we can't
    distinguish unchanged from explicitly-clicked "no" in form data).
    """
    return (
        inputs.na_k_ratio > 0
        or inputs.lymphocytes_per_ul > 0
        or inputs.eosinophils_per_ul > 0
        or inputs.resting_cortisol_ug_dl > 0
        or inputs.no_stress_leukogram != "not_assessed"
        or inputs.gi_waxing_waning == "yes"
        or inputs.hypoglycemia != "not_recorded"
        or inputs.hypercalcemia != "not_recorded"
    )


def _breed_label(v):
    return {
        "standard_poodle": "Standard Poodle",
        "portuguese_water": "Portuguese Water Dog",
        "wheaten_terrier": "Soft-Coated Wheaten Terrier",
        "nova_scotia": "Nova Scotia Duck Tolling Retriever",
        "great_dane": "Great Dane",
        "bearded_collie": "Bearded Collie",
        "leonberger": "Leonberger",
        "rottweiler": "Rottweiler",
        "other": "Other / crossbreed",
    }.get(v, v)


def calculate(inputs: AddisonsInputs) -> AddisonsResult:
    # Safety Rule #8 gate. Don't expose a headline pretest probability
    # before the clinician has entered findings — the form's age and
    # breed defaults alone produce a misleading "12%, Score 1" headline
    # that looks like a clinical conclusion.
    if not _has_clinical_data(inputs):
        return AddisonsResult(
            inputs=inputs,
            components=[],
            total_score=0,
            likelihood_pct=0,
            band_label="",
            recommendation="",
            computed=False,
            sources=ADDISONS_SOURCES,
        )

    age_pts, age_lbl = age_points(inputs.age)
    nak_pts, nak_lbl = na_k_ratio_points(inputs.na_k_ratio)
    lymph_pts, lymph_lbl = lymphocyte_points(inputs.lymphocytes_per_ul)
    eos_pts, eos_lbl = eosinophil_points(inputs.eosinophils_per_ul)
    cort_pts, cort_lbl = cortisol_points(inputs.resting_cortisol_ug_dl)

    components = [
        ScoreComponent("Age", age_lbl, age_pts),
        ScoreComponent("Breed", _breed_label(inputs.breed), BREED_POINTS.get(inputs.breed, 0)),
        ScoreComponent("Na:K ratio", nak_lbl, nak_pts),
        ScoreComponent("Lymphocytes", lymph_lbl, lymph_pts),
        ScoreComponent("Eosinophils", eos_lbl, eos_pts),
        ScoreComponent(
            "Lacks stress leukogram",
            _yn(inputs.no_stress_leukogram),
            NO_STRESS_LEUKOGRAM_POINTS.get(inputs.no_stress_leukogram, 0),
        ),
        ScoreComponent(
            "Waxing/waning GI signs",
            _yn(inputs.gi_waxing_waning),
            GI_WAXING_WANING_POINTS.get(inputs.gi_waxing_waning, 0),
        ),
        ScoreComponent(
            "Hypoglycemia", _yn(inputs.hypoglycemia), HYPOGLYCEMIA_POINTS.get(inputs.hypoglycemia, 0)
        ),
        ScoreComponent(
            "Hypercalcemia", _yn(inputs.hypercalcemia), HYPERCALCEMIA_POINTS.get(inputs.hypercalcemia, 0)
        ),
        ScoreComponent("Resting cortisol", cort_lbl, cort_pts),
    ]
    total = sum(c.points for c in components)
    pct, band, rec = score_to_likelihood(total)
    return AddisonsResult(
        inputs=inputs,
        components=components,
        total_score=total,
        likelihood_pct=pct,
        band_label=band,
        recommendation=rec,
        computed=True,
        sources=ADDISONS_SOURCES,
    )


ADDISONS_SOURCES = (
    Source(
        citation=(
            "Reagan KL, Reagan BA, Gilor C. Predicting the likelihood of "
            "hypoadrenocorticism in dogs using signalment and routine "
            "laboratory results with an ensemble machine learning predictive "
            "model. J Vet Intern Med 2026;40:e70067. (Addison Detect Tool.)"
        )
    ),
    Source(
        citation=(
            "Bennaim M, Centola S, Ramsey IK, Mooney CT. Can we predict "
            "hypoadrenocorticism in dogs with resting hypocortisolemia? A "
            "predictive model based on clinical, haematological, and "
            "biochemical variables. J Vet Intern Med 2024;38:1546–1556."
        )
    ),
    Source(
        citation=(
            "Guzmán Ramos PJ, Bennaim M, Shiel RE, Mooney CT. Diagnosis of "
            "canine spontaneous hypoadrenocorticism. Canine Med Genet "
            "2022;9:6."
        )
    ),
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/addisons-score", response_class=HTMLResponse)
async def addisons_page(request: Request):
    templates = request.app.state.templates
    inputs = AddisonsInputs()
    result = calculate(inputs)
    return templates.TemplateResponse(
        "addisons_score.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


@router.post("/addisons-score/compute", response_class=HTMLResponse)
async def addisons_compute(
    request: Request,
    age: str = Form("4.0"),
    breed: str = Form("other"),
    na_k_ratio: str = Form("0.0"),
    lymphocytes_per_ul: str = Form("0.0"),
    eosinophils_per_ul: str = Form("0.0"),
    no_stress_leukogram: str = Form("not_assessed"),
    gi_waxing_waning: str = Form("no"),
    hypoglycemia: str = Form("not_recorded"),
    hypercalcemia: str = Form("not_recorded"),
    resting_cortisol_ug_dl: str = Form("0.0"),
):
    templates = request.app.state.templates
    inputs = AddisonsInputs(
        age=parse_float_with_default(age, 4.0),
        breed=breed,
        na_k_ratio=parse_float_with_default(na_k_ratio, 0.0),
        lymphocytes_per_ul=parse_float_with_default(lymphocytes_per_ul, 0.0),
        eosinophils_per_ul=parse_float_with_default(eosinophils_per_ul, 0.0),
        no_stress_leukogram=no_stress_leukogram,
        gi_waxing_waning=gi_waxing_waning,
        hypoglycemia=hypoglycemia,
        hypercalcemia=hypercalcemia,
        resting_cortisol_ug_dl=parse_float_with_default(resting_cortisol_ug_dl, 0.0),
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/addisons_score_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


ADDISONS_CATALOG_ENTRY = {
    "slug": "addisons-score",
    "display_name": "Addison's pretest score",
    "short_name": "Addison's score",
    "category": "Endocrine & Metabolic",
    "kind": "diagnostic_score",
    "mechanism_summary": (
        "Pretest probability score for canine hypoadrenocorticism, "
        "adapted from the Reagan 2026 Addison Detect Tool variables. "
        "Helps catch atypical (eunatremic, eukalemic) Addison's that "
        "presents with vague waxing-waning illness."
    ),
}
