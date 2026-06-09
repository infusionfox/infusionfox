# Clinical background

Systemic IV lidocaine is a workhorse drug in canine critical care. It provides moderate analgesia with no respiratory depression, attenuates the inflammatory response, has anti-arrhythmic activity, and may improve outcomes in dogs with gastric dilatation-volvulus (GDV) and septic peritonitis. The catch is species: cats are markedly more sensitive to both CNS and cardiodepressant effects, and most clinicians avoid IV lidocaine for analgesia in cats entirely. This calculator is dog-only by design.

## Pharmacology

Class IB sodium-channel-blocking antiarrhythmic with separate analgesic and prokinetic effects:

- **Anti-arrhythmic**: combines with inactive fast sodium channels in ventricular conducting tissue, decreasing automaticity and shortening myocardial cell action potential. Therapeutic plasma concentration 1–6 µg/mL.
- **Analgesic**: multiple mechanisms: reduction of ectopic activity in damaged afferent neurons, action at NMDA receptors, and effects on Na⁺, Ca²⁺, and K⁺ channels at multiple sites in the pain pathway. Provides ≈30% MAC sparing in dogs at therapeutic plasma concentrations.
- **Anti-inflammatory and ROS-scavenging**: relevant in GDV; lidocaine has been shown to inhibit reactive oxygen species formation and lipid peroxidation, which is part of the proposed mechanism for the survival benefit seen in septic peritonitis and possibly GDV.
- **Prokinetic**: equivocal in dogs; does not reliably enhance GI motility despite anecdotal use for postoperative ileus. The prokinetic effect is well-documented in horses and rabbits.

After IV bolus, onset is within 2 minutes and duration 10–20 minutes. With CRI alone (no loading dose), therapeutic concentrations may not be reached for up to an hour. Hepatic metabolism is rapid; clearance falls with hepatic dysfunction, hypoproteinemia, congestive heart failure, and concurrent cimetidine or beta-blocker therapy. Plasma protein binding is variable and concentration-dependent.

## Indications

Primary use cases:

- Adjunctive analgesia under general anesthesia (alone or as part of MLK-type combinations)
- Anti-arrhythmic for ventricular tachyarrhythmias, frequent or polymorphic PVCs, runs, R-on-T phenomena, ventricular tachycardia with hemodynamic compromise
- Adjunctive treatment of GDV, to reduce arrhythmias, mitigate ischemia-reperfusion injury, and possibly reduce risk of acute kidney injury and shorten hospitalization
- Adjunctive treatment of septic peritonitis. Plumb's documents a survival benefit at 50 µg/kg/min in dogs undergoing laparotomy for septic peritonitis
- Postoperative analgesia in dogs (with or without GI surgery), single-drug or as part of an MLK protocol

## Why this calculator is dog-only

Plumb's is explicit on the species concern: cats are more sensitive than dogs to lidocaine's CNS and cardiodepressant effects, and most clinicians avoid IV lidocaine for analgesia in cats, particularly cats with concurrent illness or under general anesthesia. Plumb's adds that lidocaine combined with isoflurane in cats produces *greater* cardiovascular depression than equipotent isoflurane alone, meaning lidocaine added to balanced anesthesia in cats actively worsens hemodynamics rather than helping.

For cat analgesia, fentanyl, methadone, hydromorphone, and buprenorphine (with or without ketamine) are all better-supported choices.

## Dosing (dogs)

The InfusionFox calculator uses a default range of **1.5–3 mg/kg/hr (= 25–50 µg/kg/min)** for analgesic CRIs, which covers Plumb's published lidocaine-alone analgesic CRI and the GDV / septic peritonitis indication. The MLK protocol delivers 50 µg/kg/min, which sits at the upper end of this range.

Plumb's also publishes higher rates, up to 100 µg/kg/min (= 6 mg/kg/hr), in specific surgical-only multi-drug combinations:

- Lidocaine/dexmedetomidine/ketamine: lidocaine 100 µg/kg/min during surgery, then step down to 25 µg/kg/min postoperatively × 4 hours
- Lidocaine/ketamine: 25–100 µg/kg/min range depending on combination

