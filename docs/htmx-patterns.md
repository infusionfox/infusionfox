# HTMX patterns

Conventions for working with HTMX in infusionfox. There's no JS framework — HTMX 2.0.2 and a small amount of hand-written JS in `base.html` handle the interactivity. These patterns recur across every calculator.

## Multi-concentration prep-card with disclosure

The project standard for any calculator where a drug has more than one commonly-stocked concentration. Norepinephrine was the original; the pattern is now applied to every multi-preset engine drug (epi, dobutamine, dopamine-cri, fentanyl) and the bespoke hydromorphone CRI calculator. The anesthesia worksheet uses a compact in-row variant (a `<select>` next to each drug) since the picker is already dense.

**Use it when:**
- A drug has multiple pharmacologically equivalent concentrations (different dilutions, vial sizes, or premixed strengths).
- The clinician's choice is workflow-driven (which bag prep, which vial concentration their hospital stocks), not a clinical decision.
- The default is the most-commonly-prepared option.

**Don't use it when:**
- The drug only has one realistic preparation.
- The "alternative" is a different product with different pharmacokinetics (Simbadol 1.8 mg/mL vs regular buprenorphine 0.3 mg/mL are NOT interchangeable; never list them in the same selector).

**Engine drug implementation (full-page calculator).** The router computes `default_preset` and `alt_presets` from the drug's `concentration_presets` list, where the default is the preset matching `drug.default_concentration_ug_per_ml` and the alternatives are the other `pump_safe=True` presets. Undiluted-vial warning presets (`pump_safe=False`) are intentionally filtered out — they exist in the reference table further down the page as anchors, but the user should never pick one for pump-driven dosing.

```python
def _render_single_drug(drug, request):
    default_preset = None
    alt_presets = []
    for preset in drug.concentration_presets:
        if (default_preset is None
            and preset.concentration_ug_per_ml == drug.default_concentration_ug_per_ml):
            default_preset = preset
        elif preset.pump_safe:
            alt_presets.append(preset)
    # ... pass default_preset and alt_presets to the template
```

The template (`app/templates/calculator.html`) renders:

```html
<div class="prep-card" id="concentration-display">
    <div class="prep-card__concentration">
        <span class="prep-card__value">{{ default_preset.concentration_ug_per_ml|int }}</span>
        <span class="prep-card__unit">µg/mL</span>
    </div>
    <div class="prep-card__recipe">{{ default_preset.recipe }}</div>
</div>

<input type="hidden" id="concentration_ug_per_ml" name="concentration_ug_per_ml"
       value="{{ default_preset.concentration_ug_per_ml }}">

{% if alt_presets %}
<details class="alt-concentration-panel">
    <summary>Use a different concentration</summary>
    <!-- radio per option, including the default (so user can return to it) -->
</details>
{% endif %}
```

A small JS handler in `calculator.html` listens for change on the `alt_concentration` radio group, updates the hidden input and the prep-card display, then fires `change` on the hidden input so HTMX picks it up and re-runs the calculation.

**Label nuance.** The visible header says "Bag preparation" for drugs whose concentration is a prepared bag (norepi, epi-bag, dobutamine, dopamine-cri, fentanyl). For drugs drawn directly from a stock vial (hydromorphone), the header says "Concentration" instead. The prep-card itself shows just the numeric value + unit; the recipe text appears below only if it's relevant (vials don't have a mix recipe).

**Why no weight-band auto-pick.** Earlier versions of the non-norepi drugs had JS that auto-selected a `<select>` option based on the patient weight. The norepi-pattern rollout intentionally dropped this in favor of a fixed default plus user override via the disclosure. The auto-pick had clinical safety value (small patient → less concentrated prep) but introduced behavior that was opaque to users and bypassed by the disclosure pattern anyway. If you want auto-pick back, the design conversation is: should it modify the default on weight change, or just highlight the "recommended for this weight" alternative in the disclosure?

**Worksheet variant.** The anesthesia worksheet uses a compact `<select name="stock_<drug>">` next to each drug's dose input in the picker, not a full prep-card. The picker is already dense and a full prep-card per drug would dominate the screen. The select's options come from a per-drug `STOCK_OPTIONS` dict in `app/calculators/anesthesia_sheet.py`, and the chosen value rides through to `calculate()` via a `contextvars.ContextVar` so `_drug()` and emergency-drug call sites pick it up without a 20-call-site signature change. See `docs/anesthesia-worksheet.md` for the full plumbing.

**Defense in depth on the server.** Both surfaces validate the submitted concentration against the known list (engine drug: `drug.concentration_presets`; worksheet: `STOCK_OPTIONS[drug_key]`). A stale browser tab or adversarial post that submits an out-of-list value falls back to the default rather than computing volumes against an arbitrary concentration. Tests pin both fallbacks.

## Result panel swap

The most common pattern: a calculator form posts on input change and swaps a result panel.

**Page template** (`<name>.html`):
```html
<form
    hx-post="/<slug>/compute"
    hx-target="#result-panel"
    hx-swap="outerHTML"
    hx-trigger="input changed delay:250ms, change, load">
    <!-- inputs -->
</form>

<div id="result-panel">
    {% include "partials/<name>_result.html" %}
</div>
```

**Result partial** (`partials/<name>_result.html`):
```html
<div id="result-panel">
    {% if result and not result.valid %}
        {% include "partials/_invalid_result.html" %}
    {% else %}
        <!-- numeric body -->
    {% endif %}
</div>
```

