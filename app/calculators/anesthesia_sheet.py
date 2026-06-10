"""
Anesthesia drug sheet calculator.

Generates a complete, printable drug dose reference card for a patient
undergoing anesthesia. Covers:
  - Patient info (name, age, species, weight)
  - Fluid bolus (shock, maintenance)
  - Premedication options (opioid + sedative combinations)
  - Induction options (propofol, alfaxalone, ketamine combos)
  - Maintenance reference (isoflurane, alfaxalone CRI)
  - Emergency drugs (epi, atropine, glycopyrrolate, naloxone, flumazenil, atipamezole)
  - CRI reference (dopamine, norepinephrine)

All doses from Plumb's Veterinary Drugs current edition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import WeightUnit, lb_to_kg


class AnesthSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


# ── Stock concentrations ──────────────────────────────────────────────────────
STOCKS = {
    "acepromazine": 10.0,  # 10 mg/mL
    "dexmedetomidine": 0.5,  # 0.5 mg/mL (500 µg/mL)
    "hydromorphone": 2.0,  # 2 mg/mL
    "buprenorphine": 0.3,  # 0.3 mg/mL
    "butorphanol": 10.0,  # 10 mg/mL
    "methadone": 10.0,  # 10 mg/mL
    "midazolam": 5.0,  # 5 mg/mL
    "propofol": 10.0,  # 10 mg/mL
    "alfaxalone": 10.0,  # 10 mg/mL
    "ketamine": 100.0,  # 100 mg/mL
    "epinephrine": 1.0,  # 1 mg/mL (1:1000)
    "atropine": 0.54,  # 0.54 mg/mL
    "glycopyrrolate": 0.2,  # 0.2 mg/mL
    "naloxone": 0.4,  # 0.4 mg/mL
    "flumazenil": 0.1,  # 0.1 mg/mL
    "atipamezole": 5.0,  # 5 mg/mL
    "dopamine": 40.0,  # 40 mg/mL
    "norepinephrine": 1.0,  # 1 mg/mL
    "lidocaine": 20.0,  # 20 mg/mL (2%)
}


# Per-drug concentration alternatives the worksheet picker offers as
# user-customizable. A drug is included here only when:
#   (1) multiple commonly-stocked concentrations exist in small-animal
#       practice (not theoretically available, actually encountered),
#   (2) the choice meaningfully affects what the worksheet renders
#       (volume math or printed label), AND
#   (3) the drug surfaces somewhere in the worksheet output (premed
#       picker, emergency drugs, etc.).
#
# Drugs that are theoretically multi-concentration but don't surface
# anywhere in the rendered worksheet (lidocaine — used only on the
# standalone CRI calculator) or whose worksheet section uses literal
# Plumb's volumes that don't read from STOCKS (ketamine — DKB table is
# fixed at 100 mg/mL by source) are intentionally absent. Adding them
# would render selectors that have no effect, which is worse than no
# selector at all.
#
# Long-acting / different-product variants are also excluded (e.g.,
# Simbadol 1.8 mg/mL is NOT listed as a buprenorphine option because
# the two products aren't dose-interchangeable).
#
# The first option in each tuple is the default and matches the value
# in STOCKS. The label is what shows in the picker dropdown and on
# the printed sheet's "Stock" column after a recompute.
STOCK_OPTIONS: dict[str, tuple[tuple[float, str], ...]] = {
    "hydromorphone": (
        (2.0, "2 mg/mL (standard)"),
        (1.0, "1 mg/mL"),
        (4.0, "4 mg/mL"),
        (10.0, "10 mg/mL"),
    ),
    "midazolam": (
        (5.0, "5 mg/mL (standard)"),
        (1.0, "1 mg/mL"),
    ),
    "dexmedetomidine": (
        (0.5, "0.5 mg/mL (standard)"),
        (0.1, "0.1 mg/mL"),
    ),
    "atropine": (
        (0.54, "0.54 mg/mL (standard)"),
        (0.4, "0.4 mg/mL"),
    ),
    "naloxone": (
        (0.4, "0.4 mg/mL (standard)"),
        (1.0, "1 mg/mL"),
    ),
}


# Request-scoped stock overrides. The router sets this at the start of
# each calculate() call (via `_chosen_stocks_var.set(...)`) so the
# `_drug()` factory and any other code path that reads stock values
# picks up the user's choice without us threading a dict through 20
# call sites. ContextVars are coroutine-safe; this works correctly
# under FastAPI's async request model even with concurrent requests.
import contextvars  # noqa: E402

_chosen_stocks_var: contextvars.ContextVar[dict[str, float]] = contextvars.ContextVar(
    "chosen_stocks", default={}
)


def _stock_for(key: str) -> float:
    """Resolve the effective stock concentration for a drug.

    Looks up the user's chosen value first (from the picker selector
    submitted with the form); falls back to the default in STOCKS.
    """
    chosen = _chosen_stocks_var.get()
    return chosen.get(key, STOCKS[key])


def _stock_label_for(key: str) -> str:
    """Human-readable label for the effective stock concentration.

    If the drug has alternative concentrations in STOCK_OPTIONS, returns
    the matching option's label so the printed worksheet reflects the
    user's choice (e.g., "0.4 mg/mL (human formulation)" vs "0.54 mg/mL
    (AVMA-standard vet)"). Otherwise renders a plain "X mg/mL" string.
    """
    stock = _stock_for(key)
    options = STOCK_OPTIONS.get(key)
    if options:
        for value, label in options:
            if value == stock:
                return label
    return f"{stock:g} mg/mL"


@dataclass
class DrugLine:
    name: str
    dose_label: str  # e.g. "0.01 mg/kg IV"
    dose_mg_per_kg_low: float
    dose_mg_per_kg_high: float
    stock_mg_per_ml: float
    stock_label: str
    vol_low_ml: float
    vol_high_ml: float
    route: str
    note: str = ""
    # Dose selector support
    chosen_dose_mg_per_kg: float = 0.0  # 0 = not yet chosen; use midpoint
    dose_input_step: float = 0.001  # step for the number input
    dose_display_multiplier: float = 1.0  # 1 for mg/kg, 1000 for µg/kg display
    dose_display_unit: str = "mg/kg"  # label shown next to input

    @property
    def effective_dose_mg_per_kg(self) -> float:
        """The dose to actually use, chosen if set, otherwise midpoint."""
        if self.chosen_dose_mg_per_kg > 0:
            return self.chosen_dose_mg_per_kg
        return round((self.dose_mg_per_kg_low + self.dose_mg_per_kg_high) / 2, 4)

    @property
    def chosen_vol_ml(self) -> float:
        return round(self.effective_dose_mg_per_kg * self._weight_kg / self.stock_mg_per_ml, 3)

    # weight_kg injected after construction
    _weight_kg: float = 0.0


@dataclass
class CRITitrationStep:
    """One row of an inline anesthesia-hub titration ladder.

    Mirrors engine.TitrationStep but is computed locally in this module
    to avoid coupling the anesthesia sheet to the SINGLE_DRUG_CRI engine
    (the sheet builds its own preps with bespoke concentrations that don't
    match the engine drug configs).
    """

    dose_ug_per_kg_per_min: float
    ml_per_hr: float
    is_caution: bool


@dataclass
class CRILine:
    name: str
    dose_label: str
    rate_low_ml_per_hr: float
    rate_high_ml_per_hr: float
    prep_note: str
    note: str = ""
    # Per-step pump-rate ladder for fast titration. Empty when not applicable
    # (e.g., dopamine on the 6×kg prep already gives 1:1 mL/hr → µg/kg/min,
    # so no lookup table is needed). The bag concentration this is calibrated
    # to is shown next to the table heading so a tech can verify.
    titration_steps: tuple[CRITitrationStep, ...] = ()
    # Concentration the steps are computed against; surfaced in the table
    # header so a clinician/tech can sanity-check the prep matches the bag.
    titration_concentration_label: str = ""


@dataclass
class BolusLine:
    """Bridge bolus dosing for phenylephrine and ephedrine.

    Different shape than CRILine because these are dose-per-bolus drugs, not
    continuous-rate drugs. A clinician picks a dose within the species range,
    draws a volume from the prepared dilution, and gives the bolus. If the
    patient needs repeat dosing to hold MAP at target, the call is to switch
    to a CRI (the article's intervention ladder, step 4).

    Bolus drugs are simpler than CRIs to compute: one fixed dilution per drug
    covers the full clinical weight range cleanly. We render a volume range
    for the patient at the dose-range bounds, plus the prep note.
    """
    name: str
    dose_label: str          # e.g., "1–10 µg/kg IV"
    volume_low_ml: float     # volume at the low end of the dose range
    volume_high_ml: float    # volume at the high end
    prep_note: str           # how to prepare the bolus dilution
    note: str                # when to use this drug; bridge-to-CRI guidance


@dataclass
class AnesthesiaSheet:
    # Patient info
    patient_name: str
    patient_age: str
    species: AnesthSpecies
    weight_kg: float
    weight_display: str  # original input for display

    # Fluids
    blood_volume_ml: float
    shock_quarter_dose_ml: float
    shock_full_dose_ml: float
    maintenance_ml_per_hr: float
    maintenance_rate_ml_per_kg_per_hr: float
    fluid_bolus_low_ml: float
    fluid_bolus_high_ml: float

    # Anesthesia circuit rebreathing bag selection (preop preparation).
    # Formula: bag volume (L) = (weight_kg × tidal_volume × multiplier) / 1000
    # Tidal volume = 15 mL/kg; multiplier = 6× (3–5× TV minimum, 6× gives
    # comfortable margin). Recommend the next standard bag size up:
    # 0.5 L, 1 L, 2 L, 3 L, 5 L.
    circuit_bag_calculated_l: float
    circuit_bag_recommended_l: float
    # True when the formula's required volume exceeds the largest stocked
    # rebreathing bag (5 L). These patients need a non-rebreathing/Bain
    # circuit, a larger reservoir, or a different machine, not the 5 L
    # default. Surfaced as a warning in the preop sheet.
    circuit_bag_exceeds_max: bool
    # True when the patient is small enough that a rebreathing circuit is
    # not appropriate regardless of bag size — non-rebreathing (Mapleson D,
    # Bain, T-piece) is the right setup. Threshold ≈3 kg.
    circuit_use_nonrebreathing: bool

    # Premeds, grouped by category
    premed_opioids: list[DrugLine]
    premed_sedatives: list[DrugLine]

    # Induction
    induction_drugs: list[DrugLine]

    # DKB (cats only. None for dogs)
    dkb_protocols: list[dict] | None

    # Emergency
    emergency_drugs: list[DrugLine]

    # Bridge boluses (phenylephrine, ephedrine) — administered before/during
    # CRI preparation; if MAP requires repeat dosing, switch to a CRI.
    phenylephrine_bolus: BolusLine
    ephedrine_bolus: BolusLine

    # CRIs
    dopamine_cri: CRILine
    dobutamine_cri: CRILine
    norepi_cri: CRILine

    warnings: list[str] = field(default_factory=list)


def _vol(dose_mg_per_kg: float, weight_kg: float, stock_mg_per_ml: float) -> float:
    return round((dose_mg_per_kg * weight_kg) / stock_mg_per_ml, 3)


def _build_cri_ladder(
    doses_ug_per_kg_per_min: tuple[float, ...],
    weight_kg: float,
    concentration_ug_per_ml: float,
    caution_threshold_ug_per_kg_per_min: float | None,
) -> tuple[CRITitrationStep, ...]:
    """Build a per-step pump-rate table for one anesthesia-hub pressor.

    Same math as engine.compute() for SINGLE_DRUG_CRI: the row at each dose
    in `doses` shows what the pump should be set to at the patient's weight
    on the bag at the given concentration. is_caution fires at-or-above the
    threshold; threshold may be None to disable caution flagging entirely.
    """
    if weight_kg <= 0 or concentration_ug_per_ml <= 0:
        return ()
    steps: list[CRITitrationStep] = []
    for dose in doses_ug_per_kg_per_min:
        ml_per_hr = (weight_kg * dose / concentration_ug_per_ml) * 60
        is_caution = (
            caution_threshold_ug_per_kg_per_min is not None
            and dose > caution_threshold_ug_per_kg_per_min
        )
        steps.append(
            CRITitrationStep(
                dose_ug_per_kg_per_min=dose,
                ml_per_hr=round(ml_per_hr, 2),
                is_caution=is_caution,
            )
        )
    return tuple(steps)


# Minimum pump rate (mL/hr) considered reliable on a standard IV infusion
# pump. Below this, accuracy degrades and titration in 0.1 mL/hr increments
# becomes unreliable; a syringe pump is the clinical alternative. The 2
# mL/hr threshold is conservative; some pumps are accurate to 1 mL/hr but
# clinicians generally prefer a syringe pump at-or-below 2 mL/hr.
_MIN_RELIABLE_IV_PUMP_RATE_ML_PER_HR = 2.0


def _pick_cri_dilution(
    *,
    weight_kg: float,
    threshold_dose_ug_per_kg_per_min: float,
    available_concentrations_ug_per_ml: tuple[float, ...],
) -> tuple[float, bool]:
    """Pick the most concentrated dilution from `available_concentrations`
    such that the pump rate at `threshold_dose_ug_per_kg_per_min` for this
    patient is at or above the minimum reliable IV-pump rate.

    Returns (concentration_ug_per_ml, below_reliable_threshold) where the
    second element is True when even the most dilute available preparation
    still produces a sub-2 mL/hr pump rate at the threshold dose. In that
    case the caller should add a syringe-pump note to the prep_note since
    a standard IV pump cannot reliably deliver at this rate.

    `available_concentrations_ug_per_ml` must be non-empty. The order is
    irrelevant; the function sorts internally.

    The "threshold dose" is the lowest dose on the titration ladder for
    most drugs, but for norepinephrine it is the working anchor (0.1
    µg/kg/min) rather than the absolute ladder floor (0.05 µg/kg/min),
    because 0.05 is the absolute low and a clinician is rarely actually
    titrating to that rate.
    """
    if weight_kg <= 0 or not available_concentrations_ug_per_ml:
        # Defensive: caller should never hit this branch, but if they do,
        # fall back to whatever was passed (the first option) and flag.
        return available_concentrations_ug_per_ml[0], True

    # Sort descending: try the most concentrated first; the first option
    # that meets the threshold wins. This keeps the bag at the closest
    # standard prep when possible and only dilutes further for smaller
    # patients.
    sorted_concs = sorted(available_concentrations_ug_per_ml, reverse=True)

    for conc in sorted_concs:
        ml_per_hr_at_threshold = (
            weight_kg * threshold_dose_ug_per_kg_per_min * 60 / conc
        )
        if ml_per_hr_at_threshold >= _MIN_RELIABLE_IV_PUMP_RATE_ML_PER_HR:
            return conc, False

    # No preparation in the menu hits the IV-pump threshold. Return the
    # most dilute option so the worksheet still computes a rate; the
    # caller should add a "syringe pump required" note.
    return sorted_concs[-1], True





def _drug(
    name: str,
    dose_label: str,
    low: float,
    high: float,
    stock_key: str,
    stock_label: str,
    weight_kg: float,
    route: str,
    note: str = "",
    default_dose: float | None = None,
) -> DrugLine:
    """Build a DrugLine for the picker.

    `low`, `high`, and `default_dose` are accepted in the DISPLAY unit
    (µg/kg for dexmedetomidine, mg/kg for every other drug) and converted
    to the storage unit (always mg/kg) here.

    This unit policy lets every call site read naturally in the unit a
    clinician sees on screen. The previous convention (everything stored
    in mg/kg, including dex) forced dex defaults to be written as e.g.
    0.000005 mg/kg instead of 5 µg/kg — easy to miscount the zeros on, and
    easy to confuse with the milligram-scale ranges of every other drug.
    That awkwardness used to be worked around with a post-construction
    DrugLine rebuild that overwrote the _drug() path. With this version,
    one helper, one unit per drug, one code path — no rebuild needed.
    """
    s = _stock_for(stock_key)
    # If this drug has multiple concentrations in STOCK_OPTIONS, the
    # label needs to reflect the chosen one. Otherwise the printed
    # worksheet still says "2 mg/mL" after the user picks 4 mg/mL.
    # For drugs not in STOCK_OPTIONS, the caller-provided label is used
    # as-is so callers can include extra detail like "(1:1000)" that
    # isn't in the STOCK_OPTIONS labels.
    effective_label = (
        _stock_label_for(stock_key)
        if stock_key in STOCK_OPTIONS
        else stock_label
    )
    is_dex = stock_key == "dexmedetomidine"
    multiplier = 1000.0 if is_dex else 1.0
    low_mg_per_kg = low / multiplier
    high_mg_per_kg = high / multiplier
    chosen = (default_dose / multiplier) if default_dose is not None else 0.0
    return DrugLine(
        name=name,
        dose_label=dose_label,
        dose_mg_per_kg_low=low_mg_per_kg,
        dose_mg_per_kg_high=high_mg_per_kg,
        stock_mg_per_ml=s,
        stock_label=effective_label,
        vol_low_ml=_vol(low_mg_per_kg, weight_kg, s),
        vol_high_ml=_vol(high_mg_per_kg, weight_kg, s),
        route=route,
        note=note,
        chosen_dose_mg_per_kg=chosen,
        dose_input_step=0.1 if is_dex else 0.001,
        dose_display_multiplier=multiplier,
        dose_display_unit="µg/kg" if is_dex else "mg/kg",
        _weight_kg=weight_kg,
    )


def calculate(
    weight_value: float,
    weight_unit: WeightUnit,
    species: AnesthSpecies,
    patient_name: str = "",
    patient_age: str = "",
    chosen_stocks: dict[str, float] | None = None,
) -> AnesthesiaSheet:
    # Bind the user's chosen concentrations to the ContextVar so every
    # _drug() and _stock_for() call in this calculation sees them. Reset
    # at the end so concurrent requests don't leak state.
    _stocks_token = _chosen_stocks_var.set(chosen_stocks or {})
    try:
        return _calculate_impl(
            weight_value, weight_unit, species, patient_name, patient_age
        )
    finally:
        _chosen_stocks_var.reset(_stocks_token)


def _calculate_impl(
    weight_value: float,
    weight_unit: WeightUnit,
    species: AnesthSpecies,
    patient_name: str = "",
    patient_age: str = "",
) -> AnesthesiaSheet:

    weight_kg = lb_to_kg(weight_value) if weight_unit == WeightUnit.LB else weight_value
    weight_display = (
        f"{weight_value:.1f} {'lb' if weight_unit == WeightUnit.LB else 'kg'} ({weight_kg:.2f} kg)"
    )

    is_dog = species == AnesthSpecies.DOG

    # ── Fluids ────────────────────────────────────────────────────────────────
    # Blood volume: dogs 80–90 mL/kg, cats 50–60 mL/kg (Chohan & Davidow, Lumb & Jones 6e)
    # Shock dose = up to 1 blood volume in 1 hr, given in ¼-dose aliquots
    # per Chohan: "starting with one-quarter to one-third of the shock dose
    # given incrementally with constant monitoring"
    # Maintenance: AAHA/AAFP, 5 mL/kg/hr dogs, 3 mL/kg/hr cats
    # Fluid bolus for intraoperative hypotension: 5–10 mL/kg crystalloid over
    # 10–15 minutes (Lumb & Jones, Hypotension management chapter). This is
    # the therapeutic bolus used in the article's Step 2 intervention ladder.
    # Not appropriate in cardiac, advanced renal, or known volume-overload
    # patients — see the article scope notes.

    if is_dog:
        blood_vol_per_kg = 90.0  # mL/kg (upper end of 80–90 range)
        maintenance_per_kg_hr = 5.0  # mL/kg/hr. AAHA/AAFP
    else:
        blood_vol_per_kg = 60.0  # mL/kg (upper end of 50–60 range)
        maintenance_per_kg_hr = 3.0  # mL/kg/hr. AAHA/AAFP

    blood_volume_ml = round(blood_vol_per_kg * weight_kg, 0)
    shock_full_dose_ml = blood_volume_ml  # 1 blood volume
    shock_quarter_dose_ml = round(shock_full_dose_ml / 4, 0)  # ¼ dose aliquot
    maintenance_ml_per_hr = round(maintenance_per_kg_hr * weight_kg, 1)
    fluid_bolus_low_ml = round(5 * weight_kg, 1)
    fluid_bolus_high_ml = round(10 * weight_kg, 1)

    # Anesthesia circuit rebreathing bag size.
    #   bag (L) = (weight_kg × tidal_volume × multiplier) / 1000
    # Tidal volume 15 mL/kg, multiplier 6× (covers ≥3–5× TV with margin).
    # Calculated value is informational; recommendation is the next
    # standard bag size up (0.5 / 1 / 2 / 3 / 5 L). Patients with
    # required volume above the largest stocked bag (5 L) get a flag —
    # those need a larger reservoir or non-rebreathing setup. Patients
    # under ~3 kg get a different flag — rebreathing circuits aren't
    # appropriate at all and a non-rebreathing system (Bain, T-piece,
    # Mapleson) is the right setup regardless of which "size" the
    # formula picks.
    _STANDARD_BAG_SIZES_L = (0.5, 1.0, 2.0, 3.0, 5.0)
    circuit_bag_calculated_l = round((weight_kg * 15 * 6) / 1000, 2)
    circuit_bag_exceeds_max = circuit_bag_calculated_l > _STANDARD_BAG_SIZES_L[-1]
    circuit_use_nonrebreathing = weight_kg < 3.0
    # Always pick from the stocked list; never invent a size that doesn't
    # exist on the shelf. When the calculated need is greater than the
    # largest bag, the recommendation is the largest bag and
    # circuit_bag_exceeds_max is True so the UI can flag it.
    circuit_bag_recommended_l = next(
        (size for size in _STANDARD_BAG_SIZES_L if size >= circuit_bag_calculated_l),
        _STANDARD_BAG_SIZES_L[-1],
    )

    # ── Premed opioids ────────────────────────────────────────────────────────
    if is_dog:
        premed_opioids = [
            _drug(
                "Hydromorphone",
                "0.05–0.2 mg/kg",
                0.05,
                0.2,
                "hydromorphone",
                "2 mg/mL",
                weight_kg,
                "IM/IV",
                "Full µ-agonist. Duration ≥2 h IV, up to 4 h. "
                "Vomiting common IM, maropitant 1 mg/kg SC 15–30 min prior prevents it (Simon & Lizarraga, Ch. 23). "
                "Panting, defecation common. Less histamine release than morphine.",
                default_dose=0.1,
            ),
            _drug(
                "Methadone",
                "0.2–0.3 mg/kg",
                0.2,
                0.3,
                "methadone",
                "10 mg/mL",
                weight_kg,
                "IM/IV",
                "Full µ-agonist with NMDA antagonism (both isomers). Duration ~4 h IV/IM. "
                "Less vomiting than hydromorphone or morphine pre-anesthesia. "
                "Extra-label use, no veterinary-labeled product (use human 10 mg/mL injection). "
                "DEA Schedule II.",
                default_dose=0.2,
            ),
            _drug(
                "Butorphanol",
                "0.2–0.4 mg/kg",
                0.2,
                0.4,
                "butorphanol",
                "10 mg/mL",
                weight_kg,
                "IM/IV",
                "Kappa agonist / µ partial antagonist. Better sedation than analgesia in dogs. "
                "Short analgesic duration (~1 hr). Useful when procedure is minimally painful or for co-induction sedation.",
                default_dose=0.2,
            ),
            _drug(
                "Buprenorphine",
                "0.01–0.02 mg/kg",
                0.01,
                0.02,
                "buprenorphine",
                "0.3 mg/mL",
                weight_kg,
                "IM/IV",
                "Partial µ-agonist. Duration 6–8 hr (Ch. 23). Onset slow (30 min IM). "
                "SC absorption unreliable with standard 0.3 mg/mL formulation, use IM or IV (Simon & Lizarraga).",
                default_dose=0.01,
            ),
        ]
    else:
        premed_opioids = [
            _drug(
                "Buprenorphine",
                "0.01–0.02 mg/kg",
                0.01,
                0.02,
                "buprenorphine",
                "0.3 mg/mL",
                weight_kg,
                "IM/IV/OTM",
                "Partial µ-agonist. Duration 4–8 hr (Ch. 23). OTM bioavailability ~20–30%, use upper dose range. "
                "SC absorption unreliable (standard 0.3 mg/mL). Monitor temp post-anesthesia (hyperthermia reported).",
                default_dose=0.02,
            ),
            _drug(
                "Methadone",
                "0.1–0.3 mg/kg",
                0.1,
                0.3,
                "methadone",
                "10 mg/mL",
                weight_kg,
                "IM/IV",
                "Full µ-agonist with NMDA antagonism. Duration ~4 h. Generally well tolerated in cats; "
                "less hyperthermia than hydromorphone. Higher doses (0.4–0.6 mg/kg) used in deep-sedation "
                "protocols. Extra-label, DEA Schedule II.",
                default_dose=0.2,
            ),
            _drug(
                "Butorphanol",
                "0.2–0.4 mg/kg",
                0.2,
                0.4,
                "butorphanol",
                "10 mg/mL",
                weight_kg,
                "IM",
                "Kappa agonist. Duration 1–2 hr analgesia, 2–4 hr sedation. "
                "Prevents dexmedetomidine-induced vomiting in cats (Ch. 23). Euphoria and dysphoria both reported.",
                default_dose=0.3,
            ),
            _drug(
                "Hydromorphone",
                "0.025–0.1 mg/kg",
                0.025,
                0.1,
                "hydromorphone",
                "2 mg/mL",
                weight_kg,
                "IM/IV",
                "Hyperthermia risk; monitor temperature closely. Naloxone reverses rapidly if temp >42.2°C. "
                "Start at low end (0.025 mg/kg). Onset 15 min IM, duration ~345 min (Simon & Lizarraga, Ch. 23).",
                default_dose=0.05,
            ),
        ]

    # ── Premed sedatives ──────────────────────────────────────────────────────
    if is_dog:
        premed_sedatives = [
            _drug(
                "Dexmedetomidine",
                "3–20 µg/kg",
                3.0,
                20.0,
                "dexmedetomidine",
                "0.5 mg/mL",
                weight_kg,
                "IM",
                "Expect bradycardia + pale MMs (vasoconstriction). Reversible with atipamezole.",
                default_dose=5.0,  # µg/kg — start-low guidance when combined with an opioid
            ),
            _drug(
                "Acepromazine",
                "0.02–0.05 mg/kg",
                0.02,
                0.05,
                "acepromazine",
                "10 mg/mL",
                weight_kg,
                "IM",
                "Max 3 mg total dose regardless of weight. Not reversible. "
                "α₁ blockade → vasodilation and 20–30% ↓MAP (Creighton & Lamont, Ch. 22). "
                "Avoid in hypovolemia, shock, brachycephalics with high vagal tone. "
                "Antiemetic, reduces opioid-induced vomiting from 45% to 18%.",
                default_dose=0.02,
            ),
            _drug(
                "Midazolam",
                "0.1–0.3 mg/kg",
                0.1,
                0.3,
                "midazolam",
                "5 mg/mL",
                weight_kg,
                "IM/IV",
                "Minimal sedation alone in healthy dogs, best as co-induction agent IV with propofol/alfaxalone. "
                "Reliable IM absorption (bioavailability 50–90%). Reversible with flumazenil. "
                "Paradoxical excitement common in healthy animals at higher doses.",
                default_dose=0.2,
            ),
        ]
    else:
        premed_sedatives = [
            _drug(
                "Dexmedetomidine",
                "10–40 µg/kg",
                10.0,
                40.0,
                "dexmedetomidine",
                "0.5 mg/mL",
                weight_kg,
                "IM",
                "Expect bradycardia + pale/grey MMs. Reversible. 40 µg/kg = label dose.",
                default_dose=10.0,  # µg/kg — 10–20 µg/kg sufficient with opioid per Plumb's
            ),
            _drug(
                "Midazolam",
                "0.1–0.3 mg/kg",
                0.1,
                0.3,
                "midazolam",
                "5 mg/mL",
                weight_kg,
                "IM/IV",
                "Combine with opioid for premed. Reliable IM absorption. Muscle relaxation. "
                "Paradoxical excitement common in healthy cats at higher doses. Reversible with flumazenil.",
                default_dose=0.2,
            ),
            _drug(
                "Acepromazine",
                "0.02–0.05 mg/kg",
                0.02,
                0.05,
                "acepromazine",
                "10 mg/mL",
                weight_kg,
                "IM",
                "Max 1 mg total in cats. Not reversible. Antiemetic properties. "
                "Peripheral vasodilation, avoid in hypovolemia. No analgesic properties alone.",
                default_dose=0.02,
            ),
        ]

    # Pull dex's low/high IM volumes off the already-built DrugLine.
    # Atipamezole IM is given at the same volume as the dexmedetomidine
    # IM dose (clinical convention; the alpha-2 reversal volume mirrors
    # whatever dose volume was actually used), so the emergency-drugs
    # section below uses these to overwrite atipamezole's volume range.
    dex_vol_low = premed_sedatives[0].vol_low_ml
    dex_vol_high = premed_sedatives[0].vol_high_ml

    # ── Induction ─────────────────────────────────────────────────────────────
    if is_dog:
        induction_drugs = [
            _drug(
                "Propofol",
                "2–6 mg/kg",
                2.0,
                6.0,
                "propofol",
                "10 mg/mL",
                weight_kg,
                "IV slow to effect",
                "Premedicated: 2–4 mg/kg; unpremedicated: 4–6 mg/kg. Titrate over 60–90 s. "
                "No analgesia. Apnea common, intubation and O₂ must be immediately available.",
                default_dose=6.0,
            ),
            _drug(
                "Alfaxalone",
                "1.1–4.5 mg/kg",
                1.1,
                4.5,
                "alfaxalone",
                "10 mg/mL",
                weight_kg,
                "IV slow to effect",
                "Premedicated: 1.1–1.7 mg/kg; unpremedicated: 1.5–4.5 mg/kg. Titrate to effect. "
                "No analgesia. Apnea risk, have intubation ready. Quiet recovery environment.",
                default_dose=4.5,
            ),
        ]
        dkb_protocols = None
    else:
        induction_drugs = [
            _drug(
                "Alfaxalone",
                "2.3–9.7 mg/kg",
                2.3,
                9.7,
                "alfaxalone",
                "10 mg/mL",
                weight_kg,
                "IV slow to effect",
                "Premedicated: 2.3–3.6 mg/kg; unpremedicated: higher. Titrate over ~60 s. "
                "No analgesia. Apnea risk, intubation and O₂ must be immediately available. Quiet recovery.",
                default_dose=5.0,
            ),
            _drug(
                "Propofol",
                "2–8 mg/kg",
                2.0,
                8.0,
                "propofol",
                "10 mg/mL",
                weight_kg,
                "IV slow to effect",
                "Premedicated: 2–4 mg/kg; unpremedicated: higher. Titrate slowly, apnea common. "
                "No analgesia. AVOID repeated daily use in cats (Heinz body formation). Aseptic technique essential.",
                default_dose=6.0,
            ),
        ]

        # ── DKB (Kitty Magic), cats only ─────────────────────────────────────
        # Equal volumes of dex 0.5 mg/mL + ketamine 100 mg/mL + opioid IM
        # Volumes from Plumb's table by weight band (per drug = equal volume each)
        def _dkb_vol(wkg: float, level: str) -> tuple[float, float]:
            table = [
                (2.0, 3.0, {"mild": (0.025, 0.025), "moderate": (0.05, 0.05), "profound": (0.10, 0.15)}),
                (3.0, 4.0, {"mild": (0.05, 0.05), "moderate": (0.10, 0.10), "profound": (0.20, 0.25)}),
                (4.0, 6.0, {"mild": (0.10, 0.10), "moderate": (0.20, 0.20), "profound": (0.30, 0.35)}),
                (6.0, 7.0, {"mild": (0.20, 0.20), "moderate": (0.30, 0.30), "profound": (0.40, 0.45)}),
                (7.0, 8.0, {"mild": (0.30, 0.30), "moderate": (0.40, 0.40), "profound": (0.50, 0.55)}),
            ]
            for wmin, wmax, levels in table:
                if wmin <= wkg <= wmax:
                    return levels[level]
            return table[0][2][level] if wkg < 2.0 else table[-1][2][level]

        dkb_level_labels = {
            "mild": "Mild: preanesthesia / sedation",
            "moderate": "Moderate: castration / minor surgery",
            "profound": "Profound: OHE / invasive surgery",
        }

        dkb_protocols = []
        for level in ["mild", "moderate", "profound"]:
            vlow, vhigh = _dkb_vol(weight_kg, level)

            def _fmt(low, high, unit):
                if low == high:
                    return f"{low} {unit}"
                return f"{low}–{high} {unit}"

            dex_ug_low = round(vlow * 500, 1)
            dex_ug_high = round(vhigh * 500, 1)
            ket_mg_low = round(vlow * 100, 2)
            ket_mg_high = round(vhigh * 100, 2)
            but_mg_low = round(vlow * 10, 3)
            but_mg_high = round(vhigh * 10, 3)
            bup_ug_low = round(vlow * 300, 1)
            bup_ug_high = round(vhigh * 300, 1)

            dkb_protocols.append(
                {
                    "level": level,
                    "label": dkb_level_labels[level],
                    "vol_low": vlow,
                    "vol_high": vhigh,
                    "total_low": round(vlow * 3, 3),
                    "total_high": round(vhigh * 3, 3),
                    "dex_label": _fmt(int(dex_ug_low), int(dex_ug_high), "µg"),
                    "ket_label": _fmt(f"{ket_mg_low:.1f}", f"{ket_mg_high:.1f}", "mg"),
                    "but_label": _fmt(f"{but_mg_low:.3f}", f"{but_mg_high:.3f}", "mg"),
                    "bup_label": _fmt(int(bup_ug_low), int(bup_ug_high), "µg"),
                    "dex_per_kg": _fmt(
                        round(dex_ug_low / weight_kg, 1), round(dex_ug_high / weight_kg, 1), "µg/kg"
                    ),
                    "ket_per_kg": _fmt(
                        round(ket_mg_low / weight_kg, 2), round(ket_mg_high / weight_kg, 2), "mg/kg"
                    ),
                    "but_per_kg": _fmt(
                        round(but_mg_low / weight_kg, 3), round(but_mg_high / weight_kg, 3), "mg/kg"
                    ),
                    "bup_per_kg": _fmt(
                        round(bup_ug_low / weight_kg, 1), round(bup_ug_high / weight_kg, 1), "µg/kg"
                    ),
                    "atipa_vol_low": vlow,
                    "atipa_vol_high": vhigh,
                }
            )

    # Recalculate with correct stock
    def _emerg(name, dose_label, low_mg_kg, high_mg_kg, stock_mg_ml, stock_label, route, note=""):
        return DrugLine(
            name=name,
            dose_label=dose_label,
            dose_mg_per_kg_low=low_mg_kg,
            dose_mg_per_kg_high=high_mg_kg,
            stock_mg_per_ml=stock_mg_ml,
            stock_label=stock_label,
            vol_low_ml=round(low_mg_kg * weight_kg / stock_mg_ml, 3),
            vol_high_ml=round(high_mg_kg * weight_kg / stock_mg_ml, 3),
            route=route,
            note=note,
        )

    emergency_drugs = [
        # RECOVER 2024 single doses where specified; ranges kept for perioperative anticholinergics
        _emerg(
            "Epinephrine",
            "0.01 mg/kg",
            0.01,
            0.01,
            1.0,
            "1 mg/mL (1:1000)",
            "IV/IO",
            "CPA. RECOVER 2024. Repeat q 3–5 min.",
        ),
        _emerg(
            "Atropine",
            "0.02–0.04 mg/kg",
            0.02,
            0.04,
            _stock_for("atropine"),
            _stock_label_for("atropine"),
            "IV/IM",
            "Perioperative bradycardia. Rapid IV. Titrate to effect.",
        ),
        _emerg(
            "Glycopyrrolate",
            "0.005–0.01 mg/kg",
            0.005,
            0.01,
            0.2,
            "0.2 mg/mL",
            "IV/IM",
            "Perioperative bradycardia. Slower onset than atropine; does not cross BBB.",
        ),
        _emerg(
            "Naloxone",
            "0.04 mg/kg",
            0.04,
            0.04,
            _stock_for("naloxone"),
            _stock_label_for("naloxone"),
            "IV/IM/intranasal",
            "Opioid reversal. RECOVER 2024. Short duration, may need repeat. Reverses analgesia.",
        ),
        _emerg(
            "Flumazenil",
            "0.01 mg/kg",
            0.01,
            0.01,
            0.1,
            "0.1 mg/mL",
            "IV",
            "Benzodiazepine reversal. RECOVER 2024. Short duration, monitor for resedation.",
        ),
        _emerg(
            "Atipamezole",
            "100 µg/kg IM",
            0.1,
            0.1,
            5.0,
            "5 mg/mL",
            "IM",
            "Alpha-2 reversal. RECOVER 2024. Give same volume IM as dexmedetomidine dose.",
        ),
    ]
    # Atipamezole: give same volume IM as dexmedetomidine was given
    # (clinical convention, mirrors the dex dose volume regardless of RECOVER fixed dose)
    emergency_drugs[-1].vol_low_ml = dex_vol_low
    emergency_drugs[-1].vol_high_ml = dex_vol_high

    # ── Bridge bolus pressors (phenylephrine, ephedrine) ──────────────────────
    # These are used during preparation of a CRI: a single bolus can buy
    # 10–15 minutes while the bag is being mixed and the pump is being set
    # up. If the patient needs repeat bolus dosing to maintain MAP, that is
    # the trigger to commit to a CRI (article: "if the patient needs repeat
    # bolus dosing to maintain MAP above 65 mmHg, it is time to commit to a
    # continuous rate infusion"). The texts (Plumb's, Lumb & Jones, BSAVA)
    # don't specify a number of boluses before transitioning; the rule on
    # this worksheet matches the article's "bridge" framing rather than
    # picking a fixed count.

    # Phenylephrine: pure α₁ agonist. Dose 1–10 µg/kg IV. Stock 10 mg/mL.
    # Standard bedside dilution to 100 µg/mL (1:100 with NaCl) covers the
    # full clinical weight range: 1.5 kg patient at 1 µg/kg → 0.015 mL of
    # stock, but 0.15 mL of the 100 µg/mL prep — drawable with a TB syringe.
    # 40 kg patient at 10 µg/kg → 4 mL of prep.
    phenyl_dilute_ug_per_ml = 100.0
    phenyl_low_dose_ug = 1.0 * weight_kg
    phenyl_high_dose_ug = 10.0 * weight_kg
    phenyl_low_vol = round(phenyl_low_dose_ug / phenyl_dilute_ug_per_ml, 3)
    phenyl_high_vol = round(phenyl_high_dose_ug / phenyl_dilute_ug_per_ml, 3)
    phenylephrine_bolus = BolusLine(
        name="Phenylephrine",
        dose_label="1–10 µg/kg IV",
        volume_low_ml=phenyl_low_vol,
        volume_high_ml=phenyl_high_vol,
        prep_note=(
            "Dilute to 100 µg/mL: draw 1 mL of 10 mg/mL phenylephrine stock, "
            "add to 99 mL of 0.9% NaCl. Bolus volume scales with patient weight "
            "at the chosen dose."
        ),
        note=(
            "Pure α₁ agonist. Vasoconstriction without inotropy. Use when "
            "bradycardia is not a concern. Bridge to a CRI if MAP requires "
            "repeat bolus dosing."
        ),
    )

    # Ephedrine: mixed α/β with indirect catecholamine release — gives both
    # pressor and modest inotropic/chronotropic effect. Dose 0.05–0.1 mg/kg IV.
    # Stock 50 mg/mL. Standard bedside dilution to 1 mg/mL (1:50 with NaCl)
    # covers the full clinical weight range: 1.5 kg at 0.05 mg/kg → 0.075 mg
    # = 0.075 mL of prep (drawable with a TB syringe); 40 kg at 0.1 mg/kg
    # → 4 mg = 4 mL of prep.
    ephedrine_dilute_mg_per_ml = 1.0
    ephedrine_low_dose_mg = 0.05 * weight_kg
    ephedrine_high_dose_mg = 0.1 * weight_kg
    ephedrine_low_vol = round(ephedrine_low_dose_mg / ephedrine_dilute_mg_per_ml, 3)
    ephedrine_high_vol = round(ephedrine_high_dose_mg / ephedrine_dilute_mg_per_ml, 3)
    ephedrine_bolus = BolusLine(
        name="Ephedrine",
        dose_label="0.05–0.1 mg/kg IV",
        volume_low_ml=ephedrine_low_vol,
        volume_high_ml=ephedrine_high_vol,
        prep_note=(
            "Dilute to 1 mg/mL: draw 1 mL of 50 mg/mL ephedrine stock, add "
            "to 49 mL of 0.9% NaCl. Bolus volume scales with patient weight "
            "at the chosen dose."
        ),
        note=(
            "Mixed α/β with indirect catecholamine release. Useful when "
            "bradycardia accompanies hypotension. Bridge to a CRI if MAP "
            "requires repeat bolus dosing."
        ),
    )

    # ── Dopamine CRI ──────────────────────────────────────────────────────────
    # Murrell, Lumb & Jones 6e Ch. 21:
    # β₁ effects dominate <10 µg/kg/min; α₁ predominates ≥10 µg/kg/min.
    # In isoflurane-anesthetized dogs, <7 µg/kg/min was insufficient for MAP >70 mmHg;
    # marked SVR↑ + SV↓ at ≥10 µg/kg/min. Cats need ~10 µg/kg/min for MAP >70.
    # Proarrhythmogenic ≥10 µg/kg/min. Wean stepwise, abrupt cessation → rebound hypotension.
    # "Renal-dose" dopamine concept (1–2 µg/kg/min) is discredited; increased UO
    # is hemodynamic, not receptor-specific (Murrell citing current evidence).
    #
    # Standard preparation: 400 mg dopamine in a 250 mL bag → 1600 µg/mL.
    # Smaller patients use a more dilute preparation so the lowest titration
    # dose (5 µg/kg/min) still produces a reliable IV-pump rate (≥2 mL/hr).
    # Auto-dilution math is in _pick_cri_dilution().
    dopamine_ladder_doses = (5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0)
    # Available standard dopamine preparations, all in a 250 mL NaCl bag.
    # The 1600 µg/mL prep is the conventional adult-dog bag; the more
    # dilute options are used to keep small-patient pump rates above 2 mL/hr
    # at the lowest ladder dose (5 µg/kg/min). The 200 µg/mL prep covers
    # very small patients (down to ~1.5 kg) at a 0.5 mL stock draw, which
    # is the practical lower bound for accurate vial-to-syringe transfer.
    dopamine_dilutions = {
        1600.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 10 mL. Draw 10 mL "
            "(400 mg) of 40 mg/mL dopamine stock and add it to the bag. "
            "Final concentration: 1600 µg/mL.",
            "1600 µg/mL bag (400 mg in 250 mL)",
        ),
        800.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 5 mL. Draw 5 mL "
            "(200 mg) of 40 mg/mL dopamine stock and add it to the bag. "
            "Final concentration: 800 µg/mL.",
            "800 µg/mL bag (200 mg in 250 mL)",
        ),
        400.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 2.5 mL. Draw 2.5 mL "
            "(100 mg) of 40 mg/mL dopamine stock and add it to the bag. "
            "Final concentration: 400 µg/mL.",
            "400 µg/mL bag (100 mg in 250 mL)",
        ),
        200.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 1.25 mL. Draw 1.25 mL "
            "(50 mg) of 40 mg/mL dopamine stock and add it to the bag. "
            "Final concentration: 200 µg/mL.",
            "200 µg/mL bag (50 mg in 250 mL)",
        ),
    }
    dop_conc_ug_per_ml, dop_below_threshold = _pick_cri_dilution(
        weight_kg=weight_kg,
        threshold_dose_ug_per_kg_per_min=dopamine_ladder_doses[0],
        available_concentrations_ug_per_ml=tuple(dopamine_dilutions.keys()),
    )
    dop_recipe, dop_titration_label = dopamine_dilutions[dop_conc_ug_per_ml]
    dop_low_ml = round(5.0 * weight_kg * 60 / dop_conc_ug_per_ml, 2)
    dop_high_ml = round(10.0 * weight_kg * 60 / dop_conc_ug_per_ml, 2)
    # Caution threshold: >10 µg/kg/min lands in α-dominant + proarrhythmic
    # territory for dogs. For cats, the threshold is 2.0 µg/kg/min, matching
    # the standalone /dopamine calculator: every step of the feline dose
    # ladder (5–20 µg/kg/min) sits within the documented PVC range for cats
    # (HCM risk; ~15% of cats have undiagnosed HCM), so the caution fires
    # across the board.
    dop_caution = 2.0 if species == AnesthSpecies.CAT else 10.0
    # Ladder starts at the recommended low (5 µg/kg/min) and extends past
    # the high (10) into caution territory, same pattern as the dobutamine
    # and norepinephrine ladders.
    if dop_below_threshold:
        # Patient is smaller than what standard bag preparations can reliably
        # support on an IV pump. Don't show bag instructions, don't show a
        # titration ladder — both would be misleading. Direct the user to a
        # syringe-pump preparation, and to the standalone calculator for
        # syringe-specific math.
        dopamine_cri = CRILine(
            name="Dopamine",
            dose_label="5–10 µg/kg/min",
            rate_low_ml_per_hr=0.0,
            rate_high_ml_per_hr=0.0,
            prep_note=(
                "Patient is below the weight range for standard IV-pump "
                "bag preparation. Use a syringe pump; see the standalone "
                "calculator for syringe-specific math."
            ),
            note=(
                "Start at 5 µg/kg/min. Titrate up by 2–3 µg/kg/min every 30 min to MAP ≥65 mmHg (Plumb's). "
                "Wean by 2–3 µg/kg/min every 30 min; do not stop abruptly."
            ),
            titration_steps=(),
            titration_concentration_label="",
        )
    else:
        dop_prep_note = dop_recipe
        dopamine_cri = CRILine(
            name="Dopamine",
            dose_label="5–10 µg/kg/min",
            rate_low_ml_per_hr=dop_low_ml,
            rate_high_ml_per_hr=dop_high_ml,
            prep_note=dop_prep_note,
            note=(
                "Start at 5 µg/kg/min. Titrate up by 2–3 µg/kg/min every 30 min to MAP ≥65 mmHg (Plumb's). "
                "Wean by 2–3 µg/kg/min every 30 min; do not stop abruptly."
            ),
            titration_steps=_build_cri_ladder(
                doses_ug_per_kg_per_min=dopamine_ladder_doses,
                weight_kg=weight_kg,
                concentration_ug_per_ml=dop_conc_ug_per_ml,
                caution_threshold_ug_per_kg_per_min=dop_caution,
            ),
            titration_concentration_label=dop_titration_label,
        )

    # ── Dobutamine CRI ────────────────────────────────────────────────────────
    # Murrell, Lumb & Jones 6e Ch. 21: primarily β₁; β₂ + α₁ at 5–10 µg/kg/min.
    # Dogs: increases CO/HR/SVR; limited MAP effect. Cats: similar, SVR↓ via β₂.
    # Stock 12.5 mg/mL, impractical neat for small patients. Standard dilution
    # is 1 mg/mL (50 mg in 50 mL NaCl). Smaller patients use a more dilute
    # preparation so the lowest titration dose still produces a reliable
    # IV-pump rate (≥2 mL/hr). Proarrhythmogenic ≥10 µg/kg/min.
    # Species-specific dose range, anesthesia context (Plumb's):
    #   Dogs: 2–12 µg/kg/min IV CRI during isoflurane anesthesia.
    #   Cats: 2–20 µg/kg/min IV CRI during general anesthesia.
    # Range header reflects Plumb's; ladder steps start at the
    # clinically titratable low for each species and follow the
    # standard 2.5 µg/kg/min increment dobutamine is actually titrated
    # by. Cats also get a 1 µg/kg/min row at the start, matching the
    # Plumb's cat low CO / CHF low end (the standalone calculator
    # behaves the same way).
    if species == AnesthSpecies.CAT:
        dob_low_dose = 2.0
        dob_high_dose = 20.0
        dob_dose_label = "2–20 µg/kg/min"
        dob_caution = 5.0
        dobutamine_ladder_doses = (1.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0)
        dob_start_dose_text = "1 µg/kg/min"
    else:
        dob_low_dose = 2.0
        dob_high_dose = 12.0
        dob_dose_label = "2–12 µg/kg/min"
        dob_caution = 10.0
        dobutamine_ladder_doses = (2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0)
        dob_start_dose_text = "2.5 µg/kg/min"
    # Available standard dobutamine preparations, all in a 250 mL NaCl bag.
    # The 1 mg/mL prep is the conventional adult-dog bag; the more dilute
    # options are used to keep small-patient pump rates above 2 mL/hr at
    # the lowest ladder dose (1 µg/kg/min for cats; 2.5 µg/kg/min for dogs).
    # The 100 µg/mL prep covers small dogs (≥1.5 kg); the 25 µg/mL prep
    # extends coverage to cats down to ~1.5 kg at the 1 µg/kg/min floor,
    # at a 0.5 mL stock draw (practical lower bound for accurate transfer).
    dobutamine_dilutions = {
        1000.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 20 mL. Draw 20 mL "
            "(250 mg) of 12.5 mg/mL dobutamine stock and add it to the bag. "
            "Final concentration: 1 mg/mL.",
            "1 mg/mL bag (250 mg in 250 mL)",
        ),
        500.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 10 mL. Draw 10 mL "
            "(125 mg) of 12.5 mg/mL dobutamine stock and add it to the bag. "
            "Final concentration: 0.5 mg/mL.",
            "0.5 mg/mL bag (125 mg in 250 mL)",
        ),
        250.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 5 mL. Draw 5 mL "
            "(62.5 mg) of 12.5 mg/mL dobutamine stock and add it to the bag. "
            "Final concentration: 0.25 mg/mL.",
            "0.25 mg/mL bag (62.5 mg in 250 mL)",
        ),
        100.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 2 mL. Draw 2 mL "
            "(25 mg) of 12.5 mg/mL dobutamine stock and add it to the bag. "
            "Final concentration: 0.1 mg/mL.",
            "0.1 mg/mL bag (25 mg in 250 mL)",
        ),
        25.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 0.5 mL. Draw 0.5 mL "
            "(6.25 mg) of 12.5 mg/mL dobutamine stock and add it to the bag. "
            "Final concentration: 25 µg/mL.",
            "25 µg/mL bag (6.25 mg in 250 mL)",
        ),
    }
    dob_conc_ug_per_ml, dob_below_threshold = _pick_cri_dilution(
        weight_kg=weight_kg,
        threshold_dose_ug_per_kg_per_min=dobutamine_ladder_doses[0],
        available_concentrations_ug_per_ml=tuple(dobutamine_dilutions.keys()),
    )
    dob_recipe, dob_titration_label = dobutamine_dilutions[dob_conc_ug_per_ml]
    dob_low_ml = round(dob_low_dose * weight_kg * 60 / dob_conc_ug_per_ml, 2)
    dob_high_ml = round(dob_high_dose * weight_kg * 60 / dob_conc_ug_per_ml, 2)
    if dob_below_threshold:
        # Patient is smaller than what standard bag preparations can reliably
        # support on an IV pump.
        dobutamine_cri = CRILine(
            name="Dobutamine",
            dose_label=dob_dose_label,
            rate_low_ml_per_hr=0.0,
            rate_high_ml_per_hr=0.0,
            prep_note=(
                "Patient is below the weight range for standard IV-pump "
                "bag preparation. Use a syringe pump; see the standalone "
                "calculator for syringe-specific math."
            ),
            note=(
                f"Start at {dob_start_dose_text}. Titrate up to effect (improved CO, MAP), reassessing BP frequently between adjustments. "
                "Wean gradually when discontinuing."
            ),
            titration_steps=(),
            titration_concentration_label="",
        )
    else:
        dob_prep_note = dob_recipe
        dobutamine_cri = CRILine(
            name="Dobutamine",
            dose_label=dob_dose_label,
            rate_low_ml_per_hr=dob_low_ml,
            rate_high_ml_per_hr=dob_high_ml,
            prep_note=dob_prep_note,
            note=(
                f"Start at {dob_start_dose_text}. Titrate up to effect (improved CO, MAP), reassessing BP frequently between adjustments. "
                "Wean gradually when discontinuing."
            ),
            titration_steps=_build_cri_ladder(
                doses_ug_per_kg_per_min=dobutamine_ladder_doses,
                weight_kg=weight_kg,
                concentration_ug_per_ml=dob_conc_ug_per_ml,
                caution_threshold_ug_per_kg_per_min=dob_caution,
            ),
            titration_concentration_label=dob_titration_label,
        )

    # ── Norepinephrine CRI ────────────────────────────────────────────────────
    # Murrell, Lumb & Jones 6e Ch. 21:
    # β₁ predominates at 0.025 µg/kg/min; α₁/α₂ dominate >0.5–1.5 µg/kg/min.
    # Dogs 0.05–2 µg/kg/min: dose-dependent ↑MAP, ↑CO, no significant SVR↑ at studied doses.
    # Effective in foals/alpacas at 0.3–1.0 µg/kg/min for isoflurane hypotension.
    # At high doses: SVR↑ → ↓CO + ↑myocardial O₂ consumption.
    # Less tachycardic than epinephrine. Extravasation → tissue necrosis.
    # Standard dilution: 4 mg in 250 mL NaCl → 16 µg/mL. Smaller patients
    # use 8 or 4 µg/mL preps so the working titration anchor (0.1 µg/kg/min)
    # still produces a reliable IV-pump rate (≥2 mL/hr). The ladder also
    # starts at 0.1 — the published range floor of 0.05 is not displayed
    # because clinicians rarely titrate at the pump to that rate. The
    # dose range in DRUGS still includes 0.05 as the minimum so users
    # can enter that dose directly if they want it.
    norepi_ladder_doses = (0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0)
    norepi_dilutions = {
        16.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 4 mL. Draw 4 mL "
            "(4 mg) of 1 mg/mL norepinephrine stock and add it to the bag. "
            "Final concentration: 16 µg/mL.",
            "16 µg/mL bag (4 mg in 250 mL)",
        ),
        8.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 2 mL. Draw 2 mL "
            "(2 mg) of 1 mg/mL norepinephrine stock and add it to the bag. "
            "Final concentration: 8 µg/mL.",
            "8 µg/mL bag (2 mg in 250 mL)",
        ),
        4.0: (
            "From a 250 mL bag of 0.9% NaCl, remove 1 mL. Draw 1 mL "
            "(1 mg) of 1 mg/mL norepinephrine stock and add it to the bag. "
            "Final concentration: 4 µg/mL.",
            "4 µg/mL bag (1 mg in 250 mL)",
        ),
    }
    norepi_conc_ug_per_ml, norepi_below_threshold = _pick_cri_dilution(
        weight_kg=weight_kg,
        # 0.1 is the working anchor (not 0.05, the ladder floor).
        threshold_dose_ug_per_kg_per_min=0.1,
        available_concentrations_ug_per_ml=tuple(norepi_dilutions.keys()),
    )
    norepi_recipe, norepi_titration_label = norepi_dilutions[norepi_conc_ug_per_ml]
    norepi_low = round(0.1 * weight_kg * 60 / norepi_conc_ug_per_ml, 2)
    norepi_high = round(0.5 * weight_kg * 60 / norepi_conc_ug_per_ml, 2)
    if norepi_below_threshold:
        # Patient is smaller than what standard bag preparations can reliably
        # support on an IV pump.
        norepi_cri = CRILine(
            name="Norepinephrine",
            dose_label="0.1–1.0 µg/kg/min",
            rate_low_ml_per_hr=0.0,
            rate_high_ml_per_hr=0.0,
            prep_note=(
                "Patient is below the weight range for standard IV-pump "
                "bag preparation. Use a syringe pump; see the standalone "
                "calculator for syringe-specific math."
            ),
            note=(
                "Start at 0.1 µg/kg/min. Titrate up by 0.05–0.1 µg/kg/min to MAP ≥65 mmHg, reassessing BP frequently between adjustments. "
                "Wean gradually once MAP stable."
            ),
            titration_steps=(),
            titration_concentration_label="",
        )
    else:
        norepi_prep_note = norepi_recipe
        norepi_cri = CRILine(
            name="Norepinephrine",
            dose_label="0.1–1.0 µg/kg/min",
            rate_low_ml_per_hr=norepi_low,
            rate_high_ml_per_hr=norepi_high,
            prep_note=norepi_prep_note,
            note=(
                "Start at 0.1 µg/kg/min. Titrate up by 0.05–0.1 µg/kg/min to MAP ≥65 mmHg, reassessing BP frequently between adjustments. "
                "Wean gradually once MAP stable."
            ),
            titration_steps=_build_cri_ladder(
                doses_ug_per_kg_per_min=norepi_ladder_doses,
                weight_kg=weight_kg,
                concentration_ug_per_ml=norepi_conc_ug_per_ml,
                caution_threshold_ug_per_kg_per_min=1.0,
            ),
            titration_concentration_label=norepi_titration_label,
        )

    warnings = [
        "Verify all drug concentrations against the vial in front of you before drawing up.",
        "All induction doses assume slow IV titration to effect, never bolus the full calculated volume.",
        "Correct hypovolemia with fluid bolus before initiating inotropes or vasopressors.",
    ]

    return AnesthesiaSheet(
        patient_name=patient_name,
        patient_age=patient_age,
        species=species,
        weight_kg=round(weight_kg, 2),
        weight_display=weight_display,
        blood_volume_ml=blood_volume_ml,
        shock_quarter_dose_ml=shock_quarter_dose_ml,
        shock_full_dose_ml=shock_full_dose_ml,
        maintenance_ml_per_hr=maintenance_ml_per_hr,
        maintenance_rate_ml_per_kg_per_hr=maintenance_per_kg_hr,
        fluid_bolus_low_ml=fluid_bolus_low_ml,
        fluid_bolus_high_ml=fluid_bolus_high_ml,
        circuit_bag_calculated_l=circuit_bag_calculated_l,
        circuit_bag_recommended_l=circuit_bag_recommended_l,
        circuit_bag_exceeds_max=circuit_bag_exceeds_max,
        circuit_use_nonrebreathing=circuit_use_nonrebreathing,
        premed_opioids=premed_opioids,
        premed_sedatives=premed_sedatives,
        induction_drugs=induction_drugs,
        dkb_protocols=dkb_protocols,
        emergency_drugs=emergency_drugs,
        phenylephrine_bolus=phenylephrine_bolus,
        ephedrine_bolus=ephedrine_bolus,
        dopamine_cri=dopamine_cri,
        dobutamine_cri=dobutamine_cri,
        norepi_cri=norepi_cri,
        warnings=warnings,
    )
