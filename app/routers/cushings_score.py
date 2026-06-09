"""
Cushing's syndrome prediction tool for dogs.

Implements the Schofield et al. (2020) scoring tool directly from Table 5
and Table 6 of the paper. Scores range from -13 to +10, mapping to 0–96%
predicted likelihood.

Source: Schofield I, Brodbelt DC, Niessen SJM, et al.
Development and internal validation of a prediction tool to aid the
diagnosis of Cushing's syndrome in dogs attending primary-care practice.
J Vet Intern Med. 2020;34:2306–2318. https://doi.org/10.1111/jvim.15851
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source
from app.routers._form_parsing import parse_float_with_default

router = APIRouter()

# ---------------------------------------------------------------------------
# Scoring tables, directly from Table 5 of Schofield et al. 2020
# ---------------------------------------------------------------------------

SEX_POINTS: dict[str, int] = {
    "female_entire": 0,
    "female_neutered": -1,
    "male_entire": -1,
    "male_neutered": -1,
}


# Age ≥7 = +1, <7 = 0
def age_points(age: float) -> int:
    return 1 if age >= 7 else 0


BREED_POINTS: dict[str, int] = {
    "bichon_frise": 2,
    "border_terrier": 1,
    "labrador": -3,
    "schnauzer": -2,
    "whwt": -3,
    "other": 0,
}

POLYDIPSIA_POINTS: dict[str, int] = {"yes": 2, "no": 0}
VOMITING_POINTS: dict[str, int] = {"yes": -2, "no": 0}
POTBELLY_POINTS: dict[str, int] = {"yes": 3, "no": 0}
ALOPECIA_POINTS: dict[str, int] = {"yes": 2, "no": 0}
PRURITUS_POINTS: dict[str, int] = {"yes": -2, "no": 0}

USG_POINTS: dict[str, int] = {
    "dilute": 0,
    "not_dilute": -2,
    "not_recorded": -1,
}

ALKP_POINTS: dict[str, int] = {
    "elevated": 0,
    "not_elevated": -3,
    "not_recorded": 0,
}

# ---------------------------------------------------------------------------
# Lookup table. Table 6 of Schofield et al. 2020
# ---------------------------------------------------------------------------

SCORE_TO_LIKELIHOOD: dict[int, float] = {
    -13: 0.00,
    -12: 0.01,
    -11: 0.01,
    -10: 0.01,
    -9: 0.02,
    -8: 0.03,
    -7: 0.04,
    -6: 0.05,
    -5: 0.08,
    -4: 0.11,
    -3: 0.15,
    -2: 0.20,
    -1: 0.27,
    0: 0.35,
    1: 0.44,
    2: 0.53,
    3: 0.63,
    4: 0.71,
    5: 0.78,
    6: 0.84,
    7: 0.88,
    8: 0.92,
    9: 0.94,
    10: 0.96,
}


@dataclass
class CushingsInput:
    sex: str = "female_entire"
    age: float = 10.0
    breed: str = "other"
    polydipsia: str = "no"
    vomiting: str = "no"
    potbelly: str = "no"
    alopecia: str = "no"
    pruritus: str = "no"
    usg: str = "not_recorded"
    alkp: str = "not_recorded"


@dataclass
class ScoreComponent:
    label: str
    category: str
    points: int


@dataclass
class CushingsResult:
    inputs: CushingsInput
    components: list[ScoreComponent] = field(default_factory=list)
    total_score: int = 0
    clamped_score: int = 0  # clamped to -13..10 for lookup
    predicted_likelihood: float = 0.0
    likelihood_pct: int = 0
    # Safety Rule #8 gate: only True once the clinician has entered at
    # least one clinical sign or lab value. False on initial form load
    # so the result panel shows a placeholder instead of a misleading
    # "0 points · 12% likelihood" headline from signalment defaults.
    computed: bool = False
    sources: tuple[Source, ...] = ()


def _has_clinical_data(inputs: CushingsInput) -> bool:
    """True when at least one clinical sign or lab value is entered.

    Signalment (sex, age, breed) doesn't count — those alone are
    demographics, not a clinical assessment.
    """
    return (
        inputs.polydipsia == "yes"
        or inputs.vomiting == "yes"
        or inputs.potbelly == "yes"
        or inputs.alopecia == "yes"
        or inputs.pruritus == "yes"
        or inputs.usg != "not_recorded"
        or inputs.alkp != "not_recorded"
    )


def calculate(inputs: CushingsInput) -> CushingsResult:
    # Safety Rule #8 gate. Don't display a probability headline before
    # the clinician has entered findings.
    if not _has_clinical_data(inputs):
        return CushingsResult(
            inputs=inputs,
            components=[],
            total_score=0,
            clamped_score=0,
            predicted_likelihood=0.0,
            likelihood_pct=0,
            computed=False,
            sources=CUSHINGS_SCORE_SOURCES,
        )

    components = [
        ScoreComponent("Sex / neuter status", _sex_label(inputs.sex), SEX_POINTS.get(inputs.sex, 0)),
        ScoreComponent("Age", f"{inputs.age:.0f} yr", age_points(inputs.age)),
        ScoreComponent("Breed", _breed_label(inputs.breed), BREED_POINTS.get(inputs.breed, 0)),
        ScoreComponent(
            "Polydipsia", inputs.polydipsia.capitalize(), POLYDIPSIA_POINTS.get(inputs.polydipsia, 0)
        ),
        ScoreComponent("Vomiting", inputs.vomiting.capitalize(), VOMITING_POINTS.get(inputs.vomiting, 0)),
        ScoreComponent(
            "Potbelly / hepatomegaly", inputs.potbelly.capitalize(), POTBELLY_POINTS.get(inputs.potbelly, 0)
        ),
        ScoreComponent("Alopecia", inputs.alopecia.capitalize(), ALOPECIA_POINTS.get(inputs.alopecia, 0)),
        ScoreComponent("Pruritus", inputs.pruritus.capitalize(), PRURITUS_POINTS.get(inputs.pruritus, 0)),
        ScoreComponent("Urine specific gravity", _usg_label(inputs.usg), USG_POINTS.get(inputs.usg, -1)),
        ScoreComponent("Serum ALKP", _alkp_label(inputs.alkp), ALKP_POINTS.get(inputs.alkp, 0)),
    ]
    total = sum(c.points for c in components)
    clamped = max(-13, min(10, total))
    likelihood = SCORE_TO_LIKELIHOOD.get(clamped, 0.0)
    return CushingsResult(
        inputs=inputs,
        components=components,
        total_score=total,
        clamped_score=clamped,
        predicted_likelihood=likelihood,
        likelihood_pct=round(likelihood * 100),
        computed=True,
        sources=CUSHINGS_SCORE_SOURCES,
    )


def _sex_label(v: str) -> str:
    return {
        "female_entire": "Female intact",
        "female_neutered": "Female neutered",
        "male_entire": "Male intact",
        "male_neutered": "Male neutered",
    }.get(v, v)


def _breed_label(v: str) -> str:
    return {
        "bichon_frise": "Bichon Frisé",
        "border_terrier": "Border Terrier",
        "labrador": "Labrador Retriever",
        "schnauzer": "Schnauzer",
        "whwt": "West Highland White Terrier",
        "other": "Other breed / crossbreed",
    }.get(v, v)


def _usg_label(v: str) -> str:
    return {
        "dilute": "Dilute (≤ 1.020)",
        "not_dilute": "Not dilute (> 1.020)",
        "not_recorded": "Not recorded",
    }.get(v, v)


def _alkp_label(v: str) -> str:
    return {"elevated": "Elevated", "not_elevated": "Not elevated", "not_recorded": "Not recorded"}.get(v, v)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

_DEFAULT = CushingsInput()


@router.get("/cushings-score", response_class=HTMLResponse)
async def cushings_page(request: Request):
    templates = request.app.state.templates
    result = calculate(_DEFAULT)
    return templates.TemplateResponse(
        "cushings_score.html",
        {
            "request": request,
            "inputs": _DEFAULT,
            "result": result,
        },
    )


@router.post("/cushings-score/compute", response_class=HTMLResponse)
async def cushings_compute(
    request: Request,
    sex: str = Form("female_entire"),
    age: str = Form("10.0"),
    breed: str = Form("other"),
    polydipsia: str = Form("no"),
    vomiting: str = Form("no"),
    potbelly: str = Form("no"),
    alopecia: str = Form("no"),
    pruritus: str = Form("no"),
    usg: str = Form("not_recorded"),
    alkp: str = Form("not_recorded"),
):
    templates = request.app.state.templates
    inputs = CushingsInput(
        sex=sex,
        age=parse_float_with_default(age, 10.0),
        breed=breed,
        polydipsia=polydipsia,
        vomiting=vomiting,
        potbelly=potbelly,
        alopecia=alopecia,
        pruritus=pruritus,
        usg=usg,
        alkp=alkp,
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/cushings_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


CUSHINGS_SCORE_SOURCES = (
    Source(
        citation=(
            "Behrend EN, Kooistra HS, Nelson R, Reusch CE, Scott-Moncrieff JC. "
            "Diagnosis of spontaneous canine hyperadrenocorticism: 2012 ACVIM "
            "Consensus Statement (small animal). J Vet Intern Med "
            "2013;27:1292–1304."
        )
    ),
    Source(
        citation=(
            "Bennaim M, Shiel RE, Mooney CT. Diagnosis of spontaneous "
            "hyperadrenocorticism in dogs. Part 1: Pathophysiology, aetiology, "
            "clinical and clinicopathological features. Vet J 2019;252:105342. "
            "(Pretest probability framework.)"
        )
    ),
)
