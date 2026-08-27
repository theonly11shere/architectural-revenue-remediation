"""Trilloka V7.2.2 launch-candidate real-world scanner integrity runner.

Runs the current Journey + Context scanner/scorer regression suite and targeted
calibration/hardening checks.  Everything here is passive and offline: it performs
no live customer submissions and does not require Google credentials or network access.
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path
from copy import deepcopy

from architecture_model import infer_architecture_profile
from checkpoint_engine import FAIL, UNKNOWN, build_50_checkpoints, build_foundation_omission_signal
from hybrid_scanner import HybridScanner
from report_engine import ReportGenerator
from scorer import RevenueScorer
from test_regressions import (
    base_scan, valmont_fixture, _resolved_lead_fixture,
    test_unsupported_nearby_type_forces_specific_text_search_even_when_untyped_retry_has_results,
    test_missing_alt_accessibility_failure_triggers_generic_foundation_notice,
    test_crux_good_uses_lab_performance_semantics_not_core_web_vitals_failure,
)

ROOT = Path(__file__).resolve().parent
CORE_FILES = (
    "architecture_model.py",
    "behavioural_engine.py",
    "checkpoint_engine.py",
    "hybrid_scanner.py",
    "scorer.py",
    "report_engine.py",
    "main.py",
    "admin_auth.py",
    "scan_access.py",
    "scraper.py",
    "network_security.py",
)


def check(name: str, fn) -> bool:
    try:
        fn()
        print(f"[PASS] {name}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def test_compile() -> None:
    for filename in CORE_FILES:
        py_compile.compile(str(ROOT / filename), doraise=True)
    proc = subprocess.run(
        [sys.executable, "-W", "error", "-m", "py_compile", *CORE_FILES],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode:
        raise AssertionError((proc.stdout + "\n" + proc.stderr).strip())


def test_pytest_regressions() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_regressions.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode:
        raise AssertionError((proc.stdout + "\n" + proc.stderr).strip())
    print("       " + proc.stdout.strip().replace("\n", "\n       "))



def test_main_runtime_import() -> None:
    import main as gateway
    assert gateway.app.version == "7.2.2"
    assert gateway.scanner.ENGINE_VERSION == "v7.2.2"
    assert gateway.PLAN_CATALOG["essential_350"]["remediation_limit"] == 4
    assert gateway.PLAN_CATALOG["advanced_550"]["remediation_limit"] == 8



def test_deployment_dependency_manifest() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    if "email-validator" not in requirements and "pydantic[email]" not in requirements:
        raise AssertionError(
            "Pydantic EmailStr is used by main.py, but requirements.txt does not install email-validator"
        )



def test_network_target_ssrf_hardening() -> None:
    from network_security import NetworkTargetError, validate_public_http_url

    for target in (
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://[::1]/",
        "https://localhost/",
        "https://service.local/",
        "file:///etc/passwd",
        "https://user:pass@example.com/",
        "https://example.com:22/",
    ):
        try:
            validate_public_http_url(target)
        except NetworkTargetError:
            continue
        raise AssertionError(f"unsafe network target was accepted: {target}")

    source = (ROOT / "hybrid_scanner.py").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "self.safe_http.get" in source
    assert 'service_workers="block"' in source
    assert "host-resolver-rules" in source
    assert "validate_public_websocket_url" in source
    assert "urllib3" in requirements


def test_browser_cross_origin_fail_closed() -> None:
    from network_security import browser_cross_origin_host_allowed

    assert browser_cross_origin_host_allowed("www.target.example", "www.target.example") is True
    assert browser_cross_origin_host_allowed("fonts.gstatic.com", "www.target.example") is True
    assert browser_cross_origin_host_allowed("rebind.attacker.example", "www.target.example") is False
    assert browser_cross_origin_host_allowed("internal.target.example", "www.target.example") is False

def test_formula_reproducible() -> None:
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto")
    formula = audit["score_formula"]
    canonical = round(
        float(formula["foundation_layer_score"])
        + float(formula["revenue_user_architecture_score"])
        + float(formula["elite_architecture_score"]),
        2,
    )
    assert formula["operating_baseline"] == 0
    assert formula["penalties_already_reflected_in_layer_scores"] is True
    assert formula["canonical_three_layer_score"] == canonical
    assert audit["overall_score"] == round(RevenueScorer._calibrate_public_score(canonical), 1)
    assert formula["public_score_ceiling"] == 90.0


def test_explicit_general() -> None:
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="general")
    assert audit["business_type"] == "general"
    assert audit["journey_model"] == "general"
    assert audit["business_profile"].get("source") == "explicit_request"
    assert audit["business_profile"].get("provisional") is True


def test_restaurant_mobile_and_overlap() -> None:
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto")
    leaks = audit["tiered_remediation_packages"]["all_scoring_leaks"]
    click = next(item for item in leaks if item.get("rule_key") == "click_to_call")
    sticky = next(item for item in leaks if item.get("rule_key") == "mobile_sticky_cta")
    overlap = next(item for item in audit["overlap_adjustments"] if item.get("family") == "mobile_direct_action")
    assert click["severity_factor"] == 0.4
    assert sticky["final_score_loss"] > 0
    assert overlap["post_dedupe_total"] < overlap["pre_dedupe_total"]


def test_static_sticky_unknown() -> None:
    scan = base_scan()
    scan.update({
        "browser_loaded": False,
        "static_html_verified": True,
        "mobile_sticky_cta_present": False,
        "mobile_cta_status": "unknown",
        "architecture_profile": {
            "journey_model": "general",
            "journey_label": "General / Unresolved Journey",
            "provisional": False,
            "context_tags": [],
        },
    })
    cps = build_50_checkpoints(scan, {"architecture_profile": scan["architecture_profile"], "business_type": "general"})
    cp4 = next(cp for cp in cps if cp["id"] == 4)
    assert cp4["status"] == UNKNOWN


def test_report_compatibility_wording() -> None:
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="general")
    text = ReportGenerator()._build_scoring_methodology_explanation(audit)["hygiene_gatekeeping"].lower()
    for phrase in ("conversion friction", "ordinary seo hygiene", "baymard-informed", "does not claim full baymard certification"):
        assert phrase in text


def test_action_intent_hardening() -> None:
    cases = {
        ("Facebook", "https://facebook.com/example"): "other",
        ("Removal Orders", "/immigration/removal-orders/"): "other",
        ("Delivery Information", "/delivery/"): "other",
        ("Book Appointment", "/appointments/"): "book",
        ("Book a Table", "/reservations/"): "reserve",
        ("Order Online", "/order-online/"): "order",
    }
    for (text, href), expected in cases.items():
        assert HybridScanner._classify_action_text(text, href) == expected


def test_context_boilerplate_filtering() -> None:
    law = infer_architecture_profile({
        "title": "Vancouver Immigration Lawyers",
        "h1_tags": ["Immigration Lawyers"],
        "meta_description": "Book a consultation with our law firm",
        "page_text": "We reserve the right to update this policy in the event of changes.",
        "journey_text_sample": "Contact our lawyers about your immigration legal matter.",
        "forms_present": True,
        "phone_number_visible": True,
        "address_location_visible": True,
        "mobile_cta_types": ["contact"],
    }, "auto")
    assert "regulated_high_trust" in law["context_tags"]
    assert "hospitality_event" not in law["context_tags"]

    builder = infer_architecture_profile({
        "title": "Custom Homes Vancouver",
        "h1_tags": ["Custom Home Builder"],
        "meta_description": "Custom home renovation contractor",
        "page_text": "In the event of changes, we reserve the right to update this policy. Legal matter terms may apply.",
        "journey_text_sample": "Custom homes renovations projects portfolio contact us",
        "forms_present": False,
        "mobile_cta_types": ["contact"],
        "address_location_visible": True,
        "phone_number_visible": True,
    }, "auto")
    assert "enterprise_considered_purchase" in builder["context_tags"]
    assert "sensitive_data" not in builder["context_tags"]
    assert "hospitality_event" not in builder["context_tags"]


def test_conversion_readiness_calibration() -> None:
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="general", competitor_data_present=None)
    metrics = audit["surface_metrics"]
    assert metrics["conversion_metric_status"] == "PROVISIONAL_JOURNEY"
    assert metrics["conversion_efficiency"] == metrics["conversion_path_readiness"]
    assert metrics["conversion_path_readiness"] < 80
    assert audit["analysis_layers"]["elite_architecture"]["layer_score"] == 0


def test_surface_layer_reconciliation() -> None:
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto", competitor_data_present=None)
    layers = audit["analysis_layers"]
    metrics = audit["surface_metrics"]
    f = layers["common_foundation"]
    a = layers["adaptive_architecture"]
    assert metrics["common_foundation_index"] == round(100 * f["layer_score"] / f["layer_max"], 1)
    assert metrics["adaptive_architecture_index"] == round(100 * a["layer_score"] / a["layer_max"], 1)


def test_advisory_maturity_and_report_scale() -> None:
    reporter = ReportGenerator()
    scan = valmont_fixture()
    audit = RevenueScorer().audit_and_score(scan, business_type="auto", competitor_data_present=None)
    gate = audit["maturity_gate"]
    assert gate["score_cap_enforced"] is False
    assert gate["advisory_score_threshold"] == gate["score_cap"]
    assert "not enforced" in gate["score_cap_semantics"]
    report = reporter.generate_admin_master_report(audit, scan)
    html = reporter._build_email_html(report)
    assert "/ 78" not in html
    assert "Advisory maturity threshold" in html
    assert "not a score cap" in html


def test_competitor_query_specificity() -> None:
    profile = {
        "journey_model": "lead_quote",
        "journey_signals": ["hero:custom home", "meta:renovation", "action:contact"],
    }
    target_place = {"place_primary_type": "service", "place_types": ["service", "establishment"]}
    query = HybridScanner._competitor_search_query(target_place, profile)
    assert "custom home" in query
    assert "renovation" in query
    assert query != "local service provider"


def test_conversion_confirmation_routing() -> None:
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


def test_revenue_exposure_decoupling() -> None:
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
    considered = RevenueScorer._revenue_exposure(
        "lead_quote", [leak], evidence, {"context_tags": ["enterprise_considered_purchase"]}
    )
    assert plain["economic_severity_basis"] == considered["economic_severity_basis"] == 3.0
    assert considered["economic_context_multiplier"] > plain["economic_context_multiplier"]
    assert considered["max"] > plain["max"]



def test_foundation_signal_separation() -> None:
    signal = build_foundation_omission_signal(
        [
            {"id": 22, "status": FAIL, "rule_key": "canonical_missing", "check": "Canonical URL Present", "evidence": None},
            {"id": 31, "status": UNKNOWN, "rule_key": "mobile_viewport", "check": "Mobile Viewport Configured", "evidence": None},
        ],
        {"final_url": "https://example.com/", "title": "Example", "browser_loaded": True},
    )
    assert signal["count"] == 1
    assert signal["public_modal_disclose_items"] is False
    assert "canonical" not in signal["modal_message"].lower()


def test_conversion_priority_over_minor_hygiene() -> None:
    strong = base_scan()
    strong.update({
        "title": "Vancouver Home Renovation Contractor",
        "h1_tags": ["Custom Home Renovations"],
        "meta_description": "Custom home renovation contractor. Request a quote.",
        "page_text": "Custom home renovations projects portfolio request a quote contact us Vancouver " * 20,
        "forms_present": True,
        "form_action_valid": True,
        "form_functional_status": "PASS",
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
        "form_functional_status": "FAIL",
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



def test_non_compensatory_pillars_and_stricter_earning() -> None:
    audit = RevenueScorer().audit_and_score(_resolved_lead_fixture(), business_type="auto")
    detail = audit["analysis_layers"]["adaptive_architecture"]["weighted_checkpoint_detail"]
    pillars = detail["pillars"]
    assert round(sum(float(x["max"]) for x in pillars.values()), 2) == 60.0
    assert pillars["conversion_execution"]["max"] == 32.0
    assert pillars["trust_decision_support"]["max"] == 16.0
    assert pillars["measurement_policy"]["max"] == 8.0
    assert pillars["supporting_experience"]["max"] == 4.0
    assert audit["overall_score"] < 80.0


def test_provisional_journey_cannot_overearn() -> None:
    audit = RevenueScorer().audit_and_score(base_scan(), business_type="auto")
    detail = audit["analysis_layers"]["adaptive_architecture"]["weighted_checkpoint_detail"]
    assert audit["business_profile"].get("provisional") is True
    assert detail["journey_resolution_factor"] < 1.0
    assert audit["overall_score"] < 75.0
    assert audit["surface_metrics"]["conversion_path_readiness"] <= 85.0


def test_hasler_style_calibration() -> None:
    scan = _resolved_lead_fixture()
    scan.update({
        "performance_score": 45.0,
        "mobile_sticky_cta_present": False,
        "mobile_cta_types": ["contact"],
        "forms_present": False,
        "form_action_valid": None,
        "form_functional_status": "NOT_APPLICABLE",
        "journey_pages_verified": 5,
        "h1_tags": ["Vancouver Custom Home Builder", "Vancouver Custom Home Builder"],
        "h1_dom_count": 2,
        "missing_alt_images": 1,
        "images_with_alt": 2,
        "image_count": 3,
        "total_images": 3,
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="auto")
    assert 35.0 <= audit["overall_score"] <= 44.0
    assert audit["analysis_layers"]["elite_architecture"]["layer_score"] == 0
    cp50 = next(cp for cp in audit["full_50_checkpoint_basis"] if cp["id"] == 50)
    assert cp50["status"] == UNKNOWN and cp50["unknown_reason_code"] == "SAFE_SUBMISSION_LIMIT"


def test_commercial_exposure_expected_value_model() -> None:
    leak = {
        "rule_key": "conversion_path_error", "family": "conversion_execution",
        "economic_severity": 4.0, "intrinsic_severity_score": 4.0,
        "final_score_loss": 1.0, "confidence": "high",
        "severity_factor": 1.0, "substitution_factor": 1.0,
    }
    evidence = {"score": 95}
    result = RevenueScorer._revenue_exposure(
        "lead_quote", [leak], evidence, {"context_tags": []},
        {"economic_inputs": {"monthly_commercial_path_sessions": 1000, "expected_conversion_rate": 0.05, "expected_value_per_conversion": 1000}},
    )
    changed = dict(leak); changed["final_score_loss"] = 9.0
    changed_result = RevenueScorer._revenue_exposure(
        "lead_quote", [changed], evidence, {"context_tags": []},
        {"economic_inputs": {"monthly_commercial_path_sessions": 1000, "expected_conversion_rate": 0.05, "expected_value_per_conversion": 1000}},
    )
    assert result["model_version"] == "commercial_exposure_v2"
    assert result["basis"] == "business_input_commercial_path_analytics"
    assert result["annual_digital_opportunity_pool"] == {"low": 600000, "high": 600000}
    assert result["combined_path_impairment_pct"] == changed_result["combined_path_impairment_pct"]
    assert result["central_annual_exposure"] == changed_result["central_annual_exposure"]


def test_competitor_probe_identity_guard() -> None:
    competitor = {"name": "Example Construction", "primary_type": "general_contractor", "place_types": ["general_contractor", "service"]}
    signals = {
        "title": "Vancouver Physiotherapy Clinic",
        "meta_description": "Book physiotherapy rehabilitation treatment",
        "h1_tags": ["Physiotherapy & Sports Rehab"],
        "page_text": "Our physiotherapists treat patients with injuries and rehabilitation plans.",
    }
    profile = {"journey_model": "appointment_consultation", "context_tags": ["regulated_high_trust"]}
    result = HybridScanner._competitor_probe_identity_check(competitor, signals, profile)
    assert result["conflict"] is True
    assert result["expected_category"] == "construction_trades"
    assert result["observed_category"] == "healthcare"


def test_blueprint90_score_bands() -> None:
    expected = {26: 26.0, 32: 32.0, 40: 35.0, 55: 40.0, 65: 42.0, 70.5: 44.0, 73: 46.0, 80: 57.0, 85: 59.0, 90: 69.0, 95: 80.0, 100: 90.0}
    assert {x: RevenueScorer._calibrate_public_score(x) for x in expected} == expected


def test_safe_completion_and_field_performance_edges() -> None:
    scan = base_scan()
    text = "shop now add to cart checkout buy now product shipping returns " * 12
    scan.update({
        "title": "Shop Online", "page_text": text, "journey_text_sample": text,
        "forms_present": False, "journey_pages_verified": 0,
        "mobile_primary_cta_present": True, "mobile_cta_types": ["buy"],
        "add_to_cart_visible": True, "checkout_context_detected": True, "order_online_present": True,
    })
    audit = RevenueScorer().audit_and_score(scan, business_type="auto")
    cp50 = next(cp for cp in audit["full_50_checkpoint_basis"] if cp["id"] == 50)
    assert cp50["status"] == UNKNOWN and cp50["unknown_reason_code"] == "SAFE_SUBMISSION_LIMIT"
    assert audit["surface_metrics"]["conversion_path_readiness"] < 100.0

    leak = {
        "rule_key": "mobile_lab_performance", "family": "performance",
        "economic_severity": 1.15, "intrinsic_severity_score": 1.15,
        "final_score_loss": 1.05, "confidence": "high", "severity_factor": 0.4, "substitution_factor": 1.0,
    }
    good = RevenueScorer._revenue_exposure("lead_quote", [leak], {"score": 98}, {}, {"crux_available": True, "real_user_speed_grade": "GOOD", "performance_score": 54})
    lab = RevenueScorer._revenue_exposure("lead_quote", [leak], {"score": 98}, {}, {"crux_available": False, "real_user_speed_grade": "UNKNOWN", "performance_score": 54})
    assert good["combined_path_impairment_pct"] < lab["combined_path_impairment_pct"]
    assert good["issue_components"][0]["field_performance_override"] is True


def test_full_synthetic_blueprint_matrix() -> None:
    from synthetic_blueprint_validation import run
    rows = run()
    assert len(rows) == 36
    assert len({row["journey"] for row in rows}) == 6
    assert len({row["synthetic_level"] for row in rows}) == 6


def test_multiservice_b2b_journey_and_financial_guardrail() -> None:
    profile = infer_architecture_profile({
        "title": "Remote Alaskan Services",
        "h1_tags": ["We've Got You Covered"],
        "meta_description": "Remote support services for exploration and production operations.",
        "page_text": (
            "support services oil and gas industry exploration production activities remote operations "
            "logistics drilling aviation project support clients remote medical services remote medical clinic sets contact"
        ),
        "journey_text_sample": "remote medical services medical clinic consultation occupational health logistics drilling support contact",
        "forms_present": False,
        "phone_number_visible": True,
        "mobile_cta_types": ["contact"],
        "booking_provider_links": [],
        "booking_action_present": False,
        "reservation_present": False,
    }, "auto")
    assert profile["journey_model"] == "lead_quote"
    assert "enterprise_considered_purchase" in profile["context_tags"]
    assert "regulated_high_trust" not in profile["context_tags"]

    leaks = [
        {"rule_key": "privacy_terms_missing", "family": "trust_policy", "economic_severity": 0.89, "intrinsic_severity_score": 0.89, "final_score_loss": 0.89, "confidence": "high", "severity_factor": 0.50, "substitution_factor": 1.0},
        {"rule_key": "structured_data_missing", "family": "search_structure", "economic_severity": 0.25, "intrinsic_severity_score": 0.25, "final_score_loss": 0.18, "confidence": "high", "severity_factor": 0.45, "substitution_factor": 1.0},
        {"rule_key": "meta_description_length", "family": "search_snippet", "economic_severity": 0.04, "intrinsic_severity_score": 0.04, "final_score_loss": 0.04, "confidence": "high", "severity_factor": 0.30, "substitution_factor": 1.0},
    ]
    exposure = RevenueScorer._revenue_exposure(
        "lead_quote", leaks, {"score": 70.6}, profile,
        {"crux_available": True, "real_user_speed_grade": "GOOD"},
    )
    assert exposure["journey_model"] == "lead_quote"
    assert exposure["annual_digital_opportunity_pool"] == {"low": 18750, "high": 324000}
    assert exposure["display"] == "$500 – $16,500 / year — LOW scenario exposure"

def main() -> int:
    print("=" * 70)
    print(" TRILLOKA V7.2.2 LAUNCH-CANDIDATE BLUEPRINT90 REAL-WORLD + SECURITY INTEGRITY SUITE ")
    print("=" * 70)
    checks = (
        ("Core Python compile + warnings-as-errors", test_compile),
        ("Full regression suite", test_pytest_regressions),
        ("API gateway imports with complete runtime dependencies", test_main_runtime_import),
        ("Deployment manifest includes EmailStr dependency", test_deployment_dependency_manifest),
        ("SSRF/network target hardening is enforced", test_network_target_ssrf_hardening),
        ("Browser cross-origin network policy fails closed", test_browser_cross_origin_fail_closed),
        ("Canonical 3-layer score reproducibility", test_formula_reproducible),
        ("Explicit general remains provisional general", test_explicit_general),
        ("Restaurant click/sticky + overlap", test_restaurant_mobile_and_overlap),
        ("Static sticky checkpoint stays UNKNOWN", test_static_sticky_unknown),
        ("Report compatibility wording", test_report_compatibility_wording),
        ("Action intent false-positive hardening", test_action_intent_hardening),
        ("Context boilerplate false-positive filtering", test_context_boilerplate_filtering),
        ("Conversion readiness calibration", test_conversion_readiness_calibration),
        ("Surface metrics reconcile to earned layers", test_surface_layer_reconciliation),
        ("Maturity thresholds advisory + public 0-90 blueprint scale", test_advisory_maturity_and_report_scale),
        ("Competitor query uses specific offering evidence", test_competitor_query_specificity),
        ("High-impact confirmation targets revenue path", test_conversion_confirmation_routing),
        ("Financial exposure remains decoupled from score loss", test_revenue_exposure_decoupling),
        ("Foundation omission signal stays separate and non-disclosing", test_foundation_signal_separation),
        ("Revenue-path failures outweigh minor search hygiene", test_conversion_priority_over_minor_hygiene),
        ("60-point architecture uses non-compensatory commercial pillars", test_non_compensatory_pillars_and_stricter_earning),
        ("Provisional journeys cannot over-earn readiness", test_provisional_journey_cannot_overearn),
        ("Hasler-style good-looking site calibrates below easy Good band", test_hasler_style_calibration),
        ("Commercial exposure uses expected-value inputs, not score points", test_commercial_exposure_expected_value_model),
        ("Blueprint 0-90 public score bands are reproducible", test_blueprint90_score_bands),
        ("Safe completion + CrUX/financial edge cases are enforced", test_safe_completion_and_field_performance_edges),
        ("36-case synthetic blueprint matrix differentiates all six journeys", test_full_synthetic_blueprint_matrix),
        ("Diversified B2B service lines cannot hijack journey or financial priors", test_multiservice_b2b_journey_and_financial_guardrail),
        ("Competitor probe rejects business/content identity conflicts", test_competitor_probe_identity_guard),
        ("Unsupported Nearby types force specific Text Search fallback", test_unsupported_nearby_type_forces_specific_text_search_even_when_untyped_retry_has_results),
        ("Verified missing-alt omission triggers generic Foundation Notice", test_missing_alt_accessibility_failure_triggers_generic_foundation_notice),
        ("CrUX GOOD uses lab-performance semantics instead of false CWV wording", test_crux_good_uses_lab_performance_semantics_not_core_web_vitals_failure),
    )
    passed = sum(check(name, fn) for name, fn in checks)
    print("=" * 70)
    print(f" RESULT: {passed}/{len(checks)} checks passed")
    print("=" * 70)
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