These higher rates are surfaced as caution-band warnings rather than expanding the default range, they apply only to surgical-period combinations with planned postoperative step-down. Sustained single-drug rates above 3 mg/kg/hr substantially raise toxicity risk.

For ventricular arrhythmias, dosing is different from analgesic CRI: bolus 2 mg/kg slow IV, repeated up to 8 mg/kg cumulative; if effective, follow with 25–80 µg/kg/min (= 1.5–4.8 mg/kg/hr) CRI. Use a separate antiarrhythmic-dose protocol, this calculator targets the analgesic indication.

## Loading dose

1–2 mg/kg IV slowly (over 2–4 minutes per Plumb's; rapid bolus risks dose-dependent hypotension). The InfusionFox calculator surfaces this on every result panel.

## Administration

**Use 2% lidocaine WITHOUT epinephrine**, the plain 20 mg/mL formulation. Lidocaine-with-epinephrine is sold for dental and local infiltration; giving it IV would deliver an unintended epinephrine bolus and is a serious medication-error risk. Plumb's labels the epinephrine-containing product as not for IV use.

For accurate small-patient delivery, dilute into 5% dextrose or 0.9% sodium chloride; the MLK protocol's working solution (50 mL of 2% lidocaine into 1 L of compatible fluid → 1 mg/mL) is a useful reference. Lidocaine is compatible with most common crystalloids and many other CRIs; pH dependent, incompatible with ampicillin, cefazolin, diazepam, pantoprazole, pentobarbital, and TMS.

The veterinary-label injection contains propylene glycol, which can cause hypotension on IV bolus, give bolus doses slowly.

## Drug interactions

- **Beta-blockers and cimetidine** reduce lidocaine clearance and increase plasma concentration, dose reduction warranted if these are on board.
- **Ceftiofur** reduces lidocaine protein binding, increasing free fraction and toxicity risk.
- **Phenobarbital and mitotane** decrease lidocaine concentration via enzyme induction.
- **Furosemide**: hypokalemia from concurrent diuresis can blunt the antiarrhythmic effect.
- **α₂ agonists** and **ketamine** may increase ataxia in horses; less of an issue in dogs.

## Adverse effects

Toxicity is concentration-dependent. Plumb's puts the therapeutic plasma window at 1–6 µg/mL; toxicity becomes likely above 8 µg/mL; lethal dose in dogs is estimated at 16–28 mg/kg. Signs in order of typical appearance:

- Drowsiness, depression
- Ataxia, nystagmus
- Muscle tremors and fasciculations
- Nausea, vomiting (the sedation-plus-vomiting combination raises aspiration risk)
- Seizures, often preceded by tremor
- Bradycardia, hypotension
- Circulatory collapse and cardiac arrest at very high concentrations

Patients with hepatic dysfunction, hypoproteinemia, heart failure, and concurrent cimetidine or beta-blocker therapy are at higher risk. Reduce doses 30–50% in patients with significant liver disease.

## Antidote

**IV lipid emulsion 20% can be beneficial for treating lidocaine toxicity.** This is the same antidote used for local-anesthetic systemic toxicity (LAST) in human medicine, the lipid acts as a "lipid sink" that pulls lipophilic drug out of plasma into the emulsion, lowering free concentration. Stop the infusion at the first sign of meaningful toxicity and treat supportively (benzodiazepines for seizures; fluids and vasopressor support if circulatory collapse; lipid emulsion as the specific antidote in severe cases).

## Monitoring

- ECG continuously where available, particularly in arrhythmia indications and during higher-dose combinations
- Blood pressure
- Mentation and neurologic status, sedation or ataxia is often the first warning of toxicity
- Body temperature on prolonged infusions
- For prolonged infusions or higher-risk patients: serum lidocaine concentration if available

## Stepping down

For combined-agent protocols (eg MLK), discontinue lidocaine and ketamine first when stepping down. For single-agent CRI, taper or discontinue based on pain assessment; re-load with 1–2 mg/kg IV bolus if breakthrough pain occurs. With prolonged infusions, lidocaine and metabolites accumulate, dose reduction may be warranted at 24+ hours.

## Sources

- Plumb's Veterinary Drugs, lidocaine (intravenous; systemic) monograph (current edition).
- Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 3rd ed. Elsevier; 2023. Chapter 134, Table 134.1.
