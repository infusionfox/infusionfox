"""
Generate a peer-review packet PDF.

The packet is one page per calculator. Each page lists:
  - Calculator name and the clinical question it answers
  - Inputs the user provides
  - Encoded values, in clinical language (not code)
  - Sliding scale or dose range, as a table
  - Species-specific persistent warnings
  - Cited source(s)
  - A markup box for the reviewer

Intended audience: practicing veterinarians. They should be able to read
one page in 5 minutes, compare it against their reference textbook, and
mark anything off. No code, no test names, no filenames.

Usage:
    python3 scripts/build_review_packet.py [output.pdf]

Default output: data/peer_review_packet.pdf

The packet is regenerated from source, so when constants change it stays
in sync. A reviewer's notes map back to the calculator name (the page
header), which is the slug in the codebase.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

styles = getSampleStyleSheet()

CALCULATOR_TITLE = ParagraphStyle(
    "CalcTitle",
    parent=styles["Heading1"],
    fontSize=13,
    spaceAfter=2,
    textColor=colors.HexColor("#1f3a5f"),
)
CALCULATOR_SUBTITLE = ParagraphStyle(
    "CalcSubtitle",
    parent=styles["Normal"],
    fontSize=8.5,
    textColor=colors.HexColor("#6b7280"),
    spaceAfter=8,
)
SECTION_HEADER = ParagraphStyle(
    "SectionHeader",
    parent=styles["Heading3"],
    fontSize=9.5,
    textColor=colors.HexColor("#1f3a5f"),
    spaceBefore=6,
    spaceAfter=2,
    keepWithNext=True,
)
BODY = ParagraphStyle(
    "BodyText",
    parent=styles["Normal"],
    fontSize=8.5,
    spaceAfter=2,
    leading=10.5,
)
WARNING_BODY = ParagraphStyle(
    "WarningBody",
    parent=BODY,
    leftIndent=8,
    fontSize=8,
    leading=10,
    textColor=colors.HexColor("#7c2d12"),
    spaceAfter=1,
)
SOURCE = ParagraphStyle(
    "Source",
    parent=BODY,
    fontSize=8,
    fontName="Helvetica-Oblique",
    leading=10,
    textColor=colors.HexColor("#3b3f4a"),
)
COVER_TITLE = ParagraphStyle(
    "CoverTitle",
    parent=styles["Title"],
    fontSize=22,
    textColor=colors.HexColor("#1f3a5f"),
    spaceAfter=18,
)
COVER_BODY = ParagraphStyle(
    "CoverBody",
    parent=styles["Normal"],
    fontSize=10,
    leading=14,
    spaceAfter=8,
)


def _table_style(header_bg: str = "#e6ecf3") -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#13151a")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ]
    )


# ---------------------------------------------------------------------------
# Per-calculator extraction. Each function returns a list of flowables
# (the page body); the renderer wraps with header + markup box + page break.
# ---------------------------------------------------------------------------


@dataclass
class ReviewPage:
    slug: str
    title: str
    subtitle: str
    body: list  # list of flowables
    priority: int  # 1 = highest stakes


def _wrap_table(rows: list, col_widths: list[float]) -> Table:
    """Wrap text content in Paragraphs so cells can wrap."""
    wrapped = [[Paragraph(str(c), BODY) if not isinstance(c, Paragraph) else c for c in row] for row in rows]
    t = Table(wrapped, colWidths=col_widths, repeatRows=1)
    t.setStyle(_table_style())
    return t


def _para(text: str, style=BODY) -> Paragraph:
    """Render a paragraph that may contain inline <b>, <i>, <sub>, <super> tags.

    We don't escape `<` and `>` because that would break our inline tags.
    Inputs are all hand-authored in this script, not user content, so XSS
    isn't a concern. We do escape bare `&` (turning it into `&amp;`) because
    reportlab will reject unbalanced ampersands, but we leave entity
    references like &mdash; alone.
    """
    # Replace bare & with &amp;, but skip those already part of an entity
    import re
    safe = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|mdash|ndash|hellip|nbsp);)", "&amp;", text)
    return Paragraph(safe, style)


# ---------------------------------------------------------------------------
# Hypokalemia
# ---------------------------------------------------------------------------


def page_hypokalemia() -> ReviewPage:
    from app.calculators.hypokalemia import (
        HYPOKALEMIA_SCALE,
        HYPOKALEMIA_SOURCES,
        KCL_RATE_CEILING_MEQ_PER_KG_HR,
        PERIPHERAL_CONCENTRATION_CEILING_MEQ_PER_L,
        SUBCUTANEOUS_CONCENTRATION_CEILING_MEQ_PER_L,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> What KCl supplementation and maximum infusion rate for IV potassium replacement, given a measured serum K?", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb)", BODY))
    body.append(_para("• Serum K (mEq/L)", BODY))
    body.append(_para("• Bag size (250 mL or 1 L)", BODY))

    body.append(_para("Encoded sliding scale (DiBartola Table 5-2):", SECTION_HEADER))
    rows = [["Serum K (mEq/L)", "Add to 1 L bag", "Add to 250 mL bag", "Max rate (mL/kg/hr)"]]
    for r in HYPOKALEMIA_SCALE:
        rows.append([r.label, f"{r.kcl_per_liter} mEq", f"{r.kcl_per_250ml} mEq", str(r.max_rate_ml_per_kg_per_hr)])
    body.append(_wrap_table(rows, [1.3 * inch, 1.2 * inch, 1.4 * inch, 1.4 * inch]))

    body.append(_para("Encoded safety ceilings:", SECTION_HEADER))
    body.append(_para(f"• Maximum KCl infusion rate: <b>{KCL_RATE_CEILING_MEQ_PER_KG_HR} mEq/kg/hr</b> (above this, cardiac toxicity risk)", BODY))
    body.append(_para(f"• Peripheral vein concentration ceiling: <b>{PERIPHERAL_CONCENTRATION_CEILING_MEQ_PER_L} mEq/L</b> (vein irritation/sclerosis above)", BODY))
    body.append(_para(f"• Subcutaneous route ceiling: <b>{SUBCUTANEOUS_CONCENTRATION_CEILING_MEQ_PER_L} mEq/L</b>", BODY))
    body.append(_para("• 80 mEq/L row exceeds 60 mEq/L peripheral ceiling → calculator warns to use central line", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in HYPOKALEMIA_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="hypokalemia",
        title="Hypokalemia / KCl supplementation",
        subtitle="Electrolyte CRI · DiBartola Table 5-2",
        body=body,
        priority=4,
    )


# ---------------------------------------------------------------------------
# Hypomagnesemia
# ---------------------------------------------------------------------------


def page_hypomagnesemia() -> ReviewPage:
    from app.calculators.hypomagnesemia import (
        HYPOMAGNESEMIA_TIERS,
        HYPOMAGNESEMIA_SOURCES,
        MGSO4_STOCK_25_PCT_MEQ_PER_ML,
        MGSO4_STOCK_MEQ_PER_ML_DEFAULT,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> What MgSO4 CRI rate for hypomagnesemia, given a measured serum Mg?", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Serum Mg (mg/dL)", BODY))
    body.append(_para("• Stock concentration (50% or 25% MgSO4)", BODY))

    body.append(_para("Encoded sliding scale (Hoehne / Silverstein Box 73.1):", SECTION_HEADER))
    rows = [["Serum Mg (mg/dL)", "Severity", "Target rate"]]
    for tier in HYPOMAGNESEMIA_TIERS:
        rate = "—" if tier.rate_meq_per_kg_per_day is None else f"{tier.rate_meq_per_kg_per_day} mEq/kg/day"
        rows.append([tier.label, tier.severity, rate])
    body.append(_wrap_table(rows, [1.6 * inch, 1.4 * inch, 1.8 * inch]))

    body.append(_para("Encoded stock concentrations:", SECTION_HEADER))
    body.append(_para(f"• 50% MgSO4: <b>{MGSO4_STOCK_MEQ_PER_ML_DEFAULT} mEq/mL</b> (default)", BODY))
    body.append(_para(f"• 25% MgSO4: <b>{MGSO4_STOCK_25_PCT_MEQ_PER_ML} mEq/mL</b>", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in HYPOMAGNESEMIA_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="hypomagnesemia",
        title="Hypomagnesemia / MgSO4 CRI",
        subtitle="Electrolyte CRI · Hoehne / Silverstein Box 73.1",
        body=body,
        priority=4,
    )


# ---------------------------------------------------------------------------
# Hypophosphatemia
# ---------------------------------------------------------------------------


def page_hypophosphatemia() -> ReviewPage:
    from app.calculators.hypophosphatemia import (
        HYPOPHOSPHATEMIA_TIERS,
        HYPOPHOSPHATEMIA_SOURCES,
        KPHOS_P_MMOL_PER_ML,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> What KPhos CRI rate for hypophosphatemia, given a measured serum P?", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Serum P (mg/dL)", BODY))

    body.append(_para("Encoded sliding scale:", SECTION_HEADER))
    rows = [["Serum P (mg/dL)", "Severity", "Target rate"]]
    for tier in HYPOPHOSPHATEMIA_TIERS:
        rate = "—" if tier.rate_mmol_per_kg_per_hr is None else f"{tier.rate_mmol_per_kg_per_hr} mmol/kg/hr"
        rows.append([tier.label, tier.severity, rate])
    body.append(_wrap_table(rows, [1.6 * inch, 1.4 * inch, 1.8 * inch]))

    body.append(_para("Encoded stock concentration:", SECTION_HEADER))
    body.append(_para(f"• KPhos: <b>{KPHOS_P_MMOL_PER_ML} mmol P/mL</b>", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in HYPOPHOSPHATEMIA_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="hypophosphatemia",
        title="Hypophosphatemia / KPhos CRI",
        subtitle="Electrolyte CRI",
        body=body,
        priority=4,
    )


# ---------------------------------------------------------------------------
# Hypernatremia
# ---------------------------------------------------------------------------


def page_hypernatremia() -> ReviewPage:
    from app.calculators.hypernatremia import HYPERNATREMIA_SOURCES, MECHANISM_PROFILES

    body = []
    body.append(_para("<b>Question this calculator answers:</b> What free-water deficit and replacement rate for a hypernatremic patient?", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb)", BODY))
    body.append(_para("• Current serum Na (mEq/L)", BODY))
    body.append(_para("• Reference (target) serum Na (mEq/L)", BODY))
    body.append(_para("• Mechanism (pure water loss / hypotonic loss / solute gain)", BODY))
    body.append(_para("• Replacement window (hours)", BODY))
    body.append(_para("• Maintenance fluid rate (mL/hr, can be 0)", BODY))

    body.append(_para("Encoded formula (DiBartola):", SECTION_HEADER))
    body.append(_para("Free water deficit (L) = <b>0.6 × BW(kg) × (current Na / reference Na − 1)</b>", BODY))
    body.append(_para("Total fluid rate = (deficit / replacement_hours) + maintenance + ongoing losses", BODY))
    body.append(_para("Predicted correction rate is reported so the clinician can verify the plan stays under the safety ceiling (≤0.5 mEq/L/hr or ≤12 mEq/L/24hr in chronic cases).", BODY))

    body.append(_para("Encoded mechanism profiles (each with examples + recommended fluids + caveats):", SECTION_HEADER))
    for mech, profile in MECHANISM_PROFILES.items():
        body.append(_para(f"<b>{profile.name}</b>: {profile.description}", BODY))
        body.append(_para(f"  Strategy: {profile.initial_fluid_strategy}", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in HYPERNATREMIA_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="hypernatremia",
        title="Hypernatremia / free-water deficit",
        subtitle="Fluid therapy · DiBartola Ch. 3",
        body=body,
        priority=3,
    )


# ---------------------------------------------------------------------------
# Calcium gluconate (hyperK bridge)
# ---------------------------------------------------------------------------


def page_ca_gluconate() -> ReviewPage:
    from app.calculators.ca_gluconate import (
        DOSE_MAX_ML_PER_KG,
        DOSE_MIN_ML_PER_KG,
        CA_GLUCONATE_ELEMENTAL_CA_MG_PER_ML,
        CA_GLUCONATE_MEQ_PER_ML,
        CA_GLUCONATE_MG_PER_ML,
        CA_GLUCONATE_SOURCES,
        DURATION_MAX_MIN,
        DURATION_MIN_MIN,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> What dose and infusion rate of 10% calcium gluconate to stabilize myocardium in a hyperkalemic patient?", BODY))
    body.append(_para("<b>HIGH-ALERT MEDICATION.</b> ECG monitoring required during infusion.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Dose (mL/kg of 10% calcium gluconate)", BODY))
    body.append(_para("• Duration (minutes)", BODY))

    body.append(_para("Encoded dose range (Cooper / Silverstein Ch. 122):", SECTION_HEADER))
    body.append(_para(f"• Minimum: <b>{DOSE_MIN_ML_PER_KG} mL/kg</b>", BODY))
    body.append(_para(f"• Maximum: <b>{DOSE_MAX_ML_PER_KG} mL/kg</b>", BODY))
    body.append(_para(f"• Infusion duration: <b>{DURATION_MIN_MIN}–{DURATION_MAX_MIN} minutes</b> with continuous ECG", BODY))

    body.append(_para("Encoded stock concentrations (10% calcium gluconate):", SECTION_HEADER))
    body.append(_para(f"• Salt: <b>{CA_GLUCONATE_MG_PER_ML} mg/mL</b>", BODY))
    body.append(_para(f"• Elemental Ca: <b>{CA_GLUCONATE_ELEMENTAL_CA_MG_PER_ML} mg/mL</b>", BODY))
    body.append(_para(f"• Ca<super>2+</super> ion: <b>{CA_GLUCONATE_MEQ_PER_ML} mEq/mL</b>", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• Calcium chloride (10% CaCl<sub>2</sub>) is NOT interchangeable with calcium gluconate (3× the elemental Ca per mL)", WARNING_BODY))
    body.append(_para("• Continuous ECG required — slow or stop infusion if bradycardia / ST change / shortened QT", WARNING_BODY))
    body.append(_para("• Calcium is a bridge (membrane stabilizer) only — does not lower K. Definitive K-lowering therapy (insulin/dextrose, fluids) MUST follow.", WARNING_BODY))
    body.append(_para("• Never co-administer with bicarbonate or KPhos in same line (precipitates)", WARNING_BODY))
    body.append(_para("• Never IM or SC", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in CA_GLUCONATE_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="ca_gluconate",
        title="Calcium gluconate · hyperK myocardial stabilization",
        subtitle="High-alert · Cooper / Silverstein Ch. 122",
        body=body,
        priority=1,
    )


# ---------------------------------------------------------------------------
# Insulin + dextrose (hyperK bridge)
# ---------------------------------------------------------------------------


def page_insulin_dextrose() -> ReviewPage:
    from app.calculators.insulin_dextrose import (
        D50_STOCK_G_PER_ML,
        DEXTROSE_RATIO_DEFAULT,
        DEXTROSE_RATIO_MAX,
        DEXTROSE_RATIO_MIN,
        INSULIN_DEXTROSE_SOURCES,
        INSULIN_DOSE_DEFAULT_U_PER_KG,
        INSULIN_DOSE_MAX_U_PER_KG,
        INSULIN_DOSE_MIN_U_PER_KG,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> What dose of regular insulin + dextrose for K-lowering in a hyperkalemic patient?", BODY))
    body.append(_para("<b>HIGH-ALERT MEDICATION.</b> Use REGULAR insulin only.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Insulin dose (U/kg)", BODY))
    body.append(_para("• Dextrose ratio (g per unit insulin)", BODY))

    body.append(_para("Encoded dose range:", SECTION_HEADER))
    body.append(_para(f"• Insulin minimum: <b>{INSULIN_DOSE_MIN_U_PER_KG} U/kg</b> (default, safer)", BODY))
    body.append(_para(f"• Insulin maximum: <b>{INSULIN_DOSE_MAX_U_PER_KG} U/kg</b>", BODY))
    body.append(_para(f"• Insulin default: <b>{INSULIN_DOSE_DEFAULT_U_PER_KG} U/kg</b>", BODY))
    body.append(_para(f"• Dextrose ratio: <b>{DEXTROSE_RATIO_MIN}–{DEXTROSE_RATIO_MAX} g per unit insulin</b> (default {DEXTROSE_RATIO_DEFAULT} g/U)", BODY))

    body.append(_para("Encoded stock and prep:", SECTION_HEADER))
    body.append(_para(f"• Regular insulin (U-100): 100 U/mL", BODY))
    body.append(_para(f"• D50 stock: <b>{D50_STOCK_G_PER_ML} g/mL</b>", BODY))
    body.append(_para("• D25 prep: dilute D50 1:1 with saline (calculator computes the saline volume)", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• Use REGULAR crystalline insulin only (Humulin R, Novolin R) — never NPH, lente, glargine, lispro, aspart", WARNING_BODY))
    body.append(_para("• D50 causes phlebitis and possible endothelial injury when given undiluted; standard practice is to dilute to D25", WARNING_BODY))
    body.append(_para("• Effect onset 15–30 min, duration 4–6 hr; recheck K and BG", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in INSULIN_DEXTROSE_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="insulin_dextrose",
        title="Insulin + dextrose · hyperK K-lowering",
        subtitle="High-alert · Cooper / Silverstein Ch. 122",
        body=body,
        priority=1,
    )


# ---------------------------------------------------------------------------
# Insulin CRI · DKA
# ---------------------------------------------------------------------------


def page_insulin_cri_dka() -> ReviewPage:
    from app.calculators.insulin_cri_dka import (
        INSULIN_CRI_BAG_VOLUME_ML,
        INSULIN_CRI_CAT_CONSERVATIVE_U_PER_KG,
        INSULIN_CRI_DEFAULT_LOADING_U_PER_KG,
        INSULIN_CRI_PRIME_DISCARD_ML,
        INSULIN_CRI_TIERS,
        INSULIN_CRI_DKA_SOURCES,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Insulin CRI bag prep and pump rate for DKA management. The clinician selects the BG-tier rate.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Current blood glucose (mg/dL)", BODY))
    body.append(_para("• Cat dose option: standard 2.2 U/kg or conservative 1.1 U/kg", BODY))

    body.append(_para("Encoded bag prep:", SECTION_HEADER))
    body.append(_para(f"• Bag volume: <b>{int(INSULIN_CRI_BAG_VOLUME_ML)} mL of 0.9% NaCl</b>", BODY))
    body.append(_para(f"• Loading dose, default (dog/cat): <b>{INSULIN_CRI_DEFAULT_LOADING_U_PER_KG} U/kg</b>", BODY))
    body.append(_para(f"• Loading dose, cat conservative: <b>{INSULIN_CRI_CAT_CONSERVATIVE_U_PER_KG} U/kg</b>", BODY))
    body.append(_para(f"• Prime + discard: <b>{int(INSULIN_CRI_PRIME_DISCARD_ML)} mL</b> (saturates plastic IV-tubing binding sites)", BODY))

    body.append(_para("Encoded sliding scale (Table 73.1):", SECTION_HEADER))
    rows = [["Blood glucose", "Fluid composition", "Pump rate"]]
    for tier in INSULIN_CRI_TIERS:
        rate = "STOP insulin" if tier.pump_rate_ml_per_hr is None else f"{tier.pump_rate_ml_per_hr:g} mL/hr"
        rows.append([tier.label, tier.fluid_composition, rate])
    body.append(_wrap_table(rows, [1.5 * inch, 2.4 * inch, 1.0 * inch]))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• REGULAR crystalline insulin only — not lispro, aspart, glargine, NPH, lente", WARNING_BODY))
    body.append(_para("• Prime + discard 50 mL or the delivered dose will be lower than calculated", WARNING_BODY))
    body.append(_para("• Goal: lower BG by ≤50–75 mg/dL/hr; faster correction risks cerebral edema", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in INSULIN_CRI_DKA_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="insulin_cri_dka",
        title="Insulin CRI · DKA",
        subtitle="High-stakes sliding scale · Hoehne / Silverstein Ch. 73, Table 73.1",
        body=body,
        priority=2,
    )


# ---------------------------------------------------------------------------
# Insulin IM intermittent · DKA
# ---------------------------------------------------------------------------


def page_insulin_im_dka() -> ReviewPage:
    from app.calculators.insulin_im_dka import INSULIN_IM_TIERS, INSULIN_IM_DKA_SOURCES

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Hourly IM regular-insulin dose for DKA when CRI is not available.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb)", BODY))
    body.append(_para("• Mode: LOADING (first dose) or SUBSEQUENT (hourly)", BODY))
    body.append(_para("• For SUBSEQUENT: previous BG and current BG (calculator computes hourly drop)", BODY))

    body.append(_para("Encoded protocol (Macintire 1993 / Silverstein Ch. 73):", SECTION_HEADER))
    body.append(_para("• Loading: <b>0.2 U/kg IM regular insulin</b>", BODY))
    body.append(_para("• Subsequent doses driven by hourly BG drop:", BODY))

    rows = [["BG drop in last hour", "Subsequent dose"]]
    for tier in INSULIN_IM_TIERS:
        rows.append([tier.label, f"{tier.dose_u_per_kg} U/kg IM"])
    body.append(_wrap_table(rows, [3.0 * inch, 1.8 * inch]))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• REGULAR crystalline insulin only", WARNING_BODY))
    body.append(_para("• If BG < 100 mg/dL: stop insulin, give dextrose, recheck before resuming", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in INSULIN_IM_DKA_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="insulin_im_dka",
        title="Insulin IM intermittent · DKA",
        subtitle="High-stakes alternative · Macintire 1993",
        body=body,
        priority=2,
    )


# ---------------------------------------------------------------------------
# Fluid therapy
# ---------------------------------------------------------------------------


def page_fluid_therapy() -> ReviewPage:
    from app.calculators.fluid_therapy import (
        DEHYDRATION_BANDS,
        FLUID_THERAPY_SOURCES,
        SHOCK_BOLUS_MAX_MLPK_DOG,
        SHOCK_BOLUS_MAX_MLPK_CAT,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> What fluid plan (shock bolus + rehydration + maintenance + ongoing losses) for a patient with a given dehydration band?", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• In shock? (yes/no)", BODY))
    body.append(_para("• Dehydration band", BODY))
    body.append(_para("• Rehydration window (4–24 hr)", BODY))
    body.append(_para("• Maintenance rate (2–4 mL/kg/hr; default 3)", BODY))
    body.append(_para("• Ongoing losses (mL/hr)", BODY))

    body.append(_para("Encoded dehydration bands:", SECTION_HEADER))
    rows = [["Band", "Estimated %"]]
    for band in DEHYDRATION_BANDS:
        rows.append([band.label, f"{band.percent}%"])
    body.append(_wrap_table(rows, [3.0 * inch, 1.5 * inch]))

    body.append(_para("Encoded math:", SECTION_HEADER))
    body.append(_para("• Deficit (mL) = weight (kg) × % × 10", BODY))
    body.append(_para("• Phase 1 rate (rehydrating) = (deficit / replacement_hours) + maintenance + ongoing", BODY))
    body.append(_para("• Phase 2 rate (post-rehydration) = maintenance + ongoing", BODY))

    body.append(_para("Encoded shock bolus ceilings:", SECTION_HEADER))
    body.append(_para(f"• Dog max: <b>{SHOCK_BOLUS_MAX_MLPK_DOG} mL/kg</b> total (titrate in increments)", BODY))
    body.append(_para(f"• Cat max: <b>{SHOCK_BOLUS_MAX_MLPK_CAT} mL/kg</b> total", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in FLUID_THERAPY_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="fluid_therapy",
        title="Fluid therapy plan",
        subtitle="Foundational · Hoehne / Silverstein Box 73.1, DiBartola dehydration bands",
        body=body,
        priority=3,
    )


# ---------------------------------------------------------------------------
# SINGLE_DRUG_CRI engine drugs
# ---------------------------------------------------------------------------


def _engine_drug_page(slug: str, priority: int) -> ReviewPage:
    from app.calculators.drugs import get_drug
    from app.calculators.engine import Species

    drug = get_drug(slug)
    body = []

    body.append(_para(f"<b>Question this calculator answers:</b> Pump rate (mL/hr) for {drug.display_name} given weight, dose, and bag concentration.", BODY))
    body.append(_para(f"<b>Stock:</b> {drug.stock_concentration_display}", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para(f"• Dose ({drug.dose_unit.value})", BODY))
    body.append(_para("• Bag concentration (µg/mL) — concentration presets provided", BODY))

    body.append(_para("Encoded dose ranges:", SECTION_HEADER))
    rows = [["Species", "Range", f"Caution above ({drug.dose_unit.value})"]]
    for species in [Species.DOG, Species.CAT]:
        if species not in drug.dose_ranges:
            continue
        rng = drug.dose_ranges[species]
        caution = f"{rng.caution_threshold:g}" if rng.caution_threshold else "—"
        rows.append([species.value.title(), f"{rng.min:g}–{rng.max:g}", caution])
    body.append(_wrap_table(rows, [1.0 * inch, 1.4 * inch, 2.2 * inch]))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    seen_warnings = set()
    for species in [Species.DOG, Species.CAT]:
        if species not in drug.dose_ranges:
            continue
        rng = drug.dose_ranges[species]
        if rng.persistent_warning and rng.persistent_warning not in seen_warnings:
            seen_warnings.add(rng.persistent_warning)
            body.append(_para(f"<b>{species.value.title()}:</b> {rng.persistent_warning}", WARNING_BODY))

    if drug.concentration_presets:
        body.append(_para("Encoded concentration presets:", SECTION_HEADER))
        for preset in drug.concentration_presets[:5]:  # cap for layout
            body.append(_para(f"• <b>{preset.concentration_ug_per_ml:g} µg/mL</b> — {preset.recipe}", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in drug.sources:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug=slug,
        title=f"{drug.display_name}",
        subtitle=f"{drug.category} · engine-driven CRI",
        body=body,
        priority=priority,
    )


def page_norepinephrine() -> ReviewPage:
    return _engine_drug_page("norepinephrine", priority=2)


def page_epinephrine() -> ReviewPage:
    return _engine_drug_page("epinephrine", priority=2)


def page_dobutamine() -> ReviewPage:
    return _engine_drug_page("dobutamine", priority=2)


def page_fentanyl() -> ReviewPage:
    return _engine_drug_page("fentanyl", priority=3)


def page_dopamine_standard() -> ReviewPage:
    # Engine-driven dopamine CRI for any bag size, alternative to the
    # custom /dopamine page (Plumb's 6×kg method, 100 mL bag only).
    return _engine_drug_page("dopamine-cri", priority=2)


# ---------------------------------------------------------------------------
# Dopamine prep
# ---------------------------------------------------------------------------


def page_dopamine_prep() -> ReviewPage:
    from app.calculators.dopamine_prep import (
        DOPAMINE_BAG_VOLUME_ML,
        DOPAMINE_MAX_FINAL_CONCENTRATION_UG_PER_ML,
        DOPAMINE_PREP_SOURCES,
        DOPAMINE_STOCK_MG_PER_ML,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> What bag prep (mg dopamine to add to a 100 mL bag) and pump rate using Plumb's 6×kg method?", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Target dose (µg/kg/min)", BODY))

    body.append(_para("Encoded recipe (Plumb's 6×BW method):", SECTION_HEADER))
    body.append(_para(f"• Add (6 × BW kg) <b>mg of dopamine</b> to <b>{int(DOPAMINE_BAG_VOLUME_ML)} mL bag</b>", BODY))
    body.append(_para(f"• Stock: <b>{int(DOPAMINE_STOCK_MG_PER_ML)} mg/mL</b>", BODY))
    body.append(_para("• By construction: pump rate (mL/hr) = target dose (µg/kg/min)", BODY))

    body.append(_para("Encoded ceilings and dose ranges (Plumb's):", SECTION_HEADER))
    body.append(_para(f"• Final concentration limit: <b>{int(DOPAMINE_MAX_FINAL_CONCENTRATION_UG_PER_ML)} µg/mL</b> (≈ 53 kg patient)", BODY))
    body.append(_para("• Dog dose range: <b>3–20 µg/kg/min</b> IV CRI (severe shock: start 2.5–5, titrate +2.5–5 every ~30 min)", BODY))
    body.append(_para("• Cat dose range: <b>5–20 µg/kg/min</b> IV CRI", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• Cats with HCM: PVC risk above 10 µg/kg/min (Wiese HCM study); ECG monitoring", WARNING_BODY))
    body.append(_para("• Above 20 µg/kg/min: switch to norepinephrine for vasopressor effect", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in DOPAMINE_PREP_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="dopamine_prep",
        title="Dopamine prep · 6×BW method",
        subtitle="Vasoactive · Plumb's",
        body=body,
        priority=2,
    )


# ---------------------------------------------------------------------------
# Lidocaine
# ---------------------------------------------------------------------------


def page_lidocaine() -> ReviewPage:
    from app.calculators.lidocaine import (
        LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR,
        LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR,
        LIDOCAINE_SOURCES,
        LIDOCAINE_STOCK_MG_PER_ML,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Lidocaine CRI rate and loading bolus for ventricular tachyarrhythmias (dogs only).", BODY))
    body.append(_para("<b>DOG-ONLY.</b> IV systemic lidocaine is avoided in cats due to neurotoxicity risk.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb)", BODY))
    body.append(_para("• Dose (mg/kg/hr or µg/kg/min — calculator converts)", BODY))

    body.append(_para("Encoded dose range and loading (Plumb's):", SECTION_HEADER))
    body.append(_para(f"• CRI: <b>{LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR}–{LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR} mg/kg/hr</b> (= {int(LIDOCAINE_DOSE_MIN_MG_PER_KG_PER_HR * 1000 / 60)}–{int(LIDOCAINE_DOSE_MAX_MG_PER_KG_PER_HR * 1000 / 60)} µg/kg/min)", BODY))
    body.append(_para("• Loading: <b>1–2 mg/kg IV slowly</b>", BODY))
    body.append(_para(f"• Stock: <b>2% (= {int(LIDOCAINE_STOCK_MG_PER_ML)} mg/mL)</b>, WITHOUT epinephrine", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• DOG ONLY — cats are highly sensitive to lidocaine neurotoxicity", WARNING_BODY))
    body.append(_para("• Use lidocaine WITHOUT epinephrine for IV use", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in LIDOCAINE_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="lidocaine",
        title="Lidocaine CRI",
        subtitle="Anti-arrhythmic · DOG-ONLY · Plumb's",
        body=body,
        priority=5,
    )


# ---------------------------------------------------------------------------
# Ketamine
# ---------------------------------------------------------------------------


def page_ketamine() -> ReviewPage:
    from app.calculators.ketamine import (
        KETAMINE_DOSE_RANGES,
        KETAMINE_SOURCES,
        KETAMINE_STOCK_MG_PER_ML,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Ketamine CRI rate for surgical or postsurgical analgesia (dog or cat).", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Indication: SURGICAL or POSTSURGICAL", BODY))
    body.append(_para("• Dose (µg/kg/min or mg/kg/hr)", BODY))

    body.append(_para("Encoded indication ranges:", SECTION_HEADER))
    rows = [["Indication", "Range (µg/kg/min)", "Default"]]
    for ind, rng in KETAMINE_DOSE_RANGES.items():
        rows.append([ind.value.title(), f"{rng.min_ug_per_kg_per_min:g}–{rng.max_ug_per_kg_per_min:g}", f"{rng.default_ug_per_kg_per_min:g}"])
    body.append(_wrap_table(rows, [1.4 * inch, 1.8 * inch, 1.2 * inch]))

    body.append(_para(f"• Stock: <b>{int(KETAMINE_STOCK_MG_PER_ML)} mg/mL</b> (standard veterinary vial)", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• Cats with HCM: avoid (catecholamine release worsens dynamic LVOT obstruction)", WARNING_BODY))
    body.append(_para("• Seizure risk reported in ~20% of cats", WARNING_BODY))
    body.append(_para("• Hyperthermia risk; renal excretion (caution in renal disease)", WARNING_BODY))
    body.append(_para("• DEA Schedule III", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in KETAMINE_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="ketamine",
        title="Ketamine CRI",
        subtitle="Analgesia · Plumb's",
        body=body,
        priority=6,
    )


# ---------------------------------------------------------------------------
# Propofol
# ---------------------------------------------------------------------------


def page_propofol() -> ReviewPage:
    from app.calculators.propofol import PROPOFOL_DOSE_RANGES, PROPOFOL_SOURCES

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Propofol CRI rate for TIVA maintenance or status epilepticus.", BODY))
    body.append(_para("<b>CAT TIVA MAINTENANCE IS BLOCKED.</b> Heinz body anemia risk with prolonged exposure; calculator refuses to compute.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Indication: TIVA_MAINTENANCE or STATUS_EPILEPTICUS", BODY))
    body.append(_para("• Dose (mg/kg/min)", BODY))

    body.append(_para("Encoded ranges (mg/kg/min):", SECTION_HEADER))
    rows = [["Species", "Indication", "Range"]]
    for (ind, sp), rng in PROPOFOL_DOSE_RANGES.items():
        rows.append([sp.value.title(), ind.value.replace("_", " ").title(), f"{rng.min_mg_per_kg_per_min:g}–{rng.max_mg_per_kg_per_min:g}"])
    body.append(_wrap_table(rows, [1.0 * inch, 1.8 * inch, 1.6 * inch]))

    body.append(_para("• Stock: 10 mg/mL", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• Cat TIVA maintenance is NOT supported — Heinz body anemia, prolonged recovery; use intermittent IV boluses or alfaxalone CRI / inhalant for cat maintenance", WARNING_BODY))
    body.append(_para("• Propofol provides NO analgesia — multimodal analgesic coverage required", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in PROPOFOL_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="propofol",
        title="Propofol CRI",
        subtitle="Anesthesia · Plumb's",
        body=body,
        priority=6,
    )


# ---------------------------------------------------------------------------
# MLK
# ---------------------------------------------------------------------------


def page_mlk() -> ReviewPage:
    from app.calculators.mlk import (
        MLK_BAG_VOLUME_ML,
        MLK_KETAMINE_MG,
        MLK_LIDOCAINE_MG,
        MLK_MORPHINE_MG,
        MLK_RATE_ML_PER_KG_PER_HR,
        MLK_SOURCES,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> MLK (Morphine-Lidocaine-Ketamine) infusion bag prep and pump rate (dogs only).", BODY))
    body.append(_para("<b>DOG-ONLY</b> per Silverstein protocol (lidocaine).", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb)", BODY))

    body.append(_para("Encoded recipe (Silverstein Table 134.1):", SECTION_HEADER))
    body.append(_para(f"• <b>{MLK_MORPHINE_MG:g} mg morphine</b> + <b>{MLK_LIDOCAINE_MG:g} mg lidocaine 2%</b> + <b>{MLK_KETAMINE_MG:g} mg ketamine</b>", BODY))
    body.append(_para(f"• in <b>{int(MLK_BAG_VOLUME_ML)} mL LRS</b>", BODY))
    body.append(_para(f"• Run at <b>{int(MLK_RATE_ML_PER_KG_PER_HR)} mL/kg/hr</b>", BODY))

    body.append(_para("Encoded delivered doses (computed):", SECTION_HEADER))
    body.append(_para("• Morphine: <b>3.3 µg/kg/min</b>", BODY))
    body.append(_para("• Lidocaine: <b>50 µg/kg/min</b>", BODY))
    body.append(_para("• Ketamine: <b>10 µg/kg/min</b>", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in MLK_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="mlk",
        title="MLK infusion · multimodal analgesia",
        subtitle="DOG-ONLY · Silverstein Table 134.1",
        body=body,
        priority=6,
    )


# ---------------------------------------------------------------------------
# Methadone
# ---------------------------------------------------------------------------


def page_methadone() -> ReviewPage:
    from app.calculators.methadone import METHADONE_SOURCES, METHADONE_STOCK_MG_PER_ML

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Methadone bolus / premedication / CRI dose for dog or cat.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Stock concentration (default 10 mg/mL)", BODY))

    body.append(_para("Encoded dose ranges (Plumb's):", SECTION_HEADER))
    rows = [
        ["Indication / Species", "Range", "Frequency"],
        ["Dog bolus", "0.1–0.5 mg/kg IV/IM/SC", "q4–8h"],
        ["Cat bolus", "0.1–0.6 mg/kg IV/IM/SC", "q4–6h"],
        ["Dog premedication", "0.2–0.3 mg/kg", "single"],
        ["Cat premedication", "0.1–0.6 mg/kg", "single"],
        ["CRI loading (both)", "0.1–0.2 mg/kg IV", "single"],
        ["CRI maintenance (both)", "0.12 mg/kg/hr IV", "continuous"],
    ]
    body.append(_wrap_table(rows, [1.8 * inch, 1.8 * inch, 1.0 * inch]))

    body.append(_para(f"• Stock: <b>{int(METHADONE_STOCK_MG_PER_ML)} mg/mL</b>", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• DEA Schedule II", WARNING_BODY))
    body.append(_para("• CRI bag prep (Plumb's): 60 mg methadone (6 mL of 10 mg/mL) into 500 mL IV fluid", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in METHADONE_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="methadone",
        title="Methadone · bolus / premed / CRI",
        subtitle="Opioid analgesia · Plumb's",
        body=body,
        priority=6,
    )


# ---------------------------------------------------------------------------
# Hydromorphone
# ---------------------------------------------------------------------------


def page_hydromorphone() -> ReviewPage:
    from app.calculators.hydromorphone_cri import (
        HYDROMORPHONE_SOURCES,
        HYDROMORPHONE_STOCK_MG_PER_ML,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Hydromorphone bolus and CRI dose.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• CRI rate (mg/kg/hr)", BODY))

    body.append(_para("Encoded dose ranges (Plumb's):", SECTION_HEADER))
    rows = [
        ["Indication / Species", "Range", "Frequency"],
        ["Dog bolus", "0.05–0.20 mg/kg", "q2–4h"],
        ["Cat bolus", "0.05–0.10 mg/kg", "q2–6h"],
        ["Dog CRI", "0.03 mg/kg/hr", "continuous"],
        ["Cat CRI", "0.01–0.05 mg/kg/hr", "continuous"],
    ]
    body.append(_wrap_table(rows, [1.8 * inch, 1.8 * inch, 1.0 * inch]))

    body.append(_para(f"• Stock: <b>{HYDROMORPHONE_STOCK_MG_PER_ML} mg/mL</b>", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• DEA Schedule II", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in HYDROMORPHONE_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="hydromorphone",
        title="Hydromorphone · bolus / CRI",
        subtitle="Opioid analgesia · Plumb's",
        body=body,
        priority=6,
    )


# ---------------------------------------------------------------------------
# Alfaxalone
# ---------------------------------------------------------------------------


def page_alfaxalone() -> ReviewPage:
    from app.calculators.alfaxalone import ALFAXALONE_SOURCES, ALFAXALONE_STOCK_MG_PER_ML

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Alfaxalone induction and CRI doses, with and without premedication.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Premedicated? (yes/no)", BODY))
    body.append(_para("• Mode: INDUCTION or MAINTENANCE", BODY))

    body.append(_para("Encoded dose ranges (Plumb's):", SECTION_HEADER))
    rows = [
        ["Species + premed", "Induction (mg/kg)", "CRI (mg/kg/hr)"],
        ["Dog, unpremedicated", "1.5–4.5", "8–9"],
        ["Dog, premedicated", "1.1–1.7", "6–7"],
        ["Cat, unpremedicated", "2.2–9.7", "10–11"],
        ["Cat, premedicated", "2.3–3.6", "7–8"],
    ]
    body.append(_wrap_table(rows, [2.0 * inch, 1.8 * inch, 1.6 * inch]))

    body.append(_para(f"• Stock: <b>{int(ALFAXALONE_STOCK_MG_PER_ML)} mg/mL</b> (Alfaxan® Multidose)", BODY))

    body.append(_para("Encoded persistent warnings:", SECTION_HEADER))
    body.append(_para("• Provides NO ANALGESIA — multimodal analgesic coverage required", WARNING_BODY))
    body.append(_para("• DEA Schedule IV", WARNING_BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in ALFAXALONE_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="alfaxalone",
        title="Alfaxalone · induction / CRI",
        subtitle="Anesthesia · Plumb's",
        body=body,
        priority=6,
    )


# ---------------------------------------------------------------------------
# Kitty Magic
# ---------------------------------------------------------------------------


def page_kitty_magic() -> ReviewPage:
    from app.calculators.kitty_magic import KITTY_MAGIC_SOURCES

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Kitty Magic (DKT — dexmedetomidine + ketamine + opioid) drawn-up volumes for cat sedation/anesthesia.", BODY))
    body.append(_para("<b>CAT-ONLY.</b> Lookup table covers 2–8 kg cats.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg)", BODY))
    body.append(_para("• Opioid: BUTORPHANOL or BUPRENORPHINE", BODY))
    body.append(_para("• Level: MILD, MODERATE, or PROFOUND", BODY))

    body.append(_para("Encoded volume table (mL of EACH drug, drawn at equal volumes):", SECTION_HEADER))
    rows = [
        ["Weight band", "Mild", "Moderate", "Profound"],
        ["2–3 kg", "0.025", "0.05", "0.10–0.15"],
        ["4–6 kg", "0.10", "0.20", "0.30–0.35"],
        ["7–8 kg", "0.30", "0.40", "0.50–0.55"],
    ]
    body.append(_wrap_table(rows, [1.4 * inch, 1.0 * inch, 1.0 * inch, 1.4 * inch]))

    body.append(_para("Encoded protocol notes:", SECTION_HEADER))
    body.append(_para("• Equal volumes IM of all three drugs", BODY))
    body.append(_para("• Atipamezole reversal: equal volume to dexmedetomidine", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in KITTY_MAGIC_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="kitty_magic",
        title="Kitty Magic (DKT) · cat sedation",
        subtitle="CAT-ONLY · Plumb's lookup table",
        body=body,
        priority=6,
    )


# ---------------------------------------------------------------------------
# Cornell Onco KL
# ---------------------------------------------------------------------------


def page_cornell_onco_kl() -> ReviewPage:
    from app.calculators.cornell_onco_kl import (
        CORNELL_ONCO_KL_SOURCES,
        EFFICACY_KETA_MIN_MG_PER_KG_PER_HR,
        EFFICACY_KETA_TOTAL_DOSE_MIN_MG_PER_KG,
        EFFICACY_LIDO_MIN_MG_PER_KG_PER_HR,
        SMALL_PATIENT_THRESHOLD_KG,
        TARGET_KETAMINE_MG_PER_KG_PER_HR,
        TARGET_LIDOCAINE_CAT_MG_PER_KG_PER_HR,
        TARGET_LIDOCAINE_DOG_MG_PER_KG_PER_HR,
    )

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Cornell Oncology KL (ketamine + lidocaine) infusion bag prep and pump rate for chemotherapy-adjunct analgesia.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb), species (dog/cat)", BODY))
    body.append(_para("• Bag volume (mL)", BODY))
    body.append(_para("• Duration (hr)", BODY))

    body.append(_para("Encoded targets (rate at 2.5 mL/kg/hr × 4–6 hr):", SECTION_HEADER))
    body.append(_para(f"• Dog lidocaine: <b>{TARGET_LIDOCAINE_DOG_MG_PER_KG_PER_HR} mg/kg/hr</b>", BODY))
    body.append(_para(f"• Cat lidocaine: <b>{TARGET_LIDOCAINE_CAT_MG_PER_KG_PER_HR} mg/kg/hr</b>", BODY))
    body.append(_para(f"• Ketamine (both): <b>{TARGET_KETAMINE_MG_PER_KG_PER_HR} mg/kg/hr</b>", BODY))

    body.append(_para("Encoded efficacy thresholds (Iocolano 2025):", SECTION_HEADER))
    body.append(_para(f"• Lidocaine: ≥ <b>{EFFICACY_LIDO_MIN_MG_PER_KG_PER_HR} mg/kg/hr</b> (= 25 µg/kg/min)", BODY))
    body.append(_para(f"• Ketamine: ≥ <b>{EFFICACY_KETA_MIN_MG_PER_KG_PER_HR} mg/kg/hr</b> (= 2 µg/kg/min)", BODY))
    body.append(_para(f"• Ketamine total dose: ≥ <b>{EFFICACY_KETA_TOTAL_DOSE_MIN_MG_PER_KG} mg/kg</b> over infusion", BODY))

    body.append(_para("Encoded small-patient flag:", SECTION_HEADER))
    body.append(_para(f"• Patients < <b>{int(SMALL_PATIENT_THRESHOLD_KG)} kg</b> on a 250+ mL bag may not meet thresholds; calculator suggests a smaller bag", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in CORNELL_ONCO_KL_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="cornell_onco_kl",
        title="Oncology KL · Cornell protocol",
        subtitle="Chemotherapy-adjunct · Iocolano JAVMA 2025 / Looney 2012",
        body=body,
        priority=6,
    )


# ---------------------------------------------------------------------------
# CPR / RECOVER 2024
# ---------------------------------------------------------------------------


def page_cpr() -> ReviewPage:
    from app.routers.cpr import CPR_DRUGS, CPR_SOURCES

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Per-kg emergency drug volumes and defibrillation joules for CPR.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs:", SECTION_HEADER))
    body.append(_para("• Patient weight (kg or lb)", BODY))

    body.append(_para("Encoded drug list (RECOVER 2024):", SECTION_HEADER))
    rows = [["Drug", "Dose", "Concentration", "Category"]]
    for d in CPR_DRUGS:
        rows.append([d.name, d.dose_label, d.concentration, d.category])
    body.append(_wrap_table(rows, [1.4 * inch, 1.4 * inch, 1.4 * inch, 1.0 * inch]))

    body.append(_para("Encoded defibrillation:", SECTION_HEADER))
    body.append(_para("• External: 4–6 J/kg", BODY))
    body.append(_para("• Internal: 0.5–1 J/kg", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in CPR_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="cpr",
        title="CPR / RECOVER 2024 dosing chart",
        subtitle="Emergency · Fletcher 2024 RECOVER Guidelines",
        body=body,
        priority=2,
    )


# ---------------------------------------------------------------------------
# Diagnostic scoring tools
# ---------------------------------------------------------------------------


def page_iris_staging() -> ReviewPage:
    from app.routers.iris_staging import IRIS_SOURCES

    body = []
    body.append(_para("<b>Question this calculator answers:</b> IRIS CKD stage from creatinine and SDMA, with substaging by UPC and SBP.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs: species, creatinine (mg/dL), SDMA (µg/dL), UPC, SBP (mmHg).", BODY))

    body.append(_para("Encoded creatinine cutoffs (mg/dL):", SECTION_HEADER))
    rows = [
        ["Stage", "Dog", "Cat"],
        ["1", "< 1.4", "< 1.6"],
        ["2", "1.4–2.8", "1.6–2.8"],
        ["3", "2.8–5.0", "2.8–5.0"],
        ["4", "> 5.0", "> 5.0"],
    ]
    body.append(_wrap_table(rows, [1.0 * inch, 1.5 * inch, 1.5 * inch]))

    body.append(_para("Encoded SDMA cutoffs (µg/dL):", SECTION_HEADER))
    rows = [
        ["Stage", "Dog", "Cat"],
        ["1", "< 18", "< 18"],
        ["2", "18–35", "18–25"],
        ["3", "35–54", "25–45"],
        ["4", "> 54", "> 45"],
    ]
    body.append(_wrap_table(rows, [1.0 * inch, 1.5 * inch, 1.5 * inch]))

    body.append(_para("• Final stage = max(creatinine_stage, sdma_stage)", BODY))
    body.append(_para("• UPC substaging: P (proteinuric, > 0.5), BP (borderline 0.2–0.5), NP (non-proteinuric < 0.2)", BODY))
    body.append(_para("• SBP substaging: N / H1 / H2 / H3 (≥160 = severe)", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in IRIS_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="iris_staging",
        title="IRIS CKD staging",
        subtitle="Diagnostic · IRIS guidelines (2023 modification)",
        body=body,
        priority=7,
    )


def page_lddst() -> ReviewPage:
    from app.calculators.lddst import DEFAULT_8H_CUTOFF_UG_DL, LDDST_SOURCES

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Interpretation of the LDDST (low-dose dex suppression test) for canine HAC.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs: baseline cortisol, 4-hour cortisol, 8-hour cortisol, cut-off (default), units (µg/dL or nmol/L).", BODY))

    body.append(_para("Encoded cutoff:", SECTION_HEADER))
    body.append(_para(f"• 8-hour cortisol: <b>{DEFAULT_8H_CUTOFF_UG_DL} µg/dL</b> (≈ 40 nmol/L)", BODY))

    body.append(_para("Encoded categories:", SECTION_HEADER))
    body.append(_para("• <b>NOT_HAC</b>: 8h ≤ cut-off (suppressed)", BODY))
    body.append(_para("• <b>NOT_HAC_INVERSE</b>: 8h ≤ cut-off but 4h > baseline (inverse pattern; suspicious)", BODY))
    body.append(_para("• <b>SUPPORTS_PDH</b>: 8h > cut-off + at least one suppression criterion (4h < cut-off, 4h < 50% baseline, or 8h < 50% baseline)", BODY))
    body.append(_para("• <b>DEX_RESISTANT</b>: 8h > cut-off + no suppression criteria met", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in LDDST_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="lddst",
        title="LDDST interpretation",
        subtitle="Diagnostic · ACVIM Consensus 2013",
        body=body,
        priority=7,
    )


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------


def page_energy() -> ReviewPage:
    from app.calculators.energy import ENERGY_SOURCES

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Daily caloric requirement (RER, MER) and food serving size.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs: species, purpose (maintenance / weight loss / weight gain), current weight, BCS, ideal weight, maintenance factor, food caloric density.", BODY))

    body.append(_para("Encoded formulas:", SECTION_HEADER))
    body.append(_para("• <b>RER</b> = 70 × BW^0.75 (both species, all modes)", BODY))
    body.append(_para("• <b>Cat MER (maintenance)</b> = 100 × BW^0.67 (lean formula used regardless of BCS)", BODY))
    body.append(_para("• <b>Cat MER (weight loss)</b> = 130 × IBW^0.4 (NRC obese-cat formula, applied against ideal body weight)", BODY))
    body.append(_para("• <b>Dog MER</b> = factor × RER (factor selected by clinician from a maintenance-factor table)", BODY))

    body.append(_para("Note: in MAINTENANCE mode, the calculator uses the lean cat MER formula regardless of BCS. The 130 × BW^0.4 obese formula is applied only in WEIGHT_LOSS mode against ideal body weight. This is intentional but worth confirming with a reviewer.", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    for s in ENERGY_SOURCES:
        body.append(_para(s.citation, SOURCE))

    return ReviewPage(
        slug="energy",
        title="Energy requirements (RER / MER)",
        subtitle="Nutrition · WSAVA / NRC",
        body=body,
        priority=7,
    )


# ---------------------------------------------------------------------------
# Cushings score
# ---------------------------------------------------------------------------


def page_cushings_score() -> ReviewPage:
    from app.routers.cushings_score import SCORE_TO_LIKELIHOOD

    body = []
    body.append(_para("<b>Question this calculator answers:</b> Pretest probability of canine HAC from a multi-variable additive score.", BODY))
    body.append(Spacer(1, 6))

    body.append(_para("Inputs: sex, age, breed, polydipsia, vomiting, potbelly, alopecia, pruritus, USG, ALKP.", BODY))

    body.append(_para("Encoded score → likelihood lookup (sample):", SECTION_HEADER))
    rows = [["Total score", "Predicted likelihood"]]
    for s in [-13, -10, -5, 0, 5, 8, 10]:
        if s in SCORE_TO_LIKELIHOOD:
            rows.append([str(s), f"{int(SCORE_TO_LIKELIHOOD[s] * 100)}%"])
    body.append(_wrap_table(rows, [2.0 * inch, 2.5 * inch]))
    body.append(_para("Score range: -13 to +10 (clamped). Component points include: sex (±), age ≥7 (+1), breed risk (-3 to +2), clinical signs (PD/potbelly/alopecia +; vomiting/pruritus −), USG (-2 to 0), ALKP (-3 to 0).", BODY))

    body.append(_para("Cited source:", SECTION_HEADER))
    body.append(_para("Behrend EN, Kooistra HS, Nelson R, Reusch CE, Scott-Moncrieff JC. Diagnosis of spontaneous canine hyperadrenocorticism: 2012 ACVIM Consensus Statement. JVIM 2013.", SOURCE))
    body.append(_para("Bennaim M, Shiel RE, Mooney CT. Diagnosis of spontaneous hyperadrenocorticism in dogs (review).", SOURCE))

    return ReviewPage(
        slug="cushings_score",
        title="Cushing's pretest probability score",
        subtitle="Diagnostic · ACVIM Consensus + Bennaim review",
        body=body,
        priority=7,
    )


# ---------------------------------------------------------------------------
# Page renderer
# ---------------------------------------------------------------------------


def render_page(page: ReviewPage, page_number: int, total_pages: int) -> list:
    """Wrap the calculator-specific body with header + reviewer markup box."""
    flowables = []

    # Header
    flowables.append(Paragraph(f"<b>{page.title}</b>", CALCULATOR_TITLE))
    flowables.append(Paragraph(f"{page.subtitle}  •  Slug: <font face='Helvetica' color='#3b3f4a'>{page.slug}</font>  •  Priority {page.priority}  •  Page {page_number} of {total_pages}", CALCULATOR_SUBTITLE))

    flowables.extend(page.body)

    # Reviewer markup box — compact version, lives at bottom of page
    flowables.append(Spacer(1, 6))
    box = Table(
        [
            [Paragraph("<b>REVIEWER MARKUP</b> &nbsp;&nbsp;&nbsp; ☐ Matches reference (Yes) &nbsp;&nbsp; ☐ Correction needed (see notes)", BODY)],
            [Paragraph("Notes / corrected value / source citation:", BODY)],
            [Paragraph("&nbsp;<br/>&nbsp;<br/>&nbsp;", BODY)],
            [Paragraph("Reviewer: ______________________  &nbsp; Date: ________  &nbsp; Initials: ______", BODY)],
        ],
        colWidths=[6.5 * inch],
    )
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#92400e")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#fbbf24")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    flowables.append(box)
    flowables.append(PageBreak())
    return flowables


def render_cover() -> list:
    flowables = []
    flowables.append(Spacer(1, 0.8 * inch))
    flowables.append(Paragraph("InfusionFox Peer Review Packet", COVER_TITLE))
    flowables.append(Paragraph(
        "Each page describes one calculator: the clinical question it answers, the inputs the user enters, the dose ranges and tables encoded in the application, the warnings the application surfaces, and the cited primary source.",
        COVER_BODY,
    ))
    flowables.append(Paragraph(
        "<b>What we're asking you to verify:</b> that the encoded values (dose ranges, tier boundaries, warnings, and source attribution) faithfully reproduce the cited reference. We are NOT asking you to audit the application's math — that is independently tested.",
        COVER_BODY,
    ))
    flowables.append(Paragraph(
        "<b>Priority order:</b> highest-stakes first. Priority 1–2 are high-alert; priority 3–4 are foundational; priority 5–7 are lower-stakes or diagnostic.",
        COVER_BODY,
    ))
    flowables.append(Paragraph(
        "<b>How to mark up:</b> each page has a reviewer-markup box at the bottom. If content matches your reference, check 'Yes' and initial. If anything is off, check 'No' and write the correction with source citation. Findings map back to the calculator slug printed at the top of each page.",
        COVER_BODY,
    ))
    flowables.append(Spacer(1, 0.3 * inch))
    flowables.append(Paragraph(
        "<i>Generated from source. Reflects the application as of build date.</i>",
        SOURCE,
    ))
    flowables.append(PageBreak())
    return flowables


def build(output_path: Path) -> None:
    page_funcs = [
        # Priority 1 — high-alert hyperK bridge
        page_ca_gluconate,
        page_insulin_dextrose,
        # Priority 2 — high-alert / high-stakes pressors and emergency
        page_cpr,
        page_norepinephrine,
        page_epinephrine,
        page_dobutamine,
        page_dopamine_prep,
        page_dopamine_standard,
        page_insulin_cri_dka,
        page_insulin_im_dka,
        # Priority 3 — foundational fluid + electrolyte
        page_fluid_therapy,
        page_hypernatremia,
        page_fentanyl,
        # Priority 4 — published-table electrolytes
        page_hypokalemia,
        page_hypomagnesemia,
        page_hypophosphatemia,
        # Priority 5 — analgesia / sedation, dog-only
        page_lidocaine,
        # Priority 6 — analgesia / sedation
        page_ketamine,
        page_propofol,
        page_methadone,
        page_hydromorphone,
        page_alfaxalone,
        page_mlk,
        page_kitty_magic,
        page_cornell_onco_kl,
        # Priority 7 — diagnostic / nutrition
        page_iris_staging,
        page_lddst,
        page_cushings_score,
        page_energy,
    ]

    pages = [fn() for fn in page_funcs]
    total = len(pages)

    flowables = render_cover()
    for i, page in enumerate(pages, start=1):
        flowables.extend(render_page(page, i, total))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="InfusionFox Peer Review Packet",
        author="InfusionFox",
    )
    doc.build(flowables)
    print(f"✓ Wrote {output_path} ({total} calculator pages + cover)")


if __name__ == "__main__":
    output = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "data" / "peer_review_packet.pdf"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    build(output)
