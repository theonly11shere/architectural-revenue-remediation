"""Trilloka V7 core integrity runner.

Runs the current Journey + Context scanner/scorer regression suite instead of the
obsolete pre-V7 ``app.*`` package checks.  This file intentionally performs no live
customer submissions and does not require network access or Google credentials.
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

from checkpoint_engine import UNKNOWN, build_50_checkpoints
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
    penalty = round(sum(float(row.get("final_score_loss") or 0.0) for row in audit["scoring_ledger"]), 2)
    recomputed = round(max(0.0, min(100.0,
        float(formula["operating_baseline"])
        + float(formula["verified_strength_points_awarded"])
        + float(formula["elite_bonus_points"])
        + float(formula["reference_completeness_bonus"])
        - penalty
    )), 1)
    assert formula["total_final_penalty"] == penalty
    assert audit["overall_score"] == recomputed


def test_explicit_general() -> None:
    audit = RevenueScorer().audit_and_score(valmont_fixture(), business_type="general")
    assert audit["business_type"] == "general"
    assert audit["journey_model"] == "general"
    assert audit["business_profile"].get("source") == "explicit_request"


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


def main() -> int:
    print("=" * 62)
    print(" TRILLOKA V7 CORE SCANNER INTEGRITY SUITE ")
    print("=" * 62)
    checks = (
        ("Core Python compile", test_compile),
        ("Full regression suite", test_pytest_regressions),
        ("Score formula reproducibility", test_formula_reproducible),
        ("Explicit general remains general", test_explicit_general),
        ("Restaurant click/sticky + overlap", test_restaurant_mobile_and_overlap),
        ("Static sticky checkpoint stays UNKNOWN", test_static_sticky_unknown),
        ("Report compatibility wording", test_report_compatibility_wording),
    )
    passed = sum(check(name, fn) for name, fn in checks)
    print("=" * 62)
    print(f" RESULT: {passed}/{len(checks)} checks passed")
    print("=" * 62)
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
