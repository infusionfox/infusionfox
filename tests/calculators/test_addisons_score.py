"""
Tests for the Addison's (HOAC) likelihood score calculator.

Based on synthesis of multiple HOAC clinical-decision-support reviews.
Strongest single discriminator is resting cortisol (>2 µg/dL effectively
rules out HOAC; <1 µg/dL is highly suggestive in the right clinical context).
"""

from __future__ import annotations

import pytest

from app.routers.addisons_score import (
    AddisonsInputs,
    age_points,
    calculate,
    cortisol_points,
    eosinophil_points,
    lymphocyte_points,
    na_k_ratio_points,
)


class TestNaKRatioBands:
    @pytest.mark.parametrize(
        "ratio,expected_pts",
        [
            (20, 6),  # < 24 markedly low
            (23.9, 6),
            (24, 4),  # 24-26.9 low
            (26.9, 4),
            (27, 1),  # 27-31.9 low-normal
            (31.9, 1),
            (32, 0),  # ≥32 normal
            (40, 0),
        ],
    )
    def test_na_k_bands(self, ratio: float, expected_pts: int):
        pts, _ = na_k_ratio_points(ratio)
        assert pts == expected_pts

    def test_zero_ratio_returns_zero_points(self):
        pts, label = na_k_ratio_points(0)
        assert pts == 0
        assert "not" in label.lower()


class TestCortisolPoints:
    """The strongest discriminator."""

    def test_below_1_strongly_supports(self):
        pts, _ = cortisol_points(0.5)
        assert pts == 5

    def test_1_to_2_supports(self):
        pts, _ = cortisol_points(1.5)
        assert pts == 3

    def test_above_2_rules_out(self):
        """>2 µg/dL → -8 (rules out HOAC)."""
        pts, _ = cortisol_points(3.0)
        assert pts == -8

    def test_zero_not_measured(self):
        pts, label = cortisol_points(0)
        assert pts == 0
        assert "not" in label.lower()


class TestLymphocytes:
    def test_lymphocytosis_adds_points(self):
        pts, _ = lymphocyte_points(6000)
        assert pts == 3

    def test_low_lymph_argues_against(self):
        """Low lymph (stress leukogram) argues AGAINST HOAC."""
        pts, _ = lymphocyte_points(800)
        assert pts == -2


class TestEosinophils:
    def test_eosinophilia_adds_points(self):
        pts, _ = eosinophil_points(2000)
        assert pts == 2

    def test_eosinopenia_subtracts(self):
        """Eosinopenia (stress leukogram) argues against."""
        pts, _ = eosinophil_points(50)
        assert pts == -1


class TestAgeBand:
    def test_typical_age_range(self):
        pts, _ = age_points(4)
        assert pts == 1

    def test_juvenile(self):
        pts, _ = age_points(0.5)
        assert pts == 0

    def test_older(self):
        pts, _ = age_points(10)
        assert pts == 0


class TestComposite:
    def test_strong_supportive_picture(self):
        """Young SCWT, classic Addisonian: low Na/K, lymphocytosis, very low cortisol."""
        result = calculate(
            AddisonsInputs(
                age=3,
                breed="wheaten_terrier",
                na_k_ratio=22,
                lymphocytes_per_ul=6500,
                eosinophils_per_ul=2000,
                no_stress_leukogram="yes",
                gi_waxing_waning="yes",
                hypoglycemia="yes",
                hypercalcemia="yes",
                resting_cortisol_ug_dl=0.3,
            )
        )
        # 1 (age) + 2 (breed) + 6 (Na/K) + 3 (lymph) + 2 (eos) + 2 (no-stress)
        # + 3 (GI) + 1 (hypogly) + 1 (hyperca) + 5 (cort) = 26
        assert result.total_score == 26

    def test_high_cortisol_dominates(self):
        """Cortisol >2 should drive total very negative even with other supportive findings."""
        result = calculate(
            AddisonsInputs(
                age=4,
                breed="standard_poodle",
                na_k_ratio=22,
                lymphocytes_per_ul=6500,
                resting_cortisol_ug_dl=4.0,  # rules out → -8
            )
        )
        # Should be net negative or low overall
        assert result.total_score < 8


class TestLikelihoodBands:
    """Likelihood band depends on total score."""

    def test_negative_score_very_low(self):
        result = calculate(AddisonsInputs(resting_cortisol_ug_dl=4.0))
        # cortisol > 2 → -8 → very low
        assert result.likelihood_pct <= 5
        assert "low" in result.band_label.lower()


class TestSourceAttribution:
    def test_includes_citation(self):
        result = calculate(AddisonsInputs())
        assert len(result.sources) > 0
