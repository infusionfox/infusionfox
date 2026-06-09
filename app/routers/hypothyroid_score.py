"""
Hypothyroidism pretest probability score for dogs.

A structured pretest score adapted from the variables identified in the
Corsini et al. (2023) machine-learning prediction model. The original
study used naive Bayes / logistic regression / random forest models on
clinical signs and clinicopathological variables; this calculator
implements a simplified additive-points version of the clinical-only
model (their Models 1 and 3, AUROC 0.85–0.88) for infusionfox use.

The intent is to triage which dogs warrant thyroid testing — not to
substitute for it.

Sources:
  - Corsini A, Lunetta F, Alboni F, Drudi I, Faroni E, Fracassi F.
    Development and internal validation of diagnostic prediction models
    using machine-learning algorithms in dogs with hypothyroidism.
    Front Vet Sci 2023;10:1292988.
  - Diaz-Espineira MM et al; subsequent JVIM 2024 paper on hypothyroidism
    over-diagnosis in primary care.
  - 2023 AAHA Selected Endocrinopathies Guidelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source

router = APIRouter()


# ---------------------------------------------------------------------------
# Scoring weights (clinical adaptation of Corsini 2023 predictor variables)
# ---------------------------------------------------------------------------
# Predictors from Corsini Model 3 (qualitative, no thyroid hormone results):
# dermatologic signs, alopecia, lethargy, hematocrit, cholesterol, creatinine.
# Weights below are an additive-points adaptation calibrated so that strong
# clinical syndromes give moderate-to-high pretest probability.

DERMATOLOGIC_POINTS = {"yes": 3, "no": 0}  # bilateral symmetric flank/trunk dermatosis, recurrent pyoderma
ALOPECIA_POINTS = {"yes": 3, "no": 0}  # bilateral symmetric truncal alopecia
LETHARGY_POINTS = {"yes": 2, "no": 0}
WEIGHT_GAIN_POINTS = {"yes": 2, "no": 0}  # weight gain without polyphagia
COLD_INTOLERANCE_POINTS = {"yes": 1, "no": 0}

# Lab markers (each contributes if present)
HYPERCHOLESTEROLEMIA_POINTS = {"yes": 3, "no": 0, "not_recorded": 0}
NORMAL_CHOLESTEROL_POINTS = {"yes": -2, "no": 0}  # negative weight when cholesterol is normal
ANEMIA_POINTS = {"yes": 1, "no": 0, "not_recorded": 0}  # mild non-regenerative anemia


# Breed risk (selected over-represented breeds; based on multiple epidemiological reviews)
BREED_POINTS = {
    "golden_retriever": 2,
    "doberman": 2,
    "irish_setter": 2,
    "boxer": 1,
    "cocker_spaniel": 1,
    "dachshund": 1,
    "other": 0,
}

AGE_POINTS = {
    "under_2": -3,  # very rare in young dogs
    "2_to_6": 0,
    "over_6": 1,
}


# Recent illness or steroid exposure (sick euthyroid / suppression)
# Lowers pretest probability because false-positive thyroid testing is more
# likely in this context — better to defer testing.
NTI_OR_STEROIDS_POINTS = {"yes": -3, "no": 0}


# ---------------------------------------------------------------------------
# Probability lookup
# ---------------------------------------------------------------------------
# Maps the additive score to an approximate pretest likelihood.
# Calibrated so that:
#  - score ≤ 0  → low pretest probability (testing not currently indicated)
#  - score 1–4  → moderate pretest probability (testing may help)
#  - score ≥ 5  → high pretest probability (testing should be diagnostic)


def score_to_likelihood(score: int) -> tuple[int, str, str]:
    """Return (percent, band_label, recommendation)."""
    if score <= 0:
        return (
            5,
            "Very low",
            "Hypothyroidism is unlikely. Investigate alternative causes "
            "(obesity, atypical Cushing's, chronic disease). Thyroid "
            "testing is unlikely to be informative now.",
        )
    elif score <= 2:
        return (
            15,
            "Low",
            "Pretest probability is low. Address other differentials "
            "first; if signs persist, consider thyroid testing 4–6 weeks "
            "after stabilization.",
        )
    elif score <= 4:
        return (
            35,
            "Moderate",
            "Reasonable pretest probability. Thyroid testing is "
            "appropriate provided the patient is not currently sick "
            "with a non-thyroidal illness or on glucocorticoids.",
        )
    elif score <= 6:
        return (
            60,
            "High",
            "High pretest probability. Thyroid testing (TT4 + free T4 + "
            "TSH) is indicated. A complete profile is more informative "
            "than TT4 alone.",
        )
    else:
        return (
            80,
            "Very high",
            "Very high pretest probability. Thyroid testing should be "
            "diagnostic. If TT4 alone is non-diagnostic, proceed to a "
            "full thyroid panel.",
        )


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class HypothyroidInputs:
    age_band: str = "over_6"
    breed: str = "other"
    dermatologic: str = "no"
    alopecia: str = "no"
    lethargy: str = "no"
    weight_gain: str = "no"
    cold_intolerance: str = "no"
    hypercholesterolemia: str = "not_recorded"
    normal_cholesterol: str = "no"
    anemia: str = "not_recorded"
    nti_or_steroids: str = "no"


@dataclass
class ScoreComponent:
    label: str
    value_str: str
    points: int


@dataclass
class HypothyroidResult:
    inputs: HypothyroidInputs
    components: list[ScoreComponent] = field(default_factory=list)
    total_score: int = 0
    likelihood_pct: int = 0
    band_label: str = ""
    recommendation: str = ""
    # Safety Rule #8 gate: True once any clinical sign or lab is
    # entered; False on initial form load so the result panel shows
    # a placeholder instead of a misleading default headline.
    computed: bool = False
    sources: tuple[Source, ...] = ()


def _age_label(v):
    return {"under_2": "< 2 years", "2_to_6": "2–6 years", "over_6": "> 6 years"}.get(v, v)


def _has_clinical_data(inputs: HypothyroidInputs) -> bool:
    """True when at least one clinical sign or lab value is entered.

    Age band and breed are signalment, not clinical findings.
    """
    return (
        inputs.dermatologic == "yes"
        or inputs.alopecia == "yes"
        or inputs.lethargy == "yes"
        or inputs.weight_gain == "yes"
        or inputs.cold_intolerance == "yes"
        or inputs.hypercholesterolemia != "not_recorded"
        or inputs.normal_cholesterol == "yes"
        or inputs.anemia != "not_recorded"
        or inputs.nti_or_steroids == "yes"
    )


def _breed_label(v):
    return {
        "golden_retriever": "Golden Retriever",
        "doberman": "Doberman Pinscher",
        "irish_setter": "Irish Setter",
        "boxer": "Boxer",
        "cocker_spaniel": "Cocker Spaniel",
        "dachshund": "Dachshund",
        "other": "Other breed",
    }.get(v, v)


def _yn(v):
    return {"yes": "Yes", "no": "No", "not_recorded": "Not recorded"}.get(v, v)


def calculate(inputs: HypothyroidInputs) -> HypothyroidResult:
    # Safety Rule #8: don't display a probability headline before the
    # clinician has entered findings.
    if not _has_clinical_data(inputs):
        return HypothyroidResult(
            inputs=inputs,
            components=[],
            total_score=0,
            likelihood_pct=0,
            band_label="",
            recommendation="",
            computed=False,
            sources=HYPOTHYROID_SOURCES,
        )

    components = [
        ScoreComponent("Age", _age_label(inputs.age_band), AGE_POINTS.get(inputs.age_band, 0)),
        ScoreComponent("Breed", _breed_label(inputs.breed), BREED_POINTS.get(inputs.breed, 0)),
        ScoreComponent(
            "Bilateral truncal dermatosis or recurrent pyoderma",
            _yn(inputs.dermatologic),
            DERMATOLOGIC_POINTS.get(inputs.dermatologic, 0),
        ),
        ScoreComponent(
            "Bilateral symmetric alopecia", _yn(inputs.alopecia), ALOPECIA_POINTS.get(inputs.alopecia, 0)
        ),
        ScoreComponent(
            "Lethargy / exercise intolerance", _yn(inputs.lethargy), LETHARGY_POINTS.get(inputs.lethargy, 0)
        ),
        ScoreComponent(
            "Weight gain without polyphagia",
            _yn(inputs.weight_gain),
            WEIGHT_GAIN_POINTS.get(inputs.weight_gain, 0),
        ),
        ScoreComponent(
            "Cold intolerance / heat-seeking",
            _yn(inputs.cold_intolerance),
            COLD_INTOLERANCE_POINTS.get(inputs.cold_intolerance, 0),
        ),
        ScoreComponent(
            "Hypercholesterolemia",
            _yn(inputs.hypercholesterolemia),
            HYPERCHOLESTEROLEMIA_POINTS.get(inputs.hypercholesterolemia, 0),
        ),
        ScoreComponent(
            "Normal cholesterol",
            _yn(inputs.normal_cholesterol),
            NORMAL_CHOLESTEROL_POINTS.get(inputs.normal_cholesterol, 0),
        ),
        ScoreComponent(
            "Mild non-regenerative anemia", _yn(inputs.anemia), ANEMIA_POINTS.get(inputs.anemia, 0)
        ),
        ScoreComponent(
            "Concurrent illness or recent steroids",
            _yn(inputs.nti_or_steroids),
            NTI_OR_STEROIDS_POINTS.get(inputs.nti_or_steroids, 0),
        ),
    ]
    total = sum(c.points for c in components)
    pct, band, rec = score_to_likelihood(total)
    return HypothyroidResult(
        inputs=inputs,
        components=components,
        total_score=total,
        likelihood_pct=pct,
        band_label=band,
        recommendation=rec,
        computed=True,
        sources=HYPOTHYROID_SOURCES,
    )


HYPOTHYROID_SOURCES = (
    Source(
        citation=(
            "Corsini A, Lunetta F, Alboni F, Drudi I, Faroni E, Fracassi F. "
            "Development and internal validation of diagnostic prediction "
            "models using machine-learning algorithms in dogs with "
            "hypothyroidism. Front Vet Sci 2023;10:1292988."
        ),
        url="https://www.frontiersin.org/articles/10.3389/fvets.2023.1292988",
    ),
    Source(
        citation=(
            "Bell ET, Mooney CT, Shiel RE. Assessment of the likelihood of "
            "hypothyroidism in dogs diagnosed with and treated for "
            "hypothyroidism at primary care practices: 102 cases (2016–2021). "
            "J Vet Intern Med 2024;38:881–891."
        )
    ),
    Source(
        citation=(
            "Fleeman LM, Diaz-Espineira MM. 2023 AAHA Selected Endocrinopathies "
            "of Dogs and Cats Guidelines: Hypothyroidism. American Animal "
            "Hospital Association, 2023."
        )
    ),
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/hypothyroid-score", response_class=HTMLResponse)
async def hypothyroid_page(request: Request):
    templates = request.app.state.templates
    inputs = HypothyroidInputs()
    result = calculate(inputs)
    return templates.TemplateResponse(
        "hypothyroid_score.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


@router.post("/hypothyroid-score/compute", response_class=HTMLResponse)
async def hypothyroid_compute(
    request: Request,
    age_band: str = Form("over_6"),
    breed: str = Form("other"),
    dermatologic: str = Form("no"),
    alopecia: str = Form("no"),
    lethargy: str = Form("no"),
    weight_gain: str = Form("no"),
    cold_intolerance: str = Form("no"),
    hypercholesterolemia: str = Form("not_recorded"),
    normal_cholesterol: str = Form("no"),
    anemia: str = Form("not_recorded"),
    nti_or_steroids: str = Form("no"),
):
    templates = request.app.state.templates
    inputs = HypothyroidInputs(
        age_band=age_band,
        breed=breed,
        dermatologic=dermatologic,
        alopecia=alopecia,
        lethargy=lethargy,
        weight_gain=weight_gain,
        cold_intolerance=cold_intolerance,
        hypercholesterolemia=hypercholesterolemia,
        normal_cholesterol=normal_cholesterol,
        anemia=anemia,
        nti_or_steroids=nti_or_steroids,
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/hypothyroid_score_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


HYPOTHYROID_CATALOG_ENTRY = {
    "slug": "hypothyroid-score",
    "display_name": "Hypothyroidism pretest score",
    "short_name": "Hypothyroid score",
    "category": "Endocrine & Metabolic",
    "kind": "diagnostic_score",
    "mechanism_summary": (
        "Pretest probability score for canine hypothyroidism, adapted "
        "from the Corsini 2023 predictor variables. Triages which dogs "
        "warrant thyroid testing, addressing the well-documented "
        "over-diagnosis in primary care."
    ),
}
