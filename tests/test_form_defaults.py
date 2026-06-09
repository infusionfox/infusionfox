"""
Pin: every calculator form must be HTMX-submittable as soon as the user
enters the patient weight.

HTMX 2.x silently blocks form submission when any `required` field is
empty. Without on-screen feedback, this produces the user-visible bug
"entering weight doesn't show results." The fix on each calculator is to
pre-fill every required-and-computable field with a sensible default on
initial GET so only the weight has to be entered by the user.

This test enumerates every calculator page, walks its required inputs,
and fails when a required input renders with an empty value — unless the
field name is in EXPECTED_USER_FILLED (fields the user actually needs to
type, like weight_value itself, or blood-gas pH/pCO2/HCO3 where there is
no clinical default to pre-populate).
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# Fields that legitimately render empty because the user must enter them.
# Adding a name here is a deliberate declaration that the calculator's
# clinical workflow requires this input from the user (no usable default).
EXPECTED_USER_FILLED = {
    # Weight is always user-entered. Every calculator has this.
    "weight_value",
    "current_weight_value",  # /energy, /tube-feeding use this name
    # Blood gas inputs: the entire purpose of the calculator is to
    # interpret what the clinician measured. No defaults to seed.
    "pH",
    "pco2_mm_hg",
    "hco3_meq_per_l",
    # IRIS creatinine: deliberately blank on initial render per Safety
    # Rule #8 (calculators NEVER show output before the clinician
    # enters values). Pre-filling 1.0 caused a fake "Stage 1" headline
    # to appear before any user input. The IRIS result panel shows a
    # placeholder ("Enter creatinine to compute IRIS stage") so the
    # required-ness is obvious in the UX.
    "creatinine_mg_dl",
}


# Every calculator page that should be auditable. Not exhaustive on
# purpose — pages with no required fields, or pages that gate behind a
# user choice (anesthesia worksheet's weight field), are listed below.
CALCULATOR_PAGES = [
    "/norepinephrine",
    "/epinephrine",
    "/dobutamine",
    "/dopamine-cri",
    "/fentanyl",
    "/alfaxalone",
    "/propofol",
    "/methadone",
    "/lidocaine",
    "/mlk",
    "/dopamine",
    "/blood-gas",
    "/insulin-cri-dka",
    "/insulin-im-dka",
    "/insulin-dextrose-hyperK",
    "/ca-gluconate-hyperK",
    "/hypomagnesemia",
    "/hypophosphatemia",
    "/hypokalemia",
    "/hypernatremia",
    "/lddst",
    "/cushings-score",
    "/hypothyroid-score",
    "/addisons-score",
    "/cornell-onco-kl",
    "/iris-staging",
    "/fluid-therapy",
    "/transfusion",
    "/energy",
    "/tube-feeding",
    "/hydromorphone-cri",
    "/kitty-magic",
    "/ketamine",
    "/status-canine",
    "/status-feline",
    "/anesthesia",
    "/cpr",
]


def _required_inputs(html: str) -> list[tuple[str, str, str]]:
    """Return (name, type, value) for every <input> that has `required`.

    Excludes hidden/radio/checkbox/submit/button inputs — those either
    always have a value (hidden, radio with one option pre-checked) or
    aren't subject to required-value validation in the same way.
    """
    out: list[tuple[str, str, str]] = []
    for tag in re.findall(r"<input[^>]*\brequired\b[^>]*>", html, flags=re.DOTALL):
        name_m = re.search(r'\bname="([^"]+)"', tag)
        if not name_m:
            continue
        type_m = re.search(r'\btype="([^"]+)"', tag)
        value_m = re.search(r'\bvalue="([^"]*)"', tag)
        typ = type_m.group(1) if type_m else "text"
        if typ in ("hidden", "radio", "checkbox", "submit", "button"):
            continue
        value = value_m.group(1) if value_m else ""
        out.append((name_m.group(1), typ, value))
    return out


@pytest.mark.parametrize("path", CALCULATOR_PAGES)
def test_calculator_required_fields_have_defaults(path):
    """Every required <input> must render with a non-empty value OR be
    listed in EXPECTED_USER_FILLED.

    Failure means HTMX 2.x will silently block the form's auto-submit
    when the user enters weight, because the listed field is required
    but empty. Fix by:
      - Pre-filling the field with a sensible clinical default in the
        router context, OR
      - Adding the field name to EXPECTED_USER_FILLED if the user
        genuinely must enter it (and the calculator's UX makes that
        obvious).
    """
    r = client.get(path)
    assert r.status_code == 200, f"GET {path}: {r.status_code}"

    offenders = []
    for name, typ, value in _required_inputs(r.text):
        if name in EXPECTED_USER_FILLED:
            continue
        if value == "":
            offenders.append(f"{name} (type={typ})")

    assert not offenders, (
        f"GET {path}: required field(s) render with empty value: {offenders}. "
        f"HTMX 2.x will silently block POST until these are filled. "
        f"Pre-fill in the router or add to EXPECTED_USER_FILLED."
    )


def test_hydromorphone_form_is_submittable_on_weight_only():
    """Specific pin for the regression that originally motivated this
    test file. After the hydromorphone redesign the form has no manually-
    entered CRI rate field at all; every required input either renders
    with a non-empty value or is the weight the user is typing. This
    test walks the rendered form and asserts no required input would
    silently block the HTMX POST."""
    r = client.get("/hydromorphone-cri")
    offenders = [
        (name, value)
        for name, typ, value in _required_inputs(r.text)
        if name not in EXPECTED_USER_FILLED and value == ""
    ]
    assert not offenders, (
        f"/hydromorphone-cri has required+empty inputs that would block "
        f"the HTMX POST: {offenders}. The form should be submittable as "
        f"soon as the user enters weight."
    )


# ---------------------------------------------------------------------------
# Dose-range help text honesty: when dog and cat dose ranges are the same,
# the text should not silently claim the displayed range is the "dog
# range" while ignoring cats. When the ranges differ, both should be shown.
# This is a regression test for a bug where clicking the cat species
# button left the help text saying "Typical dog range".
# ---------------------------------------------------------------------------


def _dose_help_text(body: str) -> str:
    """Extract the .help block immediately after the dose input."""
    m = re.search(
        r'name="dose"[^>]*>\s*<div class="help">\s*(.*?)\s*</div>',
        body,
        re.DOTALL,
    )
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def test_norepi_dose_help_does_not_falsely_claim_dog_only():
    """Norepi dog and cat dose ranges are numerically identical
    (0.05–2.0 µg/kg/min). The help text must NOT say 'Typical dog
    range:' — it should say 'dogs and cats' or otherwise acknowledge
    both species."""
    body = client.get("/norepinephrine").text
    help_text = _dose_help_text(body)
    assert help_text, "Could not locate dose-range help text on /norepinephrine"
    assert "dogs and cats" in help_text.lower()
    assert "typical dog range" not in help_text.lower()


def test_help_text_shows_both_ranges_when_species_differ():
    """Dobutamine has different dog (2–20) and cat (1–5) ranges.
    The help text must show both, not just dogs."""
    body = client.get("/dobutamine").text
    help_text = _dose_help_text(body)
    assert help_text, "Could not locate dose-range help text on /dobutamine"
    assert "Dogs:" in help_text
    assert "Cats:" in help_text
    # Spot-check the numbers
    assert "2.0–20.0" in help_text  # dog range
    assert "1.0–5.0" in help_text  # cat range


def test_help_text_combines_when_ranges_match():
    """Drugs with identical dog and cat ranges should get the
    combined '(dogs and cats)' phrasing rather than duplicating
    the same numbers twice."""
    for slug in ("norepinephrine", "epinephrine", "fentanyl"):
        body = client.get(f"/{slug}").text
        help_text = _dose_help_text(body)
        assert "(dogs and cats)" in help_text.lower(), (
            f"/{slug}: expected combined-species phrasing, got: {help_text!r}"
        )
