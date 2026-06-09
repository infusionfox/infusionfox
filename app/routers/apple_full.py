"""
APPLE-full (Acute Patient Physiologic and Laboratory Evaluation, 10-variable)
illness severity score for hospitalized dogs.

Source:
  Hayes G, Mathews K, Doig G, Kruth S, Boston S, Nykamp S, Poljak Z, Dewey C.
  The Acute Patient Physiologic and Laboratory Evaluation (APPLE) Score:
  A Severity of Illness Stratification System for Hospitalized Dogs.
  J Vet Intern Med 2010;24:1034–1047. doi:10.1111/j.1939-1676.2010.0552.x

The 10-variable model adds creatinine, WBC, SpO2, total bilirubin,
respiratory rate, age, and fluid score to the variables shared with the
5-variable APPLE-fast (albumin, lactate, mentation). Where variables are
shared, the point allocations differ from APPLE-fast because the
multivariable regression is re-fit on the 10-variable set — same
patient, same value, different integer score.

Score ranges 0–80. Per Hayes Table 5:
  - >40/80 cutoff: specificity 98.3%, sensitivity 40.9% for mortality
  - >30/80 cutoff: specificity 89.4%, sensitivity 81.2% for mortality
  - AUROC 0.93 (construction) / 0.91 (validation), versus 0.87/0.84
    for APPLE-fast.

Multivariable artifacts preserved verbatim from Hayes 2010 (the paper
explicitly discusses these on page 11 as "not clinically intuitive"
but reflecting "the mortality risk findings of the dataset"):

  - Creatinine 0–0.62 mg/dL (0–55 umol/L) is the REFERENT (0 pts), not
    the normal range 0.63–1.35 mg/dL (which scores 1). The lowest-risk
    category for each variable does not necessarily correspond to the
    physiologically normal range in a multivariable context.
  - WBC <5.1 ×10⁹/L scores 9 — the highest score for this variable.
    Leukopenia in an ICU dog tracks with severe sepsis with consumption,
    immune-mediated processes, parvovirus, etc.
  - Albumin 31–32 g/L scores 9 (higher than <26 g/L which scores 6).
    Page 11 of the paper calls this out specifically.
  - Total bilirubin scoring is non-monotonic: 0.24–0.46 mg/dL scores 6,
    0.47–0.93 scores 4, >0.93 scores 3. Mild bilirubinemia carries the
    most independent risk in the multivariable model; severe
    bilirubinemia's risk is largely captured by correlated variables
    (creatinine, lactate, albumin).
  - Respiratory rate 49–60 bpm scores 6, higher than >60 bpm which
    scores 5.

Variables (other than mentation): use the most abnormal value within
the first 24 h after admission. Mentation: assessed at admission,
BEFORE sedation or analgesia. Per the paper footnote: if history and
physical examination do not prompt assessment of SpO2 or fluid score,
assign zero — but in this calculator the clinician must explicitly
enter a value (the safety rule disallows defaulted output).

The score is a population-level risk stratification tool. Individual
confidence intervals are wide (see Hayes 2010 Fig 5). Not appropriate
for driving euthanasia decisions.
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
# Per-variable scoring (Hayes 2010, Figs 3 and A1)
# ---------------------------------------------------------------------------


# Creatinine: thresholds in mg/dL (US). SI conversion: 1 mg/dL = 88.4 umol/L.
# Referent (0 pts) is 0–0.62 mg/dL (0–55 umol/L). This is a
# multivariable artifact; the model's lowest-mortality bucket sits
# below the normal range, and the normal range (0.63–1.35) carries
# score 1.
def creatinine_points(cr_mg_dl: float) -> tuple[int, str]:
    c = cr_mg_dl
    if c <= 0:
        return (0, "Not entered")
    if c <= 0.62:
        return (0, f"{c:.2f} mg/dL (0–0.62, referent)")
    if c <= 1.35:
        return (1, f"{c:.2f} mg/dL (0.63–1.35)")
    if c <= 2.26:
        return (8, f"{c:.2f} mg/dL (1.36–2.26)")
    return (9, f"{c:.2f} mg/dL (>2.26)")


# WBC count: ×10⁹/L (same unit as K/µL). Referent is 5.1–8.5 (normal).
# Note: WBC <5.1 scores 9 — leukopenia in ICU dogs is a high-mortality
# finding (severe sepsis with consumption, parvovirus, immune-mediated
# processes, etc.).
def wbc_points(wbc_x10_9: float) -> tuple[int, str]:
    w = wbc_x10_9
    if w <= 0:
        return (0, "Not entered")
    if w < 5.1:
        return (9, f"{w:.1f} ×10⁹/L (<5.1)")
    if w <= 8.5:
        return (0, f"{w:.1f} ×10⁹/L (5.1–8.5, referent)")
    if w <= 18.0:
        return (2, f"{w:.1f} ×10⁹/L (8.6–18)")
    return (3, f"{w:.1f} ×10⁹/L (>18)")


# Albumin: thresholds in g/L (SI); US g/dL → SI g/L by ×10.
# DIFFERENT from APPLE-fast: in APPLE-full the 31–32 g/L band scores 9
# (higher than <26 g/L which scores 6). The paper explicitly discusses
# this on page 11 as a multivariable artifact — the coefficients
# reflect mortality variance NOT already captured by the other 9
# variables.
def albumin_full_points(albumin_g_l: float) -> tuple[int, str]:
    a = albumin_g_l
    if a <= 0:
        return (0, "Not entered")
    if a < 26:
        return (6, f"{a:.0f} g/L (<26)")
    if a <= 30:
        return (7, f"{a:.0f} g/L (26–30)")
    if a <= 32:
        return (9, f"{a:.0f} g/L (31–32)")
    if a <= 35:
        return (0, f"{a:.0f} g/L (33–35, referent)")
    return (2, f"{a:.0f} g/L (>35)")


# SpO2: in %. Referent is 98–100% (normal saturation).
# Per the paper footnote: if pulse oximetry was not performed (history
# and physical exam did not prompt it), assign zero. The user can
# enter 98–100 to score zero, OR can simply not assess and enter the
# value when known.
def spo2_points(spo2_pct: float) -> tuple[int, str]:
    s = spo2_pct
    if s <= 0:
        return (0, "Not entered")
    if s < 90:
        return (10, f"{s:.0f}% (<90)")
    if s <= 94:
        return (4, f"{s:.0f}% (90–94)")
    if s <= 97:
        return (1, f"{s:.0f}% (95–97)")
    return (0, f"{s:.0f}% (98–100, referent)")


# Total bilirubin: thresholds in mg/dL (US). SI conversion: 1 mg/dL = 17.1 umol/L.
# NON-MONOTONIC scoring: mild bilirubinemia (0.24–0.46) carries the
# highest score (6), and increasingly severe bilirubinemia scores
# lower (0.47–0.93 → 4, >0.93 → 3). This is a multivariable artifact:
# severe bilirubinemia tracks with other high-risk variables already
# in the model (creatinine, lactate, albumin), so the marginal
# contribution shrinks at the extreme.
def bilirubin_points(bili_mg_dl: float) -> tuple[int, str]:
    b = bili_mg_dl
    if b <= 0:
        return (0, "Not entered")
    if b <= 0.23:
        return (0, f"{b:.2f} mg/dL (0–0.23, referent)")
    if b <= 0.46:
        return (6, f"{b:.2f} mg/dL (0.24–0.46)")
    if b <= 0.93:
        return (4, f"{b:.2f} mg/dL (0.47–0.93)")
    return (3, f"{b:.2f} mg/dL (>0.93)")


# Mentation 0–4 (Hayes 2010 Table 3). Assessed at admission, BEFORE
# sedation or analgesia.
# DIFFERENT from APPLE-fast: APPLE-fast assigns 0/4/6/7/14 for
# mentation scores 0/1/2/3/4. APPLE-full assigns 0/5/7/8/13 — the
# top end is slightly compressed because other variables in the
# 10-variable set absorb some of the mortality variance.
def mentation_full_points(score: int) -> tuple[int, str]:
    labels = {
        0: "0: Normal (referent)",
        1: "1: Stands unassisted, responsive but dull",
        2: "2: Stands only when assisted, responsive but dull",
        3: "3: Unable to stand, responsive",
        4: "4: Unable to stand, unresponsive",
    }
    pts = {0: 0, 1: 5, 2: 7, 3: 8, 4: 13}
    if score not in pts:
        return (0, "Not entered")
    return (pts[score], labels[score])


# Respiratory rate: breaths per minute. Referent is 25–36 bpm (normal
# rate for a hospitalized dog). Counterintuitive: 49–60 bpm scores 6,
# higher than >60 bpm which scores 5. Multivariable artifact.
def resp_rate_points(rate_bpm: float) -> tuple[int, str]:
    r = rate_bpm
    if r <= 0:
        return (0, "Not entered")
    if r < 25:
        return (3, f"{r:.0f} bpm (<25)")
    if r <= 36:
        return (0, f"{r:.0f} bpm (25–36, referent)")
    if r <= 48:
        return (5, f"{r:.0f} bpm (37–48)")
    if r <= 60:
        return (6, f"{r:.0f} bpm (49–60)")
    return (5, f"{r:.0f} bpm (>60)")


# Age: years. Referent is 3–5 years (young adult).
def age_points(age_yr: float) -> tuple[int, str]:
    a = age_yr
    if a < 0:
        return (0, "Not entered")
    if a < 3:
        return (3, f"{a:.1f} years (0–2)")
    if a <= 5:
        return (0, f"{a:.1f} years (3–5, referent)")
    if a <= 8:
        return (6, f"{a:.1f} years (6–8)")
    return (8, f"{a:.1f} years (>8)")


# Fluid score 0–2: FAST/TFAST ultrasonographic evaluation per Hayes
# 2010 Table 3 (and Boysen et al. JAVMA 2004 for FAST protocol).
#   0 — No abdominal, thoracic, or pericardial free fluid
#   1 — Free fluid in ONE cavity (abdominal OR thoracic OR pericardial)
#   2 — Free fluid in TWO OR MORE cavities
# Per the paper footnote: if FAST/TFAST was not performed, assign zero.
# The user must explicitly select 0 in this calculator.
def fluid_score_points(fluid: int) -> tuple[int, str]:
    labels = {
        0: "0: no free fluid (referent)",
        1: "1: free fluid in one cavity",
        2: "2: free fluid in ≥2 cavities",
    }
    pts = {0: 0, 1: 3, 2: 4}
    if fluid not in pts:
        return (0, "Not entered")
    return (pts[fluid], labels[fluid])


# Lactate: thresholds in mmol/L (SI). US conversion: 1 mg/dL = 1/9 mmol/L
# (lactate-specific factor; differs from glucose).
# DIFFERENT band edges from APPLE-fast: APPLE-fast uses <2, 2–8, 8–10,
# >10 mmol/L. APPLE-full uses 0–1.9, 2.0–7.9, 8.0–11.0, >11 mmol/L.
# Also DIFFERENT point allocations: fast assigns 0/4/8/12, full assigns
# 0/2/3/6 (compressed because other 9 variables absorb mortality variance).
def lactate_full_points(lac_mmol_l: float) -> tuple[int, str]:
    L = lac_mmol_l
    if L <= 0:
        return (0, "Not entered")
    if L < 2.0:
        return (0, f"{L:.1f} mmol/L (0–1.9, referent)")
    if L <= 7.9:
        return (2, f"{L:.1f} mmol/L (2.0–7.9)")
    if L <= 11.0:
        return (3, f"{L:.1f} mmol/L (8.0–11.0)")
    return (6, f"{L:.1f} mmol/L (>11)")


# ---------------------------------------------------------------------------
# Inputs / Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AppleFullInputs:
    # "si" — creatinine umol/L, albumin g/L, bilirubin umol/L, lactate mmol/L
    # "us" — creatinine mg/dL, albumin g/dL, bilirubin mg/dL, lactate mg/dL
    units: str = "si"
    # 0.0 / -1 / -1.0 are sentinels meaning "user has not entered a value yet".
    # The route layer translates empty form fields to these; the scoring
    # functions then return ("Not entered", 0 points) instead of computing
    # a misleading score from a substituted default. The page render path
    # never feeds a defaulted AppleFullInputs into calculate(); the GET
    # handler passes result=None so the placeholder renders in the
    # result panel slot. See CLAUDE.md non-negotiable #8.
    creatinine: float = 0.0
    wbc: float = 0.0
    albumin: float = 0.0
    spo2: float = 0.0
    bilirubin: float = 0.0
    mentation: int = -1
    resp_rate: float = 0.0
    age: float = -1.0
    fluid_score: int = -1
    lactate: float = 0.0


@dataclass
class ScoreComponent:
    label: str
    value_str: str
    points: int


@dataclass
class AppleFullResult:
    inputs: AppleFullInputs
    components: list[ScoreComponent] = field(default_factory=list)
    total_score: int = 0
    mortality_pct: float = 0.0
    band_label: str = ""
    recommendation: str = ""
    sources: tuple[Source, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Source citation
# ---------------------------------------------------------------------------


_HAYES_2010 = Source(
    citation=(
        "Hayes G, Mathews K, Doig G, et al. The Acute Patient Physiologic "
        "and Laboratory Evaluation (APPLE) Score: A Severity of Illness "
        "Stratification System for Hospitalized Dogs. J Vet Intern Med "
        "2010;24:1034–1047. AUROC 0.93 construction / 0.91 validation. "
        "Cutoff >30/80: specificity 89%, sensitivity 81% for mortality."
    ),
    url="https://doi.org/10.1111/j.1939-1676.2010.0552.x",
)


# ---------------------------------------------------------------------------
# calculate()
# ---------------------------------------------------------------------------


def calculate(inputs: AppleFullInputs) -> AppleFullResult:
    """Compute the 10-variable APPLE-full score.

    Mortality probability via the published logistic equation:
        R = 0.237 × score − 8.294
        P = exp(R) / (1 + exp(R))

    The scoring functions take SI internally; US inputs are converted
    before being passed in. See the per-variable scoring functions for
    unit conversion details.
    """
    if inputs.units == "us":
        cr_mg_dl = inputs.creatinine
        alb_g_l = inputs.albumin * 10.0
        bili_mg_dl = inputs.bilirubin
        lac_mmol_l = inputs.lactate / 9.0
    else:
        cr_mg_dl = inputs.creatinine / 88.4
        alb_g_l = inputs.albumin
        bili_mg_dl = inputs.bilirubin / 17.1
        lac_mmol_l = inputs.lactate

    cr_pts, cr_str = creatinine_points(cr_mg_dl)
    wbc_pts, wbc_str = wbc_points(inputs.wbc)
    alb_pts, alb_str = albumin_full_points(alb_g_l)
    spo2_pts, spo2_str = spo2_points(inputs.spo2)
    bili_pts, bili_str = bilirubin_points(bili_mg_dl)
    ment_pts, ment_str = mentation_full_points(inputs.mentation)
    rr_pts, rr_str = resp_rate_points(inputs.resp_rate)
    age_pts, age_str = age_points(inputs.age)
    fluid_pts, fluid_str = fluid_score_points(inputs.fluid_score)
    lac_pts, lac_str = lactate_full_points(lac_mmol_l)

    components = [
        ScoreComponent("Creatinine", cr_str, cr_pts),
        ScoreComponent("WBC count", wbc_str, wbc_pts),
        ScoreComponent("Albumin", alb_str, alb_pts),
        ScoreComponent("SpO₂", spo2_str, spo2_pts),
        ScoreComponent("Total bilirubin", bili_str, bili_pts),
        ScoreComponent("Mentation", ment_str, ment_pts),
        ScoreComponent("Respiratory rate", rr_str, rr_pts),
        ScoreComponent("Age", age_str, age_pts),
        ScoreComponent("Fluid score (FAST/TFAST)", fluid_str, fluid_pts),
        ScoreComponent("Lactate", lac_str, lac_pts),
    ]

    total = (
        cr_pts + wbc_pts + alb_pts + spo2_pts + bili_pts
        + ment_pts + rr_pts + age_pts + fluid_pts + lac_pts
    )

    # Mortality equation (Hayes 2010 eq. 2): R = 0.237×score − 8.294
    R = 0.237 * total - 8.294
    pct = 100.0 * (exp(R) / (1.0 + exp(R)))

    # Risk bands keyed off the two published cutoffs (>30/80 and >40/80)
    # plus a low-risk band below the high-sensitivity cutoff
    if total <= 20:
        band = "Low risk"
        recommendation = (
            "Population-level mortality risk below the >30/80 sensitivity "
            "cutoff. Continue supportive care per the primary disease "
            "process; the score does not flag this patient as high-risk "
            "in the Hayes 2010 cohort. Individual confidence intervals "
            "remain wide. Do not interpret a low score as a guarantee "
            "of survival."
        )
    elif total <= 30:
        band = "Moderate risk"
        recommendation = (
            "Below the >30/80 cutoff (89% specificity, 81% sensitivity). "
            "Close ICU monitoring and aggressive supportive care indicated. "
            "Re-score over the first 24 h; trajectory carries more "
            "prognostic weight than the admission value."
        )
    elif total <= 40:
        band = "High risk"
        recommendation = (
            "Between the >30/80 (81% sensitivity) and >40/80 (98% specificity) "
            "cutoffs. ICU-level care strongly indicated. A substantial "
            "fraction of survivors also score in this range. The score "
            "supports but does not replace clinical judgment."
        )
    else:
        band = "Critical risk"
        recommendation = (
            "Above the >40/80 cutoff (98% specificity for mortality). "
            "Aggressive resuscitation and monitoring indicated. The score "
            "is a population-level risk-stratification tool; individual "
            "confidence intervals remain wide and the score is NOT "
            "appropriate for driving euthanasia decisions."
        )

    return AppleFullResult(
        inputs=inputs,
        components=components,
        total_score=total,
        mortality_pct=pct,
        band_label=band,
        recommendation=recommendation,
        sources=(_HAYES_2010,),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/apple-full", response_class=HTMLResponse)
async def apple_full_page(request: Request):
    """Initial GET — empty form, placeholder where the result would go.

    Per the calculator default-output safety rule (CLAUDE.md non-negotiable
    #8), the result panel does NOT pre-render with a score from
    default-valued inputs. A clinician glancing at the page must NEVER
    see a numeric result that could be misread as the patient's actual
    APPLE-full.
    """
    templates = request.app.state.templates
    inputs = AppleFullInputs()
    return templates.TemplateResponse(
        "apple_full.html",
        {
            "request": request,
            "inputs": inputs,
            "result": None,
        },
    )


@router.post("/apple-full/compute", response_class=HTMLResponse)
async def apple_full_compute(
    request: Request,
    units: str = Form("si"),
    creatinine: str = Form(""),
    wbc: str = Form(""),
    albumin: str = Form(""),
    spo2: str = Form(""),
    bilirubin: str = Form(""),
    mentation: str = Form(""),
    resp_rate: str = Form(""),
    age: str = Form(""),
    fluid_score: str = Form(""),
    lactate: str = Form(""),
):
    """Compute the score only when ALL ten required variables are
    present and parseable. Otherwise return the placeholder partial.

    Mentation (0–4) and fluid score (0–2) are separate validations
    because 0 is a valid choice for each; an empty value means the
    user has not selected anything yet.
    """
    templates = request.app.state.templates

    parsed = {
        "creatinine": parse_positive_float(creatinine),
        "wbc": parse_positive_float(wbc),
        "albumin": parse_positive_float(albumin),
        "spo2": parse_positive_float(spo2),
        "bilirubin": parse_positive_float(bilirubin),
        "resp_rate": parse_positive_float(resp_rate),
        "age": parse_positive_float(age),
        "lactate": parse_positive_float(lactate),
    }
    mentation_valid = (mentation or "").strip() in ("0", "1", "2", "3", "4")
    fluid_score_valid = (fluid_score or "").strip() in ("0", "1", "2")
    missing_numeric = [k for k, v in parsed.items() if v is None]

    if missing_numeric or not mentation_valid or not fluid_score_valid:
        labels_map = {
            "creatinine": "creatinine",
            "wbc": "WBC count",
            "albumin": "albumin",
            "spo2": "SpO₂",
            "bilirubin": "total bilirubin",
            "resp_rate": "respiratory rate",
            "age": "age",
            "lactate": "lactate",
        }
        missing = [labels_map[k] for k in missing_numeric]
        if not mentation_valid:
            missing.append("mentation score")
        if not fluid_score_valid:
            missing.append("fluid score")

        if len(missing) == 1:
            msg = f"Enter {missing[0]} to compute the APPLE-full score."
        elif len(missing) == 2:
            msg = (
                f"Enter {missing[0]} and {missing[1]} "
                "to compute the APPLE-full score."
            )
        elif len(missing) <= 4:
            msg = (
                "Enter " + ", ".join(missing[:-1])
                + f", and {missing[-1]} to compute the APPLE-full score."
            )
        else:
            msg = (
                f"Enter all 10 variables ({len(missing)} still missing) "
                "to compute the APPLE-full score."
            )

        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_message": msg,
            },
        )

    inputs = AppleFullInputs(
        units=units if units in ("si", "us") else "si",
        creatinine=parsed["creatinine"],
        wbc=parsed["wbc"],
        albumin=parsed["albumin"],
        spo2=parsed["spo2"],
        bilirubin=parsed["bilirubin"],
        mentation=int(mentation),
        resp_rate=parsed["resp_rate"],
        age=parsed["age"],
        fluid_score=int(fluid_score),
        lactate=parsed["lactate"],
    )
    result = calculate(inputs)
    return templates.TemplateResponse(
        "partials/apple_full_result.html",
        {
            "request": request,
            "inputs": inputs,
            "result": result,
        },
    )


APPLE_FULL_CATALOG_ENTRY = {
    "slug": "apple-full",
    "display_name": "APPLE-full illness severity",
    "short_name": "APPLE-full",
    "category": "Emergency",
    "kind": "diagnostic_score",
    "mechanism_summary": (
        "10-variable illness severity score for hospitalized dogs "
        "(Hayes 2010). Creatinine, WBC, albumin, SpO₂, total "
        "bilirubin, mentation, respiratory rate, age, fluid score "
        "(FAST/TFAST), and lactate map to a 0–80 score and predicted "
        "hospital mortality. AUROC 0.93/0.91 (construction/validation), "
        "better than APPLE-fast (0.87/0.84). Cutoff >30/80 carries "
        "89% specificity / 81% sensitivity for mortality. Population-"
        "level tool; individual confidence intervals are wide. Not for "
        "driving euthanasia decisions."
    ),
}
