"""Trilloka V7.7 evidence-scoped customer-path marker engine.

Classification narrows what to inspect; it does not decide the journey. Journey resolution is
proof/sequence based, with terminal/progression evidence outranking semantic language and priors.
The module is additive and deterministic: it never creates checkpoint failures.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Mapping, Sequence, Tuple

# Subtype vocabularies intentionally use commercially discriminating language rather than generic words.
SUBTYPE_MARKERS: Dict[str, Dict[str, Tuple[str, ...]]] = {
 "restaurant": {"dine_in_restaurant":("dine in","table service","chef","dinner menu","lunch menu"),"cafe_bakery":("cafe","café","coffee","bakery","pastry","brunch"),"takeout_delivery":("takeout","take away","delivery","order online","pickup"),"catering_events":("catering","private dining","private event","banquet","event menu"),"bar_nightlife":("cocktail","bar menu","happy hour","wine list","taproom")},
 "ecommerce":{"retail_store":("shop","products","collection","add to cart","shipping"),"subscription_commerce":("subscribe and save","subscription box","recurring delivery"),"digital_goods":("digital download","download instantly","license key"),"wholesale":("wholesale","bulk order","case quantity","trade account")},
 "marketplace":{"product_marketplace":("sellers","vendors","list an item","buyer protection"),"service_marketplace":("providers","professionals","hire","request offers"),"booking_marketplace":("availability","hosts","guests","book a stay")},
 "local_service":{"home_trades":("plumber","electrician","roofing","hvac","renovation","contractor"),"cleaning_maintenance":("cleaning","janitorial","pressure washing","maintenance"),"moving_logistics":("moving","movers","junk removal","delivery service"),"repair_installation":("repair","installation","technician","service call"),"emergency_service":("24/7","emergency","same day","urgent service")},
 "professional_service":{"consulting":("consulting","consultant","advisory","strategy"),"accounting_tax":("accounting","accountant","bookkeeping","tax"),"engineering_architecture":("engineering","engineer","architect","design services"),"business_services":("business services","outsourcing","managed services")},
 "healthcare":{"medical_clinic":("medical clinic","physician","doctor","patient"),"dental":("dentist","dental","orthodont"),"physio_rehab":("physiotherapy","physical therapy","rehabilitation","chiropractic"),"mental_health":("psychologist","counselling","counseling","therapy"),"allied_health":("podiatry","occupational therapy","speech therapy","massage therapy")},
 "medspa":{"injectables":("botox","filler","injectable"),"laser_aesthetics":("laser","ipl","hair removal"),"skin_aesthetics":("facial","skin treatment","microneedling","peel"),"body_aesthetics":("body contour","sculpting","coolsculpt")},
 "legal":{"litigation":("litigation","lawsuit","dispute","trial"),"personal_injury":("personal injury","accident","injury claim"),"family_law":("family law","divorce","custody"),"immigration":("immigration","visa","citizenship"),"business_law":("corporate law","business law","commercial law"),"real_estate_law":("conveyancing","real estate law","property transaction")},
 "financial_services":{"financial_advisory":("financial advisor","wealth management","investment advisor"),"insurance":("insurance","coverage","policy quote"),"mortgage":("mortgage","pre-approval","refinance"),"accounting_finance":("tax planning","accounting","cpa"),"lending":("loan","financing","credit application")},
 "real_estate":{"residential_sales":("homes for sale","realtor","list your home","mls"),"property_management":("property management","tenant","landlord","rental management"),"rentals":("apartments for rent","rental listings","lease"),"commercial_real_estate":("commercial real estate","industrial property","office space"),"developer":("new development","pre-sale","presale","development project")},
 "hospitality_event":{"hotel_accommodation":("hotel","rooms","check-in","check out","guests"),"venue_events":("venue","wedding","banquet","private event"),"tour_activity":("tour","excursion","activity","tickets"),"rental_charter":("charter","rental","yacht","boat rental")},
 "saas":{"self_serve_saas":("start free","sign up free","create account","free plan"),"sales_led_saas":("request demo","contact sales","talk to sales"),"developer_platform":("api","developers","sdk","documentation"),"enterprise_software":("enterprise","security","solutions","case studies")},
 "b2b":{"manufacturer":("manufacturer","manufacturing","factory","oem"),"distributor_wholesaler":("distributor","wholesale","dealer network"),"industrial_service":("industrial service","field service","maintenance contract"),"enterprise_solution":("enterprise solution","procurement","implementation"),"supplier_rfq":("rfq","request for quote","part number","specification")},
 "agency":{"marketing_agency":("marketing agency","seo","paid media","campaign"),"creative_agency":("creative agency","branding","design studio"),"web_agency":("web design","website development","development agency"),"pr_communications":("public relations","pr agency","communications")},
 "membership_creator":{"creator_content":("creator","podcast","videos","exclusive content"),"community_membership":("community","members","membership"),"newsletter_publisher":("newsletter","publication","subscriber"),"association":("association","member benefits","chapter")},
 "education":{"school_college":("school","college","university","admissions"),"course_provider":("course","online course","certificate","curriculum"),"tutoring_training":("tutoring","training","workshop","class"),"bootcamp":("bootcamp","cohort","career program")},
 "nonprofit":{"charity":("charity","donate","tax receipt"),"advocacy_nonprofit":("advocacy","campaign","mission"),"community_nonprofit":("community organization","programs","volunteer"),"foundation":("foundation","grants","fund")},
 "automotive":{"dealer":("vehicles for sale","inventory","dealership","test drive"),"repair_service":("auto repair","mechanic","service appointment"),"parts_retail":("auto parts","parts store","add to cart"),"rental":("car rental","rent a car","pickup date")},
 "general":{"commercial_unknown":("contact","services","products","pricing")},
}

# Candidate journeys per broad type: routing only, never proof.
BUSINESS_JOURNEY_CANDIDATES: Dict[str, Tuple[str,...]] = {
 "restaurant":("local_visit","direct_purchase","reservation_event","lead_quote","appointment_consultation"), "ecommerce":("direct_purchase","membership_subscription","lead_quote"),
 "marketplace":("direct_purchase","membership_subscription","lead_quote","reservation_event"), "local_service":("lead_quote","appointment_consultation","direct_purchase"),
 "professional_service":("lead_quote","appointment_consultation","direct_purchase"), "healthcare":("appointment_consultation","lead_quote"), "medspa":("appointment_consultation","direct_purchase","membership_subscription"),
 "legal":("lead_quote","appointment_consultation"), "financial_services":("application_enrollment","appointment_consultation","lead_quote"), "real_estate":("lead_quote","appointment_consultation","application_enrollment"),
 "hospitality_event":("reservation_event","direct_purchase","lead_quote"), "saas":("demo_sales","membership_subscription","direct_purchase"), "b2b":("lead_quote","demo_sales","direct_purchase"),
 "agency":("lead_quote","appointment_consultation","demo_sales"), "membership_creator":("membership_subscription","direct_purchase","lead_quote"), "education":("application_enrollment","direct_purchase","appointment_consultation","membership_subscription"),
 "nonprofit":("donation_support","membership_subscription","application_enrollment"), "automotive":("lead_quote","appointment_consultation","direct_purchase","reservation_event"),
 "general":("lead_quote","appointment_consultation","reservation_event","direct_purchase","demo_sales","membership_subscription","donation_support","application_enrollment"),
}

# Journey grammar. Marker tiers: semantic(1), page/action(2-3), progression(4), terminal(5).
JOURNEY_GRAMMAR: Dict[str, Dict[str, Tuple[str,...]]] = {
 "local_visit":{"action":("directions","visit_location"),"progression":("menu","hours","location"),"terminal":()},
 "direct_purchase":{"action":("order","buy","add_to_cart"),"progression":("add_to_cart","cart","product_selection","checkout","payment"),"terminal":("order_confirmation",)},
 "reservation_event":{"action":("reserve","reservation","book_table","book_room","book_event"),"progression":("party_size","guests","date","time","availability","payment"),"terminal":("booking_confirmation","reservation_confirmation")},
 "appointment_consultation":{"action":("book","schedule","consultation","appointment"),"progression":("service_selection","provider_selection","date","time","availability"),"terminal":("appointment_confirmation","booking_confirmation")},
 "lead_quote":{"action":("quote","contact","estimate","enquire"),"progression":("requirements","contact_fields","project_details","budget","upload"),"terminal":("form_submission","request_sent","quote_request")},
 "demo_sales":{"action":("demo","trial","contact_sales"),"progression":("company","team_size","work_email","schedule"),"terminal":("demo_confirmation","trial_activation","form_submission")},
 "membership_subscription":{"action":("subscribe","join","membership"),"progression":("plan_selection","account","billing","payment"),"terminal":("subscription_confirmation","account_activation")},
 "donation_support":{"action":("donate","support"),"progression":("amount","donor_details","frequency","payment"),"terminal":("donation_confirmation",)},
 "application_enrollment":{"action":("apply","register","enroll","enrol"),"progression":("eligibility","application_fields","documents","program_selection"),"terminal":("application_submission","registration_confirmation","enrollment_confirmation")},
}

TEXT_MARKERS = {
 "menu":("menu","our menu","food menu","drink menu"), "hours":("hours","opening hours","open daily","hours of operation"), "location":("our location","locations","address","find us"), "directions":("get directions","directions","map"), "visit_location":("visit us","come visit","find us"),
 "cart":("shopping cart","your cart","view cart","/cart"), "checkout":("checkout","/checkout","secure checkout"), "payment":("payment","card number","billing address","pay now"),
 "order_confirmation":("order confirmed","order confirmation","thank you for your order"), "party_size":("party size","number of guests","guests"), "date":("select date","choose date","appointment date","check-in"), "time":("select time","choose time","available times"), "availability":("check availability","availability"),
 "booking_confirmation":("booking confirmed","booking confirmation"), "reservation_confirmation":("reservation confirmed","reservation confirmation"), "appointment_confirmation":("appointment confirmed","appointment confirmation"),
 "service_selection":("select service","choose service","service type"), "provider_selection":("select provider","choose provider","choose practitioner","select practitioner"),
 "requirements":("tell us about","describe your","project details","requirements"), "contact_fields":("email address","phone number","your name"), "project_details":("project details","job details","scope of work"), "budget":("budget","project budget"), "upload":("upload file","upload photo","attach file"), "form_submission":("submit","send request","send enquiry","send inquiry"), "request_sent":("request sent","thank you for contacting"), "quote_request":("request a quote","get a quote","free estimate"),
 "company":("company name","organization"), "team_size":("team size","company size","employees"), "work_email":("work email","business email"), "schedule":("schedule","calendar"), "demo_confirmation":("demo confirmed","meeting confirmed"), "trial_activation":("trial started","start your trial","free trial"),
 "plan_selection":("choose plan","select plan","pricing plan"), "account":("create account","sign up","account"), "billing":("billing","billing cycle"), "subscription_confirmation":("subscription confirmed","membership confirmed"), "account_activation":("account activated","welcome to"),
 "amount":("donation amount","choose amount","other amount"), "donor_details":("donor information","donor details"), "frequency":("monthly donation","one-time donation","recurring donation"), "donation_confirmation":("donation confirmed","thank you for your donation"),
 "eligibility":("eligibility","are you eligible","requirements"), "application_fields":("application form","applicant information"), "documents":("upload documents","supporting documents","transcript"), "program_selection":("select program","choose program","program of study"), "application_submission":("submit application","application submitted"), "registration_confirmation":("registration confirmed","registered successfully"), "enrollment_confirmation":("enrollment confirmed","enrolment confirmed"),
 "product_selection":("select options","choose option","quantity","menu item"),
}
ACTION_ALIASES={"directions":"directions","visit":"visit_location","order":"order","buy":"buy","add_to_cart":"add_to_cart","checkout":"checkout","reserve":"reserve","book":"book","quote":"quote","contact":"contact","demo":"demo","trial":"trial","subscribe":"subscribe","join":"join","donate":"donate","support":"support","apply":"apply","register":"register","enroll":"enroll","enrol":"enrol"}

def _all_text(data: Mapping[str,Any]) -> str:
    bits=[data.get("title"),data.get("meta_description")," ".join(data.get("h1_tags") or []),data.get("page_text"),data.get("journey_text_sample")]
    for p in data.get("journey_pages_scanned") or []:
        if isinstance(p,Mapping): bits.append(p.get("page_text_sample"))
    return " ".join(str(x or "") for x in bits).lower()[:180000]

def infer_subtype(data: Mapping[str,Any], business_type:str)->Dict[str,Any]:
    text=_all_text(data); rules=SUBTYPE_MARKERS.get(business_type,{})
    ranked=[]
    for subtype,terms in rules.items():
        hits=[t for t in terms if t in text]
        ranked.append((len(hits),subtype,hits))
    ranked.sort(key=lambda x:(-x[0],x[1])); n, subtype, hits = ranked[0] if ranked else (0,"unresolved",[])
    second=ranked[1][0] if len(ranked)>1 else 0
    conf=0.45 if n==0 else min(.94,.58+.09*n+.04*max(0,n-second))
    return {"subtype":subtype if n else "unresolved","subtype_label":(subtype if n else "unresolved").replace("_"," ").title(),"confidence":round(conf,2),"signals":hits[:8],"candidates":{s:c for c,s,_ in ranked[:5]}}

def _observed_markers(data:Mapping[str,Any])->Dict[str,List[Dict[str,Any]]]:
    """Bridge crawler receipts without manufacturing successful customer outcomes."""
    from urllib.parse import urlparse, urljoin, urlunparse
    out = {}
    def parse_url(value):
        try:
            return urlparse(str(value or ""))
        except ValueError:
            return urlparse("")
    def safe_url(value):
        p = parse_url(value)
        # Receipts retain the location, never URL credentials, query tokens or fragments.
        return urlunparse((p.scheme, p.netloc.rsplit("@", 1)[-1], p.path, "", "", ""))
    def verified_page(page):
        if not isinstance(page, Mapping) or page.get("verified") is not True:
            return False
        status = page.get("status_code")
        if status is None:
            return True  # Older verified receipts omitted the HTTP code.
        try:
            return 200 <= int(status) < 400
        except (TypeError, ValueError, OverflowError):
            return False
    def add(key, authority, source, detail="", source_url="", destination_url="", journey=None):
        receipt = {"authority": authority, "source": source, "detail": detail or key,
                   "source_url": safe_url(source_url), "destination_url": safe_url(destination_url)}
        if journey: receipt["journey_model"] = journey
        if receipt not in out.setdefault(key, []): out[key].append(receipt)
    base = str(data.get("final_url") or data.get("url") or data.get("domain") or "")
    for a in list(data.get("mobile_cta_types") or []) + list(data.get("journey_action_types") or []):
        if str(a).lower() in ACTION_ALIASES:
            add(ACTION_ALIASES[str(a).lower()], 3, "observed_action", str(a), base)
    bools = {"add_to_cart_visible":"add_to_cart", "checkout_context_detected":"checkout",
             "order_online_present":"order", "reservation_present":"reserve",
             "booking_action_present":"book", "directions_present":"directions"}
    for field, marker in bools.items():
        if data.get(field) is True: add(marker, 3, "verified_site_evidence", field, base)
    pages = [p for p in data.get("journey_pages_scanned") or [] if verified_page(p)]
    receipts = list(data.get("static_cta_evidence") or []) + list(data.get("journey_action_evidence") or []) + list(data.get("mobile_cta_evidence") or [])
    for page in pages:
        for receipt in page.get("static_cta_evidence") or []:
            if isinstance(receipt, Mapping): receipts.append({**receipt, "source_url": page.get("url")})
        for a in page.get("cta_types") or []:
            if a in ACTION_ALIASES: add(ACTION_ALIASES[a], 3, "observed_action", a, page.get("url"))
        for field, marker in bools.items():
            if page.get(field) is True: add(marker, 3, "verified_site_evidence", field, page.get("url"))
    for provider in data.get("booking_provider_links") or []:
        if isinstance(provider, Mapping):
            receipts.append({"source_url": provider.get("source_url") or base,
                             "href": provider.get("url"), "type": provider.get("action_type"),
                             "text": provider.get("label")})
    for receipt in receipts:
        if not isinstance(receipt, Mapping) or receipt.get("verified") is False: continue
        source_url = str(receipt.get("source_url") or receipt.get("url") or base)
        raw_dest = str(receipt.get("destination_url") or receipt.get("href") or "")
        try:
            dest = urljoin(source_url, raw_dest)
        except ValueError:
            dest = ""
        actions = receipt.get("action_types") or [receipt.get("type") or receipt.get("action_type")]
        if isinstance(actions, str): actions = [actions]
        for action in actions:
            marker = ACTION_ALIASES.get(str(action or "").lower())
            if not marker: continue
            add(marker, 3, "observed_action", str(receipt.get("text") or marker), source_url, dest)
            sp, dp = parse_url(source_url), parse_url(dest)
            # An observed outbound conversion CTA proves a handoff exists, not that it works.
            # Internal links require destination-page evidence; anchors/empty links never advance a path.
            if raw_dest and dp.scheme in {"http", "https"} and sp.hostname and dp.hostname and sp.hostname != dp.hostname:
                for journey, grammar in JOURNEY_GRAMMAR.items():
                    if marker in grammar["action"]:
                        add("external_handoff", 4, "observed_conversion_handoff", "External action destination observed; completion not tested", source_url, dest, journey)
    allowed = {"commerce_conversion","booking","contact_or_lead","evaluation","application","membership","donation","product","pricing","location"}
    progression = {m for g in JOURNEY_GRAMMAR.values() for m in g["progression"]}
    for page in pages:
        role = str(page.get("page_role") or page.get("role") or "")
        if role not in allowed: continue
        text = str(page.get("page_text_sample") or page.get("visible_text") or "").lower()
        # Outcome text alone is never a terminal receipt: FAQs and templates mention confirmations.
        for marker in progression:
            hits = [phrase for phrase in TEXT_MARKERS.get(marker, ()) if re.search(r"(?<!\w)"+re.escape(phrase)+r"(?!\w)", text)]
            if hits:
                role_paths = {"commerce_conversion":("direct_purchase",), "product":("direct_purchase",),
                    "booking":("reservation_event","appointment_consultation"),
                    "contact_or_lead":("lead_quote","demo_sales"), "application":("application_enrollment",),
                    "membership":("membership_subscription",), "donation":("donation_support",),
                    "pricing":("membership_subscription","direct_purchase","demo_sales"),
                    "location":("local_visit",), "evaluation":("local_visit",)}
                for journey in role_paths.get(role, ()):
                    if marker in JOURNEY_GRAMMAR[journey]["progression"]:
                        add(marker, 4, "verified_journey_page", hits[0], page.get("url"), journey=journey)
    if data.get("forms_present") is True and data.get("form_action_valid") is True:
        add("contact_fields", 4, "verified_form_structure", "Contact form structure observed", base, journey="lead_quote")
    if data.get("address_location_visible") is True and any(k in out for k in ("hours","menu","directions")):
        add("visit_location", 3, "composite_site_evidence", "Location and visit-planning evidence observed", base)
    # Trusted internal receipts only; scanner does not create these by submitting live forms/orders.
    for receipt in data.get("verified_outcome_receipts") or []:
        if not isinstance(receipt, Mapping): continue
        journey, marker = receipt.get("journey_model"), receipt.get("marker")
        if (journey in JOURNEY_GRAMMAR and marker in JOURNEY_GRAMMAR[journey]["terminal"]
            and receipt.get("verified") is True and receipt.get("outcome_observed") is True
            and receipt.get("source_url") and receipt.get("collection_method") in {"authorized_outcome_verification", "architect_verified_outcome"}):
            add(marker, 5, "verified_outcome_receipt", "Outcome independently verified", receipt["source_url"], journey=journey)
    return out

def resolve_journeys(data:Mapping[str,Any],business_type:str)->Dict[str,Any]:
    obs=_observed_markers(data)
    candidates=list(BUSINESS_JOURNEY_CANDIDATES.get(business_type,BUSINESS_JOURNEY_CANDIDATES["general"]))
    # Classification prioritizes discovery; observed actions can establish paths outside its priors.
    for j, grammar in JOURNEY_GRAMMAR.items():
        if j not in candidates and any(m in obs for m in grammar["action"]): candidates.append(j)
    results=[]
    for j in candidates:
        g=JOURNEY_GRAMMAR[j]; found={stage:[m for m in g[stage] if any(e.get("journey_model",j)==j for e in obs.get(m,[]))] for stage in ("action","progression","terminal")}
        if any(e.get("journey_model")==j for e in obs.get("external_handoff",[])):
            found["progression"].append("external_handoff")
        terminal=bool(found["terminal"]); progression=bool(found["progression"]); action=bool(found["action"])
        # Authority dominates quantity. Semantic/business priors are deliberately absent here.
        authority=5 if terminal and progression and action else 4 if progression and action else 3 if action else 2 if progression else 0
        completeness=(1 if action else 0)+(1 if progression else 0)+(1 if terminal else 0)
        observed_action_bonus = 0
        for marker in found["action"]:
            if any(e.get("source") == "observed_action" for e in obs.get(marker, [])):
                observed_action_bonus += 35
        strength=authority*100+completeness*20+min(15,5*sum(len(v) for v in found.values()))+observed_action_bonus
        status="VERIFIED" if terminal and progression and action else "STRONGLY_SUPPORTED" if authority==4 else "SUPPORTED" if authority==3 else "HYPOTHESIS"
        results.append({"journey_model":j,"authority":authority,"status":status,"completeness":f"{completeness}/3","strength":strength,"markers":found})
    results.sort(key=lambda x:(-x["authority"],-int(x["completeness"].split("/")[0]),-x["strength"],x["journey_model"]))
    top=results[0] if results else {"journey_model":"general","authority":0,"strength":0,"status":"HYPOTHESIS","completeness":"0/3","markers":{}}
    # No explicit action/progression proof => unresolved. Business type only tells crawler what to seek.
    supported=[r for r in results if r["authority"]>=4 and r["markers"]["action"] and r["markers"]["progression"]]
    ambiguous = len(supported)>1 and (supported[0]["authority"], supported[0]["completeness"]) == (supported[1]["authority"], supported[1]["completeness"])
    resolved=bool(top["authority"]>=3 and not ambiguous)
    return {"journey_model":top["journey_model"] if resolved else "general","resolved":resolved,"authority":top["authority"],"status":top["status"] if top["authority"] else "UNVERIFIED","path_completeness":top["completeness"],"proof":top["markers"],"ranked_paths":results,"observed_markers":obs,"candidate_journeys":list(candidates),"primary_ordering_ambiguous":ambiguous,"architect_review_required":not resolved or top["authority"]<4,"best_supported_journey":top["journey_model"] if top["authority"] else "general"}

def build_differentiation_plan(data:Mapping[str,Any],business_type:str)->Dict[str,Any]:
    subtype=infer_subtype(data,business_type); paths=resolve_journeys(data,business_type)
    seek=[]
    for j in paths["candidate_journeys"]:
        g=JOURNEY_GRAMMAR[j]
        seek.extend(g["action"]); seek.extend(g["progression"]); seek.extend(g["terminal"])
    return {"business_type":business_type,"subtype":subtype,"candidate_journeys":paths["candidate_journeys"],"seek_markers":list(dict.fromkeys(seek)),"policy":"Business type/subtype narrows the evidence search. Only observed path markers resolve the customer journey."}
