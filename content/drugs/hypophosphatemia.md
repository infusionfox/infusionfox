# Clinical background

Hypophosphatemia is one of those derangements that is frequently asymptomatic at moderate levels but rapidly catastrophic at severe levels. The single most life-threatening complication is acute intravascular hemolysis, which can occur abruptly when serum P drops below 1 mg/dL and may not be obvious until the PCV drops or the urine turns pigmenturic. The other major manifestation, respiratory muscle weakness leading to hypoventilation or frank respiratory failure, is also rapid and often unanticipated. For these reasons, severe hypophosphatemia is treated as a true urgency, not a watchful-waiting electrolyte abnormality.

## Why phosphorus matters

Phosphorus is required for:

- ATP synthesis, most obviously in muscle and red blood cells, where ATP shortage produces weakness and hemolysis respectively
- 2,3-DPG in red cells, needed for normal oxyhemoglobin dissociation; severe hypophosphatemia produces a left-shifted curve and impaired tissue oxygen delivery
- Phospholipid membrane structure
- Nucleic acid synthesis
- Bone mineralization (chronic balance, not relevant to acute therapy)

The clinical signs of severe hypophosphatemia map directly onto these requirements: muscle weakness (skeletal, respiratory, cardiac), hemolytic anemia, CNS depression, and impaired immune function.

## When does hypophosphatemia develop?

Most clinical hypophosphatemia in small animals falls into a few categories:

**Insulin-driven cellular shifting.** This is the most common cause in the hospital setting. Insulin promotes cellular phosphate uptake alongside glucose. Patients with DKA, hyperglycemic hyperosmolar syndrome, or any other indication for insulin therapy can develop rapid hypophosphatemia within hours of starting insulin. Hoehne notes that ≈48% of dogs with DKA develop or worsen hypophosphatemia after starting therapy, and severe hemolysis from this cause is a recognized cause of DKA mortality.

**Refeeding syndrome.** Severely malnourished patients (chronic anorexia, prolonged starvation, hepatic lipidosis cats) shift phosphorus intracellularly in a major way when refeeding begins, particularly with carbohydrate-rich diets that drive endogenous insulin secretion. The shift can be profound enough to cause life-threatening hypophosphatemia within 24–48 hours of refeeding. Anticipate this in any chronically anorexic patient and supplement preemptively if P is even low-normal at baseline.

**Total parenteral nutrition.** TPN solutions deliver glucose and amino acids that drive cellular phosphate uptake. Long-term TPN protocols include phosphate supplementation explicitly; short-term use without phosphate can produce hypophosphatemia within 12–24 hours.

**Primary hyperparathyroidism treatment.** Patients with chronic hyperparathyroidism develop hungry-bone syndrome after parathyroidectomy, the bones, suddenly able to take up calcium and phosphate, do so rapidly enough to drop both serum Ca and P. Severe hypophosphatemia is the more common of the two acutely.

**Post-obstructive diuresis.** The marked diuresis after relieving urinary obstruction (urethral obstruction in cats, ureteral stone removal, etc.) can wash out phosphate along with other electrolytes. Watch for it in the 24–72 hours post-relief.

**Severe respiratory alkalosis.** Hyperventilation drives phosphate intracellularly through metabolic alkalosis. More relevant to human ICU than veterinary practice but worth knowing.

**Less common in veterinary practice but documented:** chronic ethanol intake (humans), severe burns, dialysis-related, primary renal phosphate wasting (Fanconi syndrome).

## The sliding scale

The standard veterinary sliding scale by serum phosphorus:

| Serum P (mg/dL) | KPhos rate (mmol/kg/hr) | Severity |
|---|---|---|
| > 2.0 | not indicated | normophosphatemia |
| 1.5–2.0 | 0.03 | mild |
| 1.0–1.5 | 0.06 | moderate |
| 0.5–1.0 | 0.09 | severe |
| < 0.5 | 0.12 | critical |

The range bracketing the rates (0.03–0.12 mmol/kg/hr) is from Hoehne / Box 73.1; the band assignments are conventional veterinary practice and align with DiBartola Ch. 7.

## Why KPhos and not pure phosphate

Standard veterinary parenteral phosphate is **potassium phosphate (KPhos)**, which contains both potassium and phosphate. The standard preparation is potassium phosphate injection USP, providing approximately 4.4 mEq of K alongside 3 mmol of P per mL. Sodium phosphate (NaPhos) preparations exist but are less commonly stocked in veterinary settings.

