# Clinical background

Hypoadrenocorticism, Addison's disease, has earned the name "the great pretender" because its presentation is vague, intermittent, and overlaps with chronic enteropathies, primary kidney disease, hepatobiliary disease, and behavioral lethargy. Prevalence in the general dog population is roughly 0.06–0.28%, but among dogs with chronic gastrointestinal signs the prevalence reaches 4%. Once the diagnosis is suspected, confirmation by ACTH stimulation is straightforward; the challenge is suspecting it in the first place.

About 30–40% of cases present without the classic hyponatremic-hyperkalemic electrolyte pattern. These eunatremic, eukalemic Addison's (ENEKH) cases lack the most reliable laboratory tip-off and are the ones most often missed. They typically have only glucocorticoid deficiency at presentation (sometimes called "atypical" or "GDH"), and may progress to a full mineralocorticoid-deficient crisis if not recognized.

## What this score does

The score is an additive-points adaptation of the predictor variables identified in the Reagan 2026 ensemble machine-learning model (the "Addison Detect Tool" or ADT, JVIM 2026), supplemented by signalment data from the canine HOAC literature (Guzmán Ramos 2022, Bennaim 2024).

The ADT's published performance on the development cohort was sensitivity 96%, specificity 97%, AUROC 0.994 for distinguishing HOAC from non-HOAC. The simplified additive version implemented here cannot match that ML performance, but it captures the directionally correct contributions from each variable and serves the right purpose: triaging which dogs warrant ACTH stimulation testing.

## The variables

**Na:K ratio.** A Na:K < 27 is highly suggestive of hyperkalemic Addison's; ratios under 24 are nearly pathognomonic in the absence of confounders. ENEKH patients have normal ratios, so a normal ratio does not rule out HOAC.

**Lymphocytes and eosinophils.** Cortisol deficiency removes the normal suppression of these cell lines. Lymphocytosis (>5000/µL) and eosinophilia (>1500/µL) in an ill dog are highly suggestive. Conversely, profound lymphopenia argues against HOAC because it suggests cortisol production is intact (or excess).

**Lack of stress leukogram.** A sick dog *should* show a stress leukogram (neutrophilia, monocytosis, lymphopenia, eosinopenia). When you see a sick dog without a stress response, cortisol deficiency is on the differential.

**Waxing-waning GI signs.** The classic HOAC presentation is intermittent, often diet-attributed vomiting and diarrhea over weeks to months, sometimes responsive to fluid therapy and steroids (which paradoxically masks the diagnosis). This single historical detail is one of the highest-yield questions to ask.

**Hypoglycemia and hypercalcemia.** Both are reasonably common in HOAC patients (hypoglycemia from cortisol deficiency, hypercalcemia mechanism multifactorial). They are not specific to HOAC but contribute supporting evidence.

**Resting cortisol.** The single most powerful test. **Resting cortisol > 2 µg/dL effectively rules out HOAC** in a dog not receiving exogenous glucocorticoids. The score subtracts heavily when this is the case (−8 points). Resting cortisol < 2 µg/dL does not confirm HOAC (most dogs with low resting cortisol do not have HOAC), but it is the gateway to ACTH stimulation.

**Breed predisposition.** Standard Poodles, Portuguese Water Dogs, Soft-Coated Wheaten Terriers, and Nova Scotia Duck Tolling Retrievers carry the strongest documented breed risk. Bearded Collies, Great Danes, Leonbergers, and Rottweilers are also over-represented.

## What the bands mean

**Very low / low.** Hypoadrenocorticism is unlikely. Investigate other causes. If signs persist or recur, reconsider; Addison's is the great pretender, and a single negative score should not permanently close the differential.

**Moderate.** Reasonable pretest probability. Resting cortisol is the cheap first step. If resting cortisol is below 2 µg/dL, proceed to ACTH stimulation.

**High / very high.** ACTH stimulation testing is indicated. If the patient is unstable (collapsed, hyperkalemic, hypotensive), begin empiric treatment with IV fluid resuscitation and dexamethasone (which does not cross-react with the cortisol assay) while testing is underway. Do not delay treatment to complete the test.

## Important caveats

- This is a **simplified additive adaptation** of the Reagan 2026 ML model variables. Exact probability calibration is approximate, not validated against the original cohort.
- Recent exogenous corticosteroid use (within 4 weeks) confounds resting cortisol and ACTH stim testing. The score does not currently capture this; clinically, defer testing or use dexamethasone if testing during empiric treatment.
- The score is for primary HOAC screening. Secondary HOAC (pituitary/hypothalamic, often from prolonged steroid use) requires a different diagnostic approach.

## Sources

- Reagan KL, Reagan BA, Gilor C. Predicting the likelihood of hypoadrenocorticism in dogs using signalment and routine laboratory results with an ensemble machine learning predictive model. *J Vet Intern Med* 2026;40:e70067.
- Bennaim M, Centola S, Ramsey IK, Mooney CT. Can we predict hypoadrenocorticism in dogs with resting hypocortisolemia? A predictive model based on clinical, haematological, and biochemical variables. *J Vet Intern Med* 2024;38:1546–1556.
- Guzmán Ramos PJ, Bennaim M, Shiel RE, Mooney CT. Diagnosis of canine spontaneous hypoadrenocorticism. *Canine Med Genet* 2022;9:6.
