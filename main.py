"""Trilloka Architect Engine API gateway.

BACKWARD-COMPATIBILITY REQUIREMENT
- Public endpoint paths remain /api/audit and /api/scan.
- Existing request fields remain accepted.
- Existing response keys remain present for successful scans.
- New diagnostics are additive only.
- No frontend code change is required for the existing request flow.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from hybrid_scanner import HybridScanner
from scorer import RevenueScorer

try:
    from report_engine import ReportGenerator

    reporter = ReportGenerator()
    REPORT_ENGINE_AVAILABLE = True
except Exception as exc:
    print(f"[Report Engine] Import failed: {exc}")
    reporter = None
    REPORT_ENGINE_AVAILABLE = False


app = FastAPI(
    title="Trilloka Architect Engine API",
    description="3-Phase Telemetry Diagnostic & Frontend Gateway",
    version="6.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scanner = HybridScanner()
scorer = RevenueScorer()


class AuditRequest(BaseModel):
    domain: str
    business_name: Optional[str] = ""
    # Backward compatible: old clients may still send ecommerce/general/etc.
    # New clients may omit it and allow evidence-based automatic classification.
    business_type: str = "auto"
    # Backward compatible: existing booleans are accepted; None means no verified competitor comparison.
    competitor_has_feature: Optional[bool] = None
    email: Optional[EmailStr] = None


def handle_trilloka_guardrail(target_domain: str) -> Optional[Dict[str, Any]]:
    """Preserve the existing Trilloka self-scan guardrail response contract."""
    clean_url = target_domain if target_domain.startswith(("http://", "https://")) else f"https://{target_domain}"
    domain = urlparse(clean_url).netloc.lower() or target_domain.lower()

    if "trilloka" not in domain:
        return None

    snapshot_file = "trilloka_30day_audit_snapshot.json"
    snapshot_data: Dict[str, Any] = {}
    if os.path.exists(snapshot_file):
        try:
            with open(snapshot_file, "r", encoding="utf-8") as handle:
                snapshot_data = json.load(handle)
        except Exception as exc:
            print(f"[Guardrail] Error reading snapshot JSON: {exc}")

    score = float(snapshot_data.get("overall_score", 75.0))
    return {
        "success": True,
        "is_guarded": True,
        "target_domain": target_domain,
        "status": "INTERCEPTED",
        "guardrail": {
            "heading": "Nice try!!!",
            "message": "Did you really think we didn't know some of you wouldn't be able to resist yourselves. Well, The Architect has commanded us to scan his own website every 30 days and check its ongoing state of strength...",
            "note": "While external public scans are barred on core infrastructure, below are the latest stored Trilloka self-diagnostic results.",
        },
        "overall_score": score,
        "surface_metrics": {
            "mobile_performance_score": snapshot_data.get("mobile_performance_score", score),
            "seo_health_index": snapshot_data.get("seo_health_index", score),
            "ai_spectrum_pct": snapshot_data.get("ai_spectrum_pct", 0.0),
            "online_presence_index": snapshot_data.get("online_presence_index", score),
            "conversion_efficiency": snapshot_data.get("conversion_efficiency", score),
            "competitor_gap_score": 0,
            "classification": "Architect Core Platform",
        },
        "key_friction_insight": {
            "passed_count": snapshot_data.get("passed_count", 3),
            "failed_count": snapshot_data.get("failed_count", 1),
            "load_time_seconds": snapshot_data.get("load_time_seconds", 0.97),
        },
        "revenue_leak": snapshot_data.get(
            "revenue_leak",
            {"est_annual_revenue_leak": "Self-scan exposure stored in latest snapshot"},
        ),
        "cms_platform": snapshot_data.get("cms_detected", "Trilloka Engine"),
        "audit_snapshot": snapshot_data,
        "message": "Trilloka infrastructure self-scan intercepted. Displaying stored diagnostic snapshot.",
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "online",
        "system": "Trilloka Architect Engine v6.0",
        "google_api_configured": bool(os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "report_engine": REPORT_ENGINE_AVAILABLE,
    }


@app.get("/diagnostic")
def diagnostic() -> Dict[str, Any]:
    results: Dict[str, Any] = {"status": "running", "checks": {}}
    results["checks"]["env_google_api_key"] = bool(
        os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    )
    try:
        local_scanner = HybridScanner()
        results["checks"]["scanner_init"] = "OK"
        preflight = local_scanner._fast_http_preflight("https://example.com")
        results["checks"]["http_preflight"] = "OK" if preflight.get("is_reachable") else "UNAVAILABLE"
        psi = local_scanner._fetch_google_pagespeed("https://example.com")
        results["checks"]["pagespeed_api"] = psi.get("pagespeed_api_status", "unknown")
    except Exception as exc:
        results["checks"]["scanner_init"] = f"FAIL: {exc}"
    try:
        RevenueScorer()
        results["checks"]["scorer_init"] = "OK"
    except Exception as exc:
        results["checks"]["scorer_init"] = f"FAIL: {exc}"
    results["checks"]["report_engine"] = "OK" if REPORT_ENGINE_AVAILABLE else "NOT LOADED"
    return results


async def _run_scan_async(domain: str, business_name: str = "") -> Dict[str, Any]:
    """Keep blocking requests/Playwright work off the FastAPI event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: asyncio.run(scanner.execute_hybrid_scan(domain, business_name)),
    )


