"""Unit and integration tests for the canine APPLE-fast score.

Test boundaries lifted from Hayes 2010 Figs 4 and A2. Per-variable points
must match the published table exactly; the three counterintuitive items
(glucose >15 → 0, platelets 151–200 scoring HIGHER than <151, albumin
>35 → 2) have explicit dedicated tests because they are the most likely
to be "corrected" by a future contributor unfamiliar with the paper.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.apple_fast import (
    APPLE_FAST_CATALOG_ENTRY,
    AppleFastInputs,
    albumin_points,
    calculate,
    glucose_points,
    lactate_points,
    mentation_points,
    mortality_probability,
    platelet_points,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Glucose (SI mmol/L)
# ---------------------------------------------------------------------------


class TestGlucosePoints:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (3.0, 7),  # <4.6
            (4.5, 7),  # just under 4.6
            (4.6, 8),  # 4.6–5.6 band start
            (5.6, 8),  # 4.6–5.6 band end
            (5.7, 9),  # 5.7–9.0 band start
            (9.0, 9),  # 5.7–9.0 band end
            (9.1, 10),  # 9.1–15.0 band start
            (15.0, 10),  # 9.1–15.0 band end
            (15.1, 0),  # referent: >15 (the counterintuitive 0)
            (25.0, 0),  # deep referent
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = glucose_points(value)
        assert pts == expected_points

    def test_zero_means_not_entered(self):
        pts, lbl = glucose_points(0.0)
        assert pts == 0
        assert "Not entered" in lbl

    def test_referent_label_explicit(self):
        _, lbl = glucose_points(20.0)
        assert "referent" in lbl


# ---------------------------------------------------------------------------
# Albumin (SI g/L)
# ---------------------------------------------------------------------------


class TestAlbuminPoints:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (20.0, 8),  # <26
            (25.0, 8),  # just under 26
            (26.0, 7),  # 26–30 band start
            (30.0, 7),  # 26–30 band end
            (31.0, 6),  # 31–32 band start
            (32.0, 6),  # 31–32 band end
            (33.0, 0),  # 33–35 referent
            (35.0, 0),  # 33–35 referent
            (36.0, 2),  # >35 (counterintuitive non-zero)
            (45.0, 2),  # deep >35
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = albumin_points(value)
        assert pts == expected_points

    def test_high_albumin_scores_two_not_zero(self):
        """Hayes 2010 multivariable artifact: albumin >35 → 2 pts."""
        pts, _ = albumin_points(40.0)
        assert pts == 2, "albumin >35 g/L must score 2 (not 0) per Hayes 2010 Fig A2"


# ---------------------------------------------------------------------------
# Lactate (SI mmol/L)
# ---------------------------------------------------------------------------


class TestLactatePoints:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (1.0, 0),  # <2 referent
            (1.9, 0),  # just under 2
            (2.0, 4),  # 2–8 band start
            (8.0, 4),  # 2–8 band end
            (8.01, 8),  # 8–10 band start
            (10.0, 8),  # 8–10 band end
            (10.1, 12),  # >10
            (15.0, 12),  # deep >10
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = lactate_points(value)
        assert pts == expected_points


# ---------------------------------------------------------------------------
# Platelets (×10⁹/L)
# ---------------------------------------------------------------------------


class TestPlateletPoints:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (50, 5),  # <151
            (150, 5),  # just under 151
            (151, 6),  # 151–200 band start
            (200, 6),  # 151–200 band end
            (201, 3),  # 201–260 band start
            (260, 3),  # 201–260 band end
            (300, 0),  # 261–420 referent
            (420, 0),  # 261–420 referent end
            (421, 1),  # >420
            (600, 1),  # deep >420
        ],
    )
    def test_band_boundaries(self, value, expected_points):
        pts, _ = platelet_points(value)
        assert pts == expected_points

    def test_thrombocytopenia_band_scores_higher_than_severe(self):
        """Hayes 2010 multivariable artifact: 151–200 scores 6, <151 scores 5.

        This is counterintuitive (mild thrombocytopenia scoring higher than
        severe). The paper explicitly flags it as a multivariable model
        artifact. Future contributors must NOT "correct" this.
        """
        mild_pts, _ = platelet_points(175)
        severe_pts, _ = platelet_points(100)
        assert mild_pts == 6
        assert severe_pts == 5
        assert mild_pts > severe_pts, "151–200 must score HIGHER than <151"


# ---------------------------------------------------------------------------
# Mentation
# ---------------------------------------------------------------------------


class TestMentationPoints:
    @pytest.mark.parametrize(
        "value, expected_points",
        [
            (0, 0),  # Normal
            (1, 4),  # Stands unassisted, dull
            (2, 6),  # Stands assisted, dull
            (3, 7),  # Cannot stand, responsive
            (4, 14),  # Cannot stand, unresponsive
        ],
    )
    def test_all_levels(self, value, expected_points):
        pts, _ = mentation_points(value)
        assert pts == expected_points

    def test_unresponsive_dominates(self):
        """Mentation 4 alone contributes 14 — the largest single-variable contribution."""
        pts, _ = mentation_points(4)
        assert pts == 14

    def test_out_of_range_clamped(self):
        """Defensive: negative or >4 mentation values clamp to the valid band."""
        assert mentation_points(-1)[0] == 0
        assert mentation_points(5)[0] == 14
        assert mentation_points(99)[0] == 14


# ---------------------------------------------------------------------------
# Mortality probability equation (Hayes 2010 eq 1)
# ---------------------------------------------------------------------------


class TestMortalityEquation:
    """R = 0.249 × score − 7.020;  P = exp(R) / (1 + exp(R))."""

    def test_score_zero(self):
        # exp(-7.02) / (1 + exp(-7.02)) ≈ 0.000891 → 0.09%
        assert mortality_probability(0) == pytest.approx(0.000891, abs=1e-4)

    def test_score_25_cutoff(self):
        # The validated >25 cutoff: at exactly 25, P ≈ 31%
        # R(25) = 6.225 - 7.020 = -0.795
        # P = exp(-0.795)/(1+exp(-0.795)) ≈ 0.311
        assert mortality_probability(25) == pytest.approx(0.311, abs=0.01)

    def test_score_50_max(self):
        # R(50) = 12.45 - 7.020 = 5.43; P ≈ 0.996
        assert mortality_probability(50) == pytest.approx(0.996, abs=0.005)

    def test_monotonic_increasing(self):
        """Mortality must increase monotonically with score across full range."""
        prev = -1.0
        for s in range(0, 51):
            p = mortality_probability(s)
            assert p > prev
            prev = p


# ---------------------------------------------------------------------------
# Unit conversion (SI ↔ US must give identical scores)
# ---------------------------------------------------------------------------


class TestUnitConversion:
    def test_equivalent_values_score_identically(self):
        """A clinical scenario expressed in SI vs US units must yield the same total."""
        si = calculate(
            AppleFastInputs(
                units="si",
                glucose=5.0,  # mmol/L
                albumin=32.0,  # g/L
                lactate=1.5,  # mmol/L
                platelets=250,
                mentation=0,
            )
        )
        us = calculate(
            AppleFastInputs(
                units="us",
                glucose=90,  # 5.0 mmol/L × 18
                albumin=3.2,  # 32 g/L / 10
                lactate=13.5,  # 1.5 mmol/L × 9
                platelets=250,
                mentation=0,
            )
        )
        assert si.total_score == us.total_score

    def test_us_glucose_273_is_referent(self):
        """The famous 'glucose >273 mg/dL = 0' quirk via the US-units form."""
        # 273 mg/dL = 15.17 mmol/L → just above the 15.0 cutoff → referent → 0
        us = calculate(
            AppleFastInputs(units="us", glucose=280, albumin=3.4, lactate=10, platelets=350, mentation=0)
        )
        # Glucose component should be 0 (referent), albumin 0 (referent), lactate 0 (<2 mmol/L equiv = <18 mg/dL — but 10 mg/dL is <18 so 0 in fact)
        glucose_comp = next(c for c in us.components if c.label == "Glucose")
        assert glucose_comp.points == 0
        assert "referent" in glucose_comp.value_str


# ---------------------------------------------------------------------------
# End-to-end calculate()
# ---------------------------------------------------------------------------


class TestCalculate:
    def test_default_state_produces_no_score(self):
        """Safety: empty AppleFastInputs() must NOT yield a misleading
        pre-populated score. See CLAUDE.md non-negotiable #8.
        """
        r = calculate(AppleFastInputs())
        # Every component returns 0 points + "Not entered" when its
        # input is the sentinel zero / -1. The total is 0, and the
        # mortality probability is whatever the logistic curve gives
        # for a score of 0 — the headline check is that we are NOT
        # generating a clinical-looking score of 17 from physiologic
        # defaults that the clinician never typed.
        assert r.total_score == 0
        # Components labeled "Not entered" so the user sees what's missing
        not_entered = [c for c in r.components if "Not entered" in c.value_str]
        assert len(not_entered) >= 4  # glucose/alb/lac/platelets at minimum

    def test_max_severity(self):
        """Worst-case clinical inputs approach but may not hit 50 exactly."""
        r = calculate(
            AppleFastInputs(
                units="si",
                glucose=10.0,  # 9.1–15 → 10
                albumin=27.0,  # 26–30 → 7
                lactate=11.0,  # >10 → 12
                platelets=180,  # 151–200 → 6 (the counterintuitive max-platelets band)
                mentation=4,  # → 14
            )
        )
        # Components: 10 + 7 + 12 + 6 + 14 = 49
        assert r.total_score == 49
        assert r.mortality_pct > 99.0

    def test_all_referent_zone_zero_score(self):
        """Patient in every referent band scores 0 → ~0.1% mortality."""
        r = calculate(
            AppleFastInputs(
                units="si",
                glucose=20.0,  # >15 → 0 (the stress-hyperglycemia referent)
                albumin=34.0,  # 33–35 → 0
                lactate=1.0,  # <2 → 0
                platelets=350,  # 261–420 → 0
                mentation=0,  # → 0
            )
        )
        assert r.total_score == 0
        assert r.mortality_pct < 0.5

    def test_components_listed_in_canonical_order(self):
        r = calculate(AppleFastInputs())
        labels = [c.label for c in r.components]
        assert labels == ["Glucose", "Albumin", "Lactate", "Platelets", "Mentation"]

    def test_sources_present(self):
        r = calculate(AppleFastInputs())
        assert len(r.sources) >= 1
        citations = " ".join(s.citation for s in r.sources)
        assert "Hayes" in citations
        assert "2010" in citations


# ---------------------------------------------------------------------------
# Route smoke tests
# ---------------------------------------------------------------------------


class TestRoutes:
    def test_get_page_renders_with_placeholder_not_score(self):
        """Safety: initial GET must show a placeholder, not a default score.

        See CLAUDE.md non-negotiable #8.
        """
        r = client.get("/apple-fast")
        assert r.status_code == 200
        assert "APPLE-fast" in r.text
        # The scoring-quirks callout must be in the form
        assert "counterintuitive" in r.text.lower() or "quirks" in r.text.lower()
        # And: NO score in the result panel
        assert "Awaiting input" in r.text
        # The result-panel must NOT contain numeric output that could be
        # misread as a real APPLE-fast score
        assert "result-panel-placeholder" in r.text

    def test_get_page_has_no_pre_checked_mentation(self):
        """Safety: mentation radio group starts with nothing selected so
        a clinician must explicitly choose."""
        r = client.get("/apple-fast")
        # Find all radio inputs with name="mentation". None should be
        # `checked`. Use a defensive regex that catches any checked
        # mentation radio.
        import re

        for match in re.finditer(r'<input[^>]*name="mentation"[^>]*>', r.text):
            assert "checked" not in match.group(0), (
                f"Mentation radio is pre-checked: {match.group(0)}"
            )

    def test_get_page_does_not_load_compute_immediately(self):
        """Safety: hx-trigger must not include `load`, which would fire
        a compute on page mount before the clinician has typed."""
        r = client.get("/apple-fast")
        # The form's hx-trigger should not contain ", load" or "load "
        assert 'hx-trigger="input changed delay:200ms, change"' in r.text
        # Stronger: any hx-trigger that says load is a violation
        for line in r.text.splitlines():
            if "hx-trigger" in line and "load" in line:
                raise AssertionError(f"hx-trigger contains `load`: {line.strip()}")

    def test_post_compute_returns_partial(self):
        r = client.post(
            "/apple-fast/compute",
            data={
                "units": "si",
                "glucose": 5.0,
                "albumin": 32.0,
                "lactate": 1.5,
                "platelets": 250,
                "mentation": 0,
            },
        )
        assert r.status_code == 200
        assert "result-panel" in r.text
        assert "17" in r.text
        # Mortality probability appears as 5.x%
        assert "5." in r.text

    def test_post_compute_high_severity(self):
        r = client.post(
            "/apple-fast/compute",
            data={
                "units": "si",
                "glucose": 3.0,
                "albumin": 22.0,
                "lactate": 12.0,
                "platelets": 175,
                "mentation": 4,
            },
        )
        assert r.status_code == 200
        # Components: 7 + 8 + 12 + 6 + 14 = 47
        assert "47" in r.text
        # Should show high-risk band recommendation
        assert "high" in r.text.lower() or "High" in r.text

    def test_post_compute_handles_bad_input_returns_placeholder(self):
        """Safety: unparseable input returns the placeholder, NOT a
        result with substituted defaults."""
        r = client.post(
            "/apple-fast/compute",
            data={
                "units": "si",
                "glucose": "not a number",
                "albumin": "",
                "lactate": "abc",
                "platelets": "??",
                "mentation": "garbage",
            },
        )
        assert r.status_code == 200
        assert "Awaiting input" in r.text
        # And no numeric score should appear
        assert "/50" not in r.text

    def test_post_compute_partial_input_returns_placeholder(self):
        """Safety: only some fields filled → still placeholder."""
        r = client.post(
            "/apple-fast/compute",
            data={
                "units": "si",
                "glucose": "5.0",
                # Other four are missing
            },
        )
        assert r.status_code == 200
        assert "Awaiting input" in r.text

    def test_post_compute_missing_mentation_returns_placeholder(self):
        """Safety: mentation 0 is a valid score (alert); empty is not."""
        r = client.post(
            "/apple-fast/compute",
            data={
                "units": "si",
                "glucose": "5.0",
                "albumin": "32.0",
                "lactate": "1.5",
                "platelets": "250",
                # mentation deliberately omitted
            },
        )
        assert r.status_code == 200
        assert "Awaiting input" in r.text
        assert "mentation" in r.text.lower()

    def test_post_compute_mentation_zero_is_accepted(self):
        """Mentation=0 ('alert') is a real score, must be accepted."""
        r = client.post(
            "/apple-fast/compute",
            data={
                "units": "si",
                "glucose": "5.0",
                "albumin": "32.0",
                "lactate": "1.5",
                "platelets": "250",
                "mentation": "0",
            },
        )
        assert r.status_code == 200
        # We get a real score, not the placeholder
        assert "Awaiting input" not in r.text


# ---------------------------------------------------------------------------
# Catalog entry
# ---------------------------------------------------------------------------


class TestCatalogEntry:
    def test_required_fields_present(self):
        for field in ("slug", "display_name", "short_name", "category", "kind", "mechanism_summary"):
            assert field in APPLE_FAST_CATALOG_ENTRY
            assert APPLE_FAST_CATALOG_ENTRY[field]

    def test_slug_matches_route(self):
        assert APPLE_FAST_CATALOG_ENTRY["slug"] == "apple-fast"

    def test_kind_is_diagnostic_score(self):
        assert APPLE_FAST_CATALOG_ENTRY["kind"] == "diagnostic_score"

    def test_appears_in_catalog_page(self):
        r = client.get("/calculators")
        assert "APPLE-fast" in r.text or "apple-fast" in r.text

    def test_appears_in_hubs_page(self):
        r = client.get("/hubs")
        assert "APPLE-fast" in r.text or "apple-fast" in r.text
