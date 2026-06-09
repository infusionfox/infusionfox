# Clinical background

The intermittent IM regular insulin protocol is the alternative to IV CRI for DKA management. It uses hourly IM injections, with each dose adjusted by the BG drop in the previous hour. The protocol works well when continuous IV infusion isn't practical, smaller hospitals without syringe pumps, busy ICU workflows where the patient is frequently disconnected for diagnostics, or cases where IV access is unstable.

## When to choose IM over IV CRI

Both routes are acceptable. Some practical considerations that favor each:

**Favors IV CRI:**

- Critical-care setting with continuous monitoring and a dedicated nursing presence
- Need for fine titration (eg, severely acidotic patient where small adjustments in insulin rate matter)
- Patient with stable IV access and minimal interruptions for imaging or transport
- Rapid response to BG changes is desired

**Favors intermittent IM:**

- General-practice setting without 24/7 syringe-pump capability
- Patient frequently leaving the cage for diagnostics or surgical intervention
- Unstable IV access where a CRI line might be lost mid-protocol
- Smaller hospital where the IV infrastructure isn't routinely set up for sustained CRI

The two protocols are not pharmacologically equivalent. IM dosing produces a sawtooth plasma insulin pattern with peaks 30–60 minutes after injection and troughs near the end of the hour, while CRI maintains a relatively flat plasma level. In practice, both achieve the goal of suppressing ketogenesis and bringing BG down at the target rate; the choice rarely affects outcome.

## How the protocol works

The published protocol:

**Initial loading dose:** 0.2 U/kg IM regular crystalline insulin.

**Subsequent hourly doses, dosed by the BG drop in the previous hour:**

| BG drop in last hour | Next IM dose |
|---|---|
| > 75 mg/dL | 0.05 U/kg (drop too fast, back off) |
| 50–75 mg/dL | 0.1 U/kg (on target, continue) |
| < 50 mg/dL | 0.2 U/kg (drop too slow, push) |

**Goal:** lower BG by 50–75 mg/dL/hr toward < 250 mg/dL. The same target as the IV CRI protocol.

The InfusionFox calculator implements this as a two-mode workflow. Loading mode returns the 0.2 U/kg first dose; subsequent mode takes the previous and current BG values, computes the drop, and returns the next IM dose with the matched scale tier surfaced in the result panel.

## What happens at BG endpoints

Two BG endpoints need careful handling that the simple drop-table doesn't capture on its own:

**Current BG approaches the target band (< 250 mg/dL but ≥ 100 mg/dL):**
The patient is moving from "DKA acute" to "DKA resolving." Continue insulin to clear ketones, but add 2.5% dextrose to the IV fluids to prevent BG from falling into hypoglycemia while insulin is still doing its job. Step to 5% dextrose once BG drops below 150 mg/dL. The InfusionFox result panel surfaces this transition as a note when current BG is between 100 and 250.

**Current BG falls below 100 mg/dL:**
Stop insulin. Continue 5% dextrose fluids. Re-check BG and resume insulin only when BG returns to > 100 mg/dL. The InfusionFox result panel surfaces this as a STOP warning when current BG is below 100.

The sliding scale is built around an actively-falling BG. Not every cycle will produce a decline, if BG rises despite ongoing insulin, something else is going on (infection or stressor, missed dose, mixing error, electrolyte disturbance suppressing insulin action). The InfusionFox calculator handles this by warning when BG has risen rather than fallen, and recommending the maximum 0.2 U/kg dose while the underlying cause is investigated.

## Use regular crystalline insulin only

The same restriction applies as for IV CRI: regular crystalline insulin (Humulin R, Novolin R) only. Lispro and aspart have been investigated but aren't yet standard. NPH, glargine, detemir, and degludec are wrong pharmacokinetically, they don't fit the hourly sliding-scale model.

## Subcutaneous is not appropriate

**SC insulin is not appropriate in dehydrated DKA patients.** Peripheral perfusion is poor, SC absorption is unreliable, and the patient may receive an unpredictable bolus when perfusion improves. Use IM (or IV CRI) until the patient is rehydrated, eating, and ready to transition to long-acting maintenance insulin.

