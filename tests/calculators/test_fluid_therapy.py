"""
Tests for the fluid therapy (general) calculator.

Source: Hoehne SN. Diabetic Ketoacidosis. In Silverstein & Hopper 3rd ed
Ch. 73, Box 73.1. Dehydration bands per DiBartola.

Combiner for four components:
  - Shock bolus (if in_shock): increments to species ceiling (90 dog / 60 cat)
  - Rehydration deficit: weight × % × 10 mL formula, replaced over window
  - Maintenance: 2–4 mL/kg/hr (default 3)
  - Ongoing losses: free input

Output: Phase 1 (active rehydration) = rehydration + maintenance + ongoing
        Phase 2 (post-rehydration) = maintenance + ongoing
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.fluid_therapy import (
    FluidTherapyInputs,
    FluidTherapySpecies,
    compute_fluid_therapy,
)


def _inputs(
    *,
    weight_kg: float = 20.0,
    species: FluidTherapySpecies = FluidTherapySpecies.DOG,
    in_shock: bool = False,
    band: str = "moderate",
    window_hr: int = 12,
    maintenance_mlpkg_hr: float = 3.0,
    ongoing_ml_per_hr: float = 0.0,
) -> FluidTherapyInputs:
    return FluidTherapyInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        species=species,
        in_shock=in_shock,
        dehydration_band_key=band,
        rehydration_window_hr=window_hr,
        maintenance_mlpkg_hr=maintenance_mlpkg_hr,
        ongoing_losses_ml_per_hr=ongoing_ml_per_hr,
    )


class TestRehydrationDeficit:
    """Deficit (mL) = weight (kg) × % × 10."""

    def test_20kg_dog_7pct(self):
        """20 kg × 7% × 10 = 1400 mL."""
        result = compute_fluid_therapy(_inputs(weight_kg=20, band="moderate"))
        assert result.dehydration_percent == 7.0
        assert result.deficit_ml == pytest.approx(1400.0)

    def test_5kg_cat_5_5pct(self):
        """5 kg × 5.5% × 10 = 275 mL."""
        result = compute_fluid_therapy(_inputs(weight_kg=5, species=FluidTherapySpecies.CAT, band="mild"))
        assert result.dehydration_percent == 5.5
        assert result.deficit_ml == pytest.approx(275.0)


class TestRehydrationRate:
    def test_12hr_window(self):
        """1400 mL over 12 hr = 116.67 mL/hr."""
        result = compute_fluid_therapy(_inputs(weight_kg=20, band="moderate", window_hr=12))
        assert result.rehydration_rate_ml_per_hr == pytest.approx(1400 / 12, rel=1e-2)

    def test_24hr_window_halves_rate(self):
        r12 = compute_fluid_therapy(_inputs(window_hr=12))
        r24 = compute_fluid_therapy(_inputs(window_hr=24))
        assert r24.rehydration_rate_ml_per_hr == pytest.approx(r12.rehydration_rate_ml_per_hr / 2, rel=1e-2)

    def test_4hr_window_triples_rate(self):
        r12 = compute_fluid_therapy(_inputs(window_hr=12))
        r4 = compute_fluid_therapy(_inputs(window_hr=4))
        assert r4.rehydration_rate_ml_per_hr == pytest.approx(r12.rehydration_rate_ml_per_hr * 3, rel=1e-2)


class TestMaintenance:
    def test_default_3mlpkg(self):
        """20 kg × 3 mL/kg/hr = 60 mL/hr."""
        result = compute_fluid_therapy(_inputs(weight_kg=20, maintenance_mlpkg_hr=3.0))
        assert result.maintenance_rate_ml_per_hr == pytest.approx(60.0)

    def test_low_maintenance(self):
        result = compute_fluid_therapy(_inputs(weight_kg=20, maintenance_mlpkg_hr=2.0))
        assert result.maintenance_rate_ml_per_hr == pytest.approx(40.0)

    def test_high_maintenance(self):
        result = compute_fluid_therapy(_inputs(weight_kg=20, maintenance_mlpkg_hr=4.0))
        assert result.maintenance_rate_ml_per_hr == pytest.approx(80.0)


class TestPhaseRates:
    """Phase 1 = rehydration + maintenance + ongoing.
    Phase 2 = maintenance + ongoing.
    """

    def test_phase_1_includes_all_three(self):
        result = compute_fluid_therapy(
            _inputs(
                weight_kg=20, band="moderate", window_hr=12, maintenance_mlpkg_hr=3.0, ongoing_ml_per_hr=10
            )
        )
        # 1400/12 + 60 + 10 = 116.67 + 70 ≈ 186.67
        expected = 1400 / 12 + 60 + 10
        assert result.active_phase_rate_ml_per_hr == pytest.approx(expected, rel=1e-2)

    def test_phase_2_excludes_rehydration(self):
        result = compute_fluid_therapy(
            _inputs(
                weight_kg=20, band="moderate", window_hr=12, maintenance_mlpkg_hr=3.0, ongoing_ml_per_hr=10
            )
        )
        assert result.post_rehydration_rate_ml_per_hr == pytest.approx(60 + 10, rel=1e-2)

    def test_zero_ongoing(self):
        result = compute_fluid_therapy(_inputs(ongoing_ml_per_hr=0))
        # Phase 2 should equal maintenance only
        assert result.post_rehydration_rate_ml_per_hr == pytest.approx(
            result.maintenance_rate_ml_per_hr, rel=1e-2
        )


class TestShockBolus:
    """If in_shock, the calculator surfaces shock bolus increments and ceiling."""

    def test_dog_shock_ceiling_90mlpkg(self):
        """20 kg dog × 90 mL/kg = 1800 mL ceiling."""
        result = compute_fluid_therapy(_inputs(weight_kg=20, species=FluidTherapySpecies.DOG, in_shock=True))
        assert result.in_shock is True
        assert result.shock_bolus_max_ml == pytest.approx(1800.0)

    def test_cat_shock_ceiling_60mlpkg(self):
        """5 kg cat × 60 mL/kg = 300 mL ceiling."""
        result = compute_fluid_therapy(_inputs(weight_kg=5, species=FluidTherapySpecies.CAT, in_shock=True))
        assert result.in_shock is True
        assert result.shock_bolus_max_ml == pytest.approx(300.0)

    def test_no_shock_no_bolus(self):
        result = compute_fluid_therapy(_inputs(in_shock=False))
        assert result.in_shock is False
        assert result.shock_bolus_max_ml is None


class TestDehydrationBands:
    """Each band picks the correct percentage."""

    @pytest.mark.parametrize(
        "key,expected_pct",
        [
            ("subclinical", 4.0),
            ("mild", 5.5),
            ("moderate", 7.0),
            ("marked", 9.0),
            ("severe", 11.0),
            ("moribund", 13.0),
        ],
    )
    def test_band_percentage(self, key: str, expected_pct: float):
        result = compute_fluid_therapy(_inputs(band=key))
        assert result.dehydration_percent == expected_pct


class TestSourceAttribution:
    def test_includes_silverstein_or_hoehne(self):
        result = compute_fluid_therapy(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Silverstein" in cite_text or "Hoehne" in cite_text or "DiBartola" in cite_text
