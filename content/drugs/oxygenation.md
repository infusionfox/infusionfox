# Clinical background

The oxygenation assessment calculator answers two related but distinct questions from a single arterial blood gas: how severe is the patient's oxygenation impairment (P:F ratio), and what is the physiologic cause of any hypoxemia (A-a gradient). Both are computed from PaO₂, FiO₂, and PaCO₂; both are interpreted in context with each other and with the patient's clinical status. Neither number alone is sufficient.

## Why P:F ratio matters

A simple PaO₂ value is not directly comparable between patients receiving different concentrations of inspired oxygen. A PaO₂ of 90 mmHg looks normal at first glance, but if the patient is on 100% oxygen via endotracheal tube it represents profound oxygenation failure (P:F = 90); the same value on room air is healthy (P:F = 428). The P:F ratio normalizes PaO₂ to FiO₂ and produces a number that is comparable across patients, across time points in the same patient, and against published cutoffs.

The Berlin Definition of ARDS (2012) sets the human cutoffs that veterinary medicine has adopted with minor adjustments. The Wilkins et al 2007 JVECC consensus paper formally adapted these for dogs and cats. The cutoffs used in InfusionFox follow that adapted scheme:

- Above 400: normal oxygenation
- 300 to 400: mild oxygenation impairment, suggesting early V/Q mismatch
- 200 to 300: moderate, at the ALI (acute lung injury) threshold
- 100 to 200: severe, the ARDS-equivalent range
- Below 100: very severe, indicating refractory hypoxemia

The Berlin paper uses slightly different boundaries for the human ARDS phenotypes (mild 200-300, moderate 100-200, severe under 100). InfusionFox uses the wider "P:F under 300 indicates ALI or worse" framing because that matches how veterinary intensivists generally think about the metric and aligns with the Wilkins consensus. The exact label matters less than the trajectory: a worsening trend over hours is the clinical signal, regardless of which side of any single cutoff the patient is on.

## Why A-a gradient matters

The P:F ratio quantifies oxygenation severity but does not distinguish causes. A patient with P:F 250 could have severe pneumonia, opioid-induced hypoventilation, or pulmonary edema; the management differs substantially. The A-a gradient, interpreted alongside PaCO₂, separates these three patterns.

The alveolar gas equation predicts what the alveolar PO₂ should be given the inspired FiO₂ and the CO₂ being eliminated. In simplified form at sea level: PAO₂ = FiO₂ × 713 − PaCO₂/0.8. The patient's measured PaO₂ should be close to this calculated alveolar value; any large gap represents inefficient transfer from alveolus to capillary.

There are three physiologic causes of an elevated A-a gradient:

V/Q mismatch occurs when some lung units are ventilated but not adequately perfused (dead space) and others are perfused but not adequately ventilated (shunt-like physiology). Pneumonia, atelectasis, mild to moderate pulmonary edema, and asthma all produce V/Q mismatch as their primary mechanism. The hallmark is that supplemental oxygen corrects the hypoxemia, because boosting the PAO₂ in the still-ventilated alveoli compensates for the inefficient ones.

True shunt is venous blood that passes through the lung without ever encountering ventilated alveoli, then mixes back into the arterial circulation. Severe consolidation, fulminant pulmonary edema with alveolar flooding, atelectasis without recruitment, and intracardiac right-to-left shunts all produce true shunt. The hallmark is refractoriness to supplemental oxygen: no amount of FiO₂ in the ventilated lung units can compensate for blood that bypasses them entirely.

Diffusion impairment is the third mechanism, where ventilated and perfused alveoli are adjacent but the gas cannot cross the thickened alveolar-capillary membrane efficiently. Interstitial lung disease and pulmonary fibrosis are the classic causes; the pattern is intermediate between V/Q mismatch and shunt in oxygen response.

A normal A-a gradient with hypoxemia points to a different mechanism: hypoventilation. If the patient is not moving enough air through the alveoli, both PaCO₂ rises and PaO₂ falls in tandem; the alveolar gas equation predicts both changes proportionally, and the A-a remains normal. Look for the cause of the hypoventilation: anesthetic depth, opioid effect, neuromuscular disease (myasthenia, polyradiculoneuritis, tick paralysis), pleural space pathology (effusion, pneumothorax), or upper airway obstruction.

## Normal A-a thresholds

