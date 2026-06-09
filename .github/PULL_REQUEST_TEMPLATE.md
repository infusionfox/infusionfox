<!--
Thanks for contributing to InfusionFox. Please fill out the relevant sections below.
Delete sections that don't apply.
-->

## What this PR does

A clear, concise description of the change.

## Type of change

- [ ] Dose correction (changes a published dose range, warning, or indication)
- [ ] New calculator (adds a new CRI, score, or clinical reference)
- [ ] Bug fix (technical issue with calculator output, layout, or behavior)
- [ ] Documentation (README, CONTRIBUTING, SOURCES, comments, etc.)
- [ ] Refactor (no functional change)
- [ ] Tests (adding or improving tests, no functional change)
- [ ] Other (describe below)

## For clinical content changes

If this PR changes any dose range, indication, warning, or clinical interpretation, please confirm:

- [ ] At least one primary source is cited for every changed value
- [ ] The citation is added to `SOURCES.md` (or already present)
- [ ] If the change supersedes a previously-cited source, the rationale for the change is in the commit message or this PR description
- [ ] If safety-critical (could affect patient outcome), the `DISCLAIMER_VERSION` in `app/disclaimer.py` should be bumped. See the existing bump rationale comments for the format

## Code quality

- [ ] `python -m pytest -q` passes
- [ ] `ruff check app/` reports no errors
- [ ] No em-dashes (—) in prose (project style; use period, comma, colon, or restructure)
- [ ] No Google services introduced (fonts, analytics, captchas, embeds, etc.)
- [ ] Safety Rule #8 honored: calculators do not display computed output before the clinician enters values

## Testing

How did you test this? If it's a calculator change, did you verify the math against the cited source by hand or via the test suite?

## Screenshots

For UI changes, before/after screenshots are very helpful. Mobile-specific changes should include mobile screenshots.

## Related issues

Closes #
Related to #
