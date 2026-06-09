"""Tests for norepinephrine pump-precision-aware preparation logic.

The norepi calculator auto-picks a concentration based on patient weight
and dose to keep pump rate ≥ 2 mL/hr (the precision floor of most
volumetric pumps), and generates bag-size variants (250 / 500 / 1 L) at
that concentration so clinicians can pick what their clinic stocks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    NOREPI_DEFAULT_MIN_PUMP_RATE_ML_PER_HR,
    NOREPI_VIAL_SIZE_MG,
    NOREPINEPHRINE,
    bag_size_variants_for_norepi,
    pick_norepi_preset_for_patient,
)
from app.main import app

# ---------------------------------------------------------------------------
# Auto-pick algorithm
# ---------------------------------------------------------------------------


class TestPickNorepiPresetForPatient:
    """The auto-pick selects the least-dilute (highest concentration)
    norepi preset that keeps pump rate ≥ 2 mL/hr at the given dose."""

    def test_large_dog_picks_16(self):
        # 20 kg dog at 0.1 µg/kg/min → 120 µg/hr → 7.5 mL/hr at 16 µg/mL
        preset = pick_norepi_preset_for_patient(weight_kg=20, dose_ug_kg_min=0.1)
        assert preset.concentration_ug_per_ml == 16

    def test_medium_dog_picks_16(self):
        # 8 kg dog at 0.1 µg/kg/min → 48 µg/hr → 3.0 mL/hr at 16 µg/mL
        preset = pick_norepi_preset_for_patient(weight_kg=8, dose_ug_kg_min=0.1)
        assert preset.concentration_ug_per_ml == 16

    def test_small_dog_picks_8(self):
        # 5 kg dog at 0.1 µg/kg/min → 30 µg/hr → 1.875 mL/hr at 16 (below floor),
        # → 3.75 mL/hr at 8 µg/mL
        preset = pick_norepi_preset_for_patient(weight_kg=5, dose_ug_kg_min=0.1)
        assert preset.concentration_ug_per_ml == 8

    def test_cat_picks_8(self):
        # 4 kg cat at 0.1 µg/kg/min → 24 µg/hr → 1.5 at 16 (below),
        # → 3.0 at 8 µg/mL
        preset = pick_norepi_preset_for_patient(weight_kg=4, dose_ug_kg_min=0.1)
        assert preset.concentration_ug_per_ml == 8

    def test_small_cat_at_low_dose_picks_4(self):
        # 3 kg cat at 0.05 µg/kg/min → 9 µg/hr → 0.56 at 16, 1.125 at 8,
        # → 2.25 at 4 µg/mL
        preset = pick_norepi_preset_for_patient(weight_kg=3, dose_ug_kg_min=0.05)
        assert preset.concentration_ug_per_ml == 4

    def test_kitten_edge_case_picks_most_dilute(self):
        # 2 kg kitten at 0.05 µg/kg/min → 6 µg/hr → all 3 standard presets
        # give sub-2 mL/hr rates. The algorithm falls through and picks
        # the most dilute available; the caller surfaces a warning.
        preset = pick_norepi_preset_for_patient(weight_kg=2, dose_ug_kg_min=0.05)
        assert preset.concentration_ug_per_ml == 4

    def test_picks_least_dilute_above_floor(self):
        """The algorithm minimizes carrier fluid by picking the highest
        concentration above the floor, not the lowest."""
        # 8 kg dog at 0.1 µg/kg/min: 16 µg/mL gives 3.0 mL/hr (above
        # floor). Picks 16, not 8 or 4.
        preset = pick_norepi_preset_for_patient(weight_kg=8, dose_ug_kg_min=0.1)
        assert preset.concentration_ug_per_ml == 16

    @pytest.mark.parametrize("weight,dose,expected_conc", [
        (40, 0.1, 16),
        (20, 0.1, 16),
        (10, 0.1, 16),
        (8, 0.1, 16),
        (6, 0.1, 16),  # 3.75 mL/hr — just above floor
        (5, 0.1, 8),   # 1.88 at 16, 3.75 at 8
        (4, 0.1, 8),
        (3, 0.1, 8),   # 1.125 at 16, 2.25 at 8
        (3, 0.05, 4),  # very low dose drops to 4
        (2, 0.1, 4),   # 0.75 at 16, 1.5 at 8, 3.0 at 4
    ])
    def test_dose_weight_combinations(self, weight, dose, expected_conc):
        preset = pick_norepi_preset_for_patient(weight_kg=weight, dose_ug_kg_min=dose)
        assert preset.concentration_ug_per_ml == expected_conc, (
            f"weight={weight}, dose={dose}: expected {expected_conc}, "
            f"got {preset.concentration_ug_per_ml}"
        )


# ---------------------------------------------------------------------------
# Bag size variants
# ---------------------------------------------------------------------------


class TestBagSizeVariantsForNorepi:
    """At a fixed concentration, the bag size determines drug amount;
    the bag using exactly one 4 mg vial is the suggested preparation."""

    def test_16_ug_per_ml_suggests_250ml(self):
        variants = bag_size_variants_for_norepi(16.0)
        suggested = [v for v in variants if v.is_suggested]
        assert len(suggested) == 1
        assert suggested[0].bag_volume_ml == 250
        assert suggested[0].drug_amount_mg == pytest.approx(4.0)

    def test_8_ug_per_ml_suggests_500ml(self):
        variants = bag_size_variants_for_norepi(8.0)
        suggested = [v for v in variants if v.is_suggested]
        assert len(suggested) == 1
        assert suggested[0].bag_volume_ml == 500
        assert suggested[0].drug_amount_mg == pytest.approx(4.0)

    def test_4_ug_per_ml_suggests_1000ml(self):
        variants = bag_size_variants_for_norepi(4.0)
        suggested = [v for v in variants if v.is_suggested]
        assert len(suggested) == 1
        assert suggested[0].bag_volume_ml == 1000
        assert suggested[0].drug_amount_mg == pytest.approx(4.0)

    def test_three_variants_returned(self):
        variants = bag_size_variants_for_norepi(8.0)
        assert len(variants) == 3
        bag_sizes = [v.bag_volume_ml for v in variants]
        assert 250 in bag_sizes
        assert 500 in bag_sizes
        assert 1000 in bag_sizes

    def test_drug_amount_scales_with_bag_volume(self):
        """At fixed concentration, drug amount = concentration × bag volume."""
        variants = bag_size_variants_for_norepi(8.0)
        for v in variants:
            expected_mg = 8.0 * v.bag_volume_ml / 1000.0
            assert v.drug_amount_mg == pytest.approx(expected_mg)

    def test_vials_used_calculation(self):
        """Vials used = drug amount / 4 mg per vial."""
        variants = bag_size_variants_for_norepi(8.0)
        by_size = {v.bag_volume_ml: v for v in variants}

        # 250 mL × 8 µg/mL = 2 mg = half-vial
        assert by_size[250].vials_used == pytest.approx(0.5)
        assert "half-vial" in by_size[250].vial_note

        # 500 mL × 8 µg/mL = 4 mg = 1 vial
        assert by_size[500].vials_used == pytest.approx(1.0)
        assert by_size[500].vial_note == "1 vial"

        # 1000 mL × 8 µg/mL = 8 mg = 2 vials
        assert by_size[1000].vials_used == pytest.approx(2.0)
        assert "2 vials" in by_size[1000].vial_note

    def test_recipe_text_includes_drug_amount_and_bag_size(self):
        variants = bag_size_variants_for_norepi(8.0)
        for v in variants:
            assert f"{v.bag_volume_ml} mL bag" in v.recipe_text

    def test_pump_rate_invariant_across_bag_sizes(self):
        """The pump rate is determined by dose + weight + concentration.
        Bag size has no effect; this is the whole point of the design."""
        # For a fixed concentration, all bag sizes give the same pump
        # rate at the same dose × weight. The drug amount and bag
        # duration are the only things that change.
        variants = bag_size_variants_for_norepi(8.0)
        # All variants share the same concentration.
        concentrations = {v.concentration_ug_per_ml for v in variants}
        assert concentrations == {8.0}


# ---------------------------------------------------------------------------
# Router integration — end-to-end via the compute endpoint
# ---------------------------------------------------------------------------


class TestNorepiFormIntegration:
    """The form (GET /norepinephrine) renders the combined concentration +
    bag-size preparation section. All 9 (3 conc × 3 bag) recipe cards are
    pre-rendered; JS toggles which is .is-active based on the checked
    radios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_form_renders_three_concentration_tabs(self, client):
        resp = client.get("/norepinephrine")
        assert resp.status_code == 200
        body = resp.text
        # Container for the concentration tabs
        assert "conc-tabs" in body
        # The generic auto-select flag (renamed from data-norepi-auto-select
        # when the pattern was generalized for dobutamine).
        assert "data-combined-prep" in body
        # All three concentration radios
        assert 'name="concentration_ug_per_ml"' in body
        for conc in (4, 8, 16):
            assert f'value="{conc}"' in body or f'value="{conc}.0"' in body

    def test_form_renders_three_bag_size_tabs(self, client):
        resp = client.get("/norepinephrine")
        body = resp.text
        # Container for the bag size tabs
        assert "bag-size-tabs" in body
        # Generic radio name (renamed from norepi_bag_size_ml when the
        # pattern was generalized).
        assert 'name="combined_prep_bag_size_ml"' in body
        for bag in (250, 500, 1000):
            assert f'value="{bag}"' in body

    def test_form_renders_nine_recipe_cards(self, client):
        """3 concentrations × 3 bag sizes = 9 pre-rendered recipe cards.
        Each card carries a `data-conc` attribute on its outer div, which
        is unique to the wrapper (child elements use class names like
        `conc-bag-recipe__title` without the attribute)."""
        resp = client.get("/norepinephrine")
        body = resp.text
        assert body.count("data-conc=") == 9

    def test_default_recipe_card_is_active(self, client):
        """On initial load, the recipe matching the default concentration
        (16 µg/mL) and default bag (250 mL) is .is-active. The other 8
        are display:none via CSS."""
        resp = client.get("/norepinephrine")
        body = resp.text
        # Exactly one .conc-bag-recipe has the .is-active class on initial load
        assert body.count("conc-bag-recipe is-active") == 1
        # And it's the 16/250 combination
        active_start = body.find("conc-bag-recipe is-active")
        active_section = body[active_start:active_start + 500]
        assert 'data-conc="16"' in active_section
        assert 'data-bag="250"' in active_section

    def test_only_one_bag_size_radio_initially_checked(self, client):
        resp = client.get("/norepinephrine")
        body = resp.text
        # Slice from the bag-size-tabs section start
        bag_section_start = body.find("bag-size-tabs")
        bag_section_end = body.find("conc-bag-recipes")
        assert bag_section_start > 0
        assert bag_section_end > bag_section_start
        bag_section = body[bag_section_start:bag_section_end]
        assert bag_section.count("checked") == 1

    def test_only_one_concentration_radio_initially_checked(self, client):
        resp = client.get("/norepinephrine")
        body = resp.text
        # Slice from the conc-tabs to the bag-size-tabs section
        conc_section_start = body.find("conc-tabs")
        conc_section_end = body.find("bag-size-tabs")
        assert conc_section_start > 0
        assert conc_section_end > conc_section_start
        conc_section = body[conc_section_start:conc_section_end]
        assert conc_section.count("checked") == 1

    def test_full_vial_recipes_carry_suggested_badge(self, client):
        """The three full-vial recipes (16/250, 8/500, 4/1000) should each
        have the 'suggested · uses one full vial' badge."""
        resp = client.get("/norepinephrine")
        body = resp.text
        # The badge text appears 3 times — once per full-vial combination.
        assert body.count("suggested · uses one full vial") == 3

    def test_initial_suggested_badge_on_default_concentration_tab(self, client):
        """The default concentration tab (16 µg/mL) is marked
        .is-suggested on initial render. JS moves the badge as weight
        is entered."""
        resp = client.get("/norepinephrine")
        body = resp.text
        # Slice the conc-tabs section out of the page
        conc_start = body.find('class="conc-tabs"')
        conc_end = body.find('class="bag-size-tabs"')
        assert conc_start > 0 and conc_end > conc_start
        conc_section = body[conc_start:conc_end]
        # Exactly one conc-tab is marked .is-suggested initially
        assert conc_section.count("conc-tab is-suggested") == 1
        # And it's the 16 µg/mL one (the default)
        suggested_start = conc_section.find("conc-tab is-suggested")
        # The next ~250 chars should contain value="16"
        assert 'value="16"' in conc_section[suggested_start:suggested_start + 300]

    def test_initial_suggested_badge_on_default_bag_tab(self, client):
        """The 250 mL bag tab (full-vial match for 16 µg/mL default)
        is marked .is-suggested on initial render."""
        resp = client.get("/norepinephrine")
        body = resp.text
        bag_start = body.find('class="bag-size-tabs"')
        bag_end = body.find('class="conc-bag-recipes"')
        assert bag_start > 0 and bag_end > bag_start
        bag_section = body[bag_start:bag_end]
        assert bag_section.count("bag-size-tab is-suggested") == 1
        # And it's the 250 mL one
        suggested_start = bag_section.find("bag-size-tab is-suggested")
        assert 'value="250"' in bag_section[suggested_start:suggested_start + 300]

    def test_every_tab_has_a_suggested_badge_span(self, client):
        """All three conc tabs and all three bag tabs render a badge
        span (display:none unless parent is .is-suggested). JS moves the
        .is-suggested class around, but the span is always present."""
        resp = client.get("/norepinephrine")
        body = resp.text
        # Three conc-tab badges + three bag-size-tab badges
        assert body.count('class="conc-tab__badge"') == 3
        assert body.count('class="bag-size-tab__badge"') == 3

    def test_how_it_works_disclosure_present(self, client):
        """The norepi calculator has a collapsed-by-default explainer
        at the top. Covers the auto-pick, suggested-tag, and advanced-mode
        concepts in three short paragraphs."""
        resp = client.get("/norepinephrine")
        body = resp.text
        assert '<details class="how-it-works"' in body
        assert "How this calculator works" in body
        # Spot-check that the three key concepts are mentioned
        assert "suggested" in body.lower()
        assert "Advanced: target pump rate" in body
        # Default state is collapsed (no `open` attribute)
        assert '<details class="how-it-works" open' not in body

    def test_how_it_works_present_on_every_cri(self, client):
        """Every CRI calculator includes a "How this calculator works"
        disclosure now. The four combined-prep drugs (norepi, dobutamine,
        epi, dopamine-cri) describe the tab-driven UI; fentanyl describes
        the legacy prep-card UI plus the loading-dose section. Tim's
        instruction: every updated calculator includes the disclosure."""
        for slug in (
            "norepinephrine",
            "dobutamine",
            "epinephrine",
            "dopamine-cri",
            "fentanyl",
        ):
            resp = client.get(f"/{slug}")
            assert "How this calculator works" in resp.text, (
                f"/{slug} should include the how-it-works disclosure"
            )


