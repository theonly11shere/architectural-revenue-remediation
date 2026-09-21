"""Trilloka V7.7 Commercial Evidence Architecture (TCEA).

Deterministic commercial reasoning layer. It does NOT create checkpoint PASS/FAIL,
submit forms, infer actual revenue, or let research substitute for current-site evidence.
It compiles business context + capabilities + subtype hints into a Commercial Contract,
then describes Commercial Minimums, revenue decision points and leak classes for routing,
causal validation, report explanation and score prioritisation.
"""
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Mapping, Sequence

TCEA_VERSION = "v7.7-commercial-evidence-architecture-v1"

LEAK_CLASSES = (
    "acquisition", "understanding", "evaluation", "trust", "friction",
    "continuity", "completion", "expectation", "reliability", "measurement",
)
DECISION_POINTS = ("entry", "understanding", "evaluation", "trust", "commitment", "completion")

# Minimum tiers: REQUIRED = path cannot credibly work without it; EXPECTED = normally material
# when applicable; ENHANCER = useful but absence alone must never create a scored failure.
def _c(outcome, minimums, paths, leaks):
    return {"economic_outcome": outcome, "commercial_minimums": minimums,
            "likely_paths": paths, "priority_leak_classes": leaks}

def _m(key, label, tier, decision, leak, surfaces, mechanism):
    return {"key": key, "label": label, "tier": tier, "decision_point": decision,
            "leak_class": leak, "inspect_surfaces": list(surfaces), "causal_mechanism": mechanism}

