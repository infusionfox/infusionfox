"""Tests for the CRI calculation-mode toggle (STANDARD_BAG and TARGET_PUMP_RATE).

These tests guard against a specific class of clinical-safety bug:
hardcoded unit math (especially the × 60 conversion for µg/kg/min ->
µg/kg/hr) that does not apply to every drug in the SINGLE_DRUG_CRI
family. A bug of this shape silently overdoses by 60× on µg/kg/hr
drugs (fentanyl) if the template assumes µg/kg/min. The tests check
both the engine-computed numbers and the rendered HTML worked example
for internal consistency on every drug in scope.

Drug-by-drug expected math is hand-computed below for one known
input/output pair per drug, in both modes. If the engine or the
template breaks on any one drug, exactly one parametrized test fails
and points at the offending drug + mode + step.
"""

from __future__ import annotations

import pytest

from app.calculators import (
    CalcInputs,
    CriMode,
    Species,
    WeightUnit,
    compute,
)
from app.calculators.drugs import get_drug

# ---------------------------------------------------------------------------
# Drug-by-drug expected math
# ---------------------------------------------------------------------------
#
# Each entry is one verified (input, expected-output) pair. The
# numbers were computed by hand against the underlying CRI equation:
#
#   For µg/kg/min drugs:
#     total_µg_per_hr = weight_kg × dose × 60
#
#   For µg/kg/hr drugs:
#     total_µg_per_hr = weight_kg × dose
#
# Then in TARGET_PUMP_RATE mode:
#     bag_concentration_µg_per_mL = total_µg_per_hr / target_pump_rate_mL_per_hr
#     total_drug_µg = bag_concentration × bag_volume_mL
#     stock_volume_mL = total_drug_µg / stock_µg_per_mL
#
# Stock concentrations come from the catalog (drug.stock_concentration_ug_per_ml):
#   norepinephrine: 1000 µg/mL  (1 mg/mL)
#   epinephrine:    1000 µg/mL  (1 mg/mL)
#   dobutamine:    12500 µg/mL  (12.5 mg/mL)
#   dopamine-cri:  40000 µg/mL  (40 mg/mL)
#   fentanyl:         50 µg/mL  (0.05 mg/mL)

CRI_TEST_CASES = [
    # (slug, dose_unit_str, weight_kg, dose, concentration_ug_per_ml,
    #  target_pump_rate_ml_per_hr, bag_volume_ml,
    #  expected_total_ug_per_hr, expected_bag_concentration_ug_per_ml,
    #  expected_total_drug_mg, expected_stock_volume_ml)
    #
    # Scope: only drugs with supports_target_pump_rate_mode=True. Fentanyl
    # is intentionally excluded because target-pump-rate mode is disabled
    # for it (vasopressor workflow doesn't apply to opioid CRIs). See
    # tests below for explicit fentanyl-no-toggle assertions.

    # Norepinephrine. The article's worked example.
    # 0.1 µg/kg/min × 15 kg × 60 = 90 µg/hr
    # 90 µg/hr ÷ 3 mL/hr = 30 µg/mL
    # 30 µg/mL × 250 mL = 7,500 µg = 7.5 mg
    # 7,500 µg ÷ 1,000 µg/mL = 7.5 mL of 1 mg/mL stock
    pytest.param(
        "norepinephrine", "ug/kg/min", 15.0, 0.1, 16.0,
        3.0, 250.0,
        90.0, 30.0, 7.5, 7.5,
        id="norepinephrine_ug_per_kg_per_min",
    ),

    # Epinephrine. Same family math as norepi.
    # 0.05 µg/kg/min × 20 kg × 60 = 60 µg/hr
    # 60 ÷ 3 = 20 µg/mL bag
    # 20 × 250 = 5,000 µg = 5 mg
    # 5,000 µg ÷ 1,000 µg/mL = 5 mL of 1 mg/mL stock
    pytest.param(
        "epinephrine", "ug/kg/min", 20.0, 0.05, 16.0,
        3.0, 250.0,
        60.0, 20.0, 5.0, 5.0,
        id="epinephrine_ug_per_kg_per_min",
    ),

    # Dobutamine. Higher stock concentration.
    # 5 µg/kg/min × 25 kg × 60 = 7,500 µg/hr
    # 7,500 ÷ 5 = 1,500 µg/mL
    # 1,500 × 500 = 750,000 µg = 750 mg
    # 750,000 µg ÷ 12,500 µg/mL stock = 60 mL of 12.5 mg/mL stock
    pytest.param(
        "dobutamine", "ug/kg/min", 25.0, 5.0, 1000.0,
        5.0, 500.0,
        7500.0, 1500.0, 750.0, 60.0,
        id="dobutamine_ug_per_kg_per_min",
    ),

    # Dopamine-CRI. Highest stock concentration.
    # 5 µg/kg/min × 30 kg × 60 = 9,000 µg/hr
    # 9,000 ÷ 5 = 1,800 µg/mL bag
    # 1,800 × 250 = 450,000 µg = 450 mg
    # 450,000 ÷ 40,000 = 11.25 mL of 40 mg/mL stock
    pytest.param(
        "dopamine-cri", "ug/kg/min", 30.0, 5.0, 1600.0,
        5.0, 250.0,
        9000.0, 1800.0, 450.0, 11.25,
        id="dopamine_cri_ug_per_kg_per_min",
    ),
]


