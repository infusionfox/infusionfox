# Clinical background

The Acute Patient Physiologic and Laboratory Evaluation (APPLE) score is a diagnosis-independent illness severity tool for hospitalized dogs. Hayes and colleagues at the University of Guelph published two parsimonious models in 2010: a 10-variable score (APPLE-full, 0–80) and a 5-variable score (APPLE-fast, 0–50). This calculator implements the fast version.

The score's intended use is **objective stratification of illness severity**: primarily for risk-adjusting treatment groups in clinical research, and secondarily for documenting baseline severity at admission. It was explicitly **not** designed to drive euthanasia decisions, and the authors went out of their way to caution against that use.

## How the score was built

810 consecutive ICU admissions over 6 months at the Guelph teaching hospital. 55 candidate variables collected per admission per a written protocol; 598 records used for model construction and 212 held out for validation. Backward stepwise logistic regression with manual sensitivity analysis selected the 5-variable APPLE-fast set: glucose, albumin, lactate, platelet count, and mentation. Coefficients were converted to integer points using a constant multiplier chosen so the maximum sum approximated 50.

The final APPLE-fast model had AUROC 0.86 on the construction cohort and 0.85 on the validation cohort, with Hosmer-Lemeshow calibration P-values of 0.38 and 0.60 respectively (well above the 0.05 threshold for acceptable calibration). External validation by Le Gal and colleagues (EVECC 2021) confirmed the >25 cutoff carries specificity 85% and sensitivity 67% for hospital mortality.

## Variable definitions

| Variable | Source | Timing |
|---|---|---|
| Glucose | Plasma, automated chemistry | Most abnormal in first 24 h |
| Albumin | Plasma, automated chemistry | Most abnormal in first 24 h |
| Lactate | Whole blood, point-of-care | Most abnormal in first 24 h |
| Platelet count | EDTA, automated hematology | Most abnormal in first 24 h |
| Mentation | Clinical assessment | **Admission, before sedation/analgesia** |

The "most abnormal" rule for the lab variables exists to capture the trajectory of deterioration over the first day, which carried more prognostic information than admission values alone. The mentation rule is the inverse: assess it at admission, before any sedation or opioid administration confounds the assessment. The mentation scale itself is a 5-level ordinal scale ranging from 0 (normal) through 4 (recumbent, unresponsive).

## Counterintuitive scoring — preserved as published

Three items in the rubric are clinically counterintuitive. They are preserved exactly as Hayes published them, because the multivariable model assigns coefficients reflecting the mortality variance **not already captured by the other variables**, not the marginal univariable association.

**Glucose >15 mmol/L (>273 mg/dL) → 0 points.** The referent (lowest-risk) group in this cohort. Dominated by treated diabetics and patients with transient stress hyperglycemia; treated diabetics in particular carried lower mortality than the population mean. The Edwards 2025 DKA paper called this out as a quirk that causes APPLE-fast to under-score severity in dogs with DKA. In that study, all dogs had BG ≥275 mg/dL and so received 0 points for glucose, defeating the variable's discriminative power.

**Platelet count 151–200 ×10⁹/L → 6 points; <151 → 5 points.** Mild thrombocytopenia scores higher than severe thrombocytopenia. The paper explicitly flags this as a multivariable artifact (page 11): the coefficients reflect mortality risk not already explained by the other variables, and the resulting integer point assignment isn't required to be clinically intuitive.

**Albumin >35 g/L (>3.5 g/dL) → 2 points.** After adjusting for glucose, lactate, platelets, and mentation, high albumin tracked with slightly increased mortality. The univariable relationship (Fig 1 of the original paper) is the expected monotonic-decreasing one; the multivariable adjustment flips the direction at the high end.

## Interpretation

The total score maps to predicted hospital mortality via the logistic equation:

$$ P(\text{death}) = \frac{e^R}{1 + e^R}, \quad R = 0.249 \times \text{score} - 7.020 $$

Anchor points (population averages, wide individual CIs):

| Score | Predicted mortality |
|---|---|
| 0  | ~0.1% |
| 10 | ~1% |
| 20 | ~12% |
| 25 | ~31% |
| 30 | ~61% |
| 40 | ~95% |
| 50 | ~99.6% |

Hayes 2010 Table 5 offers two cutoffs depending on whether you weight sensitivity or specificity. The >25 cutoff is the more specific one (85% specificity, 67% sensitivity); the >22 cutoff trades some specificity for sensitivity (80% / 74%). The >25 cutoff has external validation from Le Gal 2021; >22 does not.

## Limitations

**Wide individual confidence intervals.** Look at Fig 5 of the original paper before applying this to an individual patient. At every score, the 95% population CI is wide: a patient scoring 30 has roughly a 60% predicted mortality but the band encompasses ~40–80%. The score is population-level epidemiology dressed up as a point prediction.

**Single-center construction.** Built on one teaching hospital's referral-heavy ICU population. Patients in a different case mix (e.g., primary-care emergency, post-op orthopedic, neonatal) may not calibrate the same. The Korean qSOFA study (PMC11992716, 2025) found APPLE-fast AUROC of only 0.61 in their cohort, far below the 0.85 reported in Hayes's validation set, suggesting the model's discrimination does not generalize uniformly.

**Euthanasia bias.** 96% of deaths in the construction cohort were euthanasias. Hayes addressed this with sensitivity analysis (Table 6: model still performed well with euthanasia cases progressively censored) but the cohort fundamentally captured veterinarian decisions to euthanize, not biological mortality alone.

**Not for euthanasia decisions.** The paper devotes a paragraph to this point in the Discussion. At the >25 cutoff with 85% specificity, 15% of dogs predicted to die would in fact live, so score-driven euthanasia would unnecessarily terminate 15% of patients. The authors are explicit that the score "should remain the collective responsibility of the individual clinician and owner. … Using these tools to dictate individual patient decisions is not appropriate."

## Companion scores

The feline equivalent (Hayes 2011) uses a different 5-variable set: temperature, mentation, mean arterial pressure, lactate, and PCV. AUROC was 0.83 on construction and 0.76 on validation, lower than the canine version. This calculator covers dogs only; the feline version is not currently implemented in InfusionFox.

For diabetic ketoacidosis specifically, Edwards 2025 showed APPLE-full (but not APPLE-fast) predicts mortality, with AUROC 0.67 at an optimal cutpoint of 23.5. Beta-hydroxybutyrate (BOHB) at cutpoint 4.75 mmol/L was also independently predictive in that population (AUROC 0.75).
