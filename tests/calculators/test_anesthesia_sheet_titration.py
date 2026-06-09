"""
Tests for the anesthesia-hub titration ladders.

The hub builds three CRILine objects (dopamine, dobutamine, norepinephrine).
All three render a weight-scaled titration ladder. Bag dilution is auto-
selected by patient weight: the most concentrated standard preparation is
chosen whose lowest titration step still produces a ≥ 2 mL/hr pump rate
(reliable IV-pump range). Small patients automatically get a more dilute
bag, and very small patients fall back to the most dilute available and
get a syringe-pump note in the prep_note.

Standard 20 kg dog hits the conventional bags:
- Dopamine 1600 µg/mL (400 mg in 250 mL): mL/hr = weight × dose × 60 / 1600
- Dobutamine 1 mg/mL = 1000 µg/mL: mL/hr = weight × dose × 60 / 1000
- Norepinephrine 16 µg/mL (4 mg in 250 mL): mL/hr = weight × dose × 60 / 16

4 kg cat auto-dilutes per drug:
- Dopamine drops to 400 µg/mL (so 5 µg/kg/min × 4 × 60 / 400 = 3 mL/hr)
- Dobutamine stays at the most-dilute 250 µg/mL but flagged below-threshold
  because even there, 1 µg/kg/min × 4 × 60 / 250 = 0.96 mL/hr < 2
- Norepinephrine drops to 8 µg/mL (so 0.1 × 4 × 60 / 8 = 3 mL/hr)

Caution thresholds:
- Dopamine: 10 µg/kg/min for dogs, 2.0 µg/kg/min for cats (always-on for
  cats, matches the standalone /dopamine calculator HCM-risk rationale).
- Dobutamine: 10 µg/kg/min for dogs, 5 µg/kg/min for cats.
- Norepinephrine: 1.0 µg/kg/min for both species.
"""

from __future__ import annotations

import pytest

from app.calculators.anesthesia_sheet import AnesthSpecies, calculate
from app.calculators.engine import WeightUnit


@pytest.fixture
def dog_20kg():
    return calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "Test", "5y")


@pytest.fixture
def cat_4kg():
    return calculate(4.0, WeightUnit.KG, AnesthSpecies.CAT, "Test", "8y")


def test_all_three_cris_have_ladders(dog_20kg):
    # All three vasopressor/inotrope CRIs render a ladder.
    assert len(dog_20kg.dopamine_cri.titration_steps) > 0
    assert len(dog_20kg.dobutamine_cri.titration_steps) > 0
    assert len(dog_20kg.norepi_cri.titration_steps) > 0


def test_concentration_labels_present_for_standard_dog(dog_20kg):
    # 20 kg dog gets the standard conventional bags.
    assert "250 mL" in dog_20kg.dopamine_cri.titration_concentration_label
    assert "1600 µg/mL" in dog_20kg.dopamine_cri.titration_concentration_label
    assert "1 mg/mL" in dog_20kg.dobutamine_cri.titration_concentration_label
    assert "16 µg/mL" in dog_20kg.norepi_cri.titration_concentration_label


class TestDopamineMath:
    """Dopamine bag is auto-selected by patient weight. Standard 20 kg dog
    hits the 1600 µg/mL bag; 4 kg cat auto-dilutes to 400 µg/mL."""

    def test_known_value_dog(self, dog_20kg):
        # 20 kg × 5 µg/kg/min × 60 / 1600 = 3.75 mL/hr
        step_5 = next(
            s for s in dog_20kg.dopamine_cri.titration_steps if s.dose_ug_per_kg_per_min == 5.0
        )
        assert step_5.ml_per_hr == pytest.approx(3.75)

    def test_cat_auto_dilutes_to_400_ug_per_ml(self, cat_4kg):
        # 4 kg cat: 1600 → 0.75 mL/hr (< 2), 800 → 1.5 (< 2), 400 → 3.0 (≥ 2).
        # Auto-selected dilution is 400 µg/mL.
        assert "400 µg/mL" in cat_4kg.dopamine_cri.titration_concentration_label
        # 4 kg × 5 µg/kg/min × 60 / 400 = 3.0 mL/hr
        step_5 = next(
            s for s in cat_4kg.dopamine_cri.titration_steps if s.dose_ug_per_kg_per_min == 5.0
        )
        assert step_5.ml_per_hr == pytest.approx(3.0)

    def test_ladder_starts_at_recommended_low(self, dog_20kg):
        # Ladder starts at 5 µg/kg/min (recommended low), not below.
        lowest_dose = min(s.dose_ug_per_kg_per_min for s in dog_20kg.dopamine_cri.titration_steps)
        assert lowest_dose == 5.0

    def test_prep_note_mentions_dilution(self, dog_20kg):
        # Prep instructions must reference the actual ingredients of the
        # selected dilution.
        note = dog_20kg.dopamine_cri.prep_note
        assert "400 mg" in note
        assert "250 mL" in note
        assert "1600 µg/mL" in note
        # Should not reference the legacy 6×kg method.
        assert "6×kg" not in note


