"""
Tests for the LDDST (low-dose dex suppression test) interpretation calculator.

Source: Behrend EN, Kooistra HS, Nelson R, Reusch CE, Scott-Moncrieff JC.
Diagnosis of spontaneous canine hyperadrenocorticism: 2012 ACVIM Consensus
Statement (Small Animal). J Vet Intern Med 2013;27:1292–1304.

Default 8-hour cut-off: 1.4 µg/dL (≈ 40 nmol/L)

Categories:
  NOT_HAC: 8h ≤ cut-off (suppressed)
  NOT_HAC_INVERSE: 8h ≤ cut-off but 4h > baseline
  SUPPORTS_PDH: 8h > cut-off + at least one suppression criterion met
  DEX_RESISTANT: 8h > cut-off + no suppression criteria met
"""

from __future__ import annotations

import pytest

from app.calculators.lddst import (
    DEFAULT_8H_CUTOFF_UG_DL,
    CortisolUnit,
    LDDSTCategory,
    LDDSTInputs,
    interpret_lddst,
    to_nmol_l,
)


def _inputs(
    *,
    baseline: float = 5.0,
    h4: float = 1.0,
    h8: float = 1.0,
    cutoff: float = DEFAULT_8H_CUTOFF_UG_DL,
    unit: CortisolUnit = CortisolUnit.UG_PER_DL,
) -> LDDSTInputs:
    return LDDSTInputs(
        baseline_cortisol=baseline,
        cortisol_4h=h4,
        cortisol_8h=h8,
        cutoff_8h=cutoff,
        unit=unit,
    )


class TestNotHAC:
    """8-hour cortisol at or below cut-off → not HAC."""

    def test_8h_below_cutoff(self):
        result = interpret_lddst(_inputs(baseline=5.0, h4=1.0, h8=1.0))
        assert result.category == LDDSTCategory.NOT_HAC

    def test_8h_exactly_at_cutoff(self):
        result = interpret_lddst(_inputs(baseline=5.0, h4=1.0, h8=1.4))
        assert result.category == LDDSTCategory.NOT_HAC


class TestNotHACInverse:
    """8h suppressed but 4h > baseline = inverse pattern, suspicious for HAC."""

    def test_inverse_pattern(self):
        """4h cortisol higher than baseline, but 8h still suppressed."""
        result = interpret_lddst(_inputs(baseline=3.0, h4=4.0, h8=1.0))
        assert result.category == LDDSTCategory.NOT_HAC_INVERSE


class TestSupportsPDH:
    """8h > cut-off AND at least one suppression criterion met."""

    def test_8h_above_cutoff_with_4h_below_cutoff(self):
        """4h < cut-off shows partial suppression — PDH-consistent."""
        result = interpret_lddst(_inputs(baseline=5.0, h4=1.0, h8=2.0))
        assert result.category == LDDSTCategory.SUPPORTS_PDH

    def test_8h_above_cutoff_with_4h_below_50pct_baseline(self):
        """4h < 50% baseline — PDH-consistent."""
        result = interpret_lddst(_inputs(baseline=10.0, h4=4.0, h8=3.0))
        # 4h = 4 < 50% of 10 = 5 ✓ suppression criterion met
        assert result.category == LDDSTCategory.SUPPORTS_PDH

    def test_8h_above_cutoff_with_8h_below_50pct_baseline(self):
        """8h < 50% baseline (but still > cut-off) — PDH-consistent."""
        result = interpret_lddst(_inputs(baseline=10.0, h4=8.0, h8=4.0))
        # 8h = 4 < 50% of 10 = 5 ✓ suppression criterion met
        assert result.category == LDDSTCategory.SUPPORTS_PDH


class TestDexResistant:
    """8h > cut-off and NO suppression criteria met."""

    def test_no_suppression(self):
        """Both 4h and 8h elevated and > 50% of baseline → resistant."""
        result = interpret_lddst(_inputs(baseline=5.0, h4=4.0, h8=3.5))
        assert result.category == LDDSTCategory.DEX_RESISTANT


class TestUnitConversion:
    """Calculator should accept either µg/dL or nmol/L; results equivalent."""

    def test_ug_per_dl_to_nmol_l_conversion(self):
        # 1.4 µg/dL × 27.59 ≈ 38.6 nmol/L
        nmol = to_nmol_l(1.4)
        assert nmol == pytest.approx(38.6, abs=0.5)

    def test_nmol_l_input_matches_ug_dl(self):
        """Same patient, same data, two units — same category."""
        ug = interpret_lddst(_inputs(baseline=5.0, h4=1.0, h8=1.0, unit=CortisolUnit.UG_PER_DL))
        # 5 µg/dL ≈ 138 nmol/L; 1 µg/dL ≈ 27.6
        nmol = interpret_lddst(
            LDDSTInputs(
                baseline_cortisol=138.0,
                cortisol_4h=27.6,
                cortisol_8h=27.6,
                cutoff_8h=40.0,
                unit=CortisolUnit.NMOL_PER_L,
            )
        )
        assert ug.category == nmol.category


class TestSourceAttribution:
    def test_includes_consensus(self):
        result = interpret_lddst(_inputs())
        cite_text = " ".join(s.citation for s in result.sources)
        assert "ACVIM" in cite_text or "Behrend" in cite_text or "consensus" in cite_text.lower()


# ---------------------------------------------------------------------------
# Route-level: placeholder text on bad input
# ---------------------------------------------------------------------------


class TestPlaceholderText:
    """LDDST takes no patient weight — inputs are cortisol values. The
    shared placeholder partial defaults to 'Enter a patient weight to
    see the result.', which is misleading on this page. The /compute
    endpoint must override that default when any required cortisol
    value is unparseable.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    def test_compute_empty_does_not_mention_weight(self, client):
        r = client.post(
            "/lddst/compute",
            data={
                "baseline_cortisol": "",
                "cortisol_4h": "",
                "cortisol_8h": "",
                "unit": "ug_dl",
            },
        )
        assert r.status_code == 200
        assert "patient weight" not in r.text.lower(), (
            "LDDST placeholder must not show 'Enter a patient weight' — "
            "the calculator takes no weight input"
        )

    def test_compute_empty_names_required_cortisol_values(self, client):
        r = client.post(
            "/lddst/compute",
            data={
                "baseline_cortisol": "",
                "cortisol_4h": "",
                "cortisol_8h": "",
                "unit": "ug_dl",
            },
        )
        # Match the substantive tokens, not the exact wording.
        assert "cortisol" in r.text.lower()
        assert "baseline" in r.text.lower()

