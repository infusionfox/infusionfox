"""
Tests for the methadone calculator.

Source: Plumb's methadone monograph.

Bolus (dog): 0.1–0.5 mg/kg IV/IM/SC q4–8h
Bolus (cat): 0.1–0.6 mg/kg IV/IM/SC q4–6h
Premed (dog): 0.2–0.3 mg/kg
Premed (cat): 0.1–0.6 mg/kg
CRI: 0.1–0.2 mg/kg IV load + 0.12 mg/kg/hr maintenance (both species)

Stock: 10 mg/mL standard. DEA C-II.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.methadone import (
    METHADONE_STOCK_MG_PER_ML,
    MethadoneInputs,
    MethadoneSpecies,
    calculate,
)


def _inputs(
    *,
    weight_kg: float = 20.0,
    species: MethadoneSpecies = MethadoneSpecies.DOG,
    stock: float = METHADONE_STOCK_MG_PER_ML,
) -> MethadoneInputs:
    return MethadoneInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        stock_mg_per_ml=stock,
    )


class TestSpeciesSupport:
    def test_both_species_in_enum(self):
        members = {m.value for m in MethadoneSpecies}
        assert "dog" in members
        assert "cat" in members


class TestBolusRanges:
    def test_dog_bolus_range(self):
        result = calculate(_inputs(weight_kg=20, species=MethadoneSpecies.DOG))
        # 0.1–0.5 mg/kg per Plumb's
        assert result.bolus_low_mg_per_kg == 0.1
        assert result.bolus_high_mg_per_kg == 0.5

    def test_cat_bolus_range(self):
        result = calculate(_inputs(weight_kg=5, species=MethadoneSpecies.CAT))
        # 0.1–0.6 mg/kg per Plumb's
        assert result.bolus_low_mg_per_kg == 0.1
        assert result.bolus_high_mg_per_kg == 0.6


class TestBolusVolume:
    def test_dog_low_bolus_volume(self):
        """20 kg × 0.1 mg/kg = 2 mg / 10 mg/mL = 0.2 mL."""
        result = calculate(_inputs(weight_kg=20))
        assert result.bolus_low_mg == pytest.approx(2.0)
        assert result.bolus_low_ml == pytest.approx(0.2)

    def test_dog_high_bolus_volume(self):
        """20 kg × 0.5 mg/kg = 10 mg / 10 = 1.0 mL."""
        result = calculate(_inputs(weight_kg=20))
        assert result.bolus_high_mg == pytest.approx(10.0)
        assert result.bolus_high_ml == pytest.approx(1.0)


class TestPremedicationRanges:
    def test_dog_premed_range(self):
        """Plumb's dog: 0.2–0.3 mg/kg."""
        result = calculate(_inputs(species=MethadoneSpecies.DOG))
        assert result.premed_low_mg_per_kg == 0.2
        assert result.premed_high_mg_per_kg == 0.3

    def test_cat_premed_range(self):
        """Plumb's cat: 0.1–0.6 mg/kg."""
        result = calculate(_inputs(species=MethadoneSpecies.CAT))
        assert result.premed_low_mg_per_kg == 0.1
        assert result.premed_high_mg_per_kg == 0.6


class TestCRIParameters:
    """CRI parameters are species-neutral per Plumb's."""

    def test_cri_load_range_same_dog_and_cat(self):
        dog = calculate(_inputs(species=MethadoneSpecies.DOG))
        cat = calculate(_inputs(species=MethadoneSpecies.CAT))
        assert dog.cri_load_low_mg_per_kg == cat.cri_load_low_mg_per_kg == 0.1
        assert dog.cri_load_high_mg_per_kg == cat.cri_load_high_mg_per_kg == 0.2

    def test_cri_maintenance_rate(self):
        result = calculate(_inputs(weight_kg=20))
        # 0.12 mg/kg/hr per Plumb's
        assert result.cri_rate_mg_per_kg_per_hr == 0.12

    def test_cri_pump_rate_undiluted(self):
        """20 kg × 0.12 mg/kg/hr = 2.4 mg/hr / 10 mg/mL = 0.24 mL/hr."""
        result = calculate(_inputs(weight_kg=20))
        assert result.cri_pump_rate_ml_per_hr == pytest.approx(0.24, abs=0.01)


class TestStockVial:
    def test_default_stock_10mg_ml(self):
        assert METHADONE_STOCK_MG_PER_ML == 10.0


class TestSourceAttribution:
    def test_includes_plumbs(self):
        result = calculate(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Plumb" in cite_text
