"""
Tests for the mannitol osmotherapy calculator.

Dosing aligned to Plumb's Veterinary Drugs (current edition):

  Osmotic diuresis (label, not FDA-approved): 1.5–2 g/kg IV over 30 min.
  Oliguric AKI: 0.25–1 g/kg IV over 15–20 min; optional follow-up CRI
    at 60–120 mg/kg/hr; cumulative cap 2 g/kg/day.
  Acute glaucoma: 1–2 g/kg IV over 10–20 min.
  Increased ICP / cerebral edema: 0.5–1 g/kg IV over 15–20 min; repeat
    q6–8h; IV CRI NOT recommended.
  Uroliths: 0.25–0.5 g/kg loading over 20 min, then CRI at 1 mg/kg/min
    (= 60 mg/kg/hr).

Math verified manually:
  50 lb dog = 22.68 kg. At 0.5 g/kg → 11.34 g total. In 20%
  (0.20 g/mL) that's 56.7 mL. Over 20 min the rate is 56.7/20 × 60 ≈
  170 mL/hr.

  For uroliths CRI on the same 50 lb dog at 60 mg/kg/hr in 20%
  (200 mg/mL): 60 × 22.68 / 200 = 6.8 mL/hr.
"""

from __future__ import annotations

import pytest

from app.calculators.engine import WeightUnit
from app.calculators.mannitol import (
    CUMULATIVE_24H_CEILING_G_PER_KG,
    INDICATION_PROFILES,
    MANNITOL_CATALOG_ENTRY,
    MannitolIndication,
    MannitolInputs,
    compute_mannitol,
)


class TestBasicBolusMath:
    def test_50lb_dog_cerebral_edema(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=50,
                weight_unit=WeightUnit.LB,
                indication=MannitolIndication.CEREBRAL_EDEMA,
                dose_g_per_kg=0.5,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.valid is True
        assert result.weight_kg == pytest.approx(22.68, abs=0.01)
        assert result.total_dose_g == pytest.approx(11.34, abs=0.05)
        assert result.volume_ml == pytest.approx(56.7, abs=0.2)
        assert result.rate_ml_per_hr == pytest.approx(170.1, abs=1.0)
        # Cerebral edema has no CRI per Plumb's
        assert result.cri_rate_low_ml_per_hr is None
        assert result.cri_rate_high_ml_per_hr is None

    def test_kg_input_25_percent(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.CEREBRAL_EDEMA,
                dose_g_per_kg=1.0,
                concentration_percent=25,
                duration_min=20,
            )
        )
        assert result.valid is True
        assert result.weight_kg == 20.0
        assert result.total_dose_g == 20.0
        # 20 g / 0.25 g/mL = 80 mL
        assert result.volume_ml == pytest.approx(80.0, abs=0.1)
        # 80 / 20 × 60 = 240 mL/hr
        assert result.rate_ml_per_hr == pytest.approx(240.0, abs=1.0)


class TestOsmoticDiuresisLabelIndication:
    def test_label_dose_within_range(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.OSMOTIC_DIURESIS,
                dose_g_per_kg=1.5,
                concentration_percent=20,
                duration_min=30,
            )
        )
        assert result.valid is True
        assert result.dose_within_indication_range is True
        # No CRI for osmotic diuresis
        assert result.cri_rate_low_ml_per_hr is None

    def test_label_indication_range_175(self):
        """Label dose is 1.5–2 g/kg, so 1.75 is mid-range."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.OSMOTIC_DIURESIS,
                dose_g_per_kg=1.75,
                concentration_percent=20,
                duration_min=30,
            )
        )
        assert result.valid is True
        assert result.dose_within_indication_range is True


class TestOliguricAkiWithCri:
    def test_bolus_dose_within_plumbs_range(self):
        """Plumb's: 0.25–1 g/kg (NOT 0.25–0.5)."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.OLIGURIC_AKI,
                dose_g_per_kg=1.0,  # At upper Plumb's bound
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.valid is True
        assert result.dose_within_indication_range is True

    def test_cri_range_at_50lb_20pct(self):
        """CRI 60–120 mg/kg/hr in 20% (200 mg/mL) on 22.68 kg dog:
        Low: 60 × 22.68 / 200 = 6.80 mL/hr
        High: 120 × 22.68 / 200 = 13.61 mL/hr"""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=50,
                weight_unit=WeightUnit.LB,
                indication=MannitolIndication.OLIGURIC_AKI,
                dose_g_per_kg=0.5,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.valid is True
        assert result.cri_rate_low_ml_per_hr == pytest.approx(6.80, abs=0.05)
        assert result.cri_rate_high_ml_per_hr == pytest.approx(13.61, abs=0.05)

    def test_cri_range_at_25pct(self):
        """Same patient at 25% (250 mg/mL):
        Low: 60 × 20 / 250 = 4.80 mL/hr
        High: 120 × 20 / 250 = 9.60 mL/hr"""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.OLIGURIC_AKI,
                dose_g_per_kg=0.5,
                concentration_percent=25,
                duration_min=20,
            )
        )
        assert result.cri_rate_low_ml_per_hr == pytest.approx(4.80, abs=0.05)
        assert result.cri_rate_high_ml_per_hr == pytest.approx(9.60, abs=0.05)


