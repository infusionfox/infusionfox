"""
Tests for the energy requirements (RER/MER) calculator.

Sources:
  Ettinger SJ, Feldman EC, Côté E, eds. Textbook of Veterinary Internal
  Medicine. 9th ed. Elsevier; 2024. Ch. 147 (dogs, Box 147.1), Ch. 150
  (Obesity, weight-loss formulas).

  National Research Council. Nutrient Requirements of Dogs and Cats. 2006.
  p. 95 (cat MER equations).

Cat MER:
  Lean cats (BCS ≤ 5/9):    MER = 100 × BW^0.67
  Overweight cats (BCS > 5): MER = 130 × BW^0.4

RER formula: 70 × BW^0.75
"""

from __future__ import annotations

import pytest

from app.calculators.energy import (
    EnergyInputs,
    EnergyPurpose,
    EnergySpecies,
    compute_energy_requirements,
)
from app.calculators.engine import WeightUnit


def _inputs(
    *,
    species: EnergySpecies = EnergySpecies.DOG,
    purpose: EnergyPurpose = EnergyPurpose.MAINTENANCE,
    weight_kg: float = 20.0,
    bcs: int | None = 5,
    ideal_kg: float | None = None,
    factor_key: str = "typical_pet",
) -> EnergyInputs:
    return EnergyInputs(
        species=species,
        purpose=purpose,
        current_weight_value=weight_kg,
        current_weight_unit=WeightUnit.KG,
        ideal_weight_value=ideal_kg,
        ideal_weight_unit=WeightUnit.KG,
        bcs=bcs,
        maintenance_factor_key=factor_key,
    )


class TestRERFormula:
    """RER = 70 × BW^0.75"""

    @pytest.mark.parametrize(
        "weight_kg,expected_rer",
        [
            (5, 70 * 5**0.75),  # 234
            (10, 70 * 10**0.75),  # 394
            (20, 70 * 20**0.75),  # 662
            (30, 70 * 30**0.75),  # 897
        ],
    )
    def test_rer_dog(self, weight_kg: float, expected_rer: float):
        result = compute_energy_requirements(_inputs(weight_kg=weight_kg))
        assert result.rer_kcal_per_day == pytest.approx(expected_rer, rel=1e-2)

    def test_rer_cat(self):
        result = compute_energy_requirements(_inputs(species=EnergySpecies.CAT, weight_kg=5))
        assert result.rer_kcal_per_day == pytest.approx(70 * 5**0.75, rel=1e-2)


class TestCatMERLean:
    """Lean cats (BCS ≤ 5): MER = 100 × BW^0.67."""

    def test_lean_cat_5kg(self):
        """5 kg × 100 × 5^0.67 ≈ 297 kcal/day."""
        result = compute_energy_requirements(_inputs(species=EnergySpecies.CAT, weight_kg=5, bcs=4))
        expected = 100 * 5**0.67
        assert result.target_kcal_per_day == pytest.approx(expected, rel=5e-2)


class TestCatMEROverweight:
    """For maintenance, the calculator uses MER = 100 × BW^0.67 regardless
    of BCS. The NRC 130 × BW^0.4 overweight formula is reserved for the
    WEIGHT_LOSS purpose (calculated against ideal body weight).
    """

    def test_overweight_cat_uses_same_formula_as_lean_for_maintenance(self):
        """Maintenance for a fat cat uses 100×BW^0.67 of CURRENT weight."""
        result = compute_energy_requirements(_inputs(species=EnergySpecies.CAT, weight_kg=7, bcs=8))
        expected = 100 * 7**0.67
        assert result.target_kcal_per_day == pytest.approx(expected, rel=5e-2)


class TestSpeciesDifferences:
    def test_dog_and_cat_differ(self):
        dog = compute_energy_requirements(_inputs(species=EnergySpecies.DOG, weight_kg=5))
        cat = compute_energy_requirements(_inputs(species=EnergySpecies.CAT, weight_kg=5))
        # RER same, MER differs (dog uses factor × RER; cat uses NRC formula)
        assert dog.rer_kcal_per_day == pytest.approx(cat.rer_kcal_per_day, rel=1e-2)
        # MER targets should generally differ
        assert dog.target_kcal_per_day != cat.target_kcal_per_day


class TestPurposeModes:
    def test_maintenance_uses_factor(self):
        result = compute_energy_requirements(_inputs(purpose=EnergyPurpose.MAINTENANCE))
        assert result.target_kcal_per_day > 0

    def test_weight_loss_below_maintenance(self):
        loss = compute_energy_requirements(
            _inputs(purpose=EnergyPurpose.WEIGHT_LOSS, weight_kg=30, bcs=8, ideal_kg=20)
        )
        maint = compute_energy_requirements(_inputs(purpose=EnergyPurpose.MAINTENANCE, weight_kg=30, bcs=8))
        # Weight loss target should be lower than maintenance for a given current weight
        assert loss.target_kcal_per_day < maint.target_kcal_per_day


class TestSourceAttribution:
    def test_includes_citation(self):
        result = compute_energy_requirements(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        # Calculator cites WSAVA / Freeman; either a textbook or society source is acceptable
        assert (
            "Ettinger" in cite_text
            or "NRC" in cite_text
            or "Nutrient" in cite_text
            or "WSAVA" in cite_text
            or "Freeman" in cite_text
        )
