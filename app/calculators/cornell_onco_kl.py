"""
Cornell KL (ketamine-lidocaine) infusion calculator.

Outpatient IV ketamine-lidocaine infusion for palliation of cancer pain
in dogs and cats. Original protocol developed at Cornell (Dr. Andrea
Looney, 2012); retrospective evaluation published 2025:

    Iocolano KE, Looney A, Balkman CE, Hume KR, Boesch JM, Sylvester SR.
    Retrospective evaluation of outpatient intravenous ketamine-lidocaine
    infusions for the palliation of cancer pain in dogs and cats. JAVMA.
    2025;263(4):499–506. doi:10.2460/javma.24.09.0595

Protocol summary (per the 2025 paper):
    - 0.9% NaCl carrier, 250 mL (cats or dogs <15 kg) or 500 mL (dogs ≥15 kg)
    - Total drug added to bag: 18 mg/kg lidocaine + 0.9 mg/kg ketamine
    - Administered at 2.5 mL/kg/hr for 4–6 hours
    - Target delivered rate: 3 mg/kg/hr lidocaine + 0.15 mg/kg/hr ketamine
        (cats: lidocaine reduced to 1.5 mg/kg/hr per Pypendop/Plumb's)
    - No loading dose
    - Repeated every 2–4 weeks for refractory cancer pain

Efficacy thresholds (per 2025 paper, Table 4 + multivariate analysis):
    Lidocaine ≥ 25 µg/kg/min (= 1.5 mg/kg/hr)
    Ketamine  ≥ 2 µg/kg/min (= 0.12 mg/kg/hr)
    Total ketamine dose ≥ 0.5 mg/kg (across the entire infusion)

Below these thresholds, the paper documents significantly lower clinical
benefit. Patients <15 kg are at highest risk of falling below thresholds
because their 2.5 mL/kg/hr × 4–6 hr infusion volume is much smaller than
the 250–500 mL bag size, so they don't finish the bag and miss drug.

Math model:
    User inputs:
        weight_kg, species, bag_volume_mL, duration_hr
    Bag prep (Looney 2012 recipe):
        lidocaine_mg_to_add = target_lido_mg_per_kg_per_hr × weight_kg × duration_hr
        lidocaine_ml_to_draw = lidocaine_mg_to_add / 20  (2% = 20 mg/mL)
        ketamine_mg_to_add = target_keta_mg_per_kg_per_hr × weight_kg × duration_hr
        ketamine_ml_to_draw = ketamine_mg_to_add / 100  (stock 100 mg/mL)
        total_drug_volume_ml_to_remove_from_bag = lido_ml + keta_ml
        final_bag_volume_ml = bag_volume_mL  (after remove + add)
    Delivered rates (2025 paper view):
        bag_lidocaine_concentration_mg_per_mL = lidocaine_mg_to_add / bag_volume_mL
        bag_ketamine_concentration_mg_per_mL = ketamine_mg_to_add / bag_volume_mL
        infusion_rate_mL_per_hr = 2.5 × weight_kg
        infusion_volume_used_mL = infusion_rate_mL_per_hr × duration_hr
        # If infusion_volume_used > bag_volume, patient runs out of bag
        # If infusion_volume_used < bag_volume, drug is wasted
        actual_lidocaine_delivered_mg = (
            min(infusion_volume_used_mL, bag_volume_mL)
            × bag_lidocaine_concentration_mg_per_mL
        )
        actual_ketamine_delivered_mg = (
            min(infusion_volume_used_mL, bag_volume_mL)
            × bag_ketamine_concentration_mg_per_mL
        )
        delivered_lidocaine_rate_mg_per_kg_per_hr = (
            actual_lidocaine_delivered_mg / weight_kg / actual_duration_hr
        )
        # similarly for ketamine

Stock concentrations (standard veterinary):
    Lidocaine: 2% = 20 mg/mL (preservative-free, NO epinephrine for IV)
    Ketamine:  100 mg/mL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Stock concentrations
LIDOCAINE_STOCK_MG_PER_ML = 20.0  # 2% lidocaine WITHOUT epinephrine
KETAMINE_STOCK_MG_PER_ML = 100.0  # standard veterinary ketamine

# Target delivered rates per 2025 JAVMA paper
TARGET_LIDOCAINE_DOG_MG_PER_KG_PER_HR = 3.0
TARGET_LIDOCAINE_CAT_MG_PER_KG_PER_HR = 1.5
TARGET_KETAMINE_MG_PER_KG_PER_HR = 0.15  # both species

# Standard infusion rate
INFUSION_RATE_ML_PER_KG_PER_HR = 2.5

# Duration window
DURATION_MIN_HR = 4
DURATION_DEFAULT_HR = 5
DURATION_MAX_HR = 6

# Bag size presets
BAG_SIZE_OPTIONS = [100, 250, 500]
BAG_SIZE_DEFAULT_LARGE = 500  # dogs ≥15 kg
BAG_SIZE_DEFAULT_SMALL = 250  # cats or dogs <15 kg

# Patient size threshold for bag selection (per 2025 paper)
SMALL_PATIENT_THRESHOLD_KG = 15.0

# Efficacy thresholds (2025 paper)
EFFICACY_LIDO_MIN_MG_PER_KG_PER_HR = 1.5  # = 25 µg/kg/min
EFFICACY_KETA_MIN_MG_PER_KG_PER_HR = 0.12  # = 2 µg/kg/min
EFFICACY_KETA_TOTAL_DOSE_MIN_MG_PER_KG = 0.5  # total across infusion


class CornellOncoKLSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class CornellOncoKLInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: CornellOncoKLSpecies
    bag_volume_ml: float
    duration_hr: float


@dataclass
class CornellOncoKLResult:
    weight_kg: float
    species: CornellOncoKLSpecies
    bag_volume_ml: float
    duration_hr: float

    # Targets
    target_lidocaine_mg_per_kg_per_hr: float
    target_ketamine_mg_per_kg_per_hr: float

    # Bag prep (Looney recipe)
    lidocaine_mg_to_add: float
    lidocaine_ml_to_draw: float
    ketamine_mg_to_add: float
    ketamine_ml_to_draw: float
    total_volume_to_remove_from_bag_ml: float

    # Bag concentrations after prep
    bag_lidocaine_mg_per_ml: float
    bag_ketamine_mg_per_ml: float

    # Infusion delivery
    infusion_rate_ml_per_hr: float
    infusion_volume_used_ml: float
    bag_finished: bool  # True if patient uses entire bag during duration
    fluid_volume_actually_delivered_ml: float
    actual_duration_hr: float  # may equal duration_hr or be capped if bag runs out

    # Actual delivered drug
    actual_lidocaine_delivered_mg: float
    actual_ketamine_delivered_mg: float
    delivered_lidocaine_mg_per_kg_per_hr: float
    delivered_ketamine_mg_per_kg_per_hr: float
    delivered_lidocaine_ug_per_kg_per_min: float
    delivered_ketamine_ug_per_kg_per_min: float
    actual_lidocaine_total_dose_mg_per_kg: float
    actual_ketamine_total_dose_mg_per_kg: float

    # Wasted drug (if bag not finished)
    lidocaine_wasted_mg: float
    ketamine_wasted_mg: float

    # Efficacy threshold checks (per 2025 paper)
    lidocaine_below_efficacy_threshold: bool
    ketamine_below_efficacy_threshold: bool
    ketamine_total_dose_below_efficacy_threshold: bool

    # Patient-size flag
    is_small_patient: bool

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See engine.CalcResult.valid for rationale.
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _target_lidocaine_rate(species: CornellOncoKLSpecies) -> float:
    if species == CornellOncoKLSpecies.CAT:
        return TARGET_LIDOCAINE_CAT_MG_PER_KG_PER_HR
    return TARGET_LIDOCAINE_DOG_MG_PER_KG_PER_HR


def compute_cornell_onco_kl(inputs: CornellOncoKLInputs) -> CornellOncoKLResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        # Refuse to compute. The previous code substituted weight_kg=0.001,
        # which produced a plausible-looking but wildly wrong recipe if the
        # clinician missed the warning. Cornell K/L delivers ketamine plus
        # lidocaine; an undersized recipe wastes drug, an oversized one
        # could cause cat lidocaine toxicity — neither acceptable.
        return CornellOncoKLResult(
            weight_kg=weight_kg,
            species=inputs.species,
            bag_volume_ml=inputs.bag_volume_ml,
            duration_hr=inputs.duration_hr,
            target_lidocaine_mg_per_kg_per_hr=_target_lidocaine_rate(inputs.species),
            target_ketamine_mg_per_kg_per_hr=TARGET_KETAMINE_MG_PER_KG_PER_HR,
            lidocaine_mg_to_add=0.0,
            lidocaine_ml_to_draw=0.0,
            ketamine_mg_to_add=0.0,
            ketamine_ml_to_draw=0.0,
            total_volume_to_remove_from_bag_ml=0.0,
            bag_lidocaine_mg_per_ml=0.0,
            bag_ketamine_mg_per_ml=0.0,
            infusion_rate_ml_per_hr=0.0,
            infusion_volume_used_ml=0.0,
            bag_finished=False,
            fluid_volume_actually_delivered_ml=0.0,
            actual_duration_hr=0.0,
            actual_lidocaine_delivered_mg=0.0,
            actual_ketamine_delivered_mg=0.0,
            delivered_lidocaine_mg_per_kg_per_hr=0.0,
            delivered_ketamine_mg_per_kg_per_hr=0.0,
            delivered_lidocaine_ug_per_kg_per_min=0.0,
            delivered_ketamine_ug_per_kg_per_min=0.0,
            actual_lidocaine_total_dose_mg_per_kg=0.0,
            actual_ketamine_total_dose_mg_per_kg=0.0,
            lidocaine_wasted_mg=0.0,
            ketamine_wasted_mg=0.0,
            lidocaine_below_efficacy_threshold=False,
            ketamine_below_efficacy_threshold=False,
            ketamine_total_dose_below_efficacy_threshold=False,
            is_small_patient=False,
            warnings=["Weight must be greater than zero."],
            notes=[],
            sources=CORNELL_ONCO_KL_SOURCES,
            valid=False,
        )

    # Clamp duration
    duration = inputs.duration_hr
    if duration < DURATION_MIN_HR:
        warnings.append(
            f"Infusion duration of {duration:g} hr is below the published "
            f"minimum of {DURATION_MIN_HR} hr. Using {DURATION_MIN_HR} hr."
        )
        duration = DURATION_MIN_HR
    elif duration > DURATION_MAX_HR:
        warnings.append(
            f"Infusion duration of {duration:g} hr is above the published "
            f"range of {DURATION_MIN_HR}–{DURATION_MAX_HR} hr. Using "
            f"{DURATION_MAX_HR} hr."
        )
        duration = DURATION_MAX_HR

    bag_volume = max(1.0, inputs.bag_volume_ml)
    is_small = weight_kg < SMALL_PATIENT_THRESHOLD_KG

    # Targets
    target_lido = _target_lidocaine_rate(inputs.species)
    target_keta = TARGET_KETAMINE_MG_PER_KG_PER_HR

    # Bag prep math (Looney recipe)
    # Drug to add = target rate × weight × duration
    lido_mg_to_add = target_lido * weight_kg * duration
    lido_ml_to_draw = lido_mg_to_add / LIDOCAINE_STOCK_MG_PER_ML
    keta_mg_to_add = target_keta * weight_kg * duration
    keta_ml_to_draw = keta_mg_to_add / KETAMINE_STOCK_MG_PER_ML
    total_remove_volume = lido_ml_to_draw + keta_ml_to_draw

    # Bag concentrations after prep
    bag_lido_conc = lido_mg_to_add / bag_volume
    bag_keta_conc = keta_mg_to_add / bag_volume

    # Infusion delivery
    infusion_rate = INFUSION_RATE_ML_PER_KG_PER_HR * weight_kg
    infusion_volume_planned = infusion_rate * duration

    # Will the patient finish the bag?
    if infusion_volume_planned >= bag_volume:
        bag_finished = True
        fluid_volume_actually = bag_volume
        # Effective duration limited by bag
        actual_duration = bag_volume / infusion_rate if infusion_rate > 0 else duration
    else:
        bag_finished = False
        fluid_volume_actually = infusion_volume_planned
        actual_duration = duration

    # Actual delivered drug
    actual_lido_delivered_mg = fluid_volume_actually * bag_lido_conc
    actual_keta_delivered_mg = fluid_volume_actually * bag_keta_conc

    # Hourly rates as actually delivered (over the actual duration)
    if actual_duration > 0 and weight_kg > 0:
        delivered_lido_rate = actual_lido_delivered_mg / weight_kg / actual_duration
        delivered_keta_rate = actual_keta_delivered_mg / weight_kg / actual_duration
    else:
        delivered_lido_rate = 0.0
        delivered_keta_rate = 0.0

    delivered_lido_ug_min = delivered_lido_rate * 1000.0 / 60.0
    delivered_keta_ug_min = delivered_keta_rate * 1000.0 / 60.0

    # Total dose delivered
    actual_lido_total_dose = actual_lido_delivered_mg / weight_kg if weight_kg > 0 else 0.0
    actual_keta_total_dose = actual_keta_delivered_mg / weight_kg if weight_kg > 0 else 0.0

    # Wasted (if bag not finished)
    lido_wasted = lido_mg_to_add - actual_lido_delivered_mg
    keta_wasted = keta_mg_to_add - actual_keta_delivered_mg

    # Efficacy threshold checks
    lido_below = delivered_lido_rate < EFFICACY_LIDO_MIN_MG_PER_KG_PER_HR
    keta_below = delivered_keta_rate < EFFICACY_KETA_MIN_MG_PER_KG_PER_HR
    keta_total_below = actual_keta_total_dose < EFFICACY_KETA_TOTAL_DOSE_MIN_MG_PER_KG

    # Persistent warnings
    if inputs.species == CornellOncoKLSpecies.CAT:
        warnings.insert(
            0,
            "CAT-specific cautions: the cat lidocaine dose is intentionally "
            "HALF the dog dose (1.5 mg/kg/hr vs 3.0) because cats have "
            "slower lidocaine clearance and a narrower toxic margin. "
            "Monitor for early lidocaine-toxicity signs (tremors, ataxia, "
            "nystagmus, hypersalivation, vomiting) and discontinue if "
            "observed. This calculator follows the published Cornell "
            "protocol (4–6 hour infusion, anesthetized/sedated patient, "
            "continuous monitoring) and is not validated for prolonged "
            "or awake-patient cat lidocaine infusion. The 2025 JAVMA "
            "paper noted that cats <15 kg in this protocol may be "
            "underdosed even at the standard rate; if delivered rates "
            "fall below the efficacy thresholds shown below, consider "
            "using a smaller bag (eg, 100 mL) so the patient finishes "
            "it within the infusion duration.",
        )

    # Bag-not-finished and small-patient warnings
    if not bag_finished:
        utilization_pct = (fluid_volume_actually / bag_volume) * 100.0
        warnings.append(
            f"⚠ This patient will only use {utilization_pct:.0f}% of the "
            f"{bag_volume:g} mL bag during the {duration:g}-hour infusion "
            f"({fluid_volume_actually:.0f} mL of {bag_volume:g} mL). "
            f"{lido_wasted:.0f} mg of lidocaine and {keta_wasted:.1f} mg "
            f"of ketamine will be wasted (DEA controlled-substance "
            f"documentation required for the ketamine waste). The "
            f"original Looney protocol ALLOWS giving the entire bag if "
            f"the patient is tolerating it well, see the protocol note. "
            f"If you want to ensure the prescribed dose is fully "
            f"delivered, consider using a smaller bag volume "
            f"(per 2025 JAVMA paper recommendation, eg, 100 mL for "
            f"patients <15 kg)."
        )

    if is_small:
        warnings.append(
            f"Patient weight ({weight_kg:.1f} kg) is below the 15 kg "
            f"threshold flagged in the 2025 JAVMA paper. Most "
            f"osteosarcoma patients (the typical Onco KL indication) "
            f"are well over this threshold, so the underdosing concern "
            f"is more relevant for cats and small-breed dogs being "
            f"treated for non-OSA cancer pain. In the original cohort, "
            f"animals <15 kg had a 71% response rate vs 91% for "
            f"≥15 kg patients. The authors recommend administering KL "
            f"infusions in smaller animals as separate syringe-pump "
            f"infusions OR diluting in a smaller volume (eg, 100-mL "
            f"saline bag) to ensure target dosages are met. Check "
            f"the delivered rates panel below to verify thresholds."
        )

    if lido_below or keta_below or keta_total_below:
        threshold_warnings = []
        if lido_below:
            threshold_warnings.append(
                f"lidocaine ({delivered_lido_rate:.2f} mg/kg/hr = "
                f"{delivered_lido_ug_min:.1f} µg/kg/min) is below the "
                f"efficacy threshold of 1.5 mg/kg/hr (25 µg/kg/min)"
            )
        if keta_below:
            threshold_warnings.append(
                f"ketamine ({delivered_keta_rate:.3f} mg/kg/hr = "
                f"{delivered_keta_ug_min:.2f} µg/kg/min) is below the "
                f"efficacy threshold of 0.12 mg/kg/hr (2 µg/kg/min)"
            )
        if keta_total_below:
            threshold_warnings.append(
                f"total ketamine dose ({actual_keta_total_dose:.3f} "
                f"mg/kg) is below the efficacy threshold of "
                f"0.5 mg/kg across the infusion"
            )
        warnings.append(
            "⚠ Below efficacy threshold(s) per 2025 JAVMA: "
            + "; ".join(threshold_warnings)
            + ". Patients receiving these 'ultralow' doses had "
            "significantly lower clinical benefit. Consider a smaller "
            "bag, longer duration, OR running ketamine and lidocaine "
            "as separate syringe-pump infusions at the target rates."
        )

    warnings.append(
        "Use 2% lidocaine WITHOUT epinephrine. Lidocaine-with-"
        "epinephrine is sold for dental and infiltration; mixing it "
        "into the bag would deliver an unintended epinephrine bolus. "
        "Read the vial."
    )
    warnings.append(
        "All animals in the 2025 cohort received concomitant oral "
        "analgesics (NSAIDs, gabapentinoids, opioids, steroids, "
        "amantadine). KL infusion is an adjunct, NOT monotherapy. "
        "Premedicate with maropitant ± ondansetron in patients with a "
        "history of vomiting on prior infusion (2 of 105 dogs in the "
        "study had infusion-associated vomiting that was prevented by "
        "antinausea premedication on subsequent infusions)."
    )
    warnings.append(
        "Remove an equal volume of saline from the bag BEFORE adding "
        "drug, so the final bag volume is unchanged. The bag-prep math "
        "below assumes this is done."
    )

    # Notes
    notes.append(
        f"Bag preparation: add {lido_ml_to_draw:.2f} mL of 2% lidocaine "
        f"({lido_mg_to_add:.0f} mg) and {keta_ml_to_draw:.2f} mL of "
        f"ketamine 100 mg/mL ({keta_mg_to_add:.1f} mg) to a "
        f"{bag_volume:g} mL bag of 0.9% NaCl, after first removing "
        f"{total_remove_volume:.2f} mL of saline."
    )
    notes.append(
        f"Bag will deliver {bag_lido_conc:.3f} mg/mL lidocaine and "
        f"{bag_keta_conc:.4f} mg/mL ketamine. At the standard infusion "
        f"rate of 2.5 mL/kg/hr × {weight_kg:.2f} kg = "
        f"{infusion_rate:.1f} mL/hr."
    )
    if bag_finished:
        notes.append(
            f"Patient will finish the bag in {actual_duration:.2f} hours "
            f"(prescribed duration was {duration:g} hr; this difference "
            f"is small and clinically equivalent)."
        )
    else:
        notes.append(
            f"At {infusion_rate:.1f} mL/hr × {duration:g} hr = "
            f"{infusion_volume_planned:.0f} mL infused, leaving "
            f"{bag_volume - infusion_volume_planned:.0f} mL in the bag."
        )
    notes.append(
        "The 2025 JAVMA paper documents efficacy thresholds: lidocaine "
        "≥ 25 µg/kg/min (1.5 mg/kg/hr), ketamine ≥ 2 µg/kg/min "
        "(0.12 mg/kg/hr), and total ketamine dose ≥ 0.5 mg/kg. Patients "
        'below these thresholds ("ultralow doses") had significantly '
        "lower clinical benefit. The actual-delivered panel below "
        "checks these for you."
    )
    notes.append(
        "Median number of infusions in the JAVMA cohort was 2 (range "
        "2–49); typical interval 27.5 days. The infusion may be "
        "repeated every 2–4 weeks based on duration of clinical "
        "benefit. Number of infusions was positively associated with "
        "longer progression-free survival."
    )

    return CornellOncoKLResult(
        weight_kg=round(weight_kg, 2),
        species=inputs.species,
        bag_volume_ml=bag_volume,
        duration_hr=duration,
        target_lidocaine_mg_per_kg_per_hr=target_lido,
        target_ketamine_mg_per_kg_per_hr=target_keta,
        lidocaine_mg_to_add=round(lido_mg_to_add, 1),
        lidocaine_ml_to_draw=round(lido_ml_to_draw, 2),
        ketamine_mg_to_add=round(keta_mg_to_add, 2),
        ketamine_ml_to_draw=round(keta_ml_to_draw, 2),
        total_volume_to_remove_from_bag_ml=round(total_remove_volume, 2),
        bag_lidocaine_mg_per_ml=round(bag_lido_conc, 4),
        bag_ketamine_mg_per_ml=round(bag_keta_conc, 4),
        infusion_rate_ml_per_hr=round(infusion_rate, 1),
        infusion_volume_used_ml=round(infusion_volume_planned, 1),
        bag_finished=bag_finished,
        fluid_volume_actually_delivered_ml=round(fluid_volume_actually, 1),
        actual_duration_hr=round(actual_duration, 2),
        actual_lidocaine_delivered_mg=round(actual_lido_delivered_mg, 1),
        actual_ketamine_delivered_mg=round(actual_keta_delivered_mg, 2),
        delivered_lidocaine_mg_per_kg_per_hr=round(delivered_lido_rate, 3),
        delivered_ketamine_mg_per_kg_per_hr=round(delivered_keta_rate, 4),
        delivered_lidocaine_ug_per_kg_per_min=round(delivered_lido_ug_min, 1),
        delivered_ketamine_ug_per_kg_per_min=round(delivered_keta_ug_min, 2),
        actual_lidocaine_total_dose_mg_per_kg=round(actual_lido_total_dose, 2),
        actual_ketamine_total_dose_mg_per_kg=round(actual_keta_total_dose, 3),
        lidocaine_wasted_mg=round(max(0.0, lido_wasted), 1),
        ketamine_wasted_mg=round(max(0.0, keta_wasted), 2),
        lidocaine_below_efficacy_threshold=lido_below,
        ketamine_below_efficacy_threshold=keta_below,
        ketamine_total_dose_below_efficacy_threshold=keta_total_below,
        is_small_patient=is_small,
        warnings=warnings,
        notes=notes,
        sources=CORNELL_ONCO_KL_SOURCES,
    )


CORNELL_ONCO_KL_SOURCES = (
    Source(
        citation=(
            "Iocolano KE, Looney A, Balkman CE, Hume KR, Boesch JM, Sylvester SR. "
            "Use of ketamine and lidocaine constant rate infusions for the "
            "palliation of cancer pain in dogs and cats. JAVMA 2025. "
            "(Retrospective evaluation of the original Cornell KL protocol; "
            "recommended drug delivery rates and the smaller-patient dilution "
            "caveat.)"
        )
    ),
    Source(
        citation=(
            "Looney AL. Oncology pain management. Cornell University College of "
            "Veterinary Medicine, 2012 protocol. Original ketamine-lidocaine bag "
            "formulation (120 mg ketamine + 1 g lidocaine in 1 L LRS)."
        )
    ),
    Source(
        citation=(
            "Pypendop BH, Ilkiw JE. Assessment of the hemodynamic effects of "
            "lidocaine administered IV in isoflurane-anesthetized cats. Am J Vet "
            "Res 2005;66:661–668. (Basis for reduced lidocaine dose in cat "
            "protocol.)"
        )
    ),
)

CORNELL_ONCO_KL_CATALOG_ENTRY = {
    "slug": "cornell-onco-kl",
    "display_name": "Oncology KL · Cornell protocol",
    "short_name": "Onco KL",
    "category": "Analgesia & Anesthesia",
    "kind": "multi_drug_protocol",
    "mechanism_summary": (
        "Outpatient IV ketamine-lidocaine bag infusion for palliation "
        "of refractory cancer pain, most commonly osteosarcoma in dogs "
        "and oral squamous cell carcinoma in cats. Sub-anesthetic "
        "ketamine (NMDA antagonism, anti-windup activity) plus systemic "
        "lidocaine (sodium-channel blockade, anti-inflammatory activity, "
        "NMDA antagonism at higher doses) administered over 4–6 hours, "
        "repeated every 2–4 weeks. Originally developed at Cornell "
        "(Looney 2012); retrospective evaluation published in JAVMA 2025 "
        "documented 76% clinical benefit rate across 105 dogs and 9 cats."
    ),
    "indications_summary": (
        "Outpatient ketamine-lidocaine bag infusion for refractory "
        "cancer pain in dogs and cats. Adjunctive to oral analgesics "
        "(NSAIDs, gabapentinoids, opioids, amantadine, steroids), "
        "bisphosphonates, and interventional therapies. Documented "
        "benefit across osteolytic, neuropathic, visceral, and "
        "radiation-side-effect cancer pain."
    ),
}