@pytest.mark.parametrize(
    "slug,dose_unit_str,weight_kg,dose,conc_ug_per_ml,"
    "target_rate,bag_vol,"
    "expected_total_hr,expected_bag_conc,expected_total_mg,expected_stock_ml",
    CRI_TEST_CASES,
)
def test_cri_target_pump_rate_math(
    slug, dose_unit_str, weight_kg, dose, conc_ug_per_ml,
    target_rate, bag_vol,
    expected_total_hr, expected_bag_conc, expected_total_mg, expected_stock_ml,
):
    """Engine-level math in TARGET_PUMP_RATE mode is correct per drug.

    Verifies that the dose-unit-aware total_dose_ug_per_hr conversion
    produces the expected number, and that the derived bag prep
    quantities match what a clinician would compute by hand. A failure
    here means compute() got the unit conversion wrong; the worked
    example template downstream will then be wrong too even if it
    branches on dose unit correctly.
    """
    drug = get_drug(slug)
    assert drug is not None, f"Unknown drug slug in test: {slug}"
    assert drug.dose_unit.value == dose_unit_str, (
        f"Test expects {slug} to be {dose_unit_str}, "
        f"but catalog says {drug.dose_unit.value}. "
        "Update the test case if the catalog changed."
    )

    inputs = CalcInputs(
        weight_value=weight_kg,
        weight_unit=WeightUnit.KG,
        dose=dose,
        concentration_ug_per_ml=conc_ug_per_ml,
        species=Species.DOG,
        cri_mode=CriMode.TARGET_PUMP_RATE,
        target_pump_rate_ml_per_hr=target_rate,
        bag_volume_ml=bag_vol,
        stock_concentration_ug_per_ml=drug.stock_concentration_ug_per_ml,
    )

    result = compute(drug, inputs)

    assert result.valid, f"Result invalid for {slug}: warnings={result.warnings}"
    assert result.cri_mode == CriMode.TARGET_PUMP_RATE
    assert result.total_dose_ug_per_hr == pytest.approx(expected_total_hr, rel=1e-9), (
        f"{slug}: total_dose_ug_per_hr "
        f"expected {expected_total_hr}, got {result.total_dose_ug_per_hr}. "
        f"This is the failure that catches the µg/kg/min vs µg/kg/hr bug "
        f"that would cause a 60× overdose on a µg/kg/hr drug."
    )
    assert result.bag_concentration_ug_per_ml == pytest.approx(expected_bag_conc, rel=1e-9), (
        f"{slug}: bag_concentration_ug_per_ml expected {expected_bag_conc}, "
        f"got {result.bag_concentration_ug_per_ml}"
    )
    assert result.total_drug_in_bag_mg == pytest.approx(expected_total_mg, rel=1e-9), (
        f"{slug}: total_drug_in_bag_mg expected {expected_total_mg}, "
        f"got {result.total_drug_in_bag_mg}"
    )
    assert result.stock_volume_to_add_ml == pytest.approx(expected_stock_ml, rel=1e-9), (
        f"{slug}: stock_volume_to_add_ml expected {expected_stock_ml}, "
        f"got {result.stock_volume_to_add_ml}"
    )


