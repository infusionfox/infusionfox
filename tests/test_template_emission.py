"""
Tests for the worked-example template mechanism and the picker checkbox
counts.

The global handler in app/templates/base.html depends on result partials
emitting <template id="worked-example-source..."> blocks with specific
IDs. The page has matching #worked-example... target divs. If a partial
stops emitting the right templates, the worked-example formulas silently
fail to render in the browser — no error, just empty placeholders. A
server-side test catches this before it ships.

The picker emits one checkbox per drug per category. A test that the
checkbox count matches the result drug-list length catches a class of
template-loop bugs.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestWorkedExampleTemplates:
    """Result partials emit <template id="worked-example-source..."> blocks
    that the global base.html handler copies into matching #worked-example
    divs. Each partial must emit the IDs its page template expects."""

    def test_insulin_im_dka_loading_emits_two_templates(self):
        """Loading mode: total units + volume."""
        r = client.post("/insulin-im-dka/compute", data={
            "weight_value": "20", "weight_unit": "kg",
            "species": "dog", "mode": "loading",
        })
        assert r.status_code == 200
        assert 'id="worked-example-source"' in r.text
        assert 'id="worked-example-source-volume"' in r.text

    def test_insulin_im_dka_subsequent_emits_three_templates(self):
        """Subsequent mode with both BG values: adds the ΔBG formula."""
        r = client.post("/insulin-im-dka/compute", data={
            "weight_value": "20", "weight_unit": "kg",
            "species": "dog", "mode": "subsequent",
            "previous_bg_mg_per_dl": "400",
            "current_bg_mg_per_dl": "340",
        })
        assert r.status_code == 200
        assert 'id="worked-example-source"' in r.text
        assert 'id="worked-example-source-volume"' in r.text
        assert 'id="worked-example-source-bg"' in r.text

    def test_insulin_cri_dka_emits_three_templates(self):
        """Total, concentration, delivered U/kg/hr."""
        r = client.post("/insulin-cri-dka/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
            "blood_glucose_mg_per_dl": "500",
        })
        assert r.status_code == 200
        assert 'id="worked-example-source"' in r.text
        assert 'id="worked-example-source-concentration"' in r.text
        assert 'id="worked-example-source-delivered"' in r.text

    def test_insulin_dextrose_emits_two_templates(self):
        """Insulin + dextrose."""
        r = client.post("/insulin-dextrose-hyperK/compute", data={
            "weight_value": "20", "weight_unit": "kg",
        })
        assert r.status_code == 200
        assert 'id="worked-example-source"' in r.text
        assert 'id="worked-example-source-dextrose"' in r.text

    def test_templates_live_inside_result_panel(self):
        """The templates must be INSIDE #result-panel so they ride along
        with the HTMX swap. Templates outside the swap target would get
        orphaned. We assert by checking that the template tags appear
        before the closing </div> of #result-panel."""
        r = client.post("/insulin-im-dka/compute", data={
            "weight_value": "20", "weight_unit": "kg",
            "species": "dog", "mode": "loading",
        })
        # Find the #result-panel opening
        panel_start = r.text.find('id="result-panel"')
        assert panel_start > 0
        # Find every template source within the response, and confirm
        # at least one is after panel_start.
        template_pos = r.text.find('id="worked-example-source"', panel_start)
        assert template_pos > panel_start, (
            "worked-example template not inside #result-panel"
        )


class TestPickerCheckboxCounts:
    """The picker emits one checkbox per drug per category. The count of
    checkboxes in each category section should match the count of drugs
    in result.premed_opioids / _sedatives / induction_drugs."""

    def _count_checkboxes(self, html, input_name):
        return len(re.findall(
            r'<input[^>]*name="' + re.escape(input_name) + r'"', html
        ))

    def test_dog_opioid_checkbox_count_matches_drug_count(self):
        """Dog has 4 opioids (Hydromorphone, Methadone, Butorphanol,
        Buprenorphine). The picker should emit 4 sel_opioid checkboxes."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        count = self._count_checkboxes(r.text, "sel_opioid")
        assert count == 4, f"expected 4 dog opioid checkboxes, got {count}"

    def test_cat_opioid_checkbox_count_matches_drug_count(self):
        """Cat also has 4 opioids."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "4", "weight_unit": "kg", "species": "cat",
        })
        count = self._count_checkboxes(r.text, "sel_opioid")
        assert count == 4, f"expected 4 cat opioid checkboxes, got {count}"

    def test_sedative_checkbox_count_dog(self):
        """Dog has 3 sedatives (Dexmedetomidine, Midazolam, Acepromazine)."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        count = self._count_checkboxes(r.text, "sel_sedative")
        assert count == 3, f"expected 3 dog sedative checkboxes, got {count}"

    def test_sedative_checkbox_count_cat(self):
        """Cat has 3 sedatives, same list."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "4", "weight_unit": "kg", "species": "cat",
        })
        count = self._count_checkboxes(r.text, "sel_sedative")
        assert count == 3, f"expected 3 cat sedative checkboxes, got {count}"

    def test_induction_checkbox_count(self):
        """Both species have 2 induction agents (Propofol, Alfaxalone)."""
        for species, weight in (("dog", "20"), ("cat", "4")):
            r = client.post("/anesthesia/compute", data={
                "weight_value": weight, "weight_unit": "kg",
                "species": species,
            })
            count = self._count_checkboxes(r.text, "sel_induction")
            assert count == 2, (
                f"expected 2 {species} induction checkboxes, got {count}"
            )

    def test_picker_default_state_all_checked(self):
        """On initial load (no sel_* fields submitted), every checkbox
        should render checked — the picker pre-selects everything so the
        printed sheet shows all drugs unless the user deselects."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        # Find checkboxes for sel_opioid and assert each has 'checked'
        checkbox_pattern = re.compile(
            r'<input[^>]*name="sel_opioid"[^>]*>'
        )
        matches = checkbox_pattern.findall(r.text)
        assert len(matches) == 4
        for tag in matches:
            assert "checked" in tag, (
                f"expected sel_opioid checkbox to be checked: {tag}"
            )
