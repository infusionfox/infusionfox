"""
Tests for the blood gas interpretation calculator.

Source: DiBartola SP, ed. Fluid, Electrolyte, and Acid-Base Disorders in
Small Animal Practice. 4th ed. Elsevier; 2012. Chapter 9 (reference
ranges, anion gap interpretation), Chapter 12 (compensation rules,
Table 12-2; cat-specific caveats, p. 304). The dog compensation rules
of thumb originate in de Morais HSA, DiBartola SP. Ventilatory and
metabolic compensation in dogs with acid-base disturbances.
J Vet Emerg Crit Care 1991;1:39-49.

Compensation rules encoded by the calculator (DiBartola Table 12-2):

    Dog metabolic acidosis:      PCO2 falls 0.7 mm Hg / 1 mEq/L fall HCO3
    Dog metabolic alkalosis:     PCO2 rises 0.7 mm Hg / 1 mEq/L rise HCO3
    Dog acute resp acidosis:     HCO3 rises 0.15 mEq/L / 1 mm Hg rise PCO2
    Dog chronic resp acidosis:   HCO3 rises 0.35 mEq/L / 1 mm Hg rise PCO2
    Dog acute resp alkalosis:    HCO3 falls 0.25 mEq/L / 1 mm Hg fall PCO2
    Dog chronic resp alkalosis:  HCO3 falls 0.55 mEq/L / 1 mm Hg fall PCO2

Cat-specific behavior (DiBartola Ch. 12, p. 304):

    Cat metabolic acidosis:      NO PREDICTED COMPENSATION ("formulas for
                                 dogs or humans should not be extrapolated
                                 for use in cats"). The calculator must
                                 NOT return an expected PCO2.
    Cat chronic resp acidosis:   UNKNOWN per Table 12-2. The calculator
                                 must NOT return an expected HCO3.

Reference ranges (DiBartola Ch. 9, Table 9-1, p. 241):

    Dog arterial:  pH 7.351-7.463, PCO2 30.8-42.8, HCO3 18.8-25.6
    Cat arterial:  pH 7.310-7.462, PCO2 25.2-36.8, HCO3 14.4-21.6

Anion gap reference (DiBartola Ch. 9, p. 244):

    Dog: 13-25 mEq/L (mean ~19)
    Cat: 17-31 mEq/L (mean ~24)
"""

from __future__ import annotations

import pytest

from app.calculators.blood_gas import (
    Acuity,
    BloodGasInputs,
    PrimaryDisturbance,
    SampleType,
    Species,
    compute_blood_gas,
)


def _inputs(
    *,
    species: Species = Species.DOG,
    sample: SampleType = SampleType.ARTERIAL,
    acuity: Acuity = Acuity.ACUTE,
    pH: float = 7.40,
    pco2: float = 37.0,
    hco3: float = 22.0,
    na: float = 0.0,
    cl: float = 0.0,
) -> BloodGasInputs:
    return BloodGasInputs(
        species=species,
        sample=sample,
        acuity=acuity,
        pH=pH,
        pco2_mm_hg=pco2,
        hco3_meq_per_l=hco3,
        na_meq_per_l=na,
        cl_meq_per_l=cl,
    )


# ---------------------------------------------------------------------------
# Primary disturbance identification
# ---------------------------------------------------------------------------


class TestPrimaryDisturbance:
    def test_normal_values_dog(self):
        """pH 7.40, PCO2 37, HCO3 22 (all dog midpoints) => no disturbance."""
        r = compute_blood_gas(_inputs(pH=7.40, pco2=37, hco3=22))
        assert r.valid is True
        assert r.primary == PrimaryDisturbance.NORMAL

    def test_metabolic_acidosis_dog(self):
        """Low pH, low HCO3 => metabolic acidosis (diarrhea / DKA pattern)."""
        r = compute_blood_gas(_inputs(pH=7.20, pco2=25, hco3=12))
        assert r.primary == PrimaryDisturbance.METABOLIC_ACIDOSIS
        assert r.is_acidemic is True

    def test_metabolic_alkalosis_dog(self):
        """High pH, high HCO3 => metabolic alkalosis (vomiting pattern)."""
        r = compute_blood_gas(_inputs(pH=7.55, pco2=45, hco3=32))
        assert r.primary == PrimaryDisturbance.METABOLIC_ALKALOSIS
        assert r.is_alkalemic is True

    def test_respiratory_acidosis_dog(self):
        """Low pH, high PCO2 => respiratory acidosis (hypoventilation)."""
        r = compute_blood_gas(_inputs(pH=7.25, pco2=65, hco3=24))
        assert r.primary == PrimaryDisturbance.RESPIRATORY_ACIDOSIS
        assert r.is_acidemic is True

    def test_respiratory_alkalosis_dog(self):
        """High pH, low PCO2 => respiratory alkalosis (hyperventilation)."""
        r = compute_blood_gas(_inputs(pH=7.55, pco2=22, hco3=22))
        assert r.primary == PrimaryDisturbance.RESPIRATORY_ALKALOSIS
        assert r.is_alkalemic is True


