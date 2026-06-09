# Clinical background

The conventional blood gas interpretation taught at every level of training is the Henderson-Hasselbalch / bicarbonate-centric view: identify the primary disturbance from pH, PCO2, and HCO3; check whether the observed compensation matches the expected; compute the anion gap if Na and Cl are available. It works well in patients who match the underlying assumption: normal albumin, normal phosphate. In the average ICU patient, that assumption is wrong.

The Stewart strong-ion approach, originally published by Peter Stewart in 1981–1983 and adapted for clinical bedside use by Constable, Fencl, and others, takes a fundamentally different view of the chemistry. The physical determinants of pH in plasma are three independent variables: the partial pressure of CO2, the **strong ion difference** (SID, the algebraic sum of fully dissociated electrolytes), and the **total weak acids** (Atot, primarily albumin and phosphate). HCO3 is a **dependent** variable that follows from those three. This is not a philosophical dispute; it is what the chemistry actually does, and it has practical consequences whenever Atot deviates from normal, which is to say, almost every sick patient in your ICU.

## What this calculator does

It implements the simplified Fencl-Stewart decomposition described by Hopper and Haskins in their 2008 JVECC review, the canonical small-animal critical care reference for this method. The standardized base excess from your blood gas analyzer is partitioned into six additive contributions:

| Component | Formula | What it identifies |
|---|---|---|
| **Free water (Na)** | 0.3 × (Na − Na_normal) | Dilutional or contraction effect |
| **Chloride** | Cl_normal − (Cl × Na_normal / Na) | Hyperchloremic acidosis or hypochloremic alkalosis, corrected for water shifts |
| **Albumin** | 3.4 × (Alb_normal − Alb) | Hypoalbuminemic alkalinizing effect (or hyperalbuminemic acidifying) |
| **Phosphate** | 0.58 × (Phos_normal − Phos) | Small contribution; meaningful in profound hypophosphatemia or uremia |
| **Lactate** | −1.0 × (Lactate − 1.5) | Strong-anion contribution from elevated lactate |
| **Unmeasured anions** | BE_total − Σ(measured) | The residual — ketones, uremic anions, exogenous toxins |

The six components sum to the patient's total base excess. Each component has a directional sign: positive means alkalinizing, negative means acidifying. In a healthy patient at species-normal values, every component should be near zero.

The clinical payoff is in the partition. A septic dog with albumin of 1.8 g/dL and lactate of 5 mmol/L might present with a conventional anion gap of 18, which on its own would look like a moderate high-AG acidosis explained by the lactate. The Stewart decomposition reveals that hypoalbuminemia is contributing +5.8 mEq/L of alkalinizing effect that is masking ~6 mEq/L of additional unmeasured anion burden beyond the lactate. The "real" anion burden is twice what the conventional AG suggested. That changes the diagnostic differential: you start asking about ketones, uremic acids, or toxins rather than treating lactic acidosis alone.

## The albumin-corrected anion gap (Figge)

The simplest gateway to this physiology is the Figge correction:

$$ \text{AG}_{\text{corrected}} = \text{AG}_{\text{measured}} + 2.5 \times (4.0 - \text{Albumin}_{g/dL}) $$

Albumin contributes ~2.5 mEq/L to the conventional anion gap for every 1 g/dL it sits in plasma. When albumin drops from 4.0 to 1.5, the conventional AG falls by ~6 mEq/L on that basis alone, turning what would have been a clinically alarming AG of 24 into an apparently reassuring AG of 18. The Figge correction back-fills the missing AG and surfaces the real unmeasured anion burden. It is not the full Stewart decomposition (it doesn't separate chloride effects from unmeasured anions, doesn't account for free water shifts, and lumps lactate in with everything else), but it captures the single largest contributor to AG distortion in the ICU population and it requires only one additional input. This calculator surfaces it on every result, and the companion `/blood-gas` calculator also computes it when albumin is supplied.

## Strong ion gap

The strong ion gap (SIG) is the strong-ion-theory equivalent of the corrected anion gap. SIDa is the apparent strong ion difference, the algebraic sum of measured strong ions:

$$ \text{SID}_a = (\text{Na} + \text{K}) - (\text{Cl} + \text{Lactate}) $$

SIDe is the effective strong ion difference, what the same patient would have if there were no unmeasured ions:

$$ \text{SID}_e = \text{HCO}_3 + \text{A}^- $$

