# InfusionFox content style guide

This document covers the **copy** on every calculator and hub page —
catalog blurbs, intros, warnings, captions, button labels. It exists so
the catalog reads as one product, not 44 different people's writing
styles.

For the engineering contract (testing, citations, validation) see
`CONTRIBUTING.md`. For the science (where doses and protocols come
from) see `SOURCES.md`. **This file is about words.**

---

## Why a style guide

A clinical-reference site lives or dies on trust. Inconsistent copy
makes users second-guess the math. The eye notices when one page says
"Workflow for X. Y is the cornerstone..." and the next says
"Confirmation of X in patients whose history..." — even before the
brain articulates *why* it noticed. If the prose can't keep a steady
voice, why would the doses?

Tight, uniform copy also gets out of the way faster. Clinicians don't
read intros — they scan for the calculator. Long intros are a tax on
people whose attention is in the cage.

---

## The two text fields, what they're for

Every entry has two pieces of copy that the rest of the site keys off:

### `catalog_blurb` — the card on `/calculators` or `/hubs`

**One sentence. ~12-20 words. Period at the end.**

What it does: tells the user, in one breath, what this is. The user is
scanning a page of 30+ cards; they have ~half a second before they
move on.

What it does NOT do: list doses, cite sources, name acronyms beyond
CRI/IV/IM, link to other pages, or qualify with "see the page for
details."

**Good:**

> First-line vasopressor for vasodilatory hypotension after fluid
> resuscitation.

> IV loading dose plus CRI for sustained opioid analgesia in dogs and
> cats.

> Workflow combining fluids, insulin, electrolytes, and bicarbonate
> for diabetic ketoacidosis.

**Bad:**

> Potent α₁ vasopressor with mild β₁ inotropic activity. Restores mean
> arterial pressure in vasodilatory hypotension after adequate fluid
> volume has been delivered. Two main settings… [too long, two
> sentences, leads with mechanism, names receptors]

> Per Plumb's: hydromorphone is an IV opioid. [naming a source]

> See the hub for full workflow. [referring out before delivering anything]

### `indications_summary` — the intro paragraph on the page itself

**One to two sentences. ~30-50 words total. ~200-350 chars.**

What it does: tells the user what the calculator computes, who the
patient is (species), and the one most important caveat for using it
correctly *or* a use-case category (not a single indication).

What it does NOT do: list every indication, cite sources (those live
in the Sources section), name textbooks or paper authors, drop URLs
("see the /hyperkalemia-emergency hub"), include doses, or pile on
clinical detail that belongs in the clinical-background article.

**Good:**

> Vasopressor CRI for dogs and cats. Used to restore mean arterial
> pressure in vasodilatory hypotension once volume resuscitation is
> adequate, including inhalant-induced anesthetic hypotension and
> septic or other distributive shock. High-alert medication;
> continuous BP and ECG monitoring required given dose-related
> arrhythmia and peripheral ischemia risk.

> Builds a complete IV fluid plan for any dehydrated dog or cat.
> Enter weight, % dehydration, and ongoing losses; outputs
> shock-bolus volumes if needed, deficit replacement over a chosen
> 4-24 hr window, maintenance rate, and the combined active-phase
> and post-rehydration rates the pump should run at.

**Bad:**

> Short-acting µ-opioid for moderate-to-severe acute pain:
> postoperative and perioperative analgesia, pancreatitis,
> peritonitis, neoplastic pain, aortic thromboembolism, and other
> inpatient analgesia where a continuous opioid infusion is
> appropriate. The CRI form is well suited to critical illness
> because… [Five sentences. Lists every conceivable indication.
> Reads like a textbook chapter, not a tool.]

> 10% calcium gluconate 0.5–1.5 mL/kg IV slowly over 10–20 min for
> emergency membrane stabilization. Onset 1–3 min… [doses belong in
> the calculator output, not the intro]

---

## Rules that apply to both fields

### 1. Lead with what the calculator *is*, not one indication.

Calculators that serve multiple indications shouldn't open by naming
one. **Fluid therapy** handles DKA, parvo, pancreatitis, Addisonian
crisis, shock, gastroenteritis, and post-op — picking one shortchanges
the rest. Same for ketamine CRI, lidocaine CRI, norepinephrine, etc.

