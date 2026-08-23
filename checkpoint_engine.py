"""Shared 50-point evidence checkpoint engine for Trilloka.

This module is intentionally dependency-free and is used by both the scorer and
report generator so the report cannot drift away from what the scoring engine
actually evaluated.

Rules:
- PASS means positive evidence was observed.
- FAIL means sufficient evidence existed and the requirement was not met.
- UNKNOWN means the scanner could not verify either state.
- NOT_APPLICABLE means the check is not commercially relevant to this site/model.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from architecture_model import common_vs_architectural, context_has, infer_architecture_profile

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
NA = "NOT_APPLICABLE"


# Report/scoring metadata for failed checkpoints that are not already represented
# by one of the scorer's dedicated high-impact rules.
CHECKPOINT_RULE_META: Dict[int, Dict[str, Any]] = {
    # Dedicated rules also need report metadata; otherwise their checkpoint
    # records fall through to zero weight/severity.
    1: {"rule_key": "unsecured_ssl", "family": "foundation_security", "weight": 3.0, "severity": 0.90},
    2: {"rule_key": "https_redirect", "family": "foundation_security", "weight": 1.4, "severity": 0.45},
    3: {"rule_key": "click_to_call", "family": "mobile_direct_action", "weight": 2.2, "severity": 0.65},
    4: {"rule_key": "mobile_sticky_cta", "family": "mobile_direct_action", "weight": 2.6, "severity": 0.70},
    5: {"rule_key": "form_architecture", "family": "conversion_execution", "weight": 3.0, "severity": 0.85},
    6: {"rule_key": "retargeting_telemetry", "family": "measurement", "weight": 1.5, "severity": 0.40},
    7: {"rule_key": "primary_conversion_path", "family": "conversion_execution", "weight": 2.6, "severity": 0.70},
    8: {"rule_key": "phone_visibility", "family": "mobile_direct_action", "weight": 2.2, "severity": 0.55},
    9: {"rule_key": "location_visibility", "family": "trust_local", "weight": 1.8, "severity": 0.50},
    10: {"rule_key": "trust_credentials", "family": "trust_proof", "weight": 1.8, "severity": 0.45},
    11: {"rule_key": "reviews_social_proof", "family": "trust_proof", "weight": 2.2, "severity": 0.55},
    12: {"rule_key": "guarantee_refund_clarity", "family": "trust_policy", "weight": 1.4, "severity": 0.40},
    13: {"rule_key": "about_team_signal", "family": "trust_identity", "weight": 1.2, "severity": 0.35},
    14: {"rule_key": "social_proof_signal", "family": "trust_proof", "weight": 1.8, "severity": 0.45},
    15: {"rule_key": "instant_query_channel", "family": "mobile_direct_action", "weight": 1.5, "severity": 0.40},
    16: {"rule_key": "meta_description_missing", "family": "search_snippet", "weight": 1.5, "severity": 0.45},
    17: {"rule_key": "meta_description_length", "family": "search_snippet", "weight": 0.9, "severity": 0.30},
    18: {"rule_key": "diluted_h1", "family": "hero_clarity", "weight": 1.6, "severity": 0.55},
    19: {"rule_key": "h1_topic_relevance", "family": "hero_clarity", "weight": 1.6, "severity": 0.45},
    20: {"rule_key": "title_length", "family": "search_snippet", "weight": 0.9, "severity": 0.30},
    21: {"rule_key": "structured_data_missing", "family": "search_structure", "weight": 1.6, "severity": 0.45},
    22: {"rule_key": "canonical_missing", "family": "search_structure", "weight": 1.2, "severity": 0.40},
    23: {"rule_key": "sitemap_missing", "family": "crawlability", "weight": 1.2, "severity": 0.40},
    24: {"rule_key": "robots_missing", "family": "crawlability", "weight": 1.2, "severity": 0.40},
    25: {"rule_key": "pagespeed_below_60", "family": "performance", "weight": 2.6, "severity": 0.70},
    26: {"rule_key": "pagespeed_below_90", "family": "performance", "weight": 1.4, "severity": 0.40},
    27: {"rule_key": "seo_score_below_80", "family": "search_structure", "weight": 1.8, "severity": 0.50},
    28: {"rule_key": "lcp_poor", "family": "performance", "weight": 2.4, "severity": 0.65},
    29: {"rule_key": "inp_poor", "family": "performance", "weight": 2.4, "severity": 0.65},
    30: {"rule_key": "cls_poor", "family": "performance", "weight": 2.1, "severity": 0.60},
    31: {"rule_key": "viewport_missing", "family": "mobile_foundation", "weight": 2.6, "severity": 0.75},
    32: {"rule_key": "tap_target_friction", "family": "mobile_usability", "weight": 2.0, "severity": 0.55},
    33: {"rule_key": "render_blocking", "family": "performance", "weight": 1.7, "severity": 0.45},
    34: {"rule_key": "missing_alt_images", "family": "accessibility_media", "weight": 1.2, "severity": 0.35},
    35: {"rule_key": "lazy_loading_gap", "family": "performance", "weight": 1.0, "severity": 0.30},
    37: {"rule_key": "author_bylines_missing", "family": "content_eeat", "weight": 1.1, "severity": 0.35},
    38: {"rule_key": "publication_dates_missing", "family": "content_eeat", "weight": 0.9, "severity": 0.30},
    39: {"rule_key": "thin_visible_content", "family": "content_depth", "weight": 1.6, "severity": 0.45},
    40: {"rule_key": "ai_template_similarity", "family": "content_distinctiveness", "weight": 0.8, "severity": 0.20},
    41: {"rule_key": "ai_template_similarity", "family": "content_distinctiveness", "weight": 0.5, "severity": 0.15},
    42: {"rule_key": "generic_headline", "family": "content_distinctiveness", "weight": 1.5, "severity": 0.45},
    43: {"rule_key": "unlinked_form_structure", "family": "conversion_execution", "weight": 2.4, "severity": 0.65},
    44: {"rule_key": "faq_missing", "family": "content_support", "weight": 1.2, "severity": 0.35},
    45: {"rule_key": "case_studies_missing", "family": "trust_proof", "weight": 1.4, "severity": 0.40},
    46: {"rule_key": "content_hub_missing", "family": "content_depth", "weight": 1.1, "severity": 0.30},
    47: {"rule_key": "social_links_missing", "family": "trust_identity", "weight": 0.8, "severity": 0.25},
    48: {"rule_key": "privacy_terms_missing", "family": "trust_policy", "weight": 1.8, "severity": 0.50},
    50: {"rule_key": "conversion_path_error", "family": "conversion_execution", "weight": 3.5, "severity": 0.90},
}

# Dedicated scorer rules that already represent these checkpoint failures.
DEDICATED_CHECKPOINT_RULES = {
    1: "unsecured_ssl",
    3: "click_to_call",
    4: "mobile_sticky_cta",
    5: "form_architecture",
    6: "measurement_telemetry",
    7: "primary_conversion_path",
    18: "diluted_h1",
    25: "core_web_vitals",
    28: "core_web_vitals",
    29: "core_web_vitals",
    30: "core_web_vitals",
    34: "missing_alt_images",
    41: "ai_template_similarity",
    43: "form_architecture",
    50: "conversion_path_error",
}


# A deliberately small whitelist of verified omissions that represent elementary
# website architecture, not advanced optimization.  These signals are reported
# separately from score severity and revenue exposure so a low-point hygiene item
# can still be surfaced as a basic implementation oversight without being inflated
# into a major financial claim.
FOUNDATION_OMISSION_META: Dict[int, Dict[str, str]] = {
    1: {
        "level": "CRITICAL",
        "title": "Secure HTTPS Foundation Missing",
        "why": "A modern public website should serve customers over HTTPS before advanced optimization is considered.",
        "solution": "Install/repair the TLS certificate, serve the public site on HTTPS, and recheck all primary URLs and assets.",
    },
    2: {
        "level": "IMPORTANT",
        "title": "HTTPS Redirect Enforcement Missing",
        "why": "A secure site should consistently send HTTP visitors to the canonical HTTPS version.",
        "solution": "Configure a permanent HTTP-to-HTTPS redirect at the CDN/server layer and verify there are no loops or mixed destinations.",
    },
    16: {
        "level": "BASIC",
        "title": "Meta Description Missing",
        "why": "A primary page should provide a basic search-result description even though search engines may rewrite it.",
        "solution": "Add a concise page-specific meta description that accurately describes the page and its customer purpose.",
    },
    18: {
        "level": "BASIC",
        "title": "Primary H1 Hierarchy Missing",
        "why": "A primary page should expose one clear main heading that communicates its topic to visitors and document structure.",
        "solution": "Add or correct one clear primary H1 that accurately represents the page's main purpose; keep supporting headings subordinate.",
    },
    22: {
        "level": "BASIC",
        "title": "Canonical URL Signal Missing",
        "why": "A canonical declaration is a basic indexing-control signal on modern production pages.",
        "solution": "Add a self-referencing or otherwise correct canonical URL in the document head and verify it resolves to the intended public page.",
    },
    24: {
        "level": "IMPORTANT",
        "title": "Robots.txt Foundation Invalid or Missing",
        "why": "Robots controls are basic crawl-management infrastructure and should not be accidentally absent or malformed.",
        "solution": "Publish a valid robots.txt at the site root, confirm intended crawl rules, and make sure important public sections are not blocked by mistake.",
    },
    31: {
        "level": "CRITICAL",
        "title": "Mobile Viewport Foundation Missing",
        "why": "A responsive mobile viewport is a basic requirement for modern mobile browsing, not an elite optimization.",
        "solution": "Add a valid viewport meta declaration and verify the primary pages render at device width without forced desktop scaling.",
    },
}

_FOUNDATION_LEVEL_ORDER = {"BASIC": 1, "IMPORTANT": 2, "CRITICAL": 3}

def build_foundation_omission_signal(
    checkpoints: List[Dict[str, Any]],
    scan_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return a separate basic-omission alert from *verified* foundation failures only.

    UNKNOWN and NOT_APPLICABLE never trigger the signal.  The result intentionally
    does not change checkpoint severity, score impact, or modeled revenue exposure.
    It exists to distinguish an elementary implementation omission from a large
    commercial leak.
    """
    scan = scan_data if isinstance(scan_data, dict) else {}
    omissions: List[Dict[str, Any]] = []
    by_id = {int(item.get("id") or 0): item for item in (checkpoints or []) if isinstance(item, dict)}
    observed_url = str(scan.get("final_url") or scan.get("url") or scan.get("domain") or "")

    for cp_id, meta in FOUNDATION_OMISSION_META.items():
        cp = by_id.get(cp_id)
        if not cp or str(cp.get("status") or "").upper() != FAIL:
            continue
        omissions.append({
            "checkpoint_id": cp_id,
            "rule_key": cp.get("rule_key"),
            "check": cp.get("check"),
            "classification": "FOUNDATIONAL_OMISSION",
            "level": meta["level"],
            "title": meta["title"],
            "why_it_matters": meta["why"],
            "recommended_change": meta["solution"],
            "observed_url": observed_url,
            "evidence": cp.get("evidence"),
            "source_note": cp.get("customer_note") or cp.get("reason") or "Verified public checkpoint failure.",
        })

    # Missing <title> is too basic to ignore, but checkpoint 20 intentionally treats
    # an absent title as UNKNOWN because it is a length heuristic.  Raise this
    # separate omission only when document/metadata evidence was actually verified.
    metadata_verified = bool(scan.get("metadata_evidence_status") == "verified" or scan.get("browser_loaded") or scan.get("static_html_verified"))
    if metadata_verified and not str(scan.get("title") or "").strip():
        omissions.append({
            "checkpoint_id": None,
            "rule_key": "title_missing_basic_omission",
            "check": "Primary Page Title Present",
            "classification": "FOUNDATIONAL_OMISSION",
            "level": "BASIC",
            "title": "Primary Page Title Missing",
            "why_it_matters": "A production page should have a meaningful document title before advanced search or conversion optimization.",
            "recommended_change": "Add a concise, page-specific <title> that identifies the business/page purpose and verify it in the rendered document head.",
            "observed_url": observed_url,
            "evidence": {"title": scan.get("title"), "metadata_evidence_status": scan.get("metadata_evidence_status")},
            "source_note": "The inspected document exposed no usable page title.",
        })

    omissions.sort(key=lambda item: (_FOUNDATION_LEVEL_ORDER.get(str(item.get("level") or "BASIC"), 0), -(int(item.get("checkpoint_id") or 999))), reverse=True)
    count = len(omissions)
    highest = max((str(item.get("level") or "BASIC") for item in omissions), key=lambda x: _FOUNDATION_LEVEL_ORDER.get(x, 0), default="NONE")
    if count == 0:
        density = "CLEAN"
    elif count == 1:
        density = "ISOLATED_OVERSIGHT"
    elif count <= 3:
        density = "FOUNDATION_ATTENTION_REQUIRED"
    else:
        density = "FOUNDATION_CONTROL_FAILURE"
    return {
        "triggered": bool(omissions),
        "count": count,
        "highest_level": highest,
        "density": density,
        "modal_title": "Critical Foundation Notice" if highest == "CRITICAL" else "Foundation Notice",
        "modal_message": (
            f"{count} verified basic website omission{'s' if count != 1 else ''} detected. Review these foundational items before advanced optimization."
            if count else "No verified basic foundation omissions detected."
        ),
        "public_modal_disclose_items": False,
        "report_section_available": bool(omissions),
        "omissions": omissions,
        "note": "This signal is separate from revenue severity and score impact. UNKNOWN and NOT_APPLICABLE checkpoints never trigger it.",
    }


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    if parsed is None or not math.isfinite(parsed):
        return None
    return parsed


