"""
Calculator engine for InfusionFox.

Design goals
------------
- One generic engine drives every calculator.
- Adding a calculator = add a CalculatorConfig (in code) OR drop a YAML file.
  YAML is the preferred, clinician-authorable format.
- Four calculator kinds:
    1. SINGLE_DRUG_CRI:     single drug, single output (NE, Epi, Dob, Fent)
    2. MULTI_DRUG_CRI:      multiple drugs share one carrier bag (K/L, MLK, FLK)
    3. SLIDING_SCALE:       input value → lookup → recommendation (KCl by serum K+)
    4. MULTI_STEP_PROTOCOL: staged guidance with conditional branches (DKA)
- Two utility kinds exposed separately: UNIT_CONVERTER, FLUID_RATE.
- Species-aware throughout: every dose range is keyed by species.

Safety philosophy
-----------------
- Numbers come from clinician-authored YAML. The engine does NOT invent,
  interpolate, or extrapolate dose ranges.
- Out-of-range doses trigger warnings; hard_max triggers strong cautions.
- YAML files carry a `sources` block, citations render on the calculator page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

LB_PER_KG = 2.20462


class Species(str, Enum):
    DOG = "dog"
    CAT = "cat"


class DoseUnit(str, Enum):
    UG_PER_KG_PER_MIN = "ug/kg/min"
    UG_PER_KG_PER_HR = "ug/kg/hr"
    MG_PER_KG_PER_MIN = "mg/kg/min"
    MG_PER_KG_PER_HR = "mg/kg/hr"
    # Milliunits per kg per minute. Used by drugs dosed in
    # international units rather than mass — currently vasopressin
    # (stock 20 U/mL → stored as 20,000 mU/mL, semantically the same
    # numeric form the engine uses for "µg/mL" elsewhere).
    MU_PER_KG_PER_MIN = "mU/kg/min"


class WeightUnit(str, Enum):
    LB = "lb"
    KG = "kg"


class CalculatorKind(str, Enum):
    SINGLE_DRUG_CRI = "single_drug_cri"
    SLIDING_SCALE = "sliding_scale"
    MULTI_STEP_PROTOCOL = "multi_step_protocol"
    DOPAMINE_PREPARATION = "dopamine_preparation"
    MULTI_DRUG_PROTOCOL = "multi_drug_protocol"
    UNIT_CONVERTER = "unit_converter"
    FLUID_RATE = "fluid_rate"


class CriMode(str, Enum):
    """Calculation mode for SINGLE_DRUG_CRI calculators.

    STANDARD_BAG is the historical default: the user picks a bag
    concentration from the available presets (or types one), and the
    calculator returns the pump rate required to deliver the requested
    dose. Pump rate scales with patient weight; bag concentration is
    fixed.

    TARGET_PUMP_RATE inverts the workflow: the user picks a target
    pump rate (typically a round low number like 3 mL/hr to minimize
    carrier fluid in an already-resuscitated patient), and the
    calculator returns the bag concentration required, plus the volume
    of stock to draw and add to a bag of the specified size. Bag
    concentration scales with patient weight; pump rate is fixed.

    The two modes are mutually exclusive on a per-submission basis.
    The result panel displayed in TARGET_PUMP_RATE mode is distinct
    from the STANDARD_BAG result panel so the user can never see both
    outputs side-by-side, which would be a medication-error hazard.
    """

    STANDARD_BAG = "standard_bag"
    TARGET_PUMP_RATE = "target_pump_rate"


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConcentrationPreset:
    concentration_ug_per_ml: float
    recipe: str
    when_to_use: str
    # Optional weight range (kg). When set, the calculator UI can auto-select
    # this preset for patients whose weight falls in this range. Both bounds
    # are inclusive. Either can be None for an open-ended range.
    weight_min_kg: float | None = None
    weight_max_kg: float | None = None
    # When False, the preset is a warning entry (e.g., undiluted vial that's
    # too concentrated for any pump-accurate use) and should not be offered
    # in the user-facing "use a different preparation" disclosure. It stays
    # in the catalog as a structural anchor (so the calculator engine can
    # cross-reference and the article can cite it), but the UI doesn't ask
    # the user to pick it.
    pump_safe: bool = True


@dataclass(frozen=True)
class DoseRange:
    min: float
    max: float
    hard_max: float | None = None
    note: str | None = None
    # Always surfaces when this species is selected, regardless of dose level.
    # Use for clinical cautions that apply across the entire dose range
    # (e.g., a drug with arrhythmogenic potential in cats at any dose).
    persistent_warning: str | None = None
    # Optional dose level at which a stronger caution kicks in, while still
    # being within the published range (i.e., below hard_max). Use when a
    # drug has known increased risk in the upper part of its valid range.
    caution_threshold: float | None = None
    caution_note: str | None = None


@dataclass(frozen=True)
class Source:
    """A citation for the clinical data in a calculator."""

    citation: str
    url: str | None = None
    reviewer: str | None = None  # e.g. "Reviewed by Dr. Jane Smith, DACVECC, 2026-04"


@dataclass(frozen=True)
class SlidingScaleRow:
    min_value: float | None
    max_value: float | None
    label: str
    recommendation: str
    warning: str | None = None


@dataclass(frozen=True)
class ProtocolStep:
    step_number: int
    title: str
    content: str
    conditions: tuple[ProtocolCondition, ...] = ()


@dataclass(frozen=True)
class ProtocolCondition:
    when: str
    then: str


@dataclass(frozen=True)
class LoadingDose:
    """One loading-dose scenario for a drug.

    Surfaced in the result panel alongside the CRI rate. Each scenario
    is a published indication with its own dose range per species.

    `dose_per_kg` is a per-species (low, high) tuple in `display_dose_unit`
    per kg. Use the same value for low and high when the published dose
    is a single value (e.g., cats perioperative fentanyl = 5 µg/kg, not
    a range).

    `display_dose_unit` is the unit the dose values are expressed in —
    "µg" (fentanyl loading: 2–10 µg/kg) or "mg" (metoclopramide lar
    par loading: 1 mg/kg). The computation converts to µg internally
    for stock-volume math; the template uses the unit label for
    display.

    `matches_cri_rate=True` means the matched value shown prominently
    equals the user's CRI dose value 1:1 in the dose unit. Clinically
    valid for drugs with short half-lives whose CRI dose unit matches
    the loading dose unit (fentanyl: µg/kg/hr CRI → µg/kg loading;
    metoclopramide could similarly use mg/kg/hr CRI → mg/kg loading
    if the scenario opted in).
    """

    label: str
    description: str
    matches_cri_rate: bool
    dose_per_kg: dict[Species, tuple[float, float]]
    display_dose_unit: str = "µg"
    note: str = ""


@dataclass(frozen=True)
class CalculatorConfig:
    """Unified config; fields used depend on `kind`."""

    slug: str
    display_name: str
    short_name: str
    category: str
    kind: CalculatorKind

    mechanism_summary: str
    indications_summary: str
    sources: tuple[Source, ...] = ()

    # One-sentence catalog-card blurb (~12-20 words). Independent of the
    # longer `indications_summary` which serves as the calculator-page
    # intro. Catalog templates use this when set; nav.py falls back to
    # `indications_summary or mechanism_summary` when it isn't.
    catalog_blurb: str = ""

    # --- SINGLE_DRUG_CRI ---
    stock_concentration_ug_per_ml: float = 0.0
    stock_concentration_display: str = ""
    dose_unit: DoseUnit | None = None
    # Display labels for non-mass units. Default "µg/mL" / "µg" covers
    # every catecholamine and most other drugs in the catalog. Drugs
    # dosed in international units (currently vasopressin) override these:
    #   concentration_unit_label = "mU/mL"
    #   dose_mass_unit = "mU"
    # The engine's internal math is unit-agnostic (treats the values as
    # numbers); the templates use these labels everywhere a unit is
    # rendered next to a concentration or in a formula explainer.
    concentration_unit_label: str = "µg/mL"
    dose_mass_unit: str = "µg"
    # Per-drug print-button opt-in. The universal calculator template
    # renders a "Print" button (blue accent, anesthesia-worksheet
    # pattern) and a print-only result header with the InfusionFox
    # mark only when this flag is True. Vasopressors and inotropes
    # set this — clinicians want a paper copy of the bag recipe,
    # pump rate, and titration ladder at the bedside. Other drug
    # categories (analgesia builder handles its own print path
    # separately) default to False.
    supports_print: bool = False
    # Whether to render the "suggested" badge on bag-size tabs. The
    # badge follows the full-vial computation (vial size ÷ chosen
    # concentration). For drugs where bag size encodes dilution
    # (norepi, epi, vasopressin, phenylephrine, dopamine-cri) the
    # badge points at the dilution best for the current patient.
    # Dobutamine sets this False: its 50 mL syringe vs 250 mL bag
    # choice encodes pump TYPE (syringe pump vs volumetric pump),
    # not dilution. All four dobutamine concentration_presets are
    # 50 mL syringe recipes, so the full-vial computation lands on
    # 250 mL — conflicting with the form's bag_size_default_ml=50
    # and producing a visually confusing "suggested" badge on the
    # tab the user didn't pick by default.
    show_bag_size_suggestion: bool = True
    default_dose: float = 0.0
    dose_ranges: dict[Species, DoseRange] = field(default_factory=dict)
    concentration_presets: tuple[ConcentrationPreset, ...] = ()
    # Optional note to display below the dilution presets table, e.g. when
    # the drug has commercially available premixes that the user should be
    # aware of in addition to the listed compounded recipes.
    dilution_note: str = ""
    default_concentration_ug_per_ml: float = 0.0
    # Optional dose-step ladder for fast titration. When present, the result
    # panel renders a table showing pump rate for each dose step at the
    # patient's weight + selected bag concentration. Designed for reference
    # by a technician at the pump while the clinician is hands-busy. Doses
    # are in the calculator's `dose_unit`. Ladders should span the published
    # therapeutic range with finer steps in the more commonly titrated band.
    titration_ladder: tuple[float, ...] = ()
    # Default pump rate (mL/hr) used as the form's initial value in
    # TARGET_PUMP_RATE mode. The right default depends on how the drug is
    # conventionally run: vasopressors and inotropes run at low carrier
    # rates (1-3 mL/hr) to minimize fluid load in patients who are already
    # fluid-resuscitated. Opioid CRIs like fentanyl are conventionally
    # prepared at a lower bag concentration and run at higher mL/hr,
    # because they don't have the same volume-restriction context.
    # Mismatched defaults produce nonsensical bag preps (e.g. drawing
    # 80 mL of a 50 µg/mL stock to deliver fentanyl at 3 mL/hr).
    target_pump_rate_default_ml_per_hr: float = 3.0
    # Whether this drug should expose the TARGET_PUMP_RATE calculation mode.
    # TARGET_PUMP_RATE was built around the vasopressor / inotrope workflow:
    # in a fluid-resuscitated patient, you want a low carrier rate (1-3
    # mL/hr) and the bag concentration floats. That workflow makes clinical
    # sense for norepi, epi, dobutamine, and dopamine.
    #
    # It does NOT make sense for analgesic CRIs (fentanyl, opioid CRIs in
    # general) where the conventional preparation is the inverse: the bag
    # is made at a standard concentration (e.g. 1 µg/mL fentanyl) and the
    # pump rate floats with the dose. Forcing a target-pump-rate mode on
    # those drugs produces either non-standard bag concentrations or
    # excessive carrier fluid loads (a 3 kg cat on fentanyl at 50 mL/hr
    # receives ~4x maintenance fluid as carrier alone).
    #
    # Default True (the original 4 vasopressor/inotrope CRIs); set False
    # on drugs whose workflow doesn't fit the target-pump-rate model.
    supports_target_pump_rate_mode: bool = True
    # Optional override for the dose pre-fill in TARGET_PUMP_RATE mode.
    # In bag-prep workflow, clinicians typically anchor on a slightly higher
    # starting dose than the absolute conservative minimum, because the bag
    # they're preparing should have headroom for titration both up AND down.
    # For example, norepinephrine's STANDARD_BAG default is 0.05 µg/kg/min
    # (the lowest published starting dose) but the conventional anchor in
    # target-pump-rate prep is 0.1 µg/kg/min — that matches the article's
    # worked example and lands the prepared bag in a more practical
    # concentration range. None means "use default_dose for both modes."
    target_pump_rate_default_dose: float | None = None

    # --- Combined bag-prep section ("norepi-pattern" UI) ---
    # When True, the calculator renders the combined concentration +
    # bag-size selector with patient-aware auto-pick and "suggested"
    # tags (originally introduced for norepinephrine, now generalized).
    # Default False — drugs not yet converted keep the original
    # prep-card + alt-concentration disclosure pattern.
    uses_combined_prep_section: bool = False
    # Bag sizes to offer in the combined prep section, in mL. Each
    # renders as a tab in the bag-size selector. Used only when
    # uses_combined_prep_section is True.
    bag_size_options_ml: tuple[int, ...] = ()
    # Default bag size on initial render (must be one of
    # bag_size_options_ml or 0 if unused).
    bag_size_default_ml: int = 0
    # Manufactured vial size in mg. Drives the "full-vial" bag suggestion
    # (the bag size whose drug amount uses exactly one full vial). The
    # full-vial bag earns the "suggested" tag for each concentration.
    vial_size_mg: float | None = None
    # Patient-driven concentration recommendation algorithm. Two options:
    #   "pump-precision": pick the highest concentration that keeps the
    #     pump rate at or above `min_pump_rate_ml_per_hr` (norepi pattern;
    #     minimizes carrier fluid while preserving volumetric-pump
    #     precision).
    #   "weight-band": pick the concentration whose ConcentrationPreset
    #     weight_min_kg/weight_max_kg band includes the patient
    #     (dobutamine pattern; concentration tracks patient size).
    # Empty string = no patient-driven suggestion.
    recommendation_strategy: str = ""
    # Used only when recommendation_strategy == "pump-precision". The
    # minimum volumetric-pump-precision rate that the algorithm aims to
    # preserve. 2.0 mL/hr is the typical floor for most pumps.
    min_pump_rate_ml_per_hr: float = 0.0
    # Diluent text used in the combined prep section's recipe cards
    # ("Add to {bag_size} bag of {diluent_label}"). Should describe the
    # clinically acceptable carriers for this drug, e.g.
    # "5% dextrose or 0.9% NaCl" or "5% dextrose, 0.9% NaCl, or LRS".
    diluent_label: str = ""
    # Three short paragraphs for the "How this calculator works"
    # disclosure (rendered at the top of the form). Empty tuple means
    # no disclosure renders. Each paragraph is one concept, ~30 words.
    how_it_works_paragraphs: tuple[str, ...] = ()

    # Loading-dose scenarios surfaced alongside the CRI rate in the
    # result panel. Each LoadingDose is one published indication
    # (e.g., "Perioperative analgesia", "Emergent severe pain") with
    # its own per-species dose range. Empty tuple means no loading-dose
    # math renders. Currently populated for fentanyl; designed to
    # generalize to other CRIs (lidocaine, ketamine) that have similar
    # loading-bolus-then-CRI workflows.
    loading_doses: tuple[LoadingDose, ...] = ()

    # --- SLIDING_SCALE ---
    scale_input_label: str = ""
    scale_input_unit: str = ""
    scale_default_value: float = 0.0
    scale_rows: tuple[SlidingScaleRow, ...] = ()
    scale_notes: tuple[str, ...] = ()

    # --- MULTI_STEP_PROTOCOL ---
    protocol_steps: tuple[ProtocolStep, ...] = ()

    # Free-form short version string for source content. Bump whenever the
    # underlying clinical reference is updated (e.g. "2025-Q1", "v2", or
    # "RECOVER-2024"). Surfaces in the UI footer near the citation block
    # and travels with audit log entries so we can correlate a clinician's
    # decision with the exact reference they consulted.
    version: str = "v1"


# ---------------------------------------------------------------------------
# Inputs / results
# ---------------------------------------------------------------------------


@dataclass
class CalcInputs:
    """Inputs for SINGLE_DRUG_CRI.

    The first five fields cover both modes. The last three apply only
    when cri_mode is TARGET_PUMP_RATE; they are None in STANDARD_BAG
    mode. In TARGET_PUMP_RATE mode, concentration_ug_per_ml is unused
    (the calculator computes a bag concentration as output instead of
    accepting one as input), but the field is still populated with the
    drug's default stock concentration so the engine never sees None
    on a field whose absence would be ambiguous.
    """

    weight_value: float
    weight_unit: WeightUnit
    dose: float
    concentration_ug_per_ml: float
    species: Species

    cri_mode: CriMode = CriMode.STANDARD_BAG
    # TARGET_PUMP_RATE mode only: the pump rate the clinician wants to
    # run at, and the size of the bag they're preparing. None in
    # STANDARD_BAG mode.
    target_pump_rate_ml_per_hr: float | None = None
    bag_volume_ml: float | None = None
    # TARGET_PUMP_RATE mode also needs the stock-vial concentration so
    # the calculator can return the volume of stock to draw. STANDARD_BAG
    # mode does not need this because the user has already done the
    # bag-prep step before opening the calculator.
    stock_concentration_ug_per_ml: float | None = None


@dataclass
class TitrationStep:
    """One row of a fast-titration reference table.

    Designed for a technician to read at the pump: dose -> pump rate at the
    current patient weight and bag concentration. The 'is_caution' flag fires
    when the dose is at or above the calculator's caution threshold (when
    one is defined for this species).
    """

    dose: float
    dose_unit: DoseUnit
    ml_per_hr_pump: float
    ml_per_hr_precise: float
    is_current: bool  # True when this row matches the dose the user just computed
    is_caution: bool


@dataclass
class CalcResult:
    weight_kg: float
    dose: float
    dose_unit: DoseUnit
    concentration_ug_per_ml: float
    species: Species

    total_dose_ug_per_min: float | None
    total_dose_ug_per_hr: float

    ml_per_hr_precise: float
    ml_per_hr_pump: float
    ml_per_hr_display: float
    ml_per_kg_per_hr: float

    warnings: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # Set to False when one or more required inputs (weight, dose,
    # concentration) are missing or non-positive. When False, the numeric
    # output fields are zeroed and templates MUST suppress them; rendering
    # a computed dose/rate alongside a "weight must be > 0" warning is a
    # clinical-safety bug. See template gating in partials/result_panel.html.
    valid: bool = True

    # Fast-titration ladder for technician reference. Empty tuple when the
    # calculator hasn't defined one. See engine.compute() for how it's built.
    titration_steps: tuple[TitrationStep, ...] = ()

    # Caution-threshold context for the ladder. Populated from the active
    # DoseRange so the template can render an inline explanation of what the
    # red caution rows mean, without requiring the user to enter a
    # caution-level dose first. None when no caution threshold is configured
    # for this species.
    caution_threshold: float | None = None
    caution_note: str | None = None

    # TARGET_PUMP_RATE mode outputs. None in STANDARD_BAG mode. When
    # populated, these describe the bag the clinician must prepare in
    # order to run at the requested fixed pump rate and still deliver
    # the requested dose. The template must use these fields ONLY when
    # cri_mode is TARGET_PUMP_RATE; rendering them alongside the
    # STANDARD_BAG outputs would create a side-by-side display of two
    # different bag preparations for the same patient, which is the
    # medication-error hazard the toggle was designed to prevent.
    cri_mode: CriMode = CriMode.STANDARD_BAG
    target_pump_rate_ml_per_hr: float | None = None
    bag_volume_ml: float | None = None
    bag_concentration_ug_per_ml: float | None = None
    total_drug_in_bag_mg: float | None = None
    stock_volume_to_add_ml: float | None = None


@dataclass
class SlidingScaleResult:
    input_value: float
    input_unit: str
    matched_row: SlidingScaleRow | None
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def lb_to_kg(lb: float) -> float:
    return lb / LB_PER_KG


def _dose_to_ug_per_hr(dose: float, dose_unit: DoseUnit, weight_kg: float) -> float:
    if dose_unit == DoseUnit.UG_PER_KG_PER_MIN:
        return weight_kg * dose * 60
    if dose_unit == DoseUnit.UG_PER_KG_PER_HR:
        return weight_kg * dose
    if dose_unit == DoseUnit.MG_PER_KG_PER_HR:
        return weight_kg * dose * 1000
    if dose_unit == DoseUnit.MG_PER_KG_PER_MIN:
        return weight_kg * dose * 60 * 1000
    if dose_unit == DoseUnit.MU_PER_KG_PER_MIN:
        # Same numerical form as UG_PER_KG_PER_MIN. The "µg/hr" return
        # value is really "mU/hr" for vasopressin; the engine works on
        # numeric values, the unit label is a display concern.
        return weight_kg * dose * 60
    raise ValueError(f"Unknown dose unit: {dose_unit}")


def compute(config: CalculatorConfig, inputs: CalcInputs) -> CalcResult:
    """SINGLE_DRUG_CRI compute.

    Validates inputs first; if any required input (weight, dose,
    concentration) is non-positive, returns a result with valid=False
    and zeroed numeric fields, so the template can suppress numeric
    output. The previous behavior (appending a warning but continuing
    to compute with the bad input) produced negative rates or a
    ZeroDivisionError on zero concentration. Both were clinical-safety
    bugs.
    """
    assert config.dose_unit is not None, "compute() requires a dose_unit on the config"

    weight_kg = lb_to_kg(inputs.weight_value) if inputs.weight_unit == WeightUnit.LB else inputs.weight_value

    # Validate first. If any input is unusable, short-circuit. Math on
    # non-positive inputs produces nonsensical or undefined outputs that
    # have no business being rendered to a clinician.
    validation_errors = _validate_single_inputs(inputs, weight_kg)
    if validation_errors:
        return CalcResult(
            weight_kg=weight_kg,
            dose=inputs.dose,
            dose_unit=config.dose_unit,
            concentration_ug_per_ml=inputs.concentration_ug_per_ml,
            species=inputs.species,
            total_dose_ug_per_min=None,
            total_dose_ug_per_hr=0.0,
            ml_per_hr_precise=0.0,
            ml_per_hr_pump=0.0,
            ml_per_hr_display=0.0,
            ml_per_kg_per_hr=0.0,
            warnings=validation_errors,
            sources=config.sources,
            valid=False,
        )

    if config.dose_unit == DoseUnit.UG_PER_KG_PER_MIN:
        total_ug_per_min = weight_kg * inputs.dose
        total_ug_per_hr = total_ug_per_min * 60
    elif config.dose_unit == DoseUnit.MU_PER_KG_PER_MIN:
        # Vasopressin pattern. The "ug/min" and "ug/hr" variables are
        # really "mU/min" and "mU/hr"; the engine works numerically
        # and the display layer carries the unit label.
        total_ug_per_min = weight_kg * inputs.dose
        total_ug_per_hr = total_ug_per_min * 60
    elif config.dose_unit == DoseUnit.UG_PER_KG_PER_HR:
        total_ug_per_min = None
        total_ug_per_hr = weight_kg * inputs.dose
    elif config.dose_unit == DoseUnit.MG_PER_KG_PER_HR:
        # mg → µg: multiply by 1000 so the rest of the function (which
        # works in µg internally so the math lines up with the µg/mL
        # bag concentration) stays unchanged. Metoclopramide is the
        # first CRI in the catalog with mg/kg/hr dosing; the formula
        # display in calculator.html and result_panel.html has a
        # matching mg/kg/hr branch.
        total_ug_per_min = None
        total_ug_per_hr = weight_kg * inputs.dose * 1000.0
    else:
        raise ValueError(f"compute() requires per-min or per-hr dose unit; got {config.dose_unit}")

    # In TARGET_PUMP_RATE mode the bag concentration is an OUTPUT, not
    # an input. We derive it from the requested pump rate and the
    # patient's per-hour dose, then use that derived concentration for
    # the remainder of the compute (pump rate, titration ladder) so
    # the result panel is internally consistent: the bag the user is
    # told to prepare actually does deliver the requested dose at the
    # requested pump rate.
    target_pump_rate_ml_per_hr: float | None = None
    bag_volume_ml: float | None = None
    bag_concentration_ug_per_ml_out: float | None = None
    total_drug_in_bag_mg: float | None = None
    stock_volume_to_add_ml: float | None = None
    concentration_ug_per_ml = inputs.concentration_ug_per_ml

    if inputs.cri_mode == CriMode.TARGET_PUMP_RATE:
        # Defensive: validation should have caught these but guard
        # against re-running compute() on a partially-populated inputs.
        if (
            inputs.target_pump_rate_ml_per_hr is None
            or inputs.target_pump_rate_ml_per_hr <= 0
            or inputs.bag_volume_ml is None
            or inputs.bag_volume_ml <= 0
            or inputs.stock_concentration_ug_per_ml is None
            or inputs.stock_concentration_ug_per_ml <= 0
        ):
            return CalcResult(
                weight_kg=weight_kg,
                dose=inputs.dose,
                dose_unit=config.dose_unit,
                concentration_ug_per_ml=inputs.concentration_ug_per_ml,
                species=inputs.species,
                total_dose_ug_per_min=None,
                total_dose_ug_per_hr=0.0,
                ml_per_hr_precise=0.0,
                ml_per_hr_pump=0.0,
                ml_per_hr_display=0.0,
                ml_per_kg_per_hr=0.0,
                warnings=[
                    "Target pump rate, bag volume, and stock concentration "
                    "must all be greater than zero."
                ],
                sources=config.sources,
                valid=False,
                cri_mode=CriMode.TARGET_PUMP_RATE,
            )

        target_pump_rate_ml_per_hr = inputs.target_pump_rate_ml_per_hr
        bag_volume_ml = inputs.bag_volume_ml
        # Bag concentration required to deliver total_ug_per_hr at the
        # requested pump rate.
        bag_concentration_ug_per_ml_out = total_ug_per_hr / target_pump_rate_ml_per_hr
        # Total drug to add to a bag of bag_volume_ml at this concentration.
        total_drug_in_bag_ug = bag_concentration_ug_per_ml_out * bag_volume_ml
        total_drug_in_bag_mg = total_drug_in_bag_ug / 1000.0
        # Volume of stock to draw, given the stock vial concentration.
        stock_volume_to_add_ml = total_drug_in_bag_ug / inputs.stock_concentration_ug_per_ml
        # The bag concentration we just computed is the one that should
        # drive the rest of the compute, NOT the unused
        # inputs.concentration_ug_per_ml field. Reassign for clarity.
        concentration_ug_per_ml = bag_concentration_ug_per_ml_out

    ml_per_hr = total_ug_per_hr / concentration_ug_per_ml
    ml_per_kg_per_hr = ml_per_hr / weight_kg
    # Inputs are valid by construction here; this only collects range/preset warnings.
    warnings = _check_range_warnings_single(config, inputs)

    # Low pump-rate safety warning. Standard IV infusion pumps lose
    # accuracy below ~1-2 mL/hr; titration in 0.1 mL/hr increments at
    # those rates is unreliable on most pumps. The clinical fix is
    # usually to dilute the bag so the same dose runs at a higher
    # mL/hr; a syringe pump is the alternative when dilution isn't
    # practical. The warning is intentionally non-prescriptive: it
    # flags the rate as below reliable IV-pump range and presents
    # both fixes, leaving the choice to the clinician.
    if ml_per_hr > 0 and ml_per_hr < 2.0:
        warnings.append(
            "Calculated pump rate is below 2 mL/hr, below the reliable "
            "range of standard IV infusion pumps. Dilute the bag so the "
            "same dose runs at a higher mL/hr, or use a syringe pump."
        )

    titration_steps = _build_titration_ladder(
        config=config,
        weight_kg=weight_kg,
        concentration_ug_per_ml=concentration_ug_per_ml,
        species=inputs.species,
        current_dose=inputs.dose,
    )

    # Surface the active species' caution context so the template can render
    # an inline explanation of the red caution rows in the ladder, even when
    # the user's current dose is below the threshold.
    active_range = config.dose_ranges.get(inputs.species)
    caution_threshold = active_range.caution_threshold if active_range else None
    caution_note = active_range.caution_note if active_range else None

    return CalcResult(
        weight_kg=weight_kg,
        dose=inputs.dose,
        dose_unit=config.dose_unit,
        concentration_ug_per_ml=concentration_ug_per_ml,
        species=inputs.species,
        total_dose_ug_per_min=total_ug_per_min,
        total_dose_ug_per_hr=total_ug_per_hr,
        ml_per_hr_precise=ml_per_hr,
        ml_per_hr_pump=round(ml_per_hr, 2),
        ml_per_hr_display=round(ml_per_hr, 1),
        ml_per_kg_per_hr=ml_per_kg_per_hr,
        warnings=warnings,
        sources=config.sources,
        valid=True,
        titration_steps=titration_steps,
        caution_threshold=caution_threshold,
        caution_note=caution_note,
        cri_mode=inputs.cri_mode,
        target_pump_rate_ml_per_hr=target_pump_rate_ml_per_hr,
        bag_volume_ml=bag_volume_ml,
        bag_concentration_ug_per_ml=bag_concentration_ug_per_ml_out,
        total_drug_in_bag_mg=total_drug_in_bag_mg,
        stock_volume_to_add_ml=stock_volume_to_add_ml,
    )


def _build_titration_ladder(
    config: CalculatorConfig,
    weight_kg: float,
    concentration_ug_per_ml: float,
    species: Species,
    current_dose: float,
) -> tuple[TitrationStep, ...]:
    """Build the per-step pump-rate ladder for fast titration reference.

    Returns an empty tuple when the calculator has no `titration_ladder`
    configured. When present, returns one TitrationStep per ladder dose
    with the pump rate that dose maps to at the patient's weight + bag
    concentration. The 'is_current' flag fires for the row whose dose
    matches the just-computed dose (within a small tolerance) so the UI
    can highlight where the patient is right now.
    """
    if not config.titration_ladder or config.dose_unit is None:
        return ()

    caution_threshold: float | None = None
    # Some drugs have species-specific minimums (e.g. dobutamine: 2 µg/kg/min
    # in dogs, 1 µg/kg/min in cats). Drop ladder steps below the active
    # species' published low so a clinician glancing at the dog ladder
    # doesn't see a "1 µg/kg/min" step that's outside Plumb's dog range.
    # We don't filter on the high end — caution_threshold inside the
    # range flags the dangerous tail, but those rows stay visible so
    # the user can see where the cliff is.
    species_min: float | None = None
    if species in config.dose_ranges:
        caution_threshold = config.dose_ranges[species].caution_threshold
        species_min = config.dose_ranges[species].min

    steps: list[TitrationStep] = []
    for dose in config.titration_ladder:
        if species_min is not None and dose < species_min:
            continue
        if config.dose_unit == DoseUnit.UG_PER_KG_PER_MIN:
            ml_per_hr = (weight_kg * dose / concentration_ug_per_ml) * 60
        elif config.dose_unit == DoseUnit.UG_PER_KG_PER_HR:
            ml_per_hr = weight_kg * dose / concentration_ug_per_ml
        else:
            # Fall back to no ladder if the dose unit isn't supported above
            return ()

        is_current = abs(dose - current_dose) < 1e-9
        is_caution = caution_threshold is not None and dose > caution_threshold

        steps.append(
            TitrationStep(
                dose=dose,
                dose_unit=config.dose_unit,
                ml_per_hr_pump=round(ml_per_hr, 2),
                ml_per_hr_precise=ml_per_hr,
                is_current=is_current,
                is_caution=is_caution,
            )
        )
    return tuple(steps)


def lookup_sliding_scale(config: CalculatorConfig, input_value: float) -> SlidingScaleResult:
    """First row where min_value <= input_value < max_value wins. Either bound
    can be None (open-ended)."""
    matched = None
    for row in config.scale_rows:
        below_min = row.min_value is not None and input_value < row.min_value
        at_or_above_max = row.max_value is not None and input_value >= row.max_value
        if not below_min and not at_or_above_max:
            matched = row
            break

    return SlidingScaleResult(
        input_value=input_value,
        input_unit=config.scale_input_unit,
        matched_row=matched,
        notes=list(config.scale_notes),
        sources=config.sources,
    )


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def _validate_single_inputs(inputs: CalcInputs, weight_kg: float) -> list[str]:
    """Return a list of validation errors for SINGLE_DRUG_CRI inputs.

    An empty list means inputs are usable; a non-empty list means at
    least one required field is missing or non-positive and the
    calculator should NOT proceed to compute. Math on non-positive
    inputs produces negative rates (clinically meaningless) or
    ZeroDivisionError on zero concentration.
    """
    errors: list[str] = []
    if weight_kg <= 0:
        errors.append("Weight must be greater than zero.")
    if inputs.dose <= 0:
        errors.append("Dose must be greater than zero.")
    if inputs.concentration_ug_per_ml <= 0:
        errors.append("Concentration must be greater than zero.")
    return errors


def _check_range_warnings_single(config: CalculatorConfig, inputs: CalcInputs) -> list[str]:
    """Range-band and unusual-concentration warnings for inputs that
    have already passed validation. Caller MUST have run
    _validate_single_inputs first; this function assumes weight, dose,
    and concentration are all positive.
    """
    warnings: list[str] = []

    dose_range = config.dose_ranges.get(inputs.species)
    if dose_range:
        if dose_range.persistent_warning:
            warnings.append(dose_range.persistent_warning)
        # SINGLE_DRUG_CRI configs always set dose_unit; narrow the type.
        assert config.dose_unit is not None
        _append_dose_warning(
            warnings, "", inputs.dose, config.dose_unit.value, dose_range, inputs.species.value
        )

    preset_concs = [p.concentration_ug_per_ml for p in config.concentration_presets]
    if (
        preset_concs
        and inputs.concentration_ug_per_ml not in preset_concs
        and (
            inputs.concentration_ug_per_ml > max(preset_concs) * 2
            or inputs.concentration_ug_per_ml < min(preset_concs) / 4
        )
    ):
        warnings.append(
            f"Concentration {inputs.concentration_ug_per_ml} µg/mL is unusual. "
            f"Standard dilutions for this drug range around {min(preset_concs)}–{max(preset_concs)} µg/mL."
        )
    return warnings


def _check_warnings_single(config: CalculatorConfig, inputs: CalcInputs, weight_kg: float) -> list[str]:
    """Combined validation + range warnings.

    Retained for backward compatibility with any caller that wants the
    full warning list without the early-return semantics of compute().
    New code should use _validate_single_inputs + _check_range_warnings_single
    separately so invalid inputs short-circuit before any math runs.
    """
    errors = _validate_single_inputs(inputs, weight_kg)
    if errors:
        # Don't run range checks on invalid inputs — the dose-range
        # comparisons would be misleading when the inputs are nonsense.
        return errors
    return _check_range_warnings_single(config, inputs)


def _append_dose_warning(
    warnings: list[str],
    prefix: str,
    dose: float,
    unit: str,
    dose_range: DoseRange,
    species_name: str,
) -> None:
    if dose < dose_range.min:
        warnings.append(
            f"{prefix}Dose {dose} {unit} is below the typical range ({dose_range.min}–{dose_range.max})."
        )
    elif dose_range.hard_max is not None and dose > dose_range.hard_max:
        warnings.append(
            f"⚠ CAUTION: {prefix}Dose {dose} {unit} exceeds the {species_name} "
            f"safety ceiling of {dose_range.hard_max}. " + (dose_range.note or "")
        )
    elif dose > dose_range.max:
        warnings.append(
            f"{prefix}Dose {dose} {unit} is above the typical range ({dose_range.min}–{dose_range.max})."
        )
    # Caution threshold, fires alongside any other warning, when dose is
    # within range but above the species-specific caution level.
    if (
        dose_range.caution_threshold is not None
        and dose > dose_range.caution_threshold
        and (dose_range.hard_max is None or dose <= dose_range.hard_max)
        and dose_range.caution_note
    ):
        warnings.append(dose_range.caution_note)


# ---------------------------------------------------------------------------
# Dilution helper
# ---------------------------------------------------------------------------


@dataclass
class DilutionInputs:
    stock_concentration_ug_per_ml: float
    desired_concentration_ug_per_ml: float
    final_volume_ml: float


@dataclass
class DilutionResult:
    drug_volume_ml: float
    diluent_volume_ml: float
    drug_volume_ml_rounded: float
    diluent_volume_ml_rounded: float
    warnings: list[str] = field(default_factory=list)
    # See CalcResult.valid for the rationale. False when stock,
    # desired concentration, or final volume is missing or non-positive,
    # OR when desired exceeds stock (you can't dilute upward).
    valid: bool = True


def compute_dilution(inputs: DilutionInputs) -> DilutionResult:
    errors: list[str] = []
    if inputs.stock_concentration_ug_per_ml <= 0:
        errors.append("Stock concentration must be greater than zero.")
    if inputs.desired_concentration_ug_per_ml <= 0:
        errors.append("Desired concentration must be greater than zero.")
    if inputs.final_volume_ml <= 0:
        errors.append("Final volume must be greater than zero.")
    # Only meaningful to compare when both are positive; otherwise the
    # individual errors above already cover it.
    if (
        inputs.stock_concentration_ug_per_ml > 0
        and inputs.desired_concentration_ug_per_ml > 0
        and inputs.desired_concentration_ug_per_ml > inputs.stock_concentration_ug_per_ml
    ):
        errors.append("Desired concentration cannot exceed stock concentration, you can't dilute upward.")

    if errors:
        return DilutionResult(
            drug_volume_ml=0.0,
            diluent_volume_ml=0.0,
            drug_volume_ml_rounded=0.0,
            diluent_volume_ml_rounded=0.0,
            warnings=errors,
            valid=False,
        )

    drug_vol = (
        inputs.desired_concentration_ug_per_ml * inputs.final_volume_ml
    ) / inputs.stock_concentration_ug_per_ml
    diluent_vol = inputs.final_volume_ml - drug_vol

    return DilutionResult(
        drug_volume_ml=drug_vol,
        diluent_volume_ml=diluent_vol,
        drug_volume_ml_rounded=round(drug_vol, 2),
        diluent_volume_ml_rounded=round(diluent_vol, 2),
        warnings=[],
        valid=True,
    )
