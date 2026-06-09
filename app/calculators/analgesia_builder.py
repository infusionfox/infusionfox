"""
Multi-modal analgesia CRI builder.

This calculator lets the clinician build a multi-modal analgesia CRI
by picking an opioid backbone (fentanyl, morphine, or hydromorphone)
and optionally adding adjuncts (Phase 1: ketamine; Phase 2 will add
lidocaine and dexmedetomidine).

Architecture:

  - Each drug option is an `AnalgesiaDrugSpec` carrying its own dose
    ranges per species, concentration presets, default dose and
    concentration, titration ladder, loading-dose protocols, and any
    species restriction. The specs reuse existing engine dataclasses
    (DoseRange, ConcentrationPreset, LoadingDose) so the builder
    inherits the single-drug CRI machinery: dose-range warnings,
    caution thresholds, loading-dose math.

  - `compute_analgesia` produces an `AnalgesiaResult` containing one
    `AnalgesiaDrugResult` per selected drug. Each per-drug result has
    its own pump rate, formula, titration ladder, warnings, and
    loading doses. The result panel renders them as side-by-side
    cards.

  - Phase 1 is per-drug independent mode only: each drug is its own
    bag/syringe with its own pump rate. Phase 3 will add combined-bag
    mode (one bag with all selected drugs in calculated ratios).

  - The opioid options reuse data from existing `CalculatorConfig`
    instances where they already exist (FENTANYL). Where they don't
    (morphine, hydromorphone, ketamine), the specs carry their own
    data without registering a standalone calculator route. This
    matches the design decision to keep standalone fentanyl and
    methadone but not add new standalones for the other drugs.

  - Lidocaine and dexmedetomidine will land in Phase 2. Lidocaine
    requires species gating (dogs only, cardiotoxicity in cats).
"""

from __future__ import annotations

from dataclasses import dataclass

from .drugs import (
    DEXMEDETOMIDINE,
    FENTANYL,
    MORPHINE,
    LoadingDoseComputation,
    compute_loading_doses,
)
from .engine import (
    ConcentrationPreset,
    DoseRange,
    DoseUnit,
    LoadingDose,
    Source,
    Species,
    WeightUnit,
    lb_to_kg,
)

# ---------------------------------------------------------------------------
# Drug spec — one option in the builder. Lighter than CalculatorConfig
# because the builder doesn't need fields specific to standalone
# rendering (catalog blurb, mechanism summary, target-pump-rate mode
# support, etc.). The fields it does carry are exactly what the
# per-drug compute and per-drug result card need.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalgesiaDrugSpec:
    """One drug option in the analgesia builder.

    The `slug` is used as the stem for form field names: the dose
    field for fentanyl is `dose_fentanyl`, concentration is
    `concentration_fentanyl`, and so on. This avoids collisions when
    multiple drugs share the form.

    `role` is either "opioid" or "adjunct". Opioids are mutually
    exclusive (one selected); adjuncts are independent toggles.

    `species_restriction` is None when both species are allowed, or
    a specific `Species` when only that species is allowed (e.g.,
    Species.DOG for lidocaine in Phase 2). The router refuses to
    compute the drug when species doesn't match.

    `role_caveat` is a one-line note explaining why this drug is in
    the builder — e.g., "Standard ICU opioid for severe pain" for
    fentanyl, "NMDA antagonism for wind-up" for ketamine.
    """

    slug: str
    display_name: str
    role: str  # "opioid" or "adjunct"
    dose_unit: DoseUnit
    default_dose: float
    dose_ranges: dict[Species, DoseRange]
    stock_concentration_ug_per_ml: float
    stock_concentration_display: str
    concentration_presets: tuple[ConcentrationPreset, ...]
    default_concentration_ug_per_ml: float
    titration_ladder: tuple[float, ...]
    loading_doses: tuple[LoadingDose, ...] = ()
    species_restriction: Species | None = None
    role_caveat: str = ""
    dilution_note: str = ""
    # Concrete syringe-pump prep recipe surfaced on the per-drug card
    # in the builder's per-drug-independent mode. The clinician's
    # mental model in this mode is "each drug runs on its own syringe
    # pump" — this string is the prep recipe that produces the
    # default_concentration_ug_per_ml. Plain text, not a structured
    # recipe — kept simple because the goal is reference copy at the
    # bedside, not a parsed object.
    syringe_prep: str = ""
    sources: tuple[Source, ...] = ()


# ---------------------------------------------------------------------------
# Drug specs — Phase 1 set.
#
# Fentanyl reuses the existing FENTANYL CalculatorConfig data so dose
# ranges, loading doses, and concentration presets stay synchronized
# between the standalone /fentanyl page and the builder. The other
# three drugs (morphine, hydromorphone, ketamine) carry their own
# data here; they don't have standalone catalog entries.
# ---------------------------------------------------------------------------


FENTANYL_SPEC = AnalgesiaDrugSpec(
    slug=FENTANYL.slug,
    display_name="Fentanyl",
    role="opioid",
    dose_unit=FENTANYL.dose_unit,
    default_dose=FENTANYL.default_dose,
    dose_ranges=FENTANYL.dose_ranges,
    stock_concentration_ug_per_ml=FENTANYL.stock_concentration_ug_per_ml,
    stock_concentration_display=FENTANYL.stock_concentration_display,
    concentration_presets=FENTANYL.concentration_presets,
    default_concentration_ug_per_ml=FENTANYL.default_concentration_ug_per_ml,
    titration_ladder=FENTANYL.titration_ladder,
    loading_doses=FENTANYL.loading_doses,
    role_caveat=(
        "Standard ICU opioid for severe acute pain. Short half-life, "
        "quickly titratable, predictable cardiopulmonary effects."
    ),
    syringe_prep=(
        "5 mL of 50 µg/mL stock + 45 mL 0.9% NaCl in a 50 mL syringe "
        "→ 5 µg/mL (1:10 dilution). Run via syringe pump."
    ),
    sources=FENTANYL.sources,
)


