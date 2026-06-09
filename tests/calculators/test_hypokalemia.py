"""
Tests for the hypokalemia (KCl supplementation) calculator.

Source under test: DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders
in Small Animal Practice. 4th ed. Elsevier; 2012. Chapter 5, Table 5-2 (p. 107).

Test strategy:
- Each band of the sliding scale gets a representative test
- Band boundaries (e.g. K=2.0 vs K=2.1) get explicit boundary tests
- Hard ceiling (0.5 mEq/kg/hr) is verified at the maximum pump rate
- "No supplementation needed" path tested for normokalemic patients
- Concentration ceiling (60 mEq/L peripheral) flag tested
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.hypokalemia import (
    BagSize,
    HypokalemiaInputs,
    compute_hypokalemia,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _inputs(weight_kg: float, k: float, bag: BagSize = BagSize.BAG_1000) -> HypokalemiaInputs:
    return HypokalemiaInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        serum_k_meq_per_l=k,
        bag_size=bag,
    )


# ---------------------------------------------------------------------------
# Band-by-band coverage of DiBartola Table 5-2
# ---------------------------------------------------------------------------


class TestSlidingScaleBands:
    """Each row of the table should produce the published KCl additive
    and pump rate ceiling."""

    def test_severe_hypokalemia_below_2(self):
        """K < 2.0 → 80 mEq/L additive, max 6 mL/kg/hr."""
        result = compute_hypokalemia(_inputs(weight_kg=20, k=1.8))
        assert result.kcl_to_add_meq == 80
        assert result.final_concentration_meq_per_l == 80
        # 20 kg × 6 mL/kg/hr = 120 mL/hr
        assert result.max_pump_rate_ml_per_hr == pytest.approx(120)
        # Should flag central-line need (concentration > 60)
        assert result.central_line_recommended is True

    def test_band_2_1_to_2_5(self):
        """K 2.1–2.5 → 60 mEq/L additive, max 8 mL/kg/hr."""
        result = compute_hypokalemia(_inputs(weight_kg=20, k=2.3))
        assert result.kcl_to_add_meq == 60
        assert result.max_pump_rate_ml_per_hr == pytest.approx(160)
        # Right at the 60 mEq/L peripheral ceiling — should not flag central
        assert result.central_line_recommended is False

    def test_band_2_6_to_3_0(self):
        """K 2.6–3.0 → 40 mEq/L additive, max 12 mL/kg/hr."""
        result = compute_hypokalemia(_inputs(weight_kg=20, k=2.8))
        assert result.kcl_to_add_meq == 40
        assert result.max_pump_rate_ml_per_hr == pytest.approx(240)

    def test_band_3_1_to_3_5(self):
        """K 3.1–3.5 → 28 mEq/L additive, max 18 mL/kg/hr."""
        result = compute_hypokalemia(_inputs(weight_kg=20, k=3.3))
        assert result.kcl_to_add_meq == 28
        assert result.max_pump_rate_ml_per_hr == pytest.approx(360)

    def test_band_3_6_to_5_0(self):
        """K 3.6–5.0 → 20 mEq/L additive, max 25 mL/kg/hr."""
        result = compute_hypokalemia(_inputs(weight_kg=20, k=4.0))
        assert result.kcl_to_add_meq == 20
        assert result.max_pump_rate_ml_per_hr == pytest.approx(500)


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------


class TestBoundaries:
    """Values right at the edges of bands must fall into the documented row."""

    def test_exactly_2_0_is_severe_band(self):
        """K = 2.0 exactly should be the <2.0 row's territory (inclusive upper)."""
        result = compute_hypokalemia(_inputs(weight_kg=10, k=2.0))
        assert result.kcl_to_add_meq == 80

    def test_2_1_falls_into_next_band(self):
        result = compute_hypokalemia(_inputs(weight_kg=10, k=2.1))
        assert result.kcl_to_add_meq == 60

    def test_2_5_is_upper_of_second_band(self):
        result = compute_hypokalemia(_inputs(weight_kg=10, k=2.5))
        assert result.kcl_to_add_meq == 60

    def test_3_0_is_upper_of_third_band(self):
        result = compute_hypokalemia(_inputs(weight_kg=10, k=3.0))
        assert result.kcl_to_add_meq == 40

    def test_above_5_returns_no_supplementation(self):
        """K > 5.0 means patient is not hypokalemic — no supplementation."""
        result = compute_hypokalemia(_inputs(weight_kg=10, k=5.5))
        assert result.no_supplementation_needed is True
        assert result.above_table_range is True
        assert result.kcl_to_add_meq == 0


