"""
Tests for insulin + dextrose (hyperK shifting) calculator.

Source: Cooper ES. Urethral Obstruction. In Silverstein & Hopper 3rd ed Ch. 122.
DiBartola Ch. 5.

Regular insulin 0.25–0.5 U/kg IV with concurrent dextrose 1–2 g per unit
insulin. Defaults: 0.25 U/kg (safer) + 2 g/U dextrose ratio.

D50 stock = 0.5 g/mL. Diluted 1:1 with saline → D25 for bolus.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.insulin_dextrose import (
    INSULIN_DOSE_MAX_U_PER_KG,
    INSULIN_DOSE_MIN_U_PER_KG,
    InsulinDextroseInputs,
    InsulinDextroseSpecies,
    compute_insulin_dextrose,
)


def _inputs(
    *,
    weight_kg: float = 5.0,
    species: InsulinDextroseSpecies = InsulinDextroseSpecies.CAT,
    insulin_dose: float = 0.25,
    dextrose_ratio: float = 2.0,
) -> InsulinDextroseInputs:
    return InsulinDextroseInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        insulin_dose_u_per_kg=insulin_dose,
        dextrose_g_per_u=dextrose_ratio,
    )


class TestInsulinMath:
    def test_5kg_cat_default(self):
        """5 kg × 0.25 U/kg = 1.25 U insulin; U-100 = 0.0125 mL."""
        result = compute_insulin_dextrose(_inputs(weight_kg=5))
        assert result.total_insulin_u == pytest.approx(1.25)
        assert result.insulin_volume_u100_ml == pytest.approx(0.0125, abs=0.001)

    def test_18kg_addisonian_dog_max(self):
        """18 kg × 0.5 U/kg = 9 U insulin."""
        result = compute_insulin_dextrose(
            _inputs(weight_kg=18, species=InsulinDextroseSpecies.DOG, insulin_dose=0.5)
        )
        assert result.total_insulin_u == pytest.approx(9.0)
        assert result.insulin_volume_u100_ml == pytest.approx(0.09, abs=0.001)


class TestDextroseMath:
    def test_default_ratio_2g_per_u(self):
        """5 kg × 0.25 U/kg = 1.25 U × 2 g/U = 2.5 g dextrose; D50 = 5 mL."""
        result = compute_insulin_dextrose(_inputs(weight_kg=5))
        assert result.dextrose_total_g == pytest.approx(2.5)
        assert result.d50_volume_ml == pytest.approx(5.0)

    def test_lower_ratio_halves_dextrose(self):
        r2 = compute_insulin_dextrose(_inputs(dextrose_ratio=2.0))
        r1 = compute_insulin_dextrose(_inputs(dextrose_ratio=1.0))
        assert r1.dextrose_total_g == pytest.approx(r2.dextrose_total_g / 2)

    def test_d25_dilution_volume(self):
        """d25_dilution_volume_ml is the SALINE volume to add (1:1 dilution).
        For a 1:1 dilution, the saline volume = the D50 volume.
        """
        result = compute_insulin_dextrose(_inputs(weight_kg=5))
        assert result.d25_dilution_volume_ml == pytest.approx(result.d50_volume_ml)


class TestInsulinDoseClamping:
    def test_below_minimum(self):
        result = compute_insulin_dextrose(_inputs(insulin_dose=0.1))
        assert result.insulin_dose_u_per_kg == INSULIN_DOSE_MIN_U_PER_KG
        assert any("range" in w.lower() or "minimum" in w.lower() for w in result.warnings)

    def test_above_maximum(self):
        result = compute_insulin_dextrose(_inputs(insulin_dose=1.0))
        assert result.insulin_dose_u_per_kg == INSULIN_DOSE_MAX_U_PER_KG
        assert any("range" in w.lower() or "maximum" in w.lower() for w in result.warnings)


class TestDextroseRatioClamping:
    def test_below_minimum_clamps(self):
        result = compute_insulin_dextrose(_inputs(dextrose_ratio=0.5))
        assert result.dextrose_g_per_u >= 1.0

    def test_above_maximum_clamps(self):
        result = compute_insulin_dextrose(_inputs(dextrose_ratio=5.0))
        assert result.dextrose_g_per_u <= 2.0


class TestSpeciesNeutral:
    def test_dog_and_cat_get_same_calc(self):
        dog = compute_insulin_dextrose(_inputs(weight_kg=10, species=InsulinDextroseSpecies.DOG))
        cat = compute_insulin_dextrose(_inputs(weight_kg=10, species=InsulinDextroseSpecies.CAT))
        assert dog.total_insulin_u == cat.total_insulin_u
        assert dog.dextrose_total_g == cat.dextrose_total_g


class TestSourceAttribution:
    def test_includes_citation(self):
        result = compute_insulin_dextrose(_inputs())
        assert len(result.sources) > 0
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Silverstein" in cite_text or "Cooper" in cite_text or "DiBartola" in cite_text