class TestDobutamineMath:
    def test_known_value_dog(self, dog_20kg):
        # 20 kg dog gets the standard 1 mg/mL prep (lowest ladder dose
        # 2.5 µg/kg/min produces 3 mL/hr at 1 mg/mL — above 2).
        # 20 kg × 5 µg/kg/min × 60 / 1000 = 6.0 mL/hr
        step_5 = next(s for s in dog_20kg.dobutamine_cri.titration_steps if s.dose_ug_per_kg_per_min == 5.0)
        assert step_5.ml_per_hr == pytest.approx(6.0)

    def test_cat_4kg_auto_dilutes_to_intermediate_prep(self, cat_4kg):
        # 4 kg cat at cat ladder floor (1 µg/kg/min):
        #   1 mg/mL: 4 × 1 × 60 / 1000 = 0.24 mL/hr (< 2, reject)
        #   0.5 mg/mL: 0.48 mL/hr (< 2, reject)
        #   0.25 mg/mL: 0.96 mL/hr (< 2, reject)
        #   0.1 mg/mL: 2.4 mL/hr (≥ 2, accept)
        # The 25 µg/mL prep was added to cover even smaller patients,
        # but for a 4 kg cat the 0.1 mg/mL prep is the first to pass.
        assert "0.1 mg/mL" in cat_4kg.dobutamine_cri.titration_concentration_label
        # 4 kg × 5 µg/kg/min × 60 / 100 = 12.0 mL/hr at 5 µg/kg/min row
        step_5 = next(s for s in cat_4kg.dobutamine_cri.titration_steps if s.dose_ug_per_kg_per_min == 5.0)
        assert step_5.ml_per_hr == pytest.approx(12.0)
        # Syringe-pump fallback note must NOT be present since the
        # picker found a working preset.
        assert "syringe pump" not in cat_4kg.dobutamine_cri.prep_note.lower()


class TestNorepiMath:
    def test_known_value_dog(self, dog_20kg):
        # 20 kg × 0.1 µg/kg/min × 60 / 16 = 7.5 mL/hr
        step_01 = next(s for s in dog_20kg.norepi_cri.titration_steps if s.dose_ug_per_kg_per_min == 0.1)
        assert step_01.ml_per_hr == pytest.approx(7.5)

    def test_cat_auto_dilutes_to_8_ug_per_ml(self, cat_4kg):
        # 4 kg cat: 16 → 1.5 mL/hr at 0.1 (< 2), 8 → 3.0 mL/hr (≥ 2).
        # Auto-selected dilution is 8 µg/mL.
        assert "8 µg/mL" in cat_4kg.norepi_cri.titration_concentration_label
        # 4 kg × 0.1 µg/kg/min × 60 / 8 = 3.0 mL/hr
        step_01 = next(s for s in cat_4kg.norepi_cri.titration_steps if s.dose_ug_per_kg_per_min == 0.1)
        assert step_01.ml_per_hr == pytest.approx(3.0)


