"""
Central navigation index for InfusionFox.

This is the single source of truth for "what's in the app." Both the home
page sidebar and the catalog page consume this, so adding a new calculator
or tool means updating one place and it shows up everywhere.

Three sources contribute:
  1. Drug calculators from drugs_by_category() — both YAML and hardcoded
  2. One-off hardcoded calculators (hypernatremia, LDDST, ...)
  3. Utility tools (weight, fluid rate, drop factor, dilution)

When you add a new one-off or tool, register it here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.calculators import drugs_by_category


@dataclass(frozen=True)
class NavEntry:
    href: str
    title: str
    short: str = ""  # small label rendered to the right (unit, "TOOL", etc.)
    description: str = ""  # legacy field, page-intro length; not used by catalog
    # One-sentence catalog blurb (~12-20 words). Independent of the longer
    # `description`/`indications_summary` text shown on the calculator
    # page itself. Catalog templates display this; when empty, fall back
    # to `description` so anything we haven't written a blurb for yet
    # still renders something.
    catalog_blurb: str = ""
    # Optional sort key override. When unset, entries within a category sort
    # alphabetically by title (case-insensitive). Use this to force a
    # related-item adjacency the title doesn't naturally produce. Example:
    # "LDDST interpretation" with sort_key="Cushing's LDDST" sorts under C
    # alongside the Cushing's score while keeping its displayed title.
    sort_key: str = ""
    # Optional pin flag. Entries with pin_first=True are ordered before
    # all alphabetically-sorted entries in the same category, preserving
    # their relative declaration order. Used for items that need to lead
    # their section regardless of letter — CPR in Emergency, Anesthesia
    # hub in Anesthesia & Sedation, Dilution helper in Tools.
    pin_first: bool = False
    # Top-level classifier: "calculator" (does math on a patient weight or
    # set of inputs and returns a number/recipe) versus "hub" (clinical
    # workflow, scoring/prediction tool, or decision-support page that
    # doesn't reduce to a single numeric output). Drives which top-level
    # catalog the entry appears on: /calculators or /hubs. Defaults to
    # "calculator" since most entries are math-driven; mark hubs
    # explicitly.
    kind: str = "calculator"


def _effective_sort_key(entry: NavEntry) -> str:
    """Case-insensitive sort key. Falls back to title when sort_key unset."""
    return (entry.sort_key or entry.title).lower()


# One-off calculators — not part of the YAML/hardcoded drug catalog
ONE_OFF_CALCULATORS: dict[str, list[NavEntry]] = {
    "Emergency": [
        NavEntry(
            href="/cpr",
            title="CPR dosing",
            short="RECOVER",
            description=(
                "Weight-based CPR drug doses per 2024 RECOVER guidelines. "
                "Arrest drugs (epinephrine, vasopressin, atropine), "
                "anti-arrhythmics (amiodarone, lidocaine, esmolol), "
                "reversal agents, and defibrillation energies."
            ),
            pin_first=True,
            catalog_blurb="Weight-based drug doses and defibrillation energies for cardiopulmonary arrest in dogs and cats.",
        ),
        NavEntry(
            href="/shock",
            title="Shock hub",
            short="Shock",
            description=(
                "Decision support for the four shock categories: "
                "hypovolemic, distributive, cardiogenic, obstructive. "
                "Differentiating signs, type-specific treatment pathways, "
                "lactate-guided resuscitation endpoints. Cross-links to "
                "fluid therapy, transfusion, norepinephrine, dobutamine, "
                "and anaphylaxis hubs."
            ),
            kind="hub",
            catalog_blurb="Decision support for the four shock categories with type-specific treatment pathways.",
        ),
        NavEntry(
            href="/anaphylaxis",
            title="Anaphylaxis hub",
            short="Anaphylx",
            description=(
                "Emergency workflow for acute anaphylaxis in dogs and cats. "
                "Epinephrine dosing (IM bolus + CRI), fluid resuscitation, "
                "antihistamines, bronchodilators, and species-specific "
                "presentation patterns. Per Pashmakova / Silverstein 3rd ed."
            ),
            kind="hub",
            catalog_blurb="Emergency workflow for acute anaphylaxis in dogs and cats.",
        ),
        NavEntry(
            href="/apple-fast",
            title="APPLE-fast illness severity",
            short="APPLE",
            description=(
                "5-variable ICU severity score for hospitalized dogs "
                "(Hayes 2010). Glucose, albumin, lactate, platelets, and "
                "mentation map to a 0–50 score and predicted hospital "
                "mortality. Externally validated cutoff >25 carries 85% "
                "specificity / 67% sensitivity. Population-level tool; "
                "not for driving euthanasia decisions."
            ),
            kind="hub",
            catalog_blurb="5-variable ICU severity score for hospitalized dogs; maps to predicted hospital mortality.",
        ),
        NavEntry(
            href="/apple-full",
            title="APPLE-full illness severity",
            short="APPLE-full",
            description=(
                "10-variable ICU severity score for hospitalized dogs "
                "(Hayes 2010). Creatinine, WBC, albumin, SpO₂, total "
                "bilirubin, mentation, respiratory rate, age, fluid "
                "score, and lactate map to a 0–80 score and predicted "
                "hospital mortality. AUROC 0.93/0.91 (construction/"
                "validation), better than APPLE-fast (0.87/0.84). "
                "Cutoff >30/80 carries 89% specificity / 81% sensitivity. "
                "Population-level tool; not for driving euthanasia decisions."
            ),
            kind="hub",
            catalog_blurb="10-variable ICU severity score for hospitalized dogs; better discrimination than APPLE-fast.",
        ),
        NavEntry(
            href="/hypoglycemia",
            title="Hypoglycemia hub",
            short="Hypoglyc",
            description=(
                "Emergency workflow for hypoglycemic crisis. Dextrose bolus "
                "and CRI preparation, glucagon CRI for insulinoma/refractory "
                "cases, and cause-specific management. Per Koenig / "
                "Silverstein 3rd ed."
            ),
            kind="hub",
            catalog_blurb="Emergency workflow for hypoglycemic crisis in dogs and cats.",
        ),
        NavEntry(
            href="/ile",
            title="Lipid Emulsion (ILE) protocol",
            short="ILE",
            description=(
                "Intravenous lipid emulsion (20%) for toxicology reversal. "
                "Local anesthetic systemic toxicity, calcium-channel and "
                "beta-blocker overdose, permethrin toxicosis in cats, "
                "ivermectin and other macrocyclic lactone toxicity, "
                "baclofen, and other lipophilic agents. Two practice "
                "protocols (fast ASRA-derived and slow conservative) "
                "shown side-by-side with tiered cumulative-dose "
                "classification."
            ),
            catalog_blurb=(
                "20% lipid emulsion for toxicology reversal of local "
                "anesthetic, CCB, beta-blocker, permethrin, and other "
                "lipophilic toxin overdoses."
            ),
        ),
        NavEntry(
            href="/dka",
            title="DKA management hub",
            short="DKA",
            description=(
                "Workflow page that ties together fluid therapy, insulin "
                "(CRI or IM), electrolyte sliding scales (K, P, Mg), "
                "and bicarbonate considerations into a single checklist. "
                "Cross-links to all five DKA calculators."
            ),
            kind="hub",
            catalog_blurb="Workflow combining fluids, insulin, electrolytes, and bicarbonate for diabetic ketoacidosis.",
        ),
        NavEntry(
            href="/hyperkalemia-emergency",
            title="Hyperkalemia hub",
            short="HyperK",
            description=(
                "Workflow page for life-threatening hyperkalemia: "
                "feline urethral obstruction, Addisonian crisis, "
                "oliguric AKI. Eight-step checklist tying together "
                "calcium gluconate, insulin/dextrose, fluid therapy, "
                "and definitive treatment of the underlying cause."
            ),
            kind="hub",
            catalog_blurb="Eight-step workflow for life-threatening hyperkalemia in dogs and cats.",
        ),
        NavEntry(
            href="/heatstroke",
            title="Heatstroke hub",
            short="Heatstroke",
            description=(
                "Workflow for non-exertional and exertional heatstroke "
                "in dogs and cats. Cooling protocol with the critical "
                "39.4°C / 103°F stop point, fluid resuscitation, "
                "monitoring for coagulopathy / DIC, AKI, GI translocation, "
                "cerebral edema, and arrhythmias. Cross-links to "
                "transfusion, fluid therapy, and status epilepticus hubs."
            ),
            kind="hub",
            catalog_blurb="Workflow for heatstroke in dogs and cats, with cooling, fluids, and complications monitoring.",
        ),
        NavEntry(
            href="/status-canine",
            title="Canine status epilepticus hub",
            short="Canine SE",
            description=(
                "Stepwise protocol for canine status epilepticus. "
                "Patient-weight-driven dose tables for benzodiazepine bolus, "
                "AED loading (levetiracetam, phenobarbital), and refractory "
                "anesthetic CRI (midazolam, propofol, ketamine). Includes "
                "supportive care checklist and dextrose dosing."
            ),
            kind="hub",
            catalog_blurb="Stepwise protocol for canine status epilepticus with weight-based dose tables.",
        ),
        NavEntry(
            href="/status-feline",
            title="Feline status epilepticus hub",
            short="Feline SE",
            sort_key="Canine status epilepticus hub Z",
            description=(
                "Stepwise protocol for feline status epilepticus. "
                "Feline-specific dose tables and cautions, including "
                "diazepam IV (vs the historical oral concern), "
                "limited propofol CRI duration for oxidative injury, "
                "and HCM-caution on ketamine."
            ),
            kind="hub",
            catalog_blurb="Stepwise protocol for feline status epilepticus with species-specific cautions.",
        ),
    ],
    "Analgesia": [
        NavEntry(
            href="/hydromorphone-cri",
            title="Hydromorphone CRI",
            short="Hydro",
            description=(
                "IV loading dose + CRI pump rate for dogs and cats. "
                "Dogs: 0.025–0.05 mg/kg load, then 0.03 mg/kg/hr. "
                "Cats: 0.025 mg/kg load, then 0.01–0.05 mg/kg/hr (start low). "
                "Stock selector (1, 2, 4, 10 mg/mL). Cat hyperthermia warning. "
                "DEA Schedule II. Per Plumb's (extra-label)."
            ),
            catalog_blurb="IV loading dose plus CRI for sustained opioid analgesia in dogs and cats.",
        ),
        NavEntry(
            href="/ketamine",
            title="Ketamine CRI",
            short="Ketamine",
            description=(
                "Subanesthetic ketamine CRI for analgesia and "
                "anti-windup. Two indication modes: surgical maintenance "
                "(10–20 µg/kg/min, intraoperative) and postsurgical / "
                "general analgesia (2–10 µg/kg/min, default 2 for 24 hr). "
                "Loading 0.5 mg/kg IV if anesthesia induced with a "
                "non-ketamine agent. Cat-specific cautions on HCM, "
                "seizures, and slow renal clearance. Stock 100 mg/mL."
            ),
            catalog_blurb="Subanesthetic ketamine CRI for analgesia and anti-windup in dogs and cats.",
        ),
        NavEntry(
            href="/methadone",
            title="Methadone",
            short="Methadone",
            description=(
                "Bolus, premedication, and CRI dosing for dogs and cats. "
                "Full µ-agonist with NMDA antagonist activity; useful for "
                "opioid-tolerant patients and perioperative analgesia. "
                "Per Plumb's (extra-label). Stock 10 mg/mL (human-labeled)."
            ),
            catalog_blurb="Bolus, premedication, and CRI dosing for dogs and cats.",
        ),
        NavEntry(
            href="/analgesia-cri",
            title="Analgesia CRI · multi-modal",
            short="Analgesia CRI",
            description=(
                "Multi-modal analgesia CRI builder. Pick an opioid backbone "
                "(fentanyl, morphine, or hydromorphone) and optionally add "
                "any combination of adjuncts: ketamine, lidocaine (dogs "
                "only), and dexmedetomidine. Each drug computed "
                "independently with its own pump rate, loading dose, and "
                "titration ladder. Combined-bag mode (MLK-style preparation) "
                "available via the prep-mode toggle. /mlk redirects here."
            ),
            catalog_blurb="Multi-modal analgesia CRI builder: opioid + ketamine / lidocaine / dex, per-drug or combined-bag prep.",
        ),
        NavEntry(
            href="/cornell-onco-kl",
            title="Oncology KL · Cornell protocol",
            short="Onco KL",
            description=(
                "Outpatient ketamine-lidocaine bag infusion for "
                "palliation of refractory cancer pain in dogs and cats. "
                "Per Iocolano/Looney 2025 JAVMA: 4–6 hour bag at "
                "2.5 mL/kg/hr, repeated every 2–4 weeks. Calculator "
                "surfaces bag-prep recipe AND delivered-rate efficacy "
                "thresholds (lido ≥ 25 µg/kg/min, keta ≥ 2 µg/kg/min, "
                "total keta ≥ 0.5 mg/kg); important for patients &lt; 15 kg."
            ),
            catalog_blurb="Outpatient ketamine-lidocaine bag for refractory cancer pain in dogs and cats.",
        ),
        NavEntry(
            href="/lidocaine",
            title="Lidocaine CRI",
            short="Lidocaine",
            description=(
                "Lidocaine maintenance CRI per Plumb's; dog-only "
                "(1.5–3 mg/kg/hr IV after 1–2 mg/kg IV loading bolus). "
                "Dose-unit toggle (µg/kg/min ↔ mg/kg/hr). Stock is 2% "
                "lidocaine WITHOUT epinephrine."
            ),
            catalog_blurb="Maintenance lidocaine CRI for analgesia, dogs only.",
        ),
    ],
    "Anesthesia & Sedation": [
        NavEntry(
            href="/anesthesia",
            title="Anesthesia worksheet",
            short="Anesthesia",
            description=(
                "Printable drug dose reference card. Enter patient name, age, species, "
                "and weight to generate: fluid bolus, premed options (opioid + sedative), "
                "induction doses, DKB (cats), emergency drugs, and dopamine / norepinephrine CRI instructions."
            ),
            kind="hub",
            pin_first=True,
            catalog_blurb="Printable patient-specific anesthesia worksheet with premeds, induction, emergency drugs, and CRIs.",
        ),
        NavEntry(
            href="/alfaxalone",
            title="Alfaxalone",
            short="Alfax",
            description=(
                "IV induction dose, maintenance bolus (per 10 min), and CRI pump rate "
                "for dogs and cats. Premedicated vs unpremedicated ranges per Plumb's label. "
                "No analgesia: ensure analgesic coverage. DEA Schedule IV."
            ),
            catalog_blurb="IV induction and CRI maintenance dosing for dogs and cats.",
        ),
        NavEntry(
            href="/propofol",
            title="Propofol · TIVA / Status epi",
            short="Propofol",
            description=(
                "Propofol CRI calculator with two indication modes: TIVA "
                "maintenance (dog-only, 0.1–0.5 mg/kg/min) and refractory "
                "status epilepticus (dogs and cats, 0.1–0.25 mg/kg/min, "
                "max ≈48 hr). Page also includes Plumb's induction-dose "
                "reference tables for clinical reference."
            ),
            catalog_blurb="Propofol CRI for total IV anesthesia or refractory status epilepticus.",
        ),
        NavEntry(
            href="/kitty-magic",
            title="Kitty Magic · DKT",
            short="DKT",
            description=(
                "Dexmedetomidine + Ketamine + Opioid (butorphanol or buprenorphine) "
                "in equal volumes IM, cats only. Per Plumb's table: mild, moderate, "
                "or profound sedation for weights 2–8 kg. Atipamezole reversal. "
                "Critical: requires specific stock concentrations."
            ),
            catalog_blurb="Dexmedetomidine-Ketamine-Opioid IM sedation protocol for cats.",
        ),
    ],
    "Vasopressors & Inotropes": [
        NavEntry(
            href="/dopamine",
            title="Dopamine CRI · 6×kg method",
            short="Dopamine 6×kg",
            description=(
                "Plumb's 6×kg preparation worksheet for a 100 mL bag. "
                "Outputs a patient-specific recipe where pump rate (mL/hr) "
                "equals the dose (µg/kg/min), no further math at the bedside. "
                "Use this when you have a 100 mL bag available."
            ),
            catalog_blurb="Bag-prep shortcut where the pump rate in mL/hr equals the µg/kg/min dose.",
        ),
        # Note: vasopressin, norepinephrine, epinephrine, dobutamine,
        # and dopamine-cri are NOT listed here — they flow automatically
        # from drugs_by_category() in nav_index() because they're
        # engine drugs (CalculatorConfig in drugs.py). Adding them here
        # would produce duplicate catalog entries.
    ],
    "Electrolytes & Fluids": [
        NavEntry(
            href="/fluid-therapy",
            title="Fluid therapy",
            short="Fluids",
            description=(
                "General-purpose fluid plan combiner: shock bolus, "
                "rehydration deficit (replaced over 4–24 hr), maintenance, "
                "and ongoing losses. Applicable to any cause of "
                "dehydration; highlighted for DKA management."
            ),
            catalog_blurb="General-purpose plan combining shock bolus, deficit replacement, maintenance, and ongoing losses.",
        ),
        NavEntry(
            href="/transfusion",
            title="Transfusion",
            short="Transfusion",
            description=(
                "Volume and rate calculator for pRBC, whole blood, and "
                "fresh frozen plasma in dogs and cats. Computes target-"
                "PCV-based volume, slow trial rate, main rate, and "
                "diphenhydramine premedication. Includes monitoring "
                "schedule, transfusion reaction reference, and species-"
                "specific blood typing/crossmatch requirements."
            ),
            catalog_blurb="Volume and rate calculator for blood products in dogs and cats.",
        ),
        NavEntry(
            href="/hypernatremia",
            title="Hypernatremia water deficit",
            short="HyperNa",
            description=(
                "Water deficit calculation with acute/chronic selector, "
                "fluid recommendations, and correction-rate safety check."
            ),
            catalog_blurb="Free-water deficit and correction rate for acute or chronic hypernatremia.",
        ),
        NavEntry(
            href="/mannitol",
            title="Mannitol osmotherapy",
            short="Mannitol",
            description=(
                "Indication-specific bolus calculator for mannitol: "
                "cerebral edema and intracranial hypertension, oliguric "
                "AKI (response test), and acute glaucoma. Computes total "
                "dose, volume at 20% or 25% concentration, and pump rate "
                "for a 15–30 min infusion. Surfaces the 2 g/kg/24h "
                "cumulative ceiling and the crystallization-filter "
                "requirement."
            ),
            catalog_blurb="Indication-specific mannitol dosing for cerebral edema, oliguric AKI, and acute glaucoma.",
        ),
        NavEntry(
            href="/hypokalemia",
            title="Hypokalemia · KCl supplementation",
            short="KCl",
            description=(
                "KCl-per-bag supplementation per DiBartola Ch. 5 Table 5-2 "
                "with patient-specific maximum pump rate to keep K delivery "
                "≤ 0.5 mEq/kg/hr."
            ),
            catalog_blurb="KCl-per-bag supplementation with a patient-specific maximum infusion rate.",
        ),
        NavEntry(
            href="/hypophosphatemia",
            title="Hypophosphatemia · KPhos CRI",
            short="KPhos",
            description=(
                "Sliding scale by serum phosphorus: KPhos CRI at "
                "0.03–0.12 mmol/kg/hr per Hoehne / DiBartola. Surfaces "
                "the K contribution from KPhos so total K supplementation "
                "(including any concurrent KCl) stays under the 0.5 "
                "mEq/kg/hr ceiling."
            ),
            catalog_blurb="Potassium phosphate CRI for moderate-to-severe hypophosphatemia in dogs and cats.",
        ),
        NavEntry(
            href="/hypomagnesemia",
            title="Hypomagnesemia · MgSO4 CRI",
            short="MgSO4",
            description=(
                "Sliding scale by serum magnesium: MgSO4 CRI at "
                "0.25–1 mEq/kg/day per DiBartola Ch. 5 / Hoehne. "
                "Considers refractory hypocalcemia and hypokalemia "
                "as additional indications."
            ),
            catalog_blurb="Magnesium sulfate CRI for symptomatic hypomagnesemia in dogs and cats.",
        ),
        NavEntry(
            href="/ca-gluconate-hyperK",
            title="Calcium gluconate",
            short="Ca gluconate",
            description=(
                "10% calcium gluconate 0.5–1.5 mL/kg IV slowly over "
                "10–20 min for emergency membrane stabilization in "
                "life-threatening hyperkalemia. Onset 1–3 min, duration "
                "30–60 min. Bridging therapy that buys time for "
                "K-lowering treatment and definitive correction."
            ),
            catalog_blurb="Membrane stabilization for life-threatening hyperkalemia in dogs and cats.",
        ),
        NavEntry(
            href="/insulin-dextrose-hyperK",
            title="Insulin + dextrose · K-shifting",
            short="Insulin/dextrose",
            description=(
                "Regular insulin 0.25–0.5 U/kg IV with concurrent "
                "dextrose 1–2 g per unit insulin for emergency "
                "K-shifting in hyperkalemia. Onset 15–30 min, duration "
                "4–6 hr, K reduction 0.5–1.2 mEq/L. Followed by 2.5–5% "
                "dextrose CRI to prevent rebound hypoglycemia."
            ),
            catalog_blurb="Regular insulin plus dextrose for emergency potassium shifting in hyperkalemia.",
        ),
    ],
    "Acid-base & blood gas": [
        NavEntry(
            href="/blood-gas",
            title="Blood gas · Basic",
            short="Blood gas",
            description=(
                "Interprets arterial or venous blood gas results in dogs "
                "and cats. Identifies the primary disturbance, evaluates "
                "whether the observed compensation is consistent with a "
                "simple disorder, and computes anion gap. Encodes species-"
                "specific caveats; dog compensation formulas should not "
                "be extrapolated to cats with metabolic acidosis."
            ),
            catalog_blurb="Identifies primary acid-base disturbance, compensation, and anion gap from pH, PCO2, and HCO3.",
        ),
        NavEntry(
            href="/blood-gas-stewart",
            title="Blood gas · Stewart approach",
            short="Stewart",
            description=(
                "Strong-ion alternative to the bicarbonate view. Decomposes "
                "base excess into six physiologic contributors (free water, "
                "chloride, albumin, phosphate, lactate, unmeasured anions) "
                "per Hopper &amp; Haskins 2008, and reports SIG plus "
                "albumin-corrected AG. Built for hypoalbuminemic ICU "
                "patients where the conventional anion gap is unreliable."
            ),
            catalog_blurb="Stewart strong-ion view: BE decomposition, SIG, and albumin-corrected AG for hypoalbuminemic patients.",
        ),
        NavEntry(
            href="/osmolar-gap",
            title="Osmolar gap",
            short="Osm gap",
            description=(
                "Computes calculated serum osmolality from Na, glucose, "
                "and BUN (or urea), then subtracts from a measured "
                "osmometer reading to expose unmeasured osmotically "
                "active substances. Primary clinical use is suspected "
                "ethylene glycol toxicosis (gap is highest within 6 hr "
                "of ingestion). Secondary uses include DKA and HHS "
                "workup, mannitol therapy monitoring, and detection of "
                "methanol, isopropanol, and propylene-glycol-vehicle IV "
                "drugs. Supports US and SI units; surfaces the time-"
                "dependent narrowing of the gap as parent compound is "
                "metabolized."
            ),
            catalog_blurb="Calculated osmolality and osmolar gap for ethylene glycol toxicosis, DKA, and osmotherapy monitoring.",
        ),
        NavEntry(
            href="/oxygenation",
            title="Oxygenation · PaO₂:FiO₂ and A-a gradient",
            short="P:F + A-a",
            description=(
                "Two complementary oxygenation metrics from a single "
                "arterial blood gas. P:F ratio classifies severity on "
                "Berlin-adapted cutoffs (300 mild, 200 moderate/ALI, "
                "100 severe/ARDS). A-a gradient with PaCO₂ context "
                "discriminates hypoventilation (normal A-a + high "
                "PaCO₂), V/Q mismatch (high A-a, O₂-responsive), and "
                "true shunt (high A-a, O₂-refractory). Altitude-aware "
                "via custom barometric pressure."
            ),
            catalog_blurb="P:F ratio and alveolar-arterial gradient for oxygenation severity and the cause of hypoxemia.",
        ),
    ],
    "Endocrine & Metabolic": [
        NavEntry(
            href="/insulin-cri-dka",
            title="Insulin CRI · DKA",
            short="Insulin CRI",
            description=(
                "Continuous low-dose IV regular insulin for diabetic "
                "ketoacidosis per Hoehne / Silverstein 3rd ed. Ch. 73 "
                "Table 73.1. Bag prep (2.2 U/kg into 250 mL 0.9% NaCl, "
                "prime + discard 50 mL). Sliding scale by current BG: "
                "rate + fluid composition step together (NaCl ↔ 2.5% ↔ "
                "5% dextrose; STOP at BG &lt; 100)."
            ),
            catalog_blurb="Continuous IV insulin protocol for diabetic ketoacidosis in dogs and cats.",
        ),
        NavEntry(
            href="/insulin-im-dka",
            title="Insulin IM intermittent · DKA",
            short="Insulin IM",
            description=(
                "Hourly intermittent IM regular insulin for DKA: "
                "Hoehne sliding scale dosed by previous-hour BG drop. "
                "Two-mode workflow: 0.2 U/kg loading, then 0.05–0.2 "
                "U/kg per cycle. Alternative to the IV CRI when "
                "continuous infusion isn't practical."
            ),
            catalog_blurb="Hourly IM insulin protocol for DKA when continuous infusion isn't practical.",
        ),
        NavEntry(
            href="/cushings-score",
            title="Cushing's pretest score",
            short="Cushing's",
            description=(
                "Schofield et al. (2020) prediction tool for canine Cushing's syndrome "
                "at point of first suspicion. Combines sex, age, breed, polydipsia, "
                "vomiting, potbelly, alopecia, pruritus, ALKP, and USG into a score "
                "from −13 (0%) to +10 (96% predicted likelihood). AUROC 0.78."
            ),
            kind="hub",
            catalog_blurb="Pretest probability for canine hyperadrenocorticism from history and routine labs.",
        ),
        NavEntry(
            href="/lddst",
            title="LDDST interpretation",
            short="LDDST",
            description=(
                "Two-stage interpretation per the 2013 ACVIM consensus "
                "statement on canine hyperadrenocorticism."
            ),
            kind="hub",
            # Forced adjacent to the Cushing's score under C. The natural
            # clinical flow is: Cushing's prediction score → LDDST
            # confirmatory test, so the sort_key places LDDST AFTER the
            # score by putting "Z" after the prefix so it sorts after
            # "Cushing's syndrome…" alphabetically.
            sort_key="Cushing's z LDDST interpretation",
            catalog_blurb="Two-stage interpretation of the low-dose dexamethasone suppression test in dogs.",
        ),
        NavEntry(
            href="/hypothyroid-score",
            title="Hypothyroidism pretest score",
            short="HypoT",
            description=(
                "Pretest probability for canine hypothyroidism. Adapted from Corsini "
                "2023 prediction-model variables; helps triage which dogs warrant "
                "thyroid testing in primary care."
            ),
            kind="hub",
            catalog_blurb="Pretest probability for canine hypothyroidism from history and routine labs.",
        ),
        NavEntry(
            href="/addisons-score",
            title="Addison's pretest score",
            short="Addison's",
            description=(
                "Pretest probability for canine hypoadrenocorticism. Adapted from "
                "the Reagan 2026 Addison Detect Tool variables; helps catch atypical "
                "(eunatremic, eukalemic) Addison's that presents as vague chronic illness."
            ),
            kind="hub",
            catalog_blurb="Pretest probability for canine hypoadrenocorticism from history and routine labs.",
        ),
        NavEntry(
            href="/iris-staging",
            title="IRIS CKD staging",
            short="IRIS",
            description=(
                "International Renal Interest Society 2023 staging for chronic kidney "
                "disease in dogs and cats. Stage 1–4 from creatinine and SDMA, "
                "substaged by UPC and systolic blood pressure."
            ),
            kind="hub",
            catalog_blurb="Staging for chronic kidney disease in dogs and cats from creatinine, SDMA, UPC, and blood pressure.",
        ),
    ],
    "Nutrition": [
        NavEntry(
            href="/energy",
            title="Energy requirements · RER / MER",
            short="RER",
            description=(
                "Resting and maintenance energy requirements; weight-loss and "
                "weight-gain calorie targets per Ettinger 9th ed Ch. 147, 150 "
                "(dog/weight loss) and NRC 2006 (cat maintenance)."
            ),
            catalog_blurb="Resting and maintenance energy targets for dogs and cats.",
        ),
        NavEntry(
            href="/tube-feeding",
            title="Tube feeding · NG / E-tube",
            short="TUBE",
            description=(
                "Bolus per-feeding volume for NG, NE, and esophagostomy tubes "
                "in dogs and cats, ramped over 3 or 4 days. NG tubes are "
                "restricted to liquid diets at the calculator level."
            ),
            catalog_blurb="Bolus per-feeding volume for NG and E-tubes in dogs and cats.",
        ),
    ],
}

# Utility tools — pure math, not drug-specific
UTILITY_TOOLS: list[NavEntry] = [
    NavEntry(
        href="/dilution",
        title="Dilution helper",
        short="TOOL",
        description="Calculate drug and diluent volumes for any stock → desired concentration.",
        pin_first=True,
        catalog_blurb="Calculate drug and diluent volumes for any stock-to-target concentration.",
    ),
    NavEntry(
        href="/tools/converter",
        title="Unit converter",
        short="TOOL",
        description="Body weight, drug amount (mg/µg/g), concentration (% / mg/mL / µg/mL), and body surface area.",
        catalog_blurb="Convert body weight, drug amounts, concentrations, and body surface area.",
    ),
    NavEntry(
        href="/tools/drop-factor",
        title="Drop factor",
        short="TOOL",
        description="Convert mL/hr to drops/min for gravity-drip sets without a pump.",
        catalog_blurb="Convert mL/hr to drops/min for gravity-drip sets without a pump.",
    ),
    NavEntry(
        href="/tools/d5w-prep",
        title="Solution preparation",
        short="TOOL",
        description=(
            "Make D5W from 50% dextrose, half-strength saline, and similar "
            "bench preparations. C₁V₁ = C₂V₂ math."
        ),
        catalog_blurb="Bench preparations of common solutions like D5W from 50% dextrose.",
    ),
]


def nav_index() -> dict[str, list[NavEntry]]:
    """
    Return the full app inventory, grouped by category, in the order:
    Emergency first → drug calculators → one-off calculators (merged into
    matching categories) → utility tools (under their own "Tools" heading).

    The same dict drives the home sidebar AND the catalog page.
    """
    # Desired display order for all sections
    SECTION_ORDER = [
        "Emergency",
        "Analgesia",
        "Anesthesia & Sedation",
        "Vasopressors & Inotropes",
        "Cardiology",
        "Antiemetics & Prokinetics",
        "Electrolytes & Fluids",
        "Acid-base & blood gas",
        "Endocrine & Metabolic",
        "Nutrition",
        "Tools",
    ]

    grouped: dict[str, list[NavEntry]] = {}

    # 1. Drug calculators (both YAML and hardcoded)
    # The home sidebar's compact label is auto-derived from display_name
    # ("Norepinephrine CRI" → "Norepinephrine"). For drugs with a method
    # variant in their display_name (only dopamine-cri so far), the auto-
    # derivation produces something verbose ("Dopamine · standard method"),
    # so we override per-slug here.
    SHORT_OVERRIDES = {
        "dopamine-cri": "Dopamine std",
        # Long single-word names overflow the catalog card's `.short` tag.
        # Use a conventional clinical short form instead. Keep these under
        # roughly 8 chars for safety across the catalog grid breakpoints.
        "norepinephrine": "Norepi",
        "epinephrine": "Epi",
        "hydromorphone-cri": "Hydro",
    }
    for category, drugs in drugs_by_category().items():
        if category.lower().startswith("examples"):
            continue
        entries = []
        for d in drugs:
            short = SHORT_OVERRIDES.get(
                d.slug,
                d.display_name.replace(" CRI", "").replace(" Infusion", ""),
            )
            entries.append(
                NavEntry(
                    href=f"/{d.slug}",
                    title=d.display_name,
                    short=short,
                    description=d.indications_summary or d.mechanism_summary,
                    # Engine-driven drugs carry their own catalog blurb on
                    # the CalculatorConfig. Falls back to empty string when
                    # the drug data hasn't set one yet; in that case the
                    # catalog template uses the legacy description.
                    catalog_blurb=getattr(d, "catalog_blurb", "") or "",
                )
            )
        if entries:
            grouped.setdefault(category, []).extend(entries)

    # 2. One-off calculators — merge into matching categories or create new
    for category, entries in ONE_OFF_CALCULATORS.items():
        grouped.setdefault(category, []).extend(entries)

    # 3. Tools always last
    grouped["Tools"] = list(UTILITY_TOOLS)

    # 3b. Sort entries within each category. Entries with pin_first=True
    # come first in their declaration order; everything else sorts
    # alphabetically by effective sort key (sort_key override or title,
    # case-insensitive). This produces consistent A→Z navigation while
    # letting us pin a section's headline calculator (CPR, Anesthesia
    # hub, Dilution helper) and force related-item adjacency (LDDST
    # under C with Cushing's).
    for section, entries in grouped.items():
        pinned = [e for e in entries if e.pin_first]
        unpinned = sorted(
            (e for e in entries if not e.pin_first),
            key=_effective_sort_key,
        )
        grouped[section] = pinned + unpinned

    # 4. Return in desired order, with any unlisted sections appended at end
    ordered: dict[str, list[NavEntry]] = {}
    for section in SECTION_ORDER:
        if section in grouped:
            ordered[section] = grouped[section]
    for section, entries in grouped.items():
        if section not in ordered:
            ordered[section] = entries

    return ordered


def _filtered_index(kind: str) -> dict[str, list[NavEntry]]:
    """Return nav_index() filtered to entries of a single kind ("calculator"
    or "hub"). Drops categories that end up empty after filtering, preserves
    the section ordering and within-section pin/sort logic from nav_index()."""
    full = nav_index()
    out: dict[str, list[NavEntry]] = {}
    for cat, entries in full.items():
        filtered = [e for e in entries if e.kind == kind]
        if filtered:
            out[cat] = filtered
    return out


def calculator_nav_index() -> dict[str, list[NavEntry]]:
    """nav_index() restricted to calculator entries (math/dose/prep tools).
    Drives /calculators."""
    return _filtered_index("calculator")


def hub_nav_index() -> dict[str, list[NavEntry]]:
    """nav_index() restricted to hub entries (clinical workflows, scoring
    tools, decision-support pages). Drives /hubs."""
    return _filtered_index("hub")
