"""
Tests for the calculator engine kernel.

This module is the math heart of the SINGLE_DRUG_CRI family
(norepinephrine, epinephrine, dobutamine, fentanyl). Bugs here would
silently affect dosing across multiple drugs, so coverage matters.

Coverage targets:
  - lb_to_kg unit conversion
  - SINGLE_DRUG_CRI compute() math for all 4 dose units
  - Dilution prep math (compute_dilution)
  - Source citation typing
"""

from __future__ import annotations

import pytest

from app.calculators.engine import (
    LB_PER_KG,
    CalcInputs,
    CalculatorConfig,
    CalculatorKind,
    DilutionInputs,
    DoseRange,
    DoseUnit,
    Source,
    Species,
    WeightUnit,
    compute,
    compute_dilution,
    lb_to_kg,
)


def _config(*, dose_unit: DoseUnit) -> CalculatorConfig:
    """Minimal SINGLE_DRUG_CRI config for testing compute()."""
    return CalculatorConfig(
        slug="test_drug",
        display_name="Test Drug",
        short_name="Test",
        category="test",
        kind=CalculatorKind.SINGLE_DRUG_CRI,
        mechanism_summary="",
        indications_summary="",
        dose_unit=dose_unit,
        default_dose=0.1,
        dose_ranges={Species.DOG: DoseRange(min=0.05, max=0.5)},
        sources=(Source(citation="Test source"),),
    )


def _inputs(*, weight_kg: float = 10, dose: float = 0.1, concentration: float = 100.0) -> CalcInputs:
    return CalcInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        dose=dose,
        concentration_ug_per_ml=concentration,
        species=Species.DOG,
    )


class TestLbToKg:
    """1 kg = 2.2046 lb (LB_PER_KG = 2.2046226218)."""

    def test_known_value(self):
        # 22.046 lb → 10 kg
        assert lb_to_kg(LB_PER_KG * 10) == pytest.approx(10.0, rel=1e-6)

    def test_zero(self):
        assert lb_to_kg(0) == 0

    def test_one_lb(self):
        assert lb_to_kg(1) == pytest.approx(0.4536, abs=0.001)

    def test_constant_is_correct(self):
        """LB_PER_KG should be 2.2046226218 exactly per common usage."""
        assert pytest.approx(2.2046226218, abs=0.0001) == LB_PER_KG


class TestComputeUgKgMin:
    """compute() with µg/kg/min dose unit."""

    def test_basic_math(self):
        """10 kg × 0.1 µg/kg/min × 60 / 100 µg/mL = 0.6 mL/hr."""
        cfg = _config(dose_unit=DoseUnit.UG_PER_KG_PER_MIN)
        result = compute(cfg, _inputs(weight_kg=10, dose=0.1, concentration=100))
        assert result.ml_per_hr_precise == pytest.approx(0.6, rel=1e-3)
        # total ug/min = 1, ug/hr = 60
        assert result.total_dose_ug_per_min == pytest.approx(1.0)
        assert result.total_dose_ug_per_hr == pytest.approx(60.0)

    def test_lb_input_converts(self):
        cfg = _config(dose_unit=DoseUnit.UG_PER_KG_PER_MIN)
        # 22.046 lb = 10 kg → same result as 10 kg input
        result_lb = compute(
            cfg,
            CalcInputs(
                weight_value=LB_PER_KG * 10,
                weight_unit=WeightUnit.LB,
                dose=0.1,
                concentration_ug_per_ml=100,
                species=Species.DOG,
            ),
        )
        result_kg = compute(cfg, _inputs(weight_kg=10))
        assert result_lb.weight_kg == pytest.approx(result_kg.weight_kg, rel=1e-6)
        assert result_lb.ml_per_hr_precise == pytest.approx(result_kg.ml_per_hr_precise, rel=1e-6)


class TestComputeUgKgHr:
    def test_basic_math(self):
        """10 kg × 0.1 µg/kg/hr / 100 µg/mL = 0.01 mL/hr."""
        cfg = _config(dose_unit=DoseUnit.UG_PER_KG_PER_HR)
        result = compute(cfg, _inputs(weight_kg=10, dose=0.1, concentration=100))
        assert result.ml_per_hr_precise == pytest.approx(0.01, rel=1e-3)
        # total_dose_ug_per_min should be None for per-hr unit
        assert result.total_dose_ug_per_min is None
        assert result.total_dose_ug_per_hr == pytest.approx(1.0)


