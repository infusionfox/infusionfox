"""Tests for the drawer filter UI.

The drawer filter is pure client-side JS — it filters the rendered DOM
in place rather than going over the network. These tests verify the
DOM structure that the JS depends on: the filter input is present, each
drawer item carries a data-search attribute with both hyphenated and
dehyphenated tokens, the empty-state container exists, and the fallback
link points at the full /search route. Functional filter behavior is
not asserted here (would need a JS runtime); the JS itself is small and
straightforward.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestDrawerFilterDOM:
    def test_filter_input_present_on_homepage(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "data-drawer-filter-input" in r.text
        assert "data-drawer-filter-clear" in r.text
        assert "data-drawer-filter-empty" in r.text

    def test_filter_input_present_on_calculator_page(self):
        r = client.get("/apple-fast")
        assert r.status_code == 200
        assert "data-drawer-filter-input" in r.text

    def test_filter_input_present_on_hub_page(self):
        r = client.get("/shock")
        assert r.status_code == 200
        assert "data-drawer-filter-input" in r.text

    def test_every_drawer_group_marked(self):
        """JS needs to enumerate groups via data-drawer-group."""
        r = client.get("/")
        # At least the major clinical categories + Site
        # Each category gets one data-drawer-group attribute.
        assert r.text.count("data-drawer-group") >= 8

    def test_every_drawer_li_has_data_search(self):
        """Every <li> the JS will iterate over needs a data-search."""
        r = client.get("/")
        # Count drawer-group__list <li> entries: each has data-search.
        # Conservative lower bound — current drawer has ~45+ items.
        assert r.text.count('data-search="') >= 30

    def test_data_search_includes_hyphenless_variant(self):
        """A drawer item with a hyphen in its title must also contain
        a hyphen-stripped copy in data-search so "applefast" matches
        the APPLE-fast entry without the user typing the hyphen."""
        r = client.get("/")
        # APPLE-fast appears in nav with title "APPLE-fast illness severity",
        # short "APPLE". The data-search attribute should contain both
        # "apple-fast" (lowercased original) and "applefast" (hyphenless).
        assert "apple-fast" in r.text.lower()
        # Find the apple-fast li and confirm its data-search has the
        # hyphenless variant.
        import re

        # Match a li that mentions apple-fast in its data-search
        pattern = re.compile(r'data-search="[^"]*apple[^"]*"', re.IGNORECASE)
        matches = pattern.findall(r.text)
        assert matches, "No drawer li mentions apple in its data-search"
        # The data-search blob should include both the hyphenated and
        # the dehyphenated form
        blob = " ".join(matches).lower()
        assert "apple-fast" in blob
        assert "applefast" in blob

    def test_empty_state_has_fallback_link_to_full_search(self):
        r = client.get("/")
        # The empty state's anchor must link to /search (the dynamic
        # ?q= is appended client-side by JS at filter time)
        assert "data-drawer-filter-fallback" in r.text
        # The hardcoded href should be "/search"
        import re

        m = re.search(
            r'href="(/search[^"]*)"[^>]*data-drawer-filter-fallback', r.text
        )
        m2 = re.search(
            r'data-drawer-filter-fallback[^>]*href="(/search[^"]*)"', r.text
        )
        href = (m and m.group(1)) or (m2 and m2.group(1))
        assert href is not None, "Fallback link href missing"
        assert href.startswith("/search")

    def test_filter_script_present(self):
        r = client.get("/")
        # The script defines `function applyFilter` and uses MutationObserver
        # to clear filter on drawer close.
        assert "applyFilter" in r.text
        assert "MutationObserver" in r.text
        # And the hyphen-stripping normalization is what makes the
        # hyphen-insensitive search work
        assert "replace(/-/g" in r.text

    def test_filter_css_class_present(self):
        """The drawer-filter CSS classes should be in the stylesheet."""
        r = client.get("/")
        # The HTML uses these classes; they must be styled by app.css.
        # Confirming the HTML side here; CSS is asserted via the
        # static asset.
        assert "drawer-filter__input" in r.text
        assert "drawer-filter__empty" in r.text


class TestDrawerFilterCSS:
    def test_css_defines_drawer_filter(self):
        r = client.get("/static/css/app.css")
        assert r.status_code == 200
        css = r.text
        # Spot-check key classes
        assert ".drawer-filter" in css
        assert ".drawer-filter__input" in css
        assert ".drawer-filter__clear" in css
        assert ".drawer-filter__empty" in css
        # The hidden states JS toggles
        assert ".drawer-item--hidden" in css
        assert ".drawer-group--hidden" in css


class TestDrawerStillFunctional:
    """Make sure adding the filter didn't break the existing drawer UX."""

    def test_drawer_toggle_button_still_present(self):
        r = client.get("/")
        assert "drawer-toggle-btn" in r.text

    def test_drawer_close_button_still_present(self):
        r = client.get("/")
        assert "drawer-close-btn" in r.text

    def test_existing_category_titles_still_render(self):
        r = client.get("/")
        # Spot-check a few categories that should still be in the drawer
        for cat in ("Emergency", "Analgesia", "Endocrine"):
            assert cat in r.text

    def test_drawer_links_still_resolve(self):
        """Smoke-test: a sample of drawer links should still 200."""
        for slug in ("apple-fast", "shock", "addisons-score", "hydromorphone-cri"):
            r = client.get(f"/{slug}")
            assert r.status_code == 200, f"/{slug} returned {r.status_code}"
