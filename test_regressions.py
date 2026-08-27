from __future__ import annotations

from report_engine import FAIL, NA, PASS, UNKNOWN, ReportGenerator
from scorer import RevenueScorer


def base_scan():
    return {
        "domain": "example.com",
        "is_reachable": True,
        "response_ok": True,
        "status_code": 200,
        "final_url": "https://example.com/",
        "has_ssl": True,
        "https_redirect_enforced": True,
        "browser_loaded": True,
        "dom_complete": True,
        "scan_quality": {
            "http_ok": True,
            "browser_loaded": True,
            "dom_complete": True,
            "bot_challenge_suspected": False,
            "pagespeed_available": True,
            "crux_available": False,
            "confidence": "high",
        },
        "evidence_coverage": {"ratio": 0.9},
        "performance_score": 90.0,
        "google_seo_score": 92.0,
        "pagespeed_api_status": "success",
        "crux_available": False,
        "real_user_speed_grade": "UNKNOWN",
        "title": "Example Company - Useful Services for Customers in Vancouver",
        "meta_description": "A useful example description that is long enough to represent a normal metadata fixture for testing purposes.",
        "h1_status": "present",
        "h1_tags": ["Useful Services"],
        "h1_dom_count": 1,
        "h1_source_count": 1,
        "h1_relevance_status": "UNKNOWN",
        "page_text": "Useful Services. Contact us for details. " * 50,
        "visible_word_count": 400,
        "phone_number_visible": True,
        "phone_visibility_status": "verified",
        "detected_phone_numbers": ["604-555-1234"],
        "click_to_call_present": True,
        "click_to_call_status": "verified",
        "mobile_primary_cta_present": True,
        "mobile_sticky_cta_present": True,
        "mobile_cta_visible": True,
        "mobile_cta_status": "verified",
        "mobile_cta_types": ["contact"],
        "add_to_cart_visible": False,
        "order_online_present": False,
        "reservation_present": False,
        "directions_present": False,
        "whatsapp_present": False,
        "live_chat_present": False,
        "forms_present": False,
        "form_action_valid": None,
        "form_functional_status": "NOT_APPLICABLE",
        "form_payload_fired": False,
        "image_count": 3,
        "total_images": 3,
        "missing_alt_images": 0,
        "images_with_alt": 3,
        "favicon_present": True,
        "html_lang_present": True,
        "ai_spectrum_pct": None,
        "ai_spectrum_status": "unknown",
        "ai_flags": {"generic_headline": False, "unlinked_forms": 0},
        "has_ga4": True,
        "has_meta_pixel": False,
        "has_qualitative_analytics": False,
        "cms_platform": "Not confidently identified",
        "cms_confidence": "low",
        "business_profile": {
            "vertical": "general",
            "confidence": 0.4,
            "primary_conversion": "primary_site_action",
            "secondary_conversions": ["contact"],
            "signals": [],
        },
        "schema_present": True,
        "schema_types": ["Organization"],
        "canonical_present": True,
        "sitemap_present": True,
        "robots_valid": True,
        "mobile_viewport_configured": True,
        "psi_lcp_ms": 1800.0,
        "psi_cls": 0.05,
        "crux_lcp_ms": None,
        "crux_inp_ms": None,
        "crux_cls": None,
        "psi_tap_targets_flagged": 0,
        "tap_targets_flagged": [],
        "psi_render_blocking_count": 0,
        "lazy_loading_status": "PASS",
        "lazy_image_count": 2,
        "retargeting_pixel_installed": False,
        "custom_photography_status": "UNKNOWN",
        "custom_photography_signal": True,
        "address_location_visible": True,
        "trust_badges_present": False,
        "reviews_visible": True,
        "guarantee_refund_present": False,
        "about_team_linked": True,
        "social_proof_present": True,
        "faq_present": True,
        "case_studies_portfolio_present": True,
        "blog_present": True,
        "social_links_present": True,
        "privacy_policy_linked": True,
        "terms_linked": True,
        "privacy_terms_linked": True,
        "cookie_banner_present": False,
        "author_bylines_present": True,
        "publication_dates_visible": True,
    }


def valmont_fixture():
    data = base_scan()
    data.update(
        {
            "domain": "valmontcafe.com",
            "title": "Valmont Cafe - Fresh Vietnamese Cuisine",
            "h1_status": "present",
            "h1_tags": ["Fresh Vietnamese Cuisine"],
            "h1_dom_count": 1,
            "h1_source_count": 1,
            "h1_relevance_status": "PASS",
            "page_text": "Valmont Cafe Fresh Vietnamese Cuisine Menu Order Online Pickup Richmond 604-276-0120 " * 20,
            "phone_number_visible": True,
            "detected_phone_numbers": ["604-276-0120"],
            "click_to_call_present": False,
            "mobile_primary_cta_present": True,
            "mobile_sticky_cta_present": False,
            "mobile_cta_visible": False,
            "mobile_cta_types": ["order"],
            "order_online_present": True,
            "has_ga4": False,
            "has_meta_pixel": False,
            "business_profile": {
                "vertical": "restaurant",
                "confidence": 0.93,
                "primary_conversion": "order_online",
                "secondary_conversions": ["reservation", "directions", "call", "view_menu"],
                "signals": ["restaurant", "menu", "order online", "cuisine"],
            },
            "blog_present": False,
            "faq_present": False,
            "case_studies_portfolio_present": False,
            "author_bylines_present": False,
            "publication_dates_visible": False,
        }
    )
    return data


def test_valmont_h1_false_positive_is_impossible():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    rules = [x["rule_key"] for x in audit["tiered_remediation_packages"]["all_scoring_leaks"]]
    assert "diluted_h1" not in rules
    assert audit["business_type"] == "restaurant"


def test_visible_phone_without_tel_is_partial_not_total_failure():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    leak = next(x for x in audit["tiered_remediation_packages"]["all_scoring_leaks"] if x["rule_key"] == "click_to_call")
    assert leak["severity_factor"] == 0.4
    assert leak["substitution_factor"] < 1.0
    assert leak["severity_score"] < 3.0


def test_sticky_and_click_to_call_are_overlap_adjusted():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    adjustment = next(x for x in audit["overlap_adjustments"] if x["family"] == "mobile_direct_action")
    assert adjustment["post_dedupe_total"] < adjustment["pre_dedupe_total"]


def test_restaurant_remediation_does_not_use_free_consultation_or_intake_team():
    scan = valmont_fixture()
    audit = RevenueScorer().audit_and_score(scan, business_type="auto", competitor_data_present=None)
    report = ReportGenerator().generate_admin_master_report(audit, scan)
    joined = " ".join(
        " ".join((leak["solutions_3_angles"].get(k, "") for k in ("technical", "cro_ux", "systems", "why_recommend")))
        for leak in report["top_6_financial_leaks"]
    ).lower()
    assert "free consultation" not in joined
    assert "intake team" not in joined
    assert "order now" in joined


def test_severity_factor_survives_to_report():
    scan = valmont_fixture()
    audit = RevenueScorer().audit_and_score(scan, business_type="auto", competitor_data_present=None)
    click = next(x for x in audit["tiered_remediation_packages"]["all_scoring_leaks"] if x["rule_key"] == "click_to_call")
    assert click["severity_factor"] == 0.4
    report = ReportGenerator().generate_admin_master_report(audit, scan)
    # V5 may consolidate click-to-call into the mobile-direct-action commercial family.
    mobile = next(x for x in report["top_10_financial_leaks"] if x.get("family") == "mobile_direct_action")
    if mobile.get("rule_key") == "click_to_call":
        assert mobile["severity_factor"] == 0.4
    else:
        raw_click = next(x for x in audit["tiered_remediation_packages"]["all_scoring_leaks"] if x["rule_key"] == "click_to_call")
        assert raw_click["severity_factor"] == 0.4
    if mobile.get("rule_key") == "click_to_call":
        assert mobile["severity_label"] == "MODERATE FRICTION"


def test_no_three_leak_critical_score_clamp():
    scan = valmont_fixture()
    audit = RevenueScorer().audit_and_score(scan, business_type="auto", competitor_data_present=None)
    assert audit["total_leaks_found"] >= 3
    assert audit["overall_score"] >= 35.0


def test_unknown_ai_is_not_faked_to_45():
    scan = base_scan()
    scan["ai_spectrum_pct"] = None
    scan["ai_spectrum_status"] = "unknown"
    audit = RevenueScorer().audit_and_score(scan, business_type="auto", competitor_data_present=None)
    assert audit["ai_spectrum_pct"] is None
    assert not any(x["rule_key"] == "ai_template_similarity" for x in audit["tiered_remediation_packages"]["all_scoring_leaks"])


def test_competitor_bonus_is_zero_when_unknown():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    assert all(row["competitor_advantage_bonus"] == 0 for row in audit["scoring_ledger"])


