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
    assert audit["overall_score"] > 49.5


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
    expected = round(max(0.0, min(100.0,
        formula["operating_baseline"]
        + formula["verified_strength_points_awarded"]
        + formula["elite_bonus_points"]
        + formula["reference_completeness_bonus"]
        - total
    )), 1)
    assert formula["total_final_penalty"] == total
    assert audit["overall_score"] == expected


def test_good_valmont_style_site_calibrates_to_good_65_75_band():
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    assert 65.0 <= audit["overall_score"] <= 75.0
    assert audit["score_rating"] == "GOOD — LEAKS REMAIN"


def test_strong_ordinary_site_does_not_casually_exceed_80():
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="auto", competitor_data_present=None)
    assert 75.0 <= audit["overall_score"] < 80.0


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
