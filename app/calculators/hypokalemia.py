"""
Hypokalemia / KCl supplementation calculator.

Source: DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base Disorders in
Small Animal Practice. 4th ed. St. Louis, MO: Elsevier Saunders; 2012.
Chapter 5 (Disorders of Potassium: Hypokalemia and Hyperkalemia), pp. 107-108,
Table 5-2 (Guidelines for Routine Intravenous Supplementation of Potassium
in Dogs and Cats).

Table 5-2 sourced originally from: Greene RW, Scott RC. Lower urinary tract
disease. In Ettinger SJ, ed. Textbook of Veterinary Internal Medicine.
Philadelphia: WB Saunders; 1975:1572.

Clinical logic:
    A serum potassium level maps to a recommended KCl supplementation per
    bag of IV fluid and a maximum fluid infusion rate. The table is
    constructed so that the infused potassium does not exceed the safety
    ceiling of 0.5 mEq/kg/hr, beyond which cardiac toxicity becomes a
    concern. Each row delivers roughly 0.48 mEq/kg/hr at the maximum
    listed infusion rate.

Hard ceiling:
    KCl IV infusion rate must not exceed 0.5 mEq/kg/hr. This is an
    absolute limit per DiBartola; exceeding it requires continuous ECG
    monitoring and is outside the scope of this calculator. The DKA
    literature notes safe use up to 0.9 mEq/kg/hr in human patients, but
    we do not encode that exception here.

Concentration ceiling:
    KCl concentration in IV fluid should not exceed 60 mEq/L in peripheral
    veins (vein irritation/sclerosis above this). The table's 80 mEq/L
    row exceeds this; central line is preferred for K <2.0 if 80 mEq/L
    is used. Subcutaneous route should not exceed 35 mEq/L.

The calculator:
    - Takes patient weight, serum K, and bag size (250 mL or 1 L)
    - Looks up the appropriate row from the table
    - Returns: total mEq KCl to add to bag, resulting concentration,
      max safe pump rate (in mL/hr) for THIS patient based on weight
    - Warns when the patient is in a band that requires central line,
      or when serum K is normal (no supplementation needed).

Pattern-only output. No treatment recommendations beyond what
DiBartola publishes. The veterinarian decides whether to act.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# ---------------------------------------------------------------------------
# DiBartola Table 5-2, encoded verbatim
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HypokalemiaScaleRow:
    """One row of the DiBartola Table 5-2 sliding scale."""

    k_min: float | None  # serum K (mEq/L) lower bound, inclusive. None = open.
    k_max: float  # serum K upper bound, inclusive
    label: str  # display string for this band
    kcl_per_liter: int  # mEq KCl per 1 L bag
    kcl_per_250ml: int  # mEq KCl per 250 mL bag
    max_rate_ml_per_kg_per_hr: int  # so total K stays ≤ 0.5 mEq/kg/hr


# Verbatim from DiBartola Ch. 5, Table 5-2 (p. 107)
HYPOKALEMIA_SCALE: tuple[HypokalemiaScaleRow, ...] = (
    HypokalemiaScaleRow(
        k_min=None,
        k_max=2.0,
        label="< 2.0",
        kcl_per_liter=80,
        kcl_per_250ml=20,
        max_rate_ml_per_kg_per_hr=6,
    ),
    HypokalemiaScaleRow(
        k_min=2.1,
        k_max=2.5,
        label="2.1–2.5",
        kcl_per_liter=60,
        kcl_per_250ml=15,
        max_rate_ml_per_kg_per_hr=8,
    ),
    HypokalemiaScaleRow(
        k_min=2.6,
        k_max=3.0,
        label="2.6–3.0",
        kcl_per_liter=40,
        kcl_per_250ml=10,
        max_rate_ml_per_kg_per_hr=12,
    ),
    HypokalemiaScaleRow(
        k_min=3.1,
        k_max=3.5,
        label="3.1–3.5",
        kcl_per_liter=28,
        kcl_per_250ml=7,
        max_rate_ml_per_kg_per_hr=18,
    ),
    HypokalemiaScaleRow(
        k_min=3.6,
        k_max=5.0,
        label="3.6–5.0",
        kcl_per_liter=20,
        kcl_per_250ml=5,
        max_rate_ml_per_kg_per_hr=25,
    ),
)

# Hard ceilings used for safety checks
KCL_RATE_CEILING_MEQ_PER_KG_HR = 0.5
PERIPHERAL_CONCENTRATION_CEILING_MEQ_PER_L = 60
SUBCUTANEOUS_CONCENTRATION_CEILING_MEQ_PER_L = 35


class BagSize(str, Enum):
    BAG_250 = "250"
    BAG_1000 = "1000"


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class HypokalemiaInputs:
    weight_value: float
    weight_unit: WeightUnit
    serum_k_meq_per_l: float
    bag_size: BagSize = BagSize.BAG_1000


@dataclass
class HypokalemiaResult:
    weight_kg: float
    serum_k: float
    bag_size_ml: int

    # Matched scale row (None if K is above the table's range, i.e. patient
    # is not hypokalemic and the calculator returns guidance to that effect)
    matched_row: HypokalemiaScaleRow | None
    band_label: str

    # Computed values for the chosen bag
    kcl_to_add_meq: int  # total mEq KCl to add to the bag
    final_concentration_meq_per_l: float

    # Maximum IV pump rate for THIS patient: weight * (max_rate_ml_per_kg_per_hr)
    max_pump_rate_ml_per_hr: float
    # The implied K delivery rate at the max pump rate, for cross-check
    delivered_k_rate_meq_per_kg_per_hr: float

    # Status flags
    no_supplementation_needed: bool
    above_table_range: bool  # patient's K > 5.0
    central_line_recommended: bool  # concentration > 60 mEq/L

    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------------------
    # Computation
    # ---------------------------------------------------------------------------
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _match_row(serum_k: float) -> HypokalemiaScaleRow | None:
    """Return the matching row for a given serum K, or None if K > 5.0.

    DiBartola's Table 5-2 has small gaps between rows (e.g. K=2.05 falls
    between the <2.0 and 2.1–2.5 rows). For real-world patient values that
    fall in those gaps, we fall to the next-lower band (i.e., treat as the
    more severely hypokalemic of the two adjacent rows), the conservative
    clinical choice. If the result is K > 5.0, return None.
    """
    if serum_k > 5.0:
        return None
    # First, exact-match pass
    for row in HYPOKALEMIA_SCALE:
        lower_ok = (row.k_min is None) or (serum_k >= row.k_min)
        upper_ok = serum_k <= row.k_max
        if lower_ok and upper_ok:
            return row
    # Gap fallback: when input falls between two bands (e.g., K=2.05 between
    # the <2.0 and 2.1–2.5 rows), fall to the more severely-hypokalemic of
    # the two adjacent bands, i.e., the one whose upper bound is the closest
    # below the input. This is the conservative clinical choice.
    candidates = [r for r in HYPOKALEMIA_SCALE if serum_k > r.k_max]
    if candidates:
        # Pick the row with the highest k_max, i.e., the band immediately
        # below the input.
        return max(candidates, key=lambda r: r.k_max)
    return None


def compute_hypokalemia(inputs: HypokalemiaInputs) -> HypokalemiaResult:
    notes: list[str] = []
    warnings: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    bag_ml = 250 if inputs.bag_size == BagSize.BAG_250 else 1000

    # Validate first. Math on a non-positive weight or K produces a
    # nonsensical pump rate; refuse to compute.
    errors: list[str] = []
    if weight_kg <= 0:
        errors.append("Weight must be greater than zero.")
    if inputs.serum_k_meq_per_l <= 0:
        errors.append("Serum potassium must be greater than zero.")
    if errors:
        return HypokalemiaResult(
            weight_kg=weight_kg,
            serum_k=inputs.serum_k_meq_per_l,
            bag_size_ml=bag_ml,
            matched_row=None,
            band_label="",
            kcl_to_add_meq=0,
            final_concentration_meq_per_l=0.0,
            max_pump_rate_ml_per_hr=0.0,
            delivered_k_rate_meq_per_kg_per_hr=0.0,
            no_supplementation_needed=False,
            above_table_range=False,
            central_line_recommended=False,
            notes=[],
            warnings=errors,
            sources=HYPOKALEMIA_SOURCES,
            valid=False,
        )

    row = _match_row(inputs.serum_k_meq_per_l)
    above_range = inputs.serum_k_meq_per_l > 5.0
    no_supp_needed = False

    # Patient's K is not hypokalemic
    if above_range:
        no_supp_needed = True
        notes.append(
            f"Serum potassium ({inputs.serum_k_meq_per_l} mEq/L) exceeds the "
            f"upper bound of DiBartola's hypokalemia supplementation scale (5.0 mEq/L). "
            f"This patient does not have hypokalemia. If serum K > 5.5 mEq/L, "
            f"consider hyperkalemia evaluation."
        )
        return HypokalemiaResult(
            weight_kg=round(weight_kg, 2),
            serum_k=inputs.serum_k_meq_per_l,
            bag_size_ml=bag_ml,
            matched_row=None,
            band_label="above table range",
            kcl_to_add_meq=0,
            final_concentration_meq_per_l=0.0,
            max_pump_rate_ml_per_hr=0.0,
            delivered_k_rate_meq_per_kg_per_hr=0.0,
            no_supplementation_needed=True,
            above_table_range=True,
            central_line_recommended=False,
            notes=notes,
            warnings=warnings,
            sources=HYPOKALEMIA_SOURCES,
        )

    # row should always be set here, but defensive fallback
    if row is None:
        warnings.append(
            f"Serum potassium {inputs.serum_k_meq_per_l} did not match any "
            f"row in the sliding-scale table. Check input."
        )
        return HypokalemiaResult(
            weight_kg=round(weight_kg, 2),
            serum_k=inputs.serum_k_meq_per_l,
            bag_size_ml=bag_ml,
            matched_row=None,
            band_label="no match",
            kcl_to_add_meq=0,
            final_concentration_meq_per_l=0.0,
            max_pump_rate_ml_per_hr=0.0,
            delivered_k_rate_meq_per_kg_per_hr=0.0,
            no_supplementation_needed=False,
            above_table_range=False,
            central_line_recommended=False,
            notes=notes,
            warnings=warnings,
            sources=HYPOKALEMIA_SOURCES,
        )

    # Lookup KCl per chosen bag size
    kcl_to_add = row.kcl_per_250ml if inputs.bag_size == BagSize.BAG_250 else row.kcl_per_liter

    # Resulting concentration in the bag
    concentration = (kcl_to_add * 1000) / bag_ml  # mEq/L

    # Max pump rate for THIS patient (per DiBartola's column)
    max_pump_rate = weight_kg * row.max_rate_ml_per_kg_per_hr if weight_kg > 0 else 0.0

    # Cross-check: at that max pump rate, what's the K delivery rate per kg per hr?
    if weight_kg > 0:
        # mL/hr × (mEq/L / 1000) = mEq/hr; divide by kg
        delivered_rate = (max_pump_rate * concentration / 1000) / weight_kg
    else:
        delivered_rate = 0.0

    # Safety flags
    central_line = concentration > PERIPHERAL_CONCENTRATION_CEILING_MEQ_PER_L
    if central_line:
        warnings.append(
            f"Resulting KCl concentration is {concentration:.0f} mEq/L, exceeds "
            f"the {PERIPHERAL_CONCENTRATION_CEILING_MEQ_PER_L} mEq/L peripheral-vein "
            f"ceiling. Use a central line to avoid pain and vein sclerosis. "
            f"Subcutaneous route is contraindicated above "
            f"{SUBCUTANEOUS_CONCENTRATION_CEILING_MEQ_PER_L} mEq/L."
        )

    # Cross-check delivery rate against the 0.5 mEq/kg/hr safety ceiling.
    # DiBartola's table is hand-tuned to ≈0.48 mEq/kg/hr per row, but
    # rounding produces values up to ~0.504. Tolerance is 0.01 above the
    # nominal ceiling.
    if delivered_rate > KCL_RATE_CEILING_MEQ_PER_KG_HR + 0.01:
        warnings.append(
            f"⚠ Computed delivery rate ({delivered_rate:.2f} mEq/kg/hr) exceeds "
            f"the {KCL_RATE_CEILING_MEQ_PER_KG_HR} mEq/kg/hr ceiling. Reduce "
            f"infusion rate or KCl supplementation."
        )

    # Standard notes
    notes.append(
        f"KCl IV infusion should not exceed "
        f"{KCL_RATE_CEILING_MEQ_PER_KG_HR} mEq/kg/hr to avoid cardiac toxicity. "
        f"At this patient's weight, the maximum pump rate is {max_pump_rate:.1f} mL/hr."
    )
    notes.append(
        "Mix the KCl thoroughly after addition to the bag, inadequate mixing "
        "has been shown to result in up to 4× concentration spikes at the "
        "outflow port."
    )
    notes.append(
        "DKA-specific exception (not encoded here): in DKA patients on insulin, "
        "rates up to 0.9 mEq/kg/hr have been reported in human literature with "
        "continuous ECG monitoring. InfusionFox enforces the 0.5 mEq/kg/hr ceiling."
    )
    notes.append(
        "Begin oral potassium supplementation as soon as the patient can "
        "tolerate it. Recheck serum K to guide therapy."
    )

    return HypokalemiaResult(
        weight_kg=round(weight_kg, 2),
        serum_k=inputs.serum_k_meq_per_l,
        bag_size_ml=bag_ml,
        matched_row=row,
        band_label=row.label,
        kcl_to_add_meq=kcl_to_add,
        final_concentration_meq_per_l=round(concentration, 1),
        max_pump_rate_ml_per_hr=round(max_pump_rate, 1),
        delivered_k_rate_meq_per_kg_per_hr=round(delivered_rate, 3),
        no_supplementation_needed=no_supp_needed,
        above_table_range=False,
        central_line_recommended=central_line,
        notes=notes,
        warnings=warnings,
        sources=HYPOKALEMIA_SOURCES,
    )


HYPOKALEMIA_SOURCES = (
    Source(
        citation=(
            "DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in Small "
            "Animal Practice, 4th ed. Elsevier, 2012. Chapter 5 (Disorders of "
            "Potassium). KCl supplementation sliding scale based on serum K, 0.5 "
            "mEq/kg/hr maximum infusion rate ceiling, and peripheral vs central "
            "concentration limits."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, potassium chloride monograph. "
            "Compatibility, peripheral concentration limits, dosing, and adverse "
            "effect profile."
        )
    ),
)

HYPOKALEMIA_CATALOG_ENTRY = {
    "slug": "hypokalemia",
    "display_name": "Hypokalemia / KCl supplementation",
    "short_name": "KCl",
    "category": "Electrolytes & Fluids",
    "mechanism_summary": (
        "Recommends KCl supplementation per IV fluid bag based on serum "
        "potassium concentration. Computes maximum patient-specific "
        "pump rate to keep delivery ≤0.5 mEq/kg/hr."
    ),
    "indications_summary": (
        "IV potassium supplementation for hypokalemia in dogs and "
        "cats. Enter serum K and body weight; returns a "
        "KCl-supplemented fluid rate sized to the deficit and capped "
        "at the 0.5 mEq/kg/hr ceiling that prevents iatrogenic "
        "cardiac arrhythmia. Reserve for patients in whom oral "
        "repletion is inadequate, impossible, or too slow."
    ),
}