class TestCautionThresholds:
    def test_dopamine_caution_dog_above_10(self, dog_20kg):
        # Dog threshold = 10. Caution fires ABOVE the threshold.
        caution = {s.dose_ug_per_kg_per_min for s in dog_20kg.dopamine_cri.titration_steps if s.is_caution}
        assert 10.0 not in caution
        assert 12.5 in caution

    def test_dopamine_caution_cat_always_on(self, cat_4kg):
        # Cat threshold = 2.0 (matches standalone /dopamine, HCM-risk
        # rationale). Every step of the ladder (5–20 µg/kg/min) sits above
        # 2.0, so every step should fire the caution.
        steps = cat_4kg.dopamine_cri.titration_steps
        assert len(steps) > 0
        assert all(s.is_caution for s in steps)

    def test_dobutamine_caution_species_specific(self, dog_20kg, cat_4kg):
        # Dog threshold = 10, cat threshold = 5. Caution fires ABOVE threshold.
        dog_caution = {s.dose_ug_per_kg_per_min for s in dog_20kg.dobutamine_cri.titration_steps if s.is_caution}
        cat_caution = {s.dose_ug_per_kg_per_min for s in cat_4kg.dobutamine_cri.titration_steps if s.is_caution}
        # Cat sees caution above 5: 7.5, 10, ... — dog only above 10: 12.5, ...
        assert 5.0 not in cat_caution
        assert 7.5 in cat_caution
        assert 10.0 not in dog_caution
        assert 12.5 in dog_caution
        # 10 is above the cat threshold of 5, so cat should still flag it
        assert 10.0 in cat_caution

    def test_norepi_caution_above_1_for_both(self, dog_20kg, cat_4kg):
        # Threshold = 1.0; caution fires above. 1.0 itself NOT flagged.
        for r in [dog_20kg, cat_4kg]:
            caution = {s.dose_ug_per_kg_per_min for s in r.norepi_cri.titration_steps if s.is_caution}
            assert 1.0 not in caution
            assert 0.5 not in caution
            # Higher doses should be flagged
            higher = {d for d in caution if d > 1.0}
            assert len(higher) > 0


class TestBelowSupportedRangeFallback:
    """When a patient is below the weight range that standard bag
    preparations can support (even the most dilute preset can't keep the
    lowest titration step above 2 mL/hr), the worksheet must NOT show a
    bag recipe, a titration ladder, or a non-zero rate range. Instead it
    directs the user to a syringe pump. The supported floor is roughly
    1.5 kg for dopamine and norepi; dobutamine's 25 µg/mL preset extends
    coverage below that, so the fallback fires at a much smaller weight.
    """

    @pytest.fixture
    def tiny_cat_1kg(self):
        # 1 kg cat: below the supported range for dopamine and norepi.
        # Dopamine: most-dilute 200 µg/mL → 5 µg/kg/min × 1 × 60 / 200 = 1.5 mL/hr (< 2)
        # Norepi: most-dilute 4 µg/mL → 0.1 × 1 × 60 / 4 = 1.5 mL/hr (< 2)
        # Dobutamine: most-dilute 25 µg/mL → 1 × 1 × 60 / 25 = 2.4 mL/hr (≥ 2 — NOT fallback)
        return calculate(1.0, WeightUnit.KG, AnesthSpecies.CAT, "Tiny", "6m")

    def test_dopamine_falls_back_to_syringe_pump_message(self, tiny_cat_1kg):
        cri = tiny_cat_1kg.dopamine_cri
        assert cri.prep_note.startswith("Patient is below the weight range")
        assert "syringe pump" in cri.prep_note.lower()
        # No bag-prep instructions (the recipe verbs are absent).
        assert "remove" not in cri.prep_note.lower()
        assert "draw" not in cri.prep_note.lower()
        # No titration ladder.
        assert cri.titration_steps == ()
        # No concentration label.
        assert cri.titration_concentration_label == ""
        # No rate range.
        assert cri.rate_low_ml_per_hr == 0.0
        assert cri.rate_high_ml_per_hr == 0.0

    def test_norepi_falls_back_to_syringe_pump_message(self, tiny_cat_1kg):
        cri = tiny_cat_1kg.norepi_cri
        assert cri.prep_note.startswith("Patient is below the weight range")
        assert "syringe pump" in cri.prep_note.lower()
        assert cri.titration_steps == ()
        assert cri.titration_concentration_label == ""
        assert cri.rate_low_ml_per_hr == 0.0
        assert cri.rate_high_ml_per_hr == 0.0

    def test_dobutamine_does_not_fall_back_at_1kg(self, tiny_cat_1kg):
        # The 25 µg/mL dobutamine preset extends the supported range
        # below 1 kg, so a 1 kg cat still gets a real bag prep with
        # a real titration ladder.
        cri = tiny_cat_1kg.dobutamine_cri
        assert "syringe pump" not in cri.prep_note.lower()
        assert "remove 0.5 mL" in cri.prep_note
        assert len(cri.titration_steps) > 0
        assert cri.titration_concentration_label != ""
        assert cri.rate_low_ml_per_hr > 0.0

    def test_1_5kg_cat_does_not_fall_back_for_any_drug(self):
        # At the supported floor of 1.5 kg, all three drugs must produce
        # a real bag prep (the auto-dilution presets were chosen for this).
        r = calculate(1.5, WeightUnit.KG, AnesthSpecies.CAT, "Edge", "8m")
        for name, cri in [
            ("Dopamine", r.dopamine_cri),
            ("Dobutamine", r.dobutamine_cri),
            ("Norepi", r.norepi_cri),
        ]:
            assert "syringe pump" not in cri.prep_note.lower(), f"{name} should not fall back at 1.5 kg"
            assert len(cri.titration_steps) > 0, f"{name} ladder should be present at 1.5 kg"
            assert cri.titration_concentration_label != "", f"{name} concentration label should be present at 1.5 kg"


