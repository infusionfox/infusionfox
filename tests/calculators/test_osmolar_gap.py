"""
Tests for the osmolar gap calculator.

Formula (US units):
  calculated osm = 2 × Na + glucose/18 + BUN/2.8

Worked example:
  Na 145, glucose 100 mg/dL, BUN 20 mg/dL:
  calc = 2 × 145 + 100/18 + 20/2.8
       = 290 + 5.555... + 7.142...
       = 302.7 mOsm/kg

  Measured osm 295 → gap = 295 − 302.7 = −7.7 → within normal limits

  Worked example, elevated:
  Na 150, glucose 120 mg/dL, BUN 30 mg/dL, measured 360:
  calc = 2 × 150 + 120/18 + 30/2.8
       = 300 + 6.667 + 10.714
       = 317.4 mOsm/kg
  Gap = 360 − 317.4 = 42.6 → significantly elevated
"""

from __future__ import annotations

import pytest

from app.calculators.osmolar_gap import (
    GAP_BORDERLINE_CEILING,
    GAP_NORMAL_CEILING,
    OSMOLAR_GAP_CATALOG_ENTRY,
    BunUnit,
    GlucoseUnit,
    OsmolarGapInputs,
    compute_osmolar_gap,
)


class TestBasicMath:
    def test_normal_panel_us_units(self):
        """Na 145, glucose 100, BUN 20 → calc osm 302.7."""
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145,
                glucose_value=100,
                glucose_unit=GlucoseUnit.MG_DL,
                bun_value=20,
                bun_unit=BunUnit.MG_DL,
            )
        )
        assert result.valid is True
        assert result.calculated_osm_mosm_per_kg == pytest.approx(302.7, abs=0.2)
        assert result.na_contribution == 290.0
        assert result.glucose_mmol_per_l == pytest.approx(5.556, abs=0.01)
        assert result.urea_mmol_per_l == pytest.approx(7.143, abs=0.01)

    def test_si_units_match_us(self):
        """Same patient in SI units should produce the same calculated osm."""
        # Na 145 mmol/L is identical to 145 mEq/L for monovalent ion
        # Glucose 100 mg/dL = 5.56 mmol/L
        # BUN 20 mg/dL = urea 7.14 mmol/L
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145,
                glucose_value=5.56,
                glucose_unit=GlucoseUnit.MMOL_L,
                bun_value=7.14,
                bun_unit=BunUnit.MMOL_L,
            )
        )
        assert result.valid is True
        assert result.calculated_osm_mosm_per_kg == pytest.approx(302.7, abs=0.5)


class TestOsmolarGap:
    def test_normal_gap_with_measured(self):
        """Measured 305, calc 302.7 → gap 2.3 → within normal."""
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145,
                glucose_value=100,
                glucose_unit=GlucoseUnit.MG_DL,
                bun_value=20,
                bun_unit=BunUnit.MG_DL,
                measured_osm_mosm_per_kg=305,
            )
        )
        assert result.osmolar_gap == pytest.approx(2.3, abs=0.5)
        assert result.gap_classification == "normal"
        assert result.gap_elevated is False

    def test_borderline_gap(self):
        """Measured 318 minus calc 302.7 = 15.3 → borderline."""
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145,
                glucose_value=100,
                glucose_unit=GlucoseUnit.MG_DL,
                bun_value=20,
                bun_unit=BunUnit.MG_DL,
                measured_osm_mosm_per_kg=318,
            )
        )
        assert result.gap_classification == "borderline"
        assert result.gap_elevated is False

    def test_elevated_gap_with_eg_warning(self):
        """Measured 360, calc 317.4 → gap 42.6 → elevated; antidote warning."""
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=150,
                glucose_value=120,
                glucose_unit=GlucoseUnit.MG_DL,
                bun_value=30,
                bun_unit=BunUnit.MG_DL,
                measured_osm_mosm_per_kg=360,
            )
        )
        assert result.gap_classification == "elevated"
        assert result.gap_elevated is True
        combined = " ".join(result.warnings).lower()
        assert "ethylene glycol" in combined
        assert "fomepizole" in combined or "ethanol" in combined

    def test_no_measured_osm_no_gap(self):
        """Without measured osm, gap is None, only calc osm reported."""
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145,
                glucose_value=100,
                glucose_unit=GlucoseUnit.MG_DL,
                bun_value=20,
                bun_unit=BunUnit.MG_DL,
            )
        )
        assert result.osmolar_gap is None
        assert result.gap_classification == ""
        # Should still surface calculated value in interpretation
        combined = " ".join(result.interpretation)
        assert "303" in combined or "302" in combined


