"""Trilloka V7.7 scan execution protocol.

Purpose
-------
Provide one deterministic production-flow contract around the existing scanner without
changing the 50 checkpoints, detection methods, research packs, scoring engine, or report engine.

Flow
----
COMMON DISCOVERY
    -> BUSINESS TYPE
    -> BUSINESS SUBTYPE
    -> TYPE-SPECIFIC INSPECTION PLAN
    -> JOURNEY/PATH RESOLUTION
    -> EXISTING CHECKPOINTS + EXISTING SCORING
    -> COMMON REPORT/DELIVERY

This module is a routing/orchestration contract. It does not manufacture evidence,
PASS/FAIL results, score weights, or research conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

try:
    from research_knowledge import get_research_guidance
except Exception:  # Allows standalone validation/import.
    get_research_guidance = None

try:
    from commercial_contracts import build_commercial_contract, commercial_minimum_gap_map
except Exception:
    build_commercial_contract = None
    commercial_minimum_gap_map = None


PROTOCOL_VERSION = "v7.7-tcea-production-flow-v1"

BUSINESS_TYPES = (
    "ecommerce", "marketplace", "local_service", "professional_service",
    "healthcare", "medspa", "legal", "financial_services", "real_estate",
    "restaurant", "hospitality_event", "saas", "b2b", "agency",
    "membership_creator", "education", "nonprofit", "automotive", "general",
)

# These are priorities for WHERE/HOW to inspect, not new checkpoints.
# Existing research_knowledge remains the authoritative source for detailed terms,
# concepts, sources, and rule multipliers.
TYPE_WORKFLOW_FOCUS: Dict[str, Dict[str, Sequence[str]]] = {
    "ecommerce": {
        "surfaces": ("product", "cart", "checkout", "shipping/delivery", "returns"),
        "priorities": ("product/offer clarity", "total cost", "checkout continuity", "delivery", "returns", "payment confidence"),
        "paths": ("direct_purchase",),
    },
    "marketplace": {
        "surfaces": ("listing/search", "provider/seller profile", "fees", "transaction/contact", "trust/safety"),
        "priorities": ("matching quality", "identity/reputation", "fees", "availability", "protection", "transaction completion"),
        "paths": ("direct_purchase", "membership_subscription", "lead_quote"),
    },
    "local_service": {
        "surfaces": ("service", "service area/location", "quote/contact", "booking", "reviews"),
        "priorities": ("service fit", "service area", "local proof", "contact/quote ease", "availability", "response expectations"),
        "paths": ("lead_quote", "appointment_consultation"),
    },
    "professional_service": {
        "surfaces": ("service/expertise", "team", "proof", "process", "pricing", "consultation/contact"),
        "priorities": ("expertise fit", "identity", "proof", "process", "commercial expectations", "qualified enquiry"),
        "paths": ("lead_quote", "appointment_consultation"),
    },
    "healthcare": {
        "surfaces": ("service/treatment", "provider", "appointment", "location", "insurance/payment", "privacy"),
        "priorities": ("provider fit", "credentials", "appointment continuity", "location", "payment/insurance", "sensitive-data trust"),
        "paths": ("appointment_consultation",),
    },
    "medspa": {
        "surfaces": ("treatment", "practitioner", "before/after or reviews", "pricing/packages", "consultation/booking", "privacy"),
        "priorities": ("treatment fit", "credentials", "proof", "pricing expectations", "booking", "safety/privacy"),
        "paths": ("appointment_consultation", "direct_purchase"),
    },
    "legal": {
        "surfaces": ("practice area", "lawyer/team", "fees/process", "proof", "consultation/intake", "privacy"),
        "priorities": ("practice fit", "lawyer identity", "trust", "hiring process", "fee expectations", "consultation"),
        "paths": ("appointment_consultation", "lead_quote"),
    },
    "financial_services": {
        "surfaces": ("product/service", "advisor", "rates/fees", "security/privacy", "application", "consultation/contact"),
        "priorities": ("trust/security", "value/fees", "professional identity", "self-service", "application/consultation", "privacy"),
        "paths": ("appointment_consultation", "lead_quote", "application_enrollment"),
    },
    "real_estate": {
        "surfaces": ("listing", "property detail", "agent", "showing/open house", "location", "financing/contact"),
        "priorities": ("listing detail", "visual proof", "agent identity", "showing path", "location", "contact"),
        "paths": ("lead_quote", "appointment_consultation"),
    },
    "restaurant": {
        "surfaces": ("menu", "reservation", "order", "hours/location", "reviews", "gallery/contact"),
        "priorities": ("menu/prices", "hours/location", "reputation", "table reservation", "order path when offered", "mobile usability"),
        "paths": ("local_visit", "reservation_event", "direct_purchase"),
    },
    "hospitality_event": {
        "surfaces": ("offer/rooms/venue", "availability", "rates", "booking", "gallery/reviews", "cancellation"),
        "priorities": ("availability", "price/rates", "experience proof", "booking continuity", "payment trust", "cancellation"),
        "paths": ("reservation_event", "direct_purchase"),
    },
    "saas": {
        "surfaces": ("product", "use cases", "pricing", "demo/trial", "customers/proof", "security/integrations"),
        "priorities": ("product fit", "commercial model", "proof", "demo/trial", "security", "implementation"),
        "paths": ("demo_sales", "membership_subscription"),
    },
    "b2b": {
        "surfaces": ("capabilities", "products/services", "industries", "specifications", "pricing/RFQ", "proof/certifications"),
        "priorities": ("capability fit", "specifications", "pricing level", "proof", "procurement", "qualified sales/RFQ"),
        "paths": ("demo_sales", "lead_quote"),
    },
    "agency": {
        "surfaces": ("services", "work/portfolio", "case studies", "team", "process", "pricing/contact"),
        "priorities": ("specialization", "work quality", "results/proof", "team", "engagement model", "discovery/contact"),
        "paths": ("lead_quote", "demo_sales"),
    },
    "membership_creator": {
        "surfaces": ("offer/benefits", "pricing", "join/subscribe", "trial/sample", "community/proof", "billing/cancellation"),
        "priorities": ("member value", "price/billing", "proof/sample", "signup effort", "renewal/cancellation", "access"),
        "paths": ("membership_subscription", "direct_purchase"),
    },
    "education": {
        "surfaces": ("program/course", "tuition/fees", "requirements", "outcomes", "apply/enroll", "advisor/contact"),
        "priorities": ("program fit", "cost", "requirements", "outcomes", "deadlines", "application completion"),
        "paths": ("application_enrollment", "lead_quote"),
    },
    "nonprofit": {
        "surfaces": ("mission/impact", "donation", "financials/trust", "programs", "payment", "support/contact"),
        "priorities": ("mission/impact", "donation continuity", "trust/transparency", "mobile giving", "recurring giving", "payment choice"),
        "paths": ("donation_support", "membership_subscription"),
    },
    "automotive": {
        "surfaces": ("inventory/service", "vehicle/service detail", "pricing/financing", "booking/test drive", "reviews", "location/contact"),
        "priorities": ("inventory/service fit", "price/finance", "location", "contact", "booking/test drive", "reputation"),
        "paths": ("lead_quote", "appointment_consultation", "direct_purchase"),
    },
    "general": {
        "surfaces": ("home", "primary navigation", "contact", "about", "prominent customer actions"),
        "priorities": ("business identity", "primary offer", "dominant customer action", "trust", "technical foundation"),
        "paths": ("general",),
    },
}


# Subtype routing is an inspection-priority layer only.  It never creates a
# checkpoint result and never overrides stronger current-site evidence.
# Keys intentionally use normalized, descriptive aliases so the production
# integration can map the exact infer_subtype() labels to these families.
SUBTYPE_WORKFLOW_FOCUS: Dict[str, Dict[str, Dict[str, Sequence[str]]]] = {
    "ecommerce": {
        "fashion_apparel": {"surfaces": ("category", "product detail", "size/fit", "shipping", "returns"), "priorities": ("visual merchandising", "size/fit confidence", "variant clarity", "delivery", "returns")},
        "electronics": {"surfaces": ("category", "product detail", "specifications", "comparison", "shipping/returns"), "priorities": ("specification clarity", "compatibility", "comparison", "warranty", "delivery")},
        "home_goods": {"surfaces": ("category", "product detail", "dimensions/materials", "delivery", "returns"), "priorities": ("dimensions", "materials", "visual proof", "delivery expectations", "returns")},
        "specialty_retail": {"surfaces": ("category", "product detail", "availability", "checkout", "policies"), "priorities": ("product fit", "availability", "price", "checkout", "policies")},
    },
    "marketplace": {
        "services_marketplace": {"surfaces": ("search/listing", "provider profile", "quote/contact", "trust/safety", "fees"), "priorities": ("provider fit", "reputation", "matching/contact", "protection", "fees")},
        "goods_marketplace": {"surfaces": ("search/listing", "item detail", "seller profile", "transaction", "protection"), "priorities": ("item quality", "seller trust", "price", "transaction", "buyer protection")},
        "rental_marketplace": {"surfaces": ("search/listing", "availability", "pricing/fees", "booking", "cancellation"), "priorities": ("availability", "total price", "booking", "host/provider trust", "cancellation")},
    },
    "local_service": {
        "home_service": {"surfaces": ("service", "service area", "quote", "reviews", "emergency/availability"), "priorities": ("service fit", "coverage", "quote friction", "local proof", "availability")},
        "cleaning": {"surfaces": ("services", "pricing/quote", "service area", "booking", "reviews"), "priorities": ("scope clarity", "price/quote", "coverage", "booking", "trust")},
        "moving": {"surfaces": ("services", "locations", "estimate", "insurance/trust", "reviews"), "priorities": ("move fit", "coverage", "estimate", "protection", "reputation")},
        "contractor_trades": {"surfaces": ("services", "projects", "credentials", "estimate", "service area"), "priorities": ("capability", "proof of work", "credentials", "estimate", "coverage")},
    },
    "professional_service": {
        "consulting": {"surfaces": ("expertise", "industries", "case studies", "team", "consultation"), "priorities": ("specialization", "outcomes", "proof", "expert identity", "qualified enquiry")},
        "accounting_tax": {"surfaces": ("services", "team", "credentials", "process", "consultation/privacy"), "priorities": ("service fit", "professional trust", "process", "fees/expectations", "secure contact")},
        "engineering_architecture": {"surfaces": ("capabilities", "projects", "team", "credentials", "RFQ/contact"), "priorities": ("technical fit", "project proof", "qualifications", "delivery capability", "qualified enquiry")},
    },
    "healthcare": {
        "dental": {"surfaces": ("treatments", "dentists", "new patient", "insurance/payment", "appointment"), "priorities": ("treatment fit", "provider trust", "new-patient clarity", "payment", "booking")},
        "physio_chiro": {"surfaces": ("conditions/services", "practitioners", "locations", "fees/insurance", "booking"), "priorities": ("condition fit", "practitioner trust", "location", "fees", "booking")},
        "medical_clinic": {"surfaces": ("services", "providers", "patient information", "location", "appointment/privacy"), "priorities": ("service eligibility", "provider identity", "patient instructions", "access", "privacy/booking")},
        "mental_health": {"surfaces": ("services", "therapists", "approach", "fees", "consultation/privacy"), "priorities": ("care fit", "therapist identity", "approach", "fees", "privacy/contact")},
    },
    "medspa": {
        "injectables": {"surfaces": ("treatments", "practitioners", "results/proof", "pricing", "consultation"), "priorities": ("treatment clarity", "credentials", "proof", "price expectations", "consultation")},
        "laser_skin": {"surfaces": ("treatments", "technology", "practitioners", "results", "booking"), "priorities": ("treatment fit", "technology/safety", "provider trust", "proof", "booking")},
        "body_aesthetics": {"surfaces": ("treatments", "eligibility", "results", "pricing/packages", "consultation"), "priorities": ("candidate fit", "expectations", "proof", "pricing", "consultation")},
    },
    "legal": {
        "consumer_law": {"surfaces": ("practice areas", "lawyers", "process", "fees", "consultation"), "priorities": ("matter fit", "lawyer identity", "process", "fee expectations", "intake")},
        "business_law": {"surfaces": ("services", "industries", "lawyers", "experience", "consultation"), "priorities": ("commercial fit", "expertise", "team", "experience", "qualified contact")},
        "litigation": {"surfaces": ("practice area", "lawyers", "results/proof", "process", "consultation"), "priorities": ("case fit", "advocate identity", "credible proof", "process", "intake")},
    },
    "financial_services": {
        "financial_advisory": {"surfaces": ("services", "advisors", "fees", "approach", "consultation"), "priorities": ("service fit", "advisor identity", "fee transparency", "approach", "consultation")},
        "insurance": {"surfaces": ("products", "coverage", "quote", "advisor/contact", "claims"), "priorities": ("coverage fit", "terms", "quote", "trust", "claims/support")},
        "lending_mortgage": {"surfaces": ("products", "rates/fees", "eligibility", "application", "advisor/privacy"), "priorities": ("product fit", "cost", "eligibility", "application", "privacy/trust")},
    },
    "real_estate": {
        "residential_agent": {"surfaces": ("listings", "property detail", "agent", "neighborhood", "showing/contact"), "priorities": ("inventory", "property detail", "agent trust", "location context", "showing")},
        "brokerage": {"surfaces": ("listings", "agents", "offices/areas", "buy/sell paths", "contact"), "priorities": ("inventory", "agent discovery", "coverage", "buyer/seller routing", "contact")},
        "property_management": {"surfaces": ("services", "properties", "owner/tenant paths", "fees", "contact"), "priorities": ("service scope", "property proof", "audience routing", "fee expectations", "enquiry")},
        "developer_new_homes": {"surfaces": ("projects", "plans/pricing", "location", "availability", "register/contact"), "priorities": ("project proof", "product/price", "location", "availability", "lead capture")},
    },
    "restaurant": {
        "fine_dining": {"surfaces": ("menu", "reservation", "hours/location", "experience/gallery", "reviews"), "priorities": ("menu/prices", "reservation", "experience", "location/hours", "reputation")},
        "casual_dining": {"surfaces": ("menu", "hours/location", "reservation/waitlist", "order", "reviews"), "priorities": ("menu/prices", "location/hours", "reservation/waitlist", "ordering", "reputation")},
        "cafe_bakery": {"surfaces": ("menu", "hours/location", "directions", "order", "gallery", "contact"), "priorities": ("menu/prices", "hours/location", "directions/visit", "order/pickup when offered", "product appeal", "contact"), "paths": ("local_visit", "direct_purchase", "reservation_event")},
        "quick_service_takeout": {"surfaces": ("menu", "order", "delivery/pickup", "hours/location", "policies"), "priorities": ("menu/prices", "ordering", "fulfilment", "hours/location", "checkout continuity")},
        "catering_events": {"surfaces": ("catering/events", "packages/menu", "gallery", "availability", "enquiry"), "priorities": ("event fit", "packages/pricing", "proof", "availability", "enquiry")},
    },
    "hospitality_event": {
        "hotel_lodging": {"surfaces": ("rooms", "availability", "rates", "booking", "amenities/policies"), "priorities": ("room fit", "availability", "total rate", "booking", "cancellation/policies")},
        "event_venue": {"surfaces": ("spaces", "capacity/packages", "gallery", "availability", "event enquiry"), "priorities": ("venue fit", "capacity", "pricing/packages", "proof", "availability/enquiry")},
        "tour_activity": {"surfaces": ("experience", "schedule/availability", "pricing", "booking", "meeting/cancellation"), "priorities": ("experience fit", "availability", "price", "booking", "logistics/policies")},
        "rental_charter": {"surfaces": ("fleet/inventory", "availability", "rates", "booking/enquiry", "terms"), "priorities": ("asset fit", "availability", "price", "booking", "terms")},
    },
    "saas": {
        "self_serve_saas": {"surfaces": ("product", "pricing", "signup/trial", "onboarding", "help/security"), "priorities": ("product clarity", "price", "signup", "time-to-value", "trust")},
        "enterprise_saas": {"surfaces": ("solutions", "use cases", "customers", "security", "demo/contact sales"), "priorities": ("business fit", "proof", "security", "implementation", "qualified sales")},
        "developer_platform": {"surfaces": ("product", "documentation", "pricing", "signup/API", "status/security"), "priorities": ("technical fit", "docs", "price", "activation", "reliability/security")},
    },
    "b2b": {
        "manufacturer": {"surfaces": ("products", "specifications", "capabilities", "certifications", "RFQ/contact"), "priorities": ("product fit", "technical specs", "capacity", "certification", "RFQ")},
        "distributor_wholesale": {"surfaces": ("catalog", "brands/products", "availability", "account/pricing", "quote/contact"), "priorities": ("catalog fit", "availability", "commercial terms", "account access", "quote")},
        "industrial_service": {"surfaces": ("capabilities", "industries", "projects", "certifications", "RFQ/contact"), "priorities": ("capability fit", "industry proof", "project evidence", "compliance", "qualified enquiry")},
    },
    "agency": {
        "marketing_agency": {"surfaces": ("services", "case studies", "results", "team", "contact"), "priorities": ("specialization", "results", "proof", "team", "discovery")},
        "creative_design": {"surfaces": ("portfolio", "services", "process", "team", "contact"), "priorities": ("work quality", "fit", "process", "team", "enquiry")},
        "web_software_agency": {"surfaces": ("services", "projects", "technical capability", "process", "quote/contact"), "priorities": ("technical fit", "project proof", "delivery process", "scope expectations", "qualified enquiry")},
    },
    "membership_creator": {
        "paid_membership": {"surfaces": ("benefits", "pricing", "join", "community/proof", "billing/cancellation"), "priorities": ("member value", "price", "signup", "proof", "billing/cancellation")},
        "course_creator": {"surfaces": ("course", "curriculum", "instructor", "pricing", "enroll"), "priorities": ("learning fit", "curriculum", "instructor trust", "price", "enrollment")},
        "newsletter_media": {"surfaces": ("content/sample", "subscribe", "pricing", "author/about", "archive"), "priorities": ("content value", "sample quality", "subscription", "creator identity", "access")},
    },
    "education": {
        "higher_education": {"surfaces": ("programs", "admissions", "tuition", "requirements", "apply"), "priorities": ("program fit", "cost", "requirements", "deadlines", "application")},
        "vocational_training": {"surfaces": ("program/course", "outcomes", "schedule", "fees", "enroll/contact"), "priorities": ("career fit", "outcomes", "schedule", "cost", "enrollment")},
        "online_course_provider": {"surfaces": ("courses", "curriculum", "instructors", "pricing", "enroll"), "priorities": ("course fit", "curriculum", "instructor proof", "price", "enrollment")},
    },
    "nonprofit": {
        "donation_led": {"surfaces": ("mission/impact", "donate", "financial trust", "programs", "payment"), "priorities": ("impact", "donation continuity", "transparency", "payment", "recurring giving")},
        "membership_association": {"surfaces": ("mission/benefits", "membership", "dues", "events/resources", "join"), "priorities": ("member value", "dues", "benefits", "community", "joining")},
        "service_charity": {"surfaces": ("programs/services", "eligibility/access", "impact", "donate/support", "contact"), "priorities": ("service access", "eligibility", "impact", "support", "contact")},
    },
    "automotive": {
        "dealer": {"surfaces": ("inventory", "vehicle detail", "pricing/finance", "test drive", "location/contact"), "priorities": ("inventory", "vehicle detail", "price/finance", "test drive", "dealer trust")},
        "repair_service": {"surfaces": ("services", "pricing/estimate", "booking", "reviews", "location"), "priorities": ("service fit", "price expectations", "booking", "reputation", "location")},
        "parts_accessories": {"surfaces": ("catalog", "product detail", "fitment", "availability", "checkout/shipping"), "priorities": ("part fit", "compatibility", "availability", "price", "fulfilment")},
    },
}


# Exact aliases emitted by pathway_markers.infer_subtype().  They map the existing
# classifier vocabulary onto workflow families; this does not reclassify the site.
SUBTYPE_ROUTING_ALIASES: Dict[str, Dict[str, str]] = {
    "restaurant": {"dine_in_restaurant":"casual_dining","cafe_bakery":"cafe_bakery","takeout_delivery":"quick_service_takeout","catering_events":"catering_events","bar_nightlife":"casual_dining"},
    "ecommerce": {"retail_store":"specialty_retail","subscription_commerce":"specialty_retail","digital_goods":"specialty_retail","wholesale":"specialty_retail"},
    "marketplace": {"product_marketplace":"goods_marketplace","service_marketplace":"services_marketplace","booking_marketplace":"rental_marketplace"},
    "local_service": {"home_trades":"contractor_trades","cleaning_maintenance":"cleaning","moving_logistics":"moving","repair_installation":"home_service","emergency_service":"home_service"},
    "professional_service": {"consulting":"consulting","accounting_tax":"accounting_tax","engineering_architecture":"engineering_architecture","business_services":"consulting"},
    "healthcare": {"medical_clinic":"medical_clinic","dental":"dental","physio_rehab":"physio_chiro","mental_health":"mental_health","allied_health":"physio_chiro"},
    "medspa": {"injectables":"injectables","laser_aesthetics":"laser_skin","skin_aesthetics":"laser_skin","body_aesthetics":"body_aesthetics"},
    "legal": {"litigation":"litigation","personal_injury":"consumer_law","family_law":"consumer_law","immigration":"consumer_law","business_law":"business_law","real_estate_law":"consumer_law"},
    "financial_services": {"financial_advisory":"financial_advisory","insurance":"insurance","mortgage":"lending_mortgage","accounting_finance":"financial_advisory","lending":"lending_mortgage"},
    "real_estate": {"residential_sales":"residential_agent","property_management":"property_management","rentals":"property_management","commercial_real_estate":"brokerage","developer":"developer_new_homes"},
    "hospitality_event": {"hotel_accommodation":"hotel_lodging","venue_events":"event_venue","tour_activity":"tour_activity","rental_charter":"rental_charter"},
    "saas": {"self_serve_saas":"self_serve_saas","sales_led_saas":"enterprise_saas","developer_platform":"developer_platform","enterprise_software":"enterprise_saas"},
    "b2b": {"manufacturer":"manufacturer","distributor_wholesaler":"distributor_wholesale","industrial_service":"industrial_service","enterprise_solution":"industrial_service","supplier_rfq":"manufacturer"},
    "agency": {"marketing_agency":"marketing_agency","creative_agency":"creative_design","web_agency":"web_software_agency","pr_communications":"marketing_agency"},
    "membership_creator": {"creator_content":"course_creator","community_membership":"paid_membership","newsletter_publisher":"newsletter_media","association":"paid_membership"},
    "education": {"school_college":"higher_education","course_provider":"online_course_provider","tutoring_training":"vocational_training","bootcamp":"vocational_training"},
    "nonprofit": {"charity":"donation_led","advocacy_nonprofit":"service_charity","community_nonprofit":"service_charity","foundation":"donation_led"},
    "automotive": {"dealer":"dealer","repair_service":"repair_service","parts_retail":"parts_accessories","rental":"dealer"},
}


COMMON_DISCOVERY_STEPS = (
    "Normalize URL and establish reachability/HTTPS evidence.",
    "Collect the existing bounded homepage/static/rendered evidence used by Trilloka.",
    "Collect identity evidence: title, H1, meta, schema/place signals, prominent copy and navigation.",
    "When exposed, prioritize one first-party self-description surface (About / Our Story / Who We Are / What We Do / Services) before locking the business type; treat it as supporting current-site evidence, never as sole authority.",
    "Collect prominent customer-action evidence without yet forcing a journey conclusion.",
    "Infer broad business type from current-site evidence; learning memory may only provide its existing bounded recognition hint.",
    "Infer business subtype from current-site evidence.",
    "If type/subtype evidence is weak or conflicting, perform only the existing bounded clarification crawl; do not borrow another type's assumptions.",
    "Freeze the best-supported business type/subtype for inspection routing. The current site remains authoritative.",
)

COMMON_COMPLETION_STEPS = (
    "Run the existing 50-checkpoint engine; do not add, remove or rename checkpoints.",
    "Apply existing applicability and PASS/FAIL/UNKNOWN/NOT_APPLICABLE rules.",
    "Apply existing research-supported scoring multipliers only where their current guardrails allow.",
    "Run existing deduplication, severity, score, maturity and evidence-confidence logic.",
    "Build strengths, weaknesses, opportunities and remediation from verified results.",
    "Return to the single common report pipeline for every business type.",
    "Generate the existing customer/admin report presentation, Vault/archive data and delivery payload.",
    "Record the completed scan in learning memory only after the scan result is complete; learned routing never becomes evidence for the current site.",
)


@dataclass(frozen=True)
class WorkflowPlan:
    protocol_version: str
    phase: str
    business_type: str
    business_subtype: str
    business_confidence: float
    subtype_confidence: float
    journey_model: str
    journey_status: str
    context_tags: List[str]
    common_discovery_steps: List[str]
    type_surfaces: List[str]
    type_priorities: List[str]
    candidate_journeys: List[str]
    research_page_terms: List[str]
    research_page_guesses: List[str]
    research_concepts: Dict[str, List[str]]
    research_customer_focus: List[str]
    commercial_contract: Dict[str, Any]
    commercial_minimum_gap_map: List[Dict[str, Any]]
    inspection_instructions: List[str]
    common_completion_steps: List[str]
    guardrails: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clean_type(value: Any) -> str:
    value = str(value or "general").strip().lower().replace("-", "_").replace(" ", "_")
    return value if value in TYPE_WORKFLOW_FOCUS else "general"


def _dedupe(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _profile(scan_or_profile: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(scan_or_profile, Mapping):
        return {}
    p = scan_or_profile.get("architecture_profile")
    if isinstance(p, Mapping):
        return p
    p = scan_or_profile.get("business_profile")
    if isinstance(p, Mapping):
        return p
    return scan_or_profile



def _normalize_subtype(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")


def _subtype_focus(btype: str, subtype: str) -> Optional[Dict[str, Sequence[str]]]:
    """Resolve exact/near subtype family without inventing a classification."""
    table = SUBTYPE_WORKFLOW_FOCUS.get(btype) or {}
    key = _normalize_subtype(subtype)
    if not key:
        return None
    alias = (SUBTYPE_ROUTING_ALIASES.get(btype) or {}).get(key)
    if alias and alias in table:
        return table[alias]
    if key in table:
        return table[key]
    # Exact token containment is only a routing alias after infer_subtype has supplied a label.
    matches = []
    for family, cfg in table.items():
        if family in key or key in family:
            matches.append((len(family), family, cfg))
    if not matches:
        return None
    matches.sort(reverse=True)
    return matches[0][2]



def workflow_routing_terms(plan: Mapping[str, Any]) -> List[str]:
    """Return URL/page-routing vocabulary from the already resolved workflow."""
    raw: List[str] = []
    raw.extend(plan.get("research_page_terms") or [])
    raw.extend(plan.get("type_surfaces") or [])
    raw.extend(plan.get("type_priorities") or [])
    terms: List[str] = []
    for item in raw:
        value = str(item or "").lower().replace("/", " ").replace("-", " ")
        for token in value.split():
            token = token.strip(" ,()[]:")
            if len(token) >= 3 and token not in {"when", "with", "from", "into", "and", "the", "for"}:
                terms.append(token)
    return _dedupe(terms)


def workflow_page_guesses(plan: Mapping[str, Any]) -> List[str]:
    # Research guesses are authoritative routing hints. Add only conservative path guesses
    # derived from simple decision-surface names so a bounded crawl does not miss an entire
    # commercial topic (menu, location, pricing, booking, etc.). Guesses are discovery only.
    guesses = list(plan.get("research_page_guesses") or [])
    safe = {
        "menu":"/menu/", "hours":"/hours/", "location":"/location/", "locations":"/locations/",
        "directions":"/location/", "order":"/order/", "reservation":"/reservations/", "booking":"/book/",
        "pricing":"/pricing/", "reviews":"/reviews/", "gallery":"/gallery/", "contact":"/contact/",
        "services":"/services/", "service":"/services/", "products":"/products/", "product":"/products/",
        "about":"/about/", "team":"/team/", "faq":"/faq/", "security":"/security/",
        "case":"/case-studies/", "projects":"/projects/", "portfolio":"/portfolio/", "apply":"/apply/",
        "donation":"/donate/", "donate":"/donate/", "membership":"/membership/", "join":"/join/",
    }
    for surface in plan.get("type_surfaces") or []:
        value = str(surface or "").lower().replace("-", " ").replace("_", " ")
        for token in value.replace("/", " ").split():
            token = token.strip(" ,()[]:")
            if token in safe:
                guesses.append(safe[token])
    return _dedupe(guesses)



def build_production_workflow(scan_or_profile: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the deterministic next-stage plan from the existing architecture result.

    This function intentionally does not infer business type itself. The existing
    architecture model remains authoritative. It consumes that result and tells the
    production scanner how to proceed.
    """
    p = _profile(scan_or_profile)
    btype = _clean_type(p.get("business_type"))
    subtype = str(p.get("business_subtype") or p.get("business_subtype_label") or "").strip()
    bconf = float(p.get("business_type_confidence") or p.get("confidence") or 0.0)
    sconf = float(p.get("business_subtype_confidence") or 0.0)
    journey = str(p.get("journey_model") or "general").strip().lower()
    contexts = _dedupe(p.get("context_tags") or [])
    marker = p.get("journey_marker_resolution") if isinstance(p.get("journey_marker_resolution"), Mapping) else {}
    journey_status = str(marker.get("status") or ("RESOLVED" if p.get("journey_resolved") else "PROVISIONAL"))

    focus = TYPE_WORKFLOW_FOCUS[btype]
    subtype_focus = _subtype_focus(btype, subtype)
    effective_surfaces = _dedupe(
        list((subtype_focus or {}).get("surfaces") or []) + list(focus["surfaces"])
    )
    effective_priorities = _dedupe(
        list((subtype_focus or {}).get("priorities") or []) + list(focus["priorities"])
    )

    guidance: Dict[str, Any] = {}
    if callable(get_research_guidance):
        try:
            # If the path is unresolved, category knowledge still guides discovery.
            # Journey-specific knowledge is allowed only as a search aid; it cannot create a finding.
            guidance = get_research_guidance(btype, journey if journey else "general", contexts) or {}
        except Exception:
            guidance = {}

    research_terms = _dedupe(guidance.get("page_terms") or [])
    research_guesses = _dedupe(guidance.get("page_guesses") or [])
    customer_focus = _dedupe(guidance.get("customer_focus") or [])
    concepts = {
        str(k): _dedupe(v or [])
        for k, v in (guidance.get("concepts") or {}).items()
        if isinstance(v, (list, tuple, set))
    }

    commercial_contract: Dict[str, Any] = {}
    commercial_gap_map: List[Dict[str, Any]] = []
    if callable(build_commercial_contract):
        try:
            commercial_contract = build_commercial_contract(btype, subtype, subtype_focus)
            if callable(commercial_minimum_gap_map):
                commercial_gap_map = commercial_minimum_gap_map(commercial_contract, effective_surfaces)
        except Exception:
            commercial_contract, commercial_gap_map = {}, []

    type_decided = btype != "general" and bconf >= 0.60
    subtype_decided = bool(subtype) and subtype.lower() != "unresolved" and sconf >= 0.50

    if not type_decided:
        phase = "COMMON_DISCOVERY"
    elif not subtype_decided:
        phase = "SUBTYPE_CLARIFICATION"
    elif not bool(p.get("journey_resolved")):
        phase = "TYPE_SPECIFIC_PATH_RESOLUTION"
    else:
        phase = "TYPE_SPECIFIC_VERIFICATION_AND_SCORING"

    instructions = [
        "Use the confirmed business type to establish commercial context and a Commercial Contract; do not change the 50-checkpoint structure.",
        "Treat subtype as an inspection modifier, never as a routing gate or proof of a customer path.",
        "Use Commercial Minimums to decide what should reasonably be inspected for this economic model; absence is eligible for a gap only after the expected surfaces have sufficient coverage.",
        "Prioritize direct observed customer-path markers over semantic/business priors when resolving the journey.",
        "Use the type's decision surfaces before generic low-value pages when the crawl budget is bounded.",
        "Use research page terms/page guesses/concepts as routing and observation instructions, not as proof that a feature exists or is missing.",
        "Separate site evidence (what exists), external measurement evidence (how it behaves), and commercial research evidence (why an observed condition may matter).",
        "Organize verified problems by revenue decision point and causal leak class rather than treating SEO/technical findings as automatically commercially important.",
        "Verify the actual site's dominant path before applying journey-specific negative conclusions.",
        "Keep secondary journeys as secondary unless their current-site marker authority exceeds the primary candidate.",
        "After the relevant pages/path are inspected, pass the accumulated evidence to the existing checkpoint and scoring engines unchanged.",
    ]

    guardrails = [
        "No new checkpoints.",
        "No checkpoint removal or renaming.",
        "No replacement of existing detection methods.",
        "No research-only FAIL.",
        "No learned-memory-only finding or score change.",
        "No business-type prior may override stronger current-site path evidence.",
        "Generic semantics may guide discovery but may not create a scored finding.",
        "Research may support commercial relevance but may not prove a site-specific condition.",
        "Commercial Minimum absence requires verified applicability plus sufficient inspection coverage.",
        "UNKNOWN remains UNKNOWN when evidence is insufficient.",
        "All business-specific branches rejoin the same report/display/delivery pipeline after scoring.",
    ]

    plan = WorkflowPlan(
        protocol_version=PROTOCOL_VERSION,
        phase=phase,
        business_type=btype,
        business_subtype=subtype or "unresolved",
        business_confidence=round(bconf, 3),
        subtype_confidence=round(sconf, 3),
        journey_model=journey or "general",
        journey_status=journey_status,
        context_tags=contexts,
        common_discovery_steps=list(COMMON_DISCOVERY_STEPS),
        type_surfaces=effective_surfaces,
        type_priorities=effective_priorities,
        candidate_journeys=list((subtype_focus or {}).get("paths") or focus["paths"]),
        research_page_terms=research_terms,
        research_page_guesses=research_guesses,
        research_concepts=concepts,
        research_customer_focus=customer_focus,
        commercial_contract=commercial_contract,
        commercial_minimum_gap_map=commercial_gap_map,
        inspection_instructions=instructions,
        common_completion_steps=list(COMMON_COMPLETION_STEPS),
        guardrails=guardrails,
    )
    return plan.to_dict()