class TestAutoDilutionHelper:
    """Direct tests on the auto-dilution helper itself, independent of
    the worksheet, to catch boundary-condition bugs early."""

    def test_helper_picks_most_concentrated_when_all_qualify(self):
        from app.calculators.anesthesia_sheet import _pick_cri_dilution
        # Large patient: even the most concentrated bag gives ≥ 2 mL/hr.
        conc, below = _pick_cri_dilution(
            weight_kg=40.0,
            threshold_dose_ug_per_kg_per_min=5.0,
            available_concentrations_ug_per_ml=(1600.0, 800.0, 400.0),
        )
        # 40 × 5 × 60 / 1600 = 7.5 mL/hr — passes at the most concentrated.
        assert conc == 1600.0
        assert below is False

    def test_helper_picks_next_most_concentrated_when_first_fails(self):
        from app.calculators.anesthesia_sheet import _pick_cri_dilution
        # Medium-small patient: 1600 fails (0.75 mL/hr), 800 fails (1.5),
        # 400 passes (3.0).
        conc, below = _pick_cri_dilution(
            weight_kg=4.0,
            threshold_dose_ug_per_kg_per_min=5.0,
            available_concentrations_ug_per_ml=(1600.0, 800.0, 400.0),
        )
        assert conc == 400.0
        assert below is False

    def test_helper_falls_back_when_no_dilution_qualifies(self):
        from app.calculators.anesthesia_sheet import _pick_cri_dilution
        # Tiny patient + high threshold dose: even the most dilute prep
        # can't hit 2 mL/hr. Falls back to most dilute with below=True.
        conc, below = _pick_cri_dilution(
            weight_kg=1.0,
            threshold_dose_ug_per_kg_per_min=1.0,
            available_concentrations_ug_per_ml=(1000.0, 500.0, 250.0),
        )
        # 1 × 1 × 60 / 250 = 0.24 mL/hr — far below 2.
        assert conc == 250.0
        assert below is True

    def test_helper_handles_empty_list_defensively(self):
        from app.calculators.anesthesia_sheet import _pick_cri_dilution
        # Defensive path: caller should never do this, but the helper
        # should not crash.
        with pytest.raises((IndexError, ValueError)):
            _pick_cri_dilution(
                weight_kg=10.0,
                threshold_dose_ug_per_kg_per_min=1.0,
                available_concentrations_ug_per_ml=(),
            )