def test_50_checkpoints_never_hardcode_unknown_metrics_to_pass():
    scan = base_scan()
    scan.update(
        {
            "pagespeed_api_status": "unavailable",
            "performance_score": None,
            "google_seo_score": None,
            "psi_lcp_ms": None,
            "crux_lcp_ms": None,
            "crux_inp_ms": None,
            "psi_cls": None,
            "crux_cls": None,
            "schema_present": None,
            "canonical_present": None,
            "sitemap_present": None,
            "robots_valid": None,
        }
    )
    reporter = ReportGenerator()
    cps = reporter._build_50_checkpoints(scan, {"business_type": "general", "business_profile": scan["business_profile"]})
    by_id = {cp["id"]: cp for cp in cps}
    for cp_id in (21, 22, 23, 24, 25, 26, 27, 28, 29, 30):
        assert by_id[cp_id]["status"] == UNKNOWN


def test_restaurant_irrelevant_content_checks_are_na():
    scan = valmont_fixture()
    reporter = ReportGenerator()
    cps = reporter._build_50_checkpoints(scan, {"business_type": "restaurant", "business_profile": scan["business_profile"]})
    by_id = {cp["id"]: cp for cp in cps}
    assert by_id[37]["status"] == NA
    assert by_id[38]["status"] == NA
    assert by_id[39]["status"] == NA
    assert by_id[45]["status"] == NA
    assert by_id[46]["status"] == NA


def test_score_math_is_reproducible():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    total = round(sum(row["final_score_loss"] for row in audit["scoring_ledger"]), 2)
    formula = audit["score_formula"]
    canonical = round(
        formula["foundation_layer_score"]
        + formula["revenue_user_architecture_score"]
        + formula["elite_architecture_score"],
        2,
    )
    expected = round(RevenueScorer._calibrate_public_score(canonical), 1)
    assert formula["total_final_penalty"] == total
    assert formula["canonical_three_layer_score"] == canonical
    assert audit["overall_score"] == expected


def test_valmont_style_site_no_longer_receives_an_easy_good_score():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    # A functional ordering site with missing mobile support and no meaningful measurement
    # should land in the functional/headroom band rather than automatically receiving 65+.
    assert 35.0 <= audit["overall_score"] <= 45.0
    assert audit["score_rating"] == "MATERIAL COMMERCIAL WEAKNESSES"
    assert audit["analysis_layers"]["elite_architecture"]["layer_score"] == 0


def test_provisional_site_does_not_receive_resolved_strong_score_too_easily():
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="auto", competitor_data_present=None)
    assert audit["business_profile"].get("provisional") is True
    assert audit["overall_score"] < 46.0
    detail = audit["analysis_layers"]["adaptive_architecture"]["weighted_checkpoint_detail"]
    assert detail["journey_resolution_factor"] < 1.0


def test_score_is_explicitly_not_literal_conversion_rate():
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="auto", competitor_data_present=None)
    assert "not a literal visitor conversion percentage" in audit["score_semantics"].lower()


def test_structurally_valid_form_does_not_fake_delivery_success():
    scan = base_scan()
    scan["forms_present"] = True
    scan["form_action_valid"] = True
    scan["form_functional_status"] = "UNKNOWN"
    reporter = ReportGenerator()
    cps = reporter._build_50_checkpoints(scan, {"business_type": "general", "business_profile": scan["business_profile"]})
    cp5 = next(cp for cp in cps if cp["id"] == 5)
    cp50 = next(cp for cp in cps if cp["id"] == 50)
    assert cp5["status"] == PASS
    assert cp50["status"] == UNKNOWN
    assert "No destructive" in cp50["customer_note"]
    assert "not destructively tested" in cp50["customer_note"].lower()


def test_static_html_fallback_collapses_unknowns_without_guessing():
    from hybrid_scanner import HybridScanner
    from checkpoint_engine import checkpoint_summary

    html = """
    <!doctype html><html lang='en'><head>
      <title>Example Company — Trusted Local Services and Customer Support</title>
      <meta name='description' content='Trusted local services with clear customer support, experienced professionals, verified reviews and convenient ways to contact our team today.'>
      <meta name='viewport' content='width=device-width, initial-scale=1'>
      <link rel='canonical' href='https://example.com/'>
      <link rel='icon' href='/favicon.ico'>
      <script type='application/ld+json'>{"@type":"LocalBusiness","telephone":"604-555-1212","address":{"@type":"PostalAddress"}}</script>
      <script src='https://www.googletagmanager.com/gtag/js?id=G-TEST'></script>
      <script src='https://connect.facebook.net/en_US/fbevents.js'></script>
    </head><body>
      <h1>Trusted Local Services for Vancouver Customers</h1>
      <a href='tel:6045551212'>Call Us</a>
      <a href='/about'>About Our Team</a><a href='/faq'>FAQ</a><a href='/blog'>Blog</a>
      <a href='/privacy'>Privacy</a><a href='/terms'>Terms</a>
      <a href='https://instagram.com/example'>Instagram</a>
      <a href='https://maps.google.com/?q=123+Main+Street'>Directions</a>
      <p>123 Main Street Vancouver. Licensed and insured. Customer reviews and testimonials from local clients.</p>
      <p>Our team provides detailed service information, pricing context, proof, process information and next steps for customers. </p>
      <p>Frequently asked questions help visitors understand timing, service areas and what happens after they contact us.</p>
      <img src='/team.jpg' alt='Service team' loading='lazy'>
      <form><input name='name'><input name='email'><button type='submit'>Send</button></form>
      <div class='cookie-consent'>Cookie Preferences</div>
    </body></html>
    """
    scanner = HybridScanner()
    scan = scanner._extract_static_html_evidence(html, "https://example.com/", True)
    scan.update(
        {
            "domain": "example.com",
            "is_reachable": True,
            "response_ok": True,
            "status_code": 200,
            "final_url": "https://example.com/",
            "has_ssl": True,
            "https_redirect_enforced": True,
            "browser_loaded": False,
            "scan_quality": {"bot_challenge_suspected": False},
            "sitemap_present": True,
            "robots_valid": True,
            "pagespeed_api_status": "success",
            "performance_score": 86.0,
            "google_seo_score": 95.0,
            "psi_lcp_ms": 2100.0,
            "psi_cls": 0.05,
            "psi_tap_targets_flagged": 0,
            "psi_render_blocking_count": 0,
            "crux_available": False,
            "crux_inp_ms": None,
            "business_profile": {"vertical": "general", "confidence": 1.0},
        }
    )
    scan["h1_relevance_status"] = "PASS"
    checkpoints = ReportGenerator()._build_50_checkpoints(scan, {"business_type": "general", "business_profile": scan["business_profile"]})
    summary = checkpoint_summary(checkpoints)
    assert summary["verified"] >= 35
    assert summary["unknown"] <= 10
    # Static HTML may prove presence, but it must not pretend to verify a sticky mobile CTA.
    cp4 = next(cp for cp in checkpoints if cp["id"] == 4)
    assert cp4["status"] == UNKNOWN


def test_report_always_contains_ten_action_items_without_faking_failures():
    scan = valmont_fixture()
    audit = RevenueScorer().audit_and_score(scan, business_type="general", competitor_data_present=None)
    report = ReportGenerator().generate_admin_master_report(audit, scan)
    assert len(report["top_10_financial_leaks"]) == 10
    assert all("solutions_3_angles" in item for item in report["top_10_financial_leaks"])
    # Non-failure fillers, when needed, must be explicitly labelled instead of masquerading as leaks.
    for item in report["top_10_financial_leaks"]:
        if item.get("finding_type") != "VERIFIED_LEAK":
            assert float(item.get("severity_score") or 0.0) == 0.0


def test_revenue_exposure_has_model_based_dollar_range():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="general", competitor_data_present=None)
    exposure = audit["revenue_leak"]
    assert exposure["estimated_annual_min"] >= 0
    assert exposure["estimated_annual_max"] >= exposure["estimated_annual_min"]
    assert "$" in exposure["est_annual_revenue_leak"]
    assert exposure["model_based"] is True
    assert exposure["measured_revenue_loss"] is False


def test_explicit_general_business_type_stays_general():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="general", competitor_data_present=None)
    assert audit["business_type"] == "general"
    assert audit["business_profile"]["source"] == "explicit_request"


def test_report_archive_writes_json_and_customer_html(tmp_path):
    scan = valmont_fixture()
    audit = RevenueScorer().audit_and_score(scan, business_type="general", competitor_data_present=None)
    reporter = ReportGenerator()
    reporter.vault_dir = str(tmp_path)
    report = reporter.generate_admin_master_report(audit, scan)
    json_path = reporter.archive_to_vault("valmontcafe.com", report, scan)
    assert str(json_path).endswith(".json")
    assert len(list(tmp_path.glob("*.json"))) == 1
    html_files = list(tmp_path.glob("*_report.html"))
    assert len(html_files) == 1
    html_text = html_files[0].read_text(encoding="utf-8")
    assert "10 Highest-Priority Revenue Findings" in html_text
    assert html_text.count("The 3-Angle Remediation Plan") == 10


