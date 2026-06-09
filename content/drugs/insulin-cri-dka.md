# Clinical background

The continuous low-dose IV insulin CRI is the standard approach to insulin therapy in diabetic ketoacidosis (DKA) when continuous infusion is practical. Compared to intermittent IM dosing, the CRI offers finer titration of plasma insulin concentration and easier management of the BG sliding scale that drives the protocol. Both routes work, neither is clearly superior in outcomes, and the choice usually comes down to local logistics and clinical preference.

## What insulin does in DKA

Insulin therapy addresses the central pathophysiology of DKA: hepatic gluconeogenesis is unrestrained, peripheral glucose uptake is suppressed, and lipolysis is generating free fatty acids that are converted to ketone bodies because the citric-acid cycle is full. Insulin reverses each of these:

- **Promotes peripheral glucose uptake** via GLUT4 translocation in muscle and adipose tissue
- **Suppresses hepatic gluconeogenesis and glycogenolysis**
- **Inhibits lipolysis**: cutting off the free-fatty-acid supply to the ketogenic pathway
- **Restores the acetyl-CoA balance** so existing ketones can re-enter normal metabolism

Of these, the suppression of lipolysis is the most important for ketoacidosis resolution. Glucose normalization happens fast, usually within the first several hours, but ketone clearance lags. Patients can have BG in target range while still being acidotic and ketonemic. **Treat to ketone resolution, not BG resolution.**

## The low-dose principle

Low-dose insulin (≈0.05–0.1 U/kg/hr delivered) provides full physiologic insulinization without the swings of higher-dose protocols. The clinical advantages over older "sliding-scale insulin" approaches in human medicine, and why the same principle is used in veterinary DKA:

- More gradual decline in BG, reducing the risk of cerebral edema from rapid osmotic shifts
- Smaller swings in serum potassium and phosphorus as those electrolytes shift intracellularly with insulin action
- More predictable response that enables protocolized titration

The protocol delivers this via a 2.2 U/kg loading dose mixed into a 250 mL bag of 0.9% NaCl, with the pump rate adjusted by a published sliding scale in response to the current blood glucose.

## Cat dosing

The literature has historically noted that 1.1 U/kg has been "occasionally recommended" for cats based on a presumed higher risk of neurologic adverse effects from rapid BG correction. A more recent study using the canine 2.2 U/kg/day dose in cats, paired with the same sliding scale, found no increase in neurologic or biochemical adverse events. The current InfusionFox default is **2.2 U/kg/day for both species**, with 1.1 U/kg/day available as a conservative cat option for clinicians who prefer it.

## When to start insulin

The optimal timing has been debated. Older literature recommended waiting 6–8 hours after starting fluids and electrolyte correction; recent evidence suggests earlier insulin initiation (around 4 hours after admission) leads to faster DKA resolution without increased complications. Practical recommendations:

- **Start fluids first.** Resuscitate intravascular volume, begin rehydration, and check serum electrolytes before any insulin.
- **Correct hypokalemia before starting insulin.** Insulin shifts K intracellularly; starting it in a patient with low-normal or frankly low K can precipitate severe hypokalemia and arrhythmias. Many institutions wait until serum K is at least 3.5 mEq/L before insulin, and many supplement K from the start.
- **Recheck electrolytes within the first 4 hours.** If they're stable and the patient is rehydrating, insulin can usually be started.
- **Don't delay insulin indefinitely waiting for a "perfect" picture.** DKA does not resolve without insulin; ketogenesis continues until insulinization halts lipolysis.

## Bag preparation

The protocol is specific:

