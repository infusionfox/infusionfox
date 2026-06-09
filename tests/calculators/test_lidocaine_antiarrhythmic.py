"""Tests for lidocaine antiarrhythmic CRI at /lidocaine-antiarrhythmic.

Distinguished from the existing /lidocaine analgesia calculator by
slug, display name ("Lidocaine CRI · Antiarrhythmic"), category
(Cardiology), and dose ranges. Both routes coexist as peers — they
cover different indications with different safety surface.

Critical species asymmetry: cats are markedly more sensitive than
dogs to both CNS toxicity and cardiovascular depression. Loading dose
is ~8× lower in cats (0.25–0.75 mg/kg vs 2–8 mg/kg in dogs). CRI
range is also lower in cats (10–40 vs 25–80 µg/kg/min), with a
correspondingly lower caution threshold (20 vs 75).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import (
    DRUGS,
    LIDOCAINE,
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


class TestLidocaineAntiarrhythmicRegistration:
    def test_in_catalog(self):
        assert LIDOCAINE in DRUGS
        assert get_drug("lidocaine-antiarrhythmic") is LIDOCAINE

    def test_slug_distinguishes_from_analgesia_lidocaine(self):
        # The slug is intentionally "lidocaine-antiarrhythmic" to
        # avoid collision with the existing custom-module /lidocaine
        # (analgesia-focused, dog-only, 1.5–3 mg/kg/hr range).
        assert LIDOCAINE.slug == "lidocaine-antiarrhythmic"

    def test_display_name_carries_indication(self):
        # The display name explicitly says "Antiarrhythmic" so the
        # catalog and calc-page header distinguish from the analgesia
        # use case.
        assert "Antiarrhythmic" in LIDOCAINE.display_name

    def test_in_cardiology(self):
        assert LIDOCAINE.category == "Cardiology"
        assert LIDOCAINE in drugs_by_category()["Cardiology"]


class TestLidocaineDoseConfig:
    def test_dose_unit(self):
        assert LIDOCAINE.dose_unit == DoseUnit.UG_PER_KG_PER_MIN

    def test_dog_range(self):
        rng = LIDOCAINE.dose_ranges[Species.DOG]
        assert rng.min == 25.0
        assert rng.max == 80.0
        assert rng.caution_threshold == 75.0

    def test_cat_range_much_lower(self):
        # Cat range is meaningfully lower than dog range — clearance
        # difference is dramatic, not subtle.
        rng = LIDOCAINE.dose_ranges[Species.CAT]
        assert rng.min == 10.0
        assert rng.max == 40.0
        # Cat caution threshold (20) is markedly lower than dog's (75).
        assert rng.caution_threshold == 20.0


class TestLidocaineSpeciesAsymmetry:
    def test_cat_warning_emphasizes_marked_sensitivity(self):
        warning = LIDOCAINE.dose_ranges[Species.CAT].persistent_warning
        # The "MARKEDLY MORE SENSITIVE" caps is intentional.
        assert "MARKEDLY MORE SENSITIVE" in warning

    def test_cat_warning_mentions_avoiding_in_cats(self):
        warning = LIDOCAINE.dose_ranges[Species.CAT].persistent_warning.lower()
        # Many cardiologists prefer alternatives — this needs to be
        # surfaced so clinicians consider alternatives.
        assert "avoid lidocaine cri in cats" in warning

    def test_cat_warning_mentions_alternatives(self):
        warning = LIDOCAINE.dose_ranges[Species.CAT].persistent_warning.lower()
        # Sotalol, magnesium are cat-friendlier alternatives.
        assert "sotalol" in warning or "magnesium" in warning

    def test_loading_dose_has_dramatic_species_asymmetry(self):
        ld = LIDOCAINE.loading_doses[0]
        dog_range = ld.dose_per_kg[Species.DOG]
        cat_range = ld.dose_per_kg[Species.CAT]
        # Dog: 2-8 mg/kg. Cat: 0.25-0.75 mg/kg. Cat's max (0.75) is
        # less than dog's MIN (2.0) — the species difference is real
        # and the test pins it so a future edit can't accidentally
        # bring cat dosing up to dog levels.
        assert cat_range[1] < dog_range[0]

    def test_loading_note_calls_out_real_species_difference(self):
        ld = LIDOCAINE.loading_doses[0]
        # The 4× difference is intentional, not a typo.
        assert "not a typo" in ld.note.lower() or "real" in ld.note.lower()


class TestLidocaineSafetyLanguage:
    def test_dog_warning_mentions_cns_signs(self):
        warning = LIDOCAINE.dose_ranges[Species.DOG].persistent_warning.lower()
        # CNS toxicity signs that should prompt pause.
        for sign in ("tremor", "seizure"):
            assert sign in warning

    def test_dog_warning_mentions_hepatic_dysfunction(self):
        warning = LIDOCAINE.dose_ranges[Species.DOG].persistent_warning.lower()
        assert "hepatic" in warning

    def test_dilution_note_mentions_no_epinephrine(self):
        # Plumb's: lidocaine WITH epinephrine is for local
        # infiltration; NEVER use IV.
        note = LIDOCAINE.dilution_note.lower()
        assert "epinephrine" in note
        assert "not" in note or "preservative-free" in note


class TestLidocaineMath:
    def test_canonical_20kg_dog(self):
        # 20 kg × 50 µg/kg/min × 60 ÷ 10000 µg/mL = 6.0 mL/hr.
        result = compute(
            LIDOCAINE,
            CalcInputs(
                weight_value=20.0,
                weight_unit=WeightUnit.KG,
                dose=50.0,
                concentration_ug_per_ml=10000.0,
                species=Species.DOG,
            ),
        )
        assert result.valid
        assert result.ml_per_hr_pump == pytest.approx(6.0)

    def test_large_dog_undiluted_stock(self):
        # 30 kg × 50 × 60 / 20000 = 4.5 mL/hr on undiluted 2% stock.
        result = compute(
            LIDOCAINE,
            CalcInputs(
                weight_value=30.0,
                weight_unit=WeightUnit.KG,
                dose=50.0,
                concentration_ug_per_ml=20000.0,
                species=Species.DOG,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(4.5)

    def test_cat_conservative_dose(self):
        # 4 kg cat × 15 µg/kg/min × 60 ÷ 4000 = 0.9 mL/hr (below
        # 2 mL/hr floor, illustrating why cats need dilute prep AND
        # often syringe pump target mode).
        result = compute(
            LIDOCAINE,
            CalcInputs(
                weight_value=4.0,
                weight_unit=WeightUnit.KG,
                dose=15.0,
                concentration_ug_per_ml=4000.0,
                species=Species.CAT,
            ),
        )
        assert result.ml_per_hr_pump == pytest.approx(0.9)


class TestLidocaineAutoRecommendation:
    def test_three_tiers(self):
        assert len(LIDOCAINE.concentration_presets) == 3
        concs = sorted(
            [p.concentration_ug_per_ml for p in LIDOCAINE.concentration_presets],
            reverse=True,
        )
        assert concs == [20000, 10000, 4000]


class TestLidocaineRoute:
    def test_form_renders_at_new_slug(self):
        r = client.get("/lidocaine-antiarrhythmic")
        assert r.status_code == 200
        body = r.text
        assert "<h1>Lidocaine CRI · Antiarrhythmic</h1>" in body
        assert ">Cardiology<" in body

    def test_compute_endpoint_works(self):
        # Critical regression check: confirms the new route doesn't
        # collide with the existing /lidocaine (analgesia) calculator's
        # /lidocaine/compute endpoint. Two distinct routes, both
        # functional.
        r = client.post(
            "/lidocaine-antiarrhythmic/compute",
            data={
                "weight_value": "20",
                "weight_unit": "kg",
                "species": "dog",
                "dose": "50",
                "concentration_ug_per_ml": "10000",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        assert "6.00" in r.text

    def test_existing_lidocaine_analgesia_route_unaffected(self):
        # The existing /lidocaine custom-module analgesia calculator
        # must continue to work — the new route is additive, not a
        # replacement.
        r = client.get("/lidocaine")
        assert r.status_code == 200
        # The page's calc-header eyebrow should NOT be Cardiology —
        # that's the new antiarrhythmic calculator's category. The
        # "Cardiology" string appears in the catalog nav drawer on
        # every page; that's not what's being checked here. The
        # specific eyebrow markup on the calc page is what matters.
        assert (
            '<div class="eyebrow">Cardiology</div>' not in r.text
            and '<div class="eyebrow"\n            >Cardiology</div>' not in r.text
        )


class TestLidocaineCrossReference:
    """The antiarrhythmic calculator references the analgesia
    calculator (and vice-versa eventually) so clinicians can find
    the right indication."""

    def test_indications_references_analgesia_route(self):
        # Cross-reference to /lidocaine for the analgesic CRI use.
        assert "/lidocaine" in LIDOCAINE.indications_summary


class TestLidocainePrintSupport:
    def test_supports_print(self):
        assert LIDOCAINE.supports_print is True

    def test_form_renders_print_button(self):
        body = client.get("/lidocaine-antiarrhythmic").text
        assert "calculator-print-btn" in body
