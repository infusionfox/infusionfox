# Contributing to InfusionFox

Thanks for your interest in infusionfox.com. This is a clinical-reference application; correctness and source attribution matter more than feature velocity.

## Quick guide: which kind of contribution are you making?

**Found an incorrect dose, an outdated reference, or content you believe is unsafe?**
This is the most valuable kind of contribution. Open a [Dose correction issue](https://github.com/infusionfox/infusionfox/issues/new?template=dose_correction.md), or email [support@infusionfox.com](mailto:support@infusionfox.com) directly if it's time-sensitive (suspected unsafe dose currently visible to users). You do NOT need to write code or file a pull request. A well-cited issue is enough; the maintainer will make the fix.

**Have an idea for a new calculator?**
Open a [Feature request](https://github.com/infusionfox/infusionfox/issues/new?template=feature_request.md) with the clinical use case, math/scoring rules, and at least one primary source citation. We may or may not implement it depending on roadmap fit, but well-reasoned proposals are always read.

**Want to submit code?**
Read the rest of this document. It covers the dev workflow, testing requirements, and the citation rule. Pull requests are welcome.

**Want to improve a clinical-background article?**
Articles live in `content/drugs/<slug>.md` and render at `/learn/<slug>`. They can be improved or expanded via PR. Stay in the established voice (direct, no hedging), cite any new clinical claims, and avoid em-dashes in prose.

---

**See also:** [`docs/style-guide.md`](docs/style-guide.md) for the copy
style guide: catalog blurbs, page intros, warnings, button labels.
Every new calculator and hub should follow it.

## Ground rules for clinical content

1. **Every calculator has a primary citation.** New calculators must list their source(s) in `SOURCES.md` and surface the citation in the result panel via the calculator's `sources` tuple.
2. **Don't make up dose ranges.** If a published source covers a range, use it verbatim. Where adaptations are clinically reasonable (e.g., point-weighting a multi-variable score), document the adaptation in the calculator file's docstring AND in `SOURCES.md`.
3. **Never reproduce copyrighted text.** Citations point readers at the source; we don't copy more than a sentence or two from any reference work.
4. **Species-specific cautions get persistent warnings.** Drugs that have known concerns in cats (HCM, lidocaine IV, propofol prolonged) carry warnings that surface unconditionally for that species.
5. **Validation failure must short-circuit.** When required inputs are missing or non-positive (weight ≤ 0, concentration = 0, etc.), the calculator MUST refuse to compute. Specifically:
   - Return a result with `valid=False` and zeroed numeric outputs. Never compute past the validation check, and never substitute a placeholder value (no `weight_kg = 0.001` "to avoid divide by zero". That produces a plausible-looking but wildly wrong dose).
   - The template MUST gate its numeric body: `{% if not result.valid %}{% include "partials/_invalid_result.html" %}{% else %}…{% endif %}`.
   - See `engine.CalcResult.valid` for the canonical pattern and `tests/calculators/test_input_validation.py` for the tests every new calculator must add.
   
   Rationale: a clinician should never see a computed dose alongside an "input must be > 0" warning, and should never see a 500 error from a `ZeroDivisionError`.

## Development workflow

```bash
# clone
cd infusionfox
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# pre-commit hooks (auto-lint + jinja parse check)
pre-commit install

# tests
pytest
```

## Tests are required for every change

InfusionFox has a comprehensive test suite (>800 tests, runs in ~10 seconds). Several production bugs that would have affected clinical users were caught by these tests before they shipped. New code must come with tests.

- **Calculator changes**: add or update tests in `tests/calculators/test_<name>.py`. Cover: each tier or band of a sliding scale, math against a known case, source attribution, input validation (zero/negative weight should never crash).
- **Database model changes**: add tests in `tests/db/`. Run `alembic revision --autogenerate -m "<description>"` and review the generated migration before committing.
- **Routes**: the integration smoke (`tests/test_integration_smoke.py`) automatically exercises every public GET route. If your change adds a new route, you'll get coverage for free.

## Database changes

InfusionFox uses Alembic for migrations. **Never edit the schema in `app/db/models.py` without generating a migration.**

```bash
# After editing models, generate a migration
INFUSIONFOX_DB_URL=sqlite:///./data/infusionfox.db alembic revision --autogenerate -m "what changed"

# Review the generated file in alembic/versions/, edit if needed
# Then apply it locally
alembic upgrade head
```

CI runs `alembic check` after applying head; if your model change doesn't have a migration, CI will fail.

## Pre-commit checks

Pre-commit runs on every commit:

- `ruff check` for lint
- `ruff format --check` for formatting
- `python scripts/check_templates.py` to verify every Jinja template parses

Run them anytime with `pre-commit run --all-files`.

## Adding a new calculator

1. Create `app/calculators/<name>.py` with: enums for species/options, an inputs dataclass, a result dataclass (with `valid: bool = True`), a `compute_<name>(inputs)` function. Look at `hypokalemia.py` for a reference shape.
2. **Validate inputs first and short-circuit on failure.** Inside `compute_<name>`, check every required input. If any is missing or non-positive, return a result with `valid=False`, zeroed numeric outputs, and the validation error in `warnings`. Do not compute anything past the validation check. See ground rule #5 above.
3. Create `app/routers/<name>.py` with `router = APIRouter()` and route handlers for `GET /<slug>` and `POST /<slug>/compute`. The auto-discovery in `app/routers/__init__.py` will pick it up.
4. Create the templates: `app/templates/<name>.html` (page) and `app/templates/<name>_result.html` (HTMX result panel). Use `.calc-header` + `.calc-grid` for layout. **Wrap the numeric body in `{% if not result.valid %}{% include "partials/_invalid_result.html" %}{% else %}…{% endif %}`** so invalid inputs render the shared error panel instead of fake numbers.
5. Add tests in `tests/calculators/test_<name>.py`. Required coverage: each tier or band of a sliding scale, math against a known case, source attribution, **and a test in `tests/calculators/test_input_validation.py` that asserts `valid is False` plus zeroed numeric outputs for invalid weight/dose/concentration**.
6. Add a row to `SOURCES.md` describing the citation and any clinical adaptations.

## Code style

- Type hints on all public functions.
- Dataclasses for structured inputs/outputs (immutable for config, mutable for results with `field(default_factory=...)` for warnings/notes/sources).
- Naive UTC datetimes everywhere (see `app/db/models.py::utcnow`).
- Logging via `app.logging_config.get_logger`, not `print()`.

## Reporting clinical issues

If you find a dose range, formula, or interpretation that's wrong: open an issue tagged `dose-concern`. These get triaged before any other category.
