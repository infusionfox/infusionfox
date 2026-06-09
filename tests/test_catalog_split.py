"""
Tests for the two-page catalog split: /calculators (math/dose tools) vs
/hubs (clinical workflows, scoring tools, decision-support pages).

The split is driven by NavEntry.kind. Each entry is classified as either
"calculator" or "hub"; the two catalog routes filter the same underlying
nav inventory by that field. This module locks in the classification —
adding a new entry without explicitly marking it as a hub means it
defaults to "calculator" and lands on /calculators, which is usually what
you want; marking it kind="hub" should be a deliberate decision.
"""

from __future__ import annotations

import pytest

from app.nav import (
    NavEntry,
    calculator_nav_index,
    hub_nav_index,
    nav_index,
)


class TestNavEntryClassification:
    def test_default_kind_is_calculator(self):
        # Default keeps the migration safe: a forgotten kind ends up on
        # /calculators rather than disappearing entirely.
        e = NavEntry(href="/x", title="X")
        assert e.kind == "calculator"

    def test_full_index_partitions_cleanly(self):
        full = nav_index()
        cal = calculator_nav_index()
        hub = hub_nav_index()
        # Every entry from the full index should appear in exactly one of
        # the two filtered indexes — no entry lost, no entry duplicated.
        all_hrefs_full = {e.href for entries in full.values() for e in entries}
        all_hrefs_cal = {e.href for entries in cal.values() for e in entries}
        all_hrefs_hub = {e.href for entries in hub.values() for e in entries}
        assert all_hrefs_cal | all_hrefs_hub == all_hrefs_full
        assert all_hrefs_cal & all_hrefs_hub == set(), (
            "An entry shouldn't appear on both /calculators and /hubs."
        )

    @pytest.mark.parametrize(
        "href",
        [
            "/anaphylaxis",
            "/anesthesia",
            "/cushings-score",
            "/addisons-score",
            "/dka",
            "/heatstroke",
            "/hyperkalemia-emergency",
            "/hypoglycemia",
            "/hypothyroid-score",
            "/iris-staging",
            "/lddst",
            "/shock",
            "/status-canine",
            "/status-feline",
        ],
    )
    def test_known_hubs_classified_as_hub(self, href):
        # Hubs are clinical workflows / scoring tools, not math calculators.
        # This locks in the current classification so a refactor doesn't
        # silently demote a hub to a calculator.
        hub = hub_nav_index()
        hrefs = {e.href for entries in hub.values() for e in entries}
        assert href in hrefs, f"{href} should be classified as a hub"

    @pytest.mark.parametrize(
        "href",
        [
            "/cpr",
            "/fluid-therapy",
            "/analgesia-cri",
            "/fentanyl",
            "/insulin-cri-dka",
            "/insulin-im-dka",
            "/dopamine-cri",
            "/norepinephrine",
            "/dilution",
            "/tools/drop-factor",
            "/energy",
            "/transfusion",
            "/hypokalemia",
            "/hypernatremia",
            "/kitty-magic",
            "/ca-gluconate-hyperK",
            "/insulin-dextrose-hyperK",
        ],
    )
    def test_known_calculators_classified_as_calculator(self, href):
        # CPR is dosing math (despite being in the Emergency category with
        # the hubs); fluid therapy / MLK / kitty magic are bag/prep math.
        # All of these should land on /calculators, not /hubs.
        cal = calculator_nav_index()
        hrefs = {e.href for entries in cal.values() for e in entries}
        assert href in hrefs, f"{href} should be classified as a calculator"


class TestCatalogRoutes:
    def test_calculators_route(self, fastapi_client):
        r = fastapi_client.get("/calculators")
        assert r.status_code == 200
        # The drawer (rendered in base.html on every page) lists the full
        # inventory, so we have to scope these assertions to the catalog
        # section itself. The catalog `<section class="catalog">` ends with
        # the closing `</section>` tag right before the footer.
        import re
        section_match = re.search(
            r'<section class="catalog">(.*?)</section>', r.text, re.DOTALL
        )
        assert section_match, "Catalog section not found"
        body = section_match.group(1)
        # Contains calculator-side entries
        assert "CPR dosing" in body
        assert "Fentanyl CRI" in body
        # Does NOT contain hub-side entries
        assert "Anesthesia worksheet" not in body
        assert "Anaphylaxis hub" not in body
        assert "IRIS CKD staging" not in body

    def test_hubs_route(self, fastapi_client):
        r = fastapi_client.get("/hubs")
        assert r.status_code == 200
        import re
        section_match = re.search(
            r'<section class="catalog">(.*?)</section>', r.text, re.DOTALL
        )
        assert section_match, "Catalog section not found"
        body = section_match.group(1)
        # Contains hub-side entries
        assert "Anesthesia worksheet" in body
        assert "Anaphylaxis hub" in body
        assert "IRIS CKD staging" in body
        # Does NOT contain calculator-side entries
        assert "CPR dosing" not in body
        assert "Fentanyl CRI" not in body

    def test_top_nav_has_both_links(self, fastapi_client):
        # Every page renders the top nav. We pick an arbitrary route here.
        r = fastapi_client.get("/")
        assert 'href="/calculators"' in r.text
        assert 'href="/hubs"' in r.text
        assert 'href="/learn"' in r.text
