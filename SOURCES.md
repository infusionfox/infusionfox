# InfusionFox · clinical sources

This document tracks the source-of-truth reference for every clinical value
(dose ranges, thresholds, formulas, recommendations) in InfusionFox. Every
calculator's clinical content traces to a citable source listed here.

## Why this file exists

1. **For peer reviewers.** A reviewer can verify any number in the app by
   checking the cited page directly.
2. **For RACE accreditation later.** RACE requires documentation of source
   materials for educational content. Maintaining this file from day one is
   easier than reconstructing it later.
3. **For future contributors.** A new contributor can understand what
   reference governs a given calculator without spelunking through code.
4. **For legal defensibility.** Clean attribution of clinical content to
   peer-reviewed/textbook sources is the standard for clinical decision
   support tools.
5. **For audit trail.** When a calculator is updated based on a newer
   edition or new evidence, the change is traceable.

## Editorial standards

- **Every numeric threshold has a source.** Dose ranges, hard_max ceilings,
  correction rates, formulas, and recheck intervals.
- **Recommendation prose is in our own words.** We never lift verbatim text
  from cited sources. Facts are not copyrightable; expression is.
- **Edition and page numbers required.** "Plumb's" alone is insufficient.
  "Plumb's 10th ed, p. 847" is the standard.
- **Source updates trigger calculator updates.** When a newer edition of a
  cited source publishes meaningfully different values, the calculator and
  this file are updated together.
- **Pre-launch peer review required for every clinical calculator.** No
  calculator goes to a paying user without independent review by a
  veterinarian familiar with the source material.

## Canonical sources by category

| Category | Canonical reference |
|---|---|
| **Vasopressors / Inotropes** | Plumb's Veterinary Drug Handbook (current edition); Hart & Silverstein in Silverstein & Hopper *Small Animal Critical Care Medicine* 3rd ed Ch. 147 |
| **Analgesia (CRI)** | Plumb's; Grimm KA et al., *Veterinary Anesthesia and Analgesia* (Lumb & Jones); Silverstein & Hopper Ch. 134 |
| **Anesthesia / Sedation** | Plumb's; Grimm KA et al., *Veterinary Anesthesia and Analgesia* (Lumb & Jones), 6th ed |
| **Electrolytes / Acid-Base** | DiBartola SP (ed), *Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice*, 4th ed (2012) |
| **Endocrinology** | ACVIM consensus statements; Feldman EC, Nelson RW, Reusch CE, Scott-Moncrieff JC, *Canine and Feline Endocrinology*, 4th ed; AAHA 2023 Selected Endocrinopathies Guidelines |
| **Critical Care** | Silverstein DC, Hopper K (eds), *Small Animal Critical Care Medicine*, 3rd ed (2023) |
| **Pharmacology / Drug references** | Plumb's Veterinary Drugs, current edition; Lumb and Jones', 6th ed |
| **Toxicology** | Peterson ME, Talcott PA (eds), *Small Animal Toxicology*, current edition |
| **Nutrition** | Ettinger SJ, Feldman EC, Côté E (eds), *Textbook of Veterinary Internal Medicine*, 9th ed; National Research Council, *Nutrient Requirements of Dogs and Cats*, 2006 |
| **Resuscitation / CPR** | RECOVER 2024 evidence-and-knowledge-gap analyses (BLS, ALS, monitoring, post-arrest, prevention) |
| **Status epilepticus / Epilepsy** | Bhatti SFM et al., *International Veterinary Epilepsy Task Force* consensus 2015; Charalambous M et al. RCTs 2017/2019 (intranasal midazolam); Hardy BT et al. 2012 (IV levetiracetam) |
| **Transfusion medicine** | Davidow B, *Vet Clin North Am Small Anim Pract* 2013; Plumb's blood products; ACVIM IMHA Consensus 2019 |

When a more specific source applies (primary research paper, consensus
statement supersedes the textbook), it's listed at the calculator level
below.

---

## Drug calculators (single-drug CRI)