MORPHINE_SPEC = AnalgesiaDrugSpec(
    slug=MORPHINE.slug,
    display_name="Morphine",
    role="opioid",
    dose_unit=MORPHINE.dose_unit,
    default_dose=MORPHINE.default_dose,
    dose_ranges=MORPHINE.dose_ranges,
    stock_concentration_ug_per_ml=MORPHINE.stock_concentration_ug_per_ml,
    stock_concentration_display=MORPHINE.stock_concentration_display,
    concentration_presets=MORPHINE.concentration_presets,
    default_concentration_ug_per_ml=MORPHINE.default_concentration_ug_per_ml,
    titration_ladder=MORPHINE.titration_ladder,
    loading_doses=MORPHINE.loading_doses,
    role_caveat=(
        "Pure mu-agonist with longer duration than fentanyl. Good choice "
        "for steady analgesia in dogs. Less favored in cats due to "
        "dysphoria."
    ),
    dilution_note=MORPHINE.dilution_note,
    syringe_prep=(
        "1 mL of 5 mg/mL stock + 49 mL 0.9% NaCl in a 50 mL syringe "
        "→ 100 µg/mL (0.1 mg/mL). Run via syringe pump."
    ),
    sources=MORPHINE.sources,
)


HYDROMORPHONE_SPEC = AnalgesiaDrugSpec(
    slug="hydromorphone",
    display_name="Hydromorphone",
    role="opioid",
    dose_unit=DoseUnit.MG_PER_KG_PER_HR,
    default_dose=0.03,  # typical analgesia, from hydromorphone-cri.md
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.02,
            max=0.1,
            caution_threshold=0.05,
            persistent_warning=(
                "Hydromorphone CRI for analgesia in dogs. Pure mu-agonist. "
                "Less histamine release than morphine and minimal nausea. "
                "Dose-dependent respiratory depression, sedation, GI "
                "hypomotility. Sustained CRI above 0.05 mg/kg/hr for "
                ">12 hours may require dose reduction."
            ),
            caution_note=(
                "⚠ Doses above 0.05 mg/kg/hr are anesthesia-context "
                "infusions rather than pure analgesia. Active monitoring "
                "and the option to reduce required if prolonged."
            ),
            note=(
                "Pure analgesia: ~0.03 mg/kg/hr. Combined analgesia + "
                "anesthesia: up to 0.1 mg/kg/hr. Doses above "
                "0.05 mg/kg/hr trigger the anesthesia-context caution."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.01,
            max=0.05,
            caution_threshold=0.03,
            persistent_warning=(
                "Hydromorphone is well-tolerated in cats but carries a "
                "known risk of hyperthermia (central thermoregulatory "
                "disruption, not true fever). Monitor temperature; "
                "discontinue if rectal temperature exceeds 40°C (104°F). "
                "More dysphoria-prone than dogs at standard mu-opioid "
                "doses. Start at the low end."
            ),
            caution_note=(
                "⚠ Cat doses above 0.03 mg/kg/hr increase hyperthermia "
                "and dysphoria risk. Stay at the low end of the range "
                "unless monitoring supports a higher rate."
            ),
            note=(
                "Cat range is more conservative than dog: 0.01–"
                "0.05 mg/kg/hr. Loading dose 0.025 mg/kg IV (vs "
                "0.05–0.1 mg/kg IV in dogs)."
            ),
        ),
    },
    stock_concentration_ug_per_ml=2000.0,  # 2 mg/mL
    stock_concentration_display="2 mg/mL (2000 µg/mL)",
    concentration_presets=(
        ConcentrationPreset(
            40,
            "10 mg (5 mL of 2 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Standard preparation for dogs at typical CRI doses.",
        ),
        ConcentrationPreset(
            20,
            "5 mg (2.5 mL of 2 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Lower concentration for small patients (cats, small dogs) or low-rate infusions.",
        ),
        ConcentrationPreset(
            80,
            "20 mg (10 mL of 2 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "More concentrated for larger dogs or higher CRI rates.",
        ),
    ),
    default_concentration_ug_per_ml=40.0,
    titration_ladder=(0.02, 0.03, 0.04, 0.05, 0.075, 0.1),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI loading dose (dogs)",
            description="0.05–0.1 mg/kg IV before starting the CRI.",
            matches_cri_rate=False,
            display_dose_unit="mg",
            dose_per_kg={
                Species.DOG: (0.05, 0.1),
            },
            note=(
                "Less histamine release than morphine. IV is safer for "
                "the loading dose. Cats: use 0.025 mg/kg IV (single value, "
                "lower than the dog range)."
            ),
        ),
        LoadingDose(
            label="Pre-CRI loading dose (cats)",
            description="0.025 mg/kg IV before starting the CRI.",
            matches_cri_rate=False,
            display_dose_unit="mg",
            dose_per_kg={
                Species.CAT: (0.025, 0.025),
            },
            note=(
                "Cats are more dysphoria- and hyperthermia-prone than "
                "dogs; the loading dose is correspondingly lower. Monitor "
                "rectal temperature."
            ),
        ),
    ),
    role_caveat=(
        "Pure mu-agonist similar to morphine but with less histamine "
        "release and less nausea. Good alternative to morphine when "
        "histamine release is a concern."
    ),
    dilution_note=(
        "Compatible with 0.9% NaCl, 5% dextrose, LRS. 2 mg/mL stock "
        "is standard; 10 mg/mL stock also exists in some formularies."
    ),
    syringe_prep=(
        "1 mL of 2 mg/mL stock + 49 mL 0.9% NaCl in a 50 mL syringe "
        "→ 40 µg/mL (0.04 mg/mL). Run via syringe pump."
    ),
    sources=(
        Source(
            citation=(
                "Plumb DC. Plumb's Veterinary Drugs, hydromorphone "
                "monograph (current edition). Sections used: Dosages "
                "(dogs and cats), Adverse Effects, Compatibility."
            ),
            reviewer=None,
        ),
    ),
)


