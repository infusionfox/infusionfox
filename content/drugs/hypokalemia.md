# Clinical background

Hypokalemia is one of the most commonly encountered electrolyte derangements in hospitalized small animals, particularly in patients with vomiting, diarrhea, polyuria from any cause, and diabetic ketoacidosis. It is also one of the easiest to under-treat: the supplementation rate is rate-limited by safety (potassium is cardiotoxic if delivered too quickly), so even patients who genuinely need aggressive replacement get it slowly. Understanding *why* the rate ceiling exists, and how to maximize delivery within it, is the main clinical skill here.

## Why potassium needs a rate ceiling

Serum potassium is a tiny fraction of total body potassium, roughly 2% is extracellular, 98% intracellular. Intravenous potassium delivered faster than the body can shift it into cells produces a rising plasma concentration that affects the cardiac action potential. Above ≈7 mEq/L, conduction abnormalities appear (peaked T waves, prolonged PR, widened QRS); above ≈8 mEq/L, sinoventricular rhythm and ventricular arrhythmias; above ≈10 mEq/L, asystole.

The published safety ceiling is **0.5 mEq/kg/hr** of IV KCl. This is the maximum sustained rate that the body can shift into cells without a clinically meaningful rise in extracellular potassium. The ceiling applies to total potassium delivery, meaning the math is rate (mL/hr) × concentration (mEq/L) × (1 L / 1000 mL) ÷ weight (kg). The InfusionFox calculator does this in reverse: given a target concentration in the bag, it tells you the maximum rate that respects the ceiling.

## The DiBartola sliding scale

Standard practice is to scale the *concentration* of KCl added to the maintenance fluid bag based on the severity of hypokalemia:

| Serum K (mEq/L) | KCl per liter of fluid |
|---|---|
| < 2.0 | 80 mEq/L |
| 2.1 – 2.5 | 60 mEq/L |
| 2.6 – 3.0 | 40 mEq/L |
| 3.1 – 3.5 | 28 mEq/L |
| 3.6 – 5.0 | 20 mEq/L (maintenance) |

The logic: more severe hypokalemia gets a higher concentration in the same bag, so that even at the rate-limited maximum infusion the patient gets meaningful replacement per hour. The corresponding maximum bag rate goes *down* as concentration goes up, at 80 mEq/L, the maximum rate is about 6 mL/kg/hr; at 20 mEq/L, you can run up to 25 mL/kg/hr without exceeding the 0.5 mEq/kg/hr potassium delivery ceiling.

## Practical points

### Concentration ceilings
- **Peripheral IV catheter:** maximum 60 mEq/L. Higher concentrations cause phlebitis, vein damage, and pain on infusion. If your math says you need 80 mEq/L (severely hypokalemic patient on a 1 L bag), you need either a central line or a smaller bag with a higher concentration.
- **Central line:** up to 80 mEq/L is safe; some references go higher with continuous ECG monitoring.
- **Subcutaneous administration:** limited to ≤30 mEq/L. Higher concentrations cause tissue irritation and unreliable absorption.

### Don't combine with anything that competes
- **Refractory hypokalemia is often refractory hypomagnesemia.** Hypomagnesemia impairs the renal tubular response to aldosterone and prevents potassium reabsorption. Patients who do not respond to aggressive K supplementation should have Mg checked and replaced.
- **Don't run K-supplemented fluid alongside dextrose CRI without thinking it through.** Dextrose drives insulin, which drives K *into* cells. The patient's serum K may stay flat or even drop while you're "supplementing" them.

### Address the cause
Most outpatient hypokalemia comes from drugs (loop diuretics, thiazides, recent corticosteroids), GI losses, or polyuric diseases. Inpatient hypokalemia in a hospitalized animal is more often dilutional (heavy maintenance fluids without K supplementation), iatrogenic (insulin therapy), or related to the disease being treated (DKA, post-obstructive diuresis). Stopping the cause is usually more effective than chasing the lab value.

## Acute critical hypokalemia

K < 2.5 mEq/L with weakness, ileus, or arrhythmias requires urgent supplementation. In a properly monitored patient (continuous ECG, central access), short-duration boluses up to 1 mEq/kg/hr have been used in critical cases, but this is outside the published safety ceiling and should only be done with continuous monitoring and immediate calcium gluconate available. The InfusionFox calculator stays at the safe ceiling by design; for the rare critical case, the bedside math is yours to do.

## Sources

- DiBartola SP: *Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice*, 4th ed., Elsevier, 2012, Chapter 5 (Disorders of Potassium).
- Plumb's Veterinary Drugs, potassium chloride monograph (current edition), for compatibility, peripheral concentration limits, and dosing notes.
