"""Dobutamine combined-prep section. Mirrors the norepi pattern that
ships as the production UI: concentration tabs + bag-size tabs +
pre-rendered recipe cards, patient-aware "suggested" badges, etc.

Dobutamine differs from norepi in three ways:
  - 2 bag sizes (50 mL syringe, 250 mL bag) instead of 3
  - Recommendation strategy is weight-band, not pump-precision
  - 250 mg / 20 mL vial (12.5 mg/mL stock), not 4 mg / 4 mL

Directional notices (too high / too low / below floor) are deliberately
not surfaced for dobutamine in v1 — the wording works for the norepi
pump-precision frame but doesn't fit dobutamine's syringe-vs-bag clinical
decision cleanly. Will be added once the right wording is settled.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DOBUTAMINE,
    bag_size_variants_for_drug,
    pick_preset_for_patient,
)
from app.main import app


class TestDobutamineConfigShape:
    """Lock down the config fields the template and JS rely on."""

    def test_uses_combined_prep_section(self):
        assert DOBUTAMINE.uses_combined_prep_section is True

    def test_bag_sizes_are_50_and_250(self):
        assert DOBUTAMINE.bag_size_options_ml == (50, 250)

    def test_default_bag_is_50_ml_syringe(self):
        """50 mL syringe pump is the dobutamine workflow default; the
        250 mL bag is the alternative for hospital volumetric workflow."""
        assert DOBUTAMINE.bag_size_default_ml == 50

    def test_vial_size_is_250_mg(self):
        """Standard commercial vial is 12.5 mg/mL × 20 mL = 250 mg.
        Drives the full-vial bag suggestion."""
        assert DOBUTAMINE.vial_size_mg == 250.0

    def test_recommendation_strategy_is_weight_band(self):
        """Dobutamine concentrations have weight bands on the
        ConcentrationPreset; the algorithm picks by patient weight,
        not by pump rate (norepi pattern)."""
        assert DOBUTAMINE.recommendation_strategy == "weight-band"

    def test_diluent_includes_lrs(self):
        """Dobutamine is compatible with 5% dextrose, 0.9% NaCl, and LRS
        (it is NOT compatible with sodium bicarbonate / alkaline solutions
        — the dilution_note covers that). LRS in the recipe is the
        clinically meaningful difference from norepi."""
        assert "LRS" in DOBUTAMINE.diluent_label

    def test_how_it_works_paragraphs_set(self):
        """The orientation disclosure should render for dobutamine."""
        assert len(DOBUTAMINE.how_it_works_paragraphs) >= 1
        # Should mention both container options so clinicians know what
        # they're choosing between.
        joined = " ".join(DOBUTAMINE.how_it_works_paragraphs)
        assert "50 mL" in joined
        assert "250 mL" in joined


class TestDobutaminePresetPicker:
    """`pick_preset_for_patient` with weight-band strategy. Bands per the
    DOBUTAMINE config:
        250 µg/mL  for <5 kg
        500 µg/mL  for 5–15 kg
        1000 µg/mL for >15 kg
    """

    def test_small_patient_picks_250(self):
        preset = pick_preset_for_patient(DOBUTAMINE, weight_kg=3.0, dose_ug_kg_min=5.0)
        assert preset.concentration_ug_per_ml == 250

    def test_medium_patient_picks_500(self):
        preset = pick_preset_for_patient(DOBUTAMINE, weight_kg=8.0, dose_ug_kg_min=5.0)
        assert preset.concentration_ug_per_ml == 500

    def test_large_patient_picks_1000(self):
        preset = pick_preset_for_patient(DOBUTAMINE, weight_kg=25.0, dose_ug_kg_min=5.0)
        assert preset.concentration_ug_per_ml == 1000

    def test_boundary_5kg_goes_to_500(self):
        """Exact boundary: 5.0 kg should fall into the 500 band (the
        upper bound on 250 is exclusive, lower bound on 500 is inclusive
        — half-open [lo, hi) interval, matching the server logic)."""
        preset = pick_preset_for_patient(DOBUTAMINE, weight_kg=5.0, dose_ug_kg_min=5.0)
        assert preset.concentration_ug_per_ml == 500

    def test_dose_is_ignored_by_weight_band(self):
        """Dose doesn't enter the weight-band calculation. A small dose
        for a large patient still picks the large-patient concentration."""
        preset = pick_preset_for_patient(DOBUTAMINE, weight_kg=25.0, dose_ug_kg_min=1.0)
        assert preset.concentration_ug_per_ml == 1000


class TestDobutamineBagSizeVariants:
    """`bag_size_variants_for_drug(DOBUTAMINE, conc)` generates the recipe
    cards for the conc × bag grid. With (50, 250) as the bag set and 1000
    µg/mL as the conc most likely to use a full 250 mg vial, only one
    combination is full-vial."""

    def test_six_variants_per_call_when_iterating_three_concs(self):
        """3 concentrations × 2 bags = 6 cards total when the router
        loops the presets."""
        total = 0
        for conc in (250, 500, 1000):
            variants = bag_size_variants_for_drug(DOBUTAMINE, conc)
            total += len(variants)
        assert total == 6

    def test_1000_x_250_is_full_vial(self):
        """1000 µg/mL × 250 mL = 250 mg drug = exactly one 250 mg vial."""
        variants = bag_size_variants_for_drug(DOBUTAMINE, 1000)
        bag_250 = next(v for v in variants if v.bag_volume_ml == 250)
        assert bag_250.is_suggested is True
        assert "1 vial" in bag_250.vial_note

    def test_partial_vial_combos_are_not_suggested(self):
        """No other (conc × bag) pairing in the dobutamine set is
        full-vial, so they should not carry the suggested flag."""
        for conc, bag in [(250, 50), (250, 250), (500, 50), (500, 250), (1000, 50)]:
            variants = bag_size_variants_for_drug(DOBUTAMINE, conc)
            v = next(v for v in variants if v.bag_volume_ml == bag)
            assert v.is_suggested is False, (
                f"{conc}×{bag} should not be flagged full-vial"
            )

    def test_recipe_text_uses_125_mg_per_ml_stock_label(self):
        """Stock is 12.5 mg/mL — the recipe should reflect this, not the
        norepi 1 mg/mL label."""
        variants = bag_size_variants_for_drug(DOBUTAMINE, 1000)
        for v in variants:
            assert "12.5 mg/mL dobutamine" in v.recipe_text, v.recipe_text

    def test_recipe_text_includes_lrs_diluent(self):
        variants = bag_size_variants_for_drug(DOBUTAMINE, 1000)
        for v in variants:
            assert "LRS" in v.recipe_text or "LRS" in v.diluent_label


class TestDobutamineFormIntegration:
    """End-to-end render of /dobutamine — the form should ship the same
    UI affordances as norepi (tabs + recipe cards + how-it-works), but
    with dobutamine-specific values."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_six_recipe_cards_render(self, client):
        body = client.get("/dobutamine").text
        # 3 concentrations × 2 bag sizes
        assert body.count("data-conc=") == 6

    def test_default_active_card_is_1000_x_50(self, client):
        body = client.get("/dobutamine").text
        m = re.search(
            r'class="conc-bag-recipe is-active"\s+data-conc="(\d+)"\s+data-bag="(\d+)"',
            body,
        )
        assert m is not None, "no .is-active recipe card on initial render"
        assert m.group(1) == "1000"
        assert m.group(2) == "50"

    def test_combined_prep_data_attributes(self, client):
        body = client.get("/dobutamine").text
        # These data attributes are what the client-side picker reads
        # to dispatch on strategy + compute full-vial bag suggestions.
        assert 'data-combined-prep="1"' in body
        assert 'data-pick-strategy="weight-band"' in body
        # vial-size 250 (mg) — rendered with possible trailing zero
        assert ('data-vial-size-mg="250"' in body
                or 'data-vial-size-mg="250.0"' in body)

    def test_conc_tabs_carry_weight_bands(self, client):
        """Weight-band picker on the client reads data-weight-min and
        data-weight-max off each .conc-tab. At minimum, the 5 and 15
        thresholds should be present."""
        body = client.get("/dobutamine").text
        assert 'data-weight-min="5"' in body
        assert 'data-weight-max="5"' in body
        assert 'data-weight-min="15"' in body
        assert 'data-weight-max="15"' in body

    def test_no_suggested_badge_on_bag_size(self, client):
        """Dobutamine's bag-size choice encodes pump TYPE (50 mL syringe
        vs 250 mL volumetric), not dilution. A "suggested" badge would
        conflict with the form's stated default (50 mL) and produce
        a visually confusing signal. The fix: drug-level opt-out
        (show_bag_size_suggestion=False) suppresses the badge entirely
        for dobutamine, and the JS dynamic update is gated on a
        data-bag-size-suggestion attribute so it doesn't add the class
        post-hoc."""
        body = client.get("/dobutamine").text
        # No is-suggested class on any bag-size-tab label.
        assert re.search(
            r'class="bag-size-tab is-suggested', body
        ) is None
        # JS opt-out attribute is rendered.
        assert 'data-bag-size-suggestion="0"' in body
        # The "suggested" badge span itself is also gated; no badge
        # spans should appear inside bag-size-tab labels.
        bag_size_section = re.search(
            r'<div class="bag-size-tabs"[\s\S]+?</div>', body
        )
        assert bag_size_section is not None
        assert "bag-size-tab__badge" not in bag_size_section.group(0)

    def test_50_ml_bag_is_initial_checked(self, client):
        body = client.get("/dobutamine").text
        m = re.search(
            r'name="combined_prep_bag_size_ml"\s+value="(\d+)"\s+checked',
            body,
        )
        assert m is not None
        assert m.group(1) == "50"

    def test_how_it_works_disclosure_renders(self, client):
        body = client.get("/dobutamine").text
        assert "How this calculator works" in body

    def test_advanced_mode_label_uses_combined_prep_copy(self, client):
        """The Advanced / target-pump-rate label was rewritten when the
        combined-prep section shipped (norepi); dobutamine should pick
        up the same copy now that it shares the pattern."""
        body = client.get("/dobutamine").text
        assert "Advanced: target pump rate" in body

    def test_compute_works(self, client):
        """A sanity check on the POST path — generalizing the form
        shouldn't have disturbed the math."""
        # 20 kg dog @ 5 µg/kg/min on the 1000 µg/mL bag.
        # pump rate = (5 × 20 × 60) / 1000 = 6 mL/hr.
        r = client.post(
            "/dobutamine/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "dose": "5",
                "concentration_ug_per_ml": "1000",
                "species": "dog",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "50",
            },
        )
        assert r.status_code == 200
        assert "6" in r.text  # 6 mL/hr pump rate