KETAMINE_SPEC = AnalgesiaDrugSpec(
    slug="ketamine",
    display_name="Ketamine",
    role="adjunct",
    # µg/kg/min is the most common ketamine CRI unit clinically (and the
    # one Plumb's emphasizes for analgesic CRIs). It also avoids the
    # high-alert mg/kg/hr vs µg/kg/min unit-confusion error documented
    # in ketamine's learn module.
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    default_dose=2.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=2.0,
            max=10.0,
            caution_threshold=10.0,
            persistent_warning=(
                "Ketamine CRI as analgesic adjunct. NMDA antagonism "
                "reduces central sensitization and wind-up. Subanesthetic "
                "doses for analgesia run 2–10 µg/kg/min. Surgical-"
                "maintenance/anti-windup intraop doses run 10–20 µg/kg/min "
                "(= 0.6–1.2 mg/kg/hr) and require anesthesia context."
            ),
            caution_note=(
                "⚠ Doses ≥ 10 µg/kg/min are surgical-maintenance "
                "infusions, not standard analgesic CRIs. Use in "
                "anesthesia context with monitoring. The Plumb's MLK "
                "protocol uses 10 µg/kg/min ketamine, which sits at "
                "this threshold."
            ),
            note=(
                "Postsurgical/general analgesia: 2–10 µg/kg/min "
                "(= 0.12–0.6 mg/kg/hr). Default 2 µg/kg/min for 24 hr. "
                "Surgical maintenance: 10–20 µg/kg/min."
            ),
        ),
        Species.CAT: DoseRange(
            min=2.0,
            max=10.0,
            caution_threshold=10.0,
            persistent_warning=(
                "Ketamine CRI in cats is used cautiously. Cats metabolize "
                "ketamine more slowly than dogs (longer half-life), so "
                "accumulation with prolonged CRI is a concern. Watch for "
                "prolonged recovery and dissociation post-CRI."
            ),
            caution_note=(
                "⚠ Doses ≥ 10 µg/kg/min are surgical-maintenance "
                "infusions. Cat accumulation is meaningful. Consider "
                "shorter infusions or lower rates."
            ),
            note=(
                "Cat range mirrors dogs (2–10 µg/kg/min for analgesia), "
                "but cat ketamine half-life is longer. Favor shorter "
                "infusions or lower rates with longer durations."
            ),
        ),
    },
    stock_concentration_ug_per_ml=100000.0,  # 100 mg/mL
    stock_concentration_display="100 mg/mL (100,000 µg/mL)",
    concentration_presets=(
        ConcentrationPreset(
            2000,
            "500 mg (5 mL of 100 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Standard concentration for ketamine CRI across patient sizes.",
        ),
        ConcentrationPreset(
            4000,
            "1000 mg (10 mL of 100 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "More concentrated prep for larger patients or higher-rate infusions.",
        ),
        ConcentrationPreset(
            1000,
            "250 mg (2.5 mL of 100 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Lower concentration for small patients on low rates.",
        ),
    ),
    default_concentration_ug_per_ml=2000.0,
    titration_ladder=(2.0, 4.0, 6.0, 8.0, 10.0),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI loading dose",
            description=(
                "0.5 mg/kg IV before starting the CRI if anesthesia was "
                "induced with a non-ketamine agent."
            ),
            matches_cri_rate=False,
            display_dose_unit="mg",
            dose_per_kg={
                Species.DOG: (0.5, 0.5),
                Species.CAT: (0.5, 0.5),
            },
            note=(
                "Per Plumb's, the loading dose is given before the CRI "
                "when induction did not include ketamine. The MLK "
                "protocol does not require a separate ketamine loading "
                "if ketamine was part of induction."
            ),
        ),
    ),
    role_caveat=(
        "NMDA antagonist. Adds central anti-hyperalgesic effect on top "
        "of the opioid backbone. Useful for chronic, neuropathic, or "
        "wind-up-driven pain. Watch the unit (µg/kg/min vs mg/kg/hr) "
        "carefully; they differ by ≈60×."
    ),
    dilution_note=(
        "Compatible with 0.9% NaCl, 5% dextrose, LRS. 100 mg/mL stock "
        "is the standard veterinary concentration."
    ),
    syringe_prep=(
        "1 mL of 100 mg/mL stock + 49 mL 0.9% NaCl in a 50 mL syringe "
        "→ 2 mg/mL (2000 µg/mL). Run via syringe pump."
    ),
    sources=(
        Source(
            citation=(
                "Plumb DC. Plumb's Veterinary Drugs, ketamine monograph "
                "(current edition). Sections used: Dosages (dogs and "
                "cats), Prescriber Highlights (unit-confusion warning), "
                "Pharmacokinetics."
            ),
            reviewer=None,
        ),
    ),
)


