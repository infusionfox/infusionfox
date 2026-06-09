"""
Tests for the oxygenation (P:F + A-a) calculator.

Math verified manually:

  Healthy patient on room air:
    PaO2 95, FiO2 0.21, PaCO2 40
    P:F = 95 / 0.21 = 452.38
    PAO2 = 0.21 × (760 − 47) − 40 / 0.8
         = 0.21 × 713 − 50
         = 149.73 − 50
         = 99.73 mmHg
    A-a = 99.73 − 95 = 4.73 mmHg

  Severe ARDS-equivalent (60% O2 fails to oxygenate):
    PaO2 60, FiO2 0.6, PaCO2 35
    P:F = 60 / 0.6 = 100
    PAO2 = 0.6 × 713 − 35/0.8 = 427.8 − 43.75 = 384.1 mmHg
    A-a = 384.1 − 60 = 324.1 mmHg

  Hypoventilation pattern (high PaCO2, normal A-a):
    PaO2 60, FiO2 0.21, PaCO2 70
    PAO2 = 0.21 × 713 − 70/0.8 = 149.7 − 87.5 = 62.2
    A-a = 62.2 − 60 = 2.2 mmHg  (normal A-a)
    Diagnosis: hypoventilation
"""

from __future__ import annotations

import pytest

from app.calculators.oxygenation import (
    DEFAULT_PATM_MMHG,
    DEFAULT_R,
    OXYGENATION_CATALOG_ENTRY,
    PH2O_MMHG_AT_37C,
    FiO2Unit,
    OxygenationInputs,
    compute_oxygenation,
)


class TestBasicMath:
    def test_healthy_room_air(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=95,
                fio2_value=0.21,
                fio2_unit=FiO2Unit.DECIMAL,
                paco2_mmhg=40,
            )
        )
        assert result.valid is True
        assert result.pf_ratio == pytest.approx(452.4, abs=1.0)
        assert result.pa_o2_alveolar_mmhg == pytest.approx(99.7, abs=0.5)
        assert result.a_a_gradient_mmhg == pytest.approx(4.7, abs=0.5)
        assert result.pf_classification == "normal"
        assert result.on_room_air is True

    def test_percent_fio2_equals_decimal(self):
        """40 percent should equal 0.40 decimal."""
        as_pct = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=100, fio2_value=40, fio2_unit=FiO2Unit.PERCENT,
                paco2_mmhg=40,
            )
        )
        as_dec = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=100, fio2_value=0.40, fio2_unit=FiO2Unit.DECIMAL,
                paco2_mmhg=40,
            )
        )
        assert as_pct.pf_ratio == pytest.approx(as_dec.pf_ratio, abs=0.5)
        assert as_pct.a_a_gradient_mmhg == pytest.approx(
            as_dec.a_a_gradient_mmhg, abs=0.5
        )

    def test_severe_ards_pattern(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=60, fio2_value=0.6, paco2_mmhg=35,
            )
        )
        assert result.pf_ratio == pytest.approx(100, abs=0.5)
        # PAO2 = 0.6 × 713 − 35/0.8 = 384.05
        assert result.pa_o2_alveolar_mmhg == pytest.approx(384.0, abs=1.0)
        # A-a = 384 − 60 = 324
        assert result.a_a_gradient_mmhg == pytest.approx(324.0, abs=2.0)
        assert result.pf_classification == "severe"
        assert result.on_room_air is False

    def test_very_severe_below_100(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=50, fio2_value=0.8, paco2_mmhg=40,
            )
        )
        # P:F = 50 / 0.8 = 62.5
        assert result.pf_ratio == pytest.approx(62.5, abs=0.5)
        assert result.pf_classification == "very_severe"


class TestPFClassificationCutoffs:
    """Verify the Berlin-adapted cutoffs at the boundaries."""

    def test_normal_at_400(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=84, fio2_value=0.21, paco2_mmhg=40,
            )
        )
        # 84 / 0.21 = 400 exactly
        assert result.pf_ratio == pytest.approx(400, abs=0.5)
        assert result.pf_classification == "normal"

    def test_mild_at_399(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=83.9, fio2_value=0.21, paco2_mmhg=40,
            )
        )
        # ~ 399
        assert result.pf_classification == "mild"

    def test_moderate_at_250(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=100, fio2_value=0.4, paco2_mmhg=40,
            )
        )
        assert result.pf_ratio == pytest.approx(250, abs=0.5)
        assert result.pf_classification == "moderate"

    def test_severe_at_150(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=75, fio2_value=0.5, paco2_mmhg=40,
            )
        )
        assert result.pf_ratio == pytest.approx(150, abs=0.5)
        assert result.pf_classification == "severe"


