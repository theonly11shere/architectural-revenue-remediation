from architecture_model import infer_architecture_profile


def test_valmont_style_restaurant_is_resolved_from_commercial_evidence():
    profile = infer_architecture_profile({
        "title": "Best Pho - Banh Mi - Vietnamese Dish - Richmond",
        "h1_tags": ["Fresh Vietnamese Cuisine"],
        "meta_description": "Vietnamese Cuisine serving north Richmond",
        "page_text": (
            "Our Restaurant. Vietnamese cuisine restaurant. Dine in menu. Pho, Banh Mi, appetizers. "
            "Opening Hours. Richmond BC. Call us. Over 200 positive Reviews. order today!"
        ),
        "journey_text_sample": "Menu fresh local. Authentic Vietnamese Dishes. Business Hours. Location. Get direction.",
    }, "auto")
    assert profile["business_type"] == "restaurant"
    assert profile["business_type_confidence"] >= 0.80
    assert profile["journey_model"] == "direct_purchase"
    assert "local_location_dependent" in profile["context_tags"]


def test_ecommerce_keeps_existing_direct_purchase_logic_with_more_vocabulary():
    profile = infer_architecture_profile({
        "title": "Cranberry Shop",
        "h1_tags": ["Shop products"],
        "page_text": "Shop online. Add to bag. Secure checkout. Delivery in 4-5 working days. Returns. Customer reviews. Buy now.",
    }, "auto")
    assert profile["business_type"] == "ecommerce"
    assert profile["journey_model"] == "direct_purchase"
    assert "commerce_payment" in profile["context_tags"]


def test_ambiguous_site_stays_general_instead_of_guessing():
    profile = infer_architecture_profile({
        "title": "Northstar",
        "h1_tags": ["Welcome"],
        "page_text": "We help people achieve better outcomes. Learn more about our team.",
    }, "auto")
    assert profile["business_type"] == "general"
    assert profile["journey_model"] == "general"


def test_multiservice_medical_mention_does_not_hijack_b2b():
    profile = infer_architecture_profile({
        "title": "Remote Alaskan Services",
        "h1_tags": ["We've Got You Covered"],
        "meta_description": "Remote support services for exploration and production operations.",
        "page_text": "support services oil gas industry logistics drilling aviation project support remote medical clinic sets contact",
        "journey_text_sample": "remote medical services medical clinic consultation occupational health logistics drilling support contact",
        "phone_number_visible": True,
        "mobile_cta_types": ["contact"],
    }, "auto")
    assert profile["journey_model"] == "lead_quote"
    assert "regulated_high_trust" not in profile["context_tags"]
