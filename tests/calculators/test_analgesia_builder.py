"""Tests for the multi-modal analgesia CRI builder (Phase 1).

Phase 1 covers: opioid backbone (fentanyl, morphine, hydromorphone),
optional ketamine adjunct, per-drug independent compute mode.

Test coverage areas:
  - Spec shapes: opioid roles, dose units, species coverage, loading
    doses present.
  - Per-drug compute math: pump rates for representative cases
    spanning µg/kg/hr (fentanyl), mg/kg/hr (morphine, hydromorphone),
    and µg/kg/min (ketamine) dose units.
  - Adjunct opt-in: ketamine appears only when its checkbox is on;
    other drugs are never silently included.
  - Species behavior: cat-specific warnings fire (morphine dysphoria,
    hydromorphone hyperthermia, etc.) and cat-restricted drugs would
    be skipped (none in Phase 1 — lidocaine lands Phase 2).
  - End-to-end POST through the router, both full-page and HTMX
    partial renders.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.analgesia_builder import (
    ADJUNCT_SPECS,
    OPIOID_SPECS,
    SPEC_BY_SLUG,
    AnalgesiaBuilderInputs,
    compute_analgesia,
    get_spec,
)
from app.calculators.engine import DoseUnit, Species, WeightUnit
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Spec shape tests — pin down the catalog of drugs available in the
# builder. Adding/removing drugs must trip these on purpose, not by
# accident.
# ---------------------------------------------------------------------------


class TestPhase1DrugSpecs:
    def test_three_opioid_options(self) -> None:
        # Phase 1 set: fentanyl, morphine, hydromorphone.
        slugs = [s.slug for s in OPIOID_SPECS]
        assert slugs == ["fentanyl", "morphine", "hydromorphone"]

    def test_all_opioids_marked_as_opioid_role(self) -> None:
        for spec in OPIOID_SPECS:
            assert spec.role == "opioid"

    def test_phase_2_adjuncts(self) -> None:
        # Phase 2 set: ketamine, lidocaine, dexmedetomidine. Order
        # is the order they appear in the form and result panel.
        slugs = [s.slug for s in ADJUNCT_SPECS]
        assert slugs == ["ketamine", "lidocaine", "dexmedetomidine"]

    def test_lidocaine_is_dog_only(self) -> None:
        # Lidocaine carries a hard species_restriction. The engine
        # uses this to skip the drug and emit a global warning when
        # the patient species doesn't match.
        lido = get_spec("lidocaine")
        assert lido is not None
        assert lido.species_restriction == Species.DOG

    def test_dexmedetomidine_has_no_species_restriction(self) -> None:
        dex = get_spec("dexmedetomidine")
        assert dex is not None
        assert dex.species_restriction is None
        # Both species must be in dose_ranges since neither is gated.
        assert Species.DOG in dex.dose_ranges
        assert Species.CAT in dex.dose_ranges

    def test_lidocaine_uses_mg_per_kg_per_hr(self) -> None:
        # Matches the standalone /lidocaine convention and the MLK
        # published dose range (1.5–3.0 mg/kg/hr). The dose unit
        # choice is deliberate — the alternative µg/kg/min is more
        # common for ketamine and the cardiac/anti-arrhythmic CRI
        # context.
        lido = get_spec("lidocaine")
        assert lido is not None
        assert lido.dose_unit == DoseUnit.MG_PER_KG_PER_HR

    def test_dexmedetomidine_uses_ug_per_kg_per_hr(self) -> None:
        # Matches Plumb's analgesic-CRI convention and the DMLK
        # 0.5 µg/kg/hr published dose.
        dex = get_spec("dexmedetomidine")
        assert dex is not None
        assert dex.dose_unit == DoseUnit.UG_PER_KG_PER_HR

    def test_ketamine_dose_unit_is_ug_per_kg_per_min(self) -> None:
        # Ketamine is the unit-confusion-prone drug Plumb's flags as a
        # high-alert error. The builder uses µg/kg/min for ketamine
        # specifically — the more common clinical convention for the
        # analgesic dose range, and the one that avoids the mg/kg/hr
        # vs µg/kg/min ≈60× error.
        ket = get_spec("ketamine")
        assert ket is not None
        assert ket.dose_unit == DoseUnit.UG_PER_KG_PER_MIN

    def test_morphine_dose_unit_is_mg_per_kg_per_hr(self) -> None:
        morph = get_spec("morphine")
        assert morph is not None
        assert morph.dose_unit == DoseUnit.MG_PER_KG_PER_HR

    def test_hydromorphone_dose_unit_is_mg_per_kg_per_hr(self) -> None:
        hydro = get_spec("hydromorphone")
        assert hydro is not None
        assert hydro.dose_unit == DoseUnit.MG_PER_KG_PER_HR

    def test_every_spec_has_both_species(self) -> None:
        # Phase 1 has no species-restricted drugs. Phase 2's lidocaine
        # will trip this requirement — that test will be relaxed for
        # specs with a species_restriction set.
        for spec in OPIOID_SPECS:
            assert Species.DOG in spec.dose_ranges
            assert Species.CAT in spec.dose_ranges
        for spec in ADJUNCT_SPECS:
            if spec.species_restriction is None:
                assert Species.DOG in spec.dose_ranges
                assert Species.CAT in spec.dose_ranges

    def test_every_spec_has_loading_doses(self) -> None:
        # Phase 1 drugs all have published loading dose protocols.
        # The builder surfaces them per-drug on the result card.
        for spec in OPIOID_SPECS + ADJUNCT_SPECS:
            assert len(spec.loading_doses) >= 1, (
                f"{spec.slug} has no loading_doses — Phase 1 expects every "
                "drug to surface at least one loading-dose protocol."
            )

    def test_cat_warnings_present_where_clinically_relevant(self) -> None:
        # Morphine in cats triggers a dysphoria caveat; hydromorphone
        # in cats triggers a hyperthermia caveat. These must be in the
        # persistent_warning text so the result panel always shows
        # them when the cat species is selected.
        morph_cat = get_spec("morphine").dose_ranges[Species.CAT]  # type: ignore[union-attr]
        assert "dysphoria" in morph_cat.persistent_warning.lower()

        hydro_cat = get_spec("hydromorphone").dose_ranges[Species.CAT]  # type: ignore[union-attr]
        assert "hyperthermia" in hydro_cat.persistent_warning.lower()

    def test_fentanyl_spec_reuses_fentanyl_calc_config(self) -> None:
        # Fentanyl spec sources its dose ranges and loading doses from
        # the FENTANYL CalculatorConfig so /fentanyl and /analgesia-cri
        # don't drift. Validate the cross-reference by checking the
        # objects are the same (not just equal).
        from app.calculators.drugs import FENTANYL

        fent_spec = get_spec("fentanyl")
        assert fent_spec is not None
        assert fent_spec.dose_ranges is FENTANYL.dose_ranges
        assert fent_spec.loading_doses is FENTANYL.loading_doses


# ---------------------------------------------------------------------------
# Per-drug compute math — verify the pump rate for representative
# cases in each dose unit. Catches dose-unit branch regressions in
# _dose_to_ug_per_hr inside analgesia_builder.
# ---------------------------------------------------------------------------


class TestPerDrugComputeMath:
    def test_fentanyl_dog_at_5_ug_per_kg_per_hr(self) -> None:
        # 20 kg × 5 µg/kg/hr / 5 µg/mL = 20 mL/hr
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=(),
            doses={"fentanyl": 5.0},
            concentrations_ug_per_ml={"fentanyl": 5.0},
        )
        result = compute_analgesia(inputs)
        assert result.valid
        assert len(result.drug_results) == 1
        assert result.drug_results[0].ml_per_hr_pump == pytest.approx(20.0, rel=1e-4)

    def test_morphine_dog_at_0_2_mg_per_kg_per_hr(self) -> None:
        # 20 kg × 0.2 mg/kg/hr × 1000 / 100 µg/mL = 40 mL/hr
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="morphine",
            adjunct_slugs=(),
            doses={"morphine": 0.2},
            concentrations_ug_per_ml={"morphine": 100.0},
        )
        result = compute_analgesia(inputs)
        assert result.valid
        assert result.drug_results[0].ml_per_hr_pump == pytest.approx(40.0, rel=1e-4)

    def test_hydromorphone_dog_at_0_03_mg_per_kg_per_hr(self) -> None:
        # 20 kg × 0.03 mg/kg/hr × 1000 / 40 µg/mL = 15 mL/hr
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="hydromorphone",
            adjunct_slugs=(),
            doses={"hydromorphone": 0.03},
            concentrations_ug_per_ml={"hydromorphone": 40.0},
        )
        result = compute_analgesia(inputs)
        assert result.valid
        assert result.drug_results[0].ml_per_hr_pump == pytest.approx(15.0, rel=1e-4)

    def test_ketamine_dog_at_2_ug_per_kg_per_min(self) -> None:
        # 20 kg × 2 µg/kg/min × 60 / 2000 µg/mL = 1.2 mL/hr
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=("ketamine",),
            doses={"fentanyl": 5.0, "ketamine": 2.0},
            concentrations_ug_per_ml={"fentanyl": 5.0, "ketamine": 2000.0},
        )
        result = compute_analgesia(inputs)
        assert result.valid
        # drug_results[0] is the opioid, [1] is the adjunct (ordering
        # is opioid-first, then adjuncts in ADJUNCT_SPECS order).
        ketamine_result = result.drug_results[1]
        assert ketamine_result.spec.slug == "ketamine"
        assert ketamine_result.ml_per_hr_pump == pytest.approx(1.2, rel=1e-4)

    def test_weight_in_pounds_converts(self) -> None:
        # 44 lb ≈ 20 kg; same dose → same pump rate as the 20 kg test.
        inputs = AnalgesiaBuilderInputs(
            weight_value=44.0922,  # 20 kg in lb
            weight_unit=WeightUnit.LB,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=(),
            doses={"fentanyl": 5.0},
            concentrations_ug_per_ml={"fentanyl": 5.0},
        )
        result = compute_analgesia(inputs)
        assert result.valid
        assert result.weight_kg == pytest.approx(20.0, rel=1e-3)
        assert result.drug_results[0].ml_per_hr_pump == pytest.approx(20.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Adjunct selection — checkbox-controlled. Drugs not toggled on are
# never computed; per-drug results are returned only for selected
# drugs.
# ---------------------------------------------------------------------------


class TestAdjunctSelection:
    def test_no_adjuncts_means_one_drug_result(self) -> None:
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=(),
            doses={"fentanyl": 5.0},
            concentrations_ug_per_ml={"fentanyl": 5.0},
        )
        result = compute_analgesia(inputs)
        assert len(result.drug_results) == 1
        assert result.drug_results[0].spec.slug == "fentanyl"

    def test_ketamine_toggle_adds_second_result(self) -> None:
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=("ketamine",),
            doses={"fentanyl": 5.0, "ketamine": 2.0},
            concentrations_ug_per_ml={"fentanyl": 5.0, "ketamine": 2000.0},
        )
        result = compute_analgesia(inputs)
        assert len(result.drug_results) == 2
        slugs = [r.spec.slug for r in result.drug_results]
        assert slugs == ["fentanyl", "ketamine"]


# ---------------------------------------------------------------------------
# Species-specific behavior — the per-drug warnings include species-
# dependent safety notes (cat dysphoria, cat hyperthermia, etc.).
# ---------------------------------------------------------------------------


class TestSpeciesBehavior:
    def test_cat_morphine_includes_dysphoria_warning(self) -> None:
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="morphine",
            adjunct_slugs=(),
            doses={"morphine": 0.08},
            concentrations_ug_per_ml={"morphine": 100.0},
        )
        result = compute_analgesia(inputs)
        morph_result = result.drug_results[0]
        combined = " ".join(morph_result.warnings).lower()
        assert "dysphoria" in combined

    def test_cat_hydromorphone_includes_hyperthermia_warning(self) -> None:
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="hydromorphone",
            adjunct_slugs=(),
            doses={"hydromorphone": 0.02},
            concentrations_ug_per_ml={"hydromorphone": 20.0},
        )
        result = compute_analgesia(inputs)
        hydro_result = result.drug_results[0]
        combined = " ".join(hydro_result.warnings).lower()
        assert "hyperthermia" in combined

    def test_cat_hydromorphone_picks_cat_specific_loading_dose(self) -> None:
        # Hydromorphone has two loading-dose scenarios: one dog-only
        # (0.05–0.1 mg/kg) and one cat-only (0.025 mg/kg fixed).
        # The cat species selection must surface only the cat scenario.
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="hydromorphone",
            adjunct_slugs=(),
            doses={"hydromorphone": 0.02},
            concentrations_ug_per_ml={"hydromorphone": 20.0},
        )
        result = compute_analgesia(inputs)
        loading = result.drug_results[0].loading_dose_results
        assert len(loading) == 1
        # Cat dose: 0.025 mg/kg × 4 kg = 0.1 mg = 0.05 mL of 2 mg/mL stock.
        assert loading[0].min_per_kg == 0.025
        assert loading[0].min_total == pytest.approx(0.1, rel=1e-4)
        assert loading[0].min_ml_stock == pytest.approx(0.05, rel=1e-4)


# ---------------------------------------------------------------------------
# Phase 2: species-gating for lidocaine, compute math for the new
# drugs.
# ---------------------------------------------------------------------------


class TestPhase2SpeciesGating:
    def test_cat_with_lidocaine_skips_lidocaine(self) -> None:
        # Toggling lidocaine ON for a cat patient must produce: no
        # lidocaine in drug_results, a global warning explaining why,
        # and other selected drugs still computed normally.
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="fentanyl",
            adjunct_slugs=("lidocaine", "dexmedetomidine"),
            doses={"fentanyl": 5.0, "lidocaine": 1.5, "dexmedetomidine": 0.5},
            concentrations_ug_per_ml={
                "fentanyl": 5.0,
                "lidocaine": 4000.0,
                "dexmedetomidine": 4.0,
            },
        )
        result = compute_analgesia(inputs)
        slugs = [r.spec.slug for r in result.drug_results]
        assert "lidocaine" not in slugs
        # Other drugs still computed.
        assert "fentanyl" in slugs
        assert "dexmedetomidine" in slugs
        # Global warning surfaced.
        combined = " ".join(result.global_warnings).lower()
        assert "lidocaine" in combined
        assert "dog" in combined  # "restricted to dogs"

    def test_dog_with_lidocaine_computes_normally(self) -> None:
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=("lidocaine",),
            doses={"fentanyl": 5.0, "lidocaine": 1.5},
            concentrations_ug_per_ml={"fentanyl": 5.0, "lidocaine": 4000.0},
        )
        result = compute_analgesia(inputs)
        slugs = [r.spec.slug for r in result.drug_results]
        assert "lidocaine" in slugs
        # No species-gating warning when the species matches.
        combined = " ".join(result.global_warnings).lower()
        assert "lidocaine" not in combined or "restricted" not in combined

    def test_cat_with_dexmedetomidine_computes(self) -> None:
        # Dex has no species_restriction; cat selection must compute
        # using the cat dose_range and not trigger any global warning.
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="fentanyl",
            adjunct_slugs=("dexmedetomidine",),
            doses={"fentanyl": 5.0, "dexmedetomidine": 0.5},
            concentrations_ug_per_ml={"fentanyl": 5.0, "dexmedetomidine": 4.0},
        )
        result = compute_analgesia(inputs)
        slugs = [r.spec.slug for r in result.drug_results]
        assert "dexmedetomidine" in slugs
        # 4 kg × 0.5 µg/kg/hr / 4 µg/mL = 0.5 mL/hr.
        dex_result = next(r for r in result.drug_results if r.spec.slug == "dexmedetomidine")
        assert dex_result.ml_per_hr_pump == pytest.approx(0.5, rel=1e-4)


class TestPhase2DrugCompute:
    def test_lidocaine_dog_at_1_5_mg_per_kg_per_hr(self) -> None:
        # 20 kg × 1.5 mg/kg/hr × 1000 / 4000 µg/mL = 7.5 mL/hr.
        # This is the MLK-protocol default dose at the standard
        # 1 g / 250 mL bag prep.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=("lidocaine",),
            doses={"fentanyl": 5.0, "lidocaine": 1.5},
            concentrations_ug_per_ml={"fentanyl": 5.0, "lidocaine": 4000.0},
        )
        result = compute_analgesia(inputs)
        lido = next(r for r in result.drug_results if r.spec.slug == "lidocaine")
        assert lido.ml_per_hr_pump == pytest.approx(7.5, rel=1e-4)

    def test_dex_dog_at_0_5_ug_per_kg_per_hr(self) -> None:
        # 20 kg × 0.5 µg/kg/hr / 4 µg/mL = 2.5 mL/hr.
        # This is the DMLK-protocol default.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=("dexmedetomidine",),
            doses={"fentanyl": 5.0, "dexmedetomidine": 0.5},
            concentrations_ug_per_ml={"fentanyl": 5.0, "dexmedetomidine": 4.0},
        )
        result = compute_analgesia(inputs)
        dex = next(r for r in result.drug_results if r.spec.slug == "dexmedetomidine")
        assert dex.ml_per_hr_pump == pytest.approx(2.5, rel=1e-4)

    def test_lidocaine_dog_loading_dose_present(self) -> None:
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=("lidocaine",),
            doses={"fentanyl": 5.0, "lidocaine": 1.5},
            concentrations_ug_per_ml={"fentanyl": 5.0, "lidocaine": 4000.0},
        )
        result = compute_analgesia(inputs)
        lido = next(r for r in result.drug_results if r.spec.slug == "lidocaine")
        # 1–2 mg/kg × 20 kg = 20–40 mg = 1–2 mL of 20 mg/mL stock.
        assert len(lido.loading_dose_results) == 1
        ld = lido.loading_dose_results[0]
        assert ld.min_total == pytest.approx(20.0, rel=1e-4)
        assert ld.max_total == pytest.approx(40.0, rel=1e-4)
        assert ld.min_ml_stock == pytest.approx(1.0, rel=1e-4)
        assert ld.max_ml_stock == pytest.approx(2.0, rel=1e-4)

    def test_cat_dex_picks_cat_specific_loading_dose(self) -> None:
        # Dex has two loading scenarios (dog 1–3 µg/kg, cat 1–2 µg/kg).
        # Cat selection must surface only the cat scenario.
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="fentanyl",
            adjunct_slugs=("dexmedetomidine",),
            doses={"fentanyl": 5.0, "dexmedetomidine": 0.5},
            concentrations_ug_per_ml={"fentanyl": 5.0, "dexmedetomidine": 4.0},
        )
        result = compute_analgesia(inputs)
        dex = next(r for r in result.drug_results if r.spec.slug == "dexmedetomidine")
        assert len(dex.loading_dose_results) == 1
        ld = dex.loading_dose_results[0]
        # Cat range 1–2 µg/kg × 4 kg = 4–8 µg.
        assert ld.min_per_kg == 1.0
        assert ld.max_per_kg == 2.0

    def test_all_four_adjuncts_dog_simultaneously(self) -> None:
        # End-to-end: opioid + ketamine + lidocaine + dex on a dog.
        # Drug-result ordering: opioid first, then adjuncts in
        # ADJUNCT_SPECS order (ketamine, lidocaine, dexmedetomidine).
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=("ketamine", "lidocaine", "dexmedetomidine"),
            doses={
                "fentanyl": 5.0,
                "ketamine": 2.0,
                "lidocaine": 1.5,
                "dexmedetomidine": 0.5,
            },
            concentrations_ug_per_ml={
                "fentanyl": 5.0,
                "ketamine": 2000.0,
                "lidocaine": 4000.0,
                "dexmedetomidine": 4.0,
            },
        )
        result = compute_analgesia(inputs)
        assert result.valid
        slugs = [r.spec.slug for r in result.drug_results]
        assert slugs == ["fentanyl", "ketamine", "lidocaine", "dexmedetomidine"]


# ---------------------------------------------------------------------------
# Caution warnings — dose-range thresholds fire correctly.
# ---------------------------------------------------------------------------


class TestCautionWarnings:
    def test_ketamine_surgical_maintenance_dose_fires_caution(self) -> None:
        # ≥ 10 µg/kg/min crosses ketamine's caution_threshold,
        # flagging the surgical-maintenance vs analgesic distinction.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=("ketamine",),
            doses={"fentanyl": 5.0, "ketamine": 10.0},
            concentrations_ug_per_ml={"fentanyl": 5.0, "ketamine": 2000.0},
        )
        result = compute_analgesia(inputs)
        ket = result.drug_results[1]
        combined = " ".join(ket.warnings).lower()
        assert "surgical" in combined or "anesthesia" in combined

    def test_subtherapeutic_dose_warns_below_min(self) -> None:
        # Fentanyl 1 µg/kg/hr is below the published 2 µg/kg/hr min.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=(),
            doses={"fentanyl": 1.0},
            concentrations_ug_per_ml={"fentanyl": 5.0},
        )
        result = compute_analgesia(inputs)
        combined = " ".join(result.drug_results[0].warnings).lower()
        assert "below" in combined


# ---------------------------------------------------------------------------
# Loading-dose handling — drugs whose loading_doses include the
# selected species must surface a panel; drugs whose loading_doses
# don't list the species must not.
# ---------------------------------------------------------------------------


class TestLoadingDoses:
    def test_morphine_loading_for_dog_present(self) -> None:
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="morphine",
            adjunct_slugs=(),
            doses={"morphine": 0.2},
            concentrations_ug_per_ml={"morphine": 100.0},
        )
        result = compute_analgesia(inputs)
        loading = result.drug_results[0].loading_dose_results
        assert len(loading) == 1
        # Range 0.1–0.3 mg/kg, 20 kg → 2–6 mg total → 0.4–1.2 mL of 5 mg/mL stock.
        assert loading[0].min_total == pytest.approx(2.0, rel=1e-4)
        assert loading[0].max_total == pytest.approx(6.0, rel=1e-4)

    def test_morphine_loading_for_cat_absent(self) -> None:
        # Morphine's loading_doses dict omits cats (clinical preference
        # is to skip the loading dose or use a very low one). So the
        # cat result should have no loading-dose panel.
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="morphine",
            adjunct_slugs=(),
            doses={"morphine": 0.08},
            concentrations_ug_per_ml={"morphine": 100.0},
        )
        result = compute_analgesia(inputs)
        loading = result.drug_results[0].loading_dose_results
        assert loading == ()


# ---------------------------------------------------------------------------
# End-to-end POST through the router.
# ---------------------------------------------------------------------------


class TestRouterEndToEnd:
    def test_get_renders_form(self) -> None:
        r = client.get("/analgesia-cri")
        assert r.status_code == 200
        body = r.text
        assert "Analgesia CRI" in body
        # All three opioid radio options appear in the form.
        assert 'value="fentanyl"' in body
        assert 'value="morphine"' in body
        assert 'value="hydromorphone"' in body
        # Ketamine checkbox appears.
        assert 'name="adjunct_ketamine"' in body

    def test_post_full_page_returns_result(self) -> None:
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "opioid_slug": "fentanyl",
                "dose_fentanyl": "5",
                "concentration_fentanyl": "5",
            },
        )
        assert r.status_code == 200
        # 20 × 5 / 5 = 20 mL/hr.
        assert "20.00" in r.text

    def test_post_htmx_returns_partial_only(self) -> None:
        # HTMX header → only the result partial returns, not the full
        # page. Ketamine markup must not appear in the partial when
        # the checkbox isn't set.
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "opioid_slug": "fentanyl",
                "dose_fentanyl": "5",
                "concentration_fentanyl": "5",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        # The partial has the result wrapper but not the form fieldset.
        assert "Fentanyl" in r.text
        assert 'name="adjunct_ketamine"' not in r.text
        # No ketamine card.
        assert "Ketamine" not in r.text

    def test_post_with_ketamine_renders_both_cards(self) -> None:
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "opioid_slug": "fentanyl",
                "adjunct_ketamine": "on",
                "dose_fentanyl": "5",
                "concentration_fentanyl": "5",
                "dose_ketamine": "2",
                "concentration_ketamine": "2000",
            },
            headers={"HX-Request": "true"},
        )
        body = r.text
        assert "Fentanyl" in body
        assert "Ketamine" in body
        # Pump rates: fentanyl 20 mL/hr, ketamine 1.2 mL/hr.
        assert "20.00" in body
        assert "1.20" in body

    def test_post_with_invalid_weight_shows_placeholder(self) -> None:
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "",
                "weight_unit": "kg",
                "species": "dog",
                "opioid_slug": "fentanyl",
            },
        )
        assert r.status_code == 200
        # Either a placeholder or a global warning about weight.
        assert "weight" in r.text.lower()

    def test_post_morphine_for_cat_renders_dysphoria_warning(self) -> None:
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "4",
                "weight_unit": "kg",
                "species": "cat",
                "opioid_slug": "morphine",
                "dose_morphine": "0.08",
                "concentration_morphine": "100",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "dysphoria" in r.text.lower()

    def test_post_with_pounds_weight_converts(self) -> None:
        # Confirm the lb → kg conversion in the router.
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "44.0922",
                "weight_unit": "lb",
                "species": "dog",
                "opioid_slug": "fentanyl",
                "dose_fentanyl": "5",
                "concentration_fentanyl": "5",
            },
            headers={"HX-Request": "true"},
        )
        # 44.09 lb ≈ 20 kg → same 20 mL/hr.
        assert "20.00" in r.text

    def test_form_renders_lidocaine_species_restriction_markup(self) -> None:
        # The form must carry the data-species-restriction attribute
        # on the lidocaine card and the .species-restriction-note
        # paragraph so the CSS :has() rule can gray it out for cats.
        # This is the visual hook — the engine still enforces the
        # restriction at compute time.
        r = client.get("/analgesia-cri")
        body = r.text
        assert 'data-species-restriction="dog"' in body
        assert "species-restriction-note" in body
        assert "Not used in cats" in body

    def test_post_cat_with_lidocaine_returns_global_warning(self) -> None:
        # End-to-end: cat patient + lidocaine toggled on → global
        # warning surfaces, lidocaine drug card does not appear.
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "4",
                "weight_unit": "kg",
                "species": "cat",
                "opioid_slug": "fentanyl",
                "adjunct_lidocaine": "on",
                "dose_fentanyl": "5",
                "concentration_fentanyl": "5",
                "dose_lidocaine": "1.5",
                "concentration_lidocaine": "4000",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        # Global warning surfaces the skipped drug by name.
        assert "Lidocaine CRI is restricted" in r.text
        # The lidocaine drug-result card (h2 with the display name)
        # must not render — only the global warning mentions lidocaine.
        assert '<h2 style="margin: 0; font-size: 1.25rem;">Lidocaine' not in r.text

    def test_post_dog_with_all_four_adjuncts(self) -> None:
        # Full end-to-end: opioid + ketamine + lidocaine + dex on a
        # dog. All four cards must render with correct pump rates.
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "opioid_slug": "fentanyl",
                "adjunct_ketamine": "on",
                "adjunct_lidocaine": "on",
                "adjunct_dexmedetomidine": "on",
                "dose_fentanyl": "5",
                "concentration_fentanyl": "5",
                "dose_ketamine": "2",
                "concentration_ketamine": "2000",
                "dose_lidocaine": "1.5",
                "concentration_lidocaine": "4000",
                "dose_dexmedetomidine": "0.5",
                "concentration_dexmedetomidine": "4",
            },
            headers={"HX-Request": "true"},
        )
        body = r.text
        # Pump rates: fentanyl 20, ketamine 1.2, lidocaine 7.5, dex 2.5.
        assert "20.00" in body  # fentanyl
        assert "1.20" in body  # ketamine
        assert "7.50" in body  # lidocaine
        assert "2.50" in body  # dex


# ---------------------------------------------------------------------------
# Spec catalog lookup — make sure the slug-to-spec map covers all
# known specs and rejects unknown slugs cleanly.
# ---------------------------------------------------------------------------


class TestOpioidFreeComposition:
    """The opioid backbone is optional. The user can submit opioid_slug
    = 'none' (the sentinel for opioid-free composition) and compose
    from adjuncts alone — KL (ketamine + lidocaine), DLK (dex +
    lidocaine + ketamine), or single-adjunct monotherapy via the
    builder."""

    def test_kl_per_drug_dog(self) -> None:
        # Opioid-free KL: ketamine + lidocaine, no opioid card in
        # the result. Computes both adjuncts at their own pump rates.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="none",
            adjunct_slugs=("ketamine", "lidocaine"),
            doses={"ketamine": 2.0, "lidocaine": 1.5},
            concentrations_ug_per_ml={"ketamine": 2000.0, "lidocaine": 4000.0},
        )
        result = compute_analgesia(inputs)
        assert result.valid
        slugs = [r.spec.slug for r in result.drug_results]
        assert "ketamine" in slugs
        assert "lidocaine" in slugs
        # No opioid cards.
        assert all(r.spec.role != "opioid" for r in result.drug_results)

    def test_dlk_per_drug_dog(self) -> None:
        # Opioid-free DLK: dex + lidocaine + ketamine. All three
        # adjuncts present; no opioid.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="none",
            adjunct_slugs=("ketamine", "lidocaine", "dexmedetomidine"),
            doses={"ketamine": 2.0, "lidocaine": 1.5, "dexmedetomidine": 0.5},
            concentrations_ug_per_ml={
                "ketamine": 2000.0,
                "lidocaine": 4000.0,
                "dexmedetomidine": 4.0,
            },
        )
        result = compute_analgesia(inputs)
        assert result.valid
        slugs = [r.spec.slug for r in result.drug_results]
        assert slugs == ["ketamine", "lidocaine", "dexmedetomidine"]

    def test_dlk_combined_bag_dog(self) -> None:
        # Combined-bag DLK: one bag, three drugs, no opioid.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="none",
            adjunct_slugs=("ketamine", "lidocaine", "dexmedetomidine"),
            doses={"ketamine": 10.0, "lidocaine": 1.5, "dexmedetomidine": 0.5},
            concentrations_ug_per_ml={},
            prep_mode="combined_bag",
            bag_volume_ml=500.0,
            shared_pump_rate_ml_per_kg_per_hr=1.0,
        )
        result = compute_analgesia(inputs)
        assert result.valid
        assert result.combined_bag is not None
        slugs = [r.spec.slug for r in result.combined_bag.drug_recipes]
        assert "ketamine" in slugs
        assert "lidocaine" in slugs
        assert "dexmedetomidine" in slugs
        assert all(
            r.spec.role != "opioid" for r in result.combined_bag.drug_recipes
        )

    def test_opioid_free_with_no_adjuncts_warns(self) -> None:
        # Opioid-free + no adjuncts toggled = nothing to compute.
        # Engine must surface a clear "select at least one drug"
        # warning rather than silently computing an empty result.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="none",
            adjunct_slugs=(),
            doses={},
            concentrations_ug_per_ml={},
        )
        result = compute_analgesia(inputs)
        assert not result.valid
        combined = " ".join(result.global_warnings).lower()
        assert "at least one drug" in combined

    def test_cat_opioid_free_lidocaine_only_skipped(self) -> None:
        # Cat patient + opioid-free + only-lidocaine adjunct → species
        # gating drops lidocaine, leaving zero selected → validation
        # warning. Both the species gating and the empty-selection
        # warning should appear.
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="none",
            adjunct_slugs=("lidocaine",),
            doses={"lidocaine": 1.5},
            concentrations_ug_per_ml={"lidocaine": 4000.0},
        )
        result = compute_analgesia(inputs)
        assert not result.valid
        combined = " ".join(result.global_warnings).lower()
        assert "lidocaine" in combined  # species gating
        assert "at least one drug" in combined  # empty selection

    def test_opioid_required_still_works(self) -> None:
        # Backwards compatibility: opioid-only (no adjuncts) still
        # works — the "select at least one drug" check doesn't fire
        # when an opioid is selected.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=(),
            doses={"fentanyl": 5.0},
            concentrations_ug_per_ml={"fentanyl": 5.0},
        )
        result = compute_analgesia(inputs)
        assert result.valid
        assert len(result.drug_results) == 1


class TestOpioidFreeRouter:
    def test_get_form_renders_none_radio(self) -> None:
        r = client.get("/analgesia-cri")
        body = r.text
        # 4th radio for opioid-free composition.
        assert 'name="opioid_slug" value="none"' in body
        # Help copy mentions the supported compositions.
        assert "opioid-free" in body

    def test_query_param_opioid_none(self) -> None:
        # /analgesia-cri?opioid=none preselects the None radio.
        r = client.get("/analgesia-cri?opioid=none&adjuncts=ketamine,lidocaine")
        body = r.text
        assert 'name="opioid_slug" value="none" checked' in body
        assert 'name="adjunct_ketamine" checked' in body
        assert 'name="adjunct_lidocaine" checked' in body

    def test_post_opioid_free_dlk_dog(self) -> None:
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "opioid_slug": "none",
                "adjunct_ketamine": "on",
                "adjunct_lidocaine": "on",
                "adjunct_dexmedetomidine": "on",
                "dose_ketamine": "2",
                "concentration_ketamine": "2000",
                "dose_lidocaine": "1.5",
                "concentration_lidocaine": "4000",
                "dose_dexmedetomidine": "0.5",
                "concentration_dexmedetomidine": "4",
            },
            headers={"HX-Request": "true"},
        )
        body = r.text
        # All three adjunct pump rates present.
        assert "1.20" in body  # ketamine
        assert "7.50" in body  # lidocaine
        assert "2.50" in body  # dex
        # No opioid card.
        assert '<h2 style="margin: 0; font-size: 1.25rem;">Fentanyl' not in body
        assert '<h2 style="margin: 0; font-size: 1.25rem;">Morphine' not in body

    def test_post_opioid_free_empty_selection_warns(self) -> None:
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "opioid_slug": "none",
            },
            headers={"HX-Request": "true"},
        )
        body = r.text
        assert "at least one drug" in body


class TestSpecLookup:
    def test_get_spec_returns_none_for_unknown(self) -> None:
        assert get_spec("nonexistent-drug") is None

    def test_all_specs_in_spec_by_slug(self) -> None:
        for spec in OPIOID_SPECS + ADJUNCT_SPECS:
            assert SPEC_BY_SLUG[spec.slug] is spec


# ---------------------------------------------------------------------------
# Phase 3: combined-bag mode. Math, mode-switching, /mlk redirect.
# ---------------------------------------------------------------------------


class TestPhase3CombinedBagMath:
    def test_mlk_classical_recipe_matches_lukasik(self) -> None:
        # 20 kg dog × 500 mL bag at 1 mL/kg/hr = 20 mL/hr → 25 hr/bag.
        # MLK published doses: morphine 0.2 mg/kg/hr, lidocaine
        # 1.5 mg/kg/hr, ketamine 10 µg/kg/min (the MLK protocol uses
        # the higher 10 µg/kg/min, not the analgesic 2 µg/kg/min).
        # Expected stock volumes (per Lukasik 2015):
        #   Morphine 100 mg → 20 mL of 5 mg/mL stock
        #   Lidocaine 750 mg → 37.5 mL of 20 mg/mL stock
        #   Ketamine 300 mg → 3 mL of 100 mg/mL stock
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="morphine",
            adjunct_slugs=("ketamine", "lidocaine"),
            doses={"morphine": 0.2, "ketamine": 10.0, "lidocaine": 1.5},
            concentrations_ug_per_ml={},
            prep_mode="combined_bag",
            bag_volume_ml=500.0,
            shared_pump_rate_ml_per_kg_per_hr=1.0,
        )
        result = compute_analgesia(inputs)
        assert result.valid
        cb = result.combined_bag
        assert cb is not None
        assert cb.pump_rate_ml_per_hr == pytest.approx(20.0, rel=1e-4)
        assert cb.hours_per_bag == pytest.approx(25.0, rel=1e-4)

        recipes_by_slug = {r.spec.slug: r for r in cb.drug_recipes}
        assert recipes_by_slug["morphine"].ml_of_stock_to_add == pytest.approx(20.0, rel=1e-3)
        assert recipes_by_slug["lidocaine"].ml_of_stock_to_add == pytest.approx(37.5, rel=1e-3)
        assert recipes_by_slug["ketamine"].ml_of_stock_to_add == pytest.approx(3.0, rel=1e-3)

        assert cb.total_stock_volume_ml == pytest.approx(60.5, rel=1e-3)
        assert cb.adjusted_carrier_ml == pytest.approx(439.5, rel=1e-3)

    def test_combined_bag_with_opioid_only(self) -> None:
        # No adjuncts — opioid-only bag. 20 kg × fentanyl 5 µg/kg/hr ×
        # 25 hr / 50 µg/mL stock = 50 mL of stock fentanyl per bag.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=(),
            doses={"fentanyl": 5.0},
            concentrations_ug_per_ml={},
            prep_mode="combined_bag",
            bag_volume_ml=500.0,
            shared_pump_rate_ml_per_kg_per_hr=1.0,
        )
        result = compute_analgesia(inputs)
        cb = result.combined_bag
        assert cb is not None
        assert len(cb.drug_recipes) == 1
        assert cb.drug_recipes[0].spec.slug == "fentanyl"
        # 20 × 5 × 25 = 2500 µg → 2500 / 50 = 50 mL.
        assert cb.drug_recipes[0].ml_of_stock_to_add == pytest.approx(50.0, rel=1e-3)

    def test_combined_bag_cat_skips_lidocaine(self) -> None:
        # Species gating works in combined-bag mode too: cat patient
        # with lidocaine toggled drops lidocaine, surfaces a global
        # warning, computes the rest.
        inputs = AnalgesiaBuilderInputs(
            weight_value=4.0,
            weight_unit=WeightUnit.KG,
            species=Species.CAT,
            opioid_slug="hydromorphone",
            adjunct_slugs=("ketamine", "lidocaine"),
            doses={"hydromorphone": 0.02, "ketamine": 2.0, "lidocaine": 1.5},
            concentrations_ug_per_ml={},
            prep_mode="combined_bag",
            bag_volume_ml=250.0,
            shared_pump_rate_ml_per_kg_per_hr=1.0,
        )
        result = compute_analgesia(inputs)
        cb = result.combined_bag
        assert cb is not None
        slugs = [r.spec.slug for r in cb.drug_recipes]
        assert "lidocaine" not in slugs
        assert "hydromorphone" in slugs
        assert "ketamine" in slugs
        assert any("Lidocaine" in w for w in result.global_warnings)


class TestPhase3ModeSwitch:
    def test_per_drug_remains_default(self) -> None:
        # Default prep_mode is per_drug — Phase 2 behavior is unchanged.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=(),
            doses={"fentanyl": 5.0},
            concentrations_ug_per_ml={"fentanyl": 5.0},
        )
        result = compute_analgesia(inputs)
        assert result.prep_mode == "per_drug"
        assert result.combined_bag is None
        assert len(result.drug_results) == 1

    def test_combined_bag_clears_per_drug_results(self) -> None:
        # In combined-bag mode, drug_results is empty; the bag recipe
        # is on combined_bag.
        inputs = AnalgesiaBuilderInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            species=Species.DOG,
            opioid_slug="fentanyl",
            adjunct_slugs=(),
            doses={"fentanyl": 5.0},
            concentrations_ug_per_ml={"fentanyl": 5.0},
            prep_mode="combined_bag",
            bag_volume_ml=500.0,
            shared_pump_rate_ml_per_kg_per_hr=1.0,
        )
        result = compute_analgesia(inputs)
        assert result.prep_mode == "combined_bag"
        assert result.combined_bag is not None
        assert result.drug_results == ()


class TestPhase3RouterAndRedirect:
    def test_mlk_redirects_to_builder(self) -> None:
        r = client.get("/mlk", follow_redirects=False)
        assert r.status_code == 301
        loc = r.headers["location"]
        # Redirect target carries the MLK protocol pre-selection.
        assert loc.startswith("/analgesia-cri")
        assert "prep_mode=combined_bag" in loc
        assert "opioid=morphine" in loc
        assert "adjuncts=ketamine" in loc
        assert "lidocaine" in loc

    def test_mlk_redirect_landing_has_mlk_preselected(self) -> None:
        # Following the redirect lands on the multi-modal builder
        # with combined-bag mode and the MLK protocol drugs checked.
        r = client.get("/mlk", follow_redirects=True)
        assert r.status_code == 200
        body = r.text
        assert 'name="prep_mode" value="combined_bag" checked' in body
        assert 'name="opioid_slug" value="morphine" checked' in body
        assert 'name="adjunct_ketamine" checked' in body
        assert 'name="adjunct_lidocaine" checked' in body
        # Ketamine but not dexmedetomidine.
        assert 'name="adjunct_dexmedetomidine" checked' not in body

    def test_query_params_preselect_state(self) -> None:
        # Direct URL with query params should work the same as the
        # /mlk redirect target.
        r = client.get(
            "/analgesia-cri?prep_mode=combined_bag&opioid=hydromorphone&adjuncts=ketamine,dexmedetomidine"
        )
        assert r.status_code == 200
        body = r.text
        assert 'name="prep_mode" value="combined_bag" checked' in body
        assert 'name="opioid_slug" value="hydromorphone" checked' in body
        assert 'name="adjunct_ketamine" checked' in body
        assert 'name="adjunct_dexmedetomidine" checked' in body
        assert 'name="adjunct_lidocaine" checked' not in body

    def test_query_params_silently_drop_unknown_slugs(self) -> None:
        # Unknown opioid → falls back to default. Unknown adjunct
        # is silently dropped.
        r = client.get("/analgesia-cri?opioid=heroin&adjuncts=bogus,ketamine")
        assert r.status_code == 200
        body = r.text
        # Default fentanyl, only known adjunct (ketamine) preselected.
        assert 'name="opioid_slug" value="fentanyl" checked' in body
        assert 'name="adjunct_ketamine" checked' in body

    def test_combined_bag_post_through_router(self) -> None:
        # End-to-end: combined-bag MLK math via the actual router.
        r = client.post(
            "/analgesia-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "opioid_slug": "morphine",
                "adjunct_ketamine": "on",
                "adjunct_lidocaine": "on",
                "dose_morphine": "0.2",
                "dose_ketamine": "10",
                "dose_lidocaine": "1.5",
                "prep_mode": "combined_bag",
                "bag_volume_ml": "500",
                "shared_pump_rate_ml_per_kg_per_hr": "1.0",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        body = r.text
        # Headline pump rate 20 mL/hr.
        assert "20.00" in body
        # Stock volumes for the three drugs.
        assert "37.50" in body  # lidocaine
        assert "3.00" in body  # ketamine
        # Combined-bag recipe card title.
        assert "Combined-bag recipe" in body