# ---------------- V6 regression protections ----------------
def test_v5_report_consolidates_performance_family():
    from scorer import RevenueScorer
    scorer = RevenueScorer()
    leaks = [
        {"rule_key":"core_web_vitals","family":"performance","title":"Perf A","description":"a","final_score_loss":2.1,"severity_factor":0.3},
        {"rule_key":"pagespeed_below_60","family":"performance","title":"Perf B","description":"b","final_score_loss":0.64,"severity_factor":0.7},
        {"rule_key":"pagespeed_below_90","family":"performance","title":"Perf C","description":"c","final_score_loss":0.08,"severity_factor":0.4},
    ]
    out = scorer._consolidate_report_families(leaks)
    assert len(out) == 1
    assert out[0]["family"] == "performance"
    assert round(out[0]["final_score_loss"],2) == 2.82
    assert len(out[0]["supporting_rule_keys"]) == 3

def test_v5_unknown_summary_explains_limits():
    from checkpoint_engine import checkpoint_summary, UNKNOWN
    cps=[{"status":UNKNOWN,"unknown_reason_code":"FIELD_DATA_UNAVAILABLE"},{"status":UNKNOWN,"unknown_reason_code":"SAFE_SUBMISSION_LIMIT"}]
    summary=checkpoint_summary(cps)
    assert summary["unknown"] == 2
    assert summary["unknown_breakdown"]["FIELD_DATA_UNAVAILABLE"] == 1
    assert summary["unknown_breakdown"]["SAFE_SUBMISSION_LIMIT"] == 1

def test_v5_commercial_priority_places_conversion_over_search_hygiene():
    from scorer import RevenueScorer
    s=RevenueScorer()
    conversion={"family":"mobile_direct_action","final_score_loss":0.5,"severity_factor":0.4}
    seo={"family":"search_snippet","final_score_loss":2.0,"severity_factor":0.8}
    assert s._commercial_sort_key(conversion) > s._commercial_sort_key(seo)


