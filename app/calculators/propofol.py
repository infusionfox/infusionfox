"""
Propofol TIVA maintenance and refractory status epilepticus calculator.

Source: Plumb's Veterinary Drugs, propofol monograph (current edition).

Two indication modes:
    1. TIVA maintenance (extra-label), dog-only in this calculator.
       Range 0.1–0.5 mg/kg/min IV CRI. Default 0.3 mg/kg/min.
       Premedications can reduce induction dose by 25%+; CRI maintenance
       dose is similarly modulated.

    2. Refractory status epilepticus (extra-label), both species.
       Range 0.1–0.25 mg/kg/min IV CRI following 2–8 mg/kg IV bolus.
       Maintain 6–12 hours then gradually decrease. Maximum duration
       ≈48 hours. Default 0.15 mg/kg/min.

Math: pump rate (mL/hr) = (weight_kg × dose_mg_per_kg_per_min × 60) /
                          stock_mg_per_ml
The standard 1% emulsion is 10 mg/mL, propofol is not typically diluted.

Cat support:
    - TIVA maintenance: NOT supported. Plumb's notes cats may be
      susceptible to long recoveries when propofol is used alone as a
      CRI or with continuous prolonged exposure (slower glucuronidation;
      Heinz-body anemia with repeated exposure). For cats, use short
      procedures with intermittent IV propofol injection (covered by
      the induction reference table, not by this CRI calculator) or
      consider alfaxalone or inhalant maintenance instead.
    - Status epilepticus: cats supported. Plumb's publishes the same
      dose range for cats and dogs (2–8 mg/kg IV bolus, 0.1–0.25 mg/kg/min
      CRI), and the indication is emergent. Persistent warning surfaces
      cat-specific concerns (Heinz body, long recovery, keep duration short).

The page also displays Plumb's induction-dose reference tables (for
guidance, not interactive). Induction dosing is a clinical judgment
based on premedication, debility, body condition, breed, and age,
Plumb's itself states "individual animal response should dictate the
dose used."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

PROPOFOL_STOCK_MG_PER_ML = 10.0  # 1% emulsion


class PropofolIndication(str, Enum):
    TIVA_MAINTENANCE = "tiva_maintenance"
    STATUS_EPILEPTICUS = "status_epilepticus"


class PropofolSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"  # only valid for STATUS_EPILEPTICUS


@dataclass
class PropofolDoseRange:
    min_mg_per_kg_per_min: float
    max_mg_per_kg_per_min: float
    default_mg_per_kg_per_min: float
    persistent_warning: str
    caution_threshold: float | None = None
    caution_note: str | None = None
    note: str | None = None


# Dose ranges keyed by (indication, species)
PROPOFOL_DOSE_RANGES: dict[tuple[PropofolIndication, PropofolSpecies], PropofolDoseRange] = {
    (PropofolIndication.TIVA_MAINTENANCE, PropofolSpecies.DOG): PropofolDoseRange(
        min_mg_per_kg_per_min=0.1,
        max_mg_per_kg_per_min=0.5,
        default_mg_per_kg_per_min=0.1,
        persistent_warning=(
            "Propofol provides NO analgesia, multimodal analgesia (opioid, "
            "local block, NSAID where appropriate) is required for surgical "
            "TIVA. Continuous monitoring is required: depth of anesthesia, "
            "respiratory rate / SpO₂ / ETCO₂, heart rate / rhythm, blood "
            "pressure. Respiratory and cardiovascular support must be "
            "immediately available, apnea is possible, especially with "
            "rapid administration or high doses. Debilitated patients "
            "require lower doses and may show exaggerated cardiorespiratory "
            "depression. Concurrent halogenated inhalants reduce TIVA "
            "requirements; concurrent opioids and α₂-agonists reduce CRI "
            "dose by up to 40–60%. Propofol enhances epinephrine-induced "
            "arrhythmias in a dose-dependent manner, use caution when "
            "epinephrine is also indicated."
        ),
        note=(
            "TIVA maintenance range is 0.1–0.5 mg/kg/min IV CRI in dogs "
            "(extra-label). Default is 0.1 mg/kg/min, which assumes a "
            "premedicated patient; premedications substantially reduce "
            "CRI requirements. Maintenance dose sparing was reported as "
            "≈48% with benzodiazepine + opioid premed and ≈37% with "
            "phenothiazine + opioid premed (label data); α₂ agonist + "
            "opioid combinations reduce dose by up to 40–60%. Titrate up "
            "if depth is inadequate; unpremedicated patients may require "
            "doses near 0.3 mg/kg/min."
        ),
    ),
    (PropofolIndication.STATUS_EPILEPTICUS, PropofolSpecies.DOG): PropofolDoseRange(
        min_mg_per_kg_per_min=0.1,
        max_mg_per_kg_per_min=0.25,
        default_mg_per_kg_per_min=0.15,
        persistent_warning=(
            "Refractory status epilepticus protocol (extra-label). "
            "Precede CRI with a 2–8 mg/kg IV bolus titrated to effect. "
            "Maintain CRI at the lowest effective dose, for the shortest "
            "possible duration. Standard practice is to maintain the "
            "infusion 6–12 hours and then gradually decrease, with a "
            "maximum CRI duration of ≈48 hours. Propofol provides NO "
            "analgesia. Apnea / respiratory depression is possible; "
            "endotracheal intubation, supplemental oxygen, and "
            "ventilatory support must be immediately available. "
            "Continuous monitoring required (depth of anesthesia, "
            "SpO₂ / ETCO₂, HR / rhythm, BP, body temperature). Watch "
            "for propofol infusion syndrome (rare; metabolic acidosis, "
            "rhabdomyolysis, hyperlipidemia, cardiac arrhythmias, "
            "cardiac and renal failure)."
        ),
        note=(
            "Status epilepticus protocol: 2–8 mg/kg IV bolus, followed "
            "by 0.1–0.25 mg/kg/min IV CRI. Maintain 6–12 hours then "
            "gradually decrease. Maximum CRI duration ≈48 hours."
        ),
    ),
    (PropofolIndication.STATUS_EPILEPTICUS, PropofolSpecies.CAT): PropofolDoseRange(
        min_mg_per_kg_per_min=0.1,
        max_mg_per_kg_per_min=0.25,
        default_mg_per_kg_per_min=0.15,
        persistent_warning=(
            "Refractory status epilepticus protocol (extra-label), cat. "
            "Cats are more susceptible to long recoveries with propofol "
            "than dogs (slower glucuronidation), and repeated/prolonged "
            "propofol exposure has been associated with increased Heinz-"
            "body anemia, anorexia, lethargy, malaise, and diarrhea. "
            "Keep CRI duration as short as possible; consider alternative "
            "agents (eg, alfaxalone CRI) where available. "
            "Precede CRI with a 2–8 mg/kg IV bolus titrated to effect. "
            "Maintain at the lowest effective dose; standard practice is "
            "to maintain 6–12 hours then gradually decrease (max ≈48 "
            "hours overall). Propofol provides NO analgesia. "
            "Apnea / respiratory depression is possible, intubate, "
            "supplemental O₂, ventilatory support must be available. "
            "Monitor CBC for Heinz-body anemia with repeated exposure."
        ),
        note=(
            "The status epilepticus protocol applies to both species "
            "(2–8 mg/kg IV bolus → 0.1–0.25 mg/kg/min CRI), but cats "
            "warrant shorter durations and CBC monitoring."
        ),
    ),
}


# Plumb's induction reference tables, reproduced for clinical reference
# only (not used by the calculator). Source: Plumb's monograph, Dosages
# section, label dosages tables.
INDUCTION_TABLE_DOG = [
    # (premedication, propofol_dose_mg_per_kg, administration_seconds, notes)
    {"premed": "None", "dose": "5.5 – 7.6", "rate": "40–90 sec", "note": "Healthy adult dog, no premed"},
    {"premed": "Acepromazine", "dose": "3.7 – 4.4", "rate": "30–90 sec", "note": ""},
    {"premed": "Xylazine", "dose": "2.2 – 3.3", "rate": "60–90 sec", "note": ""},
    {"premed": "Medetomidine", "dose": "2.2 – 2.8", "rate": "60–90 sec", "note": ""},
    {
        "premed": "Acepromazine + opioid",
        "dose": "2.6 – 4.7",
        "rate": "30–90 sec",
        "note": "Wider range across product labels",
    },
    {"premed": "Benzodiazepine + opioid", "dose": "4.0", "rate": "60–90 sec", "note": ""},
    {"premed": "α₂ agonist + opioid", "dose": "3.2", "rate": "60–90 sec", "note": ""},
]

# NOTE: Plumb's lists "8 – 13.2 mg/kg" as an induction range for several cat
# premed combinations and explicitly adds: "Many clinicians consider the
# labeled propofol dosages to be higher than necessary. Expect larger dose
# reductions than are indicated in this table when premedicants are used."
# Most clinicians use 2–8 mg/kg IV titrated to effect.
INDUCTION_TABLE_CAT = [
    {
        "premed": "None",
        "dose": "8 – 13.2 (label), 2–8 (extra-label, titrated)",
        "rate": "60–90 sec",
        "note": "Label range often considered higher than necessary",
    },
    {
        "premed": "Acepromazine, butorphanol, oxymorphone",
        "dose": "8 – 13.2 (label)",
        "rate": "60–90 sec",
        "note": "Reduce when premedicated; titrate to effect",
    },
    {"premed": "Xylazine", "dose": "7 – 12 (label)", "rate": "60–90 sec", "note": ""},
    {
        "premed": "α₂ agonist (eg dexmedetomidine)",
        "dose": "≈4–7 (extra-label)",
        "rate": "60–90 sec",
        "note": "Dexmedetomidine premed reduces propofol induction dose by ≈49% in cats",
    },
]


@dataclass
class PropofolInputs:
    weight_value: float
    weight_unit: WeightUnit
    dose_mg_per_kg_per_min: float
    indication: PropofolIndication
    species: PropofolSpecies


@dataclass
class PropofolResult:
    weight_kg: float
    pump_rate_ml_per_hr: float
    pump_rate_ml_per_min: float
    dose_mg_per_kg_per_min: float
    dose_mg_per_kg_per_hr: float
    stock_mg_per_ml: float
    indication: PropofolIndication
    species: PropofolSpecies
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale. False when weight is
    # missing or non-positive, OR when the cat-TIVA contraindication
    # triggers (the calculator refuses to produce a rate for cat
    # propofol TIVA maintenance).
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def get_propofol_dose_range(
    indication: PropofolIndication, species: PropofolSpecies
) -> PropofolDoseRange | None:
    return PROPOFOL_DOSE_RANGES.get((indication, species))


def compute_propofol(inputs: PropofolInputs) -> PropofolResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        return PropofolResult(
            weight_kg=weight_kg,
            pump_rate_ml_per_hr=0.0,
            pump_rate_ml_per_min=0.0,
            dose_mg_per_kg_per_min=inputs.dose_mg_per_kg_per_min,
            dose_mg_per_kg_per_hr=0.0,
            stock_mg_per_ml=PROPOFOL_STOCK_MG_PER_ML,
            indication=inputs.indication,
            species=inputs.species,
            warnings=["Weight must be greater than zero."],
            notes=[],
            sources=PROPOFOL_SOURCES,
            valid=False,
        )

    # Block invalid indication+species combo (cat TIVA)
    if inputs.indication == PropofolIndication.TIVA_MAINTENANCE and inputs.species == PropofolSpecies.CAT:
        warnings.append(
            "Cat TIVA maintenance is not supported by this calculator. Cats "
            "are susceptible to prolonged recovery and Heinz-body anemia "
            "with repeated/prolonged propofol exposure. Use short procedures "
            "with intermittent IV propofol bolus injections (see induction "
            "reference table), or consider alfaxalone CRI or inhalant "
            "anesthesia for maintenance."
        )
        return PropofolResult(
            weight_kg=round(weight_kg, 2),
            pump_rate_ml_per_hr=0.0,
            pump_rate_ml_per_min=0.0,
            dose_mg_per_kg_per_min=inputs.dose_mg_per_kg_per_min,
            dose_mg_per_kg_per_hr=0.0,
            stock_mg_per_ml=PROPOFOL_STOCK_MG_PER_ML,
            indication=inputs.indication,
            species=inputs.species,
            warnings=warnings,
            notes=notes,
            sources=PROPOFOL_SOURCES,
            valid=False,
        )

    dose_range = get_propofol_dose_range(inputs.indication, inputs.species)

    # Math: mL/hr = (kg × mg/kg/min × 60) / (mg/mL)
    mg_per_min = weight_kg * inputs.dose_mg_per_kg_per_min
    ml_per_min = mg_per_min / PROPOFOL_STOCK_MG_PER_ML
    ml_per_hr = ml_per_min * 60.0
    mg_per_kg_per_hr = inputs.dose_mg_per_kg_per_min * 60.0

    # Range warnings
    if dose_range is not None:
        if inputs.dose_mg_per_kg_per_min < dose_range.min_mg_per_kg_per_min:
            warnings.append(
                f"Dose {inputs.dose_mg_per_kg_per_min:g} mg/kg/min is below "
                f"the published range "
                f"({dose_range.min_mg_per_kg_per_min:g}–"
                f"{dose_range.max_mg_per_kg_per_min:g} mg/kg/min) for this "
                f"indication. Subanesthetic doses produce sedation but may "
                f"be inadequate for surgical anesthesia or seizure control."
            )
        elif inputs.dose_mg_per_kg_per_min > dose_range.max_mg_per_kg_per_min:
            warnings.append(
                f"⚠ Dose {inputs.dose_mg_per_kg_per_min:g} mg/kg/min exceeds "
                f"the published range "
                f"({dose_range.min_mg_per_kg_per_min:g}–"
                f"{dose_range.max_mg_per_kg_per_min:g} mg/kg/min) for this "
                f"indication. Reassess depth of anesthesia, premedication "
                f"effect, and analgesia adequacy. Higher doses increase "
                f"risk of apnea, hypotension, and prolonged recovery."
            )

        # Persistent warning always shown
        warnings.append(dose_range.persistent_warning)

        if dose_range.note:
            notes.append(dose_range.note)

    # Standing notes
    notes.append(
        "Stock propofol concentration is 10 mg/mL (1% emulsion). Plumb's "
        "states the emulsion should not be mixed with other therapeutic "
        "agents or into infusion fluids prior to administration. If "
        "dilution is necessary (Diprivan® only), use D5W and do not "
        "dilute below 2 mg/mL."
    )

    if inputs.indication == PropofolIndication.STATUS_EPILEPTICUS:
        notes.append(
            "Status epilepticus protocol: precede CRI with a 2–8 mg/kg IV "
            "bolus titrated to effect. Maintain CRI 6–12 hours, then "
            "gradually decrease. Maximum CRI duration ≈48 hours."
        )

    return PropofolResult(
        weight_kg=round(weight_kg, 2),
        pump_rate_ml_per_hr=round(ml_per_hr, 2),
        pump_rate_ml_per_min=round(ml_per_min, 3),
        dose_mg_per_kg_per_min=inputs.dose_mg_per_kg_per_min,
        dose_mg_per_kg_per_hr=round(mg_per_kg_per_hr, 2),
        stock_mg_per_ml=PROPOFOL_STOCK_MG_PER_ML,
        indication=inputs.indication,
        species=inputs.species,
        warnings=warnings,
        notes=notes,
        sources=PROPOFOL_SOURCES,
    )


PROPOFOL_SOURCES = (
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, propofol monograph. Induction "
            "dosing in premedicated and unpremedicated dogs and cats; TIVA and "
            "status epilepticus CRI dosing; cautions including hypotension, apnea, "
            "no analgesia, and the cat-specific Heinz body / oxidative-stress "
            "concern with repeated daily administration."
        )
    ),
    Source(
        citation=(
            "Reid J, Nolan AM. Pharmacokinetics of propofol as an induction agent "
            "in geriatric dogs. Res Vet Sci 1996;61:169–171."
        )
    ),
    Source(
        citation=(
            "Hall LW, Lagerweij E, Nolan AM, Sear JW. Effect of medetomidine on "
            "the pharmacokinetics of propofol in dogs. Am J Vet Res "
            "1994;55:116–120."
        )
    ),
)

PROPOFOL_CATALOG_ENTRY = {
    "slug": "propofol",
    "display_name": "Propofol (TIVA / Status epilepticus)",
    "short_name": "Propofol",
    "category": "Anesthesia & Sedation",
    "kind": "single_drug_cri",
    "mechanism_summary": (
        "Short-acting sedative-hypnotic injectable anesthetic; potentiates "
        "GABA at GABA-A receptors causing chloride influx and "
        "hyperpolarization. Rapid IV onset (≈1–2 min) with short duration "
        "of action (≈5–7 min after a single induction dose in dogs; "
        "5–12 min in cats) due principally to rapid redistribution from "
        "CNS to peripheral tissues. Hepatic glucuronide conjugation is the "
        "primary metabolic pathway; clearance exceeds hepatic blood flow, "
        "suggesting extrahepatic metabolism."
    ),
    "indications_summary": (
        "Propofol CRI for two indications: total IV anesthesia "
        "(TIVA) maintenance in dogs, and refractory status "
        "epilepticus in dogs and cats. Propofol does NOT provide "
        "analgesia. Multimodal analgesia must be added for surgical "
        "procedures."
    ),
}
