"""
Tests for the calculator utilities (weight conversions, dose unit
conversions, percent-mg/mL conversions, solution prep dilution).

Reusable building blocks. Bugs here would silently affect any consumer.
"""

from __future__ import annotations

import pytest

from app.calculators.utilities import (
    SolutionPrepInputs,
    WeightFromUnit,
    compute_solution_prep,
    convert_dose_amount,
    convert_weight,
    mg_per_ml_to_percent,
    percent_to_mg_per_ml,
)


class TestConvertWeight:
    def test_kg_input(self):
        result = convert_weight(10, WeightFromUnit.KG)
        assert result.kg == pytest.approx(10.0)
        assert result.lb == pytest.approx(22.046, abs=0.01)
        assert result.g == pytest.approx(10000.0)
        assert result.oz == pytest.approx(352.74, abs=0.1)

    def test_lb_input(self):
        result = convert_weight(22.046, WeightFromUnit.LB)
        assert result.kg == pytest.approx(10.0, abs=0.01)

    def test_grams_input(self):
        """500 g = 0.5 kg."""
        result = convert_weight(500, WeightFromUnit.G)
        assert result.kg == pytest.approx(0.5)
        assert result.lb == pytest.approx(1.102, abs=0.01)

    def test_oz_input(self):
        """16 oz = 1 lb = 0.4536 kg."""
        result = convert_weight(16, WeightFromUnit.OZ)
        assert result.lb == pytest.approx(1.0, abs=0.01)
        assert result.kg == pytest.approx(0.4536, abs=0.01)

    def test_zero_input(self):
        result = convert_weight(0, WeightFromUnit.KG)
        assert result.kg == 0
        assert result.lb == 0
        assert result.g == 0
        assert result.oz == 0

    def test_negative_returns_zeros(self):
        result = convert_weight(-5, WeightFromUnit.KG)
        # Negative inputs treated as zero
        assert result.kg == 0


class TestConvertDoseAmount:
    def test_mg_input(self):
        result = convert_dose_amount(1.0, "mg")
        assert result.mg == 1.0
        assert result.ug == pytest.approx(1000.0)
        assert result.g == pytest.approx(0.001, abs=0.0001)

    def test_ug_input(self):
        """1000 µg = 1 mg."""
        result = convert_dose_amount(1000, "ug")
        assert result.mg == pytest.approx(1.0)
        assert result.ug == pytest.approx(1000.0)

    def test_g_input(self):
        """1 g = 1000 mg."""
        result = convert_dose_amount(1.0, "g")
        assert result.mg == pytest.approx(1000.0)
        assert result.g == pytest.approx(1.0)

    def test_zero_input(self):
        result = convert_dose_amount(0, "mg")
        assert result.mg == 0
        assert result.ug == 0
        assert result.g == 0

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            convert_dose_amount(1, "lb")


class TestPercentMgPerMl:
    """A w/v percent solution = grams per 100 mL → percent × 10 = mg/mL."""

    def test_5pct_is_50mg_ml(self):
        """5% dextrose = 50 mg/mL."""
        assert percent_to_mg_per_ml(5) == 50.0

    def test_50pct_is_500mg_ml(self):
        """50% dextrose stock = 500 mg/mL."""
        assert percent_to_mg_per_ml(50) == 500.0

    def test_2pct_is_20mg_ml(self):
        """2% lidocaine = 20 mg/mL."""
        assert percent_to_mg_per_ml(2) == 20.0

    def test_inverse_50_is_5pct(self):
        assert mg_per_ml_to_percent(50) == 5.0

    def test_round_trip(self):
        for pct in [0.5, 2, 5, 10, 50]:
            mg = percent_to_mg_per_ml(pct)
            assert mg_per_ml_to_percent(mg) == pct


class TestSolutionPrep:
    """C1V1 = C2V2 dilution math."""

    def test_d5w_from_50pct_stock(self):
        """Plumb's example: 1000 mL of D5W → 100 mL stock 50% + 900 mL water.
        (1000 × 5) / 50 = 100.
        """
        result = compute_solution_prep(
            SolutionPrepInputs(
                target_volume_ml=1000,
                target_percent=5,
                stock_percent=50,
            )
        )
        assert result.stock_volume_ml == pytest.approx(100.0)
        assert result.diluent_volume_ml == pytest.approx(900.0)

    def test_d2_5_from_50pct(self):
        """500 mL of 2.5% from 50% stock: 25 mL stock + 475 mL water."""
        result = compute_solution_prep(
            SolutionPrepInputs(
                target_volume_ml=500,
                target_percent=2.5,
                stock_percent=50,
            )
        )
        assert result.stock_volume_ml == pytest.approx(25.0)
        assert result.diluent_volume_ml == pytest.approx(475.0)

    def test_target_higher_than_stock_warns(self):
        """Cannot dilute upward."""
        result = compute_solution_prep(
            SolutionPrepInputs(
                target_volume_ml=100,
                target_percent=10,
                stock_percent=5,
            )
        )
        assert any("lower" in w.lower() or "stock" in w.lower() for w in result.warnings)

    def test_zero_volume_warns(self):
        result = compute_solution_prep(
            SolutionPrepInputs(
                target_volume_ml=0,
                target_percent=5,
                stock_percent=50,
            )
        )
        assert any("volume" in w.lower() for w in result.warnings)

    def test_zero_target_pct_warns(self):
        result = compute_solution_prep(
            SolutionPrepInputs(
                target_volume_ml=100,
                target_percent=0,
                stock_percent=50,
            )
        )
        assert any("target" in w.lower() or "concentration" in w.lower() for w in result.warnings)

    def test_zero_stock_pct_warns(self):
        result = compute_solution_prep(
            SolutionPrepInputs(
                target_volume_ml=100,
                target_percent=5,
                stock_percent=0,
            )
        )
        assert any("stock" in w.lower() or "concentration" in w.lower() for w in result.warnings)

    def test_final_mg_per_ml_matches(self):
        """5% target → 50 mg/mL final."""
        result = compute_solution_prep(
            SolutionPrepInputs(
                target_volume_ml=1000,
                target_percent=5,
                stock_percent=50,
            )
        )
        assert result.final_mg_per_ml == pytest.approx(50.0)
