import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from scorer import run_full_audit_pipeline

app = FastAPI(title="Trilloka Revenue Leak Scanner API")

class ScanRequest(BaseModel):
    domain: str
    business_type: str

@app.post("/api/scan")
async def scan_website_endpoint(payload: ScanRequest):
    try:
        audit_data = {
            "domain": payload.domain,
            "business_type": payload.business_type
        }
        
        # Executes the 35 checkpoints, logs telemetry, saves private vault, and emails you
        result = run_full_audit_pipeline(audit_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)