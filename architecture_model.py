"""Trilloka Business Type + Journey + Context architecture model (v7.3).

V7.3 deliberately keeps three separate ideas instead of collapsing them into one label:

1) Business type — what commercial model the organization most closely operates.
2) Customer journey — how a visitor appears to create value on the public website.
3) Context — obligations/conditions that change the importance of individual checks.

Business type is a first-class scoring input.  It supplies bounded priors and later scoring
multipliers, but observed customer actions still determine the website journey.  This lets the
same business type support more than one journey and prevents a single industry label from
forcing obviously contradictory website conclusions.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Set, Tuple

from commercial_knowledge import (
    BUSINESS_PHRASE_EXPANSIONS, JOURNEY_PHRASE_EXPANSIONS,
    GENERAL_DISCOVERY_TERMS, GENERAL_PAGE_GUESSES,
    LOCAL_TERM_EXPANSIONS, HOSPITALITY_TERM_EXPANSIONS,
)

from pathway_markers import infer_subtype, resolve_journeys, build_differentiation_plan


BUSINESS_TYPE_LABELS: Dict[str, str] = {
    "general": "General / Unresolved Business",
    "ecommerce": "E-commerce / Retail",
    "marketplace": "Marketplace / Multi-Sided Commerce",
    "local_service": "Local Service",
    "professional_service": "Professional Service",
    "healthcare": "Healthcare / Clinical Service",
    "medspa": "MedSpa / Aesthetic Service",
    "legal": "Legal Service",
    "financial_services": "Financial / Advisory Service",
    "real_estate": "Real Estate",
    "restaurant": "Restaurant / Food Service",
    "hospitality_event": "Hospitality / Event / Tourism",
    "saas": "SaaS / Software",
    "b2b": "B2B / Industrial / Enterprise",
    "agency": "Agency / Creative / Marketing",
    "membership_creator": "Membership / Creator / Community",
    "education": "Education / Training",
    "nonprofit": "Nonprofit / Charity",
    "automotive": "Automotive / Dealer / Repair",
}

JOURNEY_LABELS: Dict[str, str] = {
    "lead_quote": "Lead / Quote",
    "appointment_consultation": "Appointment / Consultation",
    "reservation_event": "Reservation / Event",
    "direct_purchase": "Direct Purchase",
    "demo_sales": "Demo / Sales",
    "membership_subscription": "Membership / Subscription",
    "donation_support": "Donation / Support",
    "application_enrollment": "Application / Enrollment",
    "general": "General / Unresolved Journey",
}

JOURNEY_PRIMARY_CONVERSION: Dict[str, str] = {
    "lead_quote": "qualified_lead_or_quote",
    "appointment_consultation": "appointment_or_consultation",
    "reservation_event": "reservation_or_event_enquiry",
    "direct_purchase": "purchase_or_checkout",
    "demo_sales": "demo_trial_or_sales_contact",
    "membership_subscription": "subscribe_join_or_membership",
    "donation_support": "donation_or_support_commitment",
    "application_enrollment": "application_registration_or_enrollment",
    "general": "primary_site_action",
}

JOURNEY_SECONDARY_CONVERSIONS: Dict[str, List[str]] = {
    "lead_quote": ["contact_form", "call", "booking"],
    "appointment_consultation": ["contact_form", "call", "directions"],
    "reservation_event": ["contact_form", "call", "directions"],
    "direct_purchase": ["product_question", "chat", "contact"],
    "demo_sales": ["contact_form", "call", "chat"],
    "membership_subscription": ["contact", "follow", "community"],
    "donation_support": ["contact", "volunteer", "newsletter"],
    "application_enrollment": ["contact", "book", "information_request"],
    "general": ["contact"],
}

CONTEXT_LABELS: Dict[str, str] = {
    "regulated_high_trust": "Regulated / High-Trust",
    "local_location_dependent": "Local / Location-Dependent",
    "commerce_payment": "Commerce / Payment",
    "sensitive_data": "Sensitive-Data Collection",
    "enterprise_considered_purchase": "Enterprise / Considered Purchase",
    "hospitality_event": "Hospitality / Event",
    "recurring_commitment": "Recurring / Ongoing Commitment",
    "donation_public_trust": "Donation / Public-Trust Context",
}

# Common low-weight foundation layer. These checks are intentionally business-agnostic.
COMMON_FOUNDATION_IDS = frozenset({1, 2, *range(16, 36)})
ARCHITECTURAL_CHECKPOINT_IDS = frozenset(set(range(1, 51)) - set(COMMON_FOUNDATION_IDS))

# Journey URL priority terms. These choose evidence pages; they do not score by themselves.
JOURNEY_PAGE_TERMS: Dict[str, Tuple[str, ...]] = {
    "lead_quote": (
        "quote", "estimate", "contact", "consultation", "enquiry", "inquiry", "request",
        "services", "projects", "portfolio", "reviews", "about", "team", "pricing",
    ),
    "appointment_consultation": (
        "appointment", "book", "booking", "schedule", "consultation", "patient", "treatment",
        "services", "team", "credentials", "reviews", "contact", "pricing",
    ),
    "reservation_event": (
        "reserve", "reservation", "booking", "book", "charter", "cruise", "event", "venue",
        "tour", "rental", "wedding", "corporate", "contact", "reviews", "menu",
    ),
    "direct_purchase": (
        "product", "products", "shop", "cart", "checkout", "order", "shipping", "delivery",
        "returns", "refund", "contact", "reviews", "faq",
    ),
    "demo_sales": (
        "demo", "contact-sales", "contact", "pricing", "plans", "trial", "signup", "sign-up",
        "security", "customers", "case-studies", "solutions", "integrations",
    ),
    "membership_subscription": (
        "subscribe", "join", "membership", "newsletter", "courses", "community", "pricing", "about", "contact",
    ),
    "donation_support": (
        "donate", "donation", "give", "support", "impact", "programs", "about", "financials", "contact", "volunteer",
    ),
    "application_enrollment": (
        "apply", "application", "enroll", "enrol", "admissions", "register", "registration", "programs", "courses", "tuition", "contact",
    ),
    "general": GENERAL_DISCOVERY_TERMS,
}

JOURNEY_PAGE_GUESSES: Dict[str, List[str]] = {
    "lead_quote": ["/contact/", "/request-a-quote/", "/quote/", "/services/", "/projects/"],
    "appointment_consultation": ["/book/", "/appointments/", "/consultation/", "/services/", "/contact/"],
    "reservation_event": ["/reservations/", "/book/", "/events/", "/charters/", "/contact/"],
    "direct_purchase": ["/shop/", "/products/", "/cart/", "/checkout/", "/returns/"],
    "demo_sales": ["/demo/", "/contact-sales/", "/pricing/", "/solutions/", "/case-studies/"],
    "membership_subscription": ["/subscribe/", "/join/", "/membership/", "/pricing/", "/community/"],
    "donation_support": ["/donate/", "/give/", "/support/", "/impact/", "/about/"],
    "application_enrollment": ["/apply/", "/admissions/", "/enroll/", "/register/", "/programs/"],
    "general": GENERAL_PAGE_GUESSES,
}

JOURNEY_EXPECTED_ACTIONS: Dict[str, Set[str]] = {
    "lead_quote": {"quote", "contact", "call", "book"},
    "appointment_consultation": {"book", "contact", "call", "reserve"},
    "reservation_event": {"reserve", "book", "contact", "call", "directions", "order"},
    "direct_purchase": {"add_to_cart", "buy", "order", "checkout"},
    "demo_sales": {"demo", "trial", "contact", "quote", "book"},
    "membership_subscription": {"subscribe", "join", "contact", "buy"},
    "donation_support": {"donate", "support", "contact", "subscribe"},
    "application_enrollment": {"apply", "register", "enroll", "contact", "book"},
    "general": {"buy", "order", "reserve", "book", "call", "quote", "trial", "demo", "subscribe", "contact", "donate", "apply", "register"},
}

# Business-type priors are deliberately bounded. They influence journey selection because the user
# explicitly wants business type to affect scoring, but direct on-page actions can still outweigh them.
BUSINESS_TYPE_JOURNEY_PRIORS: Dict[str, Dict[str, float]] = {
    "general": {},
    "ecommerce": {"direct_purchase": 8.0},
    "marketplace": {"direct_purchase": 6.0, "membership_subscription": 2.0},
    "local_service": {"lead_quote": 7.0, "appointment_consultation": 2.0},
    "professional_service": {"lead_quote": 5.0, "appointment_consultation": 4.0},
    "healthcare": {"appointment_consultation": 8.0, "lead_quote": 1.0},
    "medspa": {"appointment_consultation": 8.0, "direct_purchase": 1.5},
    "legal": {"appointment_consultation": 6.5, "lead_quote": 3.5},
    "financial_services": {"appointment_consultation": 6.5, "lead_quote": 3.0, "application_enrollment": 1.0},
    "real_estate": {"lead_quote": 5.5, "appointment_consultation": 4.0},
    "restaurant": {"reservation_event": 7.5, "direct_purchase": 2.5},
    "hospitality_event": {"reservation_event": 8.0, "direct_purchase": 1.0},
    "saas": {"demo_sales": 7.5, "membership_subscription": 2.5},
    "b2b": {"demo_sales": 6.5, "lead_quote": 4.0},
    "agency": {"lead_quote": 6.5, "demo_sales": 3.0},
    "membership_creator": {"membership_subscription": 8.0, "direct_purchase": 1.5},
    "education": {"application_enrollment": 7.0, "membership_subscription": 2.5},
    "nonprofit": {"donation_support": 8.0, "membership_subscription": 1.5},
    "automotive": {"lead_quote": 4.5, "appointment_consultation": 3.5, "direct_purchase": 2.0},
}

# Compatibility mapping for older callers. Unlike v7.2 this is no longer merely a weak hint:
# it first resolves a business type, then that business type supplies bounded journey priors.
LEGACY_HINT_TO_JOURNEY: Dict[str, str] = {
    "restaurant": "reservation_event",
    "local_service": "lead_quote",
    "professional_service": "lead_quote",
    "healthcare": "appointment_consultation",
    "medspa": "appointment_consultation",
    "legal": "appointment_consultation",
    "financial_services": "appointment_consultation",
    "real_estate": "lead_quote",
    "ecommerce": "direct_purchase",
    "marketplace": "direct_purchase",
    "saas": "demo_sales",
    "agency": "lead_quote",
    "b2b": "demo_sales",
    "creator": "membership_subscription",
    "membership_creator": "membership_subscription",
    "education": "application_enrollment",
    "nonprofit": "donation_support",
    "automotive": "lead_quote",
    "general": "general",
}

JOURNEY_COMPETITOR_SEARCH_TEXT: Dict[str, str] = {
    "lead_quote": "service provider",
    "appointment_consultation": "appointment based service",
    "reservation_event": "reservation event service",
    "direct_purchase": "retail store",
    "demo_sales": "business services company",
    "membership_subscription": "membership service",
    "donation_support": "nonprofit charity",
    "application_enrollment": "education training provider",
    "general": "business",
}

JOURNEY_PHRASES: Dict[str, Tuple[Tuple[str, float], ...]] = {
    "lead_quote": (
        ("request a quote", 7.0), ("get a quote", 7.0), ("free estimate", 6.0), ("request estimate", 6.0),
        ("project consultation", 5.0), ("enquire now", 5.0), ("inquire now", 5.0), ("request service", 5.0),
        ("general contractor", 4.0), ("custom home", 4.0), ("renovation", 3.0), ("moving company", 3.0),
        ("cleaning service", 3.0), ("professional services", 2.0), ("contact us", 1.2),
    ),
    "appointment_consultation": (
        ("book appointment", 7.0), ("schedule appointment", 7.0), ("book a consultation", 6.5),
        ("schedule a consultation", 6.5), ("new patient", 5.0), ("patient", 2.0),
        ("physiotherapy", 5.0), ("physiotherapist", 5.0), ("dentist", 5.0), ("dental clinic", 5.0),
        ("chiropractic", 4.0), ("medical clinic", 4.0), ("med spa", 4.0), ("medspa", 4.0),
        ("law firm", 3.0), ("lawyer", 3.0), ("consultation", 2.0),
    ),
    "reservation_event": (
        ("private charter", 8.0), ("boat charter", 8.0), ("yacht charter", 8.0), ("charter specialists", 8.0),
        ("cruise", 6.0), ("charter", 6.0), ("private event", 6.0), ("corporate event", 6.0),
        ("wedding", 5.0), ("event venue", 6.0), ("venue", 3.0), ("tour", 3.5), ("rental", 3.5),
        ("reserve", 4.0), ("reservation", 4.0), ("book a table", 6.0), ("catering", 3.0),
        ("restaurant", 3.0), ("dining", 1.5), ("menu", 0.6), ("dinner", 0.5), ("food", 0.4),
    ),
    "direct_purchase": (
        ("add to cart", 8.0), ("checkout", 7.0), ("buy now", 7.0), ("shop now", 6.0),
        ("shopping cart", 6.0), ("order online", 5.5), ("shipping", 2.0), ("returns", 2.0),
        ("product", 1.2), ("shop", 1.5),
    ),
    "demo_sales": (
        ("request a demo", 8.0), ("book a demo", 8.0), ("contact sales", 8.0), ("start free trial", 7.0),
        ("free trial", 6.0), ("enterprise", 4.5), ("procurement", 4.0), ("manufacturer", 3.0),
        ("industrial", 3.0), ("wholesale", 3.0), ("platform", 1.2), ("software", 1.2), ("solutions", 1.0),
    ),
    "membership_subscription": (
        ("join now", 7.0), ("become a member", 7.0), ("membership", 5.0), ("subscribe", 5.0),
        ("newsletter", 2.5), ("community", 2.0), ("course", 2.0), ("cohort", 2.5),
    ),
    "donation_support": (
        ("donate now", 8.0), ("make a donation", 8.0), ("support our work", 6.5), ("give today", 7.0),
        ("monthly donor", 6.0), ("charity", 4.0), ("nonprofit", 4.0), ("our impact", 3.0), ("volunteer", 2.0),
    ),
    "application_enrollment": (
        ("apply now", 8.0), ("start your application", 8.0), ("enroll now", 7.0), ("enrol now", 7.0),
        ("register now", 6.0), ("admissions", 5.0), ("application deadline", 5.0), ("tuition", 3.0),
        ("programs", 1.5), ("courses", 1.5),
    ),
}

# Business inference phrases. Strong brand/business descriptors receive more weight than incidental copy.
BUSINESS_TYPE_PHRASES: Dict[str, Tuple[Tuple[str, float], ...]] = {
    "ecommerce": (("online store", 7), ("shop online", 6), ("add to cart", 7), ("shipping", 2), ("returns", 2)),
    "marketplace": (("marketplace", 8), ("buyers and sellers", 8), ("sell on", 5), ("vendors", 4), ("list your", 3)),
    "local_service": (("service area", 6), ("free estimate", 5), ("home services", 5), ("contractor", 4), ("plumbing", 4), ("cleaning service", 4), ("moving company", 4)),
    "professional_service": (("professional services", 7), ("consulting", 5), ("consultants", 5), ("accounting", 5), ("advisory", 4)),
    "healthcare": (("medical clinic", 8), ("health clinic", 7), ("patient", 4), ("doctor", 5), ("dentist", 6), ("physiotherapy", 6), ("chiropractic", 5)),
    "medspa": (("medspa", 9), ("med spa", 9), ("aesthetic clinic", 7), ("botox", 5), ("laser treatment", 4)),
    "legal": (("law firm", 9), ("lawyer", 7), ("attorney", 7), ("legal services", 6)),
    "financial_services": (("financial advisor", 8), ("wealth management", 8), ("investment advisor", 8), ("insurance broker", 6), ("mortgage", 5), ("financial planning", 7)),
    "real_estate": (("real estate", 8), ("realtor", 8), ("homes for sale", 7), ("property listings", 6), ("realty", 6)),
    "restaurant": (("restaurant", 8), ("book a table", 7), ("menu", 2), ("dining", 3), ("takeout", 3)),
    "hospitality_event": (("hotel", 7), ("event venue", 8), ("wedding venue", 8), ("tour", 5), ("charter", 7), ("vacation rental", 6)),
    "saas": (("software as a service", 9), ("saas", 9), ("software platform", 7), ("start free trial", 6), ("integrations", 3)),
    "b2b": (("b2b", 8), ("enterprise", 5), ("manufacturer", 6), ("manufacturing", 6), ("industrial", 5), ("wholesale", 5), ("logistics", 4)),
    "agency": (("marketing agency", 9), ("design agency", 9), ("creative agency", 9), ("digital agency", 8), ("advertising agency", 8)),
    "membership_creator": (("membership", 5), ("creator", 5), ("community", 3), ("newsletter", 3), ("patreon", 5)),
    "education": (("school", 6), ("academy", 6), ("university", 8), ("college", 8), ("admissions", 7), ("training program", 6), ("course", 2)),
    "nonprofit": (("nonprofit", 9), ("non-profit", 9), ("charity", 8), ("donate", 5), ("foundation", 5), ("registered charity", 9)),
    "automotive": (("auto repair", 8), ("car dealership", 8), ("dealership", 6), ("vehicle service", 6), ("service appointment", 4), ("used cars", 5)),
}

# V7.3.2 knowledge expansion: same inference/scoring logic, larger evidence vocabulary.
def _merge_weighted_phrase_library(base, expansion):
    merged = {}
    for key in set(base) | set(expansion):
        seen = {}
        for phrase, weight in tuple(base.get(key, ())) + tuple(expansion.get(key, ())):
            seen[str(phrase).lower()] = max(float(weight), float(seen.get(str(phrase).lower(), 0.0)))
        merged[key] = tuple(seen.items())
    return merged

JOURNEY_PHRASES = _merge_weighted_phrase_library(JOURNEY_PHRASES, JOURNEY_PHRASE_EXPANSIONS)
BUSINESS_TYPE_PHRASES = _merge_weighted_phrase_library(BUSINESS_TYPE_PHRASES, BUSINESS_PHRASE_EXPANSIONS)

REGULATED_TERMS = (
    "law firm", "lawyer", "attorney", "legal services", "physiotherapy", "physiotherapist", "medical clinic",
    "dentist", "dental clinic", "chiropractic", "psychologist", "counselling", "counseling", "podiatry",
    "registered massage therapist", "occupational therapy", "speech therapy", "chartered professional accountant",
    "financial advisor", "investment advisor", "securities", "insurance broker", "pharmacy",
)
SENSITIVE_TERMS = (
    "patient", "medical", "health history", "health information", "diagnosis", "symptom", "insurance claim",
    "case details", "financial information", "tax return", "credit card",
)
LOCAL_TERMS = (
    "service area", "directions", "visit us", "our location", "locations", "vancouver", "burnaby", "surrey",
    "richmond", "north vancouver", "west vancouver", "coquitlam", "new westminster",
)
ENTERPRISE_TERMS = (
    "enterprise", "corporate", "commercial", "industrial", "manufacturer", "manufacturing", "wholesale",
    "procurement", "custom project", "custom home", "request a quote", "case study", "case studies",
)
HOSPITALITY_EVENT_TERMS = (
    "wedding", "venue", "cruise", "charter", "yacht", "tour", "reservation",
    "restaurant", "catering", "hotel", "banquet", "rental",
) + tuple(HOSPITALITY_TERM_EXPANSIONS)
LOCAL_TERMS = tuple(LOCAL_TERMS) + tuple(LOCAL_TERM_EXPANSIONS)


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    if parsed is None or not math.isfinite(parsed):
        return None
    return parsed


def _normalize_hint(raw: Any) -> str:
    value = str(raw or "auto").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "professional_services": "professional_service", "home_service": "local_service", "aesthetics": "medspa",
        "health": "healthcare", "medical": "healthcare", "clinic": "healthcare",
        "law": "legal", "software": "saas", "commerce": "ecommerce", "e_commerce": "ecommerce",
        "store": "ecommerce", "retail": "ecommerce", "creator": "membership_creator", "content_creator": "membership_creator",
        "financial": "financial_services", "finance": "financial_services", "realty": "real_estate",
        "charity": "nonprofit", "non_profit": "nonprofit", "school": "education", "training": "education",
        "hotel": "hospitality_event", "events": "hospitality_event", "food_service": "restaurant", "cafe": "restaurant", "café": "restaurant",
        "auto_repair": "automotive", "dealer": "automotive", "auto": "auto", "": "auto",
        # Direct journey hints remain supported for API/backward compatibility.
        "lead": "lead_quote", "quote": "lead_quote", "lead_quote": "lead_quote",
        "appointment": "appointment_consultation", "consultation": "appointment_consultation", "appointment_consultation": "appointment_consultation",
        "reservation": "reservation_event", "event": "reservation_event", "reservation_event": "reservation_event",
        "purchase": "direct_purchase", "direct_purchase": "direct_purchase",
        "demo": "demo_sales", "sales": "demo_sales", "demo_sales": "demo_sales",
        "membership": "membership_subscription", "subscription": "membership_subscription", "membership_subscription": "membership_subscription",
        "donation": "donation_support", "donate": "donation_support", "donation_support": "donation_support",
        "application": "application_enrollment", "enrollment": "application_enrollment", "enrolment": "application_enrollment",
        "application_enrollment": "application_enrollment",
    }
    return aliases.get(value, value)


def _text_surfaces(data: Mapping[str, Any]) -> Dict[str, str]:
    title = str(data.get("title") or "")
    meta = str(data.get("meta_description") or "")
    h1 = " ".join(str(x) for x in (data.get("h1_tags") or []) if x)
    page = str(data.get("page_text") or "")[:32000]
    journey = str(data.get("journey_text_sample") or "")[:30000]
    schema = " ".join(str(x) for x in (data.get("schema_types") or []) if x)
    return {
        "hero": f"{title} {h1}".lower(),
        "meta": meta.lower(),
        "body": f"{page} {journey} {schema}".lower(),
        "all": f"{title} {h1} {meta} {page} {journey} {schema}".lower(),
    }


def _add_phrase_scores(scores: Dict[str, float], signals: Dict[str, List[str]], surfaces: Mapping[str, str]) -> None:
    for model, weighted_phrases in JOURNEY_PHRASES.items():
        for phrase, weight in weighted_phrases:
            if phrase in surfaces["hero"]:
                scores[model] += weight * 1.8
                signals[model].append(f"hero:{phrase}")
            elif phrase in surfaces["meta"]:
                scores[model] += weight * 1.35
                signals[model].append(f"meta:{phrase}")
            elif phrase in surfaces["body"]:
                scores[model] += weight
                signals[model].append(phrase)


def infer_business_type(data: Mapping[str, Any], requested_hint: Any = "auto") -> Dict[str, Any]:
    """Infer/resolve a broad business type separately from the customer journey.

    A recognized explicit business type is authoritative for scoring (the user chose it). Auto mode
    uses page, action, schema and local-place evidence. Confidence is deliberately capped when only
    weak textual evidence exists.
    """
    hint = _normalize_hint(requested_hint)
    if hint in BUSINESS_TYPE_LABELS and hint != "general":
        return {
            "business_type": hint,
            "business_type_label": BUSINESS_TYPE_LABELS[hint],
            "confidence": 1.0,
            "source": "explicit_request",
            "signals": [f"requested:{hint}"],
            "score_candidates": {hint: 100.0},
        }
    if hint == "general":
        return {
            "business_type": "general",
            "business_type_label": BUSINESS_TYPE_LABELS["general"],
            "confidence": 1.0,
            "source": "explicit_request",
            "signals": ["requested:general"],
            "score_candidates": {"general": 100.0},
        }

    # Backward-compatible hint from older scanner payloads. This is treated as a strong prior,
    # not a new asserted truth, unless the legacy profile itself carried high confidence.
    legacy_profile = data.get("business_profile") if isinstance(data.get("business_profile"), Mapping) else {}
    legacy_raw = legacy_profile.get("business_type") or legacy_profile.get("vertical") or data.get("legacy_business_type")
    legacy_type = _normalize_hint(legacy_raw) if legacy_raw else "auto"
    if legacy_type in BUSINESS_TYPE_LABELS and legacy_type != "general":
        try:
            legacy_conf = float(legacy_profile.get("business_type_confidence") or legacy_profile.get("confidence") or 0.0)
        except (TypeError, ValueError):
            legacy_conf = 0.0
        if legacy_conf >= 0.80:
            return {
                "business_type": legacy_type,
                "business_type_label": BUSINESS_TYPE_LABELS[legacy_type],
                "confidence": min(0.96, legacy_conf),
                "source": "legacy_profile_hint",
                "signals": [f"legacy_profile:{legacy_type}"],
                "score_candidates": {legacy_type: round(10.0 * legacy_conf, 2)},
            }

    surfaces = _text_surfaces(data)
    scores: Dict[str, float] = {key: 0.0 for key in BUSINESS_TYPE_LABELS if key != "general"}
    signals: Dict[str, List[str]] = {key: [] for key in scores}
    for business_type, weighted_phrases in BUSINESS_TYPE_PHRASES.items():
        for phrase, weight in weighted_phrases:
            if phrase in surfaces["hero"]:
                scores[business_type] += float(weight) * 1.8
                signals[business_type].append(f"hero:{phrase}")
            elif phrase in surfaces["meta"]:
                scores[business_type] += float(weight) * 1.35
                signals[business_type].append(f"meta:{phrase}")
            elif phrase in surfaces["body"]:
                scores[business_type] += float(weight)
                signals[business_type].append(phrase)

    # V7.4 adaptive knowledge memory is recognition-only and deliberately bounded. Only ACTIVE
    # learned patterns may contribute here; they cannot touch scoring, applicability or findings.
    overlay = data.get("learning_overlay") if isinstance(data.get("learning_overlay"), Mapping) else {}
    learned_scores = overlay.get("scores") if isinstance(overlay.get("scores"), Mapping) else {}
    learned_terms = overlay.get("matched_terms") if isinstance(overlay.get("matched_terms"), Mapping) else {}
    for learned_type, raw_boost in learned_scores.items():
        if learned_type not in scores:
            continue
        try:
            boost = max(0.0, min(4.0, float(raw_boost)))
        except (TypeError, ValueError):
            continue
        if boost <= 0:
            continue
        scores[learned_type] += boost
        for term in list(learned_terms.get(learned_type) or [])[:4]:
            signals[learned_type].append(f"learned:{term}")

    schema_types = {str(x).lower() for x in (data.get("schema_types") or []) if x}
    schema_map = {
        "restaurant": "restaurant", "foodestablishment": "restaurant", "store": "ecommerce", "product": "ecommerce",
        "medicalbusiness": "healthcare", "physician": "healthcare", "dentist": "healthcare", "legalservice": "legal",
        "financialservice": "financial_services", "realestateagent": "real_estate", "softwareapplication": "saas",
        "educationalorganization": "education", "school": "education", "collegeoruniversity": "education",
        "ngo": "nonprofit", "automotivebusiness": "automotive", "autodealer": "automotive", "autorepair": "automotive",
    }
    for schema, btype in schema_map.items():
        if schema in schema_types and btype in scores:
            scores[btype] += 7.0
            signals[btype].append(f"schema:{schema}")

    if data.get("add_to_cart_visible") or data.get("checkout_context_detected"):
        scores["ecommerce"] += 5.0
        signals["ecommerce"].append("commerce-path")
    if data.get("address_location_visible") and data.get("phone_number_visible"):
        scores["local_service"] += 1.5
        signals["local_service"].append("local-address-phone")
    if data.get("places_found") and str(data.get("places_confidence") or "").lower() == "high":
        primary_type = str(data.get("place_primary_type") or "").lower()
        place_map = {
            "restaurant": "restaurant", "cafe": "restaurant", "dentist": "healthcare", "doctor": "healthcare",
            "lawyer": "legal", "real_estate_agency": "real_estate", "car_dealer": "automotive", "car_repair": "automotive",
        }
        if primary_type in place_map:
            btype = place_map[primary_type]
            scores[btype] += 6.0
            signals[btype].append(f"google-place:{primary_type}")

    # Service-line contamination guardrail. A broad B2B/agency/local company can mention a
    # specialist service (for example a remote medical capability) without that one body phrase
    # redefining the whole business. Regulated/high-trust types therefore need either strong
    # hero/meta/schema/place evidence or more than one independent body signal before they can
    # outrank another credible business model. This changes classification confidence only; it
    # never creates or removes a checkpoint result by itself.
    for specialist in ("healthcare", "medspa", "legal", "financial_services"):
        specialist_signals = signals.get(specialist) or []
        if not specialist_signals:
            continue
        strong_surface = any(
            str(sig).startswith(("hero:", "meta:", "schema:", "google-place:"))
            for sig in specialist_signals
        )
        body_signal_count = sum(
            1 for sig in specialist_signals
            if not str(sig).startswith(("hero:", "meta:", "schema:", "google-place:"))
        )
        strongest_other = max((value for key, value in scores.items() if key != specialist), default=0.0)
        if not strong_surface and body_signal_count <= 1 and strongest_other >= 4.0:
            scores[specialist] = min(scores[specialist], strongest_other * 0.80)
            signals[specialist].append("guardrail:single-service-line-body-signal")

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_type, top_score = ranked[0] if ranked else ("general", 0.0)
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = max(0.0, top_score - second)
    if top_score < 4.0:
        return {
            "business_type": "general",
            "business_type_label": BUSINESS_TYPE_LABELS["general"],
            "confidence": 0.45 if top_score <= 0 else min(0.64, 0.46 + top_score * 0.03),
            "source": "auto_inference",
            "signals": [],
            "score_candidates": {k: round(v, 2) for k, v in ranked[:8]},
        }
    confidence = max(0.52, min(0.96, 0.50 + min(0.28, top_score * 0.014) + min(0.18, margin * 0.025)))
    result = {
        "business_type": top_type,
        "business_type_label": BUSINESS_TYPE_LABELS.get(top_type, top_type.replace("_", " ").title()),
        "confidence": round(confidence, 2),
        "source": "auto_inference",
        "signals": list(dict.fromkeys(signals[top_type]))[:12],
        "score_candidates": {k: round(v, 2) for k, v in ranked[:8]},
    }
    if isinstance(overlay.get("archetype"), Mapping) and overlay.get("archetype"):
        result["learned_archetype_hint"] = dict(overlay.get("archetype") or {})
    if learned_scores:
        result["learning_memory_applied"] = True
    return result


def infer_context_tags(data: Mapping[str, Any], journey_model: str = "general", business_type: str = "general") -> Tuple[List[str], Dict[str, List[str]]]:
    surfaces = _text_surfaces(data)
    text = surfaces["all"]
    tags: List[str] = []
    reasons: Dict[str, List[str]] = {}

    def mark(tag: str, why: Iterable[str]) -> None:
        vals = [str(x) for x in why if x]
        if vals:
            tags.append(tag)
            reasons[tag] = vals[:8]

    raw_regulated_hits = [term for term in REGULATED_TERMS if term in text]
    regulated_business = business_type in {"healthcare", "medspa", "legal", "financial_services"}
    if regulated_business:
        regulated_hits = list(raw_regulated_hits) + [f"business-type:{business_type}"]
    else:
        # Do not turn a diversified company into a regulated/high-trust business merely because
        # one specialist capability is mentioned in body copy. Outside a regulated business type,
        # require hero/meta prominence or multiple independent regulated signals.
        hero_meta = f"{surfaces['hero']} {surfaces['meta']}"
        prominent = [term for term in raw_regulated_hits if term in hero_meta]
        regulated_hits = list(raw_regulated_hits) if len(set(raw_regulated_hits)) >= 2 else prominent
    mark("regulated_high_trust", regulated_hits)

    geographic_terms = {"vancouver", "burnaby", "surrey", "richmond", "north vancouver", "west vancouver", "coquitlam", "new westminster"}
    structural_local_terms = {"service area", "directions", "visit us", "our location", "locations"}
    local_hits: List[str] = []
    if data.get("address_location_visible") is True:
        local_hits.append("verified address/location")
    if data.get("places_found") and str(data.get("places_confidence") or "") == "high":
        local_hits.append("verified Google Place identity")
    if any(term in text for term in structural_local_terms):
        local_hits.extend(term for term in structural_local_terms if term in text)
    local_business_type = business_type in {"local_service", "restaurant", "hospitality_event", "automotive", "real_estate"}
    if local_business_type and data.get("phone_number_visible") is True:
        local_hits.append("verified local phone path")
    # A phone number by itself is not enough to classify a national/enterprise lead site as local.
    # Journey types may still become local when real geographic/location evidence is present.
    if journey_model in {"lead_quote", "appointment_consultation", "reservation_event"} or local_business_type:
        local_hits.extend(term for term in geographic_terms if term in text)
    mark("local_location_dependent", local_hits)

    commerce_hits: List[str] = []
    if data.get("add_to_cart_visible"):
        commerce_hits.append("add-to-cart")
    if data.get("checkout_context_detected"):
        commerce_hits.append("checkout")
    if data.get("shipping_info_linked") or data.get("return_policy_linked"):
        commerce_hits.append("shipping/return policy")
    if journey_model == "direct_purchase" or business_type in {"ecommerce", "marketplace"}:
        commerce_hits.append("commerce business/journey")
    mark("commerce_payment", commerce_hits)

    raw_sensitive_hits = [term for term in SENSITIVE_TERMS if term in text]
    sensitive_hits: List[str] = []
    # Sensitive-data COLLECTION requires a plausible collection surface. Merely discussing a
    # medical/legal/financial service somewhere on the site is not enough. This prevents broader
    # business sites from inheriting high-trust weighting from incidental vocabulary.
    if data.get("forms_present"):
        explicit_sensitive = {
            "patient", "health history", "health information", "diagnosis", "symptom",
            "insurance claim", "case details", "financial information", "tax return", "credit card",
        }
        sensitive_hits.extend(term for term in raw_sensitive_hits if regulated_business or term in explicit_sensitive)
        if regulated_hits:
            sensitive_hits.append("regulated-context form")
    mark("sensitive_data", sensitive_hits)

    enterprise_hits = [term for term in ENTERPRISE_TERMS if term in text]
    if journey_model == "demo_sales" or business_type in {"b2b", "saas", "agency"}:
        enterprise_hits.append("enterprise/considered-purchase business or journey")
    mark("enterprise_considered_purchase", enterprise_hits)

    hospitality_hits = [term for term in HOSPITALITY_EVENT_TERMS if re.search(r"\b" + re.escape(term) + r"\b", text)]
    if journey_model == "reservation_event" or business_type in {"restaurant", "hospitality_event"}:
        hospitality_hits.append("hospitality/reservation business or journey")
    mark("hospitality_event", hospitality_hits)

    recurring_hits: List[str] = []
    if journey_model == "membership_subscription" or business_type in {"saas", "membership_creator"}:
        recurring_hits.append("recurring/subscription model")
    if any(token in text for token in ("monthly", "annual plan", "subscription", "membership", "auto-renew")):
        recurring_hits.append("recurring terms detected")
    mark("recurring_commitment", recurring_hits)

    donation_hits: List[str] = []
    if journey_model == "donation_support" or business_type == "nonprofit":
        donation_hits.append("donation/nonprofit model")
    if any(token in text for token in ("donate", "registered charity", "tax receipt", "our impact")):
        donation_hits.append("donation/impact language")
    mark("donation_public_trust", donation_hits)

    ordered = [tag for tag in CONTEXT_LABELS if tag in tags]
    return ordered, reasons


def infer_architecture_profile(data: Mapping[str, Any], requested_hint: Any = "auto") -> Dict[str, Any]:
    """Infer business type, customer journey and context from public evidence.

    Business type influences the expected importance and journey priors. Observed actions still
    dominate enough to reveal hybrid behavior instead of blindly forcing an industry template.
    """
    hint = _normalize_hint(requested_hint)
    force_general_journey = hint == "general"
    direct_journey_hint = hint if hint in JOURNEY_LABELS and hint != "general" else ""
    business_hint = "auto" if direct_journey_hint else hint
    business = infer_business_type(data, business_hint)
    business_type = str(business.get("business_type") or "general")
    subtype_profile = infer_subtype(data, business_type)
    differentiation_plan = build_differentiation_plan(data, business_type)
    marker_resolution = resolve_journeys(data, business_type)

    surfaces = _text_surfaces(data)
    scores: Dict[str, float] = {model: 0.0 for model in JOURNEY_LABELS if model != "general"}
    signals: Dict[str, List[str]] = {model: [] for model in scores}
    _add_phrase_scores(scores, signals, surfaces)

    # Architecture inference uses both the rendered/homepage mobile actions and verified
    # actions discovered on deeper customer-journey pages. Keep these evidence channels
    # separate in the scanner, but combine them here because the question is what journey
    # the website actually supports, not whether every action is visible on the homepage.
    actions = {str(x).lower() for x in (data.get("mobile_cta_types") or []) if x}
    actions.update(str(x).lower() for x in (data.get("journey_action_types") or []) if x)
    action_weights: Dict[str, Tuple[str, float]] = {
        "quote": ("lead_quote", 9.0), "contact": ("lead_quote", 4.0),
        "reserve": ("reservation_event", 9.0), "order": ("direct_purchase", 7.0),
        "add_to_cart": ("direct_purchase", 12.0), "buy": ("direct_purchase", 10.0),
        "demo": ("demo_sales", 10.0), "trial": ("demo_sales", 9.0),
        "subscribe": ("membership_subscription", 10.0), "join": ("membership_subscription", 10.0),
        "donate": ("donation_support", 12.0), "support": ("donation_support", 5.0),
        "apply": ("application_enrollment", 11.0), "register": ("application_enrollment", 8.0),
        "enroll": ("application_enrollment", 9.0), "enrol": ("application_enrollment", 9.0),
    }
    for action, (model, weight) in action_weights.items():
        if action in actions:
            scores[model] += weight
            signals[model].append(f"action:{action}")
    if "book" in actions:
        scores["appointment_consultation"] += 4.0
        scores["reservation_event"] += 4.0
        signals["appointment_consultation"].append("action:book")
        signals["reservation_event"].append("action:book")

    if data.get("add_to_cart_visible"):
        scores["direct_purchase"] += 12.0
        signals["direct_purchase"].append("verified add-to-cart")
    if data.get("checkout_context_detected"):
        scores["direct_purchase"] += 10.0
        signals["direct_purchase"].append("verified checkout context")
    if data.get("order_online_present"):
        scores["direct_purchase"] += 7.0
        signals["direct_purchase"].append("verified order-online path")
    if data.get("reservation_present"):
        scores["reservation_event"] += 9.0
        signals["reservation_event"].append("verified reservation path")
    if data.get("booking_provider_links"):
        scores["appointment_consultation"] += 3.0
        scores["reservation_event"] += 3.0
    if data.get("pricing_linked") and any(token in surfaces["all"] for token in ("enterprise", "demo", "software", "platform", "solutions")):
        scores["demo_sales"] += 3.0
    if data.get("forms_present") and any(token in surfaces["all"] for token in ("quote", "estimate", "enquiry", "inquiry")):
        scores["lead_quote"] += 4.0

    # Business type is intentionally meaningful. It supplies a bounded prior rather than a forced journey.
    for model, weight in BUSINESS_TYPE_JOURNEY_PRIORS.get(business_type, {}).items():
        if model in scores:
            scores[model] += float(weight)
            signals[model].append(f"business_type_prior:{business_type}")

    # Direct journey hints remain possible and are stronger than priors, but still do not create
    # perfect confidence without corroborating observed evidence.
    if direct_journey_hint in scores:
        scores[direct_journey_hint] += 8.0
        signals[direct_journey_hint].append(f"direct_journey_hint:{direct_journey_hint}")

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_model, top_score = ranked[0] if ranked else ("general", 0.0)
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = max(0.0, top_score - second_score)

    if top_score < 5.0:
        journey_model = "general"
        confidence = 0.45 if top_score <= 0 else min(0.64, 0.48 + top_score * 0.025)
        winning_signals: List[str] = []
    else:
        confidence = 0.50 + min(0.27, top_score * 0.011) + min(0.17, margin * 0.022)
        # Explicit business type is useful context, but a close multi-journey site should not receive 98% certainty.
        if second_score > 0 and second_score / max(top_score, 0.01) >= 0.72:
            confidence = min(confidence, 0.84)
        confidence = max(0.52, min(0.96, confidence))
        journey_model = top_model
        winning_signals = list(dict.fromkeys(signals[top_model]))[:12]

    # An explicit "general" choice is a deliberate neutral scoring mode, not auto-detect.
    # Keep observed candidates as secondary diagnostics, but do not silently replace the requested
    # general journey with a specialized one. Auto mode remains the way to infer a primary journey.
    if force_general_journey:
        journey_model = "general"
        confidence = 1.0
        winning_signals = ["requested:general"]

    secondary_journeys: List[Dict[str, Any]] = []
    if top_score > 0:
        for model, score in ranked[1:4]:
            if score < 4.0:
                continue
            ratio = score / top_score
            if ratio < 0.32:
                continue
            secondary_journeys.append({
                "journey_model": model,
                "journey_label": JOURNEY_LABELS.get(model, model.replace("_", " ").title()),
                "relative_strength": round(ratio, 2),
                "score": round(score, 2),
                "signals": list(dict.fromkeys(signals.get(model) or []))[:6],
            })

    # V7.5 authority resolver: observed customer-path sequences outrank weighted language/priors.
    weighted_journey_model = journey_model
    weighted_confidence = confidence
    if not force_general_journey:
        if marker_resolution.get("resolved"):
            journey_model = str(marker_resolution.get("journey_model") or "general")
            auth = int(marker_resolution.get("authority") or 0)
            confidence = min(0.98, 0.76 + 0.055 * max(0, auth - 3))
            winning_signals = [
                f"marker:{stage}:{marker}"
                for stage, markers in (marker_resolution.get("proof") or {}).items()
                for marker in markers
            ][:12]
            # Secondary journeys must obey the same evidence authority as the primary path.
            # Weighted semantic candidates remain diagnostics only and are never reported as
            # customer journeys unless the current site supplies explicit path evidence.
            secondary_journeys = []
            for item in marker_resolution.get("ranked_paths") or []:
                if str(item.get("journey_model") or "") == journey_model or int(item.get("authority") or 0) < 3:
                    continue
                secondary_journeys.append({
                    "journey_model": item.get("journey_model"),
                    "journey_label": JOURNEY_LABELS.get(str(item.get("journey_model") or ""), str(item.get("journey_model") or "").replace("_", " ").title()),
                    "status": item.get("status"),
                    "path_completeness": item.get("completeness"),
                    "authority": item.get("authority"),
                })
            secondary_journeys = secondary_journeys[:3]
        else:
            # Business semantics are a search hint, not proof of a specialized journey.
            journey_model = "general"
            confidence = min(0.69, weighted_confidence)
            winning_signals = []
            secondary_journeys = []

    context_tags, context_reasons = infer_context_tags(data, journey_model, business_type)
    provisional = bool(journey_model == "general" or confidence < 0.72 or (not force_general_journey and int(marker_resolution.get("authority") or 0) < 4) or (business_type == "general" and float(business.get("confidence") or 0.0) < 0.60))
    secondary = JOURNEY_SECONDARY_CONVERSIONS.get(journey_model, JOURNEY_SECONDARY_CONVERSIONS["general"])
    return {
        "model_basis": "hierarchical_business_subtype_path_markers_v4",
        "business_type": business_type,
        "business_type_label": business.get("business_type_label") or BUSINESS_TYPE_LABELS.get(business_type, business_type.replace("_", " ").title()),
        "business_type_confidence": round(float(business.get("confidence") or 0.0), 2),
        "business_type_source": business.get("source") or "auto_inference",
        "business_type_signals": list(business.get("signals") or []),
        "business_type_candidates": business.get("score_candidates") or {},
        "business_subtype": subtype_profile.get("subtype"),
        "business_subtype_label": subtype_profile.get("subtype_label"),
        "business_subtype_confidence": subtype_profile.get("confidence"),
        "business_subtype_signals": subtype_profile.get("signals") or [],
        "differentiation_plan": differentiation_plan,
        "journey_marker_resolution": marker_resolution,
        "weighted_journey_candidate": weighted_journey_model,
        "weighted_journey_candidate_confidence": round(float(weighted_confidence), 2),
        "journey_model": journey_model,
        "journey_label": JOURNEY_LABELS.get(journey_model, JOURNEY_LABELS["general"]),
        "confidence": round(confidence, 2),
        "provisional": provisional,
        "journey_resolved": not provisional,
        "primary_conversion": JOURNEY_PRIMARY_CONVERSION.get(journey_model, JOURNEY_PRIMARY_CONVERSION["general"]),
        "secondary_conversions": list(secondary),
        "secondary_journeys": secondary_journeys,
        "context_tags": context_tags,
        "context_labels": [CONTEXT_LABELS[tag] for tag in context_tags],
        "journey_signals": winning_signals,
        "context_reasons": context_reasons,
        "requested_hint": hint,
        "requested_business_type": business_type if business.get("source") == "explicit_request" else "",
        "direct_journey_hint": direct_journey_hint,
        "score_candidates": {k: round(v, 2) for k, v in ranked},
        # Compatibility aliases. Unlike v7.2, vertical now describes the business type while
        # journey_model always describes the customer journey.
        "vertical": business_type,
        "legacy_business_type": business_type,
        "inferred_subtype": "",
        "signals": winning_signals,
    }


def expected_actions(journey_model: str) -> Set[str]:
    return set(JOURNEY_EXPECTED_ACTIONS.get(str(journey_model or "general"), JOURNEY_EXPECTED_ACTIONS["general"]))


def competitor_search_text(journey_model: str) -> str:
    return JOURNEY_COMPETITOR_SEARCH_TEXT.get(str(journey_model or "general"), "business")


def common_vs_architectural(checkpoint_id: int) -> str:
    return "common_foundation" if int(checkpoint_id) in COMMON_FOUNDATION_IDS else "adaptive_architecture"


def context_has(profile: Mapping[str, Any], tag: str) -> bool:
    return tag in set(str(x) for x in (profile.get("context_tags") or []) if x)


def journey_is(profile: Mapping[str, Any], *models: str) -> bool:
    return str(profile.get("journey_model") or "general") in set(models)


def business_is(profile: Mapping[str, Any], *business_types: str) -> bool:
    return str(profile.get("business_type") or profile.get("legacy_business_type") or profile.get("vertical") or "general") in set(business_types)