# ---------------------------------------------------------------------------
# Compensation rules: dog (DiBartola Table 12-2)
# ---------------------------------------------------------------------------


class TestDogCompensationMetabolicAcidosis:
    """Dog rule: PCO2 falls 0.7 mm Hg per 1 mEq/L fall in HCO3-."""

    def test_simple_compensation(self):
        """HCO3 dropped 10 (22 -> 12); expected PCO2 drop = 7; expected PCO2 = 30."""
        r = compute_blood_gas(_inputs(pH=7.25, pco2=30, hco3=12))
        assert r.compensation is not None
        assert r.compensation.expected == pytest.approx(30, abs=0.5)
        assert r.compensation.is_simple is True

    def test_inadequate_compensation_flagged(self):
        """PCO2 sits at 40 (normal) when HCO3 is 12. Compensation is missing."""
        r = compute_blood_gas(_inputs(pH=7.10, pco2=40, hco3=12))
        # Expected ~30, observed 40 → outside ±2 → not simple
        assert r.compensation.is_simple is False

    def test_overcompensation_flagged_as_mixed(self):
        """PCO2 of 15 when HCO3 is 8 (DKA + sepsis hyperventilation pattern)."""
        r = compute_blood_gas(_inputs(pH=7.10, pco2=15, hco3=8))
        # baseline HCO3 ~22; observed dropped 14; expected PCO2 drop = 9.8;
        # expected PCO2 ~ 27. Observed 15 < expected_lo. Not simple.
        assert r.compensation.is_simple is False


class TestDogCompensationMetabolicAlkalosis:
    """Dog rule: PCO2 rises 0.7 mm Hg per 1 mEq/L rise in HCO3-."""

    def test_simple_compensation(self):
        """HCO3 rose 10 (22 -> 32); expected PCO2 rise = 7; expected PCO2 = 44."""
        r = compute_blood_gas(_inputs(pH=7.50, pco2=44, hco3=32))
        assert r.compensation.expected == pytest.approx(44, abs=0.5)
        assert r.compensation.is_simple is True


class TestDogCompensationAcuteRespiratoryAcidosis:
    """Dog acute resp acidosis: HCO3 rises 0.15 mEq/L per 1 mm Hg rise PCO2."""

    def test_simple_compensation(self):
        """PCO2 rose 28 (37 -> 65); expected HCO3 rise = 4.2; expected HCO3 = 26."""
        r = compute_blood_gas(
            _inputs(pH=7.25, pco2=65, hco3=26, acuity=Acuity.ACUTE)
        )
        assert r.compensation.expected == pytest.approx(26, abs=0.5)
        assert r.compensation.is_simple is True


class TestDogCompensationChronicRespiratoryAcidosis:
    """Dog chronic resp acidosis: HCO3 rises 0.35 mEq/L per 1 mm Hg rise PCO2."""

    def test_chronic_uses_higher_coefficient(self):
        """PCO2 rose ~18 (36.8 -> 55); chronic expected rise = 6.4; HCO3 ~ 28.6.
        Use a mildly acidemic pH so primary is identified as resp acidosis."""
        r = compute_blood_gas(
            _inputs(pH=7.34, pco2=55, hco3=28, acuity=Acuity.CHRONIC)
        )
        assert r.primary == PrimaryDisturbance.RESPIRATORY_ACIDOSIS
        assert r.compensation.expected == pytest.approx(28.6, abs=0.5)
        assert r.compensation.is_simple is True

    def test_chronic_coefficient_differs_from_acute(self):
        """Same PCO2 elevation, different acuity, different expected HCO3."""
        acute = compute_blood_gas(
            _inputs(pH=7.25, pco2=55, hco3=22, acuity=Acuity.ACUTE)
        )
        chronic = compute_blood_gas(
            _inputs(pH=7.25, pco2=55, hco3=22, acuity=Acuity.CHRONIC)
        )
        assert acute.primary == PrimaryDisturbance.RESPIRATORY_ACIDOSIS
        assert chronic.primary == PrimaryDisturbance.RESPIRATORY_ACIDOSIS
        assert acute.compensation.expected != chronic.compensation.expected
        assert chronic.compensation.expected > acute.compensation.expected