def test_v5_top_ten_never_repeats_same_underlying_family():
    scan = valmont_fixture()
    scan.update({
        "performance_score": 59.0,
        "pagespeed_api_status": "success",
        "psi_lcp_ms": 3300.0,
        "psi_cls": 0.04,
        "psi_render_blocking_count": 3,
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="general", competitor_data_present=None)
    report = ReportGenerator().generate_admin_master_report(audit, scan)
    families = [str(item.get("family") or item.get("rule_key")) for item in report["top_10_financial_leaks"]]
    assert len(families) == len(set(families))
    assert len([f for f in families if f == "performance"]) <= 1


def test_v5_performance_supporting_signals_are_one_report_card():
    scan = valmont_fixture()
    scan.update({
        "performance_score": 59.0,
        "pagespeed_api_status": "success",
        "psi_lcp_ms": 3300.0,
        "psi_render_blocking_count": 3,
        "lazy_loading_status": FAIL,
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="general", competitor_data_present=None)
    perf = [x for x in audit["tiered_remediation_packages"]["tier_10_arch10"] if x.get("family") == "performance"]
    assert len(perf) == 1
    assert perf[0]["leak_name"] == "Mobile Performance Architecture Drag"
    assert len(perf[0].get("supporting_findings") or []) >= 2


def test_v5_trust_and_search_subsignals_are_also_consolidated():
    scan = base_scan()
    scan.update({
        "reviews_visible": False,
        "social_proof_present": False,
        "trust_badges_present": False,
        "schema_present": False,
        "canonical_present": False,
        "meta_description": "",
        "title": "Short",
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="general", competitor_data_present=None)
    report_families = [x.get("family") for x in audit["tiered_remediation_packages"]["tier_10_arch10"]]
    assert report_families.count("trust_proof") <= 1
    assert report_families.count("search_structure") <= 1
    assert report_families.count("search_snippet") <= 1


def test_v5_primary_mobile_action_replaces_duplicate_photography_checkpoint():
    scan = base_scan()
    scan["mobile_cta_status"] = "verified"
    scan["mobile_primary_cta_present"] = True
    cps = ReportGenerator()._build_50_checkpoints(scan, {"business_type": "general", "business_profile": scan["business_profile"]})
    cp7 = next(cp for cp in cps if cp["id"] == 7)
    cp36 = next(cp for cp in cps if cp["id"] == 36)
    assert cp7["check"] == "Primary Mobile Conversion Action Visible"
    assert cp7["status"] == PASS
    assert cp36["check"] == "Original Photography (Not Stock)"


def test_v6_cookie_absence_is_context_aware():
    scan = base_scan()
    scan["cookie_banner_present"] = False
    # Tracking exists in base_scan, so jurisdiction/consent context is required rather than guessing PASS/FAIL.
    cps = ReportGenerator()._build_50_checkpoints(scan, {"business_type": "general", "business_profile": scan["business_profile"]})
    cp49 = next(cp for cp in cps if cp["id"] == 49)
    assert cp49["status"] == UNKNOWN

    no_tracking = base_scan()
    no_tracking.update({"cookie_banner_present": False, "has_ga4": False, "has_meta_pixel": False, "has_qualitative_analytics": False, "retargeting_pixel_installed": False})
    cps2 = ReportGenerator()._build_50_checkpoints(no_tracking, {"business_type": "general", "business_profile": no_tracking["business_profile"]})
    cp49b = next(cp for cp in cps2 if cp["id"] == 49)
    assert cp49b["status"] == NA


def test_v5_unknown_customer_note_is_explicit_and_unscored():
    scan = base_scan()
    scan.update({"crux_available": False, "crux_inp_ms": None, "custom_photography_status": UNKNOWN})
    audit = RevenueScorer().audit_and_score(scan, business_type="general", competitor_data_present=None)
    report = ReportGenerator().generate_admin_master_report(audit, scan)
    note = report["verification_coverage_note"].lower()
    assert "unknown does not mean failed" in note
    assert "no score deduction" in note
    assert report["checkpoint_summary"]["unknown_breakdown"]


def test_v5_report_customer_order_is_conversion_first():
    scan = base_scan()
    scan.update({
        "mobile_sticky_cta_present": False,
        "mobile_cta_visible": False,
        "mobile_cta_status": "verified",
        "meta_description": "",
        "title": "Short",
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="general", competitor_data_present=None)
    report = ReportGenerator().generate_admin_master_report(audit, scan)
    verified = [x for x in report["top_10_financial_leaks"] if x.get("finding_type") == "VERIFIED_LEAK"]
    fams = [x.get("family") for x in verified]
    assert "mobile_direct_action" in fams
    if "search_snippet" in fams:
        assert fams.index("mobile_direct_action") < fams.index("search_snippet")


def test_v5_methodology_keeps_baymard_informed_conversion_priority():
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="general", competitor_data_present=None)
    text = ReportGenerator()._build_scoring_methodology_explanation(audit)["hygiene_gatekeeping"].lower()
    assert "conversion friction" in text
    assert "ordinary seo hygiene" in text
    assert "baymard-informed" in text
    assert "does not claim full baymard certification" in text

# --- V7 completion regressions: calibration + false-positive hardening ---

def test_action_classifier_rejects_incidental_book_and_order_words():
    from hybrid_scanner import HybridScanner
    assert HybridScanner._classify_action_text("Facebook", "https://facebook.com/example") == "other"
    assert HybridScanner._classify_action_text("Removal Orders", "/immigration/removal-orders/") == "other"
    assert HybridScanner._classify_action_text("Delivery Information", "/delivery/") == "other"
    assert HybridScanner._classify_action_text("Book Appointment", "/appointments/") == "book"
    assert HybridScanner._classify_action_text("Book a Table", "/reservations/") == "reserve"
    assert HybridScanner._classify_action_text("Order Online", "/order-online/") == "order"


def test_booking_action_does_not_manufacture_reservation_context():
    from hybrid_scanner import HybridScanner
    html = """<!doctype html><html><head><title>Clinic</title></head><body>
    <h1>Clinic</h1><a href='/appointments/'>Book Appointment</a><a href='/contact/'>Contact Us</a>
    </body></html>"""
    scan = HybridScanner()._extract_static_html_evidence(html, "https://example.com/", verified=True)
    assert scan["booking_action_present"] is True
    assert scan["reservation_present"] is False
    assert "book" in scan["mobile_cta_types"]


def test_legal_policy_boilerplate_does_not_create_hospitality_context():
    from architecture_model import infer_architecture_profile
    scan = {
        "title": "Vancouver Immigration Lawyers",
        "h1_tags": ["Immigration Lawyers"],
        "meta_description": "Book a consultation with our law firm",
        "page_text": "We reserve the right to update this policy in the event of changes. Legal services and immigration advice.",
        "journey_text_sample": "Contact our lawyers about your immigration legal matter.",
        "forms_present": True,
        "phone_number_visible": True,
        "address_location_visible": True,
        "mobile_cta_types": ["contact"],
    }
    profile = infer_architecture_profile(scan, "auto")
    assert profile["journey_model"] == "appointment_consultation"
    assert "regulated_high_trust" in profile["context_tags"]
    assert "hospitality_event" not in profile["context_tags"]


def test_home_builder_policy_boilerplate_does_not_create_sensitive_or_hospitality_context():
    from architecture_model import infer_architecture_profile
    scan = {
        "title": "Custom Homes Vancouver",
        "h1_tags": ["Custom Home Builder"],
        "meta_description": "Custom home renovation contractor",
        "page_text": "In the event of changes, we reserve the right to update this policy. Legal matter terms may apply. Custom home projects.",
        "journey_text_sample": "Custom homes renovations projects portfolio contact us",
        "forms_present": False,
        "mobile_cta_types": ["contact"],
        "address_location_visible": True,
        "phone_number_visible": True,
    }
    profile = infer_architecture_profile(scan, "auto")
    assert profile["journey_model"] == "lead_quote"
    assert "enterprise_considered_purchase" in profile["context_tags"]
    assert "sensitive_data" not in profile["context_tags"]
    assert "hospitality_event" not in profile["context_tags"]


def test_conversion_readiness_cannot_look_elite_when_journey_is_general():
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="general", competitor_data_present=None)
    metrics = audit["surface_metrics"]
    assert metrics["conversion_metric_status"] == "PROVISIONAL_JOURNEY"
    assert metrics["conversion_efficiency"] == metrics["conversion_path_readiness"]
    assert metrics["conversion_path_readiness"] < 80
    assert audit["business_profile"]["journey_model"] == "general"


def test_surface_layer_indices_reconcile_to_earned_layer_scores():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    layers = audit["analysis_layers"]
    metrics = audit["surface_metrics"]
    expected_foundation = round(100 * layers["common_foundation"]["layer_score"] / layers["common_foundation"]["layer_max"], 1)
    expected_adaptive = round(100 * layers["adaptive_architecture"]["layer_score"] / layers["adaptive_architecture"]["layer_max"], 1)
    assert metrics["common_foundation_index"] == expected_foundation
    assert metrics["adaptive_architecture_index"] == expected_adaptive


def test_score_formula_exposes_canonical_three_layer_arithmetic():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    formula = audit["score_formula"]
    canonical = round(
        formula["foundation_layer_score"]
        + formula["revenue_user_architecture_score"]
        + formula["elite_architecture_score"],
        2,
    )
    assert canonical == formula["canonical_three_layer_score"]
    assert round(RevenueScorer._calibrate_public_score(canonical), 1) == audit["overall_score"]
    assert formula["penalties_already_reflected_in_layer_scores"] is True
    assert "foundation_layer_score" in formula["canonical_formula"]
    assert formula["public_score_formula"] == "piecewise_linear_blueprint90(canonical_three_layer_score)"
    assert formula["public_score_ceiling"] == 90.0


def test_maturity_threshold_is_advisory_not_an_enforced_cap():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    gate = audit["maturity_gate"]
    assert gate["score_cap_enforced"] is False
    assert gate["advisory_score_threshold"] == gate["score_cap"]
    assert "not enforced" in gate["score_cap_semantics"]


def test_report_uses_90_point_blueprint_and_advisory_threshold_language():
    reporter = ReportGenerator()
    scan = valmont_fixture()
    audit = RevenueScorer().audit_and_score(scan, business_type="auto", competitor_data_present=None)
    report = reporter.generate_admin_master_report(audit, scan)
    html = reporter._build_email_html(report)
    assert "/ 78" not in html
    assert "Advisory maturity threshold" in html
    assert "not a score cap" in html
    assert "MATERIAL COMMERCIAL WEAKNESSES (35–45)" == report["score_level_impact"]["level"]
    assert "/ 90" in html


def test_competitor_fallback_query_uses_specific_offering_evidence():
    from hybrid_scanner import HybridScanner
    profile = {
        "journey_model": "lead_quote",
        "journey_signals": ["hero:custom home", "meta:renovation", "action:contact"],
    }
    target_place = {"place_primary_type": "service", "place_types": ["service", "establishment"]}
    query = HybridScanner._competitor_search_query(target_place, profile)
    assert "custom home" in query
    assert "renovation" in query
    assert query != "local service provider"


def test_journey_role_does_not_treat_legal_orders_as_checkout_or_legal_services_as_policy():
    from hybrid_scanner import HybridScanner
    assert HybridScanner._journey_role("https://example.com/legal-services/") == "support"
    assert HybridScanner._journey_role("https://example.com/immigration/removal-orders/") == "support"
    assert HybridScanner._journey_role("https://example.com/privacy-policy/") == "policy"
    assert HybridScanner._journey_role("https://example.com/order-online/") == "commerce_conversion"


def test_revenue_exposure_context_changes_stakes_not_issue_severity():
    leak = {
        "economic_severity": 3.0,
        "intrinsic_severity_score": 3.0,
        "final_score_loss": 1.2,
        "confidence": "high",
        "severity_factor": 0.8,
        "base_impact_weight": 4.0,
    }
    evidence = {"score": 90}
    plain = RevenueScorer._revenue_exposure("lead_quote", [leak], evidence, {"context_tags": []})
    considered = RevenueScorer._revenue_exposure("lead_quote", [leak], evidence, {"context_tags": ["enterprise_considered_purchase"]})
    assert plain["economic_severity_basis"] == considered["economic_severity_basis"] == 3.0
    assert considered["economic_context_multiplier"] > plain["economic_context_multiplier"]
    assert considered["max"] > plain["max"]


def test_conversion_error_confirmation_prefers_revenue_path_over_homepage_or_policy():
    from hybrid_scanner import HybridScanner
    signals = [
        {"key": "recaptcha_invalid_site_key", "url": "https://example.com/"},
        {"key": "recaptcha_invalid_site_key", "url": "https://example.com/privacy-policy/"},
        {"key": "recaptcha_invalid_site_key", "url": "https://example.com/contact/"},
    ]
    assert HybridScanner._select_conversion_error_confirmation_url(signals, {}) == "https://example.com/contact/"

    rendered = {
        "url": "https://example.com/contact/",
        "conversion_error_signals": [{"key": "recaptcha_invalid_site_key"}],
    }
    assert HybridScanner._select_conversion_error_confirmation_url(signals, rendered) == "https://example.com/contact/"


def test_foundation_omission_signal_requires_verified_fail_and_keeps_modal_generic():
    from checkpoint_engine import build_foundation_omission_signal
    checkpoints = [
        {"id": 22, "status": FAIL, "rule_key": "canonical_missing", "check": "Canonical URL Present", "evidence": None},
        {"id": 31, "status": UNKNOWN, "rule_key": "mobile_viewport", "check": "Mobile Viewport Configured", "evidence": None},
    ]
    signal = build_foundation_omission_signal(checkpoints, {"final_url": "https://example.com/", "title": "Example", "browser_loaded": True})
    assert signal["triggered"] is True
    assert signal["count"] == 1
    assert signal["highest_level"] == "BASIC"
    assert signal["public_modal_disclose_items"] is False
    assert "canonical" not in signal["modal_message"].lower()
    assert len(signal["omissions"]) == 1
    assert signal["omissions"][0]["checkpoint_id"] == 22


def test_revenue_path_failure_outweighs_minor_search_hygiene():
    from copy import deepcopy
    strong = base_scan()
    strong.update({
        "title": "Vancouver Home Renovation Contractor",
        "h1_tags": ["Custom Home Renovations"],
        "meta_description": "Custom home renovation contractor. Request a quote.",
        "page_text": "Custom home renovations projects portfolio request a quote contact us Vancouver " * 20,
        "forms_present": True,
        "form_action_valid": True,
        "form_functional_status": PASS,
        "mobile_cta_types": ["quote", "call"],
        "click_to_call_present": True,
        "mobile_primary_cta_present": True,
        "mobile_sticky_cta_present": True,
        "credentials_present": True,
        "trust_badges_present": True,
    })
    minor = deepcopy(strong)
    minor.update({"meta_description": "", "canonical_present": False})
    major = deepcopy(strong)
    major.update({
        "forms_present": False,
        "form_action_valid": False,
        "form_functional_status": FAIL,
        "mobile_primary_cta_present": False,
        "mobile_sticky_cta_present": False,
        "mobile_cta_types": [],
        "click_to_call_present": False,
        "click_to_call_status": "verified",
    })
    scorer = RevenueScorer()
    strong_a = scorer.audit_and_score(strong, business_type="auto", competitor_data_present=None)
    minor_a = scorer.audit_and_score(minor, business_type="auto", competitor_data_present=None)
    major_a = scorer.audit_and_score(major, business_type="auto", competitor_data_present=None)
    minor_drop = strong_a["overall_score"] - minor_a["overall_score"]
    major_drop = strong_a["overall_score"] - major_a["overall_score"]
    assert minor_drop < 3.0
    assert major_drop > 10.0
    assert major_drop > minor_drop * 4
    assert major_a["surface_metrics"]["conversion_path_readiness"] < minor_a["surface_metrics"]["conversion_path_readiness"]


def test_context_hardening_preserves_genuine_hospitality_event_sites():
    from architecture_model import infer_architecture_profile
    profile = infer_architecture_profile({
        "title": "Vancouver Waterfront Wedding Venue",
        "h1_tags": ["Waterfront Wedding Venue"],
        "meta_description": "Reserve your wedding venue and event catering date.",
        "page_text": "Wedding venue banquet event catering reservations.",
        "journey_text_sample": "Book wedding venue reserve event date",
        "forms_present": True,
        "mobile_cta_types": ["reserve"],
        "address_location_visible": True,
    }, "auto")
    assert profile["journey_model"] == "reservation_event"
    assert "hospitality_event" in profile["context_tags"]

# --- V7.2 real-world scorer / economic model completion regressions ---

def _resolved_lead_fixture():
    scan = base_scan()
    scan.update({
        "title": "Vancouver Custom Home Renovation Contractor",
        "h1_tags": ["Custom Home Renovations"],
        "h1_relevance_status": "PASS",
        "meta_description": "Custom home renovation contractor serving Vancouver homeowners. Request a detailed project quote today.",
        "page_text": "Custom home renovations projects portfolio request a quote contact us Vancouver " * 24,
        "forms_present": True,
        "form_action_valid": True,
        "form_functional_status": PASS,
        "mobile_cta_types": ["quote", "call"],
        "click_to_call_present": True,
        "click_to_call_status": "verified",
        "mobile_primary_cta_present": True,
        "mobile_sticky_cta_present": True,
        "mobile_cta_status": "verified",
        "credential_signals_present": True,
        "trust_badges_present": True,
        "reviews_visible": True,
        "social_proof_present": True,
        "about_team_linked": True,
        "case_studies_portfolio_present": True,
        "measurement_platforms": ["Google Analytics / GTM", "Meta Pixel"],
        "measurement_layer_present": True,
        "has_ga4": True,
        "has_meta_pixel": True,
        "retargeting_pixel_installed": True,
    })
    return scan


def test_adaptive_layer_is_non_compensatory_and_pillars_total_60():
    audit = RevenueScorer().audit_and_score(_resolved_lead_fixture(), business_type="auto")
    detail = audit["analysis_layers"]["adaptive_architecture"]["weighted_checkpoint_detail"]
    pillars = detail["pillars"]
    assert round(sum(float(x["max"]) for x in pillars.values()), 2) == 60.0
    assert pillars["conversion_execution"]["max"] == 32.0
    assert pillars["supporting_experience"]["max"] == 4.0
    assert "verified PASS" in detail["method"]


def test_unknown_evidence_cannot_earn_points_but_is_not_a_penalty():
    scan = _resolved_lead_fixture()
    scorer = RevenueScorer()
    resolved = scorer.audit_and_score(scan, business_type="auto")
    unknown = dict(scan)
    unknown.update({
        "mobile_cta_status": "unknown",
        "mobile_sticky_cta_present": False,
        "browser_loaded": False,
        "static_html_verified": True,
    })
    # Static evidence cannot prove persistence. It must not become a FAIL/leak, but it also
    # cannot earn the same conversion-continuity points as a verified rendered PASS.
    audit_unknown = scorer.audit_and_score(unknown, business_type="auto")
    cp4 = next(cp for cp in audit_unknown["full_50_checkpoint_basis"] if cp["id"] == 4)
    assert cp4["status"] == UNKNOWN
    assert not any(x.get("rule_key") == "mobile_sticky_cta" for x in audit_unknown["tiered_remediation_packages"]["all_scoring_leaks"])
    assert audit_unknown["analysis_layers"]["adaptive_architecture"]["layer_score"] < resolved["analysis_layers"]["adaptive_architecture"]["layer_score"]


def test_score_discriminates_poor_mid_strong_without_forced_distribution():
    from copy import deepcopy
    scorer = RevenueScorer()
    strong = _resolved_lead_fixture()
    mid = deepcopy(strong)
    mid.update({
        "performance_score": 62.0,
        "mobile_sticky_cta_present": False,
        "has_meta_pixel": False,
        "retargeting_pixel_installed": False,
        "measurement_platforms": ["Google Analytics / GTM"],
        "trust_badges_present": False,
    })
    poor = deepcopy(strong)
    poor.update({
        "performance_score": 38.0,
        "mobile_primary_cta_present": False,
        "mobile_sticky_cta_present": False,
        "mobile_cta_types": [],
        "click_to_call_present": False,
        "click_to_call_status": "verified",
        "forms_present": False,
        "form_action_valid": False,
        "form_functional_status": FAIL,
        "reviews_visible": False,
        "social_proof_present": False,
        "trust_badges_present": False,
        "case_studies_portfolio_present": False,
        "canonical_present": False,
        "meta_description": "",
    })
    strong_a = scorer.audit_and_score(strong, business_type="auto")
    mid_a = scorer.audit_and_score(mid, business_type="auto")
    poor_a = scorer.audit_and_score(poor, business_type="auto")
    assert poor_a["overall_score"] < mid_a["overall_score"] < strong_a["overall_score"]
    assert strong_a["overall_score"] < 70.0  # good modern sites do not casually become exceptional
    assert poor_a["overall_score"] < 46.0


def test_elite_points_require_strong_core_architecture_first():
    from copy import deepcopy
    scorer = RevenueScorer()
    strong = _resolved_lead_fixture()
    weak_core = deepcopy(strong)
    weak_core.update({
        "mobile_primary_cta_present": False,
        "mobile_sticky_cta_present": False,
        "mobile_cta_types": [],
        "click_to_call_present": False,
        "click_to_call_status": "verified",
    })
    strong_a = scorer.audit_and_score(strong, business_type="auto")
    weak_a = scorer.audit_and_score(weak_core, business_type="auto")
    assert strong_a["analysis_layers"]["elite_architecture"]["eligibility"]["eligible"] is True
    assert weak_a["analysis_layers"]["elite_architecture"]["eligibility"]["eligible"] is False
    assert weak_a["analysis_layers"]["elite_architecture"]["layer_score"] == 0


def test_financial_exposure_v2_uses_opportunity_pool_not_score_points():
    leak = {
        "rule_key": "conversion_path_error",
        "family": "conversion_execution",
        "economic_severity": 4.0,
        "intrinsic_severity_score": 4.0,
        "final_score_loss": 1.0,
        "confidence": "high",
        "severity_factor": 1.0,
        "substitution_factor": 1.0,
    }
    evidence = {"score": 95}
    modeled = RevenueScorer._revenue_exposure(
        "lead_quote", [leak], evidence, {"context_tags": []},
        {"economic_inputs": {"annual_digital_commercial_value": 100000}},
    )
    changed_score_loss = dict(leak)
    changed_score_loss["final_score_loss"] = 9.0
    modeled_changed = RevenueScorer._revenue_exposure(
        "lead_quote", [changed_score_loss], evidence, {"context_tags": []},
        {"economic_inputs": {"annual_digital_commercial_value": 100000}},
    )
    assert modeled["model_version"] == "commercial_exposure_v2"
    assert modeled["basis"] == "business_input_annual_digital_commercial_value"
    assert modeled["annual_digital_opportunity_pool"]["low"] == 100000
    assert modeled["combined_path_impairment_pct"] == modeled_changed["combined_path_impairment_pct"]
    assert modeled["max"] == modeled_changed["max"]
    assert modeled["verified_penalty_basis"] != modeled_changed["verified_penalty_basis"]


def test_financial_exposure_compounds_overlap_and_measurement_is_low_causality():
    evidence = {"score": 95}
    perf_a = {
        "rule_key": "core_web_vitals", "family": "performance", "economic_severity": 2.0,
        "final_score_loss": 1.0, "confidence": "high", "severity_factor": 0.8, "substitution_factor": 1.0,
    }
    perf_b = {
        "rule_key": "pagespeed_below_90", "family": "performance", "economic_severity": 1.0,
        "final_score_loss": 0.2, "confidence": "high", "severity_factor": 0.5, "substitution_factor": 1.0,
    }
    exposure = RevenueScorer._revenue_exposure("lead_quote", [perf_a, perf_b], evidence, {"context_tags": []})
    assert exposure["family_impairment"]["performance"] <= 0.20
    assert exposure["combined_path_impairment_pct"] < 20.0

    measurement = {
        "rule_key": "measurement_telemetry", "family": "measurement", "economic_severity": 2.0,
        "final_score_loss": 1.0, "confidence": "high", "severity_factor": 1.0, "substitution_factor": 1.0,
    }
    conversion = {
        "rule_key": "conversion_path_error", "family": "conversion_execution", "economic_severity": 2.0,
        "final_score_loss": 1.0, "confidence": "high", "severity_factor": 1.0, "substitution_factor": 1.0,
    }
    m = RevenueScorer._revenue_exposure("lead_quote", [measurement], evidence, {"context_tags": []})
    c = RevenueScorer._revenue_exposure("lead_quote", [conversion], evidence, {"context_tags": []})
    assert c["combined_path_impairment_pct"] > m["combined_path_impairment_pct"] * 10
    assert c["max"] > m["max"] * 5


def test_competitor_probe_rejects_google_type_vs_content_category_conflict():
    from hybrid_scanner import HybridScanner
    competitor = {
        "name": "Example Construction Ltd",
        "primary_type": "general_contractor",
        "place_types": ["general_contractor", "service", "establishment"],
    }
    signals = {
        "title": "Vancouver Physiotherapy Clinic",
        "meta_description": "Book physiotherapy and rehabilitation treatment.",
        "h1_tags": ["Physiotherapy & Sports Rehab"],
        "page_text": "Our physiotherapists treat patients with sports injuries and rehabilitation plans.",
    }
    profile = {"journey_model": "appointment_consultation", "context_tags": ["regulated_high_trust"]}
    result = HybridScanner._competitor_probe_identity_check(competitor, signals, profile)
    assert result["expected_category"] == "construction_trades"
    assert result["observed_category"] == "healthcare"
    assert result["conflict"] is True


def test_nearby_search_uses_primary_type_and_retries_without_bad_filter():
    from hybrid_scanner import HybridScanner

    class Resp:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload
            self.text = str(payload)
        def json(self):
            return self._payload

    class FakeSession:
        def __init__(self):
            self.calls = []
            self.responses = [
                Resp(400, {"error": {"message": "invalid type filter"}}),
                Resp(200, {"places": []}),
                Resp(200, {"places": []}),
            ]
        def post(self, url, json=None, headers=None, timeout=None):
            self.calls.append((url, dict(json or {})))
            return self.responses.pop(0)

    scanner = HybridScanner(google_api_key="test-key")
    fake = FakeSession()
    scanner.session = fake
    target = {
        "places_found": True,
        "benchmark_identity_verified": True,
        "place_location": {"latitude": 49.28, "longitude": -123.12},
        "place_primary_type": "general_contractor",
        "place_types": ["general_contractor", "service"],
        "place_id": "target",
        "place_website_uri": "https://target.example/",
        "place_display_name": "Target Builder",
    }
    profile = {
        "journey_model": "lead_quote", "provisional": False,
        "journey_signals": ["hero:custom home", "meta:renovation"], "context_tags": ["local_location_dependent"],
    }
    scanner._fetch_local_competitors(target, profile, {"domain": "target.example"})
    first_body = fake.calls[0][1]
    retry_body = fake.calls[1][1]
    assert first_body["includedPrimaryTypes"] == ["general_contractor"]
    assert "includedTypes" not in first_body
    assert "includedPrimaryTypes" not in retry_body


def test_financial_exposure_is_explicitly_scenario_based_without_business_inputs():
    leak = {
        "rule_key": "core_web_vitals", "family": "performance", "economic_severity": 2.0,
        "final_score_loss": 1.0, "confidence": "high", "severity_factor": 0.7, "substitution_factor": 1.0,
    }
    result = RevenueScorer._revenue_exposure("lead_quote", [leak], {"score": 90}, {"context_tags": ["enterprise_considered_purchase"]})
    assert result["basis"] == "journey_scenario"
    assert result["assumptions"]["monthly_high_intent_opportunity_range"]
    assert result["annual_digital_opportunity_pool"]["high"] > result["annual_digital_opportunity_pool"]["low"]
    assert "not measured accounting loss" in result["method_note"].lower()


def test_hasler_style_strong_trust_but_unverified_completion_is_not_scored_too_generously():
    from copy import deepcopy
    scan = _resolved_lead_fixture()
    scan.update({
        "performance_score": 45.0,
        "mobile_sticky_cta_present": False,
        "mobile_cta_types": ["contact"],
        "forms_present": False,
        "form_action_valid": None,
        "form_functional_status": NA,
        "journey_pages_verified": 5,
        "h1_tags": ["Vancouver Custom Home Builder", "Vancouver Custom Home Builder"],
        "h1_dom_count": 2,
        "missing_alt_images": 1,
        "images_with_alt": 2,
        "image_count": 3,
        "total_images": 3,
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="auto")
    cp50 = next(cp for cp in audit["full_50_checkpoint_basis"] if cp["id"] == 50)
    assert cp50["status"] == UNKNOWN
    assert cp50["unknown_reason_code"] == "SAFE_SUBMISSION_LIMIT"
    assert 35.0 <= audit["overall_score"] <= 44.0
    assert audit["analysis_layers"]["elite_architecture"]["layer_score"] == 0
    assert audit["analysis_layers"]["adaptive_architecture"]["weighted_checkpoint_detail"]["pillars"]["conversion_execution"]["score"] < 24.0


def test_provisional_conversion_readiness_cannot_present_as_near_perfect():
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="auto")
    metrics = audit["surface_metrics"]
    assert metrics["conversion_metric_status"] == "PROVISIONAL_JOURNEY"
    assert metrics["conversion_path_readiness"] <= 85.0
    assert metrics["conversion_metric_components"]["journey_resolution_factor"] < 1.0


def test_financial_exposure_supports_analytics_backed_expected_value_pool():
    leak = {
        "rule_key": "conversion_path_error", "family": "conversion_execution",
        "economic_severity": 4.0, "final_score_loss": 2.0, "confidence": "high",
        "severity_factor": 1.0, "substitution_factor": 1.0,
    }
    result = RevenueScorer._revenue_exposure(
        "lead_quote", [leak], {"score": 95}, {"context_tags": []},
        {"economic_inputs": {
            "monthly_commercial_path_sessions": 1000,
            "expected_conversion_rate": 0.05,
            "expected_value_per_conversion": 1000,
        }},
    )
    assert result["basis"] == "business_input_commercial_path_analytics"
    assert result["annual_digital_opportunity_pool"] == {"low": 600000, "high": 600000}
    assert result["central_annual_exposure"] > 0
    assert result["rounding_increment"] in {100, 500}


def test_scenario_financial_exposure_avoids_false_hundred_dollar_precision():
    leak = {
        "rule_key": "core_web_vitals", "family": "performance",
        "economic_severity": 2.0, "final_score_loss": 1.0, "confidence": "high",
        "severity_factor": 0.7, "substitution_factor": 1.0,
    }
    result = RevenueScorer._revenue_exposure("lead_quote", [leak], {"score": 90}, {"context_tags": []})
    assert result["basis"] == "journey_scenario"
    assert result["rounding_increment"] >= 500
    assert result["min"] % result["rounding_increment"] == 0
    assert result["max"] % result["rounding_increment"] == 0
    assert result["confidence"] == "SCENARIO"
    assert result["confidence_score"] is None
    assert result["economic_input_confidence"] == "SCENARIO_PRIOR"
    assert "not universal empirical" in result["causal_calibration_note"].lower()


def test_admin_auth_module_roundtrip_without_storing_plain_otp(monkeypatch):
    import re
    import admin_auth as authmod

    monkeypatch.setenv("ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setenv("TRILLOKA_ADMIN_SESSION_SECRET", "test-session-secret-that-is-long-enough-for-hmac")
    captured = {}

    class Resp:
        status_code = 202
        text = "ok"

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = dict(json or {})
        return Resp()

    monkeypatch.setattr(authmod.requests, "post", fake_post)
    manager = authmod.AdminAuthManager()
    assert manager.configured is True
    challenge = manager.request_code("127.0.0.1")
    assert "@example.com" in challenge.destination
    html = captured["payload"]["html"]
    code = re.search(r">(\d{6})<", html).group(1)
    # The signed browser challenge contains only the HMAC of the OTP, never the plain code.
    assert code not in challenge.token
    session = manager.verify_code(code, challenge.token, "127.0.0.1")
    assert manager.validate_session(session.token) is True
    assert manager.session_status(session.token)["authenticated"] is True
    manager.revoke_session(session.token)
    assert manager.validate_session(session.token) is False


def test_requirements_include_email_validator_for_emailstr():
    """Production requirements must include the dependency Pydantic EmailStr imports at model construction."""
    from pathlib import Path
    requirements = (Path(__file__).resolve().parent / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "email-validator" in requirements or "pydantic[email]" in requirements



def test_network_security_blocks_classic_ssrf_targets(monkeypatch):
    import socket
    import pytest
    import network_security as ns

    blocked = [
        "http://127.0.0.1/",
        "http://127.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.10/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://0177.0.0.1/",
        "http://100.64.0.1/",
        "http://224.0.0.1/",
        "https://localhost/",
        "https://service.local/",
        "file:///etc/passwd",
        "ftp://example.com/file",
        "https://user:pass@example.com/",
        "https://example.com:22/",
    ]
    for target in blocked:
        with pytest.raises(ns.NetworkTargetError):
            ns.validate_public_http_url(target)


def test_network_security_rejects_hostname_that_dns_resolves_private(monkeypatch):
    import socket
    import pytest
    import network_security as ns

    def fake_getaddrinfo(host, port, family=0, type=0, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.23.4.5", port))]

    monkeypatch.setattr(ns.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ns.NetworkTargetError) as exc:
        ns.validate_public_http_url("https://public-looking.example/")
    assert exc.value.reason == "NON_PUBLIC_ADDRESS"


def test_network_security_rejects_mixed_public_private_dns(monkeypatch):
    import socket
    import pytest
    import network_security as ns

    def fake_getaddrinfo(host, port, family=0, type=0, proto=0):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port)),
        ]

    monkeypatch.setattr(ns.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ns.NetworkTargetError) as exc:
        ns.validate_public_http_url("https://mixed.example/")
    assert exc.value.reason == "NON_PUBLIC_ADDRESS"


def test_safe_http_revalidates_redirect_before_following(monkeypatch):
    import socket
    import pytest
    import network_security as ns

    def fake_getaddrinfo(host, port, family=0, type=0, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))]

    monkeypatch.setattr(ns.socket, "getaddrinfo", fake_getaddrinfo)

    class FakeClient(ns.SafeHTTPClient):
        def __init__(self):
            super().__init__()
            self.calls = 0
        def _request_once(self, target, *, timeout, headers, max_bytes):
            self.calls += 1
            return ns.SafeHTTPResponse(
                302,
                target.url,
                {"Location": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"},
                b"",
            )

    client = FakeClient()
    with pytest.raises(ns.NetworkTargetError) as exc:
        client.get("https://safe.example/")
    assert exc.value.reason == "NON_PUBLIC_ADDRESS"
    assert client.calls == 1


def test_safe_http_connects_to_validated_ip_not_second_dns_lookup(monkeypatch):
    import socket
    import network_security as ns

    def fake_getaddrinfo(host, port, family=0, type=0, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))]

    monkeypatch.setattr(ns.socket, "getaddrinfo", fake_getaddrinfo)
    captured = {}

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        def read(self, amount, decode_content=True):
            return b"<html>ok</html>"
        def release_conn(self):
            pass

    class FakePool:
        def __init__(self, **kwargs):
            captured["pool"] = kwargs
        def request(self, method, target, headers=None, **kwargs):
            captured["method"] = method
            captured["target"] = target
            captured["headers"] = dict(headers or {})
            return FakeResponse()
        def close(self):
            pass

    monkeypatch.setattr(ns.urllib3, "HTTPSConnectionPool", FakePool)
    response = ns.SafeHTTPClient().get("https://safe.example/path?q=1", allow_redirects=False)
    assert response.status_code == 200
    assert captured["pool"]["host"] == "93.184.216.34"
    assert captured["pool"]["server_hostname"] == "safe.example"
    assert captured["pool"]["assert_hostname"] == "safe.example"
    assert captured["headers"]["Host"] == "safe.example"