class TestEthanolCorrection:
    def test_ethanol_included_in_calc(self):
        """Ethanol 50 mg/dL = 10.87 mmol/L; should add ~11 to calc osm."""
        baseline = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145, glucose_value=100,
                bun_value=20,
            )
        )
        with_etoh = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145, glucose_value=100,
                bun_value=20,
                ethanol_mg_per_dl=50,
            )
        )
        # 50 / 4.6 ≈ 10.87 mmol/L
        delta = with_etoh.calculated_osm_mosm_per_kg - baseline.calculated_osm_mosm_per_kg
        assert delta == pytest.approx(10.87, abs=0.1)

    def test_ethanol_zero_no_contribution(self):
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145, glucose_value=100,
                bun_value=20,
                ethanol_mg_per_dl=0,
            )
        )
        assert result.ethanol_contribution_mosm == 0.0


class TestValidation:
    def test_missing_na_rejected(self):
        result = compute_osmolar_gap(
            OsmolarGapInputs(na_meq_per_l=0, glucose_value=100, bun_value=20)
        )
        assert result.valid is False
        assert any("sodium" in e.lower() for e in result.errors)

    def test_missing_glucose_rejected(self):
        result = compute_osmolar_gap(
            OsmolarGapInputs(na_meq_per_l=145, glucose_value=0, bun_value=20)
        )
        assert result.valid is False
        assert any("glucose" in e.lower() for e in result.errors)

    def test_missing_bun_rejected(self):
        result = compute_osmolar_gap(
            OsmolarGapInputs(na_meq_per_l=145, glucose_value=100, bun_value=0)
        )
        assert result.valid is False
        assert any("bun" in e.lower() or "urea" in e.lower() for e in result.errors)

    def test_extreme_na_rejected(self):
        result = compute_osmolar_gap(
            OsmolarGapInputs(na_meq_per_l=250, glucose_value=100, bun_value=20)
        )
        assert result.valid is False

    def test_extreme_measured_osm_rejected(self):
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145, glucose_value=100, bun_value=20,
                measured_osm_mosm_per_kg=600,
            )
        )
        assert result.valid is False


class TestClassificationCutoffs:
    def test_normal_ceiling_constant(self):
        assert GAP_NORMAL_CEILING == 10.0

    def test_borderline_ceiling_constant(self):
        assert GAP_BORDERLINE_CEILING == 20.0

    def test_exactly_10_is_borderline(self):
        """Boundary: gap = 10.0 is borderline, not normal."""
        # Construct: measured = calc + 10
        # calc with Na 145, glucose 100, BUN 20 → 302.7
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145, glucose_value=100, bun_value=20,
                measured_osm_mosm_per_kg=313,  # ≈ calc + 10.3
            )
        )
        assert result.gap_classification == "borderline"

    def test_exactly_20_is_elevated(self):
        """Boundary: gap >= 20.0 is elevated."""
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145, glucose_value=100, bun_value=20,
                measured_osm_mosm_per_kg=325,  # ≈ calc + 22.3
            )
        )
        assert result.gap_classification == "elevated"


class TestInterpretationGuidance:
    def test_normal_gap_does_not_rule_out_eg(self):
        """A normal gap must surface the late-EG warning."""
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=145, glucose_value=100, bun_value=20,
                measured_osm_mosm_per_kg=300,
            )
        )
        combined = " ".join(result.interpretation).lower()
        assert "does not rule out" in combined or "does NOT rule out" in " ".join(result.interpretation)
        assert "ethylene glycol" in combined

    def test_elevated_gap_lists_differentials(self):
        result = compute_osmolar_gap(
            OsmolarGapInputs(
                na_meq_per_l=150, glucose_value=120, bun_value=30,
                measured_osm_mosm_per_kg=360,
            )
        )
        combined = " ".join(result.interpretation).lower()
        assert "ethylene glycol" in combined
        # Should mention other differentials too
        assert "mannitol" in combined or "methanol" in combined


class TestCatalogEntry:
    def test_catalog_entry_complete(self):
        for key in ["slug", "display_name", "category", "mechanism_summary"]:
            assert key in OSMOLAR_GAP_CATALOG_ENTRY
        assert OSMOLAR_GAP_CATALOG_ENTRY["slug"] == "osmolar-gap"
        assert OSMOLAR_GAP_CATALOG_ENTRY["category"] == "Acid-base & blood gas"