@pytest.mark.parametrize(
    "slug,dose_unit_str,weight_kg,dose,conc_ug_per_ml,target_rate,bag_vol,"
    "expected_total_hr,expected_bag_conc,expected_total_mg,expected_stock_ml",
    CRI_TEST_CASES,
)
def test_cri_target_pump_rate_rendered_html(
    fastapi_client,
    slug, dose_unit_str, weight_kg, dose, conc_ug_per_ml,
    target_rate, bag_vol,
    expected_total_hr, expected_bag_conc, expected_total_mg, expected_stock_ml,
):
    """End-to-end HTML render: the worked-example template uses the right
    math per drug. Checks that the µg/kg/min drugs include a × 60 step
    and the µg/kg/hr drugs do NOT, by inspecting the rendered LaTeX.

    A regression on this test means a template was changed in a way
    that puts wrong math in front of a clinician. That is the safety
    bug we are guarding against.
    """
    r = fastapi_client.post(
        f"/{slug}/compute",
        data={
            "species": "dog",
            "weight_value": str(weight_kg),
            "weight_unit": "kg",
            "dose": str(dose),
            "concentration_ug_per_ml": str(conc_ug_per_ml),
            "cri_mode": "target_pump_rate",
            "target_pump_rate_ml_per_hr": str(target_rate),
            "bag_volume_ml": str(bag_vol),
        },
    )
    assert r.status_code == 200, f"{slug} compute failed: {r.status_code}"

    # All drugs render the same four-step structure.
    assert "Step 1: dose per hour" in r.text, f"{slug} missing Step 1 heading"
    assert "Step 2: bag concentration" in r.text, f"{slug} missing Step 2 heading"
    assert "Step 3: total drug in the bag" in r.text, f"{slug} missing Step 3 heading"
    assert "Step 4: volume of stock to draw" in r.text, f"{slug} missing Step 4 heading"

    # Dose-unit-specific Step 1 math.
    if dose_unit_str == "ug/kg/min":
        # Step 1 must include a × 60 conversion. This is the µg/min ->
        # µg/hr step that comes from the dose being per-minute.
        assert "\\frac{60\\,\\cancel{min}}{hr}" in r.text, (
            f"{slug} is {dose_unit_str} but Step 1 is missing the × 60 conversion. "
            "The worked example will under-report total drug per hour by a factor of 60."
        )
    elif dose_unit_str == "ug/kg/hr":
        # Step 1 must NOT include a × 60 conversion. The dose is
        # already per-hour; multiplying by 60 would overdose by 60×.
        assert "\\frac{60\\,\\cancel{min}}{hr}" not in r.text, (
            f"{slug} is {dose_unit_str} but Step 1 contains a × 60 conversion. "
            "This is the safety bug that would tell a clinician to prepare a "
            "60× over-concentrated bag (lethal for fentanyl)."
        )
        # And the kg-cancel pattern should show hr as a surviving (un-cancelled)
        # unit in the denominator, not as a cancelled one.
        assert "\\cancel{kg}\\cdot hr}" in r.text, (
            f"{slug} Step 1 should show hr as an un-cancelled denominator unit. "
            "The dose was per-hour, so hr stays as the surviving time unit."
        )

    # Headline bag concentration matches engine math.
    # Render is %.1f so we format the expected the same way for the match.
    expected_bag_conc_str = f"{expected_bag_conc:.1f}"
    assert (
        f"{expected_bag_conc_str}<span class=\"unit\">µg/mL</span>" in r.text
    ), (
        f"{slug}: rendered bag concentration does not match expected "
        f"{expected_bag_conc_str} µg/mL"
    )


