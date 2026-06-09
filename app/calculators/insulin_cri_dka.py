"""
Insulin CRI for DKA management. Hoehne / Silverstein & Hopper Ch. 73.

Source: Hoehne SN. Diabetic Ketoacidosis. In: Silverstein DC, Hopper K, eds.
Small Animal Critical Care Medicine. 3rd ed. St. Louis, MO: Elsevier;
2023. Chapter 73 (pp. 432–435), with Table 73.1 reproduced as the
sliding-scale lookup.

Protocol:
    1. Add a per-kg loading dose of regular crystalline insulin to a
       250 mL bag of 0.9% NaCl. The chapter gives 2.2 U/kg as the
       canine dose; for cats, 1.1 U/kg is "occasionally recommended"
       as a conservative option, but a 2024 study shows 2.2 U/kg/day
       in cats is safe when the sliding-scale-driven rate adjustments
       are followed.

    2. PRIME THE TUBING and discard the first 50 mL of the prepared
       solution before connecting to the patient. Regular insulin binds
       to plastic IV tubing, discarding 50 mL saturates the binding
       sites so the delivered dose matches the calculated dose.

    3. Run at the rate dictated by Table 73.1, using the fluid composition
       (0.9% NaCl alone or with 2.5% / 5% dextrose) appropriate for the
       current blood glucose. Re-check BG every 2 hours and adjust.

Table 73.1 (reproduced):
    BG > 250 mg/dL          → 0.9% NaCl alone           → 10 mL/hr
    BG 200–250 mg/dL        → 0.9% NaCl + 2.5% dextrose →  7 mL/hr
    BG 150–199 mg/dL        → 0.9% NaCl + 2.5% dextrose →  5 mL/hr
    BG 100–149 mg/dL        → 0.9% NaCl + 5% dextrose   →  5 mL/hr
    BG < 100 mg/dL          → 0.9% NaCl + 5% dextrose   → STOP insulin

Goal: lower BG to < 250 mg/dL by no more than 50–75 mg/dL/hr. If BG is
dropping too fast or too slowly, adjust the rate (or recheck whether
the fluid composition needs to step.

Cat dose option:
    The chapter notes 1.1 U/kg is "occasionally recommended" for cats.
    A recent study using 2.2 U/kg/day in cats with a sliding scale
    showed no increase in adverse neurological or biochemical events.
    This calculator defaults to 2.2 U/kg/day for both species and
    offers 1.1 U/kg/day as a conservative cat option.

Important: this is regular crystalline insulin. NOT insulin lispro,
aspart, or glargine. Lispro and aspart have been studied as
alternatives but are not yet standard of care; glargine is part of
hybrid SQ + IM protocols (also not standard in DKA). This calculator
assumes regular crystalline insulin only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

INSULIN_CRI_BAG_VOLUME_ML = 250.0
INSULIN_CRI_PRIME_DISCARD_ML = 50.0
INSULIN_CRI_DEFAULT_LOADING_U_PER_KG = 2.2
INSULIN_CRI_CAT_CONSERVATIVE_U_PER_KG = 1.1


class InsulinCriSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


class InsulinCriCatDoseOption(str, Enum):
    """Which loading dose to use for cats. Default is the modern 2.2."""

    STANDARD_2_2 = "standard"  # 2.2 U/kg, default
    CONSERVATIVE_1_1 = "conservative"  # 1.1 U/kg, older recommendation


@dataclass
class InsulinCriTier:
    """One row of Table 73.1."""

    label: str  # e.g. "BG > 250 mg/dL"
    bg_low: int | None  # inclusive lower bound; None for open-ended low
    bg_high: int | None  # exclusive upper bound; None for open-ended high
    fluid_composition: str
    pump_rate_ml_per_hr: float | None  # None means STOP insulin
    note: str | None = None


# Table 73.1, verbatim from Hoehne / Silverstein 3rd ed.
INSULIN_CRI_TIERS: list[InsulinCriTier] = [
    InsulinCriTier(
        label="BG > 250 mg/dL",
        bg_low=250,
        bg_high=None,
        fluid_composition="0.9% NaCl",
        pump_rate_ml_per_hr=10.0,
        note=("Initial DKA range. Goal: lower BG by no more than 50–75 mg/dL/hr toward < 250 mg/dL."),
    ),
    InsulinCriTier(
        label="BG 200–250 mg/dL",
        bg_low=200,
        bg_high=251,
        fluid_composition="0.9% NaCl + 2.5% dextrose",
        pump_rate_ml_per_hr=7.0,
        note=(
            "BG approaching target. Add 2.5% dextrose to the fluid line "
            "to allow continued insulin without driving BG dangerously low."
        ),
    ),
    InsulinCriTier(
        label="BG 150–199 mg/dL",
        bg_low=150,
        bg_high=200,
        fluid_composition="0.9% NaCl + 2.5% dextrose",
        pump_rate_ml_per_hr=5.0,
    ),
    InsulinCriTier(
        label="BG 100–149 mg/dL",
        bg_low=100,
        bg_high=150,
        fluid_composition="0.9% NaCl + 5% dextrose",
        pump_rate_ml_per_hr=5.0,
        note=(
            "Step dextrose up to 5% to maintain BG above 100 mg/dL while insulin continues to clear ketones."
        ),
    ),
    InsulinCriTier(
        label="BG < 100 mg/dL",
        bg_low=None,
        bg_high=100,
        fluid_composition="0.9% NaCl + 5% dextrose",
        pump_rate_ml_per_hr=None,  # STOP
        note=(
            "STOP insulin. Continue 5% dextrose to recover BG. "
            "Re-check BG, then resume insulin at the appropriate tier "
            "once BG > 100 mg/dL."
        ),
    ),
]


@dataclass
class InsulinCriInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: InsulinCriSpecies
    blood_glucose_mg_per_dl: float
    cat_dose_option: InsulinCriCatDoseOption = InsulinCriCatDoseOption.STANDARD_2_2


@dataclass
class InsulinCriResult:
    weight_kg: float
    blood_glucose_mg_per_dl: float
    species: InsulinCriSpecies
    loading_units_per_kg: float
    total_units_added_to_bag: float
    bag_volume_ml: float
    bag_concentration_units_per_ml: float  # AFTER discarding 50 mL prime
    units_per_ml_in_bag_pre_prime: float
    prime_discard_ml: float
    matched_tier: InsulinCriTier
    fluid_composition: str
    pump_rate_ml_per_hr: float | None  # None means STOP
    units_per_kg_per_hr_delivered: float | None
    insulin_stopped: bool
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale. False when weight or
    # blood glucose is missing or non-positive. The template suppresses
    # numeric output (bag prep, pump rate) when invalid.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _resolve_loading_dose(species: InsulinCriSpecies, cat_option: InsulinCriCatDoseOption) -> float:
    if species == InsulinCriSpecies.CAT and cat_option == InsulinCriCatDoseOption.CONSERVATIVE_1_1:
        return INSULIN_CRI_CAT_CONSERVATIVE_U_PER_KG
    return INSULIN_CRI_DEFAULT_LOADING_U_PER_KG


def _match_tier(bg: float) -> InsulinCriTier:
    """Find the Table 73.1 row for the entered BG."""
    for tier in INSULIN_CRI_TIERS:
        low_ok = tier.bg_low is None or bg >= tier.bg_low
        high_ok = tier.bg_high is None or bg < tier.bg_high
        if low_ok and high_ok:
            return tier
    # Fallback (shouldn't happen, tiers are exhaustive)
    return INSULIN_CRI_TIERS[-1]


def compute_insulin_cri(inputs: InsulinCriInputs) -> InsulinCriResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)

    # Validate first. Math on a non-positive weight or BG would produce
    # a meaningless or negative bag concentration and pump rate. Refuse
    # to compute and present the validation error to the clinician.
    errors: list[str] = []
    if weight_kg <= 0:
        errors.append("Weight must be greater than zero.")
    if inputs.blood_glucose_mg_per_dl <= 0:
        errors.append("Blood glucose must be greater than zero.")
    if errors:
        # Pick the highest-BG tier as a placeholder so the dataclass
        # has a non-None matched_tier (the type allows None on
        # pump_rate, but matched_tier itself is required and templates
        # may dereference its label/composition under the valid gate;
        # the gate suppresses display so the placeholder is never shown).
        placeholder_tier = INSULIN_CRI_TIERS[0]
        return InsulinCriResult(
            weight_kg=round(weight_kg, 2),
            blood_glucose_mg_per_dl=round(inputs.blood_glucose_mg_per_dl, 1),
            species=inputs.species,
            loading_units_per_kg=0.0,
            total_units_added_to_bag=0.0,
            bag_volume_ml=INSULIN_CRI_BAG_VOLUME_ML,
            bag_concentration_units_per_ml=0.0,
            units_per_ml_in_bag_pre_prime=0.0,
            prime_discard_ml=INSULIN_CRI_PRIME_DISCARD_ML,
            matched_tier=placeholder_tier,
            fluid_composition="",
            pump_rate_ml_per_hr=None,
            units_per_kg_per_hr_delivered=None,
            insulin_stopped=False,
            warnings=errors,
            notes=[],
            sources=INSULIN_CRI_DKA_SOURCES,
            valid=False,
        )

    loading_u_per_kg = _resolve_loading_dose(inputs.species, inputs.cat_dose_option)
    total_units = weight_kg * loading_u_per_kg

    # Concentration before priming (theoretical):
    units_per_ml_pre = total_units / INSULIN_CRI_BAG_VOLUME_ML
    # After discarding 50 mL prime, the deliverable volume is reduced but
    # the concentration in the remaining solution is the SAME (it's
    # homogeneous). The prime-discard step is about saturating the
    # line's plastic, NOT changing the bag concentration.
    units_per_ml_in_bag = units_per_ml_pre

    tier = _match_tier(inputs.blood_glucose_mg_per_dl)
    pump_rate = tier.pump_rate_ml_per_hr
    insulin_stopped = pump_rate is None

    # Delivered dose in U/kg/hr
    delivered = None
    if pump_rate is not None and weight_kg > 0:
        delivered = (units_per_ml_in_bag * pump_rate) / weight_kg

    # Persistent warnings
    warnings.append(
        "Use regular crystalline insulin only for this protocol. NOT "
        "insulin lispro, aspart, glargine, NPH, detemir, or any "
        "long-acting form. Lispro and aspart have been investigated as "
        "alternatives but are not yet standard of care for veterinary DKA; "
        "glargine is used in hybrid SQ + IM protocols, not as an IV CRI."
    )
    warnings.append(
        "Prime the line. Regular insulin binds to plastic IV tubing. "
        "After preparing the bag, run 50 mL of the prepared solution "
        "through the administration set and discard before connecting "
        "to the patient. This saturates the binding sites so the "
        "delivered dose matches the calculated rate."
    )
    warnings.append(
        "Do NOT administer insulin SC in dehydrated DKA patients: "
        "absorption is unreliable. IV CRI or intermittent IM is the "
        "appropriate route until the patient is rehydrated and eating."
    )
    warnings.append(
        "Goal: lower blood glucose by no more than 50–75 mg/dL/hr toward "
        "< 250 mg/dL. If BG drops too fast or too slowly, adjust the "
        "insulin pump rate (do NOT change the bag concentration). "
        "Re-check BG every 2 hours; cross-check by stepping the fluid "
        "composition (NaCl ↔ 2.5% dextrose ↔ 5% dextrose) per the "
        "sliding scale."
    )
    warnings.append(
        "Hypokalemia, hypophosphatemia, and hypomagnesemia commonly "
        "develop or worsen as DKA therapy progresses. Monitor "
        "electrolytes every 4–6 hours initially. Supplement K, P, Mg "
        "per published sliding scales. If KPhos is used, subtract its "
        "K contribution from total K supplementation."
    )

    # Add CAT-specific persistent note about which dose was used
    if inputs.species == InsulinCriSpecies.CAT:
        if inputs.cat_dose_option == InsulinCriCatDoseOption.CONSERVATIVE_1_1:
            warnings.append(
                "Using the conservative 1.1 U/kg/day cat dose. A recent "
                "study using the canine 2.2 U/kg/day dose in cats with "
                "the same sliding scale did not show increased "
                "neurological or biochemical adverse events. The "
                "conservative option remains in the literature; modern "
                "evidence supports 2.2 U/kg/day for cats."
            )
        else:
            warnings.append(
                "Using the standard 2.2 U/kg/day dose for cats. A 2024 "
                "study showed no increase in adverse events when used "
                "with the same sliding scale. The historical 1.1 U/kg/day "
                "cat dose is available as a conservative option if "
                "clinical concern warrants."
            )

    if insulin_stopped:
        warnings.insert(
            0,
            "⚠ STOP insulin infusion. BG < 100 mg/dL, continue 5% dextrose "
            "fluids and re-check BG. Resume insulin at the appropriate "
            "sliding-scale rate once BG > 100 mg/dL.",
        )

    notes.append(
        f"Bag preparation: add {total_units:.1f} U regular insulin "
        f"({loading_u_per_kg:g} U/kg × {weight_kg:.2f} kg) to a "
        f"{INSULIN_CRI_BAG_VOLUME_ML:g} mL bag of 0.9% NaCl. "
        f"Bag concentration: {units_per_ml_in_bag:.4f} U/mL. "
        f"Prime line and discard 50 mL before connecting to patient."
    )
    if tier.note:
        notes.append(tier.note)
    notes.append(
        "Continue this protocol with frequent monitoring until the "
        "patient is reliably eating, drinking, hydrated, and ketone-"
        "negative. Then transition to maintenance SC insulin "
        "(intermediate or long-acting)."
    )

    return InsulinCriResult(
        weight_kg=round(weight_kg, 2),
        blood_glucose_mg_per_dl=round(inputs.blood_glucose_mg_per_dl, 1),
        species=inputs.species,
        loading_units_per_kg=loading_u_per_kg,
        total_units_added_to_bag=round(total_units, 2),
        bag_volume_ml=INSULIN_CRI_BAG_VOLUME_ML,
        bag_concentration_units_per_ml=round(units_per_ml_in_bag, 5),
        units_per_ml_in_bag_pre_prime=round(units_per_ml_pre, 5),
        prime_discard_ml=INSULIN_CRI_PRIME_DISCARD_ML,
        matched_tier=tier,
        fluid_composition=tier.fluid_composition,
        pump_rate_ml_per_hr=pump_rate,
        units_per_kg_per_hr_delivered=(round(delivered, 4) if delivered is not None else None),
        insulin_stopped=insulin_stopped,
        warnings=warnings,
        notes=notes,
        sources=INSULIN_CRI_DKA_SOURCES,
    )


INSULIN_CRI_DKA_SOURCES = (
    Source(
        citation=(
            "Koenig A. Hypoglycemia and DKA. In: Silverstein DC, Hopper K, eds. "
            "Small Animal Critical Care Medicine, 3rd ed. Elsevier, 2023. Chapter "
            "75. Low-dose IV insulin CRI protocol (2.2 U/kg in 250 mL, 10 mL/hr "
            "starting rate), titration based on blood glucose response."
        )
    ),
    Source(
        citation=(
            "Hess RS. Diabetic ketoacidosis. In: Ettinger SJ, Feldman EC, Côté E, "
            "eds. Textbook of Veterinary Internal Medicine, 8th ed. Elsevier, "
            "2017."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, regular insulin (insulin "
            "injection) monograph. CRI dosing in DKA (extra-label) and dilution "
            "stability."
        )
    ),
)

INSULIN_CRI_CATALOG_ENTRY = {
    "slug": "insulin-cri-dka",
    "display_name": "Insulin CRI (DKA, low-dose IV)",
    "short_name": "Insulin CRI · DKA",
    "category": "Endocrine",
    "kind": "single_drug_cri",
    "mechanism_summary": (
        "Continuous low-dose IV regular crystalline insulin promotes "
        "cellular glucose uptake (GLUT4 translocation), inhibits "
        "hepatic gluconeogenesis and glycogenolysis, and, critically "
        "for DKA, halts ketogenesis by suppressing lipolysis and "
        "redirecting acetyl-CoA back into the citric acid cycle. The "
        "low-dose protocol (≈0.05–0.1 U/kg/hr delivered) provides "
        "physiologic insulinization with smaller swings than higher-"
        "dose regimens, reducing risk of rapid osmotic shifts and "
        "hypokalemia."
    ),
    "indications_summary": (
        "Continuous low-dose IV regular insulin CRI for diabetic "
        "ketoacidosis in dogs and cats. Start once intravascular "
        "volume has been restored and dehydration is being actively "
        "corrected. The sliding scale adjusts pump rate and carrier "
        "fluid composition together so BG falls steadily without "
        "driving the patient into hypoglycemia."
    ),
}
