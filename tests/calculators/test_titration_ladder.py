"""
Tests for the fast-titration ladder.

The titration ladder is a per-dose-step pump-rate table designed for a
technician at the pump while the clinician is hands-busy. Math is the same
as the single-target compute(); these tests verify:

1. The ladder is built when a config provides one, and is empty when not.
2. Each step's pump rate matches the same formula compute() uses for that
   single dose, so a tech reading a row gets the same answer they'd get if
   they had typed that exact dose into the calculator.
3. The 'is_current' flag fires for the row matching the just-computed dose.
4. The 'is_caution' flag fires for rows at or above the species-specific
   caution threshold.
5. Non-positive inputs (which short-circuit the main result via valid=False)
   produce an empty ladder, never a ladder of garbage rates.
"""

from __future__ import annotations

import pytest

from app.calculators import (
    CalcInputs,
    Species,
    WeightUnit,
    compute,
    get_drug,
)


def test_norepi_ladder_built_when_configured():
    r = compute(
        get_drug("norepinephrine"),
        CalcInputs(
            weight_value=30,
            weight_unit=WeightUnit.KG,
            dose=0.1,
            concentration_ug_per_ml=16,
            species=Species.DOG,
        ),
    )
    # Norepi ladder starts at 0.1 µg/kg/min (the working clinical anchor),
    # not 0.05 (the published range floor). The published floor is still
    # accepted as an input via dose_ranges but is not shown as a ladder
    # row to avoid implying it as a starting point.
    assert len(r.titration_steps) == 10
    assert r.titration_steps[0].dose == 0.1
    assert r.titration_steps[-1].dose == 2.0


def test_dobutamine_ladder_built_when_configured():
    r = compute(
        get_drug("dobutamine"),
        CalcInputs(
            weight_value=30,
            weight_unit=WeightUnit.KG,
            dose=5.0,
            concentration_ug_per_ml=1000,
            species=Species.DOG,
        ),
    )
    # Dog ladder filters out doses below the species min (2.0 µg/kg/min);
    # cat ladder keeps the 1.0 step. The full configured ladder is
    # (1, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20) — 9 entries — and dogs
    # drop the 1.0 row leaving 8. Cats keep all 9.
    assert len(r.titration_steps) == 8
    assert r.titration_steps[0].dose == 2.5
    assert r.titration_steps[-1].dose == 20.0


def test_dobutamine_ladder_cat_keeps_low_step():
    """Cats have a lower published dose floor (1 µg/kg/min), so the cat
    ladder must keep the 1.0 row that the dog ladder filters out."""
    r = compute(
        get_drug("dobutamine"),
        CalcInputs(
            weight_value=4,
            weight_unit=WeightUnit.KG,
            dose=1.0,
            concentration_ug_per_ml=1000,
            species=Species.CAT,
        ),
    )
    assert r.titration_steps[0].dose == 1.0
    assert len(r.titration_steps) == 9


def test_fentanyl_has_no_ladder():
    """Fentanyl was deliberately excluded from this round of titration tables."""
    r = compute(
        get_drug("fentanyl"),
        CalcInputs(
            weight_value=20,
            weight_unit=WeightUnit.KG,
            dose=10,
            concentration_ug_per_ml=50,
            species=Species.DOG,
        ),
    )
    assert r.titration_steps == ()


