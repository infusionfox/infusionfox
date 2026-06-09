"""
Bolus tube feeding calculator for dogs and cats.

Computes a per-feeding volume in mL for nasogastric (NG/NE) and esophagostomy
(E) tubes, ramping the daily caloric target over 3 or 4 days. Designed for
bolus delivery (15-20 min infusion, 4-6 feedings/day). Continuous-rate tube
feeding and gastrostomy/jejunostomy tubes are out of scope.

Daily caloric target = RER (70 × BW^0.75). RER is the standard initial
target for inappetent / refeeding patients; once tolerated, intake can be
advanced toward MER if the patient is hospitalized long enough to warrant
weight maintenance rather than maintenance of lean mass during recovery.

Safety gates enforced here, not just in the template:
  * NG / NE tubes accept liquid diets only. A canned (blenderized) diet
    on an NG tube is a hard refusal — small-bore NG tubes occlude on
    blenderized food regardless of how thoroughly blended, with a real
    risk of catastrophic tube failure or aspiration during attempted
    clearance. The compute function returns a not_indicated result with
    a clear message and no volumes.
  * Per-feeding volumes above 10 mL/kg trigger a warning. Up to 40 mL/kg
    is tolerated by some patients, but 10 mL/kg is the safe default cap.
    If the computed volume exceeds the cap, the calculator surfaces
    \"% of cap\" so the clinician can decide whether to increase feeding
    frequency or accept the higher volume.

Sources:
  - Chan DL. Enteral nutrition. In: Silverstein DC, Hopper K, eds.
    Small Animal Critical Care Medicine. 4th ed. St. Louis, MO: Elsevier;
    2023. Ch. 126.
      * RER = 70 × BW^0.75 (Box 126.1).
      * Per-feeding bolus volume cap 10 mL/kg default; range 2-40 mL/kg.
      * Bolus over 15-20 min, every 4-6 hours.
      * NG/NE tubes (3.5-5 Fr cats, 6-8 Fr dogs) — liquid diets only.
      * E-tubes (12-14 Fr) accept blenderized canned diets.
      * Refeeding ramp: gradual ramp over 2-3 days starting at 33% RER
        is standard; the calculator offers 3-day (33/66/100) and
        4-day (25/50/75/100) options.
      * Discontinue when patient voluntarily eating ~75% RER.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .energy import estimate_ibw_kg
from .engine import Source, WeightUnit, lb_to_kg
from .tube_feeding_diets import DietForm, diet_by_key


class Species(str, Enum):
    DOG = "dog"
    CAT = "cat"


class TubeType(str, Enum):
    """Feeding tube type. G-tube and J-tube are intentionally out of scope.

    NG/NE refers to nasogastric or nasoesophageal — both are small-bore
    (3.5-8 Fr) and impose the same diet-form restriction (liquid only).
    """

    NG = "ng"  # nasogastric / nasoesophageal
    E = "e"  # esophagostomy


class RampLength(int, Enum):
    """Refeeding ramp length, days to reach 100% RER.

    Both schedules begin at 33% (3-day) or 25% (4-day) of RER on Day 1
    and rise linearly to 100% on the final day. There is no published
    head-to-head trial of one ramp vs the other in veterinary patients;
    the 4-day ramp is the more conservative choice for severely
    malnourished patients (refeeding syndrome risk).
    """

    THREE_DAY = 3
    FOUR_DAY = 4


# Per-feeding volume cap (mL/kg) for routine practice. Tolerated range
# extends to ~40 mL/kg in some patients but the calculator warns past
# the default cap and tags percent-of-cap for transparency.
PER_FEEDING_CAP_ML_PER_KG = 10.0

# Discontinuation threshold: voluntary intake at this fraction of RER
# is the standard cue to remove the tube.
DISCONTINUE_INTAKE_FRACTION = 0.75


def _ramp_fractions(length: RampLength) -> tuple[float, ...]:
    """Return the daily fraction-of-RER schedule for the given ramp.

    Day 1 → Day N. Final day is always 1.0 (100% RER).
    """
    if length == RampLength.THREE_DAY:
        return (1 / 3, 2 / 3, 1.0)
    return (0.25, 0.50, 0.75, 1.0)


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------


@dataclass
class TubeFeedingInputs:
    """All inputs to the calculator.

    Diet inputs are normalized at the compute step: when ``diet_key``
    matches a catalog entry the catalog values win; for ``OTHER_KEY`` the
    raw kcal_per_ml (liquid) or can_size_ml + can_kcal (canned) +
    water_added_ml are used. The form always sends all of these so the
    user can mix-and-match (e.g. pick a named diet then override water
    added).
    """

    species: Species
    tube_type: TubeType
    diet_form: DietForm
    diet_key: str  # catalog key or OTHER_KEY

    # Patient weight, always required.
    current_weight_value: float
    current_weight_unit: WeightUnit = WeightUnit.LB

    # Patient identifier for the printable schedule. Free text — name,
    # hospital ID, cage number, whatever the clinic uses. Optional; the
    # printable falls back to a blank line for handwriting if empty.
    # Has no effect on calculation.
    patient_id: str = ""

    # Ideal body weight, optional. RER is computed on IBW when available
    # (matches the energy calculator pattern). If BCS is set without an
    # explicit IBW, the calculator estimates IBW from BCS.
    ideal_weight_value: float | None = None
    ideal_weight_unit: WeightUnit = WeightUnit.LB
    bcs: int | None = None

    # Feedings per day and ramp length.
    feedings_per_day: int = 4
    ramp_length: RampLength = RampLength.THREE_DAY

    # Which day of the ramp the patient is currently on. Drives which row
    # the result panel surfaces as the headline. Defaults to 1 (start of
    # the ramp), the only safe headline for a patient just placed on a
    # tube. Range: 1..ramp_length (the final day represents "day N and
    # beyond" since the patient stays at 100% RER after the ramp).
    current_day: int = 1

    # Diet inputs. Always sent by the form; ignored if a catalog diet is
    # selected (catalog wins) except for water_added_ml on canned which
    # is always honored.
    diet_kcal_per_ml: float | None = None  # liquid manual entry
    diet_can_size_ml: float | None = None  # canned manual entry
    diet_can_kcal: float | None = None  # canned manual entry
    water_added_ml: float = 50.0  # canned only; added to slurry for E-tube delivery


@dataclass
class DayPlan:
    """Feeding plan for a single day of the ramp.

    ``percent_of_cap`` is filled in by ``compute_tube_feeding`` from the
    per-feeding volume and the 10 mL/kg cap. Stored as a plain field so
    templates can read it without recomputing.
    """

    day: int  # 1-indexed
    fraction_of_rer: float  # 0.0-1.0
    target_kcal: float  # day's caloric target
    per_feeding_kcal: float  # target_kcal / feedings_per_day
    per_feeding_ml: float  # per_feeding_kcal / effective_kcal_per_ml
    feedings_per_day: int
    percent_of_cap: float = 0.0  # set by compute()


@dataclass
class TubeFeedingResult:
    species: Species
    tube_type: TubeType
    diet_form: DietForm
    diet_label: str  # human label (catalog or "Custom liquid"/"Custom canned")

    # Patient identifier (free text, may be empty). Surfaced for the
    # printable schedule header; calculator never reads it.
    patient_id: str

    # Patient.
    current_weight_kg: float
    ideal_weight_kg: float | None
    ideal_weight_source: str  # "user-entered" / "estimated from BCS x" / "current weight"
    rer_basis_weight_kg: float  # the weight RER was computed on
    rer_kcal_per_day: float

    # Diet, post-normalization.
    effective_kcal_per_ml: float
    can_size_ml: float | None  # canned only
    can_kcal: float | None  # canned only
    water_added_ml: float | None  # canned only

    # Plan.
    feedings_per_day: int
    ramp_length_days: int
    days: tuple[DayPlan, ...]
    per_feeding_cap_ml: float  # 10 mL/kg × weight_kg

    # The day the user selected via the segmented control. Drives which
    # row the result panel surfaces as the headline. Clamped to
    # [1, ramp_length_days] during compute.
    current_day: int = 1
    # The DayPlan corresponding to current_day. None when the calculator
    # returned a not_indicated result (no days produced).
    current_day_plan: DayPlan | None = None

    # When True the calculator declined to produce volumes (e.g. NG + canned).
    not_indicated: bool = False
    not_indicated_reason: str = ""

    # Standard envelope.
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    valid: bool = True


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _resolve_weights(inp: TubeFeedingInputs) -> tuple[float, float | None, str, float]:
    """Return (current_kg, ideal_kg_or_none, source_label, rer_basis_kg).

    RER basis preference: explicit IBW > BCS-estimated IBW > current weight.
    Matches the energy calculator's behavior.
    """
    cur_kg = _to_kg(inp.current_weight_value, inp.current_weight_unit)
    if inp.ideal_weight_value and inp.ideal_weight_value > 0:
        ideal_kg = _to_kg(inp.ideal_weight_value, inp.ideal_weight_unit)
        return cur_kg, ideal_kg, "user-entered", ideal_kg
    if inp.bcs is not None and inp.bcs > 5:
        est = estimate_ibw_kg(cur_kg, inp.bcs)
        if est is not None:
            return cur_kg, est, f"estimated from BCS {inp.bcs}/9", est
    return cur_kg, None, "current weight", cur_kg


def _resolve_diet(
    inp: TubeFeedingInputs,
) -> tuple[float, str, float | None, float | None, float | None]:
    """Return (effective_kcal_per_ml, label, can_size_ml, can_kcal, water_added_ml).

    Catalog values win when a known diet_key is selected. For OTHER_KEY,
    the raw form fields are used.
    """
    diet = diet_by_key(inp.diet_key)
    if diet is not None:
        # Catalog entry. For canned diets, account for water added to
        # the slurry — the user's effective kcal/mL after dilution is
        # what the per-feeding volume calc must use.
        if diet.form == DietForm.CANNED:
            assert diet.can_size_ml is not None and diet.can_kcal is not None
            slurry_volume = diet.can_size_ml + max(0.0, inp.water_added_ml)
            effective = diet.can_kcal / slurry_volume
            return (
                effective,
                diet.label,
                diet.can_size_ml,
                diet.can_kcal,
                inp.water_added_ml,
            )
        # Liquid.
        return (diet.kcal_per_ml, diet.label, None, None, None)

    # OTHER: manual entry.
    if inp.diet_form == DietForm.LIQUID:
        kcal_ml = inp.diet_kcal_per_ml or 0.0
        return (kcal_ml, "Custom liquid", None, None, None)

    # Canned: compute kcal/mL from can size and kcal/can + water added.
    can_size = inp.diet_can_size_ml or 0.0
    can_kcal = inp.diet_can_kcal or 0.0
    water = max(0.0, inp.water_added_ml)
    slurry = can_size + water
    effective = (can_kcal / slurry) if slurry > 0 else 0.0
    return (effective, "Custom canned", can_size, can_kcal, water)


def _safety_gate(inp: TubeFeedingInputs) -> str | None:
    """Return a human-readable reason string if the combination is unsafe,
    or None if the calculator should proceed.

    The single hard gate is NG/NE + canned (blenderized) diet. This is
    not a soft warning — small-bore NG tubes occlude on blenderized
    diets and the failure mode includes aspiration during attempted
    clearance.
    """
    if inp.tube_type == TubeType.NG and inp.diet_form == DietForm.CANNED:
        return (
            "Canned (blenderized) diets are not safe through NG or NE tubes. "
            "Small-bore nasal tubes will occlude regardless of how thoroughly "
            "the diet is blended. Use a liquid enteral diet for NG/NE feeding, "
            "or place an esophagostomy tube for blenderized canned diets."
        )
    return None


def compute_tube_feeding(inp: TubeFeedingInputs) -> TubeFeedingResult:
    """Compute the bolus tube feeding plan.

    The returned TubeFeedingResult always has ``valid = True`` (input
    validation lives in the route layer). A ``not_indicated`` result is
    a *successful* computation — the calculator deliberately declines to
    produce volumes for a safety reason and the template displays the
    reason.
    """
    cur_kg, ideal_kg, ideal_source, basis_kg = _resolve_weights(inp)
    rer = 70.0 * (basis_kg**0.75)
    cap_ml = PER_FEEDING_CAP_ML_PER_KG * basis_kg

    warnings: list[str] = []
    notes: list[str] = []

    # Safety gate first; if tripped, we still report the patient context
    # (RER, weights) but skip volumes entirely.
    reason = _safety_gate(inp)
    if reason is not None:
        return TubeFeedingResult(
            species=inp.species,
            tube_type=inp.tube_type,
            diet_form=inp.diet_form,
            diet_label="—",
            patient_id=inp.patient_id,
            current_weight_kg=cur_kg,
            ideal_weight_kg=ideal_kg,
            ideal_weight_source=ideal_source,
            rer_basis_weight_kg=basis_kg,
            rer_kcal_per_day=rer,
            effective_kcal_per_ml=0.0,
            can_size_ml=None,
            can_kcal=None,
            water_added_ml=None,
            feedings_per_day=inp.feedings_per_day,
            ramp_length_days=int(inp.ramp_length),
            days=(),
            per_feeding_cap_ml=cap_ml,
            not_indicated=True,
            not_indicated_reason=reason,
            sources=SOURCES,
        )

    effective_kcal_ml, diet_label, can_size, can_kcal, water_added = _resolve_diet(inp)

    # If the diet form is mismatched against the catalog entry's form
    # (e.g. the user picked Royal Canin Recovery Liquid but the form
    # field is set to canned), trust the catalog's form. This is a UI
    # consistency issue, not a clinical one; we just note it.
    diet = diet_by_key(inp.diet_key)
    if diet is not None and diet.form != inp.diet_form:
        notes.append(
            f"Diet form set to {diet.form.value} to match the selected product."
        )
        # Re-run safety gate against the catalog form, in case this fixed
        # things or broke them.
        adjusted = TubeFeedingInputs(
            species=inp.species,
            tube_type=inp.tube_type,
            diet_form=diet.form,
            diet_key=inp.diet_key,
            current_weight_value=inp.current_weight_value,
            current_weight_unit=inp.current_weight_unit,
            patient_id=inp.patient_id,
            ideal_weight_value=inp.ideal_weight_value,
            ideal_weight_unit=inp.ideal_weight_unit,
            bcs=inp.bcs,
            feedings_per_day=inp.feedings_per_day,
            ramp_length=inp.ramp_length,
            diet_kcal_per_ml=inp.diet_kcal_per_ml,
            diet_can_size_ml=inp.diet_can_size_ml,
            diet_can_kcal=inp.diet_can_kcal,
            water_added_ml=inp.water_added_ml,
        )
        adjusted_reason = _safety_gate(adjusted)
        if adjusted_reason is not None:
            return TubeFeedingResult(
                species=inp.species,
                tube_type=inp.tube_type,
                diet_form=diet.form,
                diet_label="—",
                patient_id=inp.patient_id,
                current_weight_kg=cur_kg,
                ideal_weight_kg=ideal_kg,
                ideal_weight_source=ideal_source,
                rer_basis_weight_kg=basis_kg,
                rer_kcal_per_day=rer,
                effective_kcal_per_ml=0.0,
                can_size_ml=None,
                can_kcal=None,
                water_added_ml=None,
                feedings_per_day=inp.feedings_per_day,
                ramp_length_days=int(inp.ramp_length),
                days=(),
                per_feeding_cap_ml=cap_ml,
                not_indicated=True,
                not_indicated_reason=adjusted_reason,
                sources=SOURCES,
            )

    if effective_kcal_ml <= 0:
        # Diet inputs are incomplete (e.g. user typed nothing in Other).
        # Caller still gets a result; volumes are zero and a warning is
        # surfaced so the template can prompt for completion.
        warnings.append("Enter the diet's kcal/mL to compute volumes.")

    fractions = _ramp_fractions(inp.ramp_length)
    feedings = max(1, inp.feedings_per_day)
    days: list[DayPlan] = []
    for i, frac in enumerate(fractions, start=1):
        target_kcal = rer * frac
        per_feed_kcal = target_kcal / feedings
        per_feed_ml = (per_feed_kcal / effective_kcal_ml) if effective_kcal_ml > 0 else 0.0
        plan = DayPlan(
            day=i,
            fraction_of_rer=frac,
            target_kcal=target_kcal,
            per_feeding_kcal=per_feed_kcal,
            per_feeding_ml=per_feed_ml,
            feedings_per_day=feedings,
            percent_of_cap=(round(100.0 * per_feed_ml / cap_ml, 1) if cap_ml > 0 else 0.0),
        )
        days.append(plan)

    # Cap warning lives on the *day-100% RER* row since that's the worst
    # case. We surface the highest-day percent as a top-level warning if
    # it exceeds 100% of cap, so the clinician sees it without scrolling.
    final = days[-1]
    final_pct = float(getattr(final, "percent_of_cap", 0.0))
    if final_pct > 100:
        warnings.append(
            f"Day-{len(days)} per-feeding volume is {final_pct:.0f}% of the "
            f"10 mL/kg bolus cap. Increase feedings per day or accept the "
            f"higher volume with close monitoring; up to 40 mL/kg is "
            f"tolerated by some patients."
        )

    # Discontinuation cue, surfaced as a note rather than a warning.
    discontinue_kcal = rer * DISCONTINUE_INTAKE_FRACTION
    notes.append(
        f"Discontinue tube when voluntary intake reaches ~{DISCONTINUE_INTAKE_FRACTION:.0%} "
        f"of RER ({discontinue_kcal:.0f} kcal/day)."
    )

    # Clamp current_day into [1, ramp_length] and pick the matching plan.
    # We default to 1 (start of the ramp) rather than the final day so
    # the headline surfaces the safest volume on initial load. Out-of-range
    # values silently clamp rather than 422-ing so users who type a
    # nonsense day still see a usable result.
    clamped_day = max(1, min(int(inp.ramp_length), inp.current_day))
    current_plan = days[clamped_day - 1] if days else None

    return TubeFeedingResult(
        species=inp.species,
        tube_type=inp.tube_type,
        diet_form=inp.diet_form if diet is None else diet.form,
        diet_label=diet_label,
        patient_id=inp.patient_id,
        current_weight_kg=cur_kg,
        ideal_weight_kg=ideal_kg,
        ideal_weight_source=ideal_source,
        rer_basis_weight_kg=basis_kg,
        rer_kcal_per_day=rer,
        effective_kcal_per_ml=effective_kcal_ml,
        can_size_ml=can_size,
        can_kcal=can_kcal,
        water_added_ml=water_added,
        feedings_per_day=feedings,
        ramp_length_days=int(inp.ramp_length),
        days=tuple(days),
        per_feeding_cap_ml=cap_ml,
        current_day=clamped_day,
        current_day_plan=current_plan,
        notes=notes,
        warnings=warnings,
        sources=SOURCES,
    )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


SOURCES: tuple[Source, ...] = (
    Source(
        citation=(
            "Chan DL. Enteral nutrition. In: Silverstein DC, Hopper K, eds. "
            "Small Animal Critical Care Medicine. 4th ed. St. Louis, MO: "
            "Elsevier; 2023. Ch. 126."
        ),
    ),
    Source(
        citation=(
            "WSAVA Global Nutrition Committee. Feeding Guide for Hospitalized "
            "Dogs and Cats. World Small Animal Veterinary Association Global "
            "Nutrition Toolkit; 2013."
        ),
        url="https://wsava.org/wp-content/uploads/2020/08/Feeding-Guide-for-Hospitalized-Dogs-and-Cats.pdf",
    ),
)


# ---------------------------------------------------------------------------
# Catalog entry
# ---------------------------------------------------------------------------


TUBE_FEEDING_CATALOG_ENTRY = {
    "slug": "tube-feeding",
    "display_name": "Tube feeding (NG / E-tube)",
    "short_name": "TUBE",
    "category": "Nutrition",
    "mechanism_summary": (
        "Computes per-feeding bolus volume in mL for nasogastric and "
        "esophagostomy tubes in dogs and cats. RER target ramped over 3 "
        "or 4 days; per-feeding volume capped at 10 mL/kg with a clear "
        "percent-of-cap indicator past the threshold. NG tubes are "
        "restricted to liquid diets at the calculator level."
    ),
    "indications_summary": (
        "Bolus tube feeding plan for hospitalized dogs and cats with NG, "
        "NE, or E-tubes. Computes per-feeding volume ramped over a 3- "
        "or 4-day refeeding schedule from a diet you select or enter "
        "manually."
    ),
}
