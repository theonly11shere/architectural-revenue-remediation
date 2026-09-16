from copy import deepcopy

import pytest

from architecture_model import infer_architecture_profile
from architect_review import build_architect_review_queue
from checkpoint_engine import FAIL, PASS, UNKNOWN, build_50_checkpoints
from hybrid_scanner import HybridScanner
from remediation_intelligence import build_outcome_remediation
from report_engine import ReportGenerator
from scorer import RevenueScorer
from test_regressions import base_scan


def _profile(journey="direct_purchase", provisional=False, context=None, business="restaurant", confidence=0.86):
    return {
        "business_type": business,
        "business_type_label": business.replace("_", " ").title(),
        "business_type_confidence": 0.9,
        "journey_model": journey,
        "journey_label": journey.replace("_", " ").title(),
        "confidence": confidence,
        "provisional": provisional,
        "journey_resolved": not provisional,
        "context_tags": list(context or []),
        "journey_signals": [],
        "secondary_journeys": [],
    }


def test_deeper_page_actions_promote_to_architecture_without_faking_homepage_mobile_cta():
    combined = {
        "title": "Valmont Cafe",
        "h1_tags": ["Fresh Vietnamese Cuisine"],
        "page_text": "Restaurant cafe menu dine in Richmond food",
        "mobile_cta_types": [],
        "mobile_cta_status": "verified",
        "mobile_primary_cta_present": False,
        "privacy_policy_linked": None,
        "terms_linked": None,
        "address_location_visible": None,
        "phone_number_visible": None,
        "add_to_cart_visible": False,
        "order_online_present": False,
        "checkout_context_detected": False,
    }
    journey = {
        "journey_pages_scanned": [
            {"url": "https://example.com/order-online/", "verified": True, "role": "commerce_conversion"},
            {"url": "https://example.com/location/", "verified": True, "role": "support"},
            {"url": "https://example.com/privacy/", "verified": True, "role": "policy"},
        ],
        "journey_pages_verified": 3,
        "journey_evidence_status": "verified",
        "journey_page_limit": 5,
        "journey_text_sample": "Order online add to cart pickup. Richmond location directions phone.",
        "discovered_internal_links": [],
        "journey_action_types": ["order", "add_to_cart", "directions"],
        "journey_action_evidence": [
            {"url": "https://example.com/order-online/", "role": "commerce_conversion", "action_types": ["order", "add_to_cart"]}
        ],
        "privacy_policy_linked": True,
        "address_location_visible": True,
        "phone_number_visible": True,
        "directions_present": True,
        "add_to_cart_visible": True,
        "order_online_present": True,
        "checkout_context_detected": True,
        "reviews_visible": False,
        "social_proof_present": False,
        "trust_badges_present": False,
        "credential_signals_present": False,
        "terms_linked": False,
        "about_team_linked": False,
        "faq_present": False,
        "case_studies_portfolio_present": False,
        "return_policy_linked": False,
        "shipping_info_linked": False,
        "pricing_linked": False,
        "blog_present": False,
        "social_links_present": False,
        "click_to_call_present": False,
        "reservation_present": False,
        "booking_action_present": False,
        "forms_present": False,
        "booking_provider_links": [],
        "journey_error_signals": [],
        "credential_signal_types": [],
    }
    HybridScanner._merge_journey_evidence(combined, journey)

    # Deeper actions inform architecture but do not masquerade as homepage/mobile CTA evidence.
    assert set(combined["journey_action_types"]) >= {"order", "add_to_cart", "directions"}
    assert combined["mobile_cta_types"] == []
    assert combined["mobile_primary_cta_present"] is False
    assert combined["privacy_policy_linked"] is True
    assert combined["address_location_visible"] is True
    assert combined["phone_number_visible"] is True

    profile = infer_architecture_profile(combined, "auto")
    assert profile["business_type"] == "restaurant"
    assert profile["journey_model"] == "direct_purchase"
    assert "local_location_dependent" in profile["context_tags"]
    assert "commerce_payment" in profile["context_tags"]


