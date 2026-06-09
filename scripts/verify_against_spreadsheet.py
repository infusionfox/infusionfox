"""
Verify the calculator engine produces the same results as the original spreadsheet.

Spreadsheet defaults (read straight from CRI_Calculator.xlsx):

NE:   weight=90 lb,  dose=0.1 ug/kg/min, conc=80 ug/mL
Epi:  weight=50 lb,  dose=0.1 ug/kg/min, conc=80 ug/mL
Dob:  weight=90 lb,  dose=5   ug/kg/min, conc=1000 ug/mL
Fent: weight=75 lb,  dose=10  ug/kg/hr,  conc=50 ug/mL
"""

import sys

sys.path.insert(0, "/home/claude/infusionfox")

from app.calculators import (
    CalcInputs,
    DilutionInputs,
    Species,
    WeightUnit,
    compute,
    compute_dilution,
    get_drug,
)


def expected_ml_per_hr_per_min_drug(weight_lb, dose, conc):
    w_kg = weight_lb / 2.20462
    return (w_kg * dose / conc) * 60


def expected_ml_per_hr_per_hr_drug(weight_lb, dose, conc):
    w_kg = weight_lb / 2.20462
    return w_kg * dose / conc


def run_case(slug, weight_lb, dose, conc, species=Species.DOG):
    drug = get_drug(slug)
    inputs = CalcInputs(
        weight_value=weight_lb,
        weight_unit=WeightUnit.LB,
        dose=dose,
        concentration_ug_per_ml=conc,
        species=species,
    )
    r = compute(drug, inputs)
    print(f"\n--- {drug.display_name} ---")
    print(f"  Weight: {weight_lb} lb → {r.weight_kg:.6f} kg")
    if r.total_dose_ug_per_min is not None:
        print(f"  Total dose: {r.total_dose_ug_per_min:.6f} µg/min")
    print(f"  Total dose: {r.total_dose_ug_per_hr:.6f} µg/hr")
    print(f"  Infusion rate: {r.ml_per_hr_precise:.6f} mL/hr")
    print(f"  Infusion rate (pump): {r.ml_per_hr_pump} mL/hr")
    print(f"  Infusion rate (display): {r.ml_per_hr_display} mL/hr")
    print(f"  mL/kg/hr: {r.ml_per_kg_per_hr:.6f}")
    if r.warnings:
        print(f"  Warnings: {r.warnings}")
    return r


# NE: 90 lb, 0.1 ug/kg/min, 80 ug/mL
r = run_case("norepinephrine", 90, 0.1, 80)
expected = expected_ml_per_hr_per_min_drug(90, 0.1, 80)
assert abs(r.ml_per_hr_precise - expected) < 1e-9, f"NE mismatch: {r.ml_per_hr_precise} vs {expected}"

# Epi: 50 lb, 0.1, 80
r = run_case("epinephrine", 50, 0.1, 80)
expected = expected_ml_per_hr_per_min_drug(50, 0.1, 80)
assert abs(r.ml_per_hr_precise - expected) < 1e-9

# Dobutamine: 90 lb, 5, 1000
r = run_case("dobutamine", 90, 5, 1000)
expected = expected_ml_per_hr_per_min_drug(90, 5, 1000)
assert abs(r.ml_per_hr_precise - expected) < 1e-9

# Fentanyl: 75 lb, 10, 50  (PER HOUR drug)
r = run_case("fentanyl", 75, 10, 50)
expected = expected_ml_per_hr_per_hr_drug(75, 10, 50)
assert abs(r.ml_per_hr_precise - expected) < 1e-9

# ---- Cat dobutamine safety check ----
print("\n\n--- Cat dobutamine safety test ---")
r = run_case("dobutamine", 10, 5, 500, species=Species.CAT)  # 5 > 2.5 cat ceiling
assert any("CAUTION" in w for w in r.warnings), "Expected cat dobutamine caution"
print("  ✓ Cat dobutamine caution fired correctly")

# ---- Dilution helper sanity check ----
print("\n--- Dilution helper ---")
# From your sheet: stock 12500, desired 1000, final 50 → drug_vol = 4 mL
d = compute_dilution(DilutionInputs(12500, 1000, 50))
print(
    f"  Dobutamine 1000 µg/mL in 50 mL: draw {d.drug_volume_ml_rounded} mL stock + {d.diluent_volume_ml_rounded} mL diluent"
)
assert abs(d.drug_volume_ml - 4.0) < 1e-9

# NE: stock 1000, desired 80, final 50 → drug_vol = 4 mL (matches your guide row)
d = compute_dilution(DilutionInputs(1000, 80, 50))
print(
    f"  NE 80 µg/mL in 50 mL: draw {d.drug_volume_ml_rounded} mL stock + {d.diluent_volume_ml_rounded} mL diluent"
)
assert abs(d.drug_volume_ml - 4.0) < 1e-9

print("\n✓ All checks passed.")
