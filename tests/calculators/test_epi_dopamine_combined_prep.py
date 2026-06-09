"""Epinephrine and dopamine-cri combined-prep section. Each rounds out
the conversion of the four vasopressor/inotrope CRIs to the norepi-pattern
UI (norepi + dobutamine were converted earlier).

Each has a distinct shape:

- Epinephrine: weight-band strategy (like dobutamine), single 50 mL
  syringe bag size (all standard CRI prep is syringe-pump). The
  bag-size tab row hides itself when there's only one option; a
  display-hidden radio carries the bag value in the POST.

- Dopamine: NO recommendation strategy. The two presets are workflow-
  driven (200 mg load in 250 mL bag → 800 µg/mL, 200 mg load in 500 mL
  bag → 400 µg/mL). The suggested-bag badge still works (full-vial
  match for chosen concentration); the suggested-conc badge sits on
  the default and doesn't move with patient inputs.

Neither surfaces directional notices in v1 — epi because the patient-
driven recommendation is captured by the suggested badge alone and the
syringe-pump workflow doesn't have a "volumetric precision floor"
problem; dopamine because no recommendation strategy means no
mismatch concept. Both are candidates for later additions.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DOPAMINE_STANDARD,
    EPINEPHRINE,
    bag_size_variants_for_drug,
    pick_preset_for_patient,
)
from app.main import app

# =========================================================================
# Epinephrine
# =========================================================================


class TestEpinephrineConfig:
    def test_uses_combined_prep_section(self):
        assert EPINEPHRINE.uses_combined_prep_section is True

    def test_single_bag_size_is_50_ml_syringe(self):
        """All standard epinephrine CRI preparations are 50 mL syringe-
        pump preps. The 250 mL bag option isn't clinically standard for
        epi (would require 5-20 vials per bag depending on concentration)."""
        assert EPINEPHRINE.bag_size_options_ml == (50,)
        assert EPINEPHRINE.bag_size_default_ml == 50

    def test_vial_size_is_1_mg(self):
        """1 mg/mL × 1 mL ampule = 1 mg vial. The CRI-strength epinephrine
        (formerly labeled 1:1000), distinct from the 0.1 mg/mL (1:10,000)
        cardiac arrest concentration."""
        assert EPINEPHRINE.vial_size_mg == 1.0

    def test_recommendation_strategy_is_weight_band(self):
        """Concentration presets carry weight bands (<5, 5-20, >20 kg)
        and the picker dispatches on them — same as dobutamine."""
        assert EPINEPHRINE.recommendation_strategy == "weight-band"

    def test_how_it_works_paragraphs_set(self):
        assert len(EPINEPHRINE.how_it_works_paragraphs) >= 1
        joined = " ".join(EPINEPHRINE.how_it_works_paragraphs)
        assert "50 mL" in joined  # confirms syringe-pump framing


class TestEpinephrinePresetPicker:
    """Weight-band picker. Bands from EPINEPHRINE config:
        20 µg/mL  <5 kg
        40 µg/mL  5–20 kg
        80 µg/mL  >20 kg
    """

    def test_small_patient_picks_20(self):
        preset = pick_preset_for_patient(EPINEPHRINE, weight_kg=3.0, dose_ug_kg_min=0.1)
        assert preset.concentration_ug_per_ml == 20

    def test_medium_patient_picks_40(self):
        preset = pick_preset_for_patient(EPINEPHRINE, weight_kg=10.0, dose_ug_kg_min=0.1)
        assert preset.concentration_ug_per_ml == 40

    def test_large_patient_picks_80(self):
        preset = pick_preset_for_patient(EPINEPHRINE, weight_kg=30.0, dose_ug_kg_min=0.1)
        assert preset.concentration_ug_per_ml == 80


class TestEpinephrineBagSizeVariants:
    def test_three_variants_one_per_concentration(self):
        """3 concentrations × 1 bag = 3 recipe cards."""
        total = 0
        for conc in (20, 40, 80):
            variants = bag_size_variants_for_drug(EPINEPHRINE, conc)
            total += len(variants)
        assert total == 3

    def test_20_x_50_is_full_vial(self):
        """20 µg/mL × 50 mL = 1 mg = 1 vial. The only full-vial pairing
        for epi in the 50 mL set."""
        variants = bag_size_variants_for_drug(EPINEPHRINE, 20)
        v = variants[0]
        assert v.is_suggested is True
        assert "1 vial" in v.vial_note

    def test_higher_concentrations_use_multiple_vials(self):
        """Standard practice for epi CRI uses 1-4 ampules; the multi-vial
        recipes shouldn't carry the full-vial badge."""
        for conc, expected_vials in [(40, 2), (80, 4)]:
            v = bag_size_variants_for_drug(EPINEPHRINE, conc)[0]
            assert v.is_suggested is False
            assert v.drug_amount_mg == expected_vials  # mg of drug == ampules