@pytest.mark.parametrize(
    "actions,expected",
    [
        (["quote"], "lead_quote"),
        (["demo"], "demo_sales"),
        (["apply"], "application_enrollment"),
        (["order"], "direct_purchase"),
    ],
)
def test_verified_deeper_actions_are_first_class_journey_evidence(actions, expected):
    profile = infer_architecture_profile(
        {
            "title": "Example Company",
            "h1_tags": ["Welcome"],
            "page_text": "Learn more about our company",
            "mobile_cta_types": [],
            "journey_action_types": actions,
        },
        "auto",
    )
    assert profile["journey_model"] == expected


def test_policy_unknown_never_becomes_failure_for_compound_requirement():
    scan = base_scan()
    scan.update({
        "architecture_profile": _profile("direct_purchase", False, ["commerce_payment"], "ecommerce"),
        "checkout_context_detected": True,
        "privacy_policy_linked": None,
        "terms_linked": None,
        "static_html_verified": True,
        "content_signal_status": "verified",
    })
    cp48 = next(cp for cp in build_50_checkpoints(scan, {}) if cp["id"] == 48)
    assert cp48["status"] == UNKNOWN

    absent = deepcopy(scan)
    absent.update({"privacy_policy_linked": False, "terms_linked": True})
    cp48_absent = next(cp for cp in build_50_checkpoints(absent, {}) if cp["id"] == 48)
    assert cp48_absent["status"] == FAIL

    present = deepcopy(scan)
    present.update({"privacy_policy_linked": True, "terms_linked": True})
    cp48_present = next(cp for cp in build_50_checkpoints(present, {}) if cp["id"] == 48)
    assert cp48_present["status"] == PASS


def test_provisional_journey_cannot_create_missing_sticky_cta_failure():
    scan = base_scan()
    scan.update({
        "architecture_profile": _profile("reservation_event", True, ["local_location_dependent", "hospitality_event"], "restaurant", 0.69),
        "mobile_cta_status": "verified",
        "mobile_primary_cta_present": True,
        "mobile_sticky_cta_present": False,
        "mobile_cta_types": ["reserve"],
    })
    cp4 = next(cp for cp in build_50_checkpoints(scan, {}) if cp["id"] == 4)
    assert cp4["status"] != FAIL

    audit = RevenueScorer().audit_and_score(scan, business_type="auto")
    leaks = audit["tiered_remediation_packages"]["all_scoring_leaks"]
    assert not any(x.get("rule_key") == "mobile_sticky_cta" for x in leaks)


def test_provisional_journey_defers_financial_scenario_model():
    leak = {
        "rule_key": "conversion_path_error", "family": "conversion_execution",
        "economic_severity": 4.0, "final_score_loss": 2.0, "confidence": "high",
        "severity_factor": 1.0, "substitution_factor": 1.0,
    }
    result = RevenueScorer._revenue_exposure(
        "reservation_event", [leak], {"score": 70},
        _profile("reservation_event", True, ["hospitality_event"], "restaurant", 0.69),
        {},
    )
    assert result["estimate_status"] == "DEFERRED_PROVISIONAL_JOURNEY"
    assert result["level"] == "DEFERRED"
    assert "Deferred" in result["display"]
    assert result["annual_digital_opportunity_pool"] is None


def test_infrastructure_remedy_does_not_receive_unrelated_category_boilerplate():
    remedy = build_outcome_remediation(
        "https_redirect", "restaurant", "reservation_event", {"hospitality_event"}, leak={}, scan_data={}
    )
    assert remedy is not None
    joined = " ".join([remedy["technical"], remedy["cro_ux"], remedy["systems"], remedy["success_check"]]).lower()
    assert "menu/price" not in joined
    assert "reservation/order/call/directions" not in joined
    assert "primary outcome to watch" not in joined

    proof = build_outcome_remediation(
        "proof_placement_gap", "restaurant", "direct_purchase", {"local_location_dependent", "commerce_payment"}, leak={}, scan_data={}
    )
    assert proof is not None
    proof_joined = " ".join([proof["technical"], proof["cro_ux"], proof["systems"]]).lower()
    assert "customer decision" in proof_joined or "decision" in proof_joined
    assert "primary outcome to watch" in proof["success_check"].lower()


