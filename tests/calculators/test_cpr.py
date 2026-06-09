"""
Tests for the CPR / RECOVER 2024 dosing chart calculator.

Source: 2024 RECOVER Resuscitation Guidelines (Fletcher et al.).

Weight-based emergency drug volumes (computed against listed stock concentrations).
Defibrillation: external 4–6 J/kg; internal 0.5–1 J/kg.

Drug list:
  Arrest:           epinephrine, vasopressin, atropine
  Anti-arrhythmic:  amiodarone, lidocaine, esmolol
  Reversal:         naloxone, flumazenil, atipamezole
"""

from __future__ import annotations

import pytest

from app.routers.cpr import CPR_DRUGS, calculate


class TestDrugListComplete:
    def test_nine_drugs(self):
        """RECOVER 2024 chart: 3 arrest + 3 anti-arrhythmic + 3 reversal = 9."""
        assert len(CPR_DRUGS) == 9

    def test_three_categories_present(self):
        categories = {d.category for d in CPR_DRUGS}
        assert categories == {"Arrest", "Anti-arrhythmic", "Reversal"}


class TestArrestDoses:
    """The headline arrest drugs."""

    def test_epinephrine_low_dose(self):
        """Low-dose epinephrine 0.01 mg/kg of 1:1000 (1 mg/mL) = 0.01 mL/kg."""
        result = calculate(weight_kg=10)
        epi = next(d for d in result.doses if "epinephrine" in d.drug.name.lower())
        # 10 kg × 0.01 mL/kg = 0.1 mL
        assert epi.volume_ml == pytest.approx(0.1)
        assert "0.01 mg/kg" in epi.drug.dose_label

    def test_vasopressin(self):
        """0.8 U/kg of 20 U/mL = 0.04 mL/kg."""
        result = calculate(weight_kg=10)
        vaso = next(d for d in result.doses if "vasopressin" in d.drug.name.lower())
        assert vaso.volume_ml == pytest.approx(0.4)


class TestAntiArrhythmicDoses:
    def test_amiodarone(self):
        """5 mg/kg of 50 mg/mL = 0.1 mL/kg."""
        result = calculate(weight_kg=10)
        amio = next(d for d in result.doses if "amiodarone" in d.drug.name.lower())
        assert amio.volume_ml == pytest.approx(1.0)
        assert "5 mg/kg" in amio.drug.dose_label

    def test_lidocaine(self):
        """2 mg/kg of 20 mg/mL = 0.1 mL/kg."""
        result = calculate(weight_kg=20)
        lido = next(d for d in result.doses if "lidocaine" in d.drug.name.lower())
        assert lido.volume_ml == pytest.approx(2.0)


class TestReversalDoses:
    def test_naloxone(self):
        """0.04 mg/kg of 0.4 mg/mL = 0.1 mL/kg."""
        result = calculate(weight_kg=20)
        nalox = next(d for d in result.doses if "naloxone" in d.drug.name.lower())
        assert nalox.volume_ml == pytest.approx(2.0)


class TestDefibrillation:
    """RECOVER 2024 publishes both biphasic and monophasic energies, with
    a 2→4 J/kg escalation strategy for biphasic external shocks. The
    calculator must expose all four values plus the biphasic escalation."""

    def test_biphasic_first_shock_2_j_per_kg(self):
        """20 kg → 40 J biphasic first external."""
        result = calculate(weight_kg=20)
        assert result.defib.biphasic_first_ext_j == 40.0
        assert "40" in result.defib.biphasic_first_ext_display

    def test_biphasic_escalate_4_j_per_kg(self):
        """20 kg → 80 J biphasic escalation external (after refractory)."""
        result = calculate(weight_kg=20)
        assert result.defib.biphasic_escalate_ext_j == 80.0
        assert "80" in result.defib.biphasic_escalate_ext_display

    def test_biphasic_internal_0_2_to_0_4_j_per_kg(self):
        """20 kg → 4–8 J biphasic internal."""
        result = calculate(weight_kg=20)
        assert result.defib.biphasic_int_low_j == pytest.approx(4.0)
        assert result.defib.biphasic_int_high_j == pytest.approx(8.0)
        assert "4" in result.defib.biphasic_int_display
        assert "8" in result.defib.biphasic_int_display

    def test_monophasic_external_4_to_6_j_per_kg(self):
        """20 kg → 80–120 J monophasic external."""
        result = calculate(weight_kg=20)
        assert result.defib.monophasic_ext_low_j == 80.0
        assert result.defib.monophasic_ext_high_j == 120.0
        assert "80" in result.defib.monophasic_ext_display
        assert "120" in result.defib.monophasic_ext_display

    def test_monophasic_internal_0_5_to_1_j_per_kg(self):
        """20 kg → 10–20 J monophasic internal."""
        result = calculate(weight_kg=20)
        assert result.defib.monophasic_int_low_j == 10.0
        assert result.defib.monophasic_int_high_j == 20.0
        assert "10" in result.defib.monophasic_int_display
        assert "20" in result.defib.monophasic_int_display

    def test_biphasic_escalate_is_double_first(self):
        """RECOVER 2024 doubles the first-shock dose if refractory."""
        result = calculate(weight_kg=15)
        assert result.defib.biphasic_escalate_ext_j == pytest.approx(
            2 * result.defib.biphasic_first_ext_j
        )

    def test_small_patient_uses_decimal_format(self):
        """2.5 kg cat: biphasic internal 0.5–1 J → display retains decimal."""
        result = calculate(weight_kg=2.5)
        # biphasic_int_low = 0.5 J, should render as "0.5" not "0" or "1"
        assert "0.5" in result.defib.biphasic_int_display


class TestVolumeScalesWithWeight:
    def test_doubling_weight_doubles_volumes(self):
        r10 = calculate(weight_kg=10)
        r20 = calculate(weight_kg=20)
        for d10, d20 in zip(r10.doses, r20.doses, strict=True):
            assert d20.volume_ml == pytest.approx(d10.volume_ml * 2, rel=1e-3)


class TestSourceAttribution:
    def test_includes_recover(self):
        result = calculate(weight_kg=10)
        cite_text = " ".join(s.citation for s in result.sources)
        assert "RECOVER" in cite_text or "Fletcher" in cite_text or "2024" in cite_text


class TestNotesPresent:
    """Each drug should carry a route/timing note."""

    def test_all_drugs_have_notes(self):
        result = calculate(weight_kg=10)
        for d in result.doses:
            assert d.note != "" or d.drug.note != ""