The partial **must include its own `#result-panel` wrapper** because `hx-swap="outerHTML"` replaces the element identified by `hx-target`. If the partial doesn't have a matching `id`, subsequent swaps lose the target and stop working.

The `hx-trigger="input changed delay:250ms, change, load"` triple is the standard. `load` makes the form post on initial page load so the result panel starts populated; `change` covers radio/select changes; `input changed delay:250ms` debounces text-input typing.

## Validation short-circuit

Every calculator result dataclass has a `valid: bool = True` field. The compute function returns `valid=False` with zeroed numerics when required inputs are missing or non-positive.

The result partial gates its numeric body:

```jinja
{% if result and not result.valid %}
    {% include "partials/_invalid_result.html" %}
{% else %}
    <!-- numeric output here -->
{% endif %}
```

This is non-negotiable per the clinical safety policy in `CONTRIBUTING.md`. A clinician must never see a computed dose alongside a "weight required" warning.

## Worked-example template mechanism

Many calculators show a "worked example with current inputs" section — LaTeX formulas that update when the inputs change. Earlier the partial included an inline `<script>` block to render KaTeX after the swap, but inline scripts inside HTMX-swapped content don't reliably execute. So the rendering is handled by a global handler in `base.html`.

**How it works:**

The page template has empty target divs for each formula:
```html
<div id="worked-example" class="formula-display">
    <!-- placeholder, populated by the global handler -->
</div>
<div id="worked-example-volume" class="formula-display">
    <!-- second slot for a different formula -->
</div>
```

The result partial emits matching `<template>` elements containing the LaTeX:
```jinja
<template id="worked-example-source">$$\text{total units} = ... = ... \,\text{U}$$</template>
<template id="worked-example-source-volume">$$\text{volume} = \frac{...}{100} = ...\,\text{mL}$$</template>
```

The naming convention is: `worked-example-source<suffix>` template → `worked-example<suffix>` target.

A global handler in `base.html` runs `syncWorkedExample()` on initial load and `htmx:afterSettle`. It finds every `template[id^="worked-example-source"]`, looks up the matching target by suffix, copies the template's `innerHTML` into the target, and runs KaTeX on it.

**Important:**
- Templates must be **inside** the result panel (`#result-panel`) so they ride along with the swap. Templates outside the swap target get destroyed by the swap and never come back.
- Use `<template>` elements (not hidden divs). The browser parses them but doesn't render them, which is exactly what we want.
- Don't add per-partial inline scripts to render LaTeX. The global handler covers it.

## `hx-preserve` for stateful UI

Some elements have client-side state (open `<details>`, focused inputs, scroll position, checkbox state) that shouldn't be reset on swap. The anesthesia worksheet's drug picker is the main example.

Pattern:

```html
<section id="preop-picker" hx-preserve="true">
    <!-- interactive controls -->
</section>
```

HTMX leaves the existing DOM untouched across swaps when an element with `hx-preserve` is found in both the old and new response with matching `id`.

**Caveats:**
- Server-rendered content inside a preserved element will go stale. If you need it to update, do it client-side (see the count-badge updater in `anesthesia_hub.html`).
- The element must exist in both the old DOM and the new HTML response. First render still inserts it normally.
- Scripts inside the preserved element only run on first render. Don't put `<script>` blocks inside.

## `_inject_chosen_doses` clamping

The anesthesia worksheet picker has editable dose inputs (named `dose_<drug>`). On form submission, the server's `_inject_chosen_doses` in `app/routers/anesthesia_hub.py` reads each `dose_*` field, clamps to the published range for that drug, and overwrites the drug line's chosen dose.

Two gotchas:

1. **Empty form values are skipped.** The code has `if val:` which treats empty strings as falsy. Clearing a dose field falls back to the natural default (the `default_dose=` parameter or the post-construction value).

2. **Clamping happens silently.** If the form submits a value outside the range, it clamps to the nearest bound without warning. This is what bites the species-change bug: dog defaults submitted with a cat species clamp to cat range, producing wrong values that look intentional. The species-change handler clears `dose_*` fields to avoid this.

## Document-level event listeners

Several JS handlers in `anesthesia_hub.html` listen on `document`, not the specific element. This is deliberate — HTMX swaps the form region, so any listener attached directly to a form element would be lost on the next swap.

The pattern:
```js
document.addEventListener('change', function (e) {
    if (!e.target || e.target.name !== 'species') return;
    // ...
});
```

Filtering by `e.target.name` inside the handler is more verbose than attaching directly, but survives HTMX swaps without re-attachment.

## What to avoid

- **Inline `<script>` blocks inside result partials.** They run unreliably after HTMX swaps. Move logic into base.html's global handler.
- **Putting `<template>` worked-example blocks outside `#result-panel`.** They get orphaned by the swap.
- **Editing `hx-target` on a calculator form without considering the partial structure.** The partial must wrap its content in an element matching the target's selector.
- **Server-side rendering of UI state inside `hx-preserve` regions.** It goes stale immediately.

## Reference files

- `app/templates/base.html` — global KaTeX + worked-example handler
- `app/templates/anesthesia_hub.html` — species-toggle handler, count-badge updater, tab JS
- `app/templates/partials/_invalid_result.html` — shared invalid-result panel
- `app/templates/partials/_source_cite.html` — shared source citation footer
