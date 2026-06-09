"""
Tests for the insulin IM intermittent · DKA calculator.

Source: Hoehne SN. Diabetic Ketoacidosis. In Silverstein & Hopper
*Small Animal Critical Care Medicine* 3rd ed. Ch. 73, p. 434.
IM protocol from Macintire 1993.

Two-mode workflow:
  LOADING:    Fixed 0.2 U/kg IM regular insulin
  SUBSEQUENT: Hourly IM dose driven by BG drop:
              drop > 75 → 0.05 U/kg
              drop 50–75 → 0.1 U/kg
              drop < 50 → 0.2 U/kg
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.insulin_im_dka import (
    InsulinImInputs,
    InsulinImMode,
    InsulinImSpecies,
    compute_insulin_im,
)


def _loading(weight_kg: float = 5.0, species: InsulinImSpecies = InsulinImSpecies.CAT) -> InsulinImInputs:
    return InsulinImInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        mode=InsulinImMode.LOADING,
    )


def _subsequent(
    weight_kg: float = 5.0,
    species: InsulinImSpecies = InsulinImSpecies.CAT,
    previous_bg: float = 500.0,
    current_bg: float = 450.0,
) -> InsulinImInputs:
    return InsulinImInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        mode=InsulinImMode.SUBSEQUENT,
        previous_bg_mg_per_dl=previous_bg,
        current_bg_mg_per_dl=current_bg,
    )


class TestLoadingMode:
    """Loading dose is always 0.2 U/kg, regardless of species."""

    def test_loading_dose_is_0_2_u_per_kg(self):
        result = compute_insulin_im(_loading(weight_kg=5))
        assert result.dose_u_per_kg == 0.2

    def test_loading_volume(self):
        """U-100 stock: 5 kg × 0.2 U/kg = 1.0 U = 0.01 mL."""
        result = compute_insulin_im(_loading(weight_kg=5))
        assert result.total_units == pytest.approx(1.0)
        assert result.volume_ml_u100 == pytest.approx(0.01)

    def test_loading_dose_dog_and_cat_same(self):
        dog = compute_insulin_im(_loading(species=InsulinImSpecies.DOG))
        cat = compute_insulin_im(_loading(species=InsulinImSpecies.CAT))
        assert dog.dose_u_per_kg == cat.dose_u_per_kg


class TestSubsequentMode:
    """Hourly dose driven by BG drop in previous hour."""

    def test_drop_above_75_reduces_dose(self):
        """500 → 410 = 90 mg/dL drop. Above 75 → reduce to 0.05 U/kg."""
        result = compute_insulin_im(_subsequent(previous_bg=500, current_bg=410))
        assert result.dose_u_per_kg == 0.05
        assert result.bg_drop_mg_per_dl == pytest.approx(90.0)

    def test_drop_50_to_75_continues_target(self):
        """500 → 440 = 60 mg/dL drop. In target range → 0.1 U/kg."""
        result = compute_insulin_im(_subsequent(previous_bg=500, current_bg=440))
        assert result.dose_u_per_kg == 0.1
        assert result.bg_drop_mg_per_dl == pytest.approx(60.0)

    def test_drop_below_50_increases_dose(self):
        """500 → 470 = 30 mg/dL drop. Below 50 → increase to 0.2 U/kg."""
        result = compute_insulin_im(_subsequent(previous_bg=500, current_bg=470))
        assert result.dose_u_per_kg == 0.2
        assert result.bg_drop_mg_per_dl == pytest.approx(30.0)


class TestBoundaryConditions:
    """Threshold values."""

    @pytest.mark.parametrize(
        "drop,expected_dose",
        [
            (76, 0.05),  # > 75
            (75, 0.05),  # 75 falls into >75 tier (drop_low=75 inclusive)
            (74, 0.1),  # 50-74 in target band
            (50, 0.1),  # 50-75 inclusive lower
            (49, 0.2),  # < 50
        ],
    )
    def test_boundary(self, drop: float, expected_dose: float):
        result = compute_insulin_im(_subsequent(previous_bg=500, current_bg=500 - drop))
        assert result.dose_u_per_kg == expected_dose


class TestNegativeDrop:
    """BG actually rose — should warn and increase dose."""

    def test_bg_rose_warns(self):
        """500 → 510 = -10 (BG went up). Should treat as no drop, increase dose."""
        result = compute_insulin_im(_subsequent(previous_bg=500, current_bg=510))
        assert result.bg_drop_mg_per_dl < 0
        # Should still produce a dose (likely 0.2) and warn
        assert result.dose_u_per_kg == 0.2
        assert (
            any(
                "rose" in w.lower() or "increase" in w.lower() or "rising" in w.lower()
                for w in result.warnings
            )
            or len(result.warnings) > 0
        )


class TestStopCondition:
    """BG < 100 should warn / stop insulin."""

    def test_low_current_bg_warns(self):
        result = compute_insulin_im(_subsequent(previous_bg=200, current_bg=80))
        # Should flag the dangerous low BG
        all_text = " ".join(result.warnings + result.notes).lower()
        assert "stop" in all_text or "100" in all_text or "low" in all_text or "hypogly" in all_text


class TestUnitMath:
    """U-100 stock: dose_units / 100 = mL stock."""

    def test_5kg_loading_volume(self):
        result = compute_insulin_im(_loading(weight_kg=5))
        # 5 kg × 0.2 U/kg = 1 U; 1 U / 100 U/mL = 0.01 mL
        assert result.volume_ml_u100 == pytest.approx(0.01, rel=1e-3)

    def test_30kg_loading_volume(self):
        result = compute_insulin_im(_loading(weight_kg=30, species=InsulinImSpecies.DOG))
        # 30 × 0.2 = 6 U / 100 = 0.06 mL
        assert result.total_units == pytest.approx(6.0)
        assert result.volume_ml_u100 == pytest.approx(0.06, rel=1e-3)


class TestSourceAttribution:
    def test_includes_silverstein_or_macintire(self):
        result = compute_insulin_im(_loading())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Silverstein" in cite_text or "Hoehne" in cite_text or "Macintire" in cite_text