The K content matters because it interacts with concurrent KCl supplementation, see below.

## The K interaction

Patients with hypophosphatemia, particularly DKA patients, are almost always also on KCl supplementation per the hypokalemia sliding scale. **The K in KPhos counts toward the 0.5 mEq/kg/hr ceiling on total K delivery.**

For a 20 kg dog with severe hypophosphatemia (P 0.6 mg/dL → 0.09 mmol/kg/hr KPhos):

- KPhos rate: 20 × 0.09 / 3 = 0.6 mL/hr
- K from KPhos: 0.6 mL/hr × 4.4 mEq/mL = 2.64 mEq/hr (= 0.132 mEq/kg/hr)
- Headroom for additional KCl: 0.5 − 0.132 = 0.368 mEq/kg/hr

If the patient was already running KCl at 0.4 mEq/kg/hr before KPhos was added, total K delivery would now be 0.532 mEq/kg/hr, over the ceiling. The KCl rate must be reduced to under 0.368 mEq/kg/hr to stay within the safety margin.

The InfusionFox hypophosphatemia calculator surfaces this math explicitly so the interaction doesn't get missed.

## Administration

**KPhos must be diluted before IV administration.** Typical practice is to add the calculated dose to a small bag of 0.9% NaCl or LRS and run via syringe pump or volumetric pump. Direct IV push or co-infusion in a calcium-containing line risks calcium phosphate precipitation, which can be fatal if it embolizes.

LRS contains calcium (~3 mEq/L). At standard CRI dilutions, calcium phosphate precipitation is unlikely but theoretically possible. Most institutions use D5W or 0.9% NaCl as the diluent for KPhos to avoid the question entirely.

A separate IV line for KPhos is the safest practice when the patient is also receiving calcium gluconate or any calcium-containing fluid.

## Monitoring

- **Serum P every 4–6 hours** during active KPhos therapy
- **Serum K every 4–6 hours** as well. KPhos contributes K and the patient is usually on additional K supplementation
- **PCV and TP** to detect hemolysis early in severe cases
- **Pulse oximetry / blood gas** if respiratory weakness is suspected
- **ECG continuously** for any patient receiving K above 0.3 mEq/kg/hr from any combined source

Discontinue KPhos when P > 2.0 mg/dL. Some institutions wait for two consecutive measurements above 2.0 before stopping to avoid rebound.

## When to consider transfusion

A DKA patient who develops a sudden drop in PCV during therapy, with or without pigmenturia, has hemolytic anemia from severe hypophosphatemia until proven otherwise. The treatment is aggressive phosphate replacement and, if anemia is severe, packed cell transfusion to maintain oxygen-carrying capacity until P normalizes and red cell ATP recovers.

## Adverse effects of KPhos therapy

- **Hyperphosphatemia**: uncommon at sliding-scale rates with appropriate monitoring, but possible with prolonged therapy or in renal insufficiency.
- **Hypocalcemia**: phosphate binds free calcium; large or rapid doses can drop ionized calcium. Watch for tetany, twitching, prolonged QT.
- **Metastatic calcification**: chronic high P-Ca product can deposit calcium phosphate in soft tissues. More of a concern with long-term over-supplementation than acute therapy.
- **Hyperkalemia**: from the K content of KPhos. The interaction calculation above is the prevention.
- **Volume overload**: at the dilutions typically used, the volume contribution is small, but watch in cardiac or renal patients.

## When the math is failing

A patient whose P doesn't recover despite apparently adequate KPhos:

- **Underestimated severity.** Recheck P now; the original measurement may have been done before the most rapid intracellular shift.
- **Ongoing intracellular movement.** Insulin still running, refeeding ongoing, supplementation is just keeping up with shifting, not net replacement.
- **Renal phosphate wasting.** Less common but worth investigating if P-replacement isn't holding (fractional excretion of phosphate, Fanconi screen).
- **Concurrent magnesium deficiency.** Mg deficiency can blunt the response to phosphate supplementation; check Mg if K, Ca, and P are all refractory.

## Sources

- Hoehne SN. Diabetic Ketoacidosis. In: Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 3rd ed. Elsevier; 2023. Chapter 73, Box 73.1 (sliding-scale rate range).
- DiBartola SP, ed. *Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice*. 4th ed. Elsevier; 2012. Chapter 7 (Disorders of Phosphorus).
