"""Fentanyl loading-dose surfacing in the result panel.

Two scenarios per Plumb's, surfaced as separate panels alongside the
CRI rate output:

1. Perioperative analgesia (matches_cri_rate=True):
   - Dogs: 2–10 µg/kg
   - Cats: 5 µg/kg (single value, not a range)
   - Shows a matched value (= user's CRI dose numerically) when
     STANDARD_BAG mode is used with a valid CRI dose. The matched
     value follows the specialist convention of giving a loading
     bolus that matches the chosen CRI rate 1:1 in µg/kg.

2. Emergent severe pain (matches_cri_rate=False):
   - Both species: 10–50 µg/kg titrated to effect
   - Range only (no matched value); the published guidance is to
     titrate, not to derive from the CRI rate.

The feature is drug-agnostic in implementation — any drug whose
loading_doses tuple is populated gets panels. Other drugs (norepi,
epi, dobutamine, dopamine-cri) leave the tuple empty and render no
loading-dose section.
"""

import pytest
from fastapi.testclient import TestClient

from app.calculators.drugs import FENTANYL, compute_loading_doses
from app.calculators.engine import Species
from app.main import app


class TestFentanylLoadingDoseConfig:
    """Lock down the loading-dose config shape against accidental edits.
    The Plumb's reference is the source of truth; these values shouldn't
    drift without an intentional config update."""

    def test_two_scenarios_present(self):
        assert len(FENTANYL.loading_doses) == 2

    def test_perioperative_first(self):
        """The perioperative panel renders first (it's the common case);
        the emergent severe-pain panel is second."""
        assert FENTANYL.loading_doses[0].label == "Perioperative analgesia"
        assert FENTANYL.loading_doses[1].label == "Emergent severe pain"

    def test_perioperative_matches_cri_rate(self):
        """Specialist convention: 1:1 µg/kg loading per µg/kg/hr CRI."""
        assert FENTANYL.loading_doses[0].matches_cri_rate is True

    def test_emergent_does_not_match_cri_rate(self):
        """Emergent dosing is titrated, not derived from the CRI rate."""
        assert FENTANYL.loading_doses[1].matches_cri_rate is False

    def test_perioperative_dog_range_2_to_10(self):
        scenario = FENTANYL.loading_doses[0]
        assert scenario.dose_per_kg[Species.DOG] == (2.0, 10.0)

    def test_perioperative_cat_is_single_value_5(self):
        """Per Plumb's, cat perioperative fentanyl is 5 µg/kg specifically,
        not a range. Encoded as (5.0, 5.0) — the template renders this
        as "Published dose: 5 µg/kg" rather than "Range: 5–5 µg/kg"."""
        scenario = FENTANYL.loading_doses[0]
        assert scenario.dose_per_kg[Species.CAT] == (5.0, 5.0)

    def test_emergent_10_to_50_both_species(self):
        """Emergent severe pain dosing is the same for both species
        (10 µg/kg initial, titrated to effect up to 50 µg/kg)."""
        scenario = FENTANYL.loading_doses[1]
        assert scenario.dose_per_kg[Species.DOG] == (10.0, 50.0)
        assert scenario.dose_per_kg[Species.CAT] == (10.0, 50.0)

    def test_emergent_has_titration_note(self):
        """The note on the emergent panel reminds clinicians to titrate
        slowly and have naloxone available."""
        scenario = FENTANYL.loading_doses[1]
        assert "naloxone" in scenario.note.lower()
        assert "titrate" in scenario.note.lower()