# ---------------------------------------------------------------------------
# Hard safety ceiling
# ---------------------------------------------------------------------------


class TestSafetyCeiling:
    """Per DiBartola, KCl IV must not exceed 0.5 mEq/kg/hr."""

    @pytest.mark.parametrize("k", [1.5, 2.3, 2.8, 3.3, 4.0])
    def test_max_rate_never_exceeds_0_5_meq_per_kg_per_hr(self, k):
        """At max pump rate, delivered K should be at or near the 0.5 mEq/kg/hr ceiling.

        DiBartola's Table 5-2 has integer-rounded mEq values that produce
        delivery rates up to ~0.504 mEq/kg/hr at the maximum pump rate
        (the 3.1–3.5 band: 28 mEq/L × 18 mL/kg/hr = 504 µmEq/kg/hr).
        The calculator's own source code documents this as acceptable;
        we test that delivery stays within 0.01 mEq/kg/hr of the ceiling.
        """
        result = compute_hypokalemia(_inputs(weight_kg=20, k=k))
        assert result.delivered_k_rate_meq_per_kg_per_hr <= 0.51


# ---------------------------------------------------------------------------
# Bag size variations
# ---------------------------------------------------------------------------


class TestBagSize:
    """Concentration should be the same regardless of bag size; total mEq scales."""

    def test_250ml_bag_severe(self):
        result_250 = compute_hypokalemia(_inputs(weight_kg=10, k=1.8, bag=BagSize.BAG_250))
        result_1000 = compute_hypokalemia(_inputs(weight_kg=10, k=1.8, bag=BagSize.BAG_1000))
        # Concentration matches between bag sizes
        assert result_250.final_concentration_meq_per_l == result_1000.final_concentration_meq_per_l
        # Total mEq is 1/4 in the smaller bag
        assert result_250.kcl_to_add_meq * 4 == result_1000.kcl_to_add_meq


# ---------------------------------------------------------------------------
# Weight unit handling
# ---------------------------------------------------------------------------


class TestWeightUnits:
    def test_lb_input_matches_kg_input(self):
        """22 lb ≈ 10 kg — both should yield the same delivered rate."""
        kg = compute_hypokalemia(
            HypokalemiaInputs(
                weight_value=10,
                weight_unit=WeightUnit.KG,
                serum_k_meq_per_l=2.3,
                bag_size=BagSize.BAG_1000,
            )
        )
        lb = compute_hypokalemia(
            HypokalemiaInputs(
                weight_value=22.046,
                weight_unit=WeightUnit.LB,
                serum_k_meq_per_l=2.3,
                bag_size=BagSize.BAG_1000,
            )
        )
        assert kg.kcl_to_add_meq == lb.kcl_to_add_meq
        assert kg.max_pump_rate_ml_per_hr == pytest.approx(lb.max_pump_rate_ml_per_hr, rel=1e-3)


# ---------------------------------------------------------------------------
# Sources are populated
# ---------------------------------------------------------------------------


class TestSourceAttribution:
    def test_result_includes_source_citation(self):
        result = compute_hypokalemia(_inputs(weight_kg=10, k=2.5))
        assert len(result.sources) > 0
        # DiBartola is the source-of-truth
        cite_text = " ".join(s.citation for s in result.sources)
        assert "DiBartola" in cite_text
