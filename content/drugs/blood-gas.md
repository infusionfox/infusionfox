# Clinical background

Blood gas analysis identifies acid-base disturbances and gauges their
severity. The four canonical disturbances (metabolic acidosis,
metabolic alkalosis, respiratory acidosis, respiratory alkalosis) each
have predictable patterns on pH, PCO₂, and HCO₃⁻. Interpretation under
time pressure benefits from a structured approach: identify acidemia
versus alkalemia, identify the primary disturbance, check whether the
observed compensation matches the rule of thumb, and look for mixed
disorders when compensation is off. The calculator follows that
algorithm; this article is the underlying reasoning.

## Physiology

Body pH is determined by the ratio of HCO₃⁻ to dissolved CO₂, the
Henderson-Hasselbalch relationship. PCO₂ is set by alveolar
ventilation: when ventilation increases, PCO₂ falls and pH rises;
when ventilation decreases, PCO₂ rises and pH falls. HCO₃⁻ is set by
renal handling (excretion of H⁺ as titratable acid and ammonium,
reabsorption of filtered HCO₃⁻) and by buffering of fixed acids.
The system has two arms because the body has two ways to lose or
gain acid: as CO₂ via the lungs and as fixed acid via the kidneys.

The normal pH of extracellular fluid is approximately 7.40. Each
primary acid-base disturbance changes one component of the
Henderson-Hasselbalch ratio in a specific direction, and the body
compensates by changing the other component in the same direction
to limit the change in pH:

| Primary disturbance | Primary change | Compensatory response |
|---|---|---|
| Metabolic acidosis | ↓ HCO₃⁻ | ↓ PCO₂ (hyperventilation) |
| Metabolic alkalosis | ↑ HCO₃⁻ | ↑ PCO₂ (hypoventilation) |
| Respiratory acidosis | ↑ PCO₂ | ↑ HCO₃⁻ (renal H⁺ excretion) |
| Respiratory alkalosis | ↓ PCO₂ | ↓ HCO₃⁻ (renal HCO₃⁻ excretion) |

Compensation moves pH back toward but never to normal, and
overcompensation does not occur. If observed pH is normal despite
abnormal PCO₂ and HCO₃⁻, the patient has a mixed disorder (two
processes pulling pH in opposite directions) rather than fully
corrected compensation.

## Sampling

Arterial samples are preferred when oxygenation matters or in shock
states where peripheral vascular collapse compromises venous samples.
Venous samples (jugular preferred over cephalic, which has stasis
artifact) are adequate for acid-base evaluation alone and easier to
obtain. Venous PCO₂ runs slightly higher and pH slightly lower than
arterial because of local tissue metabolism; the calculator switches
reference ranges based on the sample type.

Capillary samples from a warmed pinna (dogs) or claw (cats) approximate
arterial values in stable patients but are unreliable in shock.

Sample handling matters: PCO₂ rises and pH falls within 20–30 minutes
at room temperature. Analyze immediately or store on ice. Total CO₂
measured by automated chemistry analyzer may differ by up to 5 mmol/L
from total CO₂ measured by blood gas analysis depending on
collection and handling, which is one reason the reported HCO₃⁻ on a
chemistry panel and a simultaneous blood gas don't always match.

## Approach to interpretation

DiBartola Ch. 9 frames the interpretation as four questions, in order:

1. **Is an acid-base disturbance present?** Check pH. If outside the
   reference range, a disturbance is present. Normal pH does not rule
   out a disturbance. A counterbalancing mixed disorder can produce
   a normal pH.

2. **What is the primary disturbance?** If acidemic and HCO₃⁻ is low,
   metabolic acidosis. If acidemic and PCO₂ is high, respiratory
   acidosis. If alkalemic and HCO₃⁻ is high, metabolic alkalosis. If
   alkalemic and PCO₂ is low, respiratory alkalosis. When both PCO₂
   and HCO₃⁻ are deranged in the direction that explains the pH,
   one is primary and the other reflects either compensation or a
   second concurrent disorder.

3. **Is the secondary response as expected?** Apply the
   species-specific rule of thumb (see "Compensation rules" below).
   Observed compensation within the expected range is consistent with
   a simple disorder; outside the range suggests a mixed disorder.

4. **What underlying disease(s) explain the disturbance?** Compare the
   acid-base pattern to the history and physical findings. Metabolic
   acidosis in a vomiting dog is suspicious for inappropriate (does
   not fit the typical pattern); metabolic acidosis in a diarrheic
   puppy fits.

## Compensation rules

The compensation rule of thumb predicts how much the compensating
component should change for a given primary disturbance. Observed
values within ±2 (mm Hg or mEq/L) of the predicted value are
consistent with a simple disorder. Outside that window suggests a
mixed disorder.