class TestBridgeBoluses:
    """Bridge bolus pressors (phenylephrine, ephedrine) added to the
    intraoperative worksheet. Both use fixed bedside dilutions covering
    the full clinical weight range:
      phenylephrine 100 µg/mL, dose 1–10 µg/kg IV
      ephedrine 1 mg/mL, dose 0.05–0.1 mg/kg IV
    Volume_low and volume_high reflect the patient-scaled bolus volumes
    at the low and high ends of each dose range.
    """

    def test_phenylephrine_volumes_20kg_dog(self, dog_20kg):
        # 20 kg × 1 µg/kg = 20 µg ÷ 100 µg/mL = 0.2 mL low
        # 20 kg × 10 µg/kg = 200 µg ÷ 100 µg/mL = 2.0 mL high
        b = dog_20kg.phenylephrine_bolus
        assert b.volume_low_ml == pytest.approx(0.2)
        assert b.volume_high_ml == pytest.approx(2.0)
        assert "1–10 µg/kg" in b.dose_label
        assert "100 µg/mL" in b.prep_note
        # Pure α₁ note
        assert "α₁" in b.note

    def test_ephedrine_volumes_20kg_dog(self, dog_20kg):
        # 20 kg × 0.05 mg/kg = 1 mg ÷ 1 mg/mL = 1.0 mL low
        # 20 kg × 0.1 mg/kg = 2 mg ÷ 1 mg/mL = 2.0 mL high
        b = dog_20kg.ephedrine_bolus
        assert b.volume_low_ml == pytest.approx(1.0)
        assert b.volume_high_ml == pytest.approx(2.0)
        assert "0.05–0.1 mg/kg" in b.dose_label
        assert "1 mg/mL" in b.prep_note
        # Mixed α/β note
        assert "α/β" in b.note

    def test_volumes_scale_linearly_with_weight(self):
        # Doubling weight should double both bolus volumes for both drugs.
        r10 = calculate(10.0, WeightUnit.KG, AnesthSpecies.DOG, "T", "5y")
        r20 = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "T", "5y")
        assert r20.phenylephrine_bolus.volume_low_ml == pytest.approx(2 * r10.phenylephrine_bolus.volume_low_ml)
        assert r20.phenylephrine_bolus.volume_high_ml == pytest.approx(2 * r10.phenylephrine_bolus.volume_high_ml)
        assert r20.ephedrine_bolus.volume_low_ml == pytest.approx(2 * r10.ephedrine_bolus.volume_low_ml)
        assert r20.ephedrine_bolus.volume_high_ml == pytest.approx(2 * r10.ephedrine_bolus.volume_high_ml)

    def test_small_patient_volumes_are_reasonable(self):
        # 1.5 kg cat: phenyl low at 1 µg/kg gives 0.015 mL (below practical
        # TB-syringe accuracy, but the high end at 10 µg/kg gives 0.15 mL
        # which is drawable). Ephedrine low at 0.05 mg/kg gives 0.075 mL.
        # This is expected — the bolus row shows the clinician the volume
        # range, and they pick a dose within the range that gives a
        # drawable volume. The math just needs to be correct.
        r = calculate(1.5, WeightUnit.KG, AnesthSpecies.CAT, "Tiny", "8y")
        assert r.phenylephrine_bolus.volume_low_ml == pytest.approx(0.015)
        assert r.phenylephrine_bolus.volume_high_ml == pytest.approx(0.15)
        assert r.ephedrine_bolus.volume_low_ml == pytest.approx(0.075)
        assert r.ephedrine_bolus.volume_high_ml == pytest.approx(0.15)

    def test_bridge_to_cri_guidance_in_notes(self, dog_20kg):
        # Both drug notes should reference the bridge-to-CRI transition
        # rule (matches the article and the worksheet section heading).
        assert "CRI" in dog_20kg.phenylephrine_bolus.note
        assert "CRI" in dog_20kg.ephedrine_bolus.note
        assert "repeat" in dog_20kg.phenylephrine_bolus.note.lower()
        assert "repeat" in dog_20kg.ephedrine_bolus.note.lower()
