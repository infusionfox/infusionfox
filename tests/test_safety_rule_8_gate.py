"""Safety Rule #8 gate verification for scoring/staging calculators.

Safety Rule #8: Calculators NEVER show output before the clinician
enters values. This file pins the gate behavior for the four
calculators that previously violated it: /iris-staging,
/addisons-score, /cushings-score, /hypothyroid-score.

Each calculator now has a `computed: bool` flag on its result that is
True only when the inputs contain at least one clinically meaningful
finding (creatinine or SDMA for IRIS; any positive sign or recorded lab
for the three pretest scores). When `computed` is False, the result
partial renders a placeholder rather than a misleading default headline.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.routers.addisons_score import AddisonsInputs
from app.routers.addisons_score import calculate as addisons_calculate
from app.routers.cushings_score import CushingsInput
from app.routers.cushings_score import calculate as cushings_calculate
from app.routers.hypothyroid_score import HypothyroidInputs
from app.routers.hypothyroid_score import calculate as hypothyroid_calculate
from app.routers.iris_staging import IrisInputs
from app.routers.iris_staging import calculate as iris_calculate

client = TestClient(app)


# ---------------------------------------------------------------------------
# Engine-level gate tests. The computed flag tracks whether the
# clinician has entered enough data to produce a meaningful result.
# ---------------------------------------------------------------------------


class TestIrisGate:
    def test_defaults_not_computed(self):
        """No creatinine and no SDMA → result is not computed."""
        result = iris_calculate(IrisInputs())
        assert result.computed is False
        assert result.final_stage == 0

    def test_creatinine_only_computes(self):
        """Creatinine alone is sufficient to stage."""
        result = iris_calculate(IrisInputs(creatinine_mg_dl=2.0))
        assert result.computed is True
        assert result.final_stage == 2

    def test_sdma_only_computes(self):
        """SDMA alone is sufficient per IRIS 2023 (clinically valid
        when creatinine isn't available)."""
        result = iris_calculate(IrisInputs(sdma_ug_dl=20.0))
        assert result.computed is True
        assert result.stage_sdma == 2
        assert result.final_stage == 2

    def test_both_uses_worse(self):
        """When both are entered the worse markers wins."""
        result = iris_calculate(
            IrisInputs(creatinine_mg_dl=2.0, sdma_ug_dl=40.0)
        )
        assert result.computed is True
        assert result.stage_creatinine == 2
        assert result.stage_sdma == 3
        assert result.final_stage == 3


class TestAddisonsGate:
    def test_defaults_not_computed(self):
        """Signalment-only defaults → not computed."""
        result = addisons_calculate(AddisonsInputs())
        assert result.computed is False
        assert result.total_score == 0
        assert result.likelihood_pct == 0

    def test_signalment_change_alone_does_not_compute(self):
        """Changing breed without entering clinical findings is still
        not enough — breed is demographic, not a clinical finding."""
        result = addisons_calculate(AddisonsInputs(breed="standard_poodle"))
        assert result.computed is False

    def test_lab_value_triggers_compute(self):
        """A positive numeric lab field opens the gate."""
        result = addisons_calculate(AddisonsInputs(na_k_ratio=23.0))
        assert result.computed is True
        assert result.total_score > 0  # Na:K 23 contributes points

    def test_yes_finding_triggers_compute(self):
        result = addisons_calculate(AddisonsInputs(gi_waxing_waning="yes"))
        assert result.computed is True

    def test_recorded_assessment_triggers_compute(self):
        """Even a "no" answer on a not_recorded sentinel opens the
        gate — clinician explicitly assessed it."""
        result = addisons_calculate(AddisonsInputs(hypoglycemia="no"))
        assert result.computed is True


class TestCushingsGate:
    def test_defaults_not_computed(self):
        result = cushings_calculate(CushingsInput())
        assert result.computed is False
        assert result.total_score == 0

    def test_positive_sign_triggers_compute(self):
        result = cushings_calculate(CushingsInput(polydipsia="yes"))
        assert result.computed is True

    def test_recorded_lab_triggers_compute(self):
        result = cushings_calculate(CushingsInput(usg="not_dilute"))
        assert result.computed is True


class TestHypothyroidGate:
    def test_defaults_not_computed(self):
        result = hypothyroid_calculate(HypothyroidInputs())
        assert result.computed is False
        assert result.total_score == 0

    def test_positive_sign_triggers_compute(self):
        result = hypothyroid_calculate(HypothyroidInputs(dermatologic="yes"))
        assert result.computed is True

    def test_recorded_anemia_triggers_compute(self):
        result = hypothyroid_calculate(HypothyroidInputs(anemia="no"))
        assert result.computed is True


# ---------------------------------------------------------------------------
# Route-level tests. The form's initial render must show a placeholder
# rather than a misleading default headline.
# ---------------------------------------------------------------------------


class TestInitialPageRendersPlaceholder:
    """On initial GET, the result panel shows a placeholder telling the
    clinician what to enter — never a headline result from defaults."""

    def test_iris_initial(self):
        body = client.get("/iris-staging").text
        assert "Enter creatinine" in body
        # No headline result block on initial render.
        assert "result__primary" not in body

    def test_addisons_initial(self):
        body = client.get("/addisons-score").text
        assert "Enter clinical findings" in body
        assert "result__primary" not in body

    def test_cushings_initial(self):
        body = client.get("/cushings-score").text
        assert "Enter clinical signs" in body
        assert "result__primary" not in body

    def test_hypothyroid_initial(self):
        body = client.get("/hypothyroid-score").text
        assert "Enter clinical signs" in body
        assert "result__primary" not in body


class TestHtmxLoadEmptyPostStillShowsPlaceholder:
    """The form's HTMX `load` trigger fires an empty POST on page load.
    That POST must also render the placeholder — otherwise the Safety
    Rule #8 violation would re-appear via the HTMX path."""

    def test_iris_empty_post(self):
        r = client.post(
            "/iris-staging/compute",
            data={
                "species": "dog",
                "creatinine_mg_dl": "",
                "sdma_ug_dl": "",
                "upc": "",
                "sbp_mmhg": "",
            },
            headers={"HX-Request": "true"},
        )
        assert "Enter creatinine" in r.text
        assert "result__primary" not in r.text

    def test_addisons_empty_post(self):
        r = client.post(
            "/addisons-score/compute",
            data={"age": "4", "breed": "other"},
            headers={"HX-Request": "true"},
        )
        assert "Enter clinical findings" in r.text
        assert "result__primary" not in r.text


class TestPostWithClinicalDataRenders:
    """Submitting actual clinical data flips the gate and renders the
    headline result."""

    def test_iris_creatinine_renders_stage(self):
        r = client.post(
            "/iris-staging/compute",
            data={
                "species": "dog",
                "creatinine_mg_dl": "3.5",
                "sdma_ug_dl": "0",
                "upc": "0",
                "sbp_mmhg": "0",
            },
            headers={"HX-Request": "true"},
        )
        assert "Enter creatinine" not in r.text
        assert "result__primary" in r.text
        assert "IRIS Stage" in r.text

    def test_addisons_with_finding_renders(self):
        r = client.post(
            "/addisons-score/compute",
            data={
                "age": "4",
                "breed": "other",
                "na_k_ratio": "23",
                "hypoglycemia": "yes",
            },
            headers={"HX-Request": "true"},
        )
        assert "Enter clinical findings" not in r.text
        assert "result__primary" in r.text

    def test_cushings_with_finding_renders(self):
        r = client.post(
            "/cushings-score/compute",
            data={
                "sex": "female_neutered",
                "age": "10",
                "breed": "other",
                "polydipsia": "yes",
                "potbelly": "yes",
                "usg": "dilute",
                "alkp": "elevated",
            },
            headers={"HX-Request": "true"},
        )
        assert "Enter clinical signs" not in r.text
        # Cushings result template uses different headline classes;
        # the absence of the placeholder + presence of the points
        # breakdown is sufficient.
        assert "points" in r.text.lower()

    def test_hypothyroid_with_finding_renders(self):
        r = client.post(
            "/hypothyroid-score/compute",
            data={
                "age_band": "over_6",
                "breed": "golden_retriever",
                "dermatologic": "yes",
                "lethargy": "yes",
            },
            headers={"HX-Request": "true"},
        )
        assert "Enter clinical signs" not in r.text
        assert "result__primary" in r.text
