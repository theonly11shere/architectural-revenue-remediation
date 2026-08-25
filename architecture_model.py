"""Trilloka Journey + Context architecture model (v7.1).

The scanner deliberately avoids an endlessly-growing industry taxonomy.  It infers:
1) how a public website appears to convert a visitor (journey model), and
2) which contextual obligations materially change that journey (context tags).

Industry/business-type values supplied by older clients are accepted only as weak hints for
backward compatibility.  They never override stronger page/action evidence.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

JOURNEY_LABELS: Dict[str, str] = {
    "lead_quote": "Lead / Quote",
    "appointment_consultation": "Appointment / Consultation",
    "reservation_event": "Reservation / Event",
    "direct_purchase": "Direct Purchase",
    "demo_sales": "Demo / Sales",
    "membership_subscription": "Membership / Subscription",
    "general": "General / Unresolved Journey",
}

JOURNEY_PRIMARY_CONVERSION: Dict[str, str] = {
    "lead_quote": "qualified_lead_or_quote",
    "appointment_consultation": "appointment_or_consultation",
    "reservation_event": "reservation_or_event_enquiry",
    "direct_purchase": "purchase_or_checkout",
    "demo_sales": "demo_trial_or_sales_contact",
    "membership_subscription": "subscribe_join_or_membership",
    "general": "primary_site_action",
}

JOURNEY_SECONDARY_CONVERSIONS: Dict[str, List[str]] = {
    "lead_quote": ["contact_form", "call", "booking"],
    "appointment_consultation": ["contact_form", "call", "directions"],
    "reservation_event": ["contact_form", "call", "directions"],
    "direct_purchase": ["product_question", "chat", "contact"],
    "demo_sales": ["contact_form", "call", "chat"],
    "membership_subscription": ["contact", "follow", "community"],
    "general": ["contact"],
}

CONTEXT_LABELS: Dict[str, str] = {
    "regulated_high_trust": "Regulated / High-Trust",
    "local_location_dependent": "Local / Location-Dependent",
    "commerce_payment": "Commerce / Payment",
    "sensitive_data": "Sensitive-Data Collection",
    "enterprise_considered_purchase": "Enterprise / Considered Purchase",
    "hospitality_event": "Hospitality / Event",
}

# Common low-weight foundation layer. These checks are intentionally business-agnostic.
COMMON_FOUNDATION_IDS = frozenset({1, 2, *range(16, 36)})
ARCHITECTURAL_CHECKPOINT_IDS = frozenset(set(range(1, 51)) - set(COMMON_FOUNDATION_IDS))

# Journey URL priority terms.  These choose evidence pages; they do not score by themselves.
JOURNEY_PAGE_TERMS: Dict[str, Tuple[str, ...]] = {
    "lead_quote": (
        "quote", "estimate", "contact", "consultation", "enquiry", "inquiry", "request",
        "services", "projects", "portfolio", "reviews", "about", "team",
    ),
    "appointment_consultation": (
        "appointment", "book", "booking", "schedule", "consultation", "patient", "treatment",
        "services", "team", "credentials", "reviews", "contact",
    ),
    "reservation_event": (
        "reserve", "reservation", "booking", "book", "charter", "cruise", "event", "venue",
        "tour", "rental", "wedding", "corporate", "contact", "reviews",
    ),
    "direct_purchase": (
        "product", "products", "shop", "cart", "checkout", "order", "shipping", "delivery",
        "returns", "refund", "contact",
    ),
    "demo_sales": (
        "demo", "contact-sales", "contact", "pricing", "plans", "trial", "signup", "sign-up",
        "security", "customers", "case-studies", "solutions",
    ),
    "membership_subscription": (
        "subscribe", "join", "membership", "newsletter", "courses", "community", "pricing", "about", "contact",
    ),
    "general": ("contact", "book", "quote", "pricing", "services", "about", "team", "reviews"),
}

JOURNEY_PAGE_GUESSES: Dict[str, List[str]] = {
    "lead_quote": ["/contact/", "/request-a-quote/", "/quote/", "/services/", "/projects/"],
    "appointment_consultation": ["/book/", "/appointments/", "/consultation/", "/services/", "/contact/"],
    "reservation_event": ["/reservations/", "/book/", "/events/", "/charters/", "/contact/"],
    "direct_purchase": ["/shop/", "/products/", "/cart/", "/checkout/", "/returns/"],
    "demo_sales": ["/demo/", "/contact-sales/", "/pricing/", "/solutions/", "/case-studies/"],
    "membership_subscription": ["/subscribe/", "/join/", "/membership/", "/pricing/", "/community/"],
    "general": ["/contact/", "/services/", "/about/"],
}

JOURNEY_EXPECTED_ACTIONS: Dict[str, Set[str]] = {
    "lead_quote": {"quote", "contact", "call", "book"},
    "appointment_consultation": {"book", "contact", "call", "reserve"},
    "reservation_event": {"reserve", "book", "contact", "call", "directions", "order"},
    "direct_purchase": {"add_to_cart", "buy", "order", "checkout"},
    "demo_sales": {"demo", "trial", "contact", "quote", "book"},
    "membership_subscription": {"subscribe", "join", "contact", "buy"},
    "general": {"buy", "order", "reserve", "book", "call", "quote", "trial", "demo", "subscribe", "contact"},
}

# Weak backwards-compatibility hint only. Strong page/action evidence wins.
LEGACY_HINT_TO_JOURNEY: Dict[str, str] = {
    "restaurant": "reservation_event",
    "local_service": "lead_quote",
    "professional_service": "lead_quote",
    "medspa": "appointment_consultation",
    "legal": "appointment_consultation",
    "ecommerce": "direct_purchase",
    "saas": "demo_sales",
    "agency": "lead_quote",
    "b2b": "demo_sales",
    "creator": "membership_subscription",
    "general": "general",
}

# Search fallback is intentionally generic. Google primary type remains preferred.
JOURNEY_COMPETITOR_SEARCH_TEXT: Dict[str, str] = {
    "lead_quote": "local service provider",
    "appointment_consultation": "appointment based service",
    "reservation_event": "reservation event service",
    "direct_purchase": "retail store",
    "demo_sales": "business services company",
    "membership_subscription": "membership service",
    "general": "business",
}

# Phrase dictionaries are weighted by where they appear.  Strong intent terms deliberately outrank
# incidental words such as "menu", "food", "software" or "blog".
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
}

REGULATED_TERMS = (
    "law firm", "lawyer", "attorney", "legal services", "physiotherapy", "physiotherapist", "medical clinic",
    "dentist", "dental clinic", "chiropractic", "psychologist", "counselling", "counseling", "podiatry",
    "registered massage therapist", "occupational therapy", "speech therapy", "chartered professional accountant",
    "financial advisor", "investment advisor", "securities", "insurance broker", "pharmacy",
)
SENSITIVE_TERMS = (
    "patient", "medical", "health history", "health information", "diagnosis", "symptom", "insurance claim",
    "legal matter", "case details", "immigration", "financial information", "tax return", "credit card",
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
    "event", "wedding", "venue", "cruise", "charter", "yacht", "tour", "reservation", "reserve",
    "restaurant", "catering", "hotel", "banquet", "rental",
)


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
        "law": "legal", "software": "saas", "commerce": "ecommerce", "auto": "auto", "": "auto",
        # V7 direct customer-journey hints. These are hints, not forced scoring categories.
        "lead": "lead_quote", "quote": "lead_quote", "lead_quote": "lead_quote",
        "appointment": "appointment_consultation", "consultation": "appointment_consultation",
        "appointment_consultation": "appointment_consultation",
        "reservation": "reservation_event", "event": "reservation_event", "reservation_event": "reservation_event",
        "purchase": "direct_purchase", "direct_purchase": "direct_purchase",
        "demo": "demo_sales", "sales": "demo_sales", "demo_sales": "demo_sales",
        "membership": "membership_subscription", "subscription": "membership_subscription",
        "membership_subscription": "membership_subscription",
    }
    return aliases.get(value, value)


def _text_surfaces(data: Mapping[str, Any]) -> Dict[str, str]:
    title = str(data.get("title") or "")
    meta = str(data.get("meta_description") or "")
    h1 = " ".join(str(x) for x in (data.get("h1_tags") or []) if x)
    page = str(data.get("page_text") or "")[:26000]
    journey = str(data.get("journey_text_sample") or "")[:22000]
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
            # Hero/title language is more deliberate than incidental body copy.
            if phrase in surfaces["hero"]:
                scores[model] += weight * 1.8
                signals[model].append(f"hero:{phrase}")
            elif phrase in surfaces["meta"]:
                scores[model] += weight * 1.35
                signals[model].append(f"meta:{phrase}")
            elif phrase in surfaces["body"]:
                scores[model] += weight
                signals[model].append(phrase)


def _phrase_hits(text: str, terms: Iterable[str]) -> List[str]:
    """Return boundary-aware phrase matches in deterministic order.

    Context tagging must not fire because a token merely appears inside another word
    (for example ``book`` inside ``facebook``) or because generic policy boilerplate
    contains words such as ``event`` / ``reserve``.  This helper is deliberately
    conservative and context-specific callers add their own corroboration rules.
    """
    haystack = str(text or "").lower()
    hits: List[str] = []
    for raw in terms:
        term = str(raw or "").strip().lower()
        if not term:
            continue
        pattern = r"(?<![a-z0-9])" + re.escape(term).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        if re.search(pattern, haystack, re.I):
            hits.append(term)
    return hits


def infer_context_tags(data: Mapping[str, Any], journey_model: str = "general") -> Tuple[List[str], Dict[str, List[str]]]:
    surfaces = _text_surfaces(data)
    text = surfaces["all"]
    hero_meta = f"{surfaces['hero']} {surfaces['meta']}"
    # ``journey_text_sample`` is intended to contain customer-path/proof pages, not policy boilerplate.
    # Older callers may not provide it, so body remains a fallback but receives stricter thresholds.
    journey_text = str(data.get("journey_text_sample") or "").lower()
    body_text = surfaces["body"]
    tags: List[str] = []
    reasons: Dict[str, List[str]] = {}

    def mark(tag: str, why: Iterable[str]) -> None:
        vals = list(dict.fromkeys(str(x) for x in why if x))
        if vals:
            tags.append(tag)
            reasons[tag] = vals[:8]

    regulated_hits = _phrase_hits(text, REGULATED_TERMS)
    mark("regulated_high_trust", regulated_hits)

    # A city name in the footer/title does not by itself make an online/enterprise site location-dependent.
    # Strong structural location evidence always counts; geographic text only counts for journeys where
    # visiting/calling a local provider is naturally part of the customer path.
    geographic_terms = {"vancouver", "burnaby", "surrey", "richmond", "north vancouver", "west vancouver", "coquitlam", "new westminster"}
    structural_local_terms = {"service area", "directions", "visit us", "our location", "locations"}
    local_hits: List[str] = []
    if data.get("address_location_visible") is True:
        local_hits.append("verified address/location")
    if data.get("places_found") and str(data.get("places_confidence") or "") == "high":
        local_hits.append("verified Google Place identity")
    local_hits.extend(_phrase_hits(text, structural_local_terms))
    if journey_model in {"lead_quote", "appointment_consultation", "reservation_event"}:
        if data.get("phone_number_visible") is True:
            local_hits.append("verified local phone path")
        local_hits.extend(_phrase_hits(text, geographic_terms))
    mark("local_location_dependent", local_hits)

    commerce_hits: List[str] = []
    if data.get("add_to_cart_visible"):
        commerce_hits.append("add-to-cart")
    if data.get("checkout_context_detected"):
        commerce_hits.append("checkout")
    if data.get("shipping_info_linked") or data.get("return_policy_linked"):
        commerce_hits.append("shipping/return policy")
    if journey_model == "direct_purchase":
        commerce_hits.append("direct-purchase journey")
    mark("commerce_payment", commerce_hits)

    # Sensitive-data context is about information a customer may actually submit, not words that
    # happen to appear in a privacy policy, legal disclaimer, project description or footer.
    sensitive_hits: List[str] = []
    forms_present = bool(data.get("forms_present"))
    if regulated_hits and forms_present:
        sensitive_hits.append("regulated-context form")
        strong_source = f"{hero_meta} {journey_text}" if journey_text else hero_meta
        sensitive_hits.extend(_phrase_hits(strong_source, SENSITIVE_TERMS))
    elif data.get("checkout_context_detected") and journey_model == "direct_purchase":
        sensitive_hits.append("verified checkout/payment context")
    elif forms_present:
        strong_source = f"{hero_meta} {journey_text}" if journey_text else hero_meta
        explicit_sensitive = _phrase_hits(strong_source, SENSITIVE_TERMS)
        # Outside a regulated/checkout journey require corroboration; one incidental phrase is not enough.
        if len(explicit_sensitive) >= 2:
            sensitive_hits.extend(explicit_sensitive)
    mark("sensitive_data", sensitive_hits)

    # Considered-purchase/enterprise context should come from deliberate page/journey language rather
    # than policy boilerplate. A strong hero/meta hit is enough; body-only evidence needs corroboration.
    enterprise_primary = _phrase_hits(hero_meta, ENTERPRISE_TERMS)
    enterprise_journey = _phrase_hits(journey_text, ENTERPRISE_TERMS) if journey_text else []
    enterprise_body = _phrase_hits(body_text, ENTERPRISE_TERMS)
    enterprise_hits: List[str] = list(enterprise_primary)
    if enterprise_journey:
        enterprise_hits.extend(enterprise_journey)
    elif len(enterprise_body) >= 2:
        enterprise_hits.extend(enterprise_body[:4])
    if journey_model == "demo_sales":
        enterprise_hits.append("demo/sales journey")
    mark("enterprise_considered_purchase", enterprise_hits)

    # ``event`` and ``reserve`` are common legal/privacy boilerplate ("in the event...", "we reserve...").
    # They can never create hospitality/event context on their own. Strong domain terms or an actual
    # reservation journey are required.
    strong_hospitality = ("wedding", "venue", "cruise", "charter", "yacht", "restaurant", "catering", "hotel", "banquet")
    weak_hospitality = ("event", "tour", "reservation", "reserve", "rental")
    hospitality_hits: List[str] = []
    if journey_model == "reservation_event":
        hospitality_hits.append("reservation/event journey")
    hero_strong = _phrase_hits(hero_meta, strong_hospitality)
    journey_strong = _phrase_hits(journey_text, strong_hospitality) if journey_text else []
    journey_weak = _phrase_hits(journey_text, weak_hospitality) if journey_text else []
    body_strong = _phrase_hits(body_text, strong_hospitality)
    body_weak = _phrase_hits(body_text, weak_hospitality)
    if hero_strong:
        hospitality_hits.extend(hero_strong)
    elif journey_strong and (len(journey_strong) >= 2 or journey_weak or data.get("reservation_present")):
        hospitality_hits.extend(journey_strong + journey_weak[:2])
    elif len(body_strong) >= 2 or (body_strong and body_weak and (data.get("reservation_present") or journey_model == "general")):
        hospitality_hits.extend(body_strong[:3] + body_weak[:2])
    mark("hospitality_event", hospitality_hits)

    # Keep deterministic order for reports/diffs.
    ordered = [tag for tag in CONTEXT_LABELS if tag in tags]
    return ordered, reasons


def infer_architecture_profile(data: Mapping[str, Any], requested_hint: Any = "auto") -> Dict[str, Any]:
    """Infer customer-journey model and context tags from public evidence.

    This is intentionally not an industry classifier.  The optional legacy business type is a weak
    tie-breaker only and cannot outweigh strong customer-action/hero evidence.
    """
    surfaces = _text_surfaces(data)
    scores: Dict[str, float] = {model: 0.0 for model in JOURNEY_LABELS if model != "general"}
    signals: Dict[str, List[str]] = {model: [] for model in scores}
    _add_phrase_scores(scores, signals, surfaces)

    actions = {str(x).lower() for x in (data.get("mobile_cta_types") or []) if x}
    action_weights: Dict[str, Tuple[str, float]] = {
        "quote": ("lead_quote", 9.0), "contact": ("lead_quote", 4.0),
        "reserve": ("reservation_event", 9.0), "order": ("direct_purchase", 7.0),
        "add_to_cart": ("direct_purchase", 12.0), "buy": ("direct_purchase", 10.0),
        "demo": ("demo_sales", 10.0), "trial": ("demo_sales", 9.0),
        "subscribe": ("membership_subscription", 10.0), "join": ("membership_subscription", 10.0),
    }
    for action, (model, weight) in action_weights.items():
        if action in actions:
            scores[model] += weight
            signals[model].append(f"action:{action}")
    if "book" in actions:
        # Book alone is ambiguous; strong surrounding terms decide whether it is appointment vs event.
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

    hint = _normalize_hint(requested_hint)
    if hint in scores:
        # A direct V7 journey selection is an operator/user hint strong enough to resolve a close
        # ambiguity, but it cannot manufacture high confidence by itself. Unsupported manual
        # selections therefore remain provisional and are score-capped.
        scores[hint] += 6.0
        signals[hint].append(f"direct_journey_hint:{hint}")
    else:
        hinted_model = LEGACY_HINT_TO_JOURNEY.get(hint)
        if hint not in {"auto", "general"} and hinted_model and hinted_model in scores:
            # Old industry values remain intentionally weak for backward compatibility.
            scores[hinted_model] += 1.5
            signals[hinted_model].append(f"legacy_journey_hint:{hint}")

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_model, top_score = ranked[0] if ranked else ("general", 0.0)
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = max(0.0, top_score - second_score)

    if top_score < 5.0:
        journey_model = "general"
        confidence = 0.45 if top_score <= 0 else min(0.64, 0.48 + top_score * 0.025)
        winning_signals: List[str] = []
    else:
        # Absolute evidence and separation both matter.  This avoids confident misclassification from
        # many weak incidental words such as menu/food while rewarding a strong hero/action signal.
        confidence = 0.52 + min(0.26, top_score * 0.012) + min(0.20, margin * 0.025)
        confidence = max(0.52, min(0.98, confidence))
        journey_model = top_model
        winning_signals = list(dict.fromkeys(signals[top_model]))[:12]

    context_tags, context_reasons = infer_context_tags(data, journey_model)
    provisional = bool(journey_model == "general" or confidence < 0.75)
    secondary = JOURNEY_SECONDARY_CONVERSIONS.get(journey_model, JOURNEY_SECONDARY_CONVERSIONS["general"])
    return {
        "model_basis": "journey_context_v1",
        "journey_model": journey_model,
        "journey_label": JOURNEY_LABELS.get(journey_model, JOURNEY_LABELS["general"]),
        "confidence": round(confidence, 2),
        "provisional": provisional,
        "primary_conversion": JOURNEY_PRIMARY_CONVERSION.get(journey_model, JOURNEY_PRIMARY_CONVERSION["general"]),
        "secondary_conversions": list(secondary),
        "context_tags": context_tags,
        "context_labels": [CONTEXT_LABELS[tag] for tag in context_tags],
        "journey_signals": winning_signals,
        "context_reasons": context_reasons,
        "requested_journey_hint": hint,
        "direct_journey_hint": hint if hint in scores else "",
        "legacy_business_hint": hint if hint not in scores else "",
        "legacy_hint_used_only_as_tiebreaker": bool(hint not in {"auto", "general"} and hint not in scores),
        "score_candidates": {k: round(v, 2) for k, v in ranked},
        # Legacy keys retained so older report/frontend code does not break.  They now describe
        # journey architecture rather than an asserted industry taxonomy.
        "vertical": journey_model,
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
    return str(profile.get("journey_model") or profile.get("vertical") or "general") in set(models)
