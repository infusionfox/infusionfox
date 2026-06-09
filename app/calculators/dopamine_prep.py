"""
Dopamine preparation worksheet. Plumb's 6×kg method.

Source: Plumb's Veterinary Drugs (current edition; user references
Plumb's monograph for dopamine).

The 6×kg method (Plumb's, Preparation/Stability section):
    Multiply patient weight (kg) × 6 = mg of dopamine to add to a 100 mL
    bag of compatible IV fluid. When this solution is infused at 1 mL/HOUR,
    the patient receives 1 µg/kg/MINUTE. Therefore:

        pump rate (mL/hr) = dose (µg/kg/min)

Worked example from Plumb's:
    10 kg patient: 6 × 10 = 60 mg of dopamine.
    From 40 mg/mL stock: 60 mg / 40 mg/mL = 1.5 mL of stock.
    Remove 1.5 mL from a 100 mL bag, then add 1.5 mL of stock.
    To dose at 5 µg/kg/min: run pump at 5 mL/hr.

Math derivation:
    A 100 mL bag with (6 × BW) mg has concentration:
        (6 × BW × 1000) / 100 = 60 × BW µg/mL

    For dose D µg/kg/min:
        Total drug needed: BW × D µg/min × 60 = 60 × BW × D µg/hr
        mL/hr = (60 × BW × D) / (60 × BW) = D mL/hr  ✓

Plumb's also caps the final dopamine concentration at ≤3,200 µg/mL
(3.2 mg/mL). InfusionFox enforces this as a constraint check.

Dose ranges (Plumb's monograph, Dosages section):
    Dogs: 3–20 µg/kg/min IV CRI for hypotension/inhalant anesthesia.
        Severe shock: start 2.5–5, titrate +2.5–5 every ~30 min.
    Cats: 5–20 µg/kg/min IV CRI for both indications.
        Same titration as dogs.

Cat-specific concern: Lumb & Jones 6th ed Ch. 21 cites a study (Wiese
et al) where cats with hypertrophic cardiomyopathy developed PVCs at
2.5–10 µg/kg/min. Continuous ECG monitoring strongly recommended in
cats; concern increases above 10 µg/kg/min.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Plumb's specifies a 40 mg/mL stock vial concentration.
DOPAMINE_STOCK_MG_PER_ML = 40.0

# Plumb's preparation method uses a 100 mL bag.
DOPAMINE_BAG_VOLUME_ML = 100.0

# Plumb's-published upper limit for compounded dopamine concentration.
DOPAMINE_MAX_FINAL_CONCENTRATION_UG_PER_ML = 3200.0


class DopamineSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class DopaminePrepInputs:
    species: DopamineSpecies
    weight_value: float
    weight_unit: WeightUnit
    target_dose_ug_per_kg_per_min: float


@dataclass
class DopaminePrepResult:
    species: DopamineSpecies
    weight_kg: float
    target_dose: float

    # Preparation recipe
    mg_dopamine_to_add: float  # 6 × BW
    ml_stock_to_draw: float  # mg ÷ 40 mg/mL
    ml_to_remove_from_bag: float  # = ml_stock_to_draw
    bag_volume_ml: float  # 100 mL
    final_concentration_ug_per_ml: float  # 60 × BW

    # Running rate
    pump_rate_ml_per_hr: float  # = target_dose

    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def compute_dopamine_preparation(inputs: DopaminePrepInputs) -> DopaminePrepResult:
    notes: list[str] = []
    warnings: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)

    # Validate. Math on a non-positive weight or target dose produces
    # a meaningless preparation recipe; refuse to compute.
    errors: list[str] = []
    if weight_kg <= 0:
        errors.append("Weight must be greater than zero.")
    if inputs.target_dose_ug_per_kg_per_min <= 0:
        errors.append("Target dose must be greater than zero.")
    if errors:
        return DopaminePrepResult(
            species=inputs.species,
            weight_kg=weight_kg,
            target_dose=inputs.target_dose_ug_per_kg_per_min,
            mg_dopamine_to_add=0.0,
            ml_stock_to_draw=0.0,
            ml_to_remove_from_bag=0.0,
            bag_volume_ml=DOPAMINE_BAG_VOLUME_ML,
            final_concentration_ug_per_ml=0.0,
            pump_rate_ml_per_hr=0.0,
            notes=[],
            warnings=errors,
            sources=DOPAMINE_PREP_SOURCES,
            valid=False,
        )

    # Plumb's 6×kg recipe
    mg_to_add = 6.0 * weight_kg
    ml_stock = mg_to_add / DOPAMINE_STOCK_MG_PER_ML
    final_conc_ug_per_ml = 60.0 * weight_kg  # = mg_to_add * 1000 / 100

    # Cap check. Plumb's says final concentration must be ≤ 3,200 µg/mL
    if final_conc_ug_per_ml > DOPAMINE_MAX_FINAL_CONCENTRATION_UG_PER_ML:
        warnings.append(
            f"⚠ Resulting concentration ({final_conc_ug_per_ml:.0f} µg/mL) "
            f"exceeds the {DOPAMINE_MAX_FINAL_CONCENTRATION_UG_PER_ML:.0f} µg/mL "
            f"limit Plumb's specifies for compounded dopamine. For patients "
            f"this large (>{DOPAMINE_MAX_FINAL_CONCENTRATION_UG_PER_ML / 60:.0f} kg), "
            f"use a lower mg-per-bag ratio or a larger bag volume."
        )

    # Pump rate equals dose by construction
    pump_rate = inputs.target_dose_ug_per_kg_per_min

    # Species-based caution warnings
    if inputs.species == DopamineSpecies.DOG:
        if inputs.target_dose_ug_per_kg_per_min < 3:
            warnings.append(
                f"Dose {inputs.target_dose_ug_per_kg_per_min} µg/kg/min is below "
                f"the typical canine range (3–20). Per Plumb's, low-dose dopamine "
                f"is unlikely to benefit dogs with oliguric AKI."
            )
        elif inputs.target_dose_ug_per_kg_per_min > 20:
            warnings.append(
                f"⚠ Dose {inputs.target_dose_ug_per_kg_per_min} µg/kg/min exceeds "
                f"the typical canine range (3–20 per Plumb's). Reassess indication "
                f"and consider switching to norepinephrine."
            )
    elif inputs.species == DopamineSpecies.CAT:
        # Persistent cat warning, surfaces at any dose. Norepinephrine is
        # preferred in cats; PVC risk is documented across the entire feline
        # therapeutic range (2.5–10 µg/kg/min in HCM cats).
        warnings.append(
            "Norepinephrine is preferred over dopamine in cats. PVC risk "
            "is documented across the entire feline dopamine range "
            "(2.5–10 µg/kg/min in HCM cats; ≈15% of cats have undiagnosed "
            "HCM). Reserve dopamine in cats for specific indications "
            "(eg, bradycardia-driven hypotension) where its chronotropic "
            "effect is wanted and norepinephrine is not a viable option. "
            "Continuous ECG monitoring is essential at any rate."
        )
        if inputs.target_dose_ug_per_kg_per_min > 10:
            warnings.append(
                "⚠ Cat dose above 10 µg/kg/min: PVC and arrhythmia risk "
                "rises further above the already-documented 2.5–10 range. "
                "Reduce promptly if PVCs occur; switching to norepinephrine "
                "is strongly preferred."
            )
        if inputs.target_dose_ug_per_kg_per_min < 5:
            warnings.append(
                f"Dose {inputs.target_dose_ug_per_kg_per_min} µg/kg/min is below "
                f"the typical feline range (5–20)."
            )
        elif inputs.target_dose_ug_per_kg_per_min > 20:
            warnings.append(
                f"⚠ Dose {inputs.target_dose_ug_per_kg_per_min} µg/kg/min exceeds "
                f"the typical feline range (5–20)."
            )

    # General notes
    notes.append(
        "Volume depletion should be corrected before dopamine "
        "administration. Vasopressors are not a substitute for adequate "
        "fluid replacement."
    )
    notes.append(
        "Use a stepwise dose reduction prior to discontinuation to reduce the risk of rebound hypotension."
    )
    notes.append(
        "Administer into a large vein with a dedicated IV line. Extravasation "
        "can cause tissue necrosis and sloughing; check the site frequently."
    )
    notes.append(
        "Solution is stable for 24 hours at 20–25°C after dilution. Do not "
        "administer if darker than slightly yellow or otherwise discolored."
    )
    notes.append(
        "Do NOT confuse DOPamine with DOBUTamine or DOXapram (Doprap). Plumb's "
        "classifies dopamine as a high-alert medication."
    )

    return DopaminePrepResult(
        species=inputs.species,
        weight_kg=round(weight_kg, 2),
        target_dose=inputs.target_dose_ug_per_kg_per_min,
        mg_dopamine_to_add=round(mg_to_add, 1),
        ml_stock_to_draw=round(ml_stock, 2),
        ml_to_remove_from_bag=round(ml_stock, 2),
        bag_volume_ml=DOPAMINE_BAG_VOLUME_ML,
        final_concentration_ug_per_ml=round(final_conc_ug_per_ml, 0),
        pump_rate_ml_per_hr=round(pump_rate, 2),
        notes=notes,
        warnings=warnings,
        sources=DOPAMINE_PREP_SOURCES,
    )


DOPAMINE_PREP_CATALOG_ENTRY = {
    "slug": "dopamine",
    "display_name": "Dopamine",
    "short_name": "Dopa",
    "category": "Vasopressors & Inotropes",
    "kind": "dopamine_preparation",
    "mechanism_summary": (
        "Endogenous catecholamine. Direct action on peripheral dopamine receptors "
        "and direct + indirect (via NE release) action on α- and β-adrenergic "
        "receptors. In dogs and cats, adrenergic activity is dose-dependent: "
        "5–10 µg/kg/min predominantly β₁ (positive inotropy, increased contractility, "
        "HR, cardiac output); 10–15 µg/kg/min has both α₁ and β₁ effects with α₁ "
        "(vasoconstriction, increased SVR/PVR) progressively dominating. Half-life "
        "in dogs is ~11 minutes; metabolized by MAO and COMT in liver, kidney, "
        "and plasma."
    ),
    "indications_summary": (
        "Patient-specific bag-prep worksheet for a 100 mL dopamine "
        "drip. The 6×kg shortcut adds 6 mg/kg of stock to a 100 mL "
        "bag, yielding a concentration where the pump rate in mL/hr "
        "equals the dose in µg/kg/min. No further math at the "
        "bedside. Used for inotropic and vasopressor support in "
        "hypotension and shock once fluid status is adequate."
    ),
}


DOPAMINE_PREP_SOURCES = (
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, dopamine monograph. CRI dosing "
            "5–20 µg/kg/min in dogs and cats; cardiovascular and arrhythmogenic "
            "effects; recommended preparation methods."
        )
    ),
    Source(
        citation=(
            "Silverstein DC, Beer KS. Vasopressors and inotropes. In: Silverstein "
            "DC, Hopper K, eds. Small Animal Critical Care Medicine, 3rd ed. "
            "Elsevier, 2023. (6×kg method for dopamine bag preparation.)"
        )
    ),
)