class TestAcuteGlaucoma:
    def test_glaucoma_short_duration_within_range(self):
        """Plumb's says 10–20 min (NOT 20–30)."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.ACUTE_GLAUCOMA,
                dose_g_per_kg=1.5,
                concentration_percent=20,
                duration_min=15,
            )
        )
        assert result.valid is True
        # 15 min should be within range now (10–20)
        # Check no duration-out-of-range message
        combined_interp = " ".join(result.interpretation)
        assert "outside the typical range" not in combined_interp

    def test_glaucoma_25min_out_of_range(self):
        """25 min is above Plumb's 10–20 max."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.ACUTE_GLAUCOMA,
                dose_g_per_kg=1.5,
                concentration_percent=20,
                duration_min=25,
            )
        )
        assert result.valid is True
        combined_interp = " ".join(result.interpretation)
        assert "outside the typical range" in combined_interp

    def test_glaucoma_no_cri(self):
        """Acute glaucoma is a single-dose indication."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.ACUTE_GLAUCOMA,
                dose_g_per_kg=1.5,
                concentration_percent=20,
                duration_min=15,
            )
        )
        assert result.cri_rate_low_ml_per_hr is None


class TestCerebralEdema:
    def test_dose_05_within_plumbs(self):
        """Plumb's: 0.5–1 g/kg (NOT 0.25–1)."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.CEREBRAL_EDEMA,
                dose_g_per_kg=0.5,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.dose_within_indication_range is True

    def test_dose_025_now_below_plumbs(self):
        """0.25 g/kg is below the corrected lower bound 0.5 g/kg."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.CEREBRAL_EDEMA,
                dose_g_per_kg=0.25,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.dose_within_indication_range is False

    def test_no_cri_per_plumbs(self):
        """Plumb's explicitly says IV CRI is NOT recommended for cerebral edema."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.CEREBRAL_EDEMA,
                dose_g_per_kg=0.5,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.cri_rate_low_ml_per_hr is None
        assert result.cri_rate_high_ml_per_hr is None


class TestUrolithsFixedRateCri:
    def test_uroliths_loading_within_range(self):
        """Plumb's: 0.25–0.5 g/kg loading."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.UROLITHS,
                dose_g_per_kg=0.25,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.dose_within_indication_range is True

    def test_uroliths_cri_is_fixed_rate(self):
        """1 mg/kg/min = 60 mg/kg/hr fixed (not a range)."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.UROLITHS,
                dose_g_per_kg=0.25,
                concentration_percent=20,
                duration_min=20,
            )
        )
        # 60 × 20 / 200 = 6 mL/hr
        assert result.cri_rate_low_ml_per_hr == pytest.approx(6.0, abs=0.05)
        assert result.cri_rate_high_ml_per_hr == pytest.approx(6.0, abs=0.05)
        assert result.cri_rate_low_ml_per_hr == result.cri_rate_high_ml_per_hr


class TestValidation:
    def test_zero_weight_rejected(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=0,
                dose_g_per_kg=0.5,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.valid is False

    def test_zero_dose_rejected(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose_g_per_kg=0,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.valid is False

    def test_extreme_dose_rejected(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose_g_per_kg=10,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.valid is False

    def test_invalid_concentration(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose_g_per_kg=0.5,
                concentration_percent=15,
                duration_min=20,
            )
        )
        assert result.valid is False


class TestCumulativeDoseWarning:
    def test_below_ceiling_no_warning(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.CEREBRAL_EDEMA,
                dose_g_per_kg=1.0,
                concentration_percent=20,
                duration_min=20,
            )
        )
        assert result.cumulative_dose_warning is False

    def test_above_ceiling_warns(self):
        """Osmotic diuresis label dose 1.5–2 g/kg is below ceiling; 2.5 above."""
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.ACUTE_GLAUCOMA,
                dose_g_per_kg=2.5,
                concentration_percent=20,
                duration_min=15,
            )
        )
        assert result.cumulative_dose_warning is True
        assert any("2 g/kg/24h" in w for w in result.warnings)

    def test_ceiling_constant(self):
        assert CUMULATIVE_24H_CEILING_G_PER_KG == 2.0