def test_websocket_network_guard_blocks_internal_targets():
    import pytest
    import network_security as ns

    with pytest.raises(ns.NetworkTargetError):
        ns.validate_public_websocket_url("ws://127.0.0.1:80/socket")
    with pytest.raises(ns.NetworkTargetError):
        ns.validate_public_websocket_url("wss://localhost/socket")


def test_network_security_module_is_in_runtime_manifest():
    from pathlib import Path
    root = Path(__file__).resolve().parent
    requirements = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    assert (root / "network_security.py").exists()
    assert "urllib3" in requirements



def test_browser_cross_origin_policy_blocks_attacker_controlled_hosts(monkeypatch):
    import network_security as ns

    monkeypatch.delenv("TRILLOKA_BROWSER_TRUSTED_HOSTS", raising=False)
    assert ns.browser_cross_origin_host_allowed("www.target.example", "www.target.example") is True
    assert ns.browser_cross_origin_host_allowed("fonts.gstatic.com", "www.target.example") is True
    assert ns.browser_cross_origin_host_allowed("cdn.jsdelivr.net", "www.target.example") is True
    assert ns.browser_cross_origin_host_allowed("rebind.attacker.example", "www.target.example") is False
    assert ns.browser_cross_origin_host_allowed("internal.target.example", "www.target.example") is False


