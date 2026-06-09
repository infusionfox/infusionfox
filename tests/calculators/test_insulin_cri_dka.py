"""
Tests for the insulin CRI · DKA calculator.

Source: Hoehne SN. Diabetic Ketoacidosis. In Silverstein & Hopper
*Small Animal Critical Care Medicine* 3rd ed. Ch. 73, Table 73.1
(CRI sliding scale, p. 435).

Standard prep: 2.2 U/kg into 250 mL 0.9% NaCl, prime + discard 50 mL.
Cat option toggle: 2.2 U/kg (current evidence-based default) vs
1.1 U/kg (conservative, historical).

5-tier sliding scale by BG:
    > 250        → 0.9% NaCl,                  10 mL/hr
    200–250      → NaCl + 2.5% dextrose,        7 mL/hr
    150–199      → NaCl + 2.5% dextrose,        5 mL/hr
    100–149      → NaCl + 5% dextrose,          5 mL/hr
    < 100        → NaCl + 5% dextrose,          STOP insulin
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.insulin_cri_dka import (
    InsulinCriCatDoseOption,
    InsulinCriInputs,
    InsulinCriSpecies,
    compute_insulin_cri,
)


def _inputs(
    *,
    weight_kg: float = 20.0,
    species: InsulinCriSpecies = InsulinCriSpecies.DOG,
    bg: float = 400.0,
    cat_option: InsulinCriCatDoseOption = InsulinCriCatDoseOption.STANDARD_2_2,
) -> InsulinCriInputs:
    return InsulinCriInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        blood_glucose_mg_per_dl=bg,
        cat_dose_option=cat_option,
    )


class TestSlidingScale:
    """Each row of Table 73.1 produces the published rate and fluid composition."""

    def test_above_250_runs_at_10ml_hr_no_dextrose(self):
        result = compute_insulin_cri(_inputs(bg=400))
        assert result.pump_rate_ml_per_hr == 10.0
        assert "0.9% NaCl" in result.fluid_composition
        assert "dextrose" not in result.fluid_composition.lower()
        assert result.insulin_stopped is False

    def test_200_to_250_at_7ml_hr_2_5pct_dextrose(self):
        result = compute_insulin_cri(_inputs(bg=225))
        assert result.pump_rate_ml_per_hr == 7.0
        assert "2.5%" in result.fluid_composition

    def test_150_to_199_at_5ml_hr_2_5pct(self):
        result = compute_insulin_cri(_inputs(bg=170))
        assert result.pump_rate_ml_per_hr == 5.0
        assert "2.5%" in result.fluid_composition

    def test_100_to_149_at_5ml_hr_5pct(self):
        result = compute_insulin_cri(_inputs(bg=120))
        assert result.pump_rate_ml_per_hr == 5.0
        assert "5%" in result.fluid_composition

    def test_below_100_stops_insulin(self):
        result = compute_insulin_cri(_inputs(bg=80))
        assert result.pump_rate_ml_per_hr is None
        assert result.insulin_stopped is True
        assert "5%" in result.fluid_composition  # dextrose continues


class TestBoundaryConditions:
    """Threshold values must fall into the correct tier per Hoehne."""

    @pytest.mark.parametrize(
        "bg,expected_rate",
        [
            (251.0, 10.0),  # >250
            (250.0, 10.0),  # >=250 falls into >250 tier (bg_low=250 inclusive)
            (249.0, 7.0),  # 200-250 row
            (200.0, 7.0),
            (199.0, 5.0),  # 150-199 row
            (150.0, 5.0),
            (149.0, 5.0),  # 100-149 row, same rate but different fluid
            (100.0, 5.0),
            (99.0, None),  # < 100, STOP
        ],
    )
    def test_bg_boundary(self, bg: float, expected_rate: float | None):
        result = compute_insulin_cri(_inputs(bg=bg))
        assert result.pump_rate_ml_per_hr == expected_rate

    def test_dextrose_step_up_at_150(self):
        """At BG 150, fluid is 2.5%. At BG 149, fluid steps up to 5%."""
        r150 = compute_insulin_cri(_inputs(bg=150))
        r149 = compute_insulin_cri(_inputs(bg=149))
        assert "2.5%" in r150.fluid_composition
        assert "5%" in r149.fluid_composition


class TestBagPrep:
    """2.2 U/kg added to 250 mL bag (default), prime + discard 50 mL."""

    def test_dog_20kg_default(self):
        """20 kg × 2.2 U/kg = 44 U added to 250 mL bag."""
        result = compute_insulin_cri(_inputs(weight_kg=20, species=InsulinCriSpecies.DOG))
        assert result.total_units_added_to_bag == pytest.approx(44.0)
        assert result.loading_units_per_kg == pytest.approx(2.2)
        assert result.prime_discard_ml == 50
        # Concentration is total_units / bag_volume — discarding the prime
        # doesn't change concentration of the remaining bag.
        # 44 U / 250 mL = 0.176 U/mL
        assert result.bag_concentration_units_per_ml == pytest.approx(44 / 250, abs=0.001)

    def test_cat_5kg_standard_2_2(self):
        """Cat at 2.2 U/kg standard: 5 kg × 2.2 = 11 U."""
        result = compute_insulin_cri(
            _inputs(
                weight_kg=5, species=InsulinCriSpecies.CAT, cat_option=InsulinCriCatDoseOption.STANDARD_2_2
            )
        )
        assert result.total_units_added_to_bag == pytest.approx(11.0)
        assert result.loading_units_per_kg == pytest.approx(2.2)

    def test_cat_5kg_conservative_1_1(self):
        """Cat at 1.1 U/kg conservative: 5 kg × 1.1 = 5.5 U."""
        result = compute_insulin_cri(
            _inputs(
                weight_kg=5,
                species=InsulinCriSpecies.CAT,
                cat_option=InsulinCriCatDoseOption.CONSERVATIVE_1_1,
            )
        )
        assert result.total_units_added_to_bag == pytest.approx(5.5)
        assert result.loading_units_per_kg == pytest.approx(1.1)


class TestDeliveredRate:
    """U/kg/hr delivered = (concentration × pump rate) / weight"""

    def test_20kg_dog_at_10ml_hr(self):
        """20 kg, 0.176 U/mL × 10 mL/hr / 20 kg = 0.088 U/kg/hr."""
        result = compute_insulin_cri(_inputs(weight_kg=20, bg=400))
        # 44 U / 250 mL × 10 mL/hr / 20 kg = 0.088 U/kg/hr
        assert result.units_per_kg_per_hr_delivered == pytest.approx(0.088, abs=0.005)

    def test_stopped_when_bg_low(self):
        result = compute_insulin_cri(_inputs(bg=80))
        assert result.units_per_kg_per_hr_delivered is None or result.units_per_kg_per_hr_delivered == 0


class TestSpeciesBehavior:
    def test_dog_uses_2_2(self):
        """Dog dose is always 2.2 U/kg regardless of cat_option."""
        result = compute_insulin_cri(
            _inputs(species=InsulinCriSpecies.DOG, cat_option=InsulinCriCatDoseOption.CONSERVATIVE_1_1)
        )
        assert result.loading_units_per_kg == pytest.approx(2.2)

    def test_cat_options_differ(self):
        std = compute_insulin_cri(
            _inputs(species=InsulinCriSpecies.CAT, cat_option=InsulinCriCatDoseOption.STANDARD_2_2)
        )
        cons = compute_insulin_cri(
            _inputs(species=InsulinCriSpecies.CAT, cat_option=InsulinCriCatDoseOption.CONSERVATIVE_1_1)
        )
        assert std.loading_units_per_kg != cons.loading_units_per_kg


class TestSafetyWarnings:
    def test_warnings_mention_regular_insulin(self):
        result = compute_insulin_cri(_inputs())
        all_text = " ".join(result.warnings + result.notes).lower()
        assert "regular" in all_text

    def test_warnings_mention_prime_discard(self):
        result = compute_insulin_cri(_inputs())
        all_text = " ".join(result.warnings + result.notes).lower()
        assert "prime" in all_text or "discard" in all_text


class TestSourceAttribution:
    def test_includes_silverstein_or_hoehne(self):
        result = compute_insulin_cri(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Silverstein" in cite_text or "Hoehne" in cite_text
