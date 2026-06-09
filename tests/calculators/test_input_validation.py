"""
Validation-failure behavior for every calculator.

When inputs are invalid (missing, zero, or negative for fields that the
calculator can't meaningfully use), the calculator MUST:
1. Return a result with `valid=False`.
2. Zero out (or None) every numeric output field — never produce a
   negative dose, negative rate, or any other plausible-but-wrong number.
3. Surface the validation error in `warnings`.
4. Not raise any exception (in particular, no ZeroDivisionError on
   zero concentration).

These tests are the safety net that keeps a clinician from ever seeing
a computed dose alongside an "input must be > 0" message. See
engine.CalcResult.valid for the design rationale.
"""

from __future__ import annotations

import pytest

from app.calculators import (
    CalcInputs,
    DilutionInputs,
    Species,
    WeightUnit,
    compute,
    compute_dilution,
    get_drug,
)


def _norepi():
    return get_drug("norepinephrine")


# ---------------------------------------------------------------------------
# Engine: SINGLE_DRUG_CRI
# ---------------------------------------------------------------------------


class TestEngineComputeValidation:
    """The shared CRI engine must short-circuit on bad inputs, not crash
    or produce negative rates."""

    def test_negative_weight_returns_invalid(self):
        r = compute(
            _norepi(),
            CalcInputs(
                weight_value=-5,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=80,
                species=Species.DOG,
            ),
        )
        assert r.valid is False
        assert r.ml_per_hr_precise == 0.0
        assert r.ml_per_hr_pump == 0.0
        assert r.total_dose_ug_per_hr == 0.0
        assert any("Weight" in w for w in r.warnings)

    def test_zero_weight_returns_invalid(self):
        r = compute(
            _norepi(),
            CalcInputs(
                weight_value=0,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=80,
                species=Species.DOG,
            ),
        )
        assert r.valid is False

    def test_zero_dose_returns_invalid(self):
        r = compute(
            _norepi(),
            CalcInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose=0,
                concentration_ug_per_ml=80,
                species=Species.DOG,
            ),
        )
        assert r.valid is False
        assert any("Dose" in w for w in r.warnings)

    def test_zero_concentration_does_not_raise(self):
        """Pre-fix, this raised ZeroDivisionError and 500'd the request."""
        r = compute(
            _norepi(),
            CalcInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=0,
                species=Species.DOG,
            ),
        )
        assert r.valid is False
        assert r.ml_per_hr_precise == 0.0
        assert any("Concentration" in w for w in r.warnings)

    def test_negative_concentration_returns_invalid(self):
        r = compute(
            _norepi(),
            CalcInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=-50,
                species=Species.DOG,
            ),
        )
        assert r.valid is False

    def test_valid_inputs_remain_valid(self):
        r = compute(
            _norepi(),
            CalcInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose=0.1,
                concentration_ug_per_ml=80,
                species=Species.DOG,
            ),
        )
        assert r.valid is True
        assert r.ml_per_hr_precise > 0


# ---------------------------------------------------------------------------
# Engine: dilution helper
# ---------------------------------------------------------------------------


class TestDilutionValidation:
    def test_zero_stock_returns_invalid_no_crash(self):
        r = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=0,
                desired_concentration_ug_per_ml=100,
                final_volume_ml=50,
            )
        )
        assert r.valid is False
        assert r.drug_volume_ml == 0.0

    def test_desired_exceeds_stock_returns_invalid(self):
        r = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=100,
                desired_concentration_ug_per_ml=200,
                final_volume_ml=50,
            )
        )
        assert r.valid is False
        assert any("dilute upward" in w or "exceed" in w for w in r.warnings)

    def test_valid_dilution_works(self):
        r = compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=10000,
                desired_concentration_ug_per_ml=1000,
                final_volume_ml=50,
            )
        )
        assert r.valid is True
        assert r.drug_volume_ml > 0


# ---------------------------------------------------------------------------
# Bespoke calculators — one parametrized test per calculator that confirms
# the invalid path. Each test passes inputs that should fail validation
# and asserts (a) valid is False, (b) primary numeric output is zeroed,
# (c) no exception was raised.
# ---------------------------------------------------------------------------


def test_fluid_therapy_invalid_weight():
    from app.calculators.fluid_therapy import (
        FluidTherapyInputs,
        FluidTherapySpecies,
        compute_fluid_therapy,
    )

    r = compute_fluid_therapy(
        FluidTherapyInputs(
            weight_value=-5,
            weight_unit=WeightUnit.KG,
            species=FluidTherapySpecies.DOG,
            in_shock=False,
            dehydration_band_key="moderate",
            rehydration_window_hr=12,
            maintenance_mlpkg_hr=3.0,
        )
    )
    assert r.valid is False
    assert r.deficit_ml == 0.0
    assert r.rehydration_rate_ml_per_hr == 0.0
    assert r.maintenance_rate_ml_per_hr == 0.0
    assert r.active_phase_rate_ml_per_hr == 0.0


