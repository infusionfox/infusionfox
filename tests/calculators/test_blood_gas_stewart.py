"""Tests for the Stewart strong-ion blood gas calculator.

Covers:
  - Healthy patient produces ~zero on every component
  - Hypoalbuminemia produces positive BE_albumin (alkalinizing)
  - Hyperlactatemia produces negative BE_lactate
  - Septic dog: alb-corrected AG > conventional AG
  - DKA dog: large unmeasured anion residual
  - SIG / AG / corrected AG computation
  - Route smoke tests (GET, POST)
  - Sum of components ≈ total BE
  - Cross-link rendering between Stewart and Henderson views
  - Bonus: existing /blood-gas surfaces albumin-corrected AG when albumin
    is supplied
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.calculators.blood_gas import Species
from app.calculators.blood_gas_stewart import (
    BLOOD_GAS_STEWART_CATALOG_ENTRY,
    CAT_REFERENCE,
    DOG_REFERENCE,
    StewartInputs,
    compute,
    reference_for,
)
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Healthy baseline
# ---------------------------------------------------------------------------


class TestHealthyBaseline:
    def test_healthy_dog_components_near_zero(self):
        """At species-normal inputs, every measured component should be ~0."""
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=0.0,
                pH=7.4,
                pco2_mm_hg=40,
                hco3_meq_per_l=22,
                na_meq_per_l=145,
                k_meq_per_l=4.0,
                cl_meq_per_l=110,
                lactate_mmol_per_l=1.5,
                albumin_g_per_dl=3.5,
                phosphate_mg_per_dl=4.5,
            )
        )
        for c in r.components:
            if c.label == "Unmeasured anions":
                # Falls out as the residual after measured components
                continue
            assert abs(c.mEq_per_l) < 0.5, (
                f"{c.label} = {c.mEq_per_l} should be near 0 in healthy patient"
            )

    def test_healthy_dog_sig_near_zero(self):
        r = compute(
            StewartInputs(
                species=Species.DOG,
                pH=7.4,
                pco2_mm_hg=40,
                hco3_meq_per_l=22,
                na_meq_per_l=145,
                k_meq_per_l=4.0,
                cl_meq_per_l=110,
                lactate_mmol_per_l=1.5,
                albumin_g_per_dl=3.5,
                phosphate_mg_per_dl=4.5,
            )
        )
        # SIG should be small (< 5 mEq/L magnitude) in health
        assert r.sig is not None
        assert abs(r.sig) < 5.0


# ---------------------------------------------------------------------------
# Hypoalbuminemia — the headline correction
# ---------------------------------------------------------------------------


class TestHypoalbuminemia:
    def test_low_albumin_produces_alkalinizing_be(self):
        """Hypoalbuminemia removes a weak acid → positive (alkalinizing) BE_alb."""
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=0.0,
                pH=7.4,
                hco3_meq_per_l=22,
                na_meq_per_l=145,
                cl_meq_per_l=110,
                albumin_g_per_dl=1.8,
            )
        )
        alb = next(c for c in r.components if c.label == "Albumin")
        assert alb.mEq_per_l > 0
        # 3.4 × (3.5 - 1.8) = 5.78
        assert 5.0 < alb.mEq_per_l < 6.5

    def test_high_albumin_produces_acidifying_be(self):
        r = compute(
            StewartInputs(
                species=Species.DOG,
                hco3_meq_per_l=22,
                albumin_g_per_dl=5.0,
            )
        )
        alb = next(c for c in r.components if c.label == "Albumin")
        assert alb.mEq_per_l < 0

    def test_corrected_ag_exceeds_conventional_in_hypoalbuminemia(self):
        """Patient with conventional AG = 14 + albumin 1.5 should have corrected AG ~20."""
        r = compute(
            StewartInputs(
                species=Species.DOG,
                pH=7.3,
                hco3_meq_per_l=14,
                na_meq_per_l=140,
                cl_meq_per_l=112,
                albumin_g_per_dl=1.5,
            )
        )
        assert r.ag is not None
        assert r.ag_corrected is not None
        # AG = 140 - (112 + 14) = 14
        assert r.ag == pytest.approx(14, abs=0.5)
        # AG_corrected = 14 + 2.5 × (3.5 - 1.5) = 19
        assert r.ag_corrected == pytest.approx(19, abs=0.5)
        assert r.ag_corrected > r.ag


# ---------------------------------------------------------------------------
# Hyperlactatemia
# ---------------------------------------------------------------------------


class TestHyperlactatemia:
    def test_high_lactate_produces_acidifying_be(self):
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=-5.0,
                lactate_mmol_per_l=6.0,
            )
        )
        lac = next(c for c in r.components if c.label == "Lactate")
        assert lac.mEq_per_l < 0
        # -1.0 × (6.0 - 1.5) = -4.5
        assert lac.mEq_per_l == pytest.approx(-4.5, abs=0.2)

    def test_lactate_residual_separation(self):
        """When lactate alone explains the acidosis, BE_unmeasured should be small."""
        # Pure lactic acidosis: BE -5, lactate 6.5 (contributes -5)
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=-5.0,
                hco3_meq_per_l=18,
                na_meq_per_l=145,
                cl_meq_per_l=110,
                lactate_mmol_per_l=6.5,
                albumin_g_per_dl=3.5,
                phosphate_mg_per_dl=4.5,
            )
        )
        unmeasured = next(c for c in r.components if c.label == "Unmeasured anions")
        # Lactate accounts for most of the deficit; residual should be small
        assert abs(unmeasured.mEq_per_l) < 1.5


# ---------------------------------------------------------------------------
# Mass balance — sum of components = total BE
# ---------------------------------------------------------------------------


class TestMassBalance:
    @pytest.mark.parametrize(
        "be,na,cl,alb,lac",
        [
            (-10.0, 142, 108, 1.8, 5.0),
            (-18.0, 148, 110, 2.8, 3.0),
            (5.0, 150, 105, 4.0, 1.0),
            (0.0, 145, 110, 3.5, 1.5),
            (-25.0, 138, 100, 1.5, 8.0),
        ],
    )
    def test_components_sum_to_total_be(self, be, na, cl, alb, lac):
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=be,
                hco3_meq_per_l=22,
                na_meq_per_l=na,
                cl_meq_per_l=cl,
                lactate_mmol_per_l=lac,
                albumin_g_per_dl=alb,
                phosphate_mg_per_dl=4.5,
            )
        )
        total = sum(c.mEq_per_l for c in r.components)
        # Within 0.2 of the total BE (rounding tolerance)
        assert abs(total - r.be_total) < 0.3


# ---------------------------------------------------------------------------
# Clinical scenarios
# ---------------------------------------------------------------------------


class TestSepticDog:
    """Classic septic dog: hypoalbuminemia + hyperlactatemia + acidemia."""

    def setup_method(self):
        self.r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=-10.0,
                pH=7.25,
                pco2_mm_hg=32,
                hco3_meq_per_l=14,
                na_meq_per_l=142,
                k_meq_per_l=3.8,
                cl_meq_per_l=108,
                lactate_mmol_per_l=5.0,
                albumin_g_per_dl=1.8,
                phosphate_mg_per_dl=4.5,
            )
        )

    def test_dominant_contributor_is_unmeasured(self):
        """Conventional AG should look modest, but unmeasured-anion burden is large."""
        unmeasured = next(c for c in self.r.components if c.label == "Unmeasured anions")
        assert unmeasured.mEq_per_l < -8

    def test_albumin_contribution_meaningful(self):
        alb = next(c for c in self.r.components if c.label == "Albumin")
        assert alb.mEq_per_l > 4  # ~5.8

    def test_corrected_ag_higher_than_conventional(self):
        assert self.r.ag is not None
        assert self.r.ag_corrected is not None
        assert self.r.ag_corrected > self.r.ag + 2


class TestDKADog:
    """DKA: huge unmeasured-anion residual from ketones."""

    def test_unmeasured_residual_dominates(self):
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=-18.0,
                pH=7.15,
                hco3_meq_per_l=8,
                na_meq_per_l=148,
                k_meq_per_l=4.5,
                cl_meq_per_l=110,
                lactate_mmol_per_l=3.0,
                albumin_g_per_dl=2.8,
                phosphate_mg_per_dl=2.0,
            )
        )
        unmeasured = next(c for c in r.components if c.label == "Unmeasured anions")
        # Should be large and negative — ketones not measured directly
        assert unmeasured.mEq_per_l < -15


# ---------------------------------------------------------------------------
# Species
# ---------------------------------------------------------------------------


class TestSpecies:
    def test_dog_and_cat_references_differ(self):
        assert DOG_REFERENCE.na_meq_per_l != CAT_REFERENCE.na_meq_per_l
        assert DOG_REFERENCE.cl_meq_per_l != CAT_REFERENCE.cl_meq_per_l
        assert DOG_REFERENCE.albumin_g_per_dl != CAT_REFERENCE.albumin_g_per_dl

    def test_reference_for_dog(self):
        assert reference_for(Species.DOG) is DOG_REFERENCE

    def test_reference_for_cat(self):
        assert reference_for(Species.CAT) is CAT_REFERENCE

    def test_cat_normal_inputs_produce_zero_components(self):
        """Same idea as healthy dog, with cat reference values."""
        r = compute(
            StewartInputs(
                species=Species.CAT,
                base_excess=0.0,
                hco3_meq_per_l=22,
                na_meq_per_l=152,
                cl_meq_per_l=121,
                lactate_mmol_per_l=1.5,
                albumin_g_per_dl=3.0,
                phosphate_mg_per_dl=4.5,
            )
        )
        for c in r.components:
            if c.label == "Unmeasured anions":
                continue
            assert abs(c.mEq_per_l) < 0.5


# ---------------------------------------------------------------------------
# SIG
# ---------------------------------------------------------------------------


class TestSIG:
    def test_sig_requires_na_cl_hco3(self):
        r = compute(StewartInputs(species=Species.DOG))
        # Default: no electrolytes → SIG should be None
        assert r.sida is None
        assert r.side is None
        assert r.sig is None

    def test_sig_present_with_full_inputs(self):
        r = compute(
            StewartInputs(
                species=Species.DOG,
                pH=7.4,
                hco3_meq_per_l=22,
                na_meq_per_l=145,
                cl_meq_per_l=110,
                lactate_mmol_per_l=1.5,
                albumin_g_per_dl=3.5,
            )
        )
        assert r.sida is not None
        assert r.side is not None
        assert r.sig is not None


# ---------------------------------------------------------------------------
# Optional inputs / missing data
# ---------------------------------------------------------------------------


class TestOptionalInputs:
    def test_unmeasured_phosphate_defaults_to_normal(self):
        """Phosphate not entered → assume species normal → BE_phos = 0."""
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=-5.0,
                hco3_meq_per_l=18,
                albumin_g_per_dl=2.5,
                phosphate_mg_per_dl=0.0,  # not entered
            )
        )
        phos = next(c for c in r.components if c.label == "Phosphate")
        assert phos.mEq_per_l == 0.0

    def test_unmeasured_albumin_zeroes_component(self):
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=-5.0,
                albumin_g_per_dl=0.0,
            )
        )
        alb = next(c for c in r.components if c.label == "Albumin")
        assert alb.mEq_per_l == 0.0

    def test_missing_electrolytes_disables_sig_and_ag(self):
        r = compute(
            StewartInputs(
                species=Species.DOG,
                base_excess=-5.0,
                albumin_g_per_dl=2.0,
                # Na, Cl, HCO3 not provided
                hco3_meq_per_l=0.0,
            )
        )
        assert r.sig is None
        assert r.ag is None
        assert r.ag_corrected is None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


class TestRoutes:
    def test_get_page_renders_with_placeholder_not_decomposition(self):
        """Safety: initial GET must show placeholder, not a default
        decomposition. See CLAUDE.md non-negotiable #8.
        """
        r = client.get("/blood-gas-stewart")
        assert r.status_code == 200
        assert "Stewart" in r.text
        # Form fields exist
        for field_name in (
            "base_excess",
            "na_meq_per_l",
            "cl_meq_per_l",
            "albumin_g_per_dl",
            "phosphate_mg_per_dl",
            "lactate_mmol_per_l",
        ):
            assert field_name in r.text
        # Placeholder is in the result panel slot
        assert "Awaiting input" in r.text
        # Decomposition labels MUST NOT appear (they'd indicate the
        # result panel is pre-rendered)
        assert "Unmeasured anions" not in r.text

    def test_get_page_does_not_load_compute_immediately(self):
        """Safety: hx-trigger must not include `load`."""
        r = client.get("/blood-gas-stewart")
        for line in r.text.splitlines():
            if "hx-trigger" in line and "load" in line:
                raise AssertionError(f"hx-trigger contains `load`: {line.strip()}")

    def test_get_page_inputs_are_empty(self):
        """Safety: numeric inputs should not have pre-populated values."""
        import re

        r = client.get("/blood-gas-stewart")
        for fld in ("pH", "pco2_mm_hg", "hco3_meq_per_l", "na_meq_per_l", "cl_meq_per_l", "albumin_g_per_dl"):
            m = re.search(rf'name="{fld}"[^>]*value="([^"]*)"', r.text)
            if m:
                # Must be empty string — no physiologic default substituted
                assert m.group(1) == "", (
                    f"Field {fld} has pre-filled value {m.group(1)!r} on initial GET"
                )

    def test_post_compute_returns_result(self):
        r = client.post(
            "/blood-gas-stewart/compute",
            data={
                "species": "dog",
                "base_excess": "-10",
                "pH": "7.25",
                "pco2_mm_hg": "32",
                "hco3_meq_per_l": "14",
                "na_meq_per_l": "142",
                "k_meq_per_l": "3.8",
                "cl_meq_per_l": "108",
                "lactate_mmol_per_l": "5.0",
                "albumin_g_per_dl": "1.8",
                "phosphate_mg_per_dl": "4.5",
            },
        )
        assert r.status_code == 200
        # All six BE components labeled
        for label in ("Free water", "Chloride", "Albumin", "Phosphate", "Lactate", "Unmeasured"):
            assert label in r.text
        # SIG present
        assert "SIG" in r.text
        # Cross-link back to Henderson view
        assert "/blood-gas" in r.text

    def test_cross_link_from_henderson_view(self):
        """The Stewart page should be linked from /blood-gas."""
        r = client.get("/blood-gas")
        assert r.status_code == 200
        assert "/blood-gas-stewart" in r.text

    def test_post_handles_bad_input_returns_placeholder(self):
        """Safety: unparseable inputs return placeholder, not a default
        decomposition with substituted values."""
        r = client.post(
            "/blood-gas-stewart/compute",
            data={
                "species": "dog",
                "base_excess": "not a number",
                "pH": "",
                "pco2_mm_hg": "abc",
                "hco3_meq_per_l": "??",
                "na_meq_per_l": "garbage",
                "cl_meq_per_l": "",
                "albumin_g_per_dl": "",
            },
        )
        assert r.status_code == 200
        assert "Awaiting input" in r.text
        assert "Unmeasured anions" not in r.text

    def test_post_partial_inputs_return_placeholder(self):
        """Safety: only some required fields filled → placeholder."""
        r = client.post(
            "/blood-gas-stewart/compute",
            data={
                "species": "dog",
                "pH": "7.25",
                "pco2_mm_hg": "32",
                "hco3_meq_per_l": "14",
                # Na, Cl, albumin deliberately missing
            },
        )
        assert r.status_code == 200
        assert "Awaiting input" in r.text


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


class TestCatalog:
    def test_catalog_entry_present(self):
        for f in ("slug", "display_name", "category", "kind", "mechanism_summary"):
            assert f in BLOOD_GAS_STEWART_CATALOG_ENTRY
            assert BLOOD_GAS_STEWART_CATALOG_ENTRY[f]
        assert BLOOD_GAS_STEWART_CATALOG_ENTRY["slug"] == "blood-gas-stewart"

    def test_appears_in_catalog_page(self):
        r = client.get("/calculators")
        assert "Stewart" in r.text

    def test_appears_in_drawer(self):
        r = client.get("/")
        assert "/blood-gas-stewart" in r.text


# ---------------------------------------------------------------------------
# Bonus: existing /blood-gas with the corrected-AG addition
# ---------------------------------------------------------------------------


class TestExistingBloodGasCorrectedAG:
    def test_corrected_ag_appears_when_alb_low(self):
        r = client.post(
            "/blood-gas/compute",
            data={
                "species": "dog",
                "sample": "arterial",
                "acuity": "acute",
                "pH": "7.25",
                "pco2_mm_hg": "32",
                "hco3_meq_per_l": "14",
                "na_meq_per_l": "142",
                "cl_meq_per_l": "108",
                "albumin_g_per_dl": "1.8",
            },
        )
        assert r.status_code == 200
        # Corrected-AG note should surface in the interpretation
        text_lower = r.text.lower()
        assert "corrected" in text_lower or "figge" in text_lower
        # And it should cross-link to the Stewart calc
        assert "/blood-gas-stewart" in r.text or "Stewart" in r.text

    def test_existing_compute_without_albumin_still_works(self):
        """Backward compatibility — albumin is optional."""
        r = client.post(
            "/blood-gas/compute",
            data={
                "species": "dog",
                "sample": "arterial",
                "acuity": "acute",
                "pH": "7.4",
                "pco2_mm_hg": "40",
                "hco3_meq_per_l": "22",
            },
        )
        assert r.status_code == 200
