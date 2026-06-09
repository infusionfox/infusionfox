"""
MLK (Morphine-Lidocaine-Ketamine) infusion. Step-by-step bag builder.

Source: Lukasik V. 2015. Constant Rate Infusions in Small Animal Anesthesia:
A Guide to the Practitioner. World Small Animal Veterinary Association World
Congress Proceedings.

InfusionFox's MLK calculator implements the dose-driven workflow: the clinician
picks the per-drug target doses and the pump rate, and the calculator works
out how much of each drug to add to the bag so the bag, run at the chosen
rate, delivers the chosen doses.

This is the reverse direction of a fixed-recipe calculator (e.g. the
older Silverstein recipe: 10 / 150 / 30 mg in 500 mL at 10 mL/kg/hr).
The Silverstein math is internally consistent, but 10 mL/kg/hr is
roughly 3–5× a standard maintenance fluid rate and so isn't how the
recipe is actually run clinically. Most practices either run a
concentrated bag at 1–2 mL/kg/hr or piggyback MLK as a dedicated
analgesic CRI separate from maintenance fluids. The dose-driven approach
in this calculator handles both by letting the user pick doses, then
computing the bag recipe to match.

Dog-only by published protocol. Cats are uniquely sensitive to lidocaine
cardiotoxicity (Plumb's lidocaine monograph documents arrhythmia/CNS
toxicity at doses well below the MLK lidocaine target of 1.5 mg/kg/hr),
so the species selector is locked to dog.

Per-drug published dose ranges (Lukasik 2015):
    Morphine:  0.1–0.4 mg/kg/hr  (mid-range 0.2)
    Lidocaine: 1.0–2.0 mg/kg/hr  (mid-range 1.5; dogs only)
    Ketamine:  0.12–0.6 mg/kg/hr (mid-range 0.3)

Default stock concentrations:
    Morphine:  5  mg/mL (vials are commonly 5 or 15 mg/mL; 5 is default)
    Lidocaine: 20 mg/mL (2 % is the surgical/CRI stock; not the cardiac
               1 % or 4 % stocks — practice double-checks the label)
    Ketamine:  100 mg/mL (standard veterinary stock)

Pump rate is user-selectable; 1 mL/kg/hr is default. At 1 mL/kg/hr the
bag is run as a dedicated CRI not as maintenance fluids — the patient
should be assessed for separate fluid needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Published per-drug dose ranges (mg/kg/hr).
DOSE_RANGE_MORPHINE = (0.1, 0.4)
DOSE_RANGE_LIDOCAINE = (1.0, 2.0)
DOSE_RANGE_KETAMINE = (0.12, 0.6)

# Mid-range defaults from the Lukasik published ranges.
DEFAULT_DOSE_MORPHINE = 0.2
DEFAULT_DOSE_LIDOCAINE = 1.5
DEFAULT_DOSE_KETAMINE = 0.3

# Default stock concentrations (mg/mL).
DEFAULT_STOCK_MORPHINE = 5.0
DEFAULT_STOCK_LIDOCAINE = 20.0  # 2% lidocaine
DEFAULT_STOCK_KETAMINE = 100.0

# Default bag size and pump rate.
DEFAULT_BAG_VOLUME_ML = 500.0
DEFAULT_PUMP_RATE_ML_PER_KG_PER_HR = 1.0

# US DEA controlled-substance scheduling for each component. Morphine is
# Schedule II, ketamine is Schedule III; both require controlled-drug log
# entries when wasted. Lidocaine is not a controlled substance. A value
# of None means the drug is not federally scheduled. (State scheduling can
# differ; the waste section notes this.)
CONTROLLED_SCHEDULE = {
    "Morphine": "C-II",
    "Lidocaine": None,
    "Ketamine": "C-III",
}


class MlkSpecies(str, Enum):
    """MLK is dog-only by published protocol (lidocaine cardiotoxicity in cats)."""

    DOG = "dog"


@dataclass
class MlkInputs:
    weight_value: float
    weight_unit: WeightUnit
    pump_rate_ml_per_kg_per_hr: float = DEFAULT_PUMP_RATE_ML_PER_KG_PER_HR
    bag_volume_ml: float = DEFAULT_BAG_VOLUME_ML
    morphine_dose_mg_per_kg_per_hr: float = DEFAULT_DOSE_MORPHINE
    lidocaine_dose_mg_per_kg_per_hr: float = DEFAULT_DOSE_LIDOCAINE
    ketamine_dose_mg_per_kg_per_hr: float = DEFAULT_DOSE_KETAMINE
    morphine_stock_mg_per_ml: float = DEFAULT_STOCK_MORPHINE
    lidocaine_stock_mg_per_ml: float = DEFAULT_STOCK_LIDOCAINE
    ketamine_stock_mg_per_ml: float = DEFAULT_STOCK_KETAMINE
    species: MlkSpecies = MlkSpecies.DOG


@dataclass
class MlkComponent:
    """One drug component of the MLK CRI, with the math broken into the
    discrete steps used to build a bag from a target dose."""

    name: str
    dose_mg_per_kg_per_hr: float
    stock_mg_per_ml: float
    hourly_mg: float          # dose × weight  (mg/hr)
    total_mg_in_bag: float    # hourly × bag duration (mg)
    volume_ml_to_add: float   # total mg ÷ stock (mL)
    dose_range_low: float
    dose_range_high: float
    in_range: bool
    # Controlled-substance status. Morphine and ketamine require DEA
    # controlled-drug log entries when wasted; lidocaine does not.
    # `schedule` is the US DEA schedule label for the waste log; None
    # for non-controlled drugs.
    controlled: bool = False
    schedule: str | None = None


@dataclass
class MlkWasteComponent:
    """Per-drug waste for the controlled-drug log. Computed from the bag
    composition and the volume actually administered."""

    name: str
    controlled: bool
    schedule: str | None
    stock_mg_per_ml: float       # carried from MlkComponent, for labelling
    total_mg_in_bag: float       # carried from MlkComponent
    mg_given: float              # total × (volume_given / bag_volume)
    mg_wasted: float             # total × (volume_wasted / bag_volume)
    # Stock-equivalent volumes: the mL of undiluted stock that the given /
    # wasted mg corresponds to (mg ÷ stock concentration). Informational —
    # the physical waste is the diluted bag remainder, not undiluted stock
    # — but some controlled-drug logs record the stock-equivalent volume
    # alongside the mg, so both are surfaced.
    stock_ml_given: float        # mg_given ÷ stock concentration
    stock_ml_wasted: float       # mg_wasted ÷ stock concentration


@dataclass
class MlkWasteResult:
    bag_volume_ml: float
    volume_given_ml: float
    volume_wasted_ml: float
    components: list[MlkWasteComponent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    valid: bool = True


@dataclass
class MlkResult:
    weight_kg: float
    pump_rate_ml_per_kg_per_hr: float
    pump_rate_ml_per_hr: float        # weight × per-kg rate
    bag_volume_ml: float
    bag_duration_hr: float            # bag mL ÷ pump mL/hr
    components: list[MlkComponent] = field(default_factory=list)
    total_drug_volume_ml: float = 0.0  # sum of component volumes
    saline_to_remove_ml: float = 0.0   # equals total drug volume
    warnings: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()
    valid: bool = True


def _to_kg(value: float, unit: WeightUnit) -> float:
    return lb_to_kg(value) if unit == WeightUnit.LB else value


def compute_mlk(inputs: MlkInputs) -> MlkResult:
    warnings: list[str] = []

    weight_kg = _to_kg(inputs.weight_value, inputs.weight_unit)
    if weight_kg <= 0:
        return MlkResult(
            weight_kg=weight_kg,
            pump_rate_ml_per_kg_per_hr=inputs.pump_rate_ml_per_kg_per_hr,
            pump_rate_ml_per_hr=0.0,
            bag_volume_ml=inputs.bag_volume_ml,
            bag_duration_hr=0.0,
            components=[],
            warnings=["Weight must be greater than zero."],
            sources=MLK_SOURCES,
            valid=False,
        )

    if inputs.pump_rate_ml_per_kg_per_hr <= 0 or inputs.bag_volume_ml <= 0:
        return MlkResult(
            weight_kg=weight_kg,
            pump_rate_ml_per_kg_per_hr=inputs.pump_rate_ml_per_kg_per_hr,
            pump_rate_ml_per_hr=0.0,
            bag_volume_ml=inputs.bag_volume_ml,
            bag_duration_hr=0.0,
            components=[],
            warnings=["Pump rate and bag volume must both be greater than zero."],
            sources=MLK_SOURCES,
            valid=False,
        )

    pump_rate_ml_per_hr = weight_kg * inputs.pump_rate_ml_per_kg_per_hr
    bag_duration_hr = inputs.bag_volume_ml / pump_rate_ml_per_hr

    def _component(
        name: str,
        dose: float,
        stock: float,
        dose_range: tuple[float, float],
    ) -> MlkComponent:
        if stock <= 0:
            raise ValueError(f"{name} stock concentration must be > 0")
        hourly_mg = dose * weight_kg
        total_mg = hourly_mg * bag_duration_hr
        volume_ml = total_mg / stock
        in_range = dose_range[0] <= dose <= dose_range[1]
        schedule = CONTROLLED_SCHEDULE.get(name)
        return MlkComponent(
            name=name,
            dose_mg_per_kg_per_hr=dose,
            stock_mg_per_ml=stock,
            hourly_mg=round(hourly_mg, 3),
            total_mg_in_bag=round(total_mg, 2),
            volume_ml_to_add=round(volume_ml, 2),
            dose_range_low=dose_range[0],
            dose_range_high=dose_range[1],
            in_range=in_range,
            controlled=schedule is not None,
            schedule=schedule,
        )

    components = [
        _component(
            "Morphine",
            inputs.morphine_dose_mg_per_kg_per_hr,
            inputs.morphine_stock_mg_per_ml,
            DOSE_RANGE_MORPHINE,
        ),
        _component(
            "Lidocaine",
            inputs.lidocaine_dose_mg_per_kg_per_hr,
            inputs.lidocaine_stock_mg_per_ml,
            DOSE_RANGE_LIDOCAINE,
        ),
        _component(
            "Ketamine",
            inputs.ketamine_dose_mg_per_kg_per_hr,
            inputs.ketamine_stock_mg_per_ml,
            DOSE_RANGE_KETAMINE,
        ),
    ]

    for c in components:
        if not c.in_range:
            warnings.append(
                f"{c.name} dose ({c.dose_mg_per_kg_per_hr} mg/kg/hr) is outside "
                f"the published range ({c.dose_range_low}–{c.dose_range_high} "
                "mg/kg/hr). Reassess before proceeding."
            )

    total_drug_volume = sum(c.volume_ml_to_add for c in components)

    if total_drug_volume > inputs.bag_volume_ml * 0.25:
        warnings.append(
            f"Total drug volume ({total_drug_volume:.1f} mL) is more than 25 % of "
            f"the bag ({inputs.bag_volume_ml:.0f} mL). Consider a larger bag or "
            "lower doses/rate to keep drugs as the smaller fraction of the mixture."
        )

    return MlkResult(
        weight_kg=round(weight_kg, 2),
        pump_rate_ml_per_kg_per_hr=inputs.pump_rate_ml_per_kg_per_hr,
        pump_rate_ml_per_hr=round(pump_rate_ml_per_hr, 2),
        bag_volume_ml=inputs.bag_volume_ml,
        bag_duration_hr=round(bag_duration_hr, 2),
        components=components,
        total_drug_volume_ml=round(total_drug_volume, 2),
        saline_to_remove_ml=round(total_drug_volume, 2),
        warnings=warnings,
        sources=MLK_SOURCES,
    )


def compute_mlk_waste(result: MlkResult, volume_given_ml: float) -> MlkWasteResult:
    """Compute per-drug controlled-substance waste from a built MLK bag.

    Given a computed MlkResult (which carries the mg of each drug in the
    bag) and the volume actually administered to the patient, the unused
    portion of the bag contains a proportional fraction of each drug:

        mg wasted = total mg in bag × (volume wasted / bag volume)

    Morphine (C-II) and ketamine (C-III) are controlled and require waste
    log entries; lidocaine is not controlled and is shown for completeness.

    The bag must be a valid computed result. volume_given_ml is what the
    clinician records as actually infused; anything from 0 up to the full
    bag volume is accepted. A volume above the bag volume is invalid (you
    can't give more than the bag holds).
    """
    bag_volume = result.bag_volume_ml

    if not result.valid:
        return MlkWasteResult(
            bag_volume_ml=bag_volume,
            volume_given_ml=volume_given_ml,
            volume_wasted_ml=0.0,
            components=[],
            warnings=["Build a valid MLK bag before computing waste."],
            valid=False,
        )

    if volume_given_ml < 0:
        return MlkWasteResult(
            bag_volume_ml=bag_volume,
            volume_given_ml=volume_given_ml,
            volume_wasted_ml=0.0,
            components=[],
            warnings=["Volume given cannot be negative."],
            valid=False,
        )

    if volume_given_ml > bag_volume:
        return MlkWasteResult(
            bag_volume_ml=bag_volume,
            volume_given_ml=volume_given_ml,
            volume_wasted_ml=0.0,
            components=[],
            warnings=[
                f"Volume given ({volume_given_ml:g} mL) exceeds the bag volume "
                f"({bag_volume:g} mL). Check the recorded volume."
            ],
            valid=False,
        )

    volume_wasted = bag_volume - volume_given_ml
    wasted_fraction = volume_wasted / bag_volume
    given_fraction = volume_given_ml / bag_volume

    waste_components: list[MlkWasteComponent] = []
    for c in result.components:
        mg_given = c.total_mg_in_bag * given_fraction
        mg_wasted = c.total_mg_in_bag * wasted_fraction
        # Stock-equivalent volumes: the mL of undiluted stock the given /
        # wasted mg corresponds to. The physical waste is the diluted bag
        # remainder, not undiluted stock, but some controlled-drug logs
        # record the stock-equivalent volume alongside the mg.
        stock_ml_given = mg_given / c.stock_mg_per_ml if c.stock_mg_per_ml else 0.0
        stock_ml_wasted = mg_wasted / c.stock_mg_per_ml if c.stock_mg_per_ml else 0.0
        waste_components.append(
            MlkWasteComponent(
                name=c.name,
                controlled=c.controlled,
                schedule=c.schedule,
                stock_mg_per_ml=c.stock_mg_per_ml,
                total_mg_in_bag=c.total_mg_in_bag,
                mg_given=round(mg_given, 3),
                mg_wasted=round(mg_wasted, 3),
                stock_ml_given=round(stock_ml_given, 3),
                stock_ml_wasted=round(stock_ml_wasted, 3),
            )
        )

    return MlkWasteResult(
        bag_volume_ml=bag_volume,
        volume_given_ml=round(volume_given_ml, 2),
        volume_wasted_ml=round(volume_wasted, 2),
        components=waste_components,
        warnings=[],
        valid=True,
    )


MLK_SOURCES = (
    Source(
        citation=(
            "Lukasik V. 2015. Constant Rate Infusions in Small Animal Anesthesia: "
            "A Guide to the Practitioner. World Small Animal Veterinary "
            "Association World Congress Proceedings."
        )
    ),
    Source(
        citation=(
            "Muir WW, Wiese AJ, March PA. Effects of morphine, lidocaine, "
            "ketamine, and morphine-lidocaine-ketamine drug combination on "
            "minimum alveolar concentration in dogs anesthetized with isoflurane. "
            "Am J Vet Res 2003;64:1155–1160. (Foundational MLK CRI study.)"
        )
    ),
    Source(
        citation=(
            "Wang HC, Lin YL, et al. Comparison of the effects of "
            "morphine-lidocaine-ketamine and fentanyl-lidocaine-ketamine "
            "combinations administered as constant rate infusions on "
            "postprocedure rectal temperature in dogs. Am J Vet Res "
            "2020;81:58–65. (Clinical MLK CRI: lidocaine 1 mg/kg/h, ketamine "
            "0.6 mg/kg/h, morphine 0.36 mg/kg/h; note MLK was associated with "
            "more frequent hypothermia than FLK.)"
        )
    ),
    Source(
        citation=(
            "Merck/MSD Veterinary Manual. Canine Morphine-Lidocaine-Ketamine "
            "(MLK) CRI Dose clinical calculator. Tertiary reference for the "
            "canine MLK CRI dosing approach."
        )
    ),
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, morphine, lidocaine, and ketamine "
            "monographs. Dose ranges and species cautions, including the "
            "species-specific avoidance of IV lidocaine in cats."
        )
    ),
)

MLK_CATALOG_ENTRY = {
    "slug": "mlk",
    "display_name": "MLK CRI (Morphine + Lidocaine + Ketamine)",
    "short_name": "MLK",
    "category": "Multi-drug protocols",
    "kind": "multi_drug_protocol",
    "mechanism_summary": (
        "Multimodal analgesic CRI combining a µ-opioid agonist (morphine), "
        "a sodium-channel blocker with antihyperalgesic and prokinetic "
        "properties (lidocaine), and an NMDA receptor antagonist (ketamine). "
        "The three drugs target different pain pathways simultaneously, "
        "reducing the dose required of any single agent and providing "
        "broader-spectrum analgesia than monotherapy."
    ),
    "indications_summary": (
        "Multimodal CRI for moderate-to-severe pain in dogs: perioperative "
        "pain, severe medical pain (pancreatitis, peritonitis), and trauma. "
        "Dog-only because cats are uniquely sensitive to lidocaine "
        "cardiotoxicity at the dose this recipe delivers."
    ),
}
