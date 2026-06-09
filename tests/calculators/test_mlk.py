"""
Tests for the MLK (Morphine-Lidocaine-Ketamine) infusion calculator.

The MLK calculator is a reverse-direction bag builder: the user picks
per-drug doses, pump rate, and bag size; the calculator returns how much
of each drug to add. Source: Lukasik 2015 (WSAVA Proceedings).

Test fixture (mid-range Lukasik doses, dedicated CRI rate):
    20 kg dog, 1 mL/kg/hr pump rate, 500 mL bag.
    Morphine  0.2 mg/kg/hr at 5  mg/mL stock → 100 mg → 20 mL
    Lidocaine 1.5 mg/kg/hr at 20 mg/mL stock → 750 mg → 37.5 mL
    Ketamine  0.3 mg/kg/hr at 100 mg/mL stock → 150 mg → 1.5 mL
    Total drug volume: 59 mL
    Bag duration: 25 hr at 20 mL/hr
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.mlk import (
    DEFAULT_BAG_VOLUME_ML,
    DEFAULT_DOSE_KETAMINE,
    DEFAULT_DOSE_LIDOCAINE,
    DEFAULT_DOSE_MORPHINE,
    DEFAULT_PUMP_RATE_ML_PER_KG_PER_HR,
    MlkInputs,
    MlkSpecies,
    compute_mlk,
    compute_mlk_waste,
)


def _default_inputs(weight_kg: float = 20.0) -> MlkInputs:
    """Inputs using the calculator's published-mid-range defaults."""
    return MlkInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=MlkSpecies.DOG,
    )


class TestSpeciesEnumDogOnly:
    def test_only_dog_in_enum(self):
        members = {m.value for m in MlkSpecies}
        assert "dog" in members
        assert "cat" not in members


class TestDefaults:
    """Defaults match the Lukasik published mid-range protocol."""

    def test_default_pump_rate(self):
        assert DEFAULT_PUMP_RATE_ML_PER_KG_PER_HR == 1.0

    def test_default_bag_size(self):
        assert DEFAULT_BAG_VOLUME_ML == 500.0

    def test_default_morphine_dose(self):
        assert DEFAULT_DOSE_MORPHINE == 0.2

    def test_default_lidocaine_dose(self):
        assert DEFAULT_DOSE_LIDOCAINE == 1.5

    def test_default_ketamine_dose(self):
        assert DEFAULT_DOSE_KETAMINE == 0.3


class TestPumpRateAndDuration:
    """Pump rate and bag duration are the first calculation step."""

    def test_pump_rate_20kg_1mlkghr(self):
        result = compute_mlk(_default_inputs(20.0))
        # 20 kg × 1 mL/kg/hr = 20 mL/hr
        assert result.pump_rate_ml_per_hr == pytest.approx(20.0)

    def test_bag_duration_25hr(self):
        result = compute_mlk(_default_inputs(20.0))
        # 500 mL / 20 mL/hr = 25 hr
        assert result.bag_duration_hr == pytest.approx(25.0)

    def test_pump_rate_scales_with_rate_per_kg(self):
        # Same patient, 2 mL/kg/hr instead of 1
        inputs = MlkInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            pump_rate_ml_per_kg_per_hr=2.0,
        )
        result = compute_mlk(inputs)
        assert result.pump_rate_ml_per_hr == pytest.approx(40.0)
        assert result.bag_duration_hr == pytest.approx(12.5)


