"""Learning modules — structured content units for the Learn section.

A `LearningModule` bundles the components a clinician progresses through
to learn one topic: the clinical-background article, a video tutorial
(optional), the calculators it teaches, the practice problems it tests,
a post-test quiz, and metadata (learning objectives, estimated time,
instructor identification, content review date).

Modules sit at /learn/<slug>. The /learn/<slug> route falls back to
rendering a plain clinical-background article if no module is
registered with that slug, so existing article URLs stay
backward-compatible while the module system is built out.

The metadata fields (objectives, estimated time, instructor,
last_reviewed, quiz_questions) follow the structure that veterinary CE
accreditation bodies look for, so a module can be submitted for
accreditation later without restructuring the data. Until a given
module is actually accredited, the public-facing UI does not claim CE
credit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuizQuestion:
    """A single multiple-choice question for post-module assessment.

    Question bank lives alongside the module so questions stay
    content-aligned. Can serve as the post-test instrument if/when
    the module is submitted for accreditation.
    """

    prompt: str
    choices: tuple[str, ...]
    correct_index: int  # 0-based index into choices
    explanation: str  # why the correct answer is correct; shown after submit


@dataclass(frozen=True)
class RelatedCalculator:
    """Link to a calculator that this module teaches.

    The href is the calculator's URL; the note is a one-line
    description of why that calculator is relevant to this module
    (the calculator's own catalog blurb is often too generic).
    """

    href: str
    title: str
    note: str


@dataclass(frozen=True)
class LearningModule:
    """A bundled learning content unit.

    Required fields establish the module's clinical content and core
    metadata. Optional fields cover the components a clinician
    progresses through; any may be empty during build-out so modules
    can ship incrementally.
    """

    # Identity and presentation
    slug: str  # URL stem at /learn/<slug>; if matching an existing article slug, supersedes that article's standalone page
    title: str
    summary: str  # 1-2 sentences, shown on the /learn index

    # Module metadata
    objectives: tuple[str, ...]  # 3-5 learning objectives, action verbs
    estimated_minutes: int
    instructor_name: str
    instructor_credentials: str  # full credentials line
    last_reviewed: date

    # Content components — any may be None / empty
    article_slug: str | None = None  # links to content/drugs/<slug>.md
    video_url: str | None = None  # YouTube/Vimeo embed URL
    video_duration_seconds: int | None = None  # for display
    related_calculators: tuple[RelatedCalculator, ...] = ()
    practice_problem_slugs: tuple[str, ...] = ()  # subset of app.practice.PROBLEMS
    quiz_questions: tuple[QuizQuestion, ...] = ()

    @property
    def estimated_minutes_display(self) -> str:
        """Format estimated time for human display.

        '50 minutes' for under an hour, otherwise 'N hours M minutes'.
        """
        if self.estimated_minutes < 60:
            return f"{self.estimated_minutes} minutes"
        hours, mins = divmod(self.estimated_minutes, 60)
        if mins == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        return f"{hours} hour{'s' if hours != 1 else ''} {mins} minutes"


# ---------------------------------------------------------------------------
# Module registry
# ---------------------------------------------------------------------------


_VASOPRESSOR_CRI_SURGERY = LearningModule(
    slug="vasopressor-cri-surgery",
    title="Vasopressor and inotrope CRIs for intraoperative hypotension",
    summary=(
        "Recognize, drug-select, and titrate vasopressor or inotrope "
        "CRIs for the anesthetized patient with fluid-refractory "
        "hypotension. Covers the standard otherwise-healthy case and "
        "the modified approach in patients with cardiac disease or "
        "other fluid-restricted comorbidities. Includes worked "
        "bag-prep math for both common workflows, monitoring, and "
        "weaning."
    ),
    objectives=(
        "Identify when to start a vasopressor or inotrope during "
        "anesthesia, versus fluid bolus or anesthetic depth adjustment.",
        "Differentiate norepinephrine, dopamine, and dobutamine by "
        "receptor profile and clinical indication.",
        "Calculate the bag concentration and pump rate for a "
        "weight-based CRI from a stock vial.",
        "Recognize the safety bounds for each drug: titration ranges, "
        "rate ceilings, and required monitoring.",
        "Adjust an active CRI based on hemodynamic response, and "
        "describe a weaning plan.",
    ),
    estimated_minutes=50,
    instructor_name="Timothy Curran, DVM",
    instructor_credentials=(
        "Module content reviewed against current primary sources cited "
        "at the end of the background article."
    ),
    last_reviewed=date(2026, 5, 17),
    article_slug="vasopressor-cri-surgery",
    video_url=None,
    video_duration_seconds=None,
    related_calculators=(
        RelatedCalculator(
            href="/norepinephrine",
            title="Norepinephrine CRI",
            note=(
                "First-line vasopressor for vasodilatory hypotension. "
                "α₁-predominant; raises MAP without dropping cardiac "
                "output."
            ),
        ),
        RelatedCalculator(
            href="/dopamine-cri",
            title="Dopamine CRI",
            note=(
                "Dose-dependent receptor profile. Useful when "
                "bradycardia accompanies hypotension."
            ),
        ),
        RelatedCalculator(
            href="/dobutamine",
            title="Dobutamine CRI",
            note=(
                "β₁-predominant inotrope. Indicated when poor "
                "contractility is the dominant problem, not "
                "vasodilation."
            ),
        ),
        RelatedCalculator(
            href="/anesthesia",
            title="Anesthesia worksheet",
            note=(
                "Pre-computes dopamine, dobutamine, and norepinephrine "
                "CRI rates for the patient on the table, so the doses "
                "are ready before the BP drops."
            ),
        ),
    ),
    # Practice problems already in the bank that fit this module.
    # See app/practice.py for the slug catalog.
    practice_problem_slugs=(
        "norepi-titration-18kg",
        "dopamine-cri-25kg",
    ),
    quiz_questions=(
        QuizQuestion(
            prompt=(
                "A 24 kg dog under isoflurane anesthesia has MAP "
                "55 mmHg after a 10 mL/kg crystalloid bolus and "
                "reduction of vaporizer setting from 1.8% to 1.2%. "
                "The dog is normocardic (HR 95) with normal "
                "contractility on echo. Which CRI is the most "
                "appropriate first choice?"
            ),
            choices=(
                "Dobutamine 5 µg/kg/min",
                "Norepinephrine 0.1 µg/kg/min",
                "Dopamine 10 µg/kg/min",
                "Phenylephrine bolus 1 µg/kg",
            ),
            correct_index=1,
            explanation=(
                "Vasodilatory hypotension after fluid bolus and "
                "anesthetic depth adjustment is the textbook "
                "norepinephrine indication: it restores vascular "
                "tone without lowering cardiac output. Dobutamine "
                "raises CO but doesn't address vasodilation and can "
                "drop MAP further. Dopamine at 10 µg/kg/min has more "
                "chronotropic effect than this patient needs. "
                "Phenylephrine boluses are short-acting and don't "
                "address an ongoing vasodilatory state."
            ),
        ),
        QuizQuestion(
            prompt=(
                "Norepinephrine is supplied as a 1 mg/mL solution. "
                "You want to prepare a CRI for a 15 kg dog starting "
                "at 0.1 µg/kg/min, run at 3 mL/hr. How much "
                "norepinephrine should be added to a 250 mL bag of "
                "0.9% NaCl to achieve this?"
            ),
            choices=(
                "0.15 mg (0.15 mL of the 1 mg/mL stock)",
                "1.5 mg (1.5 mL of stock)",
                "7.5 mg (7.5 mL of stock)",
                "15 mg (15 mL of stock)",
            ),
            correct_index=2,
            explanation=(
                "Step 1, convert the dose to a per-hour amount "
                "for the patient. Multiply by the weight (kg "
                "cancels) and by 60 (min cancels): "
                "$$\\frac{0.1\\,\\mu g}{\\cancel{kg}\\cdot\\cancel{min}} \\times 15\\,\\cancel{kg} \\times \\frac{60\\,\\cancel{min}}{hr} = \\frac{90\\,\\mu g}{hr}$$"
                "Step 2, find the bag concentration. You want the "
                "pump at 3 mL/hr, so the bag must put 90 µg into "
                "every 3 mL (hr cancels): "
                "$$\\frac{90\\,\\mu g}{\\cancel{hr}} \\times \\frac{1\\,\\cancel{hr}}{3\\,mL} = \\frac{30\\,\\mu g}{mL}$$"
                "Step 3, total drug for the 250 mL bag "
                "(mL cancels): "
                "$$\\frac{30\\,\\mu g}{\\cancel{mL}} \\times 250\\,\\cancel{mL} = 7{,}500\\,\\mu g = 7.5\\,mg$$"
                "Step 4, volume of stock to draw from a 1 mg/mL "
                "vial (mg cancels): "
                "$$\\frac{7.5\\,\\cancel{mg}}{1} \\times \\frac{1\\,mL}{1\\,\\cancel{mg}} = 7.5\\,mL$$"
                "Add 7.5 mL of stock to the 250 mL bag. The "
                "Norepinephrine CRI calculator performs this "
                "conversion automatically."
            ),
        ),
        QuizQuestion(
            prompt=(
                "Which monitoring is required during a "
                "norepinephrine CRI?"
            ),
            choices=(
                "Pulse oximetry only.",
                "Pulse oximetry plus continuous ECG.",
                "Continuous invasive arterial blood pressure (or "
                "high-frequency oscillometric NIBP) and ECG.",
                "Hourly oscillometric NIBP cycling and ECG.",
            ),
            correct_index=2,
            explanation=(
                "Norepinephrine titrates to MAP, so MAP must be "
                "monitored continuously or near-continuously. "
                "Invasive arterial monitoring is ideal; high-frequency "
                "oscillometric (cycling every 1-2 min) is acceptable. "
                "Hourly cycling is too infrequent to titrate safely. "
                "Continuous ECG catches the arrhythmogenic complication "
                "(ventricular arrhythmias) that mandates rate reduction "
                "or drug switch."
            ),
        ),
        QuizQuestion(
            prompt=(
                "A 30 kg dog is on dopamine 5 µg/kg/min for "
                "intraoperative hypotension. MAP is now 75 mmHg and "
                "stable. The dog has recovered hemodynamically and "
                "anesthesia is about to end. What is the appropriate "
                "approach to discontinuation?"
            ),
            choices=(
                "Stop the CRI when the dog is extubated.",
                "Halve the rate, recheck MAP in 10 minutes; if "
                "stable, halve again; continue until off.",
                "Continue at full rate for 30 minutes post-extubation, "
                "then stop.",
                "Switch to oral pimobendan and stop dopamine immediately.",
            ),
            correct_index=1,
            explanation=(
                "Vasopressors and inotropes are weaned, not stopped "
                "abruptly. Halving the rate every 10-15 minutes while "
                "monitoring MAP allows the endogenous catecholamine "
                "response to take over without an overshoot of "
                "hypotension. Abrupt discontinuation in a still-"
                "anesthetized or recently-anesthetized patient risks "
                "rebound hypotension. Pimobendan has a different "
                "mechanism (inodilator) and isn't a substitute for "
                "weaning."
            ),
        ),
        QuizQuestion(
            prompt=(
                "Dobutamine is most appropriately chosen over "
                "norepinephrine when:"
            ),
            choices=(
                "MAP is below 50 mmHg from any cause.",
                "The patient has known dilated cardiomyopathy and "
                "poor contractility, with hypotension driven by low "
                "cardiac output rather than vasodilation.",
                "The patient is tachycardic and hypotensive after "
                "fluid resuscitation.",
                "Vasodilation from isoflurane is the suspected "
                "primary cause of hypotension.",
            ),
            correct_index=1,
            explanation=(
                "Dobutamine is a β₁-predominant inotrope: its job is "
                "to improve contractility. It's indicated when poor "
                "cardiac output is the mechanism driving hypotension, "
                "as in dilated cardiomyopathy or myocardial "
                "dysfunction. For pure vasodilation (option 4) or "
                "vasodilatory shock unresponsive to fluids (option "
                "3), norepinephrine is the better choice because it "
                "restores vascular tone. Choosing by MAP alone "
                "(option 1) doesn't address the underlying mechanism."
            ),
        ),
    ),
)


# Top-level registry. Add new modules here.
MODULES: tuple[LearningModule, ...] = (
    _VASOPRESSOR_CRI_SURGERY,
)


_MODULE_BY_SLUG: dict[str, LearningModule] = {m.slug: m for m in MODULES}


def get_module(slug: str) -> LearningModule | None:
    """Return the module with the given slug, or None if unregistered."""
    return _MODULE_BY_SLUG.get(slug)


def all_modules() -> tuple[LearningModule, ...]:
    """Return every registered module, in registration order."""
    return MODULES
