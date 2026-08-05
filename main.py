import os
import json
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Internal Imports
from report_engine import get_recent_cached_report
from scorer import run_full_audit_pipeline

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


@app.get("/")
def read_root():
    return {"status": "online", "system": "Trilloka Engine"}


@app.post("/api/scan")
async def trigger_scan(payload: ScanRequest):
    if not payload.domain:
        raise HTTPException(status_code=400, detail="Domain parameter is required.")
    
    # Clean domain string
    clean_domain = payload.domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    biz_type = payload.business_type if payload.business_type else "general"

    # 1. Cache Check: Use cached report if domain was scanned within 60 mins
    cached_report = get_recent_cached_report(clean_domain, max_age_minutes=60)
    if cached_report:
        logging.info(f" [CACHE HIT] Serving cached audit for {clean_domain}")
        return {
            "success": True,
            "cached": True,
            **cached_report
        }

    # 2. Fresh Run: Execute clean pipeline (Google PSI + Playwright + Scorer + Vault + Resend)
    logging.info(f" [CACHE MISS] Running fresh audit pipeline for {clean_domain}")
    audit_payload = {
        "domain": clean_domain,
        "business_type": biz_type
    }
    
    try:
        scan_result = run_full_audit_pipeline(audit_payload)
        return {
            "success": True,
            "cached": False,
            **scan_result
        }
    except Exception as e:
        logging.error(f"Error executing audit pipeline for {clean_domain}: {e}")
        raise HTTPException(status_code=500, detail=f"Audit pipeline failed: {str(e)}")


@app.post("/api/lead")
async def capture_lead(payload: LeadCaptureRequest):
    return {
        "success": True,
        "message": f"Lead registered for {payload.email}"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)