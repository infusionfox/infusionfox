# Anesthesia worksheet

This page is the most complex in the app. It does enough things that it merits its own doc. If you're about to change it, read this first.

## What it does

The anesthesia worksheet (`/anesthesia`) is a patient-specific anesthesia plan that the clinician can review on-screen and print as a paper sheet for the procedure. The clinician enters weight, species, and a few patient identifiers; the worksheet computes premed doses (opioid, sedative), induction doses, maintenance fluid rates, intraoperative fluid bolus, emergency drug doses, bridge bolus pressors (phenylephrine, ephedrine), and CRI vasopressor titration ladders (dopamine, dobutamine, norepi).

The clinician can also customize the printed sheet via the picker section: deselect drugs they won't use, and fine-tune any default dose within the published range.

## Page structure

The page has three main vertical regions, top to bottom:

1. **Patient bar** — weight/species/sex/identifier inputs. Not swapped on HTMX updates.
2. **Tab bar** — Preoperative vs Intraoperative tabs. Inside the swap wrapper.
3. **Tab pane content** — the actual sheet. Inside the swap wrapper.

The swap wrapper is `#anesthesia-sheet-wrapper`. The form's `hx-target` is this wrapper; `hx-swap="outerHTML"`. So any input change triggers a re-render of the tab bar + both tab panes.

Inside the preoperative pane sits the **drug-selection picker** — three collapsible `<details>` elements (opioids, sedatives, induction). Each has a checkbox per drug and an editable dose input. This is where the user customizes the printed sheet.

## Setting default doses

Every drug line in the picker is built by the `_drug()` helper in `anesthesia_sheet.py`. The helper accepts `low`, `high`, and `default_dose` in the **display unit** for that drug — mg/kg for almost everything, µg/kg for dexmedetomidine — and converts to the storage unit (always mg/kg) internally using the `dose_display_multiplier`. So every call site reads in the unit a clinician sees on screen.

For most drugs the display unit IS mg/kg, so nothing special happens. For dex, the helper detects `stock_key == "dexmedetomidine"`, sets `dose_display_multiplier=1000.0`, and divides the incoming values by 1000 to get storage values.

**If you're changing a dex default**, just edit the `default_dose=` argument on the dex `_drug()` call inside the appropriate species block. Same as every other drug.

Current dex defaults: dog 5 µg/kg, cat 10 µg/kg. Both written as `default_dose=5.0` and `default_dose=10.0` respectively at the call site.

(Historical note: earlier versions had a post-construction `DrugLine(...)` rebuild for dex that overwrote whatever `_drug()` produced. That rebuild is gone; the unit conversion now lives inside `_drug()`. If you encounter the old rebuild block in a stale branch, the calculator still works but editing `default_dose=` on the dex `_drug()` call is a silent no-op until the rebuild is removed.)

## Default doses currently set

**Dog:**
- Hydromorphone 0.1 mg/kg, Methadone 0.2 mg/kg, Butorphanol 0.2 mg/kg, Buprenorphine 0.01 mg/kg
- Dexmedetomidine 5 µg/kg, Midazolam 0.2 mg/kg, Acepromazine 0.02 mg/kg
- Propofol 6 mg/kg, Alfaxalone 4.5 mg/kg

**Cat:**
- Hydromorphone 0.05 mg/kg, Methadone 0.2 mg/kg, Butorphanol 0.3 mg/kg, Buprenorphine 0.02 mg/kg
- Dexmedetomidine 10 µg/kg, Midazolam 0.2 mg/kg, Acepromazine 0.02 mg/kg
- Propofol 6 mg/kg, Alfaxalone 5 mg/kg

All match "start low when combining with an opioid" guidance from Plumb's / Lumb & Jones for premed, with cat dex (10 µg/kg) following the standard "10–20 µg/kg is usually sufficient" recommendation.

## Species toggle behavior

When the user switches species (dog ↔ cat), the dose ranges and which drugs are even appropriate change. The implementation has to make sure no dog-side state leaks into the cat picker (or vice versa) — that's the failure mode that produces silently-wrong defaults.

**The current design: a species change is a full page reload.**

The species radios are wired with `hx-get="/anesthesia?species=dog|cat"`, `hx-target="body"`, `hx-swap="outerHTML"`, and `hx-include="this"`. Toggling species triggers a GET against `/anesthesia` with only the new species value in the query string. The server returns a fresh worksheet at that species with weight, patient name, patient age, picker selections, and result panel all blank. The browser replaces the entire page body.

The safety guarantee: there is no previous-species DOM at the moment the new species renders. The picker's `hx-preserve="true"` (see below) operates only within a single species' lifetime — within-species swaps preserve user interactions exactly as designed, but the species change itself bypasses the swap mechanism entirely by reloading the page.

This design replaced an earlier in-place toggle that needed a JS handler to clear `dose_*` inputs and strip `hx-preserve` from the picker. That handler existed to prevent two specific failure modes:

**Failure mode 1: stale dose values bleeding across species.** With an in-place toggle, the form's existing `dose_buprenorphine=0.01` (dog default) would post along with the new species value. The server's `_inject_chosen_doses` would clamp 0.01 to the cat range (0.01–0.02), accept it, and store 0.01 — the cat's *low end* rather than the cat's natural default of 0.02. A silent twofold underdose suggestion.

**Failure mode 2: picker DOM preservation conflicts with species change.** With `hx-preserve` active, the picker DOM survives the swap. Without a strip, the cat species change would show dog drugs in the new "cat" picker.

The blank-slate reload makes both failure modes structurally impossible — there's no form state to bleed because the form is blank, and there's no preserved DOM to strip because the entire page is replaced. The integration tests in `tests/test_anesthesia_integration.py::TestSpeciesReloadBlankSlate` pin the structural wiring so a future refactor can't accidentally reintroduce the in-place pattern.

If you're working from a branch that predates the full-reload design, the in-place toggle + JS handler still works correctly — just be aware that breaking the handler (renaming the `species` field, deleting the `change` listener, removing the picker's `id="preop-picker"` that the strip logic looks for) would reintroduce the silent-wrong-defaults bug. The full-reload design is preferred because it removes the bug class rather than guarding against it.

## The picker preservation pattern

The drug-selection picker uses `<details>` elements that can be open or closed independently. When the user is interacting with the picker — toggling checkboxes, editing doses — every change triggers an HTMX form submission, which would normally re-render the picker DOM and reset the open/closed state, the focused input, and the cursor position.

**Solution:** the picker section has `hx-preserve="true"`. HTMX leaves the existing DOM untouched across swaps. The browser's native input state (which checkboxes are checked, what's in the dose field, which `<details>` are open) survives because the elements are never replaced.

**Consequence:** anything inside the picker that would normally refresh from the server now goes stale. The only such thing is the count badge ("3 of 3") in each `<details>` summary. That gets updated client-side instead — a JS listener counts checked boxes per category and updates the badge text on every change. Also lives in the `<script>` at the bottom of `anesthesia_hub.html`.

If you add server-rendered content inside the picker, it will not update automatically. Either move it out, or add a client-side update.

## CRI auto-dilution

For each CRI vasopressor (dopamine, dobutamine, norepi), the calculator picks a dilution that produces sensible pump rates (typically 1–25 mL/hr) for the patient. Logic lives in `_pick_cri_dilution()` in `anesthesia_sheet.py`. Bigger patients get more concentrated bags; smaller patients get more dilute. Below 1.5 kg, the auto-dilution returns an empty ladder and a "use a syringe pump" message — practical CRI bag dosing doesn't work at that weight.

If you change dose ranges, sanity-check what dilutions the helper picks across the weight range. Sub-1.5kg should always trigger the fallback message.

## The dobutamine cat caution flag

Cat dobutamine doses above 5 µg/kg/min are flagged with a visual caution on the titration ladder. Cats are sensitive to dobutamine (seizures, arrhythmias above this range). The published upper end of 20 µg/kg/min stays available because rare clinical scenarios warrant it, but the UI marks the cat-unsafe zone.

Implementation: each ladder step has an `is_caution: bool` field set per-step in `anesthesia_sheet.py`. Don't remove these flags without consulting clinical sources.

## Bridge bolus pressors

Phenylephrine (1–10 µg/kg IV) and ephedrine (0.05–0.1 mg/kg IV) appear in their own intraoperative section above the CRI section. They use a `BolusLine` dataclass (not `DrugLine`) because they're single-dose IV, not CRI. The dilution is fixed (not auto-picked) since these are typically pre-diluted from stock at point of care.

The note text explicitly tells the clinician to "bridge to a CRI if MAP requires repeat bolus dosing" — they're a stopgap while setting up the infusion, not a primary treatment.

## Per-drug concentration selectors

For drugs with multiple commonly-stocked concentrations, the picker offers a compact `<select>` next to each drug's dose input so the user can pick the concentration their hospital stocks. The selected concentration drives both the printed stock label and the volume math.

**What's exposed.** The full list lives in `STOCK_OPTIONS` (`app/calculators/anesthesia_sheet.py`). Currently five drugs: hydromorphone (1/2/4/10 mg/mL), midazolam (5/1 mg/mL), dexmedetomidine (0.5/0.1 mg/mL), atropine (0.54/0.4 mg/mL), naloxone (0.4/1 mg/mL). Each tuple lists the available concentrations and labels; the first entry is the default and matches `STOCKS[drug_key]`.

A drug is included in `STOCK_OPTIONS` only when (a) multiple concentrations exist in routine small-animal practice, (b) the choice meaningfully affects what the worksheet renders, and (c) the drug surfaces somewhere in the rendered worksheet. Ketamine and lidocaine are intentionally absent: ketamine's only appearance is in the DKB section whose volumes come from a hardcoded Plumb's table that doesn't read `STOCKS`, and lidocaine isn't on the worksheet at all (only on its standalone CRI calculator). Adding them would render selectors that have no effect, which is worse than no selector.

