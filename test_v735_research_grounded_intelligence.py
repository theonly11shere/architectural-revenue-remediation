"""V7.3.5 research-grounded category/journey intelligence tests."""
from __future__ import annotations

import pytest

from category_intelligence import BUSINESS_DEEP_DIVE_PACKS, get_business_deep_dive_pack, knowledge_stats
from research_knowledge import (
    CATEGORY_RESEARCH_PACKS,
    JOURNEY_RESEARCH_PACKS,
    RESEARCH_SOURCES,
    get_research_guidance,
    research_basis_for_rule,
    research_rule_multiplier,
    research_stats,
)
from scorer import RevenueScorer
from hybrid_scanner import HybridScanner


ALL_TYPES = sorted(BUSINESS_DEEP_DIVE_PACKS)
ALL_JOURNEYS = [
    "lead_quote", "appointment_consultation", "reservation_event", "direct_purchase",
    "demo_sales", "membership_subscription", "donation_support", "application_enrollment",
]


def test_research_ledger_covers_every_supported_business_category():
    assert set(CATEGORY_RESEARCH_PACKS) == set(ALL_TYPES)
    for business_type in ALL_TYPES:
        pack = CATEGORY_RESEARCH_PACKS[business_type]
        assert len(pack.get("sources") or []) >= 2, business_type
        assert len(pack.get("customer_focus") or []) >= 6, business_type
        assert len(pack.get("page_terms") or []) >= 6, business_type
        assert len(pack.get("concepts") or {}) >= 3, business_type
        assert len(pack.get("rule_multipliers") or {}) >= 6, business_type


def test_research_ledger_covers_every_commercial_journey():
    for journey in ALL_JOURNEYS:
        assert journey in JOURNEY_RESEARCH_PACKS
        pack = JOURNEY_RESEARCH_PACKS[journey]
        assert len(pack.get("sources") or []) >= 1
        assert len(pack.get("customer_focus") or []) >= 4
        assert len(pack.get("page_terms") or []) >= 4
        assert len(pack.get("rule_multipliers") or {}) >= 4


def test_every_research_source_records_scope_population_and_limitations():
    assert len(RESEARCH_SOURCES) >= 14
    for source_id, item in RESEARCH_SOURCES.items():
        assert item.get("source"), source_id
        assert item.get("title"), source_id
        assert item.get("url", "").startswith("https://"), source_id
        assert item.get("class") in {"A", "B", "C", "D"}, source_id
        assert item.get("population"), source_id
        assert item.get("scope"), source_id
        assert item.get("limitations"), source_id


@pytest.mark.parametrize("business_type", ALL_TYPES)
def test_category_deep_dive_pack_is_research_enriched_after_type_resolution(business_type):
    # Use a plausible journey for the generic test. The category pack itself remains authoritative.
    journey = "lead_quote"
    if business_type in {"ecommerce", "marketplace"}:
        journey = "direct_purchase"
    elif business_type in {"healthcare", "medspa", "legal", "financial_services"}:
        journey = "appointment_consultation"
    elif business_type in {"restaurant", "hospitality_event"}:
        journey = "reservation_event"
    elif business_type in {"saas", "b2b"}:
        journey = "demo_sales"
    elif business_type == "membership_creator":
        journey = "membership_subscription"
    elif business_type == "education":
        journey = "application_enrollment"
    elif business_type == "nonprofit":
        journey = "donation_support"

    pack = get_business_deep_dive_pack(business_type, journey, [])
    research = pack.get("research_guidance") or {}
    assert research.get("source_ids"), business_type
    assert research.get("sources"), business_type
    assert len(pack.get("customer_focus") or []) >= len(BUSINESS_DEEP_DIVE_PACKS[business_type].get("customer_focus") or [])


def test_ecommerce_direct_purchase_activates_baymard_specific_priority():
    guidance = get_research_guidance("ecommerce", "direct_purchase", ["commerce_payment"])
    assert "baymard_checkout_2026" in guidance["source_ids"]
    assert research_rule_multiplier("checkout_cost_transparency", "ecommerce", "direct_purchase", ["commerce_payment"]) > 1.0
    assert research_rule_multiplier("guest_checkout_barrier", "ecommerce", "direct_purchase", ["commerce_payment"]) > 1.0
    assert research_rule_multiplier("delivery_expectation_clarity", "ecommerce", "direct_purchase", ["commerce_payment"]) > 1.0


def test_baymard_does_not_bleed_into_unrelated_legal_consultation_scoring():
    guidance = get_research_guidance("legal", "appointment_consultation", ["regulated_high_trust"])
    assert "baymard_checkout_2026" not in guidance["source_ids"]
    assert research_rule_multiplier("checkout_cost_transparency", "legal", "appointment_consultation", []) == 1.0
    assert research_rule_multiplier("trust_credentials", "legal", "appointment_consultation", []) > 1.0


def test_legal_nonprofit_realestate_and_restaurant_activate_distinct_sources():
    assert "clio_legal_2025" in get_research_guidance("legal", "appointment_consultation", [])["source_ids"]
    assert "mr_benchmarks_2026" in get_research_guidance("nonprofit", "donation_support", [])["source_ids"]
    assert "zillow_housing_2025" in get_research_guidance("real_estate", "lead_quote", [])["source_ids"]
    restaurant_sources = get_research_guidance("restaurant", "reservation_event", ["local_location_dependent"])["source_ids"]
    assert "google_restaurant_mobile" in restaurant_sources
    assert "brightlocal_reviews_2025" in restaurant_sources


