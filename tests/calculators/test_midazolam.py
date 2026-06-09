"""Tests for midazolam CRI as a CalculatorConfig.

Midazolam is the first drug in the "Anesthesia & Sedation" category.
Dosed in mg/kg/hr (engine's existing MG_PER_KG_PER_HR unit). Two
loading-dose scenarios: pre-CRI sedation loading and status
epilepticus loading. Cat-specific care: paradoxical excitement risk
and lower caution threshold (0.3 mg/kg/hr vs 0.5 in dogs).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DRUGS,
    MIDAZOLAM,
    drugs_by_category,
    get_drug,
)
from app.calculators.engine import (
    CalcInputs,
    DoseUnit,
    Species,
    WeightUnit,
    compute,
)
from app.main import app

client = TestClient(app)


class TestMidazolamRegistration:
    def test_in_drugs_catalog(self):
        assert MIDAZOLAM in DRUGS
        assert get_drug("midazolam") is MIDAZOLAM

    def test_category_is_anesthesia_sedation(self):
        assert MIDAZOLAM.category == "Anesthesia & Sedation"
        by_cat = drugs_by_category()
        assert MIDAZOLAM in by_cat["Anesthesia & Sedation"]

    def test_dose_unit_mg_per_kg_per_hr(self):
        assert MIDAZOLAM.dose_unit == DoseUnit.MG_PER_KG_PER_HR


class TestMidazolamDoseRanges:
    def test_dog_range(self):
        rng = MIDAZOLAM.dose_ranges[Species.DOG]
        assert rng.min == 0.1
        assert rng.max == 0.5
        # Plumb's published upper limit for sedation/anxiolysis CRI.
        assert rng.caution_threshold == 0.5

    def test_cat_range(self):
        rng = MIDAZOLAM.dose_ranges[Species.CAT]
        assert rng.min == 0.1
        assert rng.max == 0.5
        # Cats get a LOWER caution threshold than dogs — paradoxical
        # excitement and oversedation risk rise faster.
        assert rng.caution_threshold == 0.3

    def test_cat_warning_mentions_paradoxical_excitement(self):
        rng = MIDAZOLAM.dose_ranges[Species.CAT]
        warning = rng.persistent_warning.lower()
        assert "paradoxical" in warning
        assert "excitement" in warning or "disinhibition" in warning

    def test_dog_warning_mentions_respiratory_depression(self):
        rng = MIDAZOLAM.dose_ranges[Species.DOG]
        warning = rng.persistent_warning.lower()
        assert "respiratory depression" in warning

    def test_dog_warning_mentions_dependence_with_prolonged_use(self):
        rng = MIDAZOLAM.dose_ranges[Species.DOG]
        warning = rng.persistent_warning.lower()
        assert "dependence" in warning or "taper" in warning


class TestMidazolamMath:
    """Engine handles MG_PER_KG_PER_HR with the standard ×1000 mg→µg
    conversion factor."""

    def test_canonical_20kg_dog(self):
        # 20 kg × 0.25 mg/kg/hr × 1000 ÷ 1000 µg/mL = 5.0 mL/hr.
        result = compute(
            MIDAZOLAM,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=0.25,
                concentration_ug_per_ml=1000.0,  # 1 mg/mL
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(5.0)

    def test_small_cat_dilute_prep(self):
        # 3 kg × 0.25 × 1000 ÷ 200 = 3.75 mL/hr.
        result = compute(
            MIDAZOLAM,
            CalcInputs(
                weight_value=3.0,
                weight_unit=WeightUnit.KG,
                dose=0.25,
                concentration_ug_per_ml=200.0,  # 0.2 mg/mL
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(3.75)

    def test_lb_conversion(self):
        # 44 lb ≈ 19.96 kg → ~5 mL/hr at canonical dose.
        result = compute(
            MIDAZOLAM,
            CalcInputs(
                weight_value=44.0,
                weight_unit=WeightUnit.LB,
                dose=0.25,
                concentration_ug_per_ml=1000.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(5.0, rel=1e-2)

    def test_ceiling_dose_20kg_dog(self):
        # 20 × 0.5 × 1000 / 1000 = 10 mL/hr.
        result = compute(
            MIDAZOLAM,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=0.5,
                concentration_ug_per_ml=1000.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(10.0)


class TestMidazolamAutoRecommendation:
    """Three concentration tiers cover the patient-size range."""

    def test_three_tiers(self):
        assert len(MIDAZOLAM.concentration_presets) == 3
        concs = sorted(
            [p.concentration_ug_per_ml for p in MIDAZOLAM.concentration_presets],
            reverse=True,
        )
        # 1 mg/mL, 0.5 mg/mL, 0.2 mg/mL (stored as µg/mL).
        assert concs == [1000, 500, 200]

    def test_large_dog_recommended_1mg_per_ml(self):
        recommended = next(
            p for p in MIDAZOLAM.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 25)
            and (p.weight_max_kg is None or p.weight_max_kg > 25)
        )
        assert recommended.concentration_ug_per_ml == 1000

    def test_medium_patient_recommended_half_mg_per_ml(self):
        # 5 kg → 0.5 mg/mL band.
        recommended = next(
            p for p in MIDAZOLAM.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 5)
            and (p.weight_max_kg is None or p.weight_max_kg > 5)
        )
        assert recommended.concentration_ug_per_ml == 500

    def test_small_cat_recommended_0_2_mg_per_ml(self):
        # 2 kg cat → 0.2 mg/mL band.
        recommended = next(
            p for p in MIDAZOLAM.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 2)
            and (p.weight_max_kg is None or p.weight_max_kg > 2)
        )
        assert recommended.concentration_ug_per_ml == 200


class TestMidazolamLoadingDoses:
    """Two loading-dose scenarios: pre-CRI sedation and status."""

    def test_two_loading_scenarios(self):
        assert len(MIDAZOLAM.loading_doses) == 2

    def test_sedation_loading_dose_range(self):
        sedation = next(
            ld for ld in MIDAZOLAM.loading_doses if "sedation" in ld.label.lower()
        )
        dog_range = sedation.dose_per_kg[Species.DOG]
        assert dog_range == (0.1, 0.3)
        cat_range = sedation.dose_per_kg[Species.CAT]
        assert cat_range == (0.1, 0.3)
        assert sedation.display_dose_unit == "mg"

    def test_status_epilepticus_loading_dose_range(self):
        status = next(
            ld for ld in MIDAZOLAM.loading_doses if "status" in ld.label.lower()
        )
        dog_range = status.dose_per_kg[Species.DOG]
        assert dog_range == (0.2, 0.5)
        cat_range = status.dose_per_kg[Species.CAT]
        assert cat_range == (0.2, 0.5)

    def test_sedation_note_mentions_paradoxical_cat_response(self):
        sedation = next(
            ld for ld in MIDAZOLAM.loading_doses if "sedation" in ld.label.lower()
        )
        assert "paradoxical" in sedation.note.lower()

    def test_neither_loading_matches_cri_rate(self):
        # mg/kg loading vs mg/kg/hr CRI — different units, so the
        # "shown prominently as one-to-one with the CRI" UX doesn't fit.
        for ld in MIDAZOLAM.loading_doses:
            assert ld.matches_cri_rate is False


class TestMidazolamTemplateRendering:
    def test_form_renders(self):
        r = client.get("/midazolam")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Midazolam CRI</h1>" in body
        assert "5 mg/mL" in body
        # All three concentration tiers visible.
        assert "1000" in body  # display will be 1 mg/mL but stored value is 1000
        assert "500" in body
        assert "200" in body

    def test_compute_renders_correctly(self):
        r = client.post(
            "/midazolam/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "0.25",
                "concentration_ug_per_ml": "1000",
            },
            headers={"HX-Request": "true"},
        )
        body = r.text
        # 5 mL/hr pump rate.
        assert "5.00" in body
        # mg/kg/hr in formula caption.
        assert "mg/kg/hr" in body

    def test_cat_compute_shows_paradoxical_excitement_warning(self):
        r = client.post(
            "/midazolam/compute",
            data={
                "weight_value": "4",
                "weight_unit": "kg",
                "species": "cat",
                "dose": "0.25",
                "concentration_ug_per_ml": "500",
            },
            headers={"HX-Request": "true"},
        )
        assert "paradoxical" in r.text.lower()

    def test_cat_above_0_3_triggers_caution_note(self):
        r = client.post(
            "/midazolam/compute",
            data={
                "weight_value": "4",
                "weight_unit": "kg",
                "species": "cat",
                "dose": "0.4",
                "concentration_ug_per_ml": "500",
            },
            headers={"HX-Request": "true"},
        )
        # Cat caution threshold is 0.3 (vs dog's 0.5). At 0.4, the
        # caution_note should fire.
        assert "Above 0.3 mg/kg/hr" in r.text

    def test_dog_at_0_4_no_caution_note(self):
        """0.4 is below the dog caution threshold (0.5)."""
        r = client.post(
            "/midazolam/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "0.4",
                "concentration_ug_per_ml": "1000",
            },
            headers={"HX-Request": "true"},
        )
        # The dog caution note's identifying phrase shouldn't appear.
        assert "Above 0.3 mg/kg/hr" not in r.text


class TestMidazolamCatalogPresence:
    def test_appears_in_nav_under_anesthesia_sedation(self):
        from app.nav import nav_index
        groups = nav_index()
        section = groups.get("Anesthesia & Sedation", [])
        hrefs = [e.href for e in section]
        assert "/midazolam" in hrefs
        # Only once — no duplicates from ONE_OFF_CALCULATORS overlap.
        assert hrefs.count("/midazolam") == 1


class TestMidazolamNotAVasopressor:
    """Midazolam is a sedative, not a vasopressor — should NOT have
    the print button machinery."""

    def test_supports_print_default_false(self):
        assert MIDAZOLAM.supports_print is False

    def test_form_lacks_print_button(self):
        body = client.get("/midazolam").text
        assert "calculator-print-btn" not in body
        assert "infusionfox_calculator_print" not in body
