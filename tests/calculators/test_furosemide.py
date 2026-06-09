"""Tests for furosemide CRI.

Furosemide joins the Cardiology section alongside esmolol, lidocaine
antiarrhythmic, magnesium sulfate, and nitroprusside. Loop diuretic
for refractory CHF, acute pulmonary edema, and select oliguric AKI.
CRI delivery is preferred over intermittent bolus for severe cases
(Adin et al. 2003 — smoother diuresis, less ototoxicity, better
natriuretic efficiency).

Engine reuses MG_PER_KG_PER_HR.

Species asymmetry: cats more prone to dehydration / hypokalemia / prerenal
azotemia → lower upper bound (1 vs 2 mg/kg/hr) and lower caution
threshold (0.75 vs 1.0).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DRUGS,
    FUROSEMIDE,
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


class TestFurosemideRegistration:
    def test_in_catalog(self):
        assert FUROSEMIDE in DRUGS
        assert get_drug("furosemide") is FUROSEMIDE

    def test_in_cardiology(self):
        assert FUROSEMIDE.category == "Cardiology"
        assert FUROSEMIDE in drugs_by_category()["Cardiology"]


class TestFurosemideDoseConfig:
    def test_dose_unit(self):
        assert FUROSEMIDE.dose_unit == DoseUnit.MG_PER_KG_PER_HR

    def test_dog_range(self):
        rng = FUROSEMIDE.dose_ranges[Species.DOG]
        assert rng.min == 0.25
        assert rng.max == 2.0
        assert rng.caution_threshold == 1.0

    def test_cat_range_more_conservative(self):
        rng = FUROSEMIDE.dose_ranges[Species.CAT]
        assert rng.min == 0.25
        # Cat max is HALF the dog max — cats more prone to
        # dehydration/electrolyte derangement.
        assert rng.max == 1.0
        assert rng.caution_threshold == 0.75


class TestFurosemideSafetyLanguage:
    def test_dog_warning_mentions_electrolytes(self):
        warning = FUROSEMIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        # Specific electrolytes called out.
        assert "hypokalemia" in warning
        assert "hypomagnesemia" in warning

    def test_dog_warning_mentions_prerenal_azotemia(self):
        warning = FUROSEMIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "prerenal azotemia" in warning or "azotemia" in warning

    def test_dog_warning_mentions_ototoxicity(self):
        warning = FUROSEMIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "ototox" in warning

    def test_dog_warning_mentions_hypoalbuminemia(self):
        warning = FUROSEMIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "hypoalbuminemia" in warning

    def test_dog_warning_mentions_nephrotoxic_interactions(self):
        warning = FUROSEMIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        # Aminoglycosides and NSAIDs are the textbook co-administration
        # concerns.
        assert "aminoglycoside" in warning or "nsaid" in warning

    def test_cat_warning_emphasizes_dehydration_susceptibility(self):
        warning = FUROSEMIDE.dose_ranges[Species.CAT].persistent_warning
        # MORE PRONE caps is intentional.
        assert "MORE PRONE" in warning
        assert "dehydration" in warning.lower()

    def test_cat_warning_mentions_hcm_concern(self):
        warning = FUROSEMIDE.dose_ranges[Species.CAT].persistent_warning.lower()
        # HCM cats at elevated arrhythmia risk from hypokalemia.
        assert "hcm" in warning


class TestFurosemideMath:
    def test_canonical_20kg_dog(self):
        # 20 kg × 0.5 mg/kg/hr × 1000 ÷ 2000 µg/mL = 5.0 mL/hr.
        result = compute(
            FUROSEMIDE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=0.5,
                concentration_ug_per_ml=2000.0,
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(5.0)

    def test_large_dog_concentrated_prep(self):
        # 30 kg × 0.5 × 1000 / 5000 = 3 mL/hr on 5 mg/mL prep.
        result = compute(
            FUROSEMIDE,
            CalcInputs(
                weight_value=30.0,
                weight_unit=WeightUnit.KG,
                dose=0.5,
                concentration_ug_per_ml=5000.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(3.0)

    def test_small_cat_dilute_prep(self):
        # 4 kg × 0.5 × 1000 / 1000 = 2 mL/hr on 1 mg/mL dilute prep.
        result = compute(
            FUROSEMIDE,
            CalcInputs(
                weight_value=4.0,
                weight_unit=WeightUnit.KG,
                dose=0.5,
                concentration_ug_per_ml=1000.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(2.0)

    def test_high_dose_dog(self):
        # 20 × 1.5 × 1000 / 2000 = 15 mL/hr at above-caution dose.
        result = compute(
            FUROSEMIDE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=1.5,
                concentration_ug_per_ml=2000.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(15.0)


class TestFurosemideAutoRecommendation:
    def test_three_tiers(self):
        assert len(FUROSEMIDE.concentration_presets) == 3
        concs = sorted(
            [p.concentration_ug_per_ml for p in FUROSEMIDE.concentration_presets],
            reverse=True,
        )
        # 5, 2, 1 mg/mL — more dilute than catecholamines because
        # furosemide's mg/kg/hr × patient kg produces small total
        # mass-per-hour values.
        assert concs == [5000, 2000, 1000]


class TestFurosemideLoadingDose:
    def test_one_loading_scenario(self):
        assert len(FUROSEMIDE.loading_doses) == 1

    def test_loading_dose_range(self):
        ld = FUROSEMIDE.loading_doses[0]
        # 1-4 mg/kg IV slow bolus per Plumb's. Same range both species
        # (one-time bolus); cat conservatism shows up in CRI
        # maintenance, not loading.
        assert ld.dose_per_kg[Species.DOG] == (1.0, 4.0)
        assert ld.dose_per_kg[Species.CAT] == (1.0, 4.0)
        assert ld.matches_cri_rate is False

    def test_loading_note_mentions_slow_administration(self):
        ld = FUROSEMIDE.loading_doses[0]
        # Rapid push raises ototoxicity risk.
        assert "1–2 minutes" in ld.note or "ototoxicity" in ld.note.lower()


class TestFurosemideDilutionNote:
    def test_specifies_nacl_preferred(self):
        note = FUROSEMIDE.dilution_note
        # 0.9% NaCl is the preferred diluent — explicitly called out.
        assert "0.9% NaCl is the preferred diluent" in note or "NaCl is the preferred" in note

    def test_mentions_acidic_solution_incompatibility(self):
        note = FUROSEMIDE.dilution_note.lower()
        # Critical: furosemide precipitates in acidic fluids
        # (lactated Ringer's).
        assert "acidic" in note or "lactated ringer" in note


class TestFurosemideRoute:
    def test_form_renders(self):
        r = client.get("/furosemide")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Furosemide CRI</h1>" in body

    def test_compute_endpoint(self):
        r = client.post(
            "/furosemide/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "0.5",
                "concentration_ug_per_ml": "2000",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "5.00" in r.text
        # Formula uses mg/kg/hr.
        assert "mg/kg/hr" in r.text


class TestFurosemidePrintSupport:
    def test_supports_print(self):
        assert FUROSEMIDE.supports_print is True

    def test_form_renders_print_button(self):
        body = client.get("/furosemide").text
        assert "calculator-print-btn" in body