Room-air normal A-a is below 15 mmHg in young healthy patients; it rises modestly with age in humans and is presumed to do so in dogs and cats, though firm veterinary age-adjusted data is sparse. Most clinical reference ranges in veterinary critical care use a "less than 15 mmHg" cutoff on room air as a general rule, with the understanding that geriatric patients may run higher without underlying pathology.

On supplemental oxygen, the expected A-a rises with FiO₂. The alveolar PO₂ scales linearly with FiO₂, but the arterial PaO₂ does not climb as quickly because the oxyhemoglobin dissociation curve is already saturated at modest FiO₂. The result is that A-a widens with FiO₂ even in healthy lungs. A rough rule of thumb is that A-a should remain below (FiO₂ × 100) − 10 mmHg; in a healthy patient on 40% oxygen, A-a up to about 30 mmHg is unconcerning.

In practice, the precise A-a cutoff on supplemental oxygen matters less than the qualitative interpretation. A clearly elevated A-a (well above expected) prompts the V/Q-vs-shunt differential; a borderline or modestly elevated A-a is more useful as a trend over time than a single threshold call.

## Altitude effect

The alveolar gas equation depends on barometric pressure, and Patm falls roughly 120 mmHg per 1500 m of elevation. At sea level (Patm 760), the maximum achievable PaO₂ on room air is about 100 mmHg. At Denver elevation (1600 m, Patm ≈ 630), it falls to about 75 mmHg. At Mexico City elevation (2240 m, Patm ≈ 580), about 65 mmHg.

For a calculator user in Ridgefield CT, the default 760 mmHg is correct. For a user at altitude, overriding Patm is essential: a patient with PaO₂ 75 mmHg in Denver on room air is normal, but the same value at sea level is mildly hypoxemic. The same caveat applies to the A-a gradient interpretation, because the alveolar gas equation feeds directly from Patm.

## Practical workflow

When a patient is in respiratory distress and an arterial blood gas is available, the typical sequence is:

First, look at PaO₂ in the context of FiO₂. The P:F ratio tells you how severe the oxygenation problem is and triggers escalating respiratory support (high-flow oxygen, non-invasive ventilation, mechanical ventilation) at the appropriate severity tier.

Second, look at PaCO₂. If it is high (above 45 mmHg), hypoventilation is contributing to the picture regardless of any V/Q or shunt physiology. Address the cause of hypoventilation directly (lighten anesthesia, reverse opioids, support breathing mechanically).

Third, calculate the A-a gradient and interpret with the PaCO₂. Normal A-a with high CO₂ confirms hypoventilation alone. Elevated A-a with normal or low CO₂ indicates V/Q mismatch or shunt; the oxygen response distinguishes them, and the differential narrows by clinical context (radiographic appearance, auscultation, history).

The calculator surfaces all three numbers together and writes out the interpretation in plain language. The clinician confirms or overrides based on the full clinical picture.

## When to be skeptical of the numbers

Several common scenarios can produce misleading P:F or A-a values that need careful interpretation.

Recent FiO₂ change. The patient must have been on the current FiO₂ long enough for the arterial values to equilibrate before sampling, typically at least 20 to 30 minutes. A sample drawn shortly after switching from room air to 100% oxygen will not reflect the stable oxygenation state.

Inaccurate FiO₂ in the chart. A "100% oxygen" entry for a patient on a nasal cannula is wrong; effective FiO₂ from nasal cannula varies with flow rate and breathing pattern, typically 0.30 to 0.40 even at high flows. Use FiO₂ measured at the patient (face mask probe, endotracheal sensor) when possible.

Sampling error. A venous sample mistakenly labeled arterial will have low PaO₂ and high PaCO₂; the resulting P:F looks like severe oxygenation failure when the lungs are fine. Inspect the sample (color, pulsatile flow during draw) and confirm before acting.

Cardiac shunt. A right-to-left intracardiac shunt (reverse PDA, pulmonary hypertension with patent foramen ovale, certain congenital lesions) produces refractory hypoxemia with a high A-a that does not respond to oxygen. The pattern looks like severe pulmonary shunt physiology, but the pathology is extrapulmonary. Echocardiography distinguishes.

Methemoglobinemia. Acetaminophen toxicity in cats and certain drug exposures produce methemoglobin, which does not carry oxygen but reports a normal PaO₂ (which is dissolved oxygen, not hemoglobin-bound). The patient is profoundly hypoxic at the tissue level despite a normal-looking blood gas. Co-oximetry distinguishes by measuring methemoglobin fraction directly.

The calculator does not know about any of these scenarios; the clinician's judgment is required to recognize them.
