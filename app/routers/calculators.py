"""
Calculator routes; dispatches by calculator kind.

Engine-driven drugs (norepinephrine, epinephrine, dobutamine, dopamine,
fentanyl) used to share a single `/c/{slug}` dispatcher. The bare-path
migration moved each drug to its own concrete URL:

    GET  /<slug>               : renders the calculator page (kind-aware)
    POST /<slug>/compute       : HTMX live-compute for single-drug CRI
    POST /<slug>/lookup        : HTMX live-lookup for sliding scales

Routes are registered per-drug at module load time. Backwards compatibility
for `/c/<slug>` URLs is provided by `app/routers/legacy_redirects.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.calculators import (
    CalcInputs,
    CalculatorKind,
    CriMode,
    DilutionInputs,
    Species,
    WeightUnit,
    compute,
    compute_dilution,
    get_drug,
    lookup_sliding_scale,
)
from app.calculators.drugs import DRUGS
from app.routers._form_parsing import parse_positive_float

router = APIRouter()


# ---------------------------------------------------------------------------
# Page dispatch helpers — one render per calculator kind.
# Registered per drug below; not directly attached to the router.
# ---------------------------------------------------------------------------


def _dispatch_page(slug: str, request: Request) -> HTMLResponse:
    drug = get_drug(slug)
    if drug is None:
        raise HTTPException(404, f"No calculator for '{slug}'")

    if drug.kind == CalculatorKind.SINGLE_DRUG_CRI:
        return _render_single_drug(drug, request)
    if drug.kind == CalculatorKind.SLIDING_SCALE:
        return _render_sliding_scale(drug, request)
    if drug.kind == CalculatorKind.MULTI_STEP_PROTOCOL:
        return _render_multi_step(drug, request)

    raise HTTPException(500, f"Calculator kind {drug.kind.value} not yet implemented")


def _render_single_drug(drug, request: Request):
    templates = request.app.state.templates
    default_inputs = CalcInputs(
        weight_value=1.0,  # placeholder, not displayed
        weight_unit=WeightUnit.LB,
        dose=drug.default_dose,
        concentration_ug_per_ml=drug.default_concentration_ug_per_ml,
        species=Species.DOG,
    )

    dog_range = drug.dose_ranges.get(Species.DOG)
    cat_range = drug.dose_ranges.get(Species.CAT)
    cat_hard_max = cat_range.hard_max if cat_range else None

    # Resolve which preset is the headline default and which others to
    # offer in the alt-concentration disclosure. The default is the
    # preset matching drug.default_concentration_ug_per_ml; the alts are
    # the other pump_safe presets. Undiluted-vial presets (pump_safe=False)
    # are intentionally excluded — they're warnings, not real options the
    # user should pick. If no preset exactly matches the default
    # concentration (shouldn't happen, but defensive), the first pump_safe
    # preset is used as the default so the page still renders coherently.
    default_preset = None
    alt_presets = []
    for preset in drug.concentration_presets:
        if (
            default_preset is None
            and preset.concentration_ug_per_ml == drug.default_concentration_ug_per_ml
        ):
            default_preset = preset
        elif preset.pump_safe:
            alt_presets.append(preset)
    if default_preset is None:
        # Defensive fallback. Pick the first pump_safe preset and demote
        # the rest into alternatives.
        pump_safe_presets = [p for p in drug.concentration_presets if p.pump_safe]
        if pump_safe_presets:
            default_preset = pump_safe_presets[0]
            alt_presets = pump_safe_presets[1:]

    # For any drug using the combined prep section (norepi, dobutamine,
    # …), pre-compute all (concentration × bag size) variants for the
    # form. Template renders one recipe card per combination; JS toggles
    # which is visible based on the currently-checked tabs.
    form_variants = None
    if drug.uses_combined_prep_section:
        from app.calculators.drugs import bag_size_variants_for_drug

        form_variants = []
        for preset in drug.concentration_presets:
            if not preset.pump_safe:
                continue
            for v in bag_size_variants_for_drug(drug, preset.concentration_ug_per_ml):
                form_variants.append(v)

    return templates.TemplateResponse(
        "calculator.html",
        {
            "request": request,
            "drug": drug,
            "inputs": default_inputs,
            "result": None,
            "weight_value": "",
            "dog_range": dog_range,
            "cat_range": cat_range,
            "cat_hard_max": cat_hard_max,
            "default_preset": default_preset,
            "alt_presets": alt_presets,
            "form_variants": form_variants,
            "is_htmx_response": False,
        },
    )


def _render_sliding_scale(drug, request: Request):
    templates = request.app.state.templates
    result = lookup_sliding_scale(drug, drug.scale_default_value)
    return templates.TemplateResponse(
        "calculator_scale.html",
        {
            "request": request,
            "drug": drug,
            "input_value": drug.scale_default_value,
            "result": result,
        },
    )


def _render_multi_step(drug, request: Request):
    import markdown as md_lib

    templates = request.app.state.templates
    # Pre-render each step's markdown content → HTML so the template can
    # safely emit it. Markdown is what clinicians author in YAML.
    rendered_steps = [
        {
            "step_number": s.step_number,
            "title": s.title,
            "content_html": md_lib.markdown(s.content, extensions=["extra", "sane_lists"]),
            "conditions": s.conditions,
        }
        for s in drug.protocol_steps
    ]
    return templates.TemplateResponse(
        "calculator_protocol.html",
        {"request": request, "drug": drug, "rendered_steps": rendered_steps},
    )


# ---------------------------------------------------------------------------
# Compute & lookup dispatch — used by the per-drug compute endpoints.
# ---------------------------------------------------------------------------


async def _dispatch_compute(
    slug: str,
    request: Request,
    weight_value: str,
    weight_unit: str,
    dose: str,
    concentration_ug_per_ml: str,
    species: str,
    cri_mode: str,
    target_pump_rate_ml_per_hr: str,
    bag_volume_ml: str,
    combined_prep_bag_size_ml: str = "",
) -> HTMLResponse:
    drug = get_drug(slug)
    if drug is None or drug.kind != CalculatorKind.SINGLE_DRUG_CRI:
        raise HTTPException(404)
    templates = request.app.state.templates

    # Parse the mode first; an unknown value silently falls back to
    # STANDARD_BAG. A garbled mode field must not flip the user into
    # the alternate-output panel without their consent.
    try:
        mode = CriMode(cri_mode)
    except ValueError:
        mode = CriMode.STANDARD_BAG

    # Defense in depth: if the form posted target_pump_rate but the drug
    # has supports_target_pump_rate_mode=False, treat it as standard_bag.
    # The form template doesn't render the toggle for these drugs, so a
    # POST with target_pump_rate is either a stale browser tab or an
    # adversarial / malformed request. Either way, fall back to the
    # historical default rather than producing an alternate-mode result
    # the user didn't intend.
    if mode == CriMode.TARGET_PUMP_RATE and not drug.supports_target_pump_rate_mode:
        mode = CriMode.STANDARD_BAG

    weight = parse_positive_float(weight_value)
    dose_value = parse_positive_float(dose)

    if mode == CriMode.STANDARD_BAG:
        concentration = parse_positive_float(concentration_ug_per_ml)
        if weight is None or dose_value is None or concentration is None:
            return templates.TemplateResponse(
                "partials/_invalid_input_placeholder.html",
                {"request": request},
            )
        try:
            inputs = CalcInputs(
                weight_value=weight,
                weight_unit=WeightUnit(weight_unit),
                dose=dose_value,
                concentration_ug_per_ml=concentration,
                species=Species(species),
                cri_mode=CriMode.STANDARD_BAG,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    else:
        # TARGET_PUMP_RATE: bag concentration is an output, not an
        # input. The form does not collect it. We use the drug's
        # stock-vial concentration as the source we draw from.
        target_rate = parse_positive_float(target_pump_rate_ml_per_hr)
        bag_vol = parse_positive_float(bag_volume_ml)
        if (
            weight is None
            or dose_value is None
            or target_rate is None
            or bag_vol is None
        ):
            return templates.TemplateResponse(
                "partials/_invalid_input_placeholder.html",
                {"request": request},
            )
        try:
            inputs = CalcInputs(
                weight_value=weight,
                weight_unit=WeightUnit(weight_unit),
                dose=dose_value,
                # Concentration is derived in compute(); pass a
                # placeholder that won't divide by zero in any
                # defensive path. The engine reassigns this from the
                # computed bag concentration before using it.
                concentration_ug_per_ml=drug.stock_concentration_ug_per_ml,
                species=Species(species),
                cri_mode=CriMode.TARGET_PUMP_RATE,
                target_pump_rate_ml_per_hr=target_rate,
                bag_volume_ml=bag_vol,
                stock_concentration_ug_per_ml=drug.stock_concentration_ug_per_ml,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    result = compute(drug, inputs)

    # Pick the result template based on the mode the inputs declared.
    # Even on a validation failure we want to render the right partial
    # so the empty-state placeholder fits the form the user is looking
    # at, but compute() already returns valid=False with the
    # appropriate warnings.
    if inputs.cri_mode == CriMode.TARGET_PUMP_RATE:
        result_template = "partials/result_panel_target_pump_rate.html"
    else:
        result_template = "partials/result_panel.html"

    # Norepi result panel extras: at the user's chosen concentration,
    # generate the three bag-size presentations (250 / 500 / 1 L) so they
    # can pick the size their clinic stocks. Plus the dilution-
    # recommendation logic: tells the template which (if any) notice to
    # render. Three distinct situations:
    #   1. User's concentration matches recommendation → no notice.
    #   2. User's concentration > recommended → pump rate drops below the
    #      precision floor (recommended is the HIGHEST pump-safe option,
    #      so anything more concentrated is below floor). Show the
    #      "more precise preparation" notice.
    #   3. User's concentration < recommended → pump rate is above the
    #      floor but unnecessarily high; delivers extra carrier fluid for
    #      the same drug dose. Show the "more concentrated preparation"
    #      notice (different wording — the issue is fluid load, not
    #      precision).
    # Separately, if even the most-dilute preset gives a sub-floor rate
    # (very small patient at very low dose), surface the precision-floor
    # warning regardless of which conc the user picked.
    # Concentration-mismatch notices for any drug using the pump-precision
    # strategy (currently norepi). The picker returns the highest pump-safe
    # concentration that keeps rate ≥ drug.min_pump_rate_ml_per_hr; the
    # three flags surface different mismatches between that recommendation
    # and the user's selection:
    #   - concentration_too_high: user picked more concentrated than
    #     recommended (pump rate dropped below the precision floor)
    #   - concentration_too_low: user picked more dilute than recommended
    #     (rate is above floor but carrier fluid is excessive)
    #   - below_precision_floor: even the recommended (most dilute that
    #     keeps rate above floor) gives a sub-floor rate — happens for
    #     very small patients at very low doses, no standard preset is
    #     dilute enough
    # These notices don't apply to weight-band drugs (dobutamine, epi) —
    # there the patient-driven recommendation is captured by the
    # "suggested" badge on the conc tabs, and the directional framing
    # doesn't fit the workflow.
    recommended_preset = None
    concentration_too_high = False
    concentration_too_low = False
    below_precision_floor = False
    if (
        drug.recommendation_strategy == "pump-precision"
        and inputs.cri_mode == CriMode.STANDARD_BAG
        and result.valid
    ):
        from app.calculators.drugs import pick_preset_for_patient

        recommended_preset = pick_preset_for_patient(
            drug=drug,
            weight_kg=result.weight_kg,
            dose_ug_kg_min=inputs.dose,
        )
        if (
            recommended_preset.concentration_ug_per_ml
            < result.concentration_ug_per_ml
        ):
            concentration_too_high = True
        elif (
            recommended_preset.concentration_ug_per_ml
            > result.concentration_ug_per_ml
        ):
            concentration_too_low = True
        # If even the recommended preset gives a sub-floor rate, surface
        # a stronger warning. Happens for very small patients at very
        # low doses where no standard preset is dilute enough.
        recommended_rate = (
            inputs.dose * result.weight_kg * 60.0
        ) / recommended_preset.concentration_ug_per_ml
        floor = drug.min_pump_rate_ml_per_hr or 2.0
        below_precision_floor = recommended_rate < floor

    # Dobutamine-specific: the precision-floor signal applies only when
    # the user has chosen the 250 mL bag (volumetric-pump workflow). On
    # the 50 mL syringe option the assumption is a syringe pump is
    # already in use, so the floor doesn't apply. The prescription
    # offered ("use a syringe pump, or select a different concentration")
    # differs from norepi's, which is why this is a separate flag
    # rather than a reuse of `below_precision_floor`.
    dobutamine_volumetric_below_floor = False
    if (
        drug.slug == "dobutamine"
        and inputs.cri_mode == CriMode.STANDARD_BAG
        and result.valid
    ):
        try:
            bag_size = int(combined_prep_bag_size_ml)
        except (TypeError, ValueError):
            bag_size = 0
        if bag_size == 250 and result.ml_per_hr_pump < 2.0:
            dobutamine_volumetric_below_floor = True

    # Dopamine-CRI specific: surfaces a precision-floor notice when the
    # patient × dose × concentration combo drops below the 2 mL/hr
    # precision floor. Both bag sizes (250 mL and 500 mL) are
    # volumetric, so unlike dobutamine we don't gate on bag-size.
    # Common trigger: small patient at the 3 µg/kg/min dose floor on
    # the standard 200 mg / 250 mL prep (800 µg/mL) — e.g., 5 kg
    # patient × 3 µg/kg/min × 60 ÷ 800 = 1.13 mL/hr, sub-floor. The
    # remedy is to switch to the more dilute prep (500 mL bag → 400
    # µg/mL) or to a syringe pump.
    dopamine_below_floor = False
    if (
        drug.slug == "dopamine-cri"
        and inputs.cri_mode == CriMode.STANDARD_BAG
        and result.valid
        and result.ml_per_hr_pump < (drug.min_pump_rate_ml_per_hr or 2.0)
    ):
        dopamine_below_floor = True

    # Loading-dose math for drugs that publish IV loading scenarios
    # alongside the CRI (currently fentanyl). The result_panel renders
    # one panel per scenario below the CRI rate. Only computes when
    # the inputs are valid; otherwise empty tuple → template skips.
    loading_dose_results: tuple = ()
    if drug.loading_doses and result.valid:
        from app.calculators.drugs import compute_loading_doses

        loading_dose_results = compute_loading_doses(
            drug=drug,
            weight_kg=result.weight_kg,
            species=result.species,
            cri_dose_value=inputs.dose,
        )

    return templates.TemplateResponse(
        result_template,
        {
            "request": request,
            "drug": drug,
            "inputs": inputs,
            "result": result,
            "is_htmx_response": True,
            "recommended_preset": recommended_preset,
            "concentration_too_high": concentration_too_high,
            "concentration_too_low": concentration_too_low,
            "below_precision_floor": below_precision_floor,
            "dobutamine_volumetric_below_floor": dobutamine_volumetric_below_floor,
            "dopamine_below_floor": dopamine_below_floor,
            "loading_dose_results": loading_dose_results,
        },
    )


async def _dispatch_lookup(slug: str, request: Request, input_value: str) -> HTMLResponse:
    drug = get_drug(slug)
    if drug is None or drug.kind != CalculatorKind.SLIDING_SCALE:
        raise HTTPException(404)
    templates = request.app.state.templates
    parsed_input = parse_positive_float(input_value)
    if parsed_input is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {"request": request},
        )

    result = lookup_sliding_scale(drug, parsed_input)

    return templates.TemplateResponse(
        "partials/scale_result_panel.html",
        {"request": request, "drug": drug, "input_value": parsed_input, "result": result},
    )


# ---------------------------------------------------------------------------
# Register concrete routes per engine drug.
#
# DRUGS is statically known at module-load time (no YAML-loaded drugs
# currently). For each drug we register:
#   GET  /<slug>            page render
#   POST /<slug>/compute    HTMX recompute (SINGLE_DRUG_CRI only)
#   POST /<slug>/lookup     HTMX recompute (SLIDING_SCALE only)
#
# Closures bind `slug` per iteration via a default argument so each
# handler dispatches to the right drug regardless of loop variable shadowing.
# ---------------------------------------------------------------------------


def _register_engine_drug_routes() -> None:
    for drug in DRUGS:
        slug = drug.slug

        async def _page(request: Request, _slug: str = slug) -> HTMLResponse:
            return _dispatch_page(_slug, request)

        router.add_api_route(
            f"/{slug}",
            _page,
            methods=["GET"],
            response_class=HTMLResponse,
        )

        if drug.kind == CalculatorKind.SINGLE_DRUG_CRI:
            async def _compute(
                request: Request,
                weight_value: str = Form(""),
                weight_unit: str = Form("lb"),
                dose: str = Form(""),
                concentration_ug_per_ml: str = Form(""),
                species: str = Form("dog"),
                cri_mode: str = Form("standard_bag"),
                target_pump_rate_ml_per_hr: str = Form(""),
                bag_volume_ml: str = Form(""),
                combined_prep_bag_size_ml: str = Form(""),
                _slug: str = slug,
            ) -> HTMLResponse:
                return await _dispatch_compute(
                    _slug,
                    request,
                    weight_value,
                    weight_unit,
                    dose,
                    concentration_ug_per_ml,
                    species,
                    cri_mode,
                    target_pump_rate_ml_per_hr,
                    bag_volume_ml,
                    combined_prep_bag_size_ml,
                )

            router.add_api_route(
                f"/{slug}/compute",
                _compute,
                methods=["POST"],
                response_class=HTMLResponse,
            )

        if drug.kind == CalculatorKind.SLIDING_SCALE:
            async def _lookup(
                request: Request,
                input_value: str = Form(""),
                _slug: str = slug,
            ) -> HTMLResponse:
                return await _dispatch_lookup(_slug, request, input_value)

            router.add_api_route(
                f"/{slug}/lookup",
                _lookup,
                methods=["POST"],
                response_class=HTMLResponse,
            )


_register_engine_drug_routes()


# ---------------------------------------------------------------------------
# Dilution helper, unchanged
# ---------------------------------------------------------------------------


@router.post("/dilution/compute", response_class=HTMLResponse)
async def dilution_compute(
    request: Request,
    stock_concentration_ug_per_ml: str = Form(""),
    desired_concentration_ug_per_ml: str = Form(""),
    final_volume_ml: str = Form(""),
):
    templates = request.app.state.templates
    stock = parse_positive_float(stock_concentration_ug_per_ml)
    desired = parse_positive_float(desired_concentration_ug_per_ml)
    volume = parse_positive_float(final_volume_ml)
    if stock is None or desired is None or volume is None:
        return templates.TemplateResponse(
            "partials/_invalid_input_placeholder.html",
            {
                "request": request,
                "placeholder_id": "dilution-result",
            },
        )
    inputs = DilutionInputs(
        stock_concentration_ug_per_ml=stock,
        desired_concentration_ug_per_ml=desired,
        final_volume_ml=volume,
    )
    result = compute_dilution(inputs)
    # Show formula only when this compute is happening on the standalone /dilution
    # page (educational reference). The embedded helper on every drug page
    # stays free of the formula box.
    current_url = request.headers.get("hx-current-url", "")
    show_formula = current_url.endswith("/dilution") or current_url.endswith("/dilution/")
    return templates.TemplateResponse(
        "partials/dilution_result.html",
        {
            "request": request,
            "dilution_inputs": inputs,
            "dilution_result": result,
            "show_formula": show_formula,
        },
    )


@router.get("/dilution", response_class=HTMLResponse)
async def dilution_page(request: Request):
    templates = request.app.state.templates
    inputs = DilutionInputs(
        stock_concentration_ug_per_ml=12500,
        desired_concentration_ug_per_ml=1000,
        final_volume_ml=50,
    )
    result = compute_dilution(inputs)
    return templates.TemplateResponse(
        "dilution.html",
        {
            "request": request,
            "dilution_inputs": inputs,
            "dilution_result": result,
            "show_formula": True,
        },
    )
