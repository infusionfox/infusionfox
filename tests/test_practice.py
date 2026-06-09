"""Tests for the practice-problem registry and routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.practice import PROBLEMS, get_problem, problems_by_topic, topics


@pytest.fixture
def client():
    return TestClient(app)


class TestRegistry:
    def test_problems_present(self):
        # Lower bound: we always have at least ten problems. The exact
        # count grows over time; tests should track the registry rather
        # than a hardcoded number.
        assert len(PROBLEMS) >= 10

    def test_slugs_unique(self):
        slugs = [p.slug for p in PROBLEMS]
        assert len(slugs) == len(set(slugs))

    def test_every_problem_has_scenario_and_steps_and_answer(self):
        for p in PROBLEMS:
            assert p.scenario, f"{p.slug} missing scenario"
            assert p.steps, f"{p.slug} has no steps"
            assert p.final_answer, f"{p.slug} missing final answer"

    def test_every_problem_has_two_hints(self):
        for p in PROBLEMS:
            assert len(p.hints) == 2, (
                f"{p.slug} has {len(p.hints)} hints; expected 2 progressive hints"
            )
            for h in p.hints:
                assert h.strip(), f"{p.slug} has an empty hint"

    def test_difficulty_values_known(self):
        allowed = {"Intro", "Clinical", "Advanced"}
        for p in PROBLEMS:
            assert p.difficulty in allowed, f"{p.slug} difficulty={p.difficulty!r}"

    def test_topics_span_at_least_four(self):
        # We want breadth, not all problems on one topic
        assert len(topics()) >= 4

    def test_problems_by_topic_covers_everything(self):
        flat = [p for _, ps in problems_by_topic() for p in ps]
        assert len(flat) == len(PROBLEMS)

    def test_every_problem_has_expected_answer(self):
        for p in PROBLEMS:
            assert p.checks, f"{p.slug} has no answer checks"
            for c in p.checks:
                assert c.label, f"{p.slug} check has empty label"
                if c.choices is None:
                    assert c.unit, f"{p.slug} numeric check missing unit"

    def test_two_mlk_problems_grouped_together(self):
        # P4 and P8 should both be in the same topic, with P8 immediately
        # after P4 in registry order so the index renders them adjacent.
        slugs = [p.slug for p in PROBLEMS]
        i_bag = slugs.index("mlk-bag-build-24hr")
        i_waste = slugs.index("mlk-waste-100ml")
        assert i_waste == i_bag + 1, (
            "MLK waste problem should appear immediately after MLK bag build"
        )
        bag = next(p for p in PROBLEMS if p.slug == "mlk-bag-build-24hr")
        waste = next(p for p in PROBLEMS if p.slug == "mlk-waste-100ml")
        assert bag.topic == waste.topic, (
            f"MLK problems split across topics: {bag.topic!r} vs {waste.topic!r}"
        )

    def test_every_problem_has_background_link(self):
        for p in PROBLEMS:
            assert p.related_background_url, f"{p.slug} missing related_background_url"
            assert p.related_background_name, f"{p.slug} missing related_background_name"
            assert p.related_background_url.startswith("/learn/"), (
                f"{p.slug} background URL should start with /learn/, got {p.related_background_url!r}"
            )

    def test_background_links_resolve(self, client):
        # Every background link should point to a real /learn page (not 404).
        for p in PROBLEMS:
            if p.related_background_url:
                r = client.get(p.related_background_url)
                assert r.status_code == 200, (
                    f"{p.slug} background URL {p.related_background_url} → {r.status_code}"
                )

    def test_background_links_visible_outside_details(self, client):
        # The reference links (clinical background + calculator) must be
        # rendered AFTER the worked-answer </details>, so they're visible
        # without expanding the solution. A previous version had them
        # inside the details body, which hid them by default.
        import re
        r = client.get("/learn/practice")
        # For each problem, the refs block should appear after the
        # </details> that closes its practice-card__solution.
        # Pattern: '</details>' (closing solution) ... 'practice-card__refs'
        # ... '</article>' (closing card)
        article_pattern = re.compile(
            r'<details[^>]*class="practice-card__solution"[^>]*>.*?</details>'
            r'(.*?)</article>',
            re.DOTALL,
        )
        articles = article_pattern.findall(r.text)
        assert len(articles) == len(PROBLEMS), (
            f"Expected {len(PROBLEMS)} articles, got {len(articles)}"
        )
        for i, tail in enumerate(articles):
            assert "practice-card__refs" in tail, (
                f"Article {i}: refs block not found after solution </details>"
            )


class TestLookup:
    def test_get_problem_known_slug(self):
        p = get_problem("fentanyl-cri-12kg")
        assert p is not None
        assert p.slug == "fentanyl-cri-12kg"

    def test_get_problem_unknown_slug(self):
        assert get_problem("does-not-exist") is None


class TestRoutes:
    def test_index_renders(self, client):
        r = client.get("/learn/practice")
        assert r.status_code == 200
        # Every problem title should appear on the index
        for p in PROBLEMS:
            assert p.title in r.text, f"{p.slug} title missing from index"

    def test_index_answers_collapsed_by_default(self, client):
        r = client.get("/learn/practice")
        # <details> with no `open` attribute is the markup for collapsed
        assert "<details" in r.text
        # The reveal label is the summary, present whether expanded or not
        assert "Show worked answer" in r.text

    def test_single_problem_route(self, client):
        r = client.get("/learn/practice/mlk-bag-build-24hr")
        assert r.status_code == 200
        assert "MLK bag" in r.text

    def test_unknown_problem_404(self, client):
        r = client.get("/learn/practice/no-such-problem")
        assert r.status_code == 404

    def test_practice_in_top_nav(self, client):
        r = client.get("/")
        # The top-nav link is now /learn (the Learn index), which contains
        # the practice problem section. /learn/practice still works as a
        # direct URL but is no longer the primary nav target.
        assert 'href="/learn"' in r.text

    def test_answer_check_renders(self, client):
        r = client.get("/learn/practice")
        # Every problem renders at least one practice-check block. P4 has
        # 5, P8 has 2, P10 has 3, others have 1 → 1+2+2+5+2+1+1+1+1+3 = 19
        assert r.text.count('class="practice-check') >= 19
        # Numeric mode driven by data-expected + data-tolerance
        assert 'data-expected="1.2"' in r.text  # P1 fentanyl
        assert 'data-mode="numeric"' in r.text
        # P4's MC bag-size check
        assert 'data-mode="mc"' in r.text
        assert "250 mL" in r.text  # the correct bag-size option
        # The inline script is included
        assert "practice-check__btn" in r.text
        assert "FEEDBACK_CORRECT" in r.text

    def test_mc_radios_form_real_groups(self, client):
        """Every multiple-choice check must have its radios share a `name`
        so the browser treats them as one radio group. Without this, all
        clicked options stay checked simultaneously and the user can't
        change their answer after the first Check — they're stuck with
        whatever they originally picked (the JS handler reads the first
        :checked radio in document order).

        Bug history: the template originally interpolated `loop.index0`
        twice into the name, but inside the nested choice loop `loop`
        refers to the choice index, not the check index. Every radio
        got a unique name and they were independent inputs that
        happened to look like a radio group. This regression test
        catches the same shape of bug if the template is refactored
        without preserving the outer-loop alias.
        """
        import re
        from collections import Counter

        for p in PROBLEMS:
            # Skip problems with no MC checks
            mc_checks = [
                chk for chk in p.checks if getattr(chk, "choices", None)
            ]
            if not mc_checks:
                continue
            r = client.get(f"/learn/practice/{p.slug}")
            assert r.status_code == 200, f"{p.slug}: {r.status_code}"
            radios = re.findall(
                r'<input type="radio"\s+name="([^"]+)"\s+value="([^"]+)"',
                r.text,
            )
            counts = Counter(name for name, _ in radios)
            orphans = {n for n, k in counts.items() if k == 1}
            assert not orphans, (
                f"{p.slug}: every radio name should appear at least twice "
                f"(one per choice in a group). Orphans found: {orphans}. "
                f"This means the radios are not grouped and the user "
                f"can't change their answer after submitting."
            )
            # Sanity: number of distinct names equals number of MC checks
            assert len(counts) == len(mc_checks), (
                f"{p.slug}: expected {len(mc_checks)} radio groups, "
                f"got {len(counts)} distinct names ({sorted(counts)})"
            )
            # Within each group, choice values cover 0..N-1 with no gaps
            # or duplicates.
            for group_name in counts:
                values = sorted(
                    int(v) for n, v in radios if n == group_name
                )
                assert values == list(range(len(values))), (
                    f"{p.slug}/{group_name}: choice values should be "
                    f"0..N-1 with no gaps or duplicates, got {values}"
                )