@app.post("/api/audit")
async def run_audit(request: AuditRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    guardrail_response = handle_trilloka_guardrail(request.domain)
    if guardrail_response:
        return guardrail_response

    try:
        scan_data = await _run_scan_async(request.domain, request.business_name or "")
    except Exception as exc:
        print(f"[Scanner] Fatal scan error: {exc}")
        raise HTTPException(status_code=500, detail="Scanner execution failed before a defensible diagnostic could be produced") from exc

    if not scan_data.get("is_reachable"):
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{request.domain}' is offline, unreachable, or blocking both HTTP and browser inspection.",
        )

    try:
        audit_results = scorer.audit_and_score(
            scan_data=scan_data,
            business_type=request.business_type,
            competitor_data_present=request.competitor_has_feature,
        )
    except ValueError as exc:
        # Evidence insufficiency is a scan-quality outcome, not a fake score.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        import traceback

        print(f"[Scorer] Crash — {exc}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Scoring engine failed. No substitute or fallback score was generated.",
        ) from exc

    admin_master_report: Optional[Dict[str, Any]] = None
    if REPORT_ENGINE_AVAILABLE and reporter is not None:
        try:
            admin_master_report = reporter.generate_admin_master_report(
                audit_data=audit_results,
                scan_data=scan_data,
            )
            background_tasks.add_task(
                reporter.archive_to_vault,
                target_domain=request.domain,
                admin_report=admin_master_report,
                raw_scan_data=scan_data,
            )
            background_tasks.add_task(
                reporter.send_admin_alert_email,
                admin_report=admin_master_report,
            )
        except Exception as exc:
            # Report delivery failure must not corrupt a valid scan response.
            print(f"[Report Engine] Delivery/archive skipped — {exc}")

    all_leaks = (audit_results.get("tiered_remediation_packages") or {}).get("tier_10_arch10", [])

    # Existing response keys are preserved. New diagnostics are additive.
    return {
        "success": True,
        "status": "complete",
        "target_domain": request.domain,
        "overall_score": audit_results.get("overall_score"),
        "surface_metrics": audit_results.get("surface_metrics", {}),
        "key_friction_insight": audit_results.get("key_friction_insight", {}),
        "revenue_leak": audit_results.get("revenue_leak", {}),
        "cms_platform": audit_results.get("cms_platform", "Not confidently identified"),
        "dev_handoff_kit": audit_results.get("dev_handoff_kit", ""),
        "top_5_seo_leaks": all_leaks[:5],
        # Additive only: existing frontend key above is untouched.
        "top_10_financial_leaks": all_leaks[:10],
        "message": "Scan complete. Full report available for purchase.",
        # Additive v4 diagnostics
        "business_profile": audit_results.get("business_profile", {}),
        "scan_quality": scan_data.get("scan_quality", {}),
        "evidence_coverage": scan_data.get("evidence_coverage", {}),
        "scoring_ledger": audit_results.get("scoring_ledger", []),
        "overlap_adjustments": audit_results.get("overlap_adjustments", []),
        "score_formula": audit_results.get("score_formula", {}),
        "ai_spectrum_status": audit_results.get("ai_spectrum_status", "unknown"),
        "cms_confidence": scan_data.get("cms_confidence", "low"),
        "report_checkpoint_summary": (admin_master_report or {}).get("checkpoint_summary", {}),
        "verification_coverage_note": (admin_master_report or {}).get("verification_coverage_note", ""),
        "scanner_engine_version": scan_data.get("scanner_engine_version", "v6"),
    }


@app.post("/api/scan")
async def run_scan(request: AuditRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    return await run_audit(request, background_tasks)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
