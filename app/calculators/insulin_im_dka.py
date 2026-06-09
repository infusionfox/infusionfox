"""
Intermittent IM regular insulin for DKA. Hoehne / Silverstein Ch. 73.

Source: Hoehne SN. Diabetic Ketoacidosis. In: Silverstein DC, Hopper K, eds.
Small Animal Critical Care Medicine. 3rd ed. Elsevier; 2023. Ch. 73.
The intermittent IM protocol per Hoehne (citing Macintire 1993, ref 28):

    Initial dose:   0.2 U/kg IM (regular crystalline insulin)
    Then hourly IM injections, dosed by the BG drop in the previous hour:

        BG drop > 75 mg/dL    → 0.05 U/kg IM (drop too fast, back off)
        BG drop 50–75 mg/dL   → 0.1 U/kg IM  (on target)
        BG drop < 50 mg/dL    → 0.2 U/kg IM  (drop too slow, push)

    Goal: lower BG to < 250 mg/dL by no more than 50–75 mg/dL/hr.

Notes:
    - This is an alternative to the IV CRI protocol (Table 73.1).
      Hoehne notes both are acceptable; the IV CRI is more commonly
      used in critical-care settings because it offers finer
      titration. The IM protocol is useful when continuous IV
      infusion isn't practical (eg, smaller hospitals without
      syringe pumps; specific clinical workflows).
    - Subcutaneous insulin is NOT recommended in dehydrated DKA
      patients, absorption is unreliable.
    - Regular crystalline insulin only. NOT lispro, aspart, NPH,
      glargine, or any long-acting form for this protocol.
    - Same goals, electrolyte cautions, and monitoring schedule as
      the CRI protocol. See /insulin-cri-dka for the alternative.

Stock concentration:
    Regular insulin commonly comes as 100 U/mL (U-100). Calculator
    outputs the dose in both U and mL of U-100 stock for bedside use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

INSULIN_IM_LOADING_DOSE_U_PER_KG = 0.2
INSULIN_IM_STOCK_U_PER_ML = 100.0  # U-100


class InsulinImSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


class InsulinImMode(str, Enum):
    """Initial loading dose, or subsequent dose-adjusted-by-drop?"""

    LOADING = "loading"
    SUBSEQUENT = "subsequent"


@dataclass
class InsulinImTier:
    """One row of Hoehne's intermittent-IM sliding scale."""

    label: str
    drop_low: int | None  # inclusive lower bound on BG drop, None = open
    drop_high: int | None  # exclusive upper bound, None = open
    dose_u_per_kg: float
    interpretation: str  # what the tier MEANS clinically


# Hoehne IM scale (citing Macintire 1993). Ranges express "BG drop in the
# last hour" in mg/dL.
INSULIN_IM_TIERS: list[InsulinImTier] = [
    InsulinImTier(
        label="BG drop > 75 mg/dL/hr",
        drop_low=75,
        drop_high=None,
        dose_u_per_kg=0.05,
        interpretation=(
            "Glucose is dropping too fast. Reduce dose to 0.05 U/kg "
            "to slow the rate. Confirm fluid composition is appropriate "
            "(consider adding 2.5% dextrose if BG approaching 250 mg/dL)."
        ),
    ),
    InsulinImTier(
        label="BG drop 50–75 mg/dL/hr",
        drop_low=50,
        drop_high=76,
        dose_u_per_kg=0.1,
        interpretation=(
            "Glucose is dropping at the target rate. Continue at 0.1 U/kg. This is the desired band."
        ),
    ),
    InsulinImTier(
        label="BG drop < 50 mg/dL/hr",
        drop_low=None,
        drop_high=50,
        dose_u_per_kg=0.2,
        interpretation=(
            "Glucose is not dropping fast enough. Increase dose to "
            "0.2 U/kg. If multiple sequential cycles fail to drop BG "
            "into the target range, reassess hydration, electrolytes, "
            "and concurrent disease, consider switching to IV CRI for "
            "finer titration."
        ),
    ),
]


@dataclass
class InsulinImInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: InsulinImSpecies
    mode: InsulinImMode
    # For SUBSEQUENT mode only:
    previous_bg_mg_per_dl: float | None = None
    current_bg_mg_per_dl: float | None = None


@dataclass
class InsulinImResult:
    weight_kg: float
    species: InsulinImSpecies
    mode: InsulinImMode
    dose_u_per_kg: float
    total_units: float
    volume_ml_u100: float
    stock_u_per_ml: float
    matched_tier: InsulinImTier | None
    bg_drop_mg_per_dl: float | None
    previous_bg: float | None
    current_bg: float | None
    target_drop_band_low: int
    target_drop_band_high: int
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale. False when weight is
    # missing/non-positive, OR when subsequent-dose mode is requested
    # without both BG values. The template suppresses numeric output
    # so the clinician never sees a computed insulin dose alongside
    # an "input must be > 0" message.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _match_tier(drop: float) -> InsulinImTier:
    for tier in INSULIN_IM_TIERS:
        low_ok = tier.drop_low is None or drop >= tier.drop_low
        high_ok = tier.drop_high is None or drop < tier.drop_high
        if low_ok and high_ok:
            return tier
    return INSULIN_IM_TIERS[-1]


