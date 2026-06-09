# Clinical background

Hypernatremia is fundamentally a water problem, not a sodium problem. Serum sodium concentration reflects the ratio of total body sodium to total body water; in nearly every clinical case of hypernatremia, the sodium is normal or near-normal and the water is what's deficient. Treating it as "too much salt" leads to inappropriate management; treating it as "not enough water" leads to the right answer.

The other essential principle: **the rate of correction matters more than the route of correction.** Acute hypernatremia (developed over hours, e.g., salt toxicity, hypertonic saline overdose, or massive water loss) can be corrected quickly because the brain hasn't had time to adapt. Chronic hypernatremia (developed over days, e.g., diabetes insipidus, primary hypodipsia, prolonged free water deprivation) has been compensated by accumulation of intracellular idiogenic osmoles in the brain, and rapid correction in these patients drives water into brain cells faster than the osmoles can dissipate, producing cerebral edema, seizures, coma, and death. The classic teaching: **correct chronic hypernatremia at no more than 0.5 mEq/L/hr (≈10–12 mEq/L per 24 hours).**

## Distinguishing acute from chronic

History is the most reliable guide:
- **Acute**: known event in the last few hours: paint-ball ingestion, sea-water exposure, hypertonic saline misadministration, catastrophic water loss (heat stroke, prolonged status epilepticus). Sodium probably rose over hours.
- **Chronic / unknown duration**: hypernatremia found incidentally or after gradual decline; no known acute trigger; chronic systemic disease (CKD, hyperaldosteronism, central or nephrogenic DI, primary hypodipsia in older Miniature Schnauzers and Boxer-type dogs). Default to chronic management when in doubt, the cost of correcting chronic hypernatremia too slowly is much smaller than the cost of correcting it too fast.

## Mechanism categories

The InfusionFox calculator distinguishes three mechanisms because they require different fluid choices:

### 1. Pure water loss
Total body sodium is normal; water is the only deficit. Sources: renal water loss (DI, osmotic diuresis with concentrated urine), insensible loss (heat stroke, prolonged hyperventilation, panting), or inadequate intake (primary hypodipsia, hospitalization without water). The deficit is calculated from the Adrogue-Madias formula:

> Free water deficit (L) = TBW × (Na_current / Na_target − 1)

where TBW = 0.6 × body weight in kg. The water is given as 5% dextrose in water (D5W; the dextrose is metabolized and the water remains) or as half-strength saline.

### 2. Hypotonic loss
Water and a smaller amount of sodium are lost together. Sources: vomiting, diarrhea, diuretics, third-space losses. The free water component is what causes the hypernatremia; replace with isotonic fluids (LRS, Plasma-Lyte, 0.9% NaCl), even though the sodium concentration of these fluids is at or near the patient's plasma sodium, the volume restoration corrects the hypovolemia and the free water replacement happens as the patient resumes drinking.

### 3. Solute gain
Sodium load was added: salt poisoning (paint-ball, table salt ingestion, sea-water), hypertonic saline administration, hyperaldosteronism (rare). The calculator's water deficit calculation underestimates the situation here, the patient also has *too much* sodium, and the optimal fluid is one that does not add more salt. D5W is usually appropriate. Severe cases may require dialysis.

## Why we don't bolus

Hypernatremia is one of the few situations in critical care where the rate of fluid administration is itself a drug-dosing decision. A "bolus" of D5W in a chronic hypernatremic patient is dangerous in a way that a bolus of LRS in a hypovolemic dog is not. Calculate the deficit, calculate the rate, and run it on a pump. The InfusionFox calculator outputs the rate that holds the planned correction within the 0.5 mEq/L/hr ceiling.

## Practical points

- **The "previous Na" is your goal, not 145.** If the patient's known prior sodium was 158, that's the target, bringing them back to 145 in a chronic case is *unsafe* because their brain has adapted to higher osmolarity. The calculator accepts the previous Na as input.
- **Reassess every 4–6 hours.** Trend the rate of decline. If it's faster than predicted, slow the infusion; if slower, increase modestly.
- **Treat the underlying cause concurrently.** A patient with central DI needs DDAVP. A patient with primary hypodipsia needs free water access (often via a feeding tube). A patient with osmotic diuresis from uncontrolled diabetes needs insulin.

## Sources

- DiBartola SP: *Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice*, 4th ed., Elsevier, 2012, Chapter 3 (Disorders of Sodium and Water).
- Bissett SA, Lamb CR, Brockman DJ. Hypodipsic hypernatremia in a dog. *J Am Anim Hosp Assoc* 2001.
- Adrogue HJ, Madias NE: Hypernatremia. *N Engl J Med* 2000;342:1493–1499.