class TestComputeMlPerKgPerHr:
    """ml_per_kg_per_hr = ml_per_hr / weight_kg."""

    def test_division(self):
        cfg = _config(dose_unit=DoseUnit.UG_PER_KG_PER_MIN)
        result = compute(cfg, _inputs(weight_kg=10))
        assert result.ml_per_kg_per_hr == pytest.approx(result.ml_per_hr_precise / 10, rel=1e-6)


class TestComputeDilution:
    """C₁V₁ = C₂V₂ rearrangement."""

    def test_basic_dilution(self):
        """Stock 1000 µg/mL → desired 100 µg/mL in 100 mL.
        Drug vol = (100 × 100) / 1000 = 10 mL.
        Diluent vol = 100 - 10 = 90 mL.
        """
        result = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=1000,
                desired_concentration_ug_per_ml=100,
                final_volume_ml=100,
            )
        )
        assert result.drug_volume_ml == pytest.approx(10.0)
        assert result.diluent_volume_ml == pytest.approx(90.0)

    def test_warns_on_zero_stock(self):
        """Division by zero is prevented by warning."""
        result = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=0,
                desired_concentration_ug_per_ml=100,
                final_volume_ml=100,
            )
        )
        assert any("stock" in w.lower() for w in result.warnings)

    def test_warns_on_zero_desired(self):
        result = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=1000,
                desired_concentration_ug_per_ml=0,
                final_volume_ml=100,
            )
        )
        assert any("desired" in w.lower() for w in result.warnings)

    def test_warns_on_zero_volume(self):
        result = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=1000,
                desired_concentration_ug_per_ml=100,
                final_volume_ml=0,
            )
        )
        assert any("volume" in w.lower() for w in result.warnings)

    def test_warns_on_dilute_upward(self):
        """Cannot dilute to a higher concentration than the stock."""
        result = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=100,
                desired_concentration_ug_per_ml=200,
                final_volume_ml=100,
            )
        )
        assert any("dilute" in w.lower() or "exceed" in w.lower() for w in result.warnings)

    def test_rounded_values(self):
        """drug_volume_ml_rounded and diluent_volume_ml_rounded are 2-decimal rounded."""
        result = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=1000,
                desired_concentration_ug_per_ml=33,
                final_volume_ml=100,
            )
        )
        # exact: 3.3 mL drug; 96.7 mL diluent
        assert result.drug_volume_ml_rounded == pytest.approx(3.3, abs=0.01)
        assert result.diluent_volume_ml_rounded == pytest.approx(96.7, abs=0.01)


class TestDoseRange:
    """DoseRange dataclass functionality."""

    def test_simple_range(self):
        rng = DoseRange(min=0.1, max=1.0)
        assert rng.min == 0.1
        assert rng.max == 1.0
        assert rng.hard_max is None
        assert rng.persistent_warning is None

    def test_with_hard_max(self):
        rng = DoseRange(min=0.1, max=1.0, hard_max=2.0)
        assert rng.hard_max == 2.0


class TestSourceDataclass:
    def test_minimal(self):
        s = Source(citation="Plumb's 10th ed")
        assert s.citation == "Plumb's 10th ed"
        assert s.url is None
        assert s.reviewer is None

    def test_with_reviewer(self):
        s = Source(
            citation="Test",
            url="https://example.com",
            reviewer="Dr. Jane Smith, DACVECC, 2026-04",
        )
        assert s.url == "https://example.com"
        assert "Smith" in s.reviewer

    def test_is_frozen(self):
        """Source is frozen — assignments should raise."""
        s = Source(citation="Test")
        with pytest.raises((AttributeError, Exception)):
            s.citation = "Changed"  # type: ignore


class TestEnums:
    def test_species(self):
        assert Species.DOG.value == "dog"
        assert Species.CAT.value == "cat"

    def test_weight_unit(self):
        assert WeightUnit.KG.value == "kg"
        assert WeightUnit.LB.value == "lb"

    def test_dose_unit_values(self):
        units = {u.value for u in DoseUnit}
        assert "ug/kg/min" in units
        assert "ug/kg/hr" in units
        assert "mg/kg/hr" in units
        assert "mg/kg/min" in units
