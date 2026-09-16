"""Trilloka V7.4.1 research-grounded category/journey knowledge ledger.

Purpose
-------
This module does NOT create failures. It gives the existing V7.3.x scanner more
category- and journey-specific background knowledge for:
  * what evidence to look for after business type is resolved,
  * which pages are worth inspecting,
  * which observed facts are commercially decision-relevant,
  * how strongly an already-VERIFIED finding should be prioritized.

Core invariant is unchanged:
Business Type + Customer Journey + Context + VERIFIED site evidence -> applicability -> score.
Research is a prior / importance signal, never proof that a website has a problem.

Research classes
----------------
A: large empirical / quantitative + repeated usability or field dataset
B: established empirical usability / industry dataset
C: useful population-specific study / benchmark with explicit transfer limits
D: official technical guidance or expert synthesis; useful for observation/routing,
   but not a standalone commercial-outcome claim

The source metadata intentionally records population/scope limitations so that, for
example, Australian restaurant research is not treated as a universal conversion rate.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


RESEARCH_SOURCES: Dict[str, Dict[str, Any]] = {
    "baymard_checkout_2026": {
        "source": "Baymard Institute",
        "title": "Cart & Checkout Usability / Reasons for Cart Abandonment (2026 data)",
        "url": "https://baymard.com/research/checkout-usability",
        "class": "A",
        "evidence_type": "large-scale ecommerce usability testing + quantitative abandonment research",
        "population": "ecommerce shoppers / major ecommerce sites; primarily US/EU benchmark populations",
        "scope": "ecommerce cart, checkout, payment, delivery, returns and transaction friction",
        "limitations": "Applies to ecommerce/transactional purchase journeys; survey percentages are not copied directly into score deductions.",
    },
    "nng_b2b": {
        "source": "Nielsen Norman Group",
        "title": "B2B Usability",
        "url": "https://www.nngroup.com/articles/b2b-usability/",
        "class": "B",
        "evidence_type": "qualitative user research / task-success usability testing",
        "population": "B2B decision makers and business users",
        "scope": "B2B research, pricing expectations, product/service information and lead conversion",
        "limitations": "Older foundational research; used for durable information-needs patterns, not current market conversion rates.",
    },
    "nng_forms": {
        "source": "Nielsen Norman Group",
        "title": "Form and task usability research (scorer research family)",
        "url": "https://www.nngroup.com/topic/forms/",
        "class": "B",
        "evidence_type": "usability research / task completion",
        "population": "general web users across form/task contexts",
        "scope": "lead, application, booking and transaction form friction",
        "limitations": "General form principles require business/journey applicability and site-specific evidence.",
    },
    "google_cwv_2025": {
        "source": "Google web.dev / Chrome UX Report",
        "title": "Core Web Vitals thresholds and field-measurement methodology",
        "url": "https://web.dev/articles/defining-core-web-vitals-thresholds",
        "class": "A",
        "evidence_type": "field telemetry methodology + user-experience threshold research",
        "population": "real Chrome users where CrUX field data is eligible",
        "scope": "LCP, INP, CLS; 75th-percentile real-user experience",
        "limitations": "Performance telemetry indicates experience quality, not a direct dollar-loss percentage. Lab and field evidence remain distinct.",
    },
    "google_search_local": {
        "source": "Google Search Central",
        "title": "LocalBusiness structured data and business-detail guidance",
        "url": "https://developers.google.com/search/docs/appearance/structured-data/local-business",
        "class": "D",
        "evidence_type": "official technical/search guidance",
        "population": "local-business websites",
        "scope": "business identity, address, hours, telephone, restaurant/menu and local entity information",
        "limitations": "Technical/search guidance; it does not prove conversion impact by itself.",
    },
    "google_search_product": {
        "source": "Google Search Central",
        "title": "Product / Merchant listing structured data guidance",
        "url": "https://developers.google.com/search/docs/appearance/structured-data/merchant-listing",
        "class": "D",
        "evidence_type": "official technical/search guidance",
        "population": "product and ecommerce websites",
        "scope": "product identity, price, availability, shipping and returns information",
        "limitations": "Used to sharpen product-information observation/discovery, not as standalone evidence of revenue loss.",
    },
    "brightlocal_reviews_2025": {
        "source": "BrightLocal",
        "title": "Local Consumer Review Survey 2025",
        "url": "https://www.brightlocal.com/research/local-consumer-review-survey-2025/",
        "class": "B",
        "evidence_type": "consumer survey / local-business review behavior",
        "population": "consumers researching local businesses",
        "scope": "review detail, recency, trust and local-business evaluation",
        "limitations": "Local-business research; review expectations vary by category and should not force a review requirement where another proof format is appropriate.",
    },
    "clio_legal_2025": {
        "source": "Clio",
        "title": "2025 Legal Trends Report and client-intake research",
        "url": "https://www.clio.com/resources/legal-trends/read-online/",
        "class": "A",
        "evidence_type": "aggregated platform data + legal-consumer research",
        "population": "legal professionals and consumers seeking legal services, primarily North America",
        "scope": "lawyer discovery, firm websites, reviews, process clarity, client experience and pricing information",
        "limitations": "Legal-services specific; jurisdiction/practice-area differences remain important.",
    },
    "mr_benchmarks_2026": {
        "source": "M+R Benchmarks",
        "title": "M+R Benchmarks 2026 — Website Performance",
        "url": "https://mrbenchmarks.com/website-performance/",
        "class": "A",
        "evidence_type": "nonprofit digital-performance benchmark dataset",
        "population": "participating nonprofit organizations and their website/donation traffic",
        "scope": "donation-page completion, mobile/desktop giving, recurring giving and payment methods",
        "limitations": "Benchmark, not a universal target; sector, audience and organization size materially affect results.",
    },
    "zillow_housing_2025": {
        "source": "Zillow Research",
        "title": "Consumer Housing Trends Report 2025",
        "url": "https://www.zillow.com/research/buyers-housing-trends-report-2025/",
        "class": "A",
        "evidence_type": "consumer housing survey / behavioral journey research",
        "population": "US home buyers / prospective buyers",
        "scope": "agent contact, online property research, listing information, tours and communication",
        "limitations": "US housing population; use for journey importance and observable evidence, not as a universal conversion benchmark.",
    },
    "google_restaurant_mobile": {
        "source": "Google / Ipsos-style restaurant mobile research",
        "title": "How diners use mobile to find, choose and reach restaurants",
        "url": "https://www.thinkwithgoogle.com/_qs/documents/800/micro-moments-guide-how-australians-find-choose-restaurants.pdf",
        "class": "C",
        "evidence_type": "consumer mobile-journey research",
        "population": "Australian smartphone users / diners (historical study)",
        "scope": "menu/prices, reviews, restaurant choice, reservations, directions and mobile experience",
        "limitations": "Older Australian population; used directionally for evidence routing, never as a current universal conversion percentage.",
    },
    "google_finance_known_2021": {
        "source": "Google / Known",
        "title": "Financial consumer digital-experience research",
        "url": "https://www.thinkwithgoogle.com/_qs/documents/14276/Google_Finance_Infographic_Desktop_VD.pdf",
        "class": "C",
        "evidence_type": "consumer survey",
        "population": "US financial consumers (2021 study)",
        "scope": "trust, self-service, live assistance, ease and financial-product decision support",
        "limitations": "Population/time specific; used for customer-needs routing, not current conversion rates.",
    },
    "google_education_path": {
        "source": "Google / TNS",
        "title": "Higher Education Path to Enrollment research",
        "url": "https://www.thinkwithgoogle.com/_qs/documents/5773/TWG_AU_P2P_HigherEd_A_060118.pdf",
        "class": "C",
        "evidence_type": "quantitative + qualitative student journey research",
        "population": "Australian higher-education students (historical study)",
        "scope": "online research, program comparison and enrollment decision journey",
        "limitations": "Older Australian higher-education population; used directionally, not as a universal enrollment benchmark.",
    },
    "google_travel_booking": {
        "source": "Google / Phocuswright + Think with Google",
        "title": "Travel mobile shopping and booking research",
        "url": "https://www.thinkwithgoogle.com/_qs/documents/628/millennial-travelers-mobile-shopping-booking-behavior.pdf",
        "class": "C",
        "evidence_type": "traveler survey / booking-journey research",
        "population": "US leisure travelers; historical study",
        "scope": "hotel/flight research, mobile shopping and booking continuity",
        "limitations": "Older traveler population; use for journey/evidence routing rather than current rate assumptions.",
    },
    "google_auto_journey": {
        "source": "Google automotive journey research",
        "title": "Digital automotive purchase/dealer journey research",
        "url": "https://www.thinkwithgoogle.com/_qs/documents/7650/Year_in_Search__India_Insights_for_brands_jeEKocQ.pdf",
        "class": "C",
        "evidence_type": "search/journey research",
        "population": "Indian automotive buyers (historical study)",
        "scope": "dealer discovery, dealer websites, calls and digital lead generation",
        "limitations": "Regional/historical evidence; used only for directional journey importance, not universal buyer percentages.",
    },
}


# Rule-level source support keeps research attribution precise. A source is cited for a
# scoring emphasis only when its published scope actually supports that rule family.
# This prevents a category pack's unrelated source from being cited merely because
# both source and rule are active in the same business-type deep dive.
SOURCE_RULE_SUPPORT: Dict[str, Tuple[str, ...]] = {
    "baymard_checkout_2026": (
        "checkout_cost_transparency", "delivery_expectation_clarity", "shipping_info_discoverability",
        "guest_checkout_barrier", "checkout_complexity", "return_policy_discoverability",
        "conversion_path_error", "primary_conversion_path", "form_architecture",
    ),
    "nng_b2b": (
        "b2b_pricing_transparency", "case_studies_missing", "proof_placement_gap",
        "primary_conversion_path", "lead_form_friction", "form_architecture", "trust_credentials",
    ),
    "nng_forms": (
        "form_architecture", "lead_form_friction", "conversion_path_error", "primary_conversion_path",
    ),
    "google_cwv_2025": ("mobile_lab_performance",),
    "google_search_local": ("location_visibility", "phone_visibility"),
    "google_search_product": (
        "shipping_info_discoverability", "return_policy_discoverability", "delivery_expectation_clarity",
    ),
    "brightlocal_reviews_2025": ("reviews_social_proof", "proof_placement_gap"),
    "clio_legal_2025": (
        "trust_credentials", "about_team_signal", "b2b_pricing_transparency", "lead_form_friction",
        "form_architecture", "primary_conversion_path",
    ),
    "mr_benchmarks_2026": (
        "primary_conversion_path", "form_architecture", "conversion_path_error",
        "mobile_lab_performance", "proof_placement_gap",
    ),
    "zillow_housing_2025": (
        "primary_conversion_path", "phone_visibility", "click_to_call", "location_visibility",
    ),
    "google_restaurant_mobile": (
        "location_visibility", "phone_visibility", "reviews_social_proof", "primary_conversion_path",
        "conversion_path_error", "mobile_lab_performance",
    ),
    "google_finance_known_2021": (
        "trust_credentials", "primary_conversion_path", "conversion_path_error", "form_architecture",
    ),
    "google_education_path": (
        "primary_conversion_path", "form_architecture", "conversion_path_error", "content_hub_missing",
    ),
    "google_travel_booking": (
        "primary_conversion_path", "conversion_path_error", "checkout_cost_transparency", "mobile_lab_performance",
    ),
    "google_auto_journey": (
        "phone_visibility", "click_to_call", "location_visibility", "primary_conversion_path", "conversion_path_error",
    ),
}

# The strength/transferability of a source limits the extra research-specific scoring
# emphasis. Existing Trilloka business/journey/context scoring remains separate.
RESEARCH_CLASS_MAX_MULTIPLIER: Dict[str, float] = {
    "A": 1.12,
    "B": 1.09,
    "C": 1.06,
    "D": 1.04,
}

# Empty scope means broadly applicable. Non-empty scope prevents a study from
# leaking across industries just because a journey label happens to be similar.
SOURCE_BUSINESS_SCOPE: Dict[str, Tuple[str, ...]] = {
    "baymard_checkout_2026": ("ecommerce", "marketplace"),
    "nng_b2b": ("b2b", "saas", "agency", "professional_service", "marketplace"),
    "nng_forms": (),
    "google_cwv_2025": (),
    "google_search_local": ("local_service", "healthcare", "medspa", "legal", "financial_services", "real_estate", "restaurant", "hospitality_event", "automotive"),
    "google_search_product": ("ecommerce", "marketplace"),
    "brightlocal_reviews_2025": ("local_service", "healthcare", "medspa", "legal", "real_estate", "restaurant", "hospitality_event", "automotive"),
    "clio_legal_2025": ("legal",),
    "mr_benchmarks_2026": ("nonprofit",),
    "zillow_housing_2025": ("real_estate",),
    "google_restaurant_mobile": ("restaurant",),
    "google_finance_known_2021": ("financial_services",),
    "google_education_path": ("education",),
    "google_travel_booking": ("hospitality_event",),
    "google_auto_journey": ("automotive",),
}

SOURCE_JOURNEY_SCOPE: Dict[str, Tuple[str, ...]] = {
    "baymard_checkout_2026": ("direct_purchase",),
    "nng_b2b": ("lead_quote", "demo_sales", "general"),
    "nng_forms": (),
    "google_cwv_2025": (),
    "google_search_local": (),
    "google_search_product": ("direct_purchase", "general"),
    "brightlocal_reviews_2025": (),
    "clio_legal_2025": ("lead_quote", "appointment_consultation", "general"),
    "mr_benchmarks_2026": ("donation_support", "general"),
    "zillow_housing_2025": ("lead_quote", "appointment_consultation", "general"),
    "google_restaurant_mobile": ("reservation_event", "direct_purchase", "general"),
    "google_finance_known_2021": ("lead_quote", "appointment_consultation", "application_enrollment", "general"),
    "google_education_path": ("application_enrollment", "lead_quote", "general"),
    "google_travel_booking": ("reservation_event", "direct_purchase", "general"),
    "google_auto_journey": ("lead_quote", "appointment_consultation", "direct_purchase", "general"),
}


def _rule_source_records(rule_key: str, source_ids: Sequence[str], business_type: str = "general", journey_model: str = "general") -> List[Dict[str, Any]]:
    rule = str(rule_key or "").strip()
    business = str(business_type or "general").strip().lower()
    journey = str(journey_model or "general").strip().lower()
    records: List[Dict[str, Any]] = []
    for source_id in source_ids or []:
        source_id = str(source_id)
        if rule not in SOURCE_RULE_SUPPORT.get(source_id, ()):
            continue
        business_scope = SOURCE_BUSINESS_SCOPE.get(source_id, ())
        journey_scope = SOURCE_JOURNEY_SCOPE.get(source_id, ())
        if business_scope and business not in business_scope:
            continue
        if journey_scope and journey not in journey_scope:
            continue
        source = RESEARCH_SOURCES.get(source_id)
        if source:
            records.append(dict(source, id=source_id))
    return records


def _research_class_cap(source_records: Sequence[Mapping[str, Any]]) -> float:
    if not source_records:
        return 1.0
    caps = [RESEARCH_CLASS_MAX_MULTIPLIER.get(str(x.get("class") or "D"), 1.04) for x in source_records]
    return max(caps) if caps else 1.0


# Base category research packs. Each pack sharpens observation and post-verification priority.
# The terms are deliberately evidence concepts, not required features.
CATEGORY_RESEARCH_PACKS: Dict[str, Dict[str, Any]] = {
    "ecommerce": {
        "sources": ["baymard_checkout_2026", "google_search_product", "google_cwv_2025"],
        "customer_focus": [
            "complete and predictable total cost", "delivery speed and expectations", "payment confidence",
            "guest checkout availability/prominence", "checkout effort", "error recovery", "returns/refunds",
            "payment method availability", "product detail and fit", "stock/availability",
        ],
        "page_terms": ["product", "cart", "basket", "checkout", "shipping", "delivery", "returns", "payment", "order", "availability", "assessment", "quiz", "recommendation", "finder", "results"],
        "page_guesses": ["/products/", "/cart/", "/checkout/", "/shipping/", "/delivery/", "/returns/", "/payment/", "/assessment/", "/quiz/", "/recommendations/", "/results/"],
        "concepts": {
            "total_cost": ["subtotal", "shipping", "tax", "fee", "duties", "estimated total", "order total"],
            "delivery_speed": ["delivery date", "estimated arrival", "ships in", "business days", "working days", "dispatch"],
            "guest_checkout": ["guest checkout", "continue as guest", "checkout as guest", "create account"],
            "payment_confidence": ["secure checkout", "payment", "card", "paypal", "apple pay", "google pay", "shop pay"],
            "returns": ["returns", "refund", "exchange", "final sale", "return window"],
            "availability": ["in stock", "out of stock", "preorder", "backorder", "availability"],
            "guided_selection": ["assessment", "quiz", "find your", "personalized recommendation", "personalised recommendation", "recommended for you", "results"],
        },
        "rule_multipliers": {
            "checkout_cost_transparency": 1.12, "delivery_expectation_clarity": 1.10,
            "shipping_info_discoverability": 1.08, "guest_checkout_barrier": 1.09,
            "checkout_complexity": 1.09, "return_policy_discoverability": 1.07,
            "conversion_path_error": 1.08, "primary_conversion_path": 1.06,
        },
    },
    "marketplace": {
        "sources": ["baymard_checkout_2026", "nng_b2b", "google_cwv_2025"],
        "customer_focus": [
            "buyer/seller identity and reputation", "fees and total transaction cost", "matching/search quality",
            "payment confidence", "dispute/refund protection", "provider availability", "transaction completion",
        ],
        "page_terms": ["listings", "sellers", "providers", "fees", "trust", "safety", "protection", "payments", "dispute", "reviews"],
        "page_guesses": ["/listings/", "/sellers/", "/providers/", "/fees/", "/trust-safety/", "/payments/", "/reviews/"],
        "concepts": {
            "reputation": ["verified", "rating", "reviews", "completed", "seller", "provider profile"],
            "fee_transparency": ["service fee", "platform fee", "commission", "buyer fee", "seller fee", "total"],
            "protection": ["buyer protection", "seller protection", "dispute", "refund", "escrow", "guarantee"],
        },
        "rule_multipliers": {
            "checkout_cost_transparency": 1.08, "conversion_path_error": 1.08,
            "trust_credentials": 1.05, "proof_placement_gap": 1.05, "policy_content_consistency": 1.05,
            "primary_conversion_path": 1.06,
        },
    },
    "local_service": {
        "sources": ["brightlocal_reviews_2025", "google_search_local", "google_cwv_2025", "nng_forms"],
        "customer_focus": [
            "service fit", "service area/location", "availability and response expectations", "easy contact",
            "local reputation", "credentials where relevant", "price/estimate expectations", "warranty/guarantee",
        ],
        "page_terms": ["services", "service-area", "locations", "reviews", "quote", "estimate", "contact", "book", "warranty"],
        "page_guesses": ["/services/", "/service-areas/", "/locations/", "/reviews/", "/request-a-quote/", "/contact/", "/book/"],
        "concepts": {
            "local_identity": ["address", "service area", "areas we serve", "directions", "hours", "phone"],
            "reputation": ["reviews", "rating", "customer feedback", "testimonials", "verified"],
            "response": ["same day", "24/7", "emergency", "response time", "appointment"],
            "estimate": ["free estimate", "quote", "starting at", "pricing", "service call"],
        },
        "rule_multipliers": {
            "reviews_social_proof": 1.08, "phone_visibility": 1.08, "click_to_call": 1.08,
            "location_visibility": 1.08, "lead_form_friction": 1.05, "primary_conversion_path": 1.06,
        },
    },
    "professional_service": {
        "sources": ["nng_b2b", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "service/expertise fit", "who will do the work", "proof of capability", "pricing expectations",
            "process and deliverables", "contact/consultation effort", "response expectations",
        ],
        "page_terms": ["services", "expertise", "team", "case-studies", "clients", "process", "pricing", "consultation", "contact"],
        "page_guesses": ["/services/", "/expertise/", "/team/", "/case-studies/", "/process/", "/pricing/", "/consultation/", "/contact/"],
        "concepts": {
            "expertise": ["specialist", "expertise", "experience", "credentials", "certified"],
            "proof": ["case study", "client", "results", "portfolio", "testimonial"],
            "pricing": ["pricing", "fees", "retainer", "hourly", "fixed fee", "starting at", "estimate"],
            "process": ["process", "how we work", "engagement", "deliverables", "timeline"],
        },
        "rule_multipliers": {
            "b2b_pricing_transparency": 1.08, "case_studies_missing": 1.07, "proof_placement_gap": 1.07,
            "about_team_signal": 1.05, "lead_form_friction": 1.05, "primary_conversion_path": 1.05,
        },
    },
    "healthcare": {
        "sources": ["google_search_local", "brightlocal_reviews_2025", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "provider identity/qualifications", "treatment or service fit", "appointment path", "location/hours",
            "insurance/payment expectations", "privacy around sensitive information", "patient trust and proof",
        ],
        "page_terms": ["providers", "doctors", "services", "treatments", "appointments", "insurance", "patient", "locations", "privacy"],
        "page_guesses": ["/providers/", "/doctors/", "/services/", "/appointments/", "/insurance/", "/locations/", "/privacy/"],
        "concepts": {
            "provider_identity": ["doctor", "physician", "provider", "credentials", "licensed", "board certified"],
            "appointment": ["book appointment", "schedule", "new patient", "availability", "referral"],
            "payment": ["insurance", "coverage", "billing", "fees", "payment"],
            "sensitive_data": ["privacy", "patient information", "health information", "secure form"],
        },
        "rule_multipliers": {
            "trust_credentials": 1.09, "about_team_signal": 1.06, "privacy_terms_missing": 1.08,
            "form_architecture": 1.06, "primary_conversion_path": 1.06, "location_visibility": 1.05,
        },
    },
    "medspa": {
        "sources": ["brightlocal_reviews_2025", "google_search_local", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "practitioner credentials", "treatment fit", "before/after or review proof", "price/package expectations",
            "consultation/booking", "location", "safety/recovery expectations", "privacy",
        ],
        "page_terms": ["treatments", "services", "before-after", "reviews", "pricing", "packages", "consultation", "book", "team", "locations"],
        "page_guesses": ["/treatments/", "/before-after/", "/reviews/", "/pricing/", "/consultation/", "/book/", "/team/"],
        "concepts": {
            "proof": ["before and after", "before-after", "reviews", "rating", "results", "patient photos"],
            "credentials": ["licensed", "nurse", "doctor", "injector", "certified", "credentials"],
            "booking": ["consultation", "book", "appointment", "schedule", "availability"],
            "pricing": ["price", "pricing", "package", "per session", "financing"],
        },
        "rule_multipliers": {
            "trust_credentials": 1.08, "reviews_social_proof": 1.08, "proof_placement_gap": 1.07,
            "form_architecture": 1.05, "primary_conversion_path": 1.06, "privacy_terms_missing": 1.05,
        },
    },
    "legal": {
        "sources": ["clio_legal_2025", "nng_forms", "brightlocal_reviews_2025", "google_cwv_2025"],
        "customer_focus": [
            "practice-area fit", "lawyer identity and expertise", "how hiring/consultation works", "pricing/fee expectations",
            "responsiveness", "reviews/reputation", "confidentiality/trust", "clear next step",
        ],
        "page_terms": ["practice-areas", "lawyers", "attorneys", "team", "consultation", "fees", "pricing", "reviews", "contact", "process"],
        "page_guesses": ["/practice-areas/", "/lawyers/", "/attorneys/", "/consultation/", "/fees/", "/reviews/", "/contact/"],
        "concepts": {
            "practice_fit": ["practice area", "representation", "legal services", "case", "matter"],
            "lawyer_identity": ["lawyer", "attorney", "counsel", "bar", "experience", "bio"],
            "hiring_process": ["consultation", "what to expect", "how it works", "intake", "next step"],
            "fees": ["fees", "pricing", "hourly", "flat fee", "retainer", "contingency"],
        },
        "rule_multipliers": {
            "trust_credentials": 1.10, "about_team_signal": 1.07, "proof_placement_gap": 1.06,
            "lead_form_friction": 1.05, "form_architecture": 1.05, "primary_conversion_path": 1.07,
        },
    },
    "financial_services": {
        "sources": ["google_finance_known_2021", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "trust/security", "product/value clarity", "fees/rates where applicable", "human help availability",
            "self-service ease", "application/consultation path", "professional identity", "privacy",
        ],
        "page_terms": ["services", "accounts", "loans", "rates", "fees", "advisors", "security", "apply", "book", "contact", "privacy"],
        "page_guesses": ["/services/", "/rates/", "/fees/", "/advisors/", "/security/", "/apply/", "/contact/", "/privacy/"],
        "concepts": {
            "trust_security": ["security", "secure", "regulated", "licensed", "insured", "privacy", "protection"],
            "human_help": ["advisor", "speak to", "book a call", "appointment", "support", "contact"],
            "self_service": ["apply online", "calculator", "open account", "online application", "manage"],
            "value": ["rate", "interest", "fee", "pricing", "benefit", "reward", "minimum"],
        },
        "rule_multipliers": {
            "trust_credentials": 1.10, "privacy_terms_missing": 1.09, "policy_content_consistency": 1.06,
            "form_architecture": 1.06, "primary_conversion_path": 1.07, "conversion_path_error": 1.08,
        },
    },
    "real_estate": {
        "sources": ["zillow_housing_2025", "google_search_local", "google_cwv_2025"],
        "customer_focus": [
            "property/listing detail", "photos/floor plans/tours", "agent identity", "easy agent contact",
            "tour/open-house path", "location", "financing/pre-approval context", "mobile property research",
        ],
        "page_terms": ["listings", "properties", "homes", "floor-plan", "virtual-tour", "agents", "contact", "showing", "open-house", "mortgage"],
        "page_guesses": ["/listings/", "/properties/", "/homes/", "/agents/", "/book-a-showing/", "/open-houses/", "/contact/"],
        "concepts": {
            "listing_detail": ["bed", "bath", "sq ft", "price", "address", "floor plan", "photos", "virtual tour"],
            "agent_contact": ["agent", "realtor", "broker", "call", "text", "email", "schedule showing"],
            "tour": ["showing", "tour", "open house", "book", "schedule"],
            "finance": ["mortgage", "pre-approval", "financing", "calculator"],
        },
        "rule_multipliers": {
            "phone_visibility": 1.06, "click_to_call": 1.05, "primary_conversion_path": 1.08,
            "about_team_signal": 1.05, "proof_placement_gap": 1.05, "location_visibility": 1.04,
        },
    },
    "restaurant": {
        "sources": ["google_restaurant_mobile", "brightlocal_reviews_2025", "google_search_local", "google_cwv_2025"],
        "customer_focus": [
            "menu and prices", "food/venue imagery", "reviews", "hours", "location/directions",
            "reservation availability", "phone/contact", "mobile usability", "order/pickup/delivery path when offered",
        ],
        "page_terms": ["menu", "dine-in", "order", "reservation", "book", "hours", "location", "directions", "reviews", "gallery"],
        "page_guesses": ["/menu/", "/order/", "/reservations/", "/hours/", "/location/", "/reviews/", "/gallery/"],
        "concepts": {
            "menu": ["menu", "price", "appetizer", "entree", "dessert", "drinks"],
            "local": ["hours", "address", "directions", "map", "parking", "phone"],
            "reservation": ["reservation", "reserve", "book a table", "party size", "availability"],
            "reputation": ["reviews", "rating", "guest feedback", "customer reviews"],
        },
        "rule_multipliers": {
            "location_visibility": 1.10, "phone_visibility": 1.07, "reviews_social_proof": 1.08,
            "primary_conversion_path": 1.08, "conversion_path_error": 1.09, "mobile_lab_performance": 1.04,
        },
    },
    "hospitality_event": {
        "sources": ["google_travel_booking", "google_cwv_2025", "brightlocal_reviews_2025"],
        "customer_focus": [
            "availability/dates", "rates and total price", "amenities/experience", "photos", "reviews",
            "booking continuity", "payment trust", "cancellation expectations", "mobile booking",
        ],
        "page_terms": ["rooms", "availability", "rates", "book", "reservation", "amenities", "gallery", "reviews", "cancellation", "events"],
        "page_guesses": ["/rooms/", "/availability/", "/rates/", "/book/", "/amenities/", "/gallery/", "/reviews/", "/cancellation/"],
        "concepts": {
            "availability": ["check availability", "dates", "guests", "rooms", "sold out"],
            "rate": ["rate", "night", "total", "fees", "tax", "deposit"],
            "experience": ["amenities", "photos", "gallery", "location", "reviews"],
            "booking": ["book now", "reserve", "confirmation", "payment", "cancellation"],
        },
        "rule_multipliers": {
            "primary_conversion_path": 1.09, "conversion_path_error": 1.10, "checkout_cost_transparency": 1.05,
            "reviews_social_proof": 1.05, "mobile_lab_performance": 1.05, "policy_content_consistency": 1.04,
        },
    },
    "saas": {
        "sources": ["nng_b2b", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "product/use-case clarity", "pricing or buying model", "trial/demo path", "customer proof",
            "integrations", "security", "implementation/onboarding", "enterprise/contact path",
        ],
        "page_terms": ["product", "features", "solutions", "use-cases", "pricing", "demo", "trial", "customers", "case-studies", "integrations", "security", "docs"],
        "page_guesses": ["/product/", "/features/", "/solutions/", "/pricing/", "/demo/", "/trial/", "/customers/", "/integrations/", "/security/"],
        "concepts": {
            "product_fit": ["features", "use case", "workflow", "solution", "for teams", "for companies"],
            "pricing": ["pricing", "plan", "per user", "per month", "annual", "contact sales"],
            "proof": ["customers", "case study", "logos", "results", "testimonial"],
            "enterprise": ["security", "sso", "soc 2", "integrations", "api", "implementation", "support"],
        },
        "rule_multipliers": {
            "b2b_pricing_transparency": 1.09, "case_studies_missing": 1.07, "proof_placement_gap": 1.08,
            "primary_conversion_path": 1.07, "lead_form_friction": 1.05, "conversion_path_error": 1.07,
        },
    },
    "b2b": {
        "sources": ["nng_b2b", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "capabilities and specifications", "product/service availability or capacity", "pricing level",
            "industries/use cases", "proof/case studies", "certifications", "procurement/RFQ path", "contact response",
        ],
        "page_terms": ["products", "services", "capabilities", "industries", "specifications", "pricing", "case-studies", "certifications", "rfq", "quote", "contact"],
        "page_guesses": ["/products/", "/services/", "/capabilities/", "/industries/", "/pricing/", "/case-studies/", "/certifications/", "/rfq/", "/contact/"],
        "concepts": {
            "capability": ["capabilities", "specifications", "capacity", "lead time", "standards", "certified"],
            "pricing": ["pricing", "price", "quote", "budget", "starting at", "minimum order"],
            "proof": ["case study", "customers", "project", "results", "certifications"],
            "procurement": ["rfq", "request for quote", "procurement", "supplier", "technical data", "download"],
        },
        "rule_multipliers": {
            "b2b_pricing_transparency": 1.10, "case_studies_missing": 1.08, "proof_placement_gap": 1.08,
            "trust_credentials": 1.06, "primary_conversion_path": 1.07, "lead_form_friction": 1.05,
        },
    },
    "agency": {
        "sources": ["nng_b2b", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "specialization/service fit", "quality of work", "case-study results", "client proof", "team expertise",
            "engagement/process", "pricing/budget expectations", "contact/discovery path",
        ],
        "page_terms": ["services", "work", "portfolio", "case-studies", "clients", "team", "process", "pricing", "contact", "discovery"],
        "page_guesses": ["/services/", "/work/", "/portfolio/", "/case-studies/", "/clients/", "/team/", "/process/", "/contact/"],
        "concepts": {
            "work_proof": ["portfolio", "case study", "work", "results", "client", "campaign"],
            "specialization": ["services", "specialist", "industry", "strategy", "creative", "development"],
            "engagement": ["process", "discovery", "proposal", "timeline", "retainer", "project"],
            "pricing": ["pricing", "budget", "starting at", "retainer", "project fee"],
        },
        "rule_multipliers": {
            "case_studies_missing": 1.10, "proof_placement_gap": 1.09, "about_team_signal": 1.05,
            "b2b_pricing_transparency": 1.06, "lead_form_friction": 1.05, "primary_conversion_path": 1.06,
        },
    },
    "membership_creator": {
        "sources": ["nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "member value/benefits", "price and billing cadence", "trial/sample content", "renewal/cancellation expectations",
            "community/proof", "signup/payment effort", "account/member access",
        ],
        "page_terms": ["membership", "join", "subscribe", "pricing", "plans", "benefits", "community", "trial", "cancel", "billing", "login"],
        "page_guesses": ["/membership/", "/join/", "/subscribe/", "/pricing/", "/plans/", "/benefits/", "/community/", "/faq/"],
        "concepts": {
            "value": ["benefits", "included", "access", "community", "members", "exclusive"],
            "billing": ["monthly", "annual", "renew", "billing", "price", "trial"],
            "cancellation": ["cancel", "pause", "refund", "renewal", "terms"],
            "signup": ["join", "subscribe", "sign up", "create account", "payment"],
        },
        "rule_multipliers": {
            "form_architecture": 1.05, "primary_conversion_path": 1.08, "conversion_path_error": 1.08,
            "policy_content_consistency": 1.06, "checkout_complexity": 1.04, "proof_placement_gap": 1.04,
        },
    },
    "education": {
        "sources": ["google_education_path", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "program/course fit", "cost/fees", "entry requirements", "outcomes", "dates/deadlines",
            "online research information", "application/enrollment path", "contact/advisor help",
        ],
        "page_terms": ["programs", "courses", "tuition", "fees", "admissions", "requirements", "apply", "enroll", "deadlines", "outcomes", "career"],
        "page_guesses": ["/programs/", "/courses/", "/tuition/", "/admissions/", "/requirements/", "/apply/", "/enroll/", "/outcomes/"],
        "concepts": {
            "program_fit": ["program", "course", "curriculum", "duration", "format", "online", "campus"],
            "cost": ["tuition", "fees", "cost", "financial aid", "scholarship"],
            "requirements": ["requirements", "prerequisite", "admission", "eligibility", "deadline"],
            "outcomes": ["career", "employment", "graduate", "outcome", "credential", "certificate"],
        },
        "rule_multipliers": {
            "primary_conversion_path": 1.08, "form_architecture": 1.07, "lead_form_friction": 1.05,
            "conversion_path_error": 1.08, "content_hub_missing": 1.03, "mobile_lab_performance": 1.04,
        },
    },
    "nonprofit": {
        "sources": ["mr_benchmarks_2026", "nng_forms", "google_cwv_2025"],
        "customer_focus": [
            "mission/impact clarity", "donation path", "mobile donation usability", "recurring-gift option",
            "payment methods", "trust/transparency", "donation-page performance", "supporter choice",
        ],
        "page_terms": ["donate", "give", "monthly", "recurring", "impact", "mission", "financials", "annual-report", "payment", "support"],
        "page_guesses": ["/donate/", "/give/", "/monthly-giving/", "/impact/", "/mission/", "/financials/", "/annual-report/"],
        "concepts": {
            "donation": ["donate", "gift", "amount", "monthly", "one-time", "recurring"],
            "payments": ["paypal", "apple pay", "google pay", "venmo", "credit card"],
            "impact": ["impact", "mission", "where your money goes", "results", "annual report"],
            "trust": ["financials", "charity", "registration", "tax receipt", "privacy"],
        },
        "rule_multipliers": {
            "primary_conversion_path": 1.10, "form_architecture": 1.08, "conversion_path_error": 1.09,
            "mobile_lab_performance": 1.06, "trust_credentials": 1.05, "proof_placement_gap": 1.06,
        },
    },
    "automotive": {
        "sources": ["google_auto_journey", "google_search_local", "brightlocal_reviews_2025", "google_cwv_2025"],
        "customer_focus": [
            "inventory/service fit", "dealer/shop location", "phone/contact", "pricing/financing", "vehicle/service details",
            "test-drive or service booking", "reviews/reputation", "trade-in/estimate path",
        ],
        "page_terms": ["inventory", "vehicles", "service", "repair", "parts", "financing", "trade-in", "test-drive", "book-service", "reviews", "location"],
        "page_guesses": ["/inventory/", "/vehicles/", "/service/", "/repair/", "/financing/", "/trade-in/", "/test-drive/", "/book-service/", "/reviews/"],
        "concepts": {
            "inventory": ["inventory", "vehicle", "make", "model", "year", "mileage", "price"],
            "service": ["repair", "service", "maintenance", "parts", "book service", "appointment"],
            "dealer_contact": ["call", "directions", "hours", "location", "dealer", "sales"],
            "finance_trade": ["financing", "payment", "trade-in", "value your trade", "pre-qualify"],
        },
        "rule_multipliers": {
            "phone_visibility": 1.07, "click_to_call": 1.06, "location_visibility": 1.07,
            "reviews_social_proof": 1.06, "primary_conversion_path": 1.08, "conversion_path_error": 1.08,
        },
    },
}


JOURNEY_RESEARCH_PACKS: Dict[str, Dict[str, Any]] = {
    "lead_quote": {
        "sources": ["nng_b2b", "nng_forms"],
        "customer_focus": ["fit before contact", "price/estimate expectations", "proof before enquiry", "response expectation", "low-friction lead submission"],
        "page_terms": ["quote", "estimate", "contact", "services", "pricing", "case-studies", "reviews"],
        "concepts": {
            "lead_expectation": ["quote", "estimate", "response time", "what happens next", "consultation"],
            "lead_form": ["name", "email", "phone", "message", "required", "submit"],
        },
        "rule_multipliers": {"lead_form_friction": 1.06, "form_architecture": 1.05, "proof_placement_gap": 1.05, "primary_conversion_path": 1.06},
    },
    "appointment_consultation": {
        "sources": ["nng_forms", "google_search_local"],
        "customer_focus": ["provider/service fit", "availability", "location", "what to expect", "booking/contact effort"],
        "page_terms": ["book", "appointment", "consultation", "schedule", "availability", "locations", "providers"],
        "concepts": {
            "availability": ["available", "date", "time", "schedule", "calendar"],
            "expectation": ["consultation", "what to expect", "duration", "prepare", "new patient", "first visit"],
        },
        "rule_multipliers": {"primary_conversion_path": 1.07, "conversion_path_error": 1.08, "form_architecture": 1.05, "location_visibility": 1.04},
    },
    "reservation_event": {
        "sources": ["google_restaurant_mobile", "google_travel_booking", "google_search_local"],
        "customer_focus": ["availability", "date/time/party or guest requirements", "location", "price/rate expectations", "mobile reservation continuity"],
        "page_terms": ["reserve", "reservation", "book", "availability", "date", "time", "guests", "party", "location"],
        "concepts": {
            "reservation": ["reserve", "reservation", "book", "availability", "party size", "guests", "date", "time"],
        },
        "rule_multipliers": {"primary_conversion_path": 1.08, "conversion_path_error": 1.09, "mobile_lab_performance": 1.04, "location_visibility": 1.04},
    },
    "direct_purchase": {
        "sources": ["baymard_checkout_2026", "google_search_product"],
        "customer_focus": ["total cost", "delivery", "payment confidence", "guest checkout", "checkout effort", "returns", "payment choice"],
        "page_terms": ["product", "cart", "checkout", "shipping", "delivery", "returns", "payment"],
        "concepts": {
            "purchase_commitment": ["total", "shipping", "delivery", "guest", "payment", "returns", "place order"],
        },
        "rule_multipliers": {
            "checkout_cost_transparency": 1.12, "guest_checkout_barrier": 1.09, "checkout_complexity": 1.09,
            "delivery_expectation_clarity": 1.10, "return_policy_discoverability": 1.07, "conversion_path_error": 1.08,
        },
    },
    "demo_sales": {
        "sources": ["nng_b2b", "nng_forms"],
        "customer_focus": ["product/service fit", "pricing level", "proof", "implementation/security when relevant", "demo/contact effort"],
        "page_terms": ["demo", "pricing", "customers", "case-studies", "security", "integrations", "contact-sales"],
        "concepts": {"demo": ["request demo", "book demo", "contact sales", "talk to sales", "schedule"]},
        "rule_multipliers": {"b2b_pricing_transparency": 1.09, "proof_placement_gap": 1.07, "lead_form_friction": 1.05, "primary_conversion_path": 1.07},
    },
    "membership_subscription": {
        "sources": ["nng_forms", "google_cwv_2025"],
        "customer_focus": ["benefits/value", "billing cadence", "renewal/cancellation", "trial", "signup/payment effort"],
        "page_terms": ["membership", "subscribe", "join", "pricing", "billing", "cancel", "trial"],
        "concepts": {"subscription": ["monthly", "annual", "renew", "cancel", "trial", "billing", "subscribe"]},
        "rule_multipliers": {"primary_conversion_path": 1.07, "conversion_path_error": 1.08, "form_architecture": 1.05, "policy_content_consistency": 1.05},
    },
    "donation_support": {
        "sources": ["mr_benchmarks_2026", "nng_forms", "google_cwv_2025"],
        "customer_focus": ["impact/trust", "donation completion", "mobile donation", "recurring giving", "payment choice"],
        "page_terms": ["donate", "give", "monthly", "recurring", "impact", "payment"],
        "concepts": {"giving": ["donate", "gift", "monthly", "recurring", "paypal", "apple pay", "google pay"]},
        "rule_multipliers": {"primary_conversion_path": 1.10, "form_architecture": 1.08, "conversion_path_error": 1.09, "mobile_lab_performance": 1.05},
    },
    "application_enrollment": {
        "sources": ["google_education_path", "nng_forms"],
        "customer_focus": ["eligibility/requirements", "cost", "outcomes", "deadlines", "application completion", "advisor help"],
        "page_terms": ["apply", "application", "admissions", "requirements", "tuition", "deadline", "enroll"],
        "concepts": {"application": ["apply", "application", "requirements", "deadline", "documents", "submit", "enroll"]},
        "rule_multipliers": {"primary_conversion_path": 1.08, "form_architecture": 1.07, "conversion_path_error": 1.08, "lead_form_friction": 1.04},
    },
    "general": {
        "sources": ["google_cwv_2025"],
        "customer_focus": ["real-user performance and reliable interaction"],
        "page_terms": [],
        "concepts": {},
        "rule_multipliers": {},
    },
}


def _dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _merge_concepts(*maps: Mapping[str, Sequence[str]]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for mapping in maps:
        if not isinstance(mapping, Mapping):
            continue
        for key, values in mapping.items():
            result[str(key)] = _dedupe([*(result.get(str(key)) or []), *(values or [])])
    return result


def _combine_rule_multipliers(*maps: Mapping[str, float]) -> Dict[str, float]:
    """Combine category + journey research emphasis conservatively.

    Multiple studies do not stack multiplicatively without bound. We average the
    applicable factors and cap the final study-context factor to 0.94..1.12.
    """
    values_by_rule: Dict[str, List[float]] = {}
    for mapping in maps:
        if not isinstance(mapping, Mapping):
            continue
        for rule, value in mapping.items():
            try:
                values_by_rule.setdefault(str(rule), []).append(float(value))
            except Exception:
                continue
    output: Dict[str, float] = {}
    for rule, values in values_by_rule.items():
        if values:
            avg = sum(values) / len(values)
            output[rule] = round(max(0.94, min(1.12, avg)), 3)
    return output


def get_research_guidance(business_type: str, journey_model: str = "general", context_tags: Sequence[str] | None = None) -> Dict[str, Any]:
    business_type = str(business_type or "general").strip().lower()
    journey_model = str(journey_model or "general").strip().lower()
    category = CATEGORY_RESEARCH_PACKS.get(business_type) or {}
    journey = JOURNEY_RESEARCH_PACKS.get(journey_model) or JOURNEY_RESEARCH_PACKS["general"]
    source_ids = _dedupe([*(category.get("sources") or []), *(journey.get("sources") or [])])
    source_records = [dict(RESEARCH_SOURCES[sid], id=sid) for sid in source_ids if sid in RESEARCH_SOURCES]
    contexts = {str(x) for x in (context_tags or []) if x}

    # Context can sharpen observation without changing the scanner's context logic.
    extra_focus: List[str] = []
    extra_terms: List[str] = []
    if "local_location_dependent" in contexts:
        extra_focus += ["location accuracy", "hours/contact continuity"]
        extra_terms += ["location", "hours", "directions", "phone"]
    if "regulated_high_trust" in contexts:
        extra_focus += ["identity/credential confidence", "clear trust and policy information"]
        extra_terms += ["credentials", "team", "privacy", "security"]
    if "commerce_payment" in contexts:
        extra_focus += ["payment/transaction confidence", "cost and policy clarity near commitment"]
        extra_terms += ["payment", "checkout", "total", "refund", "returns"]
    if "enterprise_considered_purchase" in contexts:
        extra_focus += ["proof for shortlisting", "implementation/procurement information"]
        extra_terms += ["case-studies", "customers", "security", "procurement", "pricing"]
    if "recurring_commitment" in contexts:
        extra_focus += ["renewal/cancellation expectations", "recurring value clarity"]
        extra_terms += ["renewal", "cancel", "monthly", "annual", "billing"]

    return {
        "business_type": business_type,
        "journey_model": journey_model,
        "context_tags": sorted(contexts),
        "source_ids": source_ids,
        "sources": source_records,
        "customer_focus": _dedupe([*(category.get("customer_focus") or []), *(journey.get("customer_focus") or []), *extra_focus]),
        "page_terms": _dedupe([*(category.get("page_terms") or []), *(journey.get("page_terms") or []), *extra_terms]),
        "page_guesses": _dedupe([*(category.get("page_guesses") or [])]),
        "concepts": _merge_concepts(category.get("concepts") or {}, journey.get("concepts") or {}),
        "rule_multipliers": _combine_rule_multipliers(category.get("rule_multipliers") or {}, journey.get("rule_multipliers") or {}),
        "guardrail": "Research guides what to inspect and how to prioritize an already-verified site-specific condition. It never creates FAIL evidence by itself.",
    }


def research_rule_multiplier(rule_key: str, business_type: str, journey_model: str = "general", context_tags: Sequence[str] | None = None) -> float:
    guidance = get_research_guidance(business_type, journey_model, context_tags)
    try:
        proposed = float((guidance.get("rule_multipliers") or {}).get(str(rule_key), 1.0))
    except Exception:
        return 1.0
    if abs(proposed - 1.0) <= 1e-9:
        return 1.0
    supporting = _rule_source_records(str(rule_key), guidance.get("source_ids") or [], business_type, journey_model)
    if not supporting:
        # The base scorer may still have a business heuristic for this rule. The
        # research layer itself cannot amplify it without rule-specific source support.
        return 1.0
    cap = _research_class_cap(supporting)
    return round(max(0.94, min(float(proposed), float(cap), 1.12)), 3)


def research_basis_for_rule(rule_key: str, business_type: str, journey_model: str = "general", context_tags: Sequence[str] | None = None) -> Dict[str, Any]:
    guidance = get_research_guidance(business_type, journey_model, context_tags)
    multiplier = research_rule_multiplier(rule_key, business_type, journey_model, context_tags)
    source_records = _rule_source_records(str(rule_key), guidance.get("source_ids") or [], business_type, journey_model) if abs(multiplier - 1.0) > 1e-9 else []
    class_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    strongest_class = min((str(x.get("class") or "D") for x in source_records), key=lambda c: class_order.get(c, 9), default=None)
    return {
        "study_context_multiplier": round(multiplier, 3),
        "strongest_research_class": strongest_class,
        "source_ids": [str(x.get("id")) for x in source_records if x.get("id")],
        "sources": [
            {
                "source": x.get("source"), "title": x.get("title"), "class": x.get("class"),
                "scope": x.get("scope"), "population": x.get("population"), "limitations": x.get("limitations"),
                "url": x.get("url"),
            }
            for x in source_records
        ],
        "policy": guidance.get("guardrail"),
    }


def research_stats() -> Dict[str, int]:
    category_packs = list(CATEGORY_RESEARCH_PACKS.values())
    journey_packs = list(JOURNEY_RESEARCH_PACKS.values())
    return {
        "research_sources": len(RESEARCH_SOURCES),
        "business_categories": len(CATEGORY_RESEARCH_PACKS),
        "journey_families": len(JOURNEY_RESEARCH_PACKS),
        "category_customer_focus_items": sum(len(x.get("customer_focus") or []) for x in category_packs),
        "category_observable_terms": sum(sum(len(v or []) for v in (x.get("concepts") or {}).values()) for x in category_packs),
        "category_page_terms": sum(len(x.get("page_terms") or []) for x in category_packs),
        "category_rule_emphases": sum(len(x.get("rule_multipliers") or {}) for x in category_packs),
        "journey_customer_focus_items": sum(len(x.get("customer_focus") or []) for x in journey_packs),
        "journey_observable_terms": sum(sum(len(v or []) for v in (x.get("concepts") or {}).values()) for x in journey_packs),
        "journey_rule_emphases": sum(len(x.get("rule_multipliers") or {}) for x in journey_packs),
        "rule_source_links": sum(len(v) for v in SOURCE_RULE_SUPPORT.values()),
        "research_classes": len(RESEARCH_CLASS_MAX_MULTIPLIER),
    }