class TestIndicationProfiles:
    def test_all_five_plumbs_indications_present(self):
        """All five Plumb's indications must be represented."""
        expected = {
            MannitolIndication.OSMOTIC_DIURESIS,
            MannitolIndication.OLIGURIC_AKI,
            MannitolIndication.ACUTE_GLAUCOMA,
            MannitolIndication.CEREBRAL_EDEMA,
            MannitolIndication.UROLITHS,
        }
        assert set(INDICATION_PROFILES.keys()) == expected

    def test_osmotic_diuresis_dose_range(self):
        p = INDICATION_PROFILES[MannitolIndication.OSMOTIC_DIURESIS]
        assert p.dose_low_g_per_kg == 1.5
        assert p.dose_high_g_per_kg == 2.0
        assert p.duration_default_min == 30
        assert p.cri_rate_low_mg_per_kg_per_hr is None  # no CRI

    def test_oliguric_aki_dose_and_cri(self):
        p = INDICATION_PROFILES[MannitolIndication.OLIGURIC_AKI]
        assert p.dose_low_g_per_kg == 0.25
        assert p.dose_high_g_per_kg == 1.0  # Plumb's, NOT 0.5
        assert p.cri_rate_low_mg_per_kg_per_hr == 60.0
        assert p.cri_rate_high_mg_per_kg_per_hr == 120.0

    def test_acute_glaucoma_duration(self):
        p = INDICATION_PROFILES[MannitolIndication.ACUTE_GLAUCOMA]
        assert p.dose_low_g_per_kg == 1.0
        assert p.dose_high_g_per_kg == 2.0
        assert p.duration_low_min == 10  # Plumb's, NOT 20
        assert p.duration_high_min == 20  # Plumb's, NOT 30
        assert p.cri_rate_low_mg_per_kg_per_hr is None

    def test_cerebral_edema_dose_no_cri(self):
        p = INDICATION_PROFILES[MannitolIndication.CEREBRAL_EDEMA]
        assert p.dose_low_g_per_kg == 0.5  # Plumb's, NOT 0.25
        assert p.dose_high_g_per_kg == 1.0
        assert p.cri_rate_low_mg_per_kg_per_hr is None  # Plumb's: CRI not recommended

    def test_uroliths_fixed_cri(self):
        p = INDICATION_PROFILES[MannitolIndication.UROLITHS]
        assert p.dose_low_g_per_kg == 0.25
        assert p.dose_high_g_per_kg == 0.5
        assert p.cri_rate_low_mg_per_kg_per_hr == 60.0  # = 1 mg/kg/min
        assert p.cri_rate_high_mg_per_kg_per_hr == 60.0  # fixed rate


class TestPersistentSafetyWarning:
    def test_filter_warning_always_present(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.CEREBRAL_EDEMA,
                dose_g_per_kg=0.5,
                concentration_percent=20,
                duration_min=20,
            )
        )
        combined = " ".join(result.warnings).lower()
        assert "crystalli" in combined
        assert "0.22" in combined
        assert "filter" in combined

    def test_contraindications_listed(self):
        result = compute_mannitol(
            MannitolInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                indication=MannitolIndication.CEREBRAL_EDEMA,
                dose_g_per_kg=0.5,
                concentration_percent=20,
                duration_min=20,
            )
        )
        combined = " ".join(result.warnings).lower()
        assert "anuric" in combined
        assert "heart failure" in combined


class TestCatalogEntry:
    def test_catalog_entry_complete(self):
        for key in ["slug", "display_name", "category", "mechanism_summary"]:
            assert key in MANNITOL_CATALOG_ENTRY
        assert MANNITOL_CATALOG_ENTRY["slug"] == "mannitol"
        assert MANNITOL_CATALOG_ENTRY["category"] == "Electrolytes & Fluids"