def test_insulin_cri_dka_invalid_weight():
    from app.calculators.insulin_cri_dka import (
        InsulinCriCatDoseOption,
        InsulinCriInputs,
        InsulinCriSpecies,
        compute_insulin_cri,
    )

    r = compute_insulin_cri(
        InsulinCriInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            species=InsulinCriSpecies.DOG,
            blood_glucose_mg_per_dl=400,
            cat_dose_option=InsulinCriCatDoseOption.STANDARD_2_2,
        )
    )
    assert r.valid is False
    assert r.total_units_added_to_bag == 0.0
    assert r.bag_concentration_units_per_ml == 0.0


def test_insulin_cri_dka_invalid_bg():
    from app.calculators.insulin_cri_dka import (
        InsulinCriCatDoseOption,
        InsulinCriInputs,
        InsulinCriSpecies,
        compute_insulin_cri,
    )

    r = compute_insulin_cri(
        InsulinCriInputs(
            weight_value=20,
            weight_unit=WeightUnit.KG,
            species=InsulinCriSpecies.DOG,
            blood_glucose_mg_per_dl=0,
            cat_dose_option=InsulinCriCatDoseOption.STANDARD_2_2,
        )
    )
    assert r.valid is False


def test_insulin_im_dka_invalid_weight():
    from app.calculators.insulin_im_dka import (
        InsulinImInputs,
        InsulinImMode,
        InsulinImSpecies,
        compute_insulin_im,
    )

    r = compute_insulin_im(
        InsulinImInputs(
            weight_value=0,
            weight_unit=WeightUnit.KG,
            species=InsulinImSpecies.DOG,
            mode=InsulinImMode.LOADING,
        )
    )
    assert r.valid is False
    assert r.total_units == 0.0
    assert r.volume_ml_u100 == 0.0


def test_ca_gluconate_invalid_weight():
    """Pre-fix this substituted weight_kg=0.001, producing a plausible
    but wildly wrong dose."""
    from app.calculators.ca_gluconate import (
        CaGluconateInputs,
        CaGluconateSpecies,
        compute_ca_gluconate,
    )

    r = compute_ca_gluconate(
        CaGluconateInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            species=CaGluconateSpecies.DOG,
        )
    )
    assert r.valid is False
    assert r.total_volume_ml == 0.0
    assert r.total_dose_mg == 0.0
    assert r.elemental_ca_mg == 0.0


def test_lidocaine_invalid_weight():
    from app.calculators.lidocaine import (
        LidocaineDoseUnit,
        LidocaineInputs,
        LidocaineSpecies,
        compute_lidocaine,
    )

    r = compute_lidocaine(
        LidocaineInputs(
            weight_value=-10,
            weight_unit=WeightUnit.KG,
            species=LidocaineSpecies.DOG,
            dose_value=2.0,
            dose_unit=LidocaineDoseUnit.MG_PER_KG_PER_HR,
        )
    )
    assert r.valid is False
    assert r.pump_rate_ml_per_hr == 0.0
    assert r.loading_dose_min_mg == 0.0


def test_hypokalemia_invalid_weight():
    from app.calculators.hypokalemia import (
        BagSize,
        HypokalemiaInputs,
        compute_hypokalemia,
    )

    r = compute_hypokalemia(
        HypokalemiaInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            serum_k_meq_per_l=3.0,
            bag_size=BagSize.BAG_250,
        )
    )
    assert r.valid is False
    assert r.kcl_to_add_meq == 0
    assert r.max_pump_rate_ml_per_hr == 0.0


def test_hypokalemia_invalid_serum_k():
    from app.calculators.hypokalemia import (
        BagSize,
        HypokalemiaInputs,
        compute_hypokalemia,
    )

    r = compute_hypokalemia(
        HypokalemiaInputs(
            weight_value=20,
            weight_unit=WeightUnit.KG,
            serum_k_meq_per_l=0,
            bag_size=BagSize.BAG_250,
        )
    )
    assert r.valid is False


