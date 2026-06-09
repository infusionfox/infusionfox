"""
Default doses on the anesthesia worksheet — locked in.

The picker preselects each drug at a clinically conventional starting dose.
These defaults are clinical decisions, not arbitrary midpoints, so a
regression (someone editing default_dose= or accidentally changing the
display-unit conversion in _drug()) needs to fail loudly.

Defaults are set via the default_dose= parameter on _drug(). The value is
in the DISPLAY unit for the drug — mg/kg for most drugs, µg/kg for
dexmedetomidine — and the helper converts to the storage unit (mg/kg)
internally using the dose_display_multiplier.

Defaults reflect "start low when combining with an opioid" guidance from
Plumb's / Lumb & Jones for premed, and standard induction doses for the
premedicated patient. See docs/anesthesia-worksheet.md for the full table
and reasoning.
"""

from __future__ import annotations

import pytest

from app.calculators.anesthesia_sheet import AnesthSpecies, calculate
from app.calculators.engine import WeightUnit


def _find_drug(drugs, name):
    """Find a drug by name in a list of DrugLines. Fails the test if missing."""
    for d in drugs:
        if d.name == name:
            return d
    pytest.fail(f"{name} not found in drug list: {[d.name for d in drugs]}")


def _effective_dose(drug):
    """Return the displayed dose value (multiplier-adjusted to display units)."""
    return drug.effective_dose_mg_per_kg * drug.dose_display_multiplier


# ──────────────────────────────────────────────────────────────────────
# Dog defaults
# ──────────────────────────────────────────────────────────────────────
class TestDogDefaults:
    """Locked-in dog default doses. All match clinical 'start low' guidance."""

    @pytest.fixture
    def result(self):
        return calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "T", "5y")

    def test_dog_hydromorphone_default_0_1(self, result):
        d = _find_drug(result.premed_opioids, "Hydromorphone")
        assert _effective_dose(d) == pytest.approx(0.1)

    def test_dog_methadone_default_0_2(self, result):
        d = _find_drug(result.premed_opioids, "Methadone")
        assert _effective_dose(d) == pytest.approx(0.2)

    def test_dog_butorphanol_default_0_2(self, result):
        d = _find_drug(result.premed_opioids, "Butorphanol")
        assert _effective_dose(d) == pytest.approx(0.2)

    def test_dog_buprenorphine_default_0_01(self, result):
        d = _find_drug(result.premed_opioids, "Buprenorphine")
        assert _effective_dose(d) == pytest.approx(0.01)

    def test_dog_dexmedetomidine_default_5_ug(self, result):
        """Set via default_dose=5.0 on _drug() (in µg/kg, the display unit).
        Editing that argument now actually changes the default — unlike the
        pre-refactor state where a post-construction rebuild silently
        overwrote it."""
        d = _find_drug(result.premed_sedatives, "Dexmedetomidine")
        assert _effective_dose(d) == pytest.approx(5.0)
        assert d.dose_display_unit == "µg/kg"

    def test_dog_midazolam_default_0_2(self, result):
        d = _find_drug(result.premed_sedatives, "Midazolam")
        assert _effective_dose(d) == pytest.approx(0.2)

    def test_dog_acepromazine_default_0_02(self, result):
        d = _find_drug(result.premed_sedatives, "Acepromazine")
        assert _effective_dose(d) == pytest.approx(0.02)

    def test_dog_propofol_default_6(self, result):
        d = _find_drug(result.induction_drugs, "Propofol")
        assert _effective_dose(d) == pytest.approx(6.0)

    def test_dog_alfaxalone_default_4_5(self, result):
        d = _find_drug(result.induction_drugs, "Alfaxalone")
        assert _effective_dose(d) == pytest.approx(4.5)


