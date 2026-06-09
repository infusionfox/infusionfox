"""
Tests for the hypothyroid score calculator.

Source: Corsini A et al. Front Vet Sci 2023; 2024 JVIM hypothyroidism
overdiagnosis paper; 2023 AAHA Selected Endocrinopathies Guidelines.

Adaptive additive-points score for pretest probability of canine hypothyroidism.
Recent illness or steroid exposure REDUCES the score (sick euthyroid concern).
"""

from __future__ import annotations

from app.routers.hypothyroid_score import (
    AGE_POINTS,
    BREED_POINTS,
    DERMATOLOGIC_POINTS,
    NTI_OR_STEROIDS_POINTS,
    HypothyroidInputs,
    calculate,
)


class TestPointTables:
    def test_age_under_2_strongly_negative(self):
        """Hypothyroidism is rare in young dogs."""
        assert AGE_POINTS["under_2"] == -3

    def test_dermatologic_signs_add(self):
        assert DERMATOLOGIC_POINTS["yes"] == 3

    def test_nti_or_steroids_subtract(self):
        """Sick euthyroid is a major false-positive concern."""
        assert NTI_OR_STEROIDS_POINTS["yes"] == -3


class TestBreedRisk:
    def test_golden_doberman_high_risk(self):
        assert BREED_POINTS["golden_retriever"] == 2
        assert BREED_POINTS["doberman"] == 2

    def test_other_breed_zero(self):
        assert BREED_POINTS["other"] == 0


class TestComposite:
    def test_classic_hypothyroid_dog(self):
        """Older Golden with dermatologic signs, alopecia, lethargy,
        weight gain, hypercholesterolemia → strong score."""
        result = calculate(
            HypothyroidInputs(
                age_band="over_6",
                breed="golden_retriever",
                dermatologic="yes",
                alopecia="yes",
                lethargy="yes",
                weight_gain="yes",
                cold_intolerance="yes",
                hypercholesterolemia="yes",
                normal_cholesterol="no",
                anemia="yes",
                nti_or_steroids="no",
            )
        )
        # 1 (age) + 2 (golden) + 3 (derm) + 3 (alopecia) + 2 (lethargy)
        # + 2 (weight gain) + 1 (cold) + 3 (hyperchol) + 1 (anemia) = 18
        assert result.total_score == 18

    def test_young_dog_negative(self):
        result = calculate(
            HypothyroidInputs(
                age_band="under_2",
                breed="other",
                # anemia="no" opens the Safety Rule #8 score-data gate
                # (anemia != "not_recorded") so calculate() proceeds.
                # The "no" answer contributes 0 points, so the assertion
                # below still probes the age contribution in isolation.
                anemia="no",
            )
        )
        # -3 (age) + 0 (breed) = -3
        assert result.total_score == -3

    def test_nti_reduces_score(self):
        """Same dog without vs with concurrent illness/steroids."""
        without = calculate(
            HypothyroidInputs(
                age_band="over_6",
                breed="golden_retriever",
                dermatologic="yes",
                alopecia="yes",
                nti_or_steroids="no",
            )
        )
        with_nti = calculate(
            HypothyroidInputs(
                age_band="over_6",
                breed="golden_retriever",
                dermatologic="yes",
                alopecia="yes",
                nti_or_steroids="yes",
            )
        )
        assert with_nti.total_score == without.total_score - 3

    def test_normal_cholesterol_subtracts(self):
        """Documented normal cholesterol argues against hypothyroidism."""
        # Both branches need at least one recorded clinical finding so
        # the Safety Rule #8 score-data gate opens in calculate(); the
        # contributing-zero anemia="no" sentinel is the most neutral
        # choice. The delta of -2 between the two scores is what this
        # test pins down.
        without = calculate(HypothyroidInputs(normal_cholesterol="no", anemia="no"))
        with_normal = calculate(HypothyroidInputs(normal_cholesterol="yes", anemia="no"))
        assert with_normal.total_score == without.total_score - 2


class TestLikelihoodBands:
    def test_score_zero_or_negative_low(self):
        # anemia="no" opens the score-data gate so the band/percent
        # fields are populated; the test still verifies that an under_2
        # dog produces a low band.
        result = calculate(HypothyroidInputs(age_band="under_2", anemia="no"))
        assert result.likelihood_pct <= 10
        assert "low" in result.band_label.lower()

    def test_high_score_high_band(self):
        result = calculate(
            HypothyroidInputs(
                age_band="over_6",
                breed="golden_retriever",
                dermatologic="yes",
                alopecia="yes",
                lethargy="yes",
                weight_gain="yes",
                hypercholesterolemia="yes",
            )
        )
        # Score should land in high band
        assert result.likelihood_pct >= 30


class TestSourceAttribution:
    def test_includes_citation(self):
        result = calculate(HypothyroidInputs())
        assert len(result.sources) > 0
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Corsini" in cite_text or "AAHA" in cite_text or "hypothyroid" in cite_text.lower()
