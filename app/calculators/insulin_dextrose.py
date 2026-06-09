"""
Insulin + dextrose for hyperkalemia (potassium-shifting therapy)
calculator.

Sources:
    Cooper ES. Urethral Obstruction. In: Silverstein DC, Hopper K, eds.
    Small Animal Critical Care Medicine. 3rd ed. Elsevier; 2023.
    Chapter 122. (Cites regular insulin 0.25–0.5 U/kg IV with concurrent
    dextrose 1–2 g per unit insulin given IV, followed by dextrose CRI
    2.5–5% in fluids for 4–6 hours.)
    DiBartola SP. Disorders of Potassium. In: Fluid, Electrolyte, and
    Acid-Base Disorders in Small Animal Practice. 4th ed. Elsevier;
    2012. Chapter 5.

Mechanism:
    Insulin activates Na/K-ATPase in skeletal muscle, shifting K into
    the intracellular space. The effect is mediated by insulin's normal
    metabolic action and is independent of glucose lowering, but
    insulin's hypoglycemic effect requires concurrent dextrose to
    prevent symptomatic hypoglycemia. Onset 15–30 min; duration 4–6 hr;
    typical K reduction 0.5–1.2 mEq/L.

    Insulin shifts ~30 mEq of K intracellularly per 10 U insulin in
    humans, the magnitude of K reduction in any given patient depends
    on the starting K, the magnitude of total-body K excess, and
    concurrent acid-base status.

This is a SHIFTING therapy, not a removing therapy. Total-body K is
unchanged. The K problem fundamentally resolves only when the
underlying cause is addressed (deobstruction in UTO, mineralocorticoid
replacement in Addisonian crisis, dialysis or diuresis in AKI).

Math:
    Insulin: dose_U_per_kg × weight_kg = U → mL of U-100 stock
    Dextrose bolus: insulin_U × g_per_U = grams → mL of D50 (0.5 g/mL)
    D50 must be DILUTED before bolus (osmolarity ~2500 mOsm/L).
    Standard practice: dilute D50 with equal volume of 0.9% NaCl to
    yield D25 (~1250 mOsm/L) for the bolus, still hyperosmolar but
    the safer of the practical options. Some institutions further
    dilute to D5 (250 mOsm/L) by mixing into 50–100 mL of saline.

    Dextrose CRI: 2.5–5% in maintenance fluids for 4–6 hr to prevent
    rebound hypoglycemia.

    BG monitoring: every 1 hour × 6 hours.

Stock concentrations:
    Regular insulin (Humulin R, Novolin R), 100 U/mL (U-100)
    Dextrose 50% (D50), 0.5 g/mL = 500 mg/mL = 1.7 kcal/mL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Insulin dose range
INSULIN_DOSE_MIN_U_PER_KG = 0.25
INSULIN_DOSE_DEFAULT_U_PER_KG = 0.25  # lower end is the safer default
INSULIN_DOSE_MAX_U_PER_KG = 0.5

# Dextrose-to-insulin ratio (grams of dextrose per unit of insulin)
DEXTROSE_RATIO_MIN = 1.0
DEXTROSE_RATIO_DEFAULT = 2.0  # 2 g per unit is the standard safety default
DEXTROSE_RATIO_MAX = 2.0

# Stock concentrations
INSULIN_STOCK_U_PER_ML = 100.0  # U-100 regular insulin
D50_STOCK_G_PER_ML = 0.5  # 50% dextrose

# Onset / duration
ONSET_MIN_LOW = 15
ONSET_MIN_HIGH = 30
EFFECT_DURATION_HR_LOW = 4
EFFECT_DURATION_HR_HIGH = 6

# K reduction expected
TYPICAL_K_REDUCTION_MEQ_LOW = 0.5
TYPICAL_K_REDUCTION_MEQ_HIGH = 1.2

# Dextrose CRI to follow
CRI_DEXTROSE_PCT_LOW = 2.5
CRI_DEXTROSE_PCT_HIGH = 5.0
CRI_DURATION_HR_LOW = 4
CRI_DURATION_HR_HIGH = 6


class InsulinDextroseSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class InsulinDextroseInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: InsulinDextroseSpecies
    insulin_dose_u_per_kg: float = INSULIN_DOSE_DEFAULT_U_PER_KG
    dextrose_g_per_u: float = DEXTROSE_RATIO_DEFAULT


@dataclass
class InsulinDextroseResult:
    weight_kg: float
    species: InsulinDextroseSpecies
    insulin_dose_u_per_kg: float
    dextrose_g_per_u: float

    # Insulin
    total_insulin_u: float
    insulin_volume_u100_ml: float

    # Dextrose bolus
    dextrose_total_g: float
    d50_volume_ml: float
    d25_dilution_volume_ml: float  # if diluted 1:1 with saline → D25

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def compute_insulin_dextrose(inputs: InsulinDextroseInputs) -> InsulinDextroseResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        # Refuse to compute. The previous code substituted weight_kg=0.001,
        # which produced a plausible-looking but wildly wrong dose if the
        # clinician missed the warning.
        return InsulinDextroseResult(
            weight_kg=weight_kg,
            species=inputs.species,
            insulin_dose_u_per_kg=inputs.insulin_dose_u_per_kg,
            dextrose_g_per_u=inputs.dextrose_g_per_u,
            total_insulin_u=0.0,
            insulin_volume_u100_ml=0.0,
            dextrose_total_g=0.0,
            d50_volume_ml=0.0,
            d25_dilution_volume_ml=0.0,
            warnings=["Weight must be greater than zero."],
            notes=[],
            sources=INSULIN_DEXTROSE_SOURCES,
            valid=False,
        )

    # Clamp insulin dose
    insulin_dose = inputs.insulin_dose_u_per_kg
    if insulin_dose < INSULIN_DOSE_MIN_U_PER_KG:
        warnings.append(
            f"Insulin dose {insulin_dose:g} U/kg is below the published "
            f"range of {INSULIN_DOSE_MIN_U_PER_KG:g}–{INSULIN_DOSE_MAX_U_PER_KG:g} "
            f"U/kg. Using {INSULIN_DOSE_MIN_U_PER_KG:g}."
        )
        insulin_dose = INSULIN_DOSE_MIN_U_PER_KG
    elif insulin_dose > INSULIN_DOSE_MAX_U_PER_KG:
        warnings.append(
            f"Insulin dose {insulin_dose:g} U/kg is above the published "
            f"maximum of {INSULIN_DOSE_MAX_U_PER_KG:g} U/kg. Using "
            f"{INSULIN_DOSE_MAX_U_PER_KG:g}. Higher doses do not "
            f"reliably lower K further but do increase hypoglycemia risk."
        )
        insulin_dose = INSULIN_DOSE_MAX_U_PER_KG

    # Clamp dextrose ratio
    dextrose_ratio = inputs.dextrose_g_per_u
    if dextrose_ratio < DEXTROSE_RATIO_MIN:
        warnings.append(
            f"Dextrose-to-insulin ratio {dextrose_ratio:g} g/U is below "
            f"the published minimum of {DEXTROSE_RATIO_MIN:g}. Using "
            f"{DEXTROSE_RATIO_MIN:g}. Lower ratios increase the risk of "
            f"symptomatic hypoglycemia."
        )
        dextrose_ratio = DEXTROSE_RATIO_MIN
    elif dextrose_ratio > DEXTROSE_RATIO_MAX:
        warnings.append(
            f"Dextrose-to-insulin ratio {dextrose_ratio:g} g/U is above "
            f"the published maximum of {DEXTROSE_RATIO_MAX:g}. Using "
            f"{DEXTROSE_RATIO_MAX:g}."
        )
        dextrose_ratio = DEXTROSE_RATIO_MAX

    # Math
    total_insulin = insulin_dose * weight_kg
    insulin_vol_u100 = total_insulin / INSULIN_STOCK_U_PER_ML

    total_dextrose_g = total_insulin * dextrose_ratio
    d50_vol = total_dextrose_g / D50_STOCK_G_PER_ML
    d25_dilution = d50_vol  # equal volume saline to dilute D50 → D25

    # Persistent warnings
    warnings.append(
        "Use regular crystalline insulin (Humulin R, Novolin R). NOT "
        "intermediate or long-acting insulin. NPH, lente, glargine, "
        "detemir, and degludec are NOT appropriate for this protocol. "
        "Read the vial. Doses are small; use a U-100 insulin syringe "
        "for accuracy."
    )
    warnings.append(
        f"Dilute D50 before IV bolus. D50 osmolarity (~2500 mOsm/L) "
        f"causes phlebitis and possibly endothelial injury when given "
        f"undiluted. Standard practice: dilute the {d50_vol:.2f} mL "
        f"of D50 with an equal volume ({d25_dilution:.2f} mL) of 0.9% "
        f"NaCl, yielding D25 for the bolus. For maximum safety, "
        f"further dilute into 50–100 mL of saline (final D5–D10) and "
        f"give over 5–10 minutes."
    )
    warnings.append(
        "Insulin shifts K intracellularly, it does NOT remove K from "
        "the body. Total-body K is unchanged. Effect onset 15–30 min; "
        "duration only 4–6 hr. The K problem resolves only when the "
        "UNDERLYING CAUSE is addressed (deobstruction in UTO, "
        "mineralocorticoid replacement in Addisonian crisis, dialysis "
        "in AKI). Do not delay definitive treatment."
    )
    warnings.append(
        f"REBOUND HYPOGLYCEMIA risk for 4–6 hours after the bolus. "
        f"Monitor blood glucose every 1 hour × 6 hours. Add a "
        f"{CRI_DEXTROSE_PCT_LOW:g}–{CRI_DEXTROSE_PCT_HIGH:g}% dextrose "
        f"CRI to the maintenance fluids for {CRI_DURATION_HR_LOW}–"
        f"{CRI_DURATION_HR_HIGH} hours. If BG drops below 80 mg/dL, "
        f"give a 1 mL/kg D50 (diluted) bolus and increase the CRI "
        f"dextrose concentration. Symptomatic hypoglycemia in cats may "
        f"be subtle, weakness, lethargy, decreased mentation."
    )
    warnings.append(
        "Recheck serum K at 30 min and 1 hour. Typical reduction is "
        f"{TYPICAL_K_REDUCTION_MEQ_LOW:g}–{TYPICAL_K_REDUCTION_MEQ_HIGH:g} "
        f"mEq/L. If K has not fallen at 1 hour or has rebounded, "
        f"consider repeating insulin/dextrose AND ensure fluid therapy "
        f"and definitive treatment of the underlying cause are in "
        f"progress. Do NOT exceed 0.5 U/kg per dose."
    )

    # Notes
    notes.append(
        f"Math: insulin {insulin_dose:g} U/kg × {weight_kg:.2f} kg = "
        f"{total_insulin:.2f} U regular insulin = "
        f"{insulin_vol_u100:.3f} mL of U-100. Dextrose at "
        f"{dextrose_ratio:g} g per unit insulin = "
        f"{total_dextrose_g:.2f} g = {d50_vol:.2f} mL of D50."
    )
    notes.append(
        f"Onset {ONSET_MIN_LOW}–{ONSET_MIN_HIGH} min; effect lasts "
        f"{EFFECT_DURATION_HR_LOW}–{EFFECT_DURATION_HR_HIGH} hours. "
        f"Typical K reduction "
        f"{TYPICAL_K_REDUCTION_MEQ_LOW:g}–{TYPICAL_K_REDUCTION_MEQ_HIGH:g} "
        f"mEq/L. Calcium gluconate (membrane stabilization) should be "
        f"running first or simultaneously if there are ECG changes; "
        f"insulin/dextrose alone takes 15–30 min to start working."
    )
    notes.append(
        "Concurrent therapy: continue or start fluid therapy (improves "
        "renal perfusion and K excretion when obstruction is relieved); "
        "address the underlying cause (deobstruct, replace "
        "mineralocorticoid, treat AKI). Volume restoration and "
        "obstruction relief are the only definitive K-removal steps."
    )

    return InsulinDextroseResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        insulin_dose_u_per_kg=insulin_dose,
        dextrose_g_per_u=dextrose_ratio,
        total_insulin_u=round(total_insulin, 2),
        insulin_volume_u100_ml=round(insulin_vol_u100, 3),
        dextrose_total_g=round(total_dextrose_g, 2),
        d50_volume_ml=round(d50_vol, 2),
        d25_dilution_volume_ml=round(d25_dilution, 2),
        warnings=warnings,
        notes=notes,
        sources=INSULIN_DEXTROSE_SOURCES,
    )


INSULIN_DEXTROSE_SOURCES = (
    Source(
        citation=(
            "DiBartola SP, de Morais HA. Disorders of potassium: hypokalemia and "
            "hyperkalemia. In: DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base "
            "Disorders in Small Animal Practice, 4th ed. Elsevier, 2012. Chapter "
            "5. Insulin-glucose protocol for emergent hyperkalemia (0.25–0.5 U/kg "
            "regular insulin with 1–2 g dextrose per unit)."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, regular insulin and 50% dextrose "
            "monographs. Hyperkalemia indication, dilution requirements, and rate "
            "of administration."
        )
    ),
)

INSULIN_DEXTROSE_CATALOG_ENTRY = {
    "slug": "insulin-dextrose-hyperK",
    "display_name": "Insulin + dextrose (K-shifting)",
    "short_name": "Insulin/dextrose",
    "category": "Electrolytes & Fluids",
    "kind": "dose_calculator",
    "mechanism_summary": (
        "Potassium-shifting therapy for life-threatening hyperkalemia. "
        "Regular insulin 0.25–0.5 U/kg IV bolus with concurrent "
        "dextrose 1–2 g per unit insulin, followed by dextrose CRI "
        "2.5–5% for 4–6 hours to prevent rebound hypoglycemia. Onset "
        "15–30 min, duration 4–6 hr, typical K reduction 0.5–1.2 mEq/L. "
        "Insulin activates Na/K-ATPase, shifting K intracellularly. "
        "It does NOT remove K from the body. Definitive treatment of "
        "the underlying cause is required for the K problem to "
        "fundamentally resolve."
    ),
    "indications_summary": (
        "Emergency potassium shifting for life-threatening "
        "hyperkalemia in dogs and cats. Regular insulin drives K from "
        "extracellular fluid into cells; concurrent dextrose prevents "
        "iatrogenic hypoglycemia. Onset 15–30 min, K reduction "
        "0.5–1.2 mEq/L lasting 4–6 hr. Typically paired with calcium "
        "gluconate and definitive treatment of the underlying cause."
    ),
}