**For dogs**, the rules (DiBartola Table 12-2, originally from
de Morais and DiBartola 1991):

- Metabolic acidosis: PCO₂ falls 0.7 mm Hg per 1 mEq/L fall in HCO₃⁻
- Metabolic alkalosis: PCO₂ rises 0.7 mm Hg per 1 mEq/L rise in HCO₃⁻
- Acute respiratory acidosis: HCO₃⁻ rises 0.15 mEq/L per 1 mm Hg rise in PCO₂
- Chronic respiratory acidosis: HCO₃⁻ rises 0.35 mEq/L per 1 mm Hg rise in PCO₂
- Acute respiratory alkalosis: HCO₃⁻ falls 0.25 mEq/L per 1 mm Hg fall in PCO₂
- Chronic respiratory alkalosis: HCO₃⁻ falls 0.55 mEq/L per 1 mm Hg fall in PCO₂

The acute-vs-chronic split for respiratory disorders matters because
renal adaptation takes 2–5 days to reach steady state. Acute
compensation is purely from intracellular non-bicarbonate buffer
titration and is complete within 15 minutes. The greater HCO₃⁻
change in chronic respiratory disorders reflects renal acid handling
catching up.

Metabolic compensation by the lungs begins immediately but takes 17–24
hours to fully develop. A patient in the first day of metabolic
acidosis may show "less than expected" respiratory compensation
simply because the response hasn't completed; this is not
necessarily a mixed disorder.

## Cat-specific caveats

Cat physiology departs from dog physiology here in a way that is often
missed. Reading this section before applying any compensation rule to
a cat is important.

DiBartola Ch. 12, p. 304: *"the feline kidney apparently is unable to
adapt to metabolic acidosis and does not increase production of
ammonia or glucose from glutamine during acidosis. Based on these
studies, cats may not compensate for metabolic acidosis to the same
extent (if at all) as do dogs and humans. Thus formulas for dogs or
humans should not be extrapolated for use in cats."*

In practical terms:

- A cat with metabolic acidosis and a **normal PCO₂** may NOT have a
  mixed disorder. It may just be a cat.
- The dog rule (0.7 mm Hg ↓ PCO₂ per 1 mEq/L ↓ HCO₃⁻) does not apply
  to cats with metabolic acidosis. The calculator does not give an
  "expected PCO₂" when species is set to cat and the primary disorder
  is metabolic acidosis.
- Clinical context (history, hydration status, electrolyte panel,
  blood pressure, lactate) matters more than the blood gas alone in
  these cases.

Cat-specific data is also limited for chronic respiratory disorders
(Table 12-2 lists chronic respiratory acidosis as "Unknown"). The
calculator surfaces this gap rather than substituting the dog rule.
For acute respiratory disorders, cat compensation appears to be
similar to dogs based on small studies, and metabolic alkalosis
compensation in kittens with dietary chloride depletion was also
similar to dogs.

## Anion gap

The anion gap is the difference between commonly measured cations
(Na⁺) and commonly measured anions (Cl⁻ + HCO₃⁻):

$$\text{AG} = [\text{Na}^+] - ([\text{Cl}^-] + [\text{HCO}_3^-])$$

There is no actual gap. The law of electroneutrality is preserved by
unmeasured anions (mostly plasma proteins, with smaller contributions
from phosphate, sulfate, lactate, and other organic acids) and
unmeasured cations (calcium, magnesium, trace elements). The "gap" is
the net of unmeasured anions minus unmeasured cations.

Reference ranges from DiBartola Ch. 9, p. 244:

- **Dogs:** approximately 13–25 mEq/L (mean ~19)
- **Cats:** approximately 17–31 mEq/L (mean ~24)

Cats have a higher AG because they have a higher net negative charge
on plasma proteins, not because they have an underlying acid-base
problem.

The primary use is in metabolic acidosis. An elevated AG suggests
addition of organic acid (high-AG metabolic acidosis): lactate,
ketones, ethylene glycol metabolites, uremic acids. A normal AG in
the setting of metabolic acidosis suggests loss of HCO₃⁻ replaced
by chloride (hyperchloremic, normal-AG metabolic acidosis): GI
loss in small bowel diarrhea, proximal renal tubular acidosis,
dilutional acidosis. Both can coexist.

Hypoalbuminemia reduces the AG. In humans the correction is roughly
2.5 mEq/L per 1 g/dL fall in albumin; similar magnitude in dogs. A
patient with hypoalbuminemia and an apparently normal AG may
actually have a high AG that is being masked. For this reason
some authors recommend an "albumin-corrected anion gap," though the
correction formulas were derived in humans and the appropriate
veterinary coefficient is uncertain.

The AG is rarely useful outside metabolic acidosis. In metabolic
alkalosis or respiratory disorders, the AG is usually normal and
provides no additional information.

