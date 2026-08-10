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

from typing import Any, Dict, List

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
NA = "NOT_APPLICABLE"


# Report/scoring metadata for failed checkpoints that are not already represented
# by one of the scorer's dedicated high-impact rules.
CHECKPOINT_RULE_META: Dict[int, Dict[str, Any]] = {
    2: {"rule_key": "https_redirect", "family": "foundation_security", "weight": 1.4, "severity": 0.45},
    6: {"rule_key": "retargeting_telemetry", "family": "measurement", "weight": 1.5, "severity": 0.40},
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
    35: {"rule_key": "lazy_loading_gap", "family": "performance", "weight": 1.0, "severity": 0.30},
    37: {"rule_key": "author_bylines_missing", "family": "content_eeat", "weight": 1.1, "severity": 0.35},
    38: {"rule_key": "publication_dates_missing", "family": "content_eeat", "weight": 0.9, "severity": 0.30},
    39: {"rule_key": "thin_visible_content", "family": "content_depth", "weight": 1.6, "severity": 0.45},
    42: {"rule_key": "generic_headline", "family": "content_distinctiveness", "weight": 1.5, "severity": 0.45},
    43: {"rule_key": "unlinked_form_structure", "family": "conversion_execution", "weight": 2.4, "severity": 0.65},
    44: {"rule_key": "faq_missing", "family": "content_support", "weight": 1.2, "severity": 0.35},
    45: {"rule_key": "case_studies_missing", "family": "trust_proof", "weight": 1.4, "severity": 0.40},
    46: {"rule_key": "content_hub_missing", "family": "content_depth", "weight": 1.1, "severity": 0.30},
    47: {"rule_key": "social_links_missing", "family": "trust_identity", "weight": 0.8, "severity": 0.25},
    48: {"rule_key": "privacy_terms_missing", "family": "trust_policy", "weight": 1.8, "severity": 0.50},
}

# Dedicated scorer rules that already represent these checkpoint failures.
DEDICATED_CHECKPOINT_RULES = {
    1: "unsecured_ssl",
    3: "click_to_call",
    4: "mobile_sticky_cta",
    5: "form_architecture",
    6: "measurement_telemetry",
    18: "diluted_h1",
    28: "core_web_vitals",
    29: "core_web_vitals",
    30: "core_web_vitals",
    34: "missing_alt_images",
    40: "ai_template_similarity",
    41: "ai_template_similarity",
    43: "form_architecture",
}


def _verified(*statuses: Any) -> bool:
    return any(str(value or "").lower() == "verified" for value in statuses)


