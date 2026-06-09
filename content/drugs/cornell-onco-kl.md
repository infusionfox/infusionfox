# Clinical background

The Cornell Oncology KL infusion is a multimodal outpatient analgesic protocol developed at Cornell University by Dr. Andrea Looney, primarily used for refractory osteosarcoma pain in medium-to-large breed dogs. It combines two non-opioid analgesics, sub-anesthetic ketamine (NMDA-receptor antagonism, anti-windup activity) and systemic lidocaine (sodium-channel blockade plus anti-inflammatory and NMDA effects), into a single 0.9% NaCl bag, infused over 4–6 hours and repeated every 2–4 weeks. The protocol has been used clinically at Cornell since 2008 and was retrospectively evaluated in JAVMA in 2025, documenting a 76% clinical-benefit rate across 105 dogs and 9 cats.

The prototype patient is a Golden Retriever, Labrador, Rottweiler, or other medium-to-large breed dog with appendicular osteosarcoma whose lameness and bone pain are not adequately controlled on the standard oral protocol (NSAIDs + gabapentin + bisphosphonates ± opioids ± amantadine). Osteosarcoma was the single most common diagnosis in the 2025 cohort (43% of dogs), and the breeds most represented. Golden Retrievers, Labradors, Rottweilers, Saint Bernards, are the breeds where osteosarcoma is overrepresented in clinical practice. The protocol does work for other tumor types and pain mechanisms, but in day-to-day GP and oncology referral practice, this is overwhelmingly an osteosarcoma-pain protocol in mid-to-large dogs.

## Why combine ketamine and lidocaine

Cancer pain is mechanistically different from acute postoperative pain. Tumor-related pain, particularly osteolytic pain from osteosarcoma and infiltrative pain from oral squamous cell carcinoma, develops central sensitization with peripheral and central NMDA-receptor upregulation, and frequently has a neuropathic component superimposed on the nociceptive process. The pain pathway is "wound up," and standard opioid therapy alone often fails to control it.

Ketamine and lidocaine address this picture from complementary angles:

**Ketamine** at sub-anesthetic doses (the doses used here are 50–100× lower than induction doses) is a non-competitive NMDA-receptor antagonist. NMDA receptor activation drives the central sensitization that converts acute pain to chronic pain. Blocking it doesn't necessarily relieve pain in the moment, but it prevents and reverses wind-up, which is why a 4–6 hour infusion can produce 2–4 weeks of pain relief in patients whose pain pathway has been recalibrated.

**Lidocaine** has multiple analgesic mechanisms. The sodium-channel blockade reduces ectopic activity in damaged afferent neurons (relevant for neuropathic pain). The drug also has direct anti-inflammatory activity, NMDA-receptor antagonism at higher doses, and modulation of multiple ion channels along the pain pathway. Like ketamine, the duration of analgesic effect from a finite IV infusion can substantially outlast the plasma half-life, possibly because both drugs reset some component of central sensitization rather than merely providing acute analgesia.

## What the 2025 paper found

The retrospective evaluation followed 114 animals who received at least one Onco KL infusion between 2008 and 2023. Headline findings:

- **76% clinical benefit** following the first infusion (improvement in at least one of: appetite, ability to eat, activity level, pain score, or lameness)
- Most common diagnoses: appendicular osteosarcoma in dogs (43%), oral squamous cell carcinoma in cats (44%)
- All animals received concomitant oral analgesics (NSAIDs, gabapentinoids, opioids, amantadine, steroids); KL was an adjunct
- Median 2 infusions per patient, median 27.5-day interval
- Median progression-free survival 60 days; overall survival 135 days from diagnosis
- Adverse events were minimal: grade 1 anemia most common (likely disease-related, not protocol-related)
- 2 of 105 dogs vomited during infusion, both prevented on subsequent infusions by maropitant ± ondansetron premedication

## Efficacy thresholds

Multivariate analysis identified three dose thresholds that significantly improved the likelihood of clinical response:

- **Lidocaine infusion rate ≥ 25 µg/kg/min** (= 1.5 mg/kg/hr). P = .0051
- **Ketamine infusion rate ≥ 2 µg/kg/min** (= 0.12 mg/kg/hr). P = .0374
- **Total ketamine dose ≥ 0.5 mg/kg** across the infusion. P = .0343

Patients receiving doses below these thresholds were grouped as "ultralow dose" and had significantly lower clinical benefit. **Patients < 15 kg were significantly more likely to receive ultralow doses** because the bag-based protocol delivers drug at a fixed rate of 2.5 mL/kg/hr, which, in a small patient over a 4–6 hour duration, doesn't finish a 250 mL or 500 mL bag, leaving substantial drug behind. The clinical response rate reflected this: **71% in patients < 15 kg vs 91% in patients ≥ 15 kg** (P = .0441).

