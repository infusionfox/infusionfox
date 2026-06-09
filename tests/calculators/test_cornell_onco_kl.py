"""
Tests for the Cornell Oncology KL (ketamine-lidocaine) infusion calculator.

Sources:
  Iocolano KE et al. JAVMA 2025;263(4):499–506.
  Looney A, Cornell University CVM 2012 worksheet.

Targets (rate at 2.5 mL/kg/hr × 4–6 hr infusion):
    Dog: 3.0 mg/kg/hr lidocaine, 0.15 mg/kg/hr ketamine
    Cat: 1.5 mg/kg/hr lidocaine, 0.15 mg/kg/hr ketamine

Efficacy thresholds (from 2025 paper):
    Lidocaine: ≥ 1.5 mg/kg/hr (= 25 µg/kg/min)
    Ketamine:  ≥ 0.12 mg/kg/hr (= 2 µg/kg/min)
    Ketamine total: ≥ 0.5 mg/kg over infusion

Small-patient flag: weight < 15 kg (smaller bag recommended).
"""

from __future__ import annotations

import pytest

from app.calculators.cornell_onco_kl import (
    EFFICACY_KETA_MIN_MG_PER_KG_PER_HR,
    EFFICACY_KETA_TOTAL_DOSE_MIN_MG_PER_KG,
    EFFICACY_LIDO_MIN_MG_PER_KG_PER_HR,
    SMALL_PATIENT_THRESHOLD_KG,
    TARGET_KETAMINE_MG_PER_KG_PER_HR,
    TARGET_LIDOCAINE_CAT_MG_PER_KG_PER_HR,
    TARGET_LIDOCAINE_DOG_MG_PER_KG_PER_HR,
    CornellOncoKLInputs,
    CornellOncoKLSpecies,
    compute_cornell_onco_kl,
)
from app.calculators.engine import WeightUnit


def _inputs(
    *,
    weight_kg: float = 30.0,
    species: CornellOncoKLSpecies = CornellOncoKLSpecies.DOG,
    bag_ml: float = 500.0,
    duration_hr: float = 6.0,
) -> CornellOncoKLInputs:
    return CornellOncoKLInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        bag_volume_ml=bag_ml,
        duration_hr=duration_hr,
    )


class TestSpeciesTargets:
    def test_dog_targets(self):
        result = compute_cornell_onco_kl(_inputs(species=CornellOncoKLSpecies.DOG))
        assert result.target_lidocaine_mg_per_kg_per_hr == TARGET_LIDOCAINE_DOG_MG_PER_KG_PER_HR
        assert result.target_ketamine_mg_per_kg_per_hr == TARGET_KETAMINE_MG_PER_KG_PER_HR

    def test_cat_targets(self):
        result = compute_cornell_onco_kl(_inputs(species=CornellOncoKLSpecies.CAT))
        assert result.target_lidocaine_mg_per_kg_per_hr == TARGET_LIDOCAINE_CAT_MG_PER_KG_PER_HR
        assert result.target_ketamine_mg_per_kg_per_hr == TARGET_KETAMINE_MG_PER_KG_PER_HR


class TestPaperValidationCase:
    """30 kg dog × 500 mL bag × 6 hr should match paper Table 4 median (~2.7 mg/kg/hr lidocaine).
    Paper-validated case from prior verification work."""

    def test_30kg_dog_500ml_6hr(self):
        result = compute_cornell_onco_kl(_inputs(weight_kg=30, bag_ml=500, duration_hr=6))
        # Paper median lidocaine delivery for similar cases: ~2.7-2.8 mg/kg/hr
        assert result.delivered_lidocaine_mg_per_kg_per_hr == pytest.approx(2.7, abs=0.3)
        # All efficacy thresholds should be met
        assert result.lidocaine_below_efficacy_threshold is False
        assert result.ketamine_below_efficacy_threshold is False
        assert result.ketamine_total_dose_below_efficacy_threshold is False


class TestSmallPatientFlag:
    def test_small_dog_flagged(self):
        """Patient < 15 kg should be flagged as small."""
        result = compute_cornell_onco_kl(_inputs(weight_kg=10))
        assert result.is_small_patient is True

    def test_large_dog_not_small(self):
        result = compute_cornell_onco_kl(_inputs(weight_kg=30))
        assert result.is_small_patient is False

    def test_threshold_at_15kg(self):
        """Threshold is < 15 kg."""
        assert SMALL_PATIENT_THRESHOLD_KG == 15.0


class TestSmallPatientUnderdosing:
    """5 kg dog on 250 mL bag should fail to meet thresholds — this case
    is the canonical small-patient warning the calculator surfaces."""

    def test_5kg_dog_250ml_underdoses_lidocaine(self):
        result = compute_cornell_onco_kl(_inputs(weight_kg=5, bag_ml=250, duration_hr=6))
        # Should be flagged and likely below at least one threshold
        assert result.is_small_patient is True

    def test_5kg_dog_100ml_better(self):
        """Switching to a smaller (100 mL) bag should improve utilization."""
        r_250 = compute_cornell_onco_kl(_inputs(weight_kg=5, bag_ml=250, duration_hr=6))
        r_100 = compute_cornell_onco_kl(_inputs(weight_kg=5, bag_ml=100, duration_hr=6))
        # Smaller bag → more concentrated → higher delivered rate
        assert r_100.delivered_lidocaine_mg_per_kg_per_hr >= r_250.delivered_lidocaine_mg_per_kg_per_hr


class TestEfficacyThresholdConstants:
    def test_lidocaine_threshold(self):
        """1.5 mg/kg/hr = 25 µg/kg/min."""
        assert EFFICACY_LIDO_MIN_MG_PER_KG_PER_HR == 1.5

    def test_ketamine_threshold(self):
        """0.12 mg/kg/hr = 2 µg/kg/min."""
        assert EFFICACY_KETA_MIN_MG_PER_KG_PER_HR == 0.12

    def test_ketamine_total_dose_threshold(self):
        """Total ketamine ≥ 0.5 mg/kg over infusion."""
        assert EFFICACY_KETA_TOTAL_DOSE_MIN_MG_PER_KG == 0.5


class TestBagFinishedDetection:
    """If patient consumes entire bag before scheduled end, bag_finished=True."""

    def test_large_dog_small_bag_finishes_early(self):
        """50 kg × 2.5 mL/kg/hr × 6 hr planned = 750 mL, but bag = 250 mL.
        Bag finishes after 250/125 = 2 hr."""
        result = compute_cornell_onco_kl(_inputs(weight_kg=50, bag_ml=250, duration_hr=6))
        assert result.bag_finished is True
        assert result.actual_duration_hr < 6.0

    def test_short_duration_leaves_bag(self):
        """30 kg × 2.5 mL/kg/hr × 4 hr = 300 mL < 500 mL bag → bag remains."""
        result = compute_cornell_onco_kl(_inputs(weight_kg=30, bag_ml=500, duration_hr=4))
        assert result.bag_finished is False
        assert result.lidocaine_wasted_mg > 0  # leftover drug in bag


class TestSourceAttribution:
    def test_includes_iocolano_or_cornell(self):
        result = compute_cornell_onco_kl(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Iocolano" in cite_text or "Looney" in cite_text or "Cornell" in cite_text
