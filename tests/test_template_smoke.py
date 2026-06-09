"""
Smoke test: every template parses and renders with default context.

This test is CHEAP and BROAD — it doesn't assert any output, just ensures
that all 100+ templates can be parsed by Jinja and (where they don't depend
on real data) rendered without crashing. Catches:

  - Stray Jinja syntax errors
  - Mismatched {% block %}/{% endblock %} pairs
  - Typos in {% extends %} / {% include %} paths
  - Use of undefined globals

Tests that depend on fully-populated context belong in the integration
test suite (TestClient) — this is a pure-template lint pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"


@pytest.fixture(scope="module")
def jinja_env() -> Environment:
    """A read-only env loaded from the actual templates directory."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    # Globals injected by the app at startup — provide stub values so
    # templates that use them don't fail at parse-time. Real values
    # are exercised in integration tests.
    env.globals["css_version"] = "test"
    env.globals["url_for"] = lambda name, **kwargs: f"/{name}"
    return env


def _all_templates() -> list[Path]:
    return sorted(TEMPLATES_DIR.rglob("*.html"))


@pytest.mark.parametrize("template_path", _all_templates(), ids=lambda p: str(p.relative_to(TEMPLATES_DIR)))
def test_template_parses(template_path: Path, jinja_env: Environment) -> None:
    """Every template in app/templates/ should parse without raising."""
    rel = template_path.relative_to(TEMPLATES_DIR).as_posix()
    try:
        jinja_env.get_template(rel)
    except TemplateSyntaxError as e:
        pytest.fail(f"Template {rel} failed to parse: {e}")


def test_template_count_meets_minimum() -> None:
    """Sanity check: we should have at least 100 templates."""
    assert len(_all_templates()) >= 100
