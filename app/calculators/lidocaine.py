"""
Lidocaine CRI calculator, dog-only.

Sources:
    (Primary) Plumb's Veterinary Drugs, lidocaine (intravenous; systemic)
    monograph (current edition).
    (Secondary) Silverstein DC, Hopper K, eds. Small Animal Critical Care
    Medicine. 3rd ed. Elsevier; 2023. Chapter 134, Table 134.1, p. 789.

Plumb's and Silverstein both publish lidocaine systemic CRI for DOGS
ONLY in the analgesic context. Plumb's monograph is explicit: "Most
clinicians avoid the use of IV lidocaine in cats for anesthetic/
analgesic purposes." Cats are markedly more sensitive to both CNS
and cardiodepressant effects of lidocaine, and Plumb's adds: "When
administered to cats anesthetized with isoflurane, lidocaine causes
greater cardiovascular depression than an equipotent dose of
isoflurane alone and thus, lidocaine is not recommended as part of
a balanced anesthesia protocol." InfusionFox's species selector is
locked to dog.

Default range encoded:
    1.5–3 mg/kg/hr IV CRI (= 25–50 µg/kg/min)

This conservative default range covers Plumb's lidocaine-alone
analgesic CRI (1–2 mg/kg loading dose, 25–50 µg/kg/min CRI) and the
GDV/septic peritonitis indication (loading 1–2 mg/kg, CRI 17–50
µg/kg/min = 1–3 mg/kg/hr). The MLK protocol delivers 50 µg/kg/min
(= 3 mg/kg/hr), the upper bound matches MLK exactly.

Plumb's also publishes higher rates (up to 100 µg/kg/min = 6 mg/kg/hr)
in specific surgical-only combinations (lidocaine/dexmed/ketamine,
lidocaine/ketamine), which step down postoperatively. The calculator
surfaces these as a reference note rather than expanding the default
range.

Loading dose: 1–2 mg/kg IV slowly (Plumb's: 2–4 minutes recommended
in humans; dose-dependent hypotension if too rapid).

Toxicity:
    Plumb's therapeutic plasma range: 1–6 µg/mL.
    Toxicity: >8 µg/mL plasma. Lethal dose 16–28 mg/kg in dogs.
    Signs: ataxia, nystagmus, depression, seizures, bradycardia,
    hypotension, circulatory collapse.
    Antidote: IV lipid emulsion 20%.
    Reduce doses 30–50% in hepatic dysfunction.

Stock: 2% lidocaine WITHOUT epinephrine = 20 mg/mL. Plumb's: "Do
NOT use the product containing epinephrine IV."

Dose-unit toggle:
    User can enter dose in either µg/kg/min OR mg/kg/hr (Plumb's gives
    doses in both conventions; Plumb's flags the unit-confusion risk).
    The result panel always shows both. Conversion: mg/kg/hr × 1000 / 60
    = µg/kg/min.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

LIDOCAINE_STOCK_MG_PER_ML = 20.0  # 2% lidocaine WITHOUT epinephrine

LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR = 1.5
LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR = 3.0
LIDOCAINE_DEFAULT_DOSE_MG_PER_KG_PER_HR = 2.5
LIDOCAINE_PLUMBS_HIGH_COMBO_MG_PER_KG_PER_HR = 6.0  # = 100 µg/kg/min


class LidocaineSpecies(str, Enum):
    DOG = "dog"


class LidocaineDoseUnit(str, Enum):
    MG_PER_KG_PER_HR = "mg/kg/hr"
    UG_PER_KG_PER_MIN = "ug/kg/min"


@dataclass
class LidocaineInputs:
    weight_value: float
    weight_unit: WeightUnit
    dose_value: float
    dose_unit: LidocaineDoseUnit
    species: LidocaineSpecies = LidocaineSpecies.DOG


@dataclass
class LidocaineResult:
    weight_kg: float
    pump_rate_ml_per_hr: float
    pump_rate_ml_per_min: float
    dose_mg_per_kg_per_hr: float
    dose_ug_per_kg_per_min: float
    stock_mg_per_ml: float
    loading_dose_min_mg: float
    loading_dose_max_mg: float
    loading_volume_min_ml: float
    loading_volume_max_ml: float
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _normalize_dose(dose_value: float, dose_unit: LidocaineDoseUnit) -> tuple[float, float]:
    """Return (mg_per_kg_per_hr, ug_per_kg_per_min)."""
    if dose_unit == LidocaineDoseUnit.MG_PER_KG_PER_HR:
        return dose_value, (dose_value * 1000.0) / 60.0
    return (dose_value * 60.0) / 1000.0, dose_value


def compute_lidocaine(inputs: LidocaineInputs) -> LidocaineResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        return LidocaineResult(
            weight_kg=weight_kg,
            pump_rate_ml_per_hr=0.0,
            pump_rate_ml_per_min=0.0,
            dose_mg_per_kg_per_hr=0.0,
            dose_ug_per_kg_per_min=0.0,
            stock_mg_per_ml=LIDOCAINE_STOCK_MG_PER_ML,
            loading_dose_min_mg=0.0,
            loading_dose_max_mg=0.0,
            loading_volume_min_ml=0.0,
            loading_volume_max_ml=0.0,
            warnings=["Weight must be greater than zero."],
            notes=[],
            sources=LIDOCAINE_SOURCES,
            valid=False,
        )

    mg_per_hr, ug_per_min = _normalize_dose(inputs.dose_value, inputs.dose_unit)

    ml_per_hr = (weight_kg * mg_per_hr) / LIDOCAINE_STOCK_MG_PER_ML
    ml_per_min = ml_per_hr / 60.0

    loading_min_mg = weight_kg * 1.0
    loading_max_mg = weight_kg * 2.0
    loading_min_ml = loading_min_mg / LIDOCAINE_STOCK_MG_PER_ML
    loading_max_ml = loading_max_mg / LIDOCAINE_STOCK_MG_PER_ML

    if mg_per_hr < LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR:
        warnings.append(
            f"Dose {mg_per_hr:g} mg/kg/hr ({ug_per_min:g} µg/kg/min) is below "
            f"the standard analgesic CRI range "
            f"({LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR:g}–"
            f"{LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR:g} mg/kg/hr / "
            f"{LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR * 1000 / 60:.0f}–"
            f"{LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR * 1000 / 60:.0f} µg/kg/min). "
            f"Subtherapeutic doses may not provide adequate analgesia."
        )
    elif mg_per_hr > LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR:
        if mg_per_hr <= LIDOCAINE_PLUMBS_HIGH_COMBO_MG_PER_KG_PER_HR:
            warnings.append(
                f"⚠ Dose {mg_per_hr:g} mg/kg/hr ({ug_per_min:g} µg/kg/min) "
                f"exceeds the standard analgesic CRI range "
                f"({LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR:g}–"
                f"{LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR:g} mg/kg/hr). "
                f"Higher rates (up to 100 µg/kg/min = 6 mg/kg/hr) appear "
                f"in the literature only in specific surgical multi-drug "
                f"combinations (eg, lidocaine/dexmedetomidine/ketamine) "
                f"that step down postoperatively to ≈25 µg/kg/min. If you "
                f"are using such a protocol, verify the indication and "
                f"step-down plan; otherwise reduce the dose."
            )
        else:
            warnings.append(
                f"⚠ Dose {mg_per_hr:g} mg/kg/hr ({ug_per_min:g} µg/kg/min) "
                f"exceeds any published analgesic CRI protocol "
                f"({LIDOCAINE_PLUMBS_HIGH_COMBO_MG_PER_KG_PER_HR:g} "
                f"mg/kg/hr = 100 µg/kg/min is the highest published rate, "
                f"and only during surgery in specific combos). Lidocaine "
                f"toxicity (ataxia, nystagmus, seizures, bradycardia, "
                f"hypotension, circulatory collapse) is increasingly likely. "
                f"Reassess indication and dose."
            )

    warnings.append(
        "Use 2% lidocaine WITHOUT epinephrine (20 mg/mL plain). "
        "Do NOT use lidocaine-with-epinephrine: that formulation is "
        "sold for dental and local infiltration; giving it IV would "
        "deliver an unintended epinephrine bolus and is a serious "
        "medication-error risk."
    )
    warnings.append(
        "Lidocaine toxicity monitoring: watch for muscle twitching or "
        "fasciculations, ataxia, nystagmus, drowsiness, depression, "
        "nausea/vomiting, seizures, bradycardia, hypotension. "
        "Therapeutic plasma range is 1–6 µg/mL; toxicity becomes likely "
        "above 8 µg/mL. Antidote: IV lipid emulsion 20% can be "
        "beneficial for lidocaine toxicity. Reduce doses 30–50% in "
        "patients with hepatic dysfunction. Concurrent cimetidine or "
        "beta-blocker therapy increases lidocaine concentration. ECG "
        "and BP monitoring recommended for prolonged or higher-dose CRIs."
    )

    notes.append(
        "Standard analgesic CRI dosing (dogs): loading 1–2 mg/kg IV "
        "slowly, maintenance 25–50 µg/kg/min (= 1.5–3 mg/kg/hr) for "
        "lidocaine alone. Provides systemic analgesia with "
        "antihyperalgesic effect. A CRI for GDV / septic peritonitis at "
        "17–50 µg/kg/min (1–3 mg/kg/hr) maintained at least 3 hr "
        "postoperatively is associated with improved short-term survival "
        "in dogs."
    )
    notes.append(
        "Higher published CRI rates (up to 100 µg/kg/min = 6 mg/kg/hr) "
        "appear in specific multi-drug surgical combinations that step "
        "down postoperatively. Examples per Plumb's: "
        "lidocaine/dexmedetomidine/ketamine (lidocaine 100 µg/kg/min "
        "during surgery → 25 µg/kg/min postoperatively × 4 hr); "
        "lidocaine/ketamine (25–100 µg/kg/min). These are surfaced for "
        "reference, the calculator's default range is the standard "
        "single-drug CRI."
    )
    notes.append(
        "Stock concentration is 20 mg/mL (2% solution). Run undiluted "
        "from a syringe pump at the calculated mL/hr rate. For very "
        "small dogs where the rate is impractically low, dilution is "
        "acceptable (Plumb's working solution: 50 mL of 2% lidocaine + "
        "1 L compatible fluid → 1 mg/mL)."
    )
    notes.append(
        "Lidocaine is a component of the MLK multimodal CRI. If the "
        "patient also needs morphine and ketamine analgesia, see the "
        "MLK calculator for the published fixed-recipe protocol."
    )

    return LidocaineResult(
        weight_kg=round(weight_kg, 2),
        pump_rate_ml_per_hr=round(ml_per_hr, 2),
        pump_rate_ml_per_min=round(ml_per_min, 3),
        dose_mg_per_kg_per_hr=round(mg_per_hr, 3),
        dose_ug_per_kg_per_min=round(ug_per_min, 1),
        stock_mg_per_ml=LIDOCAINE_STOCK_MG_PER_ML,
        loading_dose_min_mg=round(loading_min_mg, 2),
        loading_dose_max_mg=round(loading_max_mg, 2),
        loading_volume_min_ml=round(loading_min_ml, 2),
        loading_volume_max_ml=round(loading_max_ml, 2),
        warnings=warnings,
        notes=notes,
        sources=LIDOCAINE_SOURCES,
    )


LIDOCAINE_SOURCES = (
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, lidocaine monograph. CRI dosing "
            "for dogs (25–80 µg/kg/min); cautions and recommended avoidance of IV "
            "lidocaine in cats for analgesic purposes."
        )
    ),
    Source(
        citation=(
            "Smith LJ, Bentley E, Shih A, Miller PE. Systemic lidocaine infusion "
            "as an analgesic for intraocular surgery in dogs: a pilot study. Vet "
            "Anaesth Analg 2004;31:53–63."
        )
    ),
    Source(
        citation=(
            "MacDougall LM, Hethey JA, Livingston A, Clark C, Shmon CL, "
            "Duke-Novakovski T. Antinociceptive, cardiopulmonary, and sedative "
            "effects of five intravenous infusion rates of lidocaine in conscious "
            "dogs. Vet Anaesth Analg 2009;36:512–522."
        )
    ),
)

LIDOCAINE_CATALOG_ENTRY = {
    "slug": "lidocaine",
    "display_name": "Lidocaine CRI",
    "short_name": "Lidocaine",
    "category": "Analgesia",
    "kind": "single_drug_cri",
    "mechanism_summary": (
        "Sodium-channel blocker (class IB antiarrhythmic). Systemic "
        "lidocaine provides analgesia through several mechanisms: "
        "reducing ectopic activity of damaged afferent neurons, action "
        "at Na⁺/Ca²⁺/K⁺ channels, and NMDA receptor modulation. Reduces "
        "MAC of inhalant anesthetics in dogs (≈30% MAC sparing at "
        "therapeutic plasma concentrations of ~3 µg/mL). Has reactive "
        "oxygen species (ROS) scavenging effects relevant in GDV. "
        "Hepatically metabolized to active metabolites; clearance "
        "decreases in hepatic dysfunction, hypoproteinemia, and with "
        "concurrent cimetidine or beta-blocker therapy."
    ),
    "indications_summary": (
        "Adjunctive systemic analgesia CRI in dogs. Useful "
        "perioperatively, for severe medical pain (pancreatitis, "
        "peritonitis), for post-operative ileus, and as adjunctive "
        "therapy in GDV and septic peritonitis. Also the L in the "
        "MLK multimodal CRI. Dog-only: cats are uniquely sensitive "
        "to lidocaine cardiotoxicity at analgesic doses."
    ),
}
