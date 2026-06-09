# Clinical background

The Acute Patient Physiologic and Laboratory Evaluation (APPLE) score is a diagnosis-independent illness severity tool for hospitalized dogs. Hayes and colleagues at the University of Guelph published two parsimonious models in 2010: a 10-variable score (APPLE-full, 0–80) and a 5-variable score (APPLE-fast, 0–50). This calculator implements the 10-variable model. The fast model is at [/apple-fast](/apple-fast); when the patient has a complete chemistry, CBC, blood gas, and FAST/TFAST evaluation, APPLE-full is the more rigorous choice.

The score's intended use is **objective stratification of illness severity**: primarily for risk-adjusting treatment groups in clinical research, and secondarily for documenting baseline severity at admission. It was explicitly **not** designed to drive euthanasia decisions, and the authors went out of their way to caution against that use.

## How the score was built

810 consecutive ICU admissions over 6 months at the Guelph teaching hospital. 55 candidate variables collected per admission per a written protocol; 598 records used for model construction and 212 held out for validation. Backward stepwise logistic regression with manual sensitivity analysis selected the 10-variable APPLE-full set: creatinine, WBC count, albumin, SpO₂, total bilirubin, mentation score, respiratory rate, age, lactate, and presence of free fluid in a body cavity. Coefficients were converted to integer points using a constant multiplier chosen so the maximum sum approximated 80.

The final APPLE-full model had AUROC 0.93 on the construction cohort (95% CI 0.90–0.95) and 0.91 on the validation cohort (95% CI 0.89–0.96), with Hosmer-Lemeshow calibration P-values of 0.74 and 0.71 respectively, well above the 0.05 threshold for acceptable calibration. The 10-variable model carried meaningfully better discrimination than the 5-variable APPLE-fast (AUROC 0.87/0.84).

Performance at the two published cutoffs:

| Cutoff | Sensitivity | Specificity |
|---|---|---|
| >30/80 | 81.2% | 89.4% |
| >40/80 | 40.9% | 98.3% |

The >30/80 cutoff is the operating point most clinicians want: high sensitivity for mortality at acceptable specificity. The >40/80 cutoff is used when false positives must be minimized.

## Variable definitions

| Variable | Source | Timing |
|---|---|---|
| Creatinine | Plasma, automated chemistry | Most abnormal in first 24 h |
| WBC count | EDTA, automated hematology | Most abnormal in first 24 h |
| Albumin | Plasma, automated chemistry | Most abnormal in first 24 h |
| SpO₂ | Pulse oximetry | Most abnormal in first 24 h |
| Total bilirubin | Plasma, automated chemistry | Most abnormal in first 24 h |
| Mentation | Clinical assessment | **Admission, before sedation/analgesia** |
| Respiratory rate | Counted bpm | Most abnormal in first 24 h |
| Age | Patient history | At admission |
| Fluid score | FAST/TFAST ultrasound | At admission (or first scan within 24 h) |
| Lactate | Whole blood, point-of-care | Most abnormal in first 24 h |

The "most abnormal" rule for the time-varying variables exists to capture the trajectory of deterioration over the first day, which carried more prognostic information than admission values alone. The mentation rule is the inverse: assess at admission, before any sedation or opioid administration confounds the assessment.

The mentation scale is a 5-level ordinal scale, the same one used in APPLE-fast: 0 (normal), 1 (stands unassisted, dull), 2 (stands only when assisted, dull), 3 (unable to stand, responsive), 4 (unable to stand, unresponsive). The fluid score is a 3-level ordinal scale based on FAST/TFAST ultrasound (Boysen et al., JAVMA 2004): 0 (no free fluid), 1 (free fluid in one cavity), 2 (free fluid in two or more cavities).

Per the original paper's footnote, if pulse oximetry was not performed (history and physical exam did not prompt it) or FAST/TFAST was not done, the score-zero (referent) range may be assigned for those two variables. In this calculator the clinician must enter values explicitly; entering 98–100 for SpO₂ or selecting 0 for fluid score has the same effect.

## Counterintuitive scoring — preserved as published

Five items in the APPLE-full rubric are clinically counterintuitive. They are preserved exactly as Hayes published them, because the multivariable regression assigns coefficients reflecting the mortality variance **not already captured by the other nine variables**, not the marginal univariable association. The paper explicitly addresses this on page 11: *"Although the scores assigned in a multivariable model may not be clinically intuitive, they reflect the mortality risk findings of the dataset. Clinically intuitive scoring should not be anticipated in a multivariable context. The lowest risk categories for each variable do not necessarily correspond to the normal range in a multivariable context."*

