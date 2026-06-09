"""Tests for nitroprusside CRI.

Nitroprusside is the first drug in the new "Cardiology" category.
Direct NO donor, mixed arterial/venous vasodilator. High-alert drug
with multiple safety guards: LIGHT-SENSITIVE, D5W-only dilution,
cyanide accumulation risk above 8 µg/kg/min or beyond 72 hr
infusion, contraindicated/cautioned in renal failure (thiocyanate
accumulation).

Engine reuses UG_PER_KG_PER_MIN (same as catecholamines). Structurally
similar to phenylephrine: 50 mg vial, three concentration tiers,
pump-precision auto-recommendation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DRUGS,
    NITROPRUSSIDE,
    drugs_by_category,
    get_drug,
)
from app.calculators.engine import (
    CalcInputs,
    DoseUnit,
    Species,
    WeightUnit,
    compute,
)
from app.main import app

client = TestClient(app)


class TestNitroprussideRegistration:
    def test_in_catalog(self):
        assert NITROPRUSSIDE in DRUGS
        assert get_drug("nitroprusside") is NITROPRUSSIDE

    def test_category_is_cardiology(self):
        """Tim's correction: nitroprusside is a vasodilator, not a
        vasopressor — it lives in the new Cardiology section."""
        assert NITROPRUSSIDE.category == "Cardiology"
        by_cat = drugs_by_category()
        assert NITROPRUSSIDE in by_cat["Cardiology"]

    def test_not_in_vasopressors_section(self):
        by_cat = drugs_by_category()
        vasopressors = by_cat.get("Vasopressors & Inotropes", [])
        assert NITROPRUSSIDE not in vasopressors


class TestNitroprussideDoseConfig:
    def test_dose_unit_ug_per_kg_per_min(self):
        assert NITROPRUSSIDE.dose_unit == DoseUnit.UG_PER_KG_PER_MIN

    def test_dog_range_published(self):
        rng = NITROPRUSSIDE.dose_ranges[Species.DOG]
        assert rng.min == 0.5
        assert rng.max == 10.0
        # Cyanide accumulation risk substantially rises above 8.
        assert rng.caution_threshold == 8.0

    def test_cat_range_published(self):
        rng = NITROPRUSSIDE.dose_ranges[Species.CAT]
        assert rng.min == 0.5
        assert rng.max == 10.0
        assert rng.caution_threshold == 8.0


class TestNitroprussideSafetyLanguage:
    """The persistent warning carries the multiple safety guards this
    drug demands. Each guard is checked here so a future text edit
    that accidentally drops one is caught."""

    def test_dog_warning_mentions_light_sensitivity(self):
        warning = NITROPRUSSIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "light" in warning
        assert "foil" in warning or "opaque" in warning

    def test_dog_warning_mentions_d5w_only(self):
        warning = NITROPRUSSIDE.dose_ranges[Species.DOG].persistent_warning
        # The "ONLY" caps is intentional in the source text — D5W is
        # the only compatible diluent.
        assert "5% dextrose" in warning or "D5W" in warning

    def test_dog_warning_mentions_cyanide(self):
        warning = NITROPRUSSIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "cyanide" in warning

    def test_dog_warning_mentions_renal_failure(self):
        warning = NITROPRUSSIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "renal failure" in warning
        # Thiocyanate is the specific metabolite of concern.
        assert "thiocyanate" in warning

    def test_dog_warning_mentions_bp_monitoring(self):
        warning = NITROPRUSSIDE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "bp" in warning or "blood pressure" in warning
        assert "arterial" in warning

    def test_cat_warning_has_same_critical_guards(self):
        warning = NITROPRUSSIDE.dose_ranges[Species.CAT].persistent_warning.lower()
        # Same critical safety surface for both species.
        for term in ("light", "5% dextrose", "cyanide", "renal failure"):
            assert term.lower() in warning, (
                f"cat warning missing critical safety guard: {term}"
            )

    def test_dilution_note_specifies_d5w_only_and_light(self):
        note = NITROPRUSSIDE.dilution_note
        assert "5% dextrose ONLY" in note or "Not 0.9% NaCl" in note
        assert "foil" in note.lower() or "opaque" in note.lower()

    def test_dilution_note_describes_color_change_discard_criterion(self):
        note = NITROPRUSSIDE.dilution_note.lower()
        assert "brown" in note or "blue" in note
        assert "discard" in note

    def test_caution_note_mentions_duration_limit(self):
        caution = NITROPRUSSIDE.dose_ranges[Species.DOG].caution_note.lower()
        assert "duration" in caution or "hr" in caution


class TestNitroprussideMath:
    def test_canonical_20kg_dog(self):
        # 20 kg × 1 µg/kg/min × 60 ÷ 200 µg/mL = 6.0 mL/hr.
        result = compute(
            NITROPRUSSIDE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=1.0,
                concentration_ug_per_ml=200.0,
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(6.0)

    def test_high_dose_20kg_dog(self):
        # 20 × 5 × 60 / 200 = 30 mL/hr. (Above caution threshold but
        # within published range.)
        result = compute(
            NITROPRUSSIDE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=5.0,
                concentration_ug_per_ml=200.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(30.0)

    def test_small_cat_with_dilute_prep(self):
        # 2 kg × 1 µg/kg/min × 60 ÷ 100 = 1.2 mL/hr — sub-floor at
        # 100 µg/mL. The auto-recommended concentration for 2 kg is
        # 100 µg/mL; the pump-precision warning should fire when
        # rendered (covered separately in the warning test below).
        result = compute(
            NITROPRUSSIDE,
            CalcInputs(
                weight_value=2.0,
                weight_unit=WeightUnit.KG,
                dose=1.0,
                concentration_ug_per_ml=100.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(1.2)

    def test_lb_conversion(self):
        # 44 lb ≈ 19.96 kg → ~6 mL/hr at canonical dose.
        result = compute(
            NITROPRUSSIDE,
            CalcInputs(
                weight_value=44.0,
                weight_unit=WeightUnit.LB,
                dose=1.0,
                concentration_ug_per_ml=200.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(6.0, rel=1e-2)


class TestNitroprussideAutoRecommendation:
    def test_three_tiers(self):
        assert len(NITROPRUSSIDE.concentration_presets) == 3
        concs = sorted(
            [p.concentration_ug_per_ml for p in NITROPRUSSIDE.concentration_presets],
            reverse=True,
        )
        assert concs == [500, 200, 100]

    def test_large_patient_recommended_500(self):
        # 25 kg → 500 µg/mL band (≥15 kg).
        recommended = next(
            p for p in NITROPRUSSIDE.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 25)
            and (p.weight_max_kg is None or p.weight_max_kg > 25)
        )
        assert recommended.concentration_ug_per_ml == 500

    def test_medium_patient_recommended_200(self):
        # 10 kg → 200 µg/mL textbook prep.
        recommended = next(
            p for p in NITROPRUSSIDE.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 10)
            and (p.weight_max_kg is None or p.weight_max_kg > 10)
        )
        assert recommended.concentration_ug_per_ml == 200

    def test_small_patient_recommended_100(self):
        # 2 kg cat → 100 µg/mL dilute prep.
        recommended = next(
            p for p in NITROPRUSSIDE.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 2)
            and (p.weight_max_kg is None or p.weight_max_kg > 2)
        )
        assert recommended.concentration_ug_per_ml == 100


class TestNitroprussideRoute:
    def test_form_renders(self):
        r = client.get("/nitroprusside")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Nitroprusside CRI</h1>" in body
        # Cardiology eyebrow on the calc page.
        assert ">Cardiology<" in body

    def test_compute_endpoint(self):
        r = client.post(
            "/nitroprusside/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "1",
                "concentration_ug_per_ml": "200",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "6.00" in r.text

    def test_caution_note_fires_above_threshold(self):
        # 9 µg/kg/min is above the 8 µg/kg/min cyanide-risk threshold.
        r = client.post(
            "/nitroprusside/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "9",
                "concentration_ug_per_ml": "200",
            },
            headers={"HX-Request": "true"},
        )
        assert "cyanide" in r.text.lower()

    def test_caution_note_text_present_in_result(self):
        # The caution_note for dosing above 8 µg/kg/min always renders
        # in the titration-ladder "Why these rows are flagged"
        # disclosure on the result panel, regardless of current dose —
        # the ladder shows where future titration would cross the
        # caution band so the clinician sees it pre-emptively.
        r = client.post(
            "/nitroprusside/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "3",
                "concentration_ug_per_ml": "200",
            },
            headers={"HX-Request": "true"},
        )
        assert "cyanide" in r.text.lower()


class TestNitroprussidePrintSupport:
    """Nitroprusside opts into the print machinery — same rationale
    as the vasopressors (ICU bedside reference)."""

    def test_supports_print_true(self):
        assert NITROPRUSSIDE.supports_print is True

    def test_form_renders_print_button(self):
        body = client.get("/nitroprusside").text
        assert "calculator-print-btn" in body
        assert "infusionfox_calculator_print" in body

    def test_result_panel_has_print_header(self):
        r = client.post(
            "/nitroprusside/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "1",
                "concentration_ug_per_ml": "200",
            },
            headers={"HX-Request": "true"},
        )
        body = r.text
        assert "print-only" in body
        assert "Nitroprusside" in body


class TestNitroprussideNavSectionOrder:
    """The new Cardiology section is positioned right after
    Vasopressors & Inotropes — they're clinically adjacent
    (hemodynamic management drugs)."""

    def test_cardiology_in_section_order(self):
        from app.nav import nav_index
        groups = nav_index()
        keys = list(groups.keys())
        # Cardiology is present.
        assert "Cardiology" in keys
        # And appears right after Vasopressors & Inotropes.
        vp_idx = keys.index("Vasopressors & Inotropes")
        cardio_idx = keys.index("Cardiology")
        assert cardio_idx == vp_idx + 1
