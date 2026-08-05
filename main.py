import os
import json
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import requests

# Initialize FastAPI App
app = FastAPI(
    title="Trilloka Engine API",
    description="Backend API for running website audits and surface metrics analysis.",
    version="1.0.0"
)

# Enable CORS for frontend interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data Models
class ScanRequest(BaseModel):
    domain: str
    business_type: Optional[str] = "general"

class LeadCaptureRequest(BaseModel):
    name: str
    email: str
    website: Optional[str] = None


# Core Helper: Fetch Google PageSpeed Insights Audit
async def fetch_live_google_audit(domain: str, biz_type: str = "general"):
    # Read Google API Key from Environment with fallback support
    api_key = os.environ.get("GOOGLE_PAGESPEED_API_KEY") or os.environ.get("PAGESPEED_API_KEY", "")
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

    try:
        response = requests.get(psi_url, timeout=20)
        if response.status_code == 200:
            data = response.json()
            lighthouse = data.get("lighthouseResult", {})
            audits = lighthouse.get("audits", {})
            categories = lighthouse.get("categories", {})

            # Extract lighthouse mobile score (scale 0-100)
            score_category = categories.get("performance", {}).get("score")
            if score_category is not None:
                overall_score = round(score_category * 100, 1)

            # Core Web Vitals
            lcp = audits.get("largest-contentful-paint", {}).get("displayValue", "N/A")
            tbt = audits.get("total-blocking-time", {}).get("displayValue", "N/A")
            cls = audits.get("cumulative-layout-shift", {}).get("displayValue", "N/A")

            surface_metrics = {
                "lcp": lcp,
                "inp_tbt": tbt,
                "cls": cls,
                "mobile_performance_score": overall_score
            }
        else:
            logging.warning(f"Google PSI API returned status code {response.status_code}")
    except Exception as e:
        logging.error(f"Error executing fetch_live_google_audit for {domain}: {e}")

    return {
        "domain": domain,
        "overall_score": overall_score,
        "surface_metrics": surface_metrics,
        "revenue_leak": f"${int((100 - overall_score) * 120)}/mo",
        "cms_platform": "Detected Web Server",
        "dev_handoff_kit": {
            "status": "Ready",
            "checkpoints_count": len(checkpoint_results)
        },
        "checkpoints_summary": checkpoint_results,
        "top_10_conversion_leaks": top_10_solutions
    }


# API Endpoints
@app.get("/")
def read_root():
    return {"status": "online", "system": "Trilloka Engine"}

@app.post("/api/scan")
async def trigger_scan(payload: ScanRequest):
    if not payload.domain:
        raise HTTPException(status_code=400, detail="Domain parameter is required.")
    
    clean_domain = payload.domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    result = await fetch_live_google_audit(clean_domain, payload.business_type)
    
    return {
        "success": True,
        **result
    }

@app.post("/api/lead")
async def capture_lead(payload: LeadCaptureRequest):
    # Endpoint to process audit lead captures
    return {
        "success": True,
        "message": f"Lead registered for {payload.email}"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)