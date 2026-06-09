# Clinical background

The Low-Dose Dexamethasone Suppression Test (LDDST) is the most informative single screening test for hyperadrenocorticism (HAC) in dogs. Compared to the ACTH stimulation test and the urine cortisol:creatinine ratio (UCCR), the LDDST has higher overall sensitivity for HAC and, uniquely among the three, can sometimes discriminate pituitary-dependent hyperadrenocorticism (PDH) from adrenal-dependent (AT) disease in the same test. The trade-off is specificity: the LDDST has a higher false-positive rate in dogs that are stressed or sick from non-adrenal disease, so the pretest probability of HAC has to be high enough to make the test worth running.

## How the test works

A baseline cortisol is drawn, dexamethasone (0.01 mg/kg IV) is administered, and cortisol is re-measured at **4 hours** and **8 hours** post-injection. Dexamethasone is a potent synthetic glucocorticoid; in a normal dog, it suppresses ACTH release from the pituitary by negative feedback, and serum cortisol falls below 1.0–1.4 µg/dL within several hours and stays suppressed for at least 8 hours.

In dogs with HAC, the suppression is incomplete, absent, or transient depending on the underlying cause. The pattern across the 4- and 8-hour points is what discriminates HAC from non-HAC and, in some cases, PDH from AT.

## Interpreting the patterns

The InfusionFox LDDST calculator implements the standard four-pattern classification:

### 1. Normal suppression
**4-hour cortisol < 1.4 µg/dL AND 8-hour cortisol < 1.4 µg/dL** → does not support HAC. The patient suppressed cortisol normally throughout the test. Look elsewhere for the cause of the clinical signs.

### 2. Inverse pattern
**8-hour cortisol < 1.4 µg/dL but 4-hour cortisol higher than 8-hour** → ambiguous. Some normal dogs show this pattern. Some HAC dogs do too. Repeat the test in 1–3 months, or pursue ACTH stim or imaging.

### 3. Pattern consistent with PDH (escape)
**4-hour cortisol < 1.4 µg/dL OR < 50% of baseline, but 8-hour cortisol > 1.4 µg/dL** → "escape from suppression." The pituitary briefly responded to dexamethasone but escaped from feedback by 8 hours. This pattern is **diagnostic of PDH** in the appropriate clinical context.

### 4. Dexamethasone-resistant pattern
**Both 4-hour and 8-hour cortisol > 1.4 µg/dL** → consistent with HAC, but the test cannot distinguish PDH from AT. Move to confirmatory imaging (adrenal ultrasound) or further testing (endogenous ACTH measurement) to make the distinction.

## When NOT to run the LDDST

- **Acutely sick dogs with non-adrenal disease**: false-positive rate is high. Stabilize the underlying illness first.
- **Recent glucocorticoid administration**: even topical, ophthalmic, or otic preparations can suppress the HPA axis for weeks. Confirm a clean steroid history before testing; if uncertain, wait 4–6 weeks or use the UCCR as a less-sensitive but less-confounded screen.
- **Low pretest probability**: a positive LDDST in a dog with only one or two nonspecific signs is more likely a false positive than true HAC. Use the InfusionFox Cushing's score or a comparable structured assessment to confirm clinical signs are convincing before testing.
- **Stressed dogs**: recent boarding, recent travel, recent procedures, or significant in-clinic anxiety all elevate the false-positive rate. Try to test on a "good day" for the patient.

## Laboratory practical points

- **Sample timing matters.** The 4- and 8-hour samples should be drawn within ±15 minutes of the target time. Earlier than 4 hours can miss the suppression nadir; later than 8 hours can miss the escape.
- **Use a single cortisol assay.** Cross-reactivity and assay-specific cutoffs vary; if you're using a different reference range than the standard 1.4 µg/dL cutoff, adjust the calculator's interpretation accordingly.
- **Ship samples cold.** Cortisol is reasonably stable but degrades over time at room temperature.

## Sources

- Behrend EN et al: Diagnosis of spontaneous canine hyperadrenocorticism: 2012 ACVIM Consensus Statement. *J Vet Intern Med* 2013;27:1292–1304.
- Feldman EC, Nelson RW, Reusch CE, Scott-Moncrieff JCR: *Canine and Feline Endocrinology*, 4th ed., Elsevier, 2015, Chapter 11.
- Behrend EN: Hyperadrenocorticism. In: Ettinger SJ, Feldman EC, Côté E, eds. *Textbook of Veterinary Internal Medicine*, 8th ed., 2017.