class TestDogCompensationRespiratoryAlkalosis:
    """Dog acute resp alkalosis: HCO3 falls 0.25 mEq/L per 1 mm Hg fall PCO2.
    Dog chronic resp alkalosis: HCO3 falls 0.55 mEq/L per 1 mm Hg fall PCO2."""

    def test_acute_compensation(self):
        """PCO2 dropped 15 (37 -> 22); acute expected HCO3 drop = 3.75; HCO3 = 18."""
        r = compute_blood_gas(
            _inputs(pH=7.55, pco2=22, hco3=18, acuity=Acuity.ACUTE)
        )
        assert r.compensation.expected == pytest.approx(18, abs=0.5)
        assert r.compensation.is_simple is True

    def test_chronic_coefficient_drops_more(self):
        chronic = compute_blood_gas(
            _inputs(pH=7.50, pco2=22, hco3=14, acuity=Acuity.CHRONIC)
        )
        acute = compute_blood_gas(
            _inputs(pH=7.50, pco2=22, hco3=14, acuity=Acuity.ACUTE)
        )
        assert chronic.primary == PrimaryDisturbance.RESPIRATORY_ALKALOSIS
        assert acute.primary == PrimaryDisturbance.RESPIRATORY_ALKALOSIS
        # Chronic predicts MORE HCO3 drop (lower expected HCO3)
        assert chronic.compensation.expected < acute.compensation.expected


# ---------------------------------------------------------------------------
# Cat-specific caveats (DiBartola Ch. 12 p. 304)
# ---------------------------------------------------------------------------


class TestCatMetabolicAcidosisCaveat:
    """The most safety-critical rule in the calculator.

    DiBartola Ch. 12, p. 304: 'formulas for dogs or humans should not
    be extrapolated for use in cats.' The calculator must NOT return
    an expected PCO2 for a cat with metabolic acidosis.
    """

    def test_no_expected_pco2_for_cat_metabolic_acidosis(self):
        r = compute_blood_gas(
            _inputs(species=Species.CAT, pH=7.22, pco2=33, hco3=14)
        )
        assert r.primary == PrimaryDisturbance.METABOLIC_ACIDOSIS
        assert r.compensation is not None
        # The defining contract: no expected value, no simple/mixed judgment.
        assert r.compensation.expected is None
        assert r.compensation.is_simple is None

    def test_cat_metabolic_acidosis_emits_caveat_warning(self):
        """The DiBartola Ch. 12 caveat must surface as a top-level warning."""
        r = compute_blood_gas(
            _inputs(species=Species.CAT, pH=7.22, pco2=33, hco3=14)
        )
        warnings_text = " ".join(r.warnings)
        assert "cat" in warnings_text.lower() or "feline" in warnings_text.lower()
        # The page number citation must be present for traceability.
        assert "DiBartola" in warnings_text


class TestCatChronicRespiratoryAcidosisUnknown:
    """DiBartola Table 12-2 lists chronic resp acidosis as Unknown for cats.
    The calculator must NOT substitute the dog value."""

    def test_no_expected_hco3_for_cat_chronic_resp_acidosis(self):
        r = compute_blood_gas(
            _inputs(species=Species.CAT, pH=7.30, pco2=55, hco3=28, acuity=Acuity.CHRONIC)
        )
        assert r.primary == PrimaryDisturbance.RESPIRATORY_ACIDOSIS
        assert r.compensation.expected is None
        assert r.compensation.is_simple is None


# ---------------------------------------------------------------------------
# Sample-type reference range switching
# ---------------------------------------------------------------------------


