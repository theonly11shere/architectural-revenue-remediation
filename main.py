import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scorer import run_full_audit_pipeline

app = FastAPI(title="Trilloka Revenue Leak Scanner API")

# Configure CORS so the frontend can communicate with the backend across ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local testing
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (POST, GET, etc.)
    allow_headers=["*"],  # Allows all headers
)

class ScanRequest(BaseModel):
    domain: str
    business_type: str

@app.get("/")
async def root():
    """
    Root endpoint to verify the API is online and prevent 404s on base URL visits.
    """
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
        
        # Executes the checkpoints, logs telemetry, saves private vault, and emails you
        result = run_full_audit_pipeline(audit_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)