COMMERCIAL_CONTRACTS: Dict[str, Dict[str, Any]] = {
"ecommerce": _c("product sale", [
 _m("offer_clarity","Product/offer clarity","REQUIRED","understanding","understanding",("product","category"),"Customers cannot confidently progress when the product, fit or value is unclear."),
 _m("price_cost","Price and material cost expectations","REQUIRED","evaluation","expectation",("product","cart","checkout"),"Unclear or late cost information can create uncertainty at commitment."),
 _m("purchase_action","Usable purchase action","REQUIRED","commitment","continuity",("product","cart"),"A customer needs a clear path from product choice toward purchase."),
 _m("fulfilment","Delivery/fulfilment expectations when applicable","EXPECTED","evaluation","expectation",("product","shipping/delivery","cart"),"Missing fulfilment expectations can delay or interrupt a purchase decision."),
 _m("returns","Returns/cancellation expectations when applicable","EXPECTED","trust","trust",("returns","product","policies"),"Risk-reduction information can matter before purchase."),
 _m("checkout","Checkout/payment continuity","REQUIRED","completion","completion",("cart","checkout"),"A broken or materially obstructed checkout directly blocks completion."),
], ("direct_purchase",), ("evaluation","expectation","trust","friction","continuity","completion","reliability")),
"marketplace": _c("transaction, lead or platform fee", [
 _m("inventory_match","Discoverable relevant listings/providers","REQUIRED","understanding","understanding",("listing/search","provider/seller profile"),"Customers need to find a suitable counterpart or item."),
 _m("listing_detail","Decision-quality listing/provider detail","REQUIRED","evaluation","evaluation",("listing/search","provider/seller profile"),"Insufficient detail weakens comparison and fit decisions."),
 _m("fees_terms","Material fees/transaction expectations","EXPECTED","evaluation","expectation",("fees","transaction/contact"),"Unexpected fees or terms can create late-stage abandonment."),
 _m("market_trust","Seller/provider identity and protection where applicable","EXPECTED","trust","trust",("provider/seller profile","trust/safety"),"Marketplace transactions require confidence in counterparties and platform protections."),
 _m("transaction_path","Usable transaction/contact/booking path","REQUIRED","completion","completion",("transaction/contact","listing/search"),"The marketplace cannot create value if users cannot progress to the intended transaction."),
], ("direct_purchase","lead_quote","reservation_event","membership_subscription"), ("understanding","evaluation","trust","friction","continuity","completion","expectation")),
"local_service": _c("service lead, booking or job", [
 _m("service_fit","Service and problem-fit clarity","REQUIRED","understanding","understanding",("service","service area/location"),"Visitors must know whether the business solves their need."),
 _m("coverage","Service area/location clarity","EXPECTED","evaluation","expectation",("service area/location","contact"),"Local customers need to know whether service is available to them."),
 _m("local_trust","Local identity/proof","EXPECTED","trust","trust",("reviews","service area/location","about"),"Local service decisions commonly depend on identity and proof."),
 _m("lead_path","Usable quote/contact/booking path","REQUIRED","completion","completion",("quote/contact","booking"),"A service business loses web opportunity when an interested visitor cannot make contact or request service."),
], ("lead_quote","appointment_consultation"), ("acquisition","understanding","trust","friction","continuity","completion","expectation")),
"professional_service": _c("qualified client enquiry", [
 _m("expertise_fit","Expertise/service fit","REQUIRED","understanding","understanding",("service/expertise","industries"),"Prospects must understand whether the firm is relevant to their problem."),
 _m("professional_identity","Professional/team identity","EXPECTED","trust","trust",("team","about"),"Considered services require confidence in who will deliver the work."),
 _m("proof_process","Proof and engagement/process expectations","EXPECTED","evaluation","evaluation",("proof","process","pricing"),"Evidence and process clarity reduce uncertainty in considered purchases."),
 _m("qualified_enquiry","Qualified enquiry/consultation path","REQUIRED","completion","completion",("consultation/contact","process"),"A qualified prospect needs a clear next step."),
], ("lead_quote","appointment_consultation"), ("understanding","evaluation","trust","expectation","friction","completion")),
"healthcare": _c("patient appointment or care enquiry", [
 _m("care_fit","Treatment/service fit","REQUIRED","understanding","understanding",("service/treatment","patient information"),"Patients need to determine whether the service addresses their need."),
 _m("provider_trust","Provider identity and relevant credentials","EXPECTED","trust","trust",("provider","team"),"Provider identity and qualifications reduce risk in high-trust care decisions."),
 _m("access_expectations","Location and fee/insurance expectations when applicable","EXPECTED","evaluation","expectation",("location","insurance/payment"),"Access and cost uncertainty can prevent appointment commitment."),
 _m("appointment_path","Usable appointment/contact path","REQUIRED","completion","completion",("appointment","contact"),"A patient must be able to progress toward care."),
 _m("sensitive_privacy","Privacy signal where sensitive data is collected","EXPECTED","trust","trust",("privacy","appointment"),"Sensitive-data collection raises trust and policy expectations."),
], ("appointment_consultation","lead_quote"), ("understanding","trust","expectation","friction","continuity","completion","reliability")),
"medspa": _c("consultation, treatment booking or product sale", [
 _m("treatment_fit","Treatment and candidate-fit clarity","REQUIRED","understanding","understanding",("treatment","eligibility"),"Customers need to understand treatment purpose and fit."),
 _m("practitioner_trust","Practitioner identity/qualifications and safety context","EXPECTED","trust","trust",("practitioner","technology","privacy"),"High-trust aesthetic decisions depend on practitioner and safety confidence."),
 _m("results_expectations","Credible proof/results and expectation setting","EXPECTED","evaluation","evaluation",("before/after or reviews","results/proof"),"Customers need realistic evidence to evaluate a discretionary treatment."),
 _m("price_booking","Price expectations and usable consultation/booking","REQUIRED","commitment","completion",("pricing/packages","consultation/booking"),"Unclear commercial expectations or a broken booking path can interrupt commitment."),
], ("appointment_consultation","direct_purchase"), ("understanding","evaluation","trust","expectation","friction","completion")),
"legal": _c("qualified client intake", [
 _m("matter_fit","Practice-area/matter fit","REQUIRED","understanding","understanding",("practice area","services"),"Prospective clients must know whether the firm handles their matter."),
 _m("lawyer_trust","Lawyer/team identity and credible proof","EXPECTED","trust","trust",("lawyer/team","proof"),"High-stakes legal decisions require identity and credibility."),
 _m("engagement_expectations","Process and fee expectations where appropriate","EXPECTED","evaluation","expectation",("fees/process","consultation/intake"),"Unclear engagement expectations can inhibit contact."),
 _m("intake","Usable consultation/intake path","REQUIRED","completion","completion",("consultation/intake","contact"),"An interested client needs a reliable route to initiate the relationship."),
 _m("privacy","Privacy where confidential information is collected","EXPECTED","trust","trust",("privacy","consultation/intake"),"Intake can involve sensitive information and therefore requires trust."),
], ("appointment_consultation","lead_quote"), ("understanding","trust","expectation","friction","continuity","completion")),
"financial_services": _c("application, consultation or financial-service lead", [
 _m("product_fit","Product/service fit and material terms","REQUIRED","understanding","understanding",("product/service","rates/fees"),"Customers need to understand the financial offer before progressing."),
 _m("advisor_identity","Advisor/company identity and trust/security","EXPECTED","trust","trust",("advisor","security/privacy"),"Financial decisions carry elevated trust and security expectations."),
 _m("cost_eligibility","Rates/fees/eligibility where applicable","EXPECTED","evaluation","expectation",("rates/fees","application"),"Cost or eligibility uncertainty can interrupt application intent."),
 _m("financial_path","Usable application/consultation path","REQUIRED","completion","completion",("application","consultation/contact"),"The site must allow a qualified customer to progress to the intended financial action."),
], ("application_enrollment","appointment_consultation","lead_quote"), ("understanding","evaluation","trust","expectation","friction","completion","reliability")),
"real_estate": _c("property lead, showing or registration", [
 _m("inventory_detail","Relevant listing/project detail","REQUIRED","evaluation","evaluation",("listing","property detail","projects"),"Property decisions require sufficient inventory and property detail."),
 _m("visual_location","Visual and location context","EXPECTED","evaluation","evaluation",("property detail","location","gallery"),"Location and visual evidence are core evaluation inputs."),
 _m("agent_identity","Agent/developer identity and proof","EXPECTED","trust","trust",("agent","about"),"Customers need confidence in the party handling a high-value transaction."),
 _m("showing_lead","Usable showing/contact/register path","REQUIRED","completion","completion",("showing/open house","financing/contact","register/contact"),"Interested buyers/renters need a direct progression path."),
], ("lead_quote","appointment_consultation","application_enrollment"), ("understanding","evaluation","trust","friction","continuity","completion","expectation")),
"restaurant": _c("visit, order, reservation or event lead", [
 _m("menu_offer","Menu/offer and material price clarity","REQUIRED","evaluation","evaluation",("menu","order"),"Customers need enough offer information to decide whether to visit or order."),
 _m("visit_info","Hours/location when a physical visit is offered","EXPECTED","commitment","expectation",("hours/location","directions"),"Missing visit logistics can stop a local customer from acting."),
 _m("offered_path","Usable order/reservation path when the site offers it","REQUIRED","completion","completion",("order","reservation"),"An advertised commercial action that cannot be completed creates direct path leakage."),
 _m("reputation","Relevant reputation/proof","ENHANCER","trust","trust",("reviews","gallery/contact"),"Proof can reduce uncertainty, but its absence alone is not a failure."),
], ("local_visit","direct_purchase","reservation_event","lead_quote"), ("evaluation","trust","expectation","friction","continuity","completion","reliability")),
"hospitality_event": _c("booking, reservation or event enquiry", [
 _m("offer_fit","Room/venue/experience clarity","REQUIRED","understanding","understanding",("offer/rooms/venue","gallery/reviews"),"Guests must understand the experience and fit."),
 _m("availability_rate","Availability and material rate expectations","REQUIRED","evaluation","expectation",("availability","rates"),"Availability and price are central booking decisions."),
 _m("booking_path","Usable booking/enquiry continuity","REQUIRED","completion","completion",("booking","availability"),"A broken booking path directly interrupts conversion."),
 _m("cancellation","Cancellation/terms where a booking is offered","EXPECTED","trust","expectation",("cancellation","booking"),"Material booking terms reduce risk and late-stage uncertainty."),
], ("reservation_event","direct_purchase","lead_quote"), ("understanding","evaluation","expectation","trust","friction","continuity","completion")),
"saas": _c("trial, subscription or qualified sales opportunity", [
 _m("product_value","Product/value/use-case clarity","REQUIRED","understanding","understanding",("product","use cases"),"Buyers must understand the problem solved and fit."),
 _m("commercial_model","Pricing/commercial expectations where appropriate","EXPECTED","evaluation","expectation",("pricing","product"),"Commercial ambiguity can block self-serve or considered evaluation."),
 _m("proof_security","Proof and security appropriate to buyer risk","EXPECTED","trust","trust",("customers/proof","security/integrations"),"Considered software purchases require confidence in outcomes and risk."),
 _m("trial_demo","Usable trial/demo/signup path when offered","REQUIRED","completion","completion",("demo/trial","pricing"),"A qualified buyer must be able to progress to trial, signup or sales."),
], ("demo_sales","membership_subscription","direct_purchase"), ("understanding","evaluation","trust","expectation","friction","continuity","completion")),
"b2b": _c("qualified RFQ, sales lead or procurement opportunity", [
 _m("capability_fit","Capability/product/service fit","REQUIRED","understanding","understanding",("capabilities","products/services","industries"),"Business buyers first need to establish supplier fit."),
 _m("specification","Decision/procurement specifications where applicable","EXPECTED","evaluation","evaluation",("specifications","products/services"),"Missing technical/commercial detail can prevent supplier shortlisting."),
 _m("b2b_proof","Proof/certifications appropriate to purchase risk","EXPECTED","trust","trust",("proof/certifications","case studies"),"B2B buyers need evidence that the supplier can deliver."),
 _m("rfq_sales","Usable RFQ/qualified-sales path","REQUIRED","completion","completion",("pricing/RFQ","contact"),"A qualified buyer needs a clear procurement or sales next step."),
], ("lead_quote","demo_sales","direct_purchase"), ("understanding","evaluation","trust","expectation","friction","continuity","completion")),
"agency": _c("qualified project enquiry", [
 _m("specialization","Service/specialization clarity","REQUIRED","understanding","understanding",("services","process"),"Prospects need to know whether the agency fits their problem."),
 _m("work_proof","Relevant work/results proof","EXPECTED","evaluation","evaluation",("work/portfolio","case studies"),"Agency selection is evidence-heavy and proof reduces uncertainty."),
 _m("team_process","Team/process/engagement expectations","EXPECTED","trust","trust",("team","process","pricing/contact"),"Prospects need confidence in who and how the work will be delivered."),
 _m("agency_contact","Usable discovery/project enquiry","REQUIRED","completion","completion",("pricing/contact","services"),"A qualified prospect needs a clear project-start path."),
], ("lead_quote","demo_sales","appointment_consultation"), ("understanding","evaluation","trust","expectation","friction","completion")),
"membership_creator": _c("subscription, membership or content purchase", [
 _m("member_value","Membership/content value and access clarity","REQUIRED","understanding","understanding",("offer/benefits","trial/sample"),"Prospects need to understand what access they receive."),
 _m("billing_terms","Price/billing/renewal expectations","REQUIRED","evaluation","expectation",("pricing","billing/cancellation"),"Recurring commitments require clear commercial expectations."),
 _m("member_proof","Proof/sample/community signal","EXPECTED","trust","trust",("community/proof","trial/sample"),"Proof or sampling can reduce uncertainty before recurring commitment."),
 _m("join_path","Usable join/subscribe path","REQUIRED","completion","completion",("join/subscribe","pricing"),"The membership cannot create value if signup cannot be completed."),
], ("membership_subscription","direct_purchase"), ("understanding","evaluation","trust","expectation","friction","continuity","completion")),
"education": _c("application, enrollment or course sale", [
 _m("program_fit","Program/course fit and outcomes","REQUIRED","understanding","understanding",("program/course","outcomes"),"Prospective students need to understand program fit and intended outcome."),
 _m("cost_requirements","Tuition/fees and requirements where applicable","EXPECTED","evaluation","expectation",("tuition/fees","requirements"),"Cost and eligibility uncertainty can stop application intent."),
 _m("deadlines_process","Application process/deadlines where applicable","EXPECTED","commitment","expectation",("apply/enroll","requirements"),"Process uncertainty can cause avoidable abandonment."),
 _m("application_path","Usable application/enrollment/contact path","REQUIRED","completion","completion",("apply/enroll","advisor/contact"),"A qualified learner needs a reliable route to apply or enroll."),
], ("application_enrollment","lead_quote","direct_purchase"), ("understanding","evaluation","expectation","trust","friction","continuity","completion")),
"nonprofit": _c("donation, membership, volunteer or program support", [
 _m("mission_impact","Mission/program/impact clarity","REQUIRED","understanding","understanding",("mission/impact","programs"),"Supporters need to understand what the organization does and why support matters."),
 _m("nonprofit_trust","Organization identity/transparency appropriate to solicitation","EXPECTED","trust","trust",("financials/trust","mission/impact"),"Donors need confidence that the organization and use of support are credible."),
 _m("donation_path","Usable donation path when donations are solicited","REQUIRED","completion","completion",("donation","payment"),"A solicitation that cannot be completed creates direct support leakage."),
 _m("giving_expectations","Giving amount/frequency/payment expectations when applicable","EXPECTED","commitment","expectation",("donation","payment"),"Clear giving choices reduce uncertainty at commitment."),
], ("donation_support","membership_subscription","lead_quote"), ("understanding","trust","expectation","friction","continuity","completion","reliability")),
"automotive": _c("vehicle sale, service booking or qualified lead", [
 _m("inventory_service_fit","Inventory/service fit","REQUIRED","understanding","understanding",("inventory/service","vehicle/service detail"),"Customers need to determine whether the vehicle or service matches their need."),
 _m("price_finance","Price/finance expectations where applicable","EXPECTED","evaluation","expectation",("pricing/financing","vehicle/service detail"),"High-value automotive decisions depend on commercial expectations."),
 _m("auto_trust","Dealer/service identity, reputation and location","EXPECTED","trust","trust",("reviews","location/contact"),"Local high-value transactions depend on identity and reputation."),
 _m("auto_action","Usable contact/test-drive/service-booking path","REQUIRED","completion","completion",("booking/test drive","location/contact"),"Interested customers need a direct route to the next commercial action."),
], ("lead_quote","appointment_consultation","direct_purchase","reservation_event"), ("understanding","evaluation","trust","expectation","friction","continuity","completion")),
"general": _c("unresolved website value action", [
 _m("identity","Business identity/offer clarity","REQUIRED","understanding","understanding",("home","about"),"The scanner needs enough evidence to understand the offer before applying business-specific expectations."),
 _m("dominant_action","Dominant customer action","EXPECTED","commitment","continuity",("primary navigation","prominent customer actions"),"A visible next step helps resolve the commercial path, but absence is not scored while the model is unresolved."),
], ("general",), ("understanding","trust","continuity","reliability")),
}

