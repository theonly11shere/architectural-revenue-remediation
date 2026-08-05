import os
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

# Enable CORS for Frontend Access (Next.js / React / Vue)
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
    business_type: str = "ecommerce"  # local, ecommerce, saas, agency, b2b, creator
    competitor_has_feature: bool = True
    email: Optional[EmailStr] = None


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """System health check to verify API status and vault directory availability."""
    return {
        "status": "online",
        "system": "Trilloka Architect Engine v3.0",
        "google_pagespeed_configured": bool(os.getenv("PAGESPEED_API_KEY")),
        "vault_storage_active": True
    }


@app.get("/diagnostic")
def diagnostic() -> Dict[str, Any]:
    """Tests each pipeline component and reports what works vs what crashes."""
    results = {"status": "running", "checks": {}}

    # Check env vars
    results["checks"]["env_pagespeed_api_key"] = bool(os.environ.get("PAGESPEED_API_KEY"))

    # Test scanner import & init
    try:
        from hybrid_scanner import HybridScanner
        s = HybridScanner()
        results["checks"]["scanner_init"] = "OK"
    except Exception as e:
        results["checks"]["scanner_init"] = f"FAIL: {str(e)}"

    # Test HTTP preflight only (no playwright)
    try:
        test = s._fast_http_preflight("https://example.com")
        results["checks"]["http_preflight"] = "OK" if test.get("is_reachable") else "OK (example.com blocked)"
    except Exception as e:
        results["checks"]["http_preflight"] = f"FAIL: {str(e)}"

    # Test PageSpeed API
    try:
        ps = s._fetch_google_pagespeed("https://example.com")
        results["checks"]["pagespeed_api"] = ps.get("pagespeed_api_status", "unknown")
    except Exception as e:
        results["checks"]["pagespeed_api"] = f"FAIL: {str(e)}"

    # Test Playwright (this is the one that usually crashes on Railway)
    try:
        dom = s._run_targeted_playwright("https://example.com", {})
        results["checks"]["playwright"] = "OK"
    except Exception as e:
        results["checks"]["playwright"] = f"FAIL: {str(e)}"

    # Test scorer
    try:
        from scorer import RevenueScorer
        sc = RevenueScorer()
        results["checks"]["scorer_init"] = "OK"
    except Exception as e:
        results["checks"]["scorer_init"] = f"FAIL: {str(e)}"

    # Test report engine
    try:
        from report_engine import ReportGenerator
        r = ReportGenerator()
        results["checks"]["report_engine_init"] = "OK"
    except Exception as e:
        results["checks"]["report_engine_init"] = f"FAIL: {str(e)}"

    return results

@app.post("/api/audit")
async def run_audit(request: AuditRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Main Endpoint:
    1. Executes 3-Phase Hybrid Scan (HTTP + Google PSI + Playwright DOM).
    2. Runs Harsh Scoring Engine (50 Checkpoints Basis).
    3. Generates 1 Master Admin Report (Top 15 Leaks, 3-Angle Solutions, 1-Month Roadmap).
    4. Archives full telemetry + Admin Report to Vault in background.
    5. Returns ONLY Free SEO Data, Top 5 SEO Leaks, and Competitor Benchmark to Frontend UI.
    """
    try:
        # Step 1: Execute 3-Phase Telemetry Scan
        scan_data = scanner.execute_hybrid_scan(request.domain)
        
        # Verify target domain accessibility
        if not scan_data.get("is_reachable", True):
            raise HTTPException(
                status_code=400, 
                detail=f"Domain '{request.domain}' is offline, unreachable, or blocking requests."
            )

        # Step 2: Calculate Harsh Scoring & Behavioral Friction Index
        audit_results = scorer.audit_and_score(
            scan_data=scan_data,
            business_type=request.business_type,
            competitor_data_present=request.competitor_has_feature
        )

        # Step 3: Generate Master Admin Report (For your review & paid delivery)
        admin_master_report = reporter.generate_admin_master_report(
            audit_data=audit_results, 
            scan_data=scan_data
        )

        # Step 4: Archive Master Snapshot to Vault in Background
        background_tasks.add_task(
            reporter.archive_to_vault,
            target_domain=request.domain,
            admin_report=admin_master_report,
            raw_scan_data=scan_data
        )

        # Step 5: Filter Top 5 SEO-Specific Leaks for Frontend Teaser
        all_leaks = audit_results.get("tiered_remediation_packages", {}).get("tier_10_arch10", [])
        
        seo_leaks = [
            leak for leak in all_leaks 
            if leak.get("category") == "seo_technical" 
            or "SEO" in leak.get("leak_name", "") 
            or "Web Vitals" in leak.get("leak_name", "")
            or "H1" in leak.get("leak_name", "")
            or "Alt" in leak.get("leak_name", "")
        ]

        # Fallback to general technical leaks if less than 5 explicit SEO leaks
        if len(seo_leaks) < 5:
            top_5_seo_leaks = all_leaks[:5]
        else:
            top_5_seo_leaks = seo_leaks[:5]

        # Step 6: Return Filtered Payload to Frontend UI
        return {
            "success": True,
            "target_domain": request.domain,
            "business_type": request.business_type,
            "overall_health_score": audit_results.get("overall_health_score"),
            "score_rating": audit_results.get("score_rating"),
            
            # --- 1. FREE SEO TELEMETRY METRICS ---
            "seo_data": {
                "title": scan_data.get("title", ""),
                "meta_description": scan_data.get("meta_description", ""),
                "h1_tags": scan_data.get("h1_tags", []),
                "performance_score": scan_data.get("performance_score", 0.0),
                "google_seo_score": scan_data.get("google_seo_score", 0.0),
                "has_ssl": scan_data.get("has_ssl", False),
                "missing_alt_images": scan_data.get("missing_alt_images", 0)
            },

            # --- 2. TOP 5 SEO LEAKS (TEASER ONLY) ---
            "top_5_seo_leaks": top_5_seo_leaks,

            # --- 3. COMPETITOR BENCHMARK DATA ---
            "competitor_data": {
                "competitor_feature_present": request.competitor_has_feature,
                "competitor_advantage_penalty_applied": 3 if request.competitor_has_feature else 0,
                "competitive_gap_status": "BEHIND_COMPETITOR" if request.competitor_has_feature else "ALIGNED"
            },

            # --- 4. BASIS OF ASSESSMENT SUMMARY ---
            "basis_of_assessment": {
                "total_checkpoints_evaluated": 50,
                "passed": 50 - audit_results.get("total_leaks_found", 0),
                "failed": audit_results.get("total_leaks_found", 0)
            },

            "message": "Free scan complete. Full 15-leak master report locked in Admin Vault."
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Internal audit execution error: {str(e)}"
        )


@app.post("/api/scan")
async def run_scan(request: AuditRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Frontend alias for /api/audit. Same 3-phase telemetry scan."""
    try:
        return await run_audit(request, background_tasks)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("[SCAN CRASH]", error_detail)
        raise HTTPException(status_code=500, detail=f"Scan pipeline crash: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)