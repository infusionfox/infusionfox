"""Morphine and dexmedetomidine standalone CRI calculators.

Added 2026-06 as Phase-2 follow-ons to the multi-modal analgesia
builder. Each drug is a SINGLE_DRUG_CRI CalculatorConfig in
drugs.py; the calculator.html template renders both for free.

The same drug data backs the multi-modal builder via
analgesia_builder.MORPHINE_SPEC and analgesia_builder.DEXMEDETOMIDINE_SPEC,
which source their dose ranges / presets / loading doses from the
CalculatorConfig (FENTANYL_SPEC pattern). These tests pin the
single-source-of-truth wiring along with the route math.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.analgesia_builder import (
    DEXMEDETOMIDINE_SPEC,
    MORPHINE_SPEC,
)
from app.calculators.drugs import DEXMEDETOMIDINE, MORPHINE
from app.calculators.engine import CalcInputs, Species, WeightUnit, compute
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Source-of-truth wiring: the builder specs reference the CalculatorConfig
# fields directly (identity, not copy).
# ---------------------------------------------------------------------------


class TestSpecSourcesFromConfig:
    """The analgesia-builder spec and the standalone CalculatorConfig
    must share the same dose data. If they ever diverge, the builder
    and standalone will disagree on the same drug — a clinical-safety
    consistency requirement."""

    def test_morphine_spec_shares_dose_ranges(self):
        assert MORPHINE_SPEC.dose_ranges is MORPHINE.dose_ranges

    def test_morphine_spec_shares_loading_doses(self):
        assert MORPHINE_SPEC.loading_doses is MORPHINE.loading_doses

    def test_morphine_spec_shares_presets(self):
        assert MORPHINE_SPEC.concentration_presets is MORPHINE.concentration_presets

    def test_dexmedetomidine_spec_shares_dose_ranges(self):
        assert DEXMEDETOMIDINE_SPEC.dose_ranges is DEXMEDETOMIDINE.dose_ranges

    def test_dexmedetomidine_spec_shares_loading_doses(self):
        assert DEXMEDETOMIDINE_SPEC.loading_doses is DEXMEDETOMIDINE.loading_doses


# ---------------------------------------------------------------------------
# Direct engine compute — bypass routes, just the math.
# ---------------------------------------------------------------------------


class TestMorphineCompute:
    def test_dog_default_dose(self):
        # 20 kg × 0.2 mg/kg/hr × 1000 µg/mg / 100 µg/mL = 40 mL/hr.
        result = compute(
            MORPHINE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=0.2,
                concentration_ug_per_ml=100.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(40.0, rel=1e-3)

    def test_cat_low_end(self):
        # 4 kg × 0.05 mg/kg/hr × 1000 / 100 = 2.0 mL/hr.
        result = compute(
            MORPHINE,
            CalcInputs(
                weight_value=4.0,
                weight_unit=WeightUnit.KG,
                dose=0.05,
                concentration_ug_per_ml=100.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(2.0, rel=1e-3)

    def test_dog_loading_dose_panel_present(self):
        # Dog loading dose 0.1–0.3 mg/kg IV slowly. Cats have no
        # loading dose published — the dose_per_kg dict only has DOG.
        loading = MORPHINE.loading_doses[0]
        assert Species.DOG in loading.dose_per_kg
        assert Species.CAT not in loading.dose_per_kg

    def test_cat_dose_caution_threshold(self):
        # The cat range is conservative and the caution threshold sits
        # at the top of the range itself (0.1 mg/kg/hr) — surfacing the
        # warning even at the high end of the cat published dose, since
        # cats are dysphoria-prone.
        cat_range = MORPHINE.dose_ranges[Species.CAT]
        assert cat_range.max == 0.1
        assert cat_range.caution_threshold == 0.1


class TestDexmedetomidineCompute:
    def test_dog_dmlk_default(self):
        # DMLK protocol: 0.5 µg/kg/hr. 20 kg × 0.5 / 4 µg/mL = 2.5 mL/hr.
        result = compute(
            DEXMEDETOMIDINE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=0.5,
                concentration_ug_per_ml=4.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(2.5, rel=1e-3)

    def test_cat_default_dose(self):
        # 4 kg × 0.5 µg/kg/hr / 4 µg/mL = 0.5 mL/hr.
        result = compute(
            DEXMEDETOMIDINE,
            CalcInputs(
                weight_value=4.0,
                weight_unit=WeightUnit.KG,
                dose=0.5,
                concentration_ug_per_ml=4.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(0.5, rel=1e-3)

    def test_dog_caution_at_2_ug_kg_hr(self):
        # Caution threshold is 2.0 µg/kg/hr (sedative territory above).
        dog_range = DEXMEDETOMIDINE.dose_ranges[Species.DOG]
        assert dog_range.caution_threshold == 2.0

    def test_cat_caution_at_1_ug_kg_hr(self):
        # Cats more α₂-sensitive; caution at 1.0 µg/kg/hr.
        cat_range = DEXMEDETOMIDINE.dose_ranges[Species.CAT]
        assert cat_range.caution_threshold == 1.0

    def test_separate_dog_and_cat_loading_dose_scenarios(self):
        # Dex has two loading-dose scenarios: dog 1–3 µg/kg and cat
        # 1–2 µg/kg. They render as separate panels so the clinician
        # sees the right protocol for their patient species.
        loading_specs = DEXMEDETOMIDINE.loading_doses
        assert len(loading_specs) == 2
        dog_loading = [ld for ld in loading_specs if Species.DOG in ld.dose_per_kg]
        cat_loading = [ld for ld in loading_specs if Species.CAT in ld.dose_per_kg]
        assert len(dog_loading) == 1
        assert len(cat_loading) == 1
        assert dog_loading[0].dose_per_kg[Species.DOG] == (1.0, 3.0)
        assert cat_loading[0].dose_per_kg[Species.CAT] == (1.0, 2.0)


# ---------------------------------------------------------------------------
# Route smoke tests — GET form + POST compute.
# ---------------------------------------------------------------------------


class TestRoutes:
    def test_morphine_get_renders(self):
        r = client.get("/morphine")
        assert r.status_code == 200
        assert 'name="weight_value"' in r.text
        # Standalone form has its own how-it-works copy from the config.
        assert "Morphine" in r.text

    def test_dexmedetomidine_get_renders(self):
        r = client.get("/dexmedetomidine")
        assert r.status_code == 200
        assert 'name="weight_value"' in r.text
        assert "Dexmedetomidine" in r.text

    def test_morphine_post_dog(self):
        # 20 kg × 0.2 mg/kg/hr / 100 µg/mL = 40 mL/hr.
        r = client.post(
            "/morphine/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "0.2",
                "concentration_ug_per_ml": "100",
            },
        )
        assert r.status_code == 200
        assert "40.00" in r.text

    def test_dexmedetomidine_post_dog(self):
        # 20 kg × 0.5 µg/kg/hr / 4 µg/mL = 2.5 mL/hr.
        r = client.post(
            "/dexmedetomidine/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "0.5",
                "concentration_ug_per_ml": "4",
            },
        )
        assert r.status_code == 200
        assert "2.50" in r.text

    def test_morphine_in_analgesia_nav(self):
        # Sanity: the new standalones appear in the homepage nav.
        r = client.get("/")
        assert r.status_code == 200
        assert "/morphine" in r.text
        assert "/dexmedetomidine" in r.text
        assert "/ketamine" in r.text  # pre-existing standalone, now surfaced in nav