- Add 2.2 U/kg of regular crystalline insulin to a 250 mL bag of 0.9% NaCl (use 1.1 U/kg if you've chosen the conservative cat option)
- **Prime the line and discard the first 50 mL of the prepared solution before connecting to the patient**

The discard step matters. Regular insulin binds to PVC plastic IV tubing, the first amount of solution through the line is partially absorbed into the plastic. Without the prime-and-discard, the patient receives substantially less insulin than the calculated rate would suggest for the first 30–60 minutes. Saturating the binding sites with a 50 mL prime ensures the delivered dose matches the calculated dose from the start.

The bag concentration after prime is approximately 0.0088 U/mL × patient weight in kg (so a 20 kg dog ends up with a bag of ≈0.176 U/mL).

## Use regular crystalline insulin only

This protocol is built around regular crystalline insulin (Humulin R, Novolin R). **Do not substitute other insulin types:**

- **Lispro and aspart**: rapid-acting analogs investigated as alternatives in veterinary DKA. Preliminary studies suggest they're safe and equally effective, but they are not yet standard of care and the published sliding scales aren't validated for them.
- **NPH, glargine, detemir, degludec**: intermediate to long-acting. Wrong pharmacokinetics for an IV CRI; some are not safe to give IV at all (NPH is a suspension). Glargine has been used in hybrid SQ + IM protocols (not as IV CRI).

The standard sources all specify regular crystalline insulin for the IV CRI protocol.

## Subcutaneous administration is not appropriate

SC insulin is **not** appropriate in dehydrated DKA patients. Peripheral perfusion is poor, SC absorption is unreliable, and the patient may receive an unpredictable bolus when perfusion improves. Use IV CRI or intermittent IM in DKA patients until they're rehydrated, eating, and have stopped requiring active insulin titration. SC maintenance insulin starts after the DKA crisis has resolved.

## The sliding scale

The protocol is straightforward:

| Blood glucose | Fluid line | Pump rate |
|---|---|---|
| > 250 mg/dL | 0.9% NaCl | 10 mL/hr |
| 200–250 | 0.9% NaCl + 2.5% dextrose | 7 mL/hr |
| 150–199 | 0.9% NaCl + 2.5% dextrose | 5 mL/hr |
| 100–149 | 0.9% NaCl + 5% dextrose | 5 mL/hr |
| < 100 | 0.9% NaCl + 5% dextrose | STOP insulin |

**The fluid composition steps in tandem with the insulin rate.** As BG falls, dextrose is added to the line so that insulin can keep working on ketones without dropping BG into a dangerous range. The CRI calculator surfaces both pieces, the pump rate and the matching fluid composition, together for whatever BG the user enters.

The target BG decline is **50–75 mg/dL/hr toward < 250 mg/dL.** If BG is dropping faster, reduce the pump rate by stepping to a lower row. If it's dropping slower, increase the rate. **Adjust the rate, not the bag concentration**, re-mixing the bag mid-treatment is a medication-error opportunity that the sliding-scale design is meant to avoid.

## Electrolytes and acid-base

Three electrolyte derangements need close monitoring during DKA management:

- **Hypokalemia**: affects 84% of dogs after starting therapy. Insulin shifts K intracellularly. Check serum K every 4–6 hours; supplement per published sliding scales (see /hypokalemia for the InfusionFox calculator). The hypokalemia ceiling is 0.5 mEq/kg/hr, do not exceed without continuous ECG.
- **Hypophosphatemia**: affects ≈48% of dogs after starting therapy. Severe hypophosphatemia causes hemolysis (the most life-threatening complication), respiratory weakness, and cardiac dysfunction. Supplement KPhos at 0.03–0.12 mmol/kg/hr IV. **Subtract the K contribution from KPhos when calculating total K supplementation**, it's easy to over-supplement K when both KCl and KPhos are running.
- **Hypomagnesemia**: supplement MgSO4 at 0.25–1 mEq/kg/day if documented.

Check phosphorus and magnesium 1–2 times daily in the early phase. Acid-base typically corrects without bicarbonate therapy as ketones clear; bicarbonate is only considered if pH is < 7.0 after 1 hour of fluid resuscitation, and even then half-correction is the standard approach.

## Concurrent disease

DKA is almost always precipitated by a concurrent illness, pancreatitis, urinary tract infection, neoplasia, hyperadrenocorticism in dogs; hepatic lipidosis, cholangiohepatitis, pancreatitis, infections, or neoplasia in cats. Up to 74% of dogs and 93% of cats with DKA have a concurrent disease at presentation. The DKA episode will not resolve cleanly until the precipitating illness is addressed, diagnostic workup should run in parallel with the metabolic resuscitation, not after it.

## Long-term transition

Continue the IV CRI insulin (or intermittent IM) until the patient is reliably eating and drinking, hydrated, and no longer ketotic. At that point, transition to twice-daily SQ administration of an intermediate or long-acting insulin (NPH, lente, glargine, PZI in cats), along with a dietary transition (high-fiber for dogs, high-protein/low-carbohydrate for cats) and a regular monitoring schedule. The transition usually overlaps a few hours of both routes, give the first SQ dose, continue the CRI for another 2–4 hours, then stop.

## Sources

- Hoehne SN. Diabetic Ketoacidosis. In: Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 3rd ed. Elsevier; 2023. Chapter 73 (pp. 432–435), with Table 73.1 reproduced as the sliding-scale lookup.
