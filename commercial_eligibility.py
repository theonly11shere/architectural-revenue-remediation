"""Commercial eligibility gate for Trilloka Revenue Readiness.

Recognition of museums, public-information sites, government resources and similar sites is
retained so the scanner can *decline* an inappropriate commercial audit instead of fabricating
financial-readiness meaning. Mixed sites may continue when a real commercial path is visible.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Mapping

_INFO_TERMS = (
    "museum","archive","archives","encyclopedia","public information","government","ministry","department of",
    "historical society","heritage collection","digital collection","research library","knowledge base","documentation",
    "open data","public records","exhibition archive","reference library","educational resource","information portal",
)
_COMMERCIAL_TERMS = (
    "buy now","add to cart","checkout","shop","order online","book now","reserve","request a quote","get a quote",
    "pricing","plans","start trial","free trial","request demo","book a consultation","schedule appointment",
    "tickets","admission","membership","subscribe","apply now","enroll now","register now","financing",
)
_SUPPORT_TERMS = ("donate","donation","support us","become a member","membership","gift shop","tickets","admission")


def _text(scan: Mapping[str, Any]) -> str:
    return " ".join([
        str(scan.get("title") or ""), str(scan.get("meta_description") or ""),
        " ".join(str(x) for x in (scan.get("h1_tags") or [])[:5]),
        str(scan.get("page_text") or "")[:18000], str(scan.get("journey_text_sample") or "")[:18000],
    ]).lower()


def evaluate_commercial_eligibility(scan: Mapping[str, Any], profile: Mapping[str, Any], requested_business_type: str = "auto") -> Dict[str, Any]:
    text = _text(scan)
    info_hits = [term for term in _INFO_TERMS if term in text]
    commercial_hits = [term for term in _COMMERCIAL_TERMS if term in text]
    support_hits = [term for term in _SUPPORT_TERMS if term in text]
    structural = []
    for key in (
        "add_to_cart_visible","checkout_context_detected","reservation_present","order_online_present",
        "mobile_primary_cta_present","form_present","pricing_signal_present",
    ):
        if scan.get(key) is True:
            structural.append(key)
    url = str(scan.get("final_url") or scan.get("url") or "").lower()
    gov_domain = bool(re.search(r"\.(?:gov|gc\.ca|gov\.uk|gouv\.fr)(?:/|$)", url))
    btype = str(profile.get("business_type") or "general")
    journey = str(profile.get("journey_model") or "general")
    explicit = str(requested_business_type or "auto").lower() not in {"", "auto"}

    # Do not treat a generic contact form / inferred lead path as enough to make an
    # informational site a commercial target. Lead/quote only counts strongly when the page
    # also exposes quote/service/pricing language. This prevents museums, archives and public
    # resources with a contact form from being commercially scored by accident.
    lead_quote_evidence = journey == "lead_quote" and any(term in text for term in (
        "request a quote", "get a quote", "estimate", "pricing", "services", "consultation", "proposal", "rfq"
    ))
    strong_commercial = bool(
        len(commercial_hits) >= 2
        or scan.get("add_to_cart_visible") is True
        or scan.get("checkout_context_detected") is True
        or journey in {"direct_purchase","appointment_consultation","reservation_event","demo_sales","membership_subscription","application_enrollment"}
        or lead_quote_evidence
    )
    informational = bool(gov_domain or len(info_hits) >= 2)
    nonprofit_like = btype == "nonprofit" or "registered charity" in text or "non-profit" in text or "nonprofit" in text

    if explicit:
        return {
            "status": "eligible_explicit",
            "allow_scan": True,
            "commercial_path_verified": strong_commercial,
            "informational_signals": info_hits[:8], "commercial_signals": commercial_hits[:8] + structural[:8],
            "reason": "The user explicitly selected a supported business category; Trilloka will audit the observable commercial path while keeping non-applicable checks gated.",
        }

    if gov_domain and not strong_commercial:
        status, allow = "not_commercial_target", False
        reason = "This appears to be a public/government information site without a sufficiently strong commercial customer journey for Revenue Readiness scoring."
    elif informational and not strong_commercial and not support_hits:
        status, allow = "not_commercial_target", False
        reason = "This appears primarily informational rather than designed to create a measurable commercial/revenue outcome."
    elif nonprofit_like and not strong_commercial:
        status, allow = "not_commercial_target", False
        reason = "This appears primarily nonprofit/public-support oriented rather than a core commercial Revenue Readiness target."
    elif (informational or nonprofit_like) and (strong_commercial or support_hits):
        status, allow = "mixed_commercial_path", True
        reason = "The organization is partly informational/public-purpose, but a measurable commercial or transaction path is visible; Trilloka will focus on that path rather than score informational content as revenue architecture."
    else:
        status, allow = "eligible", True
        reason = "A supported commercial/customer outcome is observable or the site does not show strong evidence of being purely informational."

    return {
        "status": status,
        "allow_scan": allow,
        "commercial_path_verified": strong_commercial,
        "business_type": btype,
        "journey_model": journey,
        "informational_signals": info_hits[:8],
        "commercial_signals": list(dict.fromkeys(commercial_hits[:10] + structural[:10] + support_hits[:6])),
        "reason": reason,
        "policy": "Eligibility decides whether Revenue Readiness is an appropriate product. It does not create website findings or score deductions.",
    }