def test_study_context_multiplier_is_tightly_bounded():
    for business_type in ALL_TYPES:
        for journey in ALL_JOURNEYS:
            guidance = get_research_guidance(business_type, journey, [])
            for value in (guidance.get("rule_multipliers") or {}).values():
                assert 0.94 <= float(value) <= 1.12


def test_research_basis_only_claims_sources_when_rule_is_study_emphasized():
    emphasized = research_basis_for_rule("checkout_cost_transparency", "ecommerce", "direct_purchase", ["commerce_payment"])
    assert emphasized["study_context_multiplier"] > 1.0
    assert emphasized["source_ids"]

    unrelated = research_basis_for_rule("favicon_present", "ecommerce", "direct_purchase", ["commerce_payment"])
    assert unrelated["study_context_multiplier"] == 1.0
    assert unrelated["source_ids"] == []


def test_business_type_weighting_still_requires_an_existing_leak():
    scorer = RevenueScorer()
    assert scorer._apply_business_type_weighting([], "ecommerce", "direct_purchase", ["commerce_payment"]) == []
    # Research cannot manufacture a finding; it only enriches an input leak that already exists.
    leak = {
        "rule_key": "checkout_cost_transparency",
        "category": "trust_conversion",
        "intrinsic_severity_score": 1.0,
        "economic_severity": 1.0,
        "pre_dedupe_penalty": 1.0,
        "final_score_loss": 1.0,
        "score_impact_points": 1.0,
        "final_severity_score": 1.0,
    }
    out = scorer._apply_business_type_weighting([leak], "ecommerce", "direct_purchase", ["commerce_payment"])
    assert len(out) == 1
    assert out[0]["study_context_multiplier"] > 1.0
    assert out[0]["study_research_basis"]["source_ids"]


def test_research_stats_are_exposed_in_combined_knowledge_stats():
    stats = research_stats()
    combined = knowledge_stats()
    assert stats["research_sources"] >= 14
    assert stats["business_categories"] == 18
    assert stats["journey_families"] == 9
    assert combined["research_research_sources"] == stats["research_sources"]
    assert combined["research_business_categories"] == 18


def test_v771_engine_version():
    assert HybridScanner.ENGINE_VERSION == "v7.8.1-universal-path-refinement"


def test_rule_level_attribution_is_precise_not_all_pack_sources():
    basis = research_basis_for_rule("checkout_cost_transparency", "ecommerce", "direct_purchase", ["commerce_payment"])
    assert basis["source_ids"] == ["baymard_checkout_2026"]
    assert basis["strongest_research_class"] == "A"

    perf = research_basis_for_rule("mobile_lab_performance", "restaurant", "reservation_event", [])
    # Google CWV can support performance; restaurant/mobile studies may also be applicable,
    # but unrelated local/review sources must not be attributed to the performance rule.
    assert "brightlocal_reviews_2025" not in perf["source_ids"]
    assert "google_search_local" not in perf["source_ids"]


def test_population_specific_sources_do_not_bleed_across_business_types():
    restaurant = research_basis_for_rule("primary_conversion_path", "restaurant", "reservation_event", [])
    assert "google_restaurant_mobile" in restaurant["source_ids"]
    assert "google_travel_booking" not in restaurant["source_ids"]

    hotel = research_basis_for_rule("primary_conversion_path", "hospitality_event", "reservation_event", [])
    assert "google_travel_booking" in hotel["source_ids"]
    assert "google_restaurant_mobile" not in hotel["source_ids"]

    legal = research_basis_for_rule("primary_conversion_path", "legal", "appointment_consultation", [])
    assert "clio_legal_2025" in legal["source_ids"]
    assert "zillow_housing_2025" not in legal["source_ids"]


def test_source_class_caps_population_limited_study_emphasis():
    # Restaurant and travel journey sources are intentionally class C and therefore
    # cannot amplify an already-verified rule above the class-C research cap.
    assert research_rule_multiplier("primary_conversion_path", "restaurant", "reservation_event", []) <= 1.06
    assert research_rule_multiplier("primary_conversion_path", "hospitality_event", "reservation_event", []) <= 1.06
    # A-class Baymard evidence can use the full tightly bounded research layer.
    assert research_rule_multiplier("checkout_cost_transparency", "ecommerce", "direct_purchase", []) <= 1.12


def test_unsupported_category_heuristic_does_not_gain_fake_research_weight():
    # The healthcare category may still have normal Trilloka business/context weighting,
    # but the new *research* layer does not claim a privacy study where none is mapped.
    assert research_rule_multiplier("privacy_terms_missing", "healthcare", "appointment_consultation", []) == 1.0
    basis = research_basis_for_rule("privacy_terms_missing", "healthcare", "appointment_consultation", [])
    assert basis["source_ids"] == []


def test_each_effective_research_multiplier_has_rule_specific_source_support():
    for business_type in ALL_TYPES:
        for journey in ALL_JOURNEYS:
            guidance = get_research_guidance(business_type, journey, [])
            for rule in (guidance.get("rule_multipliers") or {}):
                multiplier = research_rule_multiplier(rule, business_type, journey, [])
                basis = research_basis_for_rule(rule, business_type, journey, [])
                if abs(multiplier - 1.0) > 1e-9:
                    assert basis["source_ids"], (business_type, journey, rule)
                    assert basis["strongest_research_class"] in {"A", "B", "C", "D"}