class TestHypoventilationPattern:
    """Normal A-a + hypercapnia + hypoxemia = hypoventilation."""

    def test_normal_a_a_with_high_paco2(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=60, fio2_value=0.21, paco2_mmhg=70,
            )
        )
        # PAO2 = 0.21 × 713 − 70/0.8 = 62.23
        # A-a = 62.23 − 60 = 2.23 → normal
        assert result.a_a_gradient_mmhg == pytest.approx(2.2, abs=0.5)
        combined = " ".join(result.interpretation).lower()
        assert "hypoventilation" in combined

    def test_hypercapnia_warning_fires(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=80, fio2_value=0.21, paco2_mmhg=70,
            )
        )
        combined = " ".join(result.warnings).lower()
        assert "hypoventilation" in combined or "hypercapnia" in combined


class TestVQMismatchPattern:
    """Elevated A-a on room air with normal PaCO2 = V/Q mismatch or shunt."""

    def test_elevated_a_a_on_room_air(self):
        # PaO2 60, FiO2 0.21, PaCO2 40 → A-a should be elevated
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=60, fio2_value=0.21, paco2_mmhg=40,
            )
        )
        # PAO2 = 149.7 − 50 = 99.7
        # A-a = 99.7 − 60 = 39.7
        assert result.a_a_gradient_mmhg > 15
        combined = " ".join(result.interpretation).lower()
        assert "v/q" in combined or "shunt" in combined


class TestAltitudeEffect:
    def test_denver_altitude_lowers_alveolar_po2(self):
        """Denver Patm ~630 mmHg should reduce PAO2."""
        sea_level = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=80, fio2_value=0.21, paco2_mmhg=40,
                patm_mmhg=760,
            )
        )
        denver = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=80, fio2_value=0.21, paco2_mmhg=40,
                patm_mmhg=630,
            )
        )
        # PAO2 at sea level: 0.21 × 713 − 50 = 99.7
        # PAO2 at Denver:    0.21 × 583 − 50 = 72.4
        # The A-a should shrink at altitude because PAO2 dropped
        assert denver.pa_o2_alveolar_mmhg < sea_level.pa_o2_alveolar_mmhg
        assert denver.a_a_gradient_mmhg < sea_level.a_a_gradient_mmhg


class TestValidation:
    def test_missing_pao2_rejected(self):
        result = compute_oxygenation(
            OxygenationInputs(pao2_mmhg=0, fio2_value=0.4, paco2_mmhg=40)
        )
        assert result.valid is False

    def test_missing_fio2_rejected(self):
        result = compute_oxygenation(
            OxygenationInputs(pao2_mmhg=80, fio2_value=0, paco2_mmhg=40)
        )
        assert result.valid is False

    def test_missing_paco2_rejected(self):
        result = compute_oxygenation(
            OxygenationInputs(pao2_mmhg=80, fio2_value=0.4, paco2_mmhg=0)
        )
        assert result.valid is False

    def test_fio2_below_room_air_rejected(self):
        """FiO2 below 0.21 isn't physiological at sea level."""
        result = compute_oxygenation(
            OxygenationInputs(pao2_mmhg=80, fio2_value=0.15, paco2_mmhg=40)
        )
        assert result.valid is False

    def test_fio2_above_100_pct_rejected(self):
        result = compute_oxygenation(
            OxygenationInputs(pao2_mmhg=80, fio2_value=1.5, paco2_mmhg=40)
        )
        assert result.valid is False

    def test_fio2_percent_below_21_rejected(self):
        """21% is room-air floor; 15% should be rejected."""
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=80, fio2_value=15, fio2_unit=FiO2Unit.PERCENT,
                paco2_mmhg=40,
            )
        )
        assert result.valid is False

    def test_extreme_patm_rejected(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=80, fio2_value=0.21, paco2_mmhg=40,
                patm_mmhg=900,
            )
        )
        assert result.valid is False


class TestConstants:
    def test_default_constants(self):
        assert PH2O_MMHG_AT_37C == 47.0
        assert DEFAULT_PATM_MMHG == 760.0
        assert DEFAULT_R == 0.8


class TestCatalogEntry:
    def test_catalog_complete(self):
        for key in ["slug", "display_name", "category", "mechanism_summary"]:
            assert key in OXYGENATION_CATALOG_ENTRY
        assert OXYGENATION_CATALOG_ENTRY["slug"] == "oxygenation"
        assert OXYGENATION_CATALOG_ENTRY["category"] == "Acid-base & blood gas"


class TestSevereHypoxemiaWarning:
    def test_pf_below_100_triggers_warning(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=50, fio2_value=0.8, paco2_mmhg=40,
            )
        )
        combined = " ".join(result.warnings).lower()
        assert "mechanical ventilation" in combined or "p:f" in combined

    def test_pf_above_100_no_severe_warning(self):
        result = compute_oxygenation(
            OxygenationInputs(
                pao2_mmhg=120, fio2_value=0.4, paco2_mmhg=40,
            )
        )
        # P:F = 300 → moderate, not severe. No mechanical-ventilation warning.
        combined = " ".join(result.warnings).lower()
        assert "very severe" not in combined
