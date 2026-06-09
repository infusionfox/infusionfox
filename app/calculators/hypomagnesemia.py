"""
Hypomagnesemia / MgSO4 CRI calculator.

Sources:
    DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base Disorders in
    Small Animal Practice. 4th ed. Elsevier; 2012. Chapter 8 (Disorders
    of Magnesium).
    Hoehne SN. Diabetic Ketoacidosis. In: Silverstein DC, Hopper K, eds.
    Small Animal Critical Care Medicine. 3rd ed. Elsevier; 2023.
    Chapter 73, Box 73.1 (MgSO4 rate range 0.25–1 mEq/kg/day IV).

Sliding scale by total serum magnesium:
    Serum Mg (mg/dL)  MgSO4 rate (mEq/kg/day)   Severity
    > 1.5             not indicated              normomagnesemia
    1.2–1.5           0.25                       mild
    0.9–1.2           0.5                        moderate
    < 0.9             0.75–1.0                   severe / critical

Note that reference ranges for total serum magnesium vary by laboratory
but are typically 1.5–2.5 mg/dL in dogs and 1.7–2.5 mg/dL in cats.
Ionized magnesium is the more physiologically relevant measure but is
less commonly available; total Mg is what most clinical labs report and
what the scale above uses.

Critical clinical interaction:
    Refractory hypocalcemia and refractory hypokalemia can both be
    Mg-dependent. A patient who is not responding to calcium or potassium
    supplementation despite apparently adequate dosing should have Mg
    measured. Mg deficiency impairs PTH release and Mg is a cofactor for
    Na/K-ATPase, so until Mg is replenished the other electrolytes won't
    correct.

Stock concentration:
    Standard MgSO4 (magnesium sulfate) parenteral solution is 50%
    weight/volume = 500 mg/mL = 4.06 mEq/mL ≈ 4 mEq/mL. Some hospitals
    stock 25% (250 mg/mL = 2 mEq/mL) as well. The calculator defaults
    to 50% / 4 mEq/mL as the most common veterinary stock.

    MgSO4 must be DILUTED before IV administration, typically into 5%
    dextrose in water (D5W), since calcium-containing fluids can
    potentially form magnesium phosphate or interact with calcium-Mg
    homeostasis. 0.9% NaCl is also commonly used.

Math:
    target_rate = mEq/kg/day from the sliding scale
    daily_meq = weight_kg × target_rate
    hourly_meq = daily_meq / 24
    pump_rate (mL/hr) = hourly_meq / stock_meq_per_ml
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Standard MgSO4 50% solution: 500 mg/mL = ≈4 mEq/mL
MGSO4_STOCK_MEQ_PER_ML_DEFAULT = 4.0
MGSO4_STOCK_25_PCT_MEQ_PER_ML = 2.0  # alternate 25% stock

HOURS_PER_DAY = 24


class MgSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


class MgStockConcentration(str, Enum):
    PCT_50 = "50pct"  # 4 mEq/mL, default
    PCT_25 = "25pct"  # 2 mEq/mL


def stock_meq_per_ml(concentration: MgStockConcentration) -> float:
    return (
        MGSO4_STOCK_MEQ_PER_ML_DEFAULT
        if concentration == MgStockConcentration.PCT_50
        else MGSO4_STOCK_25_PCT_MEQ_PER_ML
    )


@dataclass
class HypomagnesemiaTier:
    """One row of the sliding scale."""

    label: str
    mg_low: float | None  # inclusive lower bound (mg/dL); None = open
    mg_high: float | None  # exclusive upper bound (mg/dL); None = open
    rate_meq_per_kg_per_day: float | None
    severity: str
    note: str | None = None


HYPOMAGNESEMIA_TIERS: list[HypomagnesemiaTier] = [
    HypomagnesemiaTier(
        label="Mg > 1.5 mg/dL",
        mg_low=1.5,
        mg_high=None,
        rate_meq_per_kg_per_day=None,
        severity="normomagnesemia",
        note=(
            "Total magnesium within the typical reference range for dogs "
            "and cats. Supplementation is not indicated for the Mg level "
            "alone, but consider checking Mg in any patient with "
            "refractory hypocalcemia or hypokalemia despite apparently "
            "adequate replacement. Mg deficiency can prevent those "
            "from correcting."
        ),
    ),
    HypomagnesemiaTier(
        label="Mg 1.2–1.5 mg/dL",
        mg_low=1.2,
        mg_high=1.5,
        rate_meq_per_kg_per_day=0.25,
        severity="mild",
        note=(
            "Mild hypomagnesemia. Often asymptomatic but worth "
            "supplementing in critically ill patients, those with "
            "refractory K or Ca derangements, or during DKA management."
        ),
    ),
    HypomagnesemiaTier(
        label="Mg 0.9–1.2 mg/dL",
        mg_low=0.9,
        mg_high=1.2,
        rate_meq_per_kg_per_day=0.5,
        severity="moderate",
        note=(
            "Moderate hypomagnesemia. May produce muscle weakness, "
            "tremors, anorexia, ileus. Begin supplementation."
        ),
    ),
    HypomagnesemiaTier(
        label="Mg < 0.9 mg/dL",
        mg_low=None,
        mg_high=0.9,
        rate_meq_per_kg_per_day=1.0,
        severity="severe",
        note=(
            "Severe hypomagnesemia. Risk of refractory ventricular "
            "arrhythmias (torsades de pointes is the classic but rare "
            "presentation), tetany, seizures. Use the upper end of the "
            "published rate range (1.0 mEq/kg/day). Consider continuous "
            "ECG monitoring during supplementation."
        ),
    ),
]


@dataclass
class HypomagnesemiaInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: MgSpecies
    serum_mg_mg_per_dl: float
    stock_concentration: MgStockConcentration = MgStockConcentration.PCT_50


@dataclass
class HypomagnesemiaResult:
    weight_kg: float
    species: MgSpecies
    serum_mg_mg_per_dl: float
    matched_tier: HypomagnesemiaTier
    not_indicated: bool

    target_rate_meq_per_kg_per_day: float | None
    daily_meq: float | None
    hourly_meq: float | None
    stock_meq_per_ml: float
    stock_concentration_label: str
    pump_rate_ml_per_hr: float | None
    pump_rate_ml_per_day: float | None

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _match_tier(mg: float) -> HypomagnesemiaTier:
    for tier in HYPOMAGNESEMIA_TIERS:
        low_ok = tier.mg_low is None or mg >= tier.mg_low
        high_ok = tier.mg_high is None or mg < tier.mg_high
        if low_ok and high_ok:
            return tier
    return HYPOMAGNESEMIA_TIERS[-1]


def compute_hypomagnesemia(inputs: HypomagnesemiaInputs) -> HypomagnesemiaResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)

    # Validate. Math on a non-positive weight produces a meaningless
    # pump rate; refuse to compute. Negative serum Mg is not physical.
    errors: list[str] = []
    if weight_kg <= 0:
        errors.append("Weight must be greater than zero.")
    if inputs.serum_mg_mg_per_dl < 0:
        errors.append("Serum magnesium cannot be negative.")
    if errors:
        stock_meq = stock_meq_per_ml(inputs.stock_concentration)
        stock_label = (
            "50% (4 mEq/mL)" if inputs.stock_concentration == MgStockConcentration.PCT_50 else "25% (2 mEq/mL)"
        )
        return HypomagnesemiaResult(
            weight_kg=weight_kg,
            species=inputs.species,
            serum_mg_mg_per_dl=inputs.serum_mg_mg_per_dl,
            matched_tier=HYPOMAGNESEMIA_TIERS[0],
            not_indicated=False,
            target_rate_meq_per_kg_per_day=None,
            daily_meq=None,
            hourly_meq=None,
            stock_meq_per_ml=stock_meq,
            stock_concentration_label=stock_label,
            pump_rate_ml_per_hr=None,
            pump_rate_ml_per_day=None,
            warnings=errors,
            notes=[],
            sources=HYPOMAGNESEMIA_SOURCES,
            valid=False,
        )

    tier = _match_tier(inputs.serum_mg_mg_per_dl)
    not_indicated = tier.rate_meq_per_kg_per_day is None
    stock_meq = stock_meq_per_ml(inputs.stock_concentration)
    stock_label = (
        "50% (4 mEq/mL)" if inputs.stock_concentration == MgStockConcentration.PCT_50 else "25% (2 mEq/mL)"
    )

    daily_meq = None
    hourly_meq = None
    pump_rate = None
    pump_rate_per_day = None

    if not not_indicated and weight_kg > 0:
        target_rate = tier.rate_meq_per_kg_per_day
        daily_meq = weight_kg * target_rate
        hourly_meq = daily_meq / HOURS_PER_DAY
        pump_rate = hourly_meq / stock_meq  # mL/hr
        pump_rate_per_day = daily_meq / stock_meq  # mL/day

    # Persistent warnings
    warnings.append(
        "MgSO4 must be DILUTED before IV administration. Standard practice "
        "is to dilute into 5% dextrose in water (D5W) or 0.9% NaCl and "
        "run via syringe pump or volumetric pump. Avoid direct IV push "
        "(rapid administration can cause hypotension, flushing, and "
        "cardiovascular collapse)."
    )
    warnings.append(
        "Watch for hypermagnesemia signs: hyporeflexia, weakness, "
        "lethargy, hypotension, prolonged PR interval. Stop the infusion "
        "if these develop. Severe hypermagnesemia can cause respiratory "
        "depression and cardiac arrest. Reduce the rate or discontinue "
        "in renal insufficiency. Mg is renally excreted."
    )
    warnings.append(
        "Re-check serum Mg every 12–24 hours during active MgSO4 "
        "supplementation. The target is the lower end of the reference "
        "range (≈1.5 mg/dL); aim to discontinue once Mg is normal and "
        "the patient is eating."
    )

    if tier.note:
        notes.append(f"{tier.label} ({tier.severity}): {tier.note}")

    if not not_indicated and daily_meq is not None:
        notes.append(
            f"Pump rate math: target {tier.rate_meq_per_kg_per_day:g} mEq/kg/day × "
            f"{weight_kg:.2f} kg = {daily_meq:.2f} mEq/day "
            f"(= {hourly_meq:.3f} mEq/hr). At "
            f"{stock_meq:g} mEq/mL stock ({stock_label}), that is "
            f"{pump_rate:.3f} mL/hr (= {pump_rate_per_day:.2f} mL/day)."
        )

    notes.append(
        "Refractory electrolyte derangements: a patient with hypocalcemia "
        "or hypokalemia that won't correct despite apparently adequate "
        "replacement should have Mg measured. Mg deficiency impairs PTH "
        "release (limiting Ca correction) and is a cofactor for "
        "Na/K-ATPase (limiting K correction). Check the referring lab's "
        "reference range, total Mg ranges vary slightly between dogs "
        "(~1.5–2.5 mg/dL) and cats (~1.7–2.5 mg/dL)."
    )
    notes.append(
        "Hypomagnesemia in DKA: insulin shifts Mg intracellularly "
        "alongside K and P. Hoehne notes that Mg decline after DKA "
        "therapy starts is observed in both dogs and cats. Check Mg "
        "1–2 times daily during DKA management."
    )
    notes.append(
        "Other causes worth considering: chronic loop or thiazide diuretic "
        "therapy, GI losses (chronic diarrhea, malabsorption), refeeding "
        "syndrome, primary hyperaldosteronism (cats), hyperthyroidism, "
        "diabetes mellitus, severe burns, chronic alcoholism (a human risk factor "
        "not directly relevant to most veterinary cases but worth knowing "
        "for the broader Mg-deficiency literature)."
    )

    return HypomagnesemiaResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        serum_mg_mg_per_dl=round(inputs.serum_mg_mg_per_dl, 2),
        matched_tier=tier,
        not_indicated=not_indicated,
        target_rate_meq_per_kg_per_day=tier.rate_meq_per_kg_per_day,
        daily_meq=(round(daily_meq, 2) if daily_meq is not None else None),
        hourly_meq=(round(hourly_meq, 4) if hourly_meq is not None else None),
        stock_meq_per_ml=stock_meq,
        stock_concentration_label=stock_label,
        pump_rate_ml_per_hr=(round(pump_rate, 3) if pump_rate is not None else None),
        pump_rate_ml_per_day=(round(pump_rate_per_day, 2) if pump_rate_per_day is not None else None),
        warnings=warnings,
        notes=notes,
        sources=HYPOMAGNESEMIA_SOURCES,
    )


HYPOMAGNESEMIA_SOURCES = (
    Source(
        citation=(
            "DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in Small "
            "Animal Practice, 4th ed. Elsevier, 2012. Chapter 7 (Disorders of "
            "Magnesium). Magnesium supplementation indications, MgSO4 dosing "
            "(0.5–1 mEq/kg/day for repletion, 0.25 mEq/kg/day for maintenance), "
            "and the magnesium-potassium relationship."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, magnesium sulfate monograph. 50% "
            "solution = 4 mEq/mL; compatibility considerations and "
            "contraindications in renal failure."
        )
    ),
)

HYPOMAGNESEMIA_CATALOG_ENTRY = {
    "slug": "hypomagnesemia",
    "display_name": "Hypomagnesemia / MgSO4 CRI",
    "short_name": "MgSO4",
    "category": "Electrolytes & Fluids",
    "kind": "sliding_scale",
    "mechanism_summary": (
        "Standard sliding-scale MgSO4 CRI for hypomagnesemia. Magnesium "
        "is a cofactor for hundreds of enzymes including Na/K-ATPase, "
        "and Mg deficiency is a frequent cause of refractory hypokalemia "
        "and hypocalcemia (Mg is required for PTH release). Severe "
        "hypomagnesemia can cause refractory ventricular arrhythmias "
        "(including torsades de pointes), tetany, and seizures."
    ),
    "indications_summary": (
        "IV magnesium sulfate CRI for hypomagnesemia in dogs and "
        "cats. Enter serum Mg, body weight, and MgSO4 stock "
        "concentration; returns a CRI rate from a 4-tier sliding "
        "scale. Also worth considering in workup of refractory "
        "hypocalcemia or hypokalemia where occult hypomagnesemia is "
        "the missing link."
    ),
}