class TestEpinephrineFormIntegration:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_three_recipe_cards_render(self, client):
        body = client.get("/epinephrine").text
        # 3 concentrations × 1 bag
        assert body.count("data-conc=") == 3

    def test_no_visible_bag_size_tabs(self, client):
        """Single-bag drugs hide the bag-size tab row — one tab is noise."""
        body = client.get("/epinephrine").text
        assert 'class="bag-size-tabs"' not in body

    def test_hidden_radio_carries_bag_value(self, client):
        """A display:none radio (not a type=hidden input) is rendered so
        the JS `:checked` selector and the form POST both work."""
        body = client.get("/epinephrine").text
        # The hidden-display radio
        assert 'type="radio" name="combined_prep_bag_size_ml"' in body
        assert 'value="50" checked' in body
        assert "display: none" in body

    def test_no_full_vial_badge_on_any_card(self, client):
        """The recipe-card "uses one full vial" badge is gated off for
        single-bag drugs — without a bag choice to make, the badge has
        no actionable meaning."""
        body = client.get("/epinephrine").text
        assert "suggested · uses one full vial" not in body

    def test_compute_works(self, client):
        """Math sanity. 10 kg dog @ 0.5 µg/kg/min × 40 µg/mL.
        Pump rate = (0.5 × 10 × 60) / 40 = 7.5 mL/hr."""
        r = client.post(
            "/epinephrine/compute",
            data={
                "weight_value": "10",
                "weight_unit": "kg",
                "dose": "0.5",
                "concentration_ug_per_ml": "40",
                "species": "dog",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "50",
            },
        )
        assert r.status_code == 200
        assert "7.5" in r.text

    def test_no_precision_floor_notice(self, client):
        """Even when the math gives a sub-floor pump rate, epi's syringe-
        pump workflow means the volumetric precision floor doesn't
        apply. No notice should fire in v1."""
        # 5 kg cat @ 0.05 µg/kg/min × 80 µg/mL gives rate = 0.1875 mL/hr.
        r = client.post(
            "/epinephrine/compute",
            data={
                "weight_value": "5",
                "weight_unit": "kg",
                "dose": "0.05",
                "concentration_ug_per_ml": "80",
                "species": "cat",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "50",
            },
        )
        assert r.status_code == 200
        assert "Pump rate below the precision floor" not in r.text
        assert "More precise preparation available" not in r.text


# =========================================================================
# Dopamine
# =========================================================================


class TestDopamineConfig:
    def test_uses_combined_prep_section(self):
        assert DOPAMINE_STANDARD.uses_combined_prep_section is True

    def test_two_bag_sizes_250_and_500(self):
        assert DOPAMINE_STANDARD.bag_size_options_ml == (250, 500)
        assert DOPAMINE_STANDARD.bag_size_default_ml == 250

    def test_vial_size_is_200_mg(self):
        """40 mg/mL × 5 mL = 200 mg vial."""
        assert DOPAMINE_STANDARD.vial_size_mg == 200.0

    def test_no_recommendation_strategy(self):
        """Dopamine's two concentrations are workflow-driven (250 vs 500
        bag), not patient-driven. The picker should return the default."""
        assert DOPAMINE_STANDARD.recommendation_strategy == ""

    def test_how_it_works_paragraphs_set(self):
        assert len(DOPAMINE_STANDARD.how_it_works_paragraphs) >= 1
        joined = " ".join(DOPAMINE_STANDARD.how_it_works_paragraphs)
        # Acknowledges the workflow-driven choice
        assert "200 mg" in joined


class TestDopaminePresetPicker:
    """No recommendation strategy → picker returns the default preset
    regardless of patient inputs."""

    def test_returns_default_for_small_patient(self):
        preset = pick_preset_for_patient(DOPAMINE_STANDARD, weight_kg=3.0, dose_ug_kg_min=5.0)
        assert preset.concentration_ug_per_ml == DOPAMINE_STANDARD.default_concentration_ug_per_ml

    def test_returns_default_for_large_patient(self):
        preset = pick_preset_for_patient(DOPAMINE_STANDARD, weight_kg=30.0, dose_ug_kg_min=10.0)
        assert preset.concentration_ug_per_ml == DOPAMINE_STANDARD.default_concentration_ug_per_ml


