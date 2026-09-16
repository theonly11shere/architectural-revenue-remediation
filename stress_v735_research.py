"""Stress checks for V7.3.5 research-grounded routing and scoring guardrails."""
from __future__ import annotations

import random
from category_intelligence import BUSINESS_DEEP_DIVE_PACKS
from research_knowledge import (
    CATEGORY_RESEARCH_PACKS,
    JOURNEY_RESEARCH_PACKS,
    SOURCE_BUSINESS_SCOPE,
    SOURCE_JOURNEY_SCOPE,
    get_research_guidance,
    research_basis_for_rule,
    research_rule_multiplier,
)

CONTEXTS = [
    "local_location_dependent", "regulated_high_trust", "commerce_payment",
    "enterprise_considered_purchase", "hospitality_event", "recurring_commitment",
    "donation_public_trust", "sensitive_data",
]


def run(seed: int = 7355, trials: int = 25000):
    rng = random.Random(seed)
    business_types = sorted(BUSINESS_DEEP_DIVE_PACKS)
    journeys = sorted(JOURNEY_RESEARCH_PACKS)
    rules = sorted({
        rule
        for pack in list(CATEGORY_RESEARCH_PACKS.values()) + list(JOURNEY_RESEARCH_PACKS.values())
        for rule in (pack.get("rule_multipliers") or {})
    } | {"favicon_present", "privacy_terms_missing", "canonical_missing"})

    precise = bounded = scope_clean = unsupported_clean = 0
    examples_checked = 0
    for _ in range(trials):
        business = rng.choice(business_types)
        journey = rng.choice(journeys)
        rule = rng.choice(rules)
        context = rng.sample(CONTEXTS, rng.randint(0, min(3, len(CONTEXTS))))
        mult = research_rule_multiplier(rule, business, journey, context)
        basis = research_basis_for_rule(rule, business, journey, context)
        examples_checked += 1

        if 0.94 <= mult <= 1.12:
            bounded += 1
        if abs(mult - 1.0) <= 1e-9:
            if not basis["source_ids"]:
                unsupported_clean += 1
        else:
            if basis["source_ids"]:
                precise += 1

        good_scope = True
        for source_id in basis["source_ids"]:
            bscope = SOURCE_BUSINESS_SCOPE.get(source_id, ())
            jscope = SOURCE_JOURNEY_SCOPE.get(source_id, ())
            if bscope and business not in bscope:
                good_scope = False
            if jscope and journey not in jscope:
                good_scope = False
        if good_scope:
            scope_clean += 1

    # Deterministic anti-contamination checks for specialist studies.
    special = {
        "baymard_checkout_2026": {"ecommerce", "marketplace"},
        "clio_legal_2025": {"legal"},
        "mr_benchmarks_2026": {"nonprofit"},
        "zillow_housing_2025": {"real_estate"},
        "google_restaurant_mobile": {"restaurant"},
        "google_finance_known_2021": {"financial_services"},
        "google_education_path": {"education"},
        "google_travel_booking": {"hospitality_event"},
        "google_auto_journey": {"automotive"},
    }
    contamination_checks = contamination_passed = 0
    for business in business_types:
        for journey in journeys:
            guidance = get_research_guidance(business, journey, [])
            for source_id, allowed in special.items():
                if source_id in guidance.get("source_ids", []) and business not in allowed:
                    # Source may be present in broad guidance through a generic journey pack,
                    # but it must never appear as scoring basis outside its population scope.
                    for rule in rules:
                        contamination_checks += 1
                        if source_id not in research_basis_for_rule(rule, business, journey, [])["source_ids"]:
                            contamination_passed += 1

    return {
        "random_trials": examples_checked,
        "bounded": bounded,
        "scoped": scope_clean,
        "effective_with_source": precise,
        "neutral_without_fake_source": unsupported_clean,
        "contamination_passed": contamination_passed,
        "contamination_checks": contamination_checks,
    }


if __name__ == "__main__":
    result = run()
    print(result)
    assert result["bounded"] == result["random_trials"]
    assert result["scoped"] == result["random_trials"]
    assert result["contamination_passed"] == result["contamination_checks"]