LIDOCAINE_SPEC = AnalgesiaDrugSpec(
    slug="lidocaine",
    display_name="Lidocaine",
    role="adjunct",
    dose_unit=DoseUnit.MG_PER_KG_PER_HR,
    # 1.5 mg/kg/hr (= 25 µg/kg/min) is the MLK protocol default —
    # the multi-modal context (combined with opioid + ketamine)
    # warrants the lower end of the analgesic range. Standalone
    # lidocaine monotherapy defaults higher (2.5 mg/kg/hr) on the
    # /lidocaine page; here the multi-modal context pulls it down.
    default_dose=1.5,
    dose_ranges={
        # Dog-only: cats are uniquely sensitive to lidocaine
        # cardiotoxicity. Plumb's lidocaine monograph documents
        # arrhythmia and CNS toxicity at doses well below the
        # standard analgesic range. The species_restriction below
        # makes this a hard gate in the engine; this dose_ranges
        # entry exists so dog computations still surface the
        # standard analgesic range string for the result panel.
        Species.DOG: DoseRange(
            min=1.5,
            max=3.0,
            caution_threshold=3.0,
            persistent_warning=(
                "Lidocaine CRI for analgesia in dogs. IV sodium-channel "
                "blocker; supraspinal and spinal anti-nociceptive effects. "
                "Used as part of multi-modal analgesia (MLK protocol). "
                "Monitor for bradycardia, hypotension, AV block, and CNS "
                "signs (muscle tremors, nausea, ataxia). Discontinue if "
                "signs appear."
            ),
            caution_note=(
                "⚠ Doses above 3 mg/kg/hr (= 50 µg/kg/min) are surgical/"
                "anti-arrhythmic territory rather than standard analgesia. "
                "Use only with active cardiac monitoring."
            ),
            note=(
                "Standard analgesic range: 1.5–3.0 mg/kg/hr (= 25–"
                "50 µg/kg/min). MLK-protocol default is 1.5 mg/kg/hr."
            ),
        ),
    },
    stock_concentration_ug_per_ml=20000.0,  # 2% (20 mg/mL) WITHOUT epi
    stock_concentration_display="20 mg/mL (2% WITHOUT epinephrine)",
    concentration_presets=(
        ConcentrationPreset(
            4000,
            "1 g (50 mL of 20 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Standard preparation for dogs at typical CRI doses.",
        ),
        ConcentrationPreset(
            2000,
            "500 mg (25 mL of 20 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Lower concentration for small dogs or low-rate infusions.",
        ),
        ConcentrationPreset(
            8000,
            "2 g (100 mL of 20 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "More concentrated for larger dogs or fluid-restricted patients.",
        ),
    ),
    default_concentration_ug_per_ml=4000.0,
    titration_ladder=(1.5, 2.0, 2.5, 3.0),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI loading dose",
            description=(
                "1–2 mg/kg IV slowly over 2–5 minutes before starting the CRI."
            ),
            matches_cri_rate=False,
            display_dose_unit="mg",
            dose_per_kg={
                Species.DOG: (1.0, 2.0),
            },
            note=(
                "Give slowly (2–5 minutes) to avoid acute CNS and "
                "cardiac toxicity from the bolus. Use lidocaine WITHOUT "
                "epinephrine. The epi-containing formulations are for "
                "local infiltration, not IV CRI."
            ),
        ),
    ),
    species_restriction=Species.DOG,
    role_caveat=(
        "IV sodium-channel blocker. Adds supraspinal and spinal anti-"
        "nociception. Dog-only. Cats are uniquely sensitive to "
        "lidocaine cardiotoxicity at standard analgesic doses."
    ),
    dilution_note=(
        "Use 2% lidocaine WITHOUT epinephrine. Compatible with 0.9% "
        "NaCl, 5% dextrose, LRS. The cardiac (1%) and surgical-"
        "infiltration (4%) stocks exist. Verify the label before "
        "drawing."
    ),
    syringe_prep=(
        "10 mL of 20 mg/mL stock (2% WITHOUT epi) + 40 mL 0.9% NaCl "
        "in a 50 mL syringe → 4 mg/mL (4000 µg/mL). Run via syringe "
        "pump. Alternative: run undiluted 20 mg/mL stock at the slower "
        "pump rate."
    ),
    sources=(
        Source(
            citation=(
                "Lukasik V. 2015. Constant Rate Infusions in Small Animal "
                "Anesthesia. WSAVA Proceedings. Plumb DC. Plumb's "
                "Veterinary Drugs, lidocaine monograph (current edition); "
                "sections used: Dosages (dogs), Adverse Effects, "
                "Prescriber Highlights (cat cardiotoxicity)."
            ),
            reviewer=None,
        ),
    ),
)


DEXMEDETOMIDINE_SPEC = AnalgesiaDrugSpec(
    slug=DEXMEDETOMIDINE.slug,
    display_name="Dexmedetomidine",
    role="adjunct",
    dose_unit=DEXMEDETOMIDINE.dose_unit,
    default_dose=DEXMEDETOMIDINE.default_dose,
    dose_ranges=DEXMEDETOMIDINE.dose_ranges,
    stock_concentration_ug_per_ml=DEXMEDETOMIDINE.stock_concentration_ug_per_ml,
    stock_concentration_display=DEXMEDETOMIDINE.stock_concentration_display,
    concentration_presets=DEXMEDETOMIDINE.concentration_presets,
    default_concentration_ug_per_ml=DEXMEDETOMIDINE.default_concentration_ug_per_ml,
    titration_ladder=DEXMEDETOMIDINE.titration_ladder,
    loading_doses=DEXMEDETOMIDINE.loading_doses,
    role_caveat=(
        "α₂-agonist. Adds opioid-sparing analgesia and reduces "
        "ketamine metabolism. Caution: dose-dependent sedation and "
        "bradycardia. DMLK protocol uses 0.5 µg/kg/hr."
    ),
    dilution_note=DEXMEDETOMIDINE.dilution_note,
    syringe_prep=(
        "0.4 mL of 500 µg/mL stock (Dexdomitor) + 49.6 mL 0.9% NaCl "
        "in a 50 mL syringe → 4 µg/mL. Draw the stock with a 1 mL "
        "(tuberculin) syringe for precision. Run via syringe pump."
    ),
    sources=DEXMEDETOMIDINE.sources,
)


# Drug-spec catalog. Phase 2 set — adds lidocaine and dexmedetomidine
# to the Phase 1 ketamine adjunct. The order here is the order they
# appear in the form and in the result panel.
OPIOID_SPECS: tuple[AnalgesiaDrugSpec, ...] = (
    FENTANYL_SPEC,
    MORPHINE_SPEC,
    HYDROMORPHONE_SPEC,
)
ADJUNCT_SPECS: tuple[AnalgesiaDrugSpec, ...] = (
    KETAMINE_SPEC,
    LIDOCAINE_SPEC,
    DEXMEDETOMIDINE_SPEC,
)
ALL_SPECS: tuple[AnalgesiaDrugSpec, ...] = OPIOID_SPECS + ADJUNCT_SPECS
SPEC_BY_SLUG: dict[str, AnalgesiaDrugSpec] = {s.slug: s for s in ALL_SPECS}


