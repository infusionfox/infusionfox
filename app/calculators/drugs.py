"""
Drug catalog, single source of truth.

Each calculator is defined as a `CalculatorConfig` instance and added to
`_HARDCODED` below. To add a new calculator, define a new config and append
its name to `_HARDCODED`.

PRE-LAUNCH TODO, source verification:
  Norepinephrine, Fentanyl, Dopamine, Dobutamine, and Epinephrine: dose
  ranges, indications, mechanism, contraindications, drug interactions,
  and clinical context all verified against Plumb's Veterinary Drugs
  monographs (current edition). Silverstein 147.1 secondary citations
  applied to NE, Dopamine, Dobutamine, and Epinephrine.

  Remaining items still spreadsheet-sourced:
    - Concentration presets / dilution recipes for NE, Epi, Dobutamine
     . Plumb's monographs (text supplied) include compatibility info but
      not specific CRI preparation recipes. Pre-launch verification against
      Plumb's Compatibility/Compounding sections + clinic-specific protocol
      pending.

  NE preparation: now uses Plumb's-published recipe (4 mg vial into
  250/500/1000 mL D5W bag). NE dilution presets verified.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .engine import (
    CalculatorConfig,
    CalculatorKind,
    ConcentrationPreset,
    DoseRange,
    DoseUnit,
    LoadingDose,
    Source,
    Species,
)

log = logging.getLogger(__name__)

NOREPINEPHRINE = CalculatorConfig(
    slug="norepinephrine",
    display_name="Norepinephrine CRI",
    short_name="NE",
    category="Vasopressors & Inotropes",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    stock_concentration_ug_per_ml=1000.0,
    stock_concentration_display="1 mg/mL (1000 µg/mL), 4 mL vial (4 mg)",
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    # 0.1 µg/kg/min is the working anchor for norepinephrine in small
    # animal anesthesia (matches the vasopressor article's worked example
    # and the conventional bag-prep starting dose). The published range
    # floor is 0.05 µg/kg/min, but clinicians rarely titrate at the pump
    # to that rate; the ladder also starts at 0.1 for the same reason.
    default_dose=0.1,
    target_pump_rate_default_dose=0.1,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.05,
            max=2.0,
            persistent_warning=(
                "High-alert medication. Do NOT confuse NOREPInephrine with "
                "EPInephrine. Use redundant verification of dose and volume. "
                "Vasopressors are not a substitute for adequate fluid "
                "replacement; correct volume status first. Extravasation "
                "causes tissue necrosis, central venous access preferred; if "
                "peripheral, use a large vein with the largest-gauge catheter "
                "possible (20-gauge has been recommended for canines)."
            ),
            caution_threshold=1.0,
            caution_note=(
                "⚠ Most sources recommend a maximum rate of 1–2 µg/kg/min. "
                "Doses above 1 µg/kg/min add increased heart rate to the "
                "increased cardiac output observed at lower doses (study "
                "in isoflurane-anesthetized dogs). Reassess indication "
                "before exceeding this range."
            ),
            note=(
                "Initial dose 0.05–0.1 µg/kg/min, titrated to effect; "
                "most sources recommend max 1–2 µg/kg/min. For "
                "isoflurane-induced hypotension, range is 0.05–2 µg/kg/min "
                "(one study reported average effective dose 0.44 µg/kg/min)."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.05,
            max=2.0,
            persistent_warning=(
                "High-alert medication. Do NOT confuse NOREPInephrine with "
                "EPInephrine. Cats may be anecdotally more susceptible to "
                "adverse effects than dogs. Vasopressors are not a substitute "
                "for adequate fluid replacement. Extravasation causes tissue "
                "necrosis, central venous access preferred."
            ),
            caution_threshold=1.0,
            caution_note=(
                "⚠ Most sources recommend a maximum rate of 1–2 µg/kg/min. "
                "Higher doses can cause arrhythmias (sinus tachycardia, "
                "atrial flutter/fibrillation, bradycardia, SVT, ventricular "
                "fibrillation reported in humans)."
            ),
            note=(
                "Same dose range as dogs. Initial 0.05–0.1 µg/kg/min, "
                "titrated to effect; most sources recommend max 1–2 µg/kg/min."
            ),
        ),
    },
    concentration_presets=(
        # Pump-rate-driven concentration tiers. The clinical goal is to keep
        # the pump rate ≥ 2 mL/hr at typical doses, which is the precision
        # floor of most volumetric pumps. The three tiers below cover the
        # patient-size range:
        # - 16 µg/mL (250 mL bag): patients ≥10 kg at 0.1 µg/kg/min keep
        #   pump rate above ~3.75 mL/hr.
        # - 8 µg/mL (500 mL bag): patients 4–10 kg keep pump rate in the
        #   3–7 mL/hr range. For smaller patients at 16 µg/mL the rate
        #   would fall below 2 mL/hr; this tier solves it.
        # - 4 µg/mL (1 L bag): patients <4 kg or any patient at very low
        #   doses where even 8 µg/mL would drop below 2 mL/hr.
        # Weight bands trigger the calculator's auto-pick so a small
        # patient defaults to the right tier without manual selection.
        # All three are pharmacologically equivalent; they're three
        # presentations of the same prescription, optimized for pump
        # precision at different patient sizes.
        # Diluent: 0.9% NaCl is acceptable for the 250 mL bag (typical
        # infusion duration of minutes-to-hours). For the 500 mL and 1 L
        # bags, infusion duration extends into the timeframe where
        # oxidative degradation matters; Plumb's specifies 5% dextrose
        # or 5% dextrose with 0.9% NaCl for those.
        ConcentrationPreset(
            16,
            "1 vial (4 mg / 4 mL) into a 250 mL bag of 5% dextrose or 0.9% NaCl",
            "Standard preparation for patients ≥10 kg. Pump rate stays above 2 mL/hr at typical doses.",
            weight_min_kg=10,
        ),
        ConcentrationPreset(
            8,
            "1 vial (4 mg / 4 mL) into a 500 mL bag of 5% dextrose or 5% dextrose with 0.9% NaCl",
            "Recommended for patients 4–10 kg. More dilute than the 250 mL preparation, so pump rate stays in the precision range for small/medium patients. Also used for prolonged infusions where bag-exchange frequency matters (sepsis, ICU).",
            weight_min_kg=4,
            weight_max_kg=10,
        ),
        ConcentrationPreset(
            4,
            "1 vial (4 mg / 4 mL) into a 1 L bag of 5% dextrose or 5% dextrose with 0.9% NaCl",
            "Recommended for patients <4 kg or any patient at very low doses where the 8 µg/mL preparation would still drop pump rate below 2 mL/hr.",
            weight_max_kg=4,
        ),
    ),
    default_concentration_ug_per_ml=16.0,
    # Combined bag-prep section: norepi was the prototype for this UI
    # pattern; these fields drive the same behavior now that the
    # template/router/JS are drug-agnostic.
    uses_combined_prep_section=True,
    bag_size_options_ml=(250, 500, 1000),
    bag_size_default_ml=250,
    vial_size_mg=4.0,
    recommendation_strategy="pump-precision",
    min_pump_rate_ml_per_hr=2.0,
    diluent_label="5% dextrose, or 5% dextrose with 0.9% NaCl",
    how_it_works_paragraphs=(
        "Enter the patient's weight and dose. The calculator picks a bag concentration that keeps the pump in its accurate range (≥ 2 mL/hr for most volumetric pumps), and a bag size that uses one full vial of stock where possible.",
        "Both selections show a <strong>suggested</strong> tag that updates as you change the patient inputs. Click any tab to override; the override sticks for the rest of the session, and a notice will appear if your choice doesn't match the patient.",
        "If even the most dilute preparation gives an unworkable rate (very small patient on a low dose), switch to <strong>Advanced: target pump rate</strong>; you pick the rate you want, the calculator derives the bag concentration to deliver it.",
    ),
    # Ladder starts at 0.1 µg/kg/min, the working clinical anchor for
    # norepinephrine. The published range floor of 0.05 is preserved in
    # dose_ranges above (so users can still enter that dose), but the
    # ladder displays the doses clinicians actually titrate at.
    titration_ladder=(0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0),
    dilution_note=(
        "Standard preparation is the contents of one 4 mg vial (4 mL of "
        "1 mg/mL stock) added to a single bag of carrier fluid. The "
        "resulting concentration depends on bag size: 250 mL gives "
        "16 µg/mL, 500 mL gives 8 µg/mL, and 1 L gives 4 µg/mL. Most "
        "general practices use the 250 mL bag for typical surgical "
        "infusions. Commercial premixed bags (4, 8, and 16 mg in 250 mL) "
        "are also available and avoid the compounding step. "
        "Carrier fluid: for short anesthesia and surgical infusions "
        "(minutes to a few hours), either 5% dextrose or 0.9% NaCl is "
        "acceptable. For prolonged infusions in sepsis or ICU care, a "
        "dextrose-containing diluent is preferred because the mildly "
        "acidic pH slows oxidative degradation of the catecholamine. "
        "Discard any solution that has turned pink, brown, or developed a "
        "precipitate. Do not co-administer norepinephrine in a line "
        "containing sodium bicarbonate or other alkalinizing solutions, "
        "and do not mix it with iron-containing fluids or oxidizing "
        "agents. If you need to compound D5W from concentrated stock, see "
        "the Solution Preparation tool at /tools/d5w-prep."
    ),
    mechanism_summary=(
        "Strong α₁ and α₂ adrenergic agonist with moderate β₁ activity. Acts "
        "at α-adrenergic receptors to cause peripheral vasoconstriction and "
        "at β receptors to cause positive inotropy and coronary artery "
        "vasodilation. Total peripheral resistance is increased, raising "
        "systolic and diastolic blood pressure. Perfusion to abdominal organs, "
        "skin, and skeletal muscle can be reduced (especially at higher "
        "doses), while coronary blood flow increases. Onset 1–2 min IV; "
        "duration 1–2 min after stop. Rapidly metabolized by COMT and MAO."
    ),
    indications_summary=(
        "Vasopressor CRI for dogs and cats. Used to restore mean "
        "arterial pressure in vasodilatory hypotension once volume "
        "resuscitation is adequate, including inhalant-induced "
        "anesthetic hypotension and septic or other distributive shock. "
        "High-alert medication; continuous BP and ECG monitoring "
        "required given dose-related arrhythmia and peripheral ischemia "
        "risk."
    ),
    catalog_blurb="First-line vasopressor for vasodilatory hypotension after fluid resuscitation.",
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, norepinephrine monograph (current "
                "edition). Sections used: Prescriber Highlights, Uses/"
                "Indications, Pharmacology/Actions, Pharmacokinetics, "
                "Contraindications/Precautions/Warnings, Adverse Effects, "
                "Drug Interactions, Dosages (dogs/cats), Monitoring, "
                "Compatibility/Compounding Considerations, Dosage Forms/"
                "Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Hart S, Silverstein DC. Catecholamines. In: Silverstein DC, "
                "Hopper K, eds. Small Animal Critical Care Medicine. 3rd ed. "
                "St. Louis, MO: Elsevier; 2023:855–859. (Chapter 147; "
                "Table 147.1. Receptor Activity, Cardiopressor Effects, and "
                "Dosages of Commonly Administered Catecholamines.) Confirms "
                "0.05–1 µg/kg/min dose range; provides clinical context for "
                "first-choice positioning in septic shock and MAP ≥ 65 mmHg "
                "target."
            ),
            reviewer=None,
        ),
    ),
)

EPINEPHRINE = CalculatorConfig(
    slug="epinephrine",
    display_name="Epinephrine CRI",
    short_name="Epi",
    category="Vasopressors & Inotropes",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    stock_concentration_ug_per_ml=1000.0,
    stock_concentration_display="1 mg/mL (1000 µg/mL), formerly labeled 1:1000",
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    default_dose=0.05,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.05,
            max=2.0,
            persistent_warning=(
                "High-alert medication. Do NOT confuse EPINEPHrine with "
                "ePHEDrine. Two commercial epinephrine concentrations exist: "
                "1 mg/mL (formerly 1:1000, used for CRI) and 0.1 mg/mL "
                "(formerly 1:10,000, used for cardiac-arrest bolus dosing); "
                "do NOT confuse them. Vasopressors are not a substitute for "
                "adequate fluid replacement; correct volume status first. "
                "Epinephrine for hypotension should be considered only "
                "when other interventions have failed, because of "
                "increased tissue oxygen demand and severe splanchnic "
                "vasoconstriction. Halogenated inhalant anesthetics "
                "(isoflurane, sevoflurane) sensitize the myocardium, "
                "arrhythmia risk is increased when epinephrine is given "
                "under inhalational anesthesia (the primary CRI "
                "indication); propranolol may be used to manage if they "
                "develop. Patients pre-medicated with acepromazine (or "
                "another phenothiazine) may exhibit 'epinephrine "
                "reversal': α-1 blockade by acepromazine unmasks β-2 "
                "vasodilation, and epinephrine can paradoxically worsen "
                "hypotension. Extravasation causes tissue necrosis, "
                "central venous access preferred; phentolamine may be "
                "used locally for extravasation."
            ),
            caution_threshold=1.0,
            caution_note=(
                "⚠ Doses above 1 µg/kg/min approach the upper end of the "
                "published 0.125–2 µg/kg/min CRI range for anesthesia "
                "hypotension. At higher doses (~5–20 µg/kg/min, "
                "supraphysiologic) epinephrine is typically reserved for "
                "CPR or anaphylaxis. Higher CRI doses can cause "
                "splanchnic ischemia and hyperlactatemia."
            ),
            note=(
                "Standard CRI dosing (dogs/cats): "
                "Anesthesia-induced hypotension nonresponsive to other "
                "inotropes: 0.125–2 µg/kg/min CRI. "
                "Anaphylaxis with established shock: 0.05 µg/kg/min slow IV "
                "infusion, titrate to clinical response. "
                "(CPR doses are bolus, not CRI: 0.01 mg/kg low-dose, "
                "0.1 mg/kg high-dose after >10 min CPR, use bolus "
                "calculators, not this tool.)"
            ),
        ),
        Species.CAT: DoseRange(
            min=0.05,
            max=2.0,
            persistent_warning=(
                "High-alert medication. Do NOT confuse EPINEPHrine with "
                "ePHEDrine, or the two commercial concentrations (1 mg/mL "
                "for CRI vs 0.1 mg/mL for arrest bolus). Vasopressors are "
                "not a substitute for adequate fluid replacement. "
                "Epinephrine for hypotension should be considered only "
                "when other interventions have failed. Halogenated "
                "inhalant anesthetics (isoflurane, sevoflurane) sensitize "
                "the myocardium, arrhythmia risk is increased under "
                "inhalational anesthesia (the primary CRI indication); "
                "propranolol may be used to manage if they develop. "
                "Patients pre-medicated with acepromazine may exhibit "
                "'epinephrine reversal' (paradoxical hypotension from "
                "α-1 blockade unmasking β-2 vasodilation). "
                "Extravasation causes tissue necrosis, central venous "
                "access preferred."
            ),
            caution_threshold=1.0,
            caution_note=(
                "⚠ Doses above 1 µg/kg/min approach the upper end of the "
                "published 0.125–2 µg/kg/min CRI range. Higher doses "
                "risk splanchnic ischemia, hyperlactatemia, and arrhythmias."
            ),
            note=(
                "Same CRI range as dogs (0.125–2 µg/kg/min for anesthesia "
                "hypotension; 0.05 µg/kg/min for anaphylaxis with shock)."
            ),
        ),
    },
    concentration_presets=(
        # NOTE: dilution recipes below are from the user's clinical spreadsheet.
        # The Plumb's monograph (text supplied) gives compatibility info but
        # not specific CRI preparation recipes. Pre-launch verification
        # against Plumb's Compatibility/Compounding section + Silverstein
        # protocol pending.
        ConcentrationPreset(
            20, "1 mL stock in 49 mL carrier fluid", "Very small patients (<5 kg)", weight_max_kg=5
        ),
        ConcentrationPreset(
            40,
            "2 mL stock in 48 mL carrier fluid",
            "Most cats, small/medium dogs (5–20 kg)",
            weight_min_kg=5,
            weight_max_kg=20,
        ),
        ConcentrationPreset(
            80, "4 mL stock in 46 mL carrier fluid", "Larger dogs (>20 kg)", weight_min_kg=20
        ),
        ConcentrationPreset(
            1000,
            "Undiluted vial (1 mg/mL stock, the CRI strength, formerly 1:1000)",
            "Too concentrated for accurate syringe-pump dosing, always dilute",
            pump_safe=False,
        ),
    ),
    default_concentration_ug_per_ml=40.0,
    # Combined bag-prep section: epinephrine has weight-band concentration
    # tiers like dobutamine, but only one bag-size option; all standard
    # CRI preparations are 50 mL syringes. The bag-size tab row hides
    # itself when bag_size_options_ml has only one entry; the form still
    # POSTs combined_prep_bag_size_ml=50 via a hidden input so the
    # contract stays consistent with the other combined-prep drugs.
    #
    # Recommendation strategy mirrors the existing concentration_presets
    # weight bands (<5 kg, 5-20 kg, >20 kg). The 20 µg/mL × 50 mL combo
    # happens to be the only full-vial pairing in the set (1 mg vial),
    # but vial-economy isn't a typical clinical concern for epi prep,
    # all three tiers are accepted standard practice and routinely use
    # 1-4 ampules, so the recipe-card "uses one full vial" badge is
    # gated off (it only renders for drugs with multiple bag sizes).
    uses_combined_prep_section=True,
    bag_size_options_ml=(50,),
    bag_size_default_ml=50,
    vial_size_mg=1.0,
    recommendation_strategy="weight-band",
    diluent_label="0.9% NaCl or 5% dextrose",
    how_it_works_paragraphs=(
        "Enter the patient's weight and dose. The calculator picks a syringe concentration matched to the patient's size: 20 µg/mL for very small patients, 40 µg/mL for most cats and small/medium dogs, 80 µg/mL for larger dogs. Each preparation is the same 50 mL syringe volume, with the drug load scaled to fit a syringe-pump infusion.",
        "The concentration tab shows a <strong>suggested</strong> tag that updates as you change the patient inputs. Click any tab to override; the override sticks for the rest of the session.",
        "For very small patients or very low doses where even the most dilute preparation gives an unworkable pump rate, switch to <strong>Advanced: target pump rate</strong>; you pick the rate you want, the calculator derives the syringe concentration to deliver it.",
    ),
    titration_ladder=(0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0),
    dilution_note=(
        "Use the 1 mg/mL ('1:1000') strength for CRI dilution, NOT the "
        "0.1 mg/mL ('1:10,000') strength which is the cardiac-arrest "
        "bolus formulation. Most balanced isotonic crystalloids (0.9% "
        "NaCl, LRS, Ringer's) work as carrier fluids, as does 5% "
        "dextrose; however, epinephrine becomes unstable in 5% dextrose "
        "at pH > 5.5, so for prolonged infusions check the solution "
        "color before and during use. Discard any solution that turns "
        "pink, brown, or develops a precipitate. Do not mix epinephrine "
        "with sodium bicarbonate or other alkalinizing solutions, and do "
        "not co-administer in a line containing oxidizing agents: the "
        "catecholamine is rapidly destroyed in those conditions."
    ),
    mechanism_summary=(
        "Endogenous catecholamine with α₁, α₂, β₁, and β₂ agonist activity. "
        "Low-dose IV (≈0.01 mg/kg) directly stimulates cardiac β₁ receptors "
        "for increased heart rate and contractility, increasing cardiac "
        "output along with myocardial work and oxygen consumption. β₂ "
        "activity in the periphery decreases peripheral vascular resistance "
        "(lowering diastolic BP). At higher dosages (≈0.1 mg/kg), peripheral "
        "vasoconstriction predominates via α₁ effects. Metabolized by MAO "
        "and COMT to inactive metabolites; does not cross the blood-brain "
        "barrier."
    ),
    indications_summary=(
        "Vasopressor CRI for dogs and cats. Reserved for hypotension "
        "that has not responded to fluid resuscitation, an inotrope, or "
        "a more selective vasopressor; positioned as a second-line "
        "vasopressor in vasodilatory shock after norepinephrine. Drives "
        "more tachycardia and myocardial oxygen demand than "
        "norepinephrine. Use the lowest effective dose and titrate down "
        "as the patient tolerates."
    ),
    catalog_blurb="Second-line catecholamine for vasopressor-refractory hypotension.",
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, epinephrine monograph (current "
                "edition). Sections used: Prescriber Highlights, Uses/"
                "Indications, Pharmacology/Actions, Pharmacokinetics, "
                "Contraindications/Precautions/Warnings, Adverse Effects, "
                "Drug Interactions, Dosages (dogs/cats, anesthesia "
                "hypotension and anaphylaxis-with-shock CRI ranges), "
                "Storage/Stability, Compatibility/Compounding "
                "Considerations, Dosage Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Hart S, Silverstein DC. Catecholamines. In: Silverstein DC, "
                "Hopper K, eds. Small Animal Critical Care Medicine. 3rd ed. "
                "St. Louis, MO: Elsevier; 2023:855–859. (Chapter 147; "
                "Table 147.1. Receptor Activity, Cardiopressor Effects, "
                "and Dosages of Commonly Administered Catecholamines.) "
                "Confirms the 0.05–1 µg/kg/min CRI range and provides "
                "clinical context: epinephrine is recommended as the first "
                "alternative to norepinephrine in septic human patients; "
                "high-dose (5–20 µg/kg/min) reserved for CPR/anaphylaxis."
            ),
            reviewer=None,
        ),
    ),
)

VASOPRESSIN = CalculatorConfig(
    slug="vasopressin",
    display_name="Vasopressin CRI",
    short_name="Vasopressin",
    category="Vasopressors & Inotropes",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # Storage convention for non-µg drugs: store the stock and the bag
    # concentrations in the *display unit's smallest increment* (here
    # mU = milliunit). The engine's "µg" math then works without any
    # change; it's a numeric, not a unit-aware, computation.
    # 20 U/mL × 1000 mU/U = 20,000 mU/mL stored stock concentration.
    stock_concentration_ug_per_ml=20000.0,
    stock_concentration_display=(
        "20 U/mL (20 000 mU/mL), 1 mL vial (20 units per vial)"
    ),
    dose_unit=DoseUnit.MU_PER_KG_PER_MIN,
    concentration_unit_label="mU/mL",
    dose_mass_unit="mU",
    # Plumb's published floor (0.5 mU/kg/min) is the conventional
    # starting rate and the headline dose. The range extends to
    # 5 mU/kg/min; Plumb's preferred shock target ceiling is 2.5.
    default_dose=0.5,
    target_pump_rate_default_dose=0.5,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.5,
            max=5.0,
            persistent_warning=(
                "High-alert medication. Vasopressors are not a "
                "substitute for adequate volume resuscitation; correct "
                "volume status first. Extravasation can cause tissue "
                "necrosis. Central venous access preferred. "
                "Continuous BP monitoring required."
            ),
            caution_threshold=2.5,
            caution_note=(
                "⚠ Plumb's preferred shock-target ceiling is 2.5 mU/kg/min. "
                "Doses above this raise coronary vasoconstriction risk "
                "and elevate mesenteric / digital ischemia risk. Reassess "
                "the indication and consider a concurrent inotrope if "
                "cardiac output is the limiting factor."
            ),
            note=(
                "Initial 0.5 mU/kg/min, titrated to MAP target; "
                "Plumb's preferred range for shock 0.5–2.5 mU/kg/min, "
                "published ceiling 5 mU/kg/min."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.5,
            max=5.0,
            persistent_warning=(
                "High-alert medication. Vasopressors are not a "
                "substitute for adequate volume resuscitation. "
                "Extravasation can cause tissue necrosis; central "
                "venous access preferred."
            ),
            caution_threshold=2.5,
            caution_note=(
                "⚠ Plumb's preferred shock-target ceiling is 2.5 mU/kg/min. "
                "Above this rate, ischemia risk rises and clinical "
                "benefit plateaus."
            ),
            note=(
                "Same dose range as dogs (0.5–5 mU/kg/min). Plumb's "
                "preferred range 0.5–2.5 for shock."
            ),
        ),
    },
    concentration_presets=(
        # Pump-rate-driven concentration tiers, same pattern as norepi.
        # Clinical goal: keep pump rate ≥ 2 mL/hr at the typical dose
        # (0.5 mU/kg/min). Three tiers cover the patient-size range:
        # - 200 mU/mL (100 mL bag, 1 vial): patients ≥7 kg.
        # - 80 mU/mL (250 mL bag, 1 vial): patients 3–7 kg, or prolonged
        #   ICU infusions where bag-exchange frequency matters.
        # - 40 mU/mL (500 mL bag, 1 vial): patients <3 kg or any patient
        #   at very low doses where 80 mU/mL would still drop below
        #   the 2 mL/hr pump-precision floor.
        # All three are pharmacologically equivalent: three
        # presentations of the same drug, optimized for pump
        # precision at different patient sizes.
        # Diluent: 0.9% NaCl or 5% dextrose, both Plumb's-compatible.
        ConcentrationPreset(
            200,
            "1 vial (20 U) into a 100 mL bag of 0.9% NaCl or 5% dextrose",
            "Standard preparation for patients ≥7 kg. Pump rate stays above 2 mL/hr at typical doses (0.5–2.5 mU/kg/min).",
            weight_min_kg=7,
        ),
        ConcentrationPreset(
            80,
            "1 vial (20 U) into a 250 mL bag of 0.9% NaCl or 5% dextrose",
            "Recommended for patients 3–7 kg, or prolonged ICU infusions where bag-exchange frequency matters. More dilute than the 100 mL preparation, so pump rate stays in the precision range for smaller patients.",
            weight_min_kg=3,
            weight_max_kg=7,
        ),
        ConcentrationPreset(
            40,
            "1 vial (20 U) into a 500 mL bag of 0.9% NaCl or 5% dextrose",
            "Recommended for patients <3 kg or any patient at very low doses where the 80 mU/mL preparation would still drop pump rate below 2 mL/hr.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=200.0,
    uses_combined_prep_section=True,
    bag_size_options_ml=(100, 250, 500),
    bag_size_default_ml=100,
    # 20 U vial expressed in the engine's "mg" semantic: 20 (numerically
    # 20 U, displayed as such in stock_concentration_display). The
    # engine's bag-recipe math multiplies vial_size_mg × 1000 to get
    # the "µg-equivalent" total drug, which for vasopressin is
    # 20 × 1000 = 20,000 mU per vial; matches the storage convention.
    vial_size_mg=20.0,
    recommendation_strategy="pump-precision",
    min_pump_rate_ml_per_hr=2.0,
    diluent_label="0.9% NaCl or 5% dextrose",
    how_it_works_paragraphs=(
        "Enter the patient's weight and dose. The calculator picks a bag concentration that keeps the pump in its accurate range (≥ 2 mL/hr for most volumetric pumps), and a bag size that uses one full 20 U vial of stock.",
        "Both selections show a <strong>suggested</strong> tag that updates as you change the patient inputs. Click any tab to override; the override sticks for the rest of the session, and a notice will appear if your choice doesn't match the patient.",
        "If even the most dilute preparation gives an unworkable rate (very small patient on a low dose), switch to <strong>Advanced: target pump rate</strong>; you pick the rate you want, the calculator derives the bag concentration to deliver it.",
    ),
    # Ladder spans Plumb's range with finer steps in the more commonly
    # titrated 0.5–2.5 band; 5.0 is the published ceiling.
    titration_ladder=(0.5, 1.0, 1.5, 2.0, 2.5, 5.0),
    dilution_note=(
        "Standard preparation is the contents of one 20 U vial (1 mL "
        "of 20 U/mL stock) added to a single bag of carrier fluid. The "
        "resulting concentration depends on bag size: 100 mL gives "
        "200 mU/mL (0.2 U/mL), 250 mL gives 80 mU/mL (0.08 U/mL), and "
        "500 mL gives 40 mU/mL (0.04 U/mL). 100 mL is the textbook "
        "preparation and the right default for most patients."
        "\n\n"
        "Carrier fluid: 0.9% NaCl and 5% dextrose are both compatible "
        "(Plumb's). For prolonged ICU infusions, dextrose-containing "
        "diluents are sometimes preferred."
        "\n\n"
        "Monitor serum sodium on infusions running > 12 hours: "
        "vasopressin retains free water via V2 receptors and can "
        "produce or worsen hyponatremia."
    ),
    mechanism_summary=(
        "Non-catecholamine vasopressor. Acts at V1 receptors on vascular "
        "smooth muscle to cause peripheral vasoconstriction independent "
        "of adrenergic receptors, which preserves activity even in "
        "catecholamine-refractory vasoplegia. V2 receptors at the renal "
        "collecting duct mediate free-water retention (this is the "
        "ADH effect). Onset 1–2 min IV; duration ~10–20 min after stop. "
        "Metabolized by hepatic and renal vasopressinase."
    ),
    indications_summary=(
        "Refractory hypotension and vasodilatory shock in dogs and "
        "cats. Used as a second-line agent when catecholamines "
        "(norepinephrine, epinephrine) have not restored MAP, or "
        "first-line in catecholamine-refractory vasoplegia (sepsis, "
        "post-CPB). Mechanism is V1-mediated, so activity is preserved "
        "in acidotic and catecholamine-down-regulated states. "
        "Continuous BP monitoring required; central venous access "
        "preferred given extravasation risk."
    ),
    catalog_blurb=(
        "Second-line / catecholamine-refractory vasopressor for "
        "vasodilatory shock in dogs and cats."
    ),
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Vasopressin monograph "
                "(current edition). Sections used: Prescriber "
                "Highlights, Uses/Indications, Pharmacology/Actions, "
                "Pharmacokinetics, Contraindications/Precautions/"
                "Warnings, Adverse Effects, Dosages (dogs/cats), "
                "Compatibility/Compounding Considerations, Dosage "
                "Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
    ),
)

PHENYLEPHRINE = CalculatorConfig(
    slug="phenylephrine",
    display_name="Phenylephrine CRI",
    short_name="PE",
    category="Vasopressors & Inotropes",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # Standard human-pharmacy stock: 10 mg/mL in 1 mL ampules.
    stock_concentration_ug_per_ml=10000.0,
    stock_concentration_display="10 mg/mL (10 000 µg/mL), 1 mL ampule (10 mg)",
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    # 1 µg/kg/min is the typical anchor for phenylephrine vasopressor
    # support; Plumb's range 0.5–3 µg/kg/min covers most clinical use.
    default_dose=1.0,
    target_pump_rate_default_dose=1.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.5,
            max=3.0,
            persistent_warning=(
                "High-alert medication. Pure α₁ agonist that produces "
                "vasoconstriction without inotropy and can cause "
                "reflex bradycardia. Vasopressors are not a substitute "
                "for adequate volume resuscitation; correct volume "
                "status first. Extravasation can cause tissue necrosis; "
                "central venous access preferred. Continuous BP and "
                "heart-rate monitoring required."
            ),
            caution_threshold=3.0,
            caution_note=(
                "⚠ Most sources recommend a maximum rate of 3 µg/kg/min. "
                "Doses above this raise the risk of severe reflex "
                "bradycardia, mesenteric and digital ischemia, and "
                "decreased cardiac output (pure α-agonism with no "
                "compensatory β-inotropy). Reassess indication before "
                "exceeding."
            ),
            note=(
                "Initial 0.5–1 µg/kg/min, titrated to MAP target; "
                "most sources recommend max 3 µg/kg/min. Useful when "
                "β-effects are undesired (HCM, atrial fibrillation, "
                "obstructive cardiac disease)."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.5,
            max=3.0,
            persistent_warning=(
                "High-alert medication. Pure α₁ agonist that produces "
                "vasoconstriction without inotropy and can cause "
                "reflex bradycardia. Cats with HCM may particularly "
                "benefit from the absence of β-stimulation. "
                "Vasopressors are not a substitute for adequate volume "
                "replacement. Extravasation causes tissue necrosis; "
                "central venous access preferred."
            ),
            caution_threshold=3.0,
            caution_note=(
                "⚠ Most sources recommend a maximum rate of 3 µg/kg/min. "
                "Above this rate, reflex bradycardia and decreased "
                "cardiac output can be marked, especially in cats with "
                "compromised myocardial function."
            ),
            note=(
                "Same dose range as dogs (0.5–3 µg/kg/min). Particularly "
                "useful in HCM cats where β-agonism is contraindicated."
            ),
        ),
    },
    concentration_presets=(
        # Pump-rate-driven concentration tiers, norepi pattern. Clinical
        # goal: keep pump rate ≥ 2 mL/hr at the typical dose
        # (1 µg/kg/min). Phenylephrine is roughly 10× less potent
        # than norepi by dose, so concentrations scale up ~10×
        # (100/40/20 vs norepi's 16/8/4).
        # - 100 µg/mL (1 vial / 100 mL): patients ≥10 kg or fluid-
        #   restricted (sepsis, CHF). Lowest carrier-fluid volume.
        # - 40 µg/mL (1 vial / 250 mL): textbook ICU/surgical prep,
        #   the "10 mg in 250 mL NaCl" recipe cited in Plumb's.
        # - 20 µg/mL (1 vial / 500 mL): very small patients or low-
        #   dose titration where the more concentrated preparations
        #   would drop pump rate below the 2 mL/hr precision floor.
        # All three are pharmacologically equivalent.
        # Diluent: 0.9% NaCl is the standard; D5W also compatible.
        ConcentrationPreset(
            100,
            "1 ampule (10 mg / 1 mL) into a 100 mL bag of 0.9% NaCl or 5% dextrose",
            "Concentrated preparation for patients ≥10 kg or fluid-restricted cases (sepsis, CHF). Lowest carrier-fluid load.",
            weight_min_kg=10,
        ),
        ConcentrationPreset(
            40,
            "1 ampule (10 mg / 1 mL) into a 250 mL bag of 0.9% NaCl or 5% dextrose",
            "Standard textbook preparation (Plumb's). Recommended for patients 3–10 kg and most general clinical use.",
            weight_min_kg=3,
            weight_max_kg=10,
        ),
        ConcentrationPreset(
            20,
            "1 ampule (10 mg / 1 mL) into a 500 mL bag of 0.9% NaCl or 5% dextrose",
            "Recommended for patients <3 kg or any patient at very low doses where the 40 µg/mL preparation would drop pump rate below 2 mL/hr.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=40.0,
    uses_combined_prep_section=True,
    bag_size_options_ml=(100, 250, 500),
    bag_size_default_ml=250,
    # 10 mg vial.
    vial_size_mg=10.0,
    recommendation_strategy="pump-precision",
    min_pump_rate_ml_per_hr=2.0,
    diluent_label="0.9% NaCl or 5% dextrose",
    how_it_works_paragraphs=(
        "Enter the patient's weight and dose. The calculator picks a bag concentration that keeps the pump in its accurate range (≥ 2 mL/hr for most volumetric pumps), and a bag size that uses one full 10 mg ampule of stock.",
        "Both selections show a <strong>suggested</strong> tag that updates as you change the patient inputs. Click any tab to override; the override sticks for the rest of the session, and a notice will appear if your choice doesn't match the patient.",
        "If even the most dilute preparation gives an unworkable rate (very small patient on a low dose), switch to <strong>Advanced: target pump rate</strong>; you pick the rate you want, the calculator derives the bag concentration to deliver it.",
    ),
    titration_ladder=(0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0),
    dilution_note=(
        "Standard preparation is the contents of one 10 mg ampule (1 mL "
        "of 10 mg/mL stock) added to a single bag of carrier fluid. The "
        "resulting concentration depends on bag size: 100 mL gives "
        "100 µg/mL, 250 mL gives 40 µg/mL, and 500 mL gives 20 µg/mL. "
        "The 250 mL bag is the textbook preparation cited in Plumb's "
        "(\"10 mg in 250 mL NaCl\") and is the right default for most "
        "patients."
        "\n\n"
        "Carrier fluid: 0.9% NaCl is the conventional diluent; 5% "
        "dextrose is also compatible. Phenylephrine is more stable in "
        "neutral-to-slightly-acidic solutions; avoid co-administration "
        "in lines containing sodium bicarbonate or other alkalinizing "
        "fluids."
        "\n\n"
        "Watch for reflex bradycardia. Phenylephrine is a pure α-agonist "
        "with no β-1 inotropic effect, and the rise in afterload can "
        "trigger a baroreceptor-mediated drop in heart rate. If marked "
        "bradycardia develops, consider adding a low-dose β-agonist or "
        "switching to norepinephrine."
    ),
    mechanism_summary=(
        "Pure α₁-adrenergic agonist with essentially no β-receptor "
        "activity at clinical doses. Acts at vascular α₁ receptors to "
        "produce arteriolar vasoconstriction; the resulting rise in "
        "systemic vascular resistance increases MAP. Lack of β-1 "
        "inotropic stimulation means cardiac output may not rise (and "
        "can fall in patients with impaired contractility). Lack of "
        "β-2 effect means no bronchodilation. Reflex bradycardia from "
        "baroreceptor response is common. Onset within 1–2 min IV; "
        "duration ~5–20 min after stop."
    ),
    indications_summary=(
        "Vasopressor CRI for vasodilatory hypotension in dogs and cats, "
        "particularly when β-stimulation is undesired or contraindicated. "
        "Common indications include hypotension during anesthesia in "
        "patients with hypertrophic cardiomyopathy (cats), obstructive "
        "cardiac disease, atrial fibrillation, or tachyarrhythmias. "
        "Also used as a second-line alternative to norepinephrine. "
        "Continuous BP and ECG monitoring required; central venous "
        "access preferred."
    ),
    catalog_blurb=(
        "Pure α₁ vasopressor for vasoconstriction without inotropy. "
        "Useful when β-stimulation is contraindicated (HCM, A-fib)."
    ),
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Phenylephrine monograph "
                "(current edition). Sections used: Prescriber "
                "Highlights, Uses/Indications, Pharmacology/Actions, "
                "Pharmacokinetics, Contraindications/Precautions/"
                "Warnings, Adverse Effects, Dosages (dogs/cats), "
                "Compatibility/Compounding Considerations, Dosage "
                "Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Hart S, Silverstein DC. Catecholamines and other "
                "vasoactive agents. In: Silverstein DC, Hopper K, eds. "
                "Small Animal Critical Care Medicine. 3rd ed. St. "
                "Louis, MO: Elsevier; 2023. Confirms the 0.5–3 µg/kg/min "
                "CRI range, provides clinical context for second-line "
                "positioning, and emphasizes the indication in "
                "HCM/obstructive disease where β-agonism is unwanted."
            ),
            reviewer=None,
        ),
    ),
)

NITROPRUSSIDE = CalculatorConfig(
    slug="nitroprusside",
    display_name="Nitroprusside CRI",
    short_name="SNP",
    category="Cardiology",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # Stock convention: 50 mg lyophilized vial reconstituted with 2 mL
    # D5W → 25 mg/mL working stock. The "vial" field encodes the
    # 50 mg total; engine math is mass-based and reconstitution
    # volume doesn't affect the bag concentration calculation
    # (it's vial mass ÷ bag volume).
    stock_concentration_ug_per_ml=25000.0,
    stock_concentration_display=(
        "50 mg lyophilized vial; reconstitute with 2 mL D5W "
        "to 25 mg/mL working stock"
    ),
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    # 1 µg/kg/min is the standard starting rate (Plumb's), titrated
    # to MAP target. Headline anchor for the calculator.
    default_dose=1.0,
    target_pump_rate_default_dose=1.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.5,
            max=10.0,
            persistent_warning=(
                "High-alert vasodilator. Multiple safety guards must "
                "be in place before starting:\n\n"
                "⚠ LIGHT-SENSITIVE. Wrap bag in foil or opaque cover; "
                "use opaque (amber) IV tubing if available. Discard if "
                "the solution turns brown, blue, or green; color change "
                "indicates degradation and the bag is no longer safe to "
                "infuse.\n\n"
                "⚠ Dilute in 5% dextrose ONLY, not 0.9% NaCl "
                "(incompatible per Plumb's). Reconstitute the vial with "
                "D5W as well.\n\n"
                "⚠ Cyanide toxicity risk rises with high doses "
                "(> 8 µg/kg/min), prolonged infusions (> 72 hr), and "
                "hepatic dysfunction. Watch for tachyphylaxis "
                "(escalating dose needed for same BP effect), metabolic "
                "acidosis, and changes in mental status; limit duration "
                "and reassess if any appear.\n\n"
                "⚠ Avoid or use caution in renal failure; thiocyanate "
                "(the cyanide metabolite) accumulates and adds neuro-"
                "toxicity.\n\n"
                "Continuous BP monitoring required; direct arterial "
                "line preferred where available. Reflex tachycardia is "
                "common; concurrent beta-blocker may be needed in "
                "patients with coronary disease."
            ),
            caution_threshold=8.0,
            caution_note=(
                "⚠ Doses above 8 µg/kg/min substantially raise cyanide "
                "accumulation risk, particularly on infusions running "
                "longer than 1–2 hours. Plumb's published ceiling is "
                "10 µg/kg/min; above the 8 µg/kg/min mark, plan for "
                "explicit duration limits (ideally < 12 hr at this "
                "level) and consider adding a second vasodilator class "
                "or switching to a non-cyanide-generating agent "
                "(hydralazine drip, IV nitroglycerin) if prolonged "
                "afterload reduction is needed."
            ),
            note=(
                "Initial 0.5–1 µg/kg/min IV, titrated upward every "
                "3–5 minutes by 0.5–1 µg/kg/min increments to BP "
                "target. Plumb's published range 0.5–10 µg/kg/min. "
                "Limit total infusion duration to < 72 hr where "
                "possible; < 24 hr is preferable at the upper end of "
                "the range."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.5,
            max=10.0,
            persistent_warning=(
                "High-alert vasodilator; same safety guards as dogs:\n\n"
                "⚠ LIGHT-SENSITIVE. Foil-wrap the bag, use opaque "
                "tubing, discard on color change.\n\n"
                "⚠ Dilute in 5% dextrose ONLY (not saline).\n\n"
                "⚠ Cyanide accumulation risk on prolonged or high-dose "
                "infusions; reduced clearance in hepatic dysfunction.\n\n"
                "⚠ Avoid in renal failure (thiocyanate accumulation).\n\n"
                "Cats have less published data than dogs for SNP; "
                "use conservatively. Continuous BP monitoring "
                "essential; HCM cats may need particular care given "
                "their preload sensitivity."
            ),
            caution_threshold=8.0,
            caution_note=(
                "⚠ Above 8 µg/kg/min in cats: cyanide accumulation "
                "risk rises sharply on infusions longer than a few "
                "hours. Published feline data is sparser than for dogs; "
                "consider lower-end maintenance and shorter total "
                "infusion duration. Reassess indication before "
                "escalating beyond this point."
            ),
            note=(
                "Same published range as dogs (0.5–10 µg/kg/min), "
                "though most feline use stays at the lower end "
                "(0.5–3 µg/kg/min) given the limited published "
                "feline data. HCM cats: careful titration; preload "
                "reduction can compromise diastolic filling."
            ),
        ),
    },
    concentration_presets=(
        # Pump-precision-style tiers, same pattern as the catecholamines.
        # 50 mg vial dropped into different bag sizes:
        #   500 µg/mL = 50 mg in 100 mL D5W (concentrated, fluid-restricted)
        #   200 µg/mL = 50 mg in 250 mL D5W (Plumb's textbook prep, default)
        #   100 µg/mL = 50 mg in 500 mL D5W (most dilute, small patients)
        # All preparations: D5W ONLY (not saline), light-protected.
        ConcentrationPreset(
            500,
            "1 vial (50 mg, reconstituted to 25 mg/mL in 2 mL D5W) into a 100 mL bag of 5% dextrose. Foil-wrap.",
            "Concentrated preparation for patients ≥15 kg or fluid-restricted CHF cases where carrier-fluid load matters. Lowest fluid burden.",
            weight_min_kg=15,
        ),
        ConcentrationPreset(
            200,
            "1 vial (50 mg, reconstituted to 25 mg/mL in 2 mL D5W) into a 250 mL bag of 5% dextrose. Foil-wrap.",
            "Plumb's textbook preparation (\"50 mg in 250 mL D5W\"). Recommended for patients 3–15 kg and most general clinical use.",
            weight_min_kg=3,
            weight_max_kg=15,
        ),
        ConcentrationPreset(
            100,
            "1 vial (50 mg, reconstituted to 25 mg/mL in 2 mL D5W) into a 500 mL bag of 5% dextrose. Foil-wrap.",
            "Dilute preparation for patients <3 kg or any patient at very low doses where the 200 µg/mL preparation would drop pump rate below 2 mL/hr.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=200.0,
    uses_combined_prep_section=True,
    bag_size_options_ml=(100, 250, 500),
    bag_size_default_ml=250,
    vial_size_mg=50.0,
    recommendation_strategy="pump-precision",
    min_pump_rate_ml_per_hr=2.0,
    diluent_label="5% dextrose ONLY (not 0.9% NaCl)",
    supports_print=True,
    how_it_works_paragraphs=(
        "Enter the patient's weight and dose. The calculator picks a bag concentration that keeps the pump in its accurate range (≥ 2 mL/hr for most volumetric pumps), and a bag size that uses one full 50 mg vial of stock.",
        "Both selections show a <strong>suggested</strong> tag that updates as you change the patient inputs. Click any tab to override; the override sticks for the rest of the session, and a notice will appear if your choice doesn't match the patient.",
        "If even the most dilute preparation gives an unworkable rate (very small patient on a low dose), switch to <strong>Advanced: target pump rate</strong>; you pick the rate you want, the calculator derives the bag concentration to deliver it.",
    ),
    # Ladder spans the published range with finer steps in the more
    # commonly titrated 0.5–3 µg/kg/min band. 10 is the published ceiling.
    titration_ladder=(0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0),
    dilution_note=(
        "Reconstitution: dissolve the 50 mg lyophilized vial in 2 mL "
        "of 5% dextrose, giving a 25 mg/mL working stock. (Sterile "
        "water for injection is also acceptable for reconstitution per "
        "manufacturer; D5W is Plumb's-recommended.) Add the entire "
        "reconstituted volume to the carrier bag.\n\n"
        "Carrier fluid: 5% dextrose ONLY. Not 0.9% NaCl; Plumb's "
        "lists saline as incompatible. The same restriction applies to "
        "any line co-administering nitroprusside; if a Y-site is "
        "needed, verify compatibility per drug.\n\n"
        "Light protection is mandatory. Wrap the bag in aluminum foil "
        "or use a manufacturer-supplied opaque cover. Use opaque "
        "(amber) IV tubing where available; the in-line clear section "
        "from a standard set is acceptable since exposure is brief, "
        "but the bag itself must remain covered.\n\n"
        "Bag stability: 24 hours from reconstitution when "
        "light-protected, refrigerated or at room temperature. "
        "Discard sooner if the solution changes color; fresh "
        "nitroprusside is light brown/orange; conversion to dark "
        "brown, blue, or green indicates degradation, and the bag is "
        "no longer safe to infuse.\n\n"
        "Hospital-policy note: many institutions have specific "
        "nitroprusside compounding protocols (foil-wrap labeled with "
        "expiration time, pharmacist-prepared, double-check sign-off). "
        "Follow local protocol where it exists; treat the above as a "
        "minimum standard."
    ),
    mechanism_summary=(
        "Direct nitric oxide donor. Releases NO spontaneously in plasma, "
        "activating guanylate cyclase in vascular smooth muscle → cGMP → "
        "vasodilation. Mixed arterial AND venous vasodilator (unlike "
        "pure arteriodilators such as hydralazine), so reduces both "
        "preload and afterload, the property that makes SNP useful "
        "for refractory CHF. Onset 30 seconds to 1 minute IV; offset "
        "1–2 minutes after stop, making it among the most titratable IV drugs "
        "available. Metabolized in erythrocytes to cyanide ions, then "
        "in liver to thiocyanate; thiocyanate eliminated renally. "
        "Cyanide accumulation is the principal toxicity risk; "
        "thiocyanate accumulation matters specifically in renal "
        "failure."
    ),
    indications_summary=(
        "Mixed arterial / venous vasodilator for hypertensive "
        "emergencies (pheochromocytoma crisis, acute severe "
        "hypertension), heart failure with afterload reduction need "
        "(MMVD stage D refractory CHF, dilated cardiomyopathy), "
        "perioperative BP control in cardiac surgery, and "
        "anesthesia-induced hypertension. Continuous BP monitoring "
        "required, with arterial line preferred. Limit total infusion "
        "duration to minimize cyanide accumulation risk."
    ),
    catalog_blurb=(
        "Direct NO donor with mixed arterial and venous vasodilation "
        "for hypertensive crisis and afterload reduction in heart failure."
    ),
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Nitroprusside Sodium monograph "
                "(current edition). Sections used: Prescriber "
                "Highlights, Uses/Indications, Pharmacology/Actions, "
                "Pharmacokinetics, Contraindications/Precautions/"
                "Warnings, Adverse Effects, Dosages (dogs/cats: "
                "hypertensive emergencies, CHF, perioperative use), "
                "Compatibility/Compounding Considerations (D5W-only "
                "diluent, light protection, color-change discard "
                "criteria), Dosage Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Côté E, Edwards NJ, Ettinger SJ, et al. Management of "
                "congestive heart failure. In: Ettinger SJ, Feldman EC, "
                "Côté E, eds. Textbook of Veterinary Internal Medicine. "
                "8th ed. Elsevier; 2017. Confirms the clinical role of "
                "nitroprusside as a bridge in stage D refractory CHF "
                "with detailed monitoring guidance and duration limits."
            ),
            reviewer=None,
        ),
    ),
)

DOBUTAMINE = CalculatorConfig(
    slug="dobutamine",
    display_name="Dobutamine CRI",
    short_name="Dobut",
    category="Vasopressors & Inotropes",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    stock_concentration_ug_per_ml=12500.0,
    stock_concentration_display="12.5 mg/mL (12 500 µg/mL)",
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    default_dose=2.5,
    dose_ranges={
        Species.DOG: DoseRange(
            # Plumb's low CO / acute CHF range: 2–20 µg/kg/min, started
            # from the low end. The 1 µg/kg/min entry point exists only
            # in the stage D end-stage refractory CHF protocol, not as a
            # general starting dose (see `note` for full context). The
            # anesthesia worksheet uses Plumb's anesthesia-specific range
            # (2–12 µg/kg/min iso) instead; this calculator covers the
            # broader CHF use case.
            min=2.0,
            max=20.0,
            persistent_warning=(
                "Dobutamine is a high-alert vasoactive drug; continuous BP "
                "and ECG monitoring are recommended where available. "
                "Tachyarrhythmias are dose-related; start at the low end "
                "of the range and titrate up to effect. The "
                "tachyarrhythmia risk rises substantially above 10 µg/kg/min "
                "in dogs. Vasopressors and inotropes are not a substitute "
                "for adequate fluid replacement; correct volume status "
                "first. Dobutamine is incompatible with sodium bicarbonate "
                "and other alkaline solutions; do not co-administer in the "
                "same line."
            ),
            caution_threshold=10.0,
            caution_note=(
                "⚠ Doses above 10 µg/kg/min are uncommon in standard practice. "
                "Upper-end dosages of 10–15 µg/kg/min are described for "
                "stage D heart failure (refractory, end-stage), and "
                "doses up to 40 µg/kg/min can be found in the literature, "
                "but these are reserved for specific clinical scenarios "
                "with intensive monitoring. Reassess indication and "
                "ensure ECG/BP monitoring is in place."
            ),
            note=(
                "Standard dosing context (dogs): "
                "low cardiac output / acute CHF: 2–20 µg/kg/min titrated "
                "from low end. "
                "MMVD stage C heart failure (acute): 2.5 → up to 10 µg/kg/min. "
                "MMVD stage D (end-stage refractory): 1 µg/kg/min, up-titrate "
                "every 15–30 min to 10–15 µg/kg/min; may combine with "
                "nitroprusside; use 12–48 hr. "
                "Hypotension during anesthesia: 5 µg/kg/min with propofol, "
                "2–12 µg/kg/min with isoflurane."
            ),
        ),
        Species.CAT: DoseRange(
            # Plumb's low CO / acute CHF range for cats: 1–5 µg/kg/min.
            # Dosage suggestions tend to be lower for cats than dogs;
            # doses above 5 have been anecdotally associated with
            # seizures. The Plumb's anesthesia-hypotension range (2–20)
            # is covered by the anesthesia worksheet instead; this calculator
            # uses the routine CHF range as the input bound.
            min=1.0,
            max=5.0,
            persistent_warning=(
                "Dobutamine is a high-alert vasoactive drug; continuous BP "
                "and ECG monitoring are recommended where available. Cats "
                "are more sensitive than dogs; the tachyarrhythmia risk "
                "rises substantially above 5 µg/kg/min, and anecdotal "
                "reports of seizures at higher doses have been published. "
                "Vasopressors and inotropes are not a substitute for "
                "adequate fluid replacement; correct volume status first. "
                "Dobutamine is incompatible with sodium bicarbonate and "
                "other alkaline solutions; do not co-administer in the "
                "same line."
            ),
            caution_threshold=5.0,
            caution_note=(
                "⚠ Cat dose above 5 µg/kg/min: seizures have been "
                "anecdotally associated with this range. The low cardiac "
                "output / CHF range in cats is 1–5 µg/kg/min. Higher "
                "doses (up to 20 µg/kg/min) appear in the literature only "
                "for hypotension during general anesthesia, where the cat "
                "is intubated and actively monitored."
            ),
            note=(
                "Standard dosing context (cats): "
                "low cardiac output / acute CHF: 1–5 µg/kg/min titrated "
                "from the low end. "
                "Hypotension during general anesthesia: 2–20 µg/kg/min."
            ),
        ),
    },
    concentration_presets=(
        # NOTE: dilution recipes below are from the user's clinical spreadsheet,
        # not from Plumb's. Plumb's monograph (in the images supplied) shows
        # dosing but not the preparation recipe. Pre-launch verification
        # against Plumb's Preparation/Stability section is pending.
        ConcentrationPreset(
            250, "1 mL stock into 49 mL carrier fluid", "Very small patients (<5 kg)", weight_max_kg=5
        ),
        ConcentrationPreset(
            500,
            "2 mL stock into 48 mL carrier fluid",
            "Most cats, small/medium dogs (5–15 kg)",
            weight_min_kg=5,
            weight_max_kg=15,
        ),
        ConcentrationPreset(
            1000, "4 mL stock into 46 mL carrier fluid", "Medium/large dogs (>15 kg)", weight_min_kg=15
        ),
        ConcentrationPreset(
            12500,
            "Undiluted vial",
            "Too concentrated for accurate syringe-pump dosing",
            pump_safe=False,
        ),
    ),
    default_concentration_ug_per_ml=1000.0,
    # Combined bag-prep section: dobutamine joins norepi in using the
    # patient-aware combined concentration + bag-size UI. Differences:
    # - Two container choices (50 mL syringe and 250 mL bag), not three.
    # - Recommendation strategy is weight-band (the existing
    #   weight_min_kg / weight_max_kg on each ConcentrationPreset above)
    #   rather than pump-precision. Dobutamine's typical pump rates are
    #   well above the volumetric precision floor at the recommended
    #   concentrations, so the clinically meaningful match is
    #   patient size → concentration tier.
    # - 250 mg/20 mL vial. Only the 1000 µg/mL × 250 mL combination is
    #   exactly one full vial; the others are partial-vial. The
    #   "suggested" tag on bag-size tabs lands on whichever option is
    #   the full-vial match for the chosen concentration, falling back
    #   to the default (50 mL syringe) when no full-vial option exists
    #   in the bag-size set.
    uses_combined_prep_section=True,
    bag_size_options_ml=(50, 250),
    bag_size_default_ml=50,
    vial_size_mg=250.0,
    recommendation_strategy="weight-band",
    diluent_label="5% dextrose, 0.9% NaCl, or LRS",
    how_it_works_paragraphs=(
        "Enter the patient's weight and dose. The calculator picks a bag concentration matched to the patient's size, and offers two containers: a 50 mL syringe (for syringe-pump precision) or a 250 mL bag (for the standard volumetric-pump workflow).",
        "Both selections show a <strong>suggested</strong> tag that updates as you change the patient inputs. Click any tab to override; the override sticks for the rest of the session.",
        "If the resulting pump rate falls below the volumetric precision floor (≈ 2 mL/hr at small patient + low dose), run the 50 mL syringe in a syringe pump for accurate delivery.",
    ),
    # Titration ladder, species-aware via the engine's filter:
    #   Dogs (min 2): see (2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20).
    #   Cats (min 1): see (1, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20).
    # The cat ladder adds a single 1 µg/kg/min row at the start (Plumb's
    # cat low CO / CHF low end) and otherwise matches the dog 2.5
    # increment pattern. We don't fill in 2 or 0.5-µg/kg/min rows because
    # the increments wouldn't match the way the drug is actually
    # titrated; clinically meaningful step size for dobutamine is
    # ~2.5 µg/kg/min, and a 1 → 2.5 jump is the realistic next move
    # from the conservative cat start.
    titration_ladder=(1.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0),
    mechanism_summary=(
        "Synthetic catecholamine, strong β₁ agonist with milder β₂ and α₁ "
        "effects, no dopaminergic activity. Causes positive inotropy with "
        "modest vasodilation, increasing forward flow with relatively little "
        "change in blood pressure. First-choice inotrope for patients with "
        "measured or suspected low cardiac output in the presence of "
        "adequate left ventricular filling pressures."
    ),
    indications_summary=(
        "Inotrope CRI for dogs and cats. Used short-term to augment "
        "forward flow in low cardiac output and acute heart failure "
        "(MMVD stage C and D), and to support cardiac output during "
        "general anesthesia. Reach for it once fluid resuscitation is "
        "complete and the goal is contractility, not vasoconstriction."
    ),
    catalog_blurb="Inotropic support for low cardiac output and acute heart failure in dogs and cats.",
    show_bag_size_suggestion=False,
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, dobutamine monograph (current "
                "edition). Sections used: Dosages (dogs and cats), with "
                "indication-specific dose ranges including stage C/D MMVD "
                "heart failure and hypotension during general anesthesia."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Hart S, Silverstein DC. Catecholamines. In: Silverstein DC, "
                "Hopper K, eds. Small Animal Critical Care Medicine. 3rd ed. "
                "St. Louis, MO: Elsevier; 2023:855–859. (Chapter 147; "
                "Table 147.1.) Confirms 5–20 µg/kg/min as first-choice "
                "inotrope for low cardiac output in dogs; notes cat doses "
                "&gt;5–10 µg/kg/min may cause CNS effects (tremors, seizures); "
                "recommends low doses only in cats."
            ),
            reviewer=None,
        ),
    ),
)


# Dopamine: standard SINGLE_DRUG_CRI calculator. The headline /dopamine
# page implements the Plumb's 6×kg method, which is elegant but ONLY works
# with a 100 mL bag (the 6×kg → 60 µg/mL/kg → mL/hr=µg/kg/min identity is
# bag-size-dependent). When 100 mL bags aren't available (many GPs stock
# only 250 mL and 1 L), this engine-based version does the standard CRI
# math at any bag size. Both routes coexist; each links to the other.
DOPAMINE_STANDARD = CalculatorConfig(
    slug="dopamine-cri",
    display_name="Dopamine CRI · standard method",
    short_name="Dopa std",
    category="Vasopressors & Inotropes",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    stock_concentration_ug_per_ml=40000.0,
    stock_concentration_display="40 mg/mL (40 000 µg/mL)",
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    default_dose=3.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=3.0,
            max=20.0,
            persistent_warning=(
                "Dopamine is a high-alert vasoactive drug; continuous BP and "
                "ECG monitoring are recommended where available. Tachyarrhythmias "
                "and α₁-mediated vasoconstriction are dose-related; start at the "
                "low end of the range and titrate up. Vasopressors are not a "
                "substitute for adequate fluid replacement; correct volume "
                "status first. Above 20 µg/kg/min, switch to norepinephrine "
                "for vasopressor effect."
            ),
            caution_threshold=10.0,
            caution_note=(
                "⚠ Doses above 10 µg/kg/min: α₁ vasoconstriction dominates over "
                "β₁ inotropy. Marked rises in SVR, falling stroke volume, "
                "and increased arrhythmia risk. Reassess indication; if "
                "vasopressor effect is the goal, norepinephrine is a more "
                "selective vasoconstrictor with a more favorable side-effect "
                "profile."
            ),
            note=(
                "Standard CRI: 3–20 µg/kg/min IV for hypotension or "
                "inhalant-induced hypotension. For severe shock, start at "
                "2.5–5 µg/kg/min and titrate +2.5–5 every ~30 min as needed."
            ),
        ),
        Species.CAT: DoseRange(
            min=5.0,
            max=20.0,
            persistent_warning=(
                "Norepinephrine is preferred over dopamine in cats. "
                "Dopamine has a documented PVC risk across the entire "
                "feline dose range (2.5–10 µg/kg/min in cats with HCM, "
                "and roughly 15% of cats have undiagnosed HCM). "
                "Norepinephrine is a more selective pressor without the "
                "same arrhythmia profile. Reserve dopamine in cats for "
                "specific indications (most commonly bradycardia-driven "
                "hypotension where dopamine's chronotropic effect is "
                "wanted), and only when norepinephrine is not a viable "
                "option (drug unavailable, etc.). Continuous ECG and "
                "BP monitoring are essential. Vasopressors are not a "
                "substitute for adequate fluid replacement."
            ),
            # Set caution low enough that every ladder row from 2.5 µg/kg/min
            # upward is flagged. The feline therapeutic range is itself
            # the documented PVC range; there is no "safe" rung in cats.
            caution_threshold=2.0,
            caution_note=(
                "⚠ Every step of the feline dopamine ladder is within the "
                "documented PVC range (2.5–10 µg/kg/min in HCM cats), "
                "and risk rises further above 10. Continuous ECG required "
                "at any rate. Reassess indication; if a selective "
                "vasopressor effect is the goal, switch to norepinephrine."
            ),
            note=(
                "Standard CRI: 5–20 µg/kg/min IV in cats. Same titration "
                "approach as dogs, but with full-ladder caution and the "
                "default expectation that norepinephrine is the better "
                "choice."
            ),
        ),
    },
    concentration_presets=(
        # Two clean preps using a 200 mg dopamine load (= 5 mL of 40 mg/mL stock).
        # Both stay well under the Plumb's hard ceiling of 3200 µg/mL.
        # No weight-based auto-selection: the choice is bag-size-driven.
        ConcentrationPreset(
            800,
            "200 mg (5 mL of 40 mg/mL) into a 250 mL bag of 0.9% NaCl or 5% dextrose",
            "250 mL bag prep",
        ),
        ConcentrationPreset(
            400,
            "200 mg (5 mL of 40 mg/mL) into a 500 mL bag of 0.9% NaCl or 5% dextrose",
            "500 mL bag prep",
        ),
    ),
    default_concentration_ug_per_ml=800.0,
    # Combined bag-prep section: dopamine fits the pattern but with no
    # patient-driven recommendation. The two pump-safe presets are
    # bag-size-driven (250 mL gives 800 µg/mL, 500 mL gives 400 µg/mL)
    # using the same 200 mg load in each, so the choice is workflow-
    # driven (which bag-size you have on hand, how long the infusion
    # will run), not patient-driven. Both deliver the same dose.
    #
    # recommendation_strategy is left empty: the picker returns the
    # default preset, the conc-tab "suggested" badge sits on the default
    # and doesn't move with patient inputs (clinically accurate: no
    # weight/dose signal should move it). The bag-size "suggested" badge
    # still works (follows the full-vial match: 800 µg/mL → 250 mL bag,
    # 400 µg/mL → 500 mL bag; both standard preps are full-vial).
    #
    # Recipe cards cover the full (conc × bag) matrix: the two standard
    # preps (200 mg in 250 / 200 mg in 500) plus two off-diagonal options
    # (400 mg in 500 = 2 vials, 100 mg in 250 = half-vial). The off-
    # diagonal cards aren't standard practice but they aren't wrong
    # either; clinicians who want them can pick them, the suggested tags
    # point away from them.
    uses_combined_prep_section=True,
    bag_size_options_ml=(250, 500),
    bag_size_default_ml=250,
    vial_size_mg=200.0,
    recommendation_strategy="",
    diluent_label="0.9% NaCl or 5% dextrose",
    how_it_works_paragraphs=(
        "Two standard preparations, both using a 200 mg load (5 mL of 40 mg/mL stock). The 250 mL bag gives 800 µg/mL; the 500 mL bag gives 400 µg/mL. Both deliver the same dose at the same pump rate; the choice is workflow-driven, not patient-driven.",
        "The <strong>suggested</strong> tag on the bag size follows your concentration choice; each concentration has a matching bag that uses one full 200 mg vial. The off-diagonal combinations (e.g. 400 µg/mL in a 250 mL bag) are still valid; the suggested tag points to the standard preparation for each concentration.",
        "For very small patients where even the more dilute 400 µg/mL preparation gives a pump rate below 2 mL/hr, switch to <strong>Advanced: target pump rate</strong>; you pick the rate you want, the calculator derives the bag concentration to deliver it.",
    ),
    titration_ladder=(2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0),
    dilution_note=(
        "Standard CRI preparation. Dopamine is compatible with 0.9% NaCl, "
        "5% dextrose, LRS, and Ringer's. Plumb's hard ceiling for the "
        "compounded final concentration is 3200 µg/mL (3.2 mg/mL); both "
        "preset preparations above are well under this limit. Discard if "
        "the solution turns pink, yellow, or brown; these indicate "
        "oxidative degradation. Dopamine is incompatible with sodium "
        "bicarbonate and other alkaline solutions; do not co-administer in "
        "the same line. For the 100 mL bag Plumb's 6×kg method, see the "
        "dopamine 6×kg calculator (it gives the same drug delivery with "
        "the elegant identity that pump rate equals dose)."
    ),
    mechanism_summary=(
        "Endogenous catecholamine; receptor activity is dose-dependent. "
        "Low doses act on dopaminergic receptors (renal/mesenteric "
        "vasodilation, the 'renal dose' concept is now discredited). "
        "Mid doses (3–10 µg/kg/min) are predominantly β₁: positive "
        "inotropy and chronotropy. Higher doses (>10 µg/kg/min) recruit "
        "α₁ vasoconstriction with rising SVR and falling stroke volume."
    ),
    indications_summary=(
        "Catecholamine CRI for dogs and cats with dose-dependent "
        "receptor activity (β₁ inotropy at mid doses, α₁ "
        "vasoconstriction at higher doses). Used for hypotension and "
        "shock where both inotropic and vasopressor support are "
        "needed. Above 20 µg/kg/min, switch to norepinephrine for a "
        "more selective vasopressor effect."
    ),
    catalog_blurb="Dose-dependent inotropic and vasopressor support for hypotension and shock.",
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb DC. Plumb's Veterinary Drugs, dopamine monograph "
                "(current edition). Sections used: Dosages (dogs and cats); "
                "Compatibility/Compounding (3200 µg/mL hard ceiling on "
                "compounded concentration; compatible diluents)."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Silverstein DC, Beer KS. Vasopressors and inotropes. In: "
                "Silverstein DC, Hopper K, eds. Small Animal Critical Care "
                "Medicine. 3rd ed. St. Louis, MO: Elsevier; 2023. (Dose-"
                "response and titration approach.)"
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Wiese AJ, et al. Effects of dopamine in conscious cats with "
                "hypertrophic cardiomyopathy. Cited in Lumb & Jones, "
                "Veterinary Anesthesia and Analgesia, 6th ed. Ch. 21. "
                "Documents PVCs at 2.5–10 µg/kg/min in HCM cats."
            ),
            reviewer=None,
        ),
    ),
)


FENTANYL = CalculatorConfig(
    slug="fentanyl",
    display_name="Fentanyl CRI",
    short_name="Fent",
    category="Analgesia",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    stock_concentration_ug_per_ml=50.0,
    stock_concentration_display="0.05 mg/mL (50 µg/mL)",
    dose_unit=DoseUnit.UG_PER_KG_PER_HR,
    default_dose=5.0,
    # Target-pump-rate mode is OFF for fentanyl. That mode is built for
    # vasopressor workflows (minimize carrier fluid in a fluid-resuscitated
    # patient). Fentanyl is conventionally prepared at a standard bag
    # concentration (e.g. 1 µg/mL) with the pump rate floating, which is
    # the historical STANDARD_BAG workflow. Forcing target-pump-rate mode
    # produced non-standard preps and, for small patients, excessive
    # carrier fluid as a fraction of maintenance.
    supports_target_pump_rate_mode=False,
    dose_ranges={
        Species.DOG: DoseRange(
            min=2.0,
            max=10.0,
            persistent_warning=(
                "Fentanyl is a potent respiratory depressant. Bradypnea, "
                "hypercapnia, and CNS depression are dose-related. Monitor "
                "respiratory rate and effort closely; have naloxone immediately "
                "available."
            ),
            note=(
                "Standard CRI range for general-anesthesia perioperative "
                "analgesia is 2–10 µg/kg/hr. Higher doses (adjunct-anesthetic "
                "5–20 µg/kg/hr or emergent severe-pain protocols up to 50 "
                "µg/kg/hr titrated) are published but assume controlled "
                "ventilation and active airway management; see the "
                "clinical-background article for those protocols."
            ),
        ),
        Species.CAT: DoseRange(
            min=2.0,
            max=10.0,
            persistent_warning=(
                "Fentanyl is a potent respiratory depressant. Bradypnea, "
                "hypercapnia, and CNS depression are dose-related. Monitor "
                "respiratory rate and effort closely; have naloxone immediately "
                "available. Fentanyl does NOT produce a MAC-sparing effect in "
                "cats (unlike dogs); opioid-induced mydriasis is common, so "
                "approach slowly and keep out of bright light."
            ),
            note=(
                "Perioperative cat CRI is 5 µg/kg/hr. Higher doses "
                "(adjunct-anesthetic or emergent severe-pain protocols, "
                "5–20 µg/kg/hr or above) are published but assume "
                "controlled ventilation; see the clinical-background "
                "article for those protocols."
            ),
        ),
    },
    # Loading-dose scenarios per Plumb's. Each scenario renders as its
    # own panel in the result section. The perioperative scenario uses
    # matches_cri_rate=True so the matched value (= user's CRI dose
    # numerically) is shown prominently; the emergent scenario is
    # titrated separately so it shows only the range.
    how_it_works_paragraphs=(
        "Enter the patient's weight and dose. The calculator returns the pump rate to deliver that dose at the chosen bag concentration. The default 5 µg/mL preparation suits most dogs and cats; alternatives are available under <strong>Use a different concentration</strong>.",
        "After you compute, the result panel shows a loading dose alongside the CRI rate. The <strong>matched value</strong> is the IV bolus that brings plasma to steady-state for your chosen CRI rate (1:1 µg/kg per µg/kg/hr), the specialist convention for short-half-life drugs.",
        "Two scenarios appear: <strong>perioperative analgesia</strong> (matched value applies) and <strong>emergent severe pain</strong> (titrated, 10–50 µg/kg). Fentanyl is a potent respiratory depressant. Monitor respiratory rate closely and keep naloxone immediately available.",
    ),
    loading_doses=(
        LoadingDose(
            label="Perioperative analgesia",
            description="During general anesthesia",
            matches_cri_rate=True,
            dose_per_kg={
                # Dogs: 2–10 µg/kg IV loading dose, matching the
                # 2–10 µg/kg/hr CRI range. (Plumb's, perioperative
                # analgesia extra-label.)
                Species.DOG: (2.0, 10.0),
                # Cats: 5 µg/kg IV loading dose, single value (not a
                # range), matching the 5 µg/kg/hr CRI rate. (Plumb's,
                # perioperative analgesia extra-label.)
                Species.CAT: (5.0, 5.0),
            },
        ),
        LoadingDose(
            label="Emergent severe pain",
            description=(
                "Titrated to effect up to 50 µg/kg; the effective dose "
                "becomes the hourly CRI rate."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # Both species: 10 µg/kg IV titrated to effect, up to
                # 50 µg/kg. (Plumb's, severe pain in emergent patient
                # extra-label, dogs and cats.)
                Species.DOG: (10.0, 50.0),
                Species.CAT: (10.0, 50.0),
            },
            note=(
                "Titrate slowly; reassess pain and respiratory rate "
                "after each increment. Have naloxone immediately "
                "available."
            ),
        ),
    ),
    concentration_presets=(
        # Three realistic clinical preparations. The default
        # (5 µg/mL) is the conventional fentanyl IV-pump CRI prep
        # for the majority of dogs and most cats; 10 µg/mL is for
        # large dogs or higher-dose work where fluid load matters;
        # 1 µg/mL is for small patients running on a syringe pump.
        #
        # All recipes use the standard sterile-prep technique: remove
        # the same volume of diluent from the bag as the volume of
        # stock you are about to add, so the final volume equals the
        # bag's nominal volume and the math is clean.
        ConcentrationPreset(
            5,
            "Remove 5 mL from a 50 mL bag of 0.9% NaCl, then add 5 mL "
            "of 50 µg/mL stock (250 µg in 50 mL final = 5 µg/mL)",
            "Standard for most patients on an IV pump",
            weight_min_kg=5.0,
            weight_max_kg=40.0,
        ),
        ConcentrationPreset(
            10,
            "Remove 10 mL from a 50 mL bag of 0.9% NaCl, then add "
            "10 mL of 50 µg/mL stock (500 µg in 50 mL final = "
            "10 µg/mL)",
            "Larger patients or higher-dose work where carrier-fluid "
            "load matters",
            weight_min_kg=40.0,
        ),
        ConcentrationPreset(
            1,
            "Remove 5 mL from a 250 mL bag of 0.9% NaCl, then add "
            "5 mL of 50 µg/mL stock (250 µg in 250 mL final = "
            "1 µg/mL)",
            "Small patients on a syringe pump or low-rate IV pump",
            weight_max_kg=5.0,
        ),
    ),
    default_concentration_ug_per_ml=5.0,
    dilution_note=(
        "Fentanyl is conventionally prepared as a diluted bag for IV-pump "
        "CRI, not run from the 50 µg/mL stock vial directly. Use the "
        "recipe matched to the patient's size; the default 5 µg/mL "
        "covers most dogs and cats and produces pump rates in the "
        "reliable 3–80 mL/hr range across typical doses. Compatible "
        "carrier fluids include 0.9% NaCl, LRS, Plasma-Lyte, and 5% "
        "dextrose; 6% hetastarch is also compatible if a colloid line "
        "is already running. Direct-from-stock administration (50 µg/mL "
        "via syringe pump) is reserved for very small patients where "
        "minimizing carrier fluid is essential and the pump can deliver "
        "fractional mL/hr reliably. Once a vial is punctured, draw what "
        "is needed for the current patient and discard the remainder; "
        "fentanyl is a DEA Schedule II controlled substance and federal "
        "/ state disposal rules apply. Document waste."
    ),
    mechanism_summary=(
        "Short-acting µ-opioid agonist, roughly 80–100× more potent than "
        "morphine on a mg-for-mg basis. Onset is within 1–2 minutes IV "
        "and the effect dissipates within 20–30 minutes after a CRI is "
        "stopped, which is what makes it useful for ICU patients who "
        "need their analgesia interrupted for neurologic reassessment. "
        "Provides analgesia, sedation, and dose-related respiratory "
        "depression; bradycardia is common but vasodilation is not. "
        "DEA Schedule II controlled substance."
    ),
    indications_summary=(
        "Short-acting opioid CRI for moderate-to-severe acute pain in "
        "dogs and cats. Used for postoperative and perioperative "
        "analgesia, pancreatitis, peritonitis, neoplastic pain, and "
        "other inpatient analgesia where a continuous opioid infusion "
        "is appropriate. The short duration suits critical illness. "
        "The infusion can be paused for neurologic reassessment and "
        "resumed without a long washout."
    ),
    catalog_blurb="Short-acting opioid CRI for acute pain in dogs and cats.",
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, fentanyl monograph (current edition). "
                "Sections used: Prescriber Highlights, Uses/Indications, "
                "Pharmacology/Actions, Pharmacokinetics, Contraindications/"
                "Precautions/Warnings, Adverse Effects, Overdose/Acute "
                "Toxicity, Drug Interactions, Dosages (dogs and cats), "
                "Preparation/Stability, Administration, Compatibility, "
                "Monitoring, and Dosage Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
    ),
)


# ---------------------------------------------------------------------------
# Morphine, pure µ-opioid agonist CRI
# ---------------------------------------------------------------------------
# Standard inpatient analgesia CRI in dogs (0.1–0.4 mg/kg/hr). The MLK
# multi-modal protocol uses morphine 0.2 mg/kg/hr as the opioid
# backbone. Cats get a conservative range (0.05–0.1 mg/kg/hr) and a
# strong caution to prefer methadone, fentanyl, or hydromorphone
# instead; morphine produces dysphoria more readily than other
# µ-agonists in cats. Histamine release on rapid IV injection is the
# distinctive practical concern: loading doses must go in slowly, and
# many practitioners give the load IM rather than IV. Stock is
# 5 mg/mL preservative-containing for IV CRI; 15 mg/mL also exists.

MORPHINE = CalculatorConfig(
    slug="morphine",
    display_name="Morphine CRI",
    short_name="Morphine",
    category="Analgesia",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    stock_concentration_ug_per_ml=5000.0,
    stock_concentration_display="5 mg/mL (5000 µg/mL); 15 mg/mL stock also available",
    dose_unit=DoseUnit.MG_PER_KG_PER_HR,
    default_dose=0.2,
    # Analgesia drugs don't use the vasopressor target-pump-rate
    # workflow. Morphine CRI is conventionally prepared at standard
    # bag concentrations (25–50 mg in 250 mL) and the pump rate
    # floats with the dose.
    supports_target_pump_rate_mode=False,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.1,
            max=0.4,
            caution_threshold=0.3,
            persistent_warning=(
                "Morphine CRI for analgesia in dogs. Histamine release on "
                "rapid IV injection; give loading doses slowly. Pure mu-"
                "agonist; expect dose-dependent respiratory depression, "
                "sedation, panting, GI hypomotility. Cumulative sedation "
                "with prolonged CRI in geriatric or hepatically-compromised "
                "patients."
            ),
            caution_note=(
                "⚠ Doses above 0.3 mg/kg/hr increase the risk of "
                "significant respiratory depression and ileus. Reserve "
                "higher rates for inpatient settings with active monitoring."
            ),
            note=(
                "Standard dog analgesia CRI: 0.1–0.4 mg/kg/hr (mid-range "
                "0.2). MLK-protocol default is 0.2 mg/kg/hr."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.05,
            max=0.1,
            caution_threshold=0.1,
            persistent_warning=(
                "Cats are more sensitive to opioid-induced dysphoria and "
                "excitation than dogs. Methadone, fentanyl, or "
                "hydromorphone are typically preferred over morphine for "
                "cat CRIs. If morphine is used in cats, use lower doses "
                "and watch closely for dysphoria, hyperthermia, and "
                "respiratory depression."
            ),
            caution_note=(
                "⚠ Morphine is rarely used as a CRI in cats. Consider "
                "methadone, fentanyl, or hydromorphone instead. If "
                "proceeding, stay at the low end of this range."
            ),
            note=(
                "Conservative cat range: 0.05–0.1 mg/kg/hr. Cats are "
                "more dysphoria-prone than dogs at standard mu-opioid "
                "doses."
            ),
        ),
    },
    concentration_presets=(
        ConcentrationPreset(
            100,
            "25 mg (5 mL of 5 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Standard prep for medium dogs at typical CRI doses.",
        ),
        ConcentrationPreset(
            200,
            "50 mg (10 mL of 5 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "More concentrated for larger dogs or higher CRI rates.",
        ),
        ConcentrationPreset(
            50,
            "12.5 mg (2.5 mL of 5 mg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Lower concentration for small patients or low-rate infusions.",
        ),
    ),
    default_concentration_ug_per_ml=100.0,
    titration_ladder=(0.1, 0.15, 0.2, 0.25, 0.3, 0.4),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI loading dose",
            description=(
                "0.1–0.3 mg/kg IV slowly (give over 5+ minutes to minimize "
                "histamine release and hypotension) before starting the CRI."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # Dogs only; cat loading doses are typically skipped
                # or replaced with a different opioid given dysphoria
                # concerns; surfacing a dog-only loading panel signals
                # this without requiring extra prose.
                Species.DOG: (0.1, 0.3),
            },
            note=(
                "Give slowly. Rapid IV morphine causes histamine release "
                "with hypotension and bronchoconstriction. Many "
                "practitioners give morphine IM rather than IV for the "
                "loading dose."
            ),
        ),
    ),
    dilution_note=(
        "Compatible with 0.9% NaCl, 5% dextrose, LRS. Preservative-free "
        "morphine should be used for epidural / intrathecal routes; "
        "standard preservative-containing morphine is fine for IV CRI. "
        "Stock 5 mg/mL is most common; 15 mg/mL also exists, verify the "
        "vial label before drawing."
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight, dose, and bag concentration. The calculator returns the pump rate to deliver that dose at the chosen concentration. Default prep is 100 µg/mL (25 mg morphine in a 250 mL bag); presets cover 50–200 µg/mL across patient sizes.",
        "After you compute, the result panel shows a loading-dose panel: 0.1–0.3 mg/kg IV given slowly over 5+ minutes before starting the CRI. Many practitioners give the load IM rather than IV to avoid histamine release.",
        "Pure µ-opioid agonist. Watch for respiratory depression, sedation, panting, and GI ileus at higher rates. In cats, dysphoria is more likely than in dogs at standard µ-opioid doses; methadone, fentanyl, or hydromorphone are typically preferred.",
    ),
    mechanism_summary=(
        "Pure µ-opioid agonist. Longer-duration and slower-onset than "
        "fentanyl; provides steady analgesia for postoperative and "
        "inpatient use. Histamine release on rapid IV injection; give "
        "boluses slowly. Dose-dependent respiratory depression, "
        "sedation, panting, and GI hypomotility. DEA Schedule II "
        "controlled substance."
    ),
    indications_summary=(
        "Moderate-to-severe acute pain in dogs: postoperative, "
        "perioperative, neoplastic, soft-tissue trauma, peritonitis, "
        "pancreatitis. MLK multi-modal protocol uses morphine as the "
        "opioid backbone. Less favored in cats due to dysphoria. "
        "Methadone, fentanyl, or hydromorphone are typically preferred."
    ),
    catalog_blurb="Pure µ-opioid CRI for moderate-to-severe acute pain in dogs (cautious cat dosing).",
    sources=(
        Source(
            citation=(
                "Plumb DC. Plumb's Veterinary Drugs, morphine monograph "
                "(current edition); sections used: Dosages (dogs and cats), "
                "Prescriber Highlights, Adverse Effects (histamine release, "
                "cat dysphoria), Drug Interactions. Lukasik V. 2015 WSAVA "
                "Proceedings. MLK-protocol default of 0.2 mg/kg/hr."
            ),
            reviewer=None,
        ),
    ),
)


# ---------------------------------------------------------------------------
# Dexmedetomidine, α₂-agonist analgesic CRI
# ---------------------------------------------------------------------------
# Sub-sedative α₂-agonist CRI for opioid-sparing analgesia (DMLK
# protocol uses 0.5 µg/kg/hr). Higher doses (>2 µg/kg/hr in dogs,
# >1 µg/kg/hr in cats) shift toward sedation rather than analgesia
# and require active CV monitoring. Cats are more sensitive to α₂
# effects than dogs; separate cat dose range (0.5–2.0 µg/kg/hr).
# Dexmedetomidine also slows ketamine metabolism; adjust ketamine
# downward when the two are combined.

DEXMEDETOMIDINE = CalculatorConfig(
    slug="dexmedetomidine",
    display_name="Dexmedetomidine CRI",
    short_name="Dex",
    category="Analgesia",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    stock_concentration_ug_per_ml=500.0,  # 0.5 mg/mL = 500 µg/mL (Dexdomitor)
    stock_concentration_display="0.5 mg/mL (500 µg/mL), Dexdomitor",
    dose_unit=DoseUnit.UG_PER_KG_PER_HR,
    default_dose=0.5,
    supports_target_pump_rate_mode=False,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.5,
            max=3.0,
            caution_threshold=2.0,
            persistent_warning=(
                "Dexmedetomidine CRI as analgesic adjunct. α₂-agonist; "
                "produces dose-dependent sedation, bradycardia, peripheral "
                "vasoconstriction (early-phase hypertension then late-phase "
                "hypotension), and opioid-sparing analgesia. Reduces "
                "ketamine metabolism; adjust ketamine downward when "
                "combined."
            ),
            caution_note=(
                "⚠ Doses above 2 µg/kg/hr move toward sedative rather "
                "than purely analgesic territory. Active cardiovascular "
                "monitoring required at higher rates; bradycardia and "
                "AV block are dose-related."
            ),
            note=(
                "Dog range: 0.5–3.0 µg/kg/hr. DMLK protocol uses "
                "0.5 µg/kg/hr (analgesic-only). Higher doses pull "
                "toward sedation."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.5,
            max=2.0,
            caution_threshold=1.0,
            persistent_warning=(
                "Cats are more sensitive to α₂-agonist effects than dogs. "
                "Expect more pronounced bradycardia and sedation at "
                "comparable doses. Start at the low end."
            ),
            caution_note=(
                "⚠ Cat doses above 1 µg/kg/hr produce significant "
                "sedation and cardiovascular effects. Reserve for "
                "monitored settings."
            ),
            note=(
                "Cat range is conservative: 0.5–2.0 µg/kg/hr. Cats "
                "metabolize dex more slowly and respond more dramatically "
                "than dogs."
            ),
        ),
    },
    concentration_presets=(
        ConcentrationPreset(
            4,
            "1 mg (2 mL of 500 µg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "Standard analgesic-CRI dilution for dogs and cats.",
        ),
        ConcentrationPreset(
            2,
            "500 µg (1 mL of 500 µg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "More dilute prep for small patients on low doses.",
        ),
        ConcentrationPreset(
            8,
            "2 mg (4 mL of 500 µg/mL stock) into a 250 mL bag of 0.9% NaCl",
            "More concentrated for larger dogs or higher rates.",
        ),
    ),
    default_concentration_ug_per_ml=4.0,
    titration_ladder=(0.5, 1.0, 1.5, 2.0, 3.0),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI loading dose (dogs)",
            description="1–3 µg/kg IV slowly over 1–2 minutes.",
            matches_cri_rate=False,
            dose_per_kg={
                Species.DOG: (1.0, 3.0),
            },
            note=(
                "Skip the loading dose if the patient is already sedated "
                "(e.g., dex was part of premedication). Slow IV "
                "administration minimizes the early hypertensive phase."
            ),
        ),
        LoadingDose(
            label="Pre-CRI loading dose (cats)",
            description="1–2 µg/kg IV slowly over 1–2 minutes.",
            matches_cri_rate=False,
            dose_per_kg={
                Species.CAT: (1.0, 2.0),
            },
            note=(
                "Cats are more sensitive to α₂ effects; stay at the "
                "low end and monitor for bradycardia."
            ),
        ),
    ),
    dilution_note=(
        "Compatible with 0.9% NaCl, 5% dextrose, LRS. 0.5 mg/mL "
        "(Dexdomitor) is the standard veterinary stock. Dexmedetomidine "
        "HCl human-labeled stocks at 100 µg/mL also exist; verify the "
        "label before drawing."
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight, dose, and bag concentration. The calculator returns the pump rate to deliver that dose at the chosen concentration. Default prep is 4 µg/mL (1 mg dex in a 250 mL bag); presets cover 2–8 µg/mL across patient sizes.",
        "After you compute, the result panel shows separate loading-dose panels for dogs (1–3 µg/kg IV) and cats (1–2 µg/kg IV). Skip the loading dose if the patient is already sedated from premedication.",
        "α₂-agonist. Watch for bradycardia, early hypertension followed by hypotension, and dose-dependent sedation. Cat doses are more conservative because cats are more α₂-sensitive than dogs. When combined with ketamine, adjust ketamine downward; dex slows its metabolism.",
    ),
    mechanism_summary=(
        "Selective α₂-agonist. Produces dose-dependent sedation, "
        "analgesia, bradycardia, peripheral vasoconstriction (early-phase "
        "hypertension followed by late-phase hypotension), and an "
        "opioid-sparing effect. Slows hepatic metabolism of co-"
        "administered drugs, notably ketamine."
    ),
    indications_summary=(
        "Sub-sedative α₂-agonist CRI for opioid-sparing analgesia in "
        "dogs and cats. DMLK multi-modal protocol uses dexmedetomidine "
        "0.5 µg/kg/hr alongside morphine, lidocaine, and ketamine. "
        "Higher rates (>2 µg/kg/hr in dogs, >1 µg/kg/hr in cats) shift "
        "toward sedation rather than analgesia and assume active "
        "cardiovascular monitoring."
    ),
    catalog_blurb="α₂-agonist CRI for opioid-sparing analgesia in dogs and cats.",
    sources=(
        Source(
            citation=(
                "Plumb DC. Plumb's Veterinary Drugs, dexmedetomidine "
                "monograph (current edition); sections used: Dosages "
                "(dogs and cats), Adverse Effects, Drug Interactions, "
                "Prescriber Highlights. DMLK protocol via Lukasik V. "
                "2015 WSAVA Proceedings."
            ),
            reviewer=None,
        ),
    ),
)


# ---------------------------------------------------------------------------
# Metoclopramide, antiemetic / prokinetic CRI
# ---------------------------------------------------------------------------
# First CRI in the catalog with mg/kg/hr dose unit (the others run in
# µg/kg/min or µg/kg/hr). Standard antiemetic CRI per Plumb's is
# 0.04–0.09 mg/kg/hr (1–2 mg/kg/day). A separate higher-dose protocol
# for intraoperative laryngeal paralysis surgery uses 1 mg/kg IV
# loading dose + 1 mg/kg/hr intraop, dropping to 0.083 mg/kg/hr
# postoperatively for a 24-hr total treatment. The lar par protocol
# is dog-only in Plumb's (not listed for cats).
#
# Plumb's does NOT specify a cat CRI dose. The standard dog range is
# used as the conservative extrapolation, with strong warning that
# other antiemetics (ondansetron, maropitant) are preferred in cats
# and other prokinetics (cisapride) are preferred for prokinetic
# indication.

MIDAZOLAM = CalculatorConfig(
    slug="midazolam",
    display_name="Midazolam CRI",
    short_name="Midaz",
    category="Anesthesia & Sedation",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # Most common vet stock: 5 mg/mL × 5 mL vial = 25 mg total.
    # 1 mg/mL ampules also exist (less common). 50 mg/mL preservative-
    # free is occasionally used for compounding.
    stock_concentration_ug_per_ml=5000.0,
    stock_concentration_display="5 mg/mL (5 000 µg/mL), 5 mL vial (25 mg)",
    dose_unit=DoseUnit.MG_PER_KG_PER_HR,
    # Anchor at 0.25 mg/kg/hr, middle of the published sedation range
    # and a common starting point in ICU practice.
    default_dose=0.25,
    target_pump_rate_default_dose=0.25,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.1,
            max=0.5,
            persistent_warning=(
                "Sedative / anxiolytic / anticonvulsant CRI. Respiratory "
                "depression can be marked in patients with pre-existing "
                "pulmonary disease, opioid co-administration, or hepatic "
                "dysfunction (impaired clearance → accumulation). Maintain "
                "monitoring of respiratory rate, SpO₂, and level of "
                "consciousness. Prolonged infusions (> 24–48 hr) can "
                "produce physiologic dependence; taper rather than "
                "discontinue abruptly. Flumazenil reverses but may "
                "precipitate seizures in chronic benzodiazepine users."
            ),
            caution_threshold=0.5,
            caution_note=(
                "⚠ 0.5 mg/kg/hr is the published upper end of the "
                "sedation/anxiolysis range. Higher rates risk deeper "
                "sedation than intended, respiratory depression, and "
                "(in prolonged infusions) accumulation. Reassess the "
                "indication before exceeding; escalating in status "
                "epilepticus is reasonable; for ICU comfort, consider "
                "adding a second-class agent (alpha-2, opioid) instead "
                "of pushing midazolam higher."
            ),
            note=(
                "Sedation / anxiolysis CRI: 0.1–0.5 mg/kg/hr IV titrated "
                "to effect. Status epilepticus refractory to bolus "
                "benzodiazepines: 0.2 mg/kg IV loading, then 0.05–0.5 "
                "mg/kg/hr CRI titrated to seizure control."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.1,
            max=0.5,
            persistent_warning=(
                "Cats can show paradoxical excitement, disinhibition, or "
                "behavioral changes on benzodiazepines; observe response "
                "after the loading dose before committing to the CRI. "
                "Respiratory depression risk is the same as dogs, "
                "particularly with opioid co-administration. Hepatic "
                "lipidosis cats clear midazolam slowly; accumulation "
                "risk on prolonged infusions. Flumazenil reverses but "
                "may precipitate seizures in chronic users."
            ),
            # Lower caution threshold for cats; paradoxical excitement
            # and oversedation risk rise faster than in dogs.
            caution_threshold=0.3,
            caution_note=(
                "⚠ Above 0.3 mg/kg/hr in cats: paradoxical excitement, "
                "oversedation, and accumulation risk rise sharply. "
                "Reassess indication and consider switching to or "
                "combining with another sedative class (alpha-2 agonist, "
                "opioid) rather than pushing midazolam alone higher."
            ),
            note=(
                "Same published range as dogs (0.1–0.5 mg/kg/hr) for "
                "sedation/anxiolysis, but most cats achieve adequate "
                "effect at the lower end (0.1–0.3 mg/kg/hr). Status "
                "epilepticus dosing parallels dogs."
            ),
        ),
    },
    concentration_presets=(
        # Pump-precision-style tiers, sized for typical syringe-pump
        # workflow (50 mL syringe). Clinical goal: keep pump rate
        # ≥ 2 mL/hr at the typical 0.25 mg/kg/hr dose.
        #
        # For 20 kg patient × 0.25 mg/kg/hr = 5 mg/hr → 1 mg/mL prep
        # gives 5 mL/hr ✓
        # For 5 kg × 0.25 = 1.25 mg/hr → 0.5 mg/mL gives 2.5 mL/hr ✓
        # For 2 kg × 0.25 = 0.5 mg/hr → 0.2 mg/mL gives 2.5 mL/hr ✓
        #
        # Recipes assume a 50 mL syringe (most common ICU container)
        # filled with stock + diluent (0.9% NaCl or 5% dextrose, both
        # Plumb's-compatible).
        ConcentrationPreset(
            1000,  # 1 mg/mL
            "10 mL stock (2 × 5 mL vials, 50 mg total) into 40 mL of 0.9% NaCl or 5% dextrose, final volume 50 mL",
            "Concentrated preparation for patients ≥10 kg or where fluid load matters. Most common ICU prep for medium-to-large dogs.",
            weight_min_kg=10,
        ),
        ConcentrationPreset(
            500,  # 0.5 mg/mL
            "5 mL stock (1 vial, 25 mg) into 45 mL of 0.9% NaCl or 5% dextrose, final volume 50 mL",
            "Standard preparation for patients 3–10 kg. Uses one full vial of stock, straightforward to prepare and matches the most common dose range.",
            weight_min_kg=3,
            weight_max_kg=10,
        ),
        ConcentrationPreset(
            200,  # 0.2 mg/mL
            "2 mL stock (10 mg) into 48 mL of 0.9% NaCl or 5% dextrose, final volume 50 mL",
            "Dilute preparation for patients <3 kg or any patient at very low doses where the 0.5 mg/mL preparation would drop pump rate below 2 mL/hr.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=500.0,
    titration_ladder=(0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI sedation loading",
            description=(
                "IV slowly (over 30–60 sec) before starting the CRI. "
                "The loading dose establishes the effect quickly; the "
                "CRI maintains it. Skip the loading dose when titrating "
                "from a lighter sedation plane or when respiratory "
                "depression is a concern."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # Dogs: 0.1-0.3 mg/kg IV slowly. Plumb's, sedation
                # co-induction and pre-CRI loading.
                Species.DOG: (0.1, 0.3),
                # Cats: same range, but most achieve effect at the
                # lower end. Watch for paradoxical excitement after
                # the loading dose before starting the CRI.
                Species.CAT: (0.1, 0.3),
            },
            display_dose_unit="mg",
            note=(
                "If paradoxical excitement appears in a cat after the "
                "loading dose, abort the CRI and choose another "
                "sedative class."
            ),
        ),
        LoadingDose(
            label="Status epilepticus loading",
            description=(
                "For status refractory to initial diazepam or midazolam "
                "bolus therapy. May be repeated to a total dose of "
                "0.5 mg/kg before starting the CRI. Concurrent "
                "load-dose anticonvulsant (levetiracetam, phenobarbital) "
                "is typical; midazolam CRI bridges to therapeutic levels."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # Dogs and cats: 0.2-0.5 mg/kg IV bolus, may repeat.
                # Plumb's status epilepticus emergency dosing.
                Species.DOG: (0.2, 0.5),
                Species.CAT: (0.2, 0.5),
            },
            display_dose_unit="mg",
            note=(
                "Establish IV access and ensure airway / oxygen are "
                "available before bolus dosing; combination "
                "anticonvulsant therapy raises respiratory depression "
                "risk."
            ),
        ),
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight and the desired CRI dose. The calculator picks a concentration (1, 0.5, or 0.2 mg/mL) that keeps the pump in its accurate range (≥ 2 mL/hr for most syringe pumps).",
        "The recommended concentration shows a <strong>suggested</strong> tag that updates as you change the patient inputs. Click any tab to override; a notice will appear if your choice gives a pump rate outside the precision range.",
        "Two loading-dose scenarios are computed: <strong>pre-CRI sedation loading</strong> (0.1–0.3 mg/kg IV before starting the CRI) and <strong>status epilepticus loading</strong> (0.2–0.5 mg/kg IV bolus, may repeat).",
    ),
    dilution_note=(
        "Standard preparation is in a 50 mL syringe for syringe-pump "
        "delivery; the conventional ICU workflow for short-to-medium "
        "term sedation CRIs. For prolonged infusions (>24 hr) or "
        "concurrent IV fluid delivery, the same concentrations can be "
        "prepared in a 100 mL or 250 mL bag using proportionally more "
        "stock."
        "\n\n"
        "Carrier fluid: 0.9% NaCl and 5% dextrose are both compatible "
        "(Plumb's). Midazolam is incompatible with sodium bicarbonate, "
        "ranitidine, and most alkaline solutions; do not co-administer "
        "in the same line."
        "\n\n"
        "Photostability: midazolam is stable in standard ambient light. "
        "Refrigeration extends stability of compounded dilutions; "
        "discard syringe contents per facility policy (24 hours is a "
        "common cutoff for compounded benzodiazepine syringes)."
    ),
    mechanism_summary=(
        "Short-acting benzodiazepine. Binds the GABA_A receptor "
        "benzodiazepine site, enhancing GABA-mediated chloride conductance to "
        "produce dose-dependent anxiolysis, sedation, anterograde "
        "amnesia, anticonvulsant activity, and centrally mediated muscle "
        "relaxation. Water-soluble (unlike diazepam), so IV administration "
        "doesn't require propylene glycol vehicle. Onset 1–3 min IV; "
        "duration 30–60 min after single bolus, longer with CRI "
        "accumulation. Hepatic metabolism (CYP3A) with renal elimination "
        "of metabolites. Clearance is impaired in hepatic dysfunction."
    ),
    indications_summary=(
        "ICU sedation and anxiolysis CRI for dogs and cats. Used for "
        "patient comfort during mechanical ventilation, prolonged "
        "catheter "
        "or wound care, or recovery from major procedures. Status "
        "epilepticus management when seizures recur after initial "
        "bolus benzodiazepine therapy. Anesthetic MAC-sparing during "
        "inhalant anesthesia (combine with opioid for balanced "
        "anesthesia). Continuous respiratory monitoring required; "
        "particularly with opioid co-administration or pre-existing "
        "pulmonary compromise."
    ),
    catalog_blurb=(
        "Short-acting benzodiazepine CRI for ICU sedation, "
        "anxiolysis, and status epilepticus management."
    ),
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Midazolam monograph "
                "(current edition). Sections used: Prescriber "
                "Highlights, Uses/Indications, Pharmacology/Actions, "
                "Pharmacokinetics, Contraindications/Precautions/"
                "Warnings, Adverse Effects, Dosages (dogs/cats: "
                "sedation, anxiolysis, status epilepticus, "
                "anesthetic premedication), Compatibility/"
                "Compounding Considerations, Dosage Forms/Regulatory "
                "Status."
            ),
            reviewer=None,
        ),
    ),
)

MAGNESIUM_SULFATE = CalculatorConfig(
    slug="magnesium-sulfate",
    display_name="Magnesium Sulfate CRI",
    short_name="MgSO4",
    category="Cardiology",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # 50% magnesium sulfate stock = 500 mg/mL = 500 000 µg/mL.
    # Plumb's notes 4.06 mEq elemental magnesium per mL of the 50%
    # solution (equivalent to 8.12 mEq/g of the MgSO4·7H2O salt;
    # the calculator works in mg of salt, not mEq, to match the most
    # common veterinary CRI workflow).
    stock_concentration_ug_per_ml=500000.0,
    stock_concentration_display=(
        "50% magnesium sulfate (500 mg/mL, 4.06 mEq/mL), "
        "50 mL multi-dose vial"
    ),
    dose_unit=DoseUnit.MG_PER_KG_PER_HR,
    # 25 mg/kg/hr, middle of the Silverstein SACCM published range,
    # common starting point for ventricular arrhythmia management.
    default_dose=25.0,
    target_pump_rate_default_dose=25.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=5.0,
            max=50.0,
            persistent_warning=(
                "Watch for hypotension with rapid administration; "
                "if BP drops, slow or pause the infusion. Continuous "
                "ECG monitoring required (AV-block risk, particularly "
                "with concurrent calcium-channel blockers or digoxin). "
                "Renal failure causes magnesium accumulation; use very "
                "cautiously, monitor serum magnesium if available. "
                "Hypermagnesemia signs: hyporeflexia (loss of patellar "
                "reflex is the earliest objective sign), respiratory "
                "depression, cardiac arrest at extreme levels."
            ),
            caution_threshold=30.0,
            caution_note=(
                "⚠ Above 30 mg/kg/hr, cumulative daily dose can exceed "
                "comfortable margins (24 hr × 30 = 720 mg/kg/day); "
                "reassess if running longer than 4–6 hours at this rate. "
                "Hypotension and AV-conduction effects also become more "
                "pronounced. Consider adding or substituting a "
                "complementary antiarrhythmic (lidocaine, procainamide) "
                "rather than escalating magnesium alone."
            ),
            note=(
                "Initial CRI 25 mg/kg/hr after the loading dose, "
                "titrated 5–50 mg/kg/hr to arrhythmia control. "
                "Continue 24–48 hr after restoration of normal "
                "rhythm; taper over 24 hr."
            ),
        ),
        Species.CAT: DoseRange(
            min=5.0,
            max=50.0,
            persistent_warning=(
                "Same monitoring concerns as dogs: hypotension, "
                "AV-conduction risk, renal accumulation. Cats have "
                "sparser published CRI data; lower-end dosing and "
                "shorter infusion durations are reasonable. Watch for "
                "loss of patellar reflex as an early hypermagnesemia "
                "sign. Avoid concurrent calcium-channel blockers."
            ),
            caution_threshold=25.0,
            caution_note=(
                "⚠ Cats: less published CRI data than dogs. Above "
                "25 mg/kg/hr, plan for explicit reassessment within "
                "2–4 hours. Cumulative-dose and hypotension margins "
                "narrow faster than in dogs."
            ),
            note=(
                "Same published range as dogs (5–50 mg/kg/hr), but "
                "feline use stays at the lower end (5–25 mg/kg/hr) "
                "given the sparser feline literature."
            ),
        ),
    },
    concentration_presets=(
        # Pump-precision tiers prepared by diluting the 50% stock
        # (500 mg/mL) into a 50 mL syringe with 0.9% NaCl or 5% dextrose.
        ConcentrationPreset(
            100000,  # 100 mg/mL
            "10 mL of 50% stock (5 000 mg total) into 40 mL of 0.9% NaCl or 5% dextrose, final volume 50 mL",
            "Concentrated preparation for patients ≥10 kg. Most common ICU prep for medium-to-large dogs at the typical 25 mg/kg/hr dose.",
            weight_min_kg=10,
        ),
        ConcentrationPreset(
            50000,  # 50 mg/mL
            "5 mL of 50% stock (2 500 mg total) into 45 mL of 0.9% NaCl or 5% dextrose, final volume 50 mL",
            "Standard preparation for patients 3–10 kg. The textbook 1:10 dilution of the 50% stock.",
            weight_min_kg=3,
            weight_max_kg=10,
        ),
        ConcentrationPreset(
            25000,  # 25 mg/mL
            "2.5 mL of 50% stock (1 250 mg total) into 47.5 mL of 0.9% NaCl or 5% dextrose, final volume 50 mL",
            "Dilute preparation for patients <3 kg or any patient at very low doses where the 50 mg/mL preparation would drop pump rate below 2 mL/hr.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=50000.0,
    titration_ladder=(5, 10, 15, 20, 25, 30, 40, 50),
    loading_doses=(
        LoadingDose(
            label="Ventricular arrhythmia loading",
            description=(
                "For ventricular tachycardia, torsades de pointes, or "
                "refractory VPCs: give IV slowly over 5–10 minutes "
                "before starting the CRI. Slower administration (closer "
                "to 10 min) reduces hypotension risk. Skip the loading "
                "dose if hypotension is already present at baseline; "
                "start at the lower end of the CRI range instead."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # Dogs and cats: 25–50 mg/kg IV slowly over 5–10 min.
                # Silverstein SACCM, Plumb's-compatible.
                Species.DOG: (25.0, 50.0),
                Species.CAT: (25.0, 50.0),
            },
            display_dose_unit="mg",
            note=(
                "Monitor BP every 1–2 min during the loading dose. "
                "If MAP drops by more than 20% from baseline, slow the "
                "infusion or pause until pressure recovers."
            ),
        ),
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight and the desired CRI dose. The calculator picks a concentration (100, 50, or 25 mg/mL) that keeps the pump in its accurate range (≥ 2 mL/hr for most syringe pumps).",
        "The recommended concentration shows a <strong>suggested</strong> tag that updates as you change the patient inputs. Click any tab to override.",
        "Loading dose for ventricular arrhythmia (25–50 mg/kg IV over 5–10 min) is shown above the CRI maintenance rate. Slow administration minimizes the hypotension risk.",
    ),
    dilution_note=(
        "Standard preparation: dilute the 50% magnesium sulfate stock "
        "(500 mg/mL) into a 50 mL syringe with 0.9% NaCl or 5% dextrose. "
        "Both diluents are compatible. For longer-running infusions, "
        "the same concentrations can be prepared in 100 mL or 250 mL "
        "bags using proportionally more stock."
        "\n\n"
        "Compatibility caveats: magnesium sulfate is incompatible with "
        "many calcium-containing solutions (precipitation risk) and "
        "with sodium bicarbonate. Do not co-administer in the same line "
        "with these; flush the line before and after if a Y-site is "
        "unavoidable."
        "\n\n"
        "Monitoring: serum magnesium 4–6 hours after starting the CRI "
        "where available, then every 12–24 hours. Patellar reflex check "
        "as an objective hypermagnesemia surveillance test; loss of "
        "patellar reflex is the earliest sign and prompts immediate "
        "dose reduction or hold."
    ),
    mechanism_summary=(
        "Physiologic calcium antagonist. Competes with calcium at "
        "voltage-gated calcium channels (slow inward current), NMDA "
        "receptors, and ATPase binding sites. In cardiac tissue: "
        "slows AV conduction, prolongs refractoriness, decreases "
        "automaticity, the mechanism underlying its utility in VT, "
        "torsades de pointes, and refractory VPCs. Also stabilizes "
        "neuromuscular function (loss of patellar reflex with elevated "
        "serum levels) and produces mild bronchodilation. Renal "
        "elimination, with accumulation in renal failure."
    ),
    indications_summary=(
        "Refractory ventricular arrhythmias (VPCs, ventricular "
        "tachycardia, torsades de pointes) in dogs and cats, "
        "particularly when hypomagnesemia is documented or suspected. "
        "Generally chosen after standard antiarrhythmic options "
        "(lidocaine for VT, procainamide) have not produced adequate "
        "control. Also used for severe documented hypomagnesemia "
        "replacement (CRI preferred over bolus for severe deficiency). "
        "Adjunct for refractory bronchospasm in severe asthma is "
        "described but less common in veterinary practice. Continuous "
        "ECG and BP monitoring required."
    ),
    catalog_blurb=(
        "Physiologic calcium antagonist for refractory ventricular "
        "arrhythmias and severe hypomagnesemia in dogs and cats."
    ),
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Magnesium Sulfate monograph "
                "(current edition). Sections used: Uses/Indications, "
                "Pharmacology/Actions, Pharmacokinetics, "
                "Contraindications/Precautions/Warnings, Adverse "
                "Effects, Dosages, Compatibility/Compounding."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Hopper K. Magnesium. In: Silverstein DC, Hopper K, eds. "
                "Small Animal Critical Care Medicine. 3rd ed. St. "
                "Louis, MO: Elsevier; 2023. Supports the CRI range "
                "(5–50 mg/kg/hr) and loading-dose protocol for "
                "refractory ventricular arrhythmias."
            ),
            reviewer=None,
        ),
    ),
)

ESMOLOL = CalculatorConfig(
    slug="esmolol",
    display_name="Esmolol CRI",
    short_name="Esmolol",
    category="Cardiology",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # Working stock: 10 mg/mL premix (Brevibloc Premixed: 100 mg/10 mL
    # or 2 500 mg/250 mL premixed bag). 250 mg/mL concentrated vial
    # also exists but requires dilution to 10 mg/mL before use; the
    # premixed bag is the typical ICU starting point.
    stock_concentration_ug_per_ml=10000.0,
    stock_concentration_display=(
        "10 mg/mL premix (10 000 µg/mL); 250 mg/mL concentrate also "
        "available; dilute to 10 mg/mL before use"
    ),
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    # 50 µg/kg/min, common starting maintenance after the loading
    # dose. Published Plumb's range: 25–200 µg/kg/min.
    default_dose=50.0,
    target_pump_rate_default_dose=50.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=25.0,
            max=200.0,
            persistent_warning=(
                "β-blocker; caution in patients with myocardial "
                "dysfunction (DCM, advanced MMVD): can worsen "
                "contractility. Watch for hypotension and bradycardia "
                "; pause the infusion if MAP drops > 20% from baseline "
                "or heart rate falls below an acceptable threshold for "
                "the patient. β1-selectivity is preserved at low-mid "
                "doses but lost at higher rates → bronchospasm risk "
                "rises at the upper end of the range. Additive AV-block "
                "and negative inotropy with calcium-channel blockers "
                "(diltiazem, verapamil); avoid concurrent use or "
                "monitor very closely. NEVER use as monotherapy in "
                "suspected pheochromocytoma without prior alpha-"
                "blockade; risk of unopposed alpha-mediated "
                "hypertensive crisis."
            ),
            caution_threshold=150.0,
            caution_note=(
                "⚠ Above 150 µg/kg/min: β1-selectivity diminishes "
                "(β2 bronchospasm risk rises) and hypotension margins "
                "narrow. Reassess indication before exceeding. If rate "
                "control is the primary goal, adding diltiazem rather "
                "than pushing esmolol higher is often the better "
                "strategy; additive AV-block effects can be desirable "
                "here when carefully monitored."
            ),
            note=(
                "Initial CRI 50 µg/kg/min after the loading dose, "
                "titrated 25–200 µg/kg/min to heart-rate or BP target. "
                "Ultra-short half-life (~9 min) means effect resolves "
                "within 10–20 minutes of stopping; highly titratable. "
                "RBC-esterase metabolism: no hepatic or renal "
                "dose adjustment needed."
            ),
        ),
        Species.CAT: DoseRange(
            min=25.0,
            max=200.0,
            persistent_warning=(
                "β-blocker; HCM cats may benefit from rate control "
                "(improves diastolic filling), but cats with asthma "
                "are at higher bronchospasm risk, particularly at "
                "doses where β1-selectivity is lost. Watch for "
                "hypotension and bradycardia; pause if MAP drops > 20% "
                "from baseline. Same monotherapy caveat in suspected "
                "pheochromocytoma; never without prior alpha-blockade. "
                "Additive AV-block with calcium-channel blockers."
            ),
            caution_threshold=150.0,
            caution_note=(
                "⚠ Cats: β1-selectivity loss above 150 µg/kg/min "
                "raises bronchospasm risk; particularly concerning in "
                "asthmatic patients. Hypotension margins also narrow "
                "faster than in dogs given typical cat body size and "
                "the relative dosing intensity."
            ),
            note=(
                "Same published range as dogs (25–200 µg/kg/min). "
                "Particularly useful in HCM cats for rate control when "
                "atrial fibrillation or sinus tachycardia compromises "
                "diastolic filling."
            ),
        ),
    },
    concentration_presets=(
        # Pump-precision tiers. Esmolol's working stock is the 10 mg/mL
        # premix; tiers represent direct premix use vs progressive
        # syringe-pump dilution.
        ConcentrationPreset(
            10000,  # 10 mg/mL = stock premix directly
            "Use the 10 mg/mL premixed bag directly via a volumetric IV pump; no dilution needed",
            "Direct use of the premixed bag for patients ≥15 kg. Lowest preparation effort; recommended when a volumetric IV pump is in use and patient size keeps pump rate in the precision range.",
            weight_min_kg=15,
        ),
        ConcentrationPreset(
            5000,  # 5 mg/mL, 1:1 dilution
            "Draw 25 mL of 10 mg/mL premix and dilute with 25 mL of 0.9% NaCl or 5% dextrose into a 50 mL syringe (1:1 dilution); deliver via syringe pump",
            "Standard 1:1 dilution for patients 3–15 kg. Matches typical syringe-pump workflow and keeps the pump rate in the precision range for medium patients.",
            weight_min_kg=3,
            weight_max_kg=15,
        ),
        ConcentrationPreset(
            2000,  # 2 mg/mL, 1:4 dilution
            "Draw 10 mL of 10 mg/mL premix and dilute with 40 mL of 0.9% NaCl or 5% dextrose into a 50 mL syringe (1:4 dilution); deliver via syringe pump",
            "Dilute preparation for cats and very small dogs (<3 kg) or any patient at very low doses where the 5 mg/mL preparation would drop pump rate below 2 mL/hr.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=5000.0,
    titration_ladder=(25, 50, 75, 100, 125, 150, 200),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI rate-control loading",
            description=(
                "IV slowly over 1 minute before starting the CRI. The "
                "loading dose establishes the effect quickly (within "
                "5 minutes of administration); the CRI maintains it. "
                "Can be repeated to 500 µg/kg total in 50–100 µg/kg "
                "increments if initial response is inadequate. Skip "
                "the loading dose when titrating from a lighter "
                "blockade or when hypotension margins are tight at "
                "baseline."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # 50-500 µg/kg IV over 1 min. Plumb's. Same range
                # for both species.
                Species.DOG: (50.0, 500.0),
                Species.CAT: (50.0, 500.0),
            },
            display_dose_unit="µg",
            note=(
                "Monitor heart rate and BP closely during the loading "
                "bolus; most of the acute hypotension risk lives in "
                "the first minute of administration. Pause and "
                "reassess if MAP drops by more than 20% from baseline."
            ),
        ),
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight and the desired CRI dose. The calculator picks a concentration (10, 5, or 2 mg/mL) that keeps the pump in its accurate range. The 10 mg/mL premix is used directly for larger patients; smaller patients get progressive dilution into a 50 mL syringe.",
        "The recommended concentration shows a <strong>suggested</strong> tag that updates as you change the patient inputs.",
        "Loading dose (50–500 µg/kg IV over 1 min) is shown above the CRI maintenance rate. Most of the acute hypotension risk concentrates in the loading bolus; give slowly and reassess before starting the CRI.",
    ),
    dilution_note=(
        "Stock: the 10 mg/mL premixed bag (Brevibloc Premixed: 100 mg/"
        "10 mL bag or 2 500 mg/250 mL bag) is the typical ICU starting "
        "point. The 250 mg/mL concentrated vial also exists but must "
        "be diluted to 10 mg/mL (or lower) before use; the "
        "manufacturer's recommended dilution is 25 mL of concentrate "
        "into 250 mL of 0.9% NaCl or 5% dextrose."
        "\n\n"
        "Compatibility: 0.9% NaCl, 5% dextrose, and lactated Ringer's "
        "are all compatible. Avoid mixing in the same line with sodium "
        "bicarbonate (precipitation risk)."
        "\n\n"
        "Storage: refrigerate the diluted product if not used "
        "immediately; per the manufacturer, the diluted solution is "
        "stable for 24 hours at room temperature and longer "
        "refrigerated. Discard if any particulate or discoloration is "
        "visible."
    ),
    mechanism_summary=(
        "Selective β1-adrenergic blocker with ultra-short half-life "
        "(~9 minutes). Metabolized by erythrocyte esterases, "
        "independent of hepatic or renal function, and safe in compromise "
        "of either. Onset 1–2 min IV; full effect within 5–10 min; "
        "offset 10–20 min after stopping, making it among the most titratable "
        "IV cardioactive drugs available. β1-selectivity is preserved "
        "at low-mid doses but is lost at higher rates (becomes "
        "nonselective with β2 effects on airway smooth muscle)."
    ),
    indications_summary=(
        "Ultra-short-acting β-blocker CRI for supraventricular "
        "tachyarrhythmias (SVT, atrial fibrillation / atrial flutter "
        "rate control), perioperative tachycardia or hypertension, "
        "thyrotoxic crisis (cats), and as a \"trial of beta-blockade\" "
        "before committing to longer-acting oral agents. Sometimes "
        "used in pheochromocytoma management AFTER alpha-blockade is "
        "established, NEVER as monotherapy. Continuous ECG, BP, and "
        "heart-rate monitoring required."
    ),
    catalog_blurb=(
        "Ultra-short-acting β1-blocker for titratable rate control in "
        "SVT, A-fib, and perioperative tachycardia."
    ),
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Esmolol Hydrochloride "
                "monograph (current edition). Sections used: "
                "Prescriber Highlights, Uses/Indications, Pharmacology/"
                "Actions, Pharmacokinetics, Contraindications/"
                "Precautions/Warnings, Adverse Effects, Dosages "
                "(loading + maintenance CRI), Compatibility/Compounding "
                "Considerations, Dosage Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Côté E, MacDonald KA, Meurs KM, Sleeper MM, eds. "
                "Feline Cardiology. Wiley-Blackwell; 2011. Supports "
                "esmolol's use in HCM cats for rate control and the "
                "specific monitoring concerns around bronchospasm at "
                "higher doses."
            ),
            reviewer=None,
        ),
    ),
)

LIDOCAINE = CalculatorConfig(
    slug="lidocaine-antiarrhythmic",
    # Display name explicitly carries the antiarrhythmic indication to
    # distinguish from the existing analgesia-focused /lidocaine
    # custom-module calculator (dog-only, 1.5–3 mg/kg/hr range covering
    # MLK and standalone analgesic CRI use). The two coexist as peer
    # routes: different indications, different dose ranges, different
    # safety surface.
    display_name="Lidocaine CRI · Antiarrhythmic",
    short_name="Lido · AA",
    category="Cardiology",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # 2% lidocaine = 20 mg/mL, the most common veterinary stock.
    # 20 mL multi-dose vial = 400 mg total. 1% (10 mg/mL) also exists.
    stock_concentration_ug_per_ml=20000.0,
    stock_concentration_display=(
        "2% lidocaine (20 mg/mL, 20 000 µg/mL), "
        "20 mL multi-dose vial (400 mg per vial)"
    ),
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    # 50 µg/kg/min, typical dog starting maintenance after the
    # loading bolus. Cats land at the lower end of their range.
    default_dose=50.0,
    target_pump_rate_default_dose=50.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=25.0,
            max=80.0,
            persistent_warning=(
                "Class IB antiarrhythmic. Continuous ECG monitoring "
                "required. Watch for CNS toxicity (muscle tremors, "
                "facial twitches, ataxia, seizures) and "
                "cardiovascular toxicity (hypotension, AV block, "
                "negative inotropy). Reduced clearance in hepatic "
                "dysfunction and in severe heart failure (decreased "
                "hepatic blood flow); accumulation risk on prolonged "
                "infusions. If tremors or other CNS signs develop, "
                "pause the infusion immediately and reassess."
            ),
            caution_threshold=75.0,
            caution_note=(
                "⚠ Above 75 µg/kg/min, CNS and cardiovascular toxicity "
                "risk rises sharply. Reassess indication before "
                "exceeding. If VT persists at high lidocaine doses, "
                "second-line antiarrhythmics (procainamide, "
                "amiodarone, magnesium) are usually a better strategy "
                "than escalating lidocaine alone."
            ),
            note=(
                "Initial CRI 25–50 µg/kg/min after the loading dose, "
                "titrated 25–80 µg/kg/min to arrhythmia control. "
                "Plumb's published range. Continue 24–48 hr after "
                "rhythm stabilization, then taper. Hepatic metabolism "
                "(CYP-dependent); the analgesic-indication lidocaine "
                "calculator at /lidocaine operates at different dose "
                "ranges (1.5–3 mg/kg/hr) for pain management."
            ),
        ),
        Species.CAT: DoseRange(
            min=10.0,
            max=40.0,
            # Cat-specific warning is intentionally strong; lidocaine
            # CNS / CV toxicity in cats can be severe and is reached
            # at much lower doses than in dogs. Many cardiologists
            # avoid CRI in cats entirely; if used, the threshold for
            # toxicity is much lower than the published "upper limit"
            # might suggest. The warning emphasizes this.
            persistent_warning=(
                "⚠ CATS ARE MARKEDLY MORE SENSITIVE to lidocaine "
                "toxicity than dogs; impaired hepatic clearance "
                "produces drug accumulation at much lower CRI rates. "
                "Many cardiologists prefer to avoid lidocaine CRI in "
                "cats entirely, choosing alternatives (sotalol, "
                "atenolol, magnesium for refractory VT). If lidocaine "
                "is used, the threshold for CNS toxicity (tremors, "
                "seizures, profound depression) and cardiovascular "
                "depression is reached at much lower rates than in "
                "dogs. Start at the lower end (10 µg/kg/min), "
                "reassess every 30–60 minutes, and pause immediately "
                "at any sign of toxicity. Continuous ECG monitoring "
                "is required throughout."
            ),
            caution_threshold=20.0,
            caution_note=(
                "⚠ Above 20 µg/kg/min in cats, the toxicity margin "
                "narrows substantially. Cats running above this rate "
                "for more than 2–4 hours have a meaningfully elevated "
                "risk of CNS and cardiovascular toxicity. Reassess "
                "indication; alternatives (magnesium, sotalol once "
                "transitionable) are often preferable to pushing "
                "lidocaine higher in a cat."
            ),
            note=(
                "Cat range 10–40 µg/kg/min, much lower than the dog "
                "range. Use at the lower end and for the shortest "
                "duration that achieves rhythm stabilization. Many "
                "feline cardiologists prefer alternatives entirely "
                "given the toxicity profile."
            ),
        ),
    },
    concentration_presets=(
        # Pump-precision tiers prepared by diluting 2% (20 mg/mL)
        # stock into a 50 mL syringe with 0.9% NaCl or 5% dextrose.
        ConcentrationPreset(
            20000,  # 20 mg/mL, undiluted 2% stock
            "Use the 2% (20 mg/mL) stock directly in a 50 mL syringe via syringe pump; no dilution needed",
            "Direct use of stock for patients ≥15 kg. Lowest preparation effort; recommended when pump rate stays in the precision range without dilution.",
            weight_min_kg=15,
        ),
        ConcentrationPreset(
            10000,  # 10 mg/mL, 1:1 dilution
            "Draw 25 mL of 2% stock and dilute with 25 mL of 0.9% NaCl or 5% dextrose into a 50 mL syringe (1:1 dilution)",
            "Standard 1:1 dilution for patients 3–15 kg. Matches typical syringe-pump workflow.",
            weight_min_kg=3,
            weight_max_kg=15,
        ),
        ConcentrationPreset(
            4000,  # 4 mg/mL, 1:4 dilution
            "Draw 10 mL of 2% stock and dilute with 40 mL of 0.9% NaCl or 5% dextrose into a 50 mL syringe (1:4 dilution)",
            "Dilute preparation for cats and very small dogs (<3 kg). Essential when the cat-specific lower dose range would drop pump rate below 2 mL/hr on more concentrated preparations.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=10000.0,
    titration_ladder=(10, 20, 25, 40, 50, 60, 75, 80),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI ventricular arrhythmia loading",
            description=(
                "IV slowly over 1–2 minutes before starting the CRI. "
                "DOG range: 2 mg/kg initial bolus; may repeat 1–2 "
                "mg/kg every 5–10 min to a total of 8 mg/kg if "
                "arrhythmia persists. CAT range: 0.25–0.75 mg/kg "
                "(MUCH lower than dogs); give very slowly and "
                "reassess between repeated boluses. Skip the loading "
                "dose if hypotension or AV block is already present "
                "at baseline; start at the lower end of the CRI range "
                "instead."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # Dogs: 2 mg/kg initial, may repeat to 8 mg/kg total.
                # The "initial bolus" range; repeat protocol covered
                # in the description text.
                Species.DOG: (2.0, 8.0),
                # Cats: 0.25-0.75 mg/kg, DRAMATICALLY lower than dogs.
                # This single field carries the species asymmetry.
                Species.CAT: (0.25, 0.75),
            },
            display_dose_unit="mg",
            note=(
                "The 4× species difference in loading dose is real, "
                "not a typo; cat hepatic clearance of lidocaine is "
                "dramatically slower. Watch for CNS signs (tremors, "
                "twitches, ataxia) during the bolus in both species, "
                "but particularly in cats."
            ),
        ),
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight, species, and the desired CRI dose. The calculator picks a concentration (20, 10, or 4 mg/mL) that keeps the pump in its accurate range.",
        "<strong>Cat dosing is markedly different from dogs</strong>; published range is 10–40 µg/kg/min vs 25–80 in dogs, with a much lower caution threshold given the cat-specific clearance differences. The calculator enforces species-specific ranges automatically once species is selected.",
        "Loading dose (2 mg/kg dogs, 0.25–0.75 mg/kg cats) is shown above the CRI maintenance rate. The species asymmetry in loading dose is real and must be respected; cat overdose can produce seizures, profound CNS depression, and cardiovascular collapse.",
    ),
    dilution_note=(
        "Stock: 2% lidocaine (20 mg/mL), 20 mL multi-dose vial = "
        "400 mg per vial. For CRI: dilute in 0.9% NaCl or 5% dextrose "
        "(both compatible). Larger patients can run the 2% stock "
        "directly via syringe pump; smaller patients need progressive "
        "dilution to keep pump rate in the precision range."
        "\n\n"
        "Use the PRESERVATIVE-FREE (\"plain\") 2% formulation, NOT "
        "lidocaine with epinephrine; the epinephrine-containing "
        "products are for local infiltration only and would produce "
        "unwanted systemic effects on IV infusion."
        "\n\n"
        "Compatibility: lidocaine is compatible with most IV fluids "
        "and many co-administered drugs. Avoid mixing in the same "
        "line with sodium bicarbonate (precipitation risk in some "
        "concentrations)."
    ),
    mechanism_summary=(
        "Class IB antiarrhythmic. Blocks voltage-gated sodium channels "
        "in cardiac tissue, preferentially during depolarization "
        "(use-dependent block). Suppresses ectopic ventricular "
        "activity and raises ventricular fibrillation threshold. "
        "Particularly effective for ventricular arrhythmias arising "
        "from myocardial ischemia, increased automaticity, and "
        "reperfusion. Onset 1–2 minutes IV; duration 10–20 minutes "
        "after stopping. Hepatic metabolism via CYP1A2 and CYP3A4. Clearance "
        "is reduced in hepatic dysfunction, severe heart "
        "failure (reduced hepatic blood flow), and on prolonged "
        "infusions. Cats: dramatically impaired clearance compared "
        "to dogs, with toxicity at much lower CRI rates."
    ),
    indications_summary=(
        "First-line CRI for sustained ventricular tachycardia, "
        "hemodynamically significant VPCs, and post-cardioversion VF "
        "prophylaxis in dogs. Limited and cautious use in cats given "
        "their markedly impaired clearance and increased toxicity "
        "sensitivity. Alternatives (sotalol, magnesium for "
        "refractory VT) are often preferred. Continuous ECG monitoring "
        "required. For the analgesic CRI indication in dogs (lower "
        "dose range, standalone or as part of MLK protocols), see "
        "/lidocaine."
    ),
    catalog_blurb=(
        "Class IB antiarrhythmic CRI for ventricular arrhythmias in "
        "dogs (cautious use in cats: markedly increased sensitivity)."
    ),
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Lidocaine HCl (Systemic) "
                "monograph (current edition). Sections used: "
                "Prescriber Highlights, Uses/Indications (separated "
                "antiarrhythmic vs analgesic indications), Pharmacology/"
                "Actions, Pharmacokinetics (species-asymmetric "
                "clearance), Contraindications/Precautions/Warnings "
                "(cat sensitivity emphasis), Adverse Effects, Dosages "
                "(species-specific loading + CRI ranges), Dosage "
                "Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Côté E, MacDonald KA, Meurs KM, Sleeper MM, eds. "
                "Feline Cardiology. Wiley-Blackwell; 2011. Documents "
                "the cat-specific lidocaine sensitivity and the "
                "alternatives (sotalol, magnesium) most feline "
                "cardiologists prefer over lidocaine CRI."
            ),
            reviewer=None,
        ),
    ),
)

FUROSEMIDE = CalculatorConfig(
    slug="furosemide",
    display_name="Furosemide CRI",
    short_name="Furosemide",
    category="Cardiology",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # Stock: 50 mg/mL injectable, 50 mL multi-dose vial (2 500 mg).
    # 10 mg/mL formulation also exists; the 50 mg/mL is most common.
    stock_concentration_ug_per_ml=50000.0,
    stock_concentration_display=(
        "50 mg/mL (50 000 µg/mL), 50 mL multi-dose vial (2 500 mg per vial)"
    ),
    dose_unit=DoseUnit.MG_PER_KG_PER_HR,
    # 0.5 mg/kg/hr, typical maintenance for refractory CHF in dogs,
    # middle of the Plumb's range. Cats commonly run at the lower end.
    default_dose=0.5,
    target_pump_rate_default_dose=0.5,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.25,
            max=2.0,
            persistent_warning=(
                "Loop diuretic with potent effects. Monitor "
                "electrolytes (Na, K, Mg, Cl) frequently; hypokalemia "
                "and hypomagnesemia are common at higher doses, and "
                "severe hypokalemia precipitates arrhythmias. "
                "Hypovolemia, prerenal azotemia, and hypotension are "
                "the principal risks; assess hydration status before "
                "starting and at intervals; pair with judicious IV "
                "fluid replacement as appropriate. Ototoxicity rises "
                "at high doses or with rapid bolus administration; "
                "CRI delivery reduces this risk versus intermittent "
                "bolus. Reduced absorption and activity in severe "
                "hypoalbuminemia. Concurrent nephrotoxic drugs "
                "(aminoglycosides, NSAIDs) amplify acute kidney "
                "injury risk."
            ),
            caution_threshold=1.0,
            caution_note=(
                "⚠ Above 1 mg/kg/hr, electrolyte derangements "
                "(hypokalemia, hypomagnesemia) and prerenal azotemia "
                "risk rise sharply. Reassess electrolytes and "
                "creatinine every 2–4 hours. Above 1.5 mg/kg/hr, "
                "escalate monitoring to every 1–2 hours and consider "
                "sequential nephron blockade (add a second diuretic "
                "class such as thiazide or spironolactone) rather "
                "than pushing furosemide alone."
            ),
            note=(
                "Initial CRI 0.25–0.5 mg/kg/hr after the loading bolus, "
                "titrated 0.25–2 mg/kg/hr to urine-output and clinical "
                "response. Plumb's published range. Reassess fluid "
                "status, electrolytes, and BUN/creatinine every 4–6 "
                "hours during the infusion."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.25,
            max=1.0,
            persistent_warning=(
                "Loop diuretic. Cats are MORE PRONE to dehydration, "
                "prerenal azotemia, and hypokalemia at any given "
                "diuretic dose compared to dogs; use conservative "
                "dosing, monitor hydration and electrolytes more "
                "frequently. Standard cat CRI range is lower (0.25–1 "
                "mg/kg/hr vs the dog 0.25–2 range). Hypokalemia in "
                "cats can precipitate cardiac arrhythmias and is "
                "particularly concerning in HCM cats already at "
                "elevated risk. Ototoxicity, hypoalbuminemia, and "
                "nephrotoxic-drug interactions apply equally to cats."
            ),
            caution_threshold=0.75,
            caution_note=(
                "⚠ Cats: above 0.75 mg/kg/hr the dehydration and "
                "electrolyte-derangement risk rises substantially. "
                "Reassess hydration, electrolytes, and creatinine "
                "every 2–4 hours. Consider sequential nephron blockade "
                "(adding spironolactone or thiazide) rather than "
                "pushing furosemide higher in a cat."
            ),
            note=(
                "Cat range 0.25–1 mg/kg/hr, more conservative than "
                "dogs. Most feline CHF patients respond at the lower "
                "end (0.25–0.5 mg/kg/hr). Plumb's published range. "
                "Frequent reassessment essential; cats decompensate "
                "from dehydration faster than dogs."
            ),
        ),
    },
    concentration_presets=(
        # Pump-precision tiers. Furosemide's typical CRI doses
        # (mg/kg/hr × small patient mass) produce small total mass-per-
        # hour values; concentrations need to be more dilute than the
        # catecholamines to keep pump rate in the precision range.
        #
        # For 20 kg dog × 0.5 mg/kg/hr = 10 mg/hr → 5 mg/mL gives
        # 2 mL/hr (at floor), so 5 mg/mL is the concentrated end.
        # For 5 kg cat × 0.5 = 2.5 mg/hr → 1 mg/mL gives 2.5 mL/hr.
        ConcentrationPreset(
            5000,  # 5 mg/mL
            "5 mL of 50 mg/mL stock (250 mg total) into 45 mL of 0.9% NaCl in a 50 mL syringe (final volume 50 mL)",
            "Recommended for patients ≥15 kg. Concentrated end of the range, minimizes carrier-fluid load in volume-restricted patients with CHF.",
            weight_min_kg=15,
        ),
        ConcentrationPreset(
            2000,  # 2 mg/mL
            "2 mL of 50 mg/mL stock (100 mg total) into 48 mL of 0.9% NaCl in a 50 mL syringe (final volume 50 mL)",
            "Standard preparation for patients 5–15 kg. Matches the most common ICU CHF workflow.",
            weight_min_kg=5,
            weight_max_kg=15,
        ),
        ConcentrationPreset(
            1000,  # 1 mg/mL
            "1 mL of 50 mg/mL stock (50 mg total) into 49 mL of 0.9% NaCl in a 50 mL syringe (final volume 50 mL)",
            "Dilute preparation for patients <5 kg (cats and small dogs). Essential when more concentrated preps would drop pump rate below 2 mL/hr at conservative cat doses.",
            weight_max_kg=5,
        ),
    ),
    default_concentration_ug_per_ml=2000.0,
    titration_ladder=(0.25, 0.5, 0.75, 1.0, 1.5, 2.0),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI loading bolus",
            description=(
                "IV slow bolus before starting the CRI. The loading "
                "dose drives the initial diuresis; the CRI maintains "
                "it with a smoother curve and less ototoxicity risk. "
                "May be repeated to higher cumulative loading doses "
                "(up to 4 mg/kg) in severe refractory pulmonary edema "
                "if initial response is inadequate. Skip the loading "
                "dose in patients already volume-depleted or in those "
                "where prior bolus diuretic has been given recently."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # Dogs and cats: 1-4 mg/kg IV slow bolus per Plumb's.
                # Cat upper bound conventionally same as dog given
                # the bolus is one-time; the conservatism shows up
                # in the CRI maintenance, not the loading.
                Species.DOG: (1.0, 4.0),
                Species.CAT: (1.0, 4.0),
            },
            display_dose_unit="mg",
            note=(
                "Give the bolus over 1–2 minutes; rapid push raises "
                "ototoxicity risk and can produce transient hypotension. "
                "Particularly slow administration is warranted in cats "
                "and small dogs given the higher per-kg drug "
                "concentration at the syringe."
            ),
        ),
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight and the desired CRI dose. The calculator picks a concentration (5, 2, or 1 mg/mL) that keeps the pump in its accurate range.",
        "Cat doses run lower than dogs (0.25–1 vs 0.25–2 mg/kg/hr), and the cat-specific caution threshold is correspondingly lower; cats are more prone to dehydration and electrolyte derangements at any given diuretic dose.",
        "Loading dose (1–4 mg/kg IV over 1–2 minutes) is shown above the CRI maintenance rate. Drive the initial diuresis with the loading bolus; the CRI maintains response with a smoother curve and less ototoxicity than repeated bolus dosing.",
    ),
    dilution_note=(
        "Stock: 50 mg/mL injectable, 50 mL multi-dose vial (2 500 mg "
        "per vial). For CRI: 0.9% NaCl is the preferred diluent. "
        "5% dextrose is borderline; some references list mild "
        "incompatibility; if D5W must be used, prepare fresh and "
        "deliver promptly."
        "\n\n"
        "Furosemide is sensitive to acidic conditions; precipitates "
        "in lactated Ringer's and most acidic IV fluids. Avoid mixing "
        "in the same line with calcium-containing solutions, "
        "epinephrine, or any acidic drug."
        "\n\n"
        "Light-protection: not strictly required for short-term "
        "infusions, but discard the prepared syringe if any color "
        "change to yellow or amber appears; furosemide degrades in "
        "ambient light over hours, particularly when exposed at "
        "elevated temperature."
        "\n\n"
        "Companion medications: pair the CRI with electrolyte "
        "monitoring at 4–6 hour intervals. Hypokalemia frequently "
        "develops within the first 12 hours and is best managed "
        "preemptively with potassium-containing IV fluid or potassium "
        "supplementation rather than waiting for severe derangement."
    ),
    mechanism_summary=(
        "Loop diuretic. Inhibits the Na-K-2Cl symporter at the thick "
        "ascending limb of the loop of Henle, reducing sodium and "
        "chloride reabsorption and producing potent diuresis with "
        "kaliuresis, magnesuria, and modest calciuresis. Onset 5 min "
        "IV; peak diuresis 30 min; duration 2 hr (single bolus). "
        "Also produces mild venodilation that contributes to preload "
        "reduction independent of diuresis, which is useful in acute "
        "pulmonary edema. Hepatic metabolism with renal excretion. "
        "CRI delivery produces a smoother diuresis curve, reduced "
        "ototoxicity, and better natriuretic efficiency per total "
        "dose than intermittent bolus."
    ),
    indications_summary=(
        "Refractory congestive heart failure (MMVD stage D, end-stage "
        "DCM, refractory pulmonary edema), acute fulminant pulmonary "
        "edema unresponsive to bolus diuretic therapy, oliguric or "
        "anuric acute kidney injury (in select protocols, with "
        "appropriate volume status), and volume management in life-"
        "threatening hyperkalemia. CRI delivery is preferred over "
        "repeated bolus for severe or refractory cases: smoother "
        "diuresis, less ototoxicity, better natriuretic efficiency. "
        "Continuous monitoring required: serum electrolytes, "
        "creatinine/BUN, body weight, urine output, blood pressure."
    ),
    catalog_blurb=(
        "Loop diuretic CRI for refractory CHF, acute pulmonary "
        "edema, and select oliguric AKI cases."
    ),
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Furosemide monograph "
                "(current edition). Sections used: Prescriber "
                "Highlights, Uses/Indications, Pharmacology/Actions, "
                "Pharmacokinetics, Contraindications/Precautions/"
                "Warnings, Adverse Effects, Dosages (CHF loading + "
                "maintenance CRI ranges, species-specific), "
                "Compatibility/Compounding Considerations, Dosage "
                "Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Adin DB, Taylor AW, Hill RC, et al. Intermittent "
                "bolus injection versus continuous infusion of "
                "furosemide in normal adult Greyhound dogs. J Vet "
                "Intern Med. 2003;17(5):632–636. Demonstrates the "
                "natriuretic-efficiency advantage of CRI delivery "
                "over equivalent total-dose intermittent bolus; "
                "the foundational vet reference supporting CRI use."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Côté E, Edwards NJ, Ettinger SJ, et al. Management of "
                "congestive heart failure. In: Ettinger SJ, Feldman EC, "
                "Côté E, eds. Textbook of Veterinary Internal Medicine. "
                "8th ed. Elsevier; 2017. Supports CRI use in stage D "
                "refractory CHF with detailed monitoring guidance."
            ),
            reviewer=None,
        ),
    ),
)

DILTIAZEM = CalculatorConfig(
    slug="diltiazem",
    display_name="Diltiazem CRI",
    short_name="Diltiazem",
    category="Cardiology",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # 5 mg/mL injectable (Cardizem and equivalents), 5 mL vial = 25 mg
    # per vial. Some 10 mL vials available (50 mg); the 5 mL/25 mg
    # is the most common veterinary stock.
    stock_concentration_ug_per_ml=5000.0,
    stock_concentration_display=(
        "5 mg/mL (5 000 µg/mL), 5 mL vial (25 mg per vial)"
    ),
    dose_unit=DoseUnit.UG_PER_KG_PER_MIN,
    # 3 µg/kg/min, typical starting maintenance after the loading
    # bolus for A-fib rate control. Silverstein SACCM range: 2–6
    # µg/kg/min with refractory cases up to 10.
    default_dose=3.0,
    target_pump_rate_default_dose=3.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=2.0,
            max=10.0,
            persistent_warning=(
                "Calcium channel blocker that produces hypotension, "
                "bradycardia, AV block, and negative inotropy.\n\n"
                "⚠ NEVER co-administer with IV beta-blockers "
                "(esmolol, propranolol, atenolol IV); additive AV-"
                "block and negative inotropy can precipitate complete "
                "heart block or cardiogenic shock. If a patient is on "
                "an oral beta-blocker, hold the next dose and "
                "consult cardiology before starting diltiazem CRI.\n\n"
                "Contraindicated in pre-existing high-grade AV block "
                "(Mobitz II, 3rd degree) and sick sinus syndrome. "
                "Caution in advanced heart failure with reduced "
                "ejection fraction; negative inotropy worsens "
                "contractility. Wolff-Parkinson-White syndrome: "
                "diltiazem can PARADOXICALLY INCREASE ventricular "
                "rate by blocking AV-node conduction while leaving "
                "the accessory pathway unaffected; confirm rhythm "
                "interpretation before use. Hepatic dysfunction → "
                "reduced clearance → accumulation risk on prolonged "
                "infusions. Continuous ECG monitoring required "
                "throughout."
            ),
            caution_threshold=7.0,
            caution_note=(
                "⚠ Above 7 µg/kg/min, hypotension and AV-block risk "
                "rise sharply. Reassess heart rate, MAP, and ECG "
                "(particularly for PR-interval prolongation and "
                "Mobitz-pattern AV block) before escalating further. "
                "For refractory rate control, the combination of "
                "diltiazem with digoxin (oral) is often a better "
                "strategy than pushing diltiazem CRI alone higher."
            ),
            note=(
                "Initial CRI 2–3 µg/kg/min after the loading bolus, "
                "titrated 2–10 µg/kg/min to ventricular rate target. "
                "Silverstein SACCM range. Effect onset 1–3 min IV; "
                "offset 30–60 min after stopping single bolus, "
                "longer accumulation with prolonged CRI."
            ),
        ),
        Species.CAT: DoseRange(
            min=2.0,
            max=10.0,
            persistent_warning=(
                "Calcium channel blocker. Same monotherapy + beta-"
                "blocker contraindication, AV-block, and hepatic-"
                "clearance concerns as dogs.\n\n"
                "⚠ HCM cats: diltiazem can be useful for rate "
                "control in atrial fibrillation or sinus tachycardia "
                "compromising diastolic filling. AVOID in HCM cats "
                "with significant LVOT (left ventricular outflow "
                "tract) obstruction; the negative inotropy worsens "
                "dynamic obstruction and can precipitate "
                "decompensation. Confirm absence of significant "
                "obstruction by echocardiogram before starting CRI in "
                "an HCM cat.\n\n"
                "Cats are smaller targets for hypotension at given "
                "CRI rates; start at the lower end (2 µg/kg/min) "
                "and titrate cautiously. Continuous ECG and BP "
                "monitoring required."
            ),
            caution_threshold=7.0,
            caution_note=(
                "⚠ Cats: above 7 µg/kg/min, hypotension margins "
                "narrow substantially given typical cat body size. "
                "Reassess MAP and ECG every 1–2 hours. In HCM cats, "
                "particular attention to evidence of LVOT-obstruction "
                "worsening (new dynamic obstruction murmur, "
                "decompensation); pause the infusion if any of these "
                "appear."
            ),
            note=(
                "Same published range as dogs (2–10 µg/kg/min). "
                "Particularly useful in HCM cats for rate control "
                "during decompensation IF LVOT obstruction is absent. "
                "Confirm with echo before starting CRI in HCM."
            ),
        ),
    },
    concentration_presets=(
        # Pump-precision tiers. Diltiazem dose × patient mass produces
        # small mass-per-hour values at typical doses; dilute
        # concentrations needed to keep pump rate above 2 mL/hr.
        ConcentrationPreset(
            1000,  # 1 mg/mL
            "10 mL of 5 mg/mL stock (50 mg, 2 vials) into 40 mL of 0.9% NaCl or 5% dextrose in a 50 mL syringe",
            "Concentrated preparation for patients ≥15 kg. Minimizes carrier-fluid load.",
            weight_min_kg=15,
        ),
        ConcentrationPreset(
            500,  # 0.5 mg/mL
            "5 mL of 5 mg/mL stock (25 mg, 1 vial) into 45 mL of 0.9% NaCl or 5% dextrose in a 50 mL syringe",
            "Standard preparation for patients 3–15 kg. Uses one full vial of stock, convenient for the typical A-fib rate-control workflow.",
            weight_min_kg=3,
            weight_max_kg=15,
        ),
        ConcentrationPreset(
            200,  # 0.2 mg/mL
            "2 mL of 5 mg/mL stock (10 mg) into 48 mL of 0.9% NaCl or 5% dextrose in a 50 mL syringe",
            "Dilute preparation for cats and small dogs (<3 kg). Essential when more concentrated preps would drop pump rate below 2 mL/hr at typical doses.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=500.0,
    titration_ladder=(2, 3, 4, 5, 7, 10),
    loading_doses=(
        LoadingDose(
            label="Pre-CRI rate-control loading",
            description=(
                "IV slowly over 2–3 minutes before starting the CRI. "
                "Initial 0.05–0.15 mg/kg; may repeat 0.05–0.1 mg/kg "
                "every 5–15 minutes to a total cumulative loading "
                "dose of 0.25 mg/kg if rate control is inadequate. "
                "Skip the loading dose in patients with marginal "
                "blood pressure or compromised contractility at "
                "baseline; start at the lower end of the CRI range "
                "instead."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # Plumb's: 0.05-0.25 mg/kg IV slowly. Same range both
                # species; cat-specific caution surfaces in the CRI
                # maintenance, not loading.
                Species.DOG: (0.05, 0.25),
                Species.CAT: (0.05, 0.25),
            },
            display_dose_unit="mg",
            note=(
                "Monitor BP and ECG continuously during the bolus. "
                "Most of the acute hypotension and AV-block risk "
                "lives in the first 2–3 minutes of administration. "
                "Pause and reassess if MAP drops > 20% from baseline "
                "or AV-conduction prolongs."
            ),
        ),
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight and the desired CRI dose. The calculator picks a concentration (1, 0.5, or 0.2 mg/mL) that keeps the pump in its accurate range.",
        "Loading dose (0.05–0.25 mg/kg IV slowly over 2–3 min) is shown above the CRI maintenance rate. Most of the acute hypotension and AV-block risk lives in the loading bolus itself; give slowly and reassess before starting the CRI.",
        "<strong>NEVER concurrent with IV beta-blockers</strong>; the additive AV-block effect can precipitate complete heart block. If the patient is on an oral beta-blocker, hold the next dose and consult cardiology before starting.",
    ),
    dilution_note=(
        "Stock: 5 mg/mL injectable, 5 mL vial = 25 mg per vial. "
        "Dilute in 0.9% NaCl or 5% dextrose; both compatible. The "
        "5 mL vial size means a typical syringe-pump preparation "
        "uses one full vial (for the 0.5 mg/mL prep) or two vials "
        "(for the 1 mg/mL concentrated prep)."
        "\n\n"
        "Compatibility: avoid co-administration in the same line "
        "with furosemide (precipitation at higher concentrations) "
        "and with sodium bicarbonate. Y-site administration with "
        "other vasoactive drugs is generally compatible but verify "
        "for any specific drug combination."
        "\n\n"
        "Storage: refrigerate the prepared syringe if not used "
        "immediately. Stability is 24 hours at room temperature, "
        "longer refrigerated. Discard if any precipitate appears."
    ),
    mechanism_summary=(
        "Non-dihydropyridine calcium channel blocker (Class IV "
        "antiarrhythmic). Blocks L-type calcium channels in cardiac "
        "tissue, particularly the AV node, slowing AV nodal "
        "conduction, prolonging refractoriness, reducing sinus rate, "
        "and producing mild-to-moderate negative inotropy. Limited "
        "vascular smooth muscle effect compared to dihydropyridines "
        "(amlodipine, nifedipine), so produces less peripheral "
        "vasodilation. Onset 1–3 min IV; duration 30–60 min after "
        "single bolus, longer accumulation with prolonged CRI. "
        "Hepatic metabolism via CYP3A4. Clearance is reduced in "
        "hepatic dysfunction."
    ),
    indications_summary=(
        "Atrial fibrillation rate control (most common CRI "
        "indication in vet ICU), supraventricular tachycardia "
        "refractory to vagal maneuvers, and rapid rate control in "
        "hyperthyroid cats or HCM cats without LVOT obstruction. "
        "CRI delivery preferred when sustained rate control is "
        "needed beyond the duration of bolus therapy. Continuous "
        "ECG and BP monitoring required throughout the infusion."
    ),
    catalog_blurb=(
        "Class IV antiarrhythmic (non-DHP calcium channel blocker) "
        "for A-fib rate control and SVT management."
    ),
    supports_print=True,
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Diltiazem HCl monograph "
                "(current edition). Sections used: Prescriber "
                "Highlights, Uses/Indications, Pharmacology/Actions, "
                "Pharmacokinetics, Contraindications/Precautions/"
                "Warnings (beta-blocker interaction, AV-block grades, "
                "WPW caution), Adverse Effects, Dosages (loading + "
                "CRI maintenance), Compatibility/Compounding, Dosage "
                "Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Côté E, MacDonald KA, Meurs KM, Sleeper MM, eds. "
                "Feline Cardiology. Wiley-Blackwell; 2011. Supports "
                "diltiazem CRI use in HCM cats for rate control with "
                "the explicit LVOT-obstruction caveat; avoid in "
                "obstructive disease, useful in non-obstructive HCM "
                "with rate-control needs."
            ),
            reviewer=None,
        ),
    ),
)

METHOCARBAMOL = CalculatorConfig(
    slug="methocarbamol",
    display_name="Methocarbamol CRI",
    short_name="Methocarb",
    category="Emergency",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    # Stock: methocarbamol injectable (Robaxin-V IV), 100 mg/mL,
    # 20 mL multi-dose vial = 2 000 mg per vial.
    stock_concentration_ug_per_ml=100000.0,
    stock_concentration_display=(
        "100 mg/mL (100 000 µg/mL), 20 mL multi-dose vial (2 000 mg)"
    ),
    dose_unit=DoseUnit.MG_PER_KG_PER_HR,
    # 10 mg/kg/hr, typical maintenance for tetanus and tremorogenic
    # toxicosis (Silverstein SACCM). Conservative anchor.
    default_dose=10.0,
    target_pump_rate_default_dose=10.0,
    dose_ranges={
        Species.DOG: DoseRange(
            min=5.0,
            max=15.0,
            persistent_warning=(
                "Skeletal muscle relaxant for tetanus, permethrin / "
                "pyrethrin toxicity (cats), strychnine toxicity, and "
                "tremorogenic mycotoxicoses. Watch for hypotension "
                "with rapid administration. Total daily dose cap: "
                "330 mg/kg/day (Plumb's); running near the top of the "
                "CRI range (15 mg/kg/hr × 24 hr = 360 mg/kg/day) "
                "exceeds this and should be brief. Sedation is "
                "expected; supportive care for recumbent patients "
                "(positional changes, eye lubrication, bladder "
                "management) required. The injectable formulation "
                "contains polyethylene glycol; avoid in renal failure "
                "(PEG accumulation risk)."
            ),
            caution_threshold=12.0,
            caution_note=(
                "⚠ Above 12 mg/kg/hr, the 330 mg/kg/day Plumb's "
                "cumulative-dose ceiling is reached within 24–28 "
                "hours. Plan a clear taper or transition strategy "
                "before exceeding this rate. Consider adjunct sedation "
                "(midazolam, dexmedetomidine) for breakthrough rigidity "
                "rather than escalating methocarbamol alone."
            ),
            note=(
                "Initial CRI 5–10 mg/kg/hr after the loading dose, "
                "titrated 5–15 mg/kg/hr to muscle-relaxation effect. "
                "Total daily dose ceiling 330 mg/kg/day; favor "
                "intermittent bolus dosing for short-term needs and "
                "reserve CRI for refractory continuous spasm "
                "(tetanus, severe permethrin toxicity)."
            ),
        ),
        Species.CAT: DoseRange(
            min=5.0,
            max=15.0,
            persistent_warning=(
                "Skeletal muscle relaxant. The primary feline "
                "indication is permethrin / pyrethrin toxicity; "
                "topical permethrin exposure produces severe tremors "
                "and seizures. Watch for hypotension with rapid "
                "administration. Same 330 mg/kg/day Plumb's cumulative "
                "ceiling as dogs. Supportive care for recumbent or "
                "heavily sedated cats (thermal support, eye care, "
                "bladder care) is essential."
            ),
            caution_threshold=12.0,
            caution_note=(
                "⚠ Cats: avoid running near or above 12 mg/kg/hr for "
                "more than 12 hours given the 330 mg/kg/day ceiling. "
                "For breakthrough tremors, layer in adjunct sedation "
                "(dexmedetomidine, midazolam, propofol where indicated) "
                "rather than pushing methocarbamol higher."
            ),
            note=(
                "Same range as dogs (5–15 mg/kg/hr). For permethrin "
                "toxicity, expect 24–72 hour infusion duration; "
                "intermittent bolus alternation with CRI is common "
                "in feline practice."
            ),
        ),
    },
    concentration_presets=(
        # Pump-precision tiers prepared by diluting the 100 mg/mL stock
        # into a 50 mL syringe with 0.9% NaCl or 5% dextrose. Note:
        # methocarbamol injectable can also be given UNDILUTED via
        # syringe pump for fluid-restricted ICU patients; the 50 mg/mL
        # 1:1 dilution is the most common starting prep.
        ConcentrationPreset(
            50000,  # 50 mg/mL
            "10 mL of 100 mg/mL stock (1 000 mg total) into 10 mL of 0.9% NaCl or 5% dextrose, final volume 20 mL (1:1 dilution; scale to 50 mL syringe with 25 mL stock + 25 mL diluent for longer runs)",
            "Standard 1:1 dilution of stock. Recommended for patients ≥10 kg at typical 10 mg/kg/hr doses.",
            weight_min_kg=10,
        ),
        ConcentrationPreset(
            20000,  # 20 mg/mL
            "10 mL of 100 mg/mL stock (1 000 mg total) into 40 mL of 0.9% NaCl or 5% dextrose, final volume 50 mL",
            "Recommended for patients 3–10 kg. More dilute than the 1:1 prep; pump rate stays in the precision range for medium patients.",
            weight_min_kg=3,
            weight_max_kg=10,
        ),
        ConcentrationPreset(
            10000,  # 10 mg/mL
            "5 mL of 100 mg/mL stock (500 mg total) into 45 mL of 0.9% NaCl or 5% dextrose, final volume 50 mL",
            "Dilute preparation for cats and very small dogs (<3 kg) or any patient at very low doses.",
            weight_max_kg=3,
        ),
    ),
    default_concentration_ug_per_ml=20000.0,
    titration_ladder=(5, 6, 8, 10, 12, 15),
    loading_doses=(
        LoadingDose(
            label="Tetanus / strychnine loading (label)",
            description=(
                "55–220 mg/kg IV slowly. Per Plumb's label: rapidly "
                "administer half of the calculated total dose, allow "
                "muscle relaxation to occur, then administer the "
                "remainder. Additional doses may be needed to "
                "relieve residual effects or prevent recurrence; "
                "total cumulative dose should not exceed 330 mg/kg/"
                "day. Do not exceed 2 mL of undiluted 100 mg/mL "
                "stock per minute (Plumb's) to avoid hypotension. "
                "After the loading dose, start the maintenance CRI "
                "within 30–60 minutes."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                # 55–220 mg/kg IV per Plumb's label, severe strychnine
                # and tetanus effects (Dogs/Cats).
                Species.DOG: (55.0, 220.0),
                Species.CAT: (55.0, 220.0),
            },
            display_dose_unit="mg",
            note=(
                "Administer in two halves with a pause for muscle "
                "relaxation between. Monitor BP throughout the "
                "bolus; hypotension is the principal acute adverse "
                "effect. Slow further if MAP drops by more than 20% "
                "from baseline."
            ),
        ),
        LoadingDose(
            label="Pyrethrin / pyrethroid loading (extra-label)",
            description=(
                "40–80 mg/kg IV slowly per Plumb's extra-label "
                "dosing for pyrethrin/pyrethroid exposure. If "
                "clinical signs are not controlled, repeat the IV "
                "bolus or transition to maintenance CRI at the "
                "initial rate of ~10 mg/kg/hr (default below). "
                "Most feline permethrin cases need 24–72 hours of "
                "methocarbamol therapy total. Do not exceed 2 mL of "
                "undiluted 100 mg/mL stock per minute."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                Species.DOG: (40.0, 80.0),
                Species.CAT: (40.0, 80.0),
            },
            display_dose_unit="mg",
            note=(
                "Cats are the predominant patient for this "
                "indication (topical permethrin exposure). Watch "
                "for breakthrough tremors and layer adjunct "
                "sedation (dexmedetomidine, midazolam) rather than "
                "escalating methocarbamol alone if signs return "
                "between boluses."
            ),
        ),
        LoadingDose(
            label="Mycotoxin ingestion bolus (extra-label)",
            description=(
                "11–35 mg/kg IV bolus, repeated every 2–4 hours to "
                "control clinical signs (Plumb's, extra-label, case "
                "report). Lower dose range than tetanus or "
                "pyrethrin given a typically shorter clinical "
                "course. Transition to maintenance CRI if tremors "
                "are persistent or recurring."
            ),
            matches_cri_rate=False,
            dose_per_kg={
                Species.DOG: (11.0, 35.0),
                Species.CAT: (11.0, 35.0),
            },
            display_dose_unit="mg",
            note=(
                "Track cumulative daily dose carefully when "
                "repeat-bolus dosing; the 330 mg/kg/day label cap "
                "applies across all bolus and CRI delivery combined."
            ),
        ),
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight and the desired CRI dose. The calculator picks a concentration (50, 20, or 10 mg/mL) that keeps the pump in its accurate range.",
        "The recommended concentration shows a <strong>suggested</strong> tag that updates as you change the patient inputs.",
        "Loading dose options shown above the CRI cover three indications: tetanus/strychnine 55–220 mg/kg (label), pyrethrin/pyrethroid 40–80 mg/kg (extra-label), and mycotoxin 11–35 mg/kg (extra-label). The 2 mL of stock per minute administration cap (Plumb's) keeps hypotension manageable.",
    ),
    dilution_note=(
        "Stock: methocarbamol injectable is 100 mg/mL in a 20 mL "
        "multi-dose vial (2 000 mg per vial). Dilute in 0.9% NaCl or "
        "5% dextrose; both compatible. For fluid-restricted ICU "
        "patients, undiluted stock can be run via syringe pump (high "
        "viscosity; verify pump tolerates it)."
        "\n\n"
        "Daily-dose tracking is essential: the 330 mg/kg/day Plumb's "
        "ceiling is reached at 13.75 mg/kg/hr × 24 hr. CRIs running "
        "more than 24 hours at the upper end of the range require "
        "explicit cumulative-dose accounting and may need a planned "
        "taper or transition to an alternative."
        "\n\n"
        "Polyethylene-glycol vehicle: the injectable formulation "
        "contains PEG-300 as a solubilizer. Renal failure cases "
        "accumulate PEG; avoid prolonged CRI use, or substitute oral "
        "dosing once the patient tolerates it."
    ),
    mechanism_summary=(
        "Centrally acting skeletal muscle relaxant. Exact mechanism "
        "not fully characterized; produces general CNS depression "
        "rather than direct action on skeletal muscle or the "
        "neuromuscular junction. Onset 5–10 minutes IV; duration "
        "highly variable (1–4 hours after bolus). Hepatic metabolism "
        "with renal elimination of metabolites. PEG-300 vehicle in the "
        "injectable adds renal-clearance dependence."
    ),
    indications_summary=(
        "Skeletal muscle relaxant for refractory continuous spasm or "
        "rigidity. Primary indications: tetanus (Clostridium tetani "
        "toxin-mediated spasms), permethrin / pyrethrin toxicity in "
        "cats (topical exposure tremors), strychnine toxicosis, and "
        "tremorogenic mycotoxicosis (penitrem A, roquefortine). "
        "Intermittent bolus dosing is the more common Plumb's-listed "
        "approach; CRI is reserved for refractory cases where "
        "continuous muscle relaxation is needed and intermittent "
        "bolus produces unacceptable rebound rigidity between doses. "
        "Supportive care for sedated / recumbent patients is essential."
    ),
    catalog_blurb=(
        "Centrally acting skeletal muscle relaxant CRI for refractory "
        "tetanus, permethrin toxicity, and tremorogenic toxicosis."
    ),
    sources=(
        Source(
            citation=(
                "Plumb's Veterinary Drugs, Methocarbamol monograph "
                "(current edition). Sections used: Uses/Indications, "
                "Pharmacology/Actions, Pharmacokinetics, "
                "Contraindications/Precautions/Warnings, Adverse "
                "Effects, Dosages (intermittent bolus regimen, daily "
                "ceiling), Dosage Forms/Regulatory Status."
            ),
            reviewer=None,
        ),
        Source(
            citation=(
                "Hopper K, Mehl M. Toxicology emergencies. In: "
                "Silverstein DC, Hopper K, eds. Small Animal Critical "
                "Care Medicine. 3rd ed. St. Louis, MO: Elsevier; 2023. "
                "Supports CRI use of methocarbamol for refractory "
                "tetanus and permethrin toxicity, with dose ranges "
                "consistent with this calculator's 5–15 mg/kg/hr."
            ),
            reviewer=None,
        ),
    ),
)

METOCLOPRAMIDE = CalculatorConfig(
    slug="metoclopramide",
    display_name="Metoclopramide CRI",
    short_name="Metoclo",
    category="Antiemetics & Prokinetics",
    kind=CalculatorKind.SINGLE_DRUG_CRI,
    stock_concentration_ug_per_ml=5000.0,
    stock_concentration_display="5 mg/mL (5000 µg/mL), 10 mL vial (50 mg)",
    dose_unit=DoseUnit.MG_PER_KG_PER_HR,
    default_dose=0.04,
    # Target-pump-rate mode is OFF. Metoclopramide CRI is conventionally
    # prepared at standard concentrations in a fluid bag; clinicians
    # don't routinely think about "target a pump rate" the way they do
    # for vasopressors in fluid-restricted patients.
    supports_target_pump_rate_mode=False,
    dose_ranges={
        Species.DOG: DoseRange(
            min=0.04,
            max=0.09,
            # caution_threshold sits just above the standard antiemetic
            # range. Doses ≥ 0.1 mg/kg/hr fire the caution note
            # (laryngeal-paralysis specialized protocol or off-label).
            caution_threshold=0.1,
            persistent_warning=(
                "Standard antiemetic/prokinetic CRI: 0.04–0.09 mg/kg/hr "
                "(1–2 mg/kg/day). Higher rates (e.g., 1 mg/kg/hr "
                "intraoperatively for laryngeal paralysis surgery) are "
                "specialized protocols. Avoid in patients with GI "
                "obstruction or perforation. Crosses the blood-brain "
                "barrier; watch for extrapyramidal signs (restlessness, "
                "involuntary movements) at higher doses or with "
                "prolonged use, more common in young or geriatric dogs."
            ),
            caution_note=(
                "⚠ Doses above 0.09 mg/kg/hr exceed the standard antiemetic "
                "CRI range. The 1 mg/kg/hr intraoperative protocol for "
                "laryngeal paralysis surgery is published but assumes "
                "anesthesia, active monitoring, and a 24-hr total "
                "treatment duration with postop step-down to "
                "0.083 mg/kg/hr."
            ),
            note=(
                "Standard antiemetic/prokinetic CRI: 0.04–0.09 mg/kg/hr "
                "(1–2 mg/kg/day). Laryngeal paralysis intraoperative "
                "protocol: 1 mg/kg IV loading + 1 mg/kg/hr intraop, "
                "dropping to 0.083 mg/kg/hr postoperatively for a "
                "24-hour total treatment duration."
            ),
        ),
        Species.CAT: DoseRange(
            min=0.04,
            max=0.09,
            caution_threshold=0.1,
            persistent_warning=(
                "Other antiemetics (ondansetron, maropitant) are "
                "preferred in cats. Other prokinetic agents (cisapride) "
                "are preferred for prokinetic indication. Reserve "
                "metoclopramide CRI for situations where alternatives "
                "are unavailable. Avoid in patients with GI obstruction "
                "or perforation. Plumb's does not list a cat CRI dose; "
                "the dog range is used as a conservative extrapolation."
            ),
            caution_note=(
                "⚠ Plumb's does not list a specific cat CRI dose. The "
                "dog range (0.04–0.09 mg/kg/hr) is the standard "
                "extrapolation used clinically. Higher rates have not "
                "been validated in cats."
            ),
            note=(
                "Cat antiemetic dosing in Plumb's is intermittent "
                "(0.2–0.5 mg/kg every 6–8 hr SC/IM/IV). The CRI dose "
                "range here is an extrapolation from the dog range, "
                "used when intermittent dosing isn't practical. Other "
                "antiemetics (ondansetron, maropitant) are preferred."
            ),
        ),
    },
    concentration_presets=(
        # Three standard preparations covering the antiemetic CRI dose
        # range across patient sizes, plus a concentrated prep for the
        # laryngeal-paralysis intraoperative protocol. Diluents:
        # 0.9% NaCl, 5% dextrose, LRS all compatible per Plumb's.
        ConcentrationPreset(
            20,
            "5 mg (1 mL stock) into a 250 mL bag of 0.9% NaCl, 5% dextrose, or LRS",
            "Small patients (<10 kg). Pump rate stays in a reasonable range for syringe-pump or low-flow infusions.",
        ),
        ConcentrationPreset(
            40,
            "10 mg (2 mL stock) into a 250 mL bag of 0.9% NaCl, 5% dextrose, or LRS, or 20 mg (4 mL) into 500 mL",
            "Standard preparation for most patients on antiemetic / prokinetic CRI.",
        ),
        ConcentrationPreset(
            1000,
            "50 mg (10 mL stock) into a 50 mL syringe of 0.9% NaCl",
            "Concentrated preparation for the laryngeal-paralysis intraoperative protocol (1 mg/kg/hr).",
        ),
    ),
    default_concentration_ug_per_ml=40.0,
    titration_ladder=(0.04, 0.05, 0.06, 0.07, 0.08, 0.09),
    dilution_note=(
        "Metoclopramide stock is 5 mg/mL (10 mL vials, 50 mg per vial). "
        "Compatible diluents per Plumb's: 0.9% NaCl, 5% dextrose, LRS, "
        "and Ringer's. Avoid co-administration with chloramphenicol, "
        "calcium gluconate, or other drugs known to be incompatible "
        "(consult Plumb's compatibility tables for the specific drug). "
        "Solutions are stable for 24 hours at room temperature in the "
        "listed diluents; discard if discoloration occurs."
    ),
    mechanism_summary=(
        "Centrally-acting dopamine (D2) antagonist with antiemetic and "
        "prokinetic effects. Blocks dopamine in the chemoreceptor "
        "trigger zone (antiemetic effect) and increases lower esophageal "
        "sphincter tone and gastric emptying via cholinergic enhancement "
        "(prokinetic effect). Crosses the blood-brain barrier; "
        "extrapyramidal signs can develop at higher doses or with "
        "prolonged use. Reduces gastric pH minimally; does not block "
        "5-HT3 receptors at typical CRI doses."
    ),
    indications_summary=(
        "Antiemetic and prokinetic CRI for dogs and cats. Used for "
        "nausea, vomiting, gastric stasis, reflux esophagitis, and "
        "prokinetic support in critically ill patients. A higher-dose "
        "protocol (1 mg/kg/hr intraoperatively, dropping to 0.083 mg/kg/hr "
        "postoperatively for 24 hours) is published for laryngeal "
        "paralysis surgery to reduce reflux and aspiration risk. Other "
        "antiemetics (ondansetron, maropitant) are preferred in cats."
    ),
    catalog_blurb="Antiemetic and prokinetic CRI for nausea, gastric stasis, and reflux prevention.",
    sources=(
        Source(
            citation=(
                "Plumb DC. Plumb's Veterinary Drugs, metoclopramide "
                "monograph (current edition). Sections used: Dosages "
                "(dogs and cats), including standard antiemetic / "
                "prokinetic CRI (0.04–0.09 mg/kg/hr) and laryngeal "
                "paralysis intraoperative protocol (1 mg/kg IV loading "
                "+ 1 mg/kg/hr intraop, 0.083 mg/kg/hr postop, 24-hr "
                "total); Compatibility/Compounding; Drug Interactions."
            ),
            reviewer=None,
        ),
    ),
    how_it_works_paragraphs=(
        "Enter the patient's weight and dose. The calculator returns the pump rate to deliver that dose at the chosen bag concentration. The default 40 µg/mL preparation suits most patients on standard antiemetic CRI (0.04–0.09 mg/kg/hr); a 20 µg/mL prep is available for small patients and a more concentrated 1000 µg/mL syringe prep covers the laryngeal-paralysis intraoperative protocol.",
        "After you compute, the result panel shows the laryngeal-paralysis loading-dose protocol alongside the CRI rate. The standard antiemetic CRI doesn't require a loading dose. The <strong>laryngeal-paralysis</strong> protocol uses a 1 mg/kg IV loading dose before the intraoperative CRI at 1 mg/kg/hr, dropping to 0.083 mg/kg/hr postoperatively.",
        "Metoclopramide is contraindicated in GI obstruction or perforation. It crosses the blood-brain barrier; watch for extrapyramidal signs (restlessness, involuntary movements) at higher doses or with prolonged use. Other antiemetics (ondansetron, maropitant) are preferred in cats.",
    ),
    loading_doses=(
        LoadingDose(
            label="Laryngeal paralysis (intraoperative)",
            description=(
                "1 mg/kg IV bolus before the 1 mg/kg/hr intraoperative CRI."
            ),
            # Not a CRI-rate-matched dose. The 1 mg/kg loading is a
            # fixed protocol value, not derived from whatever CRI rate
            # the user entered (the standard antiemetic CRI of
            # 0.04–0.09 mg/kg/hr doesn't get a loading dose).
            matches_cri_rate=False,
            display_dose_unit="mg",
            dose_per_kg={
                # Plumb's lists this protocol for dogs only.
                Species.DOG: (1.0, 1.0),
            },
            note=(
                "Postoperative rate is reduced to 0.083 mg/kg/hr IV CRI "
                "for a total treatment duration of 24 hours. Used for "
                "laryngeal paralysis surgery to reduce reflux and "
                "aspiration risk."
            ),
        ),
    ),
)


# Hardcoded configs shipped with the app. YAML files in content/calculators/
# are layered on top at startup; a YAML with the same slug overrides.
_HARDCODED: list[CalculatorConfig] = [
    NOREPINEPHRINE,
    EPINEPHRINE,
    VASOPRESSIN,
    PHENYLEPHRINE,
    NITROPRUSSIDE,
    DOBUTAMINE,
    DOPAMINE_STANDARD,
    FENTANYL,
    MORPHINE,
    DEXMEDETOMIDINE,
    MIDAZOLAM,
    MAGNESIUM_SULFATE,
    ESMOLOL,
    LIDOCAINE,
    FUROSEMIDE,
    DILTIAZEM,
    METHOCARBAMOL,
    METOCLOPRAMIDE,
]


DRUGS: list[CalculatorConfig] = list(_HARDCODED)
DRUG_BY_SLUG: dict[str, CalculatorConfig] = {d.slug: d for d in DRUGS}


def get_drug(slug: str) -> CalculatorConfig | None:
    return DRUG_BY_SLUG.get(slug)


def drugs_by_category() -> dict[str, list[CalculatorConfig]]:
    out: dict[str, list[CalculatorConfig]] = {}
    for d in DRUGS:
        out.setdefault(d.category, []).append(d)
    return out


# ---------------------------------------------------------------------------
# Norepinephrine-specific helpers
# ---------------------------------------------------------------------------
#
# Norepinephrine has a clinically meaningful pump-precision floor: most
# volumetric pumps lose accuracy below ~1–2 mL/hr, and dead-space delay in
# the extension set is non-trivial at those rates. For small patients at
# the typical 0.1 µg/kg/min starting dose, the 16 µg/mL bag preparation
# gives sub-2 mL/hr rates. The helpers below auto-select a more dilute
# preset for small patients and generate the bag-size scaled recipes
# (250 / 500 / 1 L) at the recommended concentration so clinicians stock
# what they have can still make the right preparation.

NOREPI_STOCK_MG_PER_ML = 1.0  # standard norepinephrine stock concentration
NOREPI_VIAL_SIZE_MG = 4.0  # standard vial = 4 mg / 4 mL
NOREPI_DEFAULT_MIN_PUMP_RATE_ML_PER_HR = 2.0  # pump precision floor


@dataclass(frozen=True)
class BagSizeVariant:
    """One bag-size presentation of a fixed concentration.

    Used by drugs in the "combined prep section" UI pattern (norepi, then
    dobutamine, etc.) to show multiple bag-size options at the same
    concentration. Drug amount scales with bag volume; pump rate is
    invariant.
    """

    bag_volume_ml: int
    concentration_ug_per_ml: float
    drug_amount_mg: float
    ml_stock_to_draw: float  # at the drug's stock concentration
    vials_used: float  # fractional vials (drug.vial_size_mg per vial)
    vial_note: str  # human-readable: "1 vial", "half-vial", "2 vials"
    recipe_text: str
    is_suggested: bool  # True for the bag that uses exactly one full vial
    diluent_label: str  # carrier-fluid wording for this drug + bag


def pick_preset_for_patient(
    drug: CalculatorConfig,
    weight_kg: float,
    dose_ug_kg_min: float,
) -> ConcentrationPreset:
    """Return the patient-recommended preset, per drug.recommendation_strategy.

    "pump-precision" (norepi pattern): highest concentration that keeps
    pump rate ≥ drug.min_pump_rate_ml_per_hr. Minimizes carrier fluid
    while keeping the pump in its accurate range.

    "weight-band" (dobutamine pattern): the preset whose weight_min_kg /
    weight_max_kg band includes the patient. Falls back to the closest
    preset if no band matches exactly. Doesn't use dose at all (the
    band-driven concentration tracks patient size, not infusion math).

    Empty/unrecognized strategy returns the default preset.
    """
    pump_safe = [p for p in drug.concentration_presets if p.pump_safe]
    if not pump_safe:
        return drug.concentration_presets[0]

    if drug.recommendation_strategy == "pump-precision":
        floor = drug.min_pump_rate_ml_per_hr or NOREPI_DEFAULT_MIN_PUMP_RATE_ML_PER_HR
        presets_high_to_low = sorted(
            pump_safe, key=lambda p: p.concentration_ug_per_ml, reverse=True
        )
        ug_per_hr = dose_ug_kg_min * weight_kg * 60.0
        for preset in presets_high_to_low:
            if ug_per_hr / preset.concentration_ug_per_ml >= floor:
                return preset
        # Even the most dilute is below floor; return it anyway; caller
        # surfaces the warning.
        return presets_high_to_low[-1]

    if drug.recommendation_strategy == "weight-band":
        # Find the preset whose [weight_min_kg, weight_max_kg] band
        # includes weight_kg. weight_min_kg and weight_max_kg default to
        # None on ConcentrationPreset; None = unbounded on that side.
        for preset in pump_safe:
            lo = preset.weight_min_kg if preset.weight_min_kg is not None else 0.0
            hi = (
                preset.weight_max_kg
                if preset.weight_max_kg is not None
                else float("inf")
            )
            if lo <= weight_kg < hi:
                return preset
        # No band matched (weight at exact boundary, or no bands defined).
        # Fall back: lightest band for small patients, heaviest for big.
        sorted_by_lo = sorted(
            pump_safe, key=lambda p: p.weight_min_kg or 0.0
        )
        smallest_lo = sorted_by_lo[0].weight_min_kg or 0.0
        if weight_kg < smallest_lo:
            return sorted_by_lo[0]
        return sorted_by_lo[-1]

    # Unrecognized strategy: caller-default preset.
    return next(
        (
            p
            for p in pump_safe
            if p.concentration_ug_per_ml == drug.default_concentration_ug_per_ml
        ),
        pump_safe[0],
    )


def pick_norepi_preset_for_patient(
    weight_kg: float,
    dose_ug_kg_min: float,
    min_pump_rate_ml_per_hr: float = NOREPI_DEFAULT_MIN_PUMP_RATE_ML_PER_HR,
) -> ConcentrationPreset:
    """Backward-compat wrapper for the norepi pump-precision picker.

    Kept so existing callers (tests, scripts) keep working. New code
    should call `pick_preset_for_patient(drug, ...)` instead.
    """
    return pick_preset_for_patient(NOREPINEPHRINE, weight_kg, dose_ug_kg_min)


def _format_vial_note(vials_used: float) -> str:
    """Human-readable vial description for a recipe line."""
    if abs(vials_used - 1.0) < 0.01:
        return "1 vial"
    if abs(vials_used - 0.5) < 0.01:
        return "half-vial; discard the rest"
    if abs(vials_used - 0.25) < 0.01:
        return "quarter-vial; discard the rest"
    if vials_used < 1.0:
        return f"{vials_used:.2f} of a vial; discard the rest"
    if abs(vials_used - round(vials_used)) < 0.01:
        n = int(round(vials_used))
        return f"{n} vials"
    return f"{vials_used:.2f} vials"


def _stock_label_short(drug: CalculatorConfig) -> str:
    """The short stock-concentration label for inline use in recipes.

    Example: "1 mg/mL" for norepi, "12.5 mg/mL" for dobutamine. Built
    from drug.stock_concentration_ug_per_ml, ignoring the longer
    parenthetical detail in stock_concentration_display.
    """
    mg_per_ml = drug.stock_concentration_ug_per_ml / 1000.0
    if abs(mg_per_ml - round(mg_per_ml)) < 0.01:
        return f"{int(round(mg_per_ml))} mg/mL"
    return f"{mg_per_ml:g} mg/mL"


def _drug_name_in_recipe(drug: CalculatorConfig) -> str:
    """Lowercased drug name for inline use in recipes.

    Strips both the " CRI" suffix and any "· …" disambiguation
    adornment (e.g. "Dopamine CRI · standard method" → "dopamine").
    Keep this aligned with the equivalent Jinja expression in
    calculator.html that derives `drug_short_name`.
    """
    name = drug.display_name.split(" · ", 1)[0]
    return name.replace(" CRI", "").strip().lower()


def bag_size_variants_for_drug(
    drug: CalculatorConfig,
    concentration_ug_per_ml: float,
) -> tuple[BagSizeVariant, ...]:
    """Generate bag-size presentations for any drug that uses the
    combined prep section. Drug-agnostic; uses drug.vial_size_mg,
    drug.stock_concentration_ug_per_ml, drug.bag_size_options_ml,
    drug.diluent_label.
    """
    if not drug.uses_combined_prep_section:
        return ()
    if not drug.bag_size_options_ml or drug.vial_size_mg is None:
        return ()

    stock_mg_per_ml = drug.stock_concentration_ug_per_ml / 1000.0
    stock_label = _stock_label_short(drug)
    drug_label = _drug_name_in_recipe(drug)
    diluent = drug.diluent_label

    variants = []
    for bag_ml in drug.bag_size_options_ml:
        drug_amount_mg = concentration_ug_per_ml * bag_ml / 1000.0
        ml_stock = drug_amount_mg / stock_mg_per_ml
        vials_used = drug_amount_mg / drug.vial_size_mg
        vial_note = _format_vial_note(vials_used)
        is_suggested = abs(vials_used - 1.0) < 0.01

        if abs(drug_amount_mg - round(drug_amount_mg)) < 0.01:
            drug_str = f"{int(round(drug_amount_mg))} mg"
        else:
            drug_str = f"{drug_amount_mg:.2g} mg"
        if abs(ml_stock - round(ml_stock)) < 0.01:
            ml_str = f"{int(round(ml_stock))} mL"
        else:
            ml_str = f"{ml_stock:.2g} mL"

        recipe = (
            f"{drug_str} ({ml_str} of {stock_label} {drug_label} "
            f"stock = {vial_note}) into a {bag_ml} mL bag of {diluent}"
        )

        variants.append(
            BagSizeVariant(
                bag_volume_ml=bag_ml,
                concentration_ug_per_ml=concentration_ug_per_ml,
                drug_amount_mg=drug_amount_mg,
                ml_stock_to_draw=ml_stock,
                vials_used=vials_used,
                vial_note=vial_note,
                recipe_text=recipe,
                is_suggested=is_suggested,
                diluent_label=diluent,
            )
        )

    return tuple(variants)


def bag_size_variants_for_norepi(
    concentration_ug_per_ml: float,
    bag_sizes_ml: tuple[int, ...] = (250, 500, 1000),
) -> tuple[BagSizeVariant, ...]:
    """Backward-compat wrapper. New code should call
    `bag_size_variants_for_drug(NOREPINEPHRINE, conc)` instead.
    """
    # The `bag_sizes_ml` parameter is preserved for backward compat but
    # no longer overridable in practice; the drug config drives the
    # bag-size set. If a caller passes a non-default value, honor it
    # by temporarily swapping the drug config.
    if bag_sizes_ml == NOREPINEPHRINE.bag_size_options_ml:
        return bag_size_variants_for_drug(NOREPINEPHRINE, concentration_ug_per_ml)
    # Custom override path: build variants directly.
    from dataclasses import replace

    overridden = replace(NOREPINEPHRINE, bag_size_options_ml=bag_sizes_ml)
    return bag_size_variants_for_drug(overridden, concentration_ug_per_ml)


# ---------------------------------------------------------------------------
# Loading doses: IV bolus math surfaced alongside the CRI rate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadingDoseComputation:
    """Per-scenario loading-dose math, ready for template rendering.

    Values are stored in the scenario's display dose unit (mg or µg)
    so the template can render them with `dose_unit_label` and not
    have to convert. The mL-of-stock fields are always in mL.
    """

    label: str
    description: str
    note: str
    # Dose unit label for display ("µg" or "mg"), matches the
    # LoadingDose.display_dose_unit.
    dose_unit_label: str
    # Range presentation (always shown). Values in dose_unit_label units.
    min_per_kg: float
    max_per_kg: float
    min_total: float  # min × weight
    max_total: float
    min_ml_stock: float
    max_ml_stock: float
    # True when the published dose is a single value (min == max).
    # The template renders these scenarios more compactly.
    is_single_value: bool
    # Matched value (only when matches_cri_rate=True and cri_dose given).
    # In dose_unit_label units.
    matched_per_kg: float | None
    matched_total: float | None
    matched_ml_stock: float | None
    # True when the matched value falls outside the published range.
    matched_outside_range: bool


def compute_loading_doses(
    drug: CalculatorConfig,
    weight_kg: float,
    species: Species,
    cri_dose_value: float | None = None,
) -> tuple[LoadingDoseComputation, ...]:
    """Compute loading-dose math for each scenario in drug.loading_doses.

    For each scenario:
      - Always computes the range (min, max in dose_unit_label per kg
        → total in dose_unit_label → mL stock)
      - If matches_cri_rate=True and cri_dose_value is provided, also
        computes a "matched" value at cri_dose_value per kg

    The scenario's display_dose_unit determines whether values are in
    mg or µg. The mL-stock math always converts to µg internally
    (multiplying by 1000 for mg values) so it lines up with the drug's
    µg/mL stock concentration.

    Returns empty tuple if drug.loading_doses is empty or weight is
    invalid. The caller passes the result to the result_panel template.
    """
    if not drug.loading_doses or weight_kg <= 0:
        return ()
    if drug.stock_concentration_ug_per_ml <= 0:
        return ()

    stock_ug_per_ml = drug.stock_concentration_ug_per_ml
    out: list[LoadingDoseComputation] = []

    for scenario in drug.loading_doses:
        dose_range = scenario.dose_per_kg.get(species)
        if dose_range is None:
            # No published dose for this species; skip the scenario.
            # (e.g., metoclopramide's lar par protocol is dog-only.)
            continue
        lo, hi = dose_range
        # Multiplier converts the scenario's display unit to µg, which
        # is what the stock-volume math needs. mg → µg is × 1000;
        # µg → µg is × 1.
        ug_per_display_unit = 1000.0 if scenario.display_dose_unit == "mg" else 1.0

        min_total = lo * weight_kg
        max_total = hi * weight_kg
        min_ml = (min_total * ug_per_display_unit) / stock_ug_per_ml
        max_ml = (max_total * ug_per_display_unit) / stock_ug_per_ml
        is_single = abs(lo - hi) < 1e-9

        matched_per_kg = None
        matched_total = None
        matched_ml_stock = None
        matched_outside_range = False
        if scenario.matches_cri_rate and cri_dose_value is not None and cri_dose_value > 0:
            matched_per_kg = cri_dose_value
            matched_total = matched_per_kg * weight_kg
            matched_ml_stock = (matched_total * ug_per_display_unit) / stock_ug_per_ml
            matched_outside_range = (
                matched_per_kg < lo or matched_per_kg > hi
            )

        out.append(
            LoadingDoseComputation(
                label=scenario.label,
                description=scenario.description,
                note=scenario.note,
                dose_unit_label=scenario.display_dose_unit,
                min_per_kg=lo,
                max_per_kg=hi,
                min_total=min_total,
                max_total=max_total,
                min_ml_stock=min_ml,
                max_ml_stock=max_ml,
                is_single_value=is_single,
                matched_per_kg=matched_per_kg,
                matched_total=matched_total,
                matched_ml_stock=matched_ml_stock,
                matched_outside_range=matched_outside_range,
            )
        )

    return tuple(out)


def reload_catalog() -> None:
    """Rebuild the catalog from the in-memory config list. Mostly a no-op now
    that YAML loading is gone, kept for any callers that still reference it
    (e.g., admin endpoints from a future pass)."""
    global DRUGS, DRUG_BY_SLUG
    DRUGS = list(_HARDCODED)
    DRUG_BY_SLUG = {d.slug: d for d in DRUGS}
    log.info("Reloaded catalog: %d calculators", len(DRUGS))
