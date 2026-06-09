"""
Practice problems for the InfusionFox learning section.

Each problem is a static, hand-built worked example that a clinician or
student can use to practice the kind of bedside math the calculators
automate. Problems are grouped by topic and tagged with a difficulty
level. The solution steps are rendered with KaTeX so unit cancellation
(\\cancel{...}) shows visually how the math works.

Problems are not pulled from the calculator code — they're static so
the worked answer doesn't drift if calculator logic changes. The
trade-off is that adding a problem requires editing this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SolutionStep:
    """One step in a worked solution.

    `narrative` is the plain-English explanation of what we're doing in
    this step. `math` is an optional KaTeX expression rendered inline
    in display mode; leave blank for steps that are purely narrative.
    Use \\cancel{...} around units that cross out, matching the way a
    student would draw the cancellation on paper.
    """

    narrative: str
    math: str = ""


@dataclass(frozen=True)
class AnswerCheck:
    """A single check-your-answer field on a practice problem.

    Two shapes are supported, distinguished by whether `choices` is set:

    Numeric input with tolerance (choices is None):
        The user types a number; client-side JS compares against
        `expected` with ±`tolerance_percent` wiggle room. Used for
        pump rates, mL drawn, mEq/kg/hr, etc. where rounding to one or
        two decimal places is expected.

    Multiple choice (choices is a tuple):
        The user picks one option. The correct option is identified by
        its 0-based index in `choices`, stored in `expected` (cast to
        int by the template). Used for bag-size rounding ("which
        standard size?") and yes/no judgments ("safe / exceeds cap").

    label and unit are short strings shown next to the field. For
    multiple choice, unit is typically empty since each choice carries
    its own unit text.
    """

    label: str
    expected: float           # numeric: the target value; choices: the index of the correct option
    unit: str = ""            # e.g. "mL/hr", "mg", "mL"; blank for choice-style
    tolerance_percent: float = 2.0  # only meaningful for numeric inputs
    choices: tuple[str, ...] | None = None  # if set, render as multiple choice


@dataclass(frozen=True)
class PracticeProblem:
    slug: str            # URL-stable id, kebab-case
    title: str           # short headline, e.g. "Fentanyl CRI for a 12 kg dog"
    topic: str           # grouping label, e.g. "CRI math"
    difficulty: str      # "Intro" | "Clinical" | "Advanced"
    scenario: str        # the problem statement (the question)
    # Hints are progressive nudges shown above the worked answer, each in
    # its own collapsible disclosure. By convention, hints[0] is a light
    # "where to start" nudge and hints[1] is a structural hint that shows
    # the setup (the formula or unit chain) without doing the arithmetic.
    # All hints render collapsed by default.
    hints: list[str] = field(default_factory=list)
    steps: list[SolutionStep] = field(default_factory=list)
    final_answer: str = ""  # the punchline, plainly stated
    # One or more check-your-answer fields. Each renders an input above
    # the hints. Problems with multiple checks render them stacked, each
    # independently checkable.
    checks: list[AnswerCheck] = field(default_factory=list)
    related_calculator_url: str | None = None  # link to the calculator that solves this kind of problem
    related_calculator_name: str | None = None
    # Optional link to the /learn/<slug> clinical-background article that
    # supports this problem. Rendered alongside the calculator link inside
    # the worked-answer body so a learner can read the underlying clinical
    # rationale after working the math.
    related_background_url: str | None = None
    related_background_name: str | None = None


# ---------------------------------------------------------------------------
# Problem 1 — CRI math: µg/kg/min to mL/hr (fentanyl)
# ---------------------------------------------------------------------------

P1 = PracticeProblem(
    slug="fentanyl-cri-12kg",
    title="Fentanyl CRI for a 26.4 lb dog",
    topic="CRI math",
    difficulty="Intro",
    scenario=(
        "You need to start a fentanyl CRI at 5 µg/kg/hr in a 26.4 lb dog. "
        "Your fentanyl stock is 50 µg/mL. What pump rate (mL/hr) do you set?"
    ),
    checks=[
        AnswerCheck(label="Pump rate", expected=1.2, unit="mL/hr"),
    ],
    hints=[
        "The dose is per kg but the weight is in lb. That conversion is your "
        "first step. From there, the answer needs to be in mL/hr. Work "
        "backwards from there to figure out which units have to cancel.",
        "Three steps. (1) Convert lb to kg using 2.2 lb/kg. (2) Convert the "
        "dose to an hourly drug amount (µg/hr). (3) Divide by the stock "
        "concentration (µg/mL) so the µg cancel and you're left with mL/hr.",
    ],
    steps=[
        SolutionStep(
            "Convert the patient's weight from lb to kg using the standard "
            "clinical factor of 2.2 lb/kg.",
            r"\frac{26.4 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 12 \,kg",
        ),
        SolutionStep(
            "Now dose × weight to get the hourly drug requirement in µg/hr.",
            r"5 \,\tfrac{\mu g}{\cancel{kg}\cdot hr} \times 12\,\cancel{kg} = 60 \,\tfrac{\mu g}{hr}",
        ),
        SolutionStep(
            "Divide by the stock concentration to convert µg/hr to mL/hr. The µg in the "
            "numerator cancels the µg in the denominator of the concentration, leaving mL/hr.",
            r"\frac{60 \,\cancel{\mu g}/hr}{50 \,\cancel{\mu g}/mL} = 1.2 \,\tfrac{mL}{hr}",
        ),
    ],
    final_answer="Pump rate: 1.2 mL/hr.",
    related_calculator_url="/fentanyl",
    related_calculator_name="Fentanyl CRI calculator",
    related_background_url="/learn/fentanyl",
    related_background_name="Fentanyl clinical background",
)


# ---------------------------------------------------------------------------
# Problem 2 — Fluid deficit from % dehydration
# ---------------------------------------------------------------------------

P2 = PracticeProblem(
    slug="dehydration-deficit-20kg",
    title="Replacement volume for an 8 % dehydrated dog",
    topic="Fluid therapy",
    difficulty="Intro",
    scenario=(
        "A 44 lb dog is estimated to be 8 % dehydrated on physical exam. "
        "What replacement volume should you plan for, and at what hourly rate "
        "if you want to correct the deficit over 12 hours (replacement only, "
        "not including maintenance)?"
    ),
    checks=[
        AnswerCheck(label="Total deficit", expected=1600, unit="mL"),
        AnswerCheck(label="Replacement rate", expected=133, unit="mL/hr"),
        AnswerCheck(
            label="Most appropriate replacement fluid",
            expected=0,  # index of "Lactated Ringer's (LRS)"
            choices=(
                "Lactated Ringer's (LRS)",
                "0.45 % NaCl (half-strength saline)",
                "5 % dextrose in water (D5W)",
                "6 % hetastarch",
            ),
        ),
    ],
    hints=[
        "Convert weight to kg first. The deficit formula uses kg. Then "
        "there are two pieces: a total volume and a per-hour rate. Find the "
        "volume first, then split it over the time window.",
        "(1) lb → kg via 2.2 lb/kg. (2) Deficit (in L) = % dehydration as a "
        "decimal × body weight (kg). This uses the simplification that "
        "1 kg of body weight ≈ 1 L of fluid. (3) Divide by hours for the rate.",
    ],
    steps=[
        SolutionStep(
            "Convert the patient's weight from lb to kg.",
            r"\frac{44 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 20 \,kg",
        ),
        SolutionStep(
            "Estimated deficit (in liters) = % dehydration × body weight. "
            "Each kg of body weight is ~1 L of fluid, so % × kg gives liters directly.",
            r"0.08 \times 20\,kg = 1.6 \,L = 1{,}600 \,mL",
        ),
        SolutionStep(
            "Divide by the replacement window to get an hourly rate.",
            r"\frac{1{,}600 \,mL}{12 \,hr} \approx 133 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "This is the deficit-replacement rate alone. Maintenance fluids (typically "
            "2–3 mL/kg/hr in dogs, so ~40–60 mL/hr for this patient) and ongoing losses "
            "would be added on top in a real treatment plan."
        ),
        SolutionStep(
            "For fluid choice: a balanced isotonic crystalloid like LRS is the "
            "standard replacement fluid for dehydration of unknown or mixed "
            "cause. 0.9 % NaCl is also acceptable but is mildly acidifying and "
            "lacks the potassium and buffer of LRS. Hypotonic fluids (0.45 % "
            "NaCl, D5W) are not appropriate for volume replacement; synthetic "
            "colloids like hetastarch are for refractory hypovolemia, not "
            "routine dehydration."
        ),
    ],
    final_answer="Plan to replace 1,600 mL of deficit. At a 12-hour window, replacement alone is ≈ 133 mL/hr.",
    related_calculator_url="/fluid-therapy",
    related_calculator_name="Fluid therapy calculator",
    related_background_url="/learn/fluid-therapy",
    related_background_name="Fluid therapy clinical background",
)


# ---------------------------------------------------------------------------
# Problem 3 — Potassium sliding scale + max rate check
# ---------------------------------------------------------------------------

P3 = PracticeProblem(
    slug="kcl-sliding-scale-3-2",
    title="KCl supplementation: serum K 3.2 mEq/L",
    topic="Electrolytes",
    difficulty="Intro",
    scenario=(
        "A 33 lb dog has a serum potassium of 3.2 mEq/L. Using the standard "
        "sliding scale (add 30 mEq KCl per liter of fluid for K 3.0–3.5), "
        "what volume of 2 mEq/mL KCl injection do you draw up to add to a "
        "1 L bag of LRS? And what's the maximum safe pump rate so you don't "
        "exceed 0.5 mEq/kg/hr?"
    ),
    checks=[
        AnswerCheck(label="Volume of KCl to draw", expected=15, unit="mL"),
        AnswerCheck(label="Maximum pump rate", expected=250, unit="mL/hr"),
    ],
    hints=[
        "Two pieces. The volume of KCl is a one-step unit conversion from "
        "the target mEq using the stock concentration. The rate cap needs "
        "the patient's weight in kg, then a mEq/hr → mL/hr step using the "
        "bag's final mEq/L.",
        "Volume: divide the 30 mEq target by 2 mEq/mL so mEq cancels and "
        "you're left with mL. Rate chain: (1) lb → kg via 2.2 lb/kg. "
        "(2) 0.5 mEq/kg/hr × kg = mEq/hr cap. (3) Divide mEq/hr by "
        "30 mEq/L to get L/hr, then convert L to mL.",
    ],
    steps=[
        SolutionStep(
            "From the sliding scale, K 3.0–3.5 mEq/L needs 30 mEq KCl added "
            "per liter of fluid. For a 1 L bag, that's 30 mEq. The stock is "
            "2 mEq/mL, so we need to convert mEq to mL."
        ),
        SolutionStep(
            "Divide the 30 mEq target by the stock concentration. mEq "
            "cancels, leaving mL.",
            r"\frac{30 \,\cancel{mEq}}{2 \,\cancel{mEq}/mL} = 15 \,mL",
        ),
        SolutionStep(
            "Now for the max pump rate. First convert the patient's weight "
            "from lb to kg.",
            r"\frac{33 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 15 \,kg",
        ),
        SolutionStep(
            "The maximum infusion rate of KCl is 0.5 mEq/kg/hr. Multiply by "
            "the patient's weight to get the per-hour cap.",
            r"0.5 \,\tfrac{mEq}{\cancel{kg}\cdot hr} \times 15\,\cancel{kg} = 7.5 \,\tfrac{mEq}{hr}",
        ),
        SolutionStep(
            "Convert mEq/hr to mL/hr using the bag's final concentration "
            "(30 mEq in 1,000 mL).",
            r"\frac{7.5 \,\cancel{mEq}/hr}{30 \,\cancel{mEq}/L} = 0.25 \,\tfrac{L}{hr} = 250 \,\tfrac{mL}{hr}",
        ),
    ],
    final_answer=(
        "Draw up 15 mL of 2 mEq/mL KCl and add it to the 1 L bag (delivers "
        "30 mEq). Max pump rate ≈ 250 mL/hr. Do not exceed 0.5 mEq/kg/hr."
    ),
    related_calculator_url="/hypokalemia",
    related_calculator_name="Hypokalemia (KCl) calculator",
    related_background_url="/learn/hypokalemia",
    related_background_name="Hypokalemia clinical background",
)


# ---------------------------------------------------------------------------
# Problem 4 — MLK bag build (clinical dose-driven workflow)
# ---------------------------------------------------------------------------

P4 = PracticeProblem(
    slug="mlk-bag-build-24hr",
    title="Build an MLK bag to last 24 hours",
    topic="Multi-drug CRIs",
    difficulty="Clinical",
    scenario=(
        "You're starting an MLK CRI on a 22 lb dog recovering from a "
        "splenectomy. You'd like to run the infusion at 1 mL/kg/hr and "
        "want enough drug in the bag to last 24 hours. Target doses: "
        "morphine 0.2 mg/kg/hr, lidocaine 1.6 mg/kg/hr, ketamine "
        "0.4 mg/kg/hr (all within published ranges). Stock concentrations: "
        "morphine 5 mg/mL, lidocaine 20 mg/mL (2 %), ketamine 100 mg/mL. "
        "What pump rate (mL/hr) do you set, what bag size should you "
        "choose, and how much of each drug do you add?"
    ),
    checks=[
        AnswerCheck(label="Pump rate", expected=10, unit="mL/hr"),
        AnswerCheck(
            label="Standard bag size to use",
            expected=1,  # index of the correct option below
            choices=("100 mL", "250 mL", "500 mL", "1 L"),
        ),
        AnswerCheck(label="Morphine to draw", expected=10.0, unit="mL"),
        AnswerCheck(label="Lidocaine to draw", expected=20.0, unit="mL"),
        AnswerCheck(label="Ketamine to draw", expected=1.0, unit="mL"),
        AnswerCheck(
            label="Could you run this same protocol in a cat?",
            expected=0,  # index of "No: feline lidocaine cardiotoxicity"
            choices=(
                "No: feline lidocaine cardiotoxicity",
                "Yes, at the same doses",
                "Yes, at half the doses",
                "Yes, but omit the ketamine",
            ),
        ),
    ],
    hints=[
        "Convert weight to kg first. Then the planned duration (24 hr) is "
        "what you multiply each per-hour quantity by: pump rate × duration "
        "tells you how much fluid you need (which sets the bag size), and "
        "dose × weight × duration tells you the mg of each drug.",
        "(1) lb → kg via 2.2 lb/kg. (2) Pump rate (mL/hr) = weight × per-kg "
        "rate. (3) Bag volume needed = pump rate × 24 hr; round up to the "
        "next standard bag size. (4) Each drug: total mg = dose × weight × "
        "24 hr; stock volume = total mg ÷ stock concentration. (5) Remove "
        "the combined drug volume from the bag.",
    ],
    steps=[
        SolutionStep(
            "Convert the patient's weight from lb to kg.",
            r"\frac{22 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 10 \,kg",
        ),
        SolutionStep(
            "Pump rate (mL/hr) = weight × per-kg rate. kg cancels.",
            r"10\,\cancel{kg} \times 1 \,\tfrac{mL}{\cancel{kg}\cdot hr} = 10 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "Bag volume needed for a 24-hour infusion = pump rate × duration. "
            "hr cancels, leaves mL.",
            r"10 \,\tfrac{mL}{\cancel{hr}} \times 24 \,\cancel{hr} = 240 \,mL",
        ),
        SolutionStep(
            "240 mL isn't a standard bag size. Round up to the next standard "
            "size (a 250 mL bag) so you have enough fluid for the full 24 "
            "hours. The drug amounts below are still calculated for 24 hr of "
            "infusion; the extra ~10 mL of carrier doesn't change the per-hour "
            "dose because that's set by the pump rate, not the bag size."
        ),
        SolutionStep(
            "Total morphine over 24 hr = dose × weight × duration. Two "
            "cancellations: kg cancels kg, hr cancels hr, leaving mg.",
            r"0.2 \,\tfrac{mg}{\cancel{kg}\cdot\cancel{hr}} \times 10\,\cancel{kg} \times 24\,\cancel{hr} = 48 \,mg",
        ),
        SolutionStep(
            "Volume of morphine stock to draw = mg ÷ concentration.",
            r"\frac{50 \,\cancel{mg}}{5 \,\cancel{mg}/mL} = 10 \,mL",
        ),
        SolutionStep(
            "Lidocaine and ketamine follow the same pattern.",
            r"\text{Lidocaine: } 1.6 \times 10 \times 25 = 400 \,mg \;\to\; \tfrac{400}{20} = 20 \,mL",
        ),
        SolutionStep(
            "",
            r"\text{Ketamine: } 0.4 \times 10 \times 25 = 100 \,mg \;\to\; \tfrac{100}{100} = 1 \,mL",
        ),
        SolutionStep(
            "Total drug volume = 10 + 20 + 1 = 31 mL. Remove 31 mL of saline "
            "from the 250 mL bag, then add the three drugs. The bag now holds "
            "50 mg morphine, 400 mg lidocaine, and 100 mg ketamine in 250 mL "
            "(enough to last 25 hr at 10 mL/hr, comfortably more than the 24 hr "
            "of planned infusion). Pre-loading the bag for its full duration "
            "keeps the drug concentration exactly on target throughout the "
            "infusion."
        ),
        SolutionStep(
            "Note: this protocol is dog-only. Cats are uniquely sensitive to "
            "lidocaine cardiotoxicity (myocardial depression, arrhythmias, "
            "and CNS effects can occur at the MLK lidocaine dose). For feline "
            "multimodal analgesia, consider a single-agent fentanyl, "
            "buprenorphine, or hydromorphone CRI instead."
        ),
    ],
    final_answer=(
        "Pump rate 10 mL/hr in a 250 mL bag (240 mL needed for 24 hr, rounded "
        "up; the bag lasts 25 hr at this rate). Add 50 mg morphine (10 mL), "
        "400 mg lidocaine (20 mL), and 100 mg ketamine (1 mL) after removing "
        "31 mL of saline. Loading the bag for its full duration keeps the "
        "drug concentration exactly on target."
    ),
    related_calculator_url="/analgesia-cri",
    related_calculator_name="MLK CRI calculator",
    related_background_url="/learn/mlk",
    related_background_name="MLK CRI clinical background",
)


# ---------------------------------------------------------------------------
# Problem 5 — Dopamine CRI: 400 mg in 250 mL bag
# ---------------------------------------------------------------------------

P5 = PracticeProblem(
    slug="dopamine-cri-25kg",
    title="Dopamine CRI from a 400 mg / 250 mL bag",
    topic="Vasopressor CRIs",
    difficulty="Clinical",
    scenario=(
        "A 55 lb dog has an intraoperative MAP of 55 mmHg despite fluid loading. "
        "You've prepared a dopamine bag: 400 mg of dopamine in 250 mL of NaCl. "
        "What pump rate (mL/hr) delivers 5 µg/kg/min?"
    ),
    checks=[
        AnswerCheck(label="Pump rate", expected=4.7, unit="mL/hr"),
        AnswerCheck(
            label="MAP target for adequate organ perfusion",
            expected=2,  # index of "≥ 65 mmHg"
            choices=(
                "< 50 mmHg",
                "50–60 mmHg",
                "≥ 65 mmHg",
                "≥ 80 mmHg",
            ),
        ),
    ],
    hints=[
        "Three unit mismatches to fix: lb vs kg, mg vs µg in the bag, and "
        "min vs hr for the dose. Convert weight first, then untangle the "
        "drug-amount units before doing any arithmetic.",
        "(1) lb → kg via 2.2 lb/kg. (2) Bag concentration: 400 mg ÷ 250 mL = "
        "1,600 µg/mL once you put it in matching units. (3) Pump rate "
        "(mL/hr) = (dose × weight × 60) ÷ bag concentration. The 60 converts "
        "µg/min to µg/hr.",
    ],
    steps=[
        SolutionStep(
            "Convert the patient's weight from lb to kg.",
            r"\frac{55 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 25 \,kg",
        ),
        SolutionStep(
            "Next, find the bag's final concentration in µg/mL. 400 mg = 400,000 µg.",
            r"\frac{400{,}000 \,\mu g}{250 \,mL} = 1{,}600 \,\tfrac{\mu g}{mL}",
        ),
        SolutionStep(
            "Compute the µg per minute the patient needs: dose × weight. kg cancels.",
            r"5 \,\tfrac{\mu g}{\cancel{kg}\cdot min} \times 25\,\cancel{kg} = 125 \,\tfrac{\mu g}{min}",
        ),
        SolutionStep(
            "Convert µg/min to µg/hr by multiplying by 60 min/hr.",
            r"125 \,\tfrac{\mu g}{\cancel{min}} \times 60\,\tfrac{\cancel{min}}{hr} = 7{,}500 \,\tfrac{\mu g}{hr}",
        ),
        SolutionStep(
            "Divide by the bag concentration to convert µg/hr to mL/hr. µg cancels.",
            r"\frac{7{,}500 \,\cancel{\mu g}/hr}{1{,}600 \,\cancel{\mu g}/mL} \approx 4.7 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "Titrate to a MAP of at least 65 mmHg; that's the conventional "
            "perfusion threshold below which organ blood flow becomes "
            "pressure-dependent. Below 50–60 mmHg renal autoregulation is "
            "lost and AKI risk rises sharply."
        ),
    ],
    final_answer="Run the dopamine bag at ≈ 4.7 mL/hr to deliver 5 µg/kg/min.",
    related_calculator_url="/dopamine",
    related_calculator_name="Dopamine CRI calculator",
    related_background_url="/learn/dopamine",
    related_background_name="Dopamine clinical background",
)


# ---------------------------------------------------------------------------
# Problem 6 — Insulin CRI for DKA (standard 2.2 U/kg method)
# ---------------------------------------------------------------------------

P6 = PracticeProblem(
    slug="insulin-cri-dka-15kg",
    title="Regular insulin CRI for a 33 lb DKA dog",
    topic="DKA management",
    difficulty="Clinical",
    scenario=(
        "A 33 lb dog presents in DKA with BG 480 mg/dL. You prepare a regular "
        "insulin CRI bag using the standard 2.2 U/kg method: add 2.2 U/kg to 250 mL "
        "of 0.9 % NaCl, then run the first 50 mL through the line to saturate the "
        "tubing (insulin binds to plastic). At what mL/hr should you start the "
        "infusion to deliver 0.05 U/kg/hr?"
    ),
    checks=[
        AnswerCheck(label="Pump rate", expected=4.5, unit="mL/hr"),
        AnswerCheck(
            label="Which insulin do you use for a DKA CRI?",
            expected=0,  # "Regular (short-acting)"
            choices=(
                "Regular (short-acting)",
                "NPH (intermediate-acting)",
                "Glargine (long-acting)",
                "Lispro (rapid-acting)",
            ),
        ),
    ],
    hints=[
        "Convert weight first. Both the loading dose (2.2 U/kg) and the "
        "hourly dose (0.05 U/kg/hr) need kg. Then the 50 mL line prime is "
        "the trick: you've thrown away 50 mL but kept all the insulin.",
        "(1) lb → kg via 2.2 lb/kg. (2) Total U in bag = 2.2 U/kg × kg. "
        "(3) Effective concentration = total U ÷ remaining mL (200, not 250). "
        "(4) Target hourly dose ÷ effective concentration → mL/hr.",
    ],
    steps=[
        SolutionStep(
            "Convert the patient's weight from lb to kg.",
            r"\frac{33 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 15 \,kg",
        ),
        SolutionStep(
            "Total units added to the bag = 2.2 U/kg × weight.",
            r"2.2 \,\tfrac{U}{\cancel{kg}} \times 15 \,\cancel{kg} = 33 \,U",
        ),
        SolutionStep(
            "After priming 50 mL through the line, 200 mL of bag remains. The 33 U are "
            "now in 200 mL of effective volume.",
            r"\frac{33 \,U}{200 \,mL} = 0.165 \,\tfrac{U}{mL}",
        ),
        SolutionStep(
            "Target hourly dose: 0.05 U/kg/hr × 15 kg.",
            r"0.05 \,\tfrac{U}{\cancel{kg}\cdot hr} \times 15\,\cancel{kg} = 0.75 \,\tfrac{U}{hr}",
        ),
        SolutionStep(
            "Pump rate = hourly dose ÷ concentration. U cancels, leaves mL/hr.",
            r"\frac{0.75 \,\cancel{U}/hr}{0.165 \,\cancel{U}/mL} \approx 4.5 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "Why regular insulin? Only short-acting (regular) insulin is "
            "suitable for IV CRI in DKA. Its rapid onset and short half-life "
            "let you titrate against bedside BG checks. The longer-acting "
            "preparations (NPH, glargine, detemir) and the meal-time analogs "
            "(lispro, aspart) are designed for subcutaneous use; their "
            "kinetics make precise IV titration impossible."
        ),
    ],
    final_answer="Start the insulin CRI at ≈ 4.5 mL/hr.",
    related_calculator_url="/insulin-cri-dka",
    related_calculator_name="Insulin CRI (DKA) calculator",
    related_background_url="/learn/insulin-cri-dka",
    related_background_name="Insulin CRI (DKA) clinical background",
)


# ---------------------------------------------------------------------------
# Problem 7 — Free-water deficit for hypernatremia (Adrogue–Madias)
# ---------------------------------------------------------------------------

P7 = PracticeProblem(
    slug="hypernatremia-free-water-30kg",
    title="Free-water deficit in a hypernatremic dog",
    topic="Electrolytes",
    difficulty="Advanced",
    scenario=(
        "A 66 lb dog presents with severe dehydration and serum Na of 170 mEq/L. "
        "You want to correct gradually to a target of 145 mEq/L. Estimate the free-water "
        "deficit. Use total body water = 60 % of body weight."
    ),
    checks=[
        AnswerCheck(label="Free-water deficit", expected=3.1, unit="L"),
        AnswerCheck(
            label="Most appropriate fluid for correction",
            expected=2,  # "0.45 % NaCl or D5W (hypotonic)"
            choices=(
                "0.9 % NaCl (normal saline)",
                "Lactated Ringer's (LRS)",
                "0.45 % NaCl or D5W (hypotonic)",
                "3 % hypertonic saline",
            ),
        ),
    ],
    hints=[
        "Convert lb to kg first. The TBW estimate (60 %) is a fraction of "
        "the kg weight. You're estimating how much pure water you'd need to "
        "dilute existing sodium down to the target.",
        "(1) lb → kg via 2.2 lb/kg. (2) TBW (L) ≈ 0.6 × weight (kg). (3) Free-"
        "water deficit (L) ≈ TBW × ((current Na ÷ target Na) − 1). The Na "
        "ratio is dimensionless so the answer comes out in liters. Don't "
        "forget the safety check on correction rate (no faster than "
        "0.5–1 mEq/L/hr drop).",
    ],
    steps=[
        SolutionStep(
            "Convert the patient's weight from lb to kg.",
            r"\frac{66 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 30 \,kg",
        ),
        SolutionStep(
            "Total body water (TBW) is the fluid compartment we're diluting. For a 30 kg "
            "dog, TBW ≈ 0.6 × 30 = 18 L.",
            r"0.6 \times 30\,kg = 18 \,L",
        ),
        SolutionStep(
            "Free-water deficit (L) ≈ TBW × ((current Na ÷ target Na) − 1). The unit "
            "ratios are dimensionless, so the answer comes out in liters.",
            r"18\,L \times \left(\tfrac{170}{145} - 1\right) = 18 \times 0.1724 \approx 3.1\,L",
        ),
        SolutionStep(
            "That's the free-water deficit alone (volume of pure water needed to bring "
            "Na to target). In practice you'd give a hypotonic crystalloid like D5W, "
            "0.45 % NaCl, or maintenance solutions (not pure water), and correct at no "
            "faster than 0.5–1 mEq/L/hr to avoid cerebral edema."
        ),
        SolutionStep(
            "Sanity check on the correction rate: dropping Na from 170 to 145 is a "
            "25 mEq/L change. At 0.5 mEq/L/hr that needs 50 hours; at 1 mEq/L/hr, 25 hours."
        ),
        SolutionStep(
            "Why a hypotonic fluid? You're trying to drop the serum sodium, "
            "which means giving fluid with a lower Na concentration than the "
            "patient's plasma. Isotonic crystalloids (0.9 % NaCl, LRS) "
            "wouldn't move serum Na meaningfully, and hypertonic saline "
            "would make it worse. 0.45 % NaCl and D5W are both reasonable "
            "choices in dogs; in practice the choice between them depends "
            "on whether you also need volume support (0.45 % NaCl) versus "
            "pure free water (D5W)."
        ),
    ],
    final_answer=(
        "Free-water deficit ≈ 3.1 L. Correct slowly over 25–50 hr "
        "(≤ 0.5–1 mEq/L/hr drop in Na) to avoid cerebral edema."
    ),
    related_calculator_url="/hypernatremia",
    related_calculator_name="Hypernatremia calculator",
    related_background_url="/learn/hypernatremia",
    related_background_name="Hypernatremia clinical background",
)


# ---------------------------------------------------------------------------
# Problem 8 — MLK waste calculation
# ---------------------------------------------------------------------------

P8 = PracticeProblem(
    slug="mlk-waste-100ml",
    title="Controlled-drug waste from a partially used MLK bag",
    topic="Multi-drug CRIs",
    difficulty="Advanced",
    scenario=(
        "You built the MLK bag from problem 4 (50 mg morphine, 400 mg lidocaine, "
        "100 mg ketamine in 250 mL). The patient was extubated and recovered well "
        "after ~15 hours and the CRI was discontinued with 100 mL remaining in "
        "the bag. How much of each controlled drug needs to be logged as waste?"
    ),
    checks=[
        AnswerCheck(label="Morphine wasted (C-II)", expected=20.0, unit="mg"),
        AnswerCheck(label="Ketamine wasted (C-III)", expected=40.0, unit="mg"),
        AnswerCheck(
            label="DEA schedule of morphine",
            expected=1,  # "Schedule II (C-II)"
            choices=(
                "Schedule I (C-I)",
                "Schedule II (C-II)",
                "Schedule III (C-III)",
                "Schedule IV (C-IV)",
            ),
        ),
    ],
    hints=[
        "The bag is a uniform mixture. If you know the fraction of the bag "
        "that wasn't given, that same fraction of every drug in the bag was "
        "wasted.",
        "Wasted fraction = volume remaining ÷ bag volume. Then for each drug: "
        "mg wasted = total mg in bag × wasted fraction. Lidocaine isn't "
        "federally controlled, but the math is the same.",
    ],
    steps=[
        SolutionStep(
            "First, identify the wasted-volume fraction. 100 mL of a 250 mL bag = "
            "100 / 250 = 0.4, or 40 % of the bag was wasted."
        ),
        SolutionStep(
            "Each drug in the bag is wasted proportionally. Morphine wasted = total mg × "
            "wasted fraction. mg stays, the dimensionless fraction multiplies through.",
            r"50 \,mg \times 0.4 = 20 \,mg \text{ morphine (C-II)}",
        ),
        SolutionStep(
            "Same approach for ketamine.",
            r"100 \,mg \times 0.4 = 40 \,mg \text{ ketamine (C-III)}",
        ),
        SolutionStep(
            "Lidocaine is not federally controlled, but you can compute it the same way "
            "for completeness.",
            r"400 \,mg \times 0.4 = 160 \,mg \text{ lidocaine}",
        ),
        SolutionStep(
            "Optional: stock-equivalent volumes for logs that record mL. Divide each "
            "wasted mg by its stock concentration.",
            r"\tfrac{20\,\cancel{mg}}{5\,\cancel{mg}/mL} = 4\,mL \text{ morphine stock-equivalent}",
        ),
        SolutionStep(
            "The physical waste is 100 mL of diluted bag mixture, not undiluted stock. "
            "Most controlled-drug logs want the mg figure since that's what reconciles "
            "against your inventory."
        ),
        SolutionStep(
            "On the schedules: morphine is DEA Schedule II (C-II), a full µ-agonist "
            "opioid with high abuse potential and accepted medical use. Ketamine is "
            "Schedule III (C-III). Both require controlled-drug logging; "
            "lidocaine is not federally scheduled. State scheduling can differ, "
            "and individual practices may have stricter internal policies."
        ),
    ],
    final_answer=(
        "Log 20 mg morphine (C-II) and 40 mg ketamine (C-III) as waste. Lidocaine "
        "is not federally controlled but 160 mg was discarded with the bag."
    ),
    related_calculator_url="/analgesia-cri",
    related_calculator_name="MLK CRI calculator (waste section)",
    related_background_url="/learn/mlk",
    related_background_name="MLK CRI clinical background",
)


# ---------------------------------------------------------------------------
# Problem 9 — Norepi titration: dose change → new mL/hr
# ---------------------------------------------------------------------------

P9 = PracticeProblem(
    slug="norepi-titration-18kg",
    title="Norepinephrine titration: changing the dose",
    topic="Vasopressor CRIs",
    difficulty="Clinical",
    scenario=(
        "A 39.6 lb dog is on a norepinephrine CRI from a 4 mg in 250 mL NaCl bag "
        "(final concentration 16 µg/mL) at 0.05 µg/kg/min. MAP is only 58 mmHg and "
        "you want to titrate up to 0.2 µg/kg/min. What's the new pump rate (mL/hr)?"
    ),
    checks=[
        AnswerCheck(label="New pump rate", expected=13.5, unit="mL/hr"),
        AnswerCheck(
            label="Which adrenergic receptor predominantly drives norepi's pressor effect?",
            expected=0,  # "α-1"
            choices=("α-1", "β-1", "β-2", "Dopaminergic"),
        ),
    ],
    hints=[
        "Convert weight first. The starting dose is a distractor. When you "
        "titrate, you recalculate from the new dose. Same math, new number.",
        "(1) lb → kg via 2.2 lb/kg. (2) Pump rate (mL/hr) = (dose × weight × "
        "60) ÷ bag concentration. The 60 is min → hr. Bag concentration is "
        "already given in µg/mL so no further conversion.",
    ],
    steps=[
        SolutionStep(
            "Convert the patient's weight from lb to kg.",
            r"\frac{39.6 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 18 \,kg",
        ),
        SolutionStep(
            "Compute µg/min at the new dose.",
            r"0.2 \,\tfrac{\mu g}{\cancel{kg}\cdot min} \times 18\,\cancel{kg} = 3.6 \,\tfrac{\mu g}{min}",
        ),
        SolutionStep(
            "Convert µg/min to µg/hr.",
            r"3.6 \,\tfrac{\mu g}{\cancel{min}} \times 60\,\tfrac{\cancel{min}}{hr} = 216 \,\tfrac{\mu g}{hr}",
        ),
        SolutionStep(
            "Divide by bag concentration to get mL/hr.",
            r"\frac{216 \,\cancel{\mu g}/hr}{16 \,\cancel{\mu g}/mL} = 13.5 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "Shortcut for next time: at this bag concentration and weight, mL/hr ≈ "
            "(dose in µg/kg/min) × 67.5. Useful for fast bedside titration once the "
            "first dose is set up."
        ),
        SolutionStep(
            "Why norepinephrine raises blood pressure: it's a potent α-1 "
            "agonist with modest β-1 activity. The α-1 effect is what drives "
            "the pressor response (peripheral vasoconstriction → increased "
            "systemic vascular resistance). The β-1 effect adds modest "
            "inotropy. Unlike dopamine, norepi has minimal effect at "
            "dopaminergic receptors. This is why it's preferred for "
            "vasodilatory shock where the primary problem is loss of "
            "vascular tone."
        ),
    ],
    final_answer="Set the pump to 13.5 mL/hr to deliver 0.2 µg/kg/min.",
    related_calculator_url="/norepinephrine",
    related_calculator_name="Norepinephrine CRI calculator",
    related_background_url="/learn/norepinephrine",
    related_background_name="Norepinephrine clinical background",
)


# ---------------------------------------------------------------------------
# Problem 10 — Phosphate replacement with concurrent K
# ---------------------------------------------------------------------------

P10 = PracticeProblem(
    slug="phosphate-replacement-25kg",
    title="Phosphate replacement: K-Phos addition with concurrent KCl",
    topic="Electrolytes",
    difficulty="Advanced",
    scenario=(
        "A 55 lb DKA dog has serum phosphorus of 1.2 mg/dL (severe). You want to give "
        "K-Phos at 0.03 mmol/kg/hr. K-Phos stock is 3 mmol/mL phosphate, with 4.4 mEq "
        "of potassium per mL (the same vial supplies both). The patient is already on "
        "a fluid line containing 20 mEq/L KCl at 50 mL/hr. Is the combined potassium "
        "delivery safe (cap 0.5 mEq/kg/hr)?"
    ),
    checks=[
        AnswerCheck(label="K-Phos pump rate", expected=0.25, unit="mL/hr"),
        AnswerCheck(
            label="Combined K delivery",
            expected=0.084,
            unit="mEq/kg/hr",
            tolerance_percent=5.0,
        ),
        AnswerCheck(
            label="Is this safe?",
            expected=0,  # index of "Safe: under the cap"
            choices=("Safe: under the cap", "Exceeds the 0.5 mEq/kg/hr cap"),
        ),
    ],
    hints=[
        "Convert lb to kg first. Both the phosphate dose and the K cap "
        "depend on kg. Then three sub-problems: pump rate of K-Phos, K from "
        "the K-Phos, K from the maintenance line. Sum the K and compare to "
        "the cap.",
        "(1) lb → kg via 2.2 lb/kg. (2) K-Phos rate (mL/hr): phosphate dose × "
        "weight ÷ K-Phos phosphate concentration. (3) K from K-Phos: that "
        "rate × 4.4 mEq/mL. (4) K from maintenance line: 20 mEq/L × 50 mL/hr "
        "(watch your L/mL conversion). Sum, divide by weight, compare to "
        "0.5 mEq/kg/hr.",
    ],
    steps=[
        SolutionStep(
            "Convert the patient's weight from lb to kg.",
            r"\frac{55 \,\cancel{lb}}{2.2 \,\cancel{lb}/kg} = 25 \,kg",
        ),
        SolutionStep(
            "Compute the K-Phos rate in mL/hr from the phosphate dose.",
            r"0.03 \,\tfrac{mmol}{\cancel{kg}\cdot hr} \times 25\,\cancel{kg} = 0.75 \,\tfrac{mmol}{hr}",
        ),
        SolutionStep(
            "Convert mmol/hr to mL/hr using the K-Phos phosphate concentration. mmol cancels.",
            r"\frac{0.75 \,\cancel{mmol}/hr}{3 \,\cancel{mmol}/mL} = 0.25 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "Potassium delivered by the K-Phos: each mL has 4.4 mEq K. So 0.25 mL/hr × "
            "4.4 mEq/mL gives the K from K-Phos.",
            r"0.25 \,\tfrac{\cancel{mL}}{hr} \times 4.4 \,\tfrac{mEq}{\cancel{mL}} = 1.1 \,\tfrac{mEq}{hr}",
        ),
        SolutionStep(
            "Potassium from the maintenance line: 20 mEq/L × 50 mL/hr. Convert L to mL "
            "(× 1000) so the mL cancel.",
            r"\frac{20 \,mEq}{1{,}000 \,\cancel{mL}} \times 50 \,\tfrac{\cancel{mL}}{hr} = 1.0 \,\tfrac{mEq}{hr}",
        ),
        SolutionStep(
            "Sum the two sources and divide by weight to check against the 0.5 mEq/kg/hr cap.",
            r"\frac{1.1 + 1.0 \,mEq/hr}{25\,kg} = 0.084 \,\tfrac{mEq}{kg\cdot hr}",
        ),
        SolutionStep(
            "0.084 mEq/kg/hr is well below the 0.5 mEq/kg/hr cap, so combined delivery is safe."
        ),
    ],
    final_answer=(
        "Run K-Phos at 0.25 mL/hr. Combined K delivery is ≈ 2.1 mEq/hr "
        "(0.08 mEq/kg/hr), comfortably below the 0.5 mEq/kg/hr cap."
    ),
    related_calculator_url="/hypophosphatemia",
    related_calculator_name="Hypophosphatemia (K-Phos) calculator",
    related_background_url="/learn/hypophosphatemia",
    related_background_name="Hypophosphatemia clinical background",
)


# ---------------------------------------------------------------------------
# Problem 11 — Simple metabolic acidosis identification
# ---------------------------------------------------------------------------

P11 = PracticeProblem(
    slug="metabolic-acidosis-id-dog",
    title="Identify the primary disturbance: vomiting/diarrhea dog",
    topic="Blood gas · Basic",
    difficulty="Intro",
    scenario=(
        "A 20 kg dog with 3 days of vomiting and diarrhea has the "
        "following arterial blood gas: pH 7.25, PCO₂ 28 mm Hg, "
        "HCO₃⁻ 12 mEq/L. What is the primary acid-base disturbance?"
    ),
    checks=[
        AnswerCheck(
            label="Primary disturbance",
            expected=1,
            choices=(
                "Respiratory acidosis",
                "Metabolic acidosis",
                "Respiratory alkalosis",
                "Metabolic alkalosis",
            ),
        ),
    ],
    hints=[
        "Start with pH. Is the patient acidemic (pH < 7.35) or alkalemic "
        "(pH > 7.46)? That tells you the direction. Then look at HCO₃⁻ "
        "and PCO₂. Which one moved in the direction that explains the pH?",
        "Acidemia + low HCO₃⁻ = metabolic acidosis. Acidemia + high PCO₂ = "
        "respiratory acidosis. The low PCO₂ here is the body's attempt to "
        "compensate (hyperventilation blowing off CO₂), not the primary "
        "process.",
    ],
    steps=[
        SolutionStep(
            "pH is 7.25, which is below the dog reference range "
            "(7.35–7.46). The patient is acidemic.",
        ),
        SolutionStep(
            "HCO₃⁻ is 12 mEq/L (reference 19–26), which is markedly low. "
            "A low HCO₃⁻ would push pH down. This explains the acidemia.",
        ),
        SolutionStep(
            "PCO₂ is 28 mm Hg (reference 31–43), which is also low. A low "
            "PCO₂ would push pH up, so it cannot be causing the acidemia. "
            "It's the compensatory response (hyperventilation).",
        ),
        SolutionStep(
            "Primary disturbance: metabolic acidosis with respiratory "
            "compensation. Loss of HCO₃⁻ in diarrheal fluid is the "
            "classic mechanism here.",
        ),
    ],
    final_answer="Metabolic acidosis (with appropriate respiratory compensation).",
    related_calculator_url="/blood-gas",
    related_calculator_name="Blood gas · Basic",
    related_background_url="/learn/blood-gas",
    related_background_name="Blood gas clinical background",
)


# ---------------------------------------------------------------------------
# Problem 12 — Acute respiratory acidosis (anesthesia hypoventilation)
# ---------------------------------------------------------------------------

P12 = PracticeProblem(
    slug="respiratory-acidosis-anesthesia",
    title="Anesthetized dog hypoventilating",
    topic="Blood gas · Basic",
    difficulty="Intro",
    scenario=(
        "A dog under isoflurane anesthesia has not been mechanically "
        "ventilated. An arterial blood gas drawn 30 minutes into the "
        "procedure shows: pH 7.25, PCO₂ 65 mm Hg, HCO₃⁻ 24 mEq/L. What "
        "is the primary disturbance, and is the bicarbonate response "
        "consistent with a simple disorder?"
    ),
    checks=[
        AnswerCheck(
            label="Primary disturbance",
            expected=0,
            choices=(
                "Acute respiratory acidosis",
                "Chronic respiratory acidosis",
                "Metabolic acidosis",
                "Mixed metabolic and respiratory acidosis",
            ),
        ),
        AnswerCheck(
            label="Expected HCO₃⁻",
            expected=26.0,
            unit="mEq/L",
            tolerance_percent=5.0,
        ),
    ],
    hints=[
        "Acidemia with high PCO₂ is respiratory acidosis. The next question "
        "is acute vs chronic. A dog 30 minutes into anesthesia has had no "
        "time for renal compensation, which takes 2–5 days.",
        "Apply the acute respiratory acidosis rule: HCO₃⁻ rises 0.15 mEq/L "
        "per 1 mm Hg rise in PCO₂. Baseline HCO₃⁻ for dogs is about 22, "
        "baseline PCO₂ about 37.",
    ],
    steps=[
        SolutionStep(
            "pH 7.25 is acidemic. PCO₂ 65 is markedly elevated; HCO₃⁻ 24 "
            "is within reference range but at the upper end. Primary "
            "disturbance is respiratory acidosis driven by inhalant-"
            "induced hypoventilation.",
        ),
        SolutionStep(
            "Time course is acute (30 minutes). Renal compensation takes "
            "2–5 days to fully develop, so HCO₃⁻ should rise only "
            "modestly via intracellular non-bicarbonate buffer titration.",
        ),
        SolutionStep(
            "Apply the dog acute respiratory acidosis rule: PCO₂ went up "
            "by 65 − 37 = 28 mm Hg. Expected HCO₃⁻ rise = 0.15 × 28 = "
            "4.2 mEq/L. Expected HCO₃⁻ ≈ 22 + 4.2 = 26 mEq/L.",
            r"\Delta \text{HCO}_3^- = 0.15 \,\tfrac{mEq/L}{\cancel{mm\,Hg}} \times 28 \,\cancel{mm\,Hg} = 4.2 \,mEq/L",
        ),
        SolutionStep(
            "Observed HCO₃⁻ of 24 is within ±2 of the expected 26, "
            "consistent with simple acute respiratory acidosis. The fix "
            "is mechanical ventilation, not bicarbonate.",
        ),
    ],
    final_answer=(
        "Acute respiratory acidosis from inhalant-induced hypoventilation. "
        "Expected HCO₃⁻ ≈ 26 mEq/L; observed 24 is within range. Simple "
        "disorder. Treat by ventilating, not by giving bicarbonate."
    ),
    related_calculator_url="/blood-gas",
    related_calculator_name="Blood gas · Basic",
    related_background_url="/learn/blood-gas",
    related_background_name="Blood gas clinical background",
)


# ---------------------------------------------------------------------------
# Problem 13 — Mixed: DKA with respiratory compensation overshoot
# ---------------------------------------------------------------------------

P13 = PracticeProblem(
    slug="dka-mixed-disorder",
    title="DKA dog with low PCO₂: simple or mixed?",
    topic="Blood gas · Basic",
    difficulty="Clinical",
    scenario=(
        "A 15 kg dog presents in diabetic ketoacidosis. Arterial blood "
        "gas: pH 7.10, PCO₂ 15 mm Hg, HCO₃⁻ 8 mEq/L. Apply the dog "
        "metabolic acidosis compensation rule and decide whether this "
        "is a simple disorder or a mixed disorder."
    ),
    checks=[
        AnswerCheck(
            label="Expected PCO₂",
            expected=27.0,
            unit="mm Hg",
            tolerance_percent=8.0,
        ),
        AnswerCheck(
            label="Verdict",
            expected=1,
            choices=(
                "Simple metabolic acidosis",
                "Mixed: metabolic acidosis + respiratory alkalosis",
                "Mixed: metabolic acidosis + respiratory acidosis",
                "Pure respiratory alkalosis",
            ),
        ),
    ],
    hints=[
        "First confirm metabolic acidosis is present (it is: low pH, low "
        "HCO₃⁻). Then apply the dog rule: PCO₂ should fall 0.7 mm Hg for "
        "every 1 mEq/L fall in HCO₃⁻ below the reference midpoint.",
        "Baseline HCO₃⁻ ≈ 22, observed is 8, so HCO₃⁻ has fallen by 14. "
        "Expected PCO₂ drop = 0.7 × 14 = 9.8. Expected PCO₂ = 37 − 9.8 ≈ "
        "27 mm Hg. Compare to observed PCO₂ of 15.",
    ],
    steps=[
        SolutionStep(
            "Confirm primary disturbance. pH 7.10 = severe acidemia. "
            "HCO₃⁻ 8 (very low) explains the acidosis; PCO₂ 15 is low, "
            "consistent with compensation. Primary: metabolic acidosis.",
        ),
        SolutionStep(
            "Apply the dog metabolic acidosis rule. HCO₃⁻ fell from "
            "baseline ~22 to observed 8, a drop of 14 mEq/L.",
            r"\Delta \text{HCO}_3^- = 22 - 8 = 14 \,mEq/L",
        ),
        SolutionStep(
            "Expected PCO₂ drop = 0.7 × 14 = 9.8 mm Hg. Expected PCO₂ "
            "from baseline 37 = 37 − 9.8 ≈ 27 mm Hg.",
            r"\text{expected PCO}_2 = 37 - (0.7 \times 14) \approx 27 \,mm\,Hg",
        ),
        SolutionStep(
            "Observed PCO₂ is 15, well below the expected 27 (±2 → "
            "25–29). PCO₂ is lower than compensation alone should produce.",
        ),
        SolutionStep(
            "Conclusion: mixed disorder. Primary metabolic acidosis from "
            "DKA, plus a concurrent respiratory alkalosis (the patient is "
            "hyperventilating beyond what compensation requires, which "
            "could reflect sepsis, pain, anxiety, or central drive from "
            "the ketoacidosis itself).",
        ),
    ],
    final_answer=(
        "Mixed disorder: metabolic acidosis (DKA) plus a concurrent "
        "respiratory alkalosis. PCO₂ of 15 is below the expected 27 ±2 "
        "for simple compensation."
    ),
    related_calculator_url="/blood-gas",
    related_calculator_name="Blood gas · Basic",
    related_background_url="/learn/blood-gas",
    related_background_name="Blood gas clinical background",
)


# ---------------------------------------------------------------------------
# Problem 14 — Anion gap classification (high-AG vs normal-AG)
# ---------------------------------------------------------------------------

P14 = PracticeProblem(
    slug="anion-gap-classification",
    title="High-AG vs normal-AG metabolic acidosis",
    topic="Blood gas · Basic",
    difficulty="Clinical",
    scenario=(
        "Two dogs both present with metabolic acidosis (HCO₃⁻ 12 mEq/L "
        "in both). Dog A: Na 145, Cl 110. Dog B: Na 145, Cl 120. "
        "Compute the anion gap for each, classify each as high-AG or "
        "normal-AG, and pick the differential that fits each."
    ),
    checks=[
        AnswerCheck(label="AG for Dog A", expected=23.0, unit="mEq/L", tolerance_percent=5.0),
        AnswerCheck(label="AG for Dog B", expected=13.0, unit="mEq/L", tolerance_percent=8.0),
        AnswerCheck(
            label="Dog A fits",
            expected=1,
            choices=(
                "Diarrheal HCO₃⁻ loss",
                "Lactic acidosis from septic shock",
                "Renal tubular acidosis",
            ),
        ),
        AnswerCheck(
            label="Dog B fits",
            expected=0,
            choices=(
                "Small bowel diarrhea with HCO₃⁻ loss",
                "Ethylene glycol toxicity",
                "Diabetic ketoacidosis",
            ),
        ),
    ],
    hints=[
        "AG = Na − (Cl + HCO₃⁻). Dog reference range is 13–25 mEq/L. The "
        "anion gap reflects unmeasured anions, mostly proteins plus any "
        "organic acids that have accumulated.",
        "High AG = organic acid added (lactate, ketones, ethylene glycol "
        "metabolites, uremic acids). Normal AG with low HCO₃⁻ = HCO₃⁻ "
        "lost and replaced by Cl⁻ (GI loss, RTA, dilution).",
    ],
    steps=[
        SolutionStep(
            "Dog A: AG = 145 − (110 + 12) = 23 mEq/L. Upper end of normal "
            "(reference 13–25), bordering on high.",
            r"\text{AG}_A = 145 - (110 + 12) = 23 \,mEq/L",
        ),
        SolutionStep(
            "Dog B: AG = 145 − (120 + 12) = 13 mEq/L. Low-normal.",
            r"\text{AG}_B = 145 - (120 + 12) = 13 \,mEq/L",
        ),
        SolutionStep(
            "Dog A has a borderline-high AG with low HCO₃⁻ and a normal "
            "chloride. Pattern fits an organic acid: lactate (sepsis, "
            "hypoperfusion), ketones (DKA), uremic acids, ethylene glycol.",
        ),
        SolutionStep(
            "Dog B has a normal AG with hyperchloremia. Pattern fits "
            "HCO₃⁻ loss replaced by chloride: small bowel diarrhea, "
            "renal tubular acidosis, dilutional acidosis.",
        ),
        SolutionStep(
            "Both dogs have the same HCO₃⁻ but very different "
            "mechanisms. The anion gap is the key distinguishing test.",
        ),
    ],
    final_answer=(
        "Dog A: AG ≈ 23 (high-normal), high-AG pattern fits an organic "
        "acidosis (lactic acidosis from sepsis). Dog B: AG = 13 (normal), "
        "hyperchloremic, fits HCO₃⁻ loss from diarrhea."
    ),
    related_calculator_url="/blood-gas",
    related_calculator_name="Blood gas · Basic",
    related_background_url="/learn/blood-gas",
    related_background_name="Blood gas clinical background",
)


# ---------------------------------------------------------------------------
# Problem 15 — Cat metabolic acidosis: the species caveat
# ---------------------------------------------------------------------------

P15 = PracticeProblem(
    slug="cat-metabolic-acidosis-caveat",
    title="Cat with metabolic acidosis and normal PCO₂",
    topic="Blood gas · Basic",
    difficulty="Clinical",
    scenario=(
        "A 4 kg cat with chronic kidney disease has an arterial blood "
        "gas: pH 7.22, PCO₂ 33 mm Hg, HCO₃⁻ 14 mEq/L. PCO₂ is right at "
        "the cat reference midpoint. If you apply the dog rule for "
        "expected respiratory compensation, you'd predict PCO₂ around "
        "25 mm Hg. Does the observed PCO₂ of 33 mean this cat has a "
        "mixed disorder?"
    ),
    checks=[
        AnswerCheck(
            label="Conclusion",
            expected=2,
            choices=(
                "Yes: mixed metabolic acidosis + respiratory acidosis (PCO₂ higher than expected)",
                "Yes: mixed metabolic acidosis + respiratory alkalosis",
                "No: dog formulas should not be extrapolated to cats with metabolic acidosis",
                "Cannot be determined without lactate measurement",
            ),
        ),
    ],
    hints=[
        "This is a species-specific physiology question, not a math question. "
        "What does DiBartola say about the feline kidney's adaptive response "
        "to metabolic acidosis compared with the dog and the human?",
        "DiBartola Ch. 12 p. 304 explicitly warns that dog and human "
        "compensation formulas should not be extrapolated to cats with "
        "metabolic acidosis. The feline kidney lacks the adaptive "
        "ammoniagenesis response, and the respiratory compensation "
        "response also appears blunted.",
    ],
    steps=[
        SolutionStep(
            "First the math check: cat reference HCO₃⁻ midpoint ≈ 18. "
            "Observed HCO₃⁻ 14, a drop of 4 mEq/L. If we (wrongly) "
            "applied the dog rule: expected PCO₂ drop = 0.7 × 4 = 2.8 mm "
            "Hg. Expected PCO₂ ≈ 31 − 2.8 ≈ 28 mm Hg. Observed 33 is "
            "above this. The dog rule predicts a mismatch.",
        ),
        SolutionStep(
            "But the dog rule should not be applied. DiBartola Ch. 12 "
            "p. 304: \"the feline kidney apparently is unable to adapt "
            "to metabolic acidosis ... cats may not compensate for "
            "metabolic acidosis to the same extent (if at all) as do "
            "dogs and humans. Thus formulas for dogs or humans should "
            "not be extrapolated for use in cats.\"",
        ),
        SolutionStep(
            "The cat may simply not be hyperventilating in response to "
            "the metabolic acidosis. A normal PCO₂ in a cat with "
            "metabolic acidosis is NOT by itself evidence of a mixed "
            "disorder.",
        ),
        SolutionStep(
            "Clinical interpretation in this cat depends on history, "
            "physical exam, and ancillary labs, not on a borrowed "
            "compensation formula. CKD is sufficient to explain the "
            "metabolic acidosis (impaired renal acid excretion).",
        ),
    ],
    final_answer=(
        "No mixed disorder is established by this blood gas. The cat may "
        "not be compensating because cats often don't compensate for "
        "metabolic acidosis. Dog compensation formulas should not be "
        "extrapolated to cats in this setting (DiBartola Ch. 12)."
    ),
    related_calculator_url="/blood-gas",
    related_calculator_name="Blood gas · Basic",
    related_background_url="/learn/blood-gas",
    related_background_name="Blood gas clinical background",
)


# ---------------------------------------------------------------------------
# Problem 16 — Counterbalancing mixed disorder with normal pH
# ---------------------------------------------------------------------------

P16 = PracticeProblem(
    slug="mixed-disorder-normal-ph",
    title="Normal pH but abnormal PCO₂ and HCO₃⁻",
    topic="Blood gas · Basic",
    difficulty="Advanced",
    scenario=(
        "A 30 kg dog with chronic bronchitis presents for acute illness. "
        "Arterial blood gas: pH 7.40, PCO₂ 55 mm Hg, HCO₃⁻ 33 mEq/L. The "
        "pH is normal. Does this dog have an acid-base disorder?"
    ),
    checks=[
        AnswerCheck(
            label="Interpretation",
            expected=1,
            choices=(
                "No disorder: pH is normal",
                "Mixed disorder: chronic respiratory acidosis + metabolic alkalosis",
                "Simple chronic respiratory acidosis (fully compensated)",
                "Simple metabolic alkalosis (fully compensated)",
            ),
        ),
    ],
    hints=[
        "Normal pH does not rule out an acid-base disorder. Two disorders "
        "pulling pH in opposite directions can normalize it. Look at PCO₂ "
        "and HCO₃⁻: both are abnormal, and they're moved in the same "
        "direction. Is that consistent with a single disorder?",
        "Try the chronic respiratory acidosis rule for dogs: HCO₃⁻ rises "
        "0.35 mEq/L per 1 mm Hg rise in PCO₂. Compare the observed HCO₃⁻ "
        "rise to what that rule would predict. If observed > predicted, "
        "there's a metabolic alkalosis on top.",
    ],
    steps=[
        SolutionStep(
            "pH is 7.40, exactly normal. That does NOT mean no disorder. "
            "Compensation never fully normalizes pH; overcompensation does "
            "not occur. A normal pH with both PCO₂ and HCO₃⁻ abnormal "
            "raises strong suspicion of a counterbalancing mixed disorder.",
        ),
        SolutionStep(
            "PCO₂ 55 is high (reference 31–43); HCO₃⁻ 33 is high "
            "(reference 19–26). Both moved in the same direction. A "
            "single primary disorder + compensation can't produce both "
            "abnormalities pushing pH the SAME way. The two would be in "
            "opposite directions if compensation alone were at work.",
        ),
        SolutionStep(
            "Apply the chronic respiratory acidosis rule (chronic "
            "bronchitis suggests longstanding hypercapnia): HCO₃⁻ should "
            "rise 0.35 mEq/L per 1 mm Hg rise in PCO₂.",
            r"\Delta \text{PCO}_2 = 55 - 37 = 18 \,mm\,Hg",
        ),
        SolutionStep(
            "Expected HCO₃⁻ rise from the chronic respiratory rule: "
            "0.35 × 18 = 6.3 mEq/L. Expected HCO₃⁻ ≈ 22 + 6.3 ≈ 28 mEq/L.",
            r"\text{expected HCO}_3^- = 22 + (0.35 \times 18) \approx 28 \,mEq/L",
        ),
        SolutionStep(
            "Observed HCO₃⁻ is 33, well above the predicted 28 (±2 → "
            "26–30). The bicarbonate is higher than chronic respiratory "
            "compensation alone explains. There's a concurrent metabolic "
            "alkalosis.",
        ),
        SolutionStep(
            "Final interpretation: mixed disorder. Chronic respiratory "
            "acidosis (the bronchitis baseline) plus a superimposed "
            "metabolic alkalosis. Common causes in this setting: loop "
            "diuretic use (furosemide for the bronchitis), vomiting, "
            "corticosteroid effects.",
        ),
    ],
    final_answer=(
        "Mixed disorder: chronic respiratory acidosis (from the underlying "
        "bronchitis) plus a concurrent metabolic alkalosis. Observed HCO₃⁻ "
        "of 33 is well above the ~28 predicted by chronic respiratory "
        "compensation alone. Normal pH is a clue here, not reassurance."
    ),
    related_calculator_url="/blood-gas",
    related_calculator_name="Blood gas · Basic",
    related_background_url="/learn/blood-gas",
    related_background_name="Blood gas clinical background",
)


# ---------------------------------------------------------------------------
# Problem 17 — Hypernatremia free water deficit
# ---------------------------------------------------------------------------

P17 = PracticeProblem(
    slug="hypernatremia-water-deficit-10kg",
    title="Free water deficit and safe correction rate",
    topic="Electrolytes",
    difficulty="Clinical",
    scenario=(
        "A 10 kg dog presents after being locked in a hot car (free water "
        "loss without proportional sodium loss). Serum Na is 168 mEq/L. "
        "Using a reference normal of 145 mEq/L, calculate the free water "
        "deficit, the hourly D5W replacement rate over 48 hr, and confirm "
        "the predicted rate of Na correction stays under the 12 mEq/L per "
        "24 hr ceiling."
    ),
    checks=[
        AnswerCheck(label="Water deficit", expected=0.95, unit="L", tolerance_percent=5.0),
        AnswerCheck(label="D5W rate over 48 hr", expected=20.0, unit="mL/hr", tolerance_percent=5.0),
        AnswerCheck(
            label="Predicted Na drop / 24 hr",
            expected=11.5,
            unit="mEq/L",
            tolerance_percent=8.0,
        ),
    ],
    hints=[
        "The deficit formula uses total body water, not body weight directly. "
        "TBW is roughly 0.6 × body weight (kg) for dogs and cats. Using the "
        "raw body weight in place of TBW overstates the deficit by ~67%.",
        "Three steps. (1) TBW = 0.6 × 10 = 6 L. (2) Deficit (L) = TBW × "
        "[(present Na / reference Na) − 1]. (3) Hourly rate = deficit in mL "
        "÷ 48 hr. For the correction-rate check, predicted Na drop over 24 "
        "hr ≈ (168 − 145) × (24 / 48), since the deficit is being replaced over "
        "48 hr so half the correction happens in the first 24.",
    ],
    steps=[
        SolutionStep(
            "Total body water is 60% of body weight for dogs and cats. "
            "For a 10 kg dog:",
            r"\text{TBW} = 0.6 \times 10 \,kg = 6 \,L",
        ),
        SolutionStep(
            "Apply the DiBartola free water deficit formula: TBW × "
            "[(present Na / reference Na) − 1]. The ratio quantifies how "
            "much the patient has concentrated.",
            r"\text{deficit} = 6 \,L \times \left(\frac{168}{145} - 1\right) = 6 \times 0.159 \approx 0.95 \,L",
        ),
        SolutionStep(
            "Convert to mL and spread over 48 hr (the standard DiBartola "
            "replacement window).",
            r"\frac{950 \,mL}{48 \,hr} \approx 20 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "Check the correction rate against the 10–12 mEq/L per 24 hr "
            "ceiling. Over the full 48 hr the Na drops by 23 mEq/L "
            "(168 → 145), so half of that, ≈ 11.5 mEq/L, happens in the "
            "first 24 hr.",
            r"\text{predicted } \Delta\text{Na}_{24} = (168 - 145) \times \frac{24}{48} \approx 11.5 \,\tfrac{mEq/L}{24\,hr}",
        ),
        SolutionStep(
            "11.5 mEq/L per 24 hr is just under the 12 mEq/L ceiling. The "
            "48-hour replacement schedule is safe. If the predicted drop "
            "had exceeded 12, the response would be to lengthen the "
            "replacement window (e.g., to 72 hours) rather than slow the "
            "infusion within the same window."
        ),
    ],
    final_answer=(
        "Water deficit ≈ 0.95 L. D5W at 20 mL/hr × 48 hr. Predicted Na drop "
        "≈ 11.5 mEq/L per 24 hr, just under the 12 mEq/L ceiling, so the "
        "48-hour window is safe. Use 5% dextrose in water as the "
        "replacement fluid since this is pure free-water loss."
    ),
    related_calculator_url="/hypernatremia",
    related_calculator_name="Hypernatremia water deficit calculator",
    related_background_url="/learn/hypernatremia",
    related_background_name="Hypernatremia clinical background",
)


# ---------------------------------------------------------------------------
# Problem 18 — Transfusion volume and rate
# ---------------------------------------------------------------------------

P18 = PracticeProblem(
    slug="transfusion-volume-25kg",
    title="pRBC volume and infusion rates for an anemic dog",
    topic="Electrolytes",
    difficulty="Clinical",
    scenario=(
        "A 25 kg dog has a PCV of 15% from chronic IMHA. You decide to "
        "transfuse pRBC to a target PCV of 25%. Donor pRBC PCV is the "
        "default 80%. Calculate the total pRBC volume needed, the slow "
        "trial rate for the first 30 minutes, and the main rate to "
        "finish the transfusion over a 4-hour total window."
    ),
    checks=[
        AnswerCheck(label="Total pRBC volume", expected=281.0, unit="mL", tolerance_percent=5.0),
        AnswerCheck(label="Slow trial rate", expected=12.5, unit="mL/hr", tolerance_percent=5.0),
        AnswerCheck(label="Main rate (next 3.5 hr)", expected=78.5, unit="mL/hr", tolerance_percent=5.0),
    ],
    hints=[
        "Volume needed depends on three things: the patient's total blood "
        "volume, how much PCV needs to rise, and how concentrated the "
        "donor product is. The math is one equation; the trick is knowing "
        "the species blood-volume constant.",
        "Blood volume = 90 mL/kg in dogs (60 mL/kg in cats). The slow "
        "trial is 0.5 mL/kg/hr for 30 minutes, designed to deliver "
        "0.25 mL/kg total during the trial. The main rate finishes the "
        "remainder over 3.5 hours (4 hours total minus the 30-min trial).",
    ],
    steps=[
        SolutionStep(
            "Compute total blood volume. Dogs have ~90 mL/kg blood volume.",
            r"\text{blood volume} = 90 \,\tfrac{mL}{\cancel{kg}} \times 25\,\cancel{kg} = 2{,}250 \,mL",
        ),
        SolutionStep(
            "Compute the PCV rise needed.",
            r"\Delta\text{PCV} = 25\% - 15\% = 10 \text{ points}",
        ),
        SolutionStep(
            "Apply the transfusion volume formula: total pRBC volume = "
            "(PCV rise / donor PCV) × patient blood volume. The donor PCV "
            "in the denominator captures how concentrated each mL of "
            "product is.",
            r"\text{volume} = \frac{10}{80} \times 2{,}250 \,mL \approx 281 \,mL",
        ),
        SolutionStep(
            "Slow trial rate: 0.5 mL/kg/hr for the first 30 minutes. This "
            "delivers 0.25 mL/kg total during the trial, slow enough that "
            "acute reactions (anaphylaxis, hemolysis, febrile non-hemolytic) "
            "can be detected before a meaningful volume has gone in.",
            r"\text{slow trial} = 0.5 \,\tfrac{mL}{kg \cdot hr} \times 25 \,kg = 12.5 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "Volume given during the slow trial = 0.25 mL/kg × 25 kg = "
            "6.25 mL. Remaining volume = 281 − 6.25 ≈ 275 mL.",
        ),
        SolutionStep(
            "Main rate to finish in 3.5 more hours (4 hr total window):",
            r"\text{main rate} = \frac{275 \,mL}{3.5 \,hr} \approx 78.5 \,\tfrac{mL}{hr}",
        ),
        SolutionStep(
            "Monitor TPR every 15 min during the slow trial and every 30 "
            "min thereafter. Aim to complete the transfusion within 4 hours "
            "to limit bacterial contamination risk in an open product."
        ),
    ],
    final_answer=(
        "Total pRBC volume ≈ 281 mL. Slow trial at 12.5 mL/hr for 30 min, "
        "then main rate at ~78.5 mL/hr for 3.5 hr. Total infusion time "
        "4 hr."
    ),
    related_calculator_url="/transfusion",
    related_calculator_name="Transfusion calculator",
    related_background_url="/learn/transfusion",
    related_background_name="Transfusion clinical background",
)


# ---------------------------------------------------------------------------
# Problem 19 — Tube feeding RER ramp
# ---------------------------------------------------------------------------

P19 = PracticeProblem(
    slug="tube-feeding-cat-ramp",
    title="NG-tube feeding ramp for an inappetent cat",
    topic="Nutrition",
    difficulty="Clinical",
    scenario=(
        "An 8 kg cat is hospitalized for hepatic lipidosis. You place an "
        "NG tube and plan a 3-day ramp to 100% RER using a liquid diet at "
        "1.0 kcal/mL, delivered as four boluses per day. Calculate RER, "
        "the Day 3 daily volume, and the per-bolus volume on Day 3. "
        "Compare the per-bolus volume to the 10 mL/kg per-feeding cap."
    ),
    checks=[
        AnswerCheck(label="RER", expected=333.0, unit="kcal/day", tolerance_percent=3.0),
        AnswerCheck(label="Day 3 daily volume", expected=333.0, unit="mL/day", tolerance_percent=3.0),
        AnswerCheck(label="Per-bolus volume (Day 3)", expected=83.0, unit="mL", tolerance_percent=5.0),
        AnswerCheck(
            label="Does Day 3 bolus exceed the 10 mL/kg cap?",
            expected=0,
            choices=(
                "Yes: 83 mL exceeds the 80 mL cap (10 mL/kg × 8 kg)",
                "No: under the cap",
            ),
        ),
    ],
    hints=[
        "RER is not linear in body weight. It uses an exponent: the "
        "metabolic rate scales with body mass to the 3/4 power. You'll "
        "need to compute 8 raised to the 0.75 power (or use a calculator).",
        "Three steps. (1) RER = 70 × BW^0.75 (BW in kg). For 8 kg, BW^0.75 "
        "≈ 4.76. (2) Day 3 is 100% RER in a 3-day ramp; daily volume = RER "
        "kcal/day ÷ diet kcal/mL. (3) Per-bolus = daily ÷ 4 feedings. The "
        "10 mL/kg cap = 10 × 8 = 80 mL per feeding.",
    ],
    steps=[
        SolutionStep(
            "Compute RER from the standard formula. The 0.75 exponent "
            "reflects allometric scaling: metabolism rises with body "
            "mass but more slowly than linearly.",
            r"\text{RER} = 70 \times (8)^{0.75} \approx 70 \times 4.76 \approx 333 \,\tfrac{kcal}{day}",
        ),
        SolutionStep(
            "The 3-day ramp delivers 33% / 66% / 100% of RER on Days 1, 2, "
            "3 respectively. The ramp is conservative: it gives the GI "
            "tract time to tolerate enteral nutrition and reduces "
            "refeeding-syndrome risk in chronically inappetent patients.",
        ),
        SolutionStep(
            "Day 3 daily kcal target = 100% × 333 = 333 kcal. Convert to "
            "volume of liquid diet at 1.0 kcal/mL:",
            r"\frac{333 \,\cancel{kcal}}{1.0 \,\cancel{kcal}/mL} = 333 \,\tfrac{mL}{day}",
        ),
        SolutionStep(
            "Divide by 4 feedings per day for the per-bolus volume.",
            r"\frac{333 \,mL}{4 \,\text{feedings}} \approx 83 \,\tfrac{mL}{\text{feeding}}",
        ),
        SolutionStep(
            "Compare to the 10 mL/kg per-feeding cap. For an 8 kg cat, "
            "the cap is 80 mL. 83 mL slightly exceeds the cap.",
            r"\text{cap} = 10 \,\tfrac{mL}{\cancel{kg}} \times 8 \,\cancel{kg} = 80 \,\tfrac{mL}{\text{feeding}}",
        ),
        SolutionStep(
            "The fix is to add a fifth feeding rather than push the "
            "individual bolus higher. 333 mL ÷ 5 = ~67 mL per feeding, "
            "comfortably below the 80 mL cap. Boluses larger than the cap "
            "raise the risk of regurgitation and aspiration."
        ),
    ],
    final_answer=(
        "RER ≈ 333 kcal/day. Day 3 (100% RER) = 333 mL/day at 1.0 kcal/mL. "
        "Split across 4 feedings, that's ~83 mL per bolus, which slightly "
        "exceeds the 10 mL/kg per-feeding cap (80 mL). Either add a fifth "
        "feeding (drops bolus to ~67 mL) or accept the marginal overage "
        "with close monitoring for regurgitation."
    ),
    related_calculator_url="/tube-feeding",
    related_calculator_name="Tube feeding calculator",
    related_background_url="/learn/tube-feeding",
    related_background_name="Tube feeding clinical background",
)


# ---------------------------------------------------------------------------
# Registry. Order here is the order they appear on the index page.
# ---------------------------------------------------------------------------

PROBLEMS: tuple[PracticeProblem, ...] = (P1, P2, P3, P4, P8, P5, P6, P7, P9, P10, P11, P12, P13, P14, P15, P16, P17, P18, P19)


def get_problem(slug: str) -> PracticeProblem | None:
    for p in PROBLEMS:
        if p.slug == slug:
            return p
    return None


def topics() -> list[str]:
    """Distinct topics, in the order they first appear in PROBLEMS."""
    seen: list[str] = []
    for p in PROBLEMS:
        if p.topic not in seen:
            seen.append(p.topic)
    return seen


def problems_by_topic() -> list[tuple[str, list[PracticeProblem]]]:
    grouped: dict[str, list[PracticeProblem]] = {}
    for p in PROBLEMS:
        grouped.setdefault(p.topic, []).append(p)
    # Preserve insertion order via topics()
    return [(t, grouped[t]) for t in topics()]