def get_spec(slug: str) -> AnalgesiaDrugSpec | None:
    return SPEC_BY_SLUG.get(slug)


# ---------------------------------------------------------------------------
# Inputs and results.
# ---------------------------------------------------------------------------


@dataclass
class AnalgesiaBuilderInputs:
    """Form inputs for the analgesia builder.

    `opioid_slug` names the selected opioid (one of fentanyl, morphine,
    hydromorphone). `adjunct_slugs` lists any toggled-on adjuncts
    (Phase 2: a subset of {ketamine, lidocaine, dexmedetomidine}).

    `doses` and `concentrations_ug_per_ml` are keyed by drug slug so
    the inputs can be extended without changing the shape. The router
    validates that each selected drug has a corresponding entry in
    both dicts when in per-drug mode.

    `prep_mode` controls whether the calculator computes per-drug
    independent pump rates ("per_drug", the historical / Phase 2
    default) or a single combined-bag recipe ("combined_bag", Phase 3).
    In combined-bag mode the per-drug `concentrations_ug_per_ml` are
    ignored; the bag concentrations are derived from doses, weight,
    pump rate, and bag volume. `bag_volume_ml` and
    `shared_pump_rate_ml_per_kg_per_hr` are only consulted in
    combined-bag mode.
    """

    weight_value: float
    weight_unit: WeightUnit
    species: Species
    opioid_slug: str
    adjunct_slugs: tuple[str, ...]
    doses: dict[str, float]
    concentrations_ug_per_ml: dict[str, float]
    # Phase 3 — combined-bag mode parameters.
    prep_mode: str = "per_drug"
    bag_volume_ml: float = 500.0
    shared_pump_rate_ml_per_kg_per_hr: float = 1.0


@dataclass(frozen=True)
class AnalgesiaDrugResult:
    """Per-drug compute result. One per selected drug."""

    spec: AnalgesiaDrugSpec
    dose: float
    concentration_ug_per_ml: float
    total_dose_ug_per_hr: float
    total_dose_ug_per_min: float | None  # only for µg/kg/min drugs
    ml_per_hr_precise: float
    ml_per_hr_pump: float  # rounded to pump precision
    ml_per_kg_per_hr: float
    titration_rates: tuple[tuple[float, float], ...]  # (dose, ml/hr) pairs
    warnings: tuple[str, ...]
    loading_dose_results: tuple[LoadingDoseComputation, ...]
    valid: bool


@dataclass(frozen=True)
class CombinedBagDrugRecipe:
    """One drug's contribution to a combined bag.

    Carries the math the bedside clinician needs to actually prepare
    the bag: how many mL of the stock drug to draw and add, and the
    resulting bag concentration. Loading doses and warnings are
    shared with per-drug-mode rendering — they don't change between
    modes since they're properties of the drug and dose, not the
    delivery vehicle.
    """

    spec: AnalgesiaDrugSpec
    dose: float
    # Total drug needed to fill the bag for one full bag-duration of
    # delivery. Always in the drug's standardised µg unit so the
    # template can format consistently (mg vs µg display).
    total_for_bag_ug: float
    ml_of_stock_to_add: float
    # The resulting drug concentration in the bag after the stock
    # volume is mixed in. Provides a sanity-check value the clinician
    # can compare against single-drug protocols.
    bag_concentration_ug_per_ml: float
    warnings: tuple[str, ...]
    loading_dose_results: tuple[LoadingDoseComputation, ...]


@dataclass(frozen=True)
class CombinedBagResult:
    """Top-level combined-bag recipe.

    The clinician's mental model is: I have a 500 mL bag of LRS, I
    want to run it at 1 mL/kg/hr, and I want it to deliver these
    doses of these drugs. What goes into the bag, and for how many
    hours does this bag run?

    `total_stock_volume_ml` and `adjusted_carrier_ml` together tell
    the clinician how to actually prepare the bag — draw out the
    stock volume from the LRS first if the drug volumes are
    significant, then add the drug stocks. Total bag volume stays at
    `bag_volume_ml` after this adjustment.
    """

    weight_kg: float
    species: Species
    bag_volume_ml: float
    pump_rate_ml_per_kg_per_hr: float
    pump_rate_ml_per_hr: float
    hours_per_bag: float
    drug_recipes: tuple[CombinedBagDrugRecipe, ...]
    total_stock_volume_ml: float
    adjusted_carrier_ml: float
    valid: bool


@dataclass(frozen=True)
class AnalgesiaResult:
    """Top-level result.

    In per-drug mode (`prep_mode == "per_drug"`), `drug_results`
    carries one `AnalgesiaDrugResult` per selected drug and
    `combined_bag` is None.

    In combined-bag mode (`prep_mode == "combined_bag"`),
    `combined_bag` carries the bag recipe and `drug_results` is empty.
    Templates branch on which is populated.
    """

    weight_kg: float
    species: Species
    prep_mode: str
    drug_results: tuple[AnalgesiaDrugResult, ...]
    combined_bag: CombinedBagResult | None
    valid: bool
    global_warnings: tuple[str, ...]


# ---------------------------------------------------------------------------
# Compute.
# ---------------------------------------------------------------------------


def _resolve_weight_kg(inputs: AnalgesiaBuilderInputs) -> float | None:
    if inputs.weight_value <= 0:
        return None
    if inputs.weight_unit == WeightUnit.LB:
        return lb_to_kg(inputs.weight_value)
    return inputs.weight_value


