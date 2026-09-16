"""Trilloka V7.4.1 category-specific commercial knowledge packs + research enrichment.

The packs increase what the existing scanner knows about each supported business family.
They do NOT create findings by themselves. They guide evidence collection, page selection,
and bounded business-type importance weighting after a failure has already been verified.

Core invariant remains:
Business Type + Customer Journey + Context + Verified Evidence -> Applicability -> Priority.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Tuple

from research_knowledge import get_research_guidance, research_stats as research_knowledge_stats


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

# These are evidence-routing packs, not mandatory checklists. A concept that is not observed
# remains absent/unknown unless an existing verified rule establishes applicability and failure.
BUSINESS_DEEP_DIVE_PACKS: Dict[str, Dict[str, Any]] = {
    "ecommerce": {
        "customer_focus": [
            "product fit and clarity", "price and total cost", "availability", "delivery timing",
            "shipping cost", "returns/refunds", "reviews and proof", "payment trust", "checkout effort",
            "mobile purchase continuity", "discount clarity", "post-purchase expectations",
        ],
        "page_terms": [
            "shop", "product", "products", "collections", "category", "catalog", "cart", "basket", "bag",
            "checkout", "shipping", "delivery", "returns", "refund", "faq", "reviews", "size-guide", "wishlist",
            "gift-card", "order-tracking", "payment", "sale", "offers",
        ],
        "page_guesses": [
            "/shop/", "/products/", "/collections/", "/cart/", "/checkout/", "/shipping/", "/delivery/",
            "/returns/", "/refund-policy/", "/faq/", "/reviews/", "/size-guide/", "/track-order/",
        ],
        "concepts": {
            "offer_clarity": ["product details", "specifications", "features", "what's included", "size", "dimensions", "materials"],
            "price_total_cost": ["price", "subtotal", "tax", "shipping", "delivery fee", "duties", "total"],
            "availability": ["in stock", "out of stock", "backorder", "preorder", "availability", "ships in"],
            "delivery_expectation": ["delivery", "shipping time", "dispatch", "working days", "business days", "estimated arrival"],
            "return_reassurance": ["return", "refund", "exchange", "money back", "final sale"],
            "proof": ["reviews", "ratings", "verified buyer", "customer photos", "testimonials"],
            "checkout_trust": ["secure checkout", "payment methods", "visa", "mastercard", "paypal", "shop pay", "apple pay"],
            "purchase_friction": ["create account", "required account", "coupon", "promo code", "minimum order", "required fields"],
        },
        "priority_rules": {
            "checkout_cost_transparency": 1.30, "guest_checkout_barrier": 1.25, "checkout_complexity": 1.24,
            "delivery_expectation_clarity": 1.25, "shipping_info_discoverability": 1.22,
            "return_policy_discoverability": 1.22, "proof_placement_gap": 1.14,
            "conversion_path_error": 1.18, "primary_conversion_path": 1.18, "measurement_telemetry": 1.10,
        },
    },
    "marketplace": {
        "customer_focus": [
            "quality of sellers/providers", "trust between both sides", "fees", "selection/liquidity", "search and matching",
            "buyer protection", "seller onboarding", "payment handling", "disputes/refunds", "identity/reputation",
            "transaction completion", "platform safety",
        ],
        "page_terms": [
            "marketplace", "browse", "listings", "sellers", "vendors", "providers", "buyers", "become-a-seller",
            "sell", "fees", "pricing", "trust", "safety", "buyer-protection", "seller-protection", "disputes",
            "reviews", "profiles", "verification", "how-it-works", "checkout", "payments",
        ],
        "page_guesses": [
            "/marketplace/", "/browse/", "/listings/", "/sellers/", "/providers/", "/become-a-seller/",
            "/sell/", "/fees/", "/how-it-works/", "/trust-safety/", "/buyer-protection/", "/reviews/",
        ],
        "concepts": {
            "two_sided_value": ["buyers", "sellers", "providers", "customers", "list your", "find a"],
            "reputation": ["rating", "review", "verified", "completed jobs", "seller level", "provider profile"],
            "fees": ["commission", "service fee", "seller fee", "buyer fee", "platform fee"],
            "protection": ["buyer protection", "seller protection", "refund", "dispute", "guarantee", "escrow"],
            "matching": ["search", "filters", "availability", "compare", "match", "request"],
            "onboarding": ["become a seller", "join as provider", "list an item", "create profile", "verification"],
        },
        "priority_rules": {
            "primary_conversion_path": 1.20, "conversion_path_error": 1.20, "trust_credentials": 1.18,
            "proof_placement_gap": 1.16, "privacy_terms_missing": 1.18, "policy_content_consistency": 1.18,
            "measurement_telemetry": 1.12, "form_architecture": 1.12,
        },
    },
    "local_service": {
        "customer_focus": [
            "can they solve my exact problem", "service area", "availability/response time", "price or estimate expectations",
            "trust/reviews", "licensing/insurance when relevant", "easy phone/contact", "before/after proof",
            "warranty/guarantee", "emergency or same-day availability", "booking effort", "local legitimacy",
        ],
        "page_terms": [
            "services", "service-areas", "areas-we-serve", "locations", "quote", "estimate", "book", "schedule",
            "contact", "reviews", "testimonials", "projects", "gallery", "before-after", "warranty", "guarantee",
            "emergency", "pricing", "faq", "about", "licensed", "insured",
        ],
        "page_guesses": [
            "/services/", "/service-areas/", "/areas-we-serve/", "/request-a-quote/", "/estimate/", "/book/",
            "/contact/", "/reviews/", "/projects/", "/gallery/", "/warranty/", "/faq/",
        ],
        "concepts": {
            "service_fit": ["services", "repair", "installation", "maintenance", "residential", "commercial"],
            "local_coverage": ["service area", "areas we serve", "city", "neighbourhood", "near you"],
            "response_expectation": ["same day", "24/7", "emergency", "response time", "appointments available"],
            "estimate_clarity": ["free estimate", "quote", "pricing", "starting at", "service call"],
            "trust": ["licensed", "insured", "bonded", "reviews", "years experience", "warranty", "guarantee"],
            "contact_continuity": ["call now", "request service", "book service", "text us", "get quote"],
        },
        "priority_rules": {
            "click_to_call": 1.30, "phone_visibility": 1.26, "location_visibility": 1.24,
            "form_architecture": 1.18, "lead_form_friction": 1.18, "reviews_social_proof": 1.18,
            "proof_placement_gap": 1.16, "primary_conversion_path": 1.18, "conversion_path_error": 1.20,
        },
    },
    "professional_service": {
        "customer_focus": [
            "expertise", "fit for my problem", "credibility", "who will do the work", "process", "case evidence",
            "consultation/contact effort", "pricing expectations", "confidentiality", "response expectations",
            "specialization", "professional legitimacy",
        ],
        "page_terms": [
            "services", "expertise", "industries", "team", "professionals", "about", "case-studies", "clients",
            "testimonials", "consultation", "contact", "pricing", "process", "approach", "credentials", "faq",
        ],
        "page_guesses": [
            "/services/", "/expertise/", "/team/", "/about/", "/case-studies/", "/clients/", "/consultation/",
            "/contact/", "/pricing/", "/process/", "/approach/", "/faq/",
        ],
        "concepts": {
            "expertise": ["expertise", "specialist", "experience", "certified", "qualified", "credentials"],
            "proof": ["case study", "client story", "testimonial", "results", "clients", "portfolio"],
            "process": ["our process", "how we work", "engagement", "discovery", "assessment", "deliverables"],
            "people": ["team", "partner", "consultant", "advisor", "professional", "principal"],
            "contact_expectation": ["consultation", "book a call", "contact", "response", "next step"],
            "pricing_expectation": ["fees", "pricing", "retainer", "fixed fee", "hourly", "starting at", "quote"],
        },
        "priority_rules": {
            "form_architecture": 1.18, "lead_form_friction": 1.16, "trust_credentials": 1.20,
            "about_team_signal": 1.15, "case_studies_missing": 1.18, "proof_placement_gap": 1.20,
            "primary_conversion_path": 1.16, "conversion_path_error": 1.18,
        },
    },
    "healthcare": {
        "customer_focus": [
            "provider qualifications", "treatment/service fit", "safety and trust", "appointment availability",
            "insurance/payment expectations", "location/accessibility", "privacy", "what to expect",
            "new-patient information", "reviews/proof when appropriate", "urgent vs routine access", "contact ease",
        ],
        "page_terms": [
            "services", "treatments", "conditions", "providers", "doctors", "team", "credentials", "book", "appointment",
            "new-patients", "insurance", "fees", "location", "contact", "privacy", "reviews", "faq", "what-to-expect",
        ],
        "page_guesses": [
            "/services/", "/treatments/", "/providers/", "/team/", "/book/", "/appointments/", "/new-patients/",
            "/insurance/", "/fees/", "/locations/", "/privacy/", "/faq/",
        ],
        "concepts": {
            "clinical_fit": ["treatment", "condition", "symptoms", "services", "assessment", "care"],
            "credentials": ["doctor", "registered", "licensed", "board certified", "credentials", "designation"],
            "appointment": ["book appointment", "schedule", "new patient", "availability", "referral"],
            "privacy": ["privacy", "health information", "patient information", "consent", "confidential"],
            "payment": ["insurance", "direct billing", "fees", "coverage", "payment", "benefits"],
            "expectations": ["what to expect", "first visit", "preparation", "aftercare", "follow-up"],
        },
        "priority_rules": {
            "trust_credentials": 1.35, "privacy_terms_missing": 1.30, "policy_content_consistency": 1.25,
            "proof_placement_gap": 1.20, "form_architecture": 1.18, "lead_form_friction": 1.12,
            "primary_conversion_path": 1.18, "conversion_path_error": 1.25,
        },
    },
    "medspa": {
        "customer_focus": [
            "practitioner qualifications", "treatment suitability", "safety", "before/after proof", "reviews",
            "pricing/packages", "consultation booking", "downtime/aftercare", "expected results", "contraindications",
            "location", "financing/payment options",
        ],
        "page_terms": [
            "treatments", "services", "injectables", "laser", "skin", "before-after", "gallery", "reviews", "team",
            "providers", "credentials", "consultation", "book", "pricing", "packages", "financing", "aftercare", "faq",
        ],
        "page_guesses": [
            "/treatments/", "/services/", "/before-after/", "/gallery/", "/reviews/", "/team/", "/consultation/",
            "/book/", "/pricing/", "/packages/", "/financing/", "/faq/",
        ],
        "concepts": {
            "treatment_fit": ["treatment", "candidate", "suitable", "consultation", "concerns", "goals"],
            "credentials": ["medical director", "nurse", "physician", "licensed", "certified", "injector"],
            "visual_proof": ["before and after", "gallery", "results", "photos", "reviews"],
            "expectations": ["results", "downtime", "aftercare", "sessions", "recovery", "side effects"],
            "price": ["pricing", "package", "per session", "financing", "membership", "starting at"],
        },
        "priority_rules": {
            "trust_credentials": 1.32, "reviews_social_proof": 1.24, "proof_placement_gap": 1.28,
            "privacy_terms_missing": 1.22, "policy_content_consistency": 1.18, "form_architecture": 1.16,
            "primary_conversion_path": 1.18, "conversion_path_error": 1.24,
        },
    },
    "legal": {
        "customer_focus": [
            "practice-area fit", "lawyer credentials", "relevant experience", "consultation access", "confidentiality",
            "fee expectations", "case/process clarity", "location/jurisdiction", "proof/outcomes stated carefully",
            "who handles the matter", "urgency", "contact confidence",
        ],
        "page_terms": [
            "practice-areas", "services", "lawyers", "attorneys", "team", "about", "experience", "cases", "results",
            "consultation", "contact", "fees", "privacy", "locations", "faq", "resources",
        ],
        "page_guesses": [
            "/practice-areas/", "/services/", "/lawyers/", "/team/", "/about/", "/results/", "/consultation/",
            "/contact/", "/fees/", "/privacy/", "/locations/", "/faq/",
        ],
        "concepts": {
            "matter_fit": ["practice area", "legal services", "representation", "case", "matter", "claim"],
            "credentials": ["lawyer", "attorney", "barrister", "solicitor", "bar", "years of experience"],
            "consultation": ["consultation", "case evaluation", "speak with", "contact lawyer", "book"],
            "fees": ["fees", "contingency", "retainer", "hourly", "fixed fee", "no win no fee"],
            "confidentiality": ["confidential", "privacy", "attorney-client", "legal advice disclaimer"],
        },
        "priority_rules": {
            "trust_credentials": 1.35, "privacy_terms_missing": 1.28, "about_team_signal": 1.20,
            "proof_placement_gap": 1.20, "form_architecture": 1.18, "lead_form_friction": 1.14,
            "primary_conversion_path": 1.18, "policy_content_consistency": 1.20,
        },
    },
    "financial_services": {
        "customer_focus": [
            "credentials/regulatory trust", "service fit", "fees", "risk clarity", "privacy/security", "advisor identity",
            "process", "minimums/eligibility", "performance claims context", "consultation access", "products/services",
            "ongoing relationship expectations",
        ],
        "page_terms": [
            "services", "wealth", "investments", "planning", "insurance", "mortgage", "advisors", "team", "credentials",
            "fees", "pricing", "disclosures", "privacy", "security", "consultation", "contact", "process", "faq",
        ],
        "page_guesses": [
            "/services/", "/wealth-management/", "/financial-planning/", "/advisors/", "/team/", "/fees/",
            "/disclosures/", "/privacy/", "/security/", "/consultation/", "/contact/", "/faq/",
        ],
        "concepts": {
            "credentials": ["licensed", "registered", "advisor", "planner", "designation", "fiduciary"],
            "fees": ["fees", "commission", "management fee", "advisory fee", "minimum", "pricing"],
            "risk": ["risk", "not guaranteed", "investment risk", "returns", "performance", "past performance"],
            "privacy_security": ["privacy", "security", "personal information", "financial information", "encryption"],
            "process": ["discovery", "plan", "review", "ongoing", "portfolio", "assessment"],
        },
        "priority_rules": {
            "trust_credentials": 1.35, "privacy_terms_missing": 1.35, "policy_content_consistency": 1.30,
            "proof_placement_gap": 1.18, "form_architecture": 1.18, "primary_conversion_path": 1.16,
            "measurement_telemetry": 1.08,
        },
    },
    "real_estate": {
        "customer_focus": [
            "property inventory/fit", "local expertise", "agent credibility", "pricing/valuation", "easy inquiry",
            "showing availability", "photos/details", "neighbourhood information", "seller/buyer process",
            "reviews", "contact speed", "mortgage/financing context when relevant",
        ],
        "page_terms": [
            "listings", "properties", "homes", "search", "buy", "sell", "valuation", "home-value", "agents", "team",
            "neighbourhoods", "communities", "open-house", "showing", "contact", "reviews", "market-report",
        ],
        "page_guesses": [
            "/listings/", "/properties/", "/homes/", "/buy/", "/sell/", "/home-valuation/", "/agents/", "/team/",
            "/neighbourhoods/", "/open-houses/", "/contact/", "/reviews/",
        ],
        "concepts": {
            "inventory": ["listing", "property", "bedrooms", "bathrooms", "price", "sq ft", "photos"],
            "local_expertise": ["neighbourhood", "community", "market", "local", "area"],
            "agent_trust": ["realtor", "agent", "broker", "reviews", "years", "sales"],
            "inquiry": ["schedule showing", "book viewing", "contact agent", "request information", "valuation"],
            "seller_path": ["sell your home", "home value", "listing consultation", "market analysis"],
        },
        "priority_rules": {
            "click_to_call": 1.20, "phone_visibility": 1.18, "location_visibility": 1.18,
            "reviews_social_proof": 1.18, "proof_placement_gap": 1.16, "form_architecture": 1.18,
            "primary_conversion_path": 1.20, "conversion_path_error": 1.20,
        },
    },
    "restaurant": {
        "customer_focus": [
            "menu", "prices", "location", "opening hours", "reservation availability", "order/pickup/delivery",
            "dietary options", "photos", "reviews", "contact/directions", "parking/access", "special events",
        ],
        "page_terms": [
            "menu", "food", "drink", "dine-in", "takeout", "delivery", "order", "reserve", "reservation", "book",
            "location", "hours", "directions", "contact", "reviews", "gallery", "catering", "events", "dietary",
        ],
        "page_guesses": [
            "/menu/", "/dine-in-menu/", "/order/", "/order-online/", "/reservations/", "/book/", "/location/",
            "/hours/", "/contact/", "/reviews/", "/gallery/", "/catering/", "/events/",
        ],
        "concepts": {
            "menu_price": ["menu", "$", "price", "appetizer", "entree", "drinks", "dessert"],
            "hours_location": ["hours", "open", "address", "directions", "parking", "location"],
            "reservation": ["reserve", "reservation", "book a table", "party size", "availability"],
            "ordering": ["order online", "pickup", "takeout", "delivery", "cart"],
            "dietary": ["vegetarian", "vegan", "gluten", "allergy", "halal", "dietary"],
            "proof": ["reviews", "rating", "awards", "gallery", "customer"],
        },
        "priority_rules": {
            "click_to_call": 1.24, "phone_visibility": 1.20, "location_visibility": 1.28,
            "reviews_social_proof": 1.22, "proof_placement_gap": 1.16, "primary_conversion_path": 1.24,
            "conversion_path_error": 1.25, "mobile_sticky_cta": 1.10,
        },
    },
    "hospitality_event": {
        "customer_focus": [
            "availability", "price/package clarity", "location", "photos", "reviews", "booking/reservation",
            "capacity/amenities", "cancellation terms", "dates", "what is included", "contact/event inquiry",
            "travel/access information", "trust",
        ],
        "page_terms": [
            "rooms", "suites", "stay", "availability", "book", "booking", "events", "weddings", "venue", "packages",
            "rates", "amenities", "gallery", "reviews", "location", "directions", "cancellation", "faq", "contact",
        ],
        "page_guesses": [
            "/rooms/", "/suites/", "/availability/", "/book/", "/booking/", "/events/", "/weddings/", "/venue/",
            "/packages/", "/rates/", "/amenities/", "/gallery/", "/location/", "/cancellation-policy/",
        ],
        "concepts": {
            "availability": ["availability", "dates", "check in", "check out", "book now", "reserve"],
            "price_package": ["rate", "price", "package", "per night", "deposit", "minimum stay"],
            "experience": ["amenities", "included", "capacity", "room", "venue", "tour"],
            "proof": ["reviews", "gallery", "photos", "awards", "testimonials"],
            "terms": ["cancellation", "deposit", "refund", "reschedule", "terms"],
        },
        "priority_rules": {
            "location_visibility": 1.22, "reviews_social_proof": 1.20, "proof_placement_gap": 1.18,
            "primary_conversion_path": 1.25, "conversion_path_error": 1.28, "form_architecture": 1.16,
            "policy_content_consistency": 1.15,
        },
    },
    "saas": {
        "customer_focus": [
            "what the product does", "who it is for", "use cases", "pricing", "proof/results", "integrations",
            "security", "implementation effort", "trial/demo", "support", "feature fit", "contract/commitment",
            "time to value", "comparison/alternatives",
        ],
        "page_terms": [
            "product", "platform", "features", "solutions", "use-cases", "industries", "pricing", "demo", "trial",
            "signup", "customers", "case-studies", "integrations", "security", "docs", "api", "support", "compare",
        ],
        "page_guesses": [
            "/product/", "/features/", "/solutions/", "/use-cases/", "/pricing/", "/demo/", "/trial/",
            "/customers/", "/case-studies/", "/integrations/", "/security/", "/docs/", "/api/",
        ],
        "concepts": {
            "value_clarity": ["platform", "software", "helps", "automate", "save", "increase", "reduce"],
            "pricing": ["pricing", "per user", "per month", "annual", "enterprise", "free trial"],
            "proof": ["case study", "customers", "logos", "results", "testimonial", "roi"],
            "integration": ["integrations", "api", "connect", "works with", "sync"],
            "security": ["security", "soc 2", "sso", "gdpr", "encryption", "compliance"],
            "activation": ["start trial", "get started", "book demo", "request demo", "signup"],
        },
        "priority_rules": {
            "primary_conversion_path": 1.22, "conversion_path_error": 1.22, "b2b_pricing_transparency": 1.24,
            "measurement_telemetry": 1.22, "case_studies_missing": 1.20, "proof_placement_gap": 1.20,
            "cta_competition": 1.10, "form_architecture": 1.14,
        },
    },
    "b2b": {
        "customer_focus": [
            "capability fit", "technical specifications", "industry experience", "proof/case studies", "reliability",
            "lead times", "capacity", "certifications", "procurement/contact", "pricing/RFQ", "implementation",
            "support", "geographic/service coverage", "risk reduction",
        ],
        "page_terms": [
            "solutions", "services", "products", "capabilities", "industries", "specifications", "technical", "case-studies",
            "projects", "customers", "certifications", "quality", "rfq", "quote", "contact", "locations", "support",
        ],
        "page_guesses": [
            "/solutions/", "/services/", "/products/", "/capabilities/", "/industries/", "/technical/", "/case-studies/",
            "/projects/", "/certifications/", "/quality/", "/rfq/", "/request-a-quote/", "/contact/",
        ],
        "concepts": {
            "capability": ["capabilities", "capacity", "equipment", "technology", "specifications", "custom"],
            "industry_fit": ["industries", "applications", "sectors", "use cases"],
            "proof": ["case study", "project", "customers", "results", "certifications", "quality"],
            "procurement": ["rfq", "request quote", "lead time", "minimum order", "specification", "procurement"],
            "risk": ["warranty", "quality", "certified", "compliance", "support", "service level"],
        },
        "priority_rules": {
            "primary_conversion_path": 1.20, "conversion_path_error": 1.20, "b2b_pricing_transparency": 1.22,
            "case_studies_missing": 1.25, "trust_credentials": 1.18, "proof_placement_gap": 1.22,
            "form_architecture": 1.16, "measurement_telemetry": 1.12,
        },
    },
    "agency": {
        "customer_focus": [
            "quality of work", "relevant case studies", "specialization", "results", "process", "team",
            "pricing/budget fit", "communication", "timeline", "service scope", "contact/proposal path",
            "credibility and differentiation",
        ],
        "page_terms": [
            "services", "work", "portfolio", "case-studies", "clients", "results", "industries", "process", "approach",
            "team", "about", "pricing", "packages", "proposal", "contact", "consultation", "reviews",
        ],
        "page_guesses": [
            "/services/", "/work/", "/portfolio/", "/case-studies/", "/clients/", "/results/", "/process/",
            "/team/", "/about/", "/pricing/", "/contact/", "/consultation/",
        ],
        "concepts": {
            "portfolio": ["portfolio", "our work", "case study", "projects", "clients"],
            "outcomes": ["results", "growth", "conversion", "revenue", "leads", "roi"],
            "process": ["process", "approach", "strategy", "discovery", "timeline", "deliverables"],
            "team": ["team", "founder", "strategist", "designer", "developer", "specialist"],
            "engagement": ["proposal", "consultation", "project", "budget", "starting at", "retainer"],
        },
        "priority_rules": {
            "form_architecture": 1.20, "lead_form_friction": 1.16, "case_studies_missing": 1.28,
            "proof_placement_gap": 1.25, "about_team_signal": 1.16, "primary_conversion_path": 1.18,
            "cta_competition": 1.12,
        },
    },
    "membership_creator": {
        "customer_focus": [
            "what members get", "content/community quality", "price", "frequency", "commitment/cancellation",
            "creator credibility", "social proof", "free vs paid difference", "access method", "renewal",
            "onboarding", "community expectations",
        ],
        "page_terms": [
            "membership", "join", "subscribe", "plans", "pricing", "benefits", "community", "content", "courses",
            "newsletter", "about", "creator", "testimonials", "faq", "cancel", "terms", "login",
        ],
        "page_guesses": [
            "/membership/", "/join/", "/subscribe/", "/plans/", "/pricing/", "/benefits/", "/community/",
            "/about/", "/testimonials/", "/faq/", "/cancellation/", "/terms/",
        ],
        "concepts": {
            "member_value": ["member benefits", "exclusive", "community", "content", "access", "resources"],
            "price_commitment": ["monthly", "annual", "price", "cancel", "renew", "billing"],
            "creator_trust": ["about", "creator", "experience", "followers", "testimonials", "members"],
            "onboarding": ["join", "signup", "create account", "welcome", "access"],
            "retention": ["renewal", "cancel", "pause", "membership", "support"],
        },
        "priority_rules": {
            "primary_conversion_path": 1.20, "conversion_path_error": 1.20, "privacy_terms_missing": 1.16,
            "policy_content_consistency": 1.18, "measurement_telemetry": 1.18, "proof_placement_gap": 1.16,
        },
    },
    "education": {
        "customer_focus": [
            "program/course fit", "outcomes", "credentials/accreditation", "tuition", "admissions requirements",
            "deadlines", "instructors/faculty", "student proof", "schedule/delivery format", "application process",
            "support", "career/next-step outcomes",
        ],
        "page_terms": [
            "programs", "courses", "curriculum", "admissions", "apply", "enroll", "enrol", "tuition", "fees",
            "deadlines", "faculty", "instructors", "outcomes", "careers", "students", "testimonials", "faq",
        ],
        "page_guesses": [
            "/programs/", "/courses/", "/curriculum/", "/admissions/", "/apply/", "/enroll/", "/tuition/",
            "/fees/", "/deadlines/", "/faculty/", "/outcomes/", "/student-stories/", "/faq/",
        ],
        "concepts": {
            "program_fit": ["program", "course", "curriculum", "learning outcomes", "duration", "format"],
            "admissions": ["requirements", "admissions", "apply", "deadline", "prerequisite", "eligibility"],
            "cost": ["tuition", "fees", "financial aid", "scholarship", "payment plan"],
            "credibility": ["accredited", "faculty", "instructor", "certificate", "degree", "credential"],
            "outcomes": ["career", "employment", "graduates", "outcomes", "placement", "skills"],
        },
        "priority_rules": {
            "form_architecture": 1.22, "lead_form_friction": 1.16, "primary_conversion_path": 1.22,
            "conversion_path_error": 1.22, "proof_placement_gap": 1.16, "privacy_terms_missing": 1.12,
            "policy_content_consistency": 1.12,
        },
    },
    "nonprofit": {
        "customer_focus": [
            "mission clarity", "impact proof", "financial/transparency trust", "donation ease", "what funds support",
            "recurring donation terms", "tax-receipt expectations", "ways to help", "program credibility",
            "privacy", "leadership/governance", "contact",
        ],
        "page_terms": [
            "mission", "impact", "programs", "donate", "give", "support", "ways-to-give", "monthly-giving",
            "financials", "reports", "governance", "board", "leadership", "volunteer", "privacy", "contact",
        ],
        "page_guesses": [
            "/mission/", "/impact/", "/programs/", "/donate/", "/give/", "/ways-to-give/", "/monthly-giving/",
            "/financials/", "/annual-report/", "/board/", "/leadership/", "/volunteer/", "/privacy/",
        ],
        "concepts": {
            "mission": ["mission", "who we serve", "programs", "cause", "community"],
            "impact": ["impact", "outcomes", "people served", "results", "annual report"],
            "donation": ["donate", "give", "monthly", "one-time", "tax receipt", "designation"],
            "trust": ["registered charity", "financial statements", "annual report", "board", "governance"],
            "participation": ["volunteer", "fundraise", "sponsor", "events", "newsletter"],
        },
        "priority_rules": {
            "trust_credentials": 1.22, "proof_placement_gap": 1.25, "policy_content_consistency": 1.20,
            "privacy_terms_missing": 1.16, "primary_conversion_path": 1.25, "conversion_path_error": 1.25,
            "measurement_telemetry": 1.08,
        },
    },
    "automotive": {
        "customer_focus": [
            "service/vehicle fit", "price/estimate", "availability", "location", "reviews", "warranty",
            "technician/dealer trust", "booking", "inventory details", "financing", "trade-in", "parts/service",
            "contact speed", "hours",
        ],
        "page_terms": [
            "service", "repair", "maintenance", "book", "appointment", "inventory", "vehicles", "new", "used",
            "financing", "trade-in", "test-drive", "parts", "warranty", "reviews", "location", "hours", "contact",
        ],
        "page_guesses": [
            "/service/", "/repair/", "/maintenance/", "/book-service/", "/appointments/", "/inventory/", "/vehicles/",
            "/financing/", "/trade-in/", "/test-drive/", "/parts/", "/warranty/", "/reviews/", "/location/",
        ],
        "concepts": {
            "service_fit": ["repair", "maintenance", "service", "make", "model", "diagnostic"],
            "inventory": ["inventory", "new vehicles", "used vehicles", "mileage", "price", "vin"],
            "appointment": ["book service", "schedule service", "appointment", "test drive", "availability"],
            "trust": ["certified", "technician", "dealer", "reviews", "warranty", "inspection"],
            "finance": ["financing", "payment", "lease", "trade-in", "credit", "pre-approval"],
            "local": ["location", "hours", "directions", "phone", "service area"],
        },
        "priority_rules": {
            "click_to_call": 1.22, "phone_visibility": 1.20, "location_visibility": 1.24,
            "reviews_social_proof": 1.20, "form_architecture": 1.18, "primary_conversion_path": 1.22,
            "conversion_path_error": 1.22, "proof_placement_gap": 1.14,
        },
    },
}


def _dedupe_strings(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def get_business_deep_dive_pack(
    business_type: str, journey_model: str = "general", context_tags: Iterable[str] | None = None
) -> Dict[str, Any]:
    """Return the existing category pack enriched by applicable research knowledge.

    V7.4.1 does not alter classification or failure logic. Research enrichment happens
    only after a business category is resolved (or explicitly selected), and it improves
    what the deep-dive crawler looks for plus the diagnostic context available downstream.
    """
    key = str(business_type or "general").strip().lower()
    pack = BUSINESS_DEEP_DIVE_PACKS.get(key) or {}
    research = get_research_guidance(key, journey_model, list(context_tags or [])) if key != "general" else {}

    concepts: Dict[str, List[str]] = {k: list(v or []) for k, v in (pack.get("concepts") or {}).items()}
    for concept, terms in (research.get("concepts") or {}).items():
        concepts[str(concept)] = _dedupe_strings([*(concepts.get(str(concept)) or []), *(terms or [])])

    return {
        "business_type": key,
        "label": BUSINESS_TYPE_LABELS.get(key, key.replace("_", " ").title()),
        "customer_focus": _dedupe_strings([*(pack.get("customer_focus") or []), *(research.get("customer_focus") or [])]),
        "page_terms": _dedupe_strings([*(pack.get("page_terms") or []), *(research.get("page_terms") or [])]),
        "page_guesses": _dedupe_strings([*(pack.get("page_guesses") or []), *(research.get("page_guesses") or [])]),
        "concepts": concepts,
        "priority_rules": dict(pack.get("priority_rules") or {}),
        "research_guidance": research,
    }


def business_page_terms(business_type: str, journey_model: str = "general", context_tags: Iterable[str] | None = None) -> List[str]:
    return get_business_deep_dive_pack(business_type, journey_model, context_tags).get("page_terms") or []


def business_page_guesses(business_type: str, journey_model: str = "general", context_tags: Iterable[str] | None = None) -> List[str]:
    return get_business_deep_dive_pack(business_type, journey_model, context_tags).get("page_guesses") or []


def business_rule_multiplier_expansion() -> Dict[str, Dict[str, float]]:
    return {
        key: {rule: float(value) for rule, value in (pack.get("priority_rules") or {}).items()}
        for key, pack in BUSINESS_DEEP_DIVE_PACKS.items()
    }


def public_business_type_options() -> List[Dict[str, str]]:
    return [
        {"value": key, "label": label}
        for key, label in BUSINESS_TYPE_LABELS.items()
        if key not in {"general", "nonprofit"}
    ]


def knowledge_stats() -> Dict[str, int]:
    packs = list(BUSINESS_DEEP_DIVE_PACKS.values())
    stats = {
        "business_types": len(BUSINESS_DEEP_DIVE_PACKS),
        "customer_focus_items": sum(len(x.get("customer_focus") or []) for x in packs),
        "page_routing_terms": sum(len(x.get("page_terms") or []) for x in packs),
        "page_guesses": sum(len(x.get("page_guesses") or []) for x in packs),
        "concept_families": sum(len(x.get("concepts") or {}) for x in packs),
        "concept_terms": sum(sum(len(v or []) for v in (x.get("concepts") or {}).values()) for x in packs),
        "priority_rule_overrides": sum(len(x.get("priority_rules") or {}) for x in packs),
    }
    for key, value in research_knowledge_stats().items():
        stats[f"research_{key}"] = int(value)
    return stats


def evaluate_business_type_confirmation(profile: Mapping[str, Any], threshold: float = 0.72) -> Dict[str, Any]:
    """Decide whether auto classification is safe enough for a category deep dive.

    This does not choose a business type. It only evaluates the existing inference output.
    Explicit user choices are always accepted. Auto classifications must clear confidence and
    ambiguity gates before the category-specific deep dive is allowed to run.
    """
    source = str(profile.get("business_type_source") or profile.get("source") or "")
    business_type = str(profile.get("business_type") or "general")
    try:
        confidence = float(profile.get("business_type_confidence") if profile.get("business_type_confidence") is not None else profile.get("confidence") or 0.0)
    except Exception:
        confidence = 0.0
    candidates_raw = profile.get("business_type_candidates") or profile.get("score_candidates") or {}
    candidates: List[Tuple[str, float]] = []
    if isinstance(candidates_raw, Mapping):
        for key, value in candidates_raw.items():
            if key == "general":
                continue
            try:
                candidates.append((str(key), float(value)))
            except Exception:
                continue
    candidates.sort(key=lambda x: (-x[1], x[0]))
    top_score = candidates[0][1] if candidates else 0.0
    second_score = candidates[1][1] if len(candidates) > 1 else 0.0
    ratio = (second_score / top_score) if top_score > 0 else 0.0

    explicit = source == "explicit_request"
    low_confidence = business_type == "general" or confidence < float(threshold)
    ambiguous = bool(not explicit and top_score > 0 and second_score > 0 and ratio >= 0.82 and confidence < 0.90)
    required = bool(not explicit and (low_confidence or ambiguous))

    top_options = []
    for key, score in candidates[:4]:
        top_options.append({
            "value": key,
            "label": BUSINESS_TYPE_LABELS.get(key, key.replace("_", " ").title()),
            "evidence_score": round(score, 2),
        })
    return {
        "required": required,
        "reason": "ambiguous_business_type" if ambiguous else ("low_business_type_confidence" if low_confidence else "confident_auto_classification"),
        "business_type": business_type,
        "business_type_label": BUSINESS_TYPE_LABELS.get(business_type, business_type.replace("_", " ").title()),
        "confidence": round(confidence, 3),
        "threshold": round(float(threshold), 3),
        "candidate_ratio": round(ratio, 3),
        "top_candidates": top_options,
        "options": public_business_type_options(),
        "instruction": "Choose the business category that best matches the company, then resubmit the scan with business_type set to that value." if required else "No category confirmation required.",
    }


def observe_pack_concepts(text: str, business_type: str, journey_model: str = "general", context_tags: Iterable[str] | None = None) -> Dict[str, Any]:
    """Summarize which business-specific concept families were observed in scanned text.

    This is diagnostic context only. Absence does not create a failure because page coverage may be
    incomplete and some concepts are optional for a particular journey/context.
    """
    lower = str(text or "").lower()
    pack = get_business_deep_dive_pack(business_type, journey_model, context_tags)
    observations: Dict[str, Any] = {}
    for concept, terms in (pack.get("concepts") or {}).items():
        hits = [term for term in terms if str(term).lower() in lower]
        observations[concept] = {
            "observed": bool(hits),
            "signals": hits[:8],
        }
    observed_count = sum(1 for item in observations.values() if item.get("observed"))
    return {
        "business_type": business_type,
        "business_type_label": pack.get("label"),
        "customer_focus": pack.get("customer_focus") or [],
        "concepts": observations,
        "observed_concept_count": observed_count,
        "concept_family_count": len(observations),
        "coverage_ratio": round(observed_count / max(1, len(observations)), 3),
        "research_sources": (pack.get("research_guidance") or {}).get("sources") or [],
        "research_source_ids": (pack.get("research_guidance") or {}).get("source_ids") or [],
        "policy": "Concept coverage guides deep-dive evidence routing only; absence is not a scored failure by itself. Research knowledge changes investigation priority, not website evidence state.",
    }
