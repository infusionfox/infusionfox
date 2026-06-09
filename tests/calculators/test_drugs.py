"""
Tests for the SINGLE_DRUG_CRI catalog (drugs.py).

Verifies catalog integrity for the 5 config-based drugs:
norepinephrine, epinephrine, dobutamine, dopamine-cri, fentanyl.

Tests catalog API (get_drug, drugs_by_category), config completeness
(every drug has dose ranges for both species, sources, etc.), and
math via compute() against the engine.
"""

from __future__ import annotations

import pytest

from app.calculators.drugs import (
    DEXMEDETOMIDINE,
    DOBUTAMINE,
    DOPAMINE_STANDARD,
    DRUGS,
    EPINEPHRINE,
    FENTANYL,
    MORPHINE,
    NOREPINEPHRINE,
    drugs_by_category,
    get_drug,
)
from app.calculators.engine import (
    CalcInputs,
    CalculatorKind,
    Species,
    WeightUnit,
    compute,
)


class TestCatalogContents:
    def test_five_drugs_in_catalog(self):
        assert len(DRUGS) >= 5

    def test_norepinephrine_present(self):
        assert NOREPINEPHRINE in DRUGS
        assert NOREPINEPHRINE.slug == "norepinephrine"

    def test_epinephrine_present(self):
        assert EPINEPHRINE in DRUGS
        assert EPINEPHRINE.slug == "epinephrine"

    def test_dobutamine_present(self):
        assert DOBUTAMINE in DRUGS
        assert DOBUTAMINE.slug == "dobutamine"

    def test_dopamine_standard_present(self):
        # Engine-driven dopamine CRI for any bag size, alternative to the
        # custom /dopamine page that uses the Plumb's 6×kg method (which
        # only works for 100 mL bags).
        assert DOPAMINE_STANDARD in DRUGS
        assert DOPAMINE_STANDARD.slug == "dopamine-cri"

    def test_fentanyl_present(self):
        assert FENTANYL in DRUGS
        assert FENTANYL.slug == "fentanyl"

    def test_morphine_present(self):
        # Added 2026-06 — standalone CRI calculator alongside the
        # multi-modal builder, which sources the same dose data via
        # analgesia_builder.MORPHINE_SPEC.
        assert MORPHINE in DRUGS
        assert MORPHINE.slug == "morphine"
        assert MORPHINE.category == "Analgesia"

    def test_dexmedetomidine_present(self):
        # Added 2026-06 — standalone CRI calculator. The DMLK
        # protocol uses 0.5 µg/kg/hr as the default analgesic CRI.
        assert DEXMEDETOMIDINE in DRUGS
        assert DEXMEDETOMIDINE.slug == "dexmedetomidine"
        assert DEXMEDETOMIDINE.category == "Analgesia"
        # The analgesia builder's spec must share the same dose data
        # — they should be referencing the same dict, not a copy.
        from app.calculators.analgesia_builder import DEXMEDETOMIDINE_SPEC
        assert DEXMEDETOMIDINE_SPEC.dose_ranges is DEXMEDETOMIDINE.dose_ranges


class TestGetDrug:
    def test_lookup_known_slug(self):
        result = get_drug("norepinephrine")
        assert result is NOREPINEPHRINE

    def test_lookup_unknown_slug(self):
        assert get_drug("not_a_drug") is None

    def test_lookup_all_known(self):
        for drug in DRUGS:
            assert get_drug(drug.slug) is drug


class TestDrugsByCategory:
    def test_returns_dict(self):
        result = drugs_by_category()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_each_drug_in_its_category(self):
        result = drugs_by_category()
        for drug in DRUGS:
            assert drug.category in result
            assert drug in result[drug.category]


class TestConfigCompleteness:
    """Each catalog drug should have dose ranges for dog AND cat, plus sources."""

    @pytest.mark.parametrize("drug", [NOREPINEPHRINE, EPINEPHRINE, DOBUTAMINE, FENTANYL])
    def test_has_dog_range(self, drug):
        assert Species.DOG in drug.dose_ranges
        rng = drug.dose_ranges[Species.DOG]
        assert rng.min < rng.max

    @pytest.mark.parametrize("drug", [NOREPINEPHRINE, EPINEPHRINE, DOBUTAMINE, FENTANYL])
    def test_has_cat_range(self, drug):
        assert Species.CAT in drug.dose_ranges
        rng = drug.dose_ranges[Species.CAT]
        assert rng.min < rng.max

    @pytest.mark.parametrize("drug", [NOREPINEPHRINE, EPINEPHRINE, DOBUTAMINE, FENTANYL])
    def test_has_sources(self, drug):
        assert len(drug.sources) > 0

    @pytest.mark.parametrize("drug", [NOREPINEPHRINE, EPINEPHRINE, DOBUTAMINE, FENTANYL])
    def test_kind_is_single_drug_cri(self, drug):
        assert drug.kind == CalculatorKind.SINGLE_DRUG_CRI

    @pytest.mark.parametrize("drug", [NOREPINEPHRINE, EPINEPHRINE, DOBUTAMINE, FENTANYL])
    def test_has_dose_unit(self, drug):
        assert drug.dose_unit is not None

    @pytest.mark.parametrize("drug", [NOREPINEPHRINE, EPINEPHRINE, DOBUTAMINE, FENTANYL])
    def test_has_stock_concentration(self, drug):
        assert drug.stock_concentration_ug_per_ml > 0


class TestNorepinephrineMath:
    """Spot-check: 20 kg dog × 0.1 µg/kg/min × 60 / 1000 µg/mL = 0.12 mL/hr."""

    def test_20kg_dog_at_default(self):
        inputs = CalcInputs(
            weight_value=20,
            weight_unit=WeightUnit.KG,
            dose=0.1,
            concentration_ug_per_ml=1000,
            species=Species.DOG,
        )
        result = compute(NOREPINEPHRINE, inputs)
        # 20 × 0.1 × 60 / 1000 = 0.12 mL/hr
        assert result.ml_per_hr_precise == pytest.approx(0.12, rel=1e-2)


class TestPersistentWarnings:
    """High-alert drugs should have persistent_warning text."""

    def test_norepinephrine_has_warning(self):
        rng = NOREPINEPHRINE.dose_ranges[Species.DOG]
        assert rng.persistent_warning is not None
        # Should specifically warn about NE/EPI confusion
        text = rng.persistent_warning.lower()
        assert "norep" in text or "epinephrine" in text or "confuse" in text


class TestCautionThresholds:
    """Some drugs have caution thresholds within their valid range."""

    def test_norepinephrine_caution_threshold(self):
        rng = NOREPINEPHRINE.dose_ranges[Species.DOG]
        assert rng.caution_threshold is not None
        assert rng.min < rng.caution_threshold < rng.max
        assert rng.caution_note is not None
