# Clinical background

Ketamine occupies a unique place among anesthetic and analgesic drugs: it is simultaneously a dissociative general anesthetic and a subanesthetic analgesic with strong anti-windup activity. As a CRI, it is used at much lower doses than for induction, providing useful background analgesia, reducing inhalant requirements, and dampening central sensitization in patients with severe acute or chronic pain. The major safety considerations are the unit-confusion risk (mg/kg/hr vs µg/kg/min differ by ≈60×, and Plumb's flags this as a high-alert error) and species-specific cautions in cats.

## Pharmacology

NMDA-receptor antagonist. Ketamine binds the phencyclidine site of the NMDA receptor, reducing receptor activity and the release of glutamate, the main excitatory neurotransmitter at this site. NMDA antagonism is the mechanistic basis for both its dissociative anesthesia at higher doses and its anti-hyperalgesic effect at subanesthetic CRI doses. The drug also has secondary actions at opioid and monoaminergic receptors, which contribute to its analgesic profile.

Cardiovascular effects in healthy patients are dominated by increased sympathetic tone, heart rate, mean arterial pressure, and cardiac output rise. **In sympathetically blocked or catecholamine-depleted patients, the underlying direct effect, negative inotropy, emerges.** This is the basis for cautions in critical illness, advanced heart disease, and patients on high-dose β-blockade.

Respiratory effects are usually mild at CRI doses. Apneustic breathing (rapid breaths followed by breath-holding) can occur. Pharyngeal and laryngeal reflexes are largely preserved, distinct from most other anesthetics, which is why ketamine is sometimes useful when airway reflex preservation matters.

Hepatic metabolism via CYP2B11 in dogs produces norketamine, which retains 10–30% of parent drug activity. Cats handle ketamine almost entirely by direct urinary excretion of unchanged drug, relevant in renal dysfunction.

Schedule III (C-III) controlled substance.

## Indications

Two CRI modes encoded in this calculator:

**Surgical maintenance**, intraoperative analgesia and anti-windup during procedures that involve significant nociceptive input. Range 10–20 µg/kg/min (= 0.6–1.2 mg/kg/hr). Default 10 µg/kg/min. Per Plumb's, precede with a 0.5 mg/kg IV loading dose if anesthesia was induced with a non-ketamine agent. The MLK protocol delivers ketamine at 10 µg/kg/min, matching this surgical maintenance dose.

**Postsurgical / general analgesia**, postoperative wind-down or stand-alone analgesia for severe acute or chronic pain. Range 2–10 µg/kg/min (= 0.12–0.6 mg/kg/hr). Default 2 µg/kg/min for 24 hours. This range absorbs Plumb's "general analgesia" range (0.1–0.6 mg/kg/hr after 0.5 mg/kg IV loading), which overlaps fully with the postsurgical entry.

A third use case, **refractory status epilepticus**, uses a single 5 mg/kg IV bolus per Plumb's, NOT a CRI. That use is out of this calculator's scope; consult Plumb's directly if you're treating status epi with ketamine.

## The unit-confusion problem

Plumb's flags this as a top-level Prescriber Highlight: clinicians must take care not to confuse the two CRI dose units (mg/kg/hr vs µg/kg/min). The two units differ by a factor of ≈60. The same number entered in the wrong unit produces a delivered dose ≈60× higher or lower than intended.

The InfusionFox calculator addresses this two ways: it accepts dose input in either unit (toggle next to the dose field), and it always shows both conventions in the result panel so the clinician can verify both match the protocol they're working from. Look at both numbers before you start the infusion.

## Cat-specific cautions

Ketamine is well-supported in cats, it is FDA-approved for feline anesthesia, has decades of clinical use, and is part of widely-used "kitty magic" combinations. But several cat-specific concerns deserve attention before any feline ketamine CRI:

- **Avoid in cats with hypertrophic cardiomyopathy.** Ketamine raises heart rate, blood pressure, and myocardial oxygen consumption, exactly what the HCM heart cannot tolerate. Anecdotal acute CHF reports exist in cats with mild-to-moderate cardiac disease.
- **Up to 20% of cats given ketamine alone may experience seizures at therapeutic doses.** Diazepam is suggested if treatment is needed; combining ketamine with a benzodiazepine in clinical practice substantially reduces this risk.
- **Self-limiting hyperthermia at higher doses (5–10 mg/kg).** Low-dose acepromazine (0.01–0.02 mg/kg IV) may help.
- **Renal excretion in cats** is essentially the only elimination route, consider dose reduction or alternative agents in renal dysfunction.

## Loading dose

0.5 mg/kg IV per Plumb's, administered when anesthesia was induced with a non-ketamine agent (since ketamine itself can be used for induction and would not need a separate loading dose). The InfusionFox calculator surfaces this on the result panel for surgical maintenance mode.

## Administration

The standard veterinary stock is **100 mg/mL** (10 mL vials). Compatible carriers are sterile water for injection, 5% dextrose, and 0.9% sodium chloride. Compatible in the same syringe with xylazine, fentanyl, hydromorphone, lidocaine, midazolam, and morphine, common in MLK and similar combinations.

**Do not mix ketamine with barbiturates or diazepam in the same syringe**, precipitation occurs. Anecdotal reports of mixing ketamine and diazepam exist, but Plumb's notes there's no published stability documentation. Y-site incompatibilities include ampicillin sodium, dexamethasone sodium phosphate, furosemide, heparin, regular insulin, and sodium bicarbonate.

For very small patients where the calculated pump rate is impractically low (the 100 mg/mL stock at 2 µg/kg/min in a 4 kg cat works out to ≈0.005 mL/min, well below most pump accuracy thresholds), dilute into a small fluid bag for accurate delivery. The InfusionFox result panel surfaces a dilution suggestion when the calculated rate falls below 0.1 mL/hr.

Pain on IM injection is well-documented; have a plan for sedation if injecting an awake fractious patient.

Eyes remain open after ketamine administration, apply ophthalmic lubricant to prevent corneal drying. Minimize handling and noise during recovery to reduce emergence reactions.

## Drug interactions

- **α₂ agonists** (dexmedetomidine, medetomidine, xylazine) reduce ketamine metabolism via CYP2B11 inhibition. Doses are commonly reduced when combined.
- **Barbiturates, benzodiazepines, opioids, halothane**: prolong ketamine recovery; lower doses of each agent are typical in combination.
- **Theophylline / aminophylline** lower seizure threshold (relevant in human data; veterinary significance unclear).
- **Thyroid hormones**: combined with ketamine, may produce hypertension and tachycardia (human data; β-blockers may help if seen).

## Adverse effects

At lower CRI doses, adverse effects are usually minimal. Watch for:

- Tachycardia and hypertension
- Hypersalivation (consider an anticholinergic if interfering with airway management)
- Vocalization, dysphoria
- Erratic or prolonged recovery, particularly with larger cumulative doses
- Myoclonus and tonic-clonic activity. Plumb's notes the manufacturer suggests treating with ultrashort-acting barbiturates or acepromazine if needed
- Seizures (especially in cats given ketamine alone, see above)
- Respiratory depression at higher doses
- Hyperthermia
- Pain on IM injection
- Cortisol elevation, limits the use of cortisol as a pain biomarker

## Overdose

Ketamine has a wide therapeutic index (≈5× that of pentobarbital). Acute overdose presents primarily as respiratory depression, treat with mechanical ventilation rather than analeptics like doxapram. There is no specific reversal agent. In cats, yohimbine combined with 4-aminopyridine has been suggested as a partial antagonist.

## Monitoring

- Anesthetic depth, particularly during surgical-mode CRIs
- Respiratory rate, ETCO₂, SpO₂
- ECG and blood pressure
- Body temperature
- Eye protection (lubricant, towel during field anesthesia)
- For cats receiving ketamine CRI: brief neurologic check at every recheck given the seizure-rate concern

## Recovery and stepping down

For surgical maintenance, step down to the postsurgical rate (2 µg/kg/min) at the conclusion of surgery and continue for up to 24 hours per Silverstein. Recovery quality benefits from a quiet, dim environment with minimal handling, emergence reactions are common with abrupt cessation in a stimulating environment.

For combined protocols (MLK, lidocaine/ketamine, etc.), discontinue ketamine and lidocaine before opioids when stepping down, this preserves the opioid analgesia bridge while removing the anti-windup component first.

## Sources

- Plumb's Veterinary Drugs, ketamine monograph (current edition).
- Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 3rd ed. Elsevier; 2023. Chapter 134, Table 134.1.