def compute_insulin_im(inputs: InsulinImInputs) -> InsulinImResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        # Math on a non-positive weight produces a negative or zero
        # insulin dose; refuse to compute.
        return InsulinImResult(
            weight_kg=weight_kg,
            species=inputs.species,
            mode=inputs.mode,
            dose_u_per_kg=0.0,
            total_units=0.0,
            volume_ml_u100=0.0,
            stock_u_per_ml=INSULIN_IM_STOCK_U_PER_ML,
            matched_tier=None,
            bg_drop_mg_per_dl=None,
            previous_bg=inputs.previous_bg_mg_per_dl,
            current_bg=inputs.current_bg_mg_per_dl,
            target_drop_band_low=50,
            target_drop_band_high=75,
            warnings=["Weight must be greater than zero."],
            notes=[],
            sources=INSULIN_IM_DKA_SOURCES,
            valid=False,
        )

    matched_tier: InsulinImTier | None = None
    bg_drop: float | None = None
    dose_u_per_kg: float

    if inputs.mode == InsulinImMode.LOADING:
        dose_u_per_kg = INSULIN_IM_LOADING_DOSE_U_PER_KG
        notes.append(
            f"Initial loading dose: {INSULIN_IM_LOADING_DOSE_U_PER_KG} U/kg "
            f"IM (regular crystalline insulin). Re-check BG in 1 hour, then "
            f"switch to the subsequent-dose mode and use the BG drop to "
            f"select the next dose from the sliding scale."
        )
    else:
        # SUBSEQUENT mode
        if inputs.previous_bg_mg_per_dl is None or inputs.current_bg_mg_per_dl is None:
            warnings.append(
                "Subsequent-dose mode requires both the previous and current blood glucose values."
            )
            return InsulinImResult(
                weight_kg=round(weight_kg, 2),
                species=inputs.species,
                mode=inputs.mode,
                dose_u_per_kg=0.0,
                total_units=0.0,
                volume_ml_u100=0.0,
                stock_u_per_ml=INSULIN_IM_STOCK_U_PER_ML,
                matched_tier=None,
                bg_drop_mg_per_dl=None,
                previous_bg=inputs.previous_bg_mg_per_dl,
                current_bg=inputs.current_bg_mg_per_dl,
                target_drop_band_low=50,
                target_drop_band_high=75,
                warnings=warnings,
                notes=notes,
                sources=INSULIN_IM_DKA_SOURCES,
                valid=False,
            )

        bg_drop = inputs.previous_bg_mg_per_dl - inputs.current_bg_mg_per_dl
        if bg_drop < 0:
            warnings.append(
                f"⚠ Blood glucose ROSE by {abs(bg_drop):g} mg/dL in the last "
                f"hour rather than fell. The sliding scale assumes BG is "
                f"declining. Check: insulin actually delivered? Bag/syringe "
                f"prepared correctly? Concurrent stressor (infection, "
                f"counterregulatory hormone surge)? Consider going up to "
                f"0.2 U/kg IM and reassessing fluid composition (do NOT "
                f"increase dose beyond 0.2 U/kg)."
            )
            # Treat as if drop is below 50 (slow → push to 0.2)
            matched_tier = INSULIN_IM_TIERS[2]
            dose_u_per_kg = matched_tier.dose_u_per_kg
        else:
            matched_tier = _match_tier(bg_drop)
            dose_u_per_kg = matched_tier.dose_u_per_kg
            notes.append(
                f"BG drop: {inputs.previous_bg_mg_per_dl:g} → "
                f"{inputs.current_bg_mg_per_dl:g} mg/dL "
                f"(decline of {bg_drop:g} mg/dL/hr). Matched: "
                f"{matched_tier.label}. {matched_tier.interpretation}"
            )

        # Add stop-condition warning if BG is below 100
        if inputs.current_bg_mg_per_dl < 100:
            warnings.insert(
                0,
                f"⚠ Current BG ({inputs.current_bg_mg_per_dl:g} mg/dL) is "
                f"below 100 mg/dL. Do NOT continue routine insulin "
                f"dosing in this range; switch to dextrose-supplemented "
                f"fluids (5% dextrose) and recheck BG. Resume insulin "
                f"only when BG > 100 mg/dL.",
            )
        # Or BG below 250, at target
        elif inputs.current_bg_mg_per_dl < 250:
            notes.append(
                f"Current BG ({inputs.current_bg_mg_per_dl:g} mg/dL) is "
                f"below 250 mg/dL. DKA target reached. Continue insulin "
                f"per the scale, and add 2.5% dextrose to fluids if not "
                f"already done. Step to 5% dextrose if BG drops below 150 "
                f"mg/dL. Watch for the < 100 mg/dL stop point."
            )

    total_units = weight_kg * dose_u_per_kg
    volume_ml = total_units / INSULIN_IM_STOCK_U_PER_ML

    # Persistent warnings (apply to all modes)
    warnings.append(
        "Use regular crystalline insulin only. NOT lispro, aspart, "
        "NPH, glargine, detemir, or any long-acting form. Regular "
        "insulin is the only formulation appropriate for the "
        "intermittent IM protocol."
    )
    warnings.append(
        "IM only. Do NOT give SC in a dehydrated DKA patient; absorption is unreliable."
    )
    warnings.append(
        "Goal: lower blood glucose by no more than 50–75 mg/dL/hr toward "
        "< 250 mg/dL. Re-check BG hourly, dose by the BG drop in the "
        "previous hour. If BG fails to drop into the target band over "
        "multiple cycles, reassess hydration, electrolytes, and "
        "concurrent disease; consider switching to IV CRI for finer "
        "titration."
    )
    warnings.append(
        "Hypokalemia, hypophosphatemia, and hypomagnesemia commonly "
        "develop or worsen as DKA therapy progresses. Monitor "
        "electrolytes every 4–6 hours initially and supplement per "
        "published sliding scales."
    )

    notes.append(
        "Sliding scale: BG drop > 75 → 0.05 U/kg; BG drop 50–75 → "
        "0.1 U/kg; BG drop < 50 → 0.2 U/kg. Initial dose 0.2 U/kg IM."
    )
    notes.append(
        f"Stock: regular insulin U-100 ({INSULIN_IM_STOCK_U_PER_ML:g} U/mL). "
        f"For accurate dosing of small volumes, draw with a U-100 insulin "
        f"syringe."
    )

    return InsulinImResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        mode=inputs.mode,
        dose_u_per_kg=dose_u_per_kg,
        total_units=round(total_units, 2),
        volume_ml_u100=round(volume_ml, 3),
        stock_u_per_ml=INSULIN_IM_STOCK_U_PER_ML,
        matched_tier=matched_tier,
        bg_drop_mg_per_dl=(round(bg_drop, 1) if bg_drop is not None else None),
        previous_bg=inputs.previous_bg_mg_per_dl,
        current_bg=inputs.current_bg_mg_per_dl,
        target_drop_band_low=50,
        target_drop_band_high=75,
        warnings=warnings,
        notes=notes,
        sources=INSULIN_IM_DKA_SOURCES,
    )