def test_hypomagnesemia_invalid_weight():
    from app.calculators.hypomagnesemia import (
        HypomagnesemiaInputs,
        MgSpecies,
        MgStockConcentration,
        compute_hypomagnesemia,
    )

    r = compute_hypomagnesemia(
        HypomagnesemiaInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            species=MgSpecies.DOG,
            serum_mg_mg_per_dl=1.0,
            stock_concentration=MgStockConcentration.PCT_50,
        )
    )
    assert r.valid is False
    assert r.pump_rate_ml_per_hr is None or r.pump_rate_ml_per_hr == 0.0


def test_hypophosphatemia_invalid_weight():
    from app.calculators.hypophosphatemia import (
        HypophosphatemiaInputs,
        KPhosSpecies,
        compute_hypophosphatemia,
    )

    r = compute_hypophosphatemia(
        HypophosphatemiaInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            species=KPhosSpecies.DOG,
            serum_p_mg_per_dl=1.0,
        )
    )
    assert r.valid is False
    assert r.kphos_pump_rate_ml_per_hr is None or r.kphos_pump_rate_ml_per_hr == 0.0


def test_hypernatremia_invalid_weight():
    from app.calculators.hypernatremia import (
        HyperNaInputs,
        HyperNaMechanism,
        compute_hypernatremia,
    )

    r = compute_hypernatremia(
        HyperNaInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            patient_na_meq_per_l=170,
            previous_na_meq_per_l=145,
            mechanism=HyperNaMechanism.PURE_WATER_LOSS,
            replacement_hours=24,
            maintenance_ml_per_hr=0,
        )
    )
    assert r.valid is False
    assert r.water_deficit_ml == 0.0
    assert r.total_ml_per_hr == 0.0
    assert r.predicted_rate_mEq_per_hr == 0.0


def test_blood_gas_invalid_pH_low():
    """pH below 6.5 is outside the validation range; result must be invalid."""
    from app.calculators.blood_gas import BloodGasInputs, compute_blood_gas

    r = compute_blood_gas(
        BloodGasInputs(pH=6.0, pco2_mm_hg=40.0, hco3_meq_per_l=22.0)
    )
    assert r.valid is False
    assert r.compensation is None
    assert r.anion_gap is None
    assert r.interpretation == []
    assert any("pH" in e for e in r.errors)


def test_blood_gas_invalid_pH_high():
    from app.calculators.blood_gas import BloodGasInputs, compute_blood_gas

    r = compute_blood_gas(
        BloodGasInputs(pH=8.5, pco2_mm_hg=40.0, hco3_meq_per_l=22.0)
    )
    assert r.valid is False
    assert r.compensation is None


def test_blood_gas_invalid_pco2():
    """PCO2 outside 10-120 mm Hg is rejected."""
    from app.calculators.blood_gas import BloodGasInputs, compute_blood_gas

    r = compute_blood_gas(
        BloodGasInputs(pH=7.40, pco2_mm_hg=0.0, hco3_meq_per_l=22.0)
    )
    assert r.valid is False
    assert r.compensation is None
    assert any("PCO2" in e for e in r.errors)


def test_blood_gas_invalid_hco3():
    """HCO3- outside 5-50 mEq/L is rejected."""
    from app.calculators.blood_gas import BloodGasInputs, compute_blood_gas

    r = compute_blood_gas(
        BloodGasInputs(pH=7.40, pco2_mm_hg=40.0, hco3_meq_per_l=0.0)
    )
    assert r.valid is False
    assert r.compensation is None
    assert any("HCO3" in e for e in r.errors)


def test_blood_gas_all_zero_inputs():
    """All three required inputs at zero (initial-GET state) returns invalid."""
    from app.calculators.blood_gas import BloodGasInputs, compute_blood_gas

    r = compute_blood_gas(BloodGasInputs())  # all defaults to 0
    assert r.valid is False
    assert r.compensation is None
    assert r.anion_gap is None
    # All three errors should be present
    assert len(r.errors) >= 3


def test_blood_gas_invalid_na_for_anion_gap():
    """If Na is supplied but out of range, validation rejects entire input."""
    from app.calculators.blood_gas import BloodGasInputs, compute_blood_gas

    r = compute_blood_gas(
        BloodGasInputs(
            pH=7.20, pco2_mm_hg=28.0, hco3_meq_per_l=12.0,
            na_meq_per_l=300.0, cl_meq_per_l=110.0,
        )
    )
    assert r.valid is False
    assert any("odium" in e or "Na" in e for e in r.errors)


def test_dopamine_prep_invalid_weight():
    from app.calculators.dopamine_prep import (
        DopaminePrepInputs,
        DopamineSpecies,
        compute_dopamine_preparation,
    )

    r = compute_dopamine_preparation(
        DopaminePrepInputs(
            species=DopamineSpecies.DOG,
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            target_dose_ug_per_kg_per_min=5,
        )
    )
    assert r.valid is False
    assert r.mg_dopamine_to_add == 0.0
    assert r.ml_stock_to_draw == 0.0


