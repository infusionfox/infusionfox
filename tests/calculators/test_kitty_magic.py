"""
Tests for the Kitty Magic (DKT — Dexmedetomidine-Ketamine-Opioid) calculator.

Source: Plumb's lookup table for cat sedation/anesthesia.

Cats only (table covers 2–8 kg).
Equal volumes IM of all three drugs.
Atipamezole reversal at equal volume to dexmedetomidine.

Levels: MILD, MODERATE, PROFOUND.
Opioids: BUTORPHANOL or BUPRENORPHINE.
"""

from __future__ import annotations

import pytest

from app.calculators.kitty_magic import (
    KittyMagicInputs,
    KittyMagicLevel,
    KittyMagicOpioid,
    calculate,
)


def _inputs(
    *,
    weight_kg: float = 5.0,
    opioid: KittyMagicOpioid = KittyMagicOpioid.BUTORPHANOL,
    level: KittyMagicLevel = KittyMagicLevel.MODERATE,
) -> KittyMagicInputs:
    return KittyMagicInputs(weight_kg=weight_kg, opioid=opioid, level=level)


class TestSpeciesScope:
    """Cats only — no species enum needed; the calculator is implicitly cats."""

    def test_levels_supported(self):
        members = {m.value for m in KittyMagicLevel}
        assert "mild" in members
        assert "moderate" in members
        assert "profound" in members

    def test_both_opioids(self):
        members = {m.value for m in KittyMagicOpioid}
        assert "butorphanol" in members
        assert "buprenorphine" in members


class TestTableLookup:
    """Each weight band returns the published volume per Plumb's."""

    @pytest.mark.parametrize(
        "weight_kg,level,expected_low,expected_high",
        [
            # 2–3 kg band
            (2.5, KittyMagicLevel.MILD, 0.025, 0.025),
            (2.5, KittyMagicLevel.MODERATE, 0.05, 0.05),
            (2.5, KittyMagicLevel.PROFOUND, 0.10, 0.15),
            # 4–6 kg band
            (5.0, KittyMagicLevel.MILD, 0.10, 0.10),
            (5.0, KittyMagicLevel.MODERATE, 0.20, 0.20),
            (5.0, KittyMagicLevel.PROFOUND, 0.30, 0.35),
            # 7–8 kg band
            (7.5, KittyMagicLevel.MILD, 0.30, 0.30),
            (7.5, KittyMagicLevel.MODERATE, 0.40, 0.40),
            (7.5, KittyMagicLevel.PROFOUND, 0.50, 0.55),
        ],
    )
    def test_volume_lookup(self, weight_kg, level, expected_low, expected_high):
        result = calculate(_inputs(weight_kg=weight_kg, level=level))
        assert result.in_table is True
        assert result.vol_low_ml == pytest.approx(expected_low)
        assert result.vol_high_ml == pytest.approx(expected_high)


class TestOutOfTable:
    def test_below_2kg_not_in_table(self):
        result = calculate(_inputs(weight_kg=1.0))
        assert result.in_table is False

    def test_above_8kg_not_in_table(self):
        result = calculate(_inputs(weight_kg=10.0))
        assert result.in_table is False


class TestEqualVolumes:
    """All three drugs are drawn at equal volumes per the protocol."""

    def test_three_drugs_returned(self):
        result = calculate(_inputs(weight_kg=5.0))
        assert len(result.drugs) == 3

    def test_total_volume_three_components(self):
        """total_vol = 3 × per-drug volume."""
        result = calculate(_inputs(weight_kg=5.0, level=KittyMagicLevel.MODERATE))
        # MODERATE 4-6 kg = 0.20 mL each → total 0.60
        assert result.total_vol_low_ml == pytest.approx(0.60)
        assert result.total_vol_high_ml == pytest.approx(0.60)


class TestAtipamezoleReversal:
    """Atipamezole = same volume as dex (one of the three drug volumes)."""

    def test_reversal_volume_matches_dex_volume(self):
        result = calculate(_inputs(weight_kg=5.0))
        assert result.atipamezole_vol_low_ml == pytest.approx(result.vol_low_ml)
        assert result.atipamezole_vol_high_ml == pytest.approx(result.vol_high_ml)


class TestOpioidSelection:
    """Different opioids should yield different drug entries but same volumes (since equal volumes)."""

    def test_butorphanol_and_buprenorphine_volumes_match(self):
        bu = calculate(_inputs(opioid=KittyMagicOpioid.BUTORPHANOL))
        bn = calculate(_inputs(opioid=KittyMagicOpioid.BUPRENORPHINE))
        assert bu.vol_low_ml == bn.vol_low_ml
        assert bu.vol_high_ml == bn.vol_high_ml


class TestSourceAttribution:
    def test_includes_plumbs(self):
        result = calculate(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "Plumb" in cite_text