class TestNorepiResultPanelNotices:
    """The result panel keeps the precision notices (above the headline).
    The full bag-prep section has moved to the form."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def _post(self, client, weight, dose, conc, species="dog"):
        return client.post(
            "/norepinephrine/compute",
            data={
                "weight_value": str(weight),
                "weight_unit": "kg",
                "dose": str(dose),
                "concentration_ug_per_ml": str(conc),
                "species": species,
                "cri_mode": "standard_bag",
                "target_pump_rate_ml_per_hr": "3",
                "bag_volume_ml": "250",
            },
        )

    def test_no_notice_when_concentration_matches_recommendation(self, client):
        resp = self._post(client, weight=20, dose=0.1, conc=16)
        assert resp.status_code == 200
        assert "More precise preparation available" not in resp.text
        assert "Pump rate below the precision floor" not in resp.text

    def test_recommendation_notice_when_concentration_mismatches(self, client):
        """4 kg cat at 16 µg/mL: recommendation is 8 µg/mL, surface the notice."""
        resp = self._post(client, weight=4, dose=0.1, conc=16, species="cat")
        assert resp.status_code == 200
        assert "More precise preparation available" in resp.text
        assert "8 µg/mL" in resp.text

    def test_no_notice_when_user_at_recommendation(self, client):
        resp = self._post(client, weight=4, dose=0.1, conc=8, species="cat")
        assert resp.status_code == 200
        assert "More precise preparation available" not in resp.text

    def test_below_floor_warning_in_edge_case(self, client):
        """2 kg kitten at 0.05 µg/kg/min: every preset gives a sub-floor rate."""
        resp = self._post(client, weight=2, dose=0.05, conc=16, species="cat")
        assert resp.status_code == 200
        assert "Pump rate below the precision floor" in resp.text

    def test_notice_appears_above_headline(self, client):
        """The notice is positioned above the headline so the clinician
        sees it before reading the pump rate."""
        resp = self._post(client, weight=4, dose=0.1, conc=16, species="cat")
        body = resp.text
        notice_pos = body.find("More precise preparation available")
        headline_pos = body.find('class="result__headline"')
        assert notice_pos > 0
        assert headline_pos > 0
        assert notice_pos < headline_pos

    def test_result_panel_does_not_render_old_bag_prep_section(self, client):
        """The bag prep tabs/recipe lived in the result panel before; now
        they live on the form. The result panel should NOT render them."""
        resp = self._post(client, weight=20, dose=0.1, conc=16)
        body = resp.text
        # These classes only existed on the old result-panel bag-prep
        assert "norepi-prep__tabs" not in body
        assert "norepi-prep__recipes" not in body
        assert 'norepi-prep__recipe ' not in body

    def test_too_low_concentration_shows_fluid_load_notice(self, client):
        """20 kg dog at 4 µg/mL: rate is 30 mL/hr — well above the
        precision floor, but unnecessarily high. The notice should
        describe fluid load, NOT 'below the 2 mL/hr precision floor'."""
        resp = self._post(client, weight=20, dose=0.1, conc=4)
        body = resp.text
        # Fluid-load wording present
        assert "reduce fluid load" in body
        # Precision-floor wording NOT present in the too-low case —
        # that was the clinical bug we're fixing.
        assert "below the 2 mL/hr precision floor" not in body
        # The "More precise preparation available" header (which is
        # specific to the too-high case) also should not appear here.
        assert "More precise preparation available" not in body

    def test_too_low_notice_mentions_recommendation_and_better_rate(self, client):
        """The fluid-load notice should name the recommended concentration
        and the rate that preparation would give."""
        resp = self._post(client, weight=20, dose=0.1, conc=4)
        body = resp.text
        # 20 kg at 0.1 µg/kg/min → 120 µg/hr → at 16 µg/mL = 7.50 mL/hr
        assert "16 µg/mL" in body
        assert "7.50 mL/hr" in body

    def test_too_high_concentration_still_shows_precision_notice(self, client):
        """The original too-high case (4 kg cat at 16 µg/mL, rate 1.5 mL/hr)
        still surfaces the precision-floor notice — that wording was
        correct for this direction."""
        resp = self._post(client, weight=4, dose=0.1, conc=16, species="cat")
        body = resp.text
        assert "More precise preparation available" in body
        assert "below the 2 mL/hr precision floor" in body
        # The fluid-load wording should NOT appear in the too-high case.
        assert "reduce fluid load" not in body

    def test_only_one_directional_notice_at_a_time(self, client):
        """The too-high and too-low notices are mutually exclusive — one
        flag fires for any given (concentration, recommendation) pair."""
        # Too-high case: only the precision notice
        resp = self._post(client, weight=4, dose=0.1, conc=16, species="cat")
        body = resp.text
        assert ("More precise preparation available" in body) and (
            "reduce fluid load" not in body
        )

        # Too-low case: only the fluid-load notice
        resp = self._post(client, weight=20, dose=0.1, conc=4)
        body = resp.text
        assert ("reduce fluid load" in body) and (
            "More precise preparation available" not in body
        )


# ---------------------------------------------------------------------------
# Sanity checks on the norepi config itself
# ---------------------------------------------------------------------------


class TestNorepiConfigStructure:
    """Defensive checks on the NOREPINEPHRINE config — these protect
    against accidental changes to the preset tiers that would shift the
    pump-precision algorithm."""

    def test_three_pump_safe_presets(self):
        pump_safe = [p for p in NOREPINEPHRINE.concentration_presets if p.pump_safe]
        assert len(pump_safe) == 3

    def test_preset_concentrations_are_4_8_16(self):
        pump_safe = [p for p in NOREPINEPHRINE.concentration_presets if p.pump_safe]
        concentrations = sorted(p.concentration_ug_per_ml for p in pump_safe)
        assert concentrations == [4, 8, 16]

    def test_each_full_vial_recipe_uses_one_vial(self):
        """Each preset's stated recipe should use exactly one 4 mg vial
        when paired with its natural bag size (250/500/1000 mL)."""
        # 16 µg/mL × 250 mL = 4 mg = 1 vial
        # 8 µg/mL × 500 mL = 4 mg = 1 vial
        # 4 µg/mL × 1000 mL = 4 mg = 1 vial
        for preset in NOREPINEPHRINE.concentration_presets:
            if not preset.pump_safe:
                continue
            # The recipe text should mention the full vial
            assert "1 vial" in preset.recipe, (
                f"Preset {preset.concentration_ug_per_ml} µg/mL recipe "
                f"should reference '1 vial': {preset.recipe!r}"
            )

    def test_min_pump_rate_floor_is_2_ml_per_hr(self):
        """The pump-precision floor is documented as 2 mL/hr; if this
        changes, the algorithm boundaries shift and the worked examples
        in tests above need updating."""
        assert NOREPI_DEFAULT_MIN_PUMP_RATE_ML_PER_HR == 2.0

    def test_vial_size_is_4_mg(self):
        """Norepi vials are 4 mg / 4 mL; the full-vial suggestion logic
        depends on this constant."""
        assert NOREPI_VIAL_SIZE_MG == 4.0
