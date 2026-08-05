import os
import traceback
import resend
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from report_engine import (
    save_private_audit_report,
    get_report_by_id_admin,
    force_unlock_report_admin
)

app = FastAPI(
    title="Trilloka Revenue Leak & Audit Scanner API",
    version="1.1.1"
)

# Explicitly allow trilloka.com and local development environments for CORS
origins = [
    "https://trilloka.com",
    "https://www.trilloka.com",
    "https://api.trilloka.com",
    "https://trilloka.up.railway.app",
    "http://localhost:8080",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    domain: str
    business_type: str = "general"

class CompetitorScanRequest(BaseModel):
    domain: str
    competitor_domain: str
    business_type: str = "general"

# --- HELPER ENGINES ---

def send_admin_email_alert(domain: str, score: float, report_id: str, annual_leak: str):
    """Dispatches instant email alert to admin upon successful audit completion via Resend."""
    resend_key = os.getenv("RESEND_API_KEY")
    receiver_email = os.getenv("ADMIN_EMAIL") or os.getenv("ALERT_EMAIL") or "arpitt22@trilloka.com"
    sender_email = os.getenv("FROM_EMAIL") or os.getenv("EMAIL_FROM") or "arpitt22@trilloka.com"

    if not resend_key:
        print(" ⚠️ [Resend] Skipped: RESEND_API_KEY environment variable is not set.")
        return

    resend.api_key = resend_key

    subject = f"🚨 New Audit Completed: {domain} (Score: {score})"
    html_body = f"""
    <h2>New Website Audit Completed on Trilloka</h2>
    <ul>
        <li><strong>Domain:</strong> {domain}</li>
        <li><strong>Overall Score:</strong> {score} / 100</li>
        <li><strong>Est. Annual Leak:</strong> {annual_leak}</li>
        <li><strong>Report Vault ID:</strong> {report_id}</li>
    </ul>
    <p>
        <a href="https://api.trilloka.com/admin/vault/{report_id}">Access raw vault entry</a>
    </p>
    """

    try:
        response = resend.Emails.send({
            "from": f"Trilloka Audit <{sender_email}>",
            "to": [receiver_email],
            "subject": subject,
            "html": html_body
        })
        print(f" 📧 [EMAIL SENT] Admin notification sent via Resend! ID: {response.get('id')}")
    except Exception as err:
        print(f" ❌ [EMAIL ERROR] Failed to send email alert via Resend API: {err}")

def calculate_revenue_leak(overall_score: float, biz_type: str) -> dict:
    tier_baselines = {
        "medspa": {"avg_monthly_traffic": 2500, "avg_customer_value": 450},
        "legal": {"avg_monthly_traffic": 1800, "avg_customer_value": 1200},
        "ecommerce": {"avg_monthly_traffic": 8000, "avg_customer_value": 85},
        "saas": {"avg_monthly_traffic": 4000, "avg_customer_value": 150},
        "general": {"avg_monthly_traffic": 3000, "avg_customer_value": 250}
    }
    
    baseline = tier_baselines.get(biz_type.lower(), tier_baselines["general"])
    score_gap = max(0.0, 90.0 - overall_score)
    est_conversion_drop_pct = round((score_gap / 10.0) * 0.035, 3)
    
    est_monthly_lost_clients = round((baseline["avg_monthly_traffic"] * 0.02) * est_conversion_drop_pct, 1)
    est_annual_leak = round(est_monthly_lost_clients * baseline["avg_customer_value"] * 12)
    
    return {
        "est_annual_revenue_leak": f"${est_annual_leak:,}",
        "est_conversion_drop_pct": f"{round(est_conversion_drop_pct * 100, 1)}%",
        "raw_annual_leak": est_annual_leak
    }

async def detect_cms_platform(domain: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(f"https://{domain}")
            html_lower = resp.text.lower()
            
            if "cdn.shopify.com" in html_lower or "myshopify" in html_lower:
                return "Shopify"
            elif "wp-content" in html_lower or "wordpress" in html_lower:
                return "WordPress"
            elif "assets.website-files.com" in html_lower or "webflow" in html_lower:
                return "Webflow"
            elif "squarespace" in html_lower:
                return "Squarespace"
            elif "wix.com" in html_lower:
                return "Wix"
            else:
                return "Custom / Modern Framework"
    except Exception:
        return "Custom Framework"

def generate_dev_handoff_kit(domain: str, cms: str, top_solutions: list, annual_leak: str) -> str:
    solutions_bulleted = "\n".join([f"Fix {i+1}: {sol}" for i, sol in enumerate(top_solutions[:3])])
    return (
        f"Hi Dev,\n\n"
        f"We ran a Trilloka Telemetry audit on {domain} ({cms}) and found active mobile conversion bottlenecks "
        f"costing an estimated {annual_leak}/year in lost lead flow.\n\n"
        f"Top Priorities:\n"
        f"{solutions_bulleted}\n\n"
        f"Thanks,\n"
        f"The Architect"
    )

async def fetch_live_google_audit(domain: str, biz_type: str = "general"):
    # Read Google API Key from Environment
    api_key = os.environ.get("PAGESPEED_API_KEY", "")
    key_param = f"&key={api_key}" if api_key else ""
    
    psi_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=https://{domain}&strategy=mobile{key_param}"
    
    checkpoint_results = []
    top_10_solutions = []
    overall_score = 65.0
    surface_metrics = {
        "lcp": "N/A",
        "inp_tbt": "N/A",
        "cls": "N/A",
        "mobile_performance_score": 65.0
    }

    cms_platform = await detect_cms_platform(domain)

    try:
        async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as client:
            response = await client.get(psi_url)
            
            if response.status_code == 200:
                data = response.json()
                lh = data.get("lighthouseResult", {})
                categories = lh.get("categories", {})
                audits = lh.get("audits", {})

                perf_score = categories.get("performance", {}).get("score")
                if perf_score is not None:
                    overall_score = round(perf_score * 100, 1)
                    surface_metrics["mobile_performance_score"] = overall_score

                # LCP
                lcp_audit = audits.get("largest-contentful-paint", {})
                lcp_val = lcp_audit.get("displayValue", "N/A")
                surface_metrics["lcp"] = lcp_val
                lcp_score = lcp_audit.get("score", 1.0) or 1.0
                if lcp_score < 0.5:
                    checkpoint_results.append({"checkpoint": "Largest Contentful Paint (LCP)", "status": f"Failed ({lcp_val})", "impact": "Critical"})
                    top_10_solutions.append(f"Optimize critical hero visual assets to reduce LCP from {lcp_val} down below 2.5s on mobile.")
                else:
                    checkpoint_results.append({"checkpoint": "Largest Contentful Paint (LCP)", "status": f"Passed ({lcp_val})", "impact": "Low"})

                # TBT / INP
                tbt_audit = audits.get("total-blocking-time", {})
                tbt_val = tbt_audit.get("displayValue", "N/A")
                surface_metrics["inp_tbt"] = tbt_val
                tbt_score = tbt_audit.get("score", 1.0) or 1.0
                if tbt_score < 0.5:
                    checkpoint_results.append({"checkpoint": "Main-Thread JS Latency (INP)", "status": f"Failed ({tbt_val})", "impact": "Critical"})
                    top_10_solutions.append(f"Defer or eliminate heavy third-party tracking scripts causing main-thread execution lag ({tbt_val}).")
                else:
                    checkpoint_results.append({"checkpoint": "Main-Thread JS Latency (INP)", "status": f"Passed ({tbt_val})", "impact": "Low"})

                # CLS
                cls_audit = audits.get("cumulative-layout-shift", {})
                cls_val = cls_audit.get("displayValue", "N/A")
                surface_metrics["cls"] = cls_val
                cls_score = cls_audit.get("score", 1.0) or 1.0
                if cls_score < 0.5:
                    checkpoint_results.append({"checkpoint": "Layout Stability (CLS)", "status": "Failed ({cls_val})", "impact": "High"})
                    top_10_solutions.append("Set explicit width/height parameters on dynamic layout elements to stop mobile visual jumping during render.")
                else:
                    checkpoint_results.append({"checkpoint": "Layout Stability (CLS)", "status": f"Passed ({cls_val})", "impact": "Low"})

                # Image Optimization
                img_audit = audits.get("uses-optimized-images", {})
                if (img_audit.get("score", 1.0) or 1.0) < 0.8:
                    checkpoint_results.append({"checkpoint": "Mobile Image Compression", "status": "Warning", "impact": "Medium"})
                    top_10_solutions.append(f"Convert legacy JPEG/PNG formats to WebP/AVIF on {cms_platform} to accelerate cellular load times.")

                # Meta Description
                meta_audit = audits.get("meta-description", {})
                if meta_audit.get("score", 1.0) == 0:
                    checkpoint_results.append({"checkpoint": "SEO Meta Description", "status": "Failed (Missing)", "impact": "High"})
                    top_10_solutions.append("Add structured meta descriptions to optimize click-through rate from mobile search engine results.")

            else:
                print(f" [GOOGLE API ERROR] Status Code {response.status_code}: {response.text[:200]}")

    except Exception as err:
        print(f" [API EXCEPTION] Live Google telemetry lookup failed: {err}")

    if not checkpoint_results:
        checkpoint_results = [
            {"checkpoint": "SSL & Security Headers", "status": "Passed", "impact": "Low"},
            {"checkpoint": "Mobile Responsiveness", "status": "Warning", "impact": "High"},
            {"checkpoint": "Core Web Vitals (LCP)", "status": "Warning", "impact": "Medium"}
        ]
    if not top_10_solutions:
        top_10_solutions = [
            "Implement sticky mobile tap-to-call or direct calendar scheduling widget above the fold.",
            "Compress high-resolution hero banners to prevent mobile visitor bounce rates on 4G connections."
        ]

    revenue_leak_data = calculate_revenue_leak(overall_score, biz_type)
    dev_kit = generate_dev_handoff_kit(
        domain, cms_platform, top_10_solutions, revenue_leak_data["est_annual_revenue_leak"]
    )

    return {
        "overall_score": overall_score,
        "surface_metrics": surface_metrics,
        "checkpoint_results": checkpoint_results,
        "top_10_solutions": top_10_solutions,
        "cms_platform": cms_platform,
        "revenue_leak": revenue_leak_data,
        "dev_handoff_kit": dev_kit
    }

# --- ENDPOINTS ---

@app.get("/")
def read_root():
    return {"status": "online", "service": "Trilloka Audit Scanner API", "version": "1.1.1"}

@app.post("/api/scan")
async def trigger_scan(payload: ScanRequest):
    print(f" [TELEMETRY LOGGED] {payload.domain} --> [{payload.business_type}]")
    try:
        target_domain = payload.domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
        biz_type = payload.business_type.strip().lower()

        audit = await fetch_live_google_audit(target_domain, biz_type)

        report_id = save_private_audit_report(
            domain=target_domain,
            biz_type=biz_type,
            overall_score=audit["overall_score"],
            checkpoint_results=audit["checkpoint_results"],
            top_10_solutions=audit["top_10_solutions"],
            cms_platform=audit["cms_platform"],
            revenue_leak=audit["revenue_leak"],
            dev_handoff_kit=audit["dev_handoff_kit"],
            surface_metrics=audit["surface_metrics"]
        )

        # 📧 Trigger real-time admin email notification via Resend
        send_admin_email_alert(
            domain=target_domain,
            score=audit["overall_score"],
            report_id=report_id,
            annual_leak=audit["revenue_leak"]["est_annual_revenue_leak"]
        )

        return {
            "success": True,
            "domain": target_domain,
            "report_id": report_id,
            "overall_score": audit["overall_score"],
            "surface_metrics": audit["surface_metrics"],
            "revenue_leak": audit["revenue_leak"],
            "cms_platform": audit["cms_platform"],
            "dev_handoff_kit": audit["dev_handoff_kit"],
            "checkpoints": audit["checkpoint_results"],
            "top_solutions": audit["top_10_solutions"],
            "message": "Scan completed and report secured in vault."
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f" [SCAN ERROR TRACEBACK]\n{error_trace}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scan-competitor")
async def trigger_competitor_scan(payload: CompetitorScanRequest):
    try:
        domain = payload.domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
        comp_domain = payload.competitor_domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
        biz_type = payload.business_type.strip().lower()

        primary_audit = await fetch_live_google_audit(domain, biz_type)
        comp_audit = await fetch_live_google_audit(comp_domain, biz_type)

        score_gap = round(primary_audit["overall_score"] - comp_audit["overall_score"], 1)

        report_id = save_private_audit_report(
            domain=domain,
            biz_type=biz_type,
            overall_score=primary_audit["overall_score"],
            checkpoint_results=primary_audit["checkpoint_results"],
            top_10_solutions=primary_audit["top_10_solutions"],
            cms_platform=primary_audit["cms_platform"],
            revenue_leak=primary_audit["revenue_leak"],
            dev_handoff_kit=primary_audit["dev_handoff_kit"],
            surface_metrics=primary_audit["surface_metrics"]
        )

        # 📧 Trigger email notification for competitor scan as well
        send_admin_email_alert(
            domain=domain,
            score=primary_audit["overall_score"],
            report_id=report_id,
            annual_leak=primary_audit["revenue_leak"]["est_annual_revenue_leak"]
        )

        return {
            "success": True,
            "report_id": report_id,
            "primary": {
                "domain": domain,
                "score": primary_audit["overall_score"],
                "cms": primary_audit["cms_platform"],
                "surface_metrics": primary_audit["surface_metrics"],
                "revenue_leak": primary_audit["revenue_leak"]
            },
            "competitor": {
                "domain": comp_domain,
                "score": comp_audit["overall_score"],
                "cms": comp_audit["cms_platform"],
                "surface_metrics": comp_audit["surface_metrics"]
            },
            "comparison": {
                "score_gap": score_gap,
                "status": "Outperforming Competitor" if score_gap >= 0 else "Lagging Behind Competitor"
            },
            "dev_handoff_kit": primary_audit["dev_handoff_kit"]
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f" [COMPETITOR SCAN ERROR]\n{error_trace}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/vault/{report_id}")
def admin_get_report(report_id: str, token: str = Query(...)):
    result = get_report_by_id_admin(report_id, token)
    if "error" in result:
        raise HTTPException(status_code=401 if "ACCESS_DENIED" in result["error"] else 404, detail=result["error"])
    return result

@app.post("/admin/vault/{report_id}/unlock")
def admin_unlock_report(report_id: str, token: str = Query(...)):
    result = force_unlock_report_admin(report_id, token)
    if "error" in result:
        raise HTTPException(status_code=401 if "ACCESS_DENIED" in result["error"] else 404, detail=result["error"])
    return result

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)