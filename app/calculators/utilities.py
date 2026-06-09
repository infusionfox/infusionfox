"""
Utility calculators, pure math, no clinical judgment.

These are not drug calculators; they're reference tools that show up
alongside the main catalog. Weight conversion, dose-equivalent conversion,
fluid rate math, drop-factor math. Every formula here is arithmetic, not
clinical recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import LB_PER_KG

# ---------------------------------------------------------------------------
# Unit converter
# ---------------------------------------------------------------------------


class WeightFromUnit(str, Enum):
    LB = "lb"
    KG = "kg"
    G = "g"
    OZ = "oz"


@dataclass
class WeightConversionResult:
    lb: float
    kg: float
    g: float
    oz: float


def convert_weight(value: float, from_unit: WeightFromUnit) -> WeightConversionResult:
    """Convert a single weight value to all four units."""
    if value <= 0:
        return WeightConversionResult(0, 0, 0, 0)

    if from_unit == WeightFromUnit.LB:
        kg = value / LB_PER_KG
    elif from_unit == WeightFromUnit.KG:
        kg = value
    elif from_unit == WeightFromUnit.G:
        kg = value / 1000
    elif from_unit == WeightFromUnit.OZ:
        kg = value / LB_PER_KG / 16
    else:
        raise ValueError(f"Unknown unit: {from_unit}")

    lb = kg * LB_PER_KG
    return WeightConversionResult(
        lb=round(lb, 3),
        kg=round(kg, 3),
        g=round(kg * 1000, 1),
        oz=round(lb * 16, 2),
    )


# ---------------------------------------------------------------------------
# Dose unit converter, mg ↔ µg ↔ mEq (where applicable)
# ---------------------------------------------------------------------------


@dataclass
class DoseAmountResult:
    mg: float
    ug: float
    g: float


def convert_dose_amount(value: float, from_unit: str) -> DoseAmountResult:
    """Convert a mass amount (not mEq, that's drug-specific)."""
    if value <= 0:
        return DoseAmountResult(0, 0, 0)
    if from_unit == "mg":
        mg = value
    elif from_unit == "ug":
        mg = value / 1000
    elif from_unit == "g":
        mg = value * 1000
    else:
        raise ValueError(f"Unknown unit: {from_unit}")
    return DoseAmountResult(mg=round(mg, 4), ug=round(mg * 1000, 2), g=round(mg / 1000, 6))


# ---------------------------------------------------------------------------
# Percent solution ↔ mg/mL
# ---------------------------------------------------------------------------


def percent_to_mg_per_ml(percent: float) -> float:
    """A w/v % is grams per 100 mL, so percent × 10 = mg/mL."""
    return percent * 10


def mg_per_ml_to_percent(mg_per_ml: float) -> float:
    return mg_per_ml / 10


# ---------------------------------------------------------------------------
# Dextrose / saline dilution preparation
# ---------------------------------------------------------------------------
#
# Common task in clinics that don't stock pre-made D5W bags: produce a target
# volume of a target dextrose concentration from a higher-percent stock and
# sterile water (or 0.9% NaCl, etc.).
#
# Formula is simple concentration × volume conservation:
#   stock_vol_ml = (target_vol_ml × target_pct) / stock_pct
#   diluent_vol_ml = target_vol_ml − stock_vol_ml
#
# Plumb's NE prep example: make 1 L of D5W → 100 mL of 50% dextrose +
# 900 mL sterile water. Verified: (1000 × 5) / 50 = 100 ✓.


@dataclass
class SolutionPrepInputs:
    target_volume_ml: float
    target_percent: float  # final concentration, e.g. 5 for D5W
    stock_percent: float  # stock concentration, e.g. 50 for 50% dextrose


@dataclass
class SolutionPrepResult:
    target_volume_ml: float
    target_percent: float
    stock_percent: float

    stock_volume_ml: float
    diluent_volume_ml: float

    final_mg_per_ml: float  # for cross-reference with drug calculations
    warnings: list[str] = field(default_factory=list)
    # See engine.CalcResult.valid for rationale. False when one or more
    # of target_volume / target_percent / stock_percent is non-positive,
    # or when target_percent >= stock_percent (no dilution possible).
    valid: bool = True


def compute_solution_prep(inputs: SolutionPrepInputs) -> SolutionPrepResult:
    """C1V1 = C2V2 where C is w/v percent and V is mL."""
    errors: list[str] = []

    if inputs.target_volume_ml <= 0:
        errors.append("Target volume must be greater than zero.")
    if inputs.target_percent <= 0:
        errors.append("Target concentration must be greater than zero.")
    if inputs.stock_percent <= 0:
        errors.append("Stock concentration must be greater than zero.")

    # Only compare relative magnitudes when both are positive; otherwise the
    # individual errors above already cover it.
    if (
        inputs.target_percent > 0
        and inputs.stock_percent > 0
        and inputs.target_percent >= inputs.stock_percent
    ):
        errors.append(
            f"Target concentration ({inputs.target_percent}%) must be lower "
            f"than the stock concentration ({inputs.stock_percent}%); "
            f"otherwise no dilution is happening."
        )

    if errors:
        return SolutionPrepResult(
            target_volume_ml=inputs.target_volume_ml,
            target_percent=inputs.target_percent,
            stock_percent=inputs.stock_percent,
            stock_volume_ml=0.0,
            diluent_volume_ml=0.0,
            final_mg_per_ml=0.0,
            warnings=errors,
            valid=False,
        )

    stock_vol = (inputs.target_volume_ml * inputs.target_percent) / inputs.stock_percent
    diluent_vol = inputs.target_volume_ml - stock_vol

    # Sanity warnings for unusual concentrations (only on valid inputs)
    warnings: list[str] = []
    if inputs.target_percent > 5 and inputs.target_percent <= 12.5:
        warnings.append(
            f"Final concentration of {inputs.target_percent}% dextrose is "
            f"hypertonic, for parenteral use, central venous access is "
            f"strongly preferred to avoid phlebitis."
        )
    elif inputs.target_percent > 12.5:
        warnings.append(
            f"⚠ Final concentration of {inputs.target_percent}% dextrose is "
            f"highly hypertonic. Use central venous access only and consult "
            f"a hospital pharmacist or clinical reference before "
            f"administering."
        )

    return SolutionPrepResult(
        target_volume_ml=inputs.target_volume_ml,
        target_percent=inputs.target_percent,
        stock_percent=inputs.stock_percent,
        stock_volume_ml=round(stock_vol, 2),
        diluent_volume_ml=round(diluent_vol, 2),
        final_mg_per_ml=percent_to_mg_per_ml(inputs.target_percent),
        warnings=warnings,
        valid=True,
    )


# ---------------------------------------------------------------------------
# Drop factor → mL/hr or drops/sec
# ---------------------------------------------------------------------------


@dataclass
class DropFactorInputs:
    ml_per_hour: float
    drop_factor: int  # drops per mL, typical: 10, 15, 20, 60 (microdrip)


@dataclass
class DropFactorResult:
    ml_per_hour: float
    drop_factor: int
    drops_per_minute: float
    drops_per_minute_whole: int
    seconds_per_drop: float
    notes: list[str] = field(default_factory=list)
    # See engine.CalcResult.valid for rationale.
    warnings: list[str] = field(default_factory=list)
    valid: bool = True


def compute_drop_factor(inputs: DropFactorInputs) -> DropFactorResult:
    """Convert mL/hr to drops/minute for gravity-drip sets without pumps."""
    errors: list[str] = []
    if inputs.ml_per_hour <= 0:
        errors.append("Rate must be greater than zero.")
    if inputs.drop_factor <= 0:
        errors.append("Drop factor must be greater than zero.")

    if errors:
        return DropFactorResult(
            ml_per_hour=inputs.ml_per_hour,
            drop_factor=inputs.drop_factor,
            drops_per_minute=0.0,
            drops_per_minute_whole=0,
            seconds_per_drop=0.0,
            notes=errors,
            warnings=errors,
            valid=False,
        )

    # (mL/hr × drops/mL) / 60 min/hr = drops/min
    drops_per_minute = (inputs.ml_per_hour * inputs.drop_factor) / 60
    seconds_per_drop = 60 / drops_per_minute if drops_per_minute > 0 else 0.0

    return DropFactorResult(
        ml_per_hour=inputs.ml_per_hour,
        drop_factor=inputs.drop_factor,
        drops_per_minute=round(drops_per_minute, 2),
        drops_per_minute_whole=round(drops_per_minute),
        seconds_per_drop=round(seconds_per_drop, 2),
        notes=[],
        warnings=[],
        valid=True,
    )


# ---------------------------------------------------------------------------
# Body surface area (BSA)
# ---------------------------------------------------------------------------
#
# BSA is used in oncology dosing for many chemotherapeutic agents. Two
# species-specific allometric formulas are standard in veterinary practice:
#
#   Dogs: BSA (m^2) = K * weight(kg)^(2/3) / 100, with K = 10.1
#   Cats: BSA (m^2) = K * weight(kg)^(2/3) / 100, with K = 10.0
#
# These constants come from the original allometric scaling work by Brody
# (1945) refined by subsequent feline-specific studies. The exponent 2/3
# reflects surface-area scaling; the K constant differs slightly between
# species because cats have proportionally less body surface for their mass.
#
# Note: BSA-based dosing has fallen out of favor for some chemotherapeutic
# agents (especially in cats and small dogs <10 kg) because the relationship
# between BSA and drug clearance is nonlinear in those weight ranges. Many
# protocols now use mg/kg or per-cat fixed dosing for small patients. The
# converter computes BSA but the user is responsible for selecting the
# appropriate dosing convention for the agent in question.

BSA_K_DOG = 10.1
BSA_K_CAT = 10.0


@dataclass
class BsaResult:
    weight_kg: float
    species: str  # "dog" or "cat"
    bsa_m2: float


def compute_bsa(weight_kg: float, species: str) -> BsaResult:
    if weight_kg <= 0:
        return BsaResult(weight_kg=0.0, species=species, bsa_m2=0.0)
    k = BSA_K_DOG if species == "dog" else BSA_K_CAT
    bsa = k * (weight_kg ** (2 / 3)) / 100
    return BsaResult(
        weight_kg=round(weight_kg, 3),
        species=species,
        bsa_m2=round(bsa, 4),
    )


# ---------------------------------------------------------------------------
# Concentration converter (% w/v <-> mg/mL <-> ug/mL <-> mEq/mL)
# ---------------------------------------------------------------------------


@dataclass
class ConcentrationResult:
    input_value: float
    input_unit: str
    percent: float
    mg_per_ml: float
    ug_per_ml: float
    mg_per_ml_label: str  # eg "5 mg/mL"


def convert_concentration(value: float, from_unit: str) -> ConcentrationResult:
    """Convert between %, mg/mL, ug/mL.

    % w/v means grams per 100 mL, so 1% = 10 mg/mL.
    """
    if value <= 0:
        return ConcentrationResult(0, from_unit, 0.0, 0.0, 0.0, "0 mg/mL")

    if from_unit == "percent":
        mg_per_ml = value * 10
    elif from_unit == "mg_per_ml":
        mg_per_ml = value
    elif from_unit == "ug_per_ml":
        mg_per_ml = value / 1000
    else:
        raise ValueError(f"Unknown concentration unit: {from_unit}")

    percent = mg_per_ml / 10
    ug_per_ml = mg_per_ml * 1000

    # Format mg_per_ml label nicely
    if mg_per_ml >= 1:
        label = f"{mg_per_ml:g} mg/mL"
    else:
        label = f"{ug_per_ml:g} µg/mL"

    return ConcentrationResult(
        input_value=value,
        input_unit=from_unit,
        percent=round(percent, 4),
        mg_per_ml=round(mg_per_ml, 4),
        ug_per_ml=round(ug_per_ml, 2),
        mg_per_ml_label=label,
    )
