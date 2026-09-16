"""Randomized V7.4.1 reliability guardrail stress.

This suite exercises the failure modes fixed after the Valmont real-world scan:
tri-state evidence, deeper-page journey actions, provisional economic guardrails,
and goods-commerce scoping. It does not add scanner rules.
"""
from __future__ import annotations

import random
from copy import deepcopy

from checkpoint_engine import FAIL, NA, PASS, UNKNOWN, build_50_checkpoints
from scorer import RevenueScorer
from test_regressions import base_scan

RNG = random.Random(741)

JOURNEY_ACTIONS = {
    "lead_quote": ["quote", "contact"],
    "appointment_consultation": ["book", "contact"],
    "reservation_event": ["reserve", "book"],
    "direct_purchase": ["order", "buy"],
    "demo_sales": ["demo", "trial"],
    "membership_subscription": ["join", "subscribe"],
    "donation_support": ["donate", "support"],
    "application_enrollment": ["apply", "enroll"],
}


def profile(journey: str, *, provisional: bool = False, business: str = "general"):
    return {
        "business_type": business,
        "business_type_label": business,
        "business_type_confidence": 0.9,
        "journey_model": journey,
        "journey_label": journey,
        "confidence": 0.9 if not provisional else 0.65,
        "provisional": provisional,
        "journey_resolved": not provisional,
        "context_tags": ["commerce_payment"] if journey == "direct_purchase" else [],
    }


def run(trials: int = 10000):
    tri_state_passed = 0
    action_passed = 0
    provisional_passed = 0
    commerce_scope_passed = 0

    scorer = RevenueScorer()
    quarter = trials // 4

    # 1) Unknown evidence must never be coerced into a policy failure.
    for _ in range(quarter):
        scan = base_scan()
        scan.update({
            "architecture_profile": profile("direct_purchase", business="ecommerce"),
            "checkout_context_detected": True,
            "privacy_policy_linked": None,
            "terms_linked": RNG.choice([None, True, False]),
            "static_html_verified": True,
            "content_signal_status": "verified",
        })
        cp48 = next(cp for cp in build_50_checkpoints(scan, {}) if cp["id"] == 48)
        if cp48["status"] == UNKNOWN:
            tri_state_passed += 1

    # 2) Verified deeper-page action evidence must qualify the journey action even when
    # the homepage/mobile CTA list is empty.
    journeys = list(JOURNEY_ACTIONS)
    for _ in range(quarter):
        journey = RNG.choice(journeys)
        action = RNG.choice(JOURNEY_ACTIONS[journey])
        data = base_scan()
        data.update({
            "mobile_cta_types": [],
            "mobile_primary_cta_present": False,
            "journey_action_types": [action],
            "forms_present": False,
            "click_to_call_present": False,
            "reservation_present": False,
            "booking_provider_links": [],
            "add_to_cart_visible": False,
            "checkout_context_detected": False,
            "donation_present": False,
            "application_present": False,
        })
        points, evidence = scorer._business_conversion_strength(data, journey, profile(journey))
        if points > 0 and action in evidence.get("journey_action_types", []):
            action_passed += 1

    # 3) Every provisional specialized journey must defer dollar modeling.
    dummy = [{
        "rule_key": "conversion_path_error", "family": "conversion_execution",
        "economic_severity": 3.0, "final_score_loss": 1.0,
        "confidence": "high", "severity_factor": 1.0, "substitution_factor": 1.0,
    }]
    for _ in range(quarter):
        journey = RNG.choice(journeys)
        result = RevenueScorer._revenue_exposure(journey, dummy, {"score": RNG.uniform(30, 95)}, profile(journey, provisional=True), {})
        if result.get("estimate_status") == "DEFERRED_PROVISIONAL_JOURNEY" and result.get("annual_digital_opportunity_pool") is None:
            provisional_passed += 1

    # 4) A restaurant direct-purchase path is not automatically retail goods commerce.
    for _ in range(trials - 3 * quarter):
        scan = base_scan()
        scan.update({
            "architecture_profile": profile("direct_purchase", business="restaurant"),
            "business_profile": {"vertical": "restaurant", "confidence": 0.95, "primary_conversion": "order_online", "signals": ["restaurant", "order online"]},
            "page_text": "restaurant menu order online pickup local cafe " * 15,
            "order_online_present": True,
            "mobile_cta_types": ["order"],
            "journey_action_types": ["order"],
            "mobile_cta_status": "verified",
            "journey_evidence_status": "verified",
            "journey_pages_verified": 2,
            "checkout_context_detected": True,
            "return_policy_linked": False,
            "shipping_info_linked": False,
            "content_signal_status": "verified",
        })
        audit = scorer.audit_and_score(scan, business_type="auto")
        cp12 = next(cp for cp in audit["full_50_checkpoint_basis"] if cp["id"] == 12)
        rules = {x.get("rule_key") for x in audit["tiered_remediation_packages"]["all_scoring_leaks"]}
        if cp12["status"] == NA and "return_policy_discoverability" not in rules and "shipping_info_discoverability" not in rules and "delivery_expectation_clarity" not in rules:
            commerce_scope_passed += 1

    return {
        "trials": trials,
        "tri_state_unknown_preserved": tri_state_passed,
        "deeper_action_recognized": action_passed,
        "provisional_exposure_deferred": provisional_passed,
        "restaurant_goods_scope_clean": commerce_scope_passed,
        "passed": tri_state_passed + action_passed + provisional_passed + commerce_scope_passed,
    }


if __name__ == "__main__":
    result = run()
    print(result)
    if result["passed"] != result["trials"]:
        raise SystemExit(1)
