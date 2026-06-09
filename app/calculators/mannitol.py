"""
Mannitol osmotherapy calculator.

Calculates infusion volume, rate, and (where applicable) maintenance
CRI for indication-specific mannitol therapy in dogs and cats. The
five indications and their dosing follow Plumb's Veterinary Drugs
(current edition):

  Osmotic diuresis (label dose; not FDA-approved)
    1.5–2 g/kg IV over 30 min

  Oliguric acute kidney injury (extra-label)
    0.25–1 g/kg IV over 15–20 min.
    If substantial diuresis occurs, EITHER repeat the bolus q4–6h OR
    start a maintenance CRI at 60–120 mg/kg/hr. Conventional cap
    2 g/kg/day total.

  Acute glaucoma refractory to topical agents (extra-label)
    1–2 g/kg IV over 10–20 min.
    Limit water intake 1–4 hr post-dose.

  Increased intracranial pressure from cerebral edema (extra-label)
    0.5–1 g/kg IV or intraosseously over 15–20 min.
    Repeat boluses typically q6–8h; IV CRI is NOT recommended.

  Adjunctive treatment of uroliths (extra-label)
    0.25–0.5 g/kg IV over 20 min, followed by CRI at 1 mg/kg/min
    (= 60 mg/kg/hr).

Stock concentrations:
  20% mannitol = 200 mg/mL = 0.20 g/mL (most common US vet stock)
  25% mannitol = 250 mg/mL = 0.25 g/mL

Mannitol crystallizes at room temperature and below. Standard practice
is to warm the bag to body temperature before drawing and to administer
through a 0.22 µm in-line filter to catch any micro-crystals. Visible
crystallization is a contraindication to administration until the bag
is fully redissolved by warming.

Cumulative dose caution: doses exceeding ~2 g/kg/24h or sustained use
beyond 5–7 days have been associated with paradoxical worsening of
cerebral edema (reverse osmotic shift) and acute kidney injury
(osmotic nephrosis). The calculator flags single boluses above
2 g/kg.

Math model:
    Bolus:
        total_dose_g = dose_g_per_kg × weight_kg
        volume_ml = total_dose_g / (concentration_percent / 100)
        rate_ml_per_min = volume_ml / duration_min
        rate_ml_per_hr = rate_ml_per_min × 60

    Maintenance CRI (when applicable for the indication):
        concentration_mg_per_ml = concentration_percent × 10
        cri_rate_ml_per_hr = (cri_rate_mg_per_kg_per_hr × weight_kg)
                             / concentration_mg_per_ml
        Both low and high published rates are presented as a range
        when Plumb's gives a range; a single rate is shown when the
        published rate is fixed (e.g., uroliths at 1 mg/kg/min).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source, WeightUnit, lb_to_kg

# Stock concentrations (g/mL)
CONCENTRATION_20_PERCENT_G_PER_ML = 0.20  # 200 mg/mL
CONCENTRATION_25_PERCENT_G_PER_ML = 0.25  # 250 mg/mL

# Cumulative 24-hr dose ceiling (conventional, per Plumb's). Above this,
# paradoxical worsening (cerebral reverse osmotic shift; osmotic
# nephrosis) becomes more concerning.
CUMULATIVE_24H_CEILING_G_PER_KG = 2.0


class MannitolIndication(str, Enum):
    OSMOTIC_DIURESIS = "osmotic_diuresis"
    OLIGURIC_AKI = "oliguric_aki"
    ACUTE_GLAUCOMA = "acute_glaucoma"
    CEREBRAL_EDEMA = "cerebral_edema"
    UROLITHS = "uroliths"


@dataclass(frozen=True)
class IndicationProfile:
    """Per-indication dosing per Plumb's.

    ``cri_rate_low_mg_per_kg_per_hr`` and ``cri_rate_high_mg_per_kg_per_hr``
    are None when the indication has no follow-up CRI. When both are
    equal (uroliths), the published rate is a fixed value rather than a
    range.
    """

    label: str
    dose_low_g_per_kg: float
    dose_high_g_per_kg: float
    dose_default_g_per_kg: float
    duration_default_min: int
    duration_low_min: int
    duration_high_min: int
    repeat_note: str
    monitoring_note: str
    cri_rate_low_mg_per_kg_per_hr: float | None = None
    cri_rate_high_mg_per_kg_per_hr: float | None = None
    cri_note: str = ""


INDICATION_PROFILES: dict[MannitolIndication, IndicationProfile] = {
    MannitolIndication.OSMOTIC_DIURESIS: IndicationProfile(
        label="Osmotic diuresis (label dose)",
        dose_low_g_per_kg=1.5,
        dose_high_g_per_kg=2.0,
        dose_default_g_per_kg=1.5,
        duration_default_min=30,
        duration_low_min=30,
        duration_high_min=30,
        repeat_note=(
            "Single dose; the only labeled indication in Plumb's, "
            "though not FDA-approved for veterinary use."
        ),
        monitoring_note=(
            "Confirm volume status before administration. Monitor urine "
            "output and serum electrolytes; the obligate diuresis can "
            "drive hypokalemia and hyperchloremia in patients without "
            "concurrent maintenance fluids."
        ),
    ),
    MannitolIndication.OLIGURIC_AKI: IndicationProfile(
        label="Oliguric acute kidney injury",
        dose_low_g_per_kg=0.25,
        dose_high_g_per_kg=1.0,
        dose_default_g_per_kg=0.5,
        duration_default_min=20,
        duration_low_min=15,
        duration_high_min=20,
        repeat_note=(
            "If substantial diuresis occurs, EITHER repeat the bolus "
            "every 4–6 hr OR start a maintenance CRI at 60–120 mg/kg/hr "
            "(shown below). Total daily dose conventionally capped at "
            "2 g/kg/day. Do NOT repeat if no measurable urine output "
            "within 1–2 hr; continued mannitol in the anuric patient "
            "produces volume overload and may worsen renal injury "
            "(osmotic nephrosis)."
        ),
        monitoring_note=(
            "Measure urine output via closed collection or weighed pads "
            "before and 1–2 hr after the dose. Target ≥1 mL/kg/hr "
            "response. Watch for pulmonary edema in the volume-naive "
            "patient. Hemodialysis is the next step if mannitol fails "
            "to produce urine."
        ),
        cri_rate_low_mg_per_kg_per_hr=60.0,
        cri_rate_high_mg_per_kg_per_hr=120.0,
        cri_note=(
            "60–120 mg/kg/hr CRI is an alternative to repeated boluses "
            "once diuretic response is established. Do NOT continue "
            "indefinitely; reassess every few hours and watch the "
            "2 g/kg/day cumulative cap. The high end of this range "
            "(120 mg/kg/hr × 24 hr ≈ 2.88 g/kg/day) exceeds the daily "
            "ceiling, so plan a finite infusion window."
        ),
    ),
    MannitolIndication.ACUTE_GLAUCOMA: IndicationProfile(
        label="Acute glaucoma (IOP reduction, refractory to topical agents)",
        dose_low_g_per_kg=1.0,
        dose_high_g_per_kg=2.0,
        dose_default_g_per_kg=1.5,
        duration_default_min=15,
        duration_low_min=10,
        duration_high_min=20,
        repeat_note=(
            "Typically a single dose for IOP reduction before definitive "
            "ophthalmologic intervention. Onset ~30 min, peak ~60 min, "
            "duration 4–6 hr."
        ),
        monitoring_note=(
            "Measure IOP before and 30–60 min after the dose. Limit "
            "water intake for 1–4 hr post-dose to prolong the osmotic "
            "effect. Monitor for volume overload in cardiac patients. "
            "Often combined with topical antiglaucoma therapy."
        ),
    ),
    MannitolIndication.CEREBRAL_EDEMA: IndicationProfile(
        label="Increased ICP / cerebral edema",
        dose_low_g_per_kg=0.5,
        dose_high_g_per_kg=1.0,
        dose_default_g_per_kg=0.5,
        duration_default_min=20,
        duration_low_min=15,
        duration_high_min=20,
        repeat_note=(
            "If required, repeat boluses every 6–8 hr. IV CRI is NOT "
            "recommended for this indication (sustained mannitol "
            "exposure allows the drug to cross a disrupted blood-brain "
            "barrier and pull water back into brain tissue, worsening "
            "edema). Watch the 2 g/kg/day cumulative ceiling. May give "
            "IV or intraosseously."
        ),
        monitoring_note=(
            "Monitor mentation, pupil size and response, serum sodium "
            "and osmolality (target <320 mOsm/kg), and urine output. "
            "Maintain normovolemia; replace fluid losses to prevent "
            "secondary brain insult from hypotension. Hypertonic saline "
            "is the alternative osmotic agent of choice in the "
            "hypovolemic patient."
        ),
    ),
    MannitolIndication.UROLITHS: IndicationProfile(
        label="Adjunctive treatment of uroliths",
        dose_low_g_per_kg=0.25,
        dose_high_g_per_kg=0.5,
        dose_default_g_per_kg=0.25,
        duration_default_min=20,
        duration_low_min=20,
        duration_high_min=20,
        repeat_note=(
            "Loading bolus over 20 min, followed by a maintenance CRI "
            "at 1 mg/kg/min (= 60 mg/kg/hr). The CRI rate is shown "
            "below; calculator computes mL/hr for the chosen "
            "concentration."
        ),
        monitoring_note=(
            "Monitor urine output, hydration status, and serum "
            "electrolytes through the CRI. The sustained osmotic "
            "diuresis can drive hypokalemia and hyperchloremia; "
            "concurrent maintenance fluids are typical."
        ),
        cri_rate_low_mg_per_kg_per_hr=60.0,
        cri_rate_high_mg_per_kg_per_hr=60.0,
        cri_note=(
            "Fixed published rate (1 mg/kg/min = 60 mg/kg/hr). "
            "Continued indefinitely while the urolith protocol is "
            "active; watch cumulative dosing if the infusion runs "
            "longer than ~12 hr (24 hr at 60 mg/kg/hr = 1.44 g/kg, "
            "under the 2 g/kg/day ceiling but approaching it)."
        ),
    ),
}


@dataclass
class MannitolInputs:
    """Form inputs. Defaults are placeholders that produce no result
    until the user enters values (Safety Rule #8)."""

    weight_value: float = 0.0
    weight_unit: WeightUnit = WeightUnit.LB
    indication: MannitolIndication = MannitolIndication.CEREBRAL_EDEMA
    dose_g_per_kg: float = 0.0
    concentration_percent: int = 20  # 20 or 25
    duration_min: int = 0


@dataclass
class MannitolResult:
    inputs: MannitolInputs
    valid: bool
    errors: list[str] = field(default_factory=list)

    # Computed bolus values
    weight_kg: float = 0.0
    total_dose_g: float = 0.0
    concentration_g_per_ml: float = 0.0
    volume_ml: float = 0.0
    rate_ml_per_min: float = 0.0
    rate_ml_per_hr: float = 0.0

    # Computed CRI follow-up (None when not applicable for indication)
    cri_rate_low_ml_per_hr: float | None = None
    cri_rate_high_ml_per_hr: float | None = None

    indication_profile: IndicationProfile | None = None
    dose_within_indication_range: bool = False
    cumulative_dose_warning: bool = False

    interpretation: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


_SOURCES: list[Source] = [
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs. Mannitol monograph "
            "(current edition). Indication-specific dosing for the five "
            "indications encoded here (osmotic diuresis, oliguric AKI "
            "with optional follow-up CRI, acute glaucoma, cerebral "
            "edema/increased ICP, and adjunctive treatment of uroliths "
            "with mandatory follow-up CRI) derives from this monograph."
        ),
    ),
    Source(
        citation=(
            "Silverstein DC, Hopper K, eds. Small Animal Critical Care "
            "Medicine. 4th ed. St. Louis, MO: Elsevier; 2023. Ch. 88 "
            "(Traumatic Brain Injury) for cerebral edema indication and "
            "osmotherapy strategy alongside hypertonic saline. Ch. 117 "
            "(Acute Kidney Injury) for the diuretic-response framing "
            "and contraindication in established anuric AKI."
        ),
    ),
    Source(
        citation=(
            "DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base "
            "Disorders in Small Animal Practice. 4th ed. St. Louis, MO: "
            "Elsevier Saunders; 2012. Ch. 26 (Acute Kidney Injury). "
            "Mechanism of action (osmotic gradient across the renal "
            "tubule), the osmotic nephrosis concern with prolonged or "
            "high cumulative dosing, and serum osmolality monitoring "
            "target (<320 mOsm/kg)."
        ),
    ),
]