# ──────────────────────────────────────────────────────────────────────
# Cat defaults
# ──────────────────────────────────────────────────────────────────────
class TestCatDefaults:
    """Locked-in cat default doses. All match clinical 'start low' guidance
    for cats, which differs from dog defaults for several drugs."""

    @pytest.fixture
    def result(self):
        return calculate(4.0, WeightUnit.KG, AnesthSpecies.CAT, "T", "5y")

    def test_cat_hydromorphone_default_0_05(self, result):
        d = _find_drug(result.premed_opioids, "Hydromorphone")
        assert _effective_dose(d) == pytest.approx(0.05)

    def test_cat_methadone_default_0_2(self, result):
        d = _find_drug(result.premed_opioids, "Methadone")
        assert _effective_dose(d) == pytest.approx(0.2)

    def test_cat_butorphanol_default_0_3(self, result):
        d = _find_drug(result.premed_opioids, "Butorphanol")
        assert _effective_dose(d) == pytest.approx(0.3)

    def test_cat_buprenorphine_default_0_02(self, result):
        d = _find_drug(result.premed_opioids, "Buprenorphine")
        assert _effective_dose(d) == pytest.approx(0.02)

    def test_cat_dexmedetomidine_default_10_ug(self, result):
        """Set via the post-construction rebuild. Matches 'start low (10–20
        µg/kg) when combining with an opioid' guidance."""
        d = _find_drug(result.premed_sedatives, "Dexmedetomidine")
        assert _effective_dose(d) == pytest.approx(10.0)
        assert d.dose_display_unit == "µg/kg"

    def test_cat_midazolam_default_0_2(self, result):
        d = _find_drug(result.premed_sedatives, "Midazolam")
        assert _effective_dose(d) == pytest.approx(0.2)

    def test_cat_acepromazine_default_0_02(self, result):
        d = _find_drug(result.premed_sedatives, "Acepromazine")
        assert _effective_dose(d) == pytest.approx(0.02)

    def test_cat_propofol_default_6(self, result):
        d = _find_drug(result.induction_drugs, "Propofol")
        assert _effective_dose(d) == pytest.approx(6.0)

    def test_cat_alfaxalone_default_5(self, result):
        d = _find_drug(result.induction_drugs, "Alfaxalone")
        assert _effective_dose(d) == pytest.approx(5.0)


# ──────────────────────────────────────────────────────────────────────
# Cross-species sanity checks — these encode WHERE dog and cat differ
# ──────────────────────────────────────────────────────────────────────
class TestSpeciesDifferences:
    """A few drugs have intentionally different defaults across species.
    Locking these in catches anyone who 'cleans up' by copying one side
    to the other."""

    def test_dex_differs_dog_5_cat_10(self):
        dog = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "T", "5y")
        cat = calculate(4.0, WeightUnit.KG, AnesthSpecies.CAT, "T", "5y")
        dog_dex = _find_drug(dog.premed_sedatives, "Dexmedetomidine")
        cat_dex = _find_drug(cat.premed_sedatives, "Dexmedetomidine")
        assert _effective_dose(dog_dex) == pytest.approx(5.0)
        assert _effective_dose(cat_dex) == pytest.approx(10.0)

    def test_hydromorphone_differs_dog_0_1_cat_0_05(self):
        """Cat hydromorphone starts lower than dog ('start at low end',
        per the cat note)."""
        dog = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "T", "5y")
        cat = calculate(4.0, WeightUnit.KG, AnesthSpecies.CAT, "T", "5y")
        dog_hm = _find_drug(dog.premed_opioids, "Hydromorphone")
        cat_hm = _find_drug(cat.premed_opioids, "Hydromorphone")
        assert _effective_dose(dog_hm) == pytest.approx(0.1)
        assert _effective_dose(cat_hm) == pytest.approx(0.05)

    def test_butorphanol_differs_dog_0_2_cat_0_3(self):
        """Cat butorphanol higher than dog (kappa-effect duration shorter
        in cats, often dosed slightly higher for the same effect)."""
        dog = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "T", "5y")
        cat = calculate(4.0, WeightUnit.KG, AnesthSpecies.CAT, "T", "5y")
        dog_but = _find_drug(dog.premed_opioids, "Butorphanol")
        cat_but = _find_drug(cat.premed_opioids, "Butorphanol")
        assert _effective_dose(dog_but) == pytest.approx(0.2)
        assert _effective_dose(cat_but) == pytest.approx(0.3)

    def test_buprenorphine_differs_dog_0_01_cat_0_02(self):
        """Cat bup default at 0.02 (upper end of range); dog at 0.01."""
        dog = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "T", "5y")
        cat = calculate(4.0, WeightUnit.KG, AnesthSpecies.CAT, "T", "5y")
        dog_bup = _find_drug(dog.premed_opioids, "Buprenorphine")
        cat_bup = _find_drug(cat.premed_opioids, "Buprenorphine")
        assert _effective_dose(dog_bup) == pytest.approx(0.01)
        assert _effective_dose(cat_bup) == pytest.approx(0.02)

    def test_alfaxalone_differs_dog_4_5_cat_5(self):
        """Cat alfaxalone slightly higher (cats need 5 mg/kg with typical
        premed; dogs 4.5)."""
        dog = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "T", "5y")
        cat = calculate(4.0, WeightUnit.KG, AnesthSpecies.CAT, "T", "5y")
        dog_alf = _find_drug(dog.induction_drugs, "Alfaxalone")
        cat_alf = _find_drug(cat.induction_drugs, "Alfaxalone")
        assert _effective_dose(dog_alf) == pytest.approx(4.5)
        assert _effective_dose(cat_alf) == pytest.approx(5.0)