@pytest.mark.parametrize(
    "slug,_unit_str,weight_kg,dose,conc_ug_per_ml,"
    "_target_rate,_bag_vol,"
    "_expected_total_hr,_expected_bag_conc,_expected_total_mg,_expected_stock_ml",
    CRI_TEST_CASES,
)
def test_cri_standard_bag_mode_unchanged_by_toggle_addition(
    fastapi_client,
    slug, _unit_str, weight_kg, dose, conc_ug_per_ml,
    _target_rate, _bag_vol,
    _expected_total_hr, _expected_bag_conc, _expected_total_mg, _expected_stock_ml,
):
    """Regression guard: STANDARD_BAG mode still works on every drug
    that supports the toggle. The mode toggle was added as an opt-in;
    the historical workflow must keep producing the same kind of
    result panel when cri_mode is standard_bag (or absent).
    """
    r = fastapi_client.post(
        f"/{slug}/compute",
        data={
            "species": "dog",
            "weight_value": str(weight_kg),
            "weight_unit": "kg",
            "dose": str(dose),
            "concentration_ug_per_ml": str(conc_ug_per_ml),
            "cri_mode": "standard_bag",
        },
    )
    assert r.status_code == 200, f"{slug} standard-mode compute failed: {r.status_code}"
    assert "CRI rate" in r.text, f"{slug} standard mode missing CRI rate headline"
    assert "Target pump rate &rarr; bag concentration" not in r.text, (
        f"{slug} standard mode is leaking the target-pump-rate mode banner"
    )


# ---------------------------------------------------------------------------
# Fentanyl-specific: target-pump-rate mode must NOT be available.
# ---------------------------------------------------------------------------
#
# Fentanyl is an opioid CRI. Its conventional preparation is a standard
# bag concentration (e.g. 1 µg/mL) with the pump rate floating to deliver
# the dose. Target-pump-rate mode was built for the vasopressor workflow
# (minimize carrier fluid in a fluid-resuscitated patient) and produces
# clinically nonsensical or unsafe preparations when applied to fentanyl
# (excess carrier fluid in small patients, non-standard bag concentrations
# in large patients). The supports_target_pump_rate_mode=False flag on
# the fentanyl config keeps the mode off the page. These tests guard
# the design decision.


def test_fentanyl_form_has_no_mode_toggle(fastapi_client):
    """Fentanyl page must NOT render the calculation-mode toggle.

    A regression here means the supports_target_pump_rate_mode flag
    stopped being respected by the form template, and a clinician
    would see an opt-in to a mode that produces unsafe fentanyl
    preparations.
    """
    r = fastapi_client.get("/fentanyl")
    assert r.status_code == 200
    # No mode radio INPUT elements should be present in the form.
    # (The string `name="cri_mode"` may appear inside a JS querySelector,
    # which is harmless; we want to assert no actual <input> exists.)
    assert '<input type="radio" name="cri_mode"' not in r.text, (
        "Fentanyl form is rendering a cri_mode radio input. The mode "
        "toggle should be hidden on fentanyl because target-pump-rate "
        "mode produces unsafe preparations for opioid CRIs."
    )
    # The cri-mode-toggle wrapper div should also not be rendered.
    assert 'class="field cri-mode-toggle"' not in r.text
    # No target-pump-rate inputs either.
    assert 'name="target_pump_rate_ml_per_hr"' not in r.text
    assert 'name="bag_volume_ml"' not in r.text


def test_fentanyl_post_with_target_pump_rate_falls_back_to_standard(fastapi_client):
    """A POST to fentanyl/compute with cri_mode=target_pump_rate is
    treated as standard_bag (defense in depth).

    The form template does not render the toggle on fentanyl, so a
    POST with target_pump_rate is either a stale browser tab (unlikely)
    or a malformed / adversarial request. The route handler must NOT
    return a target-pump-rate result panel; it must fall back to
    standard_bag and treat the target-mode fields as unused.
    """
    r = fastapi_client.post(
        "/fentanyl/compute",
        data={
            "species": "dog",
            "weight_value": "15",
            "weight_unit": "kg",
            "dose": "3",
            "concentration_ug_per_ml": "10",
            "cri_mode": "target_pump_rate",
            "target_pump_rate_ml_per_hr": "50",
            "bag_volume_ml": "250",
        },
    )
    assert r.status_code == 200
    # Standard-mode result panel, not the target-pump-rate variant.
    assert "CRI rate" in r.text
    assert "Target pump rate &rarr; bag concentration" not in r.text
    assert "Bag preparation" not in r.text


# ---------------------------------------------------------------------------
# Low pump-rate syringe-pump warning. Fires regardless of drug.
# ---------------------------------------------------------------------------