def build_50_checkpoints(scan_data: Dict[str, Any], audit_data: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    scan = scan_data or {}
    audit = audit_data or {}
    profile = audit.get("business_profile") or scan.get("business_profile") or {}
    vertical = str(profile.get("vertical") or audit.get("business_type") or "general").lower()
    applicability_vertical = str(profile.get("inferred_subtype") or vertical).lower()

    quality = scan.get("scan_quality") or {}
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
    ai_available = scan.get("ai_spectrum_status") == "heuristic" and scan.get("ai_spectrum_pct") is not None

    checkpoints: List[Dict[str, Any]] = []

    def add(cp_id: int, name: str, status: str, category: str, evidence: Any = None, reason: str = "") -> None:
        meta = CHECKPOINT_RULE_META.get(cp_id, {})
        dedicated = DEDICATED_CHECKPOINT_RULES.get(cp_id)
        checkpoints.append(
            {
                "id": cp_id,
                "check": name,
                "status": status,
                "category": category,
                "evidence": evidence,
                "reason": reason,
                "rule_key": dedicated or meta.get("rule_key") or f"checkpoint_{cp_id:02d}",
                "family": meta.get("family") or dedicated or f"checkpoint_{cp_id:02d}",
                "report_weight": float(meta.get("weight") or 0.0),
                "severity_factor": float(meta.get("severity") or 0.0),
                "dedicated_rule": bool(dedicated),
            }
        )

    def bool_status(value: Any, verified: bool = True) -> str:
        if not verified or value is None:
            return UNKNOWN
        return PASS if bool(value) else FAIL

    # Trust & Conversion 1-15
    add(1, "SSL Certificate Active", bool_status(scan.get("has_ssl"), bool(scan.get("is_reachable"))), "trust_conversion", scan.get("final_url"))
    add(2, "HTTPS Redirect Enforced", bool_status(scan.get("https_redirect_enforced")), "trust_conversion", scan.get("redirect_chain"))
    add(3, "Mobile Click-to-Call Present", bool_status(scan.get("click_to_call_present"), scan.get("click_to_call_status") == "verified"), "trust_conversion")
    add(4, "Mobile Sticky CTA Visible", bool_status(scan.get("mobile_sticky_cta_present"), scan.get("mobile_cta_status") == "verified"), "trust_conversion", scan.get("mobile_cta_types"))
    add(5, "Form Action / SPA Structure Valid", NA if scan.get("forms_present") is False else bool_status(scan.get("form_action_valid"), forms_verified), "trust_conversion")
    measurement_present = bool(scan.get("has_ga4") or scan.get("has_meta_pixel") or scan.get("has_qualitative_analytics"))
    add(6, "Analytics / Measurement Layer Present", bool_status(measurement_present, tracking_verified), "trust_conversion")
    add(7, "Custom Photography Used", scan.get("custom_photography_status") if scan.get("custom_photography_status") in {PASS, FAIL, UNKNOWN, NA} else UNKNOWN, "trust_conversion", {"same_origin_signal": scan.get("custom_photography_signal")}, "Original-vs-stock cannot always be proven from markup alone")
    add(8, "Phone Number Visible", bool_status(scan.get("phone_number_visible"), scan.get("phone_visibility_status") == "verified"), "trust_conversion", scan.get("detected_phone_numbers"))
    location_relevant = applicability_vertical not in {"ecommerce", "saas"}
    add(9, "Address / Location Signal Visible", NA if not location_relevant else bool_status(scan.get("address_location_visible"), content_verified), "trust_conversion")
    credential_relevant = applicability_vertical in {"legal", "medspa", "local_service", "professional_service", "ecommerce"}
    add(10, "Trust Badges / Credential Signals Present", NA if not credential_relevant else bool_status(scan.get("trust_badges_present"), content_verified), "trust_conversion")
    add(11, "Testimonials / Reviews Visible", bool_status(scan.get("reviews_visible"), content_verified), "trust_conversion")

    # Applicability is business-context aware. The scanner still inspects every signal, but
    # optional/irrelevant features do not become fake conversion failures.
    guarantee_relevant = applicability_vertical in {"ecommerce", "medspa", "local_service"}
    add(12, "Guarantee / Refund Policy Clear", bool_status(scan.get("guarantee_refund_present"), content_verified) if guarantee_relevant else NA, "trust_conversion")
    add(13, "Team / About Page Linked", bool_status(scan.get("about_team_linked"), content_verified), "trust_conversion")
    add(14, "Social Proof Signals Active", bool_status(scan.get("social_proof_present"), content_verified), "trust_conversion")
    instant_channel_present = bool(scan.get("live_chat_present") or scan.get("whatsapp_present"))
    add(15, "Live Chat / WhatsApp Query Channel", PASS if instant_channel_present and document_verified else NA, "trust_conversion", reason="Optional conversion enhancement; absence alone is not a leak")

    # SEO & Technical 16-35
    meta = str(scan.get("meta_description") or "")
    title = str(scan.get("title") or "")
    h1_status = str(scan.get("h1_status") or "unknown").lower()
    h1_tags = scan.get("h1_tags") or []
    perf = scan.get("performance_score")
    seo = scan.get("google_seo_score")
    add(16, "Meta Description Present", bool_status(bool(meta), metadata_verified), "seo_technical")
    add(17, "Meta Description Length Optimal (120-158 chars)", UNKNOWN if not metadata_verified or not meta else (PASS if 120 <= len(meta) <= 158 else FAIL), "seo_technical", len(meta) if meta else None)
    add(18, "Single H1 Tag Per Page", UNKNOWN if h1_status == "unknown" else (PASS if h1_status == "present" and len(h1_tags) == 1 else FAIL), "seo_technical", h1_tags)
    h1_rel = str(scan.get("h1_relevance_status") or UNKNOWN).upper()
    add(19, "H1 Supports Primary Topic", h1_rel if h1_rel in {PASS, FAIL, UNKNOWN} else UNKNOWN, "seo_technical")
    add(20, "Title Tag Optimal Length (50-60 chars)", UNKNOWN if not metadata_verified or not title else (PASS if 50 <= len(title) <= 60 else FAIL), "seo_technical", len(title) if title else None)
    add(21, "Schema.org Structured Data", bool_status(scan.get("schema_present"), technical_verified), "seo_technical", scan.get("schema_types"))
    add(22, "Canonical URL Set", bool_status(scan.get("canonical_present"), technical_verified), "seo_technical")
    add(23, "XML Sitemap Present", bool_status(scan.get("sitemap_present")), "seo_technical", scan.get("sitemap_status_code"))
    add(24, "Robots.txt Valid", bool_status(scan.get("robots_valid")), "seo_technical", scan.get("robots_status_code"))
    add(25, "Google PageSpeed Performance > 60", UNKNOWN if not psi_available or perf is None else (PASS if float(perf) >= 60 else FAIL), "seo_technical", perf)
    add(26, "Google PageSpeed Performance > 90", UNKNOWN if not psi_available or perf is None else (PASS if float(perf) >= 90 else FAIL), "seo_technical", perf)
    add(27, "Google SEO Score > 80", UNKNOWN if not psi_available or seo is None else (PASS if float(seo) >= 80 else FAIL), "seo_technical", seo)

    lcp = scan.get("crux_lcp_ms") if scan.get("crux_available") else scan.get("psi_lcp_ms")
    inp = scan.get("crux_inp_ms") if scan.get("crux_available") else None
    cls_value = scan.get("crux_cls") if scan.get("crux_available") else scan.get("psi_cls")
    add(28, "LCP (Largest Contentful Paint) ≤ 2.5s", UNKNOWN if lcp is None else (PASS if float(lcp) <= 2500 else FAIL), "seo_technical", lcp)
    add(29, "INP (Interaction to Next Paint) ≤ 200ms", UNKNOWN if inp is None else (PASS if float(inp) <= 200 else FAIL), "seo_technical", inp)
    add(30, "CLS (Cumulative Layout Shift) ≤ 0.1", UNKNOWN if cls_value is None else (PASS if float(cls_value) <= 0.1 else FAIL), "seo_technical", cls_value)
    add(31, "Mobile Viewport Configured", bool_status(scan.get("mobile_viewport_configured"), technical_verified), "seo_technical")

    tap_count = scan.get("psi_tap_targets_flagged")
    if tap_count is None:
        tap_list = scan.get("tap_targets_flagged")
        tap_status = UNKNOWN if not isinstance(tap_list, list) else (FAIL if len(tap_list) > 0 else (PASS if psi_available else UNKNOWN))
    else:
        tap_status = PASS if int(tap_count) == 0 else FAIL
    add(32, "Tap Targets Properly Sized", tap_status, "seo_technical", tap_count if tap_count is not None else scan.get("tap_targets_flagged"))

    blocking = scan.get("psi_render_blocking_count")
    add(33, "No Material Render-Blocking Resources", UNKNOWN if blocking is None else (PASS if int(blocking) == 0 else FAIL), "seo_technical", blocking)
    missing_alt = scan.get("missing_alt_images")
    add(34, "Images Have Accessibility Text", UNKNOWN if not image_verified or missing_alt is None else (PASS if int(missing_alt) == 0 else FAIL), "seo_technical", {"missing": missing_alt, "total": scan.get("total_images")})
    lazy_status = str(scan.get("lazy_loading_status") or UNKNOWN).upper()
    add(35, "Lazy Loading on Relevant Images", lazy_status if lazy_status in {PASS, FAIL, UNKNOWN, NA} else UNKNOWN, "seo_technical", scan.get("lazy_image_count"))

    # Content & E-E-A-T 36-50
    add(36, "Original Photography (Not Stock)", scan.get("custom_photography_status") if scan.get("custom_photography_status") in {PASS, FAIL, UNKNOWN, NA} else UNKNOWN, "content_eeat", reason="Scanner records same-origin imagery as a signal but does not claim provenance without proof")
    editorial_relevant = bool(scan.get("blog_present")) or applicability_vertical in {"legal", "medspa", "professional_service", "saas"}
    add(37, "Author Bylines Present", NA if not editorial_relevant else bool_status(scan.get("author_bylines_present"), content_verified), "content_eeat")
    add(38, "Publication Dates Visible", NA if not editorial_relevant else bool_status(scan.get("publication_dates_visible"), content_verified), "content_eeat")
    word_count = int(scan.get("visible_word_count") or 0)
    word_relevant = applicability_vertical in {"legal", "medspa", "professional_service", "local_service", "saas", "ecommerce"}
    add(39, "Visible Content Length > 300 Words", NA if not word_relevant else (UNKNOWN if not document_verified else (PASS if word_count > 300 else FAIL)), "content_eeat", word_count)
    ai_pct = scan.get("ai_spectrum_pct")
    add(40, "AI / Template Pattern Index < 30", UNKNOWN if not ai_available else (PASS if float(ai_pct) < 30 else FAIL), "content_eeat", ai_pct)
    add(41, "AI / Template Pattern Index < 60", UNKNOWN if not ai_available else (PASS if float(ai_pct) < 60 else FAIL), "content_eeat", ai_pct)
    generic = (scan.get("ai_flags") or {}).get("generic_headline")
    add(42, "No Generic Template Headlines", UNKNOWN if generic is None or not document_verified else (PASS if not bool(generic) else FAIL), "content_eeat")
    unlinked = (scan.get("ai_flags") or {}).get("unlinked_forms")
    add(43, "No Structurally Unlinked Forms", NA if scan.get("forms_present") is False else (UNKNOWN if unlinked is None else (PASS if int(unlinked) == 0 else FAIL)), "content_eeat", unlinked)
    faq_relevant = applicability_vertical in {"legal", "medspa", "professional_service", "local_service", "saas", "ecommerce"}
    add(44, "FAQ Section Present", NA if not faq_relevant else bool_status(scan.get("faq_present"), content_verified), "content_eeat")
    portfolio_relevant = applicability_vertical in {"local_service", "professional_service", "legal", "medspa", "saas"}
    add(45, "Case Studies / Portfolio Linked", NA if not portfolio_relevant else bool_status(scan.get("case_studies_portfolio_present"), content_verified), "content_eeat")
    blog_relevant = applicability_vertical in {"legal", "medspa", "professional_service", "local_service", "saas"}
    add(46, "Blog / Content Hub Active", NA if not blog_relevant else bool_status(scan.get("blog_present"), content_verified), "content_eeat")
    social_present = bool(scan.get("social_links_present"))
    add(47, "Social Media Links Active", PASS if social_present and content_verified else NA, "content_eeat", reason="Optional identity/discovery channel; absence alone is not a conversion failure")
    policy_relevant = bool(scan.get("forms_present") or scan.get("has_ga4") or scan.get("has_meta_pixel") or scan.get("retargeting_pixel_installed")) or applicability_vertical in {"ecommerce", "saas", "legal", "medspa", "professional_service"}
    add(48, "Privacy Policy & Terms Linked", bool_status(scan.get("privacy_terms_linked"), content_verified) if policy_relevant else NA, "content_eeat")
    cookie = scan.get("cookie_banner_present")
    add(49, "Cookie Consent / Preference Interface", PASS if cookie is True else UNKNOWN, "content_eeat", "Absence is jurisdiction/context dependent and is not automatically failed")
    form_status = str(scan.get("form_functional_status") or UNKNOWN).upper()
    add(50, "Contact Form Functional", NA if scan.get("forms_present") is False else (form_status if form_status in {PASS, FAIL, UNKNOWN} else UNKNOWN), "content_eeat", "No destructive live submission performed")

    return checkpoints


def checkpoint_summary(checkpoints: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {PASS: 0, FAIL: 0, UNKNOWN: 0, NA: 0}
    for checkpoint in checkpoints:
        status = checkpoint.get("status")
        if status in counts:
            counts[status] += 1
    return {
        "verified": counts[PASS] + counts[FAIL],
        "passed": counts[PASS],
        "failed": counts[FAIL],
        "unknown": counts[UNKNOWN],
        "not_applicable": counts[NA],
        "total": len(checkpoints),
    }