def workflow_trace(plan: Mapping[str, Any]) -> List[str]:
    """Human-readable execution trace for logs/tests."""
    btype = str(plan.get("business_type") or "general")
    subtype = str(plan.get("business_subtype") or "unresolved")
    journey = str(plan.get("journey_model") or "general")
    return [
        "01 COMMON_DISCOVERY",
        f"02 BUSINESS_TYPE={btype}",
        f"03 BUSINESS_SUBTYPE={subtype}",
        f"04 TYPE_BRANCH={btype}",
        f"05 JOURNEY_RESOLUTION={journey}",
        "06 TYPE_SPECIFIC_EVIDENCE_COLLECTION",
        "07 EXISTING_50_CHECKPOINTS",
        "08 EXISTING_SCORING",
        "09 COMMON_REPORT_BUILD",
        "10 COMMON_DISPLAY_AND_DELIVERY",
        "11 POST_SCAN_LEARNING",
    ]


def validate_protocol() -> Dict[str, Any]:
    missing = [b for b in BUSINESS_TYPES if b not in TYPE_WORKFLOW_FOCUS]
    empty = [
        b for b, cfg in TYPE_WORKFLOW_FOCUS.items()
        if not cfg.get("surfaces") or not cfg.get("priorities") or not cfg.get("paths")
    ]
    subtype_parent_missing = [b for b in SUBTYPE_WORKFLOW_FOCUS if b not in TYPE_WORKFLOW_FOCUS]
    subtype_families = sum(len(v) for v in SUBTYPE_WORKFLOW_FOCUS.values())
    bad_alias_targets = [
        f"{b}:{src}->{dst}"
        for b, aliases in SUBTYPE_ROUTING_ALIASES.items()
        for src, dst in aliases.items()
        if dst not in (SUBTYPE_WORKFLOW_FOCUS.get(b) or {})
    ]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "business_types": len(TYPE_WORKFLOW_FOCUS),
        "subtype_enabled_business_types": len(SUBTYPE_WORKFLOW_FOCUS),
        "subtype_workflow_families": subtype_families,
        "missing_business_types": missing,
        "empty_workflows": empty,
        "subtype_parent_missing": subtype_parent_missing,
        "bad_alias_targets": bad_alias_targets,
        "valid": not missing and not empty and not subtype_parent_missing and not bad_alias_targets,
    }


if __name__ == "__main__":
    print(validate_protocol())
