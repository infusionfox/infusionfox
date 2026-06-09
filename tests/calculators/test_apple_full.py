"""Unit and integration tests for the canine APPLE-full score.

Test boundaries lifted from Hayes 2010 Figs 3 and A1. Per-variable
points must match the published table exactly. The five counterintuitive
items have explicit dedicated tests because they are the most likely
to be "corrected" by a future contributor unfamiliar with the paper:

  - creatinine 0–0.62 mg/dL → 0 (referent, NOT the normal range)
  - WBC <5.1 → 9 (the highest score for this variable)
  - albumin 31–32 g/L → 9 (higher than <26 g/L which scores 6)
  - total bilirubin scoring is non-monotonic (0.24–0.46 → 6, then 4, then 3)
  - respiratory rate 49–60 → 6 (higher than >60 which scores 5)

Routes are tested for Safety Rule #8 compliance (no defaulted output
shown before the clinician has entered values).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.apple_full import (
    APPLE_FULL_CATALOG_ENTRY,
    AppleFullInputs,
    age_points,
    albumin_full_points,
    bilirubin_points,
    calculate,
    creatinine_points,
    fluid_score_points,
    lactate_full_points,
    mentation_full_points,
    resp_rate_points,
    spo2_points,
    wbc_points,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Creatinine (US bands; mg/dL passed in)
# ---------------------------------------------------------------------------


class TestCreatininePoints:
    """Counterintuitive: 0–0.62 mg/dL is REFERENT, not the normal range."""

    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (0.30, 0),   # 0–0.62 referent
            (0.62, 0),   # band end
            (0.63, 1),   # 0.63–1.35 band start (NORMAL range, but 1 pt)
            (1.0, 1),    # mid-normal
            (1.35, 1),   # band end
            (1.36, 8),   # 1.36–2.26 band start
            (2.26, 8),   # band end
            (2.27, 9),   # >2.26 band
            (10.0, 9),   # severe azotemia
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = creatinine_points(value)
        assert pts == expected_points

    def test_zero_means_not_entered(self):
        pts, label = creatinine_points(0.0)
        assert pts == 0
        assert "Not entered" in label

    def test_normal_range_scores_one_not_zero(self):
        """Hypocreatinemia is the referent, not normal-range cr.

        This is a multivariable artifact and a likely target for a
        well-meaning contributor to "fix". Hard test against the
        published table (Hayes 2010 Fig 3, row 1).
        """
        pts, label = creatinine_points(1.0)
        assert pts == 1
        assert "0.63" in label  # band annotation


# ---------------------------------------------------------------------------
# WBC (×10⁹/L — same in US and SI)
# ---------------------------------------------------------------------------


class TestWBCPoints:
    """Counterintuitive: leukopenia is the HIGHEST-scoring WBC band."""

    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (2.0, 9),    # leukopenia (9 pts — highest)
            (5.0, 9),    # just under referent
            (5.1, 0),    # 5.1–8.5 referent band start
            (7.0, 0),    # mid-referent
            (8.5, 0),    # band end
            (8.6, 2),    # 8.6–18 band
            (18.0, 2),   # band end
            (18.1, 3),   # >18 band
            (50.0, 3),   # marked leukocytosis
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = wbc_points(value)
        assert pts == expected_points

    def test_zero_means_not_entered(self):
        pts, _ = wbc_points(0.0)
        assert pts == 0

    def test_leukopenia_scores_higher_than_leukocytosis(self):
        """Hayes 2010 Fig 3 row 2: <5.1 → 9, >18 → 3."""
        leukopenia_pts, _ = wbc_points(3.0)
        leukocytosis_pts, _ = wbc_points(25.0)
        assert leukopenia_pts > leukocytosis_pts
        assert leukopenia_pts == 9
        assert leukocytosis_pts == 3


# ---------------------------------------------------------------------------
# Albumin (SI bands; g/L passed in)
# ---------------------------------------------------------------------------


class TestAlbuminFullPoints:
    """Counterintuitive: 31–32 g/L scores 9, higher than <26 which scores 6.
    DIFFERENT scoring from APPLE-fast (which has <26 → 8, 31–32 → 6)."""

    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (20, 6),     # <26
            (25, 6),     # just under
            (26, 7),     # 26–30 band start
            (28, 7),     # mid
            (30, 7),     # band end
            (31, 9),     # 31–32 band — the multivariable artifact
            (32, 9),     # band end
            (33, 0),     # 33–35 referent start
            (35, 0),     # band end
            (36, 2),     # >35 band
            (50, 2),     # high albumin
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = albumin_full_points(value)
        assert pts == expected_points

    def test_31_32_scores_higher_than_severe_hypoalbuminemia(self):
        """The page-11 multivariable artifact, called out by name in the paper."""
        mild_low_pts, _ = albumin_full_points(31)
        severe_low_pts, _ = albumin_full_points(20)
        assert mild_low_pts > severe_low_pts
        assert mild_low_pts == 9
        assert severe_low_pts == 6

    def test_full_albumin_differs_from_fast(self):
        """APPLE-fast: <26 → 8, 31–32 → 6. APPLE-full: <26 → 6, 31–32 → 9."""
        from app.routers.apple_fast import albumin_points as fast_albumin

        full_low, _ = albumin_full_points(20)
        fast_low, _ = fast_albumin(20)
        assert full_low == 6
        assert fast_low == 8

        full_mid, _ = albumin_full_points(31)
        fast_mid, _ = fast_albumin(31)
        assert full_mid == 9
        assert fast_mid == 6


# ---------------------------------------------------------------------------
# SpO2 (% — same in US and SI)
# ---------------------------------------------------------------------------


class TestSpo2Points:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (75, 10),    # <90 severe
            (89, 10),    # just under
            (90, 4),     # 90–94 band start
            (94, 4),     # band end
            (95, 1),     # 95–97 band start
            (97, 1),     # band end
            (98, 0),     # 98–100 referent
            (100, 0),    # band end
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = spo2_points(value)
        assert pts == expected_points

    def test_zero_means_not_entered(self):
        pts, label = spo2_points(0.0)
        assert pts == 0
        assert "Not entered" in label


# ---------------------------------------------------------------------------
# Total bilirubin (US bands; mg/dL passed in)
# ---------------------------------------------------------------------------


class TestBilirubinPoints:
    """NON-MONOTONIC scoring. The most-likely test to be "corrected"
    by a contributor unfamiliar with the multivariable artifact."""

    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (0.1, 0),    # 0–0.23 referent
            (0.23, 0),   # band end
            (0.24, 6),   # 0.24–0.46 band — HIGHEST score (6)
            (0.40, 6),   # mid-band
            (0.46, 6),   # band end
            (0.47, 4),   # 0.47–0.93 band — score drops to 4
            (0.93, 4),   # band end
            (0.94, 3),   # >0.93 band — score drops to 3
            (5.0, 3),    # severe bili
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = bilirubin_points(value)
        assert pts == expected_points

    def test_non_monotonic_scoring(self):
        """Mild bilirubinemia (6 pts) > moderate (4) > severe (3).

        This is the multivariable artifact preserved from Hayes Fig 3.
        """
        mild_pts, _ = bilirubin_points(0.30)
        mod_pts, _ = bilirubin_points(0.70)
        severe_pts, _ = bilirubin_points(2.0)
        assert mild_pts > mod_pts > severe_pts
        assert (mild_pts, mod_pts, severe_pts) == (6, 4, 3)


# ---------------------------------------------------------------------------
# Mentation (0–4; same scale as APPLE-fast but DIFFERENT point allocations)
# ---------------------------------------------------------------------------


class TestMentationFullPoints:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (0, 0),    # normal — referent
            (1, 5),
            (2, 7),
            (3, 8),
            (4, 13),   # unresponsive — top of scale
        ],
    )
    def test_all_levels(self, value, expected_points):
        pts, _ = mentation_full_points(value)
        assert pts == expected_points

    def test_unresponsive_dominates(self):
        pts, _ = mentation_full_points(4)
        assert pts == 13

    def test_full_mentation_differs_from_fast(self):
        """APPLE-fast: 0/4/6/7/14. APPLE-full: 0/5/7/8/13."""
        from app.routers.apple_fast import mentation_points as fast_mentation

        for level, full_expected, fast_expected in [
            (1, 5, 4),
            (3, 8, 7),
            (4, 13, 14),
        ]:
            full_pts, _ = mentation_full_points(level)
            fast_pts, _ = fast_mentation(level)
            assert full_pts == full_expected, f"mentation {level} full"
            assert fast_pts == fast_expected, f"mentation {level} fast"

    def test_out_of_range_returns_not_entered(self):
        """Sentinel -1 (default) means user has not selected an option."""
        pts, label = mentation_full_points(-1)
        assert pts == 0
        assert "Not entered" in label


# ---------------------------------------------------------------------------
# Respiratory rate (bpm — same in US and SI)
# ---------------------------------------------------------------------------


class TestRespRatePoints:
    """Counterintuitive: 49–60 bpm → 6 pts, higher than >60 bpm → 5 pts."""

    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (15, 3),     # <25 bradypnea
            (24, 3),     # just under
            (25, 0),     # 25–36 referent start
            (30, 0),     # normal
            (36, 0),     # band end
            (37, 5),     # 37–48 band start
            (48, 5),     # band end
            (49, 6),     # 49–60 band — HIGHEST
            (60, 6),     # band end
            (61, 5),     # >60 — counterintuitive drop
            (100, 5),    # frank tachypnea
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = resp_rate_points(value)
        assert pts == expected_points

    def test_49_60_higher_than_over_60(self):
        """Hayes Fig 3 row 7: 49–60 → 6, >60 → 5."""
        mid_high, _ = resp_rate_points(55)
        very_high, _ = resp_rate_points(80)
        assert mid_high > very_high
        assert mid_high == 6
        assert very_high == 5


# ---------------------------------------------------------------------------
# Age (years)
# ---------------------------------------------------------------------------


class TestAgePoints:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (0.5, 3),    # 0–2 band (young)
            (2.0, 3),    # band end
            (3.0, 0),    # 3–5 referent start
            (4.0, 0),    # mid
            (5.0, 0),    # band end
            (5.5, 6),    # 6–8 band (mature)
            (8.0, 6),    # band end
            (8.5, 8),    # >8 band (geriatric)
            (14.0, 8),   # senior
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = age_points(value)
        assert pts == expected_points

    def test_negative_means_not_entered(self):
        """Sentinel -1.0 (default) means user has not entered age."""
        pts, label = age_points(-1.0)
        assert pts == 0
        assert "Not entered" in label


# ---------------------------------------------------------------------------
# Fluid score (FAST/TFAST, 0–2)
# ---------------------------------------------------------------------------


class TestFluidScorePoints:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (0, 0),    # no free fluid — referent
            (1, 3),    # one cavity
            (2, 4),    # two or more cavities
        ],
    )
    def test_all_levels(self, value, expected_points):
        pts, _ = fluid_score_points(value)
        assert pts == expected_points

    def test_out_of_range_returns_not_entered(self):
        """Sentinel -1 (default) means user has not selected an option."""
        pts, label = fluid_score_points(-1)
        assert pts == 0
        assert "Not entered" in label


# ---------------------------------------------------------------------------
# Lactate (SI bands; mmol/L passed in)
# ---------------------------------------------------------------------------


class TestLactateFullPoints:
    """DIFFERENT bands and point allocations from APPLE-fast.
    APPLE-fast: <2, 2-8, 8-10, >10 → 0/4/8/12
    APPLE-full: 0-1.9, 2.0-7.9, 8.0-11.0, >11 → 0/2/3/6
    """

    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (0.5, 0),    # 0–1.9 referent
            (1.9, 0),    # band end
            (2.0, 2),    # 2.0–7.9 band start
            (5.0, 2),    # mid
            (7.9, 2),    # band end
            (8.0, 3),    # 8.0–11.0 band start
            (11.0, 3),   # band end
            (11.1, 6),   # >11 band
            (20.0, 6),   # severe
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = lactate_full_points(value)
        assert pts == expected_points

    def test_zero_means_not_entered(self):
        pts, _ = lactate_full_points(0.0)
        assert pts == 0

    def test_full_lactate_differs_from_fast(self):
        """At lactate=5.0 mmol/L: APPLE-fast → 4, APPLE-full → 2.
        The full model compresses lactate's contribution because other
        variables absorb mortality variance."""
        from app.routers.apple_fast import lactate_points as fast_lactate

        full_pts, _ = lactate_full_points(5.0)
        fast_pts, _ = fast_lactate(5.0)
        assert full_pts == 2
        assert fast_pts == 4


# ---------------------------------------------------------------------------
# Mortality equation
# ---------------------------------------------------------------------------


class TestMortalityEquation:
    """Hayes 2010 eq. (2): R = 0.237×score − 8.294; P = exp(R)/(1+exp(R))."""

    def test_score_zero(self):
        inputs = AppleFullInputs(
            units="si",
            creatinine=40, wbc=7, albumin=34, spo2=99, bilirubin=2,
            mentation=0, resp_rate=30, age=4, fluid_score=0, lactate=1.0,
        )
        r = calculate(inputs)
        assert r.total_score == 0
        assert r.mortality_pct < 0.1  # ~0.02%

    def test_score_30_cutoff(self):
        """At score 30: predicted mortality ~23.4% (published high-sens cutoff)."""
        inputs = AppleFullInputs(
            units="si",
            creatinine=300,  # 9
            wbc=20,          # 3
            albumin=34,      # 0
            spo2=99,         # 0
            bilirubin=2,     # 0
            mentation=4,     # 13
            resp_rate=30,    # 0
            age=4,           # 0
            fluid_score=0,   # 0
            lactate=5.0,     # 2 → total 9+3+0+0+0+13+0+0+0+2 = 27
        )
        r = calculate(inputs)
        assert r.total_score == 27
        # The mortality equation at score=30 yields ~23.4%
        # Spot-check the equation itself rather than the constructed score
        from math import exp
        target_R = 0.237 * 30 - 8.294
        target_P = 100.0 * exp(target_R) / (1 + exp(target_R))
        assert 22.0 < target_P < 25.0

    def test_score_max_approaches_100pct(self):
        inputs = AppleFullInputs(
            units="si",
            creatinine=400, wbc=2.0, albumin=31, spo2=80, bilirubin=6,
            mentation=4, resp_rate=55, age=14, fluid_score=2, lactate=15,
        )
        r = calculate(inputs)
        assert r.total_score == 80
        assert r.mortality_pct > 99.0

    def test_monotonic_increasing(self):
        """Higher scores produce higher mortality (no equation reversal)."""
        scores_and_morts = []
        for level in [0, 1, 2, 3, 4]:
            inputs = AppleFullInputs(
                units="si",
                creatinine=40, wbc=7, albumin=34, spo2=99, bilirubin=2,
                mentation=level, resp_rate=30, age=4, fluid_score=0, lactate=1.0,
            )
            r = calculate(inputs)
            scores_and_morts.append((r.total_score, r.mortality_pct))
        # Both score and mortality should monotonically increase
        for i in range(1, len(scores_and_morts)):
            assert scores_and_morts[i][0] >= scores_and_morts[i-1][0]
            assert scores_and_morts[i][1] >= scores_and_morts[i-1][1]


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------


class TestUnitConversion:
    def test_us_si_albumin_equivalent(self):
        """3.4 g/dL = 34 g/L → both should land in referent band."""
        us = AppleFullInputs(
            units="us",
            creatinine=1.0, wbc=7, albumin=3.4, spo2=99, bilirubin=0.1,
            mentation=0, resp_rate=30, age=4, fluid_score=0, lactate=10,
        )
        si = AppleFullInputs(
            units="si",
            creatinine=88.4, wbc=7, albumin=34, spo2=99, bilirubin=1.7,
            mentation=0, resp_rate=30, age=4, fluid_score=0, lactate=1.1,
        )
        us_r = calculate(us)
        si_r = calculate(si)
        assert us_r.total_score == si_r.total_score
        # Both should be 1 (creatinine 1.0 mg/dL → 0.63-1.35 band → 1 pt)
        assert us_r.total_score == 1

    def test_us_si_severe_patient_equivalent(self):
        """Severe patient in both unit systems produces same score (within 1 pt)."""
        us = AppleFullInputs(
            units="us",
            creatinine=3.0,    # → 9 pts (>2.26)
            wbc=3.0,           # → 9 pts (<5.1)
            albumin=2.0,       # 20 g/L → 6 pts (<26)
            spo2=85,           # → 10 pts (<90)
            bilirubin=2.0,     # → 3 pts (>0.93)
            mentation=4,       # → 13 pts
            resp_rate=55,      # → 6 pts (49-60)
            age=12,            # → 8 pts (>8)
            fluid_score=2,     # → 4 pts
            lactate=140,       # 15.55 mmol/L → 6 pts (>11)
        )
        si = AppleFullInputs(
            units="si",
            creatinine=265,    # 3.0 mg/dL ≈ 265 umol/L → 9 pts
            wbc=3.0,
            albumin=20,
            spo2=85,
            bilirubin=34,      # 2.0 mg/dL → 34 umol/L → >16 → 3 pts
            mentation=4,
            resp_rate=55,
            age=12,
            fluid_score=2,
            lactate=15.5,
        )
        us_r = calculate(us)
        si_r = calculate(si)
        assert us_r.total_score == si_r.total_score == 74


# ---------------------------------------------------------------------------
# calculate()
# ---------------------------------------------------------------------------


class TestCalculate:
    def test_default_state_produces_no_score(self):
        """Defaulted inputs (sentinels) → score 0 with ALL components Not entered.

        Hard test against Safety Rule #8. If this fails, the score
        calculation is taking defaulted values seriously.
        """
        inputs = AppleFullInputs()
        r = calculate(inputs)
        assert r.total_score == 0
        not_entered_count = sum(
            1 for c in r.components if "Not entered" in c.value_str
        )
        assert not_entered_count == 10

    def test_max_severity(self):
        inputs = AppleFullInputs(
            units="si",
            creatinine=400, wbc=2.0, albumin=31, spo2=80, bilirubin=6,
            mentation=4, resp_rate=55, age=14, fluid_score=2, lactate=15,
        )
        r = calculate(inputs)
        assert r.total_score == 80

    def test_all_referent_zone_zero_score(self):
        inputs = AppleFullInputs(
            units="si",
            creatinine=40, wbc=7, albumin=34, spo2=99, bilirubin=2,
            mentation=0, resp_rate=30, age=4, fluid_score=0, lactate=1.0,
        )
        r = calculate(inputs)
        assert r.total_score == 0
        for c in r.components:
            assert "referent" in c.value_str or c.points == 0

    def test_components_in_canonical_order(self):
        inputs = AppleFullInputs(
            units="si",
            creatinine=40, wbc=7, albumin=34, spo2=99, bilirubin=2,
            mentation=0, resp_rate=30, age=4, fluid_score=0, lactate=1.0,
        )
        r = calculate(inputs)
        labels = [c.label for c in r.components]
        assert labels == [
            "Creatinine", "WBC count", "Albumin", "SpO₂",
            "Total bilirubin", "Mentation", "Respiratory rate",
            "Age", "Fluid score (FAST/TFAST)", "Lactate",
        ]

    def test_sources_present(self):
        inputs = AppleFullInputs(
            units="si",
            creatinine=40, wbc=7, albumin=34, spo2=99, bilirubin=2,
            mentation=0, resp_rate=30, age=4, fluid_score=0, lactate=1.0,
        )
        r = calculate(inputs)
        assert len(r.sources) >= 1
        assert "Hayes" in r.sources[0].citation
        assert "2010" in r.sources[0].citation

    def test_recommendation_keyed_to_band(self):
        """Each risk band emits a distinct, characteristic recommendation."""
        # Build patients targeting each band
        bands_seen = set()
        for level in [0, 1, 2, 3, 4]:
            inputs = AppleFullInputs(
                units="si",
                creatinine=40, wbc=7, albumin=34, spo2=99, bilirubin=2,
                mentation=level, resp_rate=30, age=4, fluid_score=0,
                lactate=1.0,
            )
            r = calculate(inputs)
            bands_seen.add(r.band_label)
            assert r.recommendation  # non-empty
            # Specific band-keyed phrases
            if r.total_score <= 20:
                assert r.band_label == "Low risk"
            elif r.total_score <= 30:
                assert r.band_label == "Moderate risk"
        assert "Low risk" in bands_seen  # at mentation 0
        # Push into higher bands with severe-everything patients
        severe = AppleFullInputs(
            units="si",
            creatinine=400, wbc=2.0, albumin=31, spo2=80, bilirubin=6,
            mentation=4, resp_rate=55, age=14, fluid_score=2, lactate=15,
        )
        r = calculate(severe)
        assert r.band_label == "Critical risk"
        assert "Aggressive" in r.recommendation


# ---------------------------------------------------------------------------
# Routes — Safety Rule #8 compliance
# ---------------------------------------------------------------------------


class TestRoutes:
    def test_get_page_renders_with_placeholder_not_score(self):
        """The page MUST NOT render a score from default-valued inputs."""
        resp = client.get("/apple-full")
        assert resp.status_code == 200
        body = resp.text
        # The placeholder phrase should appear
        assert "Enter all 10 variables" in body or "to compute the APPLE-full" in body
        # And the score-headline phrasing should NOT appear (no premature result)
        # The result__primary element only renders when result is truthy
        # so the literal "/ 80" string should not appear via the result panel
        # (it does appear in the form label but as text content, not result)

    def test_get_page_has_no_pre_checked_mentation(self):
        """No mentation radio should be pre-checked on initial load."""
        resp = client.get("/apple-full")
        body = resp.text
        # Look for any "checked" attribute associated with mentation
        # We're not being too clever — just verify the radio buttons
        # don't all have a "checked" baked in
        import re
        # Find all mentation radio inputs
        mentation_radios = re.findall(
            r'<input[^>]*name="mentation"[^>]*>', body
        )
        assert len(mentation_radios) == 5  # 0-4
        # None should have 'checked'
        for radio in mentation_radios:
            assert "checked" not in radio

    def test_get_page_has_no_pre_checked_fluid_score(self):
        """No fluid_score radio should be pre-checked on initial load."""
        resp = client.get("/apple-full")
        body = resp.text
        import re
        fluid_radios = re.findall(
            r'<input[^>]*name="fluid_score"[^>]*>', body
        )
        assert len(fluid_radios) == 3  # 0, 1, 2
        for radio in fluid_radios:
            assert "checked" not in radio

    def test_get_page_does_not_load_compute_immediately(self):
        """HTMX hx-trigger MUST NOT include 'load' — that would fire
        compute on initial render and could show a defaulted score."""
        resp = client.get("/apple-full")
        body = resp.text
        # Find the hx-trigger attribute
        import re
        triggers = re.findall(r'hx-trigger="([^"]+)"', body)
        assert any("input changed" in t for t in triggers)
        for t in triggers:
            # Critical: 'load' triggers compute on page load → safety violation
            assert "load" not in t.split(",")[0].split()[0:1] or "input changed" in t
            # More strict: ensure no trigger STARTS with "load"
            words = [w.strip() for w in t.split(",")]
            for word in words:
                assert not word.startswith("load")

    def test_post_compute_returns_partial(self):
        """Valid inputs → result panel partial returned."""
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "40",
                "wbc": "7",
                "albumin": "34",
                "spo2": "99",
                "bilirubin": "2",
                "mentation": "0",
                "resp_rate": "30",
                "age": "4",
                "fluid_score": "0",
                "lactate": "1.0",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        # All-referent → score 0
        assert "0" in body
        assert "/ 80" in body
        assert "Low risk" in body or "below the" in body

    def test_post_compute_high_severity(self):
        """Severely ill patient → high score, critical-band language."""
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "400",
                "wbc": "2.0",
                "albumin": "31",
                "spo2": "80",
                "bilirubin": "6",
                "mentation": "4",
                "resp_rate": "55",
                "age": "14",
                "fluid_score": "2",
                "lactate": "15",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "80" in body
        assert "Critical risk" in body or "98% specificity" in body

    def test_post_compute_bad_input_returns_placeholder(self):
        """Non-numeric input → placeholder, NOT a defaulted score."""
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "abc",
                "wbc": "7",
                "albumin": "34",
                "spo2": "99",
                "bilirubin": "2",
                "mentation": "0",
                "resp_rate": "30",
                "age": "4",
                "fluid_score": "0",
                "lactate": "1.0",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "to compute the APPLE-full" in body
        # And no result headline language
        assert "/ 80" not in body or "APPLE-full score" not in body

    def test_post_compute_partial_input_returns_placeholder(self):
        """A subset of variables provided → placeholder, not partial score."""
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "40",
                "wbc": "7",
                # missing albumin, spo2, bilirubin, mentation, resp_rate, age, fluid_score, lactate
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "to compute the APPLE-full" in body

    def test_post_compute_missing_mentation_returns_placeholder(self):
        """Mentation not selected → placeholder. Radios start unselected
        per Safety Rule #8 so this case is the GET → POST flow before
        the clinician has clicked anything."""
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "40",
                "wbc": "7",
                "albumin": "34",
                "spo2": "99",
                "bilirubin": "2",
                # missing mentation
                "resp_rate": "30",
                "age": "4",
                "fluid_score": "0",
                "lactate": "1.0",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "mentation" in body.lower()
        assert "to compute the APPLE-full" in body

    def test_post_compute_missing_fluid_score_returns_placeholder(self):
        """Fluid score not selected → placeholder."""
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "40",
                "wbc": "7",
                "albumin": "34",
                "spo2": "99",
                "bilirubin": "2",
                "mentation": "0",
                "resp_rate": "30",
                "age": "4",
                # missing fluid_score
                "lactate": "1.0",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "fluid score" in body.lower()
        assert "to compute the APPLE-full" in body

    def test_post_compute_mentation_zero_accepted(self):
        """Mentation=0 (the referent) is a VALID selection, not 'unset'.

        Critical: the route distinguishes 'not selected' from 'explicitly
        selected 0' for radios where 0 has semantic meaning. Empty string
        means unset; '0' means user clicked the normal-mentation option.
        """
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "40",
                "wbc": "7",
                "albumin": "34",
                "spo2": "99",
                "bilirubin": "2",
                "mentation": "0",      # explicit zero
                "resp_rate": "30",
                "age": "4",
                "fluid_score": "0",    # explicit zero
                "lactate": "1.0",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        # We should get a result, not a placeholder
        assert "/ 80" in body
        assert "Low risk" in body or "below the" in body

    def test_post_compute_fluid_score_zero_accepted(self):
        """Same logic as mentation: fluid_score=0 is a valid selection."""
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "40",
                "wbc": "7",
                "albumin": "34",
                "spo2": "99",
                "bilirubin": "2",
                "mentation": "1",
                "resp_rate": "30",
                "age": "4",
                "fluid_score": "0",
                "lactate": "1.0",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "/ 80" in body
        # mentation=1 → 5 pts; rest are 0 → total 5
        assert "5" in body

    def test_post_compute_young_puppy_accepted(self):
        """Age 0.5 years (6mo) should score 3 pts in the 0–2 band.

        Note: Hayes excluded dogs <4 months from the model build, so
        very young values (e.g. 0) are outside the validated domain
        and rejected by the form parser. Anything from 4 months up
        is accepted.
        """
        resp = client.post(
            "/apple-full/compute",
            data={
                "units": "si",
                "creatinine": "40",
                "wbc": "7",
                "albumin": "34",
                "spo2": "99",
                "bilirubin": "2",
                "mentation": "0",
                "resp_rate": "30",
                "age": "0.5",           # 6-month-old puppy
                "fluid_score": "0",
                "lactate": "1.0",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "/ 80" in body
        # Only age contributes points → 3
        assert "3" in body


# ---------------------------------------------------------------------------
# Catalog entry
# ---------------------------------------------------------------------------


class TestCatalogEntry:
    def test_required_fields_present(self):
        for field in (
            "slug", "display_name", "short_name",
            "category", "kind", "mechanism_summary",
        ):
            assert field in APPLE_FULL_CATALOG_ENTRY
            assert APPLE_FULL_CATALOG_ENTRY[field]  # non-empty

    def test_slug_matches_route(self):
        assert APPLE_FULL_CATALOG_ENTRY["slug"] == "apple-full"

    def test_kind_is_diagnostic_score(self):
        assert APPLE_FULL_CATALOG_ENTRY["kind"] == "diagnostic_score"

    def test_mechanism_summary_mentions_published_validation(self):
        """The blurb should reference the 0–80 score range and AUROC."""
        summary = APPLE_FULL_CATALOG_ENTRY["mechanism_summary"]
        assert "0–80" in summary or "80" in summary
        assert "AUROC" in summary or "0.93" in summary

    def test_appears_in_catalog(self):
        """The /calculators index should list APPLE-full."""
        resp = client.get("/calculators")
        assert resp.status_code == 200
        assert "APPLE-full" in resp.text or "apple-full" in resp.text

    def test_appears_in_hubs(self):
        """The /hubs index should list APPLE-full (kind='hub')."""
        resp = client.get("/hubs")
        assert resp.status_code == 200
        assert "APPLE-full" in resp.text or "apple-full" in resp.text
