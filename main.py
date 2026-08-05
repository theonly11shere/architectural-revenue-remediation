import os
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any

# Import local pipeline engines
from hybrid_scanner import HybridScanner
from scorer import RevenueScorer
from report_engine import ReportGenerator

# Initialize FastAPI Application
app = FastAPI(
    title="Trilloka Architect Engine API",
    description="3-Phase Telemetry Diagnostic, Admin Master Report Archival, & Frontend Teaser Gateway",
    version="3.0.0"
)

# Enable CORS for Frontend Access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Pipeline Core Services
scanner = HybridScanner()
scorer = RevenueScorer()
reporter = ReportGenerator()


# Request Payload Model from Frontend
class AuditRequest(BaseModel):
    domain: str
    business_type: str = "ecommerce"
    competitor_has_feature: bool = True
    email: Optional[EmailStr] = None


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "online",
        "system": "Trilloka Architect Engine v3.0",
        "pagespeed_api_configured": bool(os.environ.get("PAGESPEED_API_KEY")),
    }


@app.get("/diagnostic")
def diagnostic() -> Dict[str, Any]:
    """Tests each pipeline component and reports what works vs what crashes."""
    results = {"status": "running", "checks": {}}
    results["checks"]["env_pagespeed_api_key"] = bool(os.environ.get("PAGESPEED_API_KEY"))
    try:
        from hybrid_scanner import HybridScanner
        s = HybridScanner()
        results["checks"]["scanner_init"] = "OK"
    except Exception as e:
        results["checks"]["scanner_init"] = f"FAIL: {str(e)}"
    try:
        test = s._fast_http_preflight("https://example.com")
        results["checks"]["http_preflight"] = "OK"
    except Exception as e:
        results["checks"]["http_preflight"] = f"FAIL: {str(e)}"
    try:
        ps = s._fetch_google_pagespeed("https://example.com")
        results["checks"]["pagespeed_api"] = ps.get("pagespeed_api_status", "unknown")
    except Exception as e:
        results["checks"]["pagespeed_api"] = f"FAIL: {str(e)}"
    try:
        from scorer import RevenueScorer
        sc = RevenueScorer()
        results["checks"]["scorer_init"] = "OK"
    except Exception as e:
        results["checks"]["scorer_init"] = f"FAIL: {str(e)}"
    try:
        from report_engine import ReportGenerator
        r = ReportGenerator()
        results["checks"]["report_engine_init"] = "OK"
    except Exception as e:
        results["checks"]["report_engine_init"] = f"FAIL: {str(e)}"
    return results


async def _run_scan_safe(domain: str) -> Dict[str, Any]:
    """Run scanner in a thread pool so it doesnt block the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, scanner.execute_hybrid_scan, domain)


async def _run_score_safe(scan_data: Dict[str, Any], business_type: str, competitor_has_feature: bool) -> Dict[str, Any]:
    """Run scorer in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, scorer.audit_and_score, scan_data, business_type, competitor_has_feature)


def _build_frontend_response(
    request: AuditRequest,
    scan_data: Dict[str, Any],
    audit_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Formats backend data into the exact structure the frontend showResults() expects."""

    overall_score = audit_results.get("overall_health_score", 50.0)
    perf_score = scan_data.get("performance_score", overall_score)
    seo_score = scan_data.get("google_seo_score", 65.0)

    # Derive surface metrics from real scan data
    surface_metrics = {
        "mobile_performance_score": round(perf_score),
        "seo_health_index": round(seo_score),
        "ai_spectrum_pct": 15,  # placeholder until real AI detection is wired
        "online_presence_index": round(overall_score * 0.85),
        "conversion_efficiency": round(overall_score * 0.8),
        "competitor_gap_score": max(10, 100 - round(overall_score)),
        "classification": scan_data.get("cms_platform", "Modern Stack")
    }

    # Build friction insight from top leak
    all_leaks = audit_results.get("tiered_remediation_packages", {}).get("tier_10_arch10", [])
    top_leak = all_leaks[0] if all_leaks else None

    key_friction = {}
    if top_leak:
        key_friction = {
            "reason": top_leak.get("impact_summary", "Structural friction detected."),
            "revenue_loss_pct": round(top_leak.get("severity_score", 5))
        }

    # Estimate revenue leak
    revenue_leak = {}
    if overall_score < 70:
        revenue_leak = {
            "est_annual_revenue_leak": f"${round((70 - overall_score) * 420)} — ${round((70 - overall_score) * 850)}"
        }

    return {
        "success": True,
        "target_domain": request.domain,
        "overall_score": round(overall_score),
        "surface_metrics": surface_metrics,
        "key_friction_insight": key_friction,
        "revenue_leak": revenue_leak,
        "cms_platform": scan_data.get("cms_platform", ""),
        "dev_handoff_kit": audit_results.get("dev_handoff_kit", ""),
        "top_5_seo_leaks": all_leaks[:5],
        "message": "Scan complete. Full report available for purchase."
    }


@app.post("/api/audit")
async def run_audit(request: AuditRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    try:
        # Step 1: Execute 3-Phase Telemetry Scan (non-blocking)
        scan_data = await _run_scan_safe(request.domain)

        if not scan_data.get("is_reachable", True):
            raise HTTPException(
                status_code=400,
                detail=f"Domain '{request.domain}' is offline, unreachable, or blocking requests."
            )

        # Step 2: Calculate Harsh Scoring
        try:
            audit_results = await _run_score_safe(
                scan_data, request.business_type, request.competitor_has_feature
            )
        except Exception as score_err:
            print(f"[Scorer] Crash — {score_err}")
            audit_results = {
                "overall_health_score": 50.0,
                "score_rating": "NEEDS REMEDIATION",
                "total_leaks_found": 0,
                "tiered_remediation_packages": {"tier_10_arch10": []}
            }

        # Step 3: Generate & Archive Admin Report (background)
        try:
            admin_master_report = reporter.generate_admin_master_report(
                audit_data=audit_results,
                scan_data=scan_data
            )
            background_tasks.add_task(
                reporter.archive_to_vault,
                target_domain=request.domain,
                admin_report=admin_master_report,
                raw_scan_data=scan_data
            )
        except Exception as report_err:
            print(f"[Report Engine] Skipped — {report_err}")

        # Step 4: Return Frontend-Compatible Payload
        return _build_frontend_response(request, scan_data, audit_results)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print("[FATAL SCAN CRASH]")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scan pipeline crash: {str(e)}")


@app.post("/api/scan")
async def run_scan(request: AuditRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Frontend alias for /api/audit. Same 3-phase telemetry scan."""
    return await run_audit(request, background_tasks)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
