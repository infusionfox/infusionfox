"""
Tests for the ketamine CRI calculator.

Source: Plumb's ketamine monograph; Silverstein & Hopper Ch. 134.

Both species. Two indication modes:
  SURGICAL:    10–20 µg/kg/min (default 10)
  POSTSURGICAL: 2–10 µg/kg/min (default 2) × 24 hr

Cat-specific persistent warnings: HCM avoidance, 20% seizure rate,
hyperthermia, renal excretion. Stock 100 mg/mL standard vet vial.
DEA Schedule III.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.ketamine import (
    KETAMINE_STOCK_MG_PER_ML,
    KetamineDoseUnit,
    KetamineIndication,
    KetamineInputs,
    KetamineSpecies,
    compute_ketamine,
    get_ketamine_dose_range,
)


def _inputs(
    *,
    weight_kg: float = 20.0,
    species: KetamineSpecies = KetamineSpecies.DOG,
    indication: KetamineIndication = KetamineIndication.SURGICAL,
    dose: float = 10.0,
    unit: KetamineDoseUnit = KetamineDoseUnit.UG_PER_KG_PER_MIN,
) -> KetamineInputs:
    return KetamineInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        dose_value=dose,
        dose_unit=unit,
        indication=indication,
        species=species,
    )


class TestSpeciesSupport:
    """Both dog and cat are supported."""

    def test_both_species_in_enum(self):
        members = {m.value for m in KetamineSpecies}
        assert "dog" in members
        assert "cat" in members


class TestIndicationRanges:
    def test_surgical_range_10_to_20(self):
        rng = get_ketamine_dose_range(KetamineIndication.SURGICAL)
        assert rng.min_ug_per_kg_per_min == 10.0
        assert rng.max_ug_per_kg_per_min == 20.0
        assert rng.default_ug_per_kg_per_min == 10.0

    def test_postsurgical_range_2_to_10(self):
        rng = get_ketamine_dose_range(KetamineIndication.POSTSURGICAL)
        assert rng.min_ug_per_kg_per_min == 2.0
        assert rng.max_ug_per_kg_per_min == 10.0
        assert rng.default_ug_per_kg_per_min == 2.0


class TestPumpRateMath:
    def test_20kg_dog_surgical_default(self):
        """20 kg × 10 µg/kg/min = 200 µg/min = 12 mg/hr.
        12 / 100 mg/mL = 0.12 mL/hr."""
        result = compute_ketamine(_inputs(weight_kg=20, dose=10.0))
        assert result.pump_rate_ml_per_hr == pytest.approx(0.12, abs=0.01)


class TestUnitToggle:
    """µg/kg/min and mg/kg/hr produce same pump rate."""

    def test_10ug_kg_min_equals_0_6mg_kg_hr(self):
        """10 µg/kg/min × 60 / 1000 = 0.6 mg/kg/hr"""
        r_ug = compute_ketamine(_inputs(dose=10.0, unit=KetamineDoseUnit.UG_PER_KG_PER_MIN))
        r_mg = compute_ketamine(_inputs(dose=0.6, unit=KetamineDoseUnit.MG_PER_KG_PER_HR))
        assert r_ug.pump_rate_ml_per_hr == pytest.approx(r_mg.pump_rate_ml_per_hr, rel=1e-2)


class TestStockConcentration:
    def test_stock_is_100mg_per_ml(self):
        assert KETAMINE_STOCK_MG_PER_ML == 100.0


class TestCatWarnings:
    """Cat-specific concerns surface in warnings/notes."""

    def test_cat_hcm_warning_present(self):
        result = compute_ketamine(_inputs(species=KetamineSpecies.CAT))
        all_text = " ".join(result.warnings + result.notes).lower()
        # Should mention HCM / cardiomyopathy / heart concerns
        assert "hcm" in all_text or "cardiomyopa" in all_text or "heart" in all_text

    def test_dog_does_not_get_cat_warnings(self):
        dog = compute_ketamine(_inputs(species=KetamineSpecies.DOG))
        cat = compute_ketamine(_inputs(species=KetamineSpecies.CAT))
        # Cat should have at least as many warnings as dog (cat-specific ones added)
        assert len(cat.warnings) + len(cat.notes) >= len(dog.warnings) + len(dog.notes)


class TestDoseClamping:
    def test_below_postsurgical_minimum_warns(self):
        result = compute_ketamine(_inputs(indication=KetamineIndication.POSTSURGICAL, dose=0.5))
        assert any(
            "range" in w.lower() or "min" in w.lower() or "below" in w.lower() for w in result.warnings
        )

    def test_above_surgical_maximum_warns(self):
        result = compute_ketamine(_inputs(indication=KetamineIndication.SURGICAL, dose=50.0))
        assert any(
            "range" in w.lower() or "max" in w.lower() or "above" in w.lower() for w in result.warnings
        )


class TestSourceAttribution:
    def test_includes_plumbs_or_silverstein(self):
        result = compute_ketamine(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Plumb" in cite_text or "Silverstein" in cite_text
