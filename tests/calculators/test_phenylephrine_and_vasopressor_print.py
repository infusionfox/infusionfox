"""Tests for phenylephrine and the uniform print feature on vasopressors.

Phenylephrine is the second pure-α vasopressor in the catalog (after
the catecholamines). The print feature is opt-in per drug via
CalculatorConfig.supports_print — set True on all 6 vasopressors:
norepinephrine, epinephrine, vasopressin, phenylephrine, dobutamine,
dopamine-cri (engine) and dopamine 6×kg (custom module).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DOBUTAMINE,
    DOPAMINE_STANDARD,
    EPINEPHRINE,
    FENTANYL,
    NOREPINEPHRINE,
    PHENYLEPHRINE,
    VASOPRESSIN,
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


class TestPhenylephrineRegistration:
    def test_in_catalog(self):
        assert get_drug("phenylephrine") is PHENYLEPHRINE

    def test_category(self):
        assert PHENYLEPHRINE.category == "Vasopressors & Inotropes"
        by_cat = drugs_by_category()
        assert PHENYLEPHRINE in by_cat["Vasopressors & Inotropes"]

    def test_dose_unit(self):
        # Pure µg/kg/min — catecholamine pattern, no unit override.
        assert PHENYLEPHRINE.dose_unit == DoseUnit.UG_PER_KG_PER_MIN
        assert PHENYLEPHRINE.concentration_unit_label == "µg/mL"
        assert PHENYLEPHRINE.dose_mass_unit == "µg"


class TestPhenylephrineDoseRanges:
    def test_dog_range_0_5_to_3(self):
        rng = PHENYLEPHRINE.dose_ranges[Species.DOG]
        assert rng.min == 0.5
        assert rng.max == 3.0
        assert rng.caution_threshold == 3.0

    def test_cat_range_0_5_to_3(self):
        rng = PHENYLEPHRINE.dose_ranges[Species.CAT]
        assert rng.min == 0.5
        assert rng.max == 3.0

    def test_persistent_warning_mentions_reflex_bradycardia(self):
        rng = PHENYLEPHRINE.dose_ranges[Species.DOG]
        # Pure α-agonism causes reflex bradycardia — must be in the
        # persistent warning so clinicians monitor for it.
        assert "reflex bradycardia" in rng.persistent_warning.lower()

    def test_titration_ladder_covers_published_range(self):
        assert 0.5 in PHENYLEPHRINE.titration_ladder
        assert 3.0 in PHENYLEPHRINE.titration_ladder
        # 1.0 is the working clinical anchor.
        assert 1.0 in PHENYLEPHRINE.titration_ladder


class TestPhenylephrineMath:
    def test_canonical_20kg_dog(self):
        # 20 kg × 1 µg/kg/min × 60 ÷ 40 µg/mL = 30 mL/hr.
        result = compute(
            PHENYLEPHRINE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=1.0,
                concentration_ug_per_ml=40.0,
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(30.0)

    def test_small_cat_with_concentrated_bag(self):
        # 4 kg cat × 1 µg/kg/min × 60 ÷ 100 µg/mL = 2.4 mL/hr.
        result = compute(
            PHENYLEPHRINE,
            CalcInputs(
                weight_value=4.0,
                weight_unit=WeightUnit.KG,
                dose=1.0,
                concentration_ug_per_ml=100.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(2.4)

    def test_max_dose_20kg_dog(self):
        # 20 × 3 × 60 / 40 = 90 mL/hr.
        result = compute(
            PHENYLEPHRINE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=3.0,
                concentration_ug_per_ml=40.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(90.0)


class TestPhenylephrineAutoRecommendation:
    def test_three_concentration_tiers(self):
        assert len(PHENYLEPHRINE.concentration_presets) == 3
        cs = sorted(
            [p.concentration_ug_per_ml for p in PHENYLEPHRINE.concentration_presets],
            reverse=True,
        )
        assert cs == [100, 40, 20]

    def test_large_dog_recommended_100(self):
        # 25 kg → 100 µg/mL band.
        recommended = next(
            p for p in PHENYLEPHRINE.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 25)
            and (p.weight_max_kg is None or p.weight_max_kg > 25)
        )
        assert recommended.concentration_ug_per_ml == 100

    def test_medium_patient_recommended_40(self):
        # 5 kg → 40 µg/mL band (textbook prep).
        recommended = next(
            p for p in PHENYLEPHRINE.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 5)
            and (p.weight_max_kg is None or p.weight_max_kg > 5)
        )
        assert recommended.concentration_ug_per_ml == 40

    def test_small_cat_recommended_20(self):
        # 2 kg → 20 µg/mL band.
        recommended = next(
            p for p in PHENYLEPHRINE.concentration_presets
            if (p.weight_min_kg is None or p.weight_min_kg <= 2)
            and (p.weight_max_kg is None or p.weight_max_kg > 2)
        )
        assert recommended.concentration_ug_per_ml == 20


class TestPhenylephrineRoute:
    def test_get_form_renders(self):
        r = client.get("/phenylephrine")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Phenylephrine CRI</h1>" in body
        # Stock display labeled.
        assert "10 mg/mL" in body

    def test_compute_endpoint(self):
        r = client.post(
            "/phenylephrine/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "1",
                "concentration_ug_per_ml": "40",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        # 30 mL/hr pump rate.
        assert "30.00" in r.text


# ---------------------------------------------------------------------------
# Print uniformity across all vasopressors.
# ---------------------------------------------------------------------------


class TestVasopressorPrintFlag:
    """Every vasopressor / inotrope drug has supports_print=True."""

    @pytest.mark.parametrize(
        "drug",
        [NOREPINEPHRINE, EPINEPHRINE, VASOPRESSIN, PHENYLEPHRINE, DOBUTAMINE, DOPAMINE_STANDARD],
    )
    def test_vasopressor_has_supports_print(self, drug):
        assert drug.supports_print is True

    def test_non_vasopressor_default_false(self):
        # Fentanyl is an analgesic, not a vasopressor — should not
        # have the print button.
        assert FENTANYL.supports_print is False


class TestPrintButtonRenders:
    """The print button + print-only result header appear on every
    vasopressor page (universal /<slug> route and the dopamine 6×kg
    standalone)."""

    @pytest.mark.parametrize(
        "path",
        [
            "/norepinephrine",
            "/epinephrine",
            "/vasopressin",
            "/phenylephrine",
            "/dobutamine",
            "/dopamine-cri",
            "/dopamine",  # 6×kg standalone (custom module)
        ],
    )
    def test_print_button_present(self, path):
        body = client.get(path).text
        # Button class — universal template uses calculator-print-btn,
        # dopamine 6×kg also adopts the same class for visual
        # consistency. JS hook is one of two functions.
        assert "calculator-print-btn" in body
        # Print machinery present.
        assert "@media print" in body
        assert "print-only" in body

    @pytest.mark.parametrize(
        "path",
        [
            "/norepinephrine",
            "/epinephrine",
            "/vasopressin",
            "/phenylephrine",
            "/dobutamine",
            "/dopamine-cri",
        ],
    )
    def test_universal_print_function_name(self, path):
        body = client.get(path).text
        assert "infusionfox_calculator_print" in body

    def test_dopamine_6xkg_uses_its_own_print_function(self):
        body = client.get("/dopamine").text
        # Dopamine 6×kg uses its own JS function name since it's a
        # separate template path.
        assert "infusionfox_dopamine_print" in body


class TestPrintButtonNotOnNonVasopressors:
    """Regression: drugs without supports_print=True don't get the
    print button or print machinery."""

    @pytest.mark.parametrize(
        "path",
        ["/fentanyl", "/morphine", "/dexmedetomidine", "/metoclopramide-cri"],
    )
    def test_non_vasopressor_lacks_print(self, path):
        body = client.get(path).text
        # No print button.
        assert "calculator-print-btn" not in body
        # No print CSS / JS.
        assert "infusionfox_calculator_print" not in body


class TestPrintOnlyHeaderInResultPanel:
    """The print-only header inside the result-panel partial carries
    the patient anchor (drug name, weight, species) and the
    InfusionFox brand mark + timestamp anchor for the JS print
    function to populate."""

    def test_norepi_result_has_print_header(self):
        r = client.post(
            "/norepinephrine/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "0.1",
                "concentration_ug_per_ml": "16",
            },
            headers={"HX-Request": "true"},
        )
        body = r.text
        assert "print-only" in body
        assert "/static/brand/logos/mark.png" in body
        assert "infusionfox.com" in body
        assert 'id="print-timestamp"' in body
        # Drug name surfaced in print header.
        assert "Norepinephrine" in body

    def test_phenylephrine_result_has_print_header(self):
        r = client.post(
            "/phenylephrine/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "1",
                "concentration_ug_per_ml": "40",
            },
            headers={"HX-Request": "true"},
        )
        body = r.text
        assert "print-only" in body
        assert "/static/brand/logos/mark.png" in body
        assert "Phenylephrine" in body
