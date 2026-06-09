"""
End-to-end integration tests for the anesthesia worksheet.

These exercise the full POST /anesthesia/compute → calculator → template
render path. Unit tests on app/calculators/anesthesia_sheet.py cover the
math; these tests cover the parts of the worksheet that depend on the
calculator, the router, and the template all working together.

The kind of test that would have caught past bugs:
- The picker not rendering correctly on first load
- The hx-preserve setup on the picker section
- Tab pane structure
- Species change rendering at the new species' defaults with a blank
  slate (replaces the previous in-place toggle + JS handler approach)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestWorksheetGetRender:
    """The GET /anesthesia page renders the full shell."""

    def test_get_returns_200(self):
        r = client.get("/anesthesia")
        assert r.status_code == 200

    def test_get_includes_form(self):
        r = client.get("/anesthesia")
        assert 'id="anesthesia-form"' in r.text

    def test_get_includes_swap_wrapper(self):
        r = client.get("/anesthesia")
        assert 'id="anesthesia-sheet-wrapper"' in r.text


class TestPatientBarLayout:
    """Visual ordering of the patient-input area.

    Two ordering decisions matter:

    1. Species block FIRST, above the patient fieldset. Picking the
       wrong species is the worst possible mistake on this worksheet —
       every dose, range, and safety threshold downstream depends on
       it. The big segmented control sits above everything so it's the
       first choice the clinician makes.

    2. Within the patient fieldset: weight → name → age. Weight is the
       only required field and the only one that drives the
       calculation; it gets the leftmost (most prominent) column.
       Name and age are optional patient-identification fields.

    Both are deliberate UX choices. Pin the order so an accidental
    refactor can't quietly revert them.
    """

    def test_species_block_appears_before_patient_fieldset(self):
        r = client.get("/anesthesia")
        # Use opening tags rather than bare class names to disambiguate
        # from the CSS block where these class names also appear.
        i_species = r.text.find('<div class="species-bar')
        i_patient = r.text.find('<fieldset class="patient-bar')
        assert i_species > 0, "species-bar block must exist on the worksheet"
        assert i_patient > 0, "patient-bar fieldset must exist on the worksheet"
        assert i_species < i_patient, (
            f"species block must come before patient bar in DOM order "
            f"(species at {i_species}, patient at {i_patient})"
        )

    def test_patient_bar_field_order_is_weight_name_age(self):
        r = client.get("/anesthesia")
        i_patient_start = r.text.find('<fieldset class="patient-bar')
        i_patient_end = r.text.find("</fieldset>", i_patient_start)
        assert i_patient_start > 0 and i_patient_end > 0
        section = r.text[i_patient_start:i_patient_end]

        i_weight = section.find('id="weight_value"')
        i_name = section.find('id="patient_name"')
        i_age = section.find('id="patient_age"')
        assert 0 < i_weight < i_name < i_age, (
            f"patient-bar field order must be weight → name → age, got "
            f"weight={i_weight}, name={i_name}, age={i_age}"
        )

    def test_species_control_renders_as_portrait_cards(self):
        """The species control is rendered as two portrait cards, not
        a small inline segmented control. This is a deliberate
        prominence choice — picking the wrong species silently
        propagates to every dose downstream, so the choice needs to be
        visually impossible to make absently. Pin the structure so a
        refactor can't quietly shrink it back to a compact form
        control."""
        r = client.get("/anesthesia")
        # The container uses the cards class, not the old segmented one.
        assert 'class="species-cards"' in r.text
        # Each card is a <label class="species-card"> wrapping the name.
        assert r.text.count('class="species-card"') == 2, (
            "should be exactly two species cards (dog + cat)"
        )
        # Each card has a name span.
        assert r.text.count('class="species-card__name"') == 2
        # Both species names render as text inside the cards.
        assert ">Dog<" in r.text
        assert ">Cat<" in r.text

    def test_species_control_has_accessibility_attributes(self):
        """The species control is a radio group, not a list of independent
        checkboxes. Screen readers need role=radiogroup + a label
        association to announce it correctly. The visible label is
        rendered visually-hidden (cards self-label with their species
        name text) but the label element stays for screen-reader use."""
        r = client.get("/anesthesia")
        assert 'role="radiogroup"' in r.text
        assert 'aria-labelledby="species-bar-label"' in r.text
        # The label element exists, marked visually-hidden so it
        # disappears for sighted users but is still announced.
        assert 'class="visually-hidden" id="species-bar-label"' in r.text


class TestWorksheetPostRender:
    """POST returns the full updated worksheet (outerHTML swap of the
    wrapper). Tab panes, picker, drug tables all included."""

    def test_post_returns_200_for_valid_input(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        assert r.status_code == 200

    def test_post_includes_both_tab_panes(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        assert 'id="anesthesia-sheet-preop"' in r.text
        assert 'id="anesthesia-sheet-intraop"' in r.text

    def test_post_includes_picker_section(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        assert 'id="preop-picker"' in r.text

    def test_picker_has_hx_preserve(self):
        """The picker must be marked hx-preserve so its DOM survives
        HTMX swaps. Without this, every checkbox change collapses the
        open <details>. See docs/anesthesia-worksheet.md."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        # Find the picker section opening tag
        i = r.text.find('id="preop-picker"')
        assert i > 0
        # hx-preserve should be on the same tag
        tag_end = r.text.find('>', i)
        tag = r.text[i:tag_end]
        assert 'hx-preserve="true"' in tag

    def test_picker_data_category_attributes_present(self):
        """The drug-picker details elements each have data-category, which
        the JS count-updater relies on."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        for cat in ("opioids", "sedatives", "induction"):
            assert f'data-category="{cat}"' in r.text


class TestWorksheetDrugContent:
    """The printed drug tables contain the expected drugs for each species."""

    def test_dog_premed_opioids_present(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        for name in ("Hydromorphone", "Methadone", "Butorphanol", "Buprenorphine"):
            assert f"<strong>{name}</strong>" in r.text

    def test_cat_includes_dkb_table(self):
        """DKB (Kitty Magic) only appears on cat worksheets."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "4", "weight_unit": "kg", "species": "cat",
        })
        assert "DKB" in r.text or "Kitty Magic" in r.text

    def test_dog_does_not_include_dkb_table(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        assert "Kitty Magic" not in r.text

    def test_intraop_includes_fluid_bolus(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        assert "Fluid bolus" in r.text
        assert "LRS" in r.text

    def test_intraop_includes_bridge_pressors(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        assert "Phenylephrine" in r.text
        assert "Ephedrine" in r.text

    def test_intraop_includes_cri_vasopressors(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        for name in ("Dopamine", "Dobutamine", "Norepinephrine"):
            assert name in r.text


class TestWorksheetSmallPatientFallback:
    """Sub-1.5 kg patients get a syringe-pump note instead of a normal
    CRI ladder. Practical CRI bag dosing doesn't work that small."""

    def test_sub_1_5kg_cat_gets_syringe_pump_message(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "1.0", "weight_unit": "kg", "species": "cat",
        })
        assert r.status_code == 200
        # The syringe-pump fallback message appears in CRI prep notes
        assert "syringe pump" in r.text.lower()


class TestWorksheetActiveTabPreserved:
    """The form has a hidden active_tab field that travels with each
    submission so the response renders with the right tab active."""

    def test_preop_tab_default(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        # The preop tab should have is-active class on its tab button
        # (we look for both a tab button and a pane with is-active)
        assert 'class="anesthesia-tab-btn is-active"' in r.text or \
               'is-active' in r.text  # may have other modifiers

    def test_intraop_tab_explicit(self):
        r = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
            "active_tab": "intraop",
        })
        # The intraop pane should have is-active
        i = r.text.find('id="anesthesia-sheet-intraop"')
        assert i > 0
        tag_end = r.text.find('>', i)
        intraop_tag = r.text[i:tag_end]
        assert "is-active" in intraop_tag


class TestSpeciesReloadBlankSlate:
    """Species change is a full page reload (not an in-place swap).

    The species radios in the worksheet template are wired with
    hx-get="/anesthesia?species=…" + hx-target="body" + hx-swap="outerHTML"
    + hx-include="this", so changing species causes the whole page to
    re-render at the chosen species with everything else blank.

    This replaces an earlier in-place toggle that needed a JS handler to
    clear dose_* inputs and strip hx-preserve from the picker — fragile
    code whose failure mode was silently-wrong default doses for the new
    species (e.g. dog buprenorphine 0.01 carrying into cat side, sitting
    at the cat low end instead of cat default 0.02).

    A blank-slate reload removes that bug class entirely: there is no
    previous-species DOM state for the new species to inherit.
    """

    def test_get_species_cat_renders_cat_page(self):
        r = client.get("/anesthesia?species=cat")
        assert r.status_code == 200
        # The cat radio should be checked
        i = r.text.find('id="sp-cat"')
        assert i > 0
        # Look at the radio tag for `checked`
        tag_end = r.text.find('>', i)
        cat_tag = r.text[i:tag_end]
        assert "checked" in cat_tag, "Cat radio should be checked on ?species=cat"
        # And dog should not be checked
        i = r.text.find('id="sp-dog"')
        tag_end = r.text.find('>', i)
        dog_tag = r.text[i:tag_end]
        assert "checked" not in dog_tag, "Dog radio should not be checked on ?species=cat"

    def test_get_species_dog_renders_dog_page(self):
        r = client.get("/anesthesia?species=dog")
        assert r.status_code == 200
        i = r.text.find('id="sp-dog"')
        tag_end = r.text.find('>', i)
        assert "checked" in r.text[i:tag_end]

    def test_get_default_species_is_dog(self):
        """No species param → dog (matches the long-standing default)."""
        r = client.get("/anesthesia")
        assert r.status_code == 200
        i = r.text.find('id="sp-dog"')
        tag_end = r.text.find('>', i)
        assert "checked" in r.text[i:tag_end]

    def test_get_invalid_species_falls_back_to_dog(self):
        """An invalid species value mustn't 500 or render an unknown
        species — fall back to dog defensively."""
        r = client.get("/anesthesia?species=ferret")
        assert r.status_code == 200
        i = r.text.find('id="sp-dog"')
        tag_end = r.text.find('>', i)
        assert "checked" in r.text[i:tag_end]

    def test_species_reload_is_blank_slate(self):
        """A species reload must produce empty weight/name/age inputs.
        That's the safety guarantee — no previous-species values can
        leak through, because there ARE no values on the new page."""
        r = client.get("/anesthesia?species=cat")
        # Weight input should have value="" (or no value attribute)
        i = r.text.find('id="weight_value"')
        assert i > 0
        tag_end = r.text.find('>', i)
        tag = r.text[i:tag_end]
        assert 'value=""' in tag, f"Weight input should be empty on species reload, got: {tag}"
        # Patient name and age similarly
        for field_id in ("patient_name", "patient_age"):
            i = r.text.find(f'id="{field_id}"')
            assert i > 0
            tag_end = r.text.find('>', i)
            assert 'value=""' in r.text[i:tag_end], (
                f"{field_id} should be empty on species reload"
            )

    def test_species_radios_have_full_reload_wiring(self):
        """Structural pin: the radios MUST do hx-get → /anesthesia with
        hx-target=body and hx-include=this. If any of those attributes
        get dropped or changed, this test fails — protecting the safety
        design against accidental refactors. The radios going back to
        triggering the form's hx-post (which only swaps the result
        panel) would silently reintroduce the in-place species switch
        and its associated bug class.
        """
        r = client.get("/anesthesia")
        # Find each radio's full opening tag and check the wiring
        for radio_id, species_val in [("sp-dog", "dog"), ("sp-cat", "cat")]:
            i = r.text.find(f'id="{radio_id}"')
            assert i > 0
            # Walk back to the opening < and forward to the closing >
            tag_start = r.text.rfind('<', 0, i)
            tag_end = r.text.find('>', i)
            tag = r.text[tag_start:tag_end + 1]
            assert f'hx-get="/anesthesia?species={species_val}"' in tag, (
                f"{radio_id} missing hx-get for full page reload: {tag}"
            )
            assert 'hx-target="body"' in tag, (
                f"{radio_id} must target body for full reload: {tag}"
            )
            assert 'hx-include="this"' in tag, (
                f"{radio_id} must hx-include only itself — no leaked "
                f"form state to the species reload: {tag}"
            )
            assert 'hx-trigger="change"' in tag, (
                f"{radio_id} must trigger on change (not the form's "
                f"default input-changed/load triggers): {tag}"
            )

    def test_species_reload_picker_renders_at_new_species_defaults(self):
        """Once the user enters a weight on the cat-species page, the
        result partial should render the cat dex range (10–40 µg/kg),
        not the dog range (3–20 µg/kg). The picker's dose labels live
        inside the result partial (POST /anesthesia/compute), so test
        through that route — the page-shell GET only shows the patient
        bar + "Awaiting input" placeholder before a weight is provided."""
        r = client.post("/anesthesia/compute", data={
            "weight_value": "4", "weight_unit": "kg", "species": "cat",
        })
        assert r.status_code == 200
        assert "10–40 µg/kg" in r.text, (
            "Cat compute should render cat dex range (10–40 µg/kg)"
        )

    def test_species_reload_no_leaked_dose_inputs(self):
        """Defense-in-depth: a cat species compute must not render the
        dog dex range, and vice versa. If hx-include="this" ever stops
        scoping the species reload to just the radio value, dog dose
        ranges could bleed onto a cat page (or the form's hx-post could
        carry stale dog state through). Pin both directions."""
        r_cat = client.post("/anesthesia/compute", data={
            "weight_value": "4", "weight_unit": "kg", "species": "cat",
        })
        assert "10–40 µg/kg" in r_cat.text  # cat dex
        assert "3–20 µg/kg" not in r_cat.text, (
            "Cat compute should not render dog dex range"
        )

        r_dog = client.post("/anesthesia/compute", data={
            "weight_value": "20", "weight_unit": "kg", "species": "dog",
        })
        assert "3–20 µg/kg" in r_dog.text  # dog dex
        assert "10–40 µg/kg" not in r_dog.text, (
            "Dog compute should not render cat dex range"
        )
