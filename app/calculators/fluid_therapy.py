"""
DKA fluid therapy calculator. Hoehne / Silverstein & Hopper Ch. 73, Box 73.1.

Combines the four fluid-therapy components for diabetic ketoacidosis:

    1. Shock bolus (if patient is in shock at presentation)
    2. Rehydration deficit (replaced over 4–24 hours)
    3. Maintenance fluid rate
    4. Ongoing losses (vomiting, osmotic polyuria, etc.)

Box 73.1 (verbatim):
    "If in shock, administer replacement isotonic crystalloid solutions
    rapidly in 10–30 mL/kg increments up to 90 mL/kg IV for dogs and
    up to 60 mL/kg IV for cats."

    "If dehydrated, calculate fluid amount to be replaced using the
    following formula: (body weight [kg] × 1000) × (% dehydration / 100)
    = deficit (mL)"

    "Rehydrate over 4–24 hours using replacement type isotonic
    crystalloids."

    "Continue maintenance rate fluid therapy at 2–4 mL/kg/hr ... and
    replace ongoing losses."

Math:
    deficit_mL  = weight_kg × (% dehydration) × 10
    rehydration_rate (mL/hr) = deficit_mL / window_hr
    maintenance_rate (mL/hr) = weight_kg × maintenance_factor
    total_active_rate (mL/hr) = rehydration_rate + maintenance_rate + ongoing_losses
    post_rehydration_rate (mL/hr) = maintenance_rate + ongoing_losses

Dehydration estimation per physical exam (DiBartola, standard veterinary
internal-medicine assessment):
    < 5%   not detectable on physical exam (subclinical)
    5–6%   dry/tacky mucous membranes; mild loss of skin elasticity
    6–8%   definite skin tenting; tacky-to-dry MM; eyes slightly sunken
    8–10%  persistent skin tent; dry MM; sunken eyes; weak pulses
    10–12% severe skin tent; cold extremities; signs of impending shock
    > 12%  moribund; severe shock

Fluid choice:
    Box 73.1 specifies "replacement type isotonic crystalloids."
    Either 0.9% NaCl or a buffered isotonic crystalloid (LRS, Plasma-Lyte
    148, Normosol-R) is acceptable. Hoehne notes recent evidence favoring
    buffered solutions for faster acidosis resolution and reduced
    hyperchloremia. The calculator does not pick the fluid for the user;
    it surfaces both options in the page text.

Important: this is the FLUID portion of DKA management only. Insulin
runs through a SEPARATE line. The DKA sliding scale dictates the
COMPOSITION of the fluid line when an insulin CRI is also running
(NaCl alone, NaCl + 2.5% dextrose, or NaCl + 5% dextrose), but the
RATE of that line is calculated by THIS calculator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Box 73.1 shock bolus ceilings
SHOCK_BOLUS_MAX_MLPK_DOG = 90.0
SHOCK_BOLUS_MAX_MLPK_CAT = 60.0
SHOCK_BOLUS_INCREMENT_LOW = 10.0
SHOCK_BOLUS_INCREMENT_HIGH = 30.0

# Maintenance range from Box 73.1
MAINTENANCE_MIN_MLPKG_HR = 2.0
MAINTENANCE_DEFAULT_MLPKG_HR = 3.0
MAINTENANCE_MAX_MLPKG_HR = 4.0

# Rehydration window range from Box 73.1
REHYDRATION_MIN_HR = 4
REHYDRATION_MAX_HR = 24
REHYDRATION_DEFAULT_HR = 12


class FluidTherapySpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class DehydrationBand:
    """Standard physical-exam dehydration band."""

    key: str
    label: str  # short label for the radio button
    description: str  # clinical description
    percent: float  # representative % for the math (midpoint of band)
    range_low: float
    range_high: float


# DiBartola-standard physical-exam dehydration bands. The "euhydrated"
# band is a InfusionFox addition: it lets the calculator build a maintenance-
# only plan for a clinically euhydrated patient (post-op recovery,
# inappetent without losses, etc.) without forcing the user to invent a
# phantom deficit. With percent=0 the deficit term drops out of the
# active-phase rate, and the result panel collapses to a single
# maintenance rate.
DEHYDRATION_BANDS: list[DehydrationBand] = [
    DehydrationBand(
        key="euhydrated",
        label="Euhydrated (0%)",
        description=(
            "No clinical evidence of dehydration. Use for maintenance-only "
            "plans: a patient who needs IV fluids for venous access, "
            "inappetence without losses, or post-operative support, but "
            "whose hydration status on exam is normal."
        ),
        percent=0.0,
        range_low=0.0,
        range_high=0.0,
    ),
    DehydrationBand(
        key="subclinical",
        label="< 5% (subclinical)",
        description=(
            "Not detectable on physical exam. History of fluid loss but "
            "normal mucous membranes, normal skin elasticity, normal "
            "eye position."
        ),
        percent=4.0,
        range_low=0.0,
        range_high=5.0,
    ),
    DehydrationBand(
        key="mild",
        label="5–6% (mild)",
        description=(
            "Dry or tacky mucous membranes; mild loss of skin elasticity. "
            "Patient appears clinically normal otherwise."
        ),
        percent=5.5,
        range_low=5.0,
        range_high=6.0,
    ),
    DehydrationBand(
        key="moderate",
        label="6–8% (moderate)",
        description=(
            "Definite skin tenting; tacky-to-dry mucous membranes; eyes "
            "slightly sunken. CRT may be slightly prolonged."
        ),
        percent=7.0,
        range_low=6.0,
        range_high=8.0,
    ),
    DehydrationBand(
        key="marked",
        label="8–10% (marked)",
        description=(
            "Persistent skin tent; dry mucous membranes; sunken eyes; "
            "weak pulses; cool extremities. Patient is depressed but "
            "still responsive."
        ),
        percent=9.0,
        range_low=8.0,
        range_high=10.0,
    ),
    DehydrationBand(
        key="severe",
        label="10–12% (severe)",
        description=(
            "Severe skin tent that does not return; cold extremities; "
            "weak or absent pulses; signs of impending shock (tachycardia, "
            "altered mentation). Aggressive resuscitation required."
        ),
        percent=11.0,
        range_low=10.0,
        range_high=12.0,
    ),
    DehydrationBand(
        key="moribund",
        label="> 12% (moribund)",
        description=(
            "Severe shock with cardiovascular collapse. The patient is "
            "obtunded or moribund. Immediate volume resuscitation is "
            "lifesaving, start with shock-bolus rates."
        ),
        percent=13.0,
        range_low=12.0,
        range_high=15.0,
    ),
]


def get_dehydration_band(key: str) -> DehydrationBand | None:
    for band in DEHYDRATION_BANDS:
        if band.key == key:
            return band
    return None


@dataclass
class FluidTherapyInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: FluidTherapySpecies
    in_shock: bool  # if true, surface shock-bolus output
    dehydration_band_key: str  # one of DEHYDRATION_BANDS keys
    rehydration_window_hr: int  # 4, 6, 12, or 24 (typical presets)
    maintenance_mlpkg_hr: float  # 2.0, 3.0, or 4.0
    ongoing_losses_ml_per_hr: float = 0.0


@dataclass
class FluidTherapyResult:
    weight_kg: float
    species: FluidTherapySpecies
    band: DehydrationBand
    dehydration_percent: float
    rehydration_window_hr: int
    maintenance_mlpkg_hr: float
    ongoing_losses_ml_per_hr: float

    # Shock bolus (only if in_shock is True)
    in_shock: bool
    shock_bolus_max_ml: float | None
    shock_increment_low_ml: float | None
    shock_increment_high_ml: float | None

    # Rehydration math
    deficit_ml: float
    rehydration_rate_ml_per_hr: float

    # Maintenance math
    maintenance_rate_ml_per_hr: float

    # Combined rates
    active_phase_rate_ml_per_hr: float  # rehydration + maintenance + ongoing
    post_rehydration_rate_ml_per_hr: float  # maintenance + ongoing only

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale. False when weight is
    # missing or non-positive. The template suppresses numeric output
    # when valid=False so a clinician never sees a negative deficit
    # alongside a "weight must be > 0" warning.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _invalid_fluid_therapy_result(
    inputs: FluidTherapyInputs,
    weight_kg: float,
    errors: list[str],
) -> FluidTherapyResult:
    """Build an invalid (zeroed) result when inputs fail validation."""
    band = get_dehydration_band(inputs.dehydration_band_key) or next(
        b for b in DEHYDRATION_BANDS if b.key == "moderate"
    )
    return FluidTherapyResult(
        weight_kg=weight_kg,
        species=inputs.species,
        band=band,
        dehydration_percent=band.percent,
        rehydration_window_hr=max(REHYDRATION_MIN_HR, inputs.rehydration_window_hr),
        maintenance_mlpkg_hr=inputs.maintenance_mlpkg_hr,
        ongoing_losses_ml_per_hr=max(0.0, inputs.ongoing_losses_ml_per_hr),
        in_shock=inputs.in_shock,
        shock_bolus_max_ml=None,
        shock_increment_low_ml=None,
        shock_increment_high_ml=None,
        deficit_ml=0.0,
        rehydration_rate_ml_per_hr=0.0,
        maintenance_rate_ml_per_hr=0.0,
        active_phase_rate_ml_per_hr=0.0,
        post_rehydration_rate_ml_per_hr=0.0,
        warnings=errors,
        notes=[],
        sources=FLUID_THERAPY_SOURCES,
        valid=False,
    )


def compute_fluid_therapy(inputs: FluidTherapyInputs) -> FluidTherapyResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)

    # Validate first. Math on a non-positive weight produces negative
    # deficits, negative rates, and a maintenance line that would
    # actively harm the patient if followed. Refuse to compute.
    if weight_kg <= 0:
        return _invalid_fluid_therapy_result(
            inputs,
            weight_kg,
            ["Weight must be greater than zero."],
        )

    band = get_dehydration_band(inputs.dehydration_band_key)
    if band is None:
        warnings.append(
            f"Unknown dehydration band '{inputs.dehydration_band_key}'. Defaulting to moderate (6–8%)."
        )
        band = next(b for b in DEHYDRATION_BANDS if b.key == "moderate")

    # Rehydration window, clamp to published range
    window_hr = inputs.rehydration_window_hr
    if window_hr < REHYDRATION_MIN_HR:
        warnings.append(
            f"Rehydration window of {window_hr} hours is below the published "
            f"minimum of 4 hours. Using {REHYDRATION_MIN_HR} hours instead."
        )
        window_hr = REHYDRATION_MIN_HR
    elif window_hr > REHYDRATION_MAX_HR:
        warnings.append(
            f"Rehydration window of {window_hr} hours is above the published "
            f"maximum of 24 hours. Using {REHYDRATION_MAX_HR} hours instead."
        )
        window_hr = REHYDRATION_MAX_HR

    # Maintenance rate, clamp to published range
    maint_factor = inputs.maintenance_mlpkg_hr
    if maint_factor < MAINTENANCE_MIN_MLPKG_HR:
        warnings.append(
            f"Maintenance factor {maint_factor:g} mL/kg/hr is below the "
            f"published 2–4 mL/kg/hr range. Using {MAINTENANCE_MIN_MLPKG_HR:g} "
            f"mL/kg/hr instead."
        )
        maint_factor = MAINTENANCE_MIN_MLPKG_HR
    elif maint_factor > MAINTENANCE_MAX_MLPKG_HR:
        warnings.append(
            f"Maintenance factor {maint_factor:g} mL/kg/hr is above the "
            f"published 2–4 mL/kg/hr range. Using {MAINTENANCE_MAX_MLPKG_HR:g} "
            f"mL/kg/hr instead."
        )
        maint_factor = MAINTENANCE_MAX_MLPKG_HR

    # Shock bolus (if applicable)
    shock_max_ml = None
    shock_inc_low = None
    shock_inc_high = None
    if inputs.in_shock:
        max_per_kg = (
            SHOCK_BOLUS_MAX_MLPK_DOG
            if inputs.species == FluidTherapySpecies.DOG
            else SHOCK_BOLUS_MAX_MLPK_CAT
        )
        shock_max_ml = weight_kg * max_per_kg
        shock_inc_low = weight_kg * SHOCK_BOLUS_INCREMENT_LOW
        shock_inc_high = weight_kg * SHOCK_BOLUS_INCREMENT_HIGH

    # Rehydration math
    deficit_ml = weight_kg * band.percent * 10.0
    rehydration_rate = deficit_ml / window_hr if window_hr > 0 else 0.0

    # Maintenance math
    maintenance_rate = weight_kg * maint_factor

    # Combined rates
    ongoing = max(0.0, inputs.ongoing_losses_ml_per_hr)
    active_phase_rate = rehydration_rate + maintenance_rate + ongoing
    post_rehydration_rate = maintenance_rate + ongoing

    # Persistent warnings
    if inputs.in_shock:
        warnings.append(
            "Patient is in shock. Address volume deficit FIRST with rapid "
            "isotonic crystalloid bolus(es) BEFORE switching to the "
            "rehydration+maintenance rate. Give 10–30 mL/kg increments, "
            "reassessing after each, up to a maximum of 90 mL/kg in dogs "
            "or 60 mL/kg in cats. Most patients respond well before "
            "reaching the maximum."
        )

    warnings.append(
        "DKA fluid therapy is dynamic. Reassess hydration, perfusion, and "
        "vital signs every 2–6 hours and adjust the rate as needed. "
        "Patients who are over-rehydrating (developing chemosis, "
        "respiratory crackles, peripheral edema, weight gain >10%) need "
        "the rate REDUCED, not stopped abruptly."
    )
    warnings.append(
        "Insulin therapy runs through a SEPARATE line; this calculator "
        "covers the resuscitation/rehydration/maintenance line only. "
        "When an insulin CRI is also running, the FLUID COMPOSITION of "
        "THIS line is dictated by the patient's current blood glucose "
        "(NaCl alone above 250, NaCl+2.5% dextrose at 200–250 and "
        "150–199, NaCl+5% dextrose below 150). The RATE calculated here "
        "doesn't change with BG, only the composition does."
    )
    warnings.append(
        "Hypokalemia, hypophosphatemia, and hypomagnesemia commonly worsen "
        "as DKA therapy progresses (insulin shifts these intracellularly). "
        "Check serum K every 4–6 hours; check phosphorus and magnesium 1–2 "
        "times daily. Supplement per published sliding scales (see "
        "/hypokalemia for K). The K administration ceiling is 0.5 mEq/kg/hr "
        "without continuous ECG."
    )

    # Notes, clinical context
    notes.append(
        f"Rehydration deficit math: {weight_kg:.2f} kg × "
        f"{band.percent:g}% × 10 = {deficit_ml:.0f} mL "
        f"(replaced over {window_hr} hours = "
        f"{rehydration_rate:.1f} mL/hr)."
    )
    notes.append(
        f"Maintenance: {weight_kg:.2f} kg × {maint_factor:g} mL/kg/hr = {maintenance_rate:.1f} mL/hr."
    )
    if ongoing > 0:
        notes.append(
            f"Ongoing losses: {ongoing:.0f} mL/hr (user-entered estimate "
            f"of vomiting, osmotic polyuria, diarrhea, or other ongoing "
            f"losses). Re-estimate hourly and adjust as needed."
        )
    notes.append(
        "Use a replacement-type isotonic crystalloid: either 0.9% NaCl "
        "OR a buffered isotonic crystalloid (LRS, Plasma-Lyte 148, "
        "Normosol-R) is acceptable. Recent evidence favors buffered "
        "solutions in DKA: they are associated with faster resolution "
        "of metabolic acidosis, reduced hyperchloremia, and decreased "
        "risk of acute kidney injury and shorter hospital stays vs "
        "0.9% NaCl. Buffered solutions also contribute a small amount "
        "of K (LRS ~4 mEq/L) which mildly blunts the post-insulin K "
        "decline."
    )
    notes.append(
        "Once the rehydration phase is complete, REDUCE the rate to "
        f"the post-rehydration target of {post_rehydration_rate:.1f} mL/hr "
        "(maintenance + ongoing losses only). Do not stop fluids "
        "abruptly, many DKA patients continue to have significant "
        "ongoing losses for 24–48 hours."
    )

    return FluidTherapyResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        band=band,
        dehydration_percent=band.percent,
        rehydration_window_hr=window_hr,
        maintenance_mlpkg_hr=maint_factor,
        ongoing_losses_ml_per_hr=ongoing,
        in_shock=inputs.in_shock,
        shock_bolus_max_ml=(round(shock_max_ml, 0) if shock_max_ml is not None else None),
        shock_increment_low_ml=(round(shock_inc_low, 0) if shock_inc_low is not None else None),
        shock_increment_high_ml=(round(shock_inc_high, 0) if shock_inc_high is not None else None),
        deficit_ml=round(deficit_ml, 0),
        rehydration_rate_ml_per_hr=round(rehydration_rate, 1),
        maintenance_rate_ml_per_hr=round(maintenance_rate, 1),
        active_phase_rate_ml_per_hr=round(active_phase_rate, 1),
        post_rehydration_rate_ml_per_hr=round(post_rehydration_rate, 1),
        warnings=warnings,
        notes=notes,
        sources=FLUID_THERAPY_SOURCES,
    )


FLUID_THERAPY_SOURCES = (
    Source(
        citation=(
            "DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in Small "
            "Animal Practice, 4th ed. Elsevier, 2012. Chapter 13 (Fluid Therapy in "
            "Practice). Dehydration assessment, deficit calculation, and "
            "replacement strategies."
        )
    ),
    Source(
        citation=(
            "Davis H, Jensen T, Johnson A, et al. 2013 AAHA/AAFP Fluid Therapy "
            "Guidelines for Dogs and Cats. J Am Anim Hosp Assoc 2013;49:149–159. "
            "Maintenance rate of 2–6 mL/kg/hr (with 5 mL/kg/hr as the typical "
            "default) and shock fluid dosing."
        )
    ),
    Source(
        citation=(
            "Chohan AS, Davidow EB. Massive transfusion in dogs and cats. Vet Clin "
            "North Am Small Anim Pract 2020;50:1419–1429. (Mini fluid challenge "
            "methodology.)"
        )
    ),
)

FLUID_THERAPY_CATALOG_ENTRY = {
    "slug": "fluid-therapy",
    "display_name": "Fluid therapy (rehydration + maintenance)",
    "short_name": "Fluid therapy",
    "category": "Fluid Therapy",
    "kind": "multi_step_protocol",
    "mechanism_summary": (
        "Combiner for the four components of an IV fluid plan in any "
        "dehydrated patient: shock bolus (if hypovolemic at presentation), "
        "rehydration deficit replacement over 4–24 hours, maintenance "
        "fluid rate, and replacement of ongoing losses. Outputs the "
        "active-phase combined rate (rehydration + maintenance + ongoing) "
        "and the post-rehydration rate (maintenance + ongoing only). "
        "Useful for any cause of dehydration. DKA, pancreatitis, parvo, "
        "Addisonian crisis, gastroenteritis, post-operative recovery."
    ),
    "indications_summary": (
        "Builds a complete IV fluid plan for any dehydrated dog or "
        "cat. Enter weight, % dehydration, and ongoing losses; "
        "outputs shock-bolus volumes if needed, deficit replacement "
        "over a chosen 4–24 hr window, maintenance rate, and the "
        "combined active-phase and post-rehydration rates the pump "
        "should run at."
    ),
}
