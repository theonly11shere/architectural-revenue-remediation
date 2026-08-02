import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scorer import run_full_audit_pipeline

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)