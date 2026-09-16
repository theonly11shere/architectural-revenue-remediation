from architecture_model import infer_architecture_profile
from pathway_markers import resolve_journeys

def test_restaurant_order_external_handoff_is_direct_purchase_2_of_3():
    scan={
        "domain":"https://cafe.example/",
        "title":"Cafe",
        "h1_tags":["Cafe & Bakery"],
        "page_text":"Coffee bakery pastries",
        "mobile_cta_types":["order"],
        "static_cta_evidence":[{
            "type":"order","action_types":["order"],"text":"Order",
            "href":"https://ordering.vendor.example/store/cafe",
            "source_url":"https://cafe.example/"
        }],
        "journey_pages_scanned":[],
    }
    p=infer_architecture_profile(scan,"auto")
    r=p["journey_marker_resolution"]
    assert p["business_type"]=="restaurant"
    assert p["journey_model"]=="direct_purchase"
    assert r["status"]=="STRONGLY_SUPPORTED"
    assert r["path_completeness"]=="2/3"
    assert "order" in r["proof"]["action"]
    assert "external_commerce_handoff" in r["proof"]["progression"]
    assert r["proof"]["terminal"]==[]

def test_generic_hours_date_time_does_not_fake_reservation_progression():
    scan={
        "domain":"https://cafe.example/",
        "title":"Cafe",
        "h1_tags":["Cafe"],
        "page_text":"Open Monday 8am to 5pm. Dinner menu. Contact us.",
        "mobile_cta_types":["contact"],
        "journey_pages_scanned":[],
    }
    r=resolve_journeys(scan,"restaurant")
    reservation=next(x for x in r["ranked_paths"] if x["journey_model"]=="reservation_event")
    assert reservation["markers"]["progression"]==[]
    assert reservation["markers"]["terminal"]==[]

def test_verified_booking_page_can_supply_progression():
    scan={
        "domain":"https://restaurant.example/",
        "title":"Restaurant",
        "page_text":"Restaurant",
        "mobile_cta_types":["reserve"],
        "journey_pages_scanned":[{
            "url":"https://restaurant.example/reserve",
            "verified":True,"role":"booking",
            "page_text_sample":"Select date. Choose time. Party size."
        }],
    }
    r=resolve_journeys(scan,"restaurant")
    assert r["journey_model"]=="reservation_event"
    assert r["status"]=="STRONGLY_SUPPORTED"
    assert r["path_completeness"]=="2/3"
