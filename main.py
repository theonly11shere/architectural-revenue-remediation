import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scorer import run_full_audit_pipeline
from report_engine import get_report_by_id_admin

app = FastAPI(title="Trilloka Revenue Leak Scanner API")

# Enable CORS for production domain connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from trilloka.com
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    domain: str
    business_type: str

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Trilloka Revenue Leak & Audit Scanner API",
        "docs_url": "/docs"
    }

@app.post("/api/scan")
async def scan_website_endpoint(payload: ScanRequest):
    try:
        audit_data = {
            "domain": payload.domain,
            "business_type": payload.business_type
        }
        
        result = run_full_audit_pipeline(audit_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/vault/{report_id}")
def view_vault_report(report_id: str, token: str):
    """Admin endpoint to view secured audit reports directly from the server vault."""
    master_token = os.environ.get("TRILLOKA_ADMIN_TOKEN", "SM65J3J34H34I34B34U")
    if token != master_token:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid Admin Verification Token")
    return get_report_by_id_admin(report_id, token)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)