def _dose_to_ug_per_hr(dose: float, dose_unit: DoseUnit, weight_kg: float) -> float:
    """Mirror of engine._dose_to_ug_per_hr.

    Kept private to this module so the builder's per-drug compute
    doesn't depend on the single-drug engine's compute() machinery.
    Adding a new dose unit requires updating both this function and
    the engine's version, which is fine — only four units exist and
    they're stable.
    """
    if dose_unit == DoseUnit.UG_PER_KG_PER_MIN:
        return weight_kg * dose * 60.0
    if dose_unit == DoseUnit.UG_PER_KG_PER_HR:
        return weight_kg * dose
    if dose_unit == DoseUnit.MG_PER_KG_PER_HR:
        return weight_kg * dose * 1000.0
    if dose_unit == DoseUnit.MG_PER_KG_PER_MIN:
        return weight_kg * dose * 60.0 * 1000.0
    raise ValueError(f"Unknown dose unit: {dose_unit}")


def _round_pump_rate(ml_per_hr: float) -> float:
    """Round pump rate to 2 decimal places — typical infusion-pump precision."""
    return round(ml_per_hr, 2)


def _compute_titration_ladder(
    spec: AnalgesiaDrugSpec,
    weight_kg: float,
    concentration_ug_per_ml: float,
) -> tuple[tuple[float, float], ...]:
    """For each titration-ladder dose, compute the pump rate at the
    chosen concentration. Returns ((dose, ml/hr), ...) tuples."""
    if concentration_ug_per_ml <= 0:
        return ()
    out: list[tuple[float, float]] = []
    for dose in spec.titration_ladder:
        total_ug_per_hr = _dose_to_ug_per_hr(dose, spec.dose_unit, weight_kg)
        ml_per_hr = total_ug_per_hr / concentration_ug_per_ml
        out.append((dose, _round_pump_rate(ml_per_hr)))
    return tuple(out)


def _drug_warnings(
    spec: AnalgesiaDrugSpec,
    species: Species,
    dose: float,
) -> tuple[str, ...]:
    """Apply dose-range checks for one drug. Returns warning strings to
    render in the per-drug card.

    Persistent warnings are always emitted (drug-level safety notes
    every clinician should see). Caution-threshold warnings fire when
    dose >= caution_threshold. Exceeds-max warnings fire when dose > max.
    Below-min warnings fire when dose < min (and dose > 0)."""
    dose_range = spec.dose_ranges.get(species)
    if dose_range is None:
        return ()

    warnings: list[str] = []

    # Persistent warning — drug-level safety / context for the role.
    if dose_range.persistent_warning:
        warnings.append(dose_range.persistent_warning)

    # Below-min warning.
    if 0 < dose < dose_range.min:
        warnings.append(
            f"⚠ Dose {dose} {spec.dose_unit.value} is below the published "
            f"range of {dose_range.min}–{dose_range.max} "
            f"{spec.dose_unit.value} for {species.value}s. "
            "Subtherapeutic dosing may not provide adequate analgesia."
        )

    # Caution-threshold warning. Fires at the threshold even if at-or-
    # under max, since the threshold is a deliberate signal that the
    # clinician is in a specialized-protocol zone (e.g., ketamine
    # surgical maintenance vs analgesia).
    if (
        dose_range.caution_threshold
        and dose >= dose_range.caution_threshold
        and dose_range.caution_note
    ):
        warnings.append(dose_range.caution_note)

    # Exceeds-max warning.
    if dose > dose_range.max:
        warnings.append(
            f"⚠ CAUTION: dose {dose} {spec.dose_unit.value} exceeds the "
            f"published maximum of {dose_range.max} {spec.dose_unit.value} "
            f"for {species.value}s."
        )

    return tuple(warnings)


def _compute_one_drug(
    spec: AnalgesiaDrugSpec,
    species: Species,
    weight_kg: float,
    dose: float,
    concentration_ug_per_ml: float,
) -> AnalgesiaDrugResult:
    """Compute pump rate, titration ladder, warnings, and loading doses
    for one selected drug."""
    if dose <= 0 or concentration_ug_per_ml <= 0 or weight_kg <= 0:
        return AnalgesiaDrugResult(
            spec=spec,
            dose=dose,
            concentration_ug_per_ml=concentration_ug_per_ml,
            total_dose_ug_per_hr=0.0,
            total_dose_ug_per_min=None,
            ml_per_hr_precise=0.0,
            ml_per_hr_pump=0.0,
            ml_per_kg_per_hr=0.0,
            titration_rates=(),
            warnings=("Enter a positive dose and concentration to compute.",),
            loading_dose_results=(),
            valid=False,
        )

    total_ug_per_hr = _dose_to_ug_per_hr(dose, spec.dose_unit, weight_kg)
    total_ug_per_min = (
        total_ug_per_hr / 60.0 if spec.dose_unit == DoseUnit.UG_PER_KG_PER_MIN else None
    )
    ml_per_hr_precise = total_ug_per_hr / concentration_ug_per_ml
    ml_per_hr_pump = _round_pump_rate(ml_per_hr_precise)
    ml_per_kg_per_hr = ml_per_hr_precise / weight_kg

    warnings = _drug_warnings(spec, species, dose)
    titration = _compute_titration_ladder(spec, weight_kg, concentration_ug_per_ml)

    # Loading doses use the existing engine helper, which needs a
    # CalculatorConfig-shaped object. Build a minimal stand-in: the
    # helper only reads `loading_doses` and `stock_concentration_ug_per_ml`.
    class _LoadingDrug:
        loading_doses = spec.loading_doses
        stock_concentration_ug_per_ml = spec.stock_concentration_ug_per_ml

    loading = compute_loading_doses(
        drug=_LoadingDrug(),  # type: ignore[arg-type]
        weight_kg=weight_kg,
        species=species,
        cri_dose_value=dose,
    )

    return AnalgesiaDrugResult(
        spec=spec,
        dose=dose,
        concentration_ug_per_ml=concentration_ug_per_ml,
        total_dose_ug_per_hr=total_ug_per_hr,
        total_dose_ug_per_min=total_ug_per_min,
        ml_per_hr_precise=ml_per_hr_precise,
        ml_per_hr_pump=ml_per_hr_pump,
        ml_per_kg_per_hr=ml_per_kg_per_hr,
        titration_rates=titration,
        warnings=warnings,
        loading_dose_results=loading,
        valid=True,
    )


