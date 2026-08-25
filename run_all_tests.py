"""Trilloka V7 completed-scanner integrity runner.

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
from test_regressions import base_scan, valmont_fixture

ROOT = Path(__file__).resolve().parent
CORE_FILES = (
    "architecture_model.py",
    "behavioural_engine.py",
    "checkpoint_engine.py",
    "hybrid_scanner.py",
    "scorer.py",
    "report_engine.py",
    "main.py",
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


def test_formula_reproducible() -> None:
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="auto")
    formula = audit["score_formula"]
    canonical = round(
        float(formula["foundation_layer_score"])
        + float(formula["revenue_user_architecture_score"])
        + float(formula["elite_architecture_score"]),
        1,
    )
    assert formula["operating_baseline"] == 0
    assert formula["penalties_already_reflected_in_layer_scores"] is True
    assert audit["overall_score"] == canonical


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


def main() -> int:
    print("=" * 70)
    print(" TRILLOKA V7 COMPLETED SCANNER INTEGRITY SUITE ")
    print("=" * 70)
    checks = (
        ("Core Python compile + warnings-as-errors", test_compile),
        ("Full regression suite", test_pytest_regressions),
        ("Canonical 3-layer score reproducibility", test_formula_reproducible),
        ("Explicit general remains provisional general", test_explicit_general),
        ("Restaurant click/sticky + overlap", test_restaurant_mobile_and_overlap),
        ("Static sticky checkpoint stays UNKNOWN", test_static_sticky_unknown),
        ("Report compatibility wording", test_report_compatibility_wording),
        ("Action intent false-positive hardening", test_action_intent_hardening),
        ("Context boilerplate false-positive filtering", test_context_boilerplate_filtering),
        ("Conversion readiness calibration", test_conversion_readiness_calibration),
        ("Surface metrics reconcile to earned layers", test_surface_layer_reconciliation),
        ("Maturity thresholds advisory + 100-point report scale", test_advisory_maturity_and_report_scale),
        ("Competitor query uses specific offering evidence", test_competitor_query_specificity),
        ("High-impact confirmation targets revenue path", test_conversion_confirmation_routing),
        ("Financial exposure remains decoupled from score loss", test_revenue_exposure_decoupling),
        ("Foundation omission signal stays separate and non-disclosing", test_foundation_signal_separation),
        ("Revenue-path failures outweigh minor search hygiene", test_conversion_priority_over_minor_hygiene),
    )
    passed = sum(check(name, fn) for name, fn in checks)
    print("=" * 70)
    print(f" RESULT: {passed}/{len(checks)} checks passed")
    print("=" * 70)
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
