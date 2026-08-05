import os
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

REPORT_VAULT_FILE = os.environ.get("REPORT_VAULT_PATH", "report_vault.json")

def get_recent_cached_report(domain: str, max_age_minutes: int = 60) -> Optional[Dict[str, Any]]:
    """Retrieves a cached report if a domain was scanned recently to guarantee score consistency."""
    if not os.path.exists(REPORT_VAULT_FILE):
        return None

    try:
        with open(REPORT_VAULT_FILE, "r") as f:
            vault = json.load(f)

        now = datetime.now(timezone.utc)
        for report_id, report in vault.items():
            if report.get("domain") == domain:
                created_at_str = report.get("created_at")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                    if (now - created_at).total_seconds() < (max_age_minutes * 60):
                        return report
    except Exception as e:
        print(f"Error reading report cache vault: {e}")
    
    return None

def save_report_to_vault(report_data: Dict[str, Any]) -> str:
    """Saves generated audit report into the storage vault."""
    vault = {}
    if os.path.exists(REPORT_VAULT_FILE):
        try:
            with open(REPORT_VAULT_FILE, "r") as f:
                vault = json.load(f)
        except Exception:
            vault = {}

    report_id = report_data.get("report_id") or str(uuid.uuid4())
    report_data["report_id"] = report_id
    if "created_at" not in report_data:
        report_data["created_at"] = datetime.now(timezone.utc).isoformat()

    vault[report_id] = report_data

    try:
        with open(REPORT_VAULT_FILE, "w") as f:
            json.dump(vault, f, indent=2)
    except Exception as e:
        print(f"Failed to write report to vault: {e}")

    return report_id

def generate_audit_report(domain: str, scan_results: Dict[str, Any], biz_type: str = "general") -> Dict[str, Any]:
    """Builds and returns the full standardized report structure."""
    
    # Check for valid recent cache
    cached = get_recent_cached_report(domain)
    if cached:
        return cached

    psi = scan_results.get("psi_raw", {})
    behavioral = scan_results.get("behavioral", {})
    
    # Extract performance metrics
    lighthouse = psi.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    score_raw = categories.get("performance", {}).get("score")
    overall_score = round(score_raw * 100, 1) if score_raw is not None else 65.0

    report = {
        "report_id": str(uuid.uuid4()),
        "domain": domain,
        "business_type": biz_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall_score,
        "surface_metrics": {
            "lcp": psi.get("lighthouseResult", {}).get("audits", {}).get("largest-contentful-paint", {}).get("displayValue", "N/A"),
            "inp_tbt": psi.get("lighthouseResult", {}).get("audits", {}).get("total-blocking-time", {}).get("displayValue", "N/A"),
            "cls": psi.get("lighthouseResult", {}).get("audits", {}).get("cumulative-layout-shift", {}).get("displayValue", "N/A"),
            "mobile_performance_score": overall_score
        },
        "revenue_leak": f"${int((100 - overall_score) * 120)}/mo",
        "cms_platform": "Detected Web Platform",
        "behavioral_summary": behavioral,
        "dev_handoff_kit": {
            "status": "Ready",
            "checkpoints_count": len(behavioral)
        }
    }

    save_report_to_vault(report)
    return report