class TestComputeLoadingDoses:
    """Math correctness for compute_loading_doses(). Fentanyl stock is
    50 µg/mL throughout."""

    def test_dog_perioperative_at_typical_dose(self):
        """20 kg dog at 5 µg/kg/hr CRI:
        - Matched: 5 µg/kg × 20 kg = 100 µg = 2.0 mL of 50 µg/mL stock
        - Range:   2–10 µg/kg → 40–200 µg → 0.8–4.0 mL"""
        results = compute_loading_doses(
            FENTANYL, weight_kg=20.0, species=Species.DOG, cri_dose_value=5.0
        )
        perioperative = results[0]
        assert perioperative.matched_per_kg == 5.0
        assert perioperative.matched_total == 100.0
        assert perioperative.matched_ml_stock == 2.0
        assert perioperative.min_total == 40.0
        assert perioperative.max_total == 200.0
        assert perioperative.min_ml_stock == 0.8
        assert perioperative.max_ml_stock == 4.0
        assert perioperative.matched_outside_range is False

    def test_cat_perioperative_is_single_value(self):
        """4 kg cat at 5 µg/kg/hr CRI on the cat perioperative scenario.
        Single-value (5, 5) → is_single_value=True so the template
        renders "Published dose" instead of "Range"."""
        results = compute_loading_doses(
            FENTANYL, weight_kg=4.0, species=Species.CAT, cri_dose_value=5.0
        )
        perioperative = results[0]
        assert perioperative.is_single_value is True
        assert perioperative.min_total == 20.0
        assert perioperative.max_total == 20.0
        # Matched is 5 µg/kg × 4 kg = 20 µg = 0.4 mL
        assert perioperative.matched_ml_stock == 0.4

    def test_dog_outside_range_flag(self):
        """20 kg dog at 15 µg/kg/hr CRI is outside the published 2–10
        µg/kg loading range for perioperative. Flag fires."""
        results = compute_loading_doses(
            FENTANYL, weight_kg=20.0, species=Species.DOG, cri_dose_value=15.0
        )
        assert results[0].matched_outside_range is True

    def test_dog_inside_range_does_not_flag(self):
        results = compute_loading_doses(
            FENTANYL, weight_kg=20.0, species=Species.DOG, cri_dose_value=5.0
        )
        assert results[0].matched_outside_range is False

    def test_emergent_has_no_matched_value(self):
        """Emergent scenario doesn't match CRI rate (titrated separately)
        so matched_* fields are None."""
        results = compute_loading_doses(
            FENTANYL, weight_kg=20.0, species=Species.DOG, cri_dose_value=5.0
        )
        emergent = results[1]
        assert emergent.matched_per_kg is None
        assert emergent.matched_total is None
        assert emergent.matched_ml_stock is None

    def test_emergent_range_for_20kg_dog(self):
        """20 kg dog, emergent severe pain: 10–50 µg/kg → 200–1000 µg →
        4.0–20.0 mL of 50 µg/mL stock."""
        results = compute_loading_doses(
            FENTANYL, weight_kg=20.0, species=Species.DOG, cri_dose_value=5.0
        )
        emergent = results[1]
        assert emergent.min_total == 200.0
        assert emergent.max_total == 1000.0
        assert emergent.min_ml_stock == 4.0
        assert emergent.max_ml_stock == 20.0

    def test_returns_empty_when_drug_has_no_loading_doses(self):
        """Drugs without loading_doses config (norepi, etc.) get an
        empty tuple — no scenarios to render."""
        from app.calculators.drugs import NOREPINEPHRINE

        results = compute_loading_doses(
            NOREPINEPHRINE, weight_kg=20.0, species=Species.DOG, cri_dose_value=0.1
        )
        assert results == ()

    def test_returns_empty_for_invalid_weight(self):
        results = compute_loading_doses(
            FENTANYL, weight_kg=0, species=Species.DOG, cri_dose_value=5.0
        )
        assert results == ()

    def test_no_matched_value_when_cri_dose_missing(self):
        """If cri_dose_value isn't provided (e.g., TARGET_PUMP_RATE mode
        where dose is computed not input), the range still renders but
        no matched value appears."""
        results = compute_loading_doses(
            FENTANYL, weight_kg=20.0, species=Species.DOG, cri_dose_value=None
        )
        assert results[0].matched_per_kg is None
        # Range still computes
        assert results[0].min_per_kg == 2.0
        assert results[0].max_per_kg == 10.0