class TestMidRangeRecipe:
    """At default mid-range doses, the recipe should reproduce exactly."""

    def test_morphine_100mg_20ml(self):
        result = compute_mlk(_default_inputs(20.0))
        morphine = next(c for c in result.components if c.name == "Morphine")
        # 0.2 mg/kg/hr × 20 kg × 25 hr = 100 mg
        assert morphine.total_mg_in_bag == pytest.approx(100.0)
        # 100 mg / 5 mg/mL = 20 mL
        assert morphine.volume_ml_to_add == pytest.approx(20.0)

    def test_lidocaine_750mg_37_5ml(self):
        result = compute_mlk(_default_inputs(20.0))
        lido = next(c for c in result.components if c.name == "Lidocaine")
        # 1.5 mg/kg/hr × 20 kg × 25 hr = 750 mg
        assert lido.total_mg_in_bag == pytest.approx(750.0)
        # 750 mg / 20 mg/mL = 37.5 mL
        assert lido.volume_ml_to_add == pytest.approx(37.5)

    def test_ketamine_150mg_1_5ml(self):
        result = compute_mlk(_default_inputs(20.0))
        ket = next(c for c in result.components if c.name == "Ketamine")
        # 0.3 mg/kg/hr × 20 kg × 25 hr = 150 mg
        assert ket.total_mg_in_bag == pytest.approx(150.0)
        # 150 mg / 100 mg/mL = 1.5 mL
        assert ket.volume_ml_to_add == pytest.approx(1.5)

    def test_total_drug_volume_59ml(self):
        result = compute_mlk(_default_inputs(20.0))
        # 20 + 37.5 + 1.5 = 59 mL
        assert result.total_drug_volume_ml == pytest.approx(59.0)

    def test_saline_to_remove_equals_drug_volume(self):
        result = compute_mlk(_default_inputs(20.0))
        assert result.saline_to_remove_ml == pytest.approx(result.total_drug_volume_ml)


class TestDoseRangeWarnings:
    """Doses outside Lukasik's published ranges should produce warnings."""

    def test_morphine_above_range_warns(self):
        inputs = MlkInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            morphine_dose_mg_per_kg_per_hr=0.6,  # above 0.4 max
        )
        result = compute_mlk(inputs)
        assert any("Morphine" in w for w in result.warnings)

    def test_lidocaine_below_range_warns(self):
        inputs = MlkInputs(
            weight_value=20.0,
            weight_unit=WeightUnit.KG,
            lidocaine_dose_mg_per_kg_per_hr=0.5,  # below 1.0 min
        )
        result = compute_mlk(inputs)
        assert any("Lidocaine" in w for w in result.warnings)

    def test_in_range_no_warning(self):
        result = compute_mlk(_default_inputs(20.0))
        # Default mid-range doses are all in-range
        in_range_warnings = [
            w for w in result.warnings if "outside the published range" in w
        ]
        assert len(in_range_warnings) == 0


class TestInvalidInputs:
    def test_zero_weight_invalid(self):
        result = compute_mlk(
            MlkInputs(weight_value=0, weight_unit=WeightUnit.KG)
        )
        assert not result.valid

    def test_negative_pump_rate_invalid(self):
        result = compute_mlk(
            MlkInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                pump_rate_ml_per_kg_per_hr=-1.0,
            )
        )
        assert not result.valid


class TestSourceAttribution:
    def test_cites_lukasik(self):
        result = compute_mlk(_default_inputs(20.0))
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Lukasik" in cite_text

    def test_cites_muir_foundational_study(self):
        result = compute_mlk(_default_inputs(20.0))
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Muir" in cite_text


class TestControlledDrugFlags:
    """Morphine (C-II) and ketamine (C-III) are controlled; lidocaine is not."""

    def test_morphine_is_c2(self):
        result = compute_mlk(_default_inputs(20.0))
        morphine = next(c for c in result.components if c.name == "Morphine")
        assert morphine.controlled is True
        assert morphine.schedule == "C-II"

    def test_ketamine_is_c3(self):
        result = compute_mlk(_default_inputs(20.0))
        ket = next(c for c in result.components if c.name == "Ketamine")
        assert ket.controlled is True
        assert ket.schedule == "C-III"

    def test_lidocaine_not_controlled(self):
        result = compute_mlk(_default_inputs(20.0))
        lido = next(c for c in result.components if c.name == "Lidocaine")
        assert lido.controlled is False
        assert lido.schedule is None


