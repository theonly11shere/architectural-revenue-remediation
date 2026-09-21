from architecture_model import infer_architecture_profile
from pathway_markers import infer_subtype, resolve_journeys, BUSINESS_JOURNEY_CANDIDATES

def test_restaurant_purchase_path_beats_reservation_prior():
    p=infer_architecture_profile({"title":"Valmont Cafe Restaurant","page_text":"Menu dining food Order Online","journey_text_sample":"Order Online Add to Cart Cart Checkout secure payment","mobile_cta_types":["order"],"journey_action_types":["order","add_to_cart","checkout"],"order_online_present":True,"add_to_cart_visible":True,"checkout_context_detected":True},"auto")
    assert p["business_type"]=="restaurant"
    assert p["journey_model"]=="direct_purchase"
    assert p["journey_marker_resolution"]["authority"]>=4
    assert p["weighted_journey_candidate"] in {"direct_purchase","reservation_event"}

def test_restaurant_words_alone_do_not_prove_reservation():
    p=infer_architecture_profile({"title":"Restaurant","page_text":"restaurant menu dining chef food"},"restaurant")
    assert p["journey_model"]=="general"
    assert p["journey_marker_resolution"]["resolved"] is False

def test_reservation_requires_explicit_path_marker():
    p=infer_architecture_profile({"title":"Restaurant","page_text":"Reserve a table. Party size. Select date. Select time. Booking confirmation","mobile_cta_types":["reserve"],"reservation_present":True},"restaurant")
    assert p["journey_model"]=="reservation_event"
    assert p["journey_marker_resolution"]["status"]=="SUPPORTED"
    assert p["journey_marker_resolution"]["proof"]["terminal"] == []

def test_all_business_types_have_candidate_search_plan():
    for b,candidates in BUSINESS_JOURNEY_CANDIDATES.items():
        assert candidates
        p=infer_architecture_profile({"page_text":"contact services"}, b if b!='general' else 'general')
        assert "differentiation_plan" in p

def test_subtypes_across_major_families():
    cases=[("restaurant","coffee bakery brunch","cafe_bakery"),("saas","request demo contact sales enterprise software","sales_led_saas"),("automotive","inventory dealership test drive vehicles for sale","dealer"),("education","online course certificate curriculum","course_provider"),("b2b","manufacturer oem factory","manufacturer"),("healthcare","dentist dental orthodontics","dental")]
    for b,text,expected in cases:
        assert infer_subtype({"page_text":text},b)["subtype"]==expected

def test_observed_quote_cta_beats_generic_schedule_language():
    r=resolve_journeys({"page_text":"schedule consultation request a proposal","mobile_cta_types":["quote"]},"professional_service")
    assert r["journey_model"]=="lead_quote"