## Volumes are small — use insulin syringes

Stock regular insulin is U-100 (100 U/mL). Doses are small:

- A 20 kg dog at 0.05 U/kg is 1 U = 0.01 mL of U-100
- A 4 kg cat at 0.05 U/kg is 0.2 U = 0.002 mL

These volumes are below the accuracy threshold of standard 1 mL or 3 mL syringes. Use a U-100 insulin syringe, which is calibrated in U directly so the math doesn't matter, you draw to the unit mark.

## Electrolytes and concurrent disease

The same considerations apply as for IV CRI insulin:

- **Hypokalemia** is the most common and dangerous derangement during DKA therapy. Insulin shifts K intracellularly. Check serum K every 4–6 hours; supplement per published sliding scales (see /hypokalemia). The 0.5 mEq/kg/hr ceiling is a hard limit.
- **Hypophosphatemia** affects roughly half of dogs after therapy starts. Severe hypophosphatemia causes hemolysis. Supplement KPhos at 0.03–0.12 mmol/kg/hr IV; subtract its K contribution from total K supplementation.
- **Hypomagnesemia**: supplement MgSO4 at 0.25–1 mEq/kg/day if documented.
- **Concurrent disease** drives most DKA episodes. Identify and treat the precipitating illness in parallel with the metabolic resuscitation.

## When IM is failing

If multiple sequential cycles fail to drop BG into the target band, particularly the case when starting at 0.2 U/kg and not seeing any decline, reassess before just continuing to push. Common causes:

- **Inadequate hydration**: perfusion to muscle is still poor and IM absorption is erratic. Check hydration status; the patient may need additional fluid resuscitation before insulin will work.
- **Electrolyte derangement**: severe hypokalemia or hypophosphatemia can blunt insulin action; correct these.
- **Concurrent infection or stress**: an unaddressed precipitating illness keeps generating counterregulatory hormones. Look for sources.
- **Insulin product**: make sure regular crystalline insulin is being used; long-acting forms won't work hourly.
- **Mixing error or expired product**

If IM continues to fail despite addressing these, **switch to IV CRI** for finer titration. The IV CRI's smoother pharmacokinetics often resolve cases that the intermittent protocol can't.

## Monitoring

Same as IV CRI:

- Blood glucose every 1 hour through the protocol
- Serum electrolytes every 4–6 hours initially; phosphorus and magnesium 1–2 times daily
- Acid-base / venous pH every 4–6 hours initially
- Urine ketones (or β-hydroxybutyrate by point-of-care meter where available)
- Hydration status and intravascular volume every 2–6 hours
- ECG continuously in patients with severe dyskalemia
- CBC and biochemistry daily

Continuous interstitial glucose monitors (eg, FreeStyle Libre on the dorsal cervical region in cats, lateral thorax in dogs) are an accurate alternative to repeat capillary glucose checks in DKA, but in the hypoglycemic range and in the setting of dehydration, accuracy degrades. **Confirm any unexpected reading with a blood glucose measurement** before acting on it.

## Long-term transition

Continue intermittent IM insulin (or transition to IV CRI if appropriate) until the patient is reliably eating, drinking, hydrated, and no longer ketotic. Then transition to twice-daily SC administration of an intermediate or long-acting insulin (NPH or lente in dogs; glargine, detemir, or PZI in cats), along with the dietary transition (high-fiber for dogs, high-protein/low-carbohydrate for cats). The transition usually overlaps the first SC dose with one or two more IM doses to bridge as the longer-acting insulin reaches steady state.

## Sources

- Hoehne SN. Diabetic Ketoacidosis. In: Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 3rd ed. Elsevier; 2023. Chapter 73 (pp. 432–435).
- Macintire DK. Treatment of diabetic ketoacidosis with continuous low-dose intravenous insulin infusion. (Cited in Hoehne Ch. 73 as the source of the IM sliding scale.)