## Common patterns

**Diabetic ketoacidosis.** Classic high-AG metabolic acidosis from
β-hydroxybutyrate and acetoacetate accumulation. Respiratory
compensation expected (Kussmaul breathing). Concurrent hyponatremia
and hypokalemia are common from osmotic diuresis. The AG often falls
disproportionately to HCO₃⁻ as the ketones are cleared with insulin,
sometimes leaving a transient hyperchloremic acidosis during recovery.

**Vomiting (upper GI).** Loss of HCl produces metabolic alkalosis with
hypochloremia. Volume depletion and hypokalemia commonly accompany.
Compensation by hypoventilation occurs but is limited because of
ongoing demand for oxygen. The pH rarely fully normalizes.

**Diarrhea (small bowel).** Loss of bicarbonate-rich fluid produces
hyperchloremic (normal-AG) metabolic acidosis. If volume depletion
leads to hypoperfusion, a lactic acidosis component (high AG) can
overlay the normal-AG picture, producing a mixed metabolic acidosis.

**Renal failure.** Mixed picture. Mild high-AG component from
retained uremic acids and phosphate. Hyperchloremic component from
impaired renal acidification (functional distal RTA). Cats with
chronic kidney disease often show a milder acidosis than dogs because
of the species' limited renal compensation.

**Inhalant anesthesia.** Inhalants depress ventilation and produce
acute respiratory acidosis. Renal compensation has no time to develop.
Expect HCO₃⁻ within 0.15 mEq/L of normal per 1 mm Hg rise in PCO₂.

**Heatstroke.** Variable. Early: respiratory alkalosis from panting.
Later: lactic acidosis from hypoperfusion overlaying or replacing
the respiratory picture. Often a mixed disorder by the time of
presentation.

**CPR.** Mixed metabolic acidosis (lactate from poor perfusion) and
respiratory acidosis (impaired ventilation). Arterial samples may
look better than the tissue acid-base state because circulating
blood through nonperfusing tissue does not equilibrate with it.
Venous samples are more representative of tissue acid-base status
during CPR.

## Limitations of the calculator

The calculator gives a structured interpretation but does not
diagnose underlying disease. Several specific limitations:

- **No strong-ion / Stewart approach.** The traditional
  Henderson-Hasselbalch framing is what most clinicians use and what
  this calculator implements. The strong-ion / Stewart approach
  (DiBartola Ch. 13) provides additional insight into the role of
  weak acids (albumin, phosphate) and strong ions (Na, Cl, lactate)
  in determining acid-base balance, particularly in critically ill
  patients with hypoalbuminemia. Worth knowing about; not in scope
  here.

- **No correction for hypoalbuminemia.** The AG is not corrected for
  albumin in this calculator because the correction formulas come
  from human medicine and the appropriate veterinary coefficient is
  uncertain. Read the AG with the albumin in mind: a normal AG in a
  hypoalbuminemic patient may be hiding an unmeasured anion.

- **No diagnosis of underlying cause.** Identifying "high-AG
  metabolic acidosis" doesn't tell you whether it's lactate, ketones,
  ethylene glycol, or uremic acids. Lactate, ketones, and BMP point
  the way.

- **Mixed-disorder identification is limited to compensation
  mismatch.** Triple disorders (e.g., metabolic acidosis +
  metabolic alkalosis + respiratory disorder) cannot be reliably
  diagnosed without additional information from the chemistry panel
  (chloride, sodium, anion gap, "delta gap" analysis).

For these limitations, the clinical context, history, and ancillary
labs remain the primary tools. The blood gas calculator is a
finding-and-framing aid, not a substitute for clinical judgment.

## Sources

- DiBartola SP, ed. *Fluid, Electrolyte, and Acid-Base Disorders in
  Small Animal Practice*. 4th ed. Elsevier; 2012. Chapter 9
  (Introduction to Acid-Base Disorders), pp. 231–252. Reference
  ranges (Table 9-1, p. 241) and anion-gap interpretation (pp.
  244–245).
- DiBartola SP, ed. *Fluid, Electrolyte, and Acid-Base Disorders in
  Small Animal Practice*. 4th ed. Elsevier; 2012. Chapters 10–13
  (the four canonical disturbances and mixed disorders). Chapter 12
  (Metabolic Acidosis), Table 12-2 p. 304, supplies the compensation
  rules of thumb encoded by the calculator and the cat-specific
  caveat against extrapolating dog formulas to cats with metabolic
  acidosis.
- de Morais HSA, DiBartola SP. Ventilatory and metabolic compensation
  in dogs with acid-base disturbances. *J Vet Emerg Crit Care*
  1991;1:39–49. Original source of the dog compensation rules of
  thumb reproduced in DiBartola Table 12-2.