# Rule/family vocabulary -> causal leak class. Unknown rules remain 'reliability' for
# technical foundation or 'evaluation' for adaptive findings; this is explanatory/ranking metadata.
RULE_LEAK_CLASS = {
 "unsecured_ssl":"trust", "https_redirect":"reliability", "core_web_vitals":"reliability",
 "mobile_lab_performance":"reliability", "pagespeed_below_60":"reliability", "pagespeed_below_90":"reliability",
 "lcp_poor":"reliability", "inp_poor":"friction", "cls_poor":"friction", "tap_target_friction":"friction",
 "primary_conversion_path":"completion", "form_architecture":"completion", "unlinked_form_structure":"completion",
 "click_to_call":"continuity", "mobile_sticky_cta":"continuity", "privacy_terms_missing":"trust",
 "reviews_missing":"trust", "case_studies_missing":"trust", "structured_data_missing":"acquisition",
 "meta_description_missing":"acquisition", "seo_score_below_80":"acquisition", "sitemap_missing":"acquisition",
 "robots_missing":"acquisition", "measurement_layer":"measurement", "retargeting_telemetry":"measurement",
 "faq_missing":"evaluation", "generic_headline":"understanding", "thin_visible_content":"understanding",
}

def normalize_business_type(value: Any) -> str:
    key = str(value or "general").strip().lower().replace("-","_").replace(" ","_")
    return key if key in COMMERCIAL_CONTRACTS else "general"