class TestFentanylResultPanelRendering:
    """End-to-end rendering of the loading-dose panels on the fentanyl
    compute response. Tests check both panels appear with the right
    values for typical patient scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def _compute(self, client, *, weight, dose, conc=5, species="dog"):
        return client.post(
            "/fentanyl/compute",
            data={
                "weight_value": str(weight),
                "weight_unit": "kg",
                "dose": str(dose),
                "concentration_ug_per_ml": str(conc),
                "species": species,
                "cri_mode": "standard_bag",
            },
        )

    def test_both_panels_render(self, client):
        body = self._compute(client, weight=20, dose=5).text
        assert "Loading dose" in body
        assert "Perioperative analgesia" in body
        assert "Emergent severe pain" in body

    def test_perioperative_matched_value_for_dog(self, client):
        """20 kg dog at 5 µg/kg/hr → matched loading dose 2.00 mL."""
        body = self._compute(client, weight=20, dose=5).text
        assert "2.00" in body  # the matched mL value
        assert "mL IV bolus" in body
        assert "100 µg" in body  # matched total
        assert "matched to your 5 µg/kg/hr CRI rate" in body

    def test_perioperative_range_for_dog(self, client):
        """Range section shows 2–10 µg/kg for dogs."""
        body = self._compute(client, weight=20, dose=5).text
        assert "Range:" in body
        assert "2–10 µg/kg" in body

    def test_perioperative_single_value_for_cat(self, client):
        """Cat single-value preset renders as 'Published dose: 5 µg/kg'
        not 'Range: 5–5 µg/kg'."""
        body = self._compute(client, weight=4, dose=5, species="cat").text
        assert "Published dose:" in body
        # Single-value formatting — only one number
        assert "Range:" not in body or "5–5" not in body

    def test_emergent_range_renders(self, client):
        """The emergent panel shows the 10–50 µg/kg range and no matched
        value (it's titrated separately, doesn't derive from CRI rate)."""
        body = self._compute(client, weight=20, dose=5).text
        assert "10–50 µg/kg" in body
        # The naloxone note should be present in the emergent panel
        assert "naloxone" in body.lower()

    def test_outside_range_warning_fires(self, client):
        """20 kg dog at 15 µg/kg/hr is outside the 2–10 published range;
        the matched-value section warns about this."""
        body = self._compute(client, weight=20, dose=15).text
        assert "outside the published loading range" in body

    def test_outside_range_warning_suppressed_when_inside(self, client):
        """Standard dose stays inside the range — no warning."""
        body = self._compute(client, weight=20, dose=5).text
        assert "outside the published loading range" not in body

    def test_section_absent_for_other_cri_drugs(self, client):
        """Loading-dose section is fentanyl-specific in v1. Other CRIs
        leave loading_doses empty and render no section."""
        for slug, conc in [
            ("norepinephrine", "16"),
            ("epinephrine", "40"),
            ("dobutamine", "500"),
            ("dopamine-cri", "800"),
        ]:
            r = client.post(
                f"/{slug}/compute",
                data={
                    "weight_value": "20",
                    "weight_unit": "kg",
                    "dose": "0.1" if slug != "dopamine-cri" and slug != "dobutamine" else "5",
                    "concentration_ug_per_ml": conc,
                    "species": "dog",
                    "cri_mode": "standard_bag",
                    "combined_prep_bag_size_ml": "50" if slug == "epinephrine" else "250",
                },
            )
            assert r.status_code == 200
            # The eyebrow heading + perioperative label combo is unique
            # to the fentanyl loading-dose section.
            assert "Perioperative analgesia" not in r.text, (
                f"/{slug} should not render the loading-dose section"
            )
