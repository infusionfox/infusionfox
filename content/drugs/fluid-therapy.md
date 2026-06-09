# Clinical background

Adequate fluid therapy is the foundation of resuscitating any dehydrated patient. It is also frequently underestimated in scope: the fluid plan combines four components (shock bolus, rehydration deficit, maintenance, ongoing losses), runs in two distinct phases (active rehydration, then post-rehydration maintenance), and has to be reassessed continuously as the patient changes. The four-component framework is most commonly cited in the DKA literature but applies to any cause of dehydration.

## The four components

A complete fluid plan accounts for four distinct things:

1. **Shock bolus**, only if the patient is intravascularly volume-depleted at presentation. Aggressive, rapid, time-limited.
2. **Rehydration deficit**, the existing interstitial dehydration. Replaced over hours.
3. **Maintenance**, what the patient's normal turnover requires. Continuous.
4. **Ongoing losses**, vomiting, polyuria, diarrhea, third-spacing. Replaced as they occur.

These don't all run simultaneously. Shock bolus is its own discrete phase. Rehydration deficit, maintenance, and ongoing losses run together during the active-rehydration phase. After the rehydration window completes, only maintenance and ongoing losses continue.

## Phase 0 — Shock bolus (if hypovolemic at presentation)

For the volume-depleted patient: 10–30 mL/kg isotonic crystalloid IV, reassessing after each increment, up to a ceiling of **90 mL/kg in dogs or 60 mL/kg in cats**.

The "reassess after each" piece matters. Most patients respond well before the ceiling, heart rate normalizes, mucous membrane color and CRT improve, mentation lifts, blood pressure rises. Continuing to push beyond clinical resolution risks fluid overload. The ceiling is the maximum across the entire shock-resuscitation phase, not a target.

Shock bolus is delivered **before** the rehydration + maintenance rate begins, not added to it. Once the patient is hemodynamically stable, switch to the active-phase combined rate (Phase 1 below).

## Phase 1 — Active rehydration

Three components run simultaneously through one IV line:

**Rehydration deficit replacement.** The math is straightforward:

$$\text{deficit (mL)} = \text{weight (kg)} \times \%\text{ dehydration} \times 10$$

Replaced over **4–24 hours**. Shorter windows (4–6 hr) for severely dehydrated patients with intact cardiac and renal function. Longer windows (12–24 hr) for cardiac, renal, or geriatric patients where rapid fluid loading is a risk. The most common GP choice is 12 hours.

**Maintenance.** 2–4 mL/kg/hr, the older ml/kg/hr maintenance convention. The allometric formula (132 × kg^0.75) is more accurate across body sizes but the simpler convention is what most institutional protocols use and what this calculator references. Default 3 mL/kg/hr (mid-range). Lower (2) for cardiac/renal limitations; higher (4) for active hypermetabolic states.

**Ongoing losses.** Vomiting, osmotic polyuria, diarrhea. Easily underestimated. A 20 kg dog with active vomiting and severe glucosuria can lose 50–100 mL/hr beyond what physical-exam dehydration captures. Re-estimate hourly and adjust.

The combined rate runs for the full rehydration window. **Reassess perfusion and hydration every 2–6 hours** and watch for over-rehydration: chemosis, respiratory crackles, peripheral edema, weight gain >10% from baseline. If any appear, reduce the rate, don't stop fluids abruptly.

## Phase 2 — Post-rehydration

After the rehydration window completes, **reduce** to maintenance + ongoing losses. The deficit is gone but the patient often has continued losses (polyuria, anorexia, vomiting) that need replacement until they're eating, drinking, hydrated, and clinically resolved, typically another 24–48 hours.

This is also when many patients have weaning hiccups. A patient who looks rehydrated and is starting to eat may have a rebound of vomiting or polyuria as fluid administration drops; raising ongoing-losses estimates and re-checking PCV/TP catches this.

## Choice of fluid

For most dehydration scenarios, an isotonic replacement crystalloid is the right starting point. The two main choices:

**Buffered isotonic crystalloid (LRS, Plasma-Lyte 148, Normosol-R)**, preferred for most non-emergent rehydration. Advantages:

- Faster correction of metabolic acidosis (bicarbonate precursors lactate, acetate, gluconate are converted to bicarbonate by the liver)
- Reduced hyperchloremia compared to 0.9% NaCl
- Decreased risk of acute kidney injury in critically ill patients (best-documented in human ICU literature)
- Small K contribution (LRS 4 mEq/L, Plasma-Lyte 5 mEq/L) blunts the post-insulin K decline in DKA

**0.9% NaCl**, preferred when:

- Severe hyponatremia (Na < 120 mEq/L) needs aggressive correction
- Severe hypochloremia
- Hypercalcemia (LRS contains calcium)
- Concurrent severe hyperkalemia (avoid the small K load from buffered solutions)
- Brain injury where lactate-induced cerebral edema is a theoretical concern (controversial)

In day-to-day practice, **default to a buffered crystalloid unless one of the specific contraindications above applies.**

## Dehydration estimation

Physical-exam dehydration assessment is more reliable than most clinicians realize, but the bands are wider than they look. The standard sliding scale:

