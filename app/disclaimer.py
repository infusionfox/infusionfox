"""InfusionFox disclaimer text and version.

The disclaimer is a hard-block modal: users cannot interact with the
site until they accept. Acceptance is recorded server-side with IP,
user-agent, and timestamp.

Versioning: bump ``DISCLAIMER_VERSION`` (use an ISO date) whenever the
text changes substantively. The frontend localStorage check compares
the user's accepted version against the current one and re-fires the
modal on mismatch. The audit-trail rows in ``disclaimer_acceptances``
record which version was accepted, so historical evidence is preserved.

When auth returns (Cloudflare Zero Trust or equivalent), acceptance
will be linked to user accounts via a foreign key; the current
device-scoped acceptance becomes a stopgap. See db/models.py.
"""

from __future__ import annotations

# Bump this (ISO date) when DISCLAIMER_TEXT is changed substantively.
# Cosmetic/formatting changes don't require a bump; substantive changes
# to the terms, scope, or data-collection notice do. Material clinical
# content corrections (calculator cutoffs, dose recommendations) also
# warrant a bump so the acceptance audit trail shows users accepted
# AFTER the corrections, not before.
#
# 2026-06-09: IRIS staging cat SDMA stage 3/4 cutoff corrected from
# 45 to 38 µg/dL (matches IRIS 2023 source); plus 7 boundary off-by-one
# fixes across creatinine, SDMA, and UPC. CPR defibrillation refactored
# to RECOVER 2024 dual-waveform (biphasic primary 2 J/kg with 4 J/kg
# escalation; monophasic secondary). Cat dopamine caution threshold
# aligned to 2.0 µg/kg/min (was 7.5) per standalone /dopamine HCM-risk
# rationale (Wiese et al PVC range across feline ladder). Added two
# new calculators: mannitol osmotherapy (5 Plumb's indications with
# optional follow-up CRI for AKI and uroliths) and osmolar gap
# (calculated osmolality + gap interpretation for EG toxicosis, DKA,
# and mannitol monitoring). Also added oxygenation calculator
# (PaO₂:FiO₂ ratio + alveolar-arterial gradient for ARDS classification
# and identifying the cause of hypoxemia).
#
# 2026-06-08: prior version.
DISCLAIMER_VERSION = "2026-06-09"

DISCLAIMER_TEXT = """\
InfusionFox is a clinical reference and calculator tool for licensed \
veterinary professionals. It supports clinical decision-making but does \
not replace it. Every calculator shows its work and cites its sources, \
so the math can be verified at the point of care. Every dose, \
calculation, and score requires verification against your patient, \
the primary literature, and current standard of care before any \
clinical action.

The author of this site is a licensed veterinarian, but InfusionFox is not \
a substitute for individual professional judgment, and no clinician-\
patient relationship is created by your use of it.

InfusionFox is free, provided without warranty of any kind. You assume \
full responsibility for clinical decisions made with this tool. The \
author and operators disclaim liability for clinical outcomes, errors \
in published rubrics, drug-label changes since publication, and any \
consequences arising from use or misuse of the calculators or content.

By accepting these terms, you acknowledge that you are a licensed \
veterinary professional or supervised member of a clinical team. To \
create an audit record of your acceptance, your IP address, browser \
user-agent, and the current date and time will be recorded.\
"""
