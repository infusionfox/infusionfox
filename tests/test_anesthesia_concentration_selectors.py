"""
Pin: anesthesia worksheet per-drug concentration selectors.

The worksheet picker exposes a stock-concentration sub-selector for
drugs listed in STOCK_OPTIONS (see app/calculators/anesthesia_sheet.py).
The selected concentration round-trips through the form as a `stock_{drug}`
field, the router validates it against STOCK_OPTIONS and rejects unknown
values, then calculate() binds it to a ContextVar that _drug() and the
emergency-drug call sites read through `_stock_for()` and `_stock_label_for()`.

These tests pin:
- selectors render with correct option lists in the picker
- the chosen concentration drives volume math
- the printed label reflects the user's choice
- invalid values silently fall back to defaults (defense in depth)
- consecutive calls don't leak ContextVar state across requests
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.calculators.anesthesia_sheet import (
    STOCK_OPTIONS,
    STOCKS,
    AnesthSpecies,
    calculate,
)
from app.calculators.engine import WeightUnit
from app.main import app

client = TestClient(app)


# ---------- STOCK_OPTIONS data ----------


class TestStockOptionsData:
    def test_all_keys_exist_in_stocks(self):
        """Every drug in STOCK_OPTIONS must also have a default in STOCKS."""
        for drug_key in STOCK_OPTIONS:
            assert drug_key in STOCKS, f"STOCK_OPTIONS includes {drug_key!r} but STOCKS has no default"

    def test_default_option_matches_stocks_default(self):
        """The first option in each STOCK_OPTIONS tuple is the default,
        and must match the value in STOCKS so the picker pre-selects the
        right row on initial render."""
        for drug_key, options in STOCK_OPTIONS.items():
            default_value, _label = options[0]
            assert default_value == STOCKS[drug_key], (
                f"{drug_key}: STOCK_OPTIONS default {default_value} doesn't "
                f"match STOCKS default {STOCKS[drug_key]}"
            )

    def test_no_duplicate_values_per_drug(self):
        """Each drug's option list must have unique concentration values."""
        for drug_key, options in STOCK_OPTIONS.items():
            values = [v for v, _label in options]
            assert len(values) == len(set(values)), f"{drug_key}: duplicate values in STOCK_OPTIONS: {values}"

    def test_currently_exposed_drugs(self):
        """Pin the current set so adding/removing a drug is a deliberate
        change with a test update, not a silent drift."""
        assert set(STOCK_OPTIONS.keys()) == {
            "hydromorphone",
            "midazolam",
            "dexmedetomidine",
            "atropine",
            "naloxone",
        }


# ---------- Picker selector rendering ----------


def _post_compute(species="dog", **overrides):
    """Helper: POST /anesthesia/compute with a default 20 kg patient
    plus any stock_* overrides the test wants."""
    data = {"weight_value": "20", "weight_unit": "kg", "species": species}
    data.update(overrides)
    return client.post("/anesthesia/compute", data=data)


class TestSelectorRendering:
    def test_all_expected_selectors_render(self):
        r = _post_compute()
        selectors = set(re.findall(r'<select name="stock_(\w+)"', r.text))
        # Every drug in STOCK_OPTIONS that surfaces in a picker should
        # have a selector. Currently that's all 5.
        assert selectors == set(STOCK_OPTIONS.keys()), (
            f"Mismatch: rendered selectors {selectors}, " f"STOCK_OPTIONS keys {set(STOCK_OPTIONS.keys())}"
        )

    def test_hydromorphone_selector_has_four_options(self):
        r = _post_compute()
        m = re.search(
            r'<select name="stock_hydromorphone"[^>]*>(.*?)</select>',
            r.text,
            flags=re.DOTALL,
        )
        assert m, "hydromorphone selector not rendered"
        opt_values = re.findall(r'<option value="([\d.]+)"', m.group(1))
        assert sorted(float(v) for v in opt_values) == [1.0, 2.0, 4.0, 10.0]

    def test_default_option_pre_selected(self):
        """On initial render with no stock_* posted, the default (2 mg/mL
        for hydromorphone) should be the selected option."""
        r = _post_compute()
        m = re.search(
            r'<select name="stock_hydromorphone"[^>]*>(.*?)</select>',
            r.text,
            flags=re.DOTALL,
        )
        # Find the option with `selected`
        sel = re.search(r'<option value="([\d.]+)"\s+selected', m.group(1))
        assert sel and float(sel.group(1)) == 2.0