class TestDefaultsAreWithinRange:
    """Every default must sit inside the published low–high range for that
    drug. A default outside the range would be clinically wrong AND would
    interact badly with the _inject_chosen_doses clamping logic."""

    @pytest.mark.parametrize("species,weight", [
        (AnesthSpecies.DOG, 20.0),
        (AnesthSpecies.CAT, 4.0),
    ])
    def test_all_defaults_within_published_range(self, species, weight):
        result = calculate(weight, WeightUnit.KG, species, "T", "5y")
        for drug_list in (result.premed_opioids, result.premed_sedatives,
                          result.induction_drugs):
            for d in drug_list:
                if d.chosen_dose_mg_per_kg > 0:  # has a default set
                    assert d.dose_mg_per_kg_low <= d.chosen_dose_mg_per_kg <= d.dose_mg_per_kg_high, (
                        f"{species.value} {d.name}: default "
                        f"{d.chosen_dose_mg_per_kg} mg/kg outside range "
                        f"{d.dose_mg_per_kg_low}-{d.dose_mg_per_kg_high} mg/kg"
                    )


# ──────────────────────────────────────────────────────────────────────
# Dex range bounds — pinned explicitly
# ──────────────────────────────────────────────────────────────────────
class TestDexRanges:
    """Lock in the dose range bounds for dexmedetomidine in both species.

    Dex is the only drug whose display unit (µg/kg) differs from the
    storage unit (mg/kg), so it's the only drug where a unit-conversion
    bug in _drug() could silently produce ranges that are off by a
    factor of 1000. These assertions check the rendered display-unit
    range, so a regression in the conversion logic fails here with a
    clear numeric mismatch — rather than the user seeing a 0.003 µg/kg
    range that looks plausible-but-wrong on the worksheet.
    """

    def test_dog_dex_range_3_to_20_ug_per_kg(self):
        r = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "", "")
        d = _find_drug(r.premed_sedatives, "Dexmedetomidine")
        low_display = d.dose_mg_per_kg_low * d.dose_display_multiplier
        high_display = d.dose_mg_per_kg_high * d.dose_display_multiplier
        assert low_display == pytest.approx(3.0), (
            f"Dog dex low: {low_display} µg/kg (expected 3.0). If you see "
            f"0.003 or 3000, the _drug() unit conversion is broken."
        )
        assert high_display == pytest.approx(20.0)

    def test_cat_dex_range_10_to_40_ug_per_kg(self):
        r = calculate(4.0, WeightUnit.KG, AnesthSpecies.CAT, "", "")
        d = _find_drug(r.premed_sedatives, "Dexmedetomidine")
        low_display = d.dose_mg_per_kg_low * d.dose_display_multiplier
        high_display = d.dose_mg_per_kg_high * d.dose_display_multiplier
        assert low_display == pytest.approx(10.0)
        assert high_display == pytest.approx(40.0)

    def test_dex_storage_in_mg_per_kg(self):
        """The DrugLine's stored low/high should be in mg/kg regardless of
        display unit. Dog dex 3 µg/kg → 0.003 mg/kg in storage; the
        worksheet's volume math depends on storage being in mg/kg."""
        r = calculate(20.0, WeightUnit.KG, AnesthSpecies.DOG, "", "")
        d = _find_drug(r.premed_sedatives, "Dexmedetomidine")
        assert d.dose_mg_per_kg_low == pytest.approx(0.003)
        assert d.dose_mg_per_kg_high == pytest.approx(0.020)
