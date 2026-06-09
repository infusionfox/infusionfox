"""
Calcium gluconate for hyperkalemia (membrane stabilization) calculator.

Sources:
    Cooper ES. Urethral Obstruction. In: Silverstein DC, Hopper K, eds.
    Small Animal Critical Care Medicine. 3rd ed. Elsevier; 2023.
    Chapter 122. (Cites 0.5–1.5 mL/kg of 10% calcium gluconate IV slowly
    over 10–20 min, monitoring ECG.)
    DiBartola SP. Disorders of Potassium. In: Fluid, Electrolyte, and
    Acid-Base Disorders in Small Animal Practice. 4th ed. Elsevier;
    2012. Chapter 5.

Mechanism:
    Calcium does NOT lower potassium. Calcium STABILIZES the cardiac
    cell membrane by raising the threshold potential, restoring the
    gradient between threshold and resting potential that hyperkalemia
    has narrowed. Effect onset is within 1–3 minutes; duration is
    30–60 minutes. The drug "buys time" while insulin/dextrose, fluid
    therapy, and definitive treatment of the underlying cause take
    effect.

Critical practice points (encoded in warnings):
    - Calcium gluconate (NOT calcium chloride), gluconate is the
      standard IV preparation for hyperkalemia. Chloride is ≈3× more
      potent on a mL basis, more cardiotoxic at the same volume, and
      more tissue-toxic on extravasation.
    - Slow IV administration over 10–20 min with continuous ECG.
      STOP if bradycardia worsens or PR interval prolongs further.
    - Never IM or SC, severe tissue necrosis.
    - Do NOT mix in calcium-incompatible lines (sodium bicarbonate
      will precipitate as calcium carbonate; KPhos co-infusion can
      precipitate as calcium phosphate).
    - Effect is short-lived (30–60 min). Must be followed by
      K-lowering therapy (insulin/dextrose, fluids, address the
      underlying cause); calcium alone will not save the patient.

Math:
    10% calcium gluconate = 100 mg/mL of the salt
                         = 9.3 mg/mL elemental Ca
                         = 0.465 mEq/mL elemental Ca
    Volume_mL = dose_mL_per_kg × weight_kg
    Rate_mL_per_min = Volume_mL / duration_min
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Stock concentration: 10% calcium gluconate
CA_GLUCONATE_MG_PER_ML = 100.0  # of the gluconate salt
CA_GLUCONATE_ELEMENTAL_CA_MG_PER_ML = 9.3
CA_GLUCONATE_MEQ_PER_ML = 0.465  # elemental Ca (Ca²⁺)

# Dose range per Silverstein Ch. 122 / DiBartola Ch. 5
DOSE_MIN_ML_PER_KG = 0.5
DOSE_DEFAULT_ML_PER_KG = 1.0
DOSE_MAX_ML_PER_KG = 1.5

# Infusion duration
DURATION_MIN_MIN = 10
DURATION_DEFAULT_MIN = 15
DURATION_MAX_MIN = 20

# Onset / duration of effect
ONSET_MIN_LOW = 1
ONSET_MIN_HIGH = 3
EFFECT_DURATION_MIN_LOW = 30
EFFECT_DURATION_MIN_HIGH = 60


class CaGluconateSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class CaGluconateInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: CaGluconateSpecies
    dose_ml_per_kg: float = DOSE_DEFAULT_ML_PER_KG
    duration_min: float = DURATION_DEFAULT_MIN


@dataclass
class CaGluconateResult:
    weight_kg: float
    species: CaGluconateSpecies

    dose_ml_per_kg: float
    duration_min: float

    # Math
    total_volume_ml: float
    total_dose_mg: float  # of calcium gluconate salt
    elemental_ca_mg: float
    elemental_ca_meq: float
    infusion_rate_ml_per_min: float

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale. False when weight is
    # missing or non-positive. The template suppresses numeric output
    # so the clinician never sees a 0.001-mL placeholder dose alongside
    # a "weight must be > 0" warning.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def compute_ca_gluconate(inputs: CaGluconateInputs) -> CaGluconateResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        # Refuse to compute. The previous code substituted weight_kg=0.001,
        # which produced a plausible-looking but wildly wrong output if the
        # clinician missed the warning.
        return CaGluconateResult(
            weight_kg=weight_kg,
            species=inputs.species,
            dose_ml_per_kg=inputs.dose_ml_per_kg,
            duration_min=inputs.duration_min,
            total_volume_ml=0.0,
            total_dose_mg=0.0,
            elemental_ca_mg=0.0,
            elemental_ca_meq=0.0,
            infusion_rate_ml_per_min=0.0,
            warnings=["Weight must be greater than zero."],
            notes=[],
            sources=CA_GLUCONATE_SOURCES,
            valid=False,
        )

    # Clamp dose
    dose = inputs.dose_ml_per_kg
    if dose < DOSE_MIN_ML_PER_KG:
        warnings.append(
            f"Dose {dose:g} mL/kg is below the published range. Using {DOSE_MIN_ML_PER_KG:g} mL/kg minimum."
        )
        dose = DOSE_MIN_ML_PER_KG
    elif dose > DOSE_MAX_ML_PER_KG:
        warnings.append(
            f"Dose {dose:g} mL/kg is above the published range. Using {DOSE_MAX_ML_PER_KG:g} mL/kg maximum."
        )
        dose = DOSE_MAX_ML_PER_KG

    # Clamp duration
    duration = inputs.duration_min
    if duration < DURATION_MIN_MIN:
        warnings.append(
            f"Infusion duration {duration:g} min is below the safe minimum "
            f"of {DURATION_MIN_MIN} min. Faster delivery markedly increases "
            f"the risk of bradyarrhythmias and hypotension. Using "
            f"{DURATION_MIN_MIN} min."
        )
        duration = DURATION_MIN_MIN
    elif duration > DURATION_MAX_MIN:
        warnings.append(
            f"Infusion duration {duration:g} min is above the published range. Using {DURATION_MAX_MIN} min."
        )
        duration = DURATION_MAX_MIN

    # Math
    total_volume = dose * weight_kg
    total_dose_mg = total_volume * CA_GLUCONATE_MG_PER_ML
    elem_ca_mg = total_volume * CA_GLUCONATE_ELEMENTAL_CA_MG_PER_ML
    elem_ca_meq = total_volume * CA_GLUCONATE_MEQ_PER_ML
    rate_ml_min = total_volume / duration if duration > 0 else 0

    # Persistent warnings (clinical safety)
    warnings.append(
        "Use 10% CALCIUM GLUCONATE, not calcium chloride. Calcium "
        "chloride is ≈3× more potent per mL, more cardiotoxic, and "
        "more tissue-toxic on extravasation. The IV preparation for "
        "hyperkalemia is calcium GLUCONATE. Read the vial."
    )
    warnings.append(
        "Continuous ECG required throughout infusion. Stop the "
        "infusion immediately if bradycardia worsens, PR interval "
        "lengthens further, or QRS widens. Resume at half the rate "
        "after rhythm stabilizes. Hypercalcemia from too-rapid IV "
        "calcium can itself cause arrhythmias and arrest."
    )
    warnings.append(
        "Never give IM or SC; severe tissue necrosis. If extravasation "
        "occurs during IV administration, stop immediately, attempt to "
        "aspirate from the catheter, then remove the catheter. Warm "
        "compresses to the area. Hyaluronidase infiltration has been "
        "described for severe extravasation."
    )
    warnings.append(
        "Calcium stabilizes the membrane; it does NOT lower serum K. "
        "Effect onset 1–3 min; duration only 30–60 min. This is a "
        "bridging therapy that buys time for K-lowering treatment "
        "(insulin/dextrose, fluid therapy) and definitive correction "
        "of the underlying cause (deobstruction, mineralocorticoid "
        "replacement, dialysis). Do NOT rely on calcium alone."
    )
    warnings.append(
        "Line compatibility: do NOT co-infuse with sodium bicarbonate "
        "(precipitates as calcium carbonate) or potassium phosphate "
        "(precipitates as calcium phosphate). Flush thoroughly between "
        "drugs. A separate IV line for any calcium-incompatible "
        "concurrent therapy is the safest practice."
    )

    # Notes
    notes.append(
        f"Math: {dose:g} mL/kg × {weight_kg:.2f} kg = "
        f"{total_volume:.2f} mL of 10% calcium gluconate "
        f"(= {total_dose_mg:.0f} mg salt = {elem_ca_mg:.1f} mg "
        f"elemental Ca = {elem_ca_meq:.2f} mEq Ca²⁺). "
        f"Delivered over {duration:g} min = "
        f"{rate_ml_min:.2f} mL/min."
    )
    notes.append(
        f"Onset {ONSET_MIN_LOW}–{ONSET_MIN_HIGH} minutes; effect lasts "
        f"only {EFFECT_DURATION_MIN_LOW}–{EFFECT_DURATION_MIN_HIGH} "
        f"minutes. Repeat doses can be given if bradyarrhythmias "
        f"recur, but the underlying K problem must be addressed in "
        f"parallel, calcium alone cannot save the patient."
    )
    notes.append(
        "Indication: emergency membrane stabilization in life-"
        "threatening hyperkalemia (typically K > 7 mEq/L, or any K "
        "with concerning ECG changes, peaked T waves, prolonged "
        "PR interval, loss of P waves, widened QRS, sine-wave "
        "rhythm). Common scenarios: feline urethral obstruction, "
        "hypoadrenocorticism (Addisonian crisis), oliguric AKI, "
        "tumor lysis syndrome, severe rhabdomyolysis."
    )

    return CaGluconateResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        dose_ml_per_kg=dose,
        duration_min=duration,
        total_volume_ml=round(total_volume, 2),
        total_dose_mg=round(total_dose_mg, 0),
        elemental_ca_mg=round(elem_ca_mg, 1),
        elemental_ca_meq=round(elem_ca_meq, 2),
        infusion_rate_ml_per_min=round(rate_ml_min, 2),
        warnings=warnings,
        notes=notes,
        sources=CA_GLUCONATE_SOURCES,
    )


CA_GLUCONATE_SOURCES = (
    Source(
        citation=(
            "DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in Small "
            "Animal Practice, 4th ed. Elsevier, 2012. Chapter 5 (potassium / "
            "hyperkalemia management) and Chapter 6 (calcium and phosphate). "
            "Membrane stabilization indication and dosing for "
            "hyperkalemia-associated cardiotoxicity."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, calcium gluconate monograph. 10% "
            "solution dosing (0.5–1.5 mL/kg slow IV with continuous ECG "
            "monitoring); contraindications; extravasation cautions."
        )
    ),
)

CA_GLUCONATE_CATALOG_ENTRY = {
    "slug": "ca-gluconate-hyperK",
    "display_name": "Calcium gluconate (membrane stabilization)",
    "short_name": "Ca gluconate",
    "category": "Electrolytes & Fluids",
    "kind": "dose_calculator",
    "mechanism_summary": (
        "Emergency membrane-stabilization therapy for life-threatening "
        "hyperkalemia. 10% calcium gluconate 0.5–1.5 mL/kg IV slowly "
        "over 10–20 min with continuous ECG. Onset 1–3 min; duration "
        "only 30–60 min. Calcium does NOT lower K, it raises the "
        "cardiac cell threshold potential, restoring the gradient that "
        "hyperkalemia has narrowed. A bridging therapy that buys time "
        "for K-lowering treatment (insulin/dextrose, fluid therapy) "
        "and definitive correction of the underlying cause."
    ),
    "indications_summary": (
        "Emergency cardiac membrane stabilization in life-threatening "
        "hyperkalemia in dogs and cats. Antagonizes the membrane "
        "effects of hyperkalemia within 1–3 min, buying 30–60 minutes "
        "for K-shifting and K-lowering therapy to take effect. Does "
        "not itself lower serum K; pair with definitive treatment of "
        "the underlying cause."
    ),
}
