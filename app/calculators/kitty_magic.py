"""
Kitty Magic (DKT / Triple Combination) calculator for cats.

Source: Plumb's Veterinary Drugs, Dexmedetomidine monograph (current edition).
Table reference: "In combination with an opioid and ketamine (ie, 'kitty magic',
DKT, or Triple Combination) to provide sedation and analgesia (extra-label)"

Critical stock concentrations; protocol only works with these exact products:
    Dexmedetomidine: 0.5 mg/mL (500 µg/mL)  [Dexdomitor®]
    Ketamine:        100 mg/mL
    Butorphanol:     10 mg/mL
    Buprenorphine:   0.3 mg/mL

The protocol draws equal volumes of each drug (Dex + Ketamine + Opioid)
into a single syringe and administers IM.

Volume per drug per sedation level (from Plumb's Table):
    Weight 2–3 kg:   Mild 0.025 mL  Moderate 0.05 mL  Profound 0.1–0.15 mL
    Weight 3–4 kg:   Mild 0.05 mL   Moderate 0.1 mL   Profound 0.2–0.25 mL
    Weight 4–6 kg:   Mild 0.1 mL    Moderate 0.2 mL   Profound 0.3–0.35 mL
    Weight 6–7 kg:   Mild 0.2 mL    Moderate 0.3 mL   Profound 0.4–0.45 mL
    Weight 7–8 kg:   Mild 0.3 mL    Moderate 0.4 mL   Profound 0.5–0.55 mL

Sedation levels:
    Mild:     Sedation or preanesthesia before anesthetic induction
    Moderate: Castration or minor surgical procedures
    Profound: Invasive surgery including OHE and declaw

Reversal:
    Atipamezole IM at the same volume as the dexmedetomidine dose used.
    This reverses dexmedetomidine (and its analgesia). Additional analgesia
    required if reversed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source

# ── Stock concentrations ─────────────────────────────────────────────────────
DEX_STOCK_MG_PER_ML = 0.5  # Dexdomitor® 0.5 mg/mL (500 µg/mL)
KETAMINE_STOCK_MG_PER_ML = 100.0
BUTORPHANOL_STOCK_MG_PER_ML = 10.0
BUPRENORPHINE_STOCK_MG_PER_ML = 0.3


class KittyMagicOpioid(str, Enum):
    BUTORPHANOL = "butorphanol"
    BUPRENORPHINE = "buprenorphine"


class KittyMagicLevel(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    PROFOUND = "profound"


# ── Lookup table directly from Plumb's ───────────────────────────────────────
# (weight_min_kg, weight_max_kg): {level: (vol_low_ml, vol_high_ml)}
# Where vol_low == vol_high for a single value, both are equal.
_TABLE: list[tuple[float, float, dict[KittyMagicLevel, tuple[float, float]]]] = [
    (
        2.0,
        3.0,
        {
            KittyMagicLevel.MILD: (0.025, 0.025),
            KittyMagicLevel.MODERATE: (0.05, 0.05),
            KittyMagicLevel.PROFOUND: (0.10, 0.15),
        },
    ),
    (
        3.0,
        4.0,
        {
            KittyMagicLevel.MILD: (0.05, 0.05),
            KittyMagicLevel.MODERATE: (0.10, 0.10),
            KittyMagicLevel.PROFOUND: (0.20, 0.25),
        },
    ),
    (
        4.0,
        6.0,
        {
            KittyMagicLevel.MILD: (0.10, 0.10),
            KittyMagicLevel.MODERATE: (0.20, 0.20),
            KittyMagicLevel.PROFOUND: (0.30, 0.35),
        },
    ),
    (
        6.0,
        7.0,
        {
            KittyMagicLevel.MILD: (0.20, 0.20),
            KittyMagicLevel.MODERATE: (0.30, 0.30),
            KittyMagicLevel.PROFOUND: (0.40, 0.45),
        },
    ),
    (
        7.0,
        8.0,
        {
            KittyMagicLevel.MILD: (0.30, 0.30),
            KittyMagicLevel.MODERATE: (0.40, 0.40),
            KittyMagicLevel.PROFOUND: (0.50, 0.55),
        },
    ),
]


@dataclass
class KittyMagicInputs:
    weight_kg: float
    opioid: KittyMagicOpioid
    level: KittyMagicLevel


@dataclass
class DrugDose:
    name: str
    stock_mg_per_ml: float
    stock_label: str
    vol_low_ml: float
    vol_high_ml: float
    dose_low_mg: float
    dose_high_mg: float
    dose_low_per_kg: str  # formatted string with unit
    dose_high_per_kg: str


@dataclass
class KittyMagicResult:
    inputs: KittyMagicInputs
    weight_kg: float
    level: KittyMagicLevel
    opioid: KittyMagicOpioid
    in_table: bool  # False if weight outside 2–8 kg
    nearest_band: str  # e.g. "4–6 kg"

    drugs: list[DrugDose] = field(default_factory=list)

    # Per-drug volumes (convenience)
    vol_low_ml: float = 0.0
    vol_high_ml: float = 0.0
    total_vol_low_ml: float = 0.0
    total_vol_high_ml: float = 0.0

    # Atipamezole reversal = same volume as dex dose
    atipamezole_vol_low_ml: float = 0.0
    atipamezole_vol_high_ml: float = 0.0

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: tuple[Source, ...] = ()


def _lookup(weight_kg: float, level: KittyMagicLevel) -> tuple[bool, str, float, float]:
    """Return (in_table, band_label, vol_low, vol_high)."""
    for wmin, wmax, levels in _TABLE:
        if wmin <= weight_kg <= wmax:
            vlow, vhigh = levels[level]
            return True, f"{wmin:.0f}–{wmax:.0f} kg", vlow, vhigh
    # Outside table, extrapolate a warning but still return nearest band
    if weight_kg < 2.0:
        vlow, vhigh = _TABLE[0][2][level]
        return False, "< 2 kg (below table)", vlow, vhigh
    vlow, vhigh = _TABLE[-1][2][level]
    return False, "> 8 kg (above table)", vlow, vhigh


def calculate(inputs: KittyMagicInputs) -> KittyMagicResult:
    warnings: list[str] = []
    notes: list[str] = []

    in_table, band, vol_low, vol_high = _lookup(inputs.weight_kg, inputs.level)

    if not in_table:
        warnings.append(
            f"Weight {inputs.weight_kg:.1f} kg is outside the Plumb's table range "
            f"(2–8 kg). Volumes shown are from the nearest band. "
            f"Use clinical judgment and consult an anesthesiologist."
        )

    # Opioid stock
    if inputs.opioid == KittyMagicOpioid.BUTORPHANOL:
        opioid_stock = BUTORPHANOL_STOCK_MG_PER_ML
        opioid_name = "Butorphanol"
        opioid_stock_label = "10 mg/mL"

        def opioid_dose_per_kg(vol: float) -> str:
            mg = vol * opioid_stock
            return f"{mg / inputs.weight_kg:.3f} mg/kg"
    else:
        opioid_stock = BUPRENORPHINE_STOCK_MG_PER_ML
        opioid_name = "Buprenorphine"
        opioid_stock_label = "0.3 mg/mL"

        def opioid_dose_per_kg(vol: float) -> str:
            ug = vol * opioid_stock * 1000
            return f"{ug / inputs.weight_kg:.1f} µg/kg"

    def dex_dose_per_kg(vol: float) -> str:
        ug = vol * DEX_STOCK_MG_PER_ML * 1000
        return f"{ug / inputs.weight_kg:.1f} µg/kg"

    def ket_dose_per_kg(vol: float) -> str:
        mg = vol * KETAMINE_STOCK_MG_PER_ML
        return f"{mg / inputs.weight_kg:.2f} mg/kg"

    drugs = [
        DrugDose(
            name="Dexmedetomidine",
            stock_mg_per_ml=DEX_STOCK_MG_PER_ML,
            stock_label="0.5 mg/mL (500 µg/mL)",
            vol_low_ml=vol_low,
            vol_high_ml=vol_high,
            dose_low_mg=round(vol_low * DEX_STOCK_MG_PER_ML, 4),
            dose_high_mg=round(vol_high * DEX_STOCK_MG_PER_ML, 4),
            dose_low_per_kg=dex_dose_per_kg(vol_low),
            dose_high_per_kg=dex_dose_per_kg(vol_high),
        ),
        DrugDose(
            name="Ketamine",
            stock_mg_per_ml=KETAMINE_STOCK_MG_PER_ML,
            stock_label="100 mg/mL",
            vol_low_ml=vol_low,
            vol_high_ml=vol_high,
            dose_low_mg=round(vol_low * KETAMINE_STOCK_MG_PER_ML, 3),
            dose_high_mg=round(vol_high * KETAMINE_STOCK_MG_PER_ML, 3),
            dose_low_per_kg=ket_dose_per_kg(vol_low),
            dose_high_per_kg=ket_dose_per_kg(vol_high),
        ),
        DrugDose(
            name=opioid_name,
            stock_mg_per_ml=opioid_stock,
            stock_label=opioid_stock_label,
            vol_low_ml=vol_low,
            vol_high_ml=vol_high,
            dose_low_mg=round(vol_low * opioid_stock, 4),
            dose_high_mg=round(vol_high * opioid_stock, 4),
            dose_low_per_kg=opioid_dose_per_kg(vol_low),
            dose_high_per_kg=opioid_dose_per_kg(vol_high),
        ),
    ]

    total_low = round(vol_low * 3, 4)
    total_high = round(vol_high * 3, 4)

    # Atipamezole reversal = same volume as dex (= vol_low or vol_high)
    warnings.append(
        "Stock concentrations are critical. This protocol only works correctly "
        "with: Dexmedetomidine 0.5 mg/mL (Dexdomitor®), Ketamine 100 mg/mL, "
        f"{opioid_name} {opioid_stock_label}. Verify each vial label before drawing up."
    )
    warnings.append(
        "Dexmedetomidine causes significant bradycardia and peripheral vasoconstriction. "
        "Mucous membranes will appear pale/grey, this is expected, not shock. "
        "Monitor SpO₂, HR, RR, and temperature. Apply ophthalmic lubricant (eyes remain open). "
        "Contraindicated in cats with cardiac disease, respiratory disorders, shock, or severe debilitation."
    )
    if inputs.opioid == KittyMagicOpioid.BUPRENORPHINE:
        warnings.append(
            "Buprenorphine has a slower onset than butorphanol, allow 20–30 min for full effect. "
            "Sedation may be less predictable and of slower onset but longer duration than "
            "butorphanol-based kitty magic (Plumb's). Monitor carefully before assuming "
            "inadequate depth."
        )
    if inputs.level == KittyMagicLevel.PROFOUND:
        warnings.append(
            "Profound sedation level, appropriate for OHE, declaw, and invasive surgery. "
            "Intubation capability and oxygen supplementation should be immediately available. "
            "Respiratory depression is more likely at this level."
        )

    notes.append(
        "Draw up equal volumes of each drug into a single syringe and administer IM. "
        "Onset 5–10 min, peak effect 15–30 min. "
        "Sedation/analgesia occurs within 5–15 minutes; allow cat to rest quietly after injection."
    )
    notes.append(
        "Reversal: atipamezole IM at the same volume as the dexmedetomidine dose used. "
        "This reverses the alpha-2 effect AND its analgesia, provide additional analgesia if reversed."
    )
    notes.append(
        "For lighter sedation (preanesthesia only), ketamine can be "
        "omitted from the protocol. The dex + opioid combination will "
        "then provide lighter, shorter sedation."
    )

    return KittyMagicResult(
        inputs=inputs,
        weight_kg=inputs.weight_kg,
        level=inputs.level,
        opioid=inputs.opioid,
        in_table=in_table,
        nearest_band=band,
        drugs=drugs,
        vol_low_ml=vol_low,
        vol_high_ml=vol_high,
        total_vol_low_ml=total_low,
        total_vol_high_ml=total_high,
        atipamezole_vol_low_ml=vol_low,
        atipamezole_vol_high_ml=vol_high,
        warnings=warnings,
        notes=notes,
        sources=KITTY_MAGIC_SOURCES,
    )


KITTY_MAGIC_SOURCES = (
    Source(
        citation=(
            "Plumb DC. Plumb's Veterinary Drugs, dexmedetomidine monograph, "
            "section on combination IM sedation in cats (kitty magic / DKT / "
            "Triple Combination, extra-label). Plus ketamine and butorphanol "
            "or buprenorphine monographs for component dosing."
        )
    ),
    Source(
        citation=(
            "Ko JC, Berman AG. Anesthesia in shelter medicine. Top Companion "
            "Anim Med 2010;25(2):92–97. (Discusses combination IM protocols "
            "for cats including dexmedetomidine-ketamine-opioid combinations.)"
        )
    ),
    Source(
        citation=(
            "Robertson SA, Lascelles BDX. Long-term pain in cats: how much do "
            "we know about this important problem? J Feline Med Surg "
            "2010;12(3):188–199."
        )
    ),
)


KITTY_MAGIC_CATALOG_ENTRY = {
    "slug": "kitty-magic",
    "display_name": "Kitty Magic (DKT)",
    "short_name": "DKT",
    "category": "Analgesia",
    "kind": "multi_drug_protocol",
    "mechanism_summary": (
        "Combination IM sedation/anesthesia protocol for cats: "
        "dexmedetomidine (α₂ agonist), ketamine (dissociative / NMDA antagonist), "
        "and butorphanol or buprenorphine (opioid). Single IM injection; "
        "onset 5–10 min; reversible with atipamezole."
    ),
}