- **< 5%**: not detectable on physical exam (subclinical). History of fluid loss but normal exam.
- **5–6%**: dry/tacky mucous membranes; mild loss of skin elasticity.
- **6–8%**: definite skin tenting; tacky-to-dry MM; eyes slightly sunken; CRT may be slightly prolonged.
- **8–10%**: persistent skin tent; dry MM; sunken eyes; weak pulses; cool extremities.
- **10–12%**: severe skin tent that does not return; cold extremities; weak or absent pulses; signs of impending shock.
- **>12%**: moribund. Severe shock. Immediate volume resuscitation is lifesaving.

Sources of error: skin tenting is unreliable in obese, cachectic, or elderly patients where skin elasticity is independently abnormal. PCV and total protein, when interpreted alongside the exam, can sharpen the estimate, both rise with dehydration. A patient whose exam suggests 8% dehydration but whose PCV/TP is normal is probably less dehydrated than the exam suggests; the converse is also true.

## Using this calculator in DKA management

When using this fluid plan for DKA specifically, two interactions matter that don't apply to general dehydration:

**Insulin runs through a separate line.** This calculator covers the resuscitation/rehydration/maintenance line only. Insulin is delivered via the IV CRI protocol (see /insulin-cri-dka) or intermittent IM (see /insulin-im-dka).

**The fluid composition steps with BG.** When an insulin CRI is also running, the **fluid composition** of this line steps with the patient's current blood glucose:

- BG > 250 → 0.9% NaCl alone (or LRS / Plasma-Lyte)
- BG 200–250 → add 2.5% dextrose
- BG 150–199 → continue 2.5% dextrose
- BG 100–149 → step to 5% dextrose
- BG < 100 → 5% dextrose, stop insulin

The **rate** calculated by this calculator does *not* change with BG, only the composition does. The sliding scale is about choreographing insulin delivery and dextrose support; it doesn't replace the rehydration math.

For the full DKA workflow, see the [DKA management hub](/dka).

## Electrolyte monitoring

Hypokalemia, hypophosphatemia, and hypomagnesemia commonly worsen as fluid therapy progresses, particularly in DKA where insulin shifts these intracellularly. Standard supplementation:

- **Hypokalemia.** KCl CRI per published sliding scale (see /hypokalemia). Hard ceiling 0.5 mEq/kg/hr without continuous ECG.
- **Hypophosphatemia.** KPhos at 0.03–0.12 mmol/kg/hr IV (see /hypophosphatemia). Subtract its K contribution from total K supplementation.
- **Hypomagnesemia.** MgSO4 at 0.25–1 mEq/kg/day if documented (see /hypomagnesemia).

Check serum K every 4–6 hours initially; phosphorus and magnesium 1–2 times daily.

## Monitoring during fluid therapy

- Volume and intravascular status every 2–6 hours
- Hydration assessment every 2–6 hours (skin turgor, MM, eye position, body weight)
- Body weight every 4–8 hours (a sensitive marker of net fluid balance)
- PCV/TP every 12 hours
- Electrolytes every 4–6 hours initially (more frequently in DKA or critically ill patients)
- Urine output where indicated (oliguric AKI, post-obstructive diuresis, etc.)

A patient gaining >10% body weight from baseline is over-rehydrated; reduce the rate. A patient losing weight despite ongoing therapy needs the rate increased or ongoing losses re-estimated.

## When to consider colloid support

Most patients respond well to crystalloid therapy alone. Consider colloid support (hetastarch, fresh frozen plasma, packed cells) if:

- Severe hypoalbuminemia (<2.0 g/dL) limiting interstitial-to-vascular fluid shift
- Persistent volume deficit despite adequate crystalloid resuscitation
- Concurrent severe protein-losing condition (protein-losing nephropathy/enteropathy, severe pancreatitis with peritonitis)
- Need for oxygen-carrying capacity replacement (hemorrhagic shock, packed cells)

Hetastarch carries kidney-injury risk in critically ill patients (well-documented in human sepsis literature, less clear in veterinary). Use cautiously and monitor renal function.

## When fluid therapy isn't working

A few common reasons:

- **Underestimated dehydration.** PCV/TP didn't budge after 12 hours of rehydration → reassess and increase the rate or extend the window.
- **Underestimated ongoing losses.** Vomiting hasn't stopped; osmotic polyuria continues until BG normalizes. The ongoing-losses input may need to be doubled.
- **Concurrent disease driving the picture.** Sepsis, pancreatitis, hepatic disease, and significant hypoalbuminemia can produce a fluid picture that won't respond to standard rehydration until the underlying problem is addressed.
- **Cardiac or renal limitation.** A patient with concurrent CHF or oliguric AKI can't tolerate the standard rate; longer rehydration windows and lower maintenance factors may be necessary.
- **Inadequate K replacement.** Severe hypokalemia worsens GI ileus and impairs the kidneys' ability to concentrate urine, propagating the fluid problem.

## Sources

- Hoehne SN. Diabetic Ketoacidosis. In: Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 3rd ed. Elsevier; 2023. Chapter 73, Box 73.1 (the source of the four-component fluid framework used here).
- DiBartola SP, ed. *Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice*. 4th ed. Elsevier; 2012. (Standard reference for dehydration physical-exam bands and the rehydration deficit formula.)
