"""
Methadone calculator, dogs and cats.

Source: Plumb's Veterinary Drugs, Methadone monograph (current edition).

Dogs (extra-label):
    Intermittent bolus: 0.1–0.5 mg/kg IV, IM, or SC every 4–8 hours
    Premedication IM:   0.2–0.3 mg/kg IM
    Premedication IV:   0.2–0.3 mg/kg IV
    CRI: Loading dose   0.1–0.2 mg/kg IV
         Maintenance    0.12 mg/kg/hour IV CRI
         Bag prep:      60 mg (6 mL of 10 mg/mL) into 500 mL IV fluid → run at 1 mL/kg/hr
    Sedative (IM):      0.25–0.75 mg/kg IM (combined with acepromazine or dexmedetomidine)
    Note: Greyhounds may require higher doses than other breeds.

Cats (extra-label):
    Intermittent bolus: 0.1–0.6 mg/kg IV, IM, or SC every 4–6 hours
    Premedication:      0.1–0.6 mg/kg IV, IM, or SC
    CRI: Loading dose   0.1–0.2 mg/kg IV
         Maintenance    0.12 mg/kg/hour IV CRI
         Bag prep:      Same as dogs, 60 mg into 500 mL, run at 1 mL/kg/hr

Stock: 10 mg/mL (human-labeled; no US veterinary product, use human methadone HCl injection).
DEA Schedule II controlled substance.
Compatible in syringe with acepromazine; Y-site compatible with dexmedetomidine, midazolam,
propofol, alfaxalone. Incompatible with meloxicam, thiopental, pentobarbital.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

METHADONE_STOCK_MG_PER_ML = 10.0
METHADONE_BAG_MG = 60.0  # mg added to bag (Plumb's bag-prep protocol)
METHADONE_BAG_VOLUME_ML = 500.0  # mL IV fluid
METHADONE_BAG_RATE_ML_PER_KG_PER_HR = 1.0  # mL/kg/hr


class MethadoneSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class MethadoneInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: MethadoneSpecies
    stock_mg_per_ml: float = METHADONE_STOCK_MG_PER_ML


@dataclass
class MethadoneResult:
    weight_kg: float
    species: MethadoneSpecies
    stock_mg_per_ml: float

    # Intermittent bolus
    bolus_low_mg_per_kg: float
    bolus_high_mg_per_kg: float
    bolus_low_mg: float
    bolus_high_mg: float
    bolus_low_ml: float
    bolus_high_ml: float
    bolus_interval: str

    # Premedication
    premed_low_mg_per_kg: float
    premed_high_mg_per_kg: float
    premed_low_mg: float
    premed_high_mg: float
    premed_low_ml: float
    premed_high_ml: float

    # CRI, loading
    cri_load_low_mg_per_kg: float
    cri_load_high_mg_per_kg: float
    cri_load_low_mg: float
    cri_load_high_mg: float
    cri_load_low_ml: float
    cri_load_high_ml: float

    # CRI, maintenance
    cri_rate_mg_per_kg_per_hr: float
    cri_pump_rate_ml_per_hr: float  # undiluted from stock vial

    # CRI, bag prep
    bag_pump_rate_ml_per_hr: float  # 1 mL/kg/hr from bag

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def calculate(inputs: MethadoneInputs) -> MethadoneResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    stock = inputs.stock_mg_per_ml

    # ── Species-specific parameters (Plumb's) ─────────────────────────────
    if inputs.species == MethadoneSpecies.DOG:
        bolus_low = 0.1
        bolus_high = 0.5
        bolus_interval = "4–8 hr"
        premed_low = 0.2
        premed_high = 0.3
    else:  # CAT
        bolus_low = 0.1
        bolus_high = 0.6
        bolus_interval = "4–6 hr"
        premed_low = 0.1
        premed_high = 0.6

    # CRI parameters same for both species per Plumb's
    cri_load_low = 0.1
    cri_load_high = 0.2
    cri_rate = 0.12  # mg/kg/hr

    # ── Calculations ──────────────────────────────────────────────────────
    def _vol(dose_mg_per_kg: float) -> float:
        return round((dose_mg_per_kg * weight_kg) / stock, 3)

    def _mg(dose_mg_per_kg: float) -> float:
        return round(dose_mg_per_kg * weight_kg, 3)

    bolus_low_mg = _mg(bolus_low)
    bolus_high_mg = _mg(bolus_high)
    bolus_low_ml = _vol(bolus_low)
    bolus_high_ml = _vol(bolus_high)

    premed_low_mg = _mg(premed_low)
    premed_high_mg = _mg(premed_high)
    premed_low_ml = _vol(premed_low)
    premed_high_ml = _vol(premed_high)

    cri_load_low_mg = _mg(cri_load_low)
    cri_load_high_mg = _mg(cri_load_high)
    cri_load_low_ml = _vol(cri_load_low)
    cri_load_high_ml = _vol(cri_load_high)

    cri_pump_rate_ml_per_hr = round((cri_rate * weight_kg) / stock, 3)
    bag_pump_rate_ml_per_hr = round(METHADONE_BAG_RATE_ML_PER_KG_PER_HR * weight_kg, 1)

    # ── Warnings ──────────────────────────────────────────────────────────
    warnings.append(
        "Bradycardia risk, methadone has greater cardiodepressant effect than morphine "
        "(Plumb's). Monitor HR and blood pressure. Use caution with pre-existing "
        "bradyarrhythmias or when combined with alpha-2 agonists."
    )
    warnings.append(
        "Respiratory depression is dose-related. Monitor RR, SpO₂, and ETCO₂. "
        "Reversible with naloxone. DEA Schedule II, no US veterinary product; "
        "use human methadone HCl injection 10 mg/mL."
    )
    if inputs.species == MethadoneSpecies.DOG:
        warnings.append(
            "Panting, whining, vocalization, and defecation common after injection in dogs (Plumb's). "
            "Greyhounds may require higher doses than other breeds."
        )
    warnings.append(
        "INCOMPATIBLE with meloxicam, thiopental, and pentobarbital at Y-sites. "
        "Do not mix in same line as NSAIDs. Compatible in syringe with acepromazine; "
        "Y-site compatible with dexmedetomidine, midazolam, propofol, alfaxalone (Plumb's)."
    )

    # ── Notes ─────────────────────────────────────────────────────────────
    notes.append(
        f"Stock: {stock} mg/mL. Only human-labeled product available in the US "
        "(methadone HCl injection 10 mg/mL). Verify vial label before drawing up."
    )
    notes.append(
        "CRI bag prep (Plumb's): Add 60 mg methadone (6 mL of 10 mg/mL) to 500 mL IV fluid "
        f"(0.9% NaCl, LRS, or 5% dextrose) → concentration 0.12 mg/mL. "
        f"Run at 1 mL/kg/hr = {bag_pump_rate_ml_per_hr} mL/hr for this patient. "
        "May combine with ketamine and/or lidocaine in same bag."
    )
    notes.append(
        "Methadone has NMDA antagonist activity (both isomers) and inhibits norepinephrine "
        "reuptake, may provide additional benefit in opioid-tolerant patients or "
        "those with central sensitisation."
    )
    notes.append(
        "SC bioavailability ≈80% (peak ~1 hr); IM bioavailability ≈90% (peak 5–15 min). "
        "Oral and OTM routes have poor/variable bioavailability in dogs; OTM is 44% in cats."
    )

    return MethadoneResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        stock_mg_per_ml=stock,
        bolus_low_mg_per_kg=bolus_low,
        bolus_high_mg_per_kg=bolus_high,
        bolus_low_mg=bolus_low_mg,
        bolus_high_mg=bolus_high_mg,
        bolus_low_ml=bolus_low_ml,
        bolus_high_ml=bolus_high_ml,
        bolus_interval=bolus_interval,
        premed_low_mg_per_kg=premed_low,
        premed_high_mg_per_kg=premed_high,
        premed_low_mg=premed_low_mg,
        premed_high_mg=premed_high_mg,
        premed_low_ml=premed_low_ml,
        premed_high_ml=premed_high_ml,
        cri_load_low_mg_per_kg=cri_load_low,
        cri_load_high_mg_per_kg=cri_load_high,
        cri_load_low_mg=cri_load_low_mg,
        cri_load_high_mg=cri_load_high_mg,
        cri_load_low_ml=cri_load_low_ml,
        cri_load_high_ml=cri_load_high_ml,
        cri_rate_mg_per_kg_per_hr=cri_rate,
        cri_pump_rate_ml_per_hr=cri_pump_rate_ml_per_hr,
        bag_pump_rate_ml_per_hr=bag_pump_rate_ml_per_hr,
        warnings=warnings,
        notes=notes,
        sources=METHADONE_SOURCES,
    )


METHADONE_SOURCES = (
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, methadone monograph. "
            "Bolus, premedication, and CRI dosing for dogs and cats "
            "(extra-label). Stock concentration (10 mg/mL human-labeled), "
            "Y-site incompatibilities, and DEA Schedule II status."
        )
    ),
    Source(
        citation=(
            "KuKanich B, Lascelles BDX, Papich MG. Use of a von Frey device for "
            "evaluation of pharmacokinetics and pharmacodynamics of morphine "
            "after oral administration in healthy dogs. Am J Vet Res "
            "2005;66:1616–1622. (Methadone metabolism and dosing context.)"
        )
    ),
    Source(
        citation=(
            "Ingvast-Larsson C, Holgersson A, Bondesson U, Lagerstedt AS, "
            "Olsson K. Clinical pharmacology of methadone in dogs. "
            "Vet Anaesth Analg 2010;37:48–56."
        )
    ),
)


METHADONE_CATALOG_ENTRY = {
    "slug": "methadone",
    "display_name": "Methadone",
    "short_name": "Methadone",
    "category": "Analgesia",
    "kind": "single_drug_cri",
    "mechanism_summary": (
        "Full mu-opioid agonist with additional NMDA-receptor antagonism. "
        "Useful for neuropathic or wind-up pain where pure mu-agonists are "
        "insufficient. Available as bolus, premedication, or CRI. DEA C-II."
    ),
}