def test_low_pump_rate_warning_fires_below_2_ml_per_hr(fastapi_client):
    """A CRI computation that produces a pump rate below 2 mL/hr
    surfaces a warning suggesting bag dilution or a syringe pump.

    This is a pump-hardware safety warning: standard IV infusion pumps
    lose accuracy below 1-2 mL/hr, so a clinician computing a rate in
    that range should know to either re-prep the bag at a lower
    concentration or switch to a syringe pump.
    """
    # Fentanyl 3 µg/kg/hr × 5 kg = 15 µg/hr.
    # On the default 50 µg/mL stock: 15 / 50 = 0.3 mL/hr (below 2).
    r = fastapi_client.post(
        "/fentanyl/compute",
        data={
            "species": "cat",
            "weight_value": "5",
            "weight_unit": "kg",
            "dose": "3",
            "concentration_ug_per_ml": "50",
            "cri_mode": "standard_bag",
        },
    )
    assert r.status_code == 200
    assert "below 2 mL/hr" in r.text, (
        "Low pump-rate warning did not fire on a sub-2 mL/hr calculation."
    )
    assert "Dilute the bag" in r.text or "syringe pump" in r.text


def test_low_pump_rate_warning_does_not_fire_at_normal_rates(fastapi_client):
    """The syringe-pump warning must NOT fire on rates above 2 mL/hr.

    A false positive at every normal rate would dilute the signal of
    the warning when it does matter.
    """
    # Norepi 0.5 µg/kg/min × 30 kg × 60 = 900 µg/hr.
    # On 16 µg/mL bag: 900 / 16 = 56.25 mL/hr (well above 2).
    r = fastapi_client.post(
        "/norepinephrine/compute",
        data={
            "species": "dog",
            "weight_value": "30",
            "weight_unit": "kg",
            "dose": "0.5",
            "concentration_ug_per_ml": "16",
            "cri_mode": "standard_bag",
        },
    )
    assert r.status_code == 200
    assert "below 2 mL/hr" not in r.text, (
        "Low pump-rate warning fired on a normal rate (~56 mL/hr). "
        "This would dilute the signal of the warning when it matters."
    )


def test_cri_mode_defaults_to_standard_bag_when_omitted(fastapi_client):
    """A POST without a cri_mode field is treated as standard_bag.

    This protects older clients (or test fixtures) that don't know
    about the mode field. Any default behavior change here would be
    a silent UX shift on every CRI calculator.
    """
    r = fastapi_client.post(
        "/norepinephrine/compute",
        data={
            "species": "dog",
            "weight_value": "15",
            "weight_unit": "kg",
            "dose": "0.1",
            "concentration_ug_per_ml": "16",
            # No cri_mode field.
        },
    )
    assert r.status_code == 200
    assert "CRI rate" in r.text, "Default mode should render standard CRI rate panel"


def test_cri_mode_unknown_value_falls_back_to_standard(fastapi_client):
    """A garbled cri_mode value falls back to standard_bag.

    A malformed field must not flip the user into the alternate-output
    panel without their consent. The route handler catches ValueError
    on the enum lookup and defaults to STANDARD_BAG.
    """
    r = fastapi_client.post(
        "/norepinephrine/compute",
        data={
            "species": "dog",
            "weight_value": "15",
            "weight_unit": "kg",
            "dose": "0.1",
            "concentration_ug_per_ml": "16",
            "cri_mode": "this_is_not_a_real_mode",
        },
    )
    assert r.status_code == 200
    assert "CRI rate" in r.text
    assert "Target pump rate &rarr; bag concentration" not in r.text


def test_cri_target_pump_rate_mode_missing_inputs_returns_invalid(fastapi_client):
    """Missing target pump rate or bag volume produces the invalid-input
    placeholder, not a result panel with garbage numbers."""
    r = fastapi_client.post(
        "/norepinephrine/compute",
        data={
            "species": "dog",
            "weight_value": "15",
            "weight_unit": "kg",
            "dose": "0.1",
            "concentration_ug_per_ml": "16",
            "cri_mode": "target_pump_rate",
            # target_pump_rate_ml_per_hr and bag_volume_ml omitted
        },
    )
    assert r.status_code == 200
    # The invalid-input partial does not render the bag-prep card.
    assert "Bag preparation" not in r.text
