"""
Hypernatremia water-deficit calculator.

Source: DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base Disorders in
Small Animal Practice. 4th ed. St. Louis, MO: Elsevier Saunders; 2012.
Chapter 3, "Disorders of Sodium and Water: Hypernatremia and Hyponatremia,"
pp. 60-61.

Clinical logic, three mechanism-based pathways:

1. PURE WATER LOSS
   - Patient lost water without proportional sodium loss
   - Examples: water deprivation, primary diabetes insipidus, central DI
   - Fluid: 5% dextrose in water (effectively free water once glucose is
     metabolized; mildly hypotonic to plasma at 278 mOsm/kg)
   - Replacement: water deficit replaced over 48 hours per DiBartola

2. HYPOTONIC LOSS
   - Patient lost water AND sodium, but lost more water proportionally
   - Examples: osmotic diuresis (DKA, mannitol), GI losses with ongoing
     dehydration, third-spacing
   - Step 1: restore ECF volume with isotonic crystalloid (0.9% NaCl, LRS)
   - Step 2: free-water replacement with hypotonic fluids (0.45% NaCl,
     half-strength LRS) for maintenance and ongoing losses
   - Volume up to 4× the suspected intravascular deficit may be required

3. GAIN OF IMPERMEANT SOLUTE
   - Patient gained sodium, no proportional water loss
   - Examples: hypertonic saline administration, sodium phosphate enemas,
     salt toxicosis, paintball ingestion
   - Fluid: 5% dextrose IV
   - Caveat: risk of ECF expansion and pulmonary edema in patients with
     cardiac or renal compromise; may require loop diuretic

Water deficit formula (DiBartola, p. 61):
    Water deficit (L) = TBW × [(P_Na(present) / P_Na(previous)) − 1]

Where TBW = 0.6 × body weight (kg) for dogs and cats, and P_Na(previous)
is the patient's known previous normal sodium, or a clinician-chosen
reference value (DiBartola's worked example uses 145).

Correction rate ceiling (DiBartola, p. 61):
    "Correction of the serum sodium concentration at a rate of less than 10
    to 12 mEq/L per 24 hours minimizes the risk of neurologic complications."

Equivalent forms, both displayed in the result:
    10–12 mEq/L per 24 hours = 0.42–0.5 mEq/L per hour

DiBartola gives 48 hours as the standard correction window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

DEFAULT_PREVIOUS_NA = 145.0  # DiBartola's worked example
DEFAULT_REPLACEMENT_HOURS = 48.0  # DiBartola, p. 61
MAX_NA_REDUCTION_MEQ_PER_24HR = 12.0
MIN_NA_REDUCTION_MEQ_PER_24HR = 10.0  # the lower bound of DiBartola's range


class HyperNaMechanism(str, Enum):
    PURE_WATER_LOSS = "pure_water_loss"
    HYPOTONIC_LOSS = "hypotonic_loss"
    SOLUTE_GAIN = "solute_gain"


@dataclass(frozen=True)
class MechanismProfile:
    """Static info about each mechanism, examples and recommended fluids."""

    name: str
    description: str
    examples: tuple[str, ...]
    initial_fluid_strategy: str
    fluids: tuple[str, ...]
    caveats: tuple[str, ...]


MECHANISM_PROFILES: dict[HyperNaMechanism, MechanismProfile] = {
    HyperNaMechanism.PURE_WATER_LOSS: MechanismProfile(
        name="Pure water loss",
        description=(
            "Free water lost without proportional sodium loss. ECF volume is "
            "typically preserved or only mildly contracted."
        ),
        examples=(
            "Water deprivation (locked in garage, no access to water)",
            "Central diabetes insipidus",
            "Nephrogenic diabetes insipidus",
            "Hypodipsia / adipsia syndromes",
        ),
        initial_fluid_strategy=(
            "Replace the calculated water deficit with 5% dextrose in water. "
            "Glucose is metabolized leaving essentially free water; the "
            "infusion is technically slightly hypotonic to plasma "
            "(approximately 252 mOsm/L) but is treated as equivalent to "
            "free water for replacement purposes."
        ),
        fluids=("5% dextrose in water (D5W)",),
        caveats=(
            "Replace slowly. DiBartola specifies 48 hours.",
            "Brain idiogenic osmoles in chronic hypernatremia mean rapid correction risks cerebral edema.",
        ),
    ),
    HyperNaMechanism.HYPOTONIC_LOSS: MechanismProfile(
        name="Hypotonic loss",
        description=(
            "Water and sodium both lost, but water lost in greater proportion. "
            "ECF volume is contracted; signs of hypovolemia (tachycardia, weak "
            "pulses, prolonged CRT) may be present."
        ),
        examples=(
            "Osmotic diuresis (DKA, mannitol therapy)",
            "GI losses with ongoing dehydration",
            "Third-spacing (peritonitis, severe pancreatitis)",
            "Heat stroke with significant ongoing losses",
        ),
        initial_fluid_strategy=(
            "Two-stage approach. First restore ECF volume with isotonic "
            "crystalloid (0.9% NaCl or LRS), volume up to 4× the suspected "
            "intravascular deficit may be required because isotonic fluid "
            "distributes throughout the ECF compartment. Then transition to "
            "hypotonic fluids for free-water replacement, maintenance, and "
            "ongoing losses."
        ),
        fluids=(
            "Initial volume restoration: 0.9% NaCl, LRS",
            "Subsequent free-water replacement: 0.45% NaCl, half-strength LRS",
        ),
        caveats=(
            "Restore ECF volume before correcting sodium, hypotension is the more immediate threat.",
            "Subsequent sodium correction should still observe the 10–12 mEq/L per 24 hr ceiling.",
        ),
    ),
    HyperNaMechanism.SOLUTE_GAIN: MechanismProfile(
        name="Gain of impermeant solute",
        description=(
            "Sodium gained without proportional water loss. ECF volume may be "
            "expanded or normal. Signs of volume overload (pulmonary edema) "
            "may be present, especially with underlying cardiac disease."
        ),
        examples=(
            "Hypertonic saline administration (iatrogenic)",
            "Sodium bicarbonate during cardiac resuscitation",
            "Salt toxicosis (paintball ingestion, dough ingestion, seawater)",
            "Sodium phosphate enemas",
            "Hypertonic feeding tube formulas in compromised patients",
        ),
        initial_fluid_strategy=(
            "Administer 5% dextrose IV. The main disadvantage is further "
            "expansion of the ECF compartment in a patient already at risk "
            "of volume overload."
        ),
        fluids=("5% dextrose in water (D5W)",),
        caveats=(
            "In normal cardiac and renal function, ECF expansion drives "
            "diuresis and natriuresis with return to baseline.",
            "In cardiac disease or oliguria, this approach risks pulmonary "
            "edema. A loop diuretic (e.g., furosemide) may be needed to "
            "promote sodium excretion.",
            "Proceed slowly, same 48-hour correction window applies.",
        ),
    ),
}


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class HyperNaInputs:
    weight_value: float
    weight_unit: WeightUnit
    patient_na_meq_per_l: float
    previous_na_meq_per_l: float = DEFAULT_PREVIOUS_NA
    mechanism: HyperNaMechanism = HyperNaMechanism.PURE_WATER_LOSS
    replacement_hours: float = DEFAULT_REPLACEMENT_HOURS
    maintenance_ml_per_hr: float = 0.0


@dataclass
class HyperNaResult:
    weight_kg: float
    patient_na: float
    previous_na: float
    mechanism: HyperNaMechanism
    replacement_hours: float
    maintenance_ml_per_hr: float

    water_deficit_l: float
    water_deficit_ml: float

    deficit_replacement_ml_per_hr: float
    total_ml_per_hr: float

    # Predicted Na correction rate, in both forms
    predicted_rate_mEq_per_hr: float
    predicted_rate_mEq_per_24hr: float

    # The mechanism profile (examples, fluids, caveats)
    profile: MechanismProfile

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def compute_hypernatremia(inputs: HyperNaInputs) -> HyperNaResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = lb_to_kg(inputs.weight_value) if inputs.weight_unit == WeightUnit.LB else inputs.weight_value

    # --- Input validation -------------------------------------------------
    # Math on a non-positive weight, Na, or hour-count produces nonsense
    # — particularly the predicted Na correction rate, which a clinician
    # uses to decide whether to slow the infusion. Refuse to compute.
    errors: list[str] = []
    if weight_kg <= 0:
        errors.append("Weight must be greater than zero.")
    if inputs.patient_na_meq_per_l <= 0:
        errors.append("Patient serum sodium must be greater than zero.")
    if inputs.previous_na_meq_per_l <= 0:
        errors.append("Previous (reference) serum sodium must be greater than zero.")
    if inputs.replacement_hours <= 0:
        errors.append("Replacement timeframe must be greater than zero.")
    if errors:
        return HyperNaResult(
            weight_kg=weight_kg,
            patient_na=inputs.patient_na_meq_per_l,
            previous_na=inputs.previous_na_meq_per_l,
            mechanism=inputs.mechanism,
            replacement_hours=inputs.replacement_hours,
            maintenance_ml_per_hr=0.0,
            water_deficit_l=0.0,
            water_deficit_ml=0.0,
            deficit_replacement_ml_per_hr=0.0,
            total_ml_per_hr=0.0,
            predicted_rate_mEq_per_hr=0.0,
            predicted_rate_mEq_per_24hr=0.0,
            profile=MECHANISM_PROFILES[inputs.mechanism],
            warnings=errors,
            notes=[],
            sources=HYPERNATREMIA_SOURCES,
            valid=False,
        )

    # If patient Na isn't actually elevated above the reference, note it
    if (
        inputs.patient_na_meq_per_l > 0
        and inputs.previous_na_meq_per_l > 0
        and inputs.patient_na_meq_per_l <= inputs.previous_na_meq_per_l
    ):
        notes.append(
            f"Patient Na ({inputs.patient_na_meq_per_l} mEq/L) is not above the "
            f"reference value ({inputs.previous_na_meq_per_l} mEq/L). "
            f"No water deficit calculated."
        )

    # --- Water deficit (DiBartola, p. 61) ---------------------------------
    # DiBartola formula: Water deficit (L) = TBW × [(P_Na_current / P_Na_previous) − 1]
    # TBW = 0.6 × body weight (kg), standard assumption for dogs and cats
    # Note: some texts write "Wt" in this formula meaning TBW in litres, not body weight.
    # Using body weight directly (without the 0.6 factor) overstates the deficit by ~67%.
    TBW_FACTOR = 0.6  # fraction of body weight that is total body water (dogs and cats)
    if weight_kg > 0 and inputs.patient_na_meq_per_l > 0 and inputs.previous_na_meq_per_l > 0:
        ratio = inputs.patient_na_meq_per_l / inputs.previous_na_meq_per_l
        tbw_l = TBW_FACTOR * weight_kg
        water_deficit_l = tbw_l * (ratio - 1)
    else:
        water_deficit_l = 0.0

    # Negative deficits clamp to zero for display
    water_deficit_l_display = max(water_deficit_l, 0.0)
    water_deficit_ml = water_deficit_l_display * 1000

    # --- Replacement rates ------------------------------------------------
    if inputs.replacement_hours > 0:
        deficit_rate = water_deficit_ml / inputs.replacement_hours
    else:
        deficit_rate = 0.0
    total_rate = deficit_rate + max(inputs.maintenance_ml_per_hr, 0.0)

    # --- Predicted sodium correction rate ---------------------------------
    if inputs.replacement_hours > 0 and inputs.patient_na_meq_per_l > inputs.previous_na_meq_per_l:
        delta_na = inputs.patient_na_meq_per_l - inputs.previous_na_meq_per_l
        predicted_per_hr = delta_na / inputs.replacement_hours
        predicted_per_24hr = delta_na / (inputs.replacement_hours / 24)
    else:
        predicted_per_hr = 0.0
        predicted_per_24hr = 0.0

    # --- Safety: 10–12 mEq/L per 24 hr ceiling ----------------------------
    # DiBartola identifies a correction rate below 10–12 mEq/L per 24 hr as
    # the ceiling that minimizes neurologic risk. Any planned correction
    # exceeding 12 mEq/L/24hr exceeds the ceiling and warns. Between 10 and
    # 12 is in DiBartola's stated range, note but no caution.
    if predicted_per_24hr > MAX_NA_REDUCTION_MEQ_PER_24HR:
        excess_24hr = predicted_per_24hr - MAX_NA_REDUCTION_MEQ_PER_24HR
        warnings.append(
            f"⚠ CAUTION: Planned correction would drop serum Na by "
            f"{predicted_per_24hr:.1f} mEq/L per 24 hr, which is {excess_24hr:.1f} above "
            f"the published ceiling of 12 mEq/L per 24 hr ({MAX_NA_REDUCTION_MEQ_PER_24HR / 24:.2f} "
            f"mEq/L/hr). Rapid correction risks cerebral edema from idiogenic "
            f"osmoles. Consider extending the replacement timeframe."
        )
    elif MIN_NA_REDUCTION_MEQ_PER_24HR <= predicted_per_24hr <= MAX_NA_REDUCTION_MEQ_PER_24HR:
        notes.append(
            f"Predicted correction rate ({predicted_per_24hr:.1f} mEq/L per 24 hr) "
            f"is within the published range of 10–12 mEq/L per 24 hr. "
            f"Acceptable, but at the upper end; recheck sodium serially."
        )

    # --- Default-value notes ----------------------------------------------
    if inputs.previous_na_meq_per_l == DEFAULT_PREVIOUS_NA and not warnings:
        notes.append(
            f"Using default reference Na of {DEFAULT_PREVIOUS_NA:.0f} mEq/L "
            f"(from a published worked example). If you have the patient's "
            f"previous documented normal sodium, override the reference "
            f"value above."
        )

    profile = MECHANISM_PROFILES[inputs.mechanism]

    return HyperNaResult(
        weight_kg=weight_kg,
        patient_na=inputs.patient_na_meq_per_l,
        previous_na=inputs.previous_na_meq_per_l,
        mechanism=inputs.mechanism,
        replacement_hours=inputs.replacement_hours,
        maintenance_ml_per_hr=inputs.maintenance_ml_per_hr,
        water_deficit_l=round(water_deficit_l_display, 3),
        water_deficit_ml=round(water_deficit_ml, 1),
        deficit_replacement_ml_per_hr=round(deficit_rate, 2),
        total_ml_per_hr=round(total_rate, 2),
        predicted_rate_mEq_per_hr=round(predicted_per_hr, 3),
        predicted_rate_mEq_per_24hr=round(predicted_per_24hr, 2),
        profile=profile,
        warnings=warnings,
        notes=notes,
        sources=HYPERNATREMIA_SOURCES,
    )


HYPERNATREMIA_SOURCES = (
    Source(
        citation=(
            "DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in Small "
            "Animal Practice, 4th ed. Elsevier, 2012. Chapter 3 (Disorders of "
            "Sodium and Water). Free water deficit formula (TBW × "
            "[Na_curr/Na_target − 1]); 10–12 mEq/L per 24 hr correction ceiling "
            "for chronic hypernatremia."
        )
    ),
    Source(
        citation=(
            "Adrogue HJ, Madias NE. Hypernatremia. N Engl J Med "
            "2000;342:1493–1499. (Original formulation of the Adrogue-Madias water "
            "deficit equation.)"
        )
    ),
    Source(
        citation=(
            "Bissett SA, Lamb CR, Brockman DJ. Hypodipsic hypernatremia in a dog. "
            "J Am Anim Hosp Assoc 2001;37:526–529."
        )
    ),
)

HYPERNA_CATALOG_ENTRY = {
    "slug": "hypernatremia",
    "display_name": "Hypernatremia water deficit",
    "short_name": "HyperNa",
    "category": "Electrolytes & Fluids",
    "mechanism_summary": (
        "Calculates free water deficit and replacement rate per DiBartola, "
        "Ch. 3. Mechanism selector (pure water loss, hypotonic loss, solute "
        "gain) drives fluid recommendations and clinical caveats."
    ),
    "indications_summary": (
        "Free-water deficit and correction plan for hypernatremia in "
        "dogs and cats. Takes serum Na and body weight, classifies "
        "the mechanism (pure water loss, hypotonic loss, or rare "
        "sodium gain), and returns a correction rate that keeps Na "
        "decline under 10–12 mEq/L per 24 hr. Slow correction matters: "
        "faster decline risks cerebral edema."
    ),
}
