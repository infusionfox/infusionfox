"""Tests for esmolol CRI.

Esmolol joins nitroprusside and magnesium sulfate in the Cardiology
section. Ultra-short-acting selective β1-blocker; RBC-esterase
metabolism (independent of hepatic/renal function). Engine reuses
UG_PER_KG_PER_MIN.

Critical safety surface verified individually:
- Never use as monotherapy in pheochromocytoma (unopposed alpha-
  mediated hypertensive crisis)
- β1-selectivity is lost at high doses → bronchospasm risk rises
  above 150 µg/kg/min
- Negative inotropy in DCM / advanced MMVD
- Additive AV-block / negative inotropy with CCBs
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DRUGS,
    ESMOLOL,
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


class TestEsmololRegistration:
    def test_in_catalog(self):
        assert ESMOLOL in DRUGS
        assert get_drug("esmolol") is ESMOLOL

    def test_in_cardiology(self):
        assert ESMOLOL.category == "Cardiology"
        assert ESMOLOL in drugs_by_category()["Cardiology"]


class TestEsmololDoseConfig:
    def test_dose_unit(self):
        assert ESMOLOL.dose_unit == DoseUnit.UG_PER_KG_PER_MIN

    def test_dog_range(self):
        rng = ESMOLOL.dose_ranges[Species.DOG]
        assert rng.min == 25.0
        assert rng.max == 200.0
        # β1-selectivity diminishes above 150 µg/kg/min.
        assert rng.caution_threshold == 150.0

    def test_cat_range(self):
        rng = ESMOLOL.dose_ranges[Species.CAT]
        assert rng.min == 25.0
        assert rng.max == 200.0
        assert rng.caution_threshold == 150.0


class TestEsmololSafetyLanguage:
    def test_dog_warning_bans_monotherapy_in_pheochromocytoma(self):
        warning = ESMOLOL.dose_ranges[Species.DOG].persistent_warning
        # The "NEVER" emphasis is intentional — unopposed alpha causes
        # hypertensive crisis. Must remain.
        assert "NEVER" in warning
        assert "pheochromocytoma" in warning.lower()
        assert "alpha" in warning.lower()

    def test_dog_warning_mentions_dcm_and_mmvd(self):
        warning = ESMOLOL.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "dcm" in warning
        assert "mmvd" in warning

    def test_dog_warning_mentions_ccb_interaction(self):
        warning = ESMOLOL.dose_ranges[Species.DOG].persistent_warning.lower()
        # Diltiazem and verapamil specifically called out.
        assert "diltiazem" in warning or "verapamil" in warning

    def test_caution_note_mentions_selectivity_loss(self):
        caution = ESMOLOL.dose_ranges[Species.DOG].caution_note.lower()
        assert "selectivity" in caution

    def test_cat_warning_mentions_asthma(self):
        warning = ESMOLOL.dose_ranges[Species.CAT].persistent_warning.lower()
        assert "asthma" in warning
        assert "bronchospasm" in warning

    def test_cat_warning_mentions_hcm_benefit(self):
        warning = ESMOLOL.dose_ranges[Species.CAT].persistent_warning.lower()
        # HCM cats benefit from rate control.
        assert "hcm" in warning


class TestEsmololMath:
    def test_canonical_20kg_dog(self):
        # 20 kg × 50 µg/kg/min × 60 ÷ 5000 µg/mL = 12.0 mL/hr.
        result = compute(
            ESMOLOL,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=50.0,
                concentration_ug_per_ml=5000.0,  # 5 mg/mL
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(12.0)

    def test_large_dog_direct_premix(self):
        # 30 kg × 50 × 60 / 10000 = 9 mL/hr on direct premix.
        result = compute(
            ESMOLOL,
            CalcInputs(
                weight_value=30.0,
                weight_unit=WeightUnit.KG,
                dose=50.0,
                concentration_ug_per_ml=10000.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(9.0)

    def test_small_cat_dilute_prep(self):
        # 4 kg × 50 × 60 / 2000 = 6 mL/hr on 2 mg/mL dilute prep.
        result = compute(
            ESMOLOL,
            CalcInputs(
                weight_value=4.0,
                weight_unit=WeightUnit.KG,
                dose=50.0,
                concentration_ug_per_ml=2000.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(6.0)

    def test_max_dose(self):
        # 20 × 200 × 60 / 5000 = 48 mL/hr at the published ceiling.
        result = compute(
            ESMOLOL,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=200.0,
                concentration_ug_per_ml=5000.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(48.0)


class TestEsmololAutoRecommendation:
    def test_three_tiers(self):
        assert len(ESMOLOL.concentration_presets) == 3
        concs = sorted(
            [p.concentration_ug_per_ml for p in ESMOLOL.concentration_presets],
            reverse=True,
        )
        assert concs == [10000, 5000, 2000]

    def test_large_patient_direct_premix(self):
        # 20 kg → 10 mg/mL premix direct (≥15 kg).
        recommended = next(
            p for p in ESMOLOL.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 20)
            and (p.weight_max_kg is None or p.weight_max_kg > 20)
        )
        assert recommended.concentration_ug_per_ml == 10000

    def test_medium_patient_1_to_1_dilution(self):
        # 5 kg → 5 mg/mL 1:1 dilution band (3-15 kg).
        recommended = next(
            p for p in ESMOLOL.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 5)
            and (p.weight_max_kg is None or p.weight_max_kg > 5)
        )
        assert recommended.concentration_ug_per_ml == 5000

    def test_small_cat_1_to_4_dilution(self):
        # 2 kg cat → 2 mg/mL 1:4 dilution band (<3 kg).
        recommended = next(
            p for p in ESMOLOL.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 2)
            and (p.weight_max_kg is None or p.weight_max_kg > 2)
        )
        assert recommended.concentration_ug_per_ml == 2000


class TestEsmololLoadingDose:
    def test_one_loading_scenario(self):
        assert len(ESMOLOL.loading_doses) == 1

    def test_rate_control_loading_range(self):
        ld = ESMOLOL.loading_doses[0]
        # 50-500 µg/kg IV over 1 min per Plumb's.
        assert ld.dose_per_kg[Species.DOG] == (50.0, 500.0)
        assert ld.dose_per_kg[Species.CAT] == (50.0, 500.0)
        assert ld.matches_cri_rate is False
        # Display unit is µg, not µg/kg/min (loading is mass per kg).
        assert ld.display_dose_unit == "µg"

    def test_loading_note_mentions_acute_hypotension_window(self):
        ld = ESMOLOL.loading_doses[0]
        # Most acute hypotension lives in the loading bolus.
        assert "first minute" in ld.note.lower() or "hypotension" in ld.note.lower()


class TestEsmololRoute:
    def test_form_renders(self):
        r = client.get("/esmolol")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Esmolol CRI</h1>" in body
        assert ">Cardiology<" in body

    def test_compute_endpoint(self):
        r = client.post(
            "/esmolol/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "50",
                "concentration_ug_per_ml": "5000",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "12.00" in r.text
        assert "µg/kg/min" in r.text

    def test_compute_renders_pheochromocytoma_warning(self):
        r = client.post(
            "/esmolol/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "50",
                "concentration_ug_per_ml": "5000",
            },
            headers={"HX-Request": "true"},
        )
        # The "NEVER monotherapy" guard for pheochromocytoma must
        # appear in the result panel (persistent warning).
        assert "pheochromocytoma" in r.text.lower()


class TestEsmololPrintSupport:
    """Esmolol opts into the print machinery — same ICU bedside-
    reference rationale as the other cardiology and vasopressor CRIs."""

    def test_supports_print(self):
        assert ESMOLOL.supports_print is True

    def test_form_renders_print_button(self):
        body = client.get("/esmolol").text
        assert "calculator-print-btn" in body
        assert "infusionfox_calculator_print" in body
