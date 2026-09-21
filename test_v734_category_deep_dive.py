"""V7.3.5 category intelligence / deep-dive regression tests.

These tests verify that every supported business family has a substantial knowledge pack,
auto inference gates weak/ambiguous classifications, explicit user selection bypasses that gate,
and category knowledge changes evidence routing/importance only after the existing logic resolves a type.
"""
from __future__ import annotations

import random
import pytest

from architecture_model import BUSINESS_TYPE_LABELS, infer_architecture_profile
from category_intelligence import (
    BUSINESS_DEEP_DIVE_PACKS,
    business_page_terms,
    business_page_guesses,
    evaluate_business_type_confirmation,
    get_business_deep_dive_pack,
    knowledge_stats,
    observe_pack_concepts,
    public_business_type_options,
)
from hybrid_scanner import HybridScanner
from scorer import BUSINESS_TYPE_RULE_MULTIPLIERS, RevenueScorer
from commercial_knowledge import BUSINESS_PHRASE_EXPANSIONS, JOURNEY_PHRASE_EXPANSIONS


BUSINESS_CASES = [
    ("ecommerce", "direct_purchase", "Northstar Outdoor Shop", "Shop collection", "Product details size guide in stock free shipping return policy product reviews add to cart proceed to checkout", ["buy"]),
    ("marketplace", "direct_purchase", "TradeSquare Marketplace", "Buyers and sellers", "Browse listings verified sellers buyer protection seller dashboard become a seller list an item checkout", ["buy"]),
    ("local_service", "lead_quote", "MetroFix Home Services", "Licensed contractor", "24/7 service same-day repair service areas we serve project gallery warranty financing available free quote", ["quote"]),
    ("professional_service", "lead_quote", "Cedar CPA Advisory Firm", "Business advisory", "Accounting firm tax advisory audit services our approach client success schedule consultation request a proposal", ["quote"]),
    ("healthcare", "appointment_consultation", "Harbour Medical Practice", "Patient care", "New patients conditions we treat insurance accepted patient portal telehealth book appointment registered therapist", ["book"]),
    ("medspa", "appointment_consultation", "Luma Aesthetic Clinic", "Medical aesthetics", "Botox cosmetic injections skin rejuvenation laser treatment before and after skin consultation book treatment", ["book"]),
    ("legal", "appointment_consultation", "Westshore Law Firm", "Legal representation", "Practice areas corporate law estate law civil litigation legal team free case review legal consultation", ["book"]),
    ("financial_services", "appointment_consultation", "Summit Wealth Management", "Financial planning", "Investment planning wealth advisor portfolio management retirement planning estate planning schedule consultation", ["book"]),
    ("real_estate", "lead_quote", "Oakline Realty", "Homes for sale", "Featured listings realtor property search home valuation listing agent schedule a showing sell your home contact", ["contact"]),
    ("restaurant", "reservation_event", "Juniper Cafe Restaurant", "Our menu", "Brunch food and drink happy hour opening hours reservations table booking order online view menu", ["reserve"]),
    ("hospitality_event", "reservation_event", "Seacliff Resort Hotel", "Rooms and suites", "Hotel rooms amenities nightly rate check-in guest stay check room availability reserve your stay event packages", ["reserve"]),
    ("saas", "demo_sales", "VectorFlow Software Platform", "Workflow automation", "Features integrations API docs security SSO pricing enterprise plan request demo start free trial contact sales", ["demo"]),
    ("b2b", "demo_sales", "IronPeak Industrial Solutions", "For enterprises", "Manufacturing distributor supply chain procurement technical specifications industries case studies request RFQ contact sales", ["demo"]),
    ("agency", "lead_quote", "Northlight Creative Agency", "Selected work", "Brand agency digital marketing media buying public relations portfolio client results start a project book discovery call", ["quote"]),
    ("membership_creator", "membership_subscription", "MakerCircle Community", "Member benefits", "Membership plans premium membership member portal exclusive content paid community join the community subscribe now", ["join"]),
    ("education", "application_enrollment", "Pacific Technical College", "Programs and admissions", "College course catalog learning outcomes diploma certificate tuition scholarship student portal apply now enrollment", ["apply"]),
    ("nonprofit", "donation_support", "River Foundation Nonprofit", "Our mission", "Registered charity community programs our impact annual report volunteer tax receipt support our mission donate now", ["donate"]),
    ("automotive", "lead_quote", "Apex Auto Repair", "Vehicle service", "Auto repair brake service tire change collision repair parts and service book service service appointment free quote", ["quote"]),
]


def test_category_knowledge_base_is_broad_and_complete():
    stats = knowledge_stats()
    assert stats["business_types"] == 18
    assert stats["customer_focus_items"] >= 200
    assert stats["page_routing_terms"] >= 300
    assert stats["page_guesses"] >= 200
    assert stats["concept_families"] >= 95
    assert stats["concept_terms"] >= 550
    assert stats["priority_rule_overrides"] >= 130
    assert len(public_business_type_options()) == 17


@pytest.mark.parametrize("business_type", sorted(BUSINESS_DEEP_DIVE_PACKS))
def test_every_business_type_has_deep_customer_and_page_knowledge(business_type):
    pack = get_business_deep_dive_pack(business_type)
    assert pack["label"] == BUSINESS_TYPE_LABELS[business_type]
    assert len(pack["customer_focus"]) >= 10
    assert len(pack["page_terms"]) >= 15
    assert len(pack["page_guesses"]) >= 12
    assert len(pack["concepts"]) >= 5
    assert sum(len(v) for v in pack["concepts"].values()) >= 25
    assert len(pack["priority_rules"]) >= 6