**Creatinine 0–0.62 mg/dL (0–55 µmol/L) → 0 points (referent).** The lowest-risk band sits *below* the normal canine creatinine range. The clinical "normal" 0.63–1.35 mg/dL band scores 1, and the score then jumps to 8 in the mild azotemia band and 9 with severe azotemia. The cleanest referent for creatinine in the multivariable context is the very lowest band, likely reflecting a population of dogs with no kidney injury and no significant correlated derangements.

**WBC <5.1 ×10⁹/L → 9 points.** Leukopenia is the *highest*-scoring WBC band, higher than marked leukocytosis (>18 ×10⁹/L → 3 pts). In an ICU dog this is clinically congruent: leukopenia tracks with severe sepsis with consumption, parvovirus, immune-mediated processes with bone-marrow suppression, and chemotherapy-induced myelosuppression in oncology patients. Leukocytosis, by contrast, is non-specific.

**Albumin 31–32 g/L → 9 points, higher than <26 g/L which scores 6.** This is the multivariable artifact the paper explicitly discusses by name on page 11: *"in the APPLE-full model an albumin of 31–32 g/L was associated with a greater mortality risk than an albumin of <26 g/L when all other variables in the model were taken into account."* The univariable association of albumin with mortality is the expected monotonic-decreasing one; the multivariable adjustment compresses the <26 g/L bucket because severe hypoalbuminemia tracks with other variables (creatinine, lactate, bilirubin) already in the model.

**Total bilirubin scoring is non-monotonic.** Mild bilirubinemia (0.24–0.46 mg/dL) carries the highest score (6 pts), increasingly severe bilirubinemia scores lower (0.47–0.93 → 4 pts, >0.93 → 3 pts). The univariable LOWESS plot in Figure 1 of the original paper shows steep risk rise at low bilirubin elevation, then plateau, exactly the pattern that produces this multivariable behavior. Severe bilirubinemia's mortality is largely captured by correlated variables in the 10-variable set; mild bilirubinemia retains independent predictive value.

**Respiratory rate 49–60 bpm → 6 points, higher than >60 bpm which scores 5.** Mild–moderate tachypnea outweighs frank tachypnea in the multivariable context. Same general explanation: the extremes track with other variables in the model and lose marginal contribution.

## Interpretation

The total score maps to predicted hospital mortality via the logistic equation:

$$ P(\text{death}) = \frac{e^R}{1 + e^R}, \quad R = 0.237 \times \text{score} - 8.294 $$

At score 0 the predicted mortality is ~0.02%. At score 30 it's ~23.4%. At score 40 it's ~58.4%. At score 50 it's ~86.4%. At the score-80 ceiling it asymptotes near 100%.

These are population-level estimates. The 95% confidence intervals around any individual point prediction are wide. Hayes Figure 5 makes this visible. A patient scoring 35 might have anywhere from 30% to 80% population-level mortality probability depending on where in the data sample they fall. Use the score for **stratification and triage support**, not for binary prognostication.

## Limitations and caveats

The Hayes 2010 cohort was a single-center referral population at a Canadian teaching hospital, and 96% of the 149 deaths were euthanasias. The authors performed sensitivity analyses censoring successive euthanasia categories and found discrimination *increased* as euthanasias were removed (AUROC rising from 0.91 to 0.94 in the all-natural-death sub-cohort), which is reassuring: the model isn't simply predicting "the clinician will recommend euthanasia." But the population is still not perfectly generalizable to first-opinion hospitals, ICUs with stricter admission criteria, or any setting outside North American referral practice. External validation across geographies remains incomplete; Hayes 2010 is what we have.

The model was built and validated on 24-hour values. Don't apply it to admission-only values or values at any other time point; the published performance characteristics will not hold. If the patient is rapidly deteriorating, re-score at 24 h captures their actual trajectory.

Several variables are not measured in every hospitalized dog: pulse oximetry might not be on a stable, alert dog who's just here for IV fluids; FAST/TFAST might not be in the workup for a clearly non-trauma presentation. The published guidance is to assign zero in those cases (i.e., use the referent range). The cleaner approach when running the score for clinical research is to standardize the data collection.

US/SI unit boundary discrepancies are minor but real. The published US and SI tables in the original paper round band edges differently for creatinine, bilirubin, and lactate. This calculator uses SI as the canonical internal representation, with US inputs converted to SI before scoring, which can produce a one-band shift for values within ~1–2% of a band boundary. For routine clinical use the difference is well within the model's individual-patient confidence interval.

## Citation

Hayes G, Mathews K, Doig G, Kruth S, Boston S, Nykamp S, Poljak Z, Dewey C. The Acute Patient Physiologic and Laboratory Evaluation (APPLE) Score: A Severity of Illness Stratification System for Hospitalized Dogs. *J Vet Intern Med* 2010;24:1034–1047. [doi:10.1111/j.1939-1676.2010.0552.x](https://doi.org/10.1111/j.1939-1676.2010.0552.x)
