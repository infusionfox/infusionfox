"""Tests for the metoclopramide CRI calculator.

Metoclopramide is the first catalog CRI dosed in mg/kg/hr (the others
are µg/kg/min or µg/kg/hr), and the first to use the loading-dose
feature for a fixed-protocol scenario (laryngeal paralysis surgery)
rather than a CRI-rate-matched one.

What these tests pin down:
  - Config shape: dose unit is MG_PER_KG_PER_HR; both species have a
    dose range; loading_doses includes the lar par protocol; the
    lar par loading is dog-only.
  - Engine math: standard CRI at 0.05 mg/kg/hr × 40 µg/mL → 25 mL/hr;
    lar par intraop at 1.0 mg/kg/hr × 1000 µg/mL → 20 mL/hr.
  - Loading-dose computation: dog at lar par dose returns a 1 mg/kg
    matched loading → 4 mL of 5 mg/mL stock for a 20 kg patient;
    cat returns no scenarios because lar par is dog-only.
  - Template rendering: pump rate displays; loading panel renders for
    dogs and is absent for cats; formula uses the ×1000 branch.
  - Cat-preferred-other warning fires when species=cat.
  - Caution-threshold warning fires for doses above the standard
    antiemetic range (lar par dose triggers it; standard dose does not).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import METOCLOPRAMIDE, compute_loading_doses
from app.calculators.engine import (
    CalcInputs,
    CriMode,
    DoseUnit,
    Species,
    compute,
)
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Config shape — pin down the static config so a regression in any field
# the template or router depends on fails loudly.
# ---------------------------------------------------------------------------


class TestMetoclopramideConfigShape:
    def test_slug(self) -> None:
        assert METOCLOPRAMIDE.slug == "metoclopramide"

    def test_dose_unit_is_mg_per_kg_per_hr(self) -> None:
        # This is the differentiator from every other CRI in the catalog.
        # The compute() function, the form template, and the formula
        # display all branch on this value, so a silent change here
        # would cascade.
        assert METOCLOPRAMIDE.dose_unit == DoseUnit.MG_PER_KG_PER_HR
        assert METOCLOPRAMIDE.dose_unit.value == "mg/kg/hr"

    def test_default_dose_at_low_end_of_standard_range(self) -> None:
        # Conservative default: low end of the standard antiemetic CRI
        # range. Clinicians titrate up if signs persist.
        assert METOCLOPRAMIDE.default_dose == 0.04

    def test_both_species_have_standard_antiemetic_range(self) -> None:
        dog_range = METOCLOPRAMIDE.dose_ranges[Species.DOG]
        cat_range = METOCLOPRAMIDE.dose_ranges[Species.CAT]
        assert dog_range.min == 0.04
        assert dog_range.max == 0.09
        assert cat_range.min == 0.04
        assert cat_range.max == 0.09

    def test_cat_range_warns_other_antiemetics_preferred(self) -> None:
        # Plumb's flags that ondansetron and maropitant are preferred
        # in cats. This must surface to the user without their having
        # to read the learn module.
        cat_range = METOCLOPRAMIDE.dose_ranges[Species.CAT]
        assert "ondansetron" in cat_range.persistent_warning.lower()
        assert "preferred" in cat_range.persistent_warning.lower()

    def test_caution_threshold_above_standard_max(self) -> None:
        # Doses ≥ 0.1 mg/kg/hr exceed the standard antiemetic range
        # and indicate the lar par protocol or an off-label dose.
        dog_range = METOCLOPRAMIDE.dose_ranges[Species.DOG]
        assert dog_range.caution_threshold == 0.1

    def test_three_concentration_presets_including_lar_par_prep(self) -> None:
        # 20 µg/mL (small patients), 40 µg/mL (default), 1000 µg/mL
        # (lar par intraoperative protocol). The high-concentration
        # preset is essential — without it the 1 mg/kg/hr intraop rate
        # would demand impractical carrier-fluid volumes.
        concs = [p.concentration_ug_per_ml for p in METOCLOPRAMIDE.concentration_presets]
        assert 20 in concs
        assert 40 in concs
        assert 1000 in concs

    def test_default_concentration_is_40_ug_per_ml(self) -> None:
        # Standard prep, suits most patients on standard antiemetic CRI.
        assert METOCLOPRAMIDE.default_concentration_ug_per_ml == 40.0

    def test_stock_concentration_5_mg_per_ml(self) -> None:
        # 5 mg/mL = 5000 µg/mL. Calculator math runs in µg internally;
        # the loading-dose stock-volume math uses this.
        assert METOCLOPRAMIDE.stock_concentration_ug_per_ml == 5000.0

    def test_one_loading_dose_scenario_lar_par(self) -> None:
        assert len(METOCLOPRAMIDE.loading_doses) == 1
        scenario = METOCLOPRAMIDE.loading_doses[0]
        assert "Laryngeal paralysis" in scenario.label

    def test_lar_par_loading_dog_only(self) -> None:
        # Plumb's lists the 1 mg/kg loading + 1 mg/kg/hr intraop
        # protocol for dogs only. The dose_per_kg dict omits cats so
        # compute_loading_doses skips the scenario for cats.
        scenario = METOCLOPRAMIDE.loading_doses[0]
        assert Species.DOG in scenario.dose_per_kg
        assert Species.CAT not in scenario.dose_per_kg

    def test_lar_par_loading_is_1_mg_per_kg(self) -> None:
        # 1 mg/kg IV bolus per Plumb's. Single value (not a range).
        scenario = METOCLOPRAMIDE.loading_doses[0]
        lo, hi = scenario.dose_per_kg[Species.DOG]
        assert lo == 1.0
        assert hi == 1.0

    def test_lar_par_loading_displays_in_mg(self) -> None:
        # The display unit is "mg", not the default "µg". This is what
        # makes the template render "1 mg/kg" rather than "1000 µg/kg".
        scenario = METOCLOPRAMIDE.loading_doses[0]
        assert scenario.display_dose_unit == "mg"

    def test_lar_par_does_not_match_cri_rate(self) -> None:
        # The 1 mg/kg loading is a fixed protocol value, not derived
        # from the user's CRI rate. matches_cri_rate=False means the
        # template shows the range/single value, not a "matched"
        # callout tied to the CRI dose.
        scenario = METOCLOPRAMIDE.loading_doses[0]
        assert scenario.matches_cri_rate is False

    def test_supports_target_pump_rate_mode_off(self) -> None:
        # Metoclopramide CRI is conventionally prepared at standard
        # concentrations in a fluid bag; clinicians don't routinely
        # target a specific pump rate for fluid-restricted patients
        # the way they do for vasopressors.
        assert METOCLOPRAMIDE.supports_target_pump_rate_mode is False

    def test_how_it_works_three_paragraphs(self) -> None:
        # Standard for all updated CRIs — three paragraphs covering
        # workflow, loading-dose disclosure, and safety.
        assert len(METOCLOPRAMIDE.how_it_works_paragraphs) == 3


# ---------------------------------------------------------------------------
# Engine math — compute() must accept MG_PER_KG_PER_HR and produce the
# right pump rate. Without the engine branch this calculator would
# raise an unhandled ValueError on every POST.
# ---------------------------------------------------------------------------


class TestMetoclopramideEngineMath:
    def test_standard_antiemetic_dog(self) -> None:
        # 20 kg dog at 0.05 mg/kg/hr × 40 µg/mL bag:
        # total ug/hr = 20 × 0.05 × 1000 = 1000 µg/hr
        # pump rate = 1000 ÷ 40 = 25.0 mL/hr
        inputs = CalcInputs(
            weight_value=20.0,
            weight_unit="kg",
            dose=0.05,
            species=Species.DOG,
            concentration_ug_per_ml=40.0,
            cri_mode=CriMode.STANDARD_BAG,
        )
        result = compute(METOCLOPRAMIDE, inputs)
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(25.0, rel=1e-4)

    def test_lar_par_intraop_dog(self) -> None:
        # 20 kg dog at 1.0 mg/kg/hr × 1000 µg/mL prep:
        # total ug/hr = 20 × 1.0 × 1000 = 20,000 µg/hr
        # pump rate = 20,000 ÷ 1000 = 20.0 mL/hr (reasonable for syringe pump)
        inputs = CalcInputs(
            weight_value=20.0,
            weight_unit="kg",
            dose=1.0,
            species=Species.DOG,
            concentration_ug_per_ml=1000.0,
            cri_mode=CriMode.STANDARD_BAG,
        )
        result = compute(METOCLOPRAMIDE, inputs)
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(20.0, rel=1e-4)

    def test_lar_par_postop_dog(self) -> None:
        # 20 kg dog at 0.083 mg/kg/hr (postop step-down) × 40 µg/mL:
        # total = 20 × 0.083 × 1000 = 1660 µg/hr
        # pump rate = 1660 ÷ 40 = 41.5 mL/hr
        inputs = CalcInputs(
            weight_value=20.0,
            weight_unit="kg",
            dose=0.083,
            species=Species.DOG,
            concentration_ug_per_ml=40.0,
            cri_mode=CriMode.STANDARD_BAG,
        )
        result = compute(METOCLOPRAMIDE, inputs)
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(41.5, rel=1e-3)

    def test_small_cat_standard_dose(self) -> None:
        # 4 kg cat at 0.04 mg/kg/hr × 40 µg/mL:
        # total = 4 × 0.04 × 1000 = 160 µg/hr
        # pump rate = 160 ÷ 40 = 4.0 mL/hr
        inputs = CalcInputs(
            weight_value=4.0,
            weight_unit="kg",
            dose=0.04,
            species=Species.CAT,
            concentration_ug_per_ml=40.0,
            cri_mode=CriMode.STANDARD_BAG,
        )
        result = compute(METOCLOPRAMIDE, inputs)
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(4.0, rel=1e-4)


# ---------------------------------------------------------------------------
# Loading-dose computation — the lar par protocol must surface for dogs
# at any input dose, but never for cats.
# ---------------------------------------------------------------------------


class TestMetoclopramideLoadingDose:
    def test_dog_at_lar_par_intraop_dose(self) -> None:
        # 20 kg dog: 1 mg/kg × 20 kg = 20 mg = 20,000 µg.
        # Stock 5 mg/mL = 5000 µg/mL → 20,000 / 5000 = 4 mL.
        results = compute_loading_doses(
            drug=METOCLOPRAMIDE,
            weight_kg=20.0,
            species=Species.DOG,
            cri_dose_value=1.0,
        )
        assert len(results) == 1
        ld = results[0]
        assert ld.dose_unit_label == "mg"
        # Single-value protocol, not a range.
        assert ld.is_single_value
        assert ld.min_per_kg == 1.0
        assert ld.min_total == pytest.approx(20.0, rel=1e-4)
        assert ld.min_ml_stock == pytest.approx(4.0, rel=1e-4)

    def test_dog_at_standard_antiemetic_dose_still_shows_lar_par(self) -> None:
        # The lar par scenario is fixed-protocol — it appears regardless
        # of what CRI rate the user entered. A clinician looking at the
        # calculator while choosing a protocol can see both the standard
        # CRI option and the lar par option side by side.
        results = compute_loading_doses(
            drug=METOCLOPRAMIDE,
            weight_kg=20.0,
            species=Species.DOG,
            cri_dose_value=0.04,
        )
        assert len(results) == 1
        # No "matched" value because matches_cri_rate=False.
        assert results[0].matched_per_kg is None
        assert results[0].matched_ml_stock is None

    def test_cat_returns_empty(self) -> None:
        # Lar par is dog-only in Plumb's. compute_loading_doses skips
        # scenarios that don't list the requested species.
        results = compute_loading_doses(
            drug=METOCLOPRAMIDE,
            weight_kg=4.0,
            species=Species.CAT,
            cri_dose_value=0.05,
        )
        assert results == ()

    def test_mg_to_ug_conversion_in_stock_volume(self) -> None:
        # 10 kg dog at 1 mg/kg loading: 10 mg total.
        # Without the mg → µg conversion the stock-volume math would
        # come out 1000x wrong (10 / 5000 = 0.002 mL instead of
        # 10,000 / 5000 = 2.0 mL).
        results = compute_loading_doses(
            drug=METOCLOPRAMIDE,
            weight_kg=10.0,
            species=Species.DOG,
            cri_dose_value=1.0,
        )
        assert results[0].min_ml_stock == pytest.approx(2.0, rel=1e-4)


# ---------------------------------------------------------------------------
# End-to-end POST — full request through the router. This is what catches
# template rendering errors, form-field name mismatches, and integration
# regressions that unit tests can miss.
# ---------------------------------------------------------------------------


class TestMetoclopramidePostCompute:
    def test_get_page_renders(self) -> None:
        r = client.get("/metoclopramide")
        assert r.status_code == 200
        assert "Metoclopramide CRI" in r.text
        # mg/kg/hr unit label must show on the form's dose input.
        assert "mg/kg/hr" in r.text

    def test_post_standard_dose_dog_returns_25_ml_per_hr(self) -> None:
        r = client.post(
            "/metoclopramide/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "dose": "0.05",
                "species": "dog",
                "concentration_ug_per_ml": "40",
                "cri_mode": "standard_bag",
            },
        )
        assert r.status_code == 200
        assert "25.00" in r.text

    def test_post_uses_mg_kg_hr_formula_branch(self) -> None:
        # The formula display has a dedicated mg/kg/hr branch with × 1000.
        # If this regresses, the formula would still show the
        # µg/kg/hr formula (missing the conversion factor) even though
        # the math is computed correctly behind the scenes.
        r = client.post(
            "/metoclopramide/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "dose": "0.05",
                "species": "dog",
                "concentration_ug_per_ml": "40",
                "cri_mode": "standard_bag",
            },
        )
        # The KaTeX source contains \times 1000 for mg/kg/hr.
        assert r"\times 1000" in r.text

    def test_post_lar_par_dog_shows_loading_panel(self) -> None:
        r = client.post(
            "/metoclopramide/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "dose": "1.0",
                "species": "dog",
                "concentration_ug_per_ml": "1000",
                "cri_mode": "standard_bag",
            },
        )
        assert r.status_code == 200
        # Pump rate 20.00 mL/hr.
        assert "20.00" in r.text
        # Loading-dose panel labeled "Laryngeal paralysis".
        assert "Laryngeal paralysis" in r.text
        # 4 mL of stock for a 20 kg dog at 1 mg/kg loading.
        assert "4.00" in r.text

    def test_post_cat_omits_lar_par_panel(self) -> None:
        # The lar par protocol is dog-only. compute_loading_doses
        # returns no scenarios for cats, so the template renders no
        # loading-dose section.
        r = client.post(
            "/metoclopramide/compute",
            data={
                "weight_value": "4",
                "weight_unit": "kg",
                "dose": "0.05",
                "species": "cat",
                "concentration_ug_per_ml": "40",
                "cri_mode": "standard_bag",
            },
        )
        assert r.status_code == 200
        assert "Laryngeal paralysis" not in r.text

    def test_post_cat_shows_other_antiemetics_preferred_warning(self) -> None:
        # The cat-specific warning ("ondansetron, maropitant preferred")
        # must surface so a clinician picking metoclopramide for a cat
        # sees the preferred alternatives without reading the learn
        # module.
        r = client.post(
            "/metoclopramide/compute",
            data={
                "weight_value": "4",
                "weight_unit": "kg",
                "dose": "0.05",
                "species": "cat",
                "concentration_ug_per_ml": "40",
                "cri_mode": "standard_bag",
            },
        )
        assert r.status_code == 200
        # Either the persistent_warning ("preferred in cats") or the
        # specific mention of preferred drugs.
        body = r.text
        assert "preferred" in body and ("ondansetron" in body or "maropitant" in body)

    def test_post_lar_par_dose_triggers_caution_warning(self) -> None:
        # Doses ≥ 0.1 mg/kg/hr exceed the standard antiemetic range
        # and should fire the caution_note flagging the lar par
        # specialized protocol.
        r = client.post(
            "/metoclopramide/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "dose": "1.0",
                "species": "dog",
                "concentration_ug_per_ml": "1000",
                "cri_mode": "standard_bag",
            },
        )
        body = r.text
        # Some surface area for the caution: "exceed" appears in the
        # caution_note copy, or CAUTION fires from the dose_range
        # validation in the engine.
        assert "exceed" in body.lower() or "CAUTION" in body

    def test_post_standard_dose_does_not_trigger_caution(self) -> None:
        # Negative case: a normal antiemetic dose should not trigger
        # the lar par-related caution copy.
        r = client.post(
            "/metoclopramide/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "dose": "0.05",
                "species": "dog",
                "concentration_ug_per_ml": "40",
                "cri_mode": "standard_bag",
            },
        )
        body = r.text
        # No CAUTION-class warning fires for an in-range dose.
        # (The persistent_warning copy is informational and shows
        # for every compute; the caution_note is the threshold flag
        # we're checking is absent here.)
        assert "exceeds" not in body.lower()
