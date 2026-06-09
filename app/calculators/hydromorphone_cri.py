"""
Hydromorphone CRI calculator, dogs and cats.

Source: Plumb's Veterinary Drugs, Hydromorphone monograph (current edition).
Combined analgesia and anesthesia extra-label dose ranges.

Dogs (combined analgesia and anesthesia, extra-label):
    Loading bolus: 0.025–0.1 mg/kg IV
    CRI:           0.02–0.1 mg/kg/hour IV
    Pure analgesia is typically dosed around 0.03 mg/kg/hr; higher rates
    are anesthesia-context infusions and the ladder flags doses above
    0.05 mg/kg/hr for sustained-rate sedation/adverse-effect risk per
    Plumb's.

Cats (extra-label, per Plumb's):
    Loading bolus: 0.025 mg/kg IV
    CRI:           0.01–0.05 mg/kg/hour IV (start at low end)

Intermittent bolus (alternative to CRI protocol):
    Dogs: 0.05–0.2 mg/kg IV/IM/SC q 2–4 hr
    Cats: 0.05–0.1 mg/kg IV/IM/SC q 2–6 hr

Stock: 2 mg/mL is the standard veterinary vial. 1, 4, and 10 mg/mL
preparations also exist in human pharmacy stock and may be encountered
in mixed-use settings; verify the vial label before drawing up.
DEA Schedule II controlled substance.

This calculator presents the CRI as a species-specific titration ladder
so the clinician can see the pump rate at every dose step on the
patient's weight at the chosen stock. The "default" highlighted row is:
    Dog: 0.03 mg/kg/hr (typical pure analgesia per Plumb's)
    Cat: 0.01 mg/kg/hr (Plumb's published low end + start-low guidance)
Doses above 0.05 mg/kg/hr flag a sustained-rate caution row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# 2 mg/mL is the standard veterinary stock vial of hydromorphone and the
# default this calculator renders. The anesthesia worksheet uses the same.
HYDROMORPHONE_STOCK_MG_PER_ML = 2.0

# Alternative concentrations available through the alt-stock disclosure.
# Each tuple element is the (concentration_mg_per_ml, short_label) pair
# rendered in the disclosure radio group. The first entry is the default.
HYDROMORPHONE_STOCK_OPTIONS: tuple[tuple[float, str], ...] = (
    (2.0, "2 mg/mL (standard veterinary vial)"),
    (1.0, "1 mg/mL (small-volume vial)"),
    (4.0, "4 mg/mL (premixed concentrate)"),
    (10.0, "10 mg/mL (high-potency / HP preparation)"),
)

# Titration ladder doses, mg/kg/hr. Species-specific because the
# combined-range for dogs (0.02–0.10) extends well above the cat
# range (0.01–0.05) for anesthesia-context infusions.
HYDROMORPHONE_DOG_LADDER_DOSES: tuple[float, ...] = (0.02, 0.03, 0.05, 0.075, 0.10)
HYDROMORPHONE_CAT_LADDER_DOSES: tuple[float, ...] = (0.01, 0.02, 0.03, 0.04, 0.05)

# Species default dose: the "starting" rate that headlines the result
# panel and highlights its row on the ladder.
HYDROMORPHONE_DOG_DEFAULT_DOSE = 0.03  # typical pure analgesia, Plumb's
HYDROMORPHONE_CAT_DEFAULT_DOSE = 0.01  # Plumb's published low end

# Above this rate, Plumb's notes that sustained infusion (>12 hr) may
# cause sedation severe enough to require dose reduction. Applied to
# both species — cats are generally more opioid-sensitive than dogs and
# the same cap is appropriate.
HYDROMORPHONE_CAUTION_THRESHOLD_MG_PER_KG_PER_HR = 0.05


class HydromorphoneSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class HydromorphoneInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: HydromorphoneSpecies
    # Stock concentration is part of the input contract so the alt-stock
    # disclosure can change it. Defaults to 2 mg/mL (matches anesthesia
    # worksheet and most-common-stocked veterinary vial).
    stock_mg_per_ml: float = HYDROMORPHONE_STOCK_MG_PER_ML


@dataclass
class TitrationStep:
    """One row of the hydromorphone CRI titration ladder."""

    dose_mg_per_kg_per_hr: float
    ml_per_hr: float
    # Highlighted "start here" row for the current species.
    is_default: bool
    # Above the sustained-rate caution threshold (>0.05 mg/kg/hr).
    is_caution: bool
    # Short annotation rendered next to the dose. None for unremarkable
    # rows. Used for the dog "analgesia" highlight, the dog
    # "anesthesia infusion" zone, and the cat "start low" marker.
    annotation: str | None = None


@dataclass
class HydromorphoneResult:
    weight_kg: float
    species: HydromorphoneSpecies
    stock_mg_per_ml: float

    # Species default dose (headline + highlighted ladder row).
    default_dose_mg_per_kg_per_hr: float
    default_pump_rate_ml_per_hr: float
    default_dose_label: str  # rendered next to the headline

    # Full titration ladder.
    titration_steps: tuple[TitrationStep, ...]

    # Loading dose (precedes CRI).
    loading_dose_low_mg_per_kg: float
    loading_dose_high_mg_per_kg: float
    loading_low_mg: float
    loading_high_mg: float
    loading_low_ml: float
    loading_high_ml: float

    # Intermittent bolus (separate alternative to the CRI protocol).
    bolus_dose_low_mg_per_kg: float
    bolus_dose_high_mg_per_kg: float
    bolus_low_mg: float
    bolus_high_mg: float
    bolus_low_ml: float
    bolus_high_ml: float
    bolus_interval_hr: str

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _ladder_doses_for(species: HydromorphoneSpecies) -> tuple[float, ...]:
    return (
        HYDROMORPHONE_DOG_LADDER_DOSES
        if species == HydromorphoneSpecies.DOG
        else HYDROMORPHONE_CAT_LADDER_DOSES
    )


def _default_dose_for(species: HydromorphoneSpecies) -> float:
    return (
        HYDROMORPHONE_DOG_DEFAULT_DOSE
        if species == HydromorphoneSpecies.DOG
        else HYDROMORPHONE_CAT_DEFAULT_DOSE
    )


def _default_label_for(species: HydromorphoneSpecies) -> str:
    if species == HydromorphoneSpecies.DOG:
        return "Typical analgesia"
    return "Plumb's start-low"


def _annotation_for(
    species: HydromorphoneSpecies,
    dose: float,
    is_default: bool,
) -> str | None:
    """Short label rendered next to a ladder row.

    Dog 0.03 mg/kg/hr is the typical pure-analgesia dose and gets the
    "Typical analgesia" annotation. Dog doses above 0.05 are anesthesia-
    context infusions and get the "Anesthesia infusion" annotation.
    Cat 0.01 (the default) gets a "Start low" annotation.
    """
    if species == HydromorphoneSpecies.DOG:
        if abs(dose - 0.03) < 1e-9:
            return "Typical analgesia"
        if dose > 0.05:
            return "Anesthesia infusion"
        return None
    # Cat
    if is_default and abs(dose - 0.01) < 1e-9:
        return "Plumb's start-low"
    return None


def _build_ladder(
    species: HydromorphoneSpecies,
    weight_kg: float,
    stock_mg_per_ml: float,
    default_dose: float,
) -> tuple[TitrationStep, ...]:
    """Compute the per-step pump rate for the species ladder.

    Step rate (mL/hr) = (dose × weight) / stock. Caution flag fires
    above HYDROMORPHONE_CAUTION_THRESHOLD; the default-dose row gets
    is_default=True so the template can highlight it without needing
    its own equality check.
    """
    steps: list[TitrationStep] = []
    for dose in _ladder_doses_for(species):
        ml_per_hr = round((dose * weight_kg) / stock_mg_per_ml, 3)
        is_default = abs(dose - default_dose) < 1e-9
        steps.append(
            TitrationStep(
                dose_mg_per_kg_per_hr=dose,
                ml_per_hr=ml_per_hr,
                is_default=is_default,
                is_caution=dose > HYDROMORPHONE_CAUTION_THRESHOLD_MG_PER_KG_PER_HR,
                annotation=_annotation_for(species, dose, is_default),
            )
        )
    return tuple(steps)


def calculate(inputs: HydromorphoneInputs) -> HydromorphoneResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    stock = inputs.stock_mg_per_ml

    # Species-specific loading bolus and intermittent bolus data.
    # Loading bolus: combined analgesia+anesthesia range for dogs.
    if inputs.species == HydromorphoneSpecies.DOG:
        loading_low_dose = 0.025
        loading_high_dose = 0.10
        bolus_low_dose = 0.05
        bolus_high_dose = 0.20
        bolus_interval = "2–4 hr"
    else:  # CAT
        loading_low_dose = 0.025
        loading_high_dose = 0.025  # single published cat loading dose
        bolus_low_dose = 0.05
        bolus_high_dose = 0.10
        bolus_interval = "2–6 hr"

    # Loading dose volumes
    loading_low_mg = round(loading_low_dose * weight_kg, 3)
    loading_high_mg = round(loading_high_dose * weight_kg, 3)
    loading_low_ml = round(loading_low_dose * weight_kg / stock, 3)
    loading_high_ml = round(loading_high_dose * weight_kg / stock, 3)

    # CRI: headline + ladder
    default_dose = _default_dose_for(inputs.species)
    default_pump_rate = round((default_dose * weight_kg) / stock, 3)
    default_label = _default_label_for(inputs.species)
    ladder = _build_ladder(inputs.species, weight_kg, stock, default_dose)

    # Intermittent bolus volumes
    bolus_low_mg = round(bolus_low_dose * weight_kg, 3)
    bolus_high_mg = round(bolus_high_dose * weight_kg, 3)
    bolus_low_ml = round(bolus_low_dose * weight_kg / stock, 3)
    bolus_high_ml = round(bolus_high_dose * weight_kg / stock, 3)

    # Species-specific clinical warnings
    if inputs.species == HydromorphoneSpecies.CAT:
        warnings.append(
            "Hyperthermia risk in cats: hydromorphone may increase body "
            "temperature after anesthesia. Monitor temperature closely. "
            "Naloxone rapidly reverses hydromorphone-induced hyperthermia. "
            "Some clinicians prefer to avoid hydromorphone in cats; "
            "consider buprenorphine as an alternative."
        )

    warnings.append(
        "Dose-related respiratory depression is possible, particularly "
        "under general anesthesia. Monitor respiratory rate, SpO₂, ETCO₂, "
        "and heart rate. Bradycardia secondary to vagal tone; treat with "
        "atropine or glycopyrrolate if needed. DEA Schedule II controlled "
        "substance."
    )

    notes.append(
        f"Stock: {stock:g} mg/mL. 1, 4, and 10 mg/mL vials also exist in "
        f"human pharmacy stock; use the alternative-stock panel above to "
        f"recompute at a different concentration. Verify the vial label "
        f"before drawing up; concentration errors with hydromorphone are "
        f"high-stakes."
    )
    notes.append(
        "Loading and bolus volumes assume IV administration. IM/SC "
        "bioavailability is high (peak at 10–30 min SC in dogs); use the "
        "same dose. Vomiting more common with IM/SC than IV."
    )
    if inputs.species == HydromorphoneSpecies.DOG:
        notes.append(
            "Vomiting, panting, whining, and defecation are common after "
            "hydromorphone in dogs. Maropitant SC 15–45 min before (or PO "
            "≥2 hr before) prevents vomiting per Plumb's."
        )
    notes.append(
        "Sustained CRIs above 0.05 mg/kg/hr for >12 hours may cause "
        "sedation and adverse effects severe enough to require reducing "
        "the rate; the titration ladder flags this zone as 'Anesthesia "
        "infusion'."
    )

    return HydromorphoneResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        stock_mg_per_ml=stock,
        default_dose_mg_per_kg_per_hr=default_dose,
        default_pump_rate_ml_per_hr=default_pump_rate,
        default_dose_label=default_label,
        titration_steps=ladder,
        loading_dose_low_mg_per_kg=loading_low_dose,
        loading_dose_high_mg_per_kg=loading_high_dose,
        loading_low_mg=loading_low_mg,
        loading_high_mg=loading_high_mg,
        loading_low_ml=loading_low_ml,
        loading_high_ml=loading_high_ml,
        bolus_dose_low_mg_per_kg=bolus_low_dose,
        bolus_dose_high_mg_per_kg=bolus_high_dose,
        bolus_low_mg=bolus_low_mg,
        bolus_high_mg=bolus_high_mg,
        bolus_low_ml=bolus_low_ml,
        bolus_high_ml=bolus_high_ml,
        bolus_interval_hr=bolus_interval,
        warnings=warnings,
        notes=notes,
        sources=HYDROMORPHONE_SOURCES,
    )


HYDROMORPHONE_SOURCES = (
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, hydromorphone monograph. "
            "Combined analgesia and anesthesia loading and CRI dose ranges "
            "for dogs and cats (extra-label). Stock concentrations, "
            "intermittent-bolus dosing, and species-specific cautions "
            "(canine respiratory depression, feline hyperthermia)."
        )
    ),
    Source(
        citation=(
            "KuKanich B, Hogan BK, Krugner-Higby LA, Smith LJ. Pharmacokinetics "
            "of hydromorphone hydrochloride in healthy dogs. Vet Anaesth Analg "
            "2008;35(3):256–264."
        )
    ),
    Source(
        citation=(
            "Pypendop BH, Ilkiw JE. Pharmacokinetics of hydromorphone "
            "hydrochloride in healthy cats. Am J Vet Res 2008;69(8):983–987."
        )
    ),
)


HYDROMORPHONE_CRI_CATALOG_ENTRY = {
    "slug": "hydromorphone-cri",
    "display_name": "Hydromorphone CRI",
    "short_name": "Hydromorphone",
    "category": "Analgesia",
    "kind": "single_drug_cri",
    "mechanism_summary": (
        "Semisynthetic full mu-opioid agonist, 5–7× more potent than morphine. "
        "No histamine release (safe for IV bolus). "
        "Caution: hyperthermia in cats. DEA C-II."
    ),
}
