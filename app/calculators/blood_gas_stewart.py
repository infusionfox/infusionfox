"""
Stewart strong-ion approach to blood gas interpretation.

Sibling to app/calculators/blood_gas.py. Where the Henderson-based
calculator interprets pH, PCO2, and HCO3 with the bicarbonate-centric
view, this calculator decomposes the standardized base excess into the
four (or five) physiologic sources Stewart's strong-ion framework
identifies, and surfaces the strong ion gap (SIG) and albumin-corrected
anion gap. The headline clinical payoff is in hypoalbuminemic patients,
where the conventional anion gap is artificially low and the
bicarbonate-only view misses real metabolic disturbance.

Source hierarchy:

  - Hopper K, Haskins SC. A case-based review of a simplified
    quantitative approach to acid-base analysis. J Vet Emerg Crit Care
    2008;18:467-476. (Canonical vet ECC reference for the simplified
    decomposition; the formula coefficients used below come from this
    paper.)
  - Constable PD. Clinical assessment of acid-base status: comparison
    of the Henderson-Hasselbalch and strong ion approaches. Vet Clin
    Pathol 2000;29:115-128. (Foundational comparison; A- formula.)
  - DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in Small
    Animal Practice, 4th ed. St. Louis: Elsevier Saunders; 2012.
    Chapters 9-12. (Species reference ranges; clinical interpretation
    of the BE components.)
  - Stewart PA. Modern quantitative acid-base chemistry. Can J Physiol
    Pharmacol 1983;61:1444-1461. (Original theory.)

Simplified Fencl-Stewart decomposition of standardized base excess:

    BE_total = BE_freewater + BE_chloride + BE_albumin
             + BE_phosphate + BE_lactate + BE_unmeasured

where each component represents one physiologic mechanism contributing
to the patient's acid-base derangement. In a healthy patient every
component should be near zero. Notable contributions identify the
mechanism. A residual BE_unmeasured (after pulling out all the
measured contributors including lactate) flags unmeasured strong
anions — ketones, uremic anions, exogenous toxins.

Sign convention throughout:
  - Positive BE component → alkalinizing effect
  - Negative BE component → acidifying effect
  - BE_total = sum of components (within rounding)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.calculators.blood_gas import Species

# ---------------------------------------------------------------------------
# Species reference values
# ---------------------------------------------------------------------------
#
# Reference midpoints used as the "normal" against which each component
# is computed. These are clinically robust midpoints from DiBartola
# Tables 9-1, 12-1, and the discussion in Ch. 12. Mild lab-to-lab drift
# in reference ranges produces a small constant offset in BE components
# but does not change the clinical interpretation, since what matters
# is the relative size of each component.


@dataclass(frozen=True)
class StewartReference:
    """Species-specific normals used to compute BE components."""

    na_meq_per_l: float
    k_meq_per_l: float
    cl_meq_per_l: float
    hco3_meq_per_l: float
    albumin_g_per_dl: float
    phosphate_mg_per_dl: float
    lactate_mmol_per_l: float


DOG_REFERENCE = StewartReference(
    na_meq_per_l=145.0,  # midpoint of dog reference range 140-150 (DiBartola Table 9-1)
    k_meq_per_l=4.0,
    cl_meq_per_l=110.0,  # dog reference range 110-124 midpoint (DiBartola)
    hco3_meq_per_l=22.0,
    albumin_g_per_dl=3.5,  # dog reference range 2.7-4.4 midpoint (DiBartola)
    phosphate_mg_per_dl=4.5,
    lactate_mmol_per_l=1.5,
)

CAT_REFERENCE = StewartReference(
    na_meq_per_l=152.0,  # cat reference range 147-156 midpoint (DiBartola)
    k_meq_per_l=4.0,
    cl_meq_per_l=121.0,  # cat reference range 117-126 midpoint (DiBartola)
    hco3_meq_per_l=22.0,
    albumin_g_per_dl=3.0,  # cat reference range 2.5-3.5 midpoint
    phosphate_mg_per_dl=4.5,
    lactate_mmol_per_l=1.5,
)


def reference_for(species: Species) -> StewartReference:
    return CAT_REFERENCE if species == Species.CAT else DOG_REFERENCE


# ---------------------------------------------------------------------------
# Inputs / Result
# ---------------------------------------------------------------------------


@dataclass
class StewartInputs:
    species: Species = Species.DOG

    # All numeric defaults are 0.0 ("not entered") rather than physiologic
    # midpoints — the GET page renders an empty form and the placeholder
    # in the result slot. The compute() engine uses internal defaults
    # (pH 7.4 in the SIG calculation, species-normal phosphate when
    # unmeasured) only after the route has validated that the headline
    # inputs are present. See CLAUDE.md non-negotiable #8.
    base_excess: float = 0.0
    pH: float = 0.0
    pco2_mm_hg: float = 0.0
    hco3_meq_per_l: float = 0.0

    # Electrolytes (mEq/L for Na, K, Cl; mmol/L for lactate)
    na_meq_per_l: float = 0.0
    k_meq_per_l: float = 0.0
    cl_meq_per_l: float = 0.0
    lactate_mmol_per_l: float = 0.0

    # Weak acid components
    albumin_g_per_dl: float = 0.0
    phosphate_mg_per_dl: float = 0.0  # often unmeasured; default to species normal


@dataclass(frozen=True)
class BEComponent:
    """One additive contribution to total BE."""

    label: str
    mEq_per_l: float
    explanation: str
    # KaTeX-renderable LaTeX showing the formula with patient values
    # plugged in. None when the component couldn't be calculated
    # (e.g., input not entered) or when the formula doesn't apply
    # (e.g., the unmeasured-anions residual).
    worked_example_latex: str | None = None


@dataclass
class StewartResult:
    inputs: StewartInputs
    reference: StewartReference

    # The BE decomposition — each component is a directional mEq/L
    # contribution that sums (modulo rounding) to the patient's total BE.
    be_total: float = 0.0
    components: list[BEComponent] = field(default_factory=list)

    # Equivalent strong-ion view
    sida: float | None = None  # apparent strong ion difference
    side: float | None = None  # effective strong ion difference
    sig: float | None = None  # SIDa - SIDe; near zero in health

    # Conventional anion gap views
    ag: float | None = None  # conventional Na - (Cl + HCO3)
    ag_corrected: float | None = None  # Figge correction for albumin

    # Clinical interpretation
    headline: str = ""
    interpretation_lines: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Estimation of BE when not provided
# ---------------------------------------------------------------------------
#
# If a user only has HCO3 and PCO2 from a chemistry panel or a basic
# arterial gas, estimate BE via the van Slyke equation rather than
# require manual computation. Most analyzers report BE directly so
# this is a fallback path.


def estimate_base_excess(hco3: float, pco2: float) -> float:
    """van Slyke approximation of standardized base excess.

    BE = HCO3 - 24.4 + 14.83 × (pH - 7.4)
    Rather than ask for pH, derive a sensible BE from HCO3 + PCO2 via:
        BE ~= HCO3 - 24 + (PCO2 - 40) × 0.4 / -1
    For our purposes the rougher form is fine since the user can
    override with the analyzer's reported BE.
    """
    if hco3 <= 0 or pco2 <= 0:
        return 0.0
    return hco3 - 24.0


# ---------------------------------------------------------------------------
# BE component formulas (Hopper & Haskins 2008, simplified Fencl-Stewart)
# ---------------------------------------------------------------------------
#
# Each function returns a directional mEq/L contribution to total BE
# along with a short explanation. The explanations surface in the
# result table next to the numeric contribution.


def _be_freewater(na_pt: float, ref: StewartReference) -> tuple[float, str, str | None]:
    """Free-water (Na) effect on BE.

    Hypernatremia → contraction (water deficit) → alkalinizing.
    Hyponatremia → dilution (water excess) → acidifying.

    Coefficient 0.3 reflects the share of the change in Na concentration
    that translates into a base excess change; magnitude is small unless
    Na is markedly abnormal.
    """
    if na_pt <= 0:
        return 0.0, "Na not entered", None
    be = 0.3 * (na_pt - ref.na_meq_per_l)
    latex = (
        r"\text{BE}_{\text{Na}} = 0.3 \times "
        f"({na_pt:.0f} - {ref.na_meq_per_l:.0f}) = {be:+.1f}\\ \\text{{mEq/L}}"
    )
    if abs(be) < 0.5:
        return be, f"Na {na_pt:.0f} ≈ normal: minimal free-water effect", latex
    direction = "alkalinizing" if be > 0 else "acidifying"
    cause = "hypernatremia (water deficit)" if be > 0 else "hyponatremia (water excess)"
    return be, f"Na {na_pt:.0f} → {cause}, {direction}", latex


def _be_chloride(na_pt: float, cl_pt: float, ref: StewartReference) -> tuple[float, str, str | None]:
    """Chloride effect on BE, corrected for free-water shifts.

        BE_Cl = Cl_normal − (Cl_pt × Na_normal / Na_pt)

    Normalizing Cl by Na/Na_normal isolates the Cl deviation from the
    confounding effect of water shifts (which move Na and Cl together).
    Negative value indicates relative hyperchloremia (acidifying);
    positive indicates relative hypochloremia (alkalinizing).
    """
    if na_pt <= 0 or cl_pt <= 0:
        return 0.0, "Na or Cl not entered", None
    cl_corrected = cl_pt * (ref.na_meq_per_l / na_pt)
    be = ref.cl_meq_per_l - cl_corrected
    latex = (
        r"\text{BE}_{\text{Cl}} = "
        f"{ref.cl_meq_per_l:.0f} - ({cl_pt:.0f} \\times {ref.na_meq_per_l:.0f} \\div {na_pt:.0f})"
        f" = {be:+.1f}\\ \\text{{mEq/L}}"
    )
    if abs(be) < 1.0:
        return be, f"Cl (corrected) {cl_corrected:.0f} ≈ normal", latex
    if be < 0:
        return be, f"Relative hyperchloremia (Cl_corr {cl_corrected:.0f}): acidifying", latex
    return be, f"Relative hypochloremia (Cl_corr {cl_corrected:.0f}): alkalinizing", latex


def _be_albumin(alb_pt: float, ref: StewartReference) -> tuple[float, str, str | None]:
    """Albumin (Atot) effect on BE.

        BE_alb = 3.4 × (Albumin_normal_g/dL − Albumin_pt_g/dL)

    Hypoalbuminemia removes a weak acid → alkalinizing.
    This is the headline clinical correction — in a sick ICU patient
    with albumin 1.5 g/dL, BE_albumin is often +6 to +8 mEq/L, masking
    a metabolic acidosis from unmeasured anions of comparable magnitude.
    """
    if alb_pt <= 0:
        return 0.0, "Albumin not entered", None
    be = 3.4 * (ref.albumin_g_per_dl - alb_pt)
    latex = (
        r"\text{BE}_{\text{alb}} = 3.4 \times "
        f"({ref.albumin_g_per_dl:.1f} - {alb_pt:.1f}) = {be:+.1f}\\ \\text{{mEq/L}}"
    )
    if abs(be) < 0.5:
        return be, f"Albumin {alb_pt:.1f} g/dL ≈ normal", latex
    if be > 0:
        return be, f"Hypoalbuminemia ({alb_pt:.1f} g/dL): alkalinizing", latex
    return be, f"Hyperalbuminemia ({alb_pt:.1f} g/dL): acidifying", latex


def _be_phosphate(phos_pt: float, ref: StewartReference) -> tuple[float, str, str | None]:
    """Phosphate (Atot) effect on BE.

        BE_phos = 0.58 × (Phos_normal_mg/dL − Phos_pt_mg/dL)

    Small contribution in most patients; magnitude becomes meaningful
    in dialysis-naïve uremia, refeeding-syndrome candidates, or
    profound hypophosphatemia. If unmeasured we assume the species
    normal and return 0.
    """
    if phos_pt <= 0:
        return 0.0, "Phosphate not entered (assumed normal)", None
    be = 0.58 * (ref.phosphate_mg_per_dl - phos_pt)
    latex = (
        r"\text{BE}_{\text{phos}} = 0.58 \times "
        f"({ref.phosphate_mg_per_dl:.1f} - {phos_pt:.1f}) = {be:+.1f}\\ \\text{{mEq/L}}"
    )
    if abs(be) < 0.5:
        return be, f"Phosphate {phos_pt:.1f} mg/dL ≈ normal", latex
    if be > 0:
        return be, f"Hypophosphatemia ({phos_pt:.1f}): small alkalinizing effect", latex
    return be, f"Hyperphosphatemia ({phos_pt:.1f}): acidifying", latex


def _be_lactate(lac_pt: float, ref: StewartReference) -> tuple[float, str, str | None]:
    """Lactate effect on BE.

        BE_lactate = −1.0 × (Lactate_pt − Lactate_normal)

    Lactate is a strong anion; elevated lactate is acidifying.
    The −1.0 coefficient reflects that 1 mmol of lactate contributes
    ~1 mEq of negative base excess at a 1:1 ratio.
    """
    if lac_pt <= 0:
        return 0.0, "Lactate not entered", None
    be = -1.0 * (lac_pt - ref.lactate_mmol_per_l)
    latex = (
        r"\text{BE}_{\text{lac}} = -1.0 \times "
        f"({lac_pt:.1f} - {ref.lactate_mmol_per_l:.1f}) = {be:+.1f}\\ \\text{{mEq/L}}"
    )
    if abs(be) < 0.5:
        return be, f"Lactate {lac_pt:.1f} mmol/L ≈ normal", latex
    if be < 0:
        return be, f"Hyperlactatemia ({lac_pt:.1f} mmol/L): acidifying", latex
    return be, f"Sub-normal lactate ({lac_pt:.1f}): small alkalinizing effect", latex


# ---------------------------------------------------------------------------
# Strong ion gap
# ---------------------------------------------------------------------------


def _compute_sig(
    inputs: StewartInputs, ref: StewartReference
) -> tuple[float | None, float | None, float | None]:
    """Return (SIDa, SIDe, SIG) when all required inputs are present.

    SIDa (apparent strong ion difference) — simplified to (Na + K) − (Cl + lactate).
    Ignores Mg²⁺ and ionized Ca²⁺ contributions (small in most patients).

    SIDe (effective strong ion difference) — HCO3 plus the dissociated weak
    acids A⁻ from albumin and phosphate, evaluated at the patient's pH.

        A⁻ = Albumin (g/L) × (0.123 × pH − 0.631)
           + Phosphate (mmol/L) × (0.309 × pH − 0.469)

    SIG = SIDa − SIDe. Should be near zero in health. More negative
    indicates unmeasured strong anions (lactate, ketones, etc.).
    """
    na = inputs.na_meq_per_l
    cl = inputs.cl_meq_per_l
    if na <= 0 or cl <= 0:
        return None, None, None

    k = inputs.k_meq_per_l if inputs.k_meq_per_l > 0 else ref.k_meq_per_l
    lactate = inputs.lactate_mmol_per_l if inputs.lactate_mmol_per_l > 0 else ref.lactate_mmol_per_l
    sida = (na + k) - (cl + lactate)

    if inputs.hco3_meq_per_l <= 0:
        return sida, None, None

    pH = inputs.pH if inputs.pH > 0 else 7.4
    alb_g_l = (inputs.albumin_g_per_dl if inputs.albumin_g_per_dl > 0 else ref.albumin_g_per_dl) * 10.0
    phos_mmol_l = (
        inputs.phosphate_mg_per_dl if inputs.phosphate_mg_per_dl > 0 else ref.phosphate_mg_per_dl
    ) / 3.1
    a_minus = alb_g_l * (0.123 * pH - 0.631) + phos_mmol_l * (0.309 * pH - 0.469)
    side = inputs.hco3_meq_per_l + a_minus
    sig = sida - side
    return sida, side, sig


# ---------------------------------------------------------------------------
# Albumin-corrected anion gap (Figge formula)
# ---------------------------------------------------------------------------


def _compute_ag_views(
    inputs: StewartInputs, ref: StewartReference
) -> tuple[float | None, float | None]:
    """Return (conventional AG, albumin-corrected AG) when computable.

    Conventional AG = Na − (Cl + HCO3) — the standard four-decade clinical
    framing. Albumin-corrected AG adds back the 2.5 mEq/L per g/dL drop
    in albumin (Figge 1998): a hypoalbuminemic patient with conventional
    AG of 12 might have a corrected AG of 18, signaling unmeasured
    anions that the conventional gap missed.
    """
    if inputs.na_meq_per_l <= 0 or inputs.cl_meq_per_l <= 0 or inputs.hco3_meq_per_l <= 0:
        return None, None
    ag = inputs.na_meq_per_l - (inputs.cl_meq_per_l + inputs.hco3_meq_per_l)
    if inputs.albumin_g_per_dl <= 0:
        return ag, None
    ag_corrected = ag + 2.5 * (ref.albumin_g_per_dl - inputs.albumin_g_per_dl)
    return ag, ag_corrected


# ---------------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------------


def _interpret(components: list[BEComponent], sig: float | None) -> tuple[str, list[str], list[str]]:
    """Headline narrative + supporting lines + caveats.

    Headline picks the dominant component(s) by magnitude. Supporting
    lines call out clinically meaningful contributions. Caveats flag
    methodology limitations.
    """
    significant = [c for c in components if abs(c.mEq_per_l) >= 2.0]
    significant.sort(key=lambda c: abs(c.mEq_per_l), reverse=True)

    if not significant:
        headline = "No dominant Stewart contribution. Values are near species normal."
        lines = ["Total BE is small and the decomposition is unrevealing."]
    else:
        dominant = significant[0]
        direction = "alkalinizing" if dominant.mEq_per_l > 0 else "acidifying"
        headline = (
            f"Dominant contributor: {dominant.label} "
            f"({dominant.mEq_per_l:+.1f} mEq/L, {direction})."
        )
        lines = []
        for c in significant:
            sign = "+" if c.mEq_per_l > 0 else ""
            lines.append(f"{c.label}: {sign}{c.mEq_per_l:.1f} mEq/L, {c.explanation}")

    # Unmeasured-anion clinical hint
    unmeasured = next((c for c in components if c.label == "Unmeasured anions"), None)
    if unmeasured and unmeasured.mEq_per_l <= -5.0:
        lines.append(
            "Unmeasured anion burden is substantial after accounting for "
            "lactate. Consider ketosis (β-hydroxybutyrate), uremic anions, "
            "ethylene glycol / methanol, or other exogenous acids."
        )

    caveats = [
        "Coefficients are species-averaged midpoints from DiBartola Tables 9-1 / "
        "12-1; lab-specific reference drift will shift individual components by "
        "a few mEq/L without changing the clinical pattern.",
        "Stewart decomposition assumes the analyzer-reported BE is a "
        "standardized base excess. If the lab reports actual BE only, "
        "compensate accordingly (the difference is small at typical PCO2).",
    ]
    if sig is None:
        caveats.append(
            "Strong ion gap not calculated. Supply Na, K, Cl, HCO3, and "
            "albumin to enable the SID view."
        )
    return headline, lines, caveats


# ---------------------------------------------------------------------------
# Public compute
# ---------------------------------------------------------------------------


def compute(inputs: StewartInputs) -> StewartResult:
    ref = reference_for(inputs.species)

    # Source BE — analyzer-reported, or estimate from HCO3.
    be_total = inputs.base_excess
    if be_total == 0.0 and inputs.hco3_meq_per_l > 0:
        be_total = estimate_base_excess(inputs.hco3_meq_per_l, inputs.pco2_mm_hg)

    # Each contributing component
    fw, fw_expl, fw_latex = _be_freewater(inputs.na_meq_per_l, ref)
    cl, cl_expl, cl_latex = _be_chloride(inputs.na_meq_per_l, inputs.cl_meq_per_l, ref)
    alb, alb_expl, alb_latex = _be_albumin(inputs.albumin_g_per_dl, ref)
    phos, phos_expl, phos_latex = _be_phosphate(inputs.phosphate_mg_per_dl, ref)
    lac, lac_expl, lac_latex = _be_lactate(inputs.lactate_mmol_per_l, ref)

    measured_sum = fw + cl + alb + phos + lac
    unmeasured = be_total - measured_sum

    # Worked example for the residual: total BE minus the sum of the
    # five measured components. Only meaningful when at least one
    # component was actually computed.
    if fw_latex or cl_latex or alb_latex or phos_latex or lac_latex:
        unmeasured_latex = (
            r"\text{BE}_{\text{unmeasured}} = \text{BE}_{\text{total}} - "
            r"(\text{BE}_{\text{Na}} + \text{BE}_{\text{Cl}} + \text{BE}_{\text{alb}} + "
            r"\text{BE}_{\text{phos}} + \text{BE}_{\text{lac}})"
            f" = {be_total:+.1f} - ({fw:+.1f} + {cl:+.1f} + {alb:+.1f} + {phos:+.1f} + {lac:+.1f})"
            f" = {unmeasured:+.1f}\\ \\text{{mEq/L}}"
        )
    else:
        unmeasured_latex = None

    components = [
        BEComponent("Free water (Na)", round(fw, 1), fw_expl, fw_latex),
        BEComponent("Chloride", round(cl, 1), cl_expl, cl_latex),
        BEComponent("Albumin", round(alb, 1), alb_expl, alb_latex),
        BEComponent("Phosphate", round(phos, 1), phos_expl, phos_latex),
        BEComponent("Lactate", round(lac, 1), lac_expl, lac_latex),
        BEComponent(
            "Unmeasured anions",
            round(unmeasured, 1),
            (
                "Residual after accounting for the five measured components. "
                "Negative = ketones, uremic anions, or exogenous acids; "
                "positive (rare) = unmeasured cations or measurement error."
            ),
            unmeasured_latex,
        ),
    ]

    sida, side, sig = _compute_sig(inputs, ref)
    ag, ag_corrected = _compute_ag_views(inputs, ref)
    headline, lines, caveats = _interpret(components, sig)

    return StewartResult(
        inputs=inputs,
        reference=ref,
        be_total=round(be_total, 1),
        components=components,
        sida=round(sida, 1) if sida is not None else None,
        side=round(side, 1) if side is not None else None,
        sig=round(sig, 1) if sig is not None else None,
        ag=round(ag, 1) if ag is not None else None,
        ag_corrected=round(ag_corrected, 1) if ag_corrected is not None else None,
        headline=headline,
        interpretation_lines=lines,
        caveats=caveats,
    )


# ---------------------------------------------------------------------------
# Catalog entry
# ---------------------------------------------------------------------------


BLOOD_GAS_STEWART_CATALOG_ENTRY = {
    "slug": "blood-gas-stewart",
    "display_name": "Blood gas · Stewart approach",
    "short_name": "Stewart",
    "category": "Acid-base & blood gas",
    "kind": "calculator",
    "mechanism_summary": (
        "Stewart strong-ion approach to blood gas interpretation. "
        "Decomposes the patient's standardized base excess into six "
        "physiologic contributors (free water, chloride, albumin, "
        "phosphate, lactate, unmeasured anions), and reports the "
        "strong ion gap and albumin-corrected anion gap. Particularly "
        "useful in hypoalbuminemic ICU patients where the conventional "
        "anion gap is misleadingly low."
    ),
}