INSULIN_IM_DKA_SOURCES = (
    Source(
        citation=(
            "Macintire DK. Treatment of diabetic ketoacidosis in dogs by "
            "continuous low-dose intravenous infusion of insulin. "
            "JAVMA 1993;202:1266–1272. (Original IM intermittent protocol "
            "described as alternative to CRI.)"
        )
    ),
    Source(
        citation=(
            "Koenig A. Hypoglycemia and DKA. In: Silverstein DC, Hopper K, eds. "
            "Small Animal Critical Care Medicine, 3rd ed. Elsevier, 2023. "
            "Chapter 75."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, regular insulin monograph. "
            "IM intermittent dosing for DKA (0.2 U/kg loading, then 0.1 U/kg "
            "q1h IM) as an alternative when CRI is unavailable."
        )
    ),
)

INSULIN_IM_CATALOG_ENTRY = {
    "slug": "insulin-im-dka",
    "display_name": "Insulin IM intermittent (DKA)",
    "short_name": "Insulin IM · DKA",
    "category": "Endocrine",
    "kind": "single_drug_cri",
    "mechanism_summary": (
        "Hourly intermittent IM regular crystalline insulin provides "
        "DKA-grade insulinization without continuous IV infusion. "
        "The sliding scale (initial 0.2 U/kg, then 0.05–0.2 U/kg "
        "based on the previous hour's BG drop) titrates exposure "
        "toward the 50–75 mg/dL/hr target decline. Less rate-"
        "controllable than IV CRI but requires no syringe pump and "
        "is useful when continuous infusion isn't practical."
    ),
    "indications_summary": (
        "Intermittent IM regular insulin for diabetic ketoacidosis "
        "in dogs and cats. An alternative to the IV CRI protocol when "
        "continuous infusion isn't practical: limited pump "
        "availability, patient can't stay on a line, or staffing "
        "constraints. Workflow has two modes: a single loading dose, "
        "then hourly doses titrated against the BG drop measured each "
        "hour."
    ),
}
