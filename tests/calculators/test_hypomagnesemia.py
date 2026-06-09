"""
Tests for the hypomagnesemia (MgSO4 CRI) calculator.

Source: Hoehne SN. Diabetic Ketoacidosis. In Silverstein & Hopper
*Small Animal Critical Care Medicine* 3rd ed. Ch. 73, Box 73.1.
MgSO4 sliding scale: 0.25–1 mEq/kg/day by serum Mg.

Stock concentrations:
- 50% MgSO4: 4 mEq/mL (default)
- 25% MgSO4: 2 mEq/mL (alternative)
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.hypomagnesemia import (
    HypomagnesemiaInputs,
    MgSpecies,
    MgStockConcentration,
    compute_hypomagnesemia,
)


def _inputs(
    *,
    weight_kg: float = 20,
    species: MgSpecies = MgSpecies.DOG,
    mg: float = 0.7,
    stock: MgStockConcentration = MgStockConcentration.PCT_50,
) -> HypomagnesemiaInputs:
    return HypomagnesemiaInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        serum_mg_mg_per_dl=mg,
        stock_concentration=stock,
    )


class TestSlidingScale:
    """Each tier produces the published rate."""

    def test_severe_below_0_9(self):
        result = compute_hypomagnesemia(_inputs(mg=0.7))
        assert result.target_rate_meq_per_kg_per_day == 1.0
        assert result.matched_tier.severity == "severe"
        assert result.not_indicated is False

    def test_moderate_0_9_to_1_2(self):
        result = compute_hypomagnesemia(_inputs(mg=1.0))
        assert result.target_rate_meq_per_kg_per_day == 0.5
        assert result.matched_tier.severity == "moderate"

    def test_mild_1_2_to_1_5(self):
        result = compute_hypomagnesemia(_inputs(mg=1.3))
        assert result.target_rate_meq_per_kg_per_day == 0.25
        assert result.matched_tier.severity == "mild"

    def test_normal_above_1_5(self):
        result = compute_hypomagnesemia(_inputs(mg=2.0))
        assert result.target_rate_meq_per_kg_per_day is None
        assert result.not_indicated is True
        assert result.matched_tier.severity == "normomagnesemia"


class TestTierBoundaries:
    @pytest.mark.parametrize(
        "mg,expected_severity",
        [
            (0.89, "severe"),
            (0.90, "moderate"),
            (1.19, "moderate"),
            (1.20, "mild"),
            (1.49, "mild"),
            (1.50, "normomagnesemia"),
        ],
    )
    def test_boundary(self, mg: float, expected_severity: str):
        result = compute_hypomagnesemia(_inputs(mg=mg))
        assert result.matched_tier.severity == expected_severity


class TestPumpRateMath:
    """Verify the daily/hourly/pump math chain."""

    def test_severe_dog_50pct_stock(self):
        """20 kg dog, Mg 0.7, 50% (4 mEq/mL).
        Daily: 20 × 1.0 = 20 mEq/day
        Hourly: 20 / 24 ≈ 0.833 mEq/hr
        Pump: 0.833 / 4 ≈ 0.208 mL/hr.
        """
        result = compute_hypomagnesemia(_inputs(weight_kg=20, mg=0.7))
        assert result.daily_meq == pytest.approx(20.0)
        assert result.hourly_meq == pytest.approx(20.0 / 24, rel=1e-3)
        assert result.pump_rate_ml_per_hr == pytest.approx(20.0 / 24 / 4, rel=1e-2)
        assert result.pump_rate_ml_per_day == pytest.approx(5.0)

    def test_25pct_stock_doubles_volume(self):
        """50% stock = 4 mEq/mL; 25% stock = 2 mEq/mL. Volume doubles for same delivery."""
        r50 = compute_hypomagnesemia(_inputs(mg=0.7, stock=MgStockConcentration.PCT_50))
        r25 = compute_hypomagnesemia(_inputs(mg=0.7, stock=MgStockConcentration.PCT_25))
        # Allow for rounding — values are rounded to 3 places in the result
        assert r25.pump_rate_ml_per_hr == pytest.approx(r50.pump_rate_ml_per_hr * 2, abs=0.002)
        assert r25.daily_meq == r50.daily_meq  # same dose, different volume


class TestStockConcentrations:
    def test_50pct_label(self):
        result = compute_hypomagnesemia(_inputs(stock=MgStockConcentration.PCT_50))
        assert result.stock_meq_per_ml == 4.0

    def test_25pct_label(self):
        result = compute_hypomagnesemia(_inputs(stock=MgStockConcentration.PCT_25))
        assert result.stock_meq_per_ml == 2.0


class TestSpeciesNeutral:
    def test_dog_and_cat_get_same_rate(self):
        dog = compute_hypomagnesemia(_inputs(species=MgSpecies.DOG, mg=0.8))
        cat = compute_hypomagnesemia(_inputs(species=MgSpecies.CAT, mg=0.8))
        assert dog.target_rate_meq_per_kg_per_day == cat.target_rate_meq_per_kg_per_day


class TestInputValidation:
    def test_negative_weight_no_crash(self):
        # Should not raise; should produce a warning
        result = compute_hypomagnesemia(_inputs(weight_kg=-5, mg=0.7))
        assert any("weight" in w.lower() for w in result.warnings)

    def test_zero_weight_no_crash(self):
        result = compute_hypomagnesemia(_inputs(weight_kg=0, mg=0.7))
        assert any("weight" in w.lower() for w in result.warnings)


class TestSourceAttribution:
    def test_includes_citation(self):
        result = compute_hypomagnesemia(_inputs(mg=0.7))
        assert len(result.sources) > 0