def _compute_combined_bag(
    weight_kg: float,
    species: Species,
    selected_specs: list[AnalgesiaDrugSpec],
    doses: dict[str, float],
    bag_volume_ml: float,
    shared_pump_rate_ml_per_kg_per_hr: float,
) -> CombinedBagResult:
    """Compute a combined-bag recipe: one bag, all drugs, shared pump rate.

    Given the patient weight, the desired per-drug doses, and the bag
    volume + shared pump rate, derive:
      - The pump rate in absolute mL/hr.
      - How many hours the prepared bag will run for.
      - For each drug: total mass to add to the bag (in µg internally,
        rendered as mg or µg by the template), mL of stock to draw,
        and the resulting bag concentration.

    The math mirrors the dose-driven MLK approach: hourly drug needed
    × hours per bag = mass per bag; mass per bag / stock concentration
    = mL of stock to draw. This is the dose-driven inverse of
    Silverstein-style fixed recipes.
    """
    pump_rate_ml_per_hr = weight_kg * shared_pump_rate_ml_per_kg_per_hr
    if pump_rate_ml_per_hr <= 0 or bag_volume_ml <= 0:
        # Degenerate inputs — return a shell with valid=False so the
        # template can render the form state.
        return CombinedBagResult(
            weight_kg=weight_kg,
            species=species,
            bag_volume_ml=bag_volume_ml,
            pump_rate_ml_per_kg_per_hr=shared_pump_rate_ml_per_kg_per_hr,
            pump_rate_ml_per_hr=0.0,
            hours_per_bag=0.0,
            drug_recipes=tuple(
                CombinedBagDrugRecipe(
                    spec=s,
                    dose=doses.get(s.slug, 0.0),
                    total_for_bag_ug=0.0,
                    ml_of_stock_to_add=0.0,
                    bag_concentration_ug_per_ml=0.0,
                    warnings=(),
                    loading_dose_results=(),
                )
                for s in selected_specs
            ),
            total_stock_volume_ml=0.0,
            adjusted_carrier_ml=bag_volume_ml,
            valid=False,
        )

    hours_per_bag = bag_volume_ml / pump_rate_ml_per_hr

    recipes: list[CombinedBagDrugRecipe] = []
    for spec in selected_specs:
        dose = doses.get(spec.slug, 0.0)
        # Convert dose to µg/hr — engine's standardised unit. This
        # makes all the per-drug math comparable regardless of which
        # dose unit the clinician entered.
        ug_per_hr = _dose_to_ug_per_hr(dose, spec.dose_unit, weight_kg)
        total_for_bag_ug = ug_per_hr * hours_per_bag
        ml_of_stock = (
            total_for_bag_ug / spec.stock_concentration_ug_per_ml
            if spec.stock_concentration_ug_per_ml > 0
            else 0.0
        )
        bag_conc = total_for_bag_ug / bag_volume_ml if bag_volume_ml > 0 else 0.0

        # Per-drug warnings and loading doses are the same as
        # per-drug mode — dose-range and loading protocols don't
        # depend on the delivery vehicle.
        warnings = _drug_warnings(spec, species, dose)

        class _LoadingDrug:
            loading_doses = spec.loading_doses
            stock_concentration_ug_per_ml = spec.stock_concentration_ug_per_ml

        loading = compute_loading_doses(
            drug=_LoadingDrug(),  # type: ignore[arg-type]
            weight_kg=weight_kg,
            species=species,
            cri_dose_value=dose,
        )

        recipes.append(
            CombinedBagDrugRecipe(
                spec=spec,
                dose=dose,
                total_for_bag_ug=total_for_bag_ug,
                ml_of_stock_to_add=ml_of_stock,
                bag_concentration_ug_per_ml=bag_conc,
                warnings=warnings,
                loading_dose_results=loading,
            )
        )

    total_stock_ml = sum(r.ml_of_stock_to_add for r in recipes)
    adjusted_carrier_ml = bag_volume_ml - total_stock_ml

    return CombinedBagResult(
        weight_kg=weight_kg,
        species=species,
        bag_volume_ml=bag_volume_ml,
        pump_rate_ml_per_kg_per_hr=shared_pump_rate_ml_per_kg_per_hr,
        pump_rate_ml_per_hr=pump_rate_ml_per_hr,
        hours_per_bag=hours_per_bag,
        drug_recipes=tuple(recipes),
        total_stock_volume_ml=total_stock_ml,
        adjusted_carrier_ml=adjusted_carrier_ml,
        valid=all(d > 0 for d in (pump_rate_ml_per_hr, bag_volume_ml)),
    )


