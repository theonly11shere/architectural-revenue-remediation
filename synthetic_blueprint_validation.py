"""Offline synthetic validation for the V7.2 public score blueprint.

This is not production scoring logic. It creates controlled website-evidence fixtures that
exercise the real scorer across six customer-journey models and six architecture maturity
levels. The assertions protect the intended public score bands without forcing real sites
into a distribution.
"""
from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import csv

from scorer import RevenueScorer
from test_regressions import base_scan

TYPE_CONFIG: Dict[str, Dict[str, Any]] = {
    "Lead / Quote": {
        "title": "Vancouver Custom Home Renovation Contractor",
        "h1": "Custom Home Renovations",
        "text": "general contractor custom home renovation request a quote free estimate project consultation Vancouver portfolio case studies ",
        "cta": ["quote", "call"],
        "extra": {},
    },
    "Appointment / Consultation": {
        "title": "Vancouver Physiotherapy Clinic — Book Appointment",
        "h1": "Physiotherapy & Sports Rehabilitation",
        "text": "physiotherapy physiotherapist new patient book appointment schedule appointment consultation Vancouver clinic treatment ",
        "cta": ["book", "call"],
        "extra": {"booking_provider_links": ["https://booking.example.com/"]},
    },
    "Reservation / Event": {
        "title": "Vancouver Waterfront Wedding Venue",
        "h1": "Waterfront Wedding & Private Event Venue",
        "text": "wedding event venue private event corporate event reserve reservation catering Vancouver book your event ",
        "cta": ["reserve", "call"],
        "extra": {"reservation_present": True},
    },
    "Direct Purchase": {
        "title": "Vancouver Outdoor Store — Shop Online",
        "h1": "Shop Outdoor Gear Online",
        "text": "shop now add to cart checkout product shipping returns buy now Vancouver outdoor gear ",
        "cta": ["add_to_cart", "buy"],
        "extra": {"add_to_cart_visible": True, "checkout_context_detected": True, "order_online_present": True},
    },
    "Demo / Sales": {
        "title": "Enterprise Operations Software — Request a Demo",
        "h1": "Enterprise Operations Platform",
        "text": "enterprise software platform solutions request a demo contact sales free trial procurement case studies pricing ",
        "cta": ["demo", "trial"],
        "extra": {"pricing_linked": True},
    },
    "Membership / Subscription": {
        "title": "Professional Learning Community — Join Now",
        "h1": "Membership for Growing Professionals",
        "text": "join now become a member membership subscribe community course cohort member benefits pricing ",
        "cta": ["join", "subscribe"],
        "extra": {"pricing_linked": True},
    },
}

RANGES = {
    "Broken": (26.0, 32.99),
    "Material": (35.0, 44.99),
    "Functional": (46.0, 58.99),
    "Strong": (59.0, 69.99),
    "Exceptional": (70.0, 79.99),
    "Near-perfect": (80.0, 90.0),
}


def _strong_base(name: str) -> Dict[str, Any]:
    cfg = TYPE_CONFIG[name]
    scan = base_scan()
    text = cfg["text"]
    conversion_forms = name in {"Lead / Quote", "Appointment / Consultation", "Reservation / Event", "Demo / Sales"}
    scan.update({
        "domain": re.sub(r"[^a-z]+", "-", name.lower()).strip("-") + ".example",
        "title": cfg["title"], "h1_tags": [cfg["h1"]], "h1_dom_count": 1, "h1_source_count": 1,
        "h1_relevance_status": "PASS", "meta_description": text[:150], "page_text": (text * 22).strip(),
        "journey_text_sample": text * 3, "visible_word_count": 550, "mobile_cta_types": cfg["cta"],
        "mobile_primary_cta_present": True, "mobile_sticky_cta_present": True, "mobile_cta_visible": True,
        "mobile_cta_status": "verified", "forms_present": conversion_forms,
        "form_action_valid": True if conversion_forms else None,
        "form_functional_status": "PASS" if conversion_forms else "NOT_APPLICABLE",
        "credential_signals_present": True, "trust_badges_present": True, "reviews_visible": True,
        "social_proof_present": True, "about_team_linked": True, "case_studies_portfolio_present": True,
        "has_ga4": True, "has_meta_pixel": True, "has_qualitative_analytics": True,
        "measurement_layer_present": True,
        "measurement_platforms": ["Google Analytics / GTM", "Meta Pixel", "Microsoft Clarity"],
        "retargeting_pixel_installed": True, "performance_score": 94.0, "google_seo_score": 96.0,
        "psi_lcp_ms": 1600.0, "psi_cls": 0.03, "crux_available": True, "crux_lcp_ms": 1800.0,
        "crux_inp_ms": 90.0, "crux_cls": 0.03, "real_user_speed_grade": "GOOD",
        "privacy_policy_linked": True, "terms_linked": True, "privacy_terms_linked": True,
        "cookie_banner_present": True, "custom_photography_status": "UNKNOWN", "custom_photography_signal": True,
    })
    scan.update(cfg["extra"])
    if name == "Direct Purchase":
        scan["guarantee_refund_present"] = True
    return scan


