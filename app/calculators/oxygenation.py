"""
Oxygenation assessment: PaO2:FiO2 ratio and alveolar-arterial gradient.

Two complementary tools computed from a single arterial blood gas plus
the patient's inspired oxygen concentration:

  PaO2:FiO2 ratio
    Quantifies oxygenation efficiency on a single scale comparable
    across patients receiving different FiO2. Adapted from the human
    Berlin ARDS criteria (ARDS Definition Task Force, JAMA 2012) and
    the veterinary ALI/ARDS consensus (Wilkins et al, JVECC 2007).

      > 400        Normal
      300 – 400    Mild oxygenation impairment
      200 – 300    Moderate (ALI threshold)
      100 – 200    Severe (ARDS equivalent)
      < 100        Very severe

  Alveolar-arterial (A-a) gradient
    Difference between the calculated alveolar PO2 (from the alveolar
    gas equation) and the measured arterial PaO2. Distinguishes the
    physiological cause of hypoxemia:

      Normal A-a + hypoxemia    Hypoventilation (PaCO2 typically high)
      Elevated A-a, O2-responsive    V/Q mismatch
      Elevated A-a, O2-refractory    True shunt
      Elevated A-a, normal CO2  Diffusion impairment or shunt

Alveolar gas equation:
    PAO2 = FiO2 × (Patm − PH2O) − PaCO2 / R

  Default constants:
    Patm   760 mmHg     Sea level barometric pressure
    PH2O    47 mmHg     Water vapor pressure at 37 °C
    R        0.8        Respiratory quotient on a mixed diet

  At sea level with default R:
    PAO2 = FiO2 × 713 − PaCO2 / 0.8

A-a gradient = PAO2 − PaO2.

Normal A-a thresholds:
    Room air, young patient    < 15 mmHg
    Room air, geriatric         varies; no firm vet-specific value
    On supplemental O2          rises with FiO2 because alveolar PO2
                                rises faster than the patient can
                                equilibrate; a rough rule of thumb is
                                A-a < (FiO2 × 100) − 10, but the
                                qualitative interpretation (high vs
                                normal) matters more than the precise
                                cutoff

Vet-specific notes:
    The physics of the alveolar gas equation are species-neutral and
    apply to dogs and cats identically. Reference ranges for PaO2 and
    A-a derive from human medicine; veterinary literature adapts
    them. The Berlin ARDS cutoffs are used by ACVECC and most vet ICU
    clinicians as the working classification.

    Elevation matters: Patm at 1500 m (~5000 ft) is ~640 mmHg, which
    drops the maximal achievable PaO2 by 20+ mmHg. The calculator
    accepts a custom Patm to handle altitude.

Sources:
    West JB, Luks AM. West's Respiratory Physiology: The Essentials.
        11th ed. Wolters Kluwer; 2020. Alveolar gas equation,
        A-a gradient physiology, and shunt/V-Q-mismatch framework.
    Lumb AB, Jones GM. Lumb and Jones' Veterinary Anesthesia and
        Analgesia. 6th ed. Wiley-Blackwell; 2024. Ch. 22 (Respiratory
        Monitoring) — alveolar gas equation and A-a interpretation in
        veterinary anesthesia.
    Silverstein DC, Hopper K, eds. Small Animal Critical Care
        Medicine. 4th ed. Elsevier; 2023. Ch. 23 (Oxygenation and
        Ventilation Monitoring) — P:F ratio and A-a gradient as ICU
        oxygenation metrics in dogs and cats.
    ARDS Definition Task Force. Acute Respiratory Distress Syndrome:
        the Berlin Definition. JAMA. 2012;307(23):2526–2533.
        doi:10.1001/jama.2012.5669. Source for the P:F cutoffs.
    Wilkins PA, Otto CM, Baumgardner JE, et al. Acute lung injury and
        acute respiratory distress syndromes in veterinary medicine:
        consensus definitions. J Vet Emerg Crit Care (San Antonio).
        2007;17(4):333–339. Veterinary ALI/ARDS adaptation of the
        Berlin criteria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engine import Source


class FiO2Unit(str, Enum):
    """FiO2 is sometimes documented as a decimal (0.40) and sometimes
    as a percent (40%). The calculator accepts either and converts
    internally to decimal."""

    DECIMAL = "decimal"
    PERCENT = "percent"


# Physical constants
PH2O_MMHG_AT_37C = 47.0  # water vapor pressure at body temperature
DEFAULT_PATM_MMHG = 760.0  # sea level
DEFAULT_R = 0.8  # respiratory quotient on a mixed diet

# Berlin-adapted P:F cutoffs (per ARDS Definition Task Force 2012 and
# Wilkins et al 2007 for veterinary use).
PF_NORMAL_LO = 400.0
PF_MILD_LO = 300.0  # 300-400 mild
PF_MODERATE_LO = 200.0  # 200-300 moderate (ALI)
PF_SEVERE_LO = 100.0  # 100-200 severe (ARDS); <100 very severe


@dataclass
class OxygenationInputs:
    """Form inputs. Empty defaults so the form yields no result until
    PaO2, FiO2, and PaCO2 are provided (Safety Rule #8)."""

    pao2_mmhg: float = 0.0
    fio2_value: float = 0.0
    fio2_unit: FiO2Unit = FiO2Unit.DECIMAL
    paco2_mmhg: float = 0.0
    patm_mmhg: float = DEFAULT_PATM_MMHG  # optional override for altitude
    respiratory_quotient: float = DEFAULT_R  # rarely changed in practice


@dataclass
class OxygenationResult:
    inputs: OxygenationInputs
    valid: bool
    errors: list[str] = field(default_factory=list)

    # Computed values
    fio2_decimal: float = 0.0  # normalized FiO2 in 0.0–1.0 range
    pf_ratio: float = 0.0
    pa_o2_alveolar_mmhg: float = 0.0  # PAO2, the alveolar partial pressure
    a_a_gradient_mmhg: float = 0.0
    pf_classification: str = ""  # normal / mild / moderate / severe / very_severe
    pf_label: str = ""  # human-readable
    on_room_air: bool = False

    interpretation: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


_SOURCES: list[Source] = [
    Source(
        citation=(
            "West JB, Luks AM. West's Respiratory Physiology: The "
            "Essentials. 11th ed. Wolters Kluwer; 2020. Foundational "
            "physiology reference for the alveolar gas equation, the "
            "A-a gradient, and the shunt vs V/Q mismatch framework. "
            "The constants used in this calculator (PH2O 47 mmHg at "
            "37 °C, R 0.8 for a mixed diet, Patm 760 mmHg at sea "
            "level) derive from this source."
        ),
    ),
    Source(
        citation=(
            "Lumb AB, Jones GM. Lumb and Jones' Veterinary Anesthesia "
            "and Analgesia. 6th ed. Wiley-Blackwell; 2024. Ch. 22 "
            "(Respiratory Monitoring). Veterinary application of the "
            "alveolar gas equation and A-a interpretation in anesthesia "
            "and emergency contexts."
        ),
    ),
    Source(
        citation=(
            "Silverstein DC, Hopper K, eds. Small Animal Critical Care "
            "Medicine. 4th ed. St. Louis, MO: Elsevier; 2023. Ch. 23 "
            "(Oxygenation and Ventilation Monitoring). P:F ratio and "
            "A-a gradient as ICU oxygenation metrics in dogs and cats; "
            "Berlin-adapted ARDS classification."
        ),
    ),
    Source(
        citation=(
            "ARDS Definition Task Force. Acute Respiratory Distress "
            "Syndrome: the Berlin Definition. JAMA. 2012;307(23):"
            "2526–2533. doi:10.1001/jama.2012.5669. Source of the P:F "
            "cutoffs (>300 normal/mild; 200–300 mild ARDS in Berlin "
            "terms but ALI in our usage; 100–200 moderate; <100 "
            "severe). Wilkins et al 2007 JVECC adapted these for "
            "veterinary use."
        ),
    ),
    Source(
        citation=(
            "Wilkins PA, Otto CM, Baumgardner JE, et al. Acute lung "
            "injury and acute respiratory distress syndromes in "
            "veterinary medicine: consensus definitions. J Vet Emerg "
            "Crit Care (San Antonio). 2007;17(4):333–339. Veterinary "
            "ALI/ARDS consensus adapting the human Berlin criteria for "
            "small animal use."
        ),
    ),
]


def _validate(inputs: OxygenationInputs) -> list[str]:
    errors: list[str] = []
    if inputs.pao2_mmhg <= 0:
        errors.append("Enter PaO₂.")
    elif not (10.0 <= inputs.pao2_mmhg <= 700.0):
        errors.append("PaO₂ must be between 10 and 700 mmHg.")

    if inputs.fio2_value <= 0:
        errors.append("Enter FiO₂.")
    else:
        # Normalize to decimal for validation
        decimal = (
            inputs.fio2_value
            if inputs.fio2_unit == FiO2Unit.DECIMAL
            else inputs.fio2_value / 100.0
        )
        if not (0.21 <= decimal <= 1.0):
            errors.append(
                "FiO₂ must be between 0.21 (room air) and 1.0 (100%). "
                "If entered as percent, use the % toggle."
            )

    if inputs.paco2_mmhg <= 0:
        errors.append("Enter PaCO₂.")
    elif not (10.0 <= inputs.paco2_mmhg <= 150.0):
        errors.append("PaCO₂ must be between 10 and 150 mmHg.")

    if inputs.patm_mmhg <= 0:
        errors.append("Barometric pressure must be positive.")
    elif not (400.0 <= inputs.patm_mmhg <= 800.0):
        errors.append(
            "Barometric pressure must be between 400 (high altitude) "
            "and 800 mmHg (slightly above sea level). Default 760."
        )

    if inputs.respiratory_quotient <= 0:
        errors.append("Respiratory quotient must be positive.")
    elif not (0.5 <= inputs.respiratory_quotient <= 1.2):
        errors.append("Respiratory quotient must be between 0.5 and 1.2.")

    return errors


def _classify_pf(pf: float) -> tuple[str, str]:
    """Return (machine_classification, human_label)."""
    if pf >= PF_NORMAL_LO:
        return ("normal", "Normal oxygenation")
    if pf >= PF_MILD_LO:
        return ("mild", "Mild oxygenation impairment")
    if pf >= PF_MODERATE_LO:
        return ("moderate", "Moderate (ALI threshold)")
    if pf >= PF_SEVERE_LO:
        return ("severe", "Severe (ARDS equivalent)")
    return ("very_severe", "Very severe")


def compute_oxygenation(inputs: OxygenationInputs) -> OxygenationResult:
    errors = _validate(inputs)
    if errors:
        return OxygenationResult(
            inputs=inputs, valid=False, errors=errors, sources=_SOURCES
        )

    # Normalize FiO2 to decimal
    if inputs.fio2_unit == FiO2Unit.PERCENT:
        fio2_decimal = inputs.fio2_value / 100.0
    else:
        fio2_decimal = inputs.fio2_value
    on_room_air = abs(fio2_decimal - 0.21) < 0.005

    # P:F ratio
    pf = inputs.pao2_mmhg / fio2_decimal
    pf_class, pf_label = _classify_pf(pf)

    # Alveolar gas equation: PAO2 = FiO2 × (Patm − PH2O) − PaCO2/R
    pa_o2_alveolar = (
        fio2_decimal * (inputs.patm_mmhg - PH2O_MMHG_AT_37C)
        - inputs.paco2_mmhg / inputs.respiratory_quotient
    )
    a_a_gradient = pa_o2_alveolar - inputs.pao2_mmhg

    interpretation: list[str] = []
    warnings: list[str] = []

    # P:F interpretation
    if pf_class == "normal":
        interpretation.append(
            f"P:F ratio is {pf:.0f} (PaO₂ {inputs.pao2_mmhg:.0f} mmHg ÷ "
            f"FiO₂ {fio2_decimal:.2f}). Within the normal range "
            f"(>400). Oxygenation efficiency does not currently "
            f"indicate clinically significant pulmonary dysfunction."
        )
    elif pf_class == "mild":
        interpretation.append(
            f"P:F ratio is {pf:.0f}. Mild oxygenation impairment "
            f"(300–400). Suggests early V/Q mismatch from pneumonia, "
            f"atelectasis, edema, or anesthesia-related compression. "
            f"Below the threshold for ALI but worth a workup."
        )
    elif pf_class == "moderate":
        interpretation.append(
            f"P:F ratio is {pf:.0f}. Moderate oxygenation impairment "
            f"(200–300, the ALI threshold per veterinary consensus "
            f"and the lower mild-ARDS bound per Berlin). Aspiration "
            f"pneumonia, transfusion-related lung injury, sepsis-"
            f"associated lung injury, and significant atelectasis "
            f"are common causes. Aggressive workup indicated."
        )
    elif pf_class == "severe":
        interpretation.append(
            f"P:F ratio is {pf:.0f}. Severe oxygenation impairment "
            f"(100–200, ARDS equivalent per Berlin). Requires "
            f"escalated respiratory support: high-flow oxygen, "
            f"non-invasive ventilation, or mechanical ventilation "
            f"depending on patient response. Mortality is "
            f"substantially elevated at this level in veterinary ICU "
            f"populations."
        )
    else:  # very_severe
        interpretation.append(
            f"P:F ratio is {pf:.0f}. Very severe (<100). Refractory "
            f"hypoxemia despite high FiO₂. Mechanical ventilation "
            f"with lung-protective settings is typically required; "
            f"prognosis is guarded."
        )

    # A-a gradient interpretation
    interpretation.append(
        f"Alveolar PO₂ (PAO₂) is {pa_o2_alveolar:.0f} mmHg "
        f"(FiO₂ {fio2_decimal:.2f} × {inputs.patm_mmhg - PH2O_MMHG_AT_37C:.0f} − "
        f"PaCO₂/R). A-a gradient is "
        f"{a_a_gradient:.0f} mmHg."
    )

    # Differentiating cause of hypoxemia using A-a + PaCO2 + room-air context
    is_hypoxemic = inputs.pao2_mmhg < (80.0 if on_room_air else 100.0)
    is_hypercapnic = inputs.paco2_mmhg > 45.0

    if on_room_air:
        if a_a_gradient < 15.0:
            if is_hypoxemic and is_hypercapnic:
                interpretation.append(
                    "Normal A-a gradient with hypoxemia and hypercapnia "
                    "is the classic pattern for hypoventilation. The "
                    "alveolar gas equation predicts that as PaCO₂ rises, "
                    "PaO₂ must fall by an equivalent amount to preserve "
                    "the gradient. Look for the cause of hypoventilation: "
                    "anesthetic depth, opioid-induced respiratory "
                    "depression, neuromuscular disease, pleural space "
                    "disease, or upper airway obstruction."
                )
            else:
                interpretation.append(
                    "A-a gradient is within the normal range for room "
                    "air (<15 mmHg). No evidence of V/Q mismatch, shunt, "
                    "or diffusion impairment at this time."
                )
        else:
            # Elevated A-a on room air
            interpretation.append(
                f"A-a gradient of {a_a_gradient:.0f} mmHg on room air "
                f"exceeds the normal limit (<15 mmHg in young patients). "
                f"Indicates V/Q mismatch, shunt, or diffusion "
                f"impairment. The diagnostic discriminator is response "
                f"to supplemental oxygen: V/Q mismatch corrects fully "
                f"or substantially with high FiO₂; true shunt does not."
            )
    else:
        # Patient on supplemental oxygen
        # Rough cutoff: A-a < (FiO2_percent − 10) on supplemental O2.
        # Imperfect, but a useful sanity check.
        expected_aa_ceiling = (fio2_decimal * 100.0) - 10.0
        if a_a_gradient < max(15.0, expected_aa_ceiling):
            interpretation.append(
                f"A-a gradient of {a_a_gradient:.0f} mmHg at FiO₂ "
                f"{fio2_decimal:.2f} is within a reasonable range for "
                f"the elevated alveolar PO₂ (rough rule of thumb: A-a "
                f"< {expected_aa_ceiling:.0f} mmHg at this FiO₂). The "
                f"P:F ratio is the more reliable metric for "
                f"oxygenation efficiency on supplemental oxygen."
            )
        else:
            interpretation.append(
                f"A-a gradient of {a_a_gradient:.0f} mmHg at FiO₂ "
                f"{fio2_decimal:.2f} is elevated above the rough "
                f"expected ceiling (<{expected_aa_ceiling:.0f} mmHg at "
                f"this FiO₂). Suggests significant V/Q mismatch or "
                f"shunt. If hypoxemia persists despite high FiO₂, "
                f"shunt physiology (pulmonary contusion, severe "
                f"consolidation, pulmonary edema, intracardiac shunt) "
                f"becomes the leading differential."
            )

    # Hypercapnia warning, surfaced separately because it's actionable
    # independent of the A-a finding.
    if is_hypercapnic:
        warnings.append(
            f"PaCO₂ {inputs.paco2_mmhg:.0f} mmHg indicates "
            f"hypoventilation. Assess ventilatory drive and mechanics: "
            f"anesthetic depth, opioid load, neuromuscular function, "
            f"pleural space, and upper airway patency. Mechanical "
            f"ventilation may be required regardless of oxygenation "
            f"if hypercapnia is severe or worsening."
        )

    # Severe hypoxemia warning
    if pf < PF_SEVERE_LO:
        warnings.append(
            "P:F ratio <100 indicates very severe oxygenation failure "
            "refractory to high FiO₂. Escalate respiratory support "
            "immediately (mechanical ventilation with lung-protective "
            "tidal volumes 6–8 mL/kg, PEEP titration). Prognosis is "
            "guarded; consider goals-of-care discussion in parallel "
            "with maximal support."
        )

    return OxygenationResult(
        inputs=inputs,
        valid=True,
        fio2_decimal=fio2_decimal,
        pf_ratio=pf,
        pa_o2_alveolar_mmhg=pa_o2_alveolar,
        a_a_gradient_mmhg=a_a_gradient,
        pf_classification=pf_class,
        pf_label=pf_label,
        on_room_air=on_room_air,
        interpretation=interpretation,
        warnings=warnings,
        sources=_SOURCES,
    )


OXYGENATION_CATALOG_ENTRY = {
    "slug": "oxygenation",
    "display_name": "Oxygenation · PaO₂:FiO₂ and A-a gradient",
    "short_name": "P:F + A-a",
    "category": "Acid-base & blood gas",
    "mechanism_summary": (
        "Two complementary oxygenation metrics from a single arterial "
        "blood gas: the PaO₂:FiO₂ ratio (Berlin-adapted ARDS "
        "classification used by ACVECC) and the alveolar-arterial "
        "gradient (distinguishes hypoventilation, V/Q mismatch, and "
        "shunt as causes of hypoxemia)."
    ),
    "indications_summary": (
        "Quantify oxygenation efficiency and identify the physiologic "
        "cause of hypoxemia. P:F ratio classifies severity from normal "
        "to very severe (Berlin/Wilkins cutoffs at 300, 200, 100). "
        "A-a gradient with PaCO₂ context discriminates hypoventilation "
        "(normal A-a + high PaCO₂), V/Q mismatch (high A-a, "
        "oxygen-responsive), and true shunt (high A-a, oxygen-"
        "refractory). Altitude-aware via custom barometric pressure."
    ),
}