class TestDopamineBagSizeVariants:
    def test_four_variants_per_concentration_set(self):
        """2 concentrations × 2 bag sizes = 4 recipe cards."""
        total = 0
        for conc in (400, 800):
            variants = bag_size_variants_for_drug(DOPAMINE_STANDARD, conc)
            total += len(variants)
        assert total == 4

    def test_800_x_250_is_full_vial(self):
        """800 µg/mL × 250 mL = 200 mg = 1 vial."""
        v = next(
            v for v in bag_size_variants_for_drug(DOPAMINE_STANDARD, 800) if v.bag_volume_ml == 250
        )
        assert v.is_suggested is True
        assert "1 vial" in v.vial_note

    def test_400_x_500_is_also_full_vial(self):
        """400 µg/mL × 500 mL = 200 mg = 1 vial. Both standard preps
        are full-vial; the suggested badge follows the concentration
        choice cleanly."""
        v = next(
            v for v in bag_size_variants_for_drug(DOPAMINE_STANDARD, 400) if v.bag_volume_ml == 500
        )
        assert v.is_suggested is True

    def test_off_diagonal_combos_not_full_vial(self):
        """800 × 500 = 400 mg (2 vials); 400 × 250 = 100 mg (half-vial).
        Neither is the standard preparation; the suggested tag points
        away from them."""
        v1 = next(
            v for v in bag_size_variants_for_drug(DOPAMINE_STANDARD, 800) if v.bag_volume_ml == 500
        )
        v2 = next(
            v for v in bag_size_variants_for_drug(DOPAMINE_STANDARD, 400) if v.bag_volume_ml == 250
        )
        assert v1.is_suggested is False
        assert v2.is_suggested is False

    def test_recipe_text_strips_disambiguation_adornment(self):
        """Display name "Dopamine CRI · standard method" should appear
        in recipes as just "dopamine" — the " · standard method"
        adornment is for navigation/catalog, not recipe text."""
        v = bag_size_variants_for_drug(DOPAMINE_STANDARD, 800)[0]
        assert "dopamine" in v.recipe_text.lower()
        assert "standard method" not in v.recipe_text.lower()


class TestDopamineFormIntegration:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_four_recipe_cards_render(self, client):
        body = client.get("/dopamine-cri").text
        # 2 concentrations × 2 bag sizes
        assert body.count("data-conc=") == 4

    def test_initial_active_is_default_pair(self, client):
        """800 µg/mL × 250 mL bag — the most common standard prep."""
        body = client.get("/dopamine-cri").text
        m = re.search(
            r'class="conc-bag-recipe is-active"\s+data-conc="(\d+)"\s+data-bag="(\d+)"',
            body,
        )
        assert m is not None
        assert m.group(1) == "800"
        assert m.group(2) == "250"

    def test_empty_strategy_attribute(self, client):
        """The pick-strategy data attr should be empty (no auto-pick)."""
        body = client.get("/dopamine-cri").text
        assert 'data-pick-strategy=""' in body

    def test_visible_bag_size_tabs(self, client):
        """Two bag-size options → tabs row should render visibly."""
        body = client.get("/dopamine-cri").text
        assert 'class="bag-size-tabs"' in body

    def test_recipe_uses_dopamine_not_dopamine_cri_or_standard_method(self, client):
        body = client.get("/dopamine-cri").text
        # The recipe text should refer to "40 mg/mL dopamine stock"
        assert "40 mg/mL dopamine stock" in body
        assert "dopamine-cri" not in body.lower() or "dopamine · standard" not in body.lower()

    def test_compute_works(self, client):
        """Math sanity. 20 kg dog @ 5 µg/kg/min × 800 µg/mL.
        Pump rate = (5 × 20 × 60) / 800 = 7.5 mL/hr."""
        r = client.post(
            "/dopamine-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "dose": "5",
                "concentration_ug_per_ml": "800",
                "species": "dog",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "250",
            },
        )
        assert r.status_code == 200
        assert "7.5" in r.text

    def test_below_floor_notice_fires(self, client):
        """Dopamine-cri now surfaces a precision-floor notice when the
        pump rate falls below the 2 mL/hr floor. Both bag sizes
        (250 / 500 mL) are volumetric for dopamine, so unlike
        dobutamine we don't gate on bag size — any sub-floor rate
        triggers the notice. The prescription points the clinician
        at the 500 mL bag (more dilute → higher rate) or a syringe
        pump."""
        # 3 kg cat @ 5 µg/kg/min × 800 → rate = 1.125 mL/hr, below floor.
        r = client.post(
            "/dopamine-cri/compute",
            data={
                "weight_value": "3",
                "weight_unit": "kg",
                "dose": "5",
                "concentration_ug_per_ml": "800",
                "species": "cat",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "250",
            },
        )
        assert r.status_code == 200
        assert "Pump rate below the precision floor" in r.text
        # Prescription mentions the 500 mL bag fix.
        assert "500 mL bag" in r.text

    def test_no_floor_notice_when_above_floor(self, client):
        """When pump rate is comfortably above the 2 mL/hr floor, no
        notice should fire."""
        # 20 kg dog @ 5 µg/kg/min × 800 → rate = 7.5 mL/hr, above floor.
        r = client.post(
            "/dopamine-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "dose": "5",
                "concentration_ug_per_ml": "800",
                "species": "dog",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "250",
            },
        )
        assert r.status_code == 200
        assert "Pump rate below the precision floor" not in r.text
