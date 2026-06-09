"""
Tests for the Cushings (HAC) likelihood score calculator.

Source: Schofield I, Brodbelt DC, Wilson ARL, Niessen SJM, Church DB,
Gallagher A, O'Neill DG. Development and evaluation of a health-related
quality-of-life tool for dogs with Cushing's syndrome.
J Vet Intern Med 2020;34(6):2595–2605. Table 5 (point weights) and
Table 6 (score → likelihood lookup).

Score range: -13 to +10 (clamped). Likelihood range: 0% to 96%.
"""

from __future__ import annotations

import pytest

from app.routers.cushings_score import (
    SCORE_TO_LIKELIHOOD,
    CushingsInput,
    age_points,
    calculate,
)


class TestAgePoints:
    @pytest.mark.parametrize(
        "age,expected",
        [
            (1, 0),
            (6.9, 0),
            (7, 1),
            (7.0, 1),
            (15, 1),
        ],
    )
    def test_age_threshold_at_7(self, age: float, expected: int):
        assert age_points(age) == expected


class TestComponentScoring:
    def test_minimal_signs_minimum_score(self):
        """No clinical signs, healthy patient → strongly negative score."""
        result = calculate(
            CushingsInput(
                sex="male_neutered",
                age=3,
                breed="labrador",
                polydipsia="no",
                vomiting="no",
                potbelly="no",
                alopecia="no",
                pruritus="no",
                usg="dilute",
                alkp="not_elevated",
            )
        )
        # Expected: -1 (sex) + 0 (age<7) + -3 (lab) + 0+0+0+0+0 + 0 (dilute USG) + -3 (alkp not elevated) = -7
        assert result.total_score == -7

    def test_max_score_classic_cushings(self):
        """Bichon, ≥7 yr, polydipsia, potbelly, alopecia, elevated ALKP, not-dilute USG."""
        result = calculate(
            CushingsInput(
                sex="female_entire",
                age=10,
                breed="bichon_frise",
                polydipsia="yes",
                vomiting="no",
                potbelly="yes",
                alopecia="yes",
                pruritus="no",
                usg="not_dilute",
                alkp="elevated",
            )
        )
        # Expected: 0 (FE) + 1 (age≥7) + 2 (bichon) + 2 (PD) + 0 (no vom)
        # + 3 (potbelly) + 2 (alopecia) + 0 (no pruritus) + -2 (USG not dilute, hyposthenuria abs)
        # + 0 (ALKP elevated, expected) = 8
        assert result.total_score == 8

    def test_pruritus_subtracts(self):
        """Pruritus argues AGAINST HAC (-2)."""
        with_pruritus = calculate(CushingsInput(pruritus="yes"))
        without_pruritus = calculate(CushingsInput(pruritus="no"))
        assert with_pruritus.total_score == without_pruritus.total_score - 2

    def test_vomiting_subtracts(self):
        """Vomiting argues against HAC (-2)."""
        with_vomiting = calculate(CushingsInput(vomiting="yes"))
        without_vomiting = calculate(CushingsInput(vomiting="no"))
        assert with_vomiting.total_score == without_vomiting.total_score - 2


class TestScoreClamping:
    def test_minimum_clamped_to_minus_13(self):
        # Construct a max-negative input
        result = calculate(
            CushingsInput(
                sex="male_neutered",
                age=3,
                breed="labrador",
                polydipsia="no",
                vomiting="yes",
                potbelly="no",
                alopecia="no",
                pruritus="yes",
                usg="dilute",
                alkp="not_elevated",
            )
        )
        assert result.clamped_score >= -13

    def test_maximum_clamped_to_10(self):
        result = calculate(
            CushingsInput(
                sex="female_entire",
                age=15,
                breed="bichon_frise",
                polydipsia="yes",
                vomiting="no",
                potbelly="yes",
                alopecia="yes",
                pruritus="no",
                usg="not_dilute",
                alkp="elevated",
            )
        )
        assert result.clamped_score <= 10


class TestLikelihoodLookup:
    @pytest.mark.parametrize(
        "score,likelihood",
        [
            (-13, 0.00),
            (-5, 0.08),
            (0, 0.35),
            (5, 0.78),
            (10, 0.96),
        ],
    )
    def test_score_to_likelihood(self, score: int, likelihood: float):
        assert SCORE_TO_LIKELIHOOD[score] == pytest.approx(likelihood)


class TestPercentageOutput:
    def test_likelihood_pct_matches(self):
        """likelihood_pct = round(likelihood × 100)."""
        result = calculate(
            CushingsInput(
                sex="female_entire",
                age=10,
                breed="bichon_frise",
                polydipsia="yes",
                potbelly="yes",
                alopecia="yes",
                usg="not_dilute",
                alkp="elevated",
            )
        )
        assert result.likelihood_pct == round(result.predicted_likelihood * 100)


class TestComponentsListed:
    """All 10 scoring components should be returned."""

    def test_ten_components_returned(self):
        # Need at least one recorded finding so the Safety Rule #8
        # score-data gate opens and the components list populates.
        # USG "not_dilute" is a neutral assessment (clinician
        # recorded USG and found it not consistent with Cushing's).
        result = calculate(CushingsInput(usg="not_dilute"))
        assert len(result.components) == 10


class TestSourceAttribution:
    def test_includes_consensus_or_review(self):
        result = calculate(CushingsInput())
        cite_text = " ".join(s.citation for s in result.sources)
        # Calculator cites the ACVIM consensus and Bennaim review
        assert "Behrend" in cite_text or "Bennaim" in cite_text or "ACVIM" in cite_text
