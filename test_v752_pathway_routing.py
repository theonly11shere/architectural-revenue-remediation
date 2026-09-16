"""V7.5.2 pathway-routing regression tests."""
from pathway_markers import resolve_journeys

def test_external_order_handoff_is_strong_direct_purchase():
    scan={"domain":"cafe.example","mobile_cta_types":["order"],"external_order_handoff_present":True,"page_text":"Cafe brunch menu and opening hours."}
    result=resolve_journeys(scan,"restaurant")
    assert result["journey_model"]=="direct_purchase" and result["authority"]==4 and result["path_completeness"]=="2/3"

def test_restaurant_hours_do_not_fabricate_reservation_progression():
    result=resolve_journeys({"domain":"cafe.example","page_text":"Cafe open Monday-Friday 8am-5pm. Coffee and brunch menu."},"restaurant")
    assert result["journey_model"]=="general" and result["authority"]==0

def test_reservation_action_alone_is_supported_only():
    result=resolve_journeys({"domain":"restaurant.example","mobile_cta_types":["reserve"],"page_text":"Reserve a table. Open daily 8am-10pm."},"restaurant")
    assert result["journey_model"]=="reservation_event" and result["authority"]==3 and result["path_completeness"]=="1/3"

def test_verified_booking_progression_is_strong():
    scan={"domain":"restaurant.example","mobile_cta_types":["reserve"],"journey_pages_scanned":[{"verified":True,"role":"booking","url":"https://restaurant.example/reservations","page_text_sample":"Party size. Select date. Choose time."}]}
    result=resolve_journeys(scan,"restaurant")
    assert result["journey_model"]=="reservation_event" and result["authority"]==4 and result["path_completeness"]=="2/3"