def test_browser_cross_origin_policy_admin_extension_is_explicit(monkeypatch):
    import network_security as ns

    monkeypatch.setenv("TRILLOKA_BROWSER_TRUSTED_HOSTS", "assets.customer-cdn.example")
    assert ns.browser_cross_origin_host_allowed("assets.customer-cdn.example", "www.target.example") is True
    assert ns.browser_cross_origin_host_allowed("evil.assets.customer-cdn.example", "www.target.example") is True
    assert ns.browser_cross_origin_host_allowed("customer-cdn.example.evil.test", "www.target.example") is False



def test_security_blocked_browser_resources_cannot_create_false_negative_leaks():
    from hybrid_scanner import HybridScanner

    scanner = HybridScanner()
    static = {
        "static_html_verified": True,
        "static_html_error": "",
        "forms_present": False,
        "mobile_cta_status": "unknown",
    }
    dom = {
        "browser_loaded": True,
        "dom_complete": True,
        "page_text": "A rendered page with enough visible text for normal evidence collection.",
        "bot_challenge_suspected": False,
        "browser_blocked_request_count": 2,
        "browser_network_restricted": True,
        "forms_present": False,
        "mobile_cta_status": "partial",
        "mobile_primary_cta_present": None,
        "mobile_sticky_cta_present": None,
        "mobile_cta_visible": None,
        "mobile_cta_types": [],
    }
    assert scanner._dom_evidence_complete(dom) is False
    merged = scanner._merge_static_and_dom(static, dom)
    assert merged["forms_present"] is None
    assert merged["mobile_primary_cta_present"] is None
    assert merged["mobile_sticky_cta_present"] is None
    assert merged["mobile_cta_status"] == "partial"


