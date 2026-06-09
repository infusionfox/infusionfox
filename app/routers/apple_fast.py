"""
APPLE-fast (Acute Patient Physiologic and Laboratory Evaluation, 5-variable)
illness severity score for hospitalized dogs.

Source:
  Hayes G, Mathews K, Doig G, Kruth S, Boston S, Nykamp S, Poljak Z, Dewey C.
  The Acute Patient Physiologic and Laboratory Evaluation (APPLE) Score:
  A Severity of Illness Stratification System for Hospitalized Dogs.
  J Vet Intern Med 2010;24:1034–1047. doi:10.1111/j.1939-1676.2010.0552.x

External validation:
  Le Gal A, Barfield D, Wignall R, Cook S. Outcome prediction in dogs
  admitted through the emergency room: accuracy of staff prediction and
  comparison with APPLEfast. EVECC 2021 Congress / proceedings.

The 5-variable model contains glucose, albumin, mentation score, platelet
count, and lactate. Score ranges 0–50. Higher scores associate with
higher mortality risk in hospitalized ICU dogs.

Key caveats baked into the UI:
  - Glucose >15 mmol/L (>273 mg/dL) scores 0, the referent (zero) group
    in the multivariable model is dominated by stress hyperglycemia and
    treated diabetics, which carried lowest mortality in this cohort.
  - Platelets 151–200 ×10⁹/L scores HIGHER than <151, a multivariable
    artifact Hayes 2010 explicitly flags; reflects mortality variance
    not already captured by the other four variables.
  - Albumin >35 g/L scores 2 (not 0), high albumin tracked with
    increased mortality after adjustment for the other variables.

Variables (other than mentation): use the most abnormal value within the
first 24 h after admission. Mentation: assessed at admission, BEFORE
sedation or analgesia. The score is a population-level risk
stratification tool; individual-patient confidence intervals are wide
(see Hayes 2010 Fig 5). Not appropriate for driving euthanasia decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.calculators.engine import Source
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


# ---------------------------------------------------------------------------
# Per-variable scoring (Hayes 2010, Figs 4 and A2)
# ---------------------------------------------------------------------------


# Glucose: thresholds are in mmol/L (SI); convert mg/dL → mmol/L by /18.
# Central (zero-point) zone: >15.0 mmol/L. This is the stress-hyperglycemia
# referent dominated by treated diabetics in the original cohort, and is
# intentionally preserved despite being clinically counterintuitive.
def glucose_points(glucose_mmol_l: float) -> tuple[int, str]:
    g = glucose_mmol_l
    if g <= 0:
        return (0, "Not entered")
    # Central / referent (gets 0 points)
    if g > 15.0:
        return (0, f"{g:.1f} mmol/L (>15.0, referent)")
    if g < 4.6:
        return (7, f"{g:.1f} mmol/L (<4.6)")
    if g <= 5.6:
        return (8, f"{g:.1f} mmol/L (4.6–5.6)")
    if g <= 9.0:
        return (9, f"{g:.1f} mmol/L (5.7–9.0)")
    # 9.1–15.0
    return (10, f"{g:.1f} mmol/L (9.1–15.0)")


# Albumin: thresholds are in g/L (SI); convert g/dL → g/L by ×10.
# Central (zero-point) zone: 33–35 g/L. >35 scores 2 (multivariable artifact).
def albumin_points(albumin_g_l: float) -> tuple[int, str]:
    a = albumin_g_l
    if a <= 0:
        return (0, "Not entered")
    if a < 26:
        return (8, f"{a:.0f} g/L (<26)")
    if a <= 30:
        return (7, f"{a:.0f} g/L (26–30)")
    if a <= 32:
        return (6, f"{a:.0f} g/L (31–32)")
    if a <= 35:
        return (0, f"{a:.0f} g/L (33–35, referent)")
    return (2, f"{a:.0f} g/L (>35)")


# Lactate: thresholds in mmol/L (SI); convert mg/dL → mmol/L by /9.
# Central (zero-point) zone: <2 mmol/L (normal).
def lactate_points(lactate_mmol_l: float) -> tuple[int, str]:
    L = lactate_mmol_l
    if L <= 0:
        return (0, "Not entered")
    if L < 2.0:
        return (0, f"{L:.1f} mmol/L (<2, referent)")
    if L <= 8.0:
        return (4, f"{L:.1f} mmol/L (2–8)")
    if L <= 10.0:
        return (8, f"{L:.1f} mmol/L (8–10)")
    return (12, f"{L:.1f} mmol/L (>10)")


# Platelets: ×10⁹/L (equivalent to K/µL). No unit conversion.
# Central (zero-point) zone: 261–420 ×10⁹/L. Note: 151–200 scores 6, HIGHER
# than <151 which scores 5, multivariable artifact preserved per paper.
def platelet_points(platelets_x10_9: float) -> tuple[int, str]:
    p = platelets_x10_9
    if p <= 0:
        return (0, "Not entered")
    if p < 151:
        return (5, f"{p:.0f} ×10⁹/L (<151)")
    if p <= 200:
        return (6, f"{p:.0f} ×10⁹/L (151–200)")
    if p <= 260:
        return (3, f"{p:.0f} ×10⁹/L (201–260)")
    if p <= 420:
        return (0, f"{p:.0f} ×10⁹/L (261–420, referent)")
    return (1, f"{p:.0f} ×10⁹/L (>420)")


MENTATION_LABELS = {
    0: "Normal",
    1: "Stands unassisted, responsive but dull",
    2: "Stands only when assisted, responsive but dull",
    3: "Unable to stand, responsive",
    4: "Unable to stand, unresponsive",
}

MENTATION_POINTS = {
    0: 0,
    1: 4,
    2: 6,
    3: 7,
    4: 14,
}


def mentation_points(mentation: int) -> tuple[int, str]:
    m = max(0, min(4, mentation))
    return (MENTATION_POINTS[m], f"{m}: {MENTATION_LABELS[m]}")


# ---------------------------------------------------------------------------
# Mortality probability + risk banding (Hayes 2010, page 7)
# ---------------------------------------------------------------------------


def mortality_probability(score: int) -> float:
    """Logistic mortality probability per Hayes 2010 equation (1).

    P = exp(R) / (1 + exp(R)),  R = 0.249 × APPLEfast − 7.020
    """
    R = 0.249 * score - 7.020
    return exp(R) / (1.0 + exp(R))


def risk_band(score: int) -> tuple[str, str]:
    """Return (band_label, recommendation_text).

    Cutoffs from Hayes 2010 Table 5:
      - >25/50: sensitivity 67%, specificity 85% for mortality
      - >22/50: sensitivity 74%, specificity 80%
    The >25 cutoff was externally validated by Le Gal 2021.
    """
    if score <= 15:
        return (
            "Low",
            "Predicted mortality is low for this score range. Continue "
            "supportive care; the score does not on its own warrant "
            "escalation. Recalculate using the most abnormal values in "
            "the first 24 h if status changes.",
        )
    if score <= 22:
        return (
            "Moderate",
            "Predicted mortality climbs steeply through this range. "
            "Reassess the worst trajectory variable (lactate, mentation, "
            "albumin), confirm volume status and gas exchange, and "
            "consider ICU-level monitoring if not already in place.",
        )
    if score <= 25:
        return (
            "Moderate–high",
            "Approaching the validated >25 cutoff (sensitivity 67%, "
            "specificity 85% for hospital mortality). Aggressive "
            "stabilization and close monitoring are indicated; "
            "communicate prognostic uncertainty plainly to owners.",
        )
    return (
        "High",
        "Above the >25 cutoff externally validated by Le Gal 2021 "
        "(specificity 85% for mortality, sensitivity 67%). Predicted "
        "mortality is substantial. Use the score to inform but NEVER "
        "dictate euthanasia decisions. Individual-patient confidence "
        "intervals are wide. Hayes 2010 explicitly cautions against "
        "score-driven euthanasia.",
    )


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class AppleFastInputs:
    # "si": glucose mmol/L, albumin g/L, lactate mmol/L
    # "us": glucose mg/dL, albumin g/dL, lactate mg/dL
    units: str = "si"
    # 0.0 / -1 are sentinels meaning "user has not entered a value yet".
    # The route layer translates empty form fields to these; the scoring
    # functions then return ("Not entered", 0 points) instead of computing
    # a misleading score from a substituted default. The page render path
    # never feeds a defaulted AppleFastInputs into calculate(); the GET
    # handler passes result=None so the placeholder renders in the
    # result panel slot.
    glucose: float = 0.0
    albumin: float = 0.0
    lactate: float = 0.0
    platelets: float = 0.0
    mentation: int = -1


@dataclass
class ScoreComponent:
    label: str
    value_str: str
    points: int


@dataclass
class AppleFastResult:
    inputs: AppleFastInputs
    components: list[ScoreComponent] = field(default_factory=list)
    total_score: int = 0
    mortality_pct: float = 0.0
    band_label: str = ""
    recommendation: str = ""
    sources: tuple[Source, ...] = ()


# US → SI conversions for internal scoring. The published rubric uses the
# same integer points for the SI and US bands (just different numeric
# expressions of the same physiologic threshold), so we normalize to SI
# and dispatch to a single set of band tables.
def _glucose_to_si(value: float, units: str) -> float:
    if units == "us":
        return value / 18.0
    return value


def _albumin_to_si(value: float, units: str) -> float:
    # g/dL → g/L
    if units == "us":
        return value * 10.0
    return value


def _lactate_to_si(value: float, units: str) -> float:
    if units == "us":
        return value / 9.0
    return value


def calculate(inputs: AppleFastInputs) -> AppleFastResult:
    glu_si = _glucose_to_si(inputs.glucose, inputs.units)
    alb_si = _albumin_to_si(inputs.albumin, inputs.units)
    lac_si = _lactate_to_si(inputs.lactate, inputs.units)

    glu_pts, glu_lbl = glucose_points(glu_si)
    alb_pts, alb_lbl = albumin_points(alb_si)
    lac_pts, lac_lbl = lactate_points(lac_si)
    plt_pts, plt_lbl = platelet_points(inputs.platelets)
    men_pts, men_lbl = mentation_points(inputs.mentation)

    # For US-unit users, the label shows the SI band the value fell into
    # (since the bands are defined in SI in the original paper). Append
    # the US-unit raw value for clarity.
    if inputs.units == "us":
        glu_lbl = f"{inputs.glucose:.0f} mg/dL → {glu_lbl}"
        alb_lbl = f"{inputs.albumin:.1f} g/dL → {alb_lbl}"
        lac_lbl = f"{inputs.lactate:.1f} mg/dL → {lac_lbl}"

    components = [
        ScoreComponent("Glucose", glu_lbl, glu_pts),
        ScoreComponent("Albumin", alb_lbl, alb_pts),
        ScoreComponent("Lactate", lac_lbl, lac_pts),
        ScoreComponent("Platelets", plt_lbl, plt_pts),
        ScoreComponent("Mentation", men_lbl, men_pts),
    ]
    total = sum(c.points for c in components)
    p = mortality_probability(total) * 100.0
    band, rec = risk_band(total)

    return AppleFastResult(
        inputs=inputs,
        components=components,
        total_score=total,
        mortality_pct=p,
        band_label=band,
        recommendation=rec,
        sources=APPLE_FAST_SOURCES,
    )


APPLE_FAST_SOURCES = (
    Source(
        citation=(
            "Hayes G, Mathews K, Doig G, Kruth S, Boston S, Nykamp S, "
            "Poljak Z, Dewey C. The Acute Patient Physiologic and "
            "Laboratory Evaluation (APPLE) Score: A Severity of Illness "
            "Stratification System for Hospitalized Dogs. J Vet Intern "
            "Med 2010;24:1034–1047."
        )
    ),
    Source(
        citation=(
            "Le Gal A, Barfield D, Wignall R, Cook S. Outcome prediction "
            "in dogs admitted through the emergency room: accuracy of "
            "staff prediction and comparison with APPLEfast scoring. "
            "EVECC 2021 Congress proceedings. (Validated cutoff >25: "
            "specificity 85%, sensitivity 67% for mortality.)"
        )
    ),
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/apple-fast", response_class=HTMLResponse)
async def apple_fast_page(request: Request):
    """Initial GET, empty form, placeholder where the result would go.

    Per the calculator default-output safety rule (CLAUDE.md #8 /
    architecture.md), the result panel does NOT pre-render with a score
    from default-valued inputs. A pre-populated score is a patient-safety
    hazard: a clinician glancing at the page could misread it as the
    patient's actual APPLE-fast.
    """
    templates = request.app.state.templates
    inputs = AppleFastInputs()
    return templates.TemplateResponse(
        "apple_fast.html",
        {
            "request": request,
            "inputs": inputs,
            "result": None,  # placeholder renders in result panel slot
        },
    )


@router.post("/apple-fast/compute", response_class=HTMLResponse)
async def apple_fast_compute(
    request: Request,
    units: str = Form("si"),
    glucose: str = Form(""),
    albumin: str = Form(""),
    lactate: str = Form(""),
    platelets: str = Form(""),
    mentation: str = Form(""),
):
    """Compute the score only when all five required variables are
    present and parseable. Otherwise return the placeholder partial so
    the user sees an unambiguous prompt rather than a score computed
    from silently-substituted defaults.
    """
    templates = request.app.state.templates

    # Validate that every required field is present + numeric. The
    # mentation radio group is a separate check because "0" (alert) is
    # a valid score; an empty value means the user has not selected
    # anything yet.
    parsed = {
        "glucose": parse_positive_float(glucose),
        "albumin": parse_positive_float(albumin),
        "lactate": parse_positive_float(lactate),
        "platelets": parse_positive_float(platelets),
    }
    mentation_valid = (mentation or "").strip() in ("0", "1", "2", "3", "4")
    missing_numeric = [k for k, v in parsed.items() if v is None]

    if missing_numeric or not mentation_valid:
        # Build a precise message naming what's still missing.
        missing_labels: list[str] = []
        if "glucose" in missing_numeric:
            missing_labels.append("glucose")
        if "albumin" in missing_numeric:
            missing_labels.append("albumin")
        if "lactate" in missing_numeric:
            missing_labels.append("lactate")
        if "platelets" in missing_numeric:
            missing_labels.append("platelet count")
        if not mentation_valid:
            missing_labels.append("mentation score")
        if len(missing_labels) == 1:
            msg = f"Enter {missing_labels[0]} to compute the APPLE-fast score."
        elif len(missing_labels) == 2:
            msg = f"Enter {missing_labels[0]} and {missing_labels[1]} to compute the APPLE-fast score."
        else:
            msg = (
                "Enter " + ", ".join(missing_labels[:-1])
                + f", and {missing_labels[-1]} to compute the APPLE-fast score."
            )
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": msg,
            },
        )

    inputs = AppleFastInputs(
        units=units if units in ("si", "us") else "si",
        glucose=parsed["glucose"],
        albumin=parsed["albumin"],
        lactate=parsed["lactate"],
        platelets=parsed["platelets"],
        mentation=int(mentation),
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/apple_fast_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


APPLE_FAST_CATALOG_ENTRY = {
    "slug": "apple-fast",
    "display_name": "APPLE-fast illness severity",
    "short_name": "APPLE-fast",
    "category": "Emergency",
    "kind": "diagnostic_score",
    "mechanism_summary": (
        "5-variable illness severity score for hospitalized dogs "
        "(Hayes 2010). Glucose, albumin, lactate, platelet count, and "
        "mentation map to a 0–50 score, which maps to predicted "
        "hospital mortality via logistic regression. Cutoff >25 "
        "carries 85% specificity / 67% sensitivity for mortality. "
        "Score is a population-level tool; individual confidence "
        "intervals are wide. Not for driving euthanasia decisions."
    ),
}