def test_scanner_diagnostic_measurement_is_not_customer_verified_strength():
    checkpoints = [
        {"id": 1, "status": PASS, "check": "SSL Certificate Active", "evidence": True},
        {"id": 40, "status": PASS, "check": "AI / Template Pattern Index Measured", "evidence": 12.0},
        {"id": 41, "status": PASS, "check": "AI / Template Pattern Index Below High-Risk Threshold (<60)", "evidence": 12.0},
    ]
    strengths = ReportGenerator._build_verified_strengths(checkpoints)
    names = {x["title"] for x in strengths}
    assert "SSL Certificate Active" in names
    assert "AI / Template Pattern Index Measured" not in names
    assert "AI / Template Pattern Index Below High-Risk Threshold (<60)" in names


def test_architect_queue_catches_provisional_journey_and_medium_proof_judgment():
    profile = _profile("reservation_event", True, ["hospitality_event"], "restaurant", 0.69)
    scan = {
        "architecture_profile": profile,
        "commercial_architecture_diagnostics": {"decision_point_evidence": {"proof_exists_sitewide": True, "decision_pages_verified": 1, "proof_visible_at_decision_point": False, "proof_placement_gap": True}},
        "mobile_primary_cta_present": True,
        "mobile_sticky_cta_present": False,
        "final_url": "https://example.com/",
    }
    audit = {
        "scoring_ledger": [{"rule_key": "proof_placement_gap", "confidence": "medium", "final_score_loss": 1.0}],
        "full_50_checkpoint_basis": [],
        "unconfirmed_high_impact_observations": [],
        "overall_score": 40,
    }
    queue = build_architect_review_queue(scan, audit, require_final_proof=False)
    categories = {x["category"] for x in queue}
    assert "journey_resolution" in categories
    assert "proof_quality" in categories


def test_https_checkpoint_carries_exact_redirect_evidence_object():
    scan = base_scan()
    evidence = {
        "enforced": False,
        "attempted_http_url": "http://example.com/",
        "final_url": "http://example.com/",
        "final_status_code": 200,
        "redirect_chain": [],
        "reason": "HTTP request ended on a successful HTTP document without reaching HTTPS",
    }
    scan.update({"https_redirect_enforced": False, "https_redirect_evidence": evidence})
    cp2 = next(cp for cp in build_50_checkpoints(scan, {}) if cp["id"] == 2)
    assert cp2["status"] == FAIL
    assert cp2["evidence"] == evidence


def test_related_required_evidence_families_preserve_unknown_instead_of_bool_coercion():
    # High-trust credentials: unresolved evidence must not become a verified absence.
    credentials = base_scan()
    credentials.update({
        "architecture_profile": _profile("appointment_consultation", False, ["regulated_high_trust"], "healthcare"),
        "credential_signals_present": None,
        "trust_badges_present": None,
        "static_html_verified": True,
        "content_signal_status": "verified",
    })
    cps = build_50_checkpoints(credentials, {})
    assert next(cp for cp in cps if cp["id"] == 10)["status"] == UNKNOWN

    # Goods-commerce refund reassurance: unresolved policy/guarantee evidence stays UNKNOWN.
    refund = base_scan()
    refund.update({
        "architecture_profile": _profile("direct_purchase", False, ["commerce_payment"], "ecommerce"),
        "return_policy_linked": None,
        "guarantee_refund_present": None,
        "static_html_verified": True,
        "content_signal_status": "verified",
    })
    cps = build_50_checkpoints(refund, {})
    assert next(cp for cp in cps if cp["id"] == 12)["status"] == UNKNOWN

    # Required broad proof / proof-of-work must also keep unresolved constituent evidence unknown.
    proof = base_scan()
    proof.update({
        "architecture_profile": _profile("demo_sales", False, ["enterprise_considered_purchase"], "b2b"),
        "social_proof_present": None,
        "reviews_visible": None,
        "credential_signals_present": None,
        "case_studies_portfolio_present": None,
        "static_html_verified": True,
        "content_signal_status": "verified",
    })
    cps = build_50_checkpoints(proof, {})
    assert next(cp for cp in cps if cp["id"] == 14)["status"] == UNKNOWN
    assert next(cp for cp in cps if cp["id"] == 45)["status"] == UNKNOWN
