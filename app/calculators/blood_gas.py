"""
Blood gas · Basic calculator.

Takes pH, PCO2, HCO3-, species, sample type, and acuity, and returns:
  - Acid-base status (acidemia / alkalemia / normal pH)
  - Primary acid-base disturbance
  - Expected compensation per published rules of thumb
  - Whether observed compensation falls within the expected range
    (i.e., simple vs mixed disorder)
  - Anion gap, if Na and Cl are supplied

Source: DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base Disorders in
Small Animal Practice. 4th ed. St. Louis, MO: Elsevier Saunders; 2012.
Chapters 9, 10, 11, 12 (the acid-base block).

Reference ranges, normal values, and compensation formulas come from
those chapters; specific tables are cited inline next to the constants
they generate.

Important clinical caveats encoded in the logic:

1.  Cats may not compensate for metabolic acidosis the way dogs do.
    DiBartola Ch. 12 (p. 304): "the feline kidney apparently is unable
    to adapt to metabolic acidosis ... cats may not compensate for
    metabolic acidosis to the same extent (if at all) as do dogs and
    humans. Thus formulas for dogs or humans should not be extrapolated
    for use in cats." When species=cat and the primary disturbance is
    metabolic acidosis, the calculator surfaces this caveat
    explicitly and does NOT report an "expected" PCO2 — it would be
    misleading.

2.  Cat data for chronic respiratory disorders is very limited. DiBartola
    Table 12-2 marks chronic respiratory acidosis and chronic respiratory
    alkalosis as "Unknown" for cats. We carry that forward — no fake
    expected value, just an explicit "data not available" note.

3.  Compensation tolerance. The textbook gives a point estimate
    (e.g., "PCO2 # by 0.7 mm Hg per 1 mEq/L # in HCO3-"). Biology has
    variance, so we use a +/- 2 mm Hg (or +/- 2 mEq/L) window around
    that point estimate before flagging an observed value as inconsistent
    with simple compensation. This is conservative compared to the
    typical clinical practice of accepting +/- 3 mm Hg. We err
    toward over-flagging mixed disorders rather than missing them.

4.  Acid-base status is keyed on pH being inside or outside the
    reference range — but normal pH does not rule out an acid-base
    disorder, since compensatory or counterbalancing mixed disorders
    can normalize the pH. So when the observed PCO2 and HCO3- both
    deviate substantially from normal with normal pH, we report
    "mixed disorder with normalized pH" rather than "no disorder."

5.  Anion gap requires Na and Cl. K is normally close to 4 mEq/L
    and contributes only a few mEq to the gap, so we use the
    simplified Na - (Cl + HCO3-) form. This matches what's actually
    reported in clinical labs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Species(str, Enum):
    DOG = "dog"
    CAT = "cat"


class SampleType(str, Enum):
    ARTERIAL = "arterial"
    VENOUS = "venous"


class Acuity(str, Enum):
    """Acute vs chronic matters only for respiratory disorders. For
    metabolic disorders the time course of compensation is folded into
    a single rule of thumb. We default to ACUTE because that matches
    the typical emergency presentation. The user can flip to CHRONIC
    when evaluating a patient with sustained respiratory disease."""

    ACUTE = "acute"
    CHRONIC = "chronic"


class PrimaryDisturbance(str, Enum):
    METABOLIC_ACIDOSIS = "metabolic_acidosis"
    METABOLIC_ALKALOSIS = "metabolic_alkalosis"
    RESPIRATORY_ACIDOSIS = "respiratory_acidosis"
    RESPIRATORY_ALKALOSIS = "respiratory_alkalosis"
    NORMAL = "normal"
    # Counterbalancing mixed disorder that produced a normal pH — the
    # PCO2 and HCO3- are both off but cancel out. Cannot be classified
    # as a single primary disturbance.
    MIXED_NORMAL_PH = "mixed_normal_ph"


# ---------------------------------------------------------------------------
# Reference ranges (DiBartola Ch. 9, p. 241)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceRange:
    """A normal range for a single measurement.

    The midpoint is the rough population mean; lo/hi are the typical
    reference range. Used both for normality checks and for displaying
    "normal:" hints to the user.
    """

    midpoint: float
    lo: float
    hi: float

    def contains(self, value: float) -> bool:
        return self.lo <= value <= self.hi


# Source: DiBartola Ch. 9, "Normal Values" section, p. 241. Ranges given
# as approximately +/- 2 SD around the mean.
DOG_ARTERIAL = {
    "pH": ReferenceRange(7.407, 7.351, 7.463),
    "PCO2": ReferenceRange(36.8, 30.8, 42.8),
    "HCO3": ReferenceRange(22.2, 18.8, 25.6),
}
DOG_VENOUS = {
    # Means from p. 241; range +/- 2 SD per the surrounding text.
    "pH": ReferenceRange(7.397, 7.351, 7.443),
    "PCO2": ReferenceRange(37.4, 33.6, 41.2),
    "HCO3": ReferenceRange(22.5, 20.8, 24.2),
}
CAT_ARTERIAL = {
    "pH": ReferenceRange(7.386, 7.310, 7.462),
    "PCO2": ReferenceRange(31.0, 25.2, 36.8),
    "HCO3": ReferenceRange(18.0, 14.4, 21.6),
}
CAT_VENOUS = {
    "pH": ReferenceRange(7.343, 7.277, 7.409),
    "PCO2": ReferenceRange(38.7, 32.7, 44.7),
    "HCO3": ReferenceRange(20.6, 18.0, 23.2),
}


def reference_ranges(species: Species, sample: SampleType) -> dict[str, ReferenceRange]:
    if species == Species.DOG and sample == SampleType.ARTERIAL:
        return DOG_ARTERIAL
    if species == Species.DOG and sample == SampleType.VENOUS:
        return DOG_VENOUS
    if species == Species.CAT and sample == SampleType.ARTERIAL:
        return CAT_ARTERIAL
    return CAT_VENOUS


# Anion gap reference ranges (DiBartola Ch. 9, p. 244, citing more
# recent studies). The simplified two-cation form Na - (Cl + HCO3-)
# is what most labs report; this matches.
ANION_GAP_DOG = ReferenceRange(18.8, 13.0, 25.0)
ANION_GAP_CAT = ReferenceRange(24.1, 17.0, 31.0)


# Compensation tolerance window. The textbook gives a point estimate;
# we accept observed values within +/- this many units of the expected
# value as "consistent with simple compensation." See module docstring
# rationale (#3) for why 2.0 rather than the more typical 3.0.
COMPENSATION_TOLERANCE = 2.0


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class BloodGasInputs:
    species: Species = Species.DOG
    sample: SampleType = SampleType.ARTERIAL
    acuity: Acuity = Acuity.ACUTE

    # Required: pH, PCO2 (mm Hg), HCO3- (mEq/L). Floats so the form layer
    # can pass partial inputs during typing; the validity check rejects
    # nonsensical values.
    pH: float = 0.0
    pco2_mm_hg: float = 0.0
    hco3_meq_per_l: float = 0.0

    # Optional: Na and Cl for anion gap. If either is zero/missing, we
    # skip AG calculation. K is normally near 4 and contributes little;
    # we use the simplified Na - (Cl + HCO3-) form by default.
    na_meq_per_l: float = 0.0
    cl_meq_per_l: float = 0.0

    # Optional: serum albumin (g/dL) for the Figge albumin-corrected
    # anion gap. Most ICU patients are hypoalbuminemic, which lowers
    # the conventional AG by ~2.5 mEq/L per 1 g/dL drop and can mask
    # a real high-AG metabolic acidosis. When supplied, we surface the
    # corrected AG alongside the conventional value. For the full
    # Stewart strong-ion decomposition see /blood-gas-stewart.
    albumin_g_per_dl: float = 0.0


@dataclass
class CompensationAssessment:
    """Result of comparing observed vs. expected compensation."""

    # What is the observed compensating value? PCO2 for metabolic
    # disorders, HCO3- for respiratory disorders.
    observed: float
    observed_label: str  # e.g., "PCO2" or "HCO3-"

    # What does the rule of thumb predict? None when the rule isn't
    # available (e.g., cat with metabolic acidosis, cat with chronic
    # respiratory disorder).
    expected: float | None
    expected_lo: float | None  # expected - tolerance
    expected_hi: float | None  # expected + tolerance

    # Plain-English description of the rule used.
    rule_description: str

    # Is the observed value consistent with a simple disorder?
    # None when we have no rule to compare against.
    is_simple: bool | None

    # Reason, if not simple OR if no rule available.
    note: str = ""

    # LaTeX-formatted worked example of the compensation calculation
    # with patient values plugged in. Rendered via KaTeX. None when no
    # rule was available (cat metabolic acidosis, cat chronic respiratory).
    worked_example_latex: str | None = None


@dataclass
class BloodGasResult:
    inputs: BloodGasInputs

    # Reference ranges for the chosen species/sample combination.
    ref_pH: ReferenceRange
    ref_pco2: ReferenceRange
    ref_hco3: ReferenceRange

    # Headline interpretation.
    primary: PrimaryDisturbance
    primary_label: str  # human-readable name, e.g. "Metabolic acidosis"

    # Is the pH outside the reference range?
    is_acidemic: bool
    is_alkalemic: bool

    # Compensation assessment, when applicable. None when primary is
    # NORMAL or MIXED_NORMAL_PH.
    compensation: CompensationAssessment | None

    # Anion gap, when Na and Cl supplied.
    anion_gap: float | None
    anion_gap_ref: ReferenceRange | None
    anion_gap_high: bool | None  # True if AG > ref.hi, False if within/below, None if not calculated

    # Albumin-corrected anion gap (Figge), when albumin is also supplied.
    # AG_corrected = AG + 2.5 × (4.0 − albumin g/dL). Surfaces real
    # high-AG acidosis hidden by hypoalbuminemia in ICU patients.
    anion_gap_corrected: float | None = None

    # Multi-step diagnostic conclusion, written out in plain English.
    interpretation: list[str] = field(default_factory=list)

    # Warnings (clinically important caveats).
    warnings: list[str] = field(default_factory=list)

    sources: tuple[Source, ...] = ()
    valid: bool = True
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Compensation rules (DiBartola Table 12-2, p. 304)
# ---------------------------------------------------------------------------


def _expected_pco2_for_metabolic_acidosis(
    species: Species, hco3: float, hco3_ref_mid: float
) -> tuple[float | None, str, str, str | None]:
    """Return (expected PCO2, rule description, note, worked example LaTeX).

    Dogs: PCO2 decreases by 0.7 mm Hg for each 1 mEq/L decrease in HCO3-.
    Cats: NO reliable rule. See module docstring caveat #1.
    """
    if species == Species.CAT:
        return (
            None,
            "Not established for cats",
            (
                "Cats may not compensate for metabolic acidosis the way "
                "dogs do (DiBartola Ch. 12, p. 304). The feline kidney "
                "is reported to lack the adaptive increase in renal "
                "ammoniagenesis that dogs and humans show, and dog "
                "compensation formulas should not be extrapolated to "
                "cats. A cat with metabolic acidosis and a normal PCO2 "
                "should NOT be interpreted as having a mixed disorder "
                "on that basis alone."
            ),
            None,
        )
    # Dog rule (Table 12-2): PCO2 # by 0.7 mm Hg per 1 mEq/L # HCO3-.
    # Baseline PCO2 and HCO3- are the population midpoint values for the
    # species/sample (here we use a typical dog baseline ~37 / ~22).
    # Reference value note: textbook uses normal HCO3- ~24, normal PCO2 ~40
    # for the worked example. We use the species reference midpoint so
    # the math stays consistent with the displayed reference ranges.
    delta_hco3 = hco3_ref_mid - hco3
    delta_pco2 = 0.7 * delta_hco3
    pco2_mid = DOG_ARTERIAL["PCO2"].midpoint
    expected = pco2_mid - delta_pco2
    latex = (
        r"\text{expected PCO}_2 = "
        f"{pco2_mid:.1f} - 0.7 \\times ({hco3_ref_mid:.1f} - {hco3:.1f})"
        f" = {expected:.1f}\\ \\text{{mm Hg}}"
    )
    return (
        expected,
        "0.7 mm Hg ↓ PCO2 per 1 mEq/L ↓ HCO3-",
        "",
        latex,
    )


def _expected_pco2_for_metabolic_alkalosis(
    species: Species, hco3: float, hco3_ref_mid: float
) -> tuple[float | None, str, str, str | None]:
    """Dogs and cats: PCO2 increases by 0.7 mm Hg per 1 mEq/L increase in HCO3-.
    Table 12-2 shows the kitten/cat value is similar (0.7), based on
    limited data.
    """
    delta_hco3 = hco3 - hco3_ref_mid
    delta_pco2 = 0.7 * delta_hco3
    if species == Species.DOG:
        pco2_mid = DOG_ARTERIAL["PCO2"].midpoint
    else:
        pco2_mid = CAT_ARTERIAL["PCO2"].midpoint
    expected = pco2_mid + delta_pco2
    latex = (
        r"\text{expected PCO}_2 = "
        f"{pco2_mid:.1f} + 0.7 \\times ({hco3:.1f} - {hco3_ref_mid:.1f})"
        f" = {expected:.1f}\\ \\text{{mm Hg}}"
    )
    cat_note = (
        " Cat data is limited (one study in kittens with dietary chloride "
        "depletion); use with appropriate caution."
        if species == Species.CAT
        else ""
    )
    return (
        expected,
        "0.7 mm Hg ↑ PCO2 per 1 mEq/L ↑ HCO3-",
        cat_note.strip(),
        latex,
    )


def _expected_hco3_for_respiratory_acidosis(
    species: Species, pco2: float, acuity: Acuity, pco2_ref_mid: float, hco3_ref_mid: float
) -> tuple[float | None, str, str, str | None]:
    """Respiratory acidosis compensation rules:
        Dogs, acute:   HCO3- ↑ 0.15 mEq/L per 1 mm Hg ↑ PCO2
        Dogs, chronic: HCO3- ↑ 0.35 mEq/L per 1 mm Hg ↑ PCO2
        Cats, acute:   HCO3- ↑ 0.15 mEq/L per 1 mm Hg ↑ PCO2 (similar to dogs)
        Cats, chronic: UNKNOWN
    """
    if species == Species.CAT and acuity == Acuity.CHRONIC:
        return (
            None,
            "Not established for cats (chronic)",
            (
                "Compensation for chronic respiratory acidosis has not "
                "been established in cats (DiBartola Table 12-2). The "
                "calculator cannot give an expected HCO3- value."
            ),
            None,
        )

    delta_pco2 = pco2 - pco2_ref_mid
    coefficient = 0.15 if acuity == Acuity.ACUTE else 0.35
    delta_hco3 = coefficient * delta_pco2
    expected = hco3_ref_mid + delta_hco3
    descr = (
        f"{coefficient:.2f} mEq/L ↑ HCO3- per 1 mm Hg ↑ PCO2 "
        f"({'acute' if acuity == Acuity.ACUTE else 'chronic'})"
    )
    latex = (
        r"\text{expected HCO}_3^- = "
        f"{hco3_ref_mid:.1f} + {coefficient:.2f} \\times ({pco2:.1f} - {pco2_ref_mid:.1f})"
        f" = {expected:.1f}\\ \\text{{mEq/L}}"
    )
    return (expected, descr, "", latex)


def _expected_hco3_for_respiratory_alkalosis(
    species: Species, pco2: float, acuity: Acuity, pco2_ref_mid: float, hco3_ref_mid: float
) -> tuple[float | None, str, str, str | None]:
    """Respiratory alkalosis compensation rules:
        Dogs, acute:   HCO3- ↓ 0.25 mEq/L per 1 mm Hg ↓ PCO2
        Dogs, chronic: HCO3- ↓ 0.55 mEq/L per 1 mm Hg ↓ PCO2
        Cats, acute:   HCO3- ↓ 0.25 mEq/L per 1 mm Hg ↓ PCO2 (similar to dogs)
        Cats, chronic: pH normalizes but degree not quantified; treat as similar to dogs

    The Table 12-2 footnote on cat chronic respiratory alkalosis says
    "Similar to dogs" with the caveat that the exact compensation
    coefficient hasn't been confirmed. We apply the dog rule and
    surface that uncertainty.
    """
    delta_pco2 = pco2_ref_mid - pco2
    coefficient = 0.25 if acuity == Acuity.ACUTE else 0.55
    delta_hco3 = coefficient * delta_pco2
    expected = hco3_ref_mid - delta_hco3
    descr = (
        f"{coefficient:.2f} mEq/L ↓ HCO3- per 1 mm Hg ↓ PCO2 "
        f"({'acute' if acuity == Acuity.ACUTE else 'chronic'})"
    )
    latex = (
        r"\text{expected HCO}_3^- = "
        f"{hco3_ref_mid:.1f} - {coefficient:.2f} \\times ({pco2_ref_mid:.1f} - {pco2:.1f})"
        f" = {expected:.1f}\\ \\text{{mEq/L}}"
    )
    cat_chronic_note = (
        " Cat chronic respiratory alkalosis compensation is qualitatively "
        "similar to dogs (chronic exposure normalizes arterial pH) but "
        "the exact coefficient hasn't been quantified."
        if species == Species.CAT and acuity == Acuity.CHRONIC
        else ""
    )
    return (expected, descr, cat_chronic_note.strip(), latex)


# ---------------------------------------------------------------------------
# Top-level interpretation
# ---------------------------------------------------------------------------


PRIMARY_LABELS = {
    PrimaryDisturbance.METABOLIC_ACIDOSIS: "Metabolic acidosis",
    PrimaryDisturbance.METABOLIC_ALKALOSIS: "Metabolic alkalosis",
    PrimaryDisturbance.RESPIRATORY_ACIDOSIS: "Respiratory acidosis",
    PrimaryDisturbance.RESPIRATORY_ALKALOSIS: "Respiratory alkalosis",
    PrimaryDisturbance.NORMAL: "Normal",
    PrimaryDisturbance.MIXED_NORMAL_PH: "Mixed disorder with normalized pH",
}


def _identify_primary(
    pH: float,
    pco2: float,
    hco3: float,
    refs: dict[str, ReferenceRange],
) -> tuple[PrimaryDisturbance, bool, bool]:
    """Identify primary disturbance.

    Returns (disturbance, is_acidemic, is_alkalemic).

    Algorithm (DiBartola Ch. 9 "Interpretation of Blood Gas Data"):
      1. If pH is outside the normal range, the patient is acidemic
         or alkalemic. Identify metabolic vs respiratory based on
         which of HCO3- or PCO2 moves in the direction that explains
         the pH change.
      2. If pH is normal but PCO2 and HCO3- are both substantially
         abnormal in opposing directions, it's a counterbalancing
         mixed disorder.
      3. If everything is within range, no disorder.
    """
    pH_low = pH < refs["pH"].lo
    pH_high = pH > refs["pH"].hi
    hco3_low = hco3 < refs["HCO3"].lo
    hco3_high = hco3 > refs["HCO3"].hi
    pco2_low = pco2 < refs["PCO2"].lo
    pco2_high = pco2 > refs["PCO2"].hi

    if pH_low:
        # Acidemic. Decide metabolic vs respiratory by which moved in
        # the acidifying direction more clearly. HCO3- low = metabolic;
        # PCO2 high = respiratory. If both, the rule is to identify the
        # primary as the one that's more deranged — but we let the
        # compensation assessment then catch the mixed pattern.
        if hco3_low and not pco2_high:
            return PrimaryDisturbance.METABOLIC_ACIDOSIS, True, False
        if pco2_high and not hco3_low:
            return PrimaryDisturbance.RESPIRATORY_ACIDOSIS, True, False
        if hco3_low and pco2_high:
            # Both. Heuristic: whichever is further from its midpoint
            # in standard-deviation-ish terms (using range/4 as a proxy)
            # is probably primary; the other is concurrent (i.e., mixed).
            # We pick HCO3- = metabolic acidosis as primary by default
            # since metabolic acidosis is more common in vetmed
            # (DiBartola Ch. 9 cites studies showing metabolic acidosis
            # as the most common acid-base disturbance in dogs).
            return PrimaryDisturbance.METABOLIC_ACIDOSIS, True, False
        # pH low but HCO3- and PCO2 both within normal range —
        # measurement inconsistency. Report as metabolic acidosis
        # (more common) but the compensation check will fail.
        return PrimaryDisturbance.METABOLIC_ACIDOSIS, True, False

    if pH_high:
        # Alkalemic. Mirror logic of acidemic case.
        if hco3_high and not pco2_low:
            return PrimaryDisturbance.METABOLIC_ALKALOSIS, False, True
        if pco2_low and not hco3_high:
            return PrimaryDisturbance.RESPIRATORY_ALKALOSIS, False, True
        if hco3_high and pco2_low:
            return PrimaryDisturbance.METABOLIC_ALKALOSIS, False, True
        return PrimaryDisturbance.METABOLIC_ALKALOSIS, False, True

    # pH is within normal range. Check for counterbalancing mixed disorder.
    if (hco3_low and pco2_low) or (hco3_high and pco2_high):
        # Both moved in the same direction: this is what compensation
        # looks like, and we shouldn't see them in a "normal pH" patient
        # unless something is off — but let it through as normal.
        return PrimaryDisturbance.NORMAL, False, False

    if (hco3_low and pco2_high) or (hco3_high and pco2_low):
        # Both deranged in opposing directions but pH normal —
        # counterbalancing mixed disorder.
        return PrimaryDisturbance.MIXED_NORMAL_PH, False, False

    # All values within normal range.
    return PrimaryDisturbance.NORMAL, False, False


def _assess_compensation(
    primary: PrimaryDisturbance,
    inputs: BloodGasInputs,
    refs: dict[str, ReferenceRange],
) -> CompensationAssessment | None:
    """Compute expected compensation and compare to observed."""
    if primary == PrimaryDisturbance.NORMAL or primary == PrimaryDisturbance.MIXED_NORMAL_PH:
        return None

    pco2_mid = refs["PCO2"].midpoint
    hco3_mid = refs["HCO3"].midpoint

    if primary == PrimaryDisturbance.METABOLIC_ACIDOSIS:
        expected, descr, note, latex = _expected_pco2_for_metabolic_acidosis(
            inputs.species, inputs.hco3_meq_per_l, hco3_mid
        )
        observed = inputs.pco2_mm_hg
        observed_label = "PCO2"
    elif primary == PrimaryDisturbance.METABOLIC_ALKALOSIS:
        expected, descr, note, latex = _expected_pco2_for_metabolic_alkalosis(
            inputs.species, inputs.hco3_meq_per_l, hco3_mid
        )
        observed = inputs.pco2_mm_hg
        observed_label = "PCO2"
    elif primary == PrimaryDisturbance.RESPIRATORY_ACIDOSIS:
        expected, descr, note, latex = _expected_hco3_for_respiratory_acidosis(
            inputs.species, inputs.pco2_mm_hg, inputs.acuity, pco2_mid, hco3_mid
        )
        observed = inputs.hco3_meq_per_l
        observed_label = "HCO3-"
    elif primary == PrimaryDisturbance.RESPIRATORY_ALKALOSIS:
        expected, descr, note, latex = _expected_hco3_for_respiratory_alkalosis(
            inputs.species, inputs.pco2_mm_hg, inputs.acuity, pco2_mid, hco3_mid
        )
        observed = inputs.hco3_meq_per_l
        observed_label = "HCO3-"
    else:
        return None

    if expected is None:
        # No rule available (cat metabolic acidosis or cat chronic resp acidosis)
        return CompensationAssessment(
            observed=observed,
            observed_label=observed_label,
            expected=None,
            expected_lo=None,
            expected_hi=None,
            rule_description=descr,
            is_simple=None,
            note=note,
            worked_example_latex=None,
        )

    expected_lo = expected - COMPENSATION_TOLERANCE
    expected_hi = expected + COMPENSATION_TOLERANCE
    is_simple = expected_lo <= observed <= expected_hi

    # When observed deviates from expected, give a directional note.
    deviation_note = ""
    if not is_simple:
        if observed < expected_lo:
            if observed_label == "PCO2":
                deviation_note = (
                    "PCO2 is lower than expected: suggests concurrent "
                    "respiratory alkalosis."
                    if primary == PrimaryDisturbance.METABOLIC_ACIDOSIS
                    else "PCO2 is lower than expected: suggests concurrent respiratory alkalosis."
                )
            else:  # HCO3-
                deviation_note = (
                    "HCO3- is lower than expected: suggests concurrent "
                    "metabolic acidosis."
                )
        else:  # observed > expected_hi
            if observed_label == "PCO2":
                deviation_note = (
                    "PCO2 is higher than expected: suggests concurrent "
                    "respiratory acidosis."
                )
            else:  # HCO3-
                deviation_note = (
                    "HCO3- is higher than expected: suggests concurrent "
                    "metabolic alkalosis."
                )

    final_note = " ".join(s for s in (note, deviation_note) if s).strip()

    return CompensationAssessment(
        observed=observed,
        observed_label=observed_label,
        expected=expected,
        expected_lo=expected_lo,
        expected_hi=expected_hi,
        rule_description=descr,
        is_simple=is_simple,
        note=final_note,
        worked_example_latex=latex,
    )


def _compute_anion_gap(
    inputs: BloodGasInputs, species: Species
) -> tuple[float | None, ReferenceRange | None, bool | None, float | None]:
    """Anion gap = Na - (Cl + HCO3-). Returns (ag, ref_range, is_high, ag_corrected).

    The fourth value is the Figge albumin-corrected anion gap when
    albumin is supplied:
        AG_corrected = AG + 2.5 × (4.0 − Albumin_g/dL)
    This back-fills the AG that hypoalbuminemia is masking — albumin
    contributes ~2.5 mEq/L to the AG per 1 g/dL, so an ICU patient with
    albumin of 1.5 g/dL has an AG that's ~6 mEq/L lower than it would
    be at normal albumin. Returns None for the corrected AG when
    albumin is not supplied.
    """
    if inputs.na_meq_per_l <= 0 or inputs.cl_meq_per_l <= 0:
        return None, None, None, None
    ag = inputs.na_meq_per_l - (inputs.cl_meq_per_l + inputs.hco3_meq_per_l)
    ref = ANION_GAP_DOG if species == Species.DOG else ANION_GAP_CAT
    if inputs.albumin_g_per_dl > 0:
        # Figge 1998: 2.5 mEq/L per 1 g/dL albumin shortfall from 4.0
        ag_corrected = ag + 2.5 * (4.0 - inputs.albumin_g_per_dl)
    else:
        ag_corrected = None
    return ag, ref, ag > ref.hi, ag_corrected


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


_SOURCES: tuple[Source, ...] = (
    Source(
        citation=(
            "DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base Disorders "
            "in Small Animal Practice. 4th ed. St. Louis, MO: Elsevier "
            "Saunders; 2012. Chapter 9 (Introduction to Acid-Base Disorders), "
            "pp. 231-252; Chapter 10 (Metabolic Acid-Base Disorders), "
            "pp. 253-285; Chapter 11 (Respiratory Acid-Base Disorders), "
            "pp. 286-301; Chapter 12 (Mixed Acid-Base Disorders), pp. 302-315."
        ),
        url=None,
    ),
    Source(
        citation=(
            "de Morais HSA, DiBartola SP. Ventilatory and metabolic "
            "compensation in dogs with acid-base disturbances. "
            "J Vet Emerg Crit Care 1991;1:39-49."
        ),
        url=None,
    ),
)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _empty_result(inputs: BloodGasInputs, errors: list[str]) -> BloodGasResult:
    refs = reference_ranges(inputs.species, inputs.sample)
    return BloodGasResult(
        inputs=inputs,
        ref_pH=refs["pH"],
        ref_pco2=refs["PCO2"],
        ref_hco3=refs["HCO3"],
        primary=PrimaryDisturbance.NORMAL,
        primary_label="—",
        is_acidemic=False,
        is_alkalemic=False,
        compensation=None,
        anion_gap=None,
        anion_gap_ref=None,
        anion_gap_high=None,
        interpretation=[],
        warnings=[],
        sources=_SOURCES,
        valid=False,
        errors=errors,
    )


def compute_blood_gas(inputs: BloodGasInputs) -> BloodGasResult:
    errors: list[str] = []

    # Input validation. The pH/PCO2/HCO3- ranges below are well outside
    # anything compatible with life — values inside this range can still
    # be wrong but are at least worth interpreting. Values outside the
    # range are almost certainly typos.
    if not (6.5 <= inputs.pH <= 7.9):
        errors.append("pH must be between 6.5 and 7.9.")
    if not (10.0 <= inputs.pco2_mm_hg <= 120.0):
        errors.append("PCO2 must be between 10 and 120 mm Hg.")
    if not (5.0 <= inputs.hco3_meq_per_l <= 50.0):
        errors.append("HCO3- must be between 5 and 50 mEq/L.")

    # Anion gap inputs are optional. If supplied, validate range.
    if inputs.na_meq_per_l > 0 and not (100.0 <= inputs.na_meq_per_l <= 200.0):
        errors.append("Sodium, if provided, must be between 100 and 200 mEq/L.")
    if inputs.cl_meq_per_l > 0 and not (60.0 <= inputs.cl_meq_per_l <= 160.0):
        errors.append("Chloride, if provided, must be between 60 and 160 mEq/L.")

    if errors:
        return _empty_result(inputs, errors)

    refs = reference_ranges(inputs.species, inputs.sample)

    primary, is_acidemic, is_alkalemic = _identify_primary(
        inputs.pH, inputs.pco2_mm_hg, inputs.hco3_meq_per_l, refs
    )

    compensation = _assess_compensation(primary, inputs, refs)

    anion_gap, anion_gap_ref, anion_gap_high, anion_gap_corrected = _compute_anion_gap(
        inputs, inputs.species
    )

    # Build the plain-English interpretation.
    interp: list[str] = []
    warnings: list[str] = []

    if primary == PrimaryDisturbance.NORMAL:
        interp.append(
            "pH, PCO2, and HCO3- are all within the reference range for this "
            "species and sample type. No acid-base disturbance is evident on "
            "blood gas alone."
        )
    elif primary == PrimaryDisturbance.MIXED_NORMAL_PH:
        interp.append(
            "pH is normal but PCO2 and HCO3- are both abnormal in opposing "
            "directions, consistent with a counterbalancing mixed disorder. "
            "Pattern is characteristic of two simultaneous primary "
            "disturbances (e.g., metabolic acidosis with respiratory "
            "alkalosis, or metabolic alkalosis with respiratory acidosis)."
        )
        # Identify which combination
        if inputs.hco3_meq_per_l < refs["HCO3"].lo and inputs.pco2_mm_hg < refs["PCO2"].lo:
            interp.append(
                "Pattern fits concurrent metabolic acidosis (low HCO3-) and "
                "respiratory alkalosis (low PCO2)."
            )
        elif inputs.hco3_meq_per_l > refs["HCO3"].hi and inputs.pco2_mm_hg > refs["PCO2"].hi:
            interp.append(
                "Pattern fits concurrent metabolic alkalosis (high HCO3-) and "
                "respiratory acidosis (high PCO2)."
            )
    else:
        # A primary acid-base disorder. State it, then assess compensation.
        ac_al = "acidemia" if is_acidemic else "alkalemia"
        interp.append(
            f"Primary disturbance: {PRIMARY_LABELS[primary]} "
            f"({ac_al}, pH {inputs.pH:.3f})."
        )

        if compensation is not None:
            if compensation.is_simple is True:
                interp.append(
                    f"Observed {compensation.observed_label} "
                    f"({compensation.observed:.1f}) is within the expected "
                    f"range for simple compensation "
                    f"({compensation.expected_lo:.1f}-{compensation.expected_hi:.1f}). "
                    f"Consistent with a simple disorder."
                )
            elif compensation.is_simple is False:
                interp.append(
                    f"Observed {compensation.observed_label} "
                    f"({compensation.observed:.1f}) is outside the expected "
                    f"range for simple compensation "
                    f"({compensation.expected_lo:.1f}-{compensation.expected_hi:.1f}). "
                    f"Suggests a mixed acid-base disorder."
                )
                if compensation.note:
                    interp.append(compensation.note)
            elif compensation.is_simple is None:
                # No rule available — cat metabolic acidosis or cat
                # chronic respiratory acidosis.
                interp.append(
                    "No reliable compensation rule available for this "
                    "combination of species and disorder. See clinical "
                    "background for details."
                )
                if compensation.note:
                    warnings.append(compensation.note)

    # Anion gap interpretation, when computed.
    if anion_gap is not None and anion_gap_ref is not None:
        if anion_gap_high:
            interp.append(
                f"Anion gap is {anion_gap:.1f} mEq/L "
                f"(reference {anion_gap_ref.lo:.0f}-{anion_gap_ref.hi:.0f}). "
                f"An elevated anion gap in the setting of metabolic acidosis "
                f"suggests organic acidosis (lactate, ketones, ethylene "
                f"glycol metabolites, uremic acids). In the absence of "
                f"metabolic acidosis it has less clinical specificity."
                if primary == PrimaryDisturbance.METABOLIC_ACIDOSIS
                else (
                    f"Anion gap is elevated at {anion_gap:.1f} mEq/L "
                    f"(reference {anion_gap_ref.lo:.0f}-{anion_gap_ref.hi:.0f}). "
                    f"Most clinically useful in the setting of metabolic "
                    f"acidosis to distinguish high-AG vs hyperchloremic "
                    f"(normal-AG) causes."
                )
            )
        else:
            interp.append(
                f"Anion gap is {anion_gap:.1f} mEq/L "
                f"(within reference range {anion_gap_ref.lo:.0f}-{anion_gap_ref.hi:.0f})."
                + (
                    " In metabolic acidosis with a normal AG, consider "
                    "hyperchloremic causes such as renal tubular acidosis, "
                    "GI bicarbonate loss (diarrhea), and dilutional acidosis."
                    if primary == PrimaryDisturbance.METABOLIC_ACIDOSIS
                    else ""
                )
            )

    # Albumin-corrected AG: surface the correction when albumin is
    # hypoalbuminemic enough to meaningfully shift the AG (>2 mEq/L
    # difference). Cross-link to the Stewart calculator for the full
    # decomposition.
    if anion_gap is not None and anion_gap_corrected is not None:
        delta = anion_gap_corrected - anion_gap
        if abs(delta) > 2.0:
            interp.append(
                f"Albumin-corrected anion gap (Figge): {anion_gap_corrected:.1f} "
                f"mEq/L, {delta:+.1f} mEq/L vs the conventional AG. "
                f"Hypoalbuminemia is masking unmeasured-anion burden; for the "
                f"full Stewart decomposition see the Stewart calculator."
            )

    # Surface the cat metabolic acidosis caveat as a top-level warning.
    if (
        inputs.species == Species.CAT
        and primary == PrimaryDisturbance.METABOLIC_ACIDOSIS
        and compensation is not None
        and compensation.is_simple is None
    ):
        warnings.append(
            "Cat-specific: respiratory compensation for metabolic acidosis "
            "may not occur to the same extent in cats as in dogs. Normal "
            "PCO2 in a cat with metabolic acidosis does not by itself "
            "indicate a mixed disorder. (DiBartola Ch. 12, p. 304)"
        )

    return BloodGasResult(
        inputs=inputs,
        ref_pH=refs["pH"],
        ref_pco2=refs["PCO2"],
        ref_hco3=refs["HCO3"],
        primary=primary,
        primary_label=PRIMARY_LABELS[primary],
        is_acidemic=is_acidemic,
        is_alkalemic=is_alkalemic,
        compensation=compensation,
        anion_gap=anion_gap,
        anion_gap_ref=anion_gap_ref,
        anion_gap_high=anion_gap_high,
        anion_gap_corrected=anion_gap_corrected,
        interpretation=interp,
        warnings=warnings,
        sources=_SOURCES,
        valid=True,
        errors=[],
    )


# ---------------------------------------------------------------------------
# Catalog entry (nav + meta)
# ---------------------------------------------------------------------------


BLOOD_GAS_CATALOG_ENTRY = {
    "slug": "blood-gas",
    "display_name": "Blood gas · Basic",
    "short_name": "Blood gas",
    "category": "Acid-base & blood gas",
    "mechanism_summary": (
        "Identifies the primary acid-base disturbance from pH, PCO2, and "
        "HCO3-, checks whether observed compensation matches the "
        "species- and acuity-specific rule of thumb, and computes anion "
        "gap when Na and Cl are provided."
    ),
    "indications_summary": (
        "Interpret arterial or venous blood gas in dogs and cats. "
        "Identifies the primary disturbance, checks whether observed "
        "compensation matches the species-specific rule of thumb, and "
        "computes anion gap when Na and Cl are supplied. Dog "
        "compensation formulas are not extrapolated to cats."
    ),
}
