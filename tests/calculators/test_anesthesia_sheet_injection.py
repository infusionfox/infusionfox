"""
Tests for the anesthesia worksheet's dose injection and drug selection
mechanisms.

`_inject_chosen_doses` in app/routers/anesthesia_hub.py reads dose_*
form fields, clamps them into the published range for each drug, and
overwrites the drug-line's chosen dose. Empty values are skipped so
the natural default takes over.

The picker checkboxes (sel_opioid, sel_sedative, sel_induction) filter
which drugs appear on the printed sheet.

These behaviors had bug history (silent clamping carrying dog defaults
into cat picker, etc.) so test coverage is justified.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestDoseInjectionClamping:
    """The server clamps submitted dose_* values into the published range
    for the drug. Out-of-range submissions silently clamp; empty values
    skip injection entirely."""

    def test_dose_within_range_used_as_is(self):
        """A submitted dose inside the range is used verbatim."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
            "dose_methadone": "0.25",
        })
        assert r.status_code == 200
        # 0.25 mg/kg × 20 kg / 10 mg/mL = 0.5 mL
        assert "0.50 mL" in r.text

    def test_dose_above_range_clamps_to_high(self):
        """Submitting a dose above the published high end clamps to high.
        Catches the case where a stale dose from another species would
        otherwise be applied at face value."""
        # Dog methadone range is 0.1–0.3 mg/kg. Submit 5.0 (absurdly high).
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
            "dose_methadone": "5.0",
        })
        assert r.status_code == 200
        # Clamps to 0.3 mg/kg × 20 kg / 10 mg/mL = 0.6 mL
        assert "0.60 mL" in r.text

    def test_dose_below_range_clamps_to_low(self):
        """Submitting a dose below the published low end clamps to low."""
        # Dog methadone range is 0.1–0.3 mg/kg. Submit 0.01 (below low).
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
            "dose_methadone": "0.01",
        })
        assert r.status_code == 200
        # Clamps to 0.1 mg/kg × 20 kg / 10 mg/mL = 0.2 mL
        assert "0.20 mL" in r.text

    def test_empty_dose_falls_back_to_default(self):
        """Empty dose_* value should NOT inject — natural default applies."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
            "dose_methadone": "",
        })
        assert r.status_code == 200
        # Dog methadone default is 0.2 mg/kg → 0.4 mL
        assert "0.40 mL" in r.text

    def test_missing_dose_field_falls_back_to_default(self):
        """Not submitting the dose_* key at all is equivalent to empty."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
            # no dose_methadone key
        })
        assert r.status_code == 200
        assert "0.40 mL" in r.text

    def test_invalid_dose_string_falls_back_to_default(self):
        """Non-numeric dose value gets ignored (suppress(ValueError) in
        the router). Natural default applies."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
            "dose_methadone": "abc",
        })
        assert r.status_code == 200
        assert "0.40 mL" in r.text


class TestSpeciesToggleDoseHandling:
    """When the user switches species in the browser, JS clears all dose_*
    values before submitting. The server-side `if val:` check in
    _inject_chosen_doses lets empty values fall through to the new
    species' natural defaults.

    These tests verify the server side of that contract. The JS itself
    isn't directly testable here, but if these tests pass and the JS does
    its job, the user-visible behavior is correct."""

    def test_cat_with_dog_dose_values_clamps_silently(self):
        """If the JS clearing handler is broken, dog defaults would be
        submitted alongside species=cat. This test documents what would
        happen: clamping into the cat range. The fix (clearing fields
        on species change) prevents this scenario. If this assertion
        ever changes meaning, _inject_chosen_doses has changed too —
        update the JS handler accordingly."""
        # Dog buprenorphine default is 0.01 mg/kg. Cat range is 0.01–0.02.
        # Submitting 0.01 with species=cat clamps to the cat low end.
        r = client.post("/anesthesia/compute", data={
            "weight_value": "4",
            "weight_unit": "kg",
            "species": "cat",
            "dose_buprenorphine": "0.01",
        })
        assert r.status_code == 200
        # 0.01 mg/kg × 4 kg / 0.3 mg/mL = 0.133 mL (cat low end)
        assert "0.13 mL" in r.text

    def test_cat_with_empty_dose_uses_cat_default(self):
        """When dose_* is cleared (the species-change JS handler's job),
        the cat default applies. Catches a regression in the JS handler:
        if it stops clearing, the test above's behavior would silently
        replace this one."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "4",
            "weight_unit": "kg",
            "species": "cat",
            "dose_buprenorphine": "",
        })
        assert r.status_code == 200
        # Cat default is 0.02 mg/kg × 4 kg / 0.3 mg/mL = 0.267 mL
        assert "0.27 mL" in r.text


class TestDrugSelectionFiltering:
    """The picker checkboxes (sel_opioid, sel_sedative, sel_induction)
    filter which drugs appear in the printed-sheet drug tables. A
    deselected drug should not appear in the printed output."""

    def test_default_load_includes_all_drugs(self):
        """A fresh POST with no sel_* fields includes every drug."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
        })
        assert r.status_code == 200
        # Every dog opioid should appear at least once
        for name in ("Hydromorphone", "Methadone", "Butorphanol",
                     "Buprenorphine"):
            assert name in r.text, f"{name} missing from default-load response"

    def test_only_selected_opioids_appear_in_printed_section(self):
        """When the user selects only methadone, hydromorphone shouldn't
        appear in the printed opioid section."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
            "sel_opioid": "Methadone",  # only one
        })
        assert r.status_code == 200
        # Locate the printed opioid section (not the picker, which always
        # shows all options). The picker has sel_opioid inputs; the printed
        # table has the drug name in a <td>. We use that as the heuristic.
        # The printed Methadone row should be present:
        assert "Methadone" in r.text
        # And the printed Hydromorphone row should be absent from the
        # printed-table area. We can look for a printed-context marker.
        # Simpler check: the printed-table row markup uses <strong>NAME</strong>
        # inside a <td>. Picker uses different markup. So we count strong tags.
        # Even simpler: hydromorphone won't have its volume cell rendered
        # for the printed sheet if it's not selected — confirm by looking
        # for "Hydromorphone</strong>" inside a sheet-table tbody cell:
        printed_section = r.text.split("PREMEDICATION. SEDATIVES")[0]
        # the printed-table row for an opioid renders as <strong>Name</strong>
        # while the picker renders the name with the dose input UI.
        assert "<strong>Methadone</strong>" in printed_section
        assert "<strong>Hydromorphone</strong>" not in printed_section

    def test_selecting_multiple_opioids_shows_all_in_printed(self):
        """Two selections both appear; one omission absent."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20",
            "weight_unit": "kg",
            "species": "dog",
            "sel_opioid": ["Methadone", "Butorphanol"],
        })
        assert r.status_code == 200
        printed_section = r.text.split("PREMEDICATION. SEDATIVES")[0]
        assert "<strong>Methadone</strong>" in printed_section
        assert "<strong>Butorphanol</strong>" in printed_section
        assert "<strong>Hydromorphone</strong>" not in printed_section
        assert "<strong>Buprenorphine</strong>" not in printed_section
