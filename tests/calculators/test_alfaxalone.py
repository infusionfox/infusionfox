"""
Tests for the alfaxalone calculator.

Source: Plumb's alfaxalone monograph.

Premed × Species combinations:
  Dog unpremedicated: induction 1.5–4.5 mg/kg, CRI 8–9 mg/kg/hr
  Dog premedicated:   induction 1.1–1.7 mg/kg, CRI 6–7 mg/kg/hr
  Cat unpremedicated: induction 2.2–9.7 mg/kg, CRI 10–11 mg/kg/hr
  Cat premedicated:   induction 2.3–3.6 mg/kg, CRI 7–8 mg/kg/hr

Stock: 10 mg/mL (Alfaxan® Multidose). DEA Schedule IV.
NO ANALGESIA — analgesic coverage required.
"""

from __future__ import annotations

import pytest

from app.calculators.alfaxalone import (
    ALFAXALONE_STOCK_MG_PER_ML,
    AlfaxaloneInputs,
    AlfaxaloneMode,
    AlfaxalonePremed,
    AlfaxaloneSpecies,
    calculate,
)
from app.calculators.engine import WeightUnit


def _inputs(
    *,
    weight_kg: float = 20.0,
    species: AlfaxaloneSpecies = AlfaxaloneSpecies.DOG,
    premedicated: AlfaxalonePremed = AlfaxalonePremed.PREMEDICATED,
    mode: AlfaxaloneMode = AlfaxaloneMode.INDUCTION,
    cri_rate: float | None = None,
) -> AlfaxaloneInputs:
    return AlfaxaloneInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        premedicated=premedicated,
        mode=mode,
        cri_rate_mg_per_kg_per_hr=cri_rate,
    )


class TestSpeciesPremedRanges:
    def test_dog_unpremed_induction(self):
        result = calculate(_inputs(species=AlfaxaloneSpecies.DOG, premedicated=AlfaxalonePremed.NONE))
        assert result.induction_low_mg_per_kg == 1.5
        assert result.induction_high_mg_per_kg == 4.5

    def test_dog_premed_induction(self):
        result = calculate(_inputs(species=AlfaxaloneSpecies.DOG, premedicated=AlfaxalonePremed.PREMEDICATED))
        assert result.induction_low_mg_per_kg == 1.1
        assert result.induction_high_mg_per_kg == 1.7

    def test_cat_unpremed_induction(self):
        result = calculate(_inputs(species=AlfaxaloneSpecies.CAT, premedicated=AlfaxalonePremed.NONE))
        assert result.induction_low_mg_per_kg == 2.2
        assert result.induction_high_mg_per_kg == 9.7

    def test_cat_premed_induction(self):
        result = calculate(_inputs(species=AlfaxaloneSpecies.CAT, premedicated=AlfaxalonePremed.PREMEDICATED))
        assert result.induction_low_mg_per_kg == 2.3
        assert result.induction_high_mg_per_kg == 3.6


class TestCRIRanges:
    @pytest.mark.parametrize(
        "species,premed,low,high",
        [
            (AlfaxaloneSpecies.DOG, AlfaxalonePremed.NONE, 8.0, 9.0),
            (AlfaxaloneSpecies.DOG, AlfaxalonePremed.PREMEDICATED, 6.0, 7.0),
            (AlfaxaloneSpecies.CAT, AlfaxalonePremed.NONE, 10.0, 11.0),
            (AlfaxaloneSpecies.CAT, AlfaxalonePremed.PREMEDICATED, 7.0, 8.0),
        ],
    )
    def test_cri_range(self, species, premed, low, high):
        result = calculate(_inputs(species=species, premedicated=premed))
        assert result.cri_range_low_mg_per_kg_per_hr == low
        assert result.cri_range_high_mg_per_kg_per_hr == high


class TestVolumes:
    def test_dog_premed_induction_low(self):
        """20 kg × 1.1 mg/kg = 22 mg / 10 mg/mL = 2.2 mL."""
        result = calculate(_inputs(weight_kg=20))
        assert result.induction_low_mg == pytest.approx(22.0)
        assert result.induction_low_ml == pytest.approx(2.2)


class TestCRIRateDefaults:
    def test_no_rate_defaults_to_low(self):
        """If user doesn't specify a rate, default to the low end of range."""
        result = calculate(
            _inputs(species=AlfaxaloneSpecies.DOG, premedicated=AlfaxalonePremed.PREMEDICATED, cri_rate=None)
        )
        # Dog premed range is 6–7; default should be 6
        assert result.cri_rate_mg_per_kg_per_hr == 6.0


class TestRangeViolation:
    def test_above_range_warns(self):
        result = calculate(
            _inputs(species=AlfaxaloneSpecies.DOG, premedicated=AlfaxalonePremed.PREMEDICATED, cri_rate=15.0)
        )
        assert any("range" in w.lower() or "outside" in w.lower() for w in result.warnings)


class TestStockVial:
    def test_stock_10mg_ml(self):
        assert ALFAXALONE_STOCK_MG_PER_ML == 10.0


class TestNoAnalgesiaWarning:
    def test_warns_about_lack_of_analgesia(self):
        result = calculate(_inputs())
        all_text = " ".join(result.warnings + result.notes).lower()
        assert "analgesia" in all_text or "analgesic" in all_text


class TestSourceAttribution:
    def test_includes_plumbs(self):
        result = calculate(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Plumb" in cite_text
