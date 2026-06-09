"""Form-value parsing helpers shared across calculator routes.

The default FastAPI behavior of ``weight_value: float = Form(...)`` returns
a 422 error when the user submits a partial value like "4." mid-typing.
HTMX swaps that error into the page (or nothing visible), and the user
sees the previous result stuck on screen. That is dangerous when
"the previous result" was for a different patient weight.

These helpers let routes accept raw strings from the form, parse them
defensively, and return ``None`` when the input is unparseable or
out-of-range. Callers should treat ``None`` as "show the placeholder
result, do not compute with stale data."

All parsed numeric values are rounded to 2 decimal places to give the
calculator a deterministic input. InfusionFox math is bedside math; precision
beyond hundredths is spurious for any weight, dose, or concentration the
clinician will actually transcribe to the chart.
"""

from __future__ import annotations

_ROUNDING_PLACES = 2


def parse_positive_float(raw: str | None) -> float | None:
    """Parse a positive float to 2 decimal places.

    Returns ``None`` for empty strings, partial input ("4.", "-"),
    non-numeric input ("abc"), or non-positive values (0, negatives).

    Always rounds to hundredths.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        value = float(s)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return round(value, _ROUNDING_PLACES)


def parse_nonneg_float(raw: str | None) -> float | None:
    """Parse a non-negative float to 2 decimal places.

    Use for fields where 0 is a meaningful input (eg, ongoing losses,
    eosinophil count). Returns ``None`` for empty/unparseable input.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        value = float(s)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return round(value, _ROUNDING_PLACES)


def parse_float_with_default(raw: str | None, default: float) -> float:
    """Parse a float, falling back to a sensible default.

    Use only for optional fields where falling back to a fixed default
    is safe (eg, replacement_hours defaults to 48, dextrose ratio
    defaults to 2.5). Never use for required inputs like patient weight.
    """
    if raw is None:
        return round(default, _ROUNDING_PLACES)
    s = raw.strip()
    if not s:
        return round(default, _ROUNDING_PLACES)
    try:
        value = float(s)
    except (TypeError, ValueError):
        return round(default, _ROUNDING_PLACES)
    return round(value, _ROUNDING_PLACES)