def _safe_int(value: Any, default: int | None = None) -> int | None:
    parsed = _safe_float(value)
    return int(parsed) if parsed is not None else default


def _verified(*statuses: Any) -> bool:
    return any(str(value or "").lower() == "verified" for value in statuses)


def _unknown_reason(cp_id: int, scan: Dict[str, Any]) -> Dict[str, str]:
    """Explain why a checkpoint remains UNKNOWN without implying a hidden failure."""
    if cp_id == 29:
        return {"code": "FIELD_DATA_UNAVAILABLE", "customer_note": "Real-user INP requires eligible field telemetry (for example CrUX). No field value was available, so this check is unscored."}
    if cp_id == 36:
        return {"code": "PUBLIC_PROVENANCE_LIMIT", "customer_note": "Image originality/provenance cannot always be proven from public markup alone. The scanner does not guess."}
    if cp_id == 49:
        return {"code": "JURISDICTION_CONTEXT_REQUIRED", "customer_note": "Cookie-consent requirements depend on jurisdiction, tracking behavior and consent configuration. Absence is not automatically treated as failure."}
    if cp_id == 50:
        return {"code": "SAFE_SUBMISSION_LIMIT", "customer_note": "The scanner avoids destructive or customer-facing live submissions. Form delivery remains unscored unless safely verifiable."}
    if cp_id in {28, 30, 32, 33}:
        return {"code": "GOOGLE_TELEMETRY_UNAVAILABLE", "customer_note": "The relevant Google/Lighthouse metric was unavailable in this scan. No deduction is applied."}
    return {"code": "PUBLIC_VERIFICATION_GAP", "customer_note": "This signal could not be independently verified from the public evidence available during the scan. It is not scored as a failure."}


