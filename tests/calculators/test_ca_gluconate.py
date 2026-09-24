"""
Tests for the calcium gluconate (hyperK membrane stabilization) calculator.

Source: Cooper ES. Urethral Obstruction. In Silverstein & Hopper 3rd ed Ch. 122.
DiBartola Ch. 5.

Stock: 10% calcium gluconate
    100 mg/mL salt = 9.3 mg/mL elemental Ca = 0.465 mEq/mL Ca²⁺
Dose: 0.5–1.5 mL/kg IV over 10–20 min with continuous ECG.

Critical: never IM/SC, never with bicarbonate or KPhos in same line.
"""

from __future__ import annotations

import pytest

from app.calculators.ca_gluconate import (
    CA_GLUCONATE_ELEMENTAL_CA_MG_PER_ML,
    CA_GLUCONATE_MEQ_PER_ML,
    CA_GLUCONATE_MG_PER_ML,
    CaGluconateInputs,
    CaGluconateSpecies,
    compute_ca_gluconate,
)
from app.calculators.engine import WeightUnit


def _inputs(
    *,
    weight_kg: float = 5.0,
    species: CaGluconateSpecies = CaGluconateSpecies.CAT,
    dose_ml_per_kg: float = 1.0,
    duration_min: float = 15.0,
) -> CaGluconateInputs:
    return CaGluconateInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        dose_ml_per_kg=dose_ml_per_kg,
        duration_min=duration_min,
    )


class TestVolumeMath:
    def test_5kg_cat_default_dose(self):
        """5 kg × 1.0 mL/kg = 5 mL total volume."""
        result = compute_ca_gluconate(_inputs(weight_kg=5, dose_ml_per_kg=1.0))
        assert result.total_volume_ml == pytest.approx(5.0)
        # 5 mL × 100 mg/mL = 500 mg salt
        assert result.total_dose_mg == pytest.approx(500.0)
        # 5 mL × 9.3 mg/mL = 46.5 mg elemental Ca
        assert result.elemental_ca_mg == pytest.approx(46.5, abs=0.05)
        # 5 mL × 0.465 mEq/mL = 2.325 mEq Ca²⁺ (calculator rounds to 2.33)
        assert result.elemental_ca_meq == pytest.approx(2.33, abs=0.01)

    def test_30kg_dog_max_dose(self):
        """30 kg × 1.5 mL/kg = 45 mL."""
        result = compute_ca_gluconate(
            _inputs(weight_kg=30, species=CaGluconateSpecies.DOG, dose_ml_per_kg=1.5)
        )
        assert result.total_volume_ml == pytest.approx(45.0)
        assert result.elemental_ca_meq == pytest.approx(45 * CA_GLUCONATE_MEQ_PER_ML, rel=1e-3)


class TestInfusionRate:
    def test_15min_default(self):
        """5 kg, 1 mL/kg dose = 5 mL over 15 min = 0.333 mL/min (rounded to 0.33)."""
        result = compute_ca_gluconate(_inputs(weight_kg=5, duration_min=15))
        assert result.infusion_rate_ml_per_min == pytest.approx(5.0 / 15, abs=0.01)

    def test_20min_doubles_no_change(self):
        """Same dose over longer time = lower rate."""
        r15 = compute_ca_gluconate(_inputs(duration_min=15))
        r20 = compute_ca_gluconate(_inputs(duration_min=20))
        assert r20.infusion_rate_ml_per_min < r15.infusion_rate_ml_per_min


class TestDoseClamping:
    def test_below_minimum_clamps_to_min(self):
        """Dose below 0.5 mL/kg should clamp to 0.5 with warning."""
        result = compute_ca_gluconate(_inputs(dose_ml_per_kg=0.1))
        assert result.dose_ml_per_kg == 0.5
        assert any("range" in w.lower() or "minimum" in w.lower() for w in result.warnings)

    def test_above_maximum_clamps_to_max(self):
        """Dose above 1.5 mL/kg should clamp to 1.5 with warning."""
        result = compute_ca_gluconate(_inputs(dose_ml_per_kg=3.0))
        assert result.dose_ml_per_kg == 1.5
        assert any("range" in w.lower() or "maximum" in w.lower() for w in result.warnings)

    def test_within_range_no_clamp(self):
        result = compute_ca_gluconate(_inputs(dose_ml_per_kg=1.0))
        assert result.dose_ml_per_kg == 1.0


class TestDurationClamping:
    def test_too_fast_warns(self):
        """Infusion under 10 min should clamp / warn."""
        result = compute_ca_gluconate(_inputs(duration_min=2))
        assert result.duration_min >= 10
        assert any(
            "duration" in w.lower() or "fast" in w.lower() or "rapid" in w.lower() for w in result.warnings
        )


class TestStockConstants:
    """Verify the encoded stock concentrations match the published 10% formulation."""

    def test_salt_concentration(self):
        assert CA_GLUCONATE_MG_PER_ML == 100.0  # 10% w/v

    def test_elemental_ca_concentration(self):
        assert CA_GLUCONATE_ELEMENTAL_CA_MG_PER_ML == 9.3

    def test_meq_concentration(self):
        # 9.3 mg / 40.08 g/mol × 2 (charge) ≈ 0.464; rounded to 0.465 in code
        assert pytest.approx(0.465, abs=0.001) == CA_GLUCONATE_MEQ_PER_ML


