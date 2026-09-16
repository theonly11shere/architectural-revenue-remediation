"""Trilloka V7.5 hierarchical business/subtype + customer-path marker engine.

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
 "restaurant":("direct_purchase","reservation_event","lead_quote","appointment_consultation"), "ecommerce":("direct_purchase","membership_subscription","lead_quote"),
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
 "direct_purchase":{"action":("order","buy","add_to_cart"),"progression":("add_to_cart","cart","product_selection"),"terminal":("checkout","payment","order_confirmation")},
 "reservation_event":{"action":("reserve","reservation","book_table","book_room","book_event"),"progression":("party_size","guests","date","time","availability"),"terminal":("booking_confirmation","reservation_confirmation","payment")},
 "appointment_consultation":{"action":("book","schedule","consultation","appointment"),"progression":("service_selection","provider_selection","date","time","availability"),"terminal":("appointment_confirmation","booking_confirmation")},
 "lead_quote":{"action":("quote","contact","estimate","enquire"),"progression":("requirements","contact_fields","project_details","budget","upload"),"terminal":("form_submission","request_sent","quote_request")},
 "demo_sales":{"action":("demo","trial","contact_sales"),"progression":("company","team_size","work_email","schedule"),"terminal":("demo_confirmation","trial_activation","form_submission")},
 "membership_subscription":{"action":("subscribe","join","membership"),"progression":("plan_selection","account","billing"),"terminal":("payment","subscription_confirmation","account_activation")},
 "donation_support":{"action":("donate","support"),"progression":("amount","donor_details","frequency"),"terminal":("payment","donation_confirmation")},
 "application_enrollment":{"action":("apply","register","enroll","enrol"),"progression":("eligibility","application_fields","documents","program_selection"),"terminal":("application_submission","registration_confirmation","enrollment_confirmation")},
}

TEXT_MARKERS = {
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
ACTION_ALIASES={"order":"order","buy":"buy","add_to_cart":"add_to_cart","checkout":"checkout","reserve":"reserve","book":"book","quote":"quote","contact":"contact","demo":"demo","trial":"trial","subscribe":"subscribe","join":"join","donate":"donate","support":"support","apply":"apply","register":"register","enroll":"enroll","enrol":"enrol"}

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
    out:Dict[str,List[Dict[str,Any]]]={}
    def add(key,authority,source,detail=""):
        out.setdefault(key,[]).append({"authority":authority,"source":source,"detail":detail or key})
    actions=set(str(x).lower() for x in (data.get("mobile_cta_types") or []))|set(str(x).lower() for x in (data.get("journey_action_types") or []))
    for a in actions:
        if a in ACTION_ALIASES:add(ACTION_ALIASES[a],3,"observed_action",a)
    bools={"add_to_cart_visible":"add_to_cart","checkout_context_detected":"checkout","order_online_present":"order","reservation_present":"reserve","booking_action_present":"book"}
    for field,m in bools.items():
        if data.get(field) is True:add(m,4 if m in {"add_to_cart","checkout"} else 3,"verified_site_evidence",field)
    text=_all_text(data)
    explicit_action_phrases = {
        "quote": ("request a quote", "get a quote", "free estimate", "request a proposal"),
        "contact": ("contact us", "contact our", "get in touch"),
        "book": ("book a consultation", "book consultation", "book appointment", "schedule appointment", "schedule a showing"),
        "reserve": ("reserve a table", "book a table", "make a reservation"),
        "order": ("order online", "order now", "order today"),
        "buy": ("buy now", "purchase now"), "demo": ("request a demo", "book a demo"),
        "trial": ("start free trial", "start a trial"), "subscribe": ("subscribe now", "start subscription"),
        "join": ("join now", "become a member"), "donate": ("donate now", "make a donation"),
        "apply": ("apply now", "start application"), "register": ("register now", "registration"),
        "enroll": ("enroll now", "enrol now"),
    }
    for marker, phrases in explicit_action_phrases.items():
        hits=[p for p in phrases if p in text]
        if hits:add(marker,3,"explicit_action_text",hits[0])
    for marker,phrases in TEXT_MARKERS.items():
        hits=[p for p in phrases if p in text]
        if hits:add(marker,4 if marker not in {"payment","order_confirmation","booking_confirmation","reservation_confirmation","appointment_confirmation","demo_confirmation","trial_activation","subscription_confirmation","account_activation","donation_confirmation","application_submission","registration_confirmation","enrollment_confirmation"} else 5,"page_text",hits[0])
    return out

def resolve_journeys(data:Mapping[str,Any],business_type:str)->Dict[str,Any]:
    obs=_observed_markers(data); candidates=BUSINESS_JOURNEY_CANDIDATES.get(business_type,BUSINESS_JOURNEY_CANDIDATES["general"])
    results=[]
    for j in candidates:
        g=JOURNEY_GRAMMAR[j]; found={stage:[m for m in g[stage] if m in obs] for stage in ("action","progression","terminal")}
        terminal=bool(found["terminal"]); progression=bool(found["progression"]); action=bool(found["action"])
        # Authority dominates quantity. Semantic/business priors are deliberately absent here.
        authority=5 if terminal else 4 if progression and action else 3 if action else 2 if progression else 0
        completeness=(1 if action else 0)+(1 if progression else 0)+(1 if terminal else 0)
        observed_action_bonus = 0
        for marker in found["action"]:
            if any(e.get("source") == "observed_action" for e in obs.get(marker, [])):
                observed_action_bonus += 35
        strength=authority*100+completeness*20+min(15,5*sum(len(v) for v in found.values()))+observed_action_bonus
        status="VERIFIED" if terminal else "STRONGLY_SUPPORTED" if authority==4 else "SUPPORTED" if authority==3 else "HYPOTHESIS"
        results.append({"journey_model":j,"authority":authority,"status":status,"completeness":f"{completeness}/3","strength":strength,"markers":found})
    results.sort(key=lambda x:(-x["strength"],x["journey_model"]))
    top=results[0] if results else {"journey_model":"general","authority":0,"strength":0,"status":"HYPOTHESIS","completeness":"0/3","markers":{}}
    # No explicit action/progression proof => unresolved. Business type only tells crawler what to seek.
    resolved=top["authority"]>=3
    return {"journey_model":top["journey_model"] if resolved else "general","resolved":resolved,"authority":top["authority"],"status":top["status"] if resolved else "UNVERIFIED","path_completeness":top["completeness"],"proof":top["markers"],"ranked_paths":results,"observed_markers":obs,"candidate_journeys":list(candidates)}

def build_differentiation_plan(data:Mapping[str,Any],business_type:str)->Dict[str,Any]:
    subtype=infer_subtype(data,business_type); paths=resolve_journeys(data,business_type)
    seek=[]
    for j in paths["candidate_journeys"]:
        g=JOURNEY_GRAMMAR[j]
        seek.extend(g["action"]); seek.extend(g["progression"]); seek.extend(g["terminal"])
    return {"business_type":business_type,"subtype":subtype,"candidate_journeys":paths["candidate_journeys"],"seek_markers":list(dict.fromkeys(seek)),"policy":"Business type/subtype narrows the evidence search. Only observed path markers resolve the customer journey."}
