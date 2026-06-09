"""
Energy requirements calculator: maintenance and weight loss only.

Computes RER and target daily caloric intake for two purposes:
  - Maintenance / weight maintenance
  - Weight loss

Previous versions also handled weight gain in inappetent / hospitalized
patients, neonatal hand-rearing of orphan puppies and kittens, and
post-weaning growth. Those purposes were removed to keep the calculator
focused on the two cases practitioners reach for most often in general
practice. Inappetent / refeeding patients should start at RER directly
(no calculator needed); growth and neonatal feeding plans benefit from
the full age-band and milk-replacer guidance found in pediatric texts.

Sources:
  - Ettinger SJ, Feldman EC, Côté E, eds. Textbook of Veterinary Internal
    Medicine. 9th ed. St. Louis, MO: Elsevier; 2024.
      * Ch. 147 (Nutrition for Healthy Adult Dogs), Box 147.1, dog RER/MER
      * Ch. 150 (Obesity). IBW-based weight-loss formulas (dog and cat)
  - National Research Council, Committee on Animal Nutrition. Nutrient
    Requirements of Dogs and Cats. Washington, DC: National Academies Press;
    2006.
      * Energy chapter (Ch. 3), p. 95, adult cat MER equations

RER (Resting Energy Requirement), universal allometric formula:
    RER = 70 × BW(kg)^0.75

A linear approximation `70 × BW + 30` exists for BW 2–25 kg only and
overestimates outside that range. The calculator always uses the
allometric formula.

Maintenance (MER), adult dogs, multiplier of RER (Ettinger Ch. 147):
    Inactive (neutered, indoor):       1.4 × RER (NRC: 95 × BW^0.75 ≈ 1.36)
    Typical adult dog:                 1.5 × RER
    Active / kenneled:                 1.85 × RER (NRC: 130 × BW^0.75)
    Working / racing / hunting:        2.5 × RER (variable; estimate only)

Maintenance (MER), adult cats, NRC 2006 direct equations (NOT RER × factor):
    Lean cats (BCS ≤ 5/9):            100 × BW^0.67 kcal/day
    Overweight cats (BCS > 5/9):      130 × BW^0.4  kcal/day

Weight loss, uses ideal body weight (IBW), not current weight (Ettinger Ch. 150):
    Dogs:   63 × IBW(kg)^0.75   (±10.2 SD; floor 42.6 × IBW^0.75)
    Cats:   52 × IBW(kg)^0.711  (±4.9 SD;  floor 42.2 × IBW^0.711)
    Reassess every 2–4 weeks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg


class EnergyPurpose(str, Enum):
    MAINTENANCE = "maintenance"
    WEIGHT_LOSS = "weight_loss"


class EnergySpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


class FoodForm(str, Enum):
    """Form of food being fed, drives serving units and labeling."""

    DRY = "dry"  # measured in cups
    CANNED = "canned"  # measured in cans


class CaloricDensityUnit(str, Enum):
    """Units the user can enter caloric density in. Matches typical pet-food
    bag labels: bags publish kcal/cup, cans publish kcal/can."""

    KCAL_PER_CUP = "kcal_per_cup"
    KCAL_PER_CAN = "kcal_per_can"


# Laflamme 1997 BCS-to-bodyweight conversion: each point above 5/9 = ~10%
# above ideal weight. Used to estimate IBW from current weight + BCS.
# A BCS of 5 is ideal, so percent_over_ideal = 0 at BCS 5.
# Reference: Laflamme DP. Development and validation of a body condition
# score system for cats. Feline Pract. 1997;25(5-6):13-18.
# Standard clinical convention is 10% per BCS unit above 5; capped at 40% (BCS 9).
def estimate_ibw_kg(current_weight_kg: float, bcs: int) -> float | None:
    """Return estimated ideal weight from current weight and BCS, or None if
    BCS is at or below ideal (5/9) or out of range."""
    if bcs is None or bcs < 1 or bcs > 9:
        return None
    if bcs <= 5:
        return None  # patient is at or below ideal, no weight loss target
    pct_over = (bcs - 5) * 10  # 6→10%, 7→20%, 8→30%, 9→40%
    return current_weight_kg / (1 + pct_over / 100)


# ---------------------------------------------------------------------------
# Maintenance multipliers. RER × factor for dogs; direct equations for cats.
# Per Ettinger Ch. 147 (dogs) and NRC 2006 (cats).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaintenanceFactor:
    key: str
    label: str
    multiplier: float
    description: str


DOG_MAINTENANCE: tuple[MaintenanceFactor, ...] = (
    MaintenanceFactor(
        "inactive_neutered",
        "Inactive / neutered indoor",
        1.4,
        "Sedentary, neutered, indoor pet dog. NRC 2006 inactive equation: "
        "95 × BW^0.75 ≈ 1.36 × RER. InfusionFox uses 1.4 as a rounded value.",
    ),
    MaintenanceFactor(
        "typical_pet",
        "Typical adult pet dog",
        1.5,
        "Standard adult pet dog with normal daily activity. Within the "
        "Ettinger Ch. 147 stated range of 'RER × 1.4–1.6 used to determine "
        "adult MERs.' Specific 1.5 multiplier is clinical convention.",
    ),
    MaintenanceFactor(
        "active",
        "Active / outdoor / kenneled",
        1.85,
        "Active dogs with regular exercise. NRC 2006 active/kenneled equation: 130 × BW^0.75 ≈ 1.85 × RER.",
    ),
    MaintenanceFactor(
        "working",
        "Working / racing / hunting",
        2.5,
        "Working dogs with sustained heavy exercise. Multiplier is "
        "highly variable per Ettinger Ch. 147; 2.5 is a starting estimate, "
        "adjust based on body condition. Not a published NRC value.",
    ),
)

# Cat MER per NRC 2006 (Nutrient Requirements of Dogs and Cats, p. 95).
# NRC publishes two equations keyed to body condition score, NOT activity
# factors, they note (p. 93) that "factors such as activity level, breed,
# or age have clear-cut effects on energy requirements [in dogs] but the
# effects of such factors are much less obvious in cats."
#
# These are equations, not RER-multipliers. The MaintenanceFactor dataclass
# below uses `multiplier` purely to satisfy the existing schema; the actual
# computation uses CAT_MER_EQUATIONS (see below).
CAT_MAINTENANCE: tuple[MaintenanceFactor, ...] = (
    MaintenanceFactor(
        "lean",
        "Lean (BCS ≤ 5/9)",
        0.0,  # unused, actual calc uses CAT_MER_EQUATIONS
        "MER = 100 × BW^0.67 kcal/day. NRC 2006 recommended for lean cats.",
    ),
    MaintenanceFactor(
        "overweight",
        "Overweight (BCS > 5/9)",
        0.0,  # unused, actual calc uses CAT_MER_EQUATIONS
        "MER = 130 × BW^0.4 kcal/day. NRC 2006 uses a lower mass exponent "
        "for overweight cats, adipose tissue is metabolically less active "
        "than lean tissue, so per-kg requirements drop with body fat.",
    ),
)


@dataclass(frozen=True)
class CatMEREquation:
    key: str
    coefficient: float  # the X in X × BW^Y
    exponent: float  # the Y
    label: str  # for display
    formula_text: str  # human-readable form, e.g. "100 × BW^0.67"


CAT_MER_EQUATIONS: dict[str, CatMEREquation] = {
    "lean": CatMEREquation("lean", 100.0, 0.67, "Lean (BCS ≤ 5/9)", "100 × BW^0.67"),
    "overweight": CatMEREquation("overweight", 130.0, 0.40, "Overweight (BCS > 5/9)", "130 × BW^0.4"),
}


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class EnergyInputs:
    species: EnergySpecies
    purpose: EnergyPurpose
    current_weight_value: float
    current_weight_unit: WeightUnit
    # Ideal body weight, used for weight-loss target. Optional; if not set
    # but BCS is, the calculator estimates IBW from BCS.
    ideal_weight_value: float | None = None
    ideal_weight_unit: WeightUnit = WeightUnit.LB
    # Body condition score on 9-point Laflamme scale (1-9). 5 = ideal.
    # When set on weight_loss with no IBW provided, used to estimate IBW.
    bcs: int | None = None
    # For maintenance: the activity factor key (matches MaintenanceFactor.key)
    maintenance_factor_key: str = "typical_pet"
    # Food details, optional. When provided, calculator returns volume targets.
    food_form: FoodForm | None = None
    caloric_density: float | None = None  # numeric kcal value
    caloric_density_unit: CaloricDensityUnit | None = None
    meals_per_day: int = 2  # used to split daily target


@dataclass
class FoodVolumeTarget:
    """Daily and per-meal food volume needed to deliver the target kcal."""

    form: FoodForm
    caloric_density: float
    caloric_density_unit: CaloricDensityUnit
    daily_servings: float  # in 'cups' for dry, 'cans' for canned
    daily_grams: float | None  # optional gram approximation (cups only)
    per_meal_servings: float
    meals_per_day: int


@dataclass
class EnergyResult:
    species: EnergySpecies
    purpose: EnergyPurpose
    current_weight_kg: float
    ideal_weight_kg: float | None
    ideal_weight_source: str  # "user-entered" / "estimated from BCS x" / "n/a"

    rer_kcal_per_day: float
    target_kcal_per_day: float
    formula_used: str
    formula_human: str  # human-readable formula with values plugged in

    # The chosen maintenance factor (only meaningful for MAINTENANCE)
    maintenance_factor: MaintenanceFactor | None

    # For weight loss: the floor below which we shouldn't go
    minimum_kcal_per_day: float | None = None

    # Food volume target (when food details supplied)
    food_volume: FoodVolumeTarget | None = None

    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _compute_food_volume(
    target_kcal: float,
    form: FoodForm,
    density: float,
    unit: CaloricDensityUnit,
    meals_per_day: int,
) -> FoodVolumeTarget | None:
    """Convert a daily kcal target into food volume per day and per meal."""
    if target_kcal <= 0 or density <= 0 or meals_per_day < 1:
        return None
    # density is kcal per serving (cup or can). daily servings = target / density
    daily = target_kcal / density
    per_meal = daily / meals_per_day
    return FoodVolumeTarget(
        form=form,
        caloric_density=density,
        caloric_density_unit=unit,
        daily_servings=round(daily, 2),
        daily_grams=None,  # we don't have weight conversion without explicit g/cup info
        per_meal_servings=round(per_meal, 2),
        meals_per_day=meals_per_day,
    )


def _rer_allometric(weight_kg: float) -> float:
    """RER = 70 × BW^0.75, universal allometric form. Ettinger Ch. 147 Box 147.1."""
    return 70.0 * (weight_kg**0.75)


def _maintenance_factor(species: EnergySpecies, key: str) -> MaintenanceFactor:
    options = DOG_MAINTENANCE if species == EnergySpecies.DOG else CAT_MAINTENANCE
    for f in options:
        if f.key == key:
            return f
    return options[1]  # default to "typical"


def compute_energy_requirements(inputs: EnergyInputs) -> EnergyResult:
    notes: list[str] = []
    warnings: list[str] = []

    cur_kg = _to_kg(inputs.current_weight_value, inputs.current_weight_unit)
    ideal_kg = (
        _to_kg(inputs.ideal_weight_value, inputs.ideal_weight_unit)
        if inputs.ideal_weight_value is not None and inputs.ideal_weight_value > 0
        else None
    )

    # Validate. Math on a non-positive weight produces a meaningless RER
    # and kcal target; refuse to compute.
    if cur_kg <= 0:
        return EnergyResult(
            species=inputs.species,
            purpose=inputs.purpose,
            current_weight_kg=cur_kg,
            ideal_weight_kg=None,
            ideal_weight_source="n/a",
            rer_kcal_per_day=0.0,
            target_kcal_per_day=0.0,
            formula_used="",
            formula_human="",
            maintenance_factor=None,
            warnings=["Current weight must be greater than zero."],
            sources=ENERGY_SOURCES,
            valid=False,
        )

    rer = _rer_allometric(cur_kg)

    # If no IBW supplied but BCS is, estimate IBW from BCS.
    ideal_weight_source = "n/a"
    if ideal_kg is not None:
        ideal_weight_source = "user-entered"
    elif inputs.bcs is not None and inputs.bcs > 5:
        estimated = estimate_ibw_kg(cur_kg, inputs.bcs)
        if estimated is not None:
            ideal_kg = estimated
            ideal_weight_source = (
                f"estimated from BCS {inputs.bcs}/9 (Laflamme: each unit above 5 ≈ 10% over ideal)"
            )

    target = 0.0
    formula_used = ""
    formula_human = ""
    maint_factor: MaintenanceFactor | None = None
    minimum: float | None = None

    if inputs.purpose == EnergyPurpose.MAINTENANCE:
        if inputs.species == EnergySpecies.CAT:
            # Cats use NRC 2006 equations directly (no RER × multiplier).
            # Two equations keyed to body condition score.
            eq = CAT_MER_EQUATIONS.get(inputs.maintenance_factor_key)
            if eq is None:
                eq = CAT_MER_EQUATIONS["lean"]
            target = eq.coefficient * (cur_kg**eq.exponent)
            # Synthesize a MaintenanceFactor for display / result panel
            maint_factor = MaintenanceFactor(
                key=eq.key,
                label=eq.label,
                multiplier=0.0,  # not meaningful for cats
                description=f"NRC 2006: MER = {eq.formula_text} kcal/day",
            )
            formula_used = f"MER = {eq.formula_text} (NRC 2006)"
            formula_human = (
                f"MER = {eq.coefficient} × {cur_kg:.2f}^{eq.exponent} = {target:.0f} kcal/day ({eq.label})"
            )
            notes.append(
                "Per NRC 2006 (Nutrient Requirements of Dogs and Cats, p. 95): "
                "lean cats use 100 × BW^0.67; overweight cats use 130 × BW^0.4. "
                "The lower exponent for overweight cats reflects that adipose "
                "tissue is less metabolically active than lean tissue."
            )
            notes.append(
                "NRC notes activity factors are 'much less obvious' in cats "
                "than dogs; body condition is the primary driver of feline MER."
            )
            notes.append(
                "Neutered cats often need substantial caloric restriction; "
                "some require 30%+ less than pre-neuter intake (Ettinger 9th, "
                "Ch. 148). Portion-controlled feeding is preferred over "
                "free access. Reassess body weight and BCS regularly."
            )
        else:
            # Dogs: RER × activity multiplier (Ettinger Ch. 147 / NRC 2006)
            maint_factor = _maintenance_factor(inputs.species, inputs.maintenance_factor_key)
            target = rer * maint_factor.multiplier
            formula_used = "MER = RER × activity factor"
            formula_human = (
                f"RER = 70 × {cur_kg:.2f}^0.75 = {rer:.0f} kcal/day; "
                f"MER = {rer:.0f} × {maint_factor.multiplier} = {target:.0f} kcal/day "
                f"({maint_factor.label})"
            )

    elif inputs.purpose == EnergyPurpose.WEIGHT_LOSS:
        if ideal_kg is None or ideal_kg <= 0:
            warnings.append(
                "Weight loss target requires an ideal body weight (IBW). "
                "Estimate from BCS, typically 10–20% loss from current weight "
                "for BCS 7/9, 20–30% for BCS 8–9/9."
            )
            target = 0.0
            formula_used = "(IBW required for weight loss target)"
            formula_human = ""
        else:
            if inputs.species == EnergySpecies.DOG:
                target = 63.0 * (ideal_kg**0.75)
                minimum = 42.6 * (ideal_kg**0.75)
                formula_used = "Target = 63 × IBW^0.75 (dog, Ettinger Ch. 150)"
                formula_human = (
                    f"63 × {ideal_kg:.1f}^0.75 = {target:.0f} kcal/day (minimum {minimum:.0f} kcal/day)"
                )
            else:
                target = 52.0 * (ideal_kg**0.711)
                minimum = 42.2 * (ideal_kg**0.711)
                formula_used = "Target = 52 × IBW^0.711 (cat, Ettinger Ch. 150)"
                formula_human = (
                    f"52 × {ideal_kg:.1f}^0.711 = {target:.0f} kcal/day (minimum {minimum:.0f} kcal/day)"
                )
            notes.append(
                "Reassess body weight every 2–4 weeks. Adjust caloric target "
                "by 10–20% based on actual loss vs target rate (1–2% of body "
                "weight per week for dogs, 0.5–1% for cats)."
            )
            notes.append(
                "Calculation uses ideal body weight, not current weight, this "
                "is intentional and matches Ettinger's recommendation."
            )

    # Optional: convert daily kcal target into food volume per day / per meal
    food_volume: FoodVolumeTarget | None = None
    if (
        target > 0
        and inputs.food_form is not None
        and inputs.caloric_density is not None
        and inputs.caloric_density > 0
        and inputs.caloric_density_unit is not None
    ):
        # Sanity-check unit/form consistency.
        unit_form_mismatch = (
            inputs.food_form == FoodForm.DRY
            and inputs.caloric_density_unit == CaloricDensityUnit.KCAL_PER_CAN
        ) or (
            inputs.food_form == FoodForm.CANNED
            and inputs.caloric_density_unit == CaloricDensityUnit.KCAL_PER_CUP
        )
        if unit_form_mismatch:
            notes.append(
                "Food form and caloric-density unit don't match (dry food is "
                "typically labeled in kcal/cup; canned in kcal/can). Verify "
                "you've entered the correct value off the label."
            )
        food_volume = _compute_food_volume(
            target_kcal=target,
            form=inputs.food_form,
            density=inputs.caloric_density,
            unit=inputs.caloric_density_unit,
            meals_per_day=inputs.meals_per_day,
        )

    return EnergyResult(
        species=inputs.species,
        purpose=inputs.purpose,
        current_weight_kg=round(cur_kg, 2),
        ideal_weight_kg=round(ideal_kg, 2) if ideal_kg is not None else None,
        ideal_weight_source=ideal_weight_source,
        rer_kcal_per_day=round(rer, 1),
        target_kcal_per_day=round(target, 1),
        formula_used=formula_used,
        formula_human=formula_human,
        maintenance_factor=maint_factor,
        minimum_kcal_per_day=round(minimum, 1) if minimum is not None else None,
        food_volume=food_volume,
        notes=notes,
        warnings=warnings,
        sources=ENERGY_SOURCES,
    )


ENERGY_SOURCES = (
    Source(
        citation=(
            "Freeman L, Becvarova I, Cave N, et al. WSAVA Global Nutrition "
            "Committee: Nutritional assessment guidelines. J Small Anim Pract "
            "2011;52:385–396. (RER and MER framework; BCS-driven target weight.)"
        )
    ),
    Source(
        citation=(
            "Ettinger SJ, Feldman EC, Côté E, eds. Textbook of Veterinary Internal "
            "Medicine. 9th ed. Elsevier, 2024. Ch. 147 (Nutrition for healthy "
            "adult dogs, RER and MER) and Ch. 150 (Obesity, IBW-based weight-loss "
            "formulas)."
        )
    ),
    Source(
        citation=(
            "National Research Council. Nutrient Requirements of Dogs and Cats. "
            "National Academies Press, 2006. (Adult cat MER equations p. 95; "
            "dog activity-factor equations.)"
        )
    ),
    Source(
        citation=(
            "Laflamme DP. Development and validation of a body condition score "
            "system for cats. Feline Pract 1997;25(5-6):13–18. (9-point BCS scale, "
            "10% per unit above 5 = ~percent over ideal weight, used to estimate "
            "IBW when not directly known.)"
        )
    ),
)

ENERGY_CATALOG_ENTRY = {
    "slug": "energy-requirements",
    "display_name": "Energy requirements (RER / MER)",
    "short_name": "RER",
    "category": "Nutrition",
    "mechanism_summary": (
        "Calculates resting energy requirement (RER) and target daily caloric "
        "intake for adult dogs and cats. Two purposes: maintenance (using "
        "Ettinger Ch. 147 activity factors for dogs; NRC 2006 body-condition "
        "equations for cats) and weight loss (Ettinger Ch. 150 IBW-based "
        "formulas)."
    ),
    "indications_summary": (
        "Daily caloric target for adult dogs and cats: routine maintenance "
        "and weight-loss programs. Pick the species, the purpose, and an "
        "optional food caloric density to get a concrete kcal-per-day target "
        "and a feeding plan."
    ),
}
