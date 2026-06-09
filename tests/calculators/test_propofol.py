"""
Tests for the propofol calculator.

Source: Plumb's propofol monograph.

Two indications:
  TIVA_MAINTENANCE: dog-only, 0.1–0.5 mg/kg/min IV CRI
  STATUS_EPILEPTICUS: dog and cat, 0.1–0.25 mg/kg/min IV CRI

Cat TIVA is blocked due to prolonged recovery + Heinz body anemia risk.
Stock 10 mg/mL.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.propofol import (
    PropofolIndication,
    PropofolInputs,
    PropofolSpecies,
    compute_propofol,
    get_propofol_dose_range,
)


def _inputs(
    *,
    weight_kg: float = 20.0,
    species: PropofolSpecies = PropofolSpecies.DOG,
    indication: PropofolIndication = PropofolIndication.TIVA_MAINTENANCE,
    dose: float = 0.2,
) -> PropofolInputs:
    return PropofolInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        dose_mg_per_kg_per_min=dose,
        indication=indication,
        species=species,
    )


class TestCatTIVABlocked:
    """Cat + TIVA is intentionally blocked due to Heinz body anemia risk."""

    def test_cat_tiva_warns_and_blocks(self):
        result = compute_propofol(
            _inputs(species=PropofolSpecies.CAT, indication=PropofolIndication.TIVA_MAINTENANCE)
        )
        all_text = " ".join(result.warnings).lower()
        assert "cat" in all_text and ("tiva" in all_text or "support" in all_text)
        # Should explicitly mention Heinz body or prolonged recovery
        assert "heinz" in all_text or "prolonged" in all_text

    def test_cat_status_epilepticus_works(self):
        """Cat status epilepticus IS supported."""
        result = compute_propofol(
            _inputs(species=PropofolSpecies.CAT, indication=PropofolIndication.STATUS_EPILEPTICUS)
        )
        # Should produce a non-zero pump rate
        assert result.pump_rate_ml_per_hr > 0


class TestDoseRanges:
    def test_dog_tiva_range(self):
        rng = get_propofol_dose_range(PropofolIndication.TIVA_MAINTENANCE, PropofolSpecies.DOG)
        assert rng is not None
        assert rng.min_mg_per_kg_per_min == 0.1
        assert rng.max_mg_per_kg_per_min == 0.5

    def test_dog_status_range(self):
        rng = get_propofol_dose_range(PropofolIndication.STATUS_EPILEPTICUS, PropofolSpecies.DOG)
        assert rng is not None
        assert rng.min_mg_per_kg_per_min == 0.1
        assert rng.max_mg_per_kg_per_min == 0.25

    def test_cat_status_range(self):
        rng = get_propofol_dose_range(PropofolIndication.STATUS_EPILEPTICUS, PropofolSpecies.CAT)
        assert rng is not None

    def test_cat_tiva_range_undefined(self):
        rng = get_propofol_dose_range(PropofolIndication.TIVA_MAINTENANCE, PropofolSpecies.CAT)
        # Cat TIVA combo isn't in the range table
        assert rng is None


class TestPumpRateMath:
    def test_20kg_dog_tiva_default(self):
        """20 kg × 0.2 mg/kg/min = 4 mg/min × 60 = 240 mg/hr / 10 mg/mL = 24 mL/hr."""
        result = compute_propofol(_inputs(weight_kg=20, dose=0.2))
        assert result.pump_rate_ml_per_hr == pytest.approx(24.0, rel=1e-2)

    def test_30kg_dog_status_default(self):
        """30 kg × 0.1 = 3 mg/min × 60 = 180 mg/hr / 10 = 18 mL/hr."""
        result = compute_propofol(
            _inputs(weight_kg=30, indication=PropofolIndication.STATUS_EPILEPTICUS, dose=0.1)
        )
        assert result.pump_rate_ml_per_hr == pytest.approx(18.0, rel=1e-2)


class TestStockConcentration:
    def test_stock_10mg_per_ml(self):
        result = compute_propofol(_inputs())
        assert result.stock_mg_per_ml == 10.0


class TestSafetyWarnings:
    def test_includes_no_analgesia_warning(self):
        """TIVA mode should warn about no analgesia from propofol."""
        result = compute_propofol(_inputs(indication=PropofolIndication.TIVA_MAINTENANCE))
        all_text = " ".join(result.warnings).lower()
        assert "analge" in all_text or "multimodal" in all_text


class TestSourceAttribution:
    def test_includes_plumbs(self):
        result = compute_propofol(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Plumb" in cite_text
