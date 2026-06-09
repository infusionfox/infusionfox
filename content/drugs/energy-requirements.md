# Clinical background

Calculating a target caloric intake for a hospitalized or chronically managed patient is one of those tasks that everyone does and almost no one writes down, yet it underlies every nutritional decision in the practice. Underfed hospitalized patients have measurably worse outcomes (delayed wound healing, prolonged hospitalization, higher mortality in critically ill cohorts), and overfed patients risk refeeding syndrome, hyperglycemia, hepatic steatosis, and the obesity that drives many of the diseases we treat in the first place. The framework below is the one used in nearly every veterinary nutrition reference; the InfusionFox calculator just removes the math.

## RER vs MER

**Resting Energy Requirement (RER)** is the energy a healthy, fasted, thermally neutral animal needs at rest, covering basal metabolism only. It's calculated from body weight using an allometric equation:

> RER (kcal/day) = 70 × (body weight in kg)^0.75

The exponent 0.75 (rather than 1.0) reflects the fact that energy expenditure scales with body surface area, not mass. A 40 kg dog does not burn twice the energy of a 20 kg dog, it burns about 1.7×. For very small animals (under 2 kg) the formula breaks down at the bottom; the linear approximation `30 × kg + 70` is sometimes used in those cases.

**Maintenance Energy Requirement (MER)** is the energy a patient at a given activity and life stage actually consumes day to day. The dog and cat math here is different and the calculator handles each species separately.

**Dogs** use `MER = factor × RER`, where the factor comes from a lookup table:

- Inactive adult dog: ≈1.2–1.4 × RER
- Active adult dog: ≈1.6 × RER
- Puppy 4–12 mo: ≈2.0 × RER
- Lactating bitch (peak): up to 4–8 × RER

**Cats** do not slot cleanly into the RER-times-factor framework, and the NRC 2006 publishes species-specific allometric equations the calculator uses directly:

- **Lean cat (BCS ≤ 5/9), maintenance:** `MER = 100 × (BW kg)^0.67 kcal/day`
- **Overweight cat (BCS > 5/9), weight loss:** `MER = 130 × (IBW kg)^0.4 kcal/day`, applied against estimated ideal body weight rather than current weight

The lean-cat formula is roughly equivalent to ≈1.2–1.4 × RER at typical adult cat weights, which is why older references sometimes describe cat maintenance as "1.2 × RER". That approximation breaks down at the extremes (small or large cats), and the calculator stays with the NRC equations to keep the math consistent across the weight range. The lower mass exponent in the overweight formula (0.4 rather than 0.67 or 0.75) reflects NRC's observation that obese cats have a lower-than-predicted resting energy expenditure relative to current body weight, and overestimating their needs slows the weight-loss trajectory.

In sick, hospitalized, or critically ill patients, **target intake is RER, not MER**. Older guidance suggested using illness factors (1.2–1.5 × RER) for hospitalized patients; current evidence does not support routinely going above RER, and the risks of overfeeding (especially refeeding syndrome in the first 72 hours of nutritional support) outweigh the theoretical benefit. Start at RER and titrate upward only if the patient is tolerating feeds and not gaining weight.

## When to feed

Patients should be fed within 24–48 hours of hospitalization unless they have an active contraindication (uncontrolled vomiting, ileus from a surgical anastomosis, recent abdominal surgery requiring NPO). Voluntary oral intake is the preferred route; if that's not happening, place a feeding tube (nasoesophageal, esophagostomy, or PEG depending on duration) before starvation has had time to compound the underlying illness.

## Refeeding syndrome

In a chronically anorectic or cachectic patient (>5–7 days of inadequate intake), aggressive refeeding can drive intracellular shifts of phosphate, potassium, and magnesium that produce profound hypophosphatemia, hypokalemia, and hypomagnesemia within 48–72 hours of starting feeds. Severe hypophosphatemia (<1 mg/dL) can cause hemolytic anemia and respiratory muscle weakness; severe hypokalemia or hypomagnesemia can cause arrhythmias.

The protective approach: in any patient with significant prior anorexia, start at **25–33% of RER** for the first 24 hours, advancing by 25% per day to full RER over 3–4 days. Monitor phosphate, potassium, and magnesium every 12–24 hours during the advance.

## Practical points

- **Body condition score (BCS) on a 9-point scale** drives target weight. A BCS-9 obese dog should be calculated at *target* (lean) body weight, not current weight. A BCS-3 cachectic patient should be calculated at *current* weight (not the higher pre-illness weight).
- **The number is a starting point.** Reassess every 1–3 days based on body weight trend, BCS, and clinical response. Patients who are not gaining or are actively losing weight need more calories or a different feeding strategy.
- **Match the food to the diagnosis.** A renal patient gets a renal diet; a chronic enteropathy patient gets a highly digestible or hydrolyzed diet; a critically ill patient gets a high-calorie convalescent formula. The kcal calculation is independent of diet selection.

## Sources

- WSAVA Global Nutrition Committee: Nutritional assessment guidelines. *J Small Anim Pract* 2011.
- Chan DL: Nutritional support of the critically ill small animal patient. *Vet Clin North Am Small Anim Pract* 2020.
- Saker KE, Remillard RL: Critical care nutrition and enteral-assisted feeding. In: Hand MS et al, *Small Animal Clinical Nutrition*, 5th ed.