where A⁻ is the dissociated weak acids from albumin and phosphate, evaluated at the patient's pH:

$$ \text{A}^- = \text{Alb}_{g/L} \times (0.123 \times \text{pH} - 0.631) + \text{Phos}_{mmol/L} \times (0.309 \times \text{pH} - 0.469) $$

SIG = SIDa − SIDe. In a healthy patient SIG is near zero (a few mEq/L of background unmeasured ions is normal). More negative SIG indicates unmeasured strong anions; more positive SIG indicates unmeasured cations (rare: toxins, paraproteins, measurement error).

The SIG and BE_unmeasured are different views of the same physiology and should agree in their qualitative reading (both show unmeasured anions when present). The BE_unmeasured framing tends to be more clinically intuitive because it carries the same sign convention as base excess; the SIG framing is more rigorous if you're already fluent in strong-ion theory.

## When to reach for this calculator

You should think Stewart when one or more of the following applies:

- **Hypoalbuminemia** of any meaningful degree. Sepsis, protein-losing enteropathy, protein-losing nephropathy, hepatic failure, severe chronic illness. Anyone with albumin under 2.5 g/dL is going to have a misleading conventional anion gap.
- **The pH is normal but you suspect a mixed disorder.** Stewart will identify a hypoalbuminemic alkalinizing contribution exactly balancing an unmeasured-anion acidifying contribution, neither of which is visible in the bicarbonate view.
- **The conventional anion gap doesn't fit the clinical picture.** A patient with septic shock physiology and AG of 14 is suspicious; either the AG is wrong (hypoalbuminemia) or your clinical impression is.
- **You want to track the source of base deficit over time.** Stewart's component view tells you whether resuscitation is improving the lactate, the chloride, the unmeasured anions, or all of the above; the conventional bicarbonate view tells you only the net effect.

## When the Henderson view is sufficient

Stewart is more rigorous; that doesn't mean it always earns its complexity. If the patient has a normal albumin, normal phosphate, normal Na, and a conventional metabolic disturbance you can categorize and treat, Henderson works fine and is faster. Reach for `/blood-gas` for the bicarbonate-based primary identification, compensation check, and conventional AG. Reach for this calculator when the conventional view is failing to explain what you're seeing.

## Method notes

The coefficients in the BE decomposition are species-averaged from DiBartola Tables 9-1 and 12-1, cross-referenced against the published values in Hopper and Haskins 2008. Lab-specific reference range drift will shift individual components by a few mEq/L without changing the clinical pattern, since what matters is the relative size of each component rather than the absolute value.

The 3.4 coefficient on albumin in g/dL (equivalently 0.34 in g/L) is the most commonly cited simplification; Constable's pH-dependent formulation is more rigorous (`0.123 × pH − 0.631`) but produces nearly identical values across the clinically relevant pH range of 7.2–7.5 and adds calculation complexity that isn't worth the precision gain at the infusionfox.

Magnesium and ionized calcium contributions to SIDa are omitted in this simplified implementation. Their typical magnitudes are small (<2 mEq/L combined) relative to the dominant ions. If you're working a case where Mg or iCa is markedly abnormal (eclamptic patients, parathyroid disease, refractory hypomagnesemia), the simplified SIG will systematically under-report the unmeasured-ion contribution from those species. The BE decomposition is unaffected because it sums to the patient's actual BE.

This is a population-level analytic tool. Individual-patient interpretation requires clinical context: the calculator tells you the algebra; the clinician decides whether the unmeasured-anion residual is ketones, uremic anions, intoxication, or laboratory artifact.

## Sources

- Hopper K, Haskins SC. A case-based review of a simplified quantitative approach to acid-base analysis. J Vet Emerg Crit Care 2008;18:467–476.
- Constable PD. Clinical assessment of acid-base status: comparison of the Henderson-Hasselbalch and strong ion approaches. Vet Clin Pathol 2000;29:115–128.
- Constable PD. A simplified strong ion model for acid-base equilibria: application to horse plasma. J Appl Physiol 1997;83:297–311.
- Stewart PA. Modern quantitative acid-base chemistry. Can J Physiol Pharmacol 1983;61:1444–1461.
- DiBartola SP. Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice, 4th ed. St. Louis: Elsevier Saunders; 2012. Chapters 9–12.
- Figge J, Jabor A, Kazda A, Fencl V. Anion gap and hypoalbuminemia. Crit Care Med 1998;26:1807–1810.
