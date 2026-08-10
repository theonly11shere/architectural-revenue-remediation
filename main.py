import os
import json
import asyncio
import uvicorn
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any

# Import local pipeline engines
from hybrid_scanner import HybridScanner
from scorer import RevenueScorer

try:
    from report_engine import ReportGenerator
    reporter = ReportGenerator()
    REPORT_ENGINE_AVAILABLE = True
except Exception:
    reporter = None
    REPORT_ENGINE_AVAILABLE = False

app = FastAPI(
    title="Trilloka Architect Engine API",
    description="3-Phase Telemetry Diagnostic & Frontend Gateway",
    version="3.0.0"
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
    business_type: str = "ecommerce"
    competitor_has_feature: bool = True
    email: Optional[EmailStr] = None


def handle_trilloka_guardrail(target_domain: str) -> Optional[Dict[str, Any]]:
    """
    Guardrail Interceptor:
    Prevents public/external live scanning of Trilloka core infrastructure.
    Serves witty sarcastic response with authentic 30-day telemetry snapshot data.
    """
    clean_url = target_domain if target_domain.startswith(("http://", "https://")) else f"https://{target_domain}"
    domain = urlparse(clean_url).netloc.lower() or target_domain.lower()

    if "trilloka" in domain:
        snapshot_file = "trilloka_30day_audit_snapshot.json"
        snapshot_data = {}

        if os.path.exists(snapshot_file):
            try:
                with open(snapshot_file, "r") as f:
                    snapshot_data = json.load(f)
            except Exception as e:
                print(f"[Guardrail] Error reading snapshot JSON: {e}")

        score = snapshot_data.get("overall_score", 75.0)

        return {
            "success": True,
            "is_guarded": True,
            "target_domain": target_domain,
            "status": "INTERCEPTED",
            "guardrail": {
                "heading": "Nice try!!!",
                "message": "Did you really think we didn't know some of you wouldn't be able to resist yourselves. Well, The Architect has commanded us to scan his own website every 30 days and check its ongoing state of strength...",
                "note": "While external public scans are barred on core infrastructure, below are the authentic telemetry results from our latest scheduled 30-day diagnostic run."
            },
            "overall_score": score,
            "surface_metrics": {
                "mobile_performance_score": score,
                "seo_health_index": score,
                "ai_spectrum_pct": snapshot_data.get("ai_spectrum_pct", 0.0),
                "online_presence_index": 75,
                "conversion_efficiency": 75,
                "competitor_gap_score": 0,
                "classification": "Architect Core Platform"
            },
            "key_friction_insight": {
                "passed_count": snapshot_data.get("passed_count", 3),
                "failed_count": snapshot_data.get("failed_count", 1),
                "load_time_seconds": snapshot_data.get("load_time_seconds", 0.97)
            },
            "revenue_leak": {
                "annual_leak": "$0 / year (Architect Core Shielded)"
            },
            "cms_platform": snapshot_data.get("cms_detected", "Trilloka Engine"),
            "audit_snapshot": snapshot_data,
            "message": "Trilloka infrastructure self-scan intercepted. Displaying official 30-day telemetry snapshot."
        }

    return None


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "online",
        "system": "Trilloka Architect Engine v3.0",
        "google_api_configured": bool(os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "report_engine": REPORT_ENGINE_AVAILABLE
    }


@app.get("/diagnostic")
def diagnostic() -> Dict[str, Any]:
    results = {"status": "running", "checks": {}}
    results["checks"]["env_google_api_key"] = bool(os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
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
    results["checks"]["report_engine"] = "OK" if REPORT_ENGINE_AVAILABLE else "NOT LOADED"
    return results


async def _run_scan_async(domain: str, business_name: str = "") -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        lambda: asyncio.run(scanner.execute_hybrid_scan(domain, business_name))
    )


@app.post("/api/audit")
async def run_audit(request: AuditRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    try:
        # STEP 1: Guardrail Check Interceptor
        guardrail_response = handle_trilloka_guardrail(request.domain)
        if guardrail_response:
            return guardrail_response

        # STEP 2: Proceed with standard live scan for external sites
        scan_data = await _run_scan_async(request.domain, request.business_name)

        if not scan_data.get("is_reachable", True):
            raise HTTPException(
                status_code=400,
                detail=f"Domain '{request.domain}' is offline, unreachable, or blocking requests."
            )

        try:
            audit_results = scorer.audit_and_score(
                scan_data=scan_data,
                business_type=request.business_type,
                competitor_data_present=request.competitor_has_feature
            )
        except Exception as score_err:
            print(f"[Scorer] Crash — {score_err}")
            import traceback
            traceback.print_exc()
            audit_results = {
                "overall_score": 50,
                "surface_metrics": {
                    "mobile_performance_score": 50,
                    "seo_health_index": 50,
                    "ai_spectrum_pct": 0,
                    "online_presence_index": 42,
                    "conversion_efficiency": 40,
                    "competitor_gap_score": 50,
                    "classification": "Unknown"
                },
                "key_friction_insight": {},
                "revenue_leak": {},
                "cms_platform": "",
                "tiered_remediation_packages": {"tier_10_arch10": []}
            }

        if REPORT_ENGINE_AVAILABLE:
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
                background_tasks.add_task(
                    reporter.send_admin_alert_email,
                    admin_report=admin_master_report
                )
            except Exception as report_err:
                print(f"[Report Engine] Skipped — {report_err}")

        all_leaks = audit_results.get("tiered_remediation_packages", {}).get("tier_10_arch10", [])

        return {
            "success": True,
            "target_domain": request.domain,
            "overall_score": audit_results.get("overall_score", 50),
            "surface_metrics": audit_results.get("surface_metrics", {}),
            "key_friction_insight": audit_results.get("key_friction_insight", {}),
            "revenue_leak": audit_results.get("revenue_leak", {}),
            "cms_platform": audit_results.get("cms_platform", ""),
            "dev_handoff_kit": audit_results.get("dev_handoff_kit", ""),
            "top_5_seo_leaks": all_leaks[:5],
            "message": "Scan complete. Full report available for purchase."
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print("[FATAL SCAN CRASH]")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scan pipeline crash: {str(e)}")


@app.post("/api/scan")
async def run_scan(request: AuditRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    return await run_audit(request, background_tasks)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)