def _broken(name: str) -> Dict[str, Any]:
    scan = _strong_base(name)
    scan.update({
        "performance_score": 32.0, "google_seo_score": 55.0, "psi_lcp_ms": 4800.0, "psi_cls": 0.22,
        "crux_available": False, "real_user_speed_grade": "UNKNOWN", "mobile_primary_cta_present": False,
        "mobile_sticky_cta_present": False, "mobile_cta_visible": False, "mobile_cta_types": [],
        "click_to_call_present": False, "click_to_call_status": "verified", "forms_present": False,
        "form_action_valid": False, "form_functional_status": "FAIL", "has_ga4": False,
        "has_meta_pixel": False, "has_qualitative_analytics": False, "measurement_layer_present": False,
        "measurement_platforms": [], "retargeting_pixel_installed": False, "reviews_visible": False,
        "social_proof_present": False, "trust_badges_present": False, "about_team_linked": False,
        "case_studies_portfolio_present": False, "canonical_present": False, "meta_description": "",
        "missing_alt_images": 2, "images_with_alt": 1, "image_count": 3, "total_images": 3,
        "privacy_policy_linked": False, "terms_linked": False, "privacy_terms_linked": False,
        "cookie_banner_present": False,
    })
    if name == "Direct Purchase":
        scan.update({"add_to_cart_visible": False, "checkout_context_detected": False, "order_online_present": False, "guarantee_refund_present": False})
    if name == "Reservation / Event": scan["reservation_present"] = False
    if name == "Appointment / Consultation": scan["booking_provider_links"] = []
    return scan


def _material(name: str) -> Dict[str, Any]:
    scan = _strong_base(name)
    scan.update({
        "performance_score": 58.0, "google_seo_score": 82.0, "psi_lcp_ms": 2900.0,
        "crux_available": False, "real_user_speed_grade": "UNKNOWN", "mobile_sticky_cta_present": False,
        "has_meta_pixel": False, "has_qualitative_analytics": False, "retargeting_pixel_installed": False,
        "measurement_platforms": ["Google Analytics / GTM"], "trust_badges_present": False,
        "case_studies_portfolio_present": False,
    })
    if name == "Direct Purchase": scan["guarantee_refund_present"] = False
    return scan


def _functional(name: str) -> Dict[str, Any]:
    scan = _material(name)
    scan.update({"performance_score": 78.0, "psi_lcp_ms": 2400.0, "mobile_sticky_cta_present": True, "trust_badges_present": True})
    return scan


def _strong(name: str) -> Dict[str, Any]:
    scan = _strong_base(name)
    if name not in {"Direct Purchase", "Membership / Subscription"}:
        scan.update({"performance_score": 88.0, "has_qualitative_analytics": False, "measurement_platforms": ["Google Analytics / GTM", "Meta Pixel"]})
    return scan


def _exceptional(name: str) -> Dict[str, Any]:
    scan = _strong_base(name)
    if name in {"Direct Purchase", "Membership / Subscription"}:
        scan.update({
            "conversion_completion_verified": True,
            "conversion_completion_verification_source": "synthetic verified non-destructive completion evidence",
            "performance_score": 85.0, "has_qualitative_analytics": False,
            "measurement_platforms": ["Google Analytics / GTM", "Meta Pixel"],
        })
    return scan


def _near_perfect(name: str) -> Dict[str, Any]:
    scan = _strong_base(name)
    scan.update({
        "conversion_completion_verified": True,
        "conversion_completion_verification_source": "synthetic verified non-destructive completion evidence",
        "performance_score": 99.0, "custom_photography_status": "PASS",
    })
    return scan

BUILDERS = {
    "Broken": _broken, "Material": _material, "Functional": _functional,
    "Strong": _strong, "Exceptional": _exceptional, "Near-perfect": _near_perfect,
}


def run(output_path: str | None = None) -> list[dict[str, Any]]:
    scorer = RevenueScorer()
    rows = []
    for journey in TYPE_CONFIG:
        previous = -1.0
        for level, builder in BUILDERS.items():
            audit = scorer.audit_and_score(builder(journey), business_type="auto")
            score = float(audit["overall_score"])
            low, high = RANGES[level]
            assert low <= score <= high, f"{journey} {level}: {score} outside {low}–{high}"
            assert score > previous, f"{journey}: non-monotonic {previous} -> {score}"
            previous = score
            cp50 = next(cp for cp in audit["full_50_checkpoint_basis"] if cp["id"] == 50)
            rows.append({
                "journey": journey, "synthetic_level": level, "score": score,
                "canonical_three_layer_score": audit["score_formula"]["canonical_three_layer_score"],
                "rating": audit["score_rating"], "conversion_path_readiness": audit["surface_metrics"]["conversion_path_readiness"],
                "elite_points": audit["analysis_layers"]["elite_architecture"]["layer_score"],
                "verified_leaks": len(audit["tiered_remediation_packages"]["all_scoring_leaks"]),
                "completion_checkpoint": cp50["status"],
                "financial_exposure": audit["financial_exposure"]["display"],
            })
    if output_path and rows:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    return rows


if __name__ == "__main__":
    target = Path(__file__).with_name("SYNTHETIC_BLUEPRINT_RESULTS.csv")
    result = run(str(target))
    for row in result:
        print(f"{row['journey']:<28} {row['synthetic_level']:<13} score={row['score']:>5.1f} canonical={row['canonical_three_layer_score']:>5.1f}  {row['rating']}")
    print(f"\nPASS: {len(result)} synthetic cases across {len(TYPE_CONFIG)} journeys and {len(BUILDERS)} score bands")
    print(f"Saved: {target}")
