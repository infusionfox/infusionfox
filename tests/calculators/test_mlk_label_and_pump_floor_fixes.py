"""Tests for three small fixes shipped in the post-vasopressor cleanup:

1. MLK label broadening — the combined-bag radio in the analgesia
   builder lists the named protocols it covers (FLK, DMLK, KL, DLK)
   instead of only "MLK-style", since the combined-bag mode is the
   umbrella workflow for any one-bag-one-pump-rate composition.

2. Dobutamine suggested-bag fix — dobutamine's bag-size choice encodes
   pump TYPE (50 mL syringe vs 250 mL volumetric), not dilution. The
   "suggested" badge was floating to 250 mL via the full-vial
   computation while the form defaulted to 50 mL, producing a
   conflicting visual signal. Now suppressed for dobutamine.

3. Dopamine sub-floor notice — dopamine-cri now surfaces a precision-
   floor notice when the pump rate drops below 2 mL/hr, prescribing
   the 500 mL more-dilute bag or a syringe pump. Previously the
   notice didn't exist for dopamine.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DOBUTAMINE,
    DOPAMINE_STANDARD,
    NOREPINEPHRINE,
    PHENYLEPHRINE,
    VASOPRESSIN,
)
from app.main import app

client = TestClient(app)


class TestMlkLabelBroadening:
    """The combined-bag radio in the analgesia builder names every
    protocol it covers, not just MLK."""

    def test_radio_label_no_longer_says_mlk_style(self):
        body = client.get("/analgesia-cri").text
        # The bare "Combined bag (MLK-style)" parenthetical is removed.
        assert "(MLK-style)" not in body

    def test_radio_label_just_says_combined_bag(self):
        body = client.get("/analgesia-cri").text
        # The label itself is just "Combined bag".
        assert ">\n                            Combined bag\n" in body

    def test_sub_line_lists_all_named_protocols(self):
        """Sub-line under the radio names each acronym this prep mode
        covers, so a clinician scanning for FLK/DMLK/KL/DLK can see
        that this is where those workflows live."""
        body = client.get("/analgesia-cri").text
        for protocol in ("MLK", "FLK", "DMLK", "KL", "DLK"):
            assert protocol in body, f"missing protocol mention: {protocol}"


class TestDobutamineSuggestedBagSuppression:
    """Dobutamine's bag-size choice encodes pump TYPE rather than
    dilution. The "suggested" badge made no sense and pointed at the
    wrong bag — now suppressed at the config level."""

    def test_config_flag_is_false(self):
        assert DOBUTAMINE.show_bag_size_suggestion is False

    def test_form_renders_no_suggested_badge(self):
        body = client.get("/dobutamine").text
        # No is-suggested on any bag-size-tab.
        assert 'class="bag-size-tab is-suggested' not in body

    def test_js_opt_out_attribute_present(self):
        body = client.get("/dobutamine").text
        # JS dynamic update is gated on this attribute.
        assert 'data-bag-size-suggestion="0"' in body


class TestSuggestedBagPreservedForOtherVasopressors:
    """Regression: drugs where bag size encodes dilution (norepi,
    epi, vasopressin, phenylephrine, dopamine-cri) still get the
    suggested-badge UX."""

    def test_norepi_keeps_suggestion(self):
        assert NOREPINEPHRINE.show_bag_size_suggestion is True
        body = client.get("/norepinephrine").text
        assert 'data-bag-size-suggestion="1"' in body
        # Initial render places is-suggested on at least one tab.
        assert "is-suggested" in body

    def test_vasopressin_keeps_suggestion(self):
        assert VASOPRESSIN.show_bag_size_suggestion is True
        body = client.get("/vasopressin").text
        assert 'data-bag-size-suggestion="1"' in body

    def test_phenylephrine_keeps_suggestion(self):
        assert PHENYLEPHRINE.show_bag_size_suggestion is True
        body = client.get("/phenylephrine").text
        assert 'data-bag-size-suggestion="1"' in body

    def test_dopamine_cri_keeps_suggestion(self):
        assert DOPAMINE_STANDARD.show_bag_size_suggestion is True
        body = client.get("/dopamine-cri").text
        assert 'data-bag-size-suggestion="1"' in body


class TestDopaminePrecisionFloorNotice:
    """Dopamine-cri surfaces a sub-floor warning when patient × dose
    × concentration produces a pump rate below 2 mL/hr."""

    def test_small_patient_low_dose_triggers_notice(self):
        # 3 kg patient × 3 µg/kg/min × 60 ÷ 800 µg/mL = 0.675 mL/hr.
        r = client.post(
            "/dopamine-cri/compute",
            data={
                "weight_value": "3",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "3",
                "concentration_ug_per_ml": "800",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "250",
            },
        )
        body = r.text
        assert "Pump rate below the precision floor" in body
        # Prescription names the specific 500 mL bag fix (the dilution
        # remedy unique to dopamine's two-bag-size options).
        assert "500 mL bag" in body

    def test_above_floor_does_not_trigger(self):
        # 20 kg × 5 × 60 ÷ 800 = 7.5 mL/hr, above floor.
        r = client.post(
            "/dopamine-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "5",
                "concentration_ug_per_ml": "800",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "250",
            },
        )
        assert "Pump rate below the precision floor" not in r.text

    def test_500ml_bag_sub_floor_also_fires(self):
        """Unlike dobutamine (notice only fires on 250 mL bag), dopamine's
        notice fires on either bag size since both are volumetric."""
        # 3 kg × 3 µg/kg/min × 60 ÷ 400 = 1.35 mL/hr, still below floor.
        r = client.post(
            "/dopamine-cri/compute",
            data={
                "weight_value": "3",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "3",
                "concentration_ug_per_ml": "400",
                "cri_mode": "standard_bag",
                "combined_prep_bag_size_ml": "500",
            },
        )
        assert "Pump rate below the precision floor" in r.text