def _validate(inputs: MannitolInputs) -> list[str]:
    errors: list[str] = []
    if inputs.weight_value <= 0:
        errors.append("Enter a patient weight.")
    if inputs.dose_g_per_kg <= 0:
        errors.append("Enter a dose in g/kg.")
    if inputs.dose_g_per_kg > 5.0:
        errors.append(
            "Dose exceeds 5 g/kg, which is above any published "
            "indication range. Verify input."
        )
    if inputs.concentration_percent not in (20, 25):
        errors.append("Concentration must be 20% or 25%.")
    if inputs.duration_min <= 0:
        errors.append("Enter an infusion duration in minutes.")
    if inputs.duration_min > 120:
        errors.append(
            "Infusion duration exceeds 120 min. Mannitol bolus "
            "infusions run 10–30 min depending on indication; verify "
            "input."
        )
    return errors


def compute_mannitol(inputs: MannitolInputs) -> MannitolResult:
    errors = _validate(inputs)
    if errors:
        return MannitolResult(
            inputs=inputs, valid=False, errors=errors, sources=_SOURCES
        )

    # Weight conversion
    if inputs.weight_unit == WeightUnit.LB:
        weight_kg = lb_to_kg(inputs.weight_value)
    else:
        weight_kg = inputs.weight_value

    profile = INDICATION_PROFILES[inputs.indication]

    total_dose_g = inputs.dose_g_per_kg * weight_kg
    concentration_g_per_ml = (
        CONCENTRATION_20_PERCENT_G_PER_ML
        if inputs.concentration_percent == 20
        else CONCENTRATION_25_PERCENT_G_PER_ML
    )
    concentration_mg_per_ml = inputs.concentration_percent * 10.0
    volume_ml = total_dose_g / concentration_g_per_ml
    rate_ml_per_min = volume_ml / inputs.duration_min
    rate_ml_per_hr = rate_ml_per_min * 60.0

    # CRI follow-up (when the indication has one).
    cri_low_ml_per_hr: float | None = None
    cri_high_ml_per_hr: float | None = None
    if (
        profile.cri_rate_low_mg_per_kg_per_hr is not None
        and profile.cri_rate_high_mg_per_kg_per_hr is not None
    ):
        cri_low_ml_per_hr = (
            profile.cri_rate_low_mg_per_kg_per_hr * weight_kg
        ) / concentration_mg_per_ml
        cri_high_ml_per_hr = (
            profile.cri_rate_high_mg_per_kg_per_hr * weight_kg
        ) / concentration_mg_per_ml

    dose_within_range = (
        profile.dose_low_g_per_kg <= inputs.dose_g_per_kg <= profile.dose_high_g_per_kg
    )
    cumulative_warning = inputs.dose_g_per_kg > CUMULATIVE_24H_CEILING_G_PER_KG

    interpretation: list[str] = []
    warnings: list[str] = []

    # Indication-specific guidance
    interpretation.append(profile.repeat_note)
    interpretation.append(profile.monitoring_note)

    # Dose-range commentary
    if not dose_within_range:
        if inputs.dose_g_per_kg < profile.dose_low_g_per_kg:
            interpretation.append(
                f"Dose {inputs.dose_g_per_kg:g} g/kg is below the "
                f"published range for this indication "
                f"({profile.dose_low_g_per_kg:g}–{profile.dose_high_g_per_kg:g} g/kg)."
            )
        else:
            interpretation.append(
                f"Dose {inputs.dose_g_per_kg:g} g/kg is above the "
                f"published range for this indication "
                f"({profile.dose_low_g_per_kg:g}–{profile.dose_high_g_per_kg:g} g/kg). "
                f"Verify input."
            )

    # Duration-range commentary
    if not (profile.duration_low_min <= inputs.duration_min <= profile.duration_high_min):
        interpretation.append(
            f"Infusion duration {inputs.duration_min} min is outside the "
            f"typical range for this indication "
            f"({profile.duration_low_min}–{profile.duration_high_min} min). "
            f"Slower infusion is generally safer; faster delivery risks "
            f"hyperosmolality and circulatory overload."
        )

    # Cumulative-dose ceiling
    if cumulative_warning:
        warnings.append(
            f"Single dose {inputs.dose_g_per_kg:g} g/kg exceeds the "
            f"2 g/kg/24h cumulative ceiling. Sustained dosing above "
            f"this threshold has been associated with paradoxical "
            f"worsening of cerebral edema (reverse osmotic shift) and "
            f"acute kidney injury (osmotic nephrosis)."
        )

    # Persistent safety warning, surfaced on every result.
    warnings.append(
        "Mannitol crystallizes at room temperature and below. Warm the "
        "bag to body temperature before drawing, and administer through "
        "a 0.22 µm in-line filter. Do NOT administer if crystals remain "
        "visible after warming. Contraindicated in anuric AKI without "
        "diuretic response, severe heart failure, intracranial "
        "hemorrhage with active bleeding, and severe hyperosmolar "
        "states (serum osmolality >320 mOsm/kg)."
    )

    return MannitolResult(
        inputs=inputs,
        valid=True,
        weight_kg=weight_kg,
        total_dose_g=total_dose_g,
        concentration_g_per_ml=concentration_g_per_ml,
        volume_ml=volume_ml,
        rate_ml_per_min=rate_ml_per_min,
        rate_ml_per_hr=rate_ml_per_hr,
        cri_rate_low_ml_per_hr=cri_low_ml_per_hr,
        cri_rate_high_ml_per_hr=cri_high_ml_per_hr,
        indication_profile=profile,
        dose_within_indication_range=dose_within_range,
        cumulative_dose_warning=cumulative_warning,
        interpretation=interpretation,
        warnings=warnings,
        sources=_SOURCES,
    )


MANNITOL_CATALOG_ENTRY = {
    "slug": "mannitol",
    "display_name": "Mannitol osmotherapy",
    "short_name": "Mannitol",
    "category": "Electrolytes & Fluids",
    "mechanism_summary": (
        "Osmotic agent that draws free water across intact endothelium "
        "into the intravascular space, then is filtered unchanged at "
        "the glomerulus where it generates an osmotic diuresis. Onset "
        "minutes; duration ~4–6 hr."
    ),
    "indications_summary": (
        "Indication-specific bolus and follow-up CRI calculator for "
        "mannitol, aligned with Plumb's: osmotic diuresis, oliguric "
        "acute kidney injury (with optional 60–120 mg/kg/hr maintenance "
        "CRI), acute glaucoma, increased intracranial pressure from "
        "cerebral edema (no CRI), and adjunctive treatment of uroliths "
        "(with fixed 1 mg/kg/min maintenance CRI). Computes total "
        "dose, volume at 20% or 25% concentration, pump rate for the "
        "bolus, and mL/hr for any maintenance CRI. Surfaces the "
        "2 g/kg/24h cumulative ceiling and the crystallization-filter "
        "requirement."
    ),
}
