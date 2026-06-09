"""
Osmolar gap calculator.

Computes serum osmolality from Na, glucose, and BUN (or urea) and
subtracts that calculated value from a measured osmolality to expose
an "osmolar gap" attributable to unmeasured osmotically active
substances. The classic veterinary application is ethylene glycol
toxicosis: glycoaldehyde and its metabolites contribute substantial
osmoles to serum within the first 12 hours of ingestion, producing a
gap that may be measurable before clinical signs are obvious.

Formula (US units, Na in mEq/L, glucose and BUN in mg/dL):
    calculated osm = 2 × Na + glucose/18 + BUN/2.8 [+ ethanol/4.6]

Formula (SI units, Na in mmol/L, glucose and urea in mmol/L):
    calculated osm = 2 × Na + glucose + urea [+ ethanol/4.6]

The conversion constants are molar-mass conversions:
    glucose MW 180 g/mol, dL → L scaling → divide mg/dL by 18 → mmol/L
    BUN: 1 mmol urea = 28 mg BUN (urea has 2 N atoms, atomic mass 14),
    scaling for dL → L gives divide-by-2.8 to convert mg/dL → mmol/L
    ethanol MW 46 g/mol, dL → L scaling → divide mg/dL by 4.6 → mmol/L

The 2× multiplier on Na accounts for the obligate paired anions
(predominantly Cl⁻ and HCO₃⁻) that accompany sodium in plasma; this is
the simplified Edelman / sodium-doubling form. The full sodium-paired
form would also account for K, Ca, and Mg, but those contribute small
and constant amounts and are conventionally omitted.

Osmolar gap = measured osm − calculated osm
    Normal: < 10 mOsm/kg
    Borderline / mild: 10 – 20 mOsm/kg
    Significant: > 20 mOsm/kg (strong suggestion of unmeasured osmole)

Vet-specific notes:
    Ethylene glycol toxicosis is the dominant differential in dogs and
    cats. The gap is highest 1 – 6 hr post-ingestion and falls as the
    parent compound is metabolized; by 12 – 18 hr post-ingestion the
    gap may have closed while metabolic acidosis and renal injury are
    rapidly worsening. A normal gap therefore does not rule out
    ethylene glycol — clinical context and a high index of suspicion
    matter.

    Mannitol therapy raises the gap and is expected; this calculator
    will detect that gap but the clinical context resolves the
    differential.

    Cats have a lower lethal dose of ethylene glycol (~1.4 mL/kg of
    undiluted antifreeze) than dogs (~4.4 mL/kg), narrowing the
    diagnostic window further.

Sources:
    DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base Disorders in
        Small Animal Practice. 4th ed. St. Louis, MO: Elsevier Saunders;
        2012. Ch. 3 (Disorders of Sodium and Water).
    Thrall MA, Grauer GF, Mero KN. Clinicopathologic findings in dogs
        and cats with ethylene glycol intoxication. J Am Vet Med Assoc.
        1984;184(1):37–41.
    Connally HE, Thrall MA, Hamar DW. Safety and efficacy of high-dose
        fomepizole compared with ethanol as therapy for ethylene glycol
        intoxication in cats. J Vet Emerg Crit Care (San Antonio).
        2010;20(2):191–206.
    Rose BD, Post TW. Clinical Physiology of Acid-Base and Electrolyte
        Disorders. 5th ed. New York: McGraw-Hill; 2001. Foundational
        reference for the calculated osmolality formula and the osmolar
        gap concept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source


class GlucoseUnit(str, Enum):
    MG_DL = "mg_dl"
    MMOL_L = "mmol_l"


class BunUnit(str, Enum):
    """BUN reported in mg/dL (US) or urea in mmol/L (SI)."""

    MG_DL = "mg_dl"
    MMOL_L = "mmol_l"


# Gap classification cutoffs (mOsm/kg).
GAP_NORMAL_CEILING = 10.0
GAP_BORDERLINE_CEILING = 20.0


@dataclass
class OsmolarGapInputs:
    """Form inputs. Empty defaults so the form yields no result until
    the user provides Na, glucose, and BUN/urea (Safety Rule #8)."""

    na_meq_per_l: float = 0.0
    glucose_value: float = 0.0
    glucose_unit: GlucoseUnit = GlucoseUnit.MG_DL
    bun_value: float = 0.0
    bun_unit: BunUnit = BunUnit.MG_DL
    measured_osm_mosm_per_kg: float = 0.0  # optional
    ethanol_mg_per_dl: float = 0.0  # optional


@dataclass
class OsmolarGapResult:
    inputs: OsmolarGapInputs
    valid: bool
    errors: list[str] = field(default_factory=list)

    # Computed values
    calculated_osm_mosm_per_kg: float = 0.0
    na_contribution: float = 0.0
    glucose_contribution_mosm: float = 0.0
    bun_contribution_mosm: float = 0.0
    ethanol_contribution_mosm: float = 0.0
    osmolar_gap: float | None = None  # None when measured osm not provided
    gap_classification: str = ""  # "normal", "borderline", "elevated", or ""
    gap_elevated: bool = False

    # Display helpers (normalized values for the formula box)
    glucose_mmol_per_l: float = 0.0
    urea_mmol_per_l: float = 0.0

    interpretation: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


_SOURCES: list[Source] = [
    Source(
        citation=(
            "DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base "
            "Disorders in Small Animal Practice. 4th ed. St. Louis, MO: "
            "Elsevier Saunders; 2012. Ch. 3 (Disorders of Sodium and "
            "Water). Reference range for serum osmolality (290–310 "
            "mOsm/kg in dogs and cats), the calculated-osmolality "
            "formula, and the clinical interpretation of an osmolar gap."
        ),
    ),
    Source(
        citation=(
            "Thrall MA, Grauer GF, Mero KN. Clinicopathologic findings "
            "in dogs and cats with ethylene glycol intoxication. J Am "
            "Vet Med Assoc. 1984;184(1):37–41. Foundational veterinary "
            "study establishing the diagnostic value of an osmolar gap "
            "in suspected ethylene glycol toxicosis, including the "
            "time-dependent narrowing of the gap as parent compound is "
            "metabolized."
        ),
    ),
    Source(
        citation=(
            "Connally HE, Thrall MA, Hamar DW. Safety and efficacy of "
            "high-dose fomepizole compared with ethanol as therapy for "
            "ethylene glycol intoxication in cats. J Vet Emerg Crit "
            "Care (San Antonio). 2010;20(2):191–206. Confirms the "
            "diagnostic role of the osmolar gap in feline ethylene "
            "glycol toxicosis and provides the narrow therapeutic "
            "window for fomepizole intervention."
        ),
    ),
    Source(
        citation=(
            "Rose BD, Post TW. Clinical Physiology of Acid-Base and "
            "Electrolyte Disorders. 5th ed. New York: McGraw-Hill; "
            "2001. Foundational physiology reference for the 2 × Na + "
            "glucose/18 + BUN/2.8 formula and the osmolar gap concept "
            "as applied in human and veterinary medicine."
        ),
    ),
]


def _validate(inputs: OsmolarGapInputs) -> list[str]:
    errors: list[str] = []
    if inputs.na_meq_per_l <= 0:
        errors.append("Enter serum sodium.")
    elif not (100.0 <= inputs.na_meq_per_l <= 200.0):
        errors.append("Sodium must be between 100 and 200 mEq/L.")
    if inputs.glucose_value <= 0:
        errors.append("Enter serum glucose.")
    if inputs.bun_value <= 0:
        errors.append("Enter BUN or urea.")
    if inputs.measured_osm_mosm_per_kg > 0 and not (
        200.0 <= inputs.measured_osm_mosm_per_kg <= 500.0
    ):
        errors.append(
            "Measured osmolality, if provided, must be between 200 and "
            "500 mOsm/kg."
        )
    return errors


def _classify_gap(gap: float) -> tuple[str, bool]:
    """Return (label, is_elevated)."""
    if gap < GAP_NORMAL_CEILING:
        return ("normal", False)
    if gap < GAP_BORDERLINE_CEILING:
        return ("borderline", False)
    return ("elevated", True)


def compute_osmolar_gap(inputs: OsmolarGapInputs) -> OsmolarGapResult:
    errors = _validate(inputs)
    if errors:
        return OsmolarGapResult(
            inputs=inputs, valid=False, errors=errors, sources=_SOURCES
        )

    # Convert glucose to mmol/L
    if inputs.glucose_unit == GlucoseUnit.MG_DL:
        glucose_mmol = inputs.glucose_value / 18.0
    else:
        glucose_mmol = inputs.glucose_value

    # Convert BUN/urea to mmol/L
    if inputs.bun_unit == BunUnit.MG_DL:
        urea_mmol = inputs.bun_value / 2.8
    else:
        urea_mmol = inputs.bun_value

    # Ethanol contribution (if provided, always mg/dL input).
    if inputs.ethanol_mg_per_dl > 0:
        ethanol_mmol = inputs.ethanol_mg_per_dl / 4.6
    else:
        ethanol_mmol = 0.0

    na_contrib = 2.0 * inputs.na_meq_per_l
    calc_osm = na_contrib + glucose_mmol + urea_mmol + ethanol_mmol

    # Osmolar gap only meaningful when measured osm is provided.
    gap: float | None = None
    gap_label = ""
    gap_elevated = False
    if inputs.measured_osm_mosm_per_kg > 0:
        gap = inputs.measured_osm_mosm_per_kg - calc_osm
        gap_label, gap_elevated = _classify_gap(gap)

    interpretation: list[str] = []
    warnings: list[str] = []

    if gap is None:
        interpretation.append(
            f"Calculated osmolality is {calc_osm:.0f} mOsm/kg. Reference "
            f"range for dogs and cats is approximately 290–310 mOsm/kg. "
            f"Enter a measured osmolality (from the lab's serum "
            f"osmometer) to compute the osmolar gap."
        )
    else:
        if gap_label == "normal":
            interpretation.append(
                f"Osmolar gap is {gap:.1f} mOsm/kg (calculated "
                f"{calc_osm:.0f}, measured {inputs.measured_osm_mosm_per_kg:.0f}). "
                f"Within the normal range (<10 mOsm/kg). No unmeasured "
                f"osmotically active substance detected at the time of "
                f"sampling."
            )
            interpretation.append(
                "A normal osmolar gap does NOT rule out ethylene glycol "
                "toxicosis. The gap may close within 12–18 hr of "
                "ingestion as the parent compound is metabolized to "
                "glycolic acid, glyoxylic acid, and oxalate, even as "
                "the patient deteriorates from worsening metabolic "
                "acidosis and renal injury. Anion gap and clinical "
                "context remain primary in late presentations."
            )
        elif gap_label == "borderline":
            interpretation.append(
                f"Osmolar gap is {gap:.1f} mOsm/kg (calculated "
                f"{calc_osm:.0f}, measured {inputs.measured_osm_mosm_per_kg:.0f}). "
                f"Borderline elevation (10–20 mOsm/kg). Possible causes "
                f"include early or late ethylene glycol toxicosis "
                f"(parent compound partially metabolized), mannitol "
                f"therapy in progress, mild measurement variance, or "
                f"early alcoholic ketoacidosis."
            )
        else:  # elevated
            interpretation.append(
                f"Osmolar gap is {gap:.1f} mOsm/kg (calculated "
                f"{calc_osm:.0f}, measured {inputs.measured_osm_mosm_per_kg:.0f}). "
                f"Significantly elevated (>20 mOsm/kg). The most "
                f"clinically urgent differential in dogs and cats is "
                f"ethylene glycol toxicosis, particularly within the "
                f"first 6 hr of ingestion. Other osmotic agents to "
                f"consider: mannitol (therapy in progress), methanol, "
                f"isopropanol, propylene glycol vehicle in IV drugs "
                f"(injectable diazepam, phenobarbital, pentobarbital), "
                f"and IV ethanol if administered as antidote."
            )
            warnings.append(
                "Significant osmolar gap. If ethylene glycol exposure "
                "is plausible from history or differentials, initiate "
                "fomepizole or ethanol antidote therapy promptly; do "
                "not wait for serum ethylene glycol assay results, "
                "which often have hours-to-days turnaround. The "
                "antidote window narrows substantially after 8 hr in "
                "dogs and 3 hr in cats."
            )

    # Mannitol-presence reminder if gap is high AND patient is plausibly
    # on mannitol therapy. We can't detect this from inputs alone, so we
    # surface a generic note in the interpretation list when gap is high.
    if gap is not None and gap_elevated:
        interpretation.append(
            "If the patient is receiving mannitol osmotherapy for "
            "cerebral edema or oliguric AKI, the elevated gap is "
            "expected and corresponds to circulating mannitol. The "
            "clinical context (timing of last dose, indication for "
            "therapy) resolves the differential."
        )

    return OsmolarGapResult(
        inputs=inputs,
        valid=True,
        calculated_osm_mosm_per_kg=calc_osm,
        na_contribution=na_contrib,
        glucose_contribution_mosm=glucose_mmol,
        bun_contribution_mosm=urea_mmol,
        ethanol_contribution_mosm=ethanol_mmol,
        osmolar_gap=gap,
        gap_classification=gap_label,
        gap_elevated=gap_elevated,
        glucose_mmol_per_l=glucose_mmol,
        urea_mmol_per_l=urea_mmol,
        interpretation=interpretation,
        warnings=warnings,
        sources=_SOURCES,
    )


OSMOLAR_GAP_CATALOG_ENTRY = {
    "slug": "osmolar-gap",
    "display_name": "Osmolar gap",
    "short_name": "Osm gap",
    "category": "Acid-base & blood gas",
    "mechanism_summary": (
        "Computes calculated serum osmolality from Na, glucose, and BUN, "
        "then subtracts from a measured osmometer reading to expose "
        "osmotically active substances not accounted for by routine "
        "chemistry — primarily ethylene glycol and its metabolites in "
        "veterinary emergency medicine."
    ),
    "indications_summary": (
        "Diagnostic adjunct in suspected toxicosis (ethylene glycol, "
        "methanol, isopropanol), DKA / HHS workup, and monitoring of "
        "mannitol therapy. Supports both US units (Na mEq/L, glucose "
        "and BUN mg/dL) and SI units (Na mmol/L, glucose and urea "
        "mmol/L). A normal gap does NOT rule out ethylene glycol in "
        "late presentations because the parent compound is metabolized "
        "to organic acids within 12–18 hr; anion gap and clinical "
        "context remain primary in those cases."
    ),
}