For the typical Onco KL patient, a medium-to-large breed dog with osteosarcoma, the standard 500 mL bag at 4–6 hours reliably hits the efficacy thresholds, and the underdosing concern is largely theoretical. The patients where this matters most are cats and small-breed dogs being treated for non-osteosarcoma cancer pain (oral SCC, sinonasal tumors, soft-tissue sarcomas in toy breeds). The Iocolano paper recommends, for these smaller patients, either splitting the KL into separate infusions or using a smaller carrier volume (such as a 100 mL bag or a syringe matched to the total volume to be infused), so that the target ketamine and lidocaine doses are actually delivered.

The InfusionFox calculator implements this by surfacing the delivered rates against the published efficacy thresholds for every patient, with explicit warnings when the rates fall below the thresholds, and offering a 100 mL bag option to rescue the small-patient case.

## Indications

In day-to-day practice, including at Cornell where the protocol originated. Onco KL is used **almost exclusively for refractory osteosarcoma pain in medium-to-large breed dogs.** That's the prototype patient: a 30–60 kg Golden, Lab, Rottweiler, Greyhound, or other osteosarcoma-overrepresented breed with appendicular bone pain that's not adequately controlled on the standard oral protocol of NSAID + gabapentinoid + bisphosphonate ± opioid.

The 2025 cohort breakdown reflects this distribution. Of 105 dogs:

- **45 had appendicular osteosarcoma** (43%, the single most common diagnosis)
- **50 had osteosarcoma at any anatomic site** (48%)
- The most-represented breeds were Golden Retriever (24%), Labrador Retriever (12%), Rottweiler (8%), Saint Bernard (4%), exactly the breeds where osteosarcoma incidence is highest

Per the cohort, the most common reasons for prescribing the infusion were:

- **Refractory osteolytic pain** (81% of cases), osteosarcoma drives almost all of this
- **Subcutaneous and intramuscular tumor invasion** (9%)
- **Radiation therapy side effects** including desquamation, mucositis, osteonecrosis (4%)
- **Visceral pain** (4%)
- **Neuropathic pain** (2%)

Other tumor types treated in the cohort included carcinomas, soft-tissue sarcomas, round-cell tumors, and various less common neoplasms, the protocol works for cancer pain regardless of histology because the underlying mechanism (central sensitization + neuropathic component) is similar across tumor types. But the typical Onco KL patient walks in the door with a known osteosarcoma diagnosis and a recent worsening of lameness.

## Cat-specific considerations

Cats represented a small minority of the 2025 cohort (9 of 114 animals = 8%). All 9 cats had medium-sized solid tumors, most commonly oral squamous cell carcinoma (44%) and sinonasal tumors (33%), and all were small (median 3.9 kg).

Cats are more sensitive than dogs to lidocaine's CNS and cardiodepressant effects. Plumb's notes that most clinicians avoid IV lidocaine for analgesia in cats. The Cornell protocol addresses this by **halving the cat lidocaine dose** to 1.5 mg/kg/hr (vs 3 mg/kg/hr in dogs); ketamine dose is unchanged at 0.15 mg/kg/hr.

The 2025 paper documented no toxicities during feline infusions in this small cohort. The authors note that this differs from older feline lidocaine literature (which documented increased cardiac and neurologic effects under isoflurane anesthesia), suggesting that the awake outpatient setting and the lower lidocaine rate make this protocol acceptable in cats. Still, cats should be monitored closely for ataxia, nystagmus, hypersalivation, and lip-licking behavior, which are early signs of lidocaine toxicity.

For cats specifically, and for any small-breed dog being treated for a non-osteosarcoma cancer, the underdosing concern from the bag-mixed protocol is acute. A 4 kg cat infusing at 2.5 mL/kg/hr × 5 hr = 50 mL, only 20% of a 250 mL bag. The InfusionFox calculator flags this and recommends a smaller bag (100 mL or syringe-pump separate infusion). For osteosarcoma patients (the bulk of clinical use), this is rarely an issue because most are well over 15 kg.

## Bag preparation

The original Looney 2012 worksheet uses a single-bag preparation:

1. Calculate total drug needed: lidocaine (target rate × weight × duration), ketamine (0.15 mg/kg × duration)
2. Convert to mL of stock: lidocaine ÷ 20 mg/mL (2% lidocaine), ketamine ÷ 100 mg/mL
3. Remove an equal total volume of saline from the bag BEFORE adding drugs
4. Add lidocaine and ketamine to the bag
5. Mix thoroughly, label clearly with patient name + total drug + concentration + start time + planned end time
6. Run on a volumetric pump at 2.5 mL/kg/hr for 4–6 hours

**Use 2% lidocaine WITHOUT epinephrine.** Lidocaine-with-epinephrine is sold for dental and infiltration; mixing it into the bag would deliver an unintended epinephrine bolus and is a serious medication-error risk.

## What to give alongside

The 2025 cohort confirms that **KL is an adjunct, not monotherapy.** All 114 animals were on at least one oral analgesic at the time of infusion (median 3 oral medications):