| Calculator | Source |
|---|---|
| **Norepinephrine** | (Primary) Plumb's, norepinephrine monograph. (Secondary) Hart & Silverstein in Silverstein & Hopper *Small Animal Critical Care Medicine* 3rd ed. Ch. 147, Table 147.1, pp. 855–859. Dose range 0.05–2 µg/kg/min both species; first-choice for septic shock; MAP ≥ 65 target. |
| **Epinephrine** | (Primary) Plumb's, epinephrine monograph (anesthesia hypotension and anaphylaxis-with-shock CRI ranges). (Secondary) Silverstein 147.1. Persistent warnings encode the 1 mg/mL vs 0.1 mg/mL concentration confusion risk and EPINEPHrine vs ePHEDrine confusion risk. |
| **Dobutamine** | (Primary) Plumb's, dobutamine monograph. (Secondary) Silverstein 147.1. Dog 1–20 µg/kg/min (caution above 10); cat 1–20 with caution above 5 per Plumb's seizure association. |
| **Dopamine (preparation worksheet)** | (Primary) Plumb's, dopamine monograph. (Secondary) Lumb and Jones', 6th ed Ch. 21 (cat HCM/PVC concern citing Wiese et al). (Secondary) Silverstein 147.1. Implements Plumb's 6×kg preparation method. Pump rate (mL/hr) = dose (µg/kg/min) by construction. |
| **Phenylephrine** | (Primary) Plumb's, phenylephrine monograph. (Secondary) Hart & Silverstein in Silverstein & Hopper 3rd ed Ch. 147. Pure α-agonist; vasoconstriction without inotropy. CRI range 0.5–3 µg/kg/min for second-line vasopressor or HCM/obstructive contexts where β-agonism is unwanted. Reflex bradycardia warning surfaced. |
| **Vasopressin** | Plumb's, vasopressin monograph. V1-receptor vasoconstrictor; non-catecholamine pressor preserving function in acidotic states where catecholamine response degrades. CRI 0.5–4 mU/kg/min. Persistent warning: not a substitute for volume resuscitation; extravasation risk. |
| **Nitroprusside** | (Primary) Plumb's, nitroprusside sodium monograph (D5W-only diluent, light protection, color-change discard criteria). (Secondary) Côté et al. Management of congestive heart failure. In Ettinger 8th ed. Confirms bridge use in stage D refractory CHF with monitoring and duration limits. Persistent warning encodes light-sensitivity, cyanide-toxicity risk, and infusion-duration cap. |
| **Esmolol** | (Primary) Plumb's, esmolol HCl monograph. (Secondary) Côté E, MacDonald KA, Meurs KM, Sleeper MM, eds. *Feline Cardiology*. Wiley-Blackwell; 2011. Supports HCM cat use for rate control; surfaces bronchospasm concern at higher doses. Ultra-short-acting β1-selective blocker; loading + maintenance CRI. |
| **Diltiazem CRI** | (Primary) Plumb's, diltiazem HCl monograph (loading + CRI; β-blocker interaction; AV-block grades; WPW caution). (Secondary) Côté et al. *Feline Cardiology* 2011. Supports HCM cat rate control with the LVOT-obstruction caveat (avoid in obstructive disease; useful in non-obstructive HCM with rate-control needs). |
| **Lidocaine CRI · Antiarrhythmic** | (Primary) Plumb's, lidocaine HCl (systemic) monograph, separated antiarrhythmic vs analgesic indications. (Secondary) Côté et al. *Feline Cardiology* 2011 documents cat-specific lidocaine sensitivity and alternatives (sotalol, magnesium) most feline cardiologists prefer. Species-asymmetric clearance; cat sensitivity emphasized. Sibling calculator to **Lidocaine CRI** (analgesia, dog-only). |
| **Furosemide CRI** | (Primary) Plumb's, furosemide monograph (CHF loading + maintenance CRI ranges). (Foundational) Adin DB, Taylor AW, Hill RC, et al. Intermittent bolus injection versus continuous infusion of furosemide in normal adult Greyhound dogs. *J Vet Intern Med* 2003;17(5):632–636. Demonstrates the natriuretic-efficiency advantage of CRI over equivalent intermittent dosing. (Secondary) Côté et al., Ettinger 8th ed Ch. on CHF. Stage D refractory CHF with detailed monitoring. |
| **Methocarbamol** | (Primary) Plumb's, methocarbamol monograph. (Secondary) Hopper K, Mehl M. Toxicology emergencies. In: Silverstein & Hopper 3rd ed. Supports CRI use for refractory tetanus and permethrin toxicity. Three indication-specific loading doses encoded (mild/moderate/severe); CRI 5–15 mg/kg/hr; daily ceiling enforced. |
| **Metoclopramide** | Plumb DC. Plumb's Veterinary Drugs, metoclopramide monograph (current edition). Standard antiemetic / prokinetic CRI 0.04–0.09 mg/kg/hr. Laryngeal paralysis intraoperative protocol (1 mg/kg IV loading + 1 mg/kg/hr intraop, 0.083 mg/kg/hr postop, 24-hr total) included as a separate indication. |
| **Fentanyl** | Plumb's, fentanyl monograph. Dose ranges, clinical notes, dilution presets, stock vial concentration. |
| **Hydromorphone CRI** | Plumb's, hydromorphone monograph. Dose 0.01–0.05 mg/kg/hr CRI for postoperative or breakthrough analgesia. Both species. |
| **Methadone** | Plumb's, methadone monograph. NMDA antagonism distinguishes from pure mu-agonists; useful in chronic/neuropathic pain contexts. Dose 0.1–0.5 mg/kg IV/IM/SC q4–6h. |
| **Lidocaine CRI** | (Primary) Plumb's, lidocaine (intravenous; systemic) monograph. (Secondary) Silverstein Ch. 134, Table 134.1, p. 789. Dog-only single-drug CRI; default range 1.5–3 mg/kg/hr (= 25–50 µg/kg/min). Plumb's-cited cat avoidance for anesthetic/analgesic IV use. IV lipid emulsion 20% antidote referenced. |
| **Ketamine CRI** | (Primary) Plumb's, ketamine monograph (adjunctive analgesia section). (Secondary) Silverstein Ch. 134, Table 134.1. Both species. Two indication modes: surgical (10–20 µg/kg/min) and postsurgical/general analgesia (2–10 µg/kg/min × 24 hr). Cat persistent warnings (HCM avoidance, 20% seizure rate, hyperthermia, renal excretion). |
| **Propofol (TIVA / Status epilepticus)** | Plumb's, propofol monograph. Two indication modes: TIVA maintenance (dog-only, 0.1–0.5 mg/kg/min IV CRI) and refractory status epilepticus (dogs and cats, 0.1–0.25 mg/kg/min preceded by 2–8 mg/kg IV bolus; max ≈48 hr). Cat TIVA blocked due to prolonged-recovery and Heinz-body anemia concerns. |
| **Alfaxalone** | Plumb's, alfaxalone monograph. IV induction dose, maintenance bolus (per 10 min), and CRI pump rate for dogs and cats. Premedicated vs unpremedicated ranges. No analgesia; analgesic coverage required. DEA Schedule IV. |