def test_public_score_blueprint_anchor_ranges_are_monotonic_and_capped_at_90():
    anchors = [
        (26, 26), (32, 32), (40, 35), (55, 40), (65, 42), (70.5, 44),
        (73, 46), (80, 57), (85, 59), (90, 69), (95, 80), (100, 90),
    ]
    values = [RevenueScorer._calibrate_public_score(x) for x, _ in anchors]
    assert values == [float(y) for _, y in anchors]
    assert all(a < b for a, b in zip(values, values[1:]))
    assert RevenueScorer._calibrate_public_score(1000) == 90.0


def test_transaction_and_subscription_completion_are_unknown_without_live_submission():
    for journey, text, extras in [
        ("direct_purchase", "shop now add to cart checkout buy now product shipping returns " * 12, {"add_to_cart_visible": True, "checkout_context_detected": True, "order_online_present": True}),
        ("membership_subscription", "join now membership subscribe member benefits pricing community " * 12, {"pricing_linked": True}),
    ]:
        scan = base_scan()
        scan.update({
            "title": text[:55], "page_text": text, "journey_text_sample": text,
            "forms_present": False, "journey_pages_verified": 0,
            "mobile_primary_cta_present": True,
            "mobile_cta_types": ["buy"] if journey == "direct_purchase" else ["join", "subscribe"],
            **extras,
        })
        audit = RevenueScorer().audit_and_score(scan, business_type="auto")
        assert audit["architecture_profile"]["journey_model"] == journey
        cp50 = next(cp for cp in audit["full_50_checkpoint_basis"] if cp["id"] == 50)
        assert cp50["status"] == UNKNOWN
        assert cp50["unknown_reason_code"] == "SAFE_SUBMISSION_LIMIT"
        assert audit["surface_metrics"]["conversion_path_readiness"] < 100.0


