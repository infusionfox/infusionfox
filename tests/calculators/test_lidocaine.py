"""
Tests for the lidocaine CRI calculator.

Source: Plumb's lidocaine monograph; Silverstein & Hopper Ch. 134.

Dog-only — IV systemic lidocaine is avoided in cats. Default range
1.5–3.0 mg/kg/hr (= 25–50 µg/kg/min). Stock 2% lidocaine = 20 mg/mL.

Loading bolus: 1–2 mg/kg IV slowly.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.lidocaine import (
    LIDOCAINE_STOCK_MG_PER_ML,
    LidocaineDoseUnit,
    LidocaineInputs,
    LidocaineSpecies,
    compute_lidocaine,
)


def _inputs(
    *,
    weight_kg: float = 20.0,
    dose: float = 2.0,
    unit: LidocaineDoseUnit = LidocaineDoseUnit.MG_PER_KG_PER_HR,
) -> LidocaineInputs:
    return LidocaineInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        dose_value=dose,
        dose_unit=unit,
        species=LidocaineSpecies.DOG,
    )


class TestSpeciesEnumDogOnly:
    """Lidocaine CRI is dog-only — there should be no CAT enum value."""

    def test_only_dog_in_enum(self):
        members = {m.value for m in LidocaineSpecies}
        assert "dog" in members
        assert "cat" not in members


class TestPumpRateMath:
    def test_default_dose_dog(self):
        """20 kg × 2 mg/kg/hr = 40 mg/hr / 20 mg/mL = 2 mL/hr."""
        result = compute_lidocaine(_inputs(weight_kg=20, dose=2.0))
        assert result.pump_rate_ml_per_hr == pytest.approx(2.0, rel=1e-2)

    def test_30kg_dog_3mg(self):
        """30 kg × 3 mg/kg/hr = 90 mg/hr / 20 = 4.5 mL/hr."""
        result = compute_lidocaine(_inputs(weight_kg=30, dose=3.0))
        assert result.pump_rate_ml_per_hr == pytest.approx(4.5, rel=1e-2)


class TestUnitToggle:
    """µg/kg/min and mg/kg/hr should produce the same pump rate."""

    def test_50ug_kg_min_equals_3mg_kg_hr(self):
        """50 µg/kg/min × 60 / 1000 = 3 mg/kg/hr"""
        r_ug = compute_lidocaine(_inputs(dose=50.0, unit=LidocaineDoseUnit.UG_PER_KG_PER_MIN))
        r_mg = compute_lidocaine(_inputs(dose=3.0, unit=LidocaineDoseUnit.MG_PER_KG_PER_HR))
        assert r_ug.pump_rate_ml_per_hr == pytest.approx(r_mg.pump_rate_ml_per_hr, rel=1e-2)

    def test_25ug_kg_min_equals_1_5mg_kg_hr(self):
        r_ug = compute_lidocaine(_inputs(dose=25.0, unit=LidocaineDoseUnit.UG_PER_KG_PER_MIN))
        r_mg = compute_lidocaine(_inputs(dose=1.5, unit=LidocaineDoseUnit.MG_PER_KG_PER_HR))
        assert r_ug.pump_rate_ml_per_hr == pytest.approx(r_mg.pump_rate_ml_per_hr, rel=1e-2)


class TestDoseClamping:
    def test_below_minimum_warns(self):
        result = compute_lidocaine(_inputs(dose=0.5))
        assert any(
            "range" in w.lower() or "min" in w.lower() or "below" in w.lower() for w in result.warnings
        )

    def test_above_maximum_warns(self):
        result = compute_lidocaine(_inputs(dose=10.0))
        assert any(
            "range" in w.lower() or "max" in w.lower() or "above" in w.lower() for w in result.warnings
        )


class TestLoadingDose:
    """1–2 mg/kg IV slow load, computed in mg and mL."""

    def test_20kg_loading(self):
        """20 kg × 1 mg/kg = 20 mg min, × 2 = 40 mg max.
        Volumes: 20/20 = 1 mL min, 40/20 = 2 mL max.
        """
        result = compute_lidocaine(_inputs(weight_kg=20))
        assert result.loading_dose_min_mg == pytest.approx(20.0)
        assert result.loading_dose_max_mg == pytest.approx(40.0)
        assert result.loading_volume_min_ml == pytest.approx(1.0)
        assert result.loading_volume_max_ml == pytest.approx(2.0)


class TestStockConcentration:
    def test_stock_is_2pct(self):
        """2% lidocaine = 20 mg/mL."""
        assert LIDOCAINE_STOCK_MG_PER_ML == 20.0


class TestSourceAttribution:
    def test_includes_plumbs_or_silverstein(self):
        result = compute_lidocaine(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Plumb" in cite_text or "Silverstein" in cite_text