## Multi-drug analgesia / sedation protocols

| Calculator | Source |
|---|---|
| **MLK infusion (Morphine-Lidocaine-Ketamine)** | Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 3rd ed. Elsevier; 2023. Ch. 134, Table 134.1, p. 789. Reproduces Silverstein's published recipe (10 mg morphine + 150 mg 2% lidocaine + 30 mg ketamine in 500 mL LRS at 10 mL/kg/hr) verbatim; math reproduces 3.3 / 50 / 10 µg/kg/min component doses. Dog-only. |
| **Cornell Oncology KL infusion** | (Primary) Iocolano KE, Looney A, Balkman CE, Hume KR, Boesch JM, Sylvester SR. Retrospective evaluation of outpatient intravenous ketamine-lidocaine infusions for the palliation of cancer pain in dogs and cats. *J Am Vet Med Assoc*. 2025;263(4):499–506. (Original) Looney A, Cornell University CVM 2012 worksheet. Both species. Bag-prep recipe + delivered-rate verification against three efficacy thresholds from the 2025 paper. |
| **Kitty Magic (DKT)** | Plumb's tables, dexmedetomidine-ketamine-opioid combination protocols for cats. Equal volumes IM with stock concentration constraints. Atipamezole reversal at equal volume to dexmedetomidine. Cats only. |

## Sliding-scale and bespoke calculators

