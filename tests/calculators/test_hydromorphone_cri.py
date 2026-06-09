"""
Tests for the hydromorphone CRI calculator (post-redesign).

Sources combined per Plumb's hydromorphone monograph:

Dog bolus (intermittent):  0.05–0.2 mg/kg q2–4h
Cat bolus (intermittent):  0.05–0.1 mg/kg q2–6h
Dog loading bolus (CRI):   0.025–0.1 mg/kg IV
Cat loading bolus (CRI):   0.025 mg/kg IV (single)
Dog CRI:                   0.02–0.1 mg/kg/hr (combined analgesia + anesthesia)
Cat CRI:                   0.01–0.05 mg/kg/hr (start low)

Stock: 2 mg/mL standard (default). 1, 4, 10 mg/mL alternatives.
DEA C-II.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.hydromorphone_cri import (
    HYDROMORPHONE_CAT_DEFAULT_DOSE,
    HYDROMORPHONE_CAT_LADDER_DOSES,
    HYDROMORPHONE_CAUTION_THRESHOLD_MG_PER_KG_PER_HR,
    HYDROMORPHONE_DOG_DEFAULT_DOSE,
    HYDROMORPHONE_DOG_LADDER_DOSES,
    HYDROMORPHONE_STOCK_MG_PER_ML,
    HYDROMORPHONE_STOCK_OPTIONS,
    HydromorphoneInputs,
    HydromorphoneSpecies,
    calculate,
)


def _inputs(
    *,
    weight_kg: float = 20.0,
    species: HydromorphoneSpecies = HydromorphoneSpecies.DOG,
    stock_mg_per_ml: float = HYDROMORPHONE_STOCK_MG_PER_ML,
) -> HydromorphoneInputs:
    return HydromorphoneInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        stock_mg_per_ml=stock_mg_per_ml,
    )


class TestSpeciesSupport:
    def test_both_species(self):
        members = {m.value for m in HydromorphoneSpecies}
        assert "dog" in members
        assert "cat" in members


# ----- Loading dose (precedes CRI) -----


class TestLoadingDoseRanges:
    def test_dog_loading_combined_range(self):
        """Dog loading: 0.025–0.1 mg/kg IV (combined analgesia + anesthesia)."""
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        assert r.loading_dose_low_mg_per_kg == pytest.approx(0.025)
        assert r.loading_dose_high_mg_per_kg == pytest.approx(0.1)

    def test_cat_loading_single_dose(self):
        """Cat loading: 0.025 mg/kg IV (single published value)."""
        r = calculate(_inputs(species=HydromorphoneSpecies.CAT))
        assert r.loading_dose_low_mg_per_kg == pytest.approx(0.025)
        assert r.loading_dose_high_mg_per_kg == pytest.approx(0.025)


# ----- Intermittent bolus (alternative to CRI protocol) -----


class TestIntermittentBolusRanges:
    def test_dog_bolus_range(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        assert r.bolus_dose_low_mg_per_kg == pytest.approx(0.05)
        assert r.bolus_dose_high_mg_per_kg == pytest.approx(0.20)
        assert r.bolus_interval_hr == "2–4 hr"

    def test_cat_bolus_range(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.CAT))
        assert r.bolus_dose_low_mg_per_kg == pytest.approx(0.05)
        assert r.bolus_dose_high_mg_per_kg == pytest.approx(0.10)
        assert r.bolus_interval_hr == "2–6 hr"


class TestIntermittentBolusVolumes:
    def test_20kg_dog_low_bolus(self):
        """20 kg × 0.05 mg/kg = 1.0 mg / 2 mg/mL = 0.5 mL."""
        r = calculate(_inputs(weight_kg=20))
        assert r.bolus_low_mg == pytest.approx(1.0)
        assert r.bolus_low_ml == pytest.approx(0.5)

    def test_20kg_dog_high_bolus(self):
        """20 kg × 0.20 mg/kg = 4.0 mg / 2 mg/mL = 2.0 mL."""
        r = calculate(_inputs(weight_kg=20))
        assert r.bolus_high_mg == pytest.approx(4.0)
        assert r.bolus_high_ml == pytest.approx(2.0)


# ----- Species default dose (drives headline + ladder highlight) -----


class TestSpeciesDefaults:
    def test_dog_default_is_pure_analgesia_dose(self):
        """Dog default = 0.03 mg/kg/hr (typical pure analgesia per Plumb's)."""
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        assert r.default_dose_mg_per_kg_per_hr == pytest.approx(0.03)
        assert pytest.approx(0.03) == HYDROMORPHONE_DOG_DEFAULT_DOSE

    def test_cat_default_is_low_end(self):
        """Cat default = 0.01 mg/kg/hr (Plumb's published low end)."""
        r = calculate(_inputs(species=HydromorphoneSpecies.CAT))
        assert r.default_dose_mg_per_kg_per_hr == pytest.approx(0.01)
        assert pytest.approx(0.01) == HYDROMORPHONE_CAT_DEFAULT_DOSE

    def test_dog_default_label(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        assert "analgesia" in r.default_dose_label.lower()

    def test_cat_default_label(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.CAT))
        assert "start-low" in r.default_dose_label.lower() or "start low" in r.default_dose_label.lower()


class TestDefaultPumpRate:
    def test_20kg_dog_at_default(self):
        """20 kg × 0.03 mg/kg/hr / 2 mg/mL = 0.3 mL/hr."""
        r = calculate(_inputs(weight_kg=20, species=HydromorphoneSpecies.DOG))
        assert r.default_pump_rate_ml_per_hr == pytest.approx(0.3, abs=0.001)

    def test_5kg_cat_at_default(self):
        """5 kg × 0.01 mg/kg/hr / 2 mg/mL = 0.025 mL/hr."""
        r = calculate(_inputs(weight_kg=5, species=HydromorphoneSpecies.CAT))
        assert r.default_pump_rate_ml_per_hr == pytest.approx(0.025, abs=0.001)


# ----- Titration ladder -----


class TestTitrationLadderShape:
    def test_dog_ladder_doses(self):
        """Dog ladder: 0.02, 0.03, 0.05, 0.075, 0.10 mg/kg/hr."""
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        doses = tuple(s.dose_mg_per_kg_per_hr for s in r.titration_steps)
        assert doses == HYDROMORPHONE_DOG_LADDER_DOSES
        assert doses == (0.02, 0.03, 0.05, 0.075, 0.10)

    def test_cat_ladder_doses(self):
        """Cat ladder: 0.01, 0.02, 0.03, 0.04, 0.05 mg/kg/hr."""
        r = calculate(_inputs(species=HydromorphoneSpecies.CAT))
        doses = tuple(s.dose_mg_per_kg_per_hr for s in r.titration_steps)
        assert doses == HYDROMORPHONE_CAT_LADDER_DOSES
        assert doses == (0.01, 0.02, 0.03, 0.04, 0.05)

    def test_dog_ladder_includes_analgesia_dose(self):
        """0.03 mg/kg/hr MUST be on the dog ladder; it's the analgesia
        highlight."""
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        doses = [s.dose_mg_per_kg_per_hr for s in r.titration_steps]
        assert pytest.approx(0.03) in doses


class TestTitrationLadderDefault:
    def test_dog_default_row_is_0_03(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        defaults = [s for s in r.titration_steps if s.is_default]
        assert len(defaults) == 1
        assert defaults[0].dose_mg_per_kg_per_hr == pytest.approx(0.03)

    def test_cat_default_row_is_0_01(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.CAT))
        defaults = [s for s in r.titration_steps if s.is_default]
        assert len(defaults) == 1
        assert defaults[0].dose_mg_per_kg_per_hr == pytest.approx(0.01)


class TestTitrationLadderAnnotations:
    def test_dog_0_03_annotated_as_analgesia(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        step = next(s for s in r.titration_steps if s.dose_mg_per_kg_per_hr == pytest.approx(0.03))
        assert step.annotation is not None
        assert "analgesia" in step.annotation.lower()

    def test_dog_high_doses_annotated_as_anesthesia(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        # 0.075 and 0.10 should be annotated as anesthesia infusion
        for dose in (0.075, 0.10):
            step = next(s for s in r.titration_steps if s.dose_mg_per_kg_per_hr == pytest.approx(dose))
            assert step.annotation is not None, f"dog dose {dose} should be annotated"
            assert (
                "anesthesia" in step.annotation.lower()
            ), f"dog dose {dose} annotation should mention anesthesia, got {step.annotation!r}"

    def test_cat_default_annotated_as_start_low(self):
        r = calculate(_inputs(species=HydromorphoneSpecies.CAT))
        step = next(s for s in r.titration_steps if s.is_default)
        assert step.annotation is not None
        assert "low" in step.annotation.lower()


class TestTitrationLadderCaution:
    def test_dog_high_doses_flagged_caution(self):
        """0.075 and 0.10 mg/kg/hr exceed 0.05 threshold."""
        r = calculate(_inputs(species=HydromorphoneSpecies.DOG))
        caution = [s for s in r.titration_steps if s.is_caution]
        cautious_doses = sorted(s.dose_mg_per_kg_per_hr for s in caution)
        assert cautious_doses == [pytest.approx(0.075), pytest.approx(0.10)]

    def test_cat_no_caution_rows(self):
        """Cat ladder max is 0.05, which equals the threshold; no rows
        should be flagged as caution."""
        r = calculate(_inputs(species=HydromorphoneSpecies.CAT))
        caution = [s for s in r.titration_steps if s.is_caution]
        assert caution == []

    def test_caution_threshold_constant(self):
        assert pytest.approx(0.05) == HYDROMORPHONE_CAUTION_THRESHOLD_MG_PER_KG_PER_HR


class TestTitrationLadderMath:
    def test_dog_0_03_at_20kg_2mg_per_ml(self):
        """0.03 mg/kg/hr × 20 kg / 2 mg/mL = 0.3 mL/hr."""
        r = calculate(_inputs(weight_kg=20, species=HydromorphoneSpecies.DOG))
        step = next(s for s in r.titration_steps if s.dose_mg_per_kg_per_hr == pytest.approx(0.03))
        assert step.ml_per_hr == pytest.approx(0.3, abs=0.001)

    def test_dog_0_10_at_20kg_2mg_per_ml(self):
        """0.10 mg/kg/hr × 20 kg / 2 mg/mL = 1.0 mL/hr."""
        r = calculate(_inputs(weight_kg=20, species=HydromorphoneSpecies.DOG))
        step = next(s for s in r.titration_steps if s.dose_mg_per_kg_per_hr == pytest.approx(0.10))
        assert step.ml_per_hr == pytest.approx(1.0, abs=0.001)

    def test_cat_0_05_at_5kg_2mg_per_ml(self):
        """0.05 mg/kg/hr × 5 kg / 2 mg/mL = 0.125 mL/hr."""
        r = calculate(_inputs(weight_kg=5, species=HydromorphoneSpecies.CAT))
        step = next(s for s in r.titration_steps if s.dose_mg_per_kg_per_hr == pytest.approx(0.05))
        assert step.ml_per_hr == pytest.approx(0.125, abs=0.001)


# ----- Stock concentration options -----


class TestStockOptions:
    def test_default_stock_is_2(self):
        assert HYDROMORPHONE_STOCK_MG_PER_ML == 2.0

    def test_stock_options_include_all_four(self):
        values = {opt for opt, _label in HYDROMORPHONE_STOCK_OPTIONS}
        assert values == {1.0, 2.0, 4.0, 10.0}

    def test_stock_options_default_is_first(self):
        """The 2 mg/mL veterinary standard must be the first option."""
        assert HYDROMORPHONE_STOCK_OPTIONS[0][0] == 2.0

    @pytest.mark.parametrize("stock", [1.0, 2.0, 4.0, 10.0])
    def test_ladder_recomputes_at_each_stock(self, stock):
        """20 kg × 0.03 mg/kg/hr / stock should produce the right pump rate
        at every alternative concentration."""
        r = calculate(_inputs(weight_kg=20, stock_mg_per_ml=stock))
        expected = round((0.03 * 20) / stock, 3)
        assert r.default_pump_rate_ml_per_hr == pytest.approx(expected, abs=0.001)


# ----- Source attribution -----


class TestSourceAttribution:
    def test_includes_plumbs(self):
        r = calculate(_inputs())
        cite = " ".join(s.citation for s in r.sources)
        assert "Plumb" in cite

    def test_mentions_combined_ranges(self):
        r = calculate(_inputs())
        cite = " ".join(s.citation for s in r.sources)
        # Source citation should reflect that the analgesia and anesthesia
        # ranges are combined per this redesign
        assert "analgesia" in cite.lower() and "anesthesia" in cite.lower()


class TestSyringePumpCallout:
    """Pin: the rendered result panel must surface the syringe-pump
    delivery mode so a clinician on a fluid pump doesn't see 0.3 mL/hr
    and assume the math is wrong. The math is correct for syringe pump
    delivery from the undiluted stock vial — without this label,
    nothing on the page says so. Covered in both the headline callout
    and the titration ladder hint."""

    def test_headline_mentions_syringe_pump(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        r = client.post(
            "/hydromorphone-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "stock_mg_per_ml": "2",
            },
        )
        assert r.status_code == 200
        assert "Syringe pump" in r.text

    def test_ladder_hint_mentions_syringe_pump(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        r = client.post(
            "/hydromorphone-cri/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "stock_mg_per_ml": "2",
            },
        )
        # The titration-card hint should call out syringe pump too, so
        # the per-step rates aren't second-guessed any more than the
        # headline rate is.
        assert "Syringe pump rate at each dose step" in r.text