class TestLadderMath:
    """Each ladder step's pump rate must match the formula compute() uses."""

    def test_norepi_step_matches_direct_compute(self):
        weight = 30.0
        conc = 16.0
        # Compute once at 0.5 µg/kg/min — read the same dose off the ladder
        direct = compute(
            get_drug("norepinephrine"),
            CalcInputs(
                weight_value=weight,
                weight_unit=WeightUnit.KG,
                dose=0.5,
                concentration_ug_per_ml=conc,
                species=Species.DOG,
            ),
        )
        ladder = direct.titration_steps
        step_05 = next(s for s in ladder if s.dose == 0.5)
        assert step_05.ml_per_hr_pump == pytest.approx(direct.ml_per_hr_pump, abs=1e-9)

    def test_norepi_step_at_known_value(self):
        # 30 kg dog, 0.1 µg/kg/min, 16 µg/mL bag
        # = 30 * 0.1 * 60 / 16 = 11.25 mL/hr
        r = compute(
            get_drug("norepinephrine"),
            CalcInputs(
                weight_value=30,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=16,
                species=Species.DOG,
            ),
        )
        step_01 = next(s for s in r.titration_steps if s.dose == 0.1)
        assert step_01.ml_per_hr_pump == pytest.approx(11.25)

    def test_dobutamine_step_at_known_value(self):
        # 30 kg dog, 5 µg/kg/min, 1000 µg/mL bag
        # = 30 * 5 * 60 / 1000 = 9.0 mL/hr
        r = compute(
            get_drug("dobutamine"),
            CalcInputs(
                weight_value=30,
                weight_unit=WeightUnit.KG,
                dose=5.0,
                concentration_ug_per_ml=1000,
                species=Species.DOG,
            ),
        )
        step_5 = next(s for s in r.titration_steps if s.dose == 5.0)
        assert step_5.ml_per_hr_pump == pytest.approx(9.0)


class TestCurrentFlag:
    def test_current_flag_fires_on_matching_row(self):
        r = compute(
            get_drug("norepinephrine"),
            CalcInputs(
                weight_value=30,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=16,
                species=Species.DOG,
            ),
        )
        current_steps = [s for s in r.titration_steps if s.is_current]
        assert len(current_steps) == 1
        assert current_steps[0].dose == 0.1

    def test_no_current_flag_when_dose_off_ladder(self):
        # 0.07 µg/kg/min isn't on the standard ladder, so no row should match
        r = compute(
            get_drug("norepinephrine"),
            CalcInputs(
                weight_value=30,
                weight_unit=WeightUnit.KG,
                dose=0.07,
                concentration_ug_per_ml=16,
                species=Species.DOG,
            ),
        )
        assert all(not s.is_current for s in r.titration_steps)


class TestCautionFlag:
    def test_caution_fires_above_threshold(self):
        # NE caution = 1.0 µg/kg/min for both species
        r = compute(
            get_drug("norepinephrine"),
            CalcInputs(
                weight_value=30,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=16,
                species=Species.DOG,
            ),
        )
        caution_steps = [s for s in r.titration_steps if s.is_caution]
        # Doses above 1.0 are flagged: 1.5, 2.0. 1.0 itself is NOT.
        assert {s.dose for s in caution_steps} == {1.5, 2.0}

    def test_dobutamine_caution_is_species_specific(self):
        # Dog: caution at 10. Cat: caution at 5.
        dog = compute(
            get_drug("dobutamine"),
            CalcInputs(
                weight_value=30,
                weight_unit=WeightUnit.KG,
                dose=5.0,
                concentration_ug_per_ml=1000,
                species=Species.DOG,
            ),
        )
        cat = compute(
            get_drug("dobutamine"),
            CalcInputs(
                weight_value=4,
                weight_unit=WeightUnit.KG,
                dose=5.0,
                concentration_ug_per_ml=1000,
                species=Species.CAT,
            ),
        )
        dog_caution = {s.dose for s in dog.titration_steps if s.is_caution}
        cat_caution = {s.dose for s in cat.titration_steps if s.is_caution}
        # Dog caution above 10: 12.5, 15, 17.5, 20 (10 itself is NOT flagged)
        assert dog_caution == {12.5, 15.0, 17.5, 20.0}
        # Cat caution above 5: 7.5, 10, 12.5, 15, 17.5, 20 (5 itself is NOT flagged)
        assert cat_caution == {7.5, 10.0, 12.5, 15.0, 17.5, 20.0}


class TestSafetyShortCircuit:
    """When inputs are invalid, no ladder should be built. Otherwise we'd
    leak a table of garbage pump rates next to a 'weight must be > 0' warning."""

    def test_negative_weight_yields_empty_ladder(self):
        r = compute(
            get_drug("norepinephrine"),
            CalcInputs(
                weight_value=-5,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=16,
                species=Species.DOG,
            ),
        )
        assert r.valid is False
        assert r.titration_steps == ()

    def test_zero_concentration_yields_empty_ladder(self):
        r = compute(
            get_drug("norepinephrine"),
            CalcInputs(
                weight_value=30,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=0,
                species=Species.DOG,
            ),
        )
        assert r.valid is False
        assert r.titration_steps == ()
