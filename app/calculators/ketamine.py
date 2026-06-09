"""
Ketamine analgesic CRI calculator.

Sources:
    (Primary) Plumb's Veterinary Drugs, ketamine monograph (current edition).
    (Secondary) Silverstein DC, Hopper K, eds. Small Animal Critical Care
    Medicine. 3rd ed. Elsevier; 2023. Chapter 134, Table 134.1, p. 789.

Two indication modes (matches Plumb's three published CRI regimens
collapsed into the two clinically distinct decisions):

    1. Surgical maintenance, intraoperative analgesia/anti-windup
       Range: 10–20 µg/kg/min (= 0.6–1.2 mg/kg/hr)
       Default: 10 µg/kg/min (matches Silverstein 134.1 surgical dose)
       Plumb's: "Intraoperative use: If anesthesia was induced with a drug
       other than ketamine, give a loading dose of ketamine 0.5 mg/kg IV,
       ketamine 10–20 µg/kg/MINUTE IV CRI."

    2. Postsurgical / general analgesia, postop wind-down or stand-alone
       Range: 2–10 µg/kg/min (= 0.12–0.6 mg/kg/hr)
       Default: 2 µg/kg/min for 24 hr (matches Silverstein 134.1 + Plumb's)
       Plumb's lists postoperative analgesia at 2–10 µg/kg/min IV CRI.
       Plumb's "general analgesia" range (0.1–0.6 mg/kg/HOUR = 1.7–10
       µg/kg/min) overlaps fully and is absorbed into this mode.

    Status epilepticus is a single 5 mg/kg IV bolus per Plumb's, NOT a CRI.
    This calculator does not encode it; if you need it, look it up in
    Plumb's directly.

Both species supported. Plumb's analgesic CRI section gives identical
ranges for dogs and cats. Cat-specific cautions are surfaced via a
persistent warning when species is cat:
    - Avoid in cats with HCM (ketamine increases HR/BP/MVO₂)
    - Up to 20% of cats may have seizures at therapeutic doses (single
      agent); diazepam if needed
    - Self-limiting hyperthermia at higher doses (5–10 mg/kg);
      acepromazine 0.01–0.02 mg/kg IV may help
    - Ketamine excreted almost exclusively unchanged in cat urine,
      relevant for renal dysfunction
    - Anecdotal acute CHF reports in cats with mild-to-moderate heart
      disease

Loading dose: 0.5 mg/kg IV per Plumb's (intraoperative if anesthesia
induced with a non-ketamine agent). Postop CRI typically continues
without an additional load.

Stock concentration: 100 mg/mL (standard veterinary vial); 50 mg/mL
human-labeled also exists. Calculator default is 100 mg/mL.

Dose-unit toggle:
    Plumb's flags ketamine CRI unit confusion as a top-level Prescriber
    Highlight: "Care should be taken to not confuse CRI dosages (ie,
    mg/kg/HOUR vs µg/kg/MINUTE)." The calculator accepts either unit
    on input; the result panel always shows both. Conversion is exact:
    mg/kg/hr × 1000 / 60 = µg/kg/min.

Toxicity / overdose:
    Ketamine has a wide therapeutic index. Overdose presents as
    significant respiratory depression, treat with mechanical
    ventilation rather than analeptics. There is no specific reversal
    agent. Yohimbine + 4-aminopyridine has been suggested as a partial
    antagonist in cats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

KETAMINE_STOCK_MG_PER_ML = 100.0  # standard veterinary vial


class KetamineSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


class KetamineIndication(str, Enum):
    SURGICAL = "surgical"
    POSTSURGICAL = "postsurgical"


class KetamineDoseUnit(str, Enum):
    UG_PER_KG_PER_MIN = "ug/kg/min"
    MG_PER_KG_PER_HR = "mg/kg/hr"


@dataclass
class KetamineDoseRange:
    min_ug_per_kg_per_min: float
    max_ug_per_kg_per_min: float
    default_ug_per_kg_per_min: float
    indication_label: str
    indication_detail: str  # surfaced in result note


KETAMINE_DOSE_RANGES: dict[KetamineIndication, KetamineDoseRange] = {
    KetamineIndication.SURGICAL: KetamineDoseRange(
        min_ug_per_kg_per_min=10.0,
        max_ug_per_kg_per_min=20.0,
        default_ug_per_kg_per_min=10.0,
        indication_label="Surgical maintenance",
        indication_detail=(
            "Intraoperative analgesia at 10–20 µg/kg/min IV CRI "
            "(= 0.6–1.2 mg/kg/hr), preceded by a 0.5 mg/kg IV loading "
            "dose if anesthesia was induced with a drug other than "
            "ketamine. Discontinue or step down to the postsurgical "
            "rate when the surgical period ends."
        ),
    ),
    KetamineIndication.POSTSURGICAL: KetamineDoseRange(
        min_ug_per_kg_per_min=2.0,
        max_ug_per_kg_per_min=10.0,
        default_ug_per_kg_per_min=2.0,
        indication_label="Postsurgical / general analgesia",
        indication_detail=(
            "Postoperative analgesia 2–10 µg/kg/min IV CRI "
            "(= 0.12–0.6 mg/kg/hr); maintenance after surgery is "
            "typically 2 µg/kg/min for 24 hr. This range also covers "
            "the published 'general analgesia' range "
            "(0.1–0.6 mg/kg/hr; loading dose 0.5 mg/kg IV). Useful for "
            "anti-windup analgesia in chronic pain states or as a "
            "wind-down rate after surgical maintenance."
        ),
    ),
}


@dataclass
class KetamineInputs:
    weight_value: float
    weight_unit: WeightUnit
    dose_value: float
    dose_unit: KetamineDoseUnit
    indication: KetamineIndication
    species: KetamineSpecies


@dataclass
class KetamineResult:
    weight_kg: float
    pump_rate_ml_per_hr: float
    pump_rate_ml_per_min: float
    dose_ug_per_kg_per_min: float
    dose_mg_per_kg_per_hr: float
    stock_mg_per_ml: float
    indication: KetamineIndication
    species: KetamineSpecies
    loading_dose_mg: float
    loading_volume_ml: float
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _normalize_dose(value: float, unit: KetamineDoseUnit) -> tuple[float, float]:
    """Return (ug_per_kg_per_min, mg_per_kg_per_hr)."""
    if unit == KetamineDoseUnit.UG_PER_KG_PER_MIN:
        return value, (value * 60.0) / 1000.0
    return (value * 1000.0) / 60.0, value


def get_ketamine_dose_range(indication: KetamineIndication) -> KetamineDoseRange:
    return KETAMINE_DOSE_RANGES[indication]


def compute_ketamine(inputs: KetamineInputs) -> KetamineResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        ug_per_min_invalid, mg_per_hr_invalid = _normalize_dose(inputs.dose_value, inputs.dose_unit)
        return KetamineResult(
            weight_kg=weight_kg,
            pump_rate_ml_per_hr=0.0,
            pump_rate_ml_per_min=0.0,
            dose_ug_per_kg_per_min=ug_per_min_invalid,
            dose_mg_per_kg_per_hr=mg_per_hr_invalid,
            stock_mg_per_ml=KETAMINE_STOCK_MG_PER_ML,
            indication=inputs.indication,
            species=inputs.species,
            loading_dose_mg=0.0,
            loading_volume_ml=0.0,
            warnings=["Weight must be greater than zero."],
            notes=[],
            sources=KETAMINE_SOURCES,
            valid=False,
        )

    ug_per_min, mg_per_hr = _normalize_dose(inputs.dose_value, inputs.dose_unit)
    dose_range = get_ketamine_dose_range(inputs.indication)

    # mL/hr = (kg × mg/kg/hr) / (mg/mL)
    ml_per_hr = (weight_kg * mg_per_hr) / KETAMINE_STOCK_MG_PER_ML
    ml_per_min = ml_per_hr / 60.0

    # Loading dose: 0.5 mg/kg IV
    loading_mg = weight_kg * 0.5
    loading_ml = loading_mg / KETAMINE_STOCK_MG_PER_ML

    # Range warnings (canonical: µg/kg/min)
    if ug_per_min < dose_range.min_ug_per_kg_per_min:
        warnings.append(
            f"Dose {ug_per_min:g} µg/kg/min ({mg_per_hr:.2f} mg/kg/hr) is "
            f"below the {dose_range.indication_label.lower()} range "
            f"({dose_range.min_ug_per_kg_per_min:g}–"
            f"{dose_range.max_ug_per_kg_per_min:g} µg/kg/min). Subtherapeutic "
            f"doses may not provide adequate analgesia."
        )
    elif ug_per_min > dose_range.max_ug_per_kg_per_min:
        # Cross-reference whether it overlaps the OTHER mode's range
        warnings.append(
            f"⚠ Dose {ug_per_min:g} µg/kg/min ({mg_per_hr:.2f} mg/kg/hr) "
            f"exceeds the {dose_range.indication_label.lower()} range "
            f"({dose_range.min_ug_per_kg_per_min:g}–"
            f"{dose_range.max_ug_per_kg_per_min:g} µg/kg/min). "
            f"{'Surgical maintenance is 10–20 µg/kg/min, switch indication if appropriate.' if inputs.indication == KetamineIndication.POSTSURGICAL else 'This is above the surgical range; reassess indication and step down at end of surgery.'}"
        )

    # Persistent unit-confusion warning. Plumb's flags this as top-priority
    warnings.append(
        "Do NOT confuse ketamine CRI dose units. mg/kg/HOUR and µg/kg/MIN "
        "differ by a factor of ~60, the same number in the wrong unit is "
        "a major medication error. Plumb's flags this as a high-alert "
        "concern. The result panel below shows both units; verify both "
        "match your protocol."
    )

    # Cat persistent warning, fires whenever species is cat
    if inputs.species == KetamineSpecies.CAT:
        warnings.append(
            "Cat-specific cautions: AVOID in cats with hypertrophic "
            "cardiomyopathy (HCM), ketamine increases heart rate, blood "
            "pressure, and myocardial oxygen consumption. Up to 20% of "
            "cats given ketamine alone may experience seizures at "
            "therapeutic doses (diazepam if needed). Self-limiting "
            "hyperthermia has been documented at 5–10 mg/kg; low-dose "
            "acepromazine (0.01–0.02 mg/kg IV) may help. Ketamine is "
            "almost exclusively excreted unchanged in cat urine; "
            "consider dose reduction or alternative agents in renal "
            "dysfunction. Anecdotal acute CHF reports exist in cats "
            "with mild-to-moderate heart disease."
        )

    # General persistent warnings
    warnings.append(
        "Ketamine increases sympathetic tone, raising HR and BP. Avoid in "
        "patients with significant hypertension, heart failure, arterial "
        "aneurysm, hyperthyroidism, or pheochromocytoma. Use caution in "
        "patients with hepatic or renal insufficiency, seizure disorders, "
        "increased intraocular pressure, and procedures involving the "
        "pharynx/larynx/trachea. Monitor depth, ETCO₂, ECG, BP, body "
        "temperature, and apply ophthalmic lubricant (eyes remain open). "
        "Minimize handling and noise during recovery. Schedule III "
        "controlled substance."
    )

    # Standing notes
    notes.append(dose_range.indication_detail)
    notes.append(
        "Stock concentration is 100 mg/mL (standard veterinary vial). "
        "Ketamine may be diluted with sterile water for injection, 5% "
        "dextrose, or 0.9% sodium chloride. Compatible in same syringe "
        "with xylazine, fentanyl, hydromorphone, lidocaine, midazolam, "
        "and morphine. Do NOT mix with barbiturates or diazepam in the "
        "same syringe (precipitation)."
    )
    notes.append(
        "Ketamine is a component of the MLK multimodal CRI (delivers "
        "10 µg/kg/min ketamine, matching surgical maintenance). For "
        "morphine + lidocaine + ketamine combined, see the MLK calculator."
    )

    return KetamineResult(
        weight_kg=round(weight_kg, 2),
        pump_rate_ml_per_hr=round(ml_per_hr, 3),
        pump_rate_ml_per_min=round(ml_per_min, 4),
        dose_ug_per_kg_per_min=round(ug_per_min, 2),
        dose_mg_per_kg_per_hr=round(mg_per_hr, 3),
        stock_mg_per_ml=KETAMINE_STOCK_MG_PER_ML,
        indication=inputs.indication,
        species=inputs.species,
        loading_dose_mg=round(loading_mg, 2),
        loading_volume_ml=round(loading_ml, 3),
        warnings=warnings,
        notes=notes,
        sources=KETAMINE_SOURCES,
    )


KETAMINE_SOURCES = (
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, ketamine monograph. Analgesic CRI "
            "dosing (postoperative: 2–10 µg/kg/min IV CRI; general analgesia: "
            "0.1–0.6 mg/kg/hr). The two dose units are equivalent and Plumb's "
            "flags the unit-confusion risk as a Prescriber Highlight."
        )
    ),
    Source(
        citation=(
            "Wagner AE, Walton JA, Hellyer PW, Gaynor JS, Mama KR. Use of low "
            "doses of ketamine administered by constant rate infusion as an "
            "adjunct for postoperative analgesia in dogs. JAVMA 2002;221:72–75."
        )
    ),
    Source(
        citation=(
            "Pypendop BH, Ilkiw JE. Pharmacokinetics of ketamine and its "
            "metabolite, norketamine, after intravenous administration of a bolus "
            "of ketamine to isoflurane-anesthetized dogs. Am J Vet Res "
            "2005;66:2034–2038."
        )
    ),
)

KETAMINE_CATALOG_ENTRY = {
    "slug": "ketamine",
    "display_name": "Ketamine CRI",
    "short_name": "Ketamine",
    "category": "Anesthesia & Sedation",
    "kind": "single_drug_cri",
    "mechanism_summary": (
        "Dissociative anesthetic; NMDA-receptor antagonist. Ketamine "
        "binds the phencyclidine site of NMDA receptors, reducing "
        "glutamate release and excitatory transmission, this is the "
        "basis for both its dissociative anesthesia and its analgesic / "
        "anti-windup effects at subanesthetic doses. Cardiovascular "
        "effects (increased HR, MAP, CO) are secondary to increased "
        "sympathetic tone; in catecholamine-depleted or sympathetically "
        "blocked patients, ketamine has direct negative inotropic effects. "
        "Hepatically metabolized (CYP2B11 in dogs); cats excrete almost "
        "exclusively unchanged in urine. Schedule III controlled substance."
    ),
    "indications_summary": (
        "Adjunctive analgesic CRI for moderate-to-severe pain in "
        "dogs and cats. NMDA antagonism reduces pain wind-up, making "
        "it useful perioperatively, for chronic pain states, and for "
        "post-operative wind-down. Also a component of the MLK "
        "multimodal CRI. Two CRI regimens are available: surgical "
        "maintenance and lower-dose postsurgical/general analgesia."
    ),
}
