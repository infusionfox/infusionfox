"""Tests for the intravenous lipid emulsion (ILE) protocol calculator.

ILE is a custom-module calculator (not engine-driven). Volume-based
dosing (mL/kg), shared bolus + three protocol options (fast standard,
fast extended, slow conservative), and tiered cumulative-dose
classification. Used for toxicology reversal across multiple
lipophilic toxicants via the lipid-sink mechanism.

Tests cover:
- Constants pinned (rates, durations, tier thresholds)
- Math for all three protocol options (bolus, rates, volumes, totals)
- Cumulative-dose tier classification (within / above / high)
- Re-bolus arithmetic per protocol
- Safety Rule #8 placeholder gate
- Safety-language coverage in the form
- Route rendering of the side-by-side protocol comparison
- Emergency-section nav placement
- Catalog entry shape
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.engine import WeightUnit
from app.calculators.ile import (
    BOLUS_DOSE_ML_PER_KG,
    CRI_DURATION_FAST_EXTENDED_MIN,
    CRI_DURATION_FAST_STANDARD_MIN,
    CRI_DURATION_SLOW_MIN,
    CRI_RATE_FAST_ML_PER_KG_PER_MIN,
    CRI_RATE_SLOW_ML_PER_KG_PER_MIN,
    CUMULATIVE_GUIDELINE_ML_PER_KG,
    CUMULATIVE_HIGH_ML_PER_KG,
    ILE_CATALOG_ENTRY,
    ILE_PERCENT,
    REBOLUS_DOSE_ML_PER_KG,
    IleInputs,
    IleSpecies,
    compute_ile,
)
from app.main import app

client = TestClient(app)


class TestIleConstants:
    """Pin protocol constants so future edits cannot silently drift
    dosing away from the established literature."""

    def test_20_percent_stock(self):
        assert ILE_PERCENT == 20

    def test_bolus_dose_1_5_ml_per_kg(self):
        assert BOLUS_DOSE_ML_PER_KG == 1.5

    def test_rebolus_same_as_bolus(self):
        assert REBOLUS_DOSE_ML_PER_KG == BOLUS_DOSE_ML_PER_KG

    def test_fast_protocol_rate(self):
        # ASRA-derived: 0.25 mL/kg/min × 30-60 min.
        assert CRI_RATE_FAST_ML_PER_KG_PER_MIN == 0.25

    def test_fast_protocol_durations(self):
        assert CRI_DURATION_FAST_STANDARD_MIN == 30
        assert CRI_DURATION_FAST_EXTENDED_MIN == 60

    def test_slow_protocol_rate(self):
        # Conservative protocol used for smaller patients, cardiac
        # instability, and sustained toxicities; documented in
        # Gwaltney-Brant 2018 and the Munich retrospective.
        assert CRI_RATE_SLOW_ML_PER_KG_PER_MIN == 0.066

    def test_slow_protocol_duration_4_hours(self):
        assert CRI_DURATION_SLOW_MIN == 240

    def test_cumulative_guideline_10_ml_per_kg(self):
        # Conservative practice guideline from Fernandez 2011. Not
        # a hard ceiling; no validated maximum daily dose exists in
        # veterinary patients (Kuo 2013).
        assert CUMULATIVE_GUIDELINE_ML_PER_KG == 10.0

    def test_cumulative_high_15_ml_per_kg(self):
        # The "high cumulative" checkpoint where lipemia status and
        # fat-overload markers should be reassessed.
        assert CUMULATIVE_HIGH_ML_PER_KG == 15.0


class TestIleMath:
    def test_canonical_20kg_dog_bolus(self):
        result = compute_ile(
            IleInputs(weight_value=20.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        assert result.valid
        assert result.bolus_volume_ml == pytest.approx(30.0)
        assert result.rebolus_volume_ml == pytest.approx(30.0)

    def test_fast_standard_20kg_dog(self):
        """20 kg dog, fast 30 min protocol:
        - Rate: 0.25 × 20 = 5 mL/min = 300 mL/hr
        - CRI volume: 5 × 30 = 150 mL
        - Bolus + CRI: 30 + 150 = 180 mL
        - Per-kg: 180 / 20 = 9.0 mL/kg → within guideline
        """
        result = compute_ile(
            IleInputs(weight_value=20.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        p = result.fast_standard
        assert p.rate_ml_per_min == pytest.approx(5.0)
        assert p.rate_ml_per_hr == pytest.approx(300.0)
        assert p.duration_min == 30
        assert p.cri_volume_ml == pytest.approx(150.0)
        assert p.bolus_plus_cri_ml == pytest.approx(180.0)
        assert p.cumulative_per_kg == pytest.approx(9.0)

    def test_fast_extended_20kg_dog(self):
        """20 kg dog, fast 60 min protocol:
        - Rate: 300 mL/hr (same as standard)
        - CRI volume: 5 × 60 = 300 mL
        - Bolus + CRI: 30 + 300 = 330 mL
        - Per-kg: 330 / 20 = 16.5 mL/kg → high cumulative
        """
        result = compute_ile(
            IleInputs(weight_value=20.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        p = result.fast_extended
        assert p.rate_ml_per_hr == pytest.approx(300.0)
        assert p.duration_min == 60
        assert p.cri_volume_ml == pytest.approx(300.0)
        assert p.bolus_plus_cri_ml == pytest.approx(330.0)
        assert p.cumulative_per_kg == pytest.approx(16.5)

    def test_slow_conservative_20kg_dog(self):
        """20 kg dog, slow 4 hr protocol:
        - Rate: 0.066 × 20 = 1.32 mL/min = 79.2 mL/hr
        - CRI volume: 1.32 × 240 = 316.8 mL
        - Bolus + CRI: 30 + 316.8 = 346.8 mL
        - Per-kg: 346.8 / 20 = 17.34 mL/kg → high cumulative
        """
        result = compute_ile(
            IleInputs(weight_value=20.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        p = result.slow_conservative
        assert p.rate_ml_per_kg_per_min == pytest.approx(0.066)
        assert p.rate_ml_per_min == pytest.approx(1.32)
        assert p.rate_ml_per_hr == pytest.approx(79.2)
        assert p.duration_min == 240
        assert p.cri_volume_ml == pytest.approx(316.8)
        assert p.bolus_plus_cri_ml == pytest.approx(346.8)
        assert p.cumulative_per_kg == pytest.approx(17.34, rel=1e-3)

    def test_slow_protocol_lower_rate_than_fast(self):
        """The slow protocol's volumetric rate is roughly one-quarter
        of the fast protocol's rate. This is the clinical reason for
        choosing it in smaller patients."""
        result = compute_ile(
            IleInputs(weight_value=11.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        # 0.066 / 0.25 ≈ 0.264 ≈ 1/4
        ratio = result.slow_conservative.rate_ml_per_hr / result.fast_standard.rate_ml_per_hr
        assert ratio == pytest.approx(0.264, rel=1e-2)

    def test_24lb_dog_rates(self):
        """24 lb (10.886 kg) dog. The user-visible case that prompted
        the two-protocol redesign: fast = 163 mL/hr, slow = 43 mL/hr.
        """
        result = compute_ile(
            IleInputs(weight_value=24.0, weight_unit=WeightUnit.LB, species=IleSpecies.DOG)
        )
        assert result.fast_standard.rate_ml_per_hr == pytest.approx(163.3, abs=0.5)
        assert result.slow_conservative.rate_ml_per_hr == pytest.approx(43.1, abs=0.5)

    def test_small_cat_bolus_and_rates(self):
        """4 kg cat:
        - Bolus: 1.5 × 4 = 6 mL
        - Fast rate: 0.25 × 4 = 1 mL/min = 60 mL/hr
        - Slow rate: 0.066 × 4 = 0.264 mL/min = 15.84 mL/hr
        """
        result = compute_ile(
            IleInputs(weight_value=4.0, weight_unit=WeightUnit.KG, species=IleSpecies.CAT)
        )
        assert result.bolus_volume_ml == pytest.approx(6.0)
        assert result.fast_standard.rate_ml_per_hr == pytest.approx(60.0)
        assert result.slow_conservative.rate_ml_per_hr == pytest.approx(15.84, rel=1e-3)

    def test_lb_conversion(self):
        # 44 lb ≈ 19.96 kg → bolus ~30 mL.
        result = compute_ile(
            IleInputs(weight_value=44.0, weight_unit=WeightUnit.LB, species=IleSpecies.DOG)
        )
        assert result.bolus_volume_ml == pytest.approx(30.0, rel=1e-2)


class TestIleTierClassification:
    """The cumulative-dose tier replaces the old binary within/exceeds
    cap. Three tiers: within (≤10), above (10-15), high (>15) mL/kg."""

    def test_fast_standard_is_within_guideline(self):
        """Fast 30 min protocol delivers exactly 9 mL/kg total
        (1.5 bolus + 7.5 CRI), which is below the 10 mL/kg
        conservative guideline regardless of patient size."""
        for weight in (3.0, 10.0, 25.0, 50.0):
            result = compute_ile(
                IleInputs(weight_value=weight, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
            )
            assert result.fast_standard.cumulative_per_kg == pytest.approx(9.0)
            assert result.fast_standard.cumulative_tier == "within"

    def test_fast_extended_is_high_cumulative(self):
        """Fast 60 min delivers 16.5 mL/kg, which is above the 15
        mL/kg high-cumulative threshold."""
        result = compute_ile(
            IleInputs(weight_value=10.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        assert result.fast_extended.cumulative_per_kg == pytest.approx(16.5)
        assert result.fast_extended.cumulative_tier == "high"

    def test_slow_conservative_is_high_cumulative(self):
        """Slow 4 hr delivers ~17.34 mL/kg, above the 15 mL/kg
        threshold. This is intentional: the slow rate delivers more
        total volume at lower peak triglyceride load."""
        result = compute_ile(
            IleInputs(weight_value=10.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        assert result.slow_conservative.cumulative_per_kg == pytest.approx(17.34, rel=1e-3)
        assert result.slow_conservative.cumulative_tier == "high"

    def test_tier_label_within(self):
        result = compute_ile(
            IleInputs(weight_value=10.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        assert "Within conservative" in result.fast_standard.cumulative_label

    def test_tier_label_high(self):
        result = compute_ile(
            IleInputs(weight_value=10.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        assert "High" in result.slow_conservative.cumulative_label

    def test_rebolus_pushes_fast_standard_to_above_tier(self):
        """Fast standard alone is 9 mL/kg (within). Adding one
        rebolus brings it to 10.5 mL/kg (above)."""
        result = compute_ile(
            IleInputs(weight_value=10.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        p = result.fast_standard
        assert p.cumulative_after_rebolus_per_kg == pytest.approx(10.5)
        assert p.cumulative_after_rebolus_tier == "above"

    def test_rebolus_after_high_protocol_stays_high(self):
        """After the slow protocol (already at 17.34 mL/kg), a rebolus
        pushes cumulative to 18.84 mL/kg, still high tier."""
        result = compute_ile(
            IleInputs(weight_value=10.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        p = result.slow_conservative
        assert p.cumulative_after_rebolus_per_kg == pytest.approx(18.84, rel=1e-3)
        assert p.cumulative_after_rebolus_tier == "high"


class TestIleClinicalNotes:
    def test_two_protocols_note_present(self):
        """Result notes describe when each protocol is preferred."""
        result = compute_ile(
            IleInputs(weight_value=10.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        notes_text = " ".join(result.notes).lower()
        assert "fast" in notes_text
        assert "slow" in notes_text

    def test_clinical_stopping_criteria_note(self):
        """Stopping criteria framed as clinical (response, lipemia,
        fat overload), not a fixed mL/kg/day."""
        result = compute_ile(
            IleInputs(weight_value=10.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        notes_text = " ".join(result.notes).lower()
        assert "stopping criteria" in notes_text
        assert "lipemia" in notes_text


class TestIleSafetyRule8:
    def test_zero_weight_invalid(self):
        result = compute_ile(
            IleInputs(weight_value=0.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        assert result.valid is False
        # No numeric output.
        assert result.bolus_volume_ml == 0.0
        assert result.fast_standard.rate_ml_per_hr == 0.0
        assert result.slow_conservative.rate_ml_per_hr == 0.0

    def test_negative_weight_invalid(self):
        result = compute_ile(
            IleInputs(weight_value=-5.0, weight_unit=WeightUnit.KG, species=IleSpecies.DOG)
        )
        assert result.valid is False

    def test_empty_post_returns_placeholder(self):
        # No weight input → placeholder (Safety Rule #8).
        r = client.post(
            "/ile/compute",
            data={"weight_value": "", "weight_unit": "kg", "species": "dog"},
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "Awaiting input" in r.text


class TestIleRoutes:
    def test_form_renders(self):
        r = client.get("/ile")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Lipid Emulsion (ILE) protocol</h1>" in body
        # Emergency eyebrow.
        assert ">Emergency<" in body

    def test_form_carries_critical_safety_warnings(self):
        body = client.get("/ile").text
        # 20% only — primary safety guard.
        assert "20% lipid emulsion ONLY" in body
        # Lipemia interferes with subsequent labs.
        assert "lipemia" in body.lower() or "Lipemia" in body
        # Concurrent propofol confounds lipid status.
        assert "propofol" in body.lower()
        # Calcium / NaHCO3 incompatibility.
        assert "calcium" in body.lower() or "sodium bicarbonate" in body.lower()
        # Fat overload syndrome.
        assert "Fat overload" in body or "fat overload" in body

    def test_compute_renders_three_phases(self):
        r = client.post(
            "/ile/compute",
            data={"weight_value": "20", "weight_unit": "kg", "species": "dog"},
            headers={"HX-Request": "true"},
        )
        body = r.text
        # All three phases labeled.
        assert "Phase 1" in body
        assert "Phase 2" in body
        assert "Phase 3" in body

    def test_compute_renders_both_protocols(self):
        r = client.post(
            "/ile/compute",
            data={"weight_value": "20", "weight_unit": "kg", "species": "dog"},
            headers={"HX-Request": "true"},
        )
        body = r.text
        # Both protocol options labeled.
        assert "Fast 30 min" in body
        assert "Fast 60 min" in body
        assert "Slow 4 hr" in body
        # Side-by-side rate display.
        assert "300.0" in body or "300 mL/hr" in body  # fast rate for 20 kg
        # Slow rate for 20 kg = 79.2 mL/hr.
        assert "79.2" in body

    def test_compute_renders_cumulative_dose_reference(self):
        r = client.post(
            "/ile/compute",
            data={"weight_value": "20", "weight_unit": "kg", "species": "dog"},
            headers={"HX-Request": "true"},
        )
        body = r.text
        # New cumulative-dose reference section replaces the old
        # "Daily ceiling" section.
        assert "Cumulative dose reference" in body
        # Tier labels visible.
        assert "Within conservative" in body
        assert "Above conservative" in body
        assert "High cumulative" in body

    def test_compute_renders_clinical_stopping_criteria(self):
        r = client.post(
            "/ile/compute",
            data={"weight_value": "20", "weight_unit": "kg", "species": "dog"},
            headers={"HX-Request": "true"},
        )
        body = r.text
        assert "stopping criteria" in body.lower()
        # Clinical, not numeric.
        assert "clinical response" in body.lower()
        assert "lipemia" in body.lower()


class TestIleNav:
    def test_ile_in_emergency(self):
        from app.nav import nav_index
        emergency = [e.href for e in nav_index().get("Emergency", [])]
        assert "/ile" in emergency
        # Only once — no duplicate registration.
        assert emergency.count("/ile") == 1


class TestIleCatalogEntry:
    def test_emergency_category(self):
        assert ILE_CATALOG_ENTRY["category"] == "Emergency"

    def test_blurb_covers_main_indications(self):
        blurb = ILE_CATALOG_ENTRY["catalog_blurb"].lower()
        assert "local anesthetic" in blurb or "anesthetic" in blurb
        assert "permethrin" in blurb or "lipophilic" in blurb

    def test_indications_summary_covers_each_use_case(self):
        summary = ILE_CATALOG_ENTRY["indications_summary"].lower()
        # Six canonical indications all named.
        assert "local anesthetic" in summary
        assert "calcium-channel" in summary
        assert "beta-blocker" in summary
        assert "permethrin" in summary
        assert "ivermectin" in summary or "macrocyclic" in summary
        assert "baclofen" in summary

    def test_mechanism_summary_mentions_both_protocols(self):
        """The reframed mechanism_summary describes the two-protocol
        model and softens the cumulative-dose framing."""
        summary = ILE_CATALOG_ENTRY["mechanism_summary"].lower()
        assert "fast" in summary and "slow" in summary
        # No claim of a hard ceiling.
        assert "hard ceiling" in summary or "not a hard" in summary or "conservative" in summary