def test_safe_non_destructive_completion_evidence_can_verify_checkpoint_50():
    scan = base_scan()
    text = "shop now add to cart checkout buy now product shipping returns " * 12
    scan.update({
        "title": "Shop Online", "page_text": text, "journey_text_sample": text,
        "forms_present": False, "mobile_primary_cta_present": True, "mobile_cta_types": ["buy"],
        "add_to_cart_visible": True, "checkout_context_detected": True, "order_online_present": True,
        "conversion_completion_verified": True,
        "conversion_completion_verification_source": "business-supplied analytics / verified test transaction",
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="auto")
    cp50 = next(cp for cp in audit["full_50_checkpoint_basis"] if cp["id"] == 50)
    assert cp50["status"] == PASS
    assert cp50["evidence"]["completion_verified"] is True


def test_crux_good_reduces_financial_performance_impairment_without_hiding_lab_finding():
    leak = {
        "rule_key": "mobile_lab_performance", "family": "performance",
        "economic_severity": 1.15, "intrinsic_severity_score": 1.15,
        "final_score_loss": 1.05, "confidence": "high",
        "severity_factor": 0.4, "substitution_factor": 1.0,
    }
    field_good = RevenueScorer._revenue_exposure(
        "lead_quote", [leak], {"score": 98.0}, {"context_tags": ["enterprise_considered_purchase"]},
        {"performance_score": 54, "crux_available": True, "real_user_speed_grade": "GOOD"},
    )
    lab_only = RevenueScorer._revenue_exposure(
        "lead_quote", [leak], {"score": 98.0}, {"context_tags": ["enterprise_considered_purchase"]},
        {"performance_score": 54, "crux_available": False, "real_user_speed_grade": "UNKNOWN"},
    )
    assert field_good["family_impairment"]["performance"] == 0.014
    assert lab_only["family_impairment"]["performance"] == 0.04
    assert field_good["issue_components"][0]["field_performance_override"] is True
    assert field_good["combined_path_impairment_pct"] < lab_only["combined_path_impairment_pct"]


def test_blueprint_ratings_match_requested_public_bands():
    expected = [
        (25.0, "CRITICAL REVENUE ARCHITECTURE WEAKNESS"),
        (26.0, "BROKEN / HIGH-RISK COMMERCIAL ARCHITECTURE"),
        (35.0, "MATERIAL COMMERCIAL WEAKNESSES"),
        (46.0, "FUNCTIONAL COMMERCIAL WEBSITE"),
        (59.0, "STRONG COMMERCIAL WEBSITE"),
        (70.0, "GENUINELY EXCEPTIONAL OBSERVABLE ARCHITECTURE"),
        (80.0, "NEAR-PERFECT VERIFIED OBSERVABLE ARCHITECTURE"),
    ]
    for score, label in expected:
        assert RevenueScorer._get_score_rating(score, {}, 0.0, {}, {}) == label


def test_multiservice_b2b_primary_surface_outranks_secondary_medical_service_words():
    from architecture_model import infer_architecture_profile

    scan = {
        "title": "Remote Alaskan Services",
        "h1_tags": ["We've Got You Covered"],
        "meta_description": "Remote support services for exploration and production operations.",
        "page_text": (
            "support services oil and gas industry exploration production activities remote operations "
            "logistics drilling aviation project support clients remote medical services remote medical clinic sets "
            "contact headquarters phone"
        ),
        # Deliberately contaminate the bounded journey sample with a medical service line.
        "journey_text_sample": (
            "remote medical services medical clinic consultation occupational health technician "
            "drug alcohol testing logistics drilling support contact"
        ),
        "forms_present": False,
        "phone_number_visible": True,
        "mobile_cta_types": ["contact"],
        "booking_provider_links": [],
        "booking_action_present": False,
        "reservation_present": False,
    }
    profile = infer_architecture_profile(scan, "auto")

    assert profile["journey_model"] == "lead_quote"
    assert profile["provisional"] is False
    assert profile["score_candidates"]["lead_quote"] > profile["score_candidates"]["appointment_consultation"]
    assert profile["classification_guardrails"]["diversified_b2b_pattern"] is True
    assert profile["classification_guardrails"]["secondary_service_suppression_applied"] is True
    assert "enterprise_considered_purchase" in profile["context_tags"]
    assert "regulated_high_trust" not in profile["context_tags"]


def test_genuine_primary_clinic_still_classifies_as_appointment_after_multiservice_guardrail():
    from architecture_model import infer_architecture_profile

    scan = {
        "title": "Vancouver Physiotherapy Clinic",
        "h1_tags": ["Physiotherapy & Sports Rehabilitation"],
        "meta_description": "Book an appointment with a physiotherapist.",
        "page_text": "new patient physiotherapy treatment schedule appointment clinic team contact",
        "journey_text_sample": "book appointment patient intake physiotherapy consultation",
        "forms_present": True,
        "phone_number_visible": True,
        "mobile_cta_types": ["book", "contact"],
        "booking_action_present": True,
        "booking_provider_links": ["https://booking.example.com/"],
    }
    profile = infer_architecture_profile(scan, "auto")

    assert profile["journey_model"] == "appointment_consultation"
    assert "regulated_high_trust" in profile["context_tags"]
    assert profile["classification_guardrails"]["verified_booking_action"] is True


def test_fairweather_style_lead_scenario_uses_b2b_financial_priors_not_appointment_priors():
    leaks = [
        {
            "rule_key": "privacy_terms_missing", "family": "trust_policy",
            "economic_severity": 0.89, "intrinsic_severity_score": 0.89,
            "final_score_loss": 0.89, "confidence": "high",
            "severity_factor": 0.50, "substitution_factor": 1.0,
        },
        {
            "rule_key": "structured_data_missing", "family": "search_structure",
            "economic_severity": 0.25, "intrinsic_severity_score": 0.25,
            "final_score_loss": 0.18, "confidence": "high",
            "severity_factor": 0.45, "substitution_factor": 1.0,
        },
        {
            "rule_key": "meta_description_length", "family": "search_snippet",
            "economic_severity": 0.04, "intrinsic_severity_score": 0.04,
            "final_score_loss": 0.04, "confidence": "high",
            "severity_factor": 0.30, "substitution_factor": 1.0,
        },
    ]
    profile = {
        "journey_model": "lead_quote",
        "journey_label": "Lead / Quote",
        "context_tags": ["enterprise_considered_purchase", "local_location_dependent"],
    }
    result = RevenueScorer._revenue_exposure(
        "lead_quote", leaks, {"score": 70.6}, profile,
        {"crux_available": True, "real_user_speed_grade": "GOOD"},
    )

    assert result["journey_model"] == "lead_quote"
    assert result["journey_label"] == "Lead / Quote"
    assert result["annual_digital_opportunity_pool"] == {"low": 18750, "high": 324000}
    assert result["economic_context_multiplier"] == 1.25
    assert result["economic_context_tags"] == ["enterprise_considered_purchase"]
    assert result["combined_path_impairment_pct"] == 4.4
    assert result["central_annual_exposure"] == 7500
    assert result["display"] == "$500 – $16,500 / year — LOW scenario exposure"


def test_privacy_finding_copy_does_not_assume_healthcare_when_tracking_is_the_basis():
    title, copy = RevenueScorer._checkpoint_failure_copy({
        "rule_key": "privacy_terms_missing",
        "check": "Privacy Policy Linked for Data Collection",
        "evidence": {"requirement": "privacy_only", "privacy_policy_linked": None, "terms_linked": None},
    })
    assert title == "Privacy Policy Trust Gap"
    assert "measurement/tracking" in copy
    assert "healthcare context" not in copy.lower()


def test_unsupported_nearby_type_forces_specific_text_search_even_when_untyped_retry_has_results():
    from hybrid_scanner import HybridScanner

    class Resp:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload
            self.text = str(payload)
        def json(self):
            return self._payload

    class FakeSession:
        def __init__(self):
            self.calls = []
            self.responses = [
                Resp(400, {"error": {"message": "Unsupported types: general_contractor."}}),
                Resp(200, {"places": [{
                    "id": "irrelevant", "displayName": {"text": "Nearby Hospital"},
                    "primaryType": "general_hospital", "types": ["general_hospital"],
                    "formattedAddress": "North Vancouver, BC"
                }]}),
                Resp(200, {"places": [{
                    "id": "builder", "displayName": {"text": "Relevant Custom Builder"},
                    "primaryType": "home_builder", "types": ["home_builder", "general_contractor"],
                    "formattedAddress": "North Vancouver, BC"
                }]}),
            ]
        def post(self, url, json=None, headers=None, timeout=None):
            self.calls.append((url, dict(json or {})))
            return self.responses.pop(0)

    scanner = HybridScanner(google_api_key="test-key")
    scanner.session = FakeSession()
    target = {
        "places_found": True,
        "benchmark_identity_verified": True,
        "place_location": {"latitude": 49.28, "longitude": -123.12},
        "place_primary_type": "general_contractor",
        "place_types": ["general_contractor", "service"],
        "place_id": "target",
        "place_website_uri": "https://target.example/",
        "place_display_name": "Target Builder",
    }
    profile = {
        "journey_model": "lead_quote", "provisional": False,
        "journey_signals": ["hero:custom home", "meta:renovation"],
        "context_tags": ["local_location_dependent", "enterprise_considered_purchase"],
    }
    result = scanner._fetch_local_competitors(target, profile, {"domain": "target.example"})
    assert len(scanner.session.calls) == 3
    assert "places:searchText" in scanner.session.calls[2][0]
    assert scanner.session.calls[2][1]["textQuery"] == "general contractor custom home renovation"
    assert result["nearby_type_filter_rejected"] is True
    assert result["text_search_status"] == "http_200"
    assert result["competitor_search_strategy"] == "typed_nearby_rejected+specific_text"
    assert result["competitors"][0]["name"] == "Relevant Custom Builder"


def test_missing_alt_accessibility_failure_triggers_generic_foundation_notice():
    from checkpoint_engine import build_foundation_omission_signal
    checkpoints = [{
        "id": 34, "status": FAIL, "rule_key": "missing_alt_images",
        "check": "Images Have Accessibility Text", "evidence": {"missing": 1, "total": 20},
    }]
    signal = build_foundation_omission_signal(
        checkpoints,
        {"final_url": "https://example.com/", "title": "Example", "browser_loaded": True},
    )
    assert signal["triggered"] is True
    assert signal["count"] == 1
    assert signal["highest_level"] == "BASIC"
    assert signal["public_modal_disclose_items"] is False
    assert "alt" not in signal["modal_message"].lower()
    assert signal["omissions"][0]["checkpoint_id"] == 34
    assert "Accessibility" in signal["omissions"][0]["title"]


def test_crux_good_uses_lab_performance_semantics_not_core_web_vitals_failure():
    scan = _resolved_lead_fixture()
    scan.update({
        "performance_score": 39.0,
        "pagespeed_api_status": "success",
        "crux_available": True,
        "real_user_speed_grade": "GOOD",
        "crux_lcp_ms": 1604.0,
        "crux_inp_ms": 40.0,
        "crux_cls": 0.0,
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="auto")
    leaks = audit["tiered_remediation_packages"]["all_scoring_leaks"]
    lab = next(item for item in leaks if item.get("rule_key") == "mobile_lab_performance")
    assert lab["leak_name"] == "Mobile Lab Performance Headroom"
    assert "field data is GOOD" in lab["impact_summary"]
    assert not any(
        item.get("rule_key") == "core_web_vitals" and "Poor Real-User" not in str(item.get("title") or "")
        for item in leaks
    )
    financial = audit["financial_exposure"]
    component = next(item for item in financial["issue_components"] if item["rule_key"] == "mobile_lab_performance")
    assert component["field_performance_override"] is True
    assert component["causal_impairment_ceiling"] == 0.035