def test_dopamine_prep_invalid_dose():
    from app.calculators.dopamine_prep import (
        DopaminePrepInputs,
        DopamineSpecies,
        compute_dopamine_preparation,
    )

    r = compute_dopamine_preparation(
        DopaminePrepInputs(
            species=DopamineSpecies.DOG,
            weight_value=20,
            weight_unit=WeightUnit.KG,
            target_dose_ug_per_kg_per_min=0,
        )
    )
    assert r.valid is False


def test_ketamine_invalid_weight():
    from app.calculators.ketamine import (
        KetamineDoseUnit,
        KetamineIndication,
        KetamineInputs,
        KetamineSpecies,
        compute_ketamine,
    )

    r = compute_ketamine(
        KetamineInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            species=KetamineSpecies.DOG,
            indication=KetamineIndication.SURGICAL,
            dose_value=10,
            dose_unit=KetamineDoseUnit.UG_PER_KG_PER_MIN,
        )
    )
    assert r.valid is False
    assert r.pump_rate_ml_per_hr == 0.0


def test_propofol_invalid_weight():
    from app.calculators.propofol import (
        PropofolIndication,
        PropofolInputs,
        PropofolSpecies,
        compute_propofol,
    )

    r = compute_propofol(
        PropofolInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            species=PropofolSpecies.DOG,
            indication=PropofolIndication.TIVA_MAINTENANCE,
            dose_mg_per_kg_per_min=0.2,
        )
    )
    assert r.valid is False
    assert r.pump_rate_ml_per_hr == 0.0


def test_propofol_cat_tiva_is_invalid():
    """Cat propofol TIVA maintenance is contraindicated; the calculator
    must return valid=False so the template suppresses the rate."""
    from app.calculators.propofol import (
        PropofolIndication,
        PropofolInputs,
        PropofolSpecies,
        compute_propofol,
    )

    r = compute_propofol(
        PropofolInputs(
            weight_value=4,
            weight_unit=WeightUnit.KG,
            species=PropofolSpecies.CAT,
            indication=PropofolIndication.TIVA_MAINTENANCE,
            dose_mg_per_kg_per_min=0.2,
        )
    )
    assert r.valid is False
    assert r.pump_rate_ml_per_hr == 0.0


def test_mlk_invalid_weight():
    from app.calculators.mlk import MlkInputs, compute_mlk

    r = compute_mlk(
        MlkInputs(weight_value=-1, weight_unit=WeightUnit.KG)
    )
    assert r.valid is False
    assert r.pump_rate_ml_per_hr == 0.0
    assert r.components == []


def test_insulin_dextrose_invalid_weight():
    """Pre-fix this substituted weight_kg=0.001."""
    from app.calculators.insulin_dextrose import (
        InsulinDextroseInputs,
        InsulinDextroseSpecies,
        compute_insulin_dextrose,
    )

    r = compute_insulin_dextrose(
        InsulinDextroseInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            species=InsulinDextroseSpecies.DOG,
        )
    )
    assert r.valid is False
    assert r.total_insulin_u == 0.0
    assert r.dextrose_total_g == 0.0
    assert r.d50_volume_ml == 0.0


def test_lddst_invalid_baseline():
    from app.calculators.lddst import (
        CortisolUnit,
        LDDSTCategory,
        LDDSTInputs,
        interpret_lddst,
    )

    r = interpret_lddst(
        LDDSTInputs(
            unit=CortisolUnit.UG_PER_DL,
            baseline_cortisol=0,
            cortisol_4h=2.0,
            cortisol_8h=2.5,
            cutoff_8h=1.4,
        )
    )
    assert r.valid is False
    assert r.category == LDDSTCategory.INVALID


def test_lddst_invalid_cutoff():
    from app.calculators.lddst import (
        CortisolUnit,
        LDDSTInputs,
        interpret_lddst,
    )

    r = interpret_lddst(
        LDDSTInputs(
            unit=CortisolUnit.UG_PER_DL,
            baseline_cortisol=4.0,
            cortisol_4h=2.0,
            cortisol_8h=2.5,
            cutoff_8h=0,
        )
    )
    assert r.valid is False