class TestSpeciesNeutral:
    """Dose range is the same for dog and cat."""

    def test_dog_and_cat_get_same_dose_range(self):
        dog = compute_ca_gluconate(_inputs(species=CaGluconateSpecies.DOG, weight_kg=5))
        cat = compute_ca_gluconate(_inputs(species=CaGluconateSpecies.CAT, weight_kg=5))
        assert dog.total_volume_ml == cat.total_volume_ml


class TestSafetyWarnings:
    """The persistent warnings about admin route, line compatibility, etc."""

    def test_warnings_include_chloride_distinction(self):
        result = compute_ca_gluconate(_inputs())
        all_warnings = " ".join(result.warnings).lower() + " ".join(result.notes).lower()
        assert "chloride" in all_warnings or "gluconate" in all_warnings

    def test_warnings_mention_ecg(self):
        result = compute_ca_gluconate(_inputs())
        all_warnings = " ".join(result.warnings).lower() + " ".join(result.notes).lower()
        assert "ecg" in all_warnings

    def test_warnings_mention_bridging(self):
        """Calcium is a bridge; K-lowering therapy must follow."""
        result = compute_ca_gluconate(_inputs())
        all_text = " ".join(result.warnings).lower() + " ".join(result.notes).lower()
        # Should mention insulin/dextrose, fluids, or "bridge"/"buys time"/"K-lowering"
        assert any(
            kw in all_text for kw in ["insulin", "dextrose", "bridge", "buys time", "lowering", "definitive"]
        )


class TestSourceAttribution:
    def test_includes_silverstein_or_dibartola(self):
        result = compute_ca_gluconate(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Silverstein" in cite_text or "DiBartola" in cite_text or "Cooper" in cite_text


class TestStockConcentration23Pct:
    """Dilution recipe for 23% (equine) stock: draw 10/23 × target volume
    of 23%, top up with saline to the same target volume, yielding a
    10%-equivalent solution."""

    def _make(self, weight_kg: float, dose_ml_per_kg: float, stock: str):
        from app.calculators.ca_gluconate import (
            CaGluconateInputs,
            CaGluconateSpecies,
            StockConcentration,
            compute_ca_gluconate,
        )
        from app.calculators.engine import WeightUnit

        return compute_ca_gluconate(
            CaGluconateInputs(
                weight_value=weight_kg,
                weight_unit=WeightUnit.KG,
                species=CaGluconateSpecies.CAT,
                dose_ml_per_kg=dose_ml_per_kg,
                duration_min=15,
                stock_concentration=StockConcentration(stock),
            )
        )

    def test_23pct_populates_dilution_recipe(self):
        r = self._make(weight_kg=5.0, dose_ml_per_kg=1.0, stock="23")
        assert r.stock_23pct_volume_ml is not None
        assert r.diluent_volume_ml is not None
        assert r.diluted_final_volume_ml == r.total_volume_ml

    def test_23pct_recipe_math_5kg_cat(self):
        # 5 kg × 1.0 mL/kg = 5 mL of 10% equivalent
        # 23% stock: draw 5 × 10/23 = 2.174 mL, add 5 - 2.174 = 2.826 mL saline
        r = self._make(weight_kg=5.0, dose_ml_per_kg=1.0, stock="23")
        assert r.total_volume_ml == 5.0
        assert abs(r.stock_23pct_volume_ml - 2.17) < 0.02
        assert abs(r.diluent_volume_ml - 2.83) < 0.02

    def test_10pct_leaves_dilution_recipe_none(self):
        r = self._make(weight_kg=5.0, dose_ml_per_kg=1.0, stock="10")
        assert r.stock_23pct_volume_ml is None
        assert r.diluent_volume_ml is None
        assert r.diluted_final_volume_ml is None

    def test_23pct_delivers_same_elemental_ca_as_10pct(self):
        # Whole point of the dilution: elemental Ca and mEq are identical.
        r10 = self._make(weight_kg=5.0, dose_ml_per_kg=1.0, stock="10")
        r23 = self._make(weight_kg=5.0, dose_ml_per_kg=1.0, stock="23")
        assert r10.elemental_ca_mg == r23.elemental_ca_mg
        assert r10.elemental_ca_meq == r23.elemental_ca_meq
        assert r10.total_dose_mg == r23.total_dose_mg

    def test_23pct_warning_present(self):
        r = self._make(weight_kg=5.0, dose_ml_per_kg=1.0, stock="23")
        assert any("23%" in w and "neat" in w.lower() for w in r.warnings)

    def test_10pct_no_23pct_warning(self):
        r = self._make(weight_kg=5.0, dose_ml_per_kg=1.0, stock="10")
        assert not any("23%" in w for w in r.warnings)

    def test_23pct_dilution_note_in_notes(self):
        r = self._make(weight_kg=5.0, dose_ml_per_kg=1.0, stock="23")
        joined = " ".join(r.notes)
        assert "Dilution recipe" in joined
        assert "0.9% NaCl" in joined
