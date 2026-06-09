"""
LDDST (Low-Dose Dexamethasone Suppression Test) interpretation tool.

Encoded against the 2013 ACVIM consensus statement on diagnosis of canine
hyperadrenocorticism (Behrend EN, Kooistra HS, Nelson R, Reusch CE,
Scott-Moncrieff JC. JVIM 2013;27:1292-1304. doi:10.1111/jvim.12192).

Logic flow (two-stage, faithful to the consensus statement):

Stage 1. Is HAC present?
    Diagnosis depends on the 8-hour post-dexamethasone cortisol concentration.
    If 8-hour cortisol > cut-off → consistent with HAC, proceed to Stage 2.
    If 8-hour cortisol ≤ cut-off → does not support HAC.
    "Inverse pattern" (8-hour suppressed but 4-hour elevated above baseline):
    flagged as "highly suspicious for HAC" per the consensus statement, with
    a note recommending further testing.

Stage 2. Is it PDH? (only run if Stage 1 = HAC)
    Per the consensus statement (citing Feldman 1996), a dog with HAC is
    identified as PDH if ANY of the following are true:
        - 4-hour cortisol < cut-off, OR
        - 4-hour cortisol < 50% of basal cortisol, OR
        - 8-hour cortisol < 50% of basal cortisol (but > cut-off, established
          by Stage 1)
    If NONE of these are met: dexamethasone-resistant pattern. The dog could
    have either AT or one of the ~25% of PDH cases that fail to suppress.
    Per the consensus statement, lack of suppression does NOT confirm AT.

Cut-off:
    The consensus statement deliberately does NOT specify a single 8-hour
    cortisol cut-off, labs and assays vary, and the panel recommends each
    lab establish its own. We default to 1.4 µg/dL (a commonly reported
    value) but expose this as a user-editable input with a prominent warning
    that the user should verify against their own lab's reference range.

Units:
    The chart's thresholds are encoded in µg/dL. nmol/L inputs convert to
    µg/dL at the input boundary so the rule engine has a single source of
    truth and can't drift when units are mixed.
    Conversion: 1 µg/dL = 27.59 nmol/L (cortisol MW 362.46 g/mol).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source

# Cortisol MW 362.46 g/mol → 1 µg/dL = 27.59 nmol/L
UG_DL_TO_NMOL_L = 27.59
NMOL_L_TO_UG_DL = 1 / UG_DL_TO_NMOL_L

DEFAULT_8H_CUTOFF_UG_DL = 1.4


class CortisolUnit(str, Enum):
    UG_PER_DL = "ug_dl"
    NMOL_PER_L = "nmol_l"


def to_ug_dl(value: float, unit: CortisolUnit) -> float:
    if unit == CortisolUnit.UG_PER_DL:
        return value
    if unit == CortisolUnit.NMOL_PER_L:
        return value * NMOL_L_TO_UG_DL
    raise ValueError(f"Unknown cortisol unit: {unit}")


def to_nmol_l(value_ug_dl: float) -> float:
    return value_ug_dl * UG_DL_TO_NMOL_L


# ---------------------------------------------------------------------------
# Result categories
# ---------------------------------------------------------------------------


class LDDSTCategory(str, Enum):
    NOT_HAC = "not_hac"
    NOT_HAC_INVERSE = "not_hac_inverse"  # special: 8-hr suppressed but 4-hr elevated
    SUPPORTS_PDH = "supports_pdh"
    DEX_RESISTANT = "dex_resistant"
    INVALID = "invalid"  # input errors


CATEGORY_TITLES: dict[LDDSTCategory, str] = {
    LDDSTCategory.NOT_HAC: "Pattern does not support HAC",
    LDDSTCategory.NOT_HAC_INVERSE: "Inverse pattern, further testing indicated",
    LDDSTCategory.SUPPORTS_PDH: "Pattern consistent with PDH",
    LDDSTCategory.DEX_RESISTANT: "Dexamethasone-resistant pattern (PDH or AT)",
    LDDSTCategory.INVALID: "Input error",
}

CATEGORY_DESCRIPTIONS: dict[LDDSTCategory, str] = {
    LDDSTCategory.NOT_HAC: (
        "The 8-hour post-dexamethasone cortisol is at or below the cut-off, "
        "indicating adequate suppression of the hypothalamic-pituitary-adrenal "
        "axis."
    ),
    LDDSTCategory.NOT_HAC_INVERSE: (
        "The 8-hour cortisol is suppressed below the cut-off, but the 4-hour "
        "cortisol exceeds the basal value. Per the consensus statement, this "
        "inverse pattern is highly suspicious for HAC and further testing is "
        "indicated."
    ),
    LDDSTCategory.SUPPORTS_PDH: (
        "The 8-hour cortisol exceeds the cut-off (consistent with HAC), and "
        "at least one suppression criterion is met (4-hour < cut-off, 4-hour "
        "< 50% of baseline, or 8-hour < 50% of baseline). Per the consensus "
        "statement, suppression on the LDDST identifies PDH within a "
        "population of dogs already known to have HAC."
    ),
    LDDSTCategory.DEX_RESISTANT: (
        "The 8-hour cortisol exceeds the cut-off (consistent with HAC), but "
        "no suppression criteria are met. Per the consensus statement, "
        "dexamethasone resistance occurs in 100% of dogs with adrenal tumor "
        "and approximately 25% of dogs with PDH. Lack of suppression does "
        "not confirm AT, additional testing (cACTH, abdominal ultrasound, "
        "or HDDST) is needed to differentiate."
    ),
    LDDSTCategory.INVALID: "Check input values.",
}


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class LDDSTInputs:
    baseline_cortisol: float
    cortisol_4h: float
    cortisol_8h: float
    cutoff_8h: float = DEFAULT_8H_CUTOFF_UG_DL
    unit: CortisolUnit = CortisolUnit.UG_PER_DL


@dataclass
class CriterionEval:
    """One of the three PDH-suppression criteria, with whether it was met."""

    label: str
    met: bool
    detail: str


@dataclass
class LDDSTResult:
    unit: CortisolUnit
    baseline: float
    cortisol_4h: float
    cortisol_8h: float
    cutoff_8h: float

    # Same values normalized to µg/dL (used for rule evaluation)
    baseline_ug_dl: float
    cortisol_4h_ug_dl: float
    cortisol_8h_ug_dl: float
    cutoff_8h_ug_dl: float

    percent_4h: float | None
    percent_8h: float | None

    # Stage 1
    hac_present: bool
    stage1_explanation: str

    # Stage 2 (only meaningful if hac_present)
    pdh_criteria: list[CriterionEval]

    category: LDDSTCategory
    category_title: str
    category_description: str

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale. False when the LDDSTCategory
    # is INVALID (i.e., one or more cortisol/cutoff inputs are non-positive).
    # The template suppresses the stage-1/stage-2 interpretive blocks so the
    # clinician never sees a negative-cortisol-driven category.
    valid: bool = True


def interpret_lddst(inputs: LDDSTInputs) -> LDDSTResult:
    warnings: list[str] = []
    notes: list[str] = []

    # Normalize all four values to µg/dL, rule engine operates only here
    baseline = to_ug_dl(inputs.baseline_cortisol, inputs.unit)
    h4 = to_ug_dl(inputs.cortisol_4h, inputs.unit)
    h8 = to_ug_dl(inputs.cortisol_8h, inputs.unit)
    cutoff = to_ug_dl(inputs.cutoff_8h, inputs.unit)

    # ---- Input validation ----
    if baseline <= 0:
        warnings.append("Baseline cortisol must be greater than zero.")
    if h4 < 0:
        warnings.append("4-hour cortisol cannot be negative.")
    if h8 < 0:
        warnings.append("8-hour cortisol cannot be negative.")
    if cutoff <= 0:
        warnings.append("Cut-off must be greater than zero.")

    # Compute percents (used by criteria below)
    pct_4h = (h4 / baseline) * 100 if baseline > 0 else None
    pct_8h = (h8 / baseline) * 100 if baseline > 0 else None

    # ---- Stage 1: HAC present? ----
    # Uses 8-hour cortisol vs cut-off.
    if warnings:
        category = LDDSTCategory.INVALID
        stage1_explanation = "Inputs invalid, see warnings."
        hac_present = False
        criteria_eval: list[CriterionEval] = []
    else:
        hac_present = h8 > cutoff
        if hac_present:
            stage1_explanation = (
                f"8-hour cortisol ({h8:.2f} µg/dL) exceeds the cut-off "
                f"({cutoff:.2f} µg/dL) → consistent with HAC."
            )
        else:
            # Check for the inverse pattern: 4-hour exceeds baseline
            inverse = h4 > baseline
            if inverse:
                stage1_explanation = (
                    f"8-hour cortisol ({h8:.2f} µg/dL) is at or below the "
                    f"cut-off ({cutoff:.2f} µg/dL), but 4-hour cortisol "
                    f"({h4:.2f} µg/dL) exceeds baseline ({baseline:.2f} µg/dL). "
                    f"This is the consensus statement's 'inverse pattern.'"
                )
                category = LDDSTCategory.NOT_HAC_INVERSE
            else:
                stage1_explanation = (
                    f"8-hour cortisol ({h8:.2f} µg/dL) is at or below the "
                    f"cut-off ({cutoff:.2f} µg/dL) → adequate suppression."
                )
                category = LDDSTCategory.NOT_HAC

        # ---- Stage 2: PDH? (only if HAC) ----
        criteria_eval = []
        if hac_present:
            c1_met = h4 < cutoff
            criteria_eval.append(
                CriterionEval(
                    label="4-hour cortisol < cut-off",
                    met=c1_met,
                    detail=f"4-hr {h4:.2f} {'<' if c1_met else '≥'} cut-off {cutoff:.2f} µg/dL",
                )
            )

            c2_met = pct_4h is not None and pct_4h < 50.0
            criteria_eval.append(
                CriterionEval(
                    label="4-hour cortisol < 50% of baseline",
                    met=c2_met,
                    detail=(
                        f"4-hr is {pct_4h:.1f}% of baseline"
                        if pct_4h is not None
                        else "no baseline available"
                    ),
                )
            )

            c3_met = pct_8h is not None and pct_8h < 50.0
            criteria_eval.append(
                CriterionEval(
                    label="8-hour cortisol < 50% of baseline",
                    met=c3_met,
                    detail=(
                        f"8-hr is {pct_8h:.1f}% of baseline"
                        if pct_8h is not None
                        else "no baseline available"
                    ),
                )
            )

            any_met = any(c.met for c in criteria_eval)
            category = LDDSTCategory.SUPPORTS_PDH if any_met else LDDSTCategory.DEX_RESISTANT

    # ---- Notes ----
    if not warnings and inputs.cutoff_8h == DEFAULT_8H_CUTOFF_UG_DL and inputs.unit == CortisolUnit.UG_PER_DL:
        notes.append(
            f"Using default 8-hour cut-off of {DEFAULT_8H_CUTOFF_UG_DL} µg/dL. "
            f"The consensus statement does not specify a single value, verify "
            f"against your lab's reference range and override the cut-off if needed."
        )

    return LDDSTResult(
        unit=inputs.unit,
        baseline=inputs.baseline_cortisol,
        cortisol_4h=inputs.cortisol_4h,
        cortisol_8h=inputs.cortisol_8h,
        cutoff_8h=inputs.cutoff_8h,
        baseline_ug_dl=round(baseline, 4),
        cortisol_4h_ug_dl=round(h4, 4),
        cortisol_8h_ug_dl=round(h8, 4),
        cutoff_8h_ug_dl=round(cutoff, 4),
        percent_4h=round(pct_4h, 1) if pct_4h is not None else None,
        percent_8h=round(pct_8h, 1) if pct_8h is not None else None,
        hac_present=hac_present,
        stage1_explanation=stage1_explanation,
        pdh_criteria=criteria_eval,
        category=category,
        category_title=CATEGORY_TITLES[category],
        category_description=CATEGORY_DESCRIPTIONS[category],
        warnings=warnings,
        notes=notes,
        sources=LDDST_SOURCES,
        valid=category != LDDSTCategory.INVALID,
    )


LDDST_SOURCES = (
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
            "Feldman EC, Nelson RW, Reusch CE, Scott-Moncrieff JCR. Canine and "
            "Feline Endocrinology, 4th ed. Elsevier, 2015. Chapter 11 (Canine "
            "Hyperadrenocorticism). LDDST protocol, interpretation of 4-hour and "
            "8-hour cortisol patterns, and discrimination between PDH and AT."
        )
    ),
    Source(
        citation=(
            "Behrend EN. Hyperadrenocorticism. In: Ettinger SJ, Feldman EC, Côté "
            "E, eds. Textbook of Veterinary Internal Medicine, 8th ed. Elsevier, "
            "2017."
        )
    ),
)

LDDST_CATALOG_ENTRY = {
    "slug": "lddst",
    "display_name": "LDDST interpretation",
    "short_name": "LDDST",
    "category": "Endocrine & Metabolic",
    "mechanism_summary": (
        "Two-stage interpretation of a low-dose dexamethasone suppression test "
        "per the 2013 ACVIM consensus statement on canine hyperadrenocorticism: "
        "first determine if HAC is present, then within HAC cases evaluate "
        "the suppression criteria for pituitary-dependent disease."
    ),
    "indications_summary": (
        "Interpretation of the low-dose dexamethasone suppression "
        "test in dogs with a clinical pretest probability for "
        "hyperadrenocorticism. Enter the basal, 4-hour, and 8-hour "
        "cortisol values; returns a classification as suppression "
        "(normal), non-suppression (consistent with HAC), or a "
        "pattern distinguishing pituitary-dependent from "
        "adrenal-dependent disease. Not a screening test."
    ),
}
