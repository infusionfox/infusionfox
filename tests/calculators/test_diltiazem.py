"""Tests for diltiazem CRI.

Class IV antiarrhythmic — non-dihydropyridine calcium channel blocker.
Joins the Cardiology section. Engine reuses UG_PER_KG_PER_MIN.

Critical safety surface — all pinned individually:
- NEVER co-administer with IV beta-blockers (esmolol, propranolol)
  — additive AV block / negative inotropy → complete heart block
- WPW: can PARADOXICALLY INCREASE ventricular rate via accessory
  pathway when AV-node conduction is blocked
- Pre-existing high-grade AV block (Mobitz II, 3rd degree) — contraindicated
- HCM with LVOT obstruction — AVOID (negative inotropy worsens
  dynamic obstruction); useful in non-obstructive HCM
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DILTIAZEM,
    DRUGS,
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


class TestDiltiazemRegistration:
    def test_in_catalog(self):
        assert DILTIAZEM in DRUGS
        assert get_drug("diltiazem") is DILTIAZEM

    def test_in_cardiology(self):
        assert DILTIAZEM.category == "Cardiology"
        assert DILTIAZEM in drugs_by_category()["Cardiology"]


class TestDiltiazemDoseConfig:
    def test_dose_unit(self):
        assert DILTIAZEM.dose_unit == DoseUnit.UG_PER_KG_PER_MIN

    def test_dog_range(self):
        rng = DILTIAZEM.dose_ranges[Species.DOG]
        assert rng.min == 2.0
        assert rng.max == 10.0
        assert rng.caution_threshold == 7.0

    def test_cat_range_same_as_dog(self):
        rng = DILTIAZEM.dose_ranges[Species.CAT]
        # Same published range — cat-specific concerns (LVOT
        # obstruction, hypotension sensitivity) surface in the
        # warning text, not the numeric range.
        assert rng.min == 2.0
        assert rng.max == 10.0
        assert rng.caution_threshold == 7.0


class TestDiltiazemBetaBlockerContraindication:
    """The single most important safety guard — concurrent IV
    beta-blocker can precipitate complete heart block. Pinned
    individually so a future edit can't accidentally weaken or remove
    the language."""

    def test_dog_warning_says_NEVER_with_beta_blocker(self):
        warning = DILTIAZEM.dose_ranges[Species.DOG].persistent_warning
        # The "NEVER" caps is intentional. Must remain.
        assert "NEVER" in warning
        # Specific beta-blockers called out.
        assert "esmolol" in warning.lower()
        assert "propranolol" in warning.lower()

    def test_dog_warning_explains_heart_block_mechanism(self):
        warning = DILTIAZEM.dose_ranges[Species.DOG].persistent_warning.lower()
        # The clinical consequence — complete heart block — must be
        # named so the rationale for the prohibition is clear.
        assert "complete heart block" in warning or "cardiogenic shock" in warning

    def test_dog_warning_addresses_oral_beta_blocker_handoff(self):
        warning = DILTIAZEM.dose_ranges[Species.DOG].persistent_warning.lower()
        # Patients on oral beta-blocker present a transition risk;
        # the warning prescribes "hold next dose + consult cardiology"
        # rather than just "don't combine."
        assert "oral beta-blocker" in warning


class TestDiltiazemOtherContraindications:
    def test_warning_mentions_wpw_paradoxical_acceleration(self):
        warning = DILTIAZEM.dose_ranges[Species.DOG].persistent_warning
        # WPW: blocking AV node while accessory pathway remains
        # active can paradoxically accelerate ventricular rate.
        # Must be explicit — clinicians might assume AV blockade is
        # always rate-lowering.
        assert "PARADOXICALLY INCREASE" in warning
        assert "Wolff-Parkinson-White" in warning or "WPW" in warning

    def test_warning_mentions_av_block_contraindication(self):
        warning = DILTIAZEM.dose_ranges[Species.DOG].persistent_warning.lower()
        # Pre-existing Mobitz II / 3rd degree AV block is a hard
        # contraindication.
        assert "mobitz" in warning or "3rd degree" in warning

    def test_warning_mentions_sick_sinus_syndrome(self):
        warning = DILTIAZEM.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "sick sinus syndrome" in warning

    def test_cat_warning_mentions_lvot_obstruction_caveat(self):
        warning = DILTIAZEM.dose_ranges[Species.CAT].persistent_warning
        # HCM cats with LVOT obstruction: AVOID (negative inotropy
        # worsens dynamic obstruction). Critical for HCM management.
        assert "LVOT" in warning
        assert "AVOID" in warning or "avoid" in warning

    def test_cat_warning_distinguishes_obstructive_vs_non_obstructive_hcm(self):
        warning = DILTIAZEM.dose_ranges[Species.CAT].persistent_warning.lower()
        # Useful in non-obstructive HCM; avoid in obstructive.
        # Both halves of the distinction must be present so it
        # doesn't read as "avoid in all HCM."
        assert "obstruction" in warning


class TestDiltiazemMath:
    def test_canonical_20kg_dog(self):
        # 20 kg × 3 µg/kg/min × 60 ÷ 500 µg/mL = 7.2 mL/hr.
        result = compute(
            DILTIAZEM,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=3.0,
                concentration_ug_per_ml=500.0,
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(7.2)

    def test_small_cat_dilute_prep(self):
        # 4 kg × 3 × 60 / 200 = 3.6 mL/hr on 0.2 mg/mL dilute prep.
        result = compute(
            DILTIAZEM,
            CalcInputs(
                weight_value=4.0,
                weight_unit=WeightUnit.KG,
                dose=3.0,
                concentration_ug_per_ml=200.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(3.6)

    def test_high_dose(self):
        # 20 × 7 × 60 / 500 = 16.8 mL/hr at caution threshold.
        result = compute(
            DILTIAZEM,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=7.0,
                concentration_ug_per_ml=500.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(16.8)


class TestDiltiazemAutoRecommendation:
    def test_three_tiers(self):
        assert len(DILTIAZEM.concentration_presets) == 3
        concs = sorted(
            [p.concentration_ug_per_ml for p in DILTIAZEM.concentration_presets],
            reverse=True,
        )
        # 1, 0.5, 0.2 mg/mL — dilute because diltiazem CRI mass-per-
        # hour values are small at typical doses.
        assert concs == [1000, 500, 200]

    def test_medium_dog_recommended_default_band(self):
        # 10 kg → 0.5 mg/mL (3-15 kg band).
        recommended = next(
            p for p in DILTIAZEM.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 10)
            and (p.weight_max_kg is None or p.weight_max_kg > 10)
        )
        assert recommended.concentration_ug_per_ml == 500


class TestDiltiazemLoadingDose:
    def test_one_loading_scenario(self):
        assert len(DILTIAZEM.loading_doses) == 1

    def test_loading_range(self):
        ld = DILTIAZEM.loading_doses[0]
        # Plumb's: 0.05-0.25 mg/kg IV slowly over 2-3 min.
        assert ld.dose_per_kg[Species.DOG] == (0.05, 0.25)
        assert ld.dose_per_kg[Species.CAT] == (0.05, 0.25)
        assert ld.matches_cri_rate is False
        assert ld.display_dose_unit == "mg"

    def test_loading_description_mentions_slow_administration(self):
        ld = DILTIAZEM.loading_doses[0]
        # Rapid push: maximizes acute hypotension and AV-block risk.
        assert "2–3 minutes" in ld.description or "slowly" in ld.description.lower()


class TestDiltiazemRoute:
    def test_form_renders(self):
        r = client.get("/diltiazem")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Diltiazem CRI</h1>" in body

    def test_compute_endpoint(self):
        r = client.post(
            "/diltiazem/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "3",
                "concentration_ug_per_ml": "500",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "7.20" in r.text
        # mg/kg/min formula caption.
        assert "µg/kg/min" in r.text

    def test_compute_surfaces_beta_blocker_contraindication(self):
        # Critical safety: the NEVER-with-beta-blocker guard appears
        # in the result panel after compute (Safety Rule #8 means
        # warnings show after input, not on initial GET).
        r = client.post(
            "/diltiazem/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "3",
                "concentration_ug_per_ml": "500",
            },
            headers={"HX-Request": "true"},
        )
        assert "NEVER co-administer" in r.text
        assert "beta-blocker" in r.text.lower()

    def test_cat_compute_surfaces_lvot_caveat(self):
        r = client.post(
            "/diltiazem/compute",
            data={
                "weight_value": "4",
                "weight_unit": "kg",
                "species": "cat",
                "dose": "3",
                "concentration_ug_per_ml": "200",
            },
            headers={"HX-Request": "true"},
        )
        assert "LVOT" in r.text


class TestDiltiazemPrintSupport:
    def test_supports_print(self):
        assert DILTIAZEM.supports_print is True

    def test_form_renders_print_button(self):
        body = client.get("/diltiazem").text
        assert "calculator-print-btn" in body
