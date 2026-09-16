"""Broad-spectrum knowledge tests for V7.3.3.
These test recognition breadth without changing Trilloka's scoring/reasoning model.
"""
import pytest
from architecture_model import infer_architecture_profile

CASES = [
("ecommerce","direct_purchase","Northstar Outdoor Shop","Shop collection","Product details size guide in stock free shipping return policy product reviews add to cart proceed to checkout",["buy"]),
("marketplace","direct_purchase","TradeSquare Marketplace","Buyers and sellers","Browse listings verified sellers buyer protection seller dashboard become a seller list an item checkout",["buy"]),
("local_service","lead_quote","MetroFix Home Services","Licensed contractor","24/7 service same-day repair service areas we serve project gallery warranty financing available free quote",["quote"]),
("professional_service","lead_quote","Cedar CPA Advisory Firm","Business advisory","Accounting firm tax advisory audit services our approach client success schedule consultation request a proposal",["quote"]),
("healthcare","appointment_consultation","Harbour Medical Practice","Patient care","New patients conditions we treat insurance accepted patient portal telehealth book appointment registered therapist",["book"]),
("medspa","appointment_consultation","Luma Aesthetic Clinic","Medical aesthetics","Botox cosmetic injections skin rejuvenation laser treatment before and after skin consultation book treatment",["book"]),
("legal","appointment_consultation","Westshore Law Firm","Legal representation","Practice areas corporate law estate law civil litigation legal team free case review legal consultation",["book"]),
("financial_services","appointment_consultation","Summit Wealth Management","Financial planning","Investment planning wealth advisor portfolio management retirement planning estate planning schedule consultation",["book"]),
("real_estate","lead_quote","Oakline Realty","Homes for sale","Featured listings realtor property search home valuation listing agent schedule a showing sell your home contact",["contact"]),
("restaurant","reservation_event","Juniper Cafe Restaurant","Our menu","Brunch food and drink happy hour opening hours reservations table booking order online view menu",["reserve"]),
("hospitality_event","reservation_event","Seacliff Resort Hotel","Rooms and suites","Hotel rooms amenities nightly rate check-in guest stay check room availability reserve your stay event packages",["reserve"]),
("saas","demo_sales","VectorFlow Software Platform","Workflow automation","Features integrations API docs security SSO pricing enterprise plan request demo start free trial contact sales",["demo"]),
("b2b","demo_sales","IronPeak Industrial Solutions","For enterprises","Manufacturing distributor supply chain procurement technical specifications industries case studies request RFQ contact sales",["demo"]),
("agency","lead_quote","Northlight Creative Agency","Selected work","Brand agency digital marketing media buying public relations portfolio client results start a project book discovery call",["quote"]),
("membership_creator","membership_subscription","MakerCircle Community","Member benefits","Membership plans premium membership member portal exclusive content paid community join the community subscribe now",["join"]),
("education","application_enrollment","Pacific Technical College","Programs and admissions","College course catalog learning outcomes diploma certificate tuition scholarship student portal apply now enrollment",["apply"]),
("nonprofit","donation_support","River Foundation Nonprofit","Our mission","Registered charity community programs our impact annual report volunteer tax receipt support our mission donate now",["donate"]),
("automotive","lead_quote","Apex Auto Repair","Vehicle service","Auto repair brake service tire change collision repair parts and service book service service appointment free quote",["quote"]),
]

@pytest.mark.parametrize("expected_type,expected_journey,title,h1,text,actions", CASES)
def test_all_business_types_have_deep_recognition(expected_type,expected_journey,title,h1,text,actions):
    p = infer_architecture_profile({"title":title,"h1_tags":[h1],"page_text":text,"journey_text_sample":text,"mobile_cta_types":actions},"auto")
    assert p["business_type"] == expected_type, p
    assert p["business_type_confidence"] >= .70, p
    assert p["journey_model"] == expected_journey, p

@pytest.mark.parametrize("text",[
    "We help organizations move forward with confidence. Learn more about our people.",
    "Welcome to Northstar. Discover our story and latest news.",
    "A better experience starts here. Explore what we do.",
])
def test_generic_sites_stay_unresolved(text):
    p=infer_architecture_profile({"title":"Northstar","h1_tags":["Welcome"],"page_text":text},"auto")
    assert p["business_type"]=="general", p

@pytest.mark.parametrize("title,text,not_type",[
("Industrial Safety Systems","Enterprise industrial manufacturing safety equipment for hospitals and factories request RFQ","healthcare"),
("LegalTech Software","Software platform for law firms integrations API request demo free trial","legal"),
("Restaurant POS Platform","SaaS software platform for restaurants pricing integrations request demo","restaurant"),
("Automotive Marketing Agency","Digital marketing agency for car dealers selected work client results start a project","automotive"),
("Nonprofit Accounting Advisors","CPA accounting advisory for nonprofit organizations tax services request proposal","nonprofit"),
])
def test_audience_words_do_not_hijack_provider_identity(title,text,not_type):
    p=infer_architecture_profile({"title":title,"h1_tags":[title],"page_text":text,"journey_text_sample":text},"auto")
    assert p["business_type"] != not_type, p

@pytest.mark.parametrize("journey,text,action",[
("lead_quote","Request a proposal get pricing tell us about your project", "quote"),
("appointment_consultation","Book appointment schedule assessment patient booking", "book"),
("reservation_event","Reserve your stay check room availability table reservation", "reserve"),
("direct_purchase","Add to cart proceed to checkout complete order", "buy"),
("demo_sales","Request demo contact sales start free trial", "demo"),
("membership_subscription","Become a member choose membership subscribe now", "join"),
("donation_support","Donate now monthly giving support our mission", "donate"),
("application_enrollment","Apply now start application course registration", "apply"),
])
def test_all_journey_families_are_recognized(journey,text,action):
    # Explicit general business freezes business classification but intentionally tests journey vocabulary.
    p=infer_architecture_profile({"title":"Organization","h1_tags":["Get started"],"page_text":text,"mobile_cta_types":[action]},"auto")
    assert p["journey_model"] == journey, p