@pytest.mark.parametrize("expected_type,expected_journey,title,h1,text,actions", BUSINESS_CASES)
def test_confident_auto_types_unlock_category_deep_dive(expected_type, expected_journey, title, h1, text, actions):
    profile = infer_architecture_profile({
        "title": title,
        "h1_tags": [h1],
        "page_text": text,
        "journey_text_sample": text,
        "mobile_cta_types": actions,
    }, "auto")
    assert profile["business_type"] == expected_type, profile
    assert profile["journey_model"] == expected_journey, profile
    gate = evaluate_business_type_confirmation(profile)
    assert gate["required"] is False, (profile, gate)


def test_ambiguous_general_site_requires_user_category_confirmation():
    profile = infer_architecture_profile({
        "title": "Northstar",
        "h1_tags": ["A better way forward"],
        "page_text": "We help people and organizations move forward. Explore our story and learn more.",
    }, "auto")
    gate = evaluate_business_type_confirmation(profile)
    assert profile["business_type"] == "general"
    assert gate["required"] is True
    assert gate["reason"] == "low_business_type_confidence"
    assert len(gate["options"]) == 17


@pytest.mark.parametrize("business_type", sorted(BUSINESS_DEEP_DIVE_PACKS))
def test_explicit_user_category_is_authoritative_and_never_reasked(business_type):
    profile = infer_architecture_profile({"title": "Ambiguous Company", "page_text": "Welcome"}, business_type)
    gate = evaluate_business_type_confirmation(profile)
    assert profile["business_type"] == business_type
    assert profile["business_type_source"] == "explicit_request"
    assert profile["business_type_confidence"] == 1.0
    assert gate["required"] is False


@pytest.mark.parametrize("business_type", sorted(BUSINESS_DEEP_DIVE_PACKS))
def test_category_page_vocabulary_affects_existing_page_router(business_type):
    scanner = HybridScanner()
    term = business_page_terms(business_type)[0].replace(" ", "-")
    target = f"https://example.com/{term}/"
    selected = scanner._select_priority_journey_urls(
        "https://example.com/",
        ["https://example.com/news/", target, "https://example.com/contact/"],
        "general",
        8,
        [],
        business_type,
        [],
    )
    assert target in selected, (business_type, term, selected)


@pytest.mark.parametrize("business_type", sorted(BUSINESS_DEEP_DIVE_PACKS))
def test_category_priority_knowledge_is_merged_but_bounded(business_type):
    pack = get_business_deep_dive_pack(business_type)
    merged = BUSINESS_TYPE_RULE_MULTIPLIERS[business_type]
    for rule, value in pack["priority_rules"].items():
        assert rule in merged
        assert merged[rule] >= min(float(value), 1.35) or merged[rule] >= float(value)
        effective = RevenueScorer._business_type_weight_multiplier(rule, "trust_conversion", business_type)
        assert 0.75 <= effective <= 1.35


@pytest.mark.parametrize("business_type", sorted(BUSINESS_DEEP_DIVE_PACKS))
def test_business_concept_observation_is_non_scoring_and_type_specific(business_type):
    pack = get_business_deep_dive_pack(business_type)
    concept, terms = next(iter(pack["concepts"].items()))
    text = " ".join(terms[:2])
    result = observe_pack_concepts(text, business_type)
    assert result["concepts"][concept]["observed"] is True
    assert result["observed_concept_count"] >= 1
    assert "not a scored failure" in result["policy"].lower()


def test_engine_version_is_v771():
    assert HybridScanner.ENGINE_VERSION == "v7.8.1-universal-path-refinement"


def test_randomized_business_phrase_resilience_across_all_types():
    rng = random.Random(734)
    # 20 shuffled/sampled evidence variants per business family = 360 randomized cases.
    for business_type, _, title, h1, base_text, actions in BUSINESS_CASES:
        phrases = [p for p, w in BUSINESS_PHRASE_EXPANSIONS.get(business_type, ()) if float(w) >= 3.0]
        assert phrases, business_type
        successes = 0
        trials = 20
        for _ in range(trials):
            sample_size = min(len(phrases), max(4, int(len(phrases) * rng.uniform(0.35, 0.70))))
            sample = rng.sample(phrases, sample_size)
            rng.shuffle(sample)
            text = " ".join(sample) + " " + " ".join(base_text.split()[:12])
            profile = infer_architecture_profile({
                "title": title,
                "h1_tags": [h1],
                "page_text": text,
                "journey_text_sample": text,
                "mobile_cta_types": actions,
            }, "auto")
            if profile["business_type"] == business_type:
                successes += 1
        # This is resilience, not a forced-perfect benchmark. Every family must survive most partial/noisy variants.
        assert successes >= 16, (business_type, successes, trials)


def test_randomized_journey_phrase_resilience_all_journeys():
    rng = random.Random(735)
    action_for = {
        "lead_quote": "quote", "appointment_consultation": "book", "reservation_event": "reserve",
        "direct_purchase": "buy", "demo_sales": "demo", "membership_subscription": "join",
        "donation_support": "donate", "application_enrollment": "apply",
    }
    for journey, items in JOURNEY_PHRASE_EXPANSIONS.items():
        strong = [p for p, w in items if float(w) >= 5.0]
        assert strong, journey
        action = action_for[journey]
        successes = 0
        for _ in range(20):
            k = min(len(strong), max(2, int(len(strong) * rng.uniform(0.35, 0.75))))
            sample = rng.sample(strong, k)
            rng.shuffle(sample)
            profile = infer_architecture_profile({
                "title": "Organization",
                "h1_tags": ["Get started"],
                "page_text": " ".join(sample),
                "journey_text_sample": " ".join(sample),
                "mobile_cta_types": [action],
            }, "auto")
            if profile["journey_model"] == journey:
                successes += 1
        assert successes >= 16, (journey, successes)
