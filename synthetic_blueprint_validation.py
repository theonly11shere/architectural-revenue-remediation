"""Offline V7.3 synthetic journey matrix.

This preserves the older six-journey calibration regression while the production scorer now also
uses a first-class business-type layer. The matrix does not replace real fixtures; it catches broad
score inversion/regression when common architecture strength is progressively improved.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from scorer import RevenueScorer
from test_regressions import base_scan

JOURNEYS = (
    "lead_quote", "appointment_consultation", "reservation_event",
    "direct_purchase", "demo_sales", "membership_subscription",
)
LEVELS = ("critical", "weak", "foundational", "functional", "strong", "exceptional")


def _fixture(journey: str, level_index: int) -> Dict[str, Any]:
    scan = deepcopy(base_scan())
    # Explicit legacy journey hints remain supported for API/backward compatibility.
    scan.update({
        "title": "Example Commercial Website",
        "h1_tags": ["Clear Customer Value Proposition"],
        "meta_description": "Clear customer value proposition with a direct next step and trusted support.",
        "h1_relevance_status": "PASS",
        "static_html_verified": True,
        "browser_loaded": True,
        "content_signal_status": "verified",
        "technical_evidence_status": "verified",
        "tracking_evidence_status": "verified",
        "image_evidence_status": "verified",
        "form_evidence_status": "verified",
        "mobile_cta_status": "verified",
        "click_to_call_status": "verified",
        "is_reachable": True,
        "response_ok": True,
        "has_ssl": True,
        "https_redirect_enforced": True,
        "mobile_viewport_configured": True,
    })

    # Progressively strengthen the same architecture without giving every journey irrelevant
    # commerce/booking features. This tests score monotonicity, not category-specific perfection.
    if level_index >= 1:
        scan.update({"performance_score": 45.0, "seo_score": 70.0, "canonical_present": True})
    if level_index >= 2:
        scan.update({
            "performance_score": 62.0, "seo_score": 82.0, "schema_present": True,
            "social_proof_present": True, "reviews_visible": True,
            "about_team_linked": True, "privacy_terms_linked": True,
        })
    if level_index >= 3:
        scan.update({
            "performance_score": 75.0, "seo_score": 90.0,
            "mobile_primary_cta_present": True, "mobile_sticky_cta_present": True,
            "measurement_layer_present": True, "has_ga4": True,
            "credential_signals_present": True, "trust_badges_present": True,
        })
    if level_index >= 4:
        scan.update({
            "performance_score": 88.0, "seo_score": 95.0, "has_meta_pixel": True,
            "retargeting_pixel_installed": True, "case_studies_portfolio_present": True,
            "faq_present": True, "social_links_present": True,
        })
    if level_index >= 5:
        scan.update({
            "performance_score": 96.0, "seo_score": 99.0,
            "crux_available": True, "real_user_speed_grade": "GOOD",
            "crux_lcp_ms": 1800.0, "crux_inp_ms": 120.0, "crux_cls": 0.05,
        })

    # Journey-relevant action evidence.
    action_map = {
        "lead_quote": ["quote", "contact"],
        "appointment_consultation": ["book", "call"],
        "reservation_event": ["reserve", "call"],
        "direct_purchase": ["buy", "add_to_cart"],
        "demo_sales": ["demo", "contact"],
        "membership_subscription": ["subscribe", "join"],
    }
    if level_index >= 2:
        scan["mobile_cta_types"] = action_map[journey]
        scan["mobile_primary_cta_present"] = True
    if journey in {"lead_quote", "appointment_consultation", "demo_sales"} and level_index >= 2:
        scan.update({"forms_present": True, "form_action_valid": True, "form_functional_status": "PASS"})
    if journey == "direct_purchase" and level_index >= 2:
        scan.update({"add_to_cart_visible": True, "checkout_context_detected": True, "shipping_info_linked": True, "return_policy_linked": True})
    if journey == "reservation_event" and level_index >= 2:
        scan.update({"reservation_present": True, "address_location_visible": True, "phone_number_visible": True, "click_to_call_present": True})
    if journey == "appointment_consultation" and level_index >= 2:
        scan.update({"booking_action_present": True, "phone_number_visible": True, "click_to_call_present": True})
    return scan


def run() -> List[Dict[str, Any]]:
    scorer = RevenueScorer()
    rows: List[Dict[str, Any]] = []
    for journey in JOURNEYS:
        for idx, level in enumerate(LEVELS):
            audit = scorer.audit_and_score(_fixture(journey, idx), business_type=journey)
            score = float(audit.get("overall_score") or 0.0)
            rows.append({"journey": journey, "synthetic_level": level, "score": score})
    return rows
