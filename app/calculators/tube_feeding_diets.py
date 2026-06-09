"""
Tube feeding diet catalog.

This file is intentionally kept separate from the tube feeding calculator
logic so product specs can be updated periodically (formulations and pack
sizes change) without touching calculator code or tests.

Each TubeFeedingDiet entry describes a single SKU as labeled on the can or
bottle. Numbers come from manufacturer-published caloric content statements
or AAFCO labels on currently-marketed US packaging. Cross-check the can in
front of you before relying on these in a patient — manufacturers reformulate
without notice.

Last reviewed: 2026-05-16.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DietForm(str, Enum):
    """Physical form of the diet, which gates tube-type compatibility.

    Liquid diets are safe through NG/NE and E-tubes.
    Canned diets must be blenderized and are E-tube only — they will
    occlude small-bore NG/NE tubes regardless of how thoroughly blended.
    """

    LIQUID = "liquid"
    CANNED = "canned"


@dataclass(frozen=True)
class TubeFeedingDiet:
    """A single diet SKU available in the dropdown.

    Attributes:
        key: Stable identifier used as the option value in the form.
        label: Display name shown to the user.
        form: Liquid or canned. Drives tube-type compatibility.
        kcal_per_ml: Caloric density. For canned diets this is the
            label kcal/can divided by the can volume in mL; the user
            will see can-size and kcal/can fields auto-fill so they
            can verify against the actual can.
        can_size_ml: For canned diets, the labeled net weight converted
            to a volume estimate (assuming ~1 g/mL for these wet diets).
            None for liquid diets.
        can_kcal: For canned diets, the manufacturer-published kcal per
            can. None for liquid diets.
        notes: Free-text note shown beside the diet name in the
            feedback line, e.g. region of the listed spec.
    """

    key: str
    label: str
    form: DietForm
    kcal_per_ml: float
    can_size_ml: float | None = None
    can_kcal: float | None = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Diet catalog
#
# Sources are listed for each entry. When updating, replace the spec, bump
# the "Last reviewed" date at the top of this file, and confirm the URL
# still resolves.
# ---------------------------------------------------------------------------

ROYAL_CANIN_RECOVERY_LIQUID = TubeFeedingDiet(
    key="rc_recovery_liquid",
    label="Royal Canin Recovery Liquid",
    form=DietForm.LIQUID,
    kcal_per_ml=1.0,
    notes="8 oz bottle, 1.0 kcal/mL as labeled.",
    # Source: Royal Canin Recovery Convalescence Liquid label, metabolisable
    # energy 1 kcal/mL. Available in 4-pack of 8 oz bottles in US.
)

HILLS_AD = TubeFeedingDiet(
    key="hills_ad",
    label="Hill's a/d",
    form=DietForm.CANNED,
    kcal_per_ml=183 / 156,  # ≈ 1.17 kcal/mL
    can_size_ml=156.0,  # 5.5 oz net weight, ~1 g/mL
    can_kcal=183.0,
    notes="5.5 oz (156 g) can, 183 kcal/can.",
    # Source: hillspet.com Prescription Diet a/d product page, caloric
    # content 183 kcal / 5.5 oz (156 g) can.
)

ROYAL_CANIN_RECOVERY_CANNED = TubeFeedingDiet(
    key="rc_recovery_canned",
    label="Royal Canin Recovery (canned)",
    form=DietForm.CANNED,
    kcal_per_ml=149 / 145,  # ≈ 1.03 kcal/mL
    can_size_ml=145.0,  # 5.1 oz net weight, ~1 g/mL
    can_kcal=149.0,
    notes="5.1 oz (145 g) US can, 149 kcal/can.",
    # Source: Royal Canin Recovery as-fed label per current US 5.1 oz can,
    # 1025 kcal ME/kg, 149 kcal/can. EU 195 g packaging differs and is
    # not represented here. If the can in front of you shows a different
    # size or kcal/can, switch to Other and enter values directly.
)


DIETS: tuple[TubeFeedingDiet, ...] = (
    ROYAL_CANIN_RECOVERY_LIQUID,
    HILLS_AD,
    ROYAL_CANIN_RECOVERY_CANNED,
)


# Reserved key used by the form to signal manual entry of can size and
# kcal/can. Not a TubeFeedingDiet because the values come from the user,
# not the catalog.
OTHER_KEY = "other"


def diet_by_key(key: str) -> TubeFeedingDiet | None:
    """Look up a diet by its stable key. Returns None if not found
    (including for the sentinel ``OTHER_KEY``)."""
    for diet in DIETS:
        if diet.key == key:
            return diet
    return None
