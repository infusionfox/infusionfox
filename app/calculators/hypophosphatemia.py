"""
Hypophosphatemia / KPhos CRI calculator.

Sources:
    DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base Disorders in
    Small Animal Practice. 4th ed. Elsevier; 2012. Chapter 7
    (Disorders of Phosphorus).
    Hoehne SN. Diabetic Ketoacidosis. In: Silverstein DC, Hopper K, eds.
    Small Animal Critical Care Medicine. 3rd ed. Elsevier; 2023.
    Chapter 73, Box 73.1 (KPhos rate range 0.03–0.12 mmol/kg/hr IV).

Sliding scale by serum phosphorus:
    Serum P (mg/dL)   KPhos rate (mmol/kg/hr)   Indication
    > 2.0             not indicated              normophosphatemia
    1.5–2.0           0.03                       mild
    1.0–1.5           0.06                       moderate
    0.5–1.0           0.09                       severe
    < 0.5             0.12                       critical

Critical clinical interaction:
    Standard KPhos solution contains BOTH potassium AND phosphate. The
    most common veterinary preparation (potassium phosphate injection,
    USP) provides:
        ≈ 4.4 mEq K per mL
        ≈ 3.0 mmol P per mL
    So infusing 1 mL of KPhos delivers about 4.4 mEq of K. For a patient
    on a concurrent KCl CRI per the hypokalemia sliding scale, the K
    contribution from KPhos must be SUBTRACTED from the planned KCl
    supplementation, otherwise total K delivery can easily exceed the
    0.5 mEq/kg/hr ceiling, producing dangerous hyperkalemia and
    arrhythmias.

    The calculator surfaces:
        - mmol/hr P delivered
        - mEq/hr K delivered (from the KPhos itself)
        - max-K-from-KCl-allowable to stay under 0.5 mEq/kg/hr total
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Standard veterinary KPhos preparation (potassium phosphate injection, USP)
KPHOS_K_MEQ_PER_ML = 4.4
KPHOS_P_MMOL_PER_ML = 3.0

# Total K administration ceiling (DiBartola Ch. 5 / Hoehne Ch. 73)
TOTAL_K_CEILING_MEQ_PER_KG_PER_HR = 0.5


class KPhosSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class HypophosphatemiaTier:
    """One row of the sliding scale."""

    label: str
    p_low: float | None  # inclusive lower bound (mg/dL); None = open
    p_high: float | None  # exclusive upper bound (mg/dL); None = open
    rate_mmol_per_kg_per_hr: float | None  # None = no supplementation needed
    severity: str
    note: str | None = None


HYPOPHOSPHATEMIA_TIERS: list[HypophosphatemiaTier] = [
    HypophosphatemiaTier(
        label="P > 2.0 mg/dL",
        p_low=2.0,
        p_high=None,
        rate_mmol_per_kg_per_hr=None,
        severity="normophosphatemia",
        note=(
            "Phosphorus is within or above the reference range. "
            "Supplementation is not indicated. Continue monitoring "
            "every 12–24 hours during ongoing therapy that can drop "
            "P (insulin, total parenteral nutrition, refeeding)."
        ),
    ),
    HypophosphatemiaTier(
        label="P 1.5–2.0 mg/dL",
        p_low=1.5,
        p_high=2.0,
        rate_mmol_per_kg_per_hr=0.03,
        severity="mild",
        note=(
            "Mild hypophosphatemia. Often asymptomatic but worth "
            "supplementing in patients with ongoing P-lowering therapy "
            "(eg, DKA on insulin) to prevent further drop."
        ),
    ),
    HypophosphatemiaTier(
        label="P 1.0–1.5 mg/dL",
        p_low=1.0,
        p_high=1.5,
        rate_mmol_per_kg_per_hr=0.06,
        severity="moderate",
        note=(
            "Moderate hypophosphatemia. Subclinical or producing "
            "weakness, hyporexia, dysphagia. Begin supplementation."
        ),
    ),
    HypophosphatemiaTier(
        label="P 0.5–1.0 mg/dL",
        p_low=0.5,
        p_high=1.0,
        rate_mmol_per_kg_per_hr=0.09,
        severity="severe",
        note=(
            "Severe hypophosphatemia. Risk of hemolysis, respiratory "
            "muscle weakness, cardiac dysfunction. Begin aggressive "
            "supplementation; monitor PCV and acid-base."
        ),
    ),
    HypophosphatemiaTier(
        label="P < 0.5 mg/dL",
        p_low=None,
        p_high=0.5,
        rate_mmol_per_kg_per_hr=0.12,
        severity="critical",
        note=(
            "Critical hypophosphatemia. Acute hemolytic anemia is "
            "imminent or already occurring; respiratory and cardiac "
            "failure are real risks. Maximum sliding-scale rate. "
            "Recheck P every 4–6 hours. Consider transfusion if "
            "hemolysis develops."
        ),
    ),
]


@dataclass
class HypophosphatemiaInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: KPhosSpecies
    serum_p_mg_per_dl: float
    concurrent_kcl_meq_per_kg_per_hr: float = 0.0  # if patient is on KCl CRI


@dataclass
class HypophosphatemiaResult:
    weight_kg: float
    species: KPhosSpecies
    serum_p_mg_per_dl: float
    matched_tier: HypophosphatemiaTier
    not_indicated: bool

    # Math
    target_rate_mmol_per_kg_per_hr: float | None
    p_delivered_mmol_per_hr: float | None
    k_delivered_meq_per_hr: float | None
    k_delivered_meq_per_kg_per_hr: float | None
    kphos_pump_rate_ml_per_hr: float | None

    # K interaction
    concurrent_kcl_meq_per_kg_per_hr: float
    total_k_meq_per_kg_per_hr: float | None
    total_k_ceiling_meq_per_kg_per_hr: float
    max_kcl_remaining_meq_per_kg_per_hr: float | None
    exceeds_k_ceiling: bool

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _match_tier(p: float) -> HypophosphatemiaTier:
    for tier in HYPOPHOSPHATEMIA_TIERS:
        low_ok = tier.p_low is None or p >= tier.p_low
        high_ok = tier.p_high is None or p < tier.p_high
        if low_ok and high_ok:
            return tier
    return HYPOPHOSPHATEMIA_TIERS[-1]


def compute_hypophosphatemia(inputs: HypophosphatemiaInputs) -> HypophosphatemiaResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)

    # Validate. Math on a non-positive weight produces a meaningless
    # KPhos rate and total-K accounting; refuse to compute.
    errors: list[str] = []
    if weight_kg <= 0:
        errors.append("Weight must be greater than zero.")
    if inputs.serum_p_mg_per_dl < 0:
        errors.append("Serum phosphorus cannot be negative.")
    if errors:
        return HypophosphatemiaResult(
            weight_kg=weight_kg,
            species=inputs.species,
            serum_p_mg_per_dl=inputs.serum_p_mg_per_dl,
            matched_tier=HYPOPHOSPHATEMIA_TIERS[0],
            not_indicated=False,
            target_rate_mmol_per_kg_per_hr=None,
            p_delivered_mmol_per_hr=None,
            k_delivered_meq_per_hr=None,
            k_delivered_meq_per_kg_per_hr=None,
            kphos_pump_rate_ml_per_hr=None,
            concurrent_kcl_meq_per_kg_per_hr=inputs.concurrent_kcl_meq_per_kg_per_hr,
            total_k_meq_per_kg_per_hr=None,
            total_k_ceiling_meq_per_kg_per_hr=TOTAL_K_CEILING_MEQ_PER_KG_PER_HR,
            max_kcl_remaining_meq_per_kg_per_hr=None,
            exceeds_k_ceiling=False,
            warnings=errors,
            notes=[],
            sources=HYPOPHOSPHATEMIA_SOURCES,
            valid=False,
        )

    tier = _match_tier(inputs.serum_p_mg_per_dl)
    not_indicated = tier.rate_mmol_per_kg_per_hr is None

    # Math (only if supplementation indicated)
    p_delivered = None
    k_delivered = None
    k_per_kg_hr = None
    pump_rate = None
    total_k = None
    max_kcl_remaining = None
    exceeds = False

    if not not_indicated and weight_kg > 0:
        target_rate = tier.rate_mmol_per_kg_per_hr
        p_delivered = weight_kg * target_rate  # mmol/hr P
        # KPhos pump rate (mL/hr): p_delivered (mmol/hr) / KPHOS_P_MMOL_PER_ML
        pump_rate = p_delivered / KPHOS_P_MMOL_PER_ML
        # K delivered (mEq/hr): pump_rate × KPHOS_K_MEQ_PER_ML
        k_delivered = pump_rate * KPHOS_K_MEQ_PER_ML
        # K per kg per hr from KPhos
        k_per_kg_hr = k_delivered / weight_kg

        # Total K (KPhos + concurrent KCl)
        total_k = k_per_kg_hr + max(0.0, inputs.concurrent_kcl_meq_per_kg_per_hr)
        # Max KCl remaining headroom
        max_kcl_remaining = max(0.0, TOTAL_K_CEILING_MEQ_PER_KG_PER_HR - k_per_kg_hr)
        exceeds = total_k > TOTAL_K_CEILING_MEQ_PER_KG_PER_HR

        if exceeds:
            warnings.insert(
                0,
                f"⚠ TOTAL K delivery would be {total_k:.3f} mEq/kg/hr, "
                f"EXCEEDING the 0.5 mEq/kg/hr ceiling. KPhos alone "
                f"contributes {k_per_kg_hr:.3f} mEq/kg/hr; concurrent KCl "
                f"is currently {inputs.concurrent_kcl_meq_per_kg_per_hr:g} "
                f"mEq/kg/hr. REDUCE concurrent KCl to "
                f"{max_kcl_remaining:.3f} mEq/kg/hr or less so total K "
                f"stays under the ceiling. Continuous ECG monitoring "
                f"recommended for any sustained delivery near the ceiling.",
            )

    # Persistent warnings
    warnings.append(
        "K from KPhos counts toward the total K administration ceiling "
        "(0.5 mEq/kg/hr per DiBartola). The result panel below shows the "
        "K contribution from KPhos and the headroom remaining for "
        "concurrent KCl. If the patient is on a KCl CRI per the "
        "hypokalemia sliding scale, REDUCE the KCl rate by the K "
        "contribution from KPhos."
    )
    warnings.append(
        "Standard KPhos preparation (potassium phosphate injection, USP): "
        f"{KPHOS_K_MEQ_PER_ML:g} mEq K + {KPHOS_P_MMOL_PER_ML:g} mmol P "
        "per mL. Verify your hospital stock matches these concentrations "
        "before infusing, some compounded preparations differ. Read the "
        "vial."
    )
    warnings.append(
        "KPhos must be DILUTED before IV administration, never give "
        "undiluted. Dilute into 0.9% NaCl, LRS, or Plasma-Lyte and run "
        "via syringe pump or volumetric pump. Direct IV push or "
        "incompatible-line co-infusion can precipitate (calcium-"
        "containing fluids will form calcium phosphate; KPhos and LRS "
        "are technically compatible at standard CRI dilutions but "
        "verify with your hospital pharmacy)."
    )
    warnings.append(
        "Re-check serum P every 4–6 hours during active KPhos therapy. "
        "Discontinue when P > 2.0 mg/dL. Watch for hyperphosphatemia, "
        "hypocalcemia (P-Ca product), and metastatic mineralization with "
        "prolonged or excessive supplementation."
    )

    if tier.note:
        notes.append(f"{tier.label} ({tier.severity}): {tier.note}")

    if not not_indicated and p_delivered is not None:
        notes.append(
            f"Pump rate math: target {tier.rate_mmol_per_kg_per_hr:g} mmol/kg/hr × "
            f"{weight_kg:.2f} kg = {p_delivered:.3f} mmol/hr P. "
            f"At {KPHOS_P_MMOL_PER_ML:g} mmol P/mL stock, that is "
            f"{pump_rate:.3f} mL/hr KPhos. K contribution: "
            f"{pump_rate:.3f} mL/hr × {KPHOS_K_MEQ_PER_ML:g} mEq/mL = "
            f"{k_delivered:.3f} mEq/hr K (= {k_per_kg_hr:.3f} mEq/kg/hr)."
        )

    notes.append(
        "Hypophosphatemia in DKA: insulin therapy shifts P intracellularly, "
        "and ≈48% of dogs with DKA develop or worsen hypophosphatemia "
        "during therapy (Hoehne Ch. 73). Severe hypophosphatemia causes "
        "hemolysis (the most life-threatening complication), respiratory "
        "muscle weakness, cardiac dysfunction, and CNS depression. "
        "Monitor every 4–12 hours during DKA management."
    )
    notes.append(
        "Other causes of hypophosphatemia worth considering: refeeding "
        "syndrome (severe, can be fatal), primary hyperparathyroidism "
        "treatment, total parenteral nutrition, severe malnutrition, "
        "post-obstructive diuresis, severe respiratory alkalosis."
    )

    return HypophosphatemiaResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        serum_p_mg_per_dl=round(inputs.serum_p_mg_per_dl, 2),
        matched_tier=tier,
        not_indicated=not_indicated,
        target_rate_mmol_per_kg_per_hr=tier.rate_mmol_per_kg_per_hr,
        p_delivered_mmol_per_hr=(round(p_delivered, 3) if p_delivered is not None else None),
        k_delivered_meq_per_hr=(round(k_delivered, 3) if k_delivered is not None else None),
        k_delivered_meq_per_kg_per_hr=(round(k_per_kg_hr, 3) if k_per_kg_hr is not None else None),
        kphos_pump_rate_ml_per_hr=(round(pump_rate, 3) if pump_rate is not None else None),
        concurrent_kcl_meq_per_kg_per_hr=max(0.0, inputs.concurrent_kcl_meq_per_kg_per_hr),
        total_k_meq_per_kg_per_hr=(round(total_k, 3) if total_k is not None else None),
        total_k_ceiling_meq_per_kg_per_hr=TOTAL_K_CEILING_MEQ_PER_KG_PER_HR,
        max_kcl_remaining_meq_per_kg_per_hr=(
            round(max_kcl_remaining, 3) if max_kcl_remaining is not None else None
        ),
        exceeds_k_ceiling=exceeds,
        warnings=warnings,
        notes=notes,
        sources=HYPOPHOSPHATEMIA_SOURCES,
    )


HYPOPHOSPHATEMIA_SOURCES = (
    Source(
        citation=(
            "DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in Small "
            "Animal Practice, 4th ed. Elsevier, 2012. Chapter 6 (Disorders of "
            "Phosphate). Refeeding syndrome, hypophosphatemia in DKA, and KPhos "
            "supplementation rate (0.03–0.12 mmol/kg/hr)."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, potassium phosphate monograph. "
            "Concentration (3 mmol P + 4.4 mEq K per mL), compatibility, and "
            "contraindications."
        )
    ),
    Source(
        citation=(
            "Willard MD. Disorders of phosphorus. In: DiBartola SP, ed. Fluid, "
            "Electrolyte, and Acid-Base Disorders in Small Animal Practice, 4th "
            "ed. Elsevier, 2012."
        )
    ),
)

HYPOPHOSPHATEMIA_CATALOG_ENTRY = {
    "slug": "hypophosphatemia",
    "display_name": "Hypophosphatemia / KPhos CRI",
    "short_name": "KPhos",
    "category": "Electrolytes & Fluids",
    "kind": "sliding_scale",
    "mechanism_summary": (
        "Standard sliding-scale KPhos CRI for hypophosphatemia, with the "
        "K-contribution interaction surfaced explicitly. Severe "
        "hypophosphatemia causes acute intravascular hemolysis (the most "
        "life-threatening complication), respiratory muscle weakness, "
        "and cardiac dysfunction. Most commonly seen during DKA therapy "
        "(insulin shifts P intracellularly) and refeeding syndrome."
    ),
    "indications_summary": (
        "IV potassium phosphate CRI for hypophosphatemia in dogs and "
        "cats. Enter serum P and body weight; returns a KPhos rate "
        "from a 5-tier sliding scale and surfaces the potassium load "
        "KPhos contributes so total K supplementation (including any "
        "concurrent KCl) stays under the 0.5 mEq/kg/hr cardiac-safety "
        "ceiling."
    ),
}
