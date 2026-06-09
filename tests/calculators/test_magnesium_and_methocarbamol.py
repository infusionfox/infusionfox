"""Tests for magnesium sulfate and methocarbamol CRIs.

Both reuse the engine's existing MG_PER_KG_PER_HR unit (no engine
work). Both follow the fentanyl pattern: concentration presets with
weight bands but no combined bag-prep UI (typical syringe-pump
workflow). Both carry significant safety surface (hypotension with
rapid push, drug-specific accumulation risks, monitoring
requirements) verified individually.

Categorization:
- magnesium sulfate → Cardiology (primary CRI indication is
  refractory ventricular arrhythmia)
- methocarbamol → Emergency (tetanus, permethrin toxicity,
  tremorogenic mycotoxicoses — first Emergency-section drug
  alongside the procedural calculators)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DRUGS,
    MAGNESIUM_SULFATE,
    METHOCARBAMOL,
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


# ---------------------------------------------------------------------------
# Magnesium sulfate
# ---------------------------------------------------------------------------


class TestMagnesiumSulfateRegistration:
    def test_in_catalog(self):
        assert MAGNESIUM_SULFATE in DRUGS
        assert get_drug("magnesium-sulfate") is MAGNESIUM_SULFATE

    def test_in_cardiology_section(self):
        assert MAGNESIUM_SULFATE.category == "Cardiology"
        by_cat = drugs_by_category()
        assert MAGNESIUM_SULFATE in by_cat["Cardiology"]


class TestMagnesiumSulfateDoseConfig:
    def test_dose_unit(self):
        assert MAGNESIUM_SULFATE.dose_unit == DoseUnit.MG_PER_KG_PER_HR

    def test_dog_range(self):
        rng = MAGNESIUM_SULFATE.dose_ranges[Species.DOG]
        assert rng.min == 5.0
        assert rng.max == 50.0
        # Above 30 mg/kg/hr the cumulative-daily-dose margin gets tight.
        assert rng.caution_threshold == 30.0

    def test_cat_range_lower_caution(self):
        # Cats: sparser published CRI data, lower caution threshold.
        rng = MAGNESIUM_SULFATE.dose_ranges[Species.CAT]
        assert rng.caution_threshold == 25.0


class TestMagnesiumSulfateSafetyLanguage:
    def test_warning_mentions_hypotension(self):
        warning = MAGNESIUM_SULFATE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "hypotension" in warning

    def test_warning_mentions_av_block(self):
        warning = MAGNESIUM_SULFATE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "av" in warning  # AV-block

    def test_warning_mentions_renal_failure(self):
        warning = MAGNESIUM_SULFATE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "renal failure" in warning

    def test_warning_mentions_patellar_reflex_surveillance(self):
        # The earliest objective sign of hypermagnesemia — Plumb's-cited.
        warning = MAGNESIUM_SULFATE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "patellar reflex" in warning


class TestMagnesiumSulfateMath:
    def test_canonical_20kg_dog(self):
        # 20 kg × 25 mg/kg/hr × 1000 ÷ 50000 µg/mL = 10.0 mL/hr.
        result = compute(
            MAGNESIUM_SULFATE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=25.0,
                concentration_ug_per_ml=50000.0,  # 50 mg/mL
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(10.0)

    def test_small_cat_dilute_prep(self):
        # 3 kg × 10 mg/kg/hr × 1000 ÷ 25000 = 1.2 mL/hr.
        result = compute(
            MAGNESIUM_SULFATE,
            CalcInputs(
                weight_value=3.0,
                weight_unit=WeightUnit.KG,
                dose=10.0,
                concentration_ug_per_ml=25000.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(1.2)

    def test_high_dose(self):
        # 20 × 40 × 1000 / 50000 = 16 mL/hr. (Above caution threshold
        # but within range.)
        result = compute(
            MAGNESIUM_SULFATE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=40.0,
                concentration_ug_per_ml=50000.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(16.0)


class TestMagnesiumSulfateAutoRecommendation:
    def test_three_tiers(self):
        assert len(MAGNESIUM_SULFATE.concentration_presets) == 3
        concs = sorted(
            [p.concentration_ug_per_ml for p in MAGNESIUM_SULFATE.concentration_presets],
            reverse=True,
        )
        assert concs == [100000, 50000, 25000]

    def test_large_patient_recommended_100mg_per_ml(self):
        recommended = next(
            p for p in MAGNESIUM_SULFATE.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 20)
            and (p.weight_max_kg is None or p.weight_max_kg > 20)
        )
        assert recommended.concentration_ug_per_ml == 100000  # 100 mg/mL


class TestMagnesiumSulfateLoadingDose:
    def test_one_loading_scenario(self):
        assert len(MAGNESIUM_SULFATE.loading_doses) == 1

    def test_ventricular_arrhythmia_range(self):
        ld = MAGNESIUM_SULFATE.loading_doses[0]
        assert "arrhythmia" in ld.label.lower() or "ventricular" in ld.label.lower()
        # 25-50 mg/kg IV slowly per Silverstein SACCM.
        assert ld.dose_per_kg[Species.DOG] == (25.0, 50.0)
        assert ld.dose_per_kg[Species.CAT] == (25.0, 50.0)
        assert ld.matches_cri_rate is False


class TestMagnesiumSulfateRoute:
    def test_form_renders(self):
        r = client.get("/magnesium-sulfate")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Magnesium Sulfate CRI</h1>" in body
        assert ">Cardiology<" in body

    def test_compute_endpoint(self):
        r = client.post(
            "/magnesium-sulfate/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "25",
                "concentration_ug_per_ml": "50000",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "10.00" in r.text
        # Formula caption renders mg/kg/hr.
        assert "mg/kg/hr" in r.text


# ---------------------------------------------------------------------------
# Methocarbamol
# ---------------------------------------------------------------------------


class TestMethocarbamolRegistration:
    def test_in_catalog(self):
        assert METHOCARBAMOL in DRUGS
        assert get_drug("methocarbamol") is METHOCARBAMOL

    def test_in_emergency_section(self):
        assert METHOCARBAMOL.category == "Emergency"
        by_cat = drugs_by_category()
        assert METHOCARBAMOL in by_cat["Emergency"]


class TestMethocarbamolDoseConfig:
    def test_dose_unit(self):
        assert METHOCARBAMOL.dose_unit == DoseUnit.MG_PER_KG_PER_HR

    def test_dog_range(self):
        rng = METHOCARBAMOL.dose_ranges[Species.DOG]
        assert rng.min == 5.0
        assert rng.max == 15.0
        # 12 mg/kg/hr × 24 hr = 288 mg/kg/day, comfortably under
        # the 330 ceiling. Above 12 narrows the 24-hour margin.
        assert rng.caution_threshold == 12.0

    def test_cat_range_same(self):
        rng = METHOCARBAMOL.dose_ranges[Species.CAT]
        assert rng.min == 5.0
        assert rng.max == 15.0
        assert rng.caution_threshold == 12.0


class TestMethocarbamolSafetyLanguage:
    def test_dog_warning_mentions_daily_dose_ceiling(self):
        warning = METHOCARBAMOL.dose_ranges[Species.DOG].persistent_warning
        # Plumb's 330 mg/kg/day total daily dose ceiling.
        assert "330 mg/kg/day" in warning

    def test_dog_warning_mentions_hypotension(self):
        warning = METHOCARBAMOL.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "hypotension" in warning

    def test_dog_warning_mentions_peg_renal_caution(self):
        # PEG-300 vehicle accumulates in renal failure.
        warning = METHOCARBAMOL.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "polyethylene glycol" in warning or "peg" in warning
        assert "renal failure" in warning

    def test_cat_warning_mentions_permethrin(self):
        # Primary feline indication.
        warning = METHOCARBAMOL.dose_ranges[Species.CAT].persistent_warning.lower()
        assert "permethrin" in warning

    def test_indications_mention_tetanus_and_toxicoses(self):
        indications = METHOCARBAMOL.indications_summary.lower()
        for term in ("tetanus", "permethrin", "strychnine"):
            assert term in indications


class TestMethocarbamolMath:
    def test_canonical_20kg_dog(self):
        # 20 kg × 10 mg/kg/hr × 1000 ÷ 20000 µg/mL = 10.0 mL/hr.
        result = compute(
            METHOCARBAMOL,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=10.0,
                concentration_ug_per_ml=20000.0,  # 20 mg/mL
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(10.0)

    def test_cat_permethrin_scenario(self):
        # 4 kg permethrin-toxicity cat at maintenance dose:
        # 4 × 10 × 1000 / 10000 = 4 mL/hr (on 10 mg/mL dilute prep).
        result = compute(
            METHOCARBAMOL,
            CalcInputs(
                weight_value=4.0,
                weight_unit=WeightUnit.KG,
                dose=10.0,
                concentration_ug_per_ml=10000.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(4.0)


class TestMethocarbamolAutoRecommendation:
    def test_three_tiers(self):
        assert len(METHOCARBAMOL.concentration_presets) == 3
        concs = sorted(
            [p.concentration_ug_per_ml for p in METHOCARBAMOL.concentration_presets],
            reverse=True,
        )
        assert concs == [50000, 20000, 10000]


class TestMethocarbamolLoadingDose:
    def test_three_loading_scenarios(self):
        assert len(METHOCARBAMOL.loading_doses) == 3

    def test_tetanus_loading_range(self):
        ld = METHOCARBAMOL.loading_doses[0]
        assert "tetanus" in ld.label.lower() or "strychnine" in ld.label.lower()
        # 55–220 mg/kg IV slowly per Plumb's label.
        assert ld.dose_per_kg[Species.DOG] == (55.0, 220.0)
        assert ld.dose_per_kg[Species.CAT] == (55.0, 220.0)
        assert ld.matches_cri_rate is False

    def test_pyrethrin_loading_range(self):
        ld = METHOCARBAMOL.loading_doses[1]
        assert "pyrethrin" in ld.label.lower() or "pyrethroid" in ld.label.lower()
        # 40–80 mg/kg IV slowly per Plumb's extra-label dosing.
        assert ld.dose_per_kg[Species.DOG] == (40.0, 80.0)
        assert ld.dose_per_kg[Species.CAT] == (40.0, 80.0)
        assert ld.matches_cri_rate is False

    def test_mycotoxin_loading_range(self):
        ld = METHOCARBAMOL.loading_doses[2]
        assert "mycotoxin" in ld.label.lower()
        # 11–35 mg/kg IV bolus q2–4h per Plumb's extra-label case report.
        assert ld.dose_per_kg[Species.DOG] == (11.0, 35.0)
        assert ld.dose_per_kg[Species.CAT] == (11.0, 35.0)
        assert ld.matches_cri_rate is False

    def test_loading_note_mentions_administration_cap(self):
        # 2 mL/min stock administration cap (Plumb's) appears in the
        # tetanus and pyrethrin loading descriptions.
        for ld in METHOCARBAMOL.loading_doses[:2]:
            assert "2 mL" in ld.description or "2 ml" in ld.description.lower()


class TestMethocarbamolRoute:
    def test_form_renders(self):
        r = client.get("/methocarbamol")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Methocarbamol CRI</h1>" in body
        assert ">Emergency<" in body

    def test_compute_endpoint(self):
        r = client.post(
            "/methocarbamol/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "10",
                "concentration_ug_per_ml": "20000",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "10.00" in r.text


class TestNeitherSupportsPrint:
    """Neither is a vasopressor — keep print machinery off by default.
    Tim can opt in later if ICU bedside reference proves useful for
    either."""

    def test_magnesium_print_off(self):
        assert MAGNESIUM_SULFATE.supports_print is False
        body = client.get("/magnesium-sulfate").text
        assert "calculator-print-btn" not in body

    def test_methocarbamol_print_off(self):
        assert METHOCARBAMOL.supports_print is False
        body = client.get("/methocarbamol").text
        assert "calculator-print-btn" not in body
