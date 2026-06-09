"""Tests for the anesthesia circuit rebreathing bag calculation.

The bag formula is `(weight_kg × 15 × 6) / 1000` (tidal volume 15 mL/kg,
6× multiplier). The recommended bag must always be a stocked standard
size (0.5, 1, 2, 3, or 5 L), never the raw calculated number. Patients
above ~55 kg or below ~3 kg need special handling.
"""

from __future__ import annotations

import pytest

from app.calculators.anesthesia_sheet import (
    AnesthSpecies,
    calculate,
)
from app.calculators.engine import WeightUnit

STANDARD_BAG_SIZES_L = (0.5, 1.0, 2.0, 3.0, 5.0)


@pytest.mark.parametrize(
    "weight_kg, expected_bag",
    [
        # 1 kg → 0.09 L → 0.5
        (1.0, 0.5),
        # 5 kg → 0.45 L → 0.5
        (5.0, 0.5),
        # 6 kg → 0.54 L → 1.0
        (6.0, 1.0),
        # 11 kg → 0.99 L → 1.0
        (11.0, 1.0),
        # 12 kg → 1.08 L → 2.0
        (12.0, 2.0),
        # 22 kg → 1.98 L → 2.0
        (22.0, 2.0),
        # 23 kg → 2.07 L → 3.0
        (23.0, 3.0),
        # 33 kg → 2.97 L → 3.0
        (33.0, 3.0),
        # 34 kg → 3.06 L → 5.0
        (34.0, 5.0),
        # 55 kg → 4.95 L → 5.0
        (55.0, 5.0),
    ],
)
def test_recommended_bag_is_correct_size(weight_kg, expected_bag):
    """Each weight should pick the next standard bag size up from
    the calculated volume."""
    result = calculate(weight_kg, WeightUnit.KG, AnesthSpecies.DOG, "", "")
    assert result.circuit_bag_recommended_l == expected_bag


@pytest.mark.parametrize(
    "weight_kg",
    [1.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 100.0, 150.0],
)
def test_recommended_bag_is_always_in_standard_sizes(weight_kg):
    """The recommendation must always be one of the stocked bag sizes;
    never a random in-between number."""
    result = calculate(weight_kg, WeightUnit.KG, AnesthSpecies.DOG, "", "")
    assert result.circuit_bag_recommended_l in STANDARD_BAG_SIZES_L


def test_oversized_patient_flag_fires_above_5l():
    """Patients whose calculated volume exceeds 5 L should be flagged
    so the user knows the recommendation has reached the ceiling."""
    # 60 kg → 5.4 L (above 5 L)
    result = calculate(60.0, WeightUnit.KG, AnesthSpecies.DOG, "", "")
    assert result.circuit_bag_exceeds_max is True
    # Recommendation still maxes out at 5 L (the stocked size)
    assert result.circuit_bag_recommended_l == 5.0


def test_oversized_flag_does_not_fire_at_or_under_5l():
    """Patients at or under 55 kg should not trigger the oversized flag."""
    # 55 kg → 4.95 L
    result = calculate(55.0, WeightUnit.KG, AnesthSpecies.DOG, "", "")
    assert result.circuit_bag_exceeds_max is False


def test_small_patient_recommends_nonrebreathing():
    """Under 3 kg, rebreathing circuits aren't appropriate regardless
    of bag math. Flag for a non-rebreathing setup."""
    result = calculate(2.0, WeightUnit.KG, AnesthSpecies.CAT, "", "")
    assert result.circuit_use_nonrebreathing is True


def test_3kg_cat_uses_rebreathing():
    """At and above 3 kg, the rebreathing recommendation applies."""
    result = calculate(3.0, WeightUnit.KG, AnesthSpecies.CAT, "", "")
    assert result.circuit_use_nonrebreathing is False
    assert result.circuit_bag_recommended_l == 0.5


def test_calculated_value_uses_the_exact_formula():
    """Sanity-check that the calculated_l field actually applies the
    documented formula (15 × 6 ÷ 1000)."""
    weight_kg = 20.0
    expected = (20.0 * 15 * 6) / 1000  # = 1.8
    result = calculate(weight_kg, WeightUnit.KG, AnesthSpecies.DOG, "", "")
    assert result.circuit_bag_calculated_l == round(expected, 2)
    # And the recommendation picks the next bag up from 1.8 → 2.0
    assert result.circuit_bag_recommended_l == 2.0