If a calculator really is single-indication (e.g., insulin CRI for
DKA — the sliding scale is built for DKA specifically), naming the
indication is fine and useful.

### 2. Name the species in the first sentence.

The clinician reading needs to know whether this applies to their
patient. "in dogs and cats", "in dogs only", "in cats only" — first
sentence, ideally as a phrase attached to the noun ("vasopressor CRI
**for dogs and cats**") not a separate fact buried later.

Dog- or cat-only restrictions deserve emphasis because someone will
otherwise try to use the wrong protocol on the wrong species.

### 3. Use generic drug names, lowercase, in running prose.

`norepinephrine`, not `Norepinephrine` or `Levophed` (brand). The only
times a generic drug name is capitalized:

- At the start of a sentence.
- In a heading or title (`Norepinephrine CRI` page title).

Brand names go in clinical-background articles, not the intro.

### 4. No source citations in the intro.

Sources live in:

- The dedicated **Sources section** at the bottom of each calculator
  page (driven by the `sources` tuple on `CalculatorConfig` or the
  hardcoded source list in the calculator module).
- `SOURCES.md` in the repo root.
- The clinical-background article at `/learn/<slug>` where applicable.

Inline citations like "per Plumb's", "per Silverstein", "Iocolano 2025
JAVMA", "the Reagan 2026 Addison Detect Tool" make the intro read like
a literature review. They also age badly — when a source updates, the
intro is the last place anyone remembers to fix.

The one exception: when a standard of care is universally known by its
publishing body (e.g., "per the 2024 RECOVER CPR guidelines"), naming
it is informative because it tells the clinician *which version* of a
universally-followed protocol the math comes from. Use this sparingly.

### 5. No cross-page URLs in prose.

Cross-links between calculators and hubs are useful UI features.
Putting them inside the intro paragraph isn't:

❌ "See the /hyperkalemia-emergency hub for the full workflow."

✓ The hyperkalemia-emergency hub has its own card on `/hubs` and gets
linked from the catalog. The calcium gluconate page lists itself
inside the hyperkalemia hub's component-calculator section. The user
discovers the connection through the hub UI, not through an inline URL.

The one exception: dual versions of the same hub (canine/feline status
epilepticus, dopamine 6×kg vs. standard method) carry an inline link
to their counterpart because the pages are mirror twins and switching
between them is the dominant action.

### 6. No bare HTML entities.

If the source string contains `<`, `>`, `&`, `"`, or `'`, write them
plain. Jinja's autoescape will handle the rendering. **Never** write
`&lt; 15 kg` — you'll see the literal characters on the page.

### 7. Consistent species phrasing.

Pick one of these patterns and use it consistently within the same
intro:

- "in dogs and cats" (post-modifier on the noun)
- "for dogs and cats" (purpose-modifier)
- "dog-only" or "cats only" (when restricted)

Mixing them in adjacent sentences ("...in dogs and cats. Useful in
dogs.") is jarring.

### 8. American spelling.

`anesthesia`, not `anaesthesia`. `edema`, not `oedema`. `esophagus`,
not `oesophagus`. The audience is mostly US; the textbooks the math
comes from (Plumb's, Silverstein, Ettinger, DiBartola, NRC, IRIS,
RECOVER) are predominantly US spelling.

### 9. Numerals for numbers, except at sentence start.

"15 mEq/L" not "fifteen mEq/L". "3 mg/kg" not "three mg/kg". When a
number lands at the start of a sentence: rephrase to move it
mid-sentence rather than spelling it out.

### 10. Dashes: prefer periods and commas in prose.

- **Em-dash (`—`):** use sparingly. A period or comma is almost
  always cleaner. Reserve em-dashes for the rare case where a
  comma would be genuinely ambiguous (e.g., parenthetical setoff
  in a sentence that already contains commas) and a parenthesis
  would lose the flow. If you write more than one em-dash on a
  page, rewrite one of them.
- **En-dash (`–`):** numeric ranges only. "0.05–0.5 µg/kg/min",
  "3–4 days", "385–396" (page ranges). Never in prose between
  words.
- **Hyphen (`-`):** compound modifiers before a noun
  ("short-acting opioid", "small-bore tube", "high-risk patient")
  and a handful of prefixes that need it for readability
  ("anti-emetic", "non-functional"). Default to closed forms for
  common prefixes ("reevaluate" → prefer "recheck"; "replacement"
  beats "re-placement"; "post-op" is fine but "postoperative" is
  closed). If you find yourself reaching for a hyphen, ask whether
  the closed form is already an English word.

Don't use straight `--` or three dashes. The em-dash crutch is
the most common copy issue on this site: when in doubt, period.

---

## What belongs *outside* the intro

The intro is real-estate-constrained. These things have proper homes
elsewhere:

| Content | Where it goes |
|---|---|
| Specific doses, mg/kg, mL/hr | The calculator's result panel and dose tables |
| Onset/duration | Clinical background article or the page's dedicated reference section |
| ECG criteria, threshold values | "When to use this" section on the page, or in the warnings block |
| List of indications | Clinical background article |
| List of common scenarios / case examples | Clinical background article |
| Source attributions | Sources section (auto-rendered from `sources` tuple) |
| Cross-links to other pages | Catalog cards on `/hubs` and `/calculators`, hub component sections, inline content links where contextually relevant |
| Safety reminders | The warnings block at the top of the page (`<div class="warnings danger">`) |
| Stock concentration / preparation notes | Calculator inputs and warnings, not prose |

**Rule of thumb:** if you find yourself writing the third sentence of
an intro, ask whether what you're about to say belongs in the
clinical-background article instead.

---

## Every calculator has a clinical background article

Every calculator on the site is paired with a long-form article at
`/learn/<slug>`. This is non-negotiable. The calculator is the
*answer* — the doses, the rates, the volumes — and the clinical
background is the *reason* the answer is correct. A site that ships
the answer without the reason looks like a dose generator. A site
that ships both looks like a reference. The difference is what
clinicians come back for.

What the article covers, at a minimum:

- **When to use this calculator / drug / protocol.** Indications,
  contraindications, the patient profile.
- **The clinical reasoning behind the numbers.** Why these doses,
  why this ramp, why this tube type. Not just *what* but *why*.
- **Species-specific differences** that affect use (cat vs. dog
  pharmacology, breed-specific cautions, life-stage adjustments).
- **Monitoring** during use and **discontinuation** criteria.
- **Sources** — the primary references, not just the textbook.

Length varies. A simple electrolyte calculator may need 40 lines;
something like fluid therapy or tube feeding needs 100+. Write what
the topic deserves, not a fixed word count.

### Required wiring

When you add a new calculator, **all three pieces must land in the
same change**:

1. **The calculator** itself (`app/calculators/<slug>.py` with a
   `<NAME>_CATALOG_ENTRY` dict) and its route/template.
2. **The article file** at `content/drugs/<slug>.md`. The filename
   must match the `slug` field of the catalog entry exactly.
3. **The catalog registration** in `app/routers/content.py`. Add
   the catalog entry to `_CUSTOM_ROUTE_CATALOG` so `/learn/<slug>`
   resolves the calculator's display name and category. Without
   this step the article returns 404.

The calculator page template must include the Clinical background
link in its tab nav:

```html
<nav class="calc-tabs">
    <a href="#calculator" class="active">Calculator</a>
    <a href="/learn/<slug>">Clinical background</a>
    ...
</nav>
```

### Article voice

The clinical background reads like a senior clinician explaining
something to a junior colleague who already knows the basics. It is
*not* a textbook chapter, not a literature review, and not a
patient education handout. Specifically:

- Write in second person ("you place the tube under brief
  sedation") or impersonal ("the tube is placed under brief
  sedation"), never first person.
- Numerals over spelled-out numbers (per the rules above).
- Generic drug names lowercase in running prose.
- Inline citations are fine when the claim is contested or unusual
  (e.g., "Chan 2020 argues against illness factors"); otherwise
  pile sources in the Sources section at the bottom.
- No more than 2-3 markdown heading levels (`##` and `###`). A
  forest of subheadings reads like a slide deck.

### Markdown content shares an article when calculators share clinical context

If two calculators are pharmacologically identical and differ only
in preparation recipe (e.g., dopamine standard CRI vs. dopamine 6×kg
prep), they share one `.md` file via the `ARTICLE_SLUG_ALIASES` map
in `content/routes/content.py`. The header on each calculator page
still says the calculator-specific name; only the article body is
shared. Don't duplicate long-form content.

### Sources: prefer freely-available corroboration

The clinical-background article and the calculator's `sources` tuple
should usually include a freely-available secondary source that
corroborates the paywalled or textbook primary source, when one
exists.

Why this matters:

- **Auditability.** A clinician who hasn't bought the textbook can
  still verify the calculator's logic. "Trust me, it's in Silverstein
  Ch. 126" is not a verifiable claim for someone without the book.
- **Politically neutral authority.** WSAVA, AVMA, ACVECC, and similar
  professional-body publications carry institutional weight without
  manufacturer affiliation. Listing one of these alongside the
  primary citation makes it harder to dismiss the calculator as
  reflecting a single author's preferences.
- **Global reach.** Many of the textbooks InfusionFox relies on
  (Silverstein, Plumb's, Ettinger) are US-published and reflect US
  practice. Freely-available WSAVA documents are written for a
  worldwide audience and corroborate the same numbers.

What this looks like in practice:

- Cite the primary source first (Silverstein chapter, NRC document,
  the original drug-development paper) because it's where the
  numbers come from.
- Cite the corroborating freely-available source second. The most
  common patterns:
  - **WSAVA Global Nutrition Toolkit** for nutrition calculators
    (RER targets, tube feeding, weight management).
  - **ACVECC consensus statements** for emergency-medicine
    calculators when one exists for the topic.
  - **Plumb's Veterinary Drugs** (subscription, widely accessible
    in clinics) as a dose-corroboration secondary for drug
    calculators.
  - **Free-access journal articles** (open-access journals, PMC
    deposits) when the same numbers appear in a peer-reviewed venue.

Don't pile on citations to look comprehensive. Cherry-picking
sources that only tangentially touch the calculator's logic
weakens, not strengthens, the article. If a secondary source
corroborates the primary, include it; if it doesn't, don't.

If no freely-available corroborating source exists for a particular
calculator, that's worth a note in a `# TODO` comment in the source
tuple so future contributors know it's an outstanding gap, not an
oversight.

---

## Style for other on-page copy

### Warnings (`<div class="warnings danger">`)

- Short bullet items. Each bullet is one declarative sentence or one
  imperative ("Check blood glucose first.").
- The *most important* warning leads. If there's one thing a user
  must read before computing, it goes first.
- No prose paragraphs. If a warning needs more than three sentences,
  it belongs in clinical-background.
- Species-specific warnings (cat HCM, lidocaine in cats) surface
  unconditionally for the affected species — this is in
  `CONTRIBUTING.md` as a non-negotiable.

### Result panel labels

- Match the case of the source: "CRI rate" (display label) but
  "mL/hr" (unit, lowercase).
- Units always have a space between number and unit: "1.87 mL/hr".
  Exception: percent and degree have no space ("11%", "39.4°C").
- "Display" vs. "Exact" when showing rounded vs. full-precision
  values is the canonical pattern; reuse it.

### Reference tables

- Column headers are sentence-case ("Drug", "Dose", "Volume"), not
  Title Case.
- Sub-labels under a drug name go in monospace, smaller font —
  used for stock concentration ("2 mg/mL") under the drug name.
- The first row of every dose table is the most commonly used
  preparation. Variants follow.

### Button labels

- One or two words, sentence case ("Calculators", "Browse",
  "Sign in").
- Verbs preferred ("Browse calculators") for primary CTAs; nouns
  fine for nav ("Reference").
- No periods.

---

## Worked-example div pattern (engineering note that affects copy)

When a calculator page shows a "Worked example with current inputs"
LaTeX block, the `<div id="worked-example">` must **always be
rendered**, even on initial page load when `result` is `None`.

The HTMX-driven update flow writes into the existing div by ID; if
the div is conditionally rendered, the JS bails silently and the user
sees stale content.

✓ Correct pattern:

```jinja
<h3>Worked example with current inputs</h3>
<div id="worked-example" class="formula-display">
    {% if result %}
        $$...$$
    {% else %}
        <p style="color: var(--ink-mute); font-style: italic; margin: 0;">
            Enter a patient weight to see the worked example.
        </p>
    {% endif %}
</div>
```

❌ Bug pattern (causes stale-worked-example bug):

```jinja
{% if result %}
<h3>Worked example with current inputs</h3>
<div id="worked-example" class="formula-display">$$...$$</div>
{% else %}
<p>Enter a patient weight...</p>
{% endif %}
```

The placeholder text must live *inside* the div, not as an alternative
to it. See `calculator.html` for the canonical pattern.

---

## Default weight inputs (engineering note)

**Calculator pages never default to a non-empty patient weight.** The
weight input renders as an empty string on initial GET; the result
panel renders the `_invalid_input_placeholder.html` partial reading
"Enter a patient weight to see the result." Computation only begins
once the user types a value, at which point HTMX fires the POST.

Why this matters: a pre-filled weight (e.g. "22" lb in the input)
silently encourages clinicians to read the rendered doses without
realizing the calculator never received their patient's weight. Even
one dose given to a 60 lb dog from a calculator that defaulted to 22 lb
is a serious harm, and pre-filling makes that misread easier. An empty
field with a clear "enter a weight" placeholder makes the dependency
on patient weight obvious.

This applies to *every* weight-driven calculator, regardless of
whether the rest of the form has defaults. Pick reasonable defaults
for species, units, route, ramp length, feedings per day, and any
other non-weight field, but leave weight empty.

✓ Correct pattern in the route handler:

```python
@router.get("/example", response_class=HTMLResponse)
async def example_page(request: Request):
    inputs = _default_inputs()  # internal dataclass uses 1.0 to satisfy type
    return templates.TemplateResponse(
        "example.html",
        {
            "request": request,
            "inputs": inputs,
            "result": None,                   # do not call compute() here
            "current_weight_value": "",       # template binds the input to this
            ...
        },
    )
```

And in the template:

```jinja
<input type="number" ... name="current_weight_value"
       value="{{ current_weight_value if current_weight_value is defined else inputs.current_weight_value }}"
       required>
```

❌ Bug pattern:

```python
inputs = TubeFeedingInputs(current_weight_value=22.0, ...)
result = compute_tube_feeding(inputs)   # don't pre-compute on GET
return templates.TemplateResponse(..., {"result": result, "current_weight_value": "22"})
```

The internal dataclass field can carry a placeholder like `1.0` to
satisfy type-checking, but the **string passed to the template** as
`current_weight_value` must be `""`, and **`result` must be `None`**
on initial load. See `app/routers/energy.py` and
`app/routers/tube_feeding.py` for canonical examples.

---

## Adding a new calculator: copy checklist

Before merging a new calculator, walk through this:

- [ ] Catalog blurb is one sentence, 12-20 words, no doses or
      citations, species named.
- [ ] Intro paragraph is 1-2 sentences, 30-50 words, leads with what
      the calculator *is*, names species, doesn't list one
      indication when there are several.
- [ ] No source citations in the intro (they're in `sources` tuple
      and in `SOURCES.md`).
- [ ] No `&lt;` `&gt;` `&amp;` literals in any source string.
- [ ] No cross-page URLs in the intro paragraph.
- [ ] Species-specific cautions surface as warnings, not as
      sentences buried in the intro.
- [ ] **Clinical background article exists** at
      `content/drugs/<slug>.md`, the catalog entry is registered in
      `_CUSTOM_ROUTE_CATALOG` in `app/routers/content.py`, and the
      calculator template's tab nav includes a `Clinical background`
      link to `/learn/<slug>`.
- [ ] **Sources include a freely-available secondary** corroborating
      the primary source where one exists (WSAVA toolkit, ACVECC
      consensus, open-access journal). If none exists, that's noted
      as a `# TODO` in the sources tuple.
- [ ] The `<div id="worked-example">` is always rendered (test it
      with an initial GET — should be present even before any
      input).
- [ ] **Weight input is empty on initial GET** (no pre-filled
      numeric default), result panel shows the "Enter a patient
      weight" placeholder, and no computed numbers appear until
      the user types a weight.
- [ ] American spelling.

When in doubt: look at how `fluid_therapy.py`, `norepinephrine` (in
`drugs.py`), and `cushings_score.html` handle their intros. Those are
the reference examples.
