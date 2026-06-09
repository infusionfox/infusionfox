"""
Tests for the dopamine preparation calculator.

Source: Plumb's dopamine monograph.

6×BW recipe:
    Add (6 × BW kg) mg dopamine to 100 mL bag.
    Stock 40 mg/mL → mL to draw = (6 × BW) / 40.
    Final concentration = 60 × BW µg/mL.
    Pump rate (mL/hr) = target dose (µg/kg/min) by construction.

Cap: final concentration ≤ 3200 µg/mL (≈ patients ≤ 53 kg).

Cat warning: dopamine in HCM cats — Wiese HCM PVC risk above 10 µg/kg/min.
"""

from __future__ import annotations

import pytest

from app.calculators.dopamine_prep import (
    DOPAMINE_BAG_VOLUME_ML,
    DOPAMINE_MAX_FINAL_CONCENTRATION_UG_PER_ML,
    DOPAMINE_STOCK_MG_PER_ML,
    DopaminePrepInputs,
    DopamineSpecies,
    compute_dopamine_preparation,
)
from app.calculators.engine import WeightUnit


def _inputs(
    *,
    weight_kg: float = 20.0,
    species: DopamineSpecies = DopamineSpecies.DOG,
    target_dose: float = 5.0,
) -> DopaminePrepInputs:
    return DopaminePrepInputs(
        species=species,
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        target_dose_ug_per_kg_per_min=target_dose,
    )


class TestRecipe:
    def test_20kg_dog_default(self):
        """20 kg dog: add 120 mg / 3 mL stock to 100 mL bag.
        Final concentration = 1200 µg/mL.
        """
        result = compute_dopamine_preparation(_inputs(weight_kg=20))
        assert result.mg_dopamine_to_add == pytest.approx(120.0)
        assert result.ml_stock_to_draw == pytest.approx(3.0)
        assert result.final_concentration_ug_per_ml == pytest.approx(1200.0)
        assert result.bag_volume_ml == 100.0

    def test_5kg_cat(self):
        """5 kg cat: 30 mg / 0.75 mL into 100 mL bag, final 300 µg/mL."""
        result = compute_dopamine_preparation(_inputs(weight_kg=5, species=DopamineSpecies.CAT))
        assert result.mg_dopamine_to_add == pytest.approx(30.0)
        assert result.ml_stock_to_draw == pytest.approx(0.75, rel=1e-2)
        assert result.final_concentration_ug_per_ml == pytest.approx(300.0)


class TestPumpRateEqualsDose:
    """By construction, pump_rate (mL/hr) = target_dose (µg/kg/min)."""

    def test_dose_5_pump_5(self):
        result = compute_dopamine_preparation(_inputs(target_dose=5))
        assert result.pump_rate_ml_per_hr == 5.0

    def test_dose_10_pump_10(self):
        result = compute_dopamine_preparation(_inputs(target_dose=10))
        assert result.pump_rate_ml_per_hr == 10.0


class TestConcentrationCap:
    """Final concentration must stay ≤ 3200 µg/mL."""

    def test_cap_value(self):
        assert DOPAMINE_MAX_FINAL_CONCENTRATION_UG_PER_ML == 3200.0

    def test_at_cap_53kg(self):
        """Plumb's cap: 53 kg dog gives 3180 µg/mL (just under)."""
        result = compute_dopamine_preparation(_inputs(weight_kg=53))
        assert result.final_concentration_ug_per_ml < 3200
        assert not any("exceed" in w.lower() for w in result.warnings)

    def test_above_cap_warns(self):
        """60 kg dog would exceed 3200 µg/mL → warning."""
        result = compute_dopamine_preparation(_inputs(weight_kg=60))
        assert result.final_concentration_ug_per_ml > 3200
        assert any("exceed" in w.lower() or "limit" in w.lower() for w in result.warnings)


class TestSpeciesWarnings:
    def test_dog_low_dose_warns(self):
        """< 3 µg/kg/min argues against benefit per Plumb's."""
        result = compute_dopamine_preparation(_inputs(target_dose=2))
        assert any(
            "range" in w.lower() or "low" in w.lower() or "below" in w.lower() for w in result.warnings
        )

    def test_dog_high_dose_warns(self):
        """> 20 µg/kg/min — switch to norepinephrine."""
        result = compute_dopamine_preparation(_inputs(target_dose=25))
        assert any(
            "range" in w.lower() or "exceeds" in w.lower() or "norepinephrine" in w.lower()
            for w in result.warnings
        )

    def test_cat_warning_present(self):
        """Cat HCM risk above 10 µg/kg/min."""
        result = compute_dopamine_preparation(_inputs(species=DopamineSpecies.CAT, target_dose=12))
        all_text = " ".join(result.warnings + result.notes).lower()
        assert "hcm" in all_text or "ecg" in all_text or "pvc" in all_text or "10" in all_text


class TestStockConstants:
    def test_stock_40mg_ml(self):
        assert DOPAMINE_STOCK_MG_PER_ML == 40.0

    def test_bag_100ml(self):
        assert DOPAMINE_BAG_VOLUME_ML == 100.0


class TestInputValidation:
    def test_zero_weight_warns(self):
        result = compute_dopamine_preparation(_inputs(weight_kg=0))
        assert any("weight" in w.lower() for w in result.warnings)

    def test_zero_dose_warns(self):
        result = compute_dopamine_preparation(_inputs(target_dose=0))
        assert any("dose" in w.lower() for w in result.warnings)


class TestSourceAttribution:
    def test_includes_plumbs(self):
        result = compute_dopamine_preparation(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Plumb" in cite_text