def compute_analgesia(inputs: AnalgesiaBuilderInputs) -> AnalgesiaResult:
    """Compute analgesia results.

    Branches on `inputs.prep_mode`:

      - "per_drug" (default): one `AnalgesiaDrugResult` per selected
        drug, each with its own pump rate. Each drug is its own bag /
        syringe in this mode.

      - "combined_bag" (Phase 3): one `CombinedBagResult` describing
        a single shared bag at a shared pump rate, with per-drug stock
        volumes to add. The MLK / DMLK workflow.

    Global warnings (form-level: invalid weight, species-restricted
    drug skipped, unrecognised opioid) apply to both modes and live
    on the top-level `AnalgesiaResult.global_warnings`.
    """
    weight_kg = _resolve_weight_kg(inputs)
    global_warnings: list[str] = []

    if weight_kg is None:
        global_warnings.append(
            "Enter a positive patient weight to compute pump rates."
        )

    # Resolve opioid spec. The sentinel "none" (or empty string) means
    # the user has chosen opioid-free composition (KL, DLK, monotherapy
    # with adjuncts, etc.). Unknown slugs are still an error.
    opioid_spec: AnalgesiaDrugSpec | None = None
    if inputs.opioid_slug and inputs.opioid_slug != "none":
        opioid_spec = get_spec(inputs.opioid_slug)
        if opioid_spec is None or opioid_spec.role != "opioid":
            global_warnings.append(
                f"Unknown or invalid opioid: {inputs.opioid_slug!r}. "
                "Select fentanyl, morphine, hydromorphone, or None "
                "(opioid-free)."
            )
            return AnalgesiaResult(
                weight_kg=weight_kg or 0.0,
                species=inputs.species,
                prep_mode=inputs.prep_mode,
                drug_results=(),
                combined_bag=None,
                valid=False,
                global_warnings=tuple(global_warnings),
            )

    # Build the active-spec list: opioid first (if any), then adjuncts
    # in the order they appear in ADJUNCT_SPECS (so the result panel is
    # rendered with a stable ordering regardless of form submission
    # order).
    selected_specs: list[AnalgesiaDrugSpec] = []
    if opioid_spec is not None:
        selected_specs.append(opioid_spec)
    for adj in ADJUNCT_SPECS:
        if adj.slug in inputs.adjunct_slugs:
            # Species gating: if the drug is restricted to a species
            # and the user picked a different one, surface a global
            # warning and skip the adjunct (don't compute it).
            if adj.species_restriction and adj.species_restriction != inputs.species:
                global_warnings.append(
                    f"{adj.display_name} CRI is restricted to "
                    f"{adj.species_restriction.value}s. Skipping for "
                    f"{inputs.species.value}."
                )
                continue
            selected_specs.append(adj)

    # At least one drug must be selected to compute anything. The most
    # common ways into this state: opioid-free chosen with no adjunct
    # checkboxes, or species gating skipping every restricted adjunct
    # the user toggled (e.g. cat patient with lidocaine as the only
    # adjunct).
    if not selected_specs:
        global_warnings.append(
            "Select at least one drug. With opioid-free composition you "
            "still need to toggle on a ketamine, lidocaine, or "
            "dexmedetomidine adjunct."
        )

    # Pump-rate sanity for combined-bag mode.
    if (
        inputs.prep_mode == "combined_bag"
        and inputs.shared_pump_rate_ml_per_kg_per_hr <= 0
    ):
        global_warnings.append(
            "Combined-bag mode requires a positive shared pump rate "
            "(mL/kg/hr)."
        )
    if inputs.prep_mode == "combined_bag" and inputs.bag_volume_ml <= 0:
        global_warnings.append(
            "Combined-bag mode requires a positive bag volume (mL)."
        )

    if weight_kg is None:
        # Form-state shells for the chosen mode.
        if inputs.prep_mode == "combined_bag":
            return AnalgesiaResult(
                weight_kg=0.0,
                species=inputs.species,
                prep_mode=inputs.prep_mode,
                drug_results=(),
                combined_bag=_compute_combined_bag(
                    weight_kg=0.0,
                    species=inputs.species,
                    selected_specs=selected_specs,
                    doses=inputs.doses,
                    bag_volume_ml=inputs.bag_volume_ml,
                    shared_pump_rate_ml_per_kg_per_hr=(
                        inputs.shared_pump_rate_ml_per_kg_per_hr
                    ),
                ),
                valid=False,
                global_warnings=tuple(global_warnings),
            )
        return AnalgesiaResult(
            weight_kg=0.0,
            species=inputs.species,
            prep_mode=inputs.prep_mode,
            drug_results=tuple(
                AnalgesiaDrugResult(
                    spec=s,
                    dose=inputs.doses.get(s.slug, 0.0),
                    concentration_ug_per_ml=inputs.concentrations_ug_per_ml.get(s.slug, 0.0),
                    total_dose_ug_per_hr=0.0,
                    total_dose_ug_per_min=None,
                    ml_per_hr_precise=0.0,
                    ml_per_hr_pump=0.0,
                    ml_per_kg_per_hr=0.0,
                    titration_rates=(),
                    warnings=(),
                    loading_dose_results=(),
                    valid=False,
                )
                for s in selected_specs
            ),
            combined_bag=None,
            valid=False,
            global_warnings=tuple(global_warnings),
        )

    # Compute the chosen mode.
    if inputs.prep_mode == "combined_bag":
        combined = _compute_combined_bag(
            weight_kg=weight_kg,
            species=inputs.species,
            selected_specs=selected_specs,
            doses=inputs.doses,
            bag_volume_ml=inputs.bag_volume_ml,
            shared_pump_rate_ml_per_kg_per_hr=(
                inputs.shared_pump_rate_ml_per_kg_per_hr
            ),
        )
        return AnalgesiaResult(
            weight_kg=weight_kg,
            species=inputs.species,
            prep_mode=inputs.prep_mode,
            drug_results=(),
            combined_bag=combined,
            valid=(
                combined.valid
                and bool(combined.drug_recipes)
                and not any("requires" in w for w in global_warnings)
                and not any("at least one drug" in w for w in global_warnings)
            ),
            global_warnings=tuple(global_warnings),
        )

    drug_results = tuple(
        _compute_one_drug(
            spec=s,
            species=inputs.species,
            weight_kg=weight_kg,
            dose=inputs.doses.get(s.slug, 0.0),
            concentration_ug_per_ml=inputs.concentrations_ug_per_ml.get(s.slug, 0.0),
        )
        for s in selected_specs
    )

    return AnalgesiaResult(
        weight_kg=weight_kg,
        species=inputs.species,
        prep_mode=inputs.prep_mode,
        drug_results=drug_results,
        combined_bag=None,
        # Require at least one drug result. Vacuous all() over () is
        # True, which would let an empty-selection submission claim
        # validity — caught here so the result panel shows the
        # global warning instead of an empty success state.
        valid=bool(drug_results) and all(r.valid for r in drug_results),
        global_warnings=tuple(global_warnings),
    )
