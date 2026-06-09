"""
Intravenous Lipid Emulsion (ILE) for toxicology reversal.

Sources:
    Plumb's Veterinary Drugs, Intravenous Lipid Emulsion / Fat Emulsion
    monograph (current edition).
    Fernandez AL, Lee JA, Rahilly L, et al. The use of intravenous
    lipid emulsion as an antidote in veterinary toxicology. J Vet
    Emerg Crit Care. 2011;21(4):309-320.
    Neal JM, Barrington MJ, Fettiplace MR, et al. The Third American
    Society of Regional Anesthesia and Pain Medicine Practice Advisory
    on Local Anesthetic Systemic Toxicity: Executive Summary 2017.
    Reg Anesth Pain Med. 2018;43(2):113-123.
    Hayes WK, Brown SR, Hodgson HA, et al. Intravenous lipid emulsion
    therapy for permethrin toxicosis in cats. J Vet Emerg Crit Care.
    2020;30(5):608-614.
    Gwaltney-Brant SM, Meadows I. Intravenous lipid emulsions in
    veterinary clinical toxicology. Vet Clin North Am Small Anim
    Pract. 2018;48(6):933-942. Documents the practice range of
    0.06-0.5 mL/kg/min infusion rates over varying durations.
    Kuo I, Akpa BS et al. limits on lipid emulsion dosing in vet
    practice (cited in MSPCA-Angell: no maximum daily dose has been
    determined in veterinary patients).

Mechanism — "lipid sink":
    The 20% lipid emulsion creates a lipophilic compartment in plasma
    that sequesters fat-soluble toxins, drawing them away from their
    sites of action (cardiac sodium channels, central nervous system,
    etc.). Effect onset within minutes of bolus; benefit largely
    determined by the proportion of toxin that partitions into the
    emulsion.

Indications encoded in this calculator's persistent warnings:
    - Local anesthetic systemic toxicity (LAST) — lidocaine,
      bupivacaine overdose. The original indication.
    - Calcium channel blocker toxicity — diltiazem, amlodipine
      overdose. Cardiotoxic effects respond to ILE.
    - Beta-blocker toxicity — propranolol, atenolol overdose.
    - Permethrin / pyrethrin toxicity in cats. Topical exposure
      produces severe tremors and seizures; ILE supplements
      methocarbamol and supportive care.
    - Macrocyclic lactones — ivermectin overdose, particularly in
      MDR1-deficient breeds (Collies, Australian Shepherds, etc.).
    - Baclofen toxicity.
    - Other lipophilic toxicants.

Two protocols are in established veterinary practice. The calculator
shows both side-by-side rather than choosing for the clinician,
because protocol selection depends on indication acuity, cardiovascular
stability, and patient size, not weight alone.

    A) Fast (ASRA-derived) — 0.25 mL/kg/min × 30-60 min after a
       1.5 mL/kg bolus. Original LAST rescue protocol; preferred for
       acute cardiovascular collapse, larger patients, and rapid
       reversal indications.

    B) Slow (conservative) — 0.066 mL/kg/min × 240 min after the same
       1.5 mL/kg bolus. Used in smaller patients (the Munich
       retrospective documented this for dogs in the ~15 kg range
       and below), in cardiac instability where high volumetric load
       is poorly tolerated, and in sustained toxicities (permethrin,
       ivermectin, baclofen) where ongoing lipid sink coverage
       outlasts a 30-60 min infusion.

Cumulative dose:
    No validated maximum daily dose exists in veterinary patients.
    The 10 mL/kg/day figure cited in older protocols is conservative-
    practice extrapolation from human ASRA's 12 mL/kg recommendation,
    not a hard ceiling. VETgirl cites 8 mL/kg/day "although that is
    debated."

    Mechanistically, fat overload syndrome is rate-driven (peak plasma
    triglyceride exceeding hydrolysis and clearance capacity) rather
    than total-dose-driven. The slow protocol delivers similar or
    higher cumulative volumes at ~25% the peak triglyceride load and
    is correspondingly better tolerated cumulatively.

    The calculator classifies each protocol's cumulative dose
    (bolus + CRI, expressed per-kg) into three tiers:
        ≤ 10 mL/kg : within conservative guideline (Fernandez 2011)
        10-15 mL/kg : above conservative guideline; routinely seen
                      in practice, particularly the slow protocol
        > 15 mL/kg : high cumulative; check lipemia and fat-overload
                      markers (triglycerides, hemolysis, transaminases)
                      before continuing

    Stopping criteria are clinical (response, lipemia status, fat-
    overload signs), not a fixed mL/kg/day. The tier flags are
    checkpoints, not stop signs.

Critical practice points (encoded in warnings):
    - Use 20% lipid emulsion ONLY (Intralipid 20%, SMOFlipid, etc.).
      10% emulsion is HALF the effect at double the fluid load and is
      not appropriate for toxicology reversal.
    - Lipemia interferes with most subsequent biochemistry. Draw all
      essential labs BEFORE starting ILE.
    - Concurrent propofol confounds blood-lipid status (propofol
      vehicle is the same emulsion).
    - Dedicated IV line preferred where possible. Incompatible with
      calcium-containing solutions and sodium bicarbonate.
    - Fat overload syndrome at high cumulative doses or in
      pancreatitis-prone breeds: hyperlipidemia, hepatosplenomegaly,
      coagulopathy, hemolysis.
    - Discard remaining emulsion after 24 hours (sterility).

Math:
    Stock: 20% lipid emulsion = 200 mg/mL of fat (= 0.2 g/mL)
    Bolus volume = bolus_dose_ml_per_kg × weight_kg
    CRI rate (mL/min) = rate_ml_per_kg_per_min × weight_kg
    CRI rate (mL/hr) = rate_ml_per_kg_per_min × weight_kg × 60
    Protocol total = bolus_volume + CRI_rate × CRI_duration_min
    Cumulative per-kg = protocol_total / weight_kg
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Stock: 20% lipid emulsion
ILE_PERCENT = 20
ILE_MG_PER_ML = 200.0  # 20% = 200 mg fat per mL

# Loading bolus (shared between both protocols)
BOLUS_DOSE_ML_PER_KG = 1.5
BOLUS_DURATION_MIN_LOW = 2
BOLUS_DURATION_MIN_HIGH = 3

# Fast protocol (ASRA-derived): 0.25 mL/kg/min × 30-60 min
CRI_RATE_FAST_ML_PER_KG_PER_MIN = 0.25
CRI_DURATION_FAST_STANDARD_MIN = 30
CRI_DURATION_FAST_EXTENDED_MIN = 60

# Slow protocol (conservative): 0.066 mL/kg/min × 240 min
# Documented in practice by Gwaltney-Brant 2018 and the Munich
# retrospective for smaller patients and cardiovascular instability.
CRI_RATE_SLOW_ML_PER_KG_PER_MIN = 0.066
CRI_DURATION_SLOW_MIN = 240  # 4 hours

# Re-bolus (repeat of loading dose if inadequate response)
REBOLUS_DOSE_ML_PER_KG = 1.5

# Cumulative dose tier thresholds (per-kg).
# Conservative guideline: Fernandez 2011; VETgirl cites 8-10 mL/kg/day
# as a common max "although that is debated." No validated maximum in
# veterinary patients (Kuo 2013).
# High cumulative: 15 mL/kg approaches the human ASRA upper bound and
# is the checkpoint for lipemia and fat-overload markers.
CUMULATIVE_GUIDELINE_ML_PER_KG = 10.0
CUMULATIVE_HIGH_ML_PER_KG = 15.0


class IleSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class IleInputs:
    weight_value: float
    weight_unit: WeightUnit
    species: IleSpecies


@dataclass
class IleProtocolOption:
    """One of the established ILE practice protocols.

    The calculator computes both the ASRA-derived fast protocol (at
    its standard 30-min and extended 60-min durations) and the
    conservative slow protocol (240 min). Each option carries enough
    information for the template to render a side-by-side row: rate,
    duration, volumes, and the cumulative-dose tier classification
    (both for the protocol alone and after one rescue rebolus).
    """

    name: str  # e.g. "Fast (ASRA)" or "Slow (conservative)"
    short_label: str  # e.g. "Fast 30 min", "Slow 4 hr"

    rate_ml_per_kg_per_min: float
    rate_ml_per_min: float
    rate_ml_per_hr: float

    duration_min: int

    cri_volume_ml: float
    bolus_plus_cri_ml: float

    # Cumulative dose per-kg and tier classification.
    # cumulative_per_kg = bolus_plus_cri_ml / weight_kg
    cumulative_per_kg: float
    cumulative_tier: str  # "within" | "above" | "high"
    cumulative_label: str

    # Same but after one rescue rebolus (adds REBOLUS_DOSE_ML_PER_KG)
    cumulative_after_rebolus_per_kg: float
    cumulative_after_rebolus_tier: str
    cumulative_after_rebolus_label: str


@dataclass
class IleResult:
    weight_kg: float
    species: IleSpecies

    # Loading bolus (shared between protocols)
    bolus_volume_ml: float
    bolus_duration_min_low: int
    bolus_duration_min_high: int

    # Three protocol options shown side-by-side
    fast_standard: IleProtocolOption
    fast_extended: IleProtocolOption
    slow_conservative: IleProtocolOption

    # Re-bolus
    rebolus_volume_ml: float

    # Reference thresholds exposed for template display
    cumulative_guideline_ml_per_kg: float  # 10.0
    cumulative_high_ml_per_kg: float  # 15.0

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    # See ca_gluconate.CaGluconateResult.valid for rationale. False when
    # weight is missing or non-positive; the template suppresses numeric
    # output entirely (Safety Rule #8).
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def _classify_cumulative(per_kg: float) -> tuple[str, str]:
    """Return (tier, human-readable label) for a cumulative per-kg dose.

    Three tiers:
        ≤ 10 mL/kg : "within"  — Within conservative guideline
        ≤ 15 mL/kg : "above"   — Above conservative guideline
        > 15 mL/kg : "high"    — High cumulative; check lipemia and
                                  fat-overload markers
    """
    if per_kg <= CUMULATIVE_GUIDELINE_ML_PER_KG:
        return ("within", "Within conservative guideline")
    if per_kg <= CUMULATIVE_HIGH_ML_PER_KG:
        return ("above", "Above conservative guideline")
    return ("high", "High cumulative; check lipemia and fat-overload markers")


def _build_protocol(
    *,
    name: str,
    short_label: str,
    rate_per_kg_per_min: float,
    duration_min: int,
    weight_kg: float,
    bolus_volume_ml: float,
    rebolus_volume_ml: float,
) -> IleProtocolOption:
    """Build one protocol option with kinetics, volumes, and tier flags."""
    rate_per_min = rate_per_kg_per_min * weight_kg
    rate_per_hr = rate_per_min * 60.0
    cri_volume = rate_per_min * duration_min
    bolus_plus_cri = bolus_volume_ml + cri_volume

    cumulative_per_kg = bolus_plus_cri / weight_kg if weight_kg > 0 else 0.0
    tier, label = _classify_cumulative(cumulative_per_kg)

    after_rebolus = bolus_plus_cri + rebolus_volume_ml
    after_per_kg = after_rebolus / weight_kg if weight_kg > 0 else 0.0
    after_tier, after_label = _classify_cumulative(after_per_kg)

    return IleProtocolOption(
        name=name,
        short_label=short_label,
        rate_ml_per_kg_per_min=rate_per_kg_per_min,
        rate_ml_per_min=rate_per_min,
        rate_ml_per_hr=rate_per_hr,
        duration_min=duration_min,
        cri_volume_ml=cri_volume,
        bolus_plus_cri_ml=bolus_plus_cri,
        cumulative_per_kg=cumulative_per_kg,
        cumulative_tier=tier,
        cumulative_label=label,
        cumulative_after_rebolus_per_kg=after_per_kg,
        cumulative_after_rebolus_tier=after_tier,
        cumulative_after_rebolus_label=after_label,
    )


ILE_SOURCES: tuple[Source, ...] = (
    Source(
        citation=(
            "Plumb's Veterinary Drugs, Intravenous Lipid Emulsion "
            "monograph (current edition). Sections used: "
            "Uses/Indications (LAST, CCB / beta-blocker overdose, "
            "lipophilic toxicoses), Pharmacology/Actions (lipid-sink "
            "mechanism), Pharmacokinetics, Adverse Effects (fat "
            "overload, pancreatitis), Dosages (bolus + CRI protocol "
            "with documented 0.06-0.5 mL/kg/min CRI range), "
            "Compatibility/Compounding Considerations."
        ),
        reviewer=None,
    ),
    Source(
        citation=(
            "Fernandez AL, Lee JA, Rahilly L, et al. The use of "
            "intravenous lipid emulsion as an antidote in veterinary "
            "toxicology. J Vet Emerg Crit Care. 2011;21(4):309-320. "
            "Foundational veterinary review establishing the fast "
            "(0.25 mL/kg/min × 30-60 min) protocol and the "
            "conservative 10 mL/kg/day guideline."
        ),
        reviewer=None,
    ),
    Source(
        citation=(
            "Neal JM, Barrington MJ, Fettiplace MR, et al. The Third "
            "American Society of Regional Anesthesia and Pain Medicine "
            "Practice Advisory on Local Anesthetic Systemic Toxicity: "
            "Executive Summary 2017. Reg Anesth Pain Med. 2018;43(2)"
            ":113-123. Human LAST protocol from which the vet fast "
            "protocol is derived."
        ),
        reviewer=None,
    ),
    Source(
        citation=(
            "Hayes WK, Brown SR, Hodgson HA, et al. Intravenous lipid "
            "emulsion therapy for permethrin toxicosis in cats. J Vet "
            "Emerg Crit Care. 2020;30(5):608-614. Specific feline "
            "evidence for the permethrin indication."
        ),
        reviewer=None,
    ),
    Source(
        citation=(
            "Gwaltney-Brant SM, Meadows I. Intravenous lipid emulsions "
            "in veterinary clinical toxicology. Vet Clin North Am "
            "Small Anim Pract. 2018;48(6):933-942. Documents the "
            "practice range of 0.06-0.5 mL/kg/min infusion rates and "
            "the slow-protocol approach for smaller patients and "
            "sustained toxicities. Also cites the absence of a "
            "validated maximum daily dose in vet patients."
        ),
        reviewer=None,
    ),
)


ILE_CATALOG_ENTRY = {
    "slug": "ile",
    "display_name": "Lipid Emulsion (ILE) protocol",
    "short_name": "ILE",
    "category": "Emergency",
    "kind": "dose_calculator",
    "catalog_blurb": (
        "Intravenous lipid emulsion for toxicology reversal: local "
        "anesthetic systemic toxicity, calcium-channel and beta-blocker "
        "overdose, permethrin toxicosis, lipophilic toxicants."
    ),
    "indications_summary": (
        "20% intravenous lipid emulsion as an antidote for lipophilic "
        "toxicoses including local anesthetic systemic toxicity "
        "(lidocaine, bupivacaine), calcium-channel and beta-blocker "
        "overdose, permethrin and pyrethrin toxicosis in cats, "
        "ivermectin and macrocyclic lactone toxicity (particularly "
        "MDR1-deficient breeds), baclofen toxicosis, and other "
        "lipophilic agents. Mechanism is the lipid-sink effect: the "
        "emulsion sequesters fat-soluble toxins away from their sites "
        "of action."
    ),
    "mechanism_summary": (
        "20% intravenous lipid emulsion as an antidote for lipophilic "
        "toxicoses. The lipid-sink mechanism sequesters fat-soluble "
        "toxins (local anesthetics, calcium-channel and beta-blocker "
        "overdoses, permethrin, ivermectin in MDR1-deficient breeds, "
        "baclofen) into a lipophilic plasma compartment. Two practice "
        "protocols (fast and slow) shown side-by-side; selection "
        "depends on indication acuity, cardiovascular stability, and "
        "patient size. Cumulative dose tracked against a conservative "
        "guideline, not a hard ceiling."
    ),
}


def compute_ile(inputs: IleInputs) -> IleResult:
    warnings: list[str] = []
    notes: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        # Safety Rule #8: zero-fill numeric output when weight isn't entered.
        zero_protocol = IleProtocolOption(
            name="",
            short_label="",
            rate_ml_per_kg_per_min=0.0,
            rate_ml_per_min=0.0,
            rate_ml_per_hr=0.0,
            duration_min=0,
            cri_volume_ml=0.0,
            bolus_plus_cri_ml=0.0,
            cumulative_per_kg=0.0,
            cumulative_tier="within",
            cumulative_label="",
            cumulative_after_rebolus_per_kg=0.0,
            cumulative_after_rebolus_tier="within",
            cumulative_after_rebolus_label="",
        )
        return IleResult(
            weight_kg=weight_kg,
            species=inputs.species,
            bolus_volume_ml=0.0,
            bolus_duration_min_low=BOLUS_DURATION_MIN_LOW,
            bolus_duration_min_high=BOLUS_DURATION_MIN_HIGH,
            fast_standard=zero_protocol,
            fast_extended=zero_protocol,
            slow_conservative=zero_protocol,
            rebolus_volume_ml=0.0,
            cumulative_guideline_ml_per_kg=CUMULATIVE_GUIDELINE_ML_PER_KG,
            cumulative_high_ml_per_kg=CUMULATIVE_HIGH_ML_PER_KG,
            warnings=["Weight must be greater than zero."],
            notes=[],
            sources=ILE_SOURCES,
            valid=False,
        )

    # Loading bolus + rebolus (shared between protocols)
    bolus_volume = BOLUS_DOSE_ML_PER_KG * weight_kg
    rebolus_volume = REBOLUS_DOSE_ML_PER_KG * weight_kg

    # Build the three protocol options
    fast_standard = _build_protocol(
        name="Fast (ASRA)",
        short_label="Fast 30 min",
        rate_per_kg_per_min=CRI_RATE_FAST_ML_PER_KG_PER_MIN,
        duration_min=CRI_DURATION_FAST_STANDARD_MIN,
        weight_kg=weight_kg,
        bolus_volume_ml=bolus_volume,
        rebolus_volume_ml=rebolus_volume,
    )
    fast_extended = _build_protocol(
        name="Fast (ASRA), extended",
        short_label="Fast 60 min",
        rate_per_kg_per_min=CRI_RATE_FAST_ML_PER_KG_PER_MIN,
        duration_min=CRI_DURATION_FAST_EXTENDED_MIN,
        weight_kg=weight_kg,
        bolus_volume_ml=bolus_volume,
        rebolus_volume_ml=rebolus_volume,
    )
    slow_conservative = _build_protocol(
        name="Slow (conservative)",
        short_label="Slow 4 hr",
        rate_per_kg_per_min=CRI_RATE_SLOW_ML_PER_KG_PER_MIN,
        duration_min=CRI_DURATION_SLOW_MIN,
        weight_kg=weight_kg,
        bolus_volume_ml=bolus_volume,
        rebolus_volume_ml=rebolus_volume,
    )

    # Clinical guidance notes (non-blocking, not warnings)
    notes.append(
        "Two practice protocols shown side-by-side. The fast protocol "
        "(ASRA-derived) is preferred for acute cardiovascular collapse, "
        "larger patients, and rapid reversal indications (LAST, CCB and "
        "beta-blocker shock). The slow protocol is preferred in smaller "
        "patients, in cardiovascular instability where the high "
        "volumetric load of the fast protocol is poorly tolerated, and "
        "in sustained toxicities (permethrin, ivermectin, baclofen) "
        "where ongoing lipid sink coverage outlasts a 30-60 min infusion."
    )
    notes.append(
        "Stopping criteria are clinical: clinical response, lipemia "
        "status before any repeat dose, and fat-overload markers "
        "(triglycerides, hemolysis, transaminases). No validated "
        "maximum daily dose exists in veterinary patients. The "
        "cumulative-dose tier flags are checkpoints, not stop signs."
    )

    return IleResult(
        weight_kg=weight_kg,
        species=inputs.species,
        bolus_volume_ml=bolus_volume,
        bolus_duration_min_low=BOLUS_DURATION_MIN_LOW,
        bolus_duration_min_high=BOLUS_DURATION_MIN_HIGH,
        fast_standard=fast_standard,
        fast_extended=fast_extended,
        slow_conservative=slow_conservative,
        rebolus_volume_ml=rebolus_volume,
        cumulative_guideline_ml_per_kg=CUMULATIVE_GUIDELINE_ML_PER_KG,
        cumulative_high_ml_per_kg=CUMULATIVE_HIGH_ML_PER_KG,
        warnings=warnings,
        notes=notes,
        sources=ILE_SOURCES,
        valid=True,
    )
