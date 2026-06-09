"""
Tests for the hypophosphatemia (KPhos CRI) calculator.

Source: Hoehne SN. Diabetic Ketoacidosis. In Silverstein & Hopper
*Small Animal Critical Care Medicine* 3rd ed. Ch. 73, Box 73.1.
KPhos sliding scale: 0.03–0.12 mmol/kg/hr by serum P.

Critical interaction: KPhos contributes K (4.4 mEq K per mL of standard
KPhos = 4.4 mEq K per 3 mmol P). Calculator must track total K delivery
against the 0.5 mEq/kg/hr ceiling when patient is on concurrent KCl.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.hypophosphatemia import (
    HypophosphatemiaInputs,
    KPhosSpecies,
    compute_hypophosphatemia,
)


def _inputs(
    *,
    weight_kg: float = 20,
    species: KPhosSpecies = KPhosSpecies.DOG,
    p: float = 0.8,
    concurrent_kcl: float = 0.0,
) -> HypophosphatemiaInputs:
    return HypophosphatemiaInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        serum_p_mg_per_dl=p,
        concurrent_kcl_meq_per_kg_per_hr=concurrent_kcl,
    )


class TestSlidingScale:
    """Each tier of the sliding scale produces the expected rate."""

    def test_critical_below_0_5(self):
        result = compute_hypophosphatemia(_inputs(p=0.4))
        assert result.target_rate_mmol_per_kg_per_hr == 0.12
        assert result.matched_tier.severity == "critical"
        assert result.not_indicated is False

    def test_severe_0_5_to_1_0(self):
        result = compute_hypophosphatemia(_inputs(p=0.7))
        assert result.target_rate_mmol_per_kg_per_hr == 0.09
        assert result.matched_tier.severity == "severe"

    def test_moderate_1_0_to_1_5(self):
        result = compute_hypophosphatemia(_inputs(p=1.2))
        assert result.target_rate_mmol_per_kg_per_hr == 0.06
        assert result.matched_tier.severity == "moderate"

    def test_mild_1_5_to_2_0(self):
        result = compute_hypophosphatemia(_inputs(p=1.7))
        assert result.target_rate_mmol_per_kg_per_hr == 0.03
        assert result.matched_tier.severity == "mild"

    def test_normal_above_2_0(self):
        result = compute_hypophosphatemia(_inputs(p=2.5))
        assert result.target_rate_mmol_per_kg_per_hr is None
        assert result.not_indicated is True
        assert result.matched_tier.severity == "normophosphatemia"


class TestTierBoundaries:
    """Exact threshold values must fall into the documented tier."""

    @pytest.mark.parametrize(
        "p,expected_severity",
        [
            (0.49, "critical"),
            (0.50, "severe"),
            (0.99, "severe"),
            (1.00, "moderate"),
            (1.49, "moderate"),
            (1.50, "mild"),
            (1.99, "mild"),
            (2.00, "normophosphatemia"),
        ],
    )
    def test_boundary(self, p: float, expected_severity: str):
        result = compute_hypophosphatemia(_inputs(p=p))
        assert result.matched_tier.severity == expected_severity, (
            f"P={p} should be {expected_severity}, got {result.matched_tier.severity}"
        )


class TestKInteraction:
    """KPhos contributes K. Total K delivery ≤ 0.5 mEq/kg/hr ceiling."""

    def test_no_concurrent_kcl_below_ceiling(self):
        """20 kg dog at P 0.4 (critical, 0.12 mmol/kg/hr) — well within ceiling."""
        result = compute_hypophosphatemia(_inputs(weight_kg=20, p=0.4))
        # 0.12 mmol/kg/hr P × 20 kg = 2.4 mmol/hr P
        # 2.4 mmol P / 3 mmol per mL × 4.4 mEq K per mL ≈ 3.52 mEq K/hr
        # 3.52 / 20 kg = 0.176 mEq/kg/hr — below ceiling
        assert result.k_delivered_meq_per_kg_per_hr == pytest.approx(0.176, rel=1e-2)
        assert result.exceeds_k_ceiling is False

    def test_with_concurrent_kcl_total_below_ceiling(self):
        """0.176 from KPhos + 0.3 from KCl = 0.476 — still below 0.5."""
        result = compute_hypophosphatemia(_inputs(p=0.4, concurrent_kcl=0.3))
        assert result.total_k_meq_per_kg_per_hr == pytest.approx(0.476, rel=1e-2)
        assert result.exceeds_k_ceiling is False

    def test_with_concurrent_kcl_total_exceeds_ceiling(self):
        """0.176 from KPhos + 0.4 from KCl = 0.576 — over 0.5."""
        result = compute_hypophosphatemia(_inputs(p=0.4, concurrent_kcl=0.4))
        assert result.total_k_meq_per_kg_per_hr == pytest.approx(0.576, rel=1e-2)
        assert result.exceeds_k_ceiling is True
        assert any("ceiling" in w.lower() or "exceed" in w.lower() for w in result.warnings)

    def test_max_kcl_remaining_calculated(self):
        """Patient on KPhos delivering 0.176 K/kg/hr — should report 0.324 KCl headroom."""
        result = compute_hypophosphatemia(_inputs(p=0.4, concurrent_kcl=0.0))
        assert result.max_kcl_remaining_meq_per_kg_per_hr == pytest.approx(0.324, rel=1e-2)


class TestSpeciesNeutral:
    """Sliding scale is identical for dog and cat."""

    def test_dog_and_cat_get_same_rate(self):
        dog = compute_hypophosphatemia(_inputs(species=KPhosSpecies.DOG, p=0.7))
        cat = compute_hypophosphatemia(_inputs(species=KPhosSpecies.CAT, p=0.7))
        assert dog.target_rate_mmol_per_kg_per_hr == cat.target_rate_mmol_per_kg_per_hr


class TestInputValidation:
    def test_negative_weight_warns(self):
        result = compute_hypophosphatemia(_inputs(weight_kg=-5, p=0.7))
        assert any("weight" in w.lower() for w in result.warnings)

    def test_zero_weight_warns(self):
        result = compute_hypophosphatemia(_inputs(weight_kg=0, p=0.7))
        assert any("weight" in w.lower() for w in result.warnings)

    def test_negative_phosphorus_warns(self):
        result = compute_hypophosphatemia(_inputs(p=-1.0))
        assert any("phosphorus" in w.lower() or "negative" in w.lower() for w in result.warnings)


class TestSourceAttribution:
    def test_includes_citation(self):
        result = compute_hypophosphatemia(_inputs(p=0.7))
        assert len(result.sources) > 0
        cite_text = " ".join(s.citation for s in result.sources)
        # DiBartola Ch. 6 is the textbook source for phosphorus disorders
        assert "DiBartola" in cite_text