def build_commercial_contract(business_type: Any, subtype: Any = "", subtype_focus: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    b = normalize_business_type(business_type)
    base = COMMERCIAL_CONTRACTS[b]
    modifier = {}
    if subtype_focus:
        modifier = {"surfaces": list(subtype_focus.get("surfaces") or []),
                    "priorities": list(subtype_focus.get("priorities") or []),
                    "paths": list(subtype_focus.get("paths") or [])}
    return {"version": TCEA_VERSION, "business_type": b, "business_subtype": str(subtype or "unresolved"),
            "economic_outcome": base["economic_outcome"], "commercial_minimums": [dict(x) for x in base["commercial_minimums"]],
            "likely_paths": list(base["likely_paths"]), "priority_leak_classes": list(base["priority_leak_classes"]),
            "subtype_modifier": modifier,
            "policy": "Business context defines commercially reasonable minimums; subtype only modifies inspection priority. Site evidence proves conditions; research only supports commercial relevance."}

def classify_leak(rule_key: Any, category: Any = "", analysis_layer: Any = "") -> str:
    rule = str(rule_key or "")
    if rule in RULE_LEAK_CLASS: return RULE_LEAK_CLASS[rule]
    cat = str(category or "")
    if cat == "measurement": return "measurement"
    if str(analysis_layer or "") == "common_foundation" or cat == "seo_technical": return "reliability"
    if cat == "trust_conversion": return "continuity"
    if cat == "content_eeat": return "trust"
    return "evaluation"

def decision_point_for_leak(leak_class: str) -> str:
    return {"acquisition":"entry","understanding":"understanding","evaluation":"evaluation","trust":"trust",
            "expectation":"evaluation","friction":"commitment","continuity":"commitment","completion":"completion",
            "reliability":"commitment","measurement":"completion"}.get(leak_class,"evaluation")

def commercial_priority_metadata(leak: Mapping[str, Any], contract: Mapping[str, Any], journey_model: str) -> Dict[str, Any]:
    lc = classify_leak(leak.get("rule_key"), leak.get("category"), leak.get("analysis_layer"))
    decision = decision_point_for_leak(lc)
    evidence = str(leak.get("confidence") or "unknown").lower()
    evidence_strength = {"unknown":0,"low":2,"medium":4,"high":5}.get(evidence,2)
    path_importance = 3 if journey_model and journey_model != "general" else 1
    proximity = {"entry":1,"understanding":2,"evaluation":3,"trust":3,"commitment":4,"completion":5}[decision]
    severity_raw = float(leak.get("severity_factor") or 0.0)
    severity = 1 if severity_raw <= .2 else 2 if severity_raw <= .4 else 3 if severity_raw <= .65 else 4 if severity_raw < .9 else 5
    relevant = lc in set(contract.get("priority_leak_classes") or [])
    commercial_relevance = 5 if relevant else (2 if str(leak.get("analysis_layer")) == "common_foundation" else 3)
    # Bounded 0-100 prioritisation index. It ranks verified findings; it does not claim probability or revenue loss.
    idx = round(100.0 * (0.25*evidence_strength/5 + 0.18*path_importance/3 + 0.18*proximity/5 + 0.21*severity/5 + 0.18*commercial_relevance/5), 1)
    cap = "LOW" if evidence_strength <= 1 else "MEDIUM" if evidence_strength <= 3 else "HIGH"
    return {"leak_class": lc, "decision_point": decision, "evidence_strength": evidence_strength,
            "path_importance": path_importance, "decision_point_proximity": proximity, "failure_severity": severity,
            "commercial_relevance": commercial_relevance, "commercial_leak_priority_index": idx,
            "evidence_priority_cap": cap,
            "causal_questions": ["WHAT IS WRONG?","WHERE IS IT?","WHO DOES IT AFFECT?","AT WHAT DECISION POINT?","WHY COULD THIS REDUCE CONVERSION?","WHAT SITE/MEASUREMENT EVIDENCE PROVES THE CONDITION?","WHAT RESEARCH SUPPORTS THE COMMERCIAL RELEVANCE?"],
            "policy": "Priority ranks evidence-supported website readiness findings; it is not measured financial loss or conversion probability."}

def commercial_minimum_gap_map(contract: Mapping[str, Any], inspected_surfaces: Iterable[str] = ()) -> List[Dict[str, Any]]:
    """Coverage-aware map only. Never manufactures a FAIL from absence.

    Minimums become eligible for absence testing only after their expected surfaces were inspected.
    Actual PASS/FAIL remains owned by existing checkpoint/site evidence.
    """
    inspected = " ".join(str(x).lower() for x in inspected_surfaces or [])
    out=[]
    for minimum in contract.get("commercial_minimums") or []:
        surfaces = list(minimum.get("inspect_surfaces") or [])
        covered = [s for s in surfaces if any(tok and tok in inspected for tok in str(s).lower().replace("/"," ").split())]
        out.append({**minimum, "coverage_status":"COVERED" if covered else "UNVERIFIED",
                    "covered_surfaces":covered, "gap_status":"EVALUATE_FROM_VERIFIED_EVIDENCE" if covered else "UNKNOWN",
                    "scoring_policy":"No deduction from this map alone. A scored gap requires an applicable verified checkpoint/finding plus sufficient coverage."})
    return out