**Picker placement.** Three of the five drugs (hydromorphone, midazolam, dexmedetomidine) appear in the existing opioid/sedative picker sections; the selector renders inline below the dose input in each row via a shared Jinja macro at the top of `anesthesia_sheet_preop.html`. Atropine and naloxone don't have a checkbox-driven picker (they're always on the printed emergency-drug list), so they get their own picker section labeled "Emergency drug concentrations" with just the drug name + selector, no checkbox or dose input. The section only renders when both drugs are present in `result.emergency_drugs`.

**Round-trip plumbing.** The selector posts `stock_<drug>=<value>` with the form. The router parses, validates against `STOCK_OPTIONS` (any value outside the known list falls back to the default silently), and passes a `chosen_stocks: dict[str, float]` to `calculate()`. `calculate()` binds it to a `contextvars.ContextVar` named `_chosen_stocks_var` and resets on exit so concurrent requests don't leak state. `_drug()` and the emergency-drug call sites read effective concentrations through `_stock_for(key)` instead of `STOCKS[key]` directly; the printed label is resolved through `_stock_label_for(key)` so it matches the user's pick.

The ContextVar pattern is the trade-off: it avoids threading `chosen_stocks` through 20+ `_drug()` call sites in `calculate()`, at the cost of a request-scoped global. ContextVars are coroutine-safe under FastAPI's async request model, so there's no actual concurrency hazard. Tests in `tests/test_anesthesia_concentration_selectors.py::TestContextVarReset` pin the reset behavior.

**Adding a drug to `STOCK_OPTIONS`.** Three things to check:
1. The drug must actually surface in the worksheet output (premed picker row, emergency-drug list, etc.). If it doesn't, the selector won't do anything.
2. The render path must read its stock value through `_stock_for(key)` (premed/induction drugs go through `_drug()` which already does; emergency drugs via `_emerg(...)` need their call site updated to use `_stock_for(...)` + `_stock_label_for(...)` like the atropine/naloxone calls do).
3. The picker template needs a row to attach the selector to. If the drug is already in an opioid/sedative/induction picker, the macro covers it automatically. If not, add it to the "Emergency drug concentrations" section (or a new section if the drug doesn't fit there).

After adding, update `tests/test_anesthesia_concentration_selectors.py::TestStockOptionsData::test_currently_exposed_drugs` to include the new drug — that test fails by design when the set drifts so additions are deliberate.

## Tab implementation

Tabs are CSS-driven: a tab pane has `.is-active` class when active; the tab bar buttons have `.is-active` matching the active tab. There's a small JS function `infusionfox_anesthesia_activateTab(target)` that toggles the classes. The active tab is also tracked in a hidden form input (`#active_tab`) so server-side responses can preserve which tab is showing.

Print CSS hides the inactive tab pane via `display: none !important`. Only the active tab prints.

## Things people will want to change

- **Drug defaults** — `_drug()` `default_dose=` for every drug, including dex. For dex the value is in µg/kg (the display unit); for everything else it's in mg/kg. The defaults table above is the source of truth.
- **Dose ranges** — `_drug()`'s `low` and `high` positional args. The `dose_label` string near it should match.
- **Picker layout** — `.preop-picker` CSS in `anesthesia_hub.html`. The 3-column grid kicks in at ≥900px; below that, stacks.
- **Adding a new drug to the picker** — add an `_drug()` call inside the appropriate species block in `anesthesia_sheet.py`. The picker template iterates `result.premed_opioids` / `_sedatives` / `induction_drugs`, so anything you add is automatically picked up.

## Things to be careful of

- **Don't add inline `<script>` blocks inside the picker.** `hx-preserve` keeps the DOM intact, including any scripts — they won't re-run on swap.
- **Don't add server-rendered counts or computed text inside the picker** without a matching client-side update — `hx-preserve` will make it go stale.
- **Don't change `hx-target` on the form** without thinking about what's still inside the swap wrapper. The picker depends on being inside the wrapper (so it's preserved on `hx-preserve` after the first render).
- **Don't change the species radios' HTMX wiring back to in-place behavior.** The radios use `hx-get="/anesthesia?species=..."` + `hx-target="body"` + `hx-include="this"` to force a full page reload on species change. Reverting to the form's default `hx-post → /anesthesia/compute` would reintroduce the species-toggle bug class (stale dog doses bleeding into the cat picker via `hx-preserve`). Tests in `tests/test_anesthesia_integration.py::TestSpeciesReloadBlankSlate` pin the wiring; they'll fail loudly if it changes.
- **Dex defaults are in µg/kg** at the `_drug()` call site, not mg/kg. The helper detects dex via `stock_key == "dexmedetomidine"` and converts internally. Writing `default_dose=0.005` for dex would set the default to 0.005 µg/kg (way below clinical), not 5 µg/kg.