def test_cornell_onco_kl_invalid_weight():
    """Pre-fix this substituted weight_kg=0.001."""
    from app.calculators.cornell_onco_kl import (
        CornellOncoKLInputs,
        CornellOncoKLSpecies,
        compute_cornell_onco_kl,
    )

    r = compute_cornell_onco_kl(
        CornellOncoKLInputs(
            weight_value=-1,
            weight_unit=WeightUnit.KG,
            species=CornellOncoKLSpecies.DOG,
            bag_volume_ml=1000,
            duration_hr=24,
        )
    )
    assert r.valid is False
    assert r.lidocaine_mg_to_add == 0.0
    assert r.ketamine_mg_to_add == 0.0
    assert r.infusion_rate_ml_per_hr == 0.0


def test_energy_invalid_weight():
    from app.calculators.energy import (
        EnergyInputs,
        EnergyPurpose,
        EnergySpecies,
        compute_energy_requirements,
    )

    r = compute_energy_requirements(
        EnergyInputs(
            species=EnergySpecies.DOG,
            purpose=EnergyPurpose.MAINTENANCE,
            current_weight_value=-1,
            current_weight_unit=WeightUnit.KG,
        )
    )
    assert r.valid is False
    assert r.rer_kcal_per_day == 0.0
    assert r.target_kcal_per_day == 0.0


# ---------------------------------------------------------------------------
# Utilities (notes-style: solution prep, fluid rate, drop factor)
# ---------------------------------------------------------------------------


def test_solution_prep_target_exceeds_stock_invalid():
    from app.calculators.utilities import (
        SolutionPrepInputs,
        compute_solution_prep,
    )

    r = compute_solution_prep(
        SolutionPrepInputs(
            target_volume_ml=1000,
            target_percent=50,
            stock_percent=10,
        )
    )
    assert r.valid is False
    assert r.stock_volume_ml == 0.0
    assert r.diluent_volume_ml == 0.0


def test_solution_prep_zero_volume_invalid():
    from app.calculators.utilities import (
        SolutionPrepInputs,
        compute_solution_prep,
    )

    r = compute_solution_prep(
        SolutionPrepInputs(
            target_volume_ml=0,
            target_percent=5,
            stock_percent=50,
        )
    )
    assert r.valid is False


def test_drop_factor_invalid_rate():
    from app.calculators.utilities import DropFactorInputs, compute_drop_factor

    r = compute_drop_factor(
        DropFactorInputs(ml_per_hour=0, drop_factor=20)
    )
    assert r.valid is False
    assert r.drops_per_minute == 0.0


def test_drop_factor_invalid_factor():
    from app.calculators.utilities import DropFactorInputs, compute_drop_factor

    r = compute_drop_factor(
        DropFactorInputs(ml_per_hour=100, drop_factor=0)
    )
    assert r.valid is False


# ---------------------------------------------------------------------------
# Crash safety: every calculator must NEVER raise on non-positive inputs.
# This is the broadest safety net — if a future calculator ever bypasses
# the validation pattern, this test will catch it as a crash on the
# request handler.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario",
    [
        # SINGLE_DRUG_CRI with various drugs
        lambda: compute(
            get_drug("norepinephrine"),
            CalcInputs(
                weight_value=0,
                weight_unit=WeightUnit.KG,
                dose=0,
                concentration_ug_per_ml=0,
                species=Species.DOG,
            ),
        ),
        lambda: compute(
            get_drug("epinephrine"),
            CalcInputs(
                weight_value=-5,
                weight_unit=WeightUnit.KG,
                dose=0.05,
                concentration_ug_per_ml=80,
                species=Species.CAT,
            ),
        ),
        lambda: compute(
            get_drug("dobutamine"),
            CalcInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose=5,
                concentration_ug_per_ml=0,  # zero conc was the divide-by-zero
                species=Species.DOG,
            ),
        ),
        lambda: compute(
            get_drug("fentanyl"),
            CalcInputs(
                weight_value=20,
                weight_unit=WeightUnit.KG,
                dose=10,
                concentration_ug_per_ml=-50,  # negative conc
                species=Species.DOG,
            ),
        ),
        lambda: compute_dilution(
            DilutionInputs(
                stock_concentration_ug_per_ml=0,
                desired_concentration_ug_per_ml=0,
                final_volume_ml=0,
            )
        ),
    ],
    ids=[
        "norepi_all_zero",
        "epi_negative_weight",
        "dobutamine_zero_concentration_no_zero_div",
        "fentanyl_negative_concentration",
        "dilution_all_zero",
    ],
)
def test_no_exceptions_on_invalid_inputs(scenario):
    """The previous engine raised ZeroDivisionError on zero concentration;
    must not happen now. Any other exception is also a failure."""
    result = scenario()
    assert result.valid is False