class TestSampleTypeReferenceRanges:
    def test_venous_sample_uses_different_ranges(self):
        """Venous samples have different pH/PCO2 reference ranges than arterial."""
        arterial = compute_blood_gas(
            _inputs(sample=SampleType.ARTERIAL, pH=7.40, pco2=37, hco3=22)
        )
        venous = compute_blood_gas(
            _inputs(sample=SampleType.VENOUS, pH=7.40, pco2=37, hco3=22)
        )
        assert arterial.ref_pco2.lo != venous.ref_pco2.lo or arterial.ref_pco2.hi != venous.ref_pco2.hi


# ---------------------------------------------------------------------------
# Anion gap
# ---------------------------------------------------------------------------


class TestAnionGap:
    """AG = Na - (Cl + HCO3). DiBartola Ch. 9, p. 244."""

    def test_anion_gap_math(self):
        """Na 145, Cl 110, HCO3 22 => AG = 13."""
        r = compute_blood_gas(_inputs(pH=7.40, pco2=37, hco3=22, na=145, cl=110))
        assert r.anion_gap == pytest.approx(13.0, abs=0.1)

    def test_anion_gap_skipped_when_na_zero(self):
        """If Na is missing (0), AG is not computed."""
        r = compute_blood_gas(_inputs(pH=7.40, pco2=37, hco3=22, na=0, cl=110))
        assert r.anion_gap is None

    def test_anion_gap_skipped_when_cl_zero(self):
        r = compute_blood_gas(_inputs(pH=7.40, pco2=37, hco3=22, na=145, cl=0))
        assert r.anion_gap is None

    def test_high_ag_metabolic_acidosis_dka_pattern(self):
        """DKA: Na 140, Cl 100, HCO3 8 => AG = 32 (high)."""
        r = compute_blood_gas(
            _inputs(pH=7.10, pco2=15, hco3=8, na=140, cl=100)
        )
        assert r.anion_gap == pytest.approx(32, abs=0.5)
        assert r.anion_gap_high is True

    def test_normal_ag_metabolic_acidosis_diarrhea_pattern(self):
        """Hyperchloremic acidosis: Na 145, Cl 122, HCO3 12 => AG = 11 (normal)."""
        r = compute_blood_gas(
            _inputs(pH=7.25, pco2=28, hco3=12, na=145, cl=122)
        )
        assert r.anion_gap == pytest.approx(11, abs=0.5)
        assert r.anion_gap_high is False

    def test_cat_anion_gap_uses_higher_reference(self):
        """Cat AG reference is 17-31 (vs dog 13-25). AG of 22 is normal in cat."""
        r = compute_blood_gas(
            _inputs(species=Species.CAT, pH=7.40, pco2=30, hco3=18, na=152, cl=112)
        )
        assert r.anion_gap == pytest.approx(22, abs=0.5)
        # 22 is within the cat reference range 17-31
        assert r.anion_gap_high is False


# ---------------------------------------------------------------------------
# Source attribution (per CONTRIBUTING.md rule)
# ---------------------------------------------------------------------------


class TestSourceAttribution:
    def test_dibartola_source_present(self):
        r = compute_blood_gas(_inputs(pH=7.25, pco2=28, hco3=12))
        citations = " ".join(s.citation for s in r.sources)
        assert "DiBartola" in citations

    def test_de_morais_dibartola_1991_source_present(self):
        """The 1991 JVECC paper is the primary source for the compensation rules."""
        r = compute_blood_gas(_inputs(pH=7.25, pco2=28, hco3=12))
        citations = " ".join(s.citation for s in r.sources)
        assert "de Morais" in citations or "1991" in citations


# ---------------------------------------------------------------------------
# Route-level: placeholder text on initial GET and on bad input
# ---------------------------------------------------------------------------


