# Clinical background

Canine hypothyroidism is one of the most over-diagnosed endocrinopathies in primary care veterinary medicine. The 2024 Bell et al. study in JVIM reviewed 102 dogs treated for hypothyroidism at primary care practices and found that ECVIM-CA diplomates considered the diagnosis "confirmed or likely" in only a minority of those cases; many had been started on levothyroxine for life on the basis of a single low TT4 in a dog without convincing clinical signs. The cost of this is real: lifelong medication, repeat blood work, and a label that follows the patient through every subsequent consultation.

The driver of over-diagnosis is the test, not the disease. Total T4 has high sensitivity but poor specificity. About 1 in 7 apparently healthy dogs has a TT4 below the reference interval at any given moment, and concurrent illness, drugs (corticosteroids, sulfonamides, phenobarbital, NSAIDs), and even circadian variation can all suppress TT4 transiently in euthyroid dogs. The same lab value means very different things depending on the pretest probability of the patient it came from.

## What this score does

The score implements a structured pretest probability assessment adapted from the variables identified in the Corsini et al. 2023 prediction model (Frontiers in Vet Sci). Their machine-learning models, internally validated with cross-validation, achieved AUROC of 0.85–0.99 depending on which variables were included. The clinical-only models (no thyroid hormones in the inputs) reached AUROC ≈ 0.85–0.88, which is the relevant performance bracket for a pretest tool.

The variables are:

- **Signalment**: breed predisposition (Goldens, Dobermans, Irish Setters most over-represented), age (rare under 2 years, more common in middle-aged to older dogs)
- **Dermatologic signs**: bilateral symmetric truncal alopecia, recurrent pyoderma, "rat tail" alopecia, otitis externa
- **Metabolic / energy signs**: lethargy, weight gain without polyphagia, cold intolerance
- **Laboratory findings**: hypercholesterolemia (the single most useful supportive lab finding), mild non-regenerative anemia
- **Confounders**: current systemic illness or recent glucocorticoid administration both strongly suppress thyroid testing reliability

A patient with classic dermatologic syndrome plus hypercholesterolemia and lethargy in a predisposed breed scores high. A young dog of an unaffected breed with vague lethargy and no skin signs scores low. The point of the exercise is to flag, before testing, which patient is which.

## What the bands mean

**Very low / low pretest probability.** Don't test. The pretest probability is so low that even a positive result is more likely to be a false positive than true disease. Investigate alternatives: obesity, atypical Cushing's syndrome, chronic illness, behavioral causes. If clinical signs persist after addressing other differentials, reconsider testing in 4–6 weeks.

**Moderate pretest probability.** Testing is reasonable. Use a complete thyroid panel (TT4 + free T4 by equilibrium dialysis + TSH) rather than TT4 alone. Avoid testing during acute illness or within 4 weeks of glucocorticoid use.

**High / very high pretest probability.** Testing should be diagnostic. If the initial TT4 is non-diagnostic, proceed to a full panel. The 2023 AAHA Selected Endocrinopathies guidelines note that 20–40% of dogs with overt hypothyroidism have TSH within the reference range, so a normal TSH does not exclude the diagnosis in a high-pretest-probability patient.

## Important caveats

- This is a **clinical adaptation** of the Corsini variables, not a direct re-implementation of their machine-learning models. The exact probability calibration is approximate.
- The score does not include thyroid hormone results. If the patient already has thyroid testing, you are past the pretest stage.
- "Sick euthyroid" syndrome (non-thyroidal illness suppression of TT4) is not detected by the score. The "currently sick or recent steroids" question is the safeguard: if yes, defer testing.

## Sources

- Corsini A, Lunetta F, Alboni F, Drudi I, Faroni E, Fracassi F. Development and internal validation of diagnostic prediction models using machine-learning algorithms in dogs with hypothyroidism. *Front Vet Sci* 2023;10:1292988.
- Bell ET, Mooney CT, Shiel RE. Assessment of the likelihood of hypothyroidism in dogs diagnosed with and treated for hypothyroidism at primary care practices: 102 cases (2016–2021). *J Vet Intern Med* 2024;38:881–891.
- Fleeman LM et al. *2023 AAHA Selected Endocrinopathies of Dogs and Cats Guidelines*: Hypothyroidism. American Animal Hospital Association.