# ---------- Effective stock + label ----------


class TestStockOverride:
    def test_default_when_no_override(self):
        """No stock_* field posted → STOCKS defaults apply unchanged."""
        r = _post_compute()
        # Hydromorphone default label is "2 mg/mL (standard)"
        # in STOCK_OPTIONS — that's what the printed sheet should show.
        assert "2 mg/mL (standard)" in r.text

    def test_override_changes_label(self):
        """POST stock_hydromorphone=4 → printed label reflects choice."""
        r = _post_compute(stock_hydromorphone="4")
        assert "4 mg/mL" in r.text
        # The pre-2-mg/mL default label should no longer dominate;
        # specifically the "(standard)" parenthetical should
        # be replaced with a different label.
        m = re.search(
            r'<select name="stock_hydromorphone"[^>]*>(.*?)</select>',
            r.text,
            flags=re.DOTALL,
        )
        # The 4.0 option should now be the selected one.
        sel = re.search(r'<option value="4\.0?"\s+selected', m.group(1))
        assert sel, "After stock_hydromorphone=4, the 4 mg/mL option should be selected"

    def test_override_changes_volume_math(self):
        """Hydromorphone at 0.1 mg/kg × 20 kg = 2 mg.
        At 2 mg/mL stock: 1.0 mL. At 4 mg/mL stock: 0.5 mL."""
        # Calculate directly at both concentrations and compare via
        # the engine, which is the deterministic path.
        from app.calculators.anesthesia_sheet import calculate

        r_default = calculate(
            20.0,
            WeightUnit.KG,
            AnesthSpecies.DOG,
        )
        r_strong = calculate(
            20.0,
            WeightUnit.KG,
            AnesthSpecies.DOG,
            chosen_stocks={"hydromorphone": 4.0},
        )
        hydro_default = next(d for d in r_default.premed_opioids if d.name == "Hydromorphone")
        hydro_strong = next(d for d in r_strong.premed_opioids if d.name == "Hydromorphone")
        # vol_low at default 2 mg/mL = (0.05 × 20) / 2 = 0.5 mL
        # vol_low at 4 mg/mL = (0.05 × 20) / 4 = 0.25 mL
        assert hydro_default.vol_low_ml == pytest.approx(0.5, abs=0.01)
        assert hydro_strong.vol_low_ml == pytest.approx(0.25, abs=0.01)


class TestInvalidStockFallback:
    """Invalid stock values must silently fall back to the default,
    never compute volumes against an out-of-list concentration. This
    is defense in depth against stale browser tabs and adversarial posts."""

    def test_unknown_value_falls_back(self):
        """stock_hydromorphone=99 (not in STOCK_OPTIONS) → default applied."""
        r = _post_compute(stock_hydromorphone="99")
        # Default label should still appear.
        assert "2 mg/mL (standard)" in r.text
        # The 4 mg/mL option should NOT be the selected one.
        m = re.search(
            r'<select name="stock_hydromorphone"[^>]*>(.*?)</select>',
            r.text,
            flags=re.DOTALL,
        )
        sel = re.search(r'<option value="([\d.]+)"\s+selected', m.group(1))
        assert sel and float(sel.group(1)) == 2.0

    def test_non_numeric_value_falls_back(self):
        """stock_hydromorphone=abc → ValueError → default applied."""
        r = _post_compute(stock_hydromorphone="abc")
        assert r.status_code == 200
        assert "2 mg/mL (standard)" in r.text

    def test_unknown_drug_key_ignored(self):
        """stock_zzz=99 (no STOCK_OPTIONS entry for 'zzz') → silently
        ignored. No errors, no effect."""
        r = _post_compute(stock_zzz="99")
        assert r.status_code == 200