| Calculator | Source |
|---|---|
| **Hypernatremia (water deficit)** | DiBartola SP (ed). *Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice*. 4th ed. St. Louis, MO: Elsevier Saunders; 2012. Ch. 3 (Disorders of Sodium and Water: Hypernatremia and Hyponatremia), pp. 60–61. Acute/chronic correction-rate selector. |
| **Hypokalemia (KCl supplementation)** | DiBartola, 4th ed, Ch. 5 (Disorders of Potassium: Hypokalemia and Hyperkalemia), pp. 107–108, Table 5-2. (Originally Greene RW, Scott RC 1975.) Hard 0.5 mEq/kg/hr ceiling enforced; DKA exception noted. |
| **Hypophosphatemia · KPhos CRI** | (Sliding-scale rate range) Hoehne SN in Silverstein & Hopper 3rd ed Ch. 73, Box 73.1 (KPhos 0.03–0.12 mmol/kg/hr IV). (Disorders of phosphorus) DiBartola 4th ed Ch. 7. 5-tier sliding scale; concurrent KCl K-load interaction surfaced. |
| **Hypomagnesemia · MgSO4 CRI** | (Sliding-scale rate range) Hoehne SN in Silverstein & Hopper 3rd ed Ch. 73, Box 73.1 (MgSO4 0.25–1 mEq/kg/day IV). (Disorders of magnesium) DiBartola 4th ed Ch. 8. 4-tier sliding scale; 50% and 25% stock toggle. |
| **Calcium gluconate (hyperK membrane stabilization)** | Cooper ES. Urethral Obstruction. In Silverstein & Hopper 3rd ed Ch. 122 (0.5–1.5 mL/kg of 10% calcium gluconate IV slowly over 10–20 min with continuous ECG). DiBartola 4th ed Ch. 5. 10% calcium gluconate (100 mg/mL salt = 9.3 mg/mL elemental Ca = 0.465 mEq/mL Ca²⁺). |
| **Insulin + dextrose (hyperK shifting)** | Cooper ES in Silverstein & Hopper 3rd ed Ch. 122 (regular insulin 0.25–0.5 U/kg IV with concurrent dextrose 1–2 g per unit insulin, followed by 2.5–5% dextrose CRI for 4–6 hr). DiBartola 4th ed Ch. 5. |
| **Insulin CRI · DKA** | Hoehne SN in Silverstein & Hopper 3rd ed Ch. 73, pp. 432–435. Table 73.1 (CRI sliding scale). Box 73.1 (treatment overview). 5-tier sliding scale by BG; cat dose option toggle (default 2.2, conservative 1.1). |
| **Insulin IM intermittent · DKA** | Hoehne SN in Silverstein & Hopper 3rd ed Ch. 73, p. 434. IM protocol from Macintire DK, *Vet Clin North Am Small Anim Pract*. 1995;25(3):639–650. Two-mode workflow (loading + subsequent BG-drop-driven titration). |
| **Fluid therapy (general)** | Hoehne SN in Silverstein & Hopper 3rd ed Ch. 73, Box 73.1 (recommended treatment and monitoring schedule for DKA; math is generalizable). DiBartola dehydration physical-exam bands. Combiner for shock bolus, rehydration deficit, maintenance, and ongoing losses. |
| **Transfusion (pRBC / whole blood / FFP)** | Davidow B. Transfusion medicine in small animals. *Vet Clin North Am Small Anim Pract* 2013;43:735–756. Plumb's blood products. ACVIM IMHA Consensus 2019 (transfusion section). Volume formula: (PCV_target − PCV_current) / PCV_donor × patient blood volume. Blood volume 90 mL/kg dog, 60 mL/kg cat. Donor PCV defaults pRBC 80%, whole blood 60%. FFP 10–20 mL/kg. Slow-trial-then-main rate scheme; 4-hr completion limit. |
| **Blood gas interpretation** | (Primary) DiBartola SP (ed). *Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice*. 4th ed. St. Louis, MO: Elsevier Saunders; 2012. Ch. 9 (Introduction to Acid-Base Disorders), pp. 231–252, reference ranges (Table 9-1, p. 241) and anion-gap interpretation (pp. 244–245). Ch. 10–13 (the four canonical disturbances). Ch. 12 (Metabolic Acidosis), Table 12-2 p. 304, compensation rules of thumb (originally de Morais HSA, DiBartola SP. A clinical approach to acid-base disorders. *Vet Clin North Am Small Anim Pract* 1991;21:613–629), and the cat-specific caveat against extrapolating dog formulas to cats with metabolic acidosis. (Freely-available secondary) `# TODO`: no peer-reviewed open-access corroborating source identified at time of publication; de Morais & DiBartola 1991 JVECC is paywalled. |
| **Blood gas · Stewart strong-ion** | (Primary) Hopper K, Haskins SC. A case-based review of a simplified quantitative approach to acid-base analysis. *J Vet Emerg Crit Care* 2008;18:467–476. Canonical vet ECC reference for the simplified Fencl-Stewart decomposition; formula coefficients used in code come from this paper. (Foundational) Constable PD. Clinical assessment of acid-base status: comparison of the Henderson-Hasselbalch and strong ion approaches. *Vet Clin Pathol* 2000;29:115–128. (A- formula.) (Original theory) Stewart PA. Modern quantitative acid-base chemistry. *Can J Physiol Pharmacol* 1983;61:1444–1461. (Species ranges) DiBartola 4th ed Ch. 9–12. Decomposes standardized base excess into free water, chloride, albumin, phosphate, lactate, and unmeasured components. Strong ion gap (SIG) and albumin-corrected anion gap surfaced for the hypoalbuminemic patient. |
| **Tube feeding (NG / esophagostomy ramp)** | (Primary) Chan DL. Enteral nutrition. In: Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 4th ed. St. Louis, MO: Elsevier; 2023. Ch. 126. RER = 70 × BW^0.75 (Box 126.1); per-feeding bolus volume cap 10 mL/kg default (range 2–40 mL/kg). (Secondary) WSAVA Global Nutrition Committee. *Feeding Guide for Hospitalized Dogs and Cats*. WSAVA Global Nutrition Toolkit; 2013. Three-day ramp schedule (33% / 67% / 100% RER) with bolus split and overflow handling. |
| **Mannitol osmotherapy** | (Primary) Plumb DC. *Plumb's Veterinary Drugs*. Mannitol monograph (current edition). Encodes all five Plumb's indications: osmotic diuresis (label, not FDA-approved) 1.5–2 g/kg over 30 min; oliguric AKI 0.25–1 g/kg over 15–20 min with optional follow-up CRI 60–120 mg/kg/hr; acute glaucoma refractory to topical agents 1–2 g/kg over 10–20 min with 1–4 hr post-dose water restriction; increased ICP / cerebral edema 0.5–1 g/kg over 15–20 min q6–8h (IV CRI NOT recommended per Plumb's); adjunctive uroliths 0.25–0.5 g/kg over 20 min + fixed CRI 1 mg/kg/min (= 60 mg/kg/hr). Conventional 2 g/kg/day cumulative ceiling enforced. (Secondary) Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 4th ed. Elsevier; 2023. Ch. 88 (TBI) for cerebral edema; Ch. 117 (AKI) for diuretic-response framing. (Secondary) DiBartola SP. *Fluid, Electrolyte, and Acid-Base Disorders*. 4th ed. Elsevier; 2012. Ch. 26. Osmotic nephrosis mechanism and serum osmolality monitoring target (<320 mOsm/kg). Persistent warning encodes crystallization risk and the 0.22 µm filter requirement. |
| **Osmolar gap** | (Primary) DiBartola SP, ed. *Fluid, Electrolyte, and Acid-Base Disorders in Small Animal Practice*. 4th ed. St. Louis, MO: Elsevier Saunders; 2012. Ch. 3 (Disorders of Sodium and Water). Reference range for serum osmolality (290–310 mOsm/kg in dogs and cats), the calculated-osmolality formula (2 × Na + glucose/18 + BUN/2.8 in US units; 2 × Na + glucose + urea in SI), and clinical interpretation of the gap. (Foundational) Thrall MA, Grauer GF, Mero KN. Clinicopathologic findings in dogs and cats with ethylene glycol intoxication. *J Am Vet Med Assoc* 1984;184(1):37–41. Establishes the diagnostic value of an osmolar gap in suspected EG toxicosis and the time-dependent narrowing of the gap as parent compound is metabolized. (Feline-specific) Connally HE, Thrall MA, Hamar DW. Safety and efficacy of high-dose fomepizole compared with ethanol as therapy for ethylene glycol intoxication in cats. *J Vet Emerg Crit Care* 2010;20(2):191–206. Narrow therapeutic window in cats (~3 hr post-ingestion). (Foundational physiology) Rose BD, Post TW. *Clinical Physiology of Acid-Base and Electrolyte Disorders*. 5th ed. McGraw-Hill; 2001. Gap cutoffs encoded: <10 normal, 10–20 borderline, >20 elevated. |
| **Oxygenation · P:F ratio + A-a gradient** | (Foundational physiology) West JB, Luks AM. *West's Respiratory Physiology: The Essentials*. 11th ed. Wolters Kluwer; 2020. Alveolar gas equation, A-a gradient physiology, and shunt/V-Q-mismatch framework. Constants used in code (PH₂O 47 mmHg at 37 °C, R 0.8 for mixed diet, Patm 760 mmHg at sea level) derive from this source. (Veterinary anesthesia) Lumb AB, Jones GM. *Lumb and Jones' Veterinary Anesthesia and Analgesia*. 6th ed. Wiley-Blackwell; 2024. Ch. 22 (Respiratory Monitoring). (Veterinary ICU) Silverstein DC, Hopper K, eds. *Small Animal Critical Care Medicine*. 4th ed. Elsevier; 2023. Ch. 23 (Oxygenation and Ventilation Monitoring). (Cutoffs) ARDS Definition Task Force. Acute Respiratory Distress Syndrome: the Berlin Definition. *JAMA* 2012;307(23):2526–2533. doi:10.1001/jama.2012.5669. Source of the 300/200/100 P:F cutoffs. (Veterinary ALI/ARDS) Wilkins PA, Otto CM, Baumgardner JE, et al. Acute lung injury and acute respiratory distress syndromes in veterinary medicine: consensus definitions. *J Vet Emerg Crit Care* 2007;17(4):333–339. Veterinary adaptation of the Berlin criteria used in InfusionFox's classification scheme. |

## Diagnostic scoring tools

| Calculator | Source |
|---|---|
| **Cushing's syndrome prediction score** | Schofield I, Brodbelt DC, Niessen SJM, et al. Development and internal validation of a prediction tool to aid the diagnosis of Cushing's syndrome in dogs attending primary-care practice. *J Vet Intern Med* 2020;34:2306–2318. doi:10.1111/jvim.15851. Tables 5 and 6 directly. Score range −13 to +10, mapping to 0–96% predicted likelihood. AUROC 0.78. |
| **LDDST interpretation** | Behrend EN, Kooistra HS, Nelson R, Reusch CE, Scott-Moncrieff JC. Diagnosis of spontaneous canine hyperadrenocorticism: 2012 ACVIM Consensus Statement (Small Animal). *J Vet Intern Med* 2013;27:1292–1304. doi:10.1111/jvim.12192. Two-stage interpretation. |
| **Hypothyroidism pretest score** | (Primary) Corsini A, Lunetta F, Alboni F, Drudi I, Faroni E, Fracassi F. Development and internal validation of diagnostic prediction models using machine-learning algorithms in dogs with hypothyroidism. *Front Vet Sci* 2023;10:1292988. (Supporting) Bell ET, Mooney CT, Shiel RE. Assessment of the likelihood of hypothyroidism in dogs diagnosed with and treated for hypothyroidism at primary care practices: 102 cases (2016–2021). *J Vet Intern Med* 2024;38:881–891. (Guidelines) Fleeman LM et al. *2023 AAHA Selected Endocrinopathies of Dogs and Cats Guidelines*. **Note:** simplified additive adaptation of Corsini's qualitative-only models (M1/M3, AUROC 0.85–0.88), not direct ML reimplementation. |
| **Addison's pretest score** | (Primary) Reagan KL, Reagan BA, Gilor C. Predicting the likelihood of hypoadrenocorticism in dogs using signalment and routine laboratory results with an ensemble machine learning predictive model. *J Vet Intern Med* 2026;40:e70067. (Addison Detect Tool / ADT). (Supporting) Bennaim M, Centola S, Ramsey IK, Mooney CT. Can we predict hypoadrenocorticism in dogs with resting hypocortisolemia? *J Vet Intern Med* 2024;38:1546–1556. (Background) Guzmán Ramos PJ, Bennaim M, Shiel RE, Mooney CT. Diagnosis of canine spontaneous hypoadrenocorticism. *Canine Med Genet* 2022;9:6. **Note:** simplified additive adaptation of ADT variables, not direct random-forest reimplementation. |
| **IRIS CKD staging** | International Renal Interest Society. *IRIS Staging of CKD* (modified 2023). http://www.iris-kidney.com/guidelines/staging.html. (Supporting) Polzin DJ. Chronic kidney disease in small animals. *Vet Clin North Am Small Anim Pract* 2011;41:15–30. Pure lookup-table: stage from creatinine + SDMA, substaged by UPC and SBP. |
| **APPLE-fast** | Hayes G, Mathews K, Doig G, Kruth S, Boston S, Nykamp S, Poljak Z, Dewey C. The Acute Patient Physiologic and Laboratory Evaluation (APPLE) Score: A Severity of Illness Stratification System for Hospitalized Dogs. *J Vet Intern Med* 2010;24:1034–1047. doi:10.1111/j.1939-1676.2010.0552.x. Five-variable model (glucose, albumin, mentation, platelets, lactate); score 0–50. External validation: Le Gal A, Barfield D, Wignall R, Cook S. Outcome prediction in dogs admitted through the emergency room. EVECC 2021. Multivariable artifacts (e.g., glucose >15 mmol/L scoring 0 as referent) preserved verbatim with UI explanations. |
| **APPLE-full** | Hayes G, Mathews K, Doig G, et al. The APPLE Score (10-variable). *J Vet Intern Med* 2010;24:1034–1047. doi:10.1111/j.1939-1676.2010.0552.x. Ten-variable model adds creatinine, WBC, SpO2, total bilirubin, respiratory rate, age, and fluid score. Score 0–80. Per Hayes Table 5: >40/80 cutoff specificity 98.3% / sensitivity 40.9%; >30/80 cutoff specificity 89.4% / sensitivity 81.2%. AUROC 0.93 construction / 0.91 validation. Multivariable artifacts (creatinine 0–0.62 mg/dL as referent, etc.) preserved verbatim per Hayes 2010 p. 11 discussion. |
| **Energy requirements (RER / MER)** | (1) Ettinger SJ, Feldman EC, Côté E (eds). *Textbook of Veterinary Internal Medicine*. 9th ed. Elsevier; 2024. Ch. 147 (dogs, Box 147.1), Ch. 150 (Obesity, weight-loss formulas). (2) National Research Council. *Nutrient Requirements of Dogs and Cats*. 2006. p. 95 (cat MER equations). Reference Cat MER formulas: lean (BCS ≤ 5/9) MER = 100 × BW^0.67; overweight (BCS > 5/9) MER = 130 × BW^0.4. **Note:** the calculator applies the lean (100 × BW^0.67) formula for ALL cats in MAINTENANCE mode regardless of BCS. Overweight cats are treated by switching to WEIGHT_LOSS mode (which uses ideal body weight, not the 130 × BW^0.4 overweight formula). The 130 × BW^0.4 formula is documented here for clinician reference but is not currently in calculator code. |

## Workflow hubs

| Hub | Source |
|---|---|
| **CPR (RECOVER 2024)** | Hoehne SN, Hopper K, Epstein SE. Reassessment Campaign on Veterinary Resuscitation (RECOVER) 2024 evidence and knowledge gap analysis: Basic life support. *J Vet Emerg Crit Care* 2024 (and accompanying advanced life support, monitoring, post-cardiac arrest, and prevention/preparedness papers). Plumb's monographs for emergency drug stock concentrations. Weight-based dosing chart. |
| **Anaphylaxis hub** | Pashmakova MB. Anaphylaxis. In Silverstein & Hopper 3rd ed Ch. 141. World Allergy Organization guidelines. Species-specific clinical pattern (dog GI/hepatic; cat respiratory). Epinephrine first-line. Diagnostic criteria adapted from human guidelines. |
| **Hypoglycemia hub** | Idowu O, Heading K. Hypoglycemia in dogs: causes, management, and diagnosis. *Can Vet J* 2018;59(6):642–649. Plumb's dextrose monograph. 50% dextrose 0.5–1 mL/kg IV diluted 1:4. |
| **DKA hub** | Hoehne SN. Diabetic Ketoacidosis. In Silverstein & Hopper 3rd ed Ch. 73, pp. 432–435 (and Box 73.1, Table 73.1). ACVIM consensus on management of canine and feline DKA. Cross-links to fluid therapy, insulin CRI/IM, and electrolyte calculators. |
| **Hyperkalemia emergency hub** | Cooper ES. Urethral Obstruction. In Silverstein & Hopper 3rd ed Ch. 122. DiBartola 4th ed Ch. 5. ACVIM consensus on canine hypoadrenocorticism (Addisonian crisis context). 8-step checklist. |
| **Status epilepticus hub · dog** | (RCT evidence) Charalambous M, Volk HA, Tipold A, et al. Comparison of intranasal versus intravenous midazolam for management of status epilepticus in dogs. *J Vet Intern Med* 2019;33:2709–2717. (RCT) Hardy BT, Patterson EE, Cloyd JM, et al. Double-masked, placebo-controlled study of intravenous levetiracetam for the treatment of status epilepticus and acute repetitive seizures in dogs. *J Vet Intern Med* 2012;26:334–340. (Consensus) Bhatti SFM, De Risio L, Muñana K, et al. International Veterinary Epilepsy Task Force consensus proposal: medical treatment of canine epilepsy in Europe. *BMC Vet Res* 2015;11:176. Plumb's drug monographs for stock concentrations. |
| **Status epilepticus hub · cat** | Pakozdy A, Halasz P, Klang A. Epilepsy in cats: theory and practice. *J Vet Intern Med* 2014;28:255–263. (Extrapolated for IV levetiracetam) Hardy BT et al. 2012. (Foundational intranasal evidence) Charalambous M, Bhatti SFM, Van Ham L, et al. Intranasal midazolam versus rectal diazepam. *J Vet Intern Med* 2017;31:1149–1158. Plumb's monographs with cat-specific cautions (propofol limited duration, ketamine HCM caution). |
| **Heatstroke hub** | (Primary retrospective) Bruchim Y, Klement E, Saragusty J, et al. Heat stroke in dogs: a retrospective study of 54 cases (1999–2004) and analysis of risk factors for death. *J Vet Intern Med* 2006;20:38–46. (Epidemiology) Hall EJ, Carter AJ, Bradbury J, et al. Establishing risk factors for canine heat-related illness in UK dogs: a VetCompass study. *Sci Rep* 2020;10:9128. (Critical care reference) Drobatz KJ. Heatstroke. In Silverstein & Hopper 3rd ed (Ch. 191 in 3rd ed). (AKI biomarkers) Segev G, Daminet S, Meyer E, et al. Characterization of kidney damage using several renal biomarkers in dogs with naturally occurring heatstroke. *Vet J* 2015;206:231–235. The 39.4°C / 103°F cooling stop point is the most-violated rule. |

## Utility tools

| Tool | Source |
|---|---|
| Dilution helper | Pure math, no clinical source needed. |
| Unit converter (weight, BSA, drug amount, concentration) | BSA formulas: dog K = 10.1, cat K = 10.0 (standard veterinary references). Other conversions are pure unit math. |
| Fluid rate calculator | Pure math; rate selection (mL/kg/day) is clinician's decision. |
| Drop factor | Pure math, no clinical source needed. |
| D5W / solution preparation | Pure math (C₁V₁ = C₂V₂); guard against target concentration ≥ stock concentration. |

---

## Pre-launch peer review tracker

Each clinical calculator must be reviewed by an independent veterinarian
familiar with the source material before going to paying users. Review is
documented per-calculator with date and reviewer (with permission to name).

| Calculator | Reviewer | Date | Notes |
|---|---|---|---|
| Norepinephrine | (pending) |  |  |
| Epinephrine | (pending) |  |  |
| Dobutamine | (pending) |  |  |
| Dopamine prep | (pending) |  |  |
| Fentanyl | (pending) |  |  |
| Hydromorphone CRI | (pending) |  |  |
| Methadone | (pending) |  |  |
| Lidocaine CRI | (pending) |  |  |
| Ketamine CRI | (pending) |  |  |
| Propofol | (pending) |  |  |
| Alfaxalone | (pending) |  |  |
| MLK | (pending) |  |  |
| Cornell Oncology KL | (pending) |  |  |
| Kitty Magic | (pending) |  |  |
| Hypernatremia | (pending) |  |  |
| Hypokalemia | (pending) |  |  |
| Hypophosphatemia | (pending) |  |  |
| Hypomagnesemia | (pending) |  |  |
| Calcium gluconate | (pending) |  |  |
| Insulin + dextrose | (pending) |  |  |
| Insulin CRI · DKA | (pending) |  |  |
| Insulin IM · DKA | (pending) |  |  |
| Fluid therapy | (pending) |  |  |
| Transfusion | (pending) |  |  |
| Blood gas interpretation | (pending) |  |  |
| Cushing's score | (pending) |  |  |
| LDDST | (pending) |  |  |
| Hypothyroid score | (pending) |  |  |
| Addison's score | (pending) |  |  |
| IRIS staging | (pending) |  |  |
| Energy (RER/MER) | (pending) |  |  |
| CPR | (pending) |  |  |
| Anaphylaxis hub | (pending) |  |  |
| Hypoglycemia hub | (pending) |  |  |
| DKA hub | (pending) |  |  |
| Hyperkalemia emergency hub | (pending) |  |  |
| Status epilepticus dog hub | (pending) |  |  |
| Status epilepticus cat hub | (pending) |  |  |
| Heatstroke hub | (pending) |  |  |

---

## Items requiring attorney review

These items have specific copyright or attribution considerations beyond
ordinary peer review:

1. **DiBartola Table 5-2 reproduction** in the hypokalemia KCl sliding-scale
   calculator. Tables of facts vs creative arrangement, flagged for legal
   counsel. Originally Greene RW, Scott RC 1975, reproduced in DiBartola.
2. **Cornell Oncology KL**: the calculator builds on Cornell's 2012 worksheet.
   The article includes a non-affiliation disclaimer. Nominative fair use of
   the "Cornell" name appears defensible as the protocol is published under
   that name in the 2025 JAVMA paper, but worth confirming with counsel.
3. **RECOVER guidelines reproduction** in the CPR calculator. Weight-based
   dose chart is published in the 2024 papers; we reproduce stock
   concentrations and dose-per-kg values as facts. Defensible nominative
   fair use of "RECOVER" branding.
4. **Diagnostic scoring adaptations**: hypothyroid score and Addison's
   score thresholds are simplified additive adaptations of published
   ML models (Corsini 2023, Reagan 2026). Each calculator and article
   calls this out explicitly. Practice is common for infusionfox reference
   tools but worth flagging.

---

## Maintenance

When adding or modifying a calculator:

1. Identify the source-of-truth reference (book, paper, consensus statement)
2. Add it to this file in the appropriate table with edition + page
3. Encode the values in the calculator config
4. Cite the source on the calculator page (footer "Source" section, automatic
   via the `_source_cite.html` partial when `result.sources` is populated)
5. Update the calculator's status to "pending peer review"
6. After review, update the reviewer table

When a source publishes a new edition:

1. Compare the relevant section to the current encoding
2. If material values changed, update the calculator
3. Update this file's edition reference
4. Re-flag for review if changes are non-trivial