class TestPlaceholderText:
    """The blood gas calculator has no patient weight input. The shared
    placeholder partial defaults to 'Enter a patient weight to see the
    result.', which is wrong here. Both the initial GET render and the
    HTMX response for unparseable inputs must override the default with
    a message that names the actual required fields (pH, PCO2, HCO3).

    A user landing on the page and seeing 'Enter a patient weight'
    above pH/PCO2/HCO3 inputs would reasonably conclude the page is
    broken; the form even hides the field they're being told to fill.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    def test_initial_get_does_not_mention_weight(self, client):
        r = client.get("/blood-gas")
        assert r.status_code == 200
        assert "patient weight" not in r.text.lower(), (
            "blood gas page must not show the default 'Enter a patient "
            "weight' placeholder; it has no weight input"
        )

    def test_initial_get_names_actual_required_inputs(self, client):
        r = client.get("/blood-gas")
        # Match the visible character forms used in the placeholder,
        # not the form field names. Subscript 2/3 may render as ASCII
        # depending on font; check for the unambiguous tokens.
        assert "Enter pH" in r.text
        assert "PCO" in r.text and "HCO" in r.text

    def test_empty_compute_response_does_not_mention_weight(self, client):
        r = client.post(
            "/blood-gas/compute",
            data={
                "species": "dog",
                "sample": "arterial",
                "acuity": "acute",
                "pH": "",
                "pco2_mm_hg": "",
                "hco3_meq_per_l": "",
            },
        )
        assert r.status_code == 200
        assert "patient weight" not in r.text.lower()
        assert "Enter pH" in r.text


# ---------------------------------------------------------------------------
# Route-level: species/sample-aware reference range hints on the form
# ---------------------------------------------------------------------------


class TestReferenceRangeHints:
    """The form renders all four species/sample reference range hints
    under each numeric input (pH, PCO2, HCO3). CSS `:has()` shows only
    the matching one based on which species + sample radios are checked
    — no JS, no full-form re-render on radio change. This test pins
    the server-rendered HTML; the visual toggle is verified separately
    by the headless render in the project's manual QA path.

    Values come from DiBartola Ch. 9, Table 9-1 (p. 241). The
    calculator engine owns the numbers (DOG_ARTERIAL, DOG_VENOUS,
    CAT_ARTERIAL, CAT_VENOUS); if those ever change, the hints update
    automatically without a template edit.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    def test_all_twelve_range_hints_render(self, client):
        """Three numeric inputs × four species/sample combos = 12 hints."""
        import re

        r = client.get("/blood-gas")
        assert r.status_code == 200
        contexts = re.findall(
            r'class="help bg-range" data-bg-context="([^"]+)"', r.text
        )
        assert len(contexts) == 12, (
            f"expected 12 .bg-range elements (3 inputs × 4 contexts), "
            f"got {len(contexts)}"
        )
        # Each context appears exactly 3 times (once per input).
        from collections import Counter

        counts = Counter(contexts)
        assert dict(counts) == {
            "dog-arterial": 3,
            "dog-venous": 3,
            "cat-arterial": 3,
            "cat-venous": 3,
        }, counts

    def test_dog_arterial_ph_range_matches_engine_values(self, client):
        """The dog arterial pH range shown on the form matches the
        engine's DOG_ARTERIAL["pH"] range. If a future contributor
        changes the engine numbers, this asserts the form updates
        with them (single source of truth)."""
        from app.calculators.blood_gas import DOG_ARTERIAL

        r = client.get("/blood-gas")
        lo = f"{DOG_ARTERIAL['pH'].lo:.3f}"
        hi = f"{DOG_ARTERIAL['pH'].hi:.3f}"
        assert lo in r.text
        assert hi in r.text
        # And it's labeled (dog, arterial), not just a bare number
        assert f"{lo}\u2013{hi}" in r.text or f"{lo}-{hi}" in r.text

    def test_cat_venous_hco3_range_matches_engine_values(self, client):
        from app.calculators.blood_gas import CAT_VENOUS

        r = client.get("/blood-gas")
        lo = f"{CAT_VENOUS['HCO3'].lo:.1f}"
        hi = f"{CAT_VENOUS['HCO3'].hi:.1f}"
        assert lo in r.text
        assert hi in r.text
        assert "(cat, venous)" in r.text

    def test_form_carries_bg_form_class_for_css_has_scoping(self, client):
        """The :has() CSS rules in app.css scope to .bg-form to avoid
        affecting other forms on the page. If the template loses this
        class, all four hints would render simultaneously under each
        input — degraded but not broken; pin it so a refactor doesn't
        silently reduce the page to that state."""
        r = client.get("/blood-gas")
        assert 'class="bg-form"' in r.text