class TestEmergencyDrugOverride:
    """Atropine and naloxone are in the emergency-drug section, not the
    opioid/sedative/induction picker. Their concentrations come through
    _emerg() call sites that use _stock_for/_stock_label_for."""

    def test_atropine_override_label(self):
        """After picking 0.4 mg/mL, the printed worksheet's atropine
        stock should reflect the alternative. Under the unified label
        format, alternatives are bare values with no parenthetical and
        the default is the one tagged "(standard)". So a successful
        override means the (standard)-tagged 0.54 row is no longer the
        selected dropdown option."""
        r = _post_compute(stock_atropine="0.4")
        # The 0.4 option should be the selected one in the dropdown.
        m = re.search(
            r'<select name="stock_atropine"[^>]*>(.*?)</select>',
            r.text,
            flags=re.DOTALL,
        )
        assert m, "atropine selector not rendered"
        sel = re.search(r'<option value="0\.4"\s+selected', m.group(1))
        assert sel, "After stock_atropine=0.4, the 0.4 mg/mL option should be " "the selected dropdown row."

    def test_atropine_override_volume(self):
        """0.02 mg/kg × 20 kg = 0.4 mg.
        At 0.54 mg/mL: 0.741 mL. At 0.4 mg/mL: 1.0 mL."""
        r_default = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG)
        r_alt = calculate(
            20.0,
            WeightUnit.KG,
            AnesthSpecies.DOG,
            chosen_stocks={"atropine": 0.4},
        )
        atro_default = next(d for d in r_default.emergency_drugs if d.name == "Atropine")
        atro_alt = next(d for d in r_alt.emergency_drugs if d.name == "Atropine")
        # Atropine low dose = 0.02 mg/kg
        assert atro_default.vol_low_ml == pytest.approx(0.741, abs=0.01)
        assert atro_alt.vol_low_ml == pytest.approx(1.0, abs=0.01)

    def test_naloxone_override(self):
        r = _post_compute(stock_naloxone="1.0")
        assert "1 mg/mL" in r.text  # the alt label

    def test_picker_has_emergency_section(self):
        r = _post_compute()
        assert 'data-category="emergency-stocks"' in r.text
        assert "Emergency drug concentrations" in r.text


# ---------- ContextVar safety ----------


class TestContextVarReset:
    """The ContextVar that holds chosen_stocks must reset between
    calculate() calls so concurrent requests don't leak state. We can't
    easily simulate true concurrency in a unit test, but we can verify
    that two sequential calls with different chosen_stocks don't bleed
    into each other."""

    def test_sequential_calls_dont_leak(self):
        # First call: override hydromorphone to 4 mg/mL
        r1 = calculate(
            20.0,
            WeightUnit.KG,
            AnesthSpecies.DOG,
            chosen_stocks={"hydromorphone": 4.0},
        )
        hydro1 = next(d for d in r1.premed_opioids if d.name == "Hydromorphone")
        assert hydro1.stock_mg_per_ml == 4.0

        # Second call: no overrides. Hydromorphone should be back to 2.0.
        r2 = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG)
        hydro2 = next(d for d in r2.premed_opioids if d.name == "Hydromorphone")
        assert (
            hydro2.stock_mg_per_ml == 2.0
        ), f"Sequential calculate() leaked ContextVar state: got {hydro2.stock_mg_per_ml}"

    def test_empty_chosen_stocks_same_as_none(self):
        r_none = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG)
        r_empty = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, chosen_stocks={})
        h_none = next(d for d in r_none.premed_opioids if d.name == "Hydromorphone")
        h_empty = next(d for d in r_empty.premed_opioids if d.name == "Hydromorphone")
        assert h_none.stock_mg_per_ml == h_empty.stock_mg_per_ml