def build_50_checkpoints(scan_data: Dict[str, Any], audit_data: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Build 50 evidence checkpoints with strict business/context applicability.

    V7 journey/context rules:
    - 22 low-weight common foundation checks apply across sites when evidence exists.
    - 28 adaptive architectural checks are enabled by the observed customer journey + context tags.
    - Legacy industry/business-type selections are weak hints only; no subtype taxonomy controls scoring.
    - High-impact confirmation supports CONFIRMED, CORROBORATED (reduced-confidence) and unresolved states.

    Authenticity rules:
    - Optional enhancements become NOT_APPLICABLE when absent instead of fake failures.
    - Exact SEO character counts are treated as broad heuristics, not universal laws.
    - Privacy/Terms requirements adapt to actual data/commerce context.
    - End-to-end form delivery is never claimed as PASS without a safe submission; visible public
      error states can still be verified as FAIL passively.
    """
    scan = scan_data if isinstance(scan_data, dict) else {}
    audit = audit_data if isinstance(audit_data, dict) else {}
    profile_raw = audit.get("business_profile") or scan.get("business_profile") or {}
    profile = profile_raw if isinstance(profile_raw, dict) else {}

    architecture_raw = audit.get("architecture_profile") or scan.get("architecture_profile") or profile
    architecture = architecture_raw if isinstance(architecture_raw, dict) and architecture_raw.get("journey_model") else infer_architecture_profile(scan, audit.get("business_type") or "auto")
    journey = str(architecture.get("journey_model") or "general")
    context_tags = {str(x) for x in (architecture.get("context_tags") or []) if x}
    provisional_model = bool(architecture.get("provisional"))
    regulated = "regulated_high_trust" in context_tags
    local_context = "local_location_dependent" in context_tags
    commerce_context = "commerce_payment" in context_tags or journey == "direct_purchase"
    sensitive_context = "sensitive_data" in context_tags
    enterprise_context = "enterprise_considered_purchase" in context_tags
    hospitality_context = "hospitality_event" in context_tags

    quality_raw = scan.get("scan_quality")
    quality = quality_raw if isinstance(quality_raw, dict) else {}
    browser_verified = bool(scan.get("browser_loaded")) and not bool(quality.get("bot_challenge_suspected"))
    static_verified = bool(scan.get("static_html_verified"))
    document_verified = browser_verified or static_verified
    metadata_verified = _verified(scan.get("metadata_evidence_status")) or document_verified
    image_verified = _verified(scan.get("image_evidence_status")) or browser_verified
    tracking_verified = _verified(scan.get("tracking_evidence_status")) or document_verified
    forms_verified = _verified(scan.get("form_evidence_status")) or document_verified
    content_verified = _verified(scan.get("content_signal_status")) or document_verified
    technical_verified = _verified(scan.get("technical_evidence_status")) or document_verified
    psi_available = scan.get("pagespeed_api_status") == "success"
    ai_available = scan.get("ai_spectrum_status") == "heuristic" and _safe_float(scan.get("ai_spectrum_pct")) is not None

    checkpoints: List[Dict[str, Any]] = []

    def add(cp_id: int, name: str, status: str, category: str, evidence: Any = None, reason: str = "") -> None:
        meta = CHECKPOINT_RULE_META.get(cp_id, {})
        dedicated = DEDICATED_CHECKPOINT_RULES.get(cp_id)
        rule_key = dedicated or meta.get("rule_key") or f"checkpoint_{cp_id:02d}"
        confirmation_root = scan.get("high_impact_confirmation") if isinstance(scan.get("high_impact_confirmation"), dict) else {}
        confirmation_results = confirmation_root.get("results") if isinstance(confirmation_root.get("results"), dict) else {}
        confirmation_record = confirmation_results.get(rule_key) if isinstance(confirmation_results.get(rule_key), dict) else {}
        confirmation_status = str(confirmation_record.get("status") or "").upper()
        if status == FAIL and confirmation_record and confirmation_status not in {"CONFIRMED", "CORROBORATED"}:
            status = UNKNOWN
            confirmation_note = "This first-pass failure was selected for high-impact confirmation but did not survive a sufficient independent recheck, so it is UNKNOWN and unscored."
            reason = (reason + " " + confirmation_note).strip()
        elif status == FAIL and confirmation_status == "CORROBORATED":
            reason = (reason + " The exact public signal was independently corroborated but not fully reproduced in Chromium; scoring is reduced by the scorer guardrail.").strip()
        unknown_meta = _unknown_reason(cp_id, scan) if status == UNKNOWN else {"code": "", "customer_note": ""}
        if status == UNKNOWN and confirmation_record:
            unknown_meta = {"code": "HIGH_IMPACT_CONFIRMATION_UNRESOLVED", "customer_note": reason or "Second-pass confirmation did not support a confident failure; no deduction is applied."}
        checkpoints.append(
            {
                "id": cp_id,
                "check": name,
                "status": status,
                "category": category,
                "evidence": evidence,
                "reason": reason,
                "business_type": journey,
                "business_subtype": "",
                "journey_model": journey,
                "context_tags": sorted(context_tags),
                "analysis_layer": common_vs_architectural(cp_id),
                "rule_key": rule_key,
                "family": meta.get("family") or dedicated or f"checkpoint_{cp_id:02d}",
                "report_weight": _safe_float(meta.get("weight")) or 0.0,
                "severity_factor": _safe_float(meta.get("severity")) or 0.0,
                "dedicated_rule": bool(dedicated),
                "unknown_reason_code": unknown_meta["code"],
                "customer_note": reason or unknown_meta["customer_note"],
                "confirmation": confirmation_record,
            }
        )

    def bool_status(value: Any, verified: bool = True) -> str:
        if not verified or value is None:
            return UNKNOWN
        return PASS if bool(value) else FAIL

    def optional_presence(value: Any, verified: bool, note: str) -> tuple[str, str]:
        if verified and value is True:
            return PASS, note
        return NA, note

    final_url = str(scan.get("final_url") or scan.get("url") or "").lower()
    product_context = bool(
        scan.get("add_to_cart_visible")
        or scan.get("checkout_context_detected")
        or any(token in final_url for token in ("/product/", "/products/", "/item/", "/p/"))
    )
    call_relevant = bool(local_context and journey in {"lead_quote", "appointment_consultation", "reservation_event"})
    sticky_relevant = bool(
        (journey in {"appointment_consultation", "reservation_event"} and (local_context or hospitality_context))
        or (journey == "lead_quote" and local_context)
        or (journey == "direct_purchase" and product_context)
    )
    location_relevant = bool(local_context)
    credential_required = bool(regulated)
    credential_relevant = bool(regulated or enterprise_context)
    review_required = bool(hospitality_context or (local_context and not enterprise_context))
    team_required = bool(regulated or enterprise_context or journey in {"lead_quote", "appointment_consultation", "demo_sales"})
    broad_proof_required = bool(journey != "general")

    # Trust & Conversion 1-15
    add(1, "SSL Certificate Active", bool_status(scan.get("has_ssl"), bool(scan.get("is_reachable"))), "trust_conversion", scan.get("final_url"))
    add(2, "HTTPS Redirect Enforced", bool_status(scan.get("https_redirect_enforced")), "trust_conversion", scan.get("redirect_chain"))

    if call_relevant:
        add(3, "Mobile Click-to-Call Present", bool_status(scan.get("click_to_call_present"), scan.get("click_to_call_status") == "verified"), "trust_conversion", reason="Required only when the inferred customer journey and local context make calling a normal primary/supporting conversion path.")
    else:
        status, note = optional_presence(scan.get("click_to_call_present"), scan.get("click_to_call_status") == "verified", "Calling is optional for this customer journey/context; absence is not scored as a failure.")
        add(3, "Mobile Click-to-Call Present", status, "trust_conversion", reason=note)

    if sticky_relevant:
        add(4, "Persistent Mobile Primary Action", bool_status(scan.get("mobile_sticky_cta_present"), scan.get("mobile_cta_status") == "verified"), "trust_conversion", scan.get("mobile_cta_types"), "A persistent action is scored only where mobile direct-action continuity is central to the inferred journey; direct purchase requires product/checkout context.")
    else:
        status, note = optional_presence(scan.get("mobile_sticky_cta_present"), scan.get("mobile_cta_status") == "verified", "A sticky CTA is an optional enhancement for this customer journey/context and is not required for readiness.")
        add(4, "Persistent Mobile Primary Action", status, "trust_conversion", scan.get("mobile_cta_types"), note)

    add(5, "Form Action / SPA Structure Valid", NA if scan.get("forms_present") is False else bool_status(scan.get("form_action_valid"), forms_verified), "trust_conversion")

    measurement_present = scan.get("measurement_layer_present")
    if measurement_present is None:
        measurement_present = bool(
            scan.get("has_ga4") or scan.get("has_meta_pixel") or scan.get("has_qualitative_analytics")
            or scan.get("has_other_measurement")
        )
    if provisional_model and not measurement_present:
        add(6, "Analytics / Measurement Layer Present", UNKNOWN if tracking_verified else UNKNOWN, "trust_conversion", scan.get("measurement_platforms"), "Journey model is provisional; absence of a common measurement layer is retained as unscored evidence rather than a business-specific failure.")
    else:
        add(6, "Analytics / Measurement Layer Present", bool_status(measurement_present, tracking_verified), "trust_conversion", scan.get("measurement_platforms"))

    if provisional_model:
        primary_status = PASS if scan.get("mobile_primary_cta_present") is True and scan.get("mobile_cta_status") == "verified" else UNKNOWN
        add(7, "Primary Mobile Conversion Action Visible", primary_status, "trust_conversion", scan.get("mobile_cta_types"), "The customer journey is provisional, so a missing action is not failed until the primary revenue path is resolved.")
    else:
        add(7, "Primary Mobile Conversion Action Visible", bool_status(scan.get("mobile_primary_cta_present"), scan.get("mobile_cta_status") == "verified"), "trust_conversion", scan.get("mobile_cta_types"))

    if call_relevant:
        add(8, "Phone Number Visible", bool_status(scan.get("phone_number_visible"), scan.get("phone_visibility_status") == "verified"), "trust_conversion", scan.get("detected_phone_numbers"), "Phone visibility is required only where calling is a normal customer path.")
    else:
        status, note = optional_presence(scan.get("phone_number_visible"), scan.get("phone_visibility_status") == "verified", "Phone contact is optional for this customer journey/context; absence is not scored.")
        add(8, "Phone Number Visible", status, "trust_conversion", scan.get("detected_phone_numbers"), note)

    add(9, "Address / Location Signal Visible", NA if not location_relevant else bool_status(scan.get("address_location_visible"), content_verified), "trust_conversion", reason="Location is required only when public evidence indicates a location-dependent customer journey/context.")

    credential_value = bool(scan.get("credential_signals_present") or scan.get("trust_badges_present"))
    if credential_required:
        add(10, "Professional / Regulatory Credential Signals", bool_status(credential_value, content_verified), "trust_conversion", scan.get("credential_signal_types"), "Credentials are required only when the public evidence indicates a regulated/high-trust context.")
    elif credential_relevant:
        status, note = optional_presence(credential_value, content_verified, "Professional credentials may be commercially relevant in this context, but absence is not automatically failed because licensing/registration requirements vary by service and jurisdiction.")
        add(10, "Professional / Regulatory Credential Signals", status, "trust_conversion", scan.get("credential_signal_types"), note)
    else:
        status, note = optional_presence(credential_value, content_verified, "Formal credentials are not universally required for this customer journey/context; real credentials count positively when present.")
        add(10, "Professional / Regulatory Credential Signals", status, "trust_conversion", scan.get("credential_signal_types"), note)

    if review_required:
        add(11, "Testimonials / Reviews Visible", bool_status(scan.get("reviews_visible"), content_verified), "trust_conversion", reason="Review/testimonial proof is required only when local or hospitality/event context makes public reputation a normal decision input.")
    else:
        status, note = optional_presence(scan.get("reviews_visible"), content_verified, "Reviews are not the required proof format for this customer journey/context; case studies, credentials or other proof can satisfy trust instead.")
        add(11, "Testimonials / Reviews Visible", status, "trust_conversion", reason=note)

    if commerce_context and journey == "direct_purchase":
        refund_value = bool(scan.get("return_policy_linked") or scan.get("guarantee_refund_present"))
        add(12, "Return / Refund Policy Discoverable", bool_status(refund_value, content_verified), "trust_conversion", {"return_policy_linked": scan.get("return_policy_linked"), "guarantee_signal": scan.get("guarantee_refund_present")}, "Refund/return reassurance is a commerce requirement; it is not imposed on clinics or ordinary service businesses.")
    else:
        add(12, "Return / Refund Policy Discoverable", NA, "trust_conversion", reason="Not a universal requirement for this customer journey/context.")

    add(13, "Team / About Identity Path Linked", bool_status(scan.get("about_team_linked"), content_verified) if team_required else (PASS if scan.get("about_team_linked") is True and content_verified else NA), "trust_conversion", reason="Identity/team transparency is scored when the observed journey/context makes organizational identity part of the decision; optional elsewhere.")

    proof_value = bool(scan.get("social_proof_present") or scan.get("reviews_visible") or scan.get("credential_signals_present") or scan.get("case_studies_portfolio_present"))
    add(14, "Relevant Social / Customer Proof Active", bool_status(proof_value, content_verified) if broad_proof_required else (PASS if proof_value and content_verified else NA), "trust_conversion", reason="Proof can be reviews, credentials, case studies or other verifiable customer/business evidence; the required format varies by journey/context.")

    instant_channel_present = bool(scan.get("live_chat_present") or scan.get("whatsapp_present"))
    add(15, "Live Chat / WhatsApp Query Channel", PASS if instant_channel_present and document_verified else NA, "trust_conversion", reason="Optional conversion enhancement; absence alone is not a leak.")

    # SEO & Technical 16-35. These are broad technical/search fundamentals; scoring weights remain modest.
    meta = str(scan.get("meta_description") or "")
    title = str(scan.get("title") or "")
    h1_status = str(scan.get("h1_status") or "unknown").lower()
    h1_tags_raw = scan.get("h1_tags")
    h1_tags = h1_tags_raw if isinstance(h1_tags_raw, list) else []
    perf = _safe_float(scan.get("performance_score"))
    seo = _safe_float(scan.get("google_seo_score"))
    add(16, "Meta Description Present", bool_status(bool(meta), metadata_verified), "seo_technical")
    add(17, "Meta Description Length Reasonable (70-180 chars)", UNKNOWN if not metadata_verified or not meta else (PASS if 70 <= len(meta) <= 180 else FAIL), "seo_technical", len(meta) if meta else None, "Broad heuristic range only; search engines may rewrite snippets and no exact character count guarantees performance.")
    add(18, "Clear Primary H1 Hierarchy", UNKNOWN if h1_status == "unknown" else (PASS if h1_status == "present" and len(h1_tags) == 1 else FAIL), "seo_technical", h1_tags)
    h1_rel = str(scan.get("h1_relevance_status") or UNKNOWN).upper()
    add(19, "H1 Supports Primary Topic", h1_rel if h1_rel in {PASS, FAIL, UNKNOWN} else UNKNOWN, "seo_technical")
    add(20, "Title Tag Length Reasonable (20-65 chars)", UNKNOWN if not metadata_verified or not title else (PASS if 20 <= len(title) <= 65 else FAIL), "seo_technical", len(title) if title else None, "Broad readability/search heuristic; not a universal ranking cutoff.")
    add(21, "Schema.org Structured Data", bool_status(scan.get("schema_present"), technical_verified), "seo_technical", scan.get("schema_types"))
    add(22, "Canonical URL Set", bool_status(scan.get("canonical_present"), technical_verified), "seo_technical")
    add(23, "XML Sitemap Present", bool_status(scan.get("sitemap_present")), "seo_technical", scan.get("sitemap_status_code"))
    add(24, "Robots.txt Valid", bool_status(scan.get("robots_valid")), "seo_technical", scan.get("robots_status_code"))
    add(25, "Google PageSpeed Performance > 60", UNKNOWN if not psi_available or perf is None else (PASS if perf >= 60 else FAIL), "seo_technical", perf)
    add(26, "Google PageSpeed Performance > 90", UNKNOWN if not psi_available or perf is None else (PASS if perf >= 90 else FAIL), "seo_technical", perf, "90+ is an elite optimization target; failure here is deduplicated behind more serious performance evidence.")
    add(27, "Google SEO Score > 80", UNKNOWN if not psi_available or seo is None else (PASS if seo >= 80 else FAIL), "seo_technical", seo)

    lcp = _safe_float(scan.get("crux_lcp_ms") if scan.get("crux_available") else scan.get("psi_lcp_ms"))
    inp = _safe_float(scan.get("crux_inp_ms") if scan.get("crux_available") else None)
    cls_value = _safe_float(scan.get("crux_cls") if scan.get("crux_available") else scan.get("psi_cls"))
    add(28, "LCP (Largest Contentful Paint) ≤ 2.5s", UNKNOWN if lcp is None else (PASS if lcp <= 2500 else FAIL), "seo_technical", lcp)
    add(29, "INP (Interaction to Next Paint) ≤ 200ms", UNKNOWN if inp is None else (PASS if inp <= 200 else FAIL), "seo_technical", inp)
    add(30, "CLS (Cumulative Layout Shift) ≤ 0.1", UNKNOWN if cls_value is None else (PASS if cls_value <= 0.1 else FAIL), "seo_technical", cls_value)
    add(31, "Mobile Viewport Configured", bool_status(scan.get("mobile_viewport_configured"), technical_verified), "seo_technical")

    tap_count_raw = scan.get("psi_tap_targets_flagged")
    tap_count = _safe_int(tap_count_raw)
    if tap_count is None:
        tap_list = scan.get("tap_targets_flagged")
        tap_status = UNKNOWN if not isinstance(tap_list, list) else (FAIL if len(tap_list) > 0 else (PASS if psi_available else UNKNOWN))
    else:
        tap_status = PASS if tap_count == 0 else FAIL
    add(32, "Tap Targets Properly Sized", tap_status, "seo_technical", tap_count if tap_count is not None else scan.get("tap_targets_flagged"))

    blocking = _safe_int(scan.get("psi_render_blocking_count"))
    add(33, "No Material Render-Blocking Resources", UNKNOWN if blocking is None else (PASS if blocking == 0 else FAIL), "seo_technical", blocking)
    missing_alt = _safe_int(scan.get("missing_alt_images"))
    add(34, "Images Have Accessibility Text", UNKNOWN if not image_verified or missing_alt is None else (PASS if missing_alt == 0 else FAIL), "seo_technical", {"missing": missing_alt, "total": scan.get("total_images")})
    lazy_status = str(scan.get("lazy_loading_status") or UNKNOWN).upper()
    add(35, "Lazy Loading on Relevant Images", lazy_status if lazy_status in {PASS, FAIL, UNKNOWN, NA} else UNKNOWN, "seo_technical", scan.get("lazy_image_count"))

    # Content / trust-support 36-50. Optional content formats are never forced onto every customer journey.
    add(36, "Original Photography (Not Stock)", scan.get("custom_photography_status") if scan.get("custom_photography_status") in {PASS, FAIL, UNKNOWN, NA} else UNKNOWN, "content_eeat", reason="Scanner records same-origin imagery as a signal but does not claim provenance without proof.")

    if scan.get("author_bylines_present") is True and content_verified:
        add(37, "Author Attribution on Editorial Content", PASS, "content_eeat")
    else:
        add(37, "Author Attribution on Editorial Content", NA, "content_eeat", reason="No article-level editorial page was safely verified in this bounded scan; absence is not treated as a site-wide failure.")

    if scan.get("publication_dates_visible") is True and content_verified:
        add(38, "Publication / Updated Dates on Editorial Content", PASS, "content_eeat")
    else:
        add(38, "Publication / Updated Dates on Editorial Content", NA, "content_eeat", reason="No article-level editorial page was safely verified in this bounded scan; absence is not treated as a site-wide failure.")

    word_count = _safe_int(scan.get("visible_word_count"), 0) or 0
    content_depth_relevant = bool(regulated or enterprise_context or journey in {"demo_sales"} or (journey == "lead_quote" and enterprise_context))
    fail_below = 90 if enterprise_context or journey == "demo_sales" else 110
    pass_at = 150 if enterprise_context or journey == "demo_sales" else 180
    if not content_depth_relevant:
        content_depth_status = NA
    elif not document_verified:
        content_depth_status = UNKNOWN
    elif word_count < fail_below:
        content_depth_status = FAIL
    elif word_count >= pass_at:
        content_depth_status = PASS
    else:
        content_depth_status = UNKNOWN
    add(39, "Primary Page Not Extremely Thin", content_depth_status, "content_eeat", {"visible_word_count": word_count, "fail_below": fail_below, "pass_at_or_above": pass_at}, "Conservative Trilloka heuristic: only extremely thin primary-page content is failed; intermediate lengths remain unscored rather than padded to a word-count target.")

    ai_pct = _safe_float(scan.get("ai_spectrum_pct"))
    add(40, "AI / Template Pattern Index Measured", PASS if ai_available else UNKNOWN, "content_eeat", ai_pct, "Measurement availability only; this checkpoint does not claim AI authorship and does not fail based on a low/high value.")
    add(41, "AI / Template Pattern Index Below High-Risk Threshold (<60)", UNKNOWN if not ai_available or ai_pct is None else (PASS if ai_pct < 60 else FAIL), "content_eeat", ai_pct)
    ai_flags = scan.get("ai_flags") if isinstance(scan.get("ai_flags"), dict) else {}
    generic = ai_flags.get("generic_headline")
    add(42, "No Generic Template Headlines", UNKNOWN if generic is None or not document_verified else (PASS if not bool(generic) else FAIL), "content_eeat")
    unlinked = _safe_int(ai_flags.get("unlinked_forms"))
    add(43, "No Structurally Unlinked Forms", NA if scan.get("forms_present") is False else (UNKNOWN if unlinked is None else (PASS if unlinked == 0 else FAIL)), "content_eeat", unlinked)

    if scan.get("faq_present") is True and content_verified:
        add(44, "FAQ / Objection-Handling Support", PASS, "content_eeat")
    else:
        add(44, "FAQ / Objection-Handling Support", NA, "content_eeat", reason="FAQ format is optional; absence is not scored unless future evidence shows a business-specific objection gap.")

    proof_of_work_relevant = bool(enterprise_context or journey == "demo_sales")
    proof_of_work = bool(scan.get("case_studies_portfolio_present") or scan.get("reviews_visible") or scan.get("social_proof_present"))
    add(45, "Customer / Proof-of-Work Evidence", bool_status(proof_of_work, content_verified) if proof_of_work_relevant else NA, "content_eeat", {"case_studies": scan.get("case_studies_portfolio_present"), "social_proof": scan.get("social_proof_present")}, "Proof-of-work/customer evidence is required only for enterprise/considered-purchase or demo/sales journeys; ordinary local and regulated services are not forced to publish case studies.")

    if scan.get("blog_present") is True and content_verified:
        add(46, "Blog / Content Hub Available", PASS, "content_eeat")
    else:
        add(46, "Blog / Content Hub Available", NA, "content_eeat", reason="A content hub is optional and is not treated as a conversion failure merely because the business does not publish one.")

    social_present = bool(scan.get("social_links_present"))
    add(47, "Social Media Links Active", PASS if social_present and content_verified else NA, "content_eeat", reason="Optional identity/discovery channel; absence alone is not a conversion failure.")

    tracking_or_data = bool(
        scan.get("forms_present") or measurement_present or scan.get("has_meta_pixel")
        or scan.get("retargeting_pixel_installed") or scan.get("has_ga4")
    )
    privacy_required = bool(tracking_or_data or commerce_context or regulated or sensitive_context)
    terms_required = bool(commerce_context and (journey == "direct_purchase" or scan.get("checkout_context_detected")))
    if not privacy_required:
        add(48, "Required Privacy / Terms Policy Links", NA, "content_eeat", reason="No verified data/commerce context made a policy link mandatory for scoring in this public scan.")
    elif terms_required:
        policy_ok = bool(scan.get("privacy_policy_linked") and scan.get("terms_linked"))
        add(48, "Privacy & Terms Policies Linked", bool_status(policy_ok, content_verified), "content_eeat", {"requirement": "privacy_and_terms", "privacy_policy_linked": scan.get("privacy_policy_linked"), "terms_linked": scan.get("terms_linked")}, "Both policies are expected only for verified transaction/account/checkout contexts.")
    else:
        policy_ok = bool(scan.get("privacy_policy_linked"))
        add(48, "Privacy Policy Linked for Data Collection", bool_status(policy_ok, content_verified), "content_eeat", {"requirement": "privacy_only", "privacy_policy_linked": scan.get("privacy_policy_linked"), "terms_linked": scan.get("terms_linked")}, "A Privacy policy is required where forms/tracking, regulated context, commerce, or sensitive-data evidence makes it applicable; Terms are not forced outside transaction/account contexts.")

    cookie = scan.get("cookie_banner_present")
    tracking_or_cookie_context = bool(
        measurement_present or scan.get("has_meta_pixel") or scan.get("has_qualitative_analytics")
        or scan.get("retargeting_pixel_installed") or scan.get("consent_required") is True
    )
    if cookie is True:
        cookie_status = PASS
        cookie_reason = "Consent/preference interface detected."
    elif scan.get("consent_required") is False or not tracking_or_cookie_context:
        cookie_status = NA
        cookie_reason = "No verified consent-requiring context was established from the public scan; absence is not treated as a leak."
    else:
        cookie_status = UNKNOWN
        cookie_reason = "Tracking/cookie context exists, but jurisdiction and consent requirements cannot be determined from the public page alone; no deduction is applied."
    add(49, "Cookie Consent / Preference Interface", cookie_status, "content_eeat", scan.get("cookie_banner_present"), cookie_reason)

    conversion_errors = list(scan.get("conversion_error_signals") or []) if isinstance(scan.get("conversion_error_signals"), list) else []
    if conversion_errors:
        completion_status = FAIL
        completion_reason = "A customer-visible error state was passively observed on a conversion page. No form was submitted and no customer data was mutated."
    elif scan.get("forms_present") or (_safe_int(scan.get("journey_pages_verified"), 0) or 0) > 0:
        completion_status = UNKNOWN
        completion_reason = "No customer-visible error was observed, but end-to-end delivery/completion is not claimed because the scanner does not submit live customer forms or orders."
    else:
        completion_status = NA
        completion_reason = "No form/booking conversion path was verified in the bounded public evidence sample."
    add(50, "Customer Conversion Path Completion / Error State", completion_status, "content_eeat", {
        "error_signals": conversion_errors[:6],
        "form_payload_fired": scan.get("form_payload_fired"),
        "browser_journey_url": scan.get("browser_journey_url"),
        "browser_journey_rendered": scan.get("browser_journey_rendered"),
        "external_booking_provider_health": scan.get("external_booking_provider_health") or {},
    }, completion_reason)

    return checkpoints

def checkpoint_summary(checkpoints: List[Dict[str, Any]]) -> Dict[str, Any]:
    def summarize(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        counts = {PASS: 0, FAIL: 0, UNKNOWN: 0, NA: 0}
        unknown_breakdown: Dict[str, int] = {}
        for checkpoint in items:
            status = checkpoint.get("status")
            if status in counts:
                counts[status] += 1
            if status == UNKNOWN:
                code = str(checkpoint.get("unknown_reason_code") or "PUBLIC_VERIFICATION_GAP")
                unknown_breakdown[code] = unknown_breakdown.get(code, 0) + 1
        applicable = max(0, len(items) - counts[NA])
        verified = counts[PASS] + counts[FAIL]
        return {
            "verified": verified, "passed": counts[PASS], "failed": counts[FAIL],
            "unknown": counts[UNKNOWN], "not_applicable": counts[NA], "total": len(items),
            "applicable": applicable,
            "verified_applicable_ratio": round(verified / applicable, 3) if applicable else 0.0,
            "unknown_breakdown": unknown_breakdown,
        }

    overall = summarize(checkpoints)
    layers = {
        "common_foundation": summarize([cp for cp in checkpoints if cp.get("analysis_layer") == "common_foundation"]),
        "adaptive_architecture": summarize([cp for cp in checkpoints if cp.get("analysis_layer") != "common_foundation"]),
    }
    overall["layers"] = layers
    overall["layer_definition"] = {
        "common_foundation": "Universal HTTPS, SEO/search structure, performance, mobile and accessibility foundations. Visible to every scan and deliberately lower-weight in Revenue Readiness.",
        "adaptive_architecture": "Customer-journey and context-sensitive conversion, trust, policy, proof and completion architecture.",
    }
    return overall
