"""
Tests for the hypernatremia (water deficit) calculator.

Source: DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in
Small Animal Practice. 4th ed. Elsevier; 2012. Ch. 3, pp. 60–61.

Free water deficit formula (used by the calculator):
    deficit (L) = 0.6 × BW(kg) × (current Na / reference Na − 1)

Correction rate ceiling: ≤0.5 mEq/L/hr (≤12 mEq/L/24hr) to avoid cerebral
edema in chronic cases. The calculator surfaces predicted correction
rate so the clinician can verify their plan stays under that ceiling.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.hypernatremia import (
    HyperNaInputs,
    HyperNaMechanism,
    compute_hypernatremia,
)


def _inputs(
    *,
    weight_kg: float = 20.0,
    patient_na: float = 175.0,
    previous_na: float = 145.0,
    mechanism: HyperNaMechanism = HyperNaMechanism.PURE_WATER_LOSS,
    replacement_hours: float = 24.0,
    maintenance_ml_per_hr: float = 0.0,
) -> HyperNaInputs:
    return HyperNaInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        patient_na_meq_per_l=patient_na,
        previous_na_meq_per_l=previous_na,
        mechanism=mechanism,
        replacement_hours=replacement_hours,
        maintenance_ml_per_hr=maintenance_ml_per_hr,
    )


class TestWaterDeficitFormula:
    """deficit = 0.6 × BW × (current/reference − 1)"""

    def test_20kg_dog_175_to_145(self):
        """20 kg, Na 175 → 145.
        Deficit = 0.6 × 20 × (175/145 − 1) = 12 × 0.207 ≈ 2.483 L
        """
        result = compute_hypernatremia(_inputs(weight_kg=20, patient_na=175, previous_na=145))
        expected_l = 0.6 * 20 * (175 / 145 - 1)
        assert result.water_deficit_l == pytest.approx(expected_l, rel=1e-3)
        assert result.water_deficit_ml == pytest.approx(expected_l * 1000, rel=1e-3)

    def test_5kg_cat_165_to_152(self):
        """5 kg, Na 165 → 152.
        Deficit = 0.6 × 5 × (165/152 − 1) ≈ 0.257 L = 257 mL
        """
        result = compute_hypernatremia(_inputs(weight_kg=5, patient_na=165, previous_na=152))
        expected_l = 0.6 * 5 * (165 / 152 - 1)
        assert result.water_deficit_l == pytest.approx(expected_l, rel=1e-2)


class TestReplacementRate:
    """Pump rate = deficit / replacement_hours + maintenance"""

    def test_24hr_replacement(self):
        result = compute_hypernatremia(_inputs(replacement_hours=24))
        assert result.deficit_replacement_ml_per_hr == pytest.approx(result.water_deficit_ml / 24, rel=1e-3)

    def test_48hr_replacement_halves_rate(self):
        r24 = compute_hypernatremia(_inputs(replacement_hours=24))
        r48 = compute_hypernatremia(_inputs(replacement_hours=48))
        # 48-hour replacement runs at half the rate
        assert r48.deficit_replacement_ml_per_hr == pytest.approx(
            r24.deficit_replacement_ml_per_hr / 2, rel=1e-3
        )

    def test_includes_maintenance(self):
        no_maint = compute_hypernatremia(_inputs(maintenance_ml_per_hr=0))
        with_maint = compute_hypernatremia(_inputs(maintenance_ml_per_hr=50))
        assert with_maint.total_ml_per_hr == pytest.approx(
            no_maint.deficit_replacement_ml_per_hr + 50, rel=1e-3
        )


class TestPredictedCorrectionRate:
    """Predicted Na correction over the chosen window."""

    def test_24hr_replacement_full_correction_rate(self):
        """Full deficit replacement over 24 hr brings Na from current to reference."""
        result = compute_hypernatremia(
            _inputs(weight_kg=20, patient_na=175, previous_na=145, replacement_hours=24)
        )
        # Total drop = 30 mEq over 24 hr = 1.25 mEq/L/hr → above the 0.5 ceiling
        assert result.predicted_rate_mEq_per_24hr == pytest.approx(30.0, rel=1e-2)

    def test_acute_case_can_be_corrected_quickly(self):
        """Acute hypernatremia (<48hr onset) tolerates faster correction."""
        result = compute_hypernatremia(
            _inputs(weight_kg=20, patient_na=175, previous_na=145, replacement_hours=12)
        )
        # 30 mEq / 12 hr = 2.5 mEq/L/hr — fast, but acceptable in acute
        assert result.predicted_rate_mEq_per_hr == pytest.approx(30.0 / 12, rel=1e-2)


class TestMechanismProfiles:
    def test_pure_water_loss_returns_profile(self):
        result = compute_hypernatremia(_inputs(mechanism=HyperNaMechanism.PURE_WATER_LOSS))
        assert result.profile is not None
        assert result.profile.name == "Pure water loss"

    def test_hypotonic_loss_returns_profile(self):
        result = compute_hypernatremia(_inputs(mechanism=HyperNaMechanism.HYPOTONIC_LOSS))
        assert result.profile.name != "Pure water loss"

    def test_solute_gain_returns_profile(self):
        result = compute_hypernatremia(_inputs(mechanism=HyperNaMechanism.SOLUTE_GAIN))
        assert result.profile is not None


class TestEdgeCases:
    def test_patient_na_below_reference(self):
        """If patient Na < reference, deficit is negative — calculator should flag."""
        result = compute_hypernatremia(_inputs(patient_na=130, previous_na=145))
        # Either warning emitted, or deficit pinned to zero; behavior is documented in code
        # Most reasonable: deficit calculation runs and produces negative number; warnings
        # advise that the patient isn't hypernatremic.
        assert (
            any(
                "hyperna" in w.lower() or "elevated" in w.lower() or "above" in w.lower()
                for w in result.warnings
            )
            or result.water_deficit_l <= 0
        )

    def test_negative_weight_warns(self):
        result = compute_hypernatremia(_inputs(weight_kg=-5))
        assert any("weight" in w.lower() for w in result.warnings)

    def test_zero_replacement_hours_warns(self):
        result = compute_hypernatremia(_inputs(replacement_hours=0))
        assert any("replacement" in w.lower() or "timeframe" in w.lower() for w in result.warnings)


class TestSourceAttribution:
    def test_includes_dibartola(self):
        result = compute_hypernatremia(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "DiBartola" in cite_text
