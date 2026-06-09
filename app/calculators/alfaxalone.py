"""
Alfaxalone calculator, dogs and cats.

Source: Plumb's Veterinary Drugs, Alfaxalone monograph (current edition).

Stock: 10 mg/mL (Alfaxan® Multidose). DEA Schedule IV.

DOGS. IV induction (label):
    Unpremedicated: 1.5–4.5 mg/kg IV (avg ~3 mg/kg)
    Premedicated:   1.1–1.7 mg/kg IV (varies by premedication)

DOGS. IV maintenance (label):
    Bolus: 1.2–1.5 mg/kg IV per 10 min (premedicated: 1.0–1.2 mg/kg)
    CRI:   6–7 mg/kg/hr (premedicated); 8–9 mg/kg/hr (unpremedicated)
           = 0.10–0.12 mL/kg/min (premedicated); 0.13–0.15 mL/kg/min (unpremedicated)

CATS. IV induction (label):
    Unpremedicated: 2.2–9.7 mg/kg IV (avg ~5 mg/kg)
    Premedicated:   2.3–3.6 mg/kg IV

CATS. IV maintenance (label):
    Bolus: 1.1–1.3 mg/kg IV per 10 min (premedicated); 1.6–1.8 mg/kg (unpremedicated)
    CRI:   7–8 mg/kg/hr (premedicated); 10–11 mg/kg/hr (unpremedicated)
           = 0.011–0.013 mL/kg/min (premedicated); 0.016–0.018 mL/kg/min (unpremedicated)

CATS. IM sedation (extra-label, selected protocols from Plumb's):
    Alfaxalone 3 mg/kg + dexmedetomidine 10 µg/kg + butorphanol 0.2 mg/kg IM (castration)
    Alfaxalone 1 mg/kg + dexmedetomidine 5 µg/kg + butorphanol 0.2 mg/kg IM (90 min sedation)
    Alfaxalone 1.5 mg/kg + hydromorphone 0.1 mg/kg + midazolam 0.2 mg/kg IM
    Alfaxalone 2–3 mg/kg + butorphanol 0.2–0.4 mg/kg IM (blood donation)
    (IM combos are surfaced as reference notes, not calculated, volumes depend on combo drugs)

Administration: IV slowly over ~60 seconds to effect. Never rapid bolus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

ALFAXALONE_STOCK_MG_PER_ML = 10.0


class AlfaxaloneSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


class AlfaxalonePremed(str, Enum):
    NONE = "none"
    PREMEDICATED = "premedicated"


class AlfaxaloneMode(str, Enum):
    INDUCTION = "induction"
    MAINTENANCE = "maintenance"


@dataclass
class AlfaxaloneInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: AlfaxaloneSpecies
    premedicated: AlfaxalonePremed
    mode: AlfaxaloneMode
    # For maintenance CRI, user-adjustable rate within range
    cri_rate_mg_per_kg_per_hr: float | None = None


@dataclass
class AlfaxaloneDoseRange:
    low_mg_per_kg: float
    high_mg_per_kg: float
    label: str


@dataclass
class AlfaxaloneResult:
    weight_kg: float
    species: AlfaxaloneSpecies
    premedicated: AlfaxalonePremed
    mode: AlfaxaloneMode
    stock_mg_per_ml: float

    # Induction
    induction_low_mg_per_kg: float
    induction_high_mg_per_kg: float
    induction_low_mg: float
    induction_high_mg: float
    induction_low_ml: float
    induction_high_ml: float

    # Maintenance bolus (per 10 min)
    bolus_low_mg_per_kg: float
    bolus_high_mg_per_kg: float
    bolus_low_mg: float
    bolus_high_mg: float
    bolus_low_ml: float
    bolus_high_ml: float

    # Maintenance CRI
    cri_range_low_mg_per_kg_per_hr: float
    cri_range_high_mg_per_kg_per_hr: float
    cri_rate_mg_per_kg_per_hr: float
    cri_pump_rate_ml_per_hr: float
    cri_range_low_ml_per_hr: float
    cri_range_high_ml_per_hr: float

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


# ── Species/premedication parameters from Plumb's ────────────────────────────

_PARAMS: dict[tuple[AlfaxaloneSpecies, AlfaxalonePremed], dict] = {
    (AlfaxaloneSpecies.DOG, AlfaxalonePremed.NONE): {
        "induction_low": 1.5,
        "induction_high": 4.5,
        "bolus_low": 1.3,
        "bolus_high": 1.5,
        "cri_low": 8.0,
        "cri_high": 9.0,
    },
    (AlfaxaloneSpecies.DOG, AlfaxalonePremed.PREMEDICATED): {
        "induction_low": 1.1,
        "induction_high": 1.7,
        "bolus_low": 1.0,
        "bolus_high": 1.2,
        "cri_low": 6.0,
        "cri_high": 7.0,
    },
    (AlfaxaloneSpecies.CAT, AlfaxalonePremed.NONE): {
        "induction_low": 2.2,
        "induction_high": 9.7,
        "bolus_low": 1.4,
        "bolus_high": 1.8,
        "cri_low": 10.0,
        "cri_high": 11.0,
    },
    (AlfaxaloneSpecies.CAT, AlfaxalonePremed.PREMEDICATED): {
        "induction_low": 2.3,
        "induction_high": 3.6,
        "bolus_low": 1.1,
        "bolus_high": 1.3,
        "cri_low": 7.0,
        "cri_high": 8.0,
    },
}


def calculate(inputs: AlfaxaloneInputs) -> AlfaxaloneResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    stock = ALFAXALONE_STOCK_MG_PER_ML
    p = _PARAMS[(inputs.species, inputs.premedicated)]

    # Induction
    ind_low_mg = round(p["induction_low"] * weight_kg, 2)
    ind_high_mg = round(p["induction_high"] * weight_kg, 2)
    ind_low_ml = round(ind_low_mg / stock, 2)
    ind_high_ml = round(ind_high_mg / stock, 2)

    # Maintenance bolus
    bol_low_mg = round(p["bolus_low"] * weight_kg, 2)
    bol_high_mg = round(p["bolus_high"] * weight_kg, 2)
    bol_low_ml = round(bol_low_mg / stock, 2)
    bol_high_ml = round(bol_high_mg / stock, 2)

    # Maintenance CRI
    cri_low = p["cri_low"]
    cri_high = p["cri_high"]
    cri_rate = inputs.cri_rate_mg_per_kg_per_hr
    if cri_rate is None:
        cri_rate = cri_low  # default to low end

    cri_ml_per_hr = round((cri_rate * weight_kg) / stock, 2)
    cri_low_ml_per_hr = round((cri_low * weight_kg) / stock, 2)
    cri_high_ml_per_hr = round((cri_high * weight_kg) / stock, 2)

    # Range warning for CRI
    if cri_rate < cri_low or cri_rate > cri_high:
        warnings.append(
            f"CRI rate {cri_rate} mg/kg/hr is outside the published range "
            f"({cri_low}–{cri_high} mg/kg/hr) for {'premedicated' if inputs.premedicated == AlfaxalonePremed.PREMEDICATED else 'unpremedicated'} "
            f"{inputs.species.value}s per Plumb's."
        )

    # Critical warnings
    warnings.append(
        "Administer IV slowly over ~60 seconds to effect, titrate against patient response. "
        "Rapid IV administration causes respiratory depression and apnea. "
        "Postinduction apnea occurred in 40% of dogs and 16% of cats in field studies (mean duration 100 s in dogs, 60 s in cats). "
        "Have intubation equipment, oxygen, and IPPV immediately available."
    )
    warnings.append(
        "Alfaxalone provides NO analgesia. Ensure appropriate analgesic coverage for any painful procedure."
    )

    if inputs.species == AlfaxaloneSpecies.CAT and inputs.premedicated == AlfaxalonePremed.NONE:
        warnings.append(
            "Unpremedicated cats have a wide induction range (2.2–9.7 mg/kg). "
            "Titrate slowly to effect, the upper end is rarely needed. "
            "Excitement, muscle tremors, opisthotonus, and paddling are more common without premedication. "
            "Recover in a quiet room."
        )

    warnings.append("DEA Schedule IV controlled substance. Record all use per applicable regulations.")

    # Notes
    notes.append(
        "CRI dose unit warning (per Plumb's): do not confuse mg/kg/HOUR with mg/kg/MINUTE; "
        "these differ by 60×. The CRI rate above is in mg/kg/hr."
    )
    notes.append(
        "Preanesthetic drugs reduce induction dose by 10–50% depending on agent. "
        "Always titrate induction dose against the individual patient's response; "
        "do not administer the full calculated dose as a rapid bolus."
    )
    if inputs.species == AlfaxaloneSpecies.CAT:
        notes.append(
            "IM protocols for cats (extra-label, from Plumb's): "
            "Alfaxalone 3 mg/kg + dexmedetomidine 10 µg/kg + butorphanol 0.2 mg/kg IM (castration); "
            "Alfaxalone 1.5 mg/kg + hydromorphone 0.1 mg/kg + midazolam 0.2 mg/kg IM (IV catheter placement); "
            "Alfaxalone 2–3 mg/kg + butorphanol 0.2–0.4 mg/kg IM (blood donation). "
            "These are combination protocols, use the Kitty Magic calculator for dexmedetomidine combinations."
        )
    notes.append(
        "Maintenance bolus provides ~6–8 min of additional anesthesia per injection. "
        "CRI may require a 3-step infusion regimen to maintain stable plasma concentrations "
        "(Plumb's references a study in cats showing 3-step infusion outperformed single rate)."
    )

    return AlfaxaloneResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        premedicated=inputs.premedicated,
        mode=inputs.mode,
        stock_mg_per_ml=stock,
        induction_low_mg_per_kg=p["induction_low"],
        induction_high_mg_per_kg=p["induction_high"],
        induction_low_mg=ind_low_mg,
        induction_high_mg=ind_high_mg,
        induction_low_ml=ind_low_ml,
        induction_high_ml=ind_high_ml,
        bolus_low_mg_per_kg=p["bolus_low"],
        bolus_high_mg_per_kg=p["bolus_high"],
        bolus_low_mg=bol_low_mg,
        bolus_high_mg=bol_high_mg,
        bolus_low_ml=bol_low_ml,
        bolus_high_ml=bol_high_ml,
        cri_range_low_mg_per_kg_per_hr=cri_low,
        cri_range_high_mg_per_kg_per_hr=cri_high,
        cri_rate_mg_per_kg_per_hr=cri_rate,
        cri_pump_rate_ml_per_hr=cri_ml_per_hr,
        cri_range_low_ml_per_hr=cri_low_ml_per_hr,
        cri_range_high_ml_per_hr=cri_high_ml_per_hr,
        warnings=warnings,
        notes=notes,
        sources=ALFAXALONE_SOURCES,
    )


ALFAXALONE_SOURCES = (
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, alfaxalone monograph. Induction "
            "dosing for premedicated and unpremedicated dogs and cats; CRI/TIVA; "
            "IM/SC route in cats (extra-label); cyclodextrin (HPCD) vehicle "
            "properties."
        )
    ),
    Source(
        citation=(
            "Suarez MA, Dzikiti BT, Stegmann FG, Hartman M. Comparison of "
            "alfaxalone and propofol administered as total intravenous anaesthesia "
            "for ovariohysterectomy in dogs. Vet Anaesth Analg 2012;39(3):236–244."
        )
    ),
    Source(
        citation=(
            "Whittem T, Pasloske KS, Heit MC, Ranasinghe MG. The pharmacokinetics "
            "and pharmacodynamics of alfaxalone in cats after single and multiple "
            "intravenous administration. J Vet Pharmacol Ther 2008;31(6):571–579."
        )
    ),
)

ALFAXALONE_CATALOG_ENTRY = {
    "slug": "alfaxalone",
    "display_name": "Alfaxalone",
    "short_name": "Alfaxalone",
    "category": "Anesthesia & Sedation",
    "kind": "single_drug_induction",
    "mechanism_summary": (
        "Neuroactive steroid IV anesthetic. GABA-A potentiation via a "
        "different binding site than propofol. Wider therapeutic margin and "
        "less cardiovascular depression than propofol; labeled IM/SC route "
        "in cats. No analgesia."
    ),
}