class TestWasteCalculation:
    """Per-drug waste = total mg in bag × (volume wasted / bag volume).

    Default-mid-range bag (20 kg, 1 mL/kg/hr, 500 mL): morphine 100 mg, lidocaine
    750 mg, ketamine 150 mg in the 500 mL bag.
    """

    def test_waste_300ml_given(self):
        # 300 mL given of 500 mL bag → 200 mL wasted = 40% of each drug
        bag = compute_mlk(_default_inputs(20.0))
        waste = compute_mlk_waste(bag, 300.0)
        assert waste.valid
        assert waste.volume_wasted_ml == pytest.approx(200.0)
        morphine = next(c for c in waste.components if c.name == "Morphine")
        lido = next(c for c in waste.components if c.name == "Lidocaine")
        ket = next(c for c in waste.components if c.name == "Ketamine")
        # 40 % of 100 / 750 / 150 mg
        assert morphine.mg_wasted == pytest.approx(40.0)
        assert lido.mg_wasted == pytest.approx(300.0)
        assert ket.mg_wasted == pytest.approx(60.0)
        # given fractions sum correctly with wasted
        assert morphine.mg_given == pytest.approx(60.0)

    def test_full_bag_given_zero_waste(self):
        bag = compute_mlk(_default_inputs(20.0))
        waste = compute_mlk_waste(bag, 500.0)
        assert waste.valid
        assert all(c.mg_wasted == pytest.approx(0.0) for c in waste.components)

    def test_nothing_given_full_waste(self):
        bag = compute_mlk(_default_inputs(20.0))
        waste = compute_mlk_waste(bag, 0.0)
        assert waste.valid
        morphine = next(c for c in waste.components if c.name == "Morphine")
        assert morphine.mg_wasted == pytest.approx(100.0)
        assert morphine.mg_given == pytest.approx(0.0)

    def test_volume_over_bag_invalid(self):
        bag = compute_mlk(_default_inputs(20.0))
        waste = compute_mlk_waste(bag, 600.0)
        assert not waste.valid

    def test_negative_volume_invalid(self):
        bag = compute_mlk(_default_inputs(20.0))
        waste = compute_mlk_waste(bag, -10.0)
        assert not waste.valid

    def test_invalid_bag_propagates(self):
        # An invalid bag (zero weight) can't produce a waste result
        bad_bag = compute_mlk(MlkInputs(weight_value=0, weight_unit=WeightUnit.KG))
        waste = compute_mlk_waste(bad_bag, 100.0)
        assert not waste.valid

    def test_waste_carries_controlled_flags(self):
        bag = compute_mlk(_default_inputs(20.0))
        waste = compute_mlk_waste(bag, 250.0)
        morphine = next(c for c in waste.components if c.name == "Morphine")
        lido = next(c for c in waste.components if c.name == "Lidocaine")
        assert morphine.controlled is True
        assert morphine.schedule == "C-II"
        assert lido.controlled is False

    def test_stock_equivalent_volumes(self):
        # 300 mL given of 500 mL bag: morphine 40 mg wasted at 5 mg/mL stock
        # = 8 mL stock-equivalent; 60 mg given = 12 mL stock-equivalent.
        bag = compute_mlk(_default_inputs(20.0))
        waste = compute_mlk_waste(bag, 300.0)
        morphine = next(c for c in waste.components if c.name == "Morphine")
        assert morphine.stock_mg_per_ml == pytest.approx(5.0)
        assert morphine.stock_ml_wasted == pytest.approx(8.0)
        assert morphine.stock_ml_given == pytest.approx(12.0)
        # Ketamine: 60 mg wasted at 100 mg/mL = 0.6 mL stock-equivalent
        ket = next(c for c in waste.components if c.name == "Ketamine")
        assert ket.stock_ml_wasted == pytest.approx(0.6)