class TestDobutamineVolumetricBelowFloorNotice:
    """The volumetric-below-floor notice fires when the user has the
    250 mL bag selected AND the computed pump rate is below 2 mL/hr.
    Prescription: use a syringe pump, or select a different concentration.

    The notice does NOT fire when:
      - the user has the 50 mL syringe selected (assumes syringe pump
        is already in use)
      - the rate is at or above 2 mL/hr
      - the user is in TARGET_PUMP_RATE mode (no bag selection involved)
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def _post(self, client, weight, dose, conc, bag, *, species="dog"):
        return client.post(
            "/dobutamine/compute",
            data={
                "weight_value": str(weight),
                "weight_unit": "kg",
                "dose": str(dose),
                "concentration_ug_per_ml": str(conc),
                "species": species,
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": str(bag),
            },
        )

    def test_fires_on_250_bag_with_sub_floor_rate(self, client):
        """2 kg cat @ 2.5 µg/kg/min @ 1000 µg/mL × 250 mL bag.
        Rate = (2.5 × 2 × 60) / 1000 = 0.3 mL/hr → below floor → fires."""
        body = self._post(client, 2, 2.5, 1000, 250, species="cat").text
        assert "Pump rate below the precision floor" in body
        assert "Use a syringe pump, or select a different concentration" in body

    def test_suppressed_on_50_ml_syringe_path(self, client):
        """Same sub-floor rate but user has chosen the 50 mL syringe.
        Notice should NOT fire — the assumption is a syringe pump is in
        use, where the floor doesn't apply."""
        body = self._post(client, 2, 2.5, 1000, 50, species="cat").text
        assert "Use a syringe pump, or select a different concentration" not in body

    def test_suppressed_when_rate_above_floor(self, client):
        """20 kg dog @ 5 µg/kg/min @ 1000 µg/mL × 250 mL bag.
        Rate = 6 mL/hr → above 2 mL/hr → no notice."""
        body = self._post(client, 20, 5, 1000, 250).text
        assert "Use a syringe pump, or select a different concentration" not in body

    def test_fires_even_at_most_dilute_concentration(self, client):
        """2 kg cat @ 2.5 µg/kg/min @ 250 µg/mL × 250 mL bag.
        Already at the most dilute pump-safe preset, rate is still
        below floor (1.2 mL/hr). Notice should still fire — the
        clinician needs to know the volumetric pump can't deliver
        this accurately. Tim's prescription ("or select a different
        concentration") is general by design; in this edge case the
        user will realize no different concentration helps and reach
        for a syringe pump."""
        body = self._post(client, 2, 2.5, 250, 250, species="cat").text
        assert "Pump rate below the precision floor" in body

    def test_does_not_fire_on_norepinephrine(self, client):
        """Sanity check: the dobutamine-specific notice copy must not
        appear on norepi results, even though norepi has its own
        below-floor notice with similar style."""
        body = client.post(
            "/norepinephrine/compute",
            data={
                "weight_value": "2",
                "weight_unit": "kg",
                "dose": "0.05",
                "concentration_ug_per_ml": "16",
                "species": "cat",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "250",
            },
        ).text
        # Norepi's own below-floor wording is different
        assert "Use a syringe pump, or select a different concentration" not in body
