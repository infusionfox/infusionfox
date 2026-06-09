"""
Tests for the IRIS CKD staging calculator.

Source: IRIS staging guidelines (modified 2023).

Creatinine stage cutoffs (mg/dL), inclusive ranges:
  Dog:    Stage 1 <1.4, Stage 2 1.4-2.8, Stage 3 2.9-5.0, Stage 4 >5.0
  Cat:    Stage 1 <1.6, Stage 2 1.6-2.8, Stage 3 2.9-5.0, Stage 4 >5.0

SDMA cutoffs (µg/dL), inclusive ranges:
  Dog:    Stage 1 <18, Stage 2 18-35, Stage 3 36-54, Stage 4 >54
  Cat:    Stage 1 <18, Stage 2 18-25, Stage 3 26-38, Stage 4 >38

Final stage = max(creatinine_stage, sdma_stage).
Substaging by UPC and SBP.
"""

from __future__ import annotations

import pytest

from app.routers.iris_staging import IrisInputs, calculate


class TestDogCreatinineStaging:
    @pytest.mark.parametrize(
        "creat,expected",
        [
            (1.0, 1),    # below 1.4
            (1.39, 1),
            (1.4, 2),    # boundary, start of stage 2
            (2.0, 2),
            (2.8, 2),    # boundary, IRIS-inclusive upper of stage 2
            (2.9, 3),    # boundary, start of stage 3
            (3.0, 3),
            (5.0, 3),    # boundary, IRIS-inclusive upper of stage 3
            (5.1, 4),    # >5.0 is stage 4
            (10.0, 4),
        ],
    )
    def test_dog_creatinine_stage(self, creat: float, expected: int):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=creat))
        assert result.stage_creatinine == expected


class TestCatCreatinineStaging:
    @pytest.mark.parametrize(
        "creat,expected",
        [
            (1.0, 1),
            (1.59, 1),
            (1.6, 2),    # cat boundary differs from dog
            (2.5, 2),
            (2.8, 2),    # IRIS-inclusive upper of stage 2
            (2.9, 3),    # start of stage 3
            (4.0, 3),
            (5.0, 3),    # IRIS-inclusive upper of stage 3
            (5.1, 4),    # >5.0 is stage 4
        ],
    )
    def test_cat_creatinine_stage(self, creat: float, expected: int):
        result = calculate(IrisInputs(species="cat", creatinine_mg_dl=creat))
        assert result.stage_creatinine == expected


class TestSDMAStaging:
    @pytest.mark.parametrize(
        "species,sdma,expected",
        [
            ("dog", 10.0, 1),
            ("dog", 17.9, 1),
            ("dog", 18.0, 2),    # start of stage 2
            ("dog", 30.0, 2),
            ("dog", 35.0, 2),    # IRIS-inclusive upper of stage 2
            ("dog", 36.0, 3),    # start of stage 3
            ("dog", 54.0, 3),    # IRIS-inclusive upper of stage 3
            ("dog", 55.0, 4),    # >54 is stage 4
            ("cat", 17.0, 1),
            ("cat", 18.0, 2),    # start of stage 2
            ("cat", 25.0, 2),    # IRIS-inclusive upper of stage 2
            ("cat", 26.0, 3),    # start of stage 3
            ("cat", 38.0, 3),    # IRIS-inclusive upper of stage 3 (was incorrectly 45)
            ("cat", 39.0, 4),    # >38 is stage 4 (was incorrectly ≥45)
            ("cat", 45.0, 4),    # well into stage 4
        ],
    )
    def test_sdma_stage(self, species: str, sdma: float, expected: int):
        result = calculate(IrisInputs(species=species, sdma_ug_dl=sdma))
        assert result.stage_sdma == expected


class TestFinalStageIsMax:
    """Final stage is the worse of creatinine vs SDMA."""

    def test_higher_creat_wins(self):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=3.0, sdma_ug_dl=20.0))
        # Cr → stage 3, SDMA → stage 2, final = 3
        assert result.stage_creatinine == 3
        assert result.stage_sdma == 2
        assert result.final_stage == 3

    def test_higher_sdma_wins(self):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=1.5, sdma_ug_dl=40.0))
        # Cr → stage 2, SDMA → stage 3, final = 3
        assert result.stage_creatinine == 2
        assert result.stage_sdma == 3
        assert result.final_stage == 3

    def test_no_sdma_uses_creat_only(self):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0, sdma_ug_dl=0))
        assert result.final_stage == result.stage_creatinine


class TestUPCSubstaging:
    def test_dog_high_upc_proteinuric(self):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0, upc=1.0))
        assert "proteinuric" in result.upc_label.lower() or result.upc_abbrev == "P"

    def test_dog_low_upc_nonproteinuric(self):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0, upc=0.1))
        assert "non" in result.upc_label.lower() or result.upc_abbrev == "NP"

    def test_dog_upc_0_5_is_borderline(self):
        """IRIS 2023: dog UPC 0.5 is Borderline (inclusive upper bound)."""
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0, upc=0.5))
        assert result.upc_abbrev == "BP"

    def test_dog_upc_above_0_5_is_proteinuric(self):
        """IRIS 2023: dog UPC >0.5 is Proteinuric."""
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0, upc=0.51))
        assert result.upc_abbrev == "P"

    def test_cat_upc_0_4_is_borderline(self):
        """IRIS 2023: cat UPC 0.4 is Borderline (inclusive upper bound)."""
        result = calculate(IrisInputs(species="cat", creatinine_mg_dl=2.0, upc=0.4))
        assert result.upc_abbrev == "BP"

    def test_cat_upc_above_0_4_is_proteinuric(self):
        """IRIS 2023: cat UPC >0.4 is Proteinuric."""
        result = calculate(IrisInputs(species="cat", creatinine_mg_dl=2.0, upc=0.41))
        assert result.upc_abbrev == "P"

    def test_no_upc(self):
        """upc=0 means not measured."""
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0, upc=0))
        # Should produce some "not measured" indicator
        assert result.upc_abbrev != "P" or "not" in result.upc_label.lower()


class TestBPSubstaging:
    def test_severe_hypertension_high_risk(self):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0, sbp_mmhg=180))
        # Severe per IRIS: ≥160 SBP
        assert "severe" in result.bp_label.lower() or result.bp_abbrev in ("H3", "H4")

    def test_normotensive(self):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0, sbp_mmhg=130))
        # Should reflect normotension
        assert "normo" in result.bp_label.lower() or result.bp_abbrev == "N"


class TestSpeciesValidation:
    def test_unknown_species_defaults_to_dog(self):
        result = calculate(IrisInputs(species="ferret", creatinine_mg_dl=1.5))
        # 1.5 is stage 2 for dog (≥1.4), but stage 1 for cat (<1.6)
        assert result.stage_creatinine == 2


class TestSourceAttribution:
    def test_includes_iris(self):
        result = calculate(IrisInputs(species="dog", creatinine_mg_dl=2.0))
        cite_text = " ".join(s.citation for s in result.sources)
        assert "IRIS" in cite_text or "Renal" in cite_text