- **Gabapentinoids** (gabapentin, pregabalin), 92% of patients. The first-line oral neuropathic-pain agent in veterinary medicine; synergizes well with KL's NMDA / sodium-channel mechanism.
- **NSAIDs**, 70% of patients (carprofen, meloxicam, firocoxib, deracoxib, galliprant, piroxicam). Anti-inflammatory effect on tumor-associated inflammation.
- **Opioids**, 68% of patients (oxycodone, tramadol, buprenorphine, codeine, hydrocodone). Often the bridge between escalating pain and the next KL infusion.
- **Steroids**, 46% of patients (mostly prednisolone). Anti-inflammatory; sometimes anti-tumor in lymphoma, mast cell disease.
- **Amantadine**, 18%. Oral NMDA antagonist that complements ketamine's mechanism between IV infusions.
- **Bisphosphonates** (zoledronate, pamidronate, alendronate), 45% of patients with bone tumors. Address osteolysis directly.

After the first KL infusion, 12% of patients had concomitant medications decreased; 6% had increases; 82% stayed the same. The drugs most commonly discontinued after KL were amantadine and gabapentinoids, suggesting KL was effective enough to taper off these adjuncts in some patients.

## Premedication

The 2025 paper notes that 2 of 105 dogs experienced vomiting during their first infusion, which was prevented on subsequent infusions by premedication with **maropitant citrate ± ondansetron**. One of these dogs also had hypersalivation and lip-licking on disconnection from the infusion, which improved with metoclopramide and glycopyrrolate before subsequent infusions.

For any patient with a history of nausea, vomiting, or motion sickness, or who's just been started on chemotherapy, premedicating with maropitant 30–60 min before the infusion is a low-cost intervention that improves the patient experience.

## Adverse events

Grade 1 anemia was the most commonly recorded adverse event but is likely disease-related rather than protocol-related (cancer-associated anemia of chronic disease is common in this population). Other documented events:

- 1 dog with first-degree AV block + sinus bradycardia under general anesthesia 1 day after KL, resolved with anesthetic recovery; possibly KL-related, possibly anesthetic-related
- 1 dog with acute hemorrhage and possible DIC 1 day post-infusion, almost certainly disease progression rather than protocol
- 1 dog with dull mentation after an unintentional 4× rate increase, resolved when the rate was corrected
- No neurologic toxicities documented in any animal
- No toxicities of any kind documented in cats

Mild ALT elevations were observed in some patients but several had pre-existing vacuolar hepatopathy or were on concurrent steroids/chemotherapy.

The protocol is genuinely well tolerated. The main safety considerations are the medication-error risks: drawing up the wrong lidocaine formulation (epinephrine-containing), mixing up the unit conventions for ketamine (mg/kg/hr vs µg/kg/min), and the controlled-substance documentation requirements for the ketamine waste when small patients don't finish the bag.

## Repeating the infusion

The infusion is typically repeated every 2–4 weeks based on duration of clinical benefit. The 2025 cohort received a median of 2 infusions (range 2–49); a small number of patients received >10 infusions over their disease course. **Number of infusions was positively associated with longer progression-free survival** (P = .0005), although causation runs both ways, patients alive longer received more infusions.

In practice, the recheck cadence usually aligns with oncology recheck schedules (every 2–4 weeks), so the infusion fits naturally into the patient's existing care plan. The owner-reported pain assessment from the prior interval drives the decision to repeat.

## Limitations and what to know

The 2025 paper is a retrospective single-institution case series, it documents safety and clinical benefit but not efficacy in a controlled comparison. Specific limitations the authors acknowledge:

- Subjective owner-reported pain assessments (caregiver placebo effect is well-documented in canine osteoarthritis pain trials and likely applies here)
- No control group; can't separate KL benefit from concomitant analgesic adjustments, oncology treatments, or natural fluctuation
- Retrospective design means adverse events may have been undercaptured
- Variable timing of recheck blood work
- Small cat population (n = 9)

Despite these limitations, the dose-response relationship the paper documents (efficacy thresholds with statistical support) is the most useful clinical finding, it's the basis for the InfusionFox calculator's threshold checks and the authors' recommendation to use smaller bags for smaller patients.

A prospective randomized study with objective pain measurements is what's needed to firmly establish efficacy. Until then, KL infusion is a reasonable adjunctive option for refractory cancer pain, well-tolerated, and worth offering to clients whose pets are not adequately controlled on oral therapy alone.

## Sources

- Iocolano KE, Looney A, Balkman CE, Hume KR, Boesch JM, Sylvester SR. Retrospective evaluation of outpatient intravenous ketamine-lidocaine infusions for the palliation of cancer pain in dogs and cats. *J Am Vet Med Assoc*. 2025;263(4):499–506. doi:10.2460/javma.24.09.0595
- Looney A. Cornell University College of Veterinary Medicine ketamine-lidocaine fluid infusion protocol (worksheet, dated 7/5/2012; used clinically at Cornell from 2008 onward).
- Plumb's Veterinary Drugs, lidocaine and ketamine monographs (current edition), for component-level pharmacology, drug interactions, and toxicity management.

---

*InfusionFox is not affiliated with or endorsed by Cornell University, Cornell University College of Veterinary Medicine, or the authors of the cited publication. The "Cornell KL" name is used because it is how this protocol is referred to in the published veterinary literature.*
