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


def save_private_audit_report(
    domain: str,
    biz_type: str,
    overall_score: float,
    checkpoint_results: list,
    top_10_solutions: list,
    report_vault_id: Optional[str] = None
) -> str:
    """Saves generated private audit report into the storage vault."""
    vault = {}
    if os.path.exists(REPORT_VAULT_FILE):
        try:
            with open(REPORT_VAULT_FILE, "r") as f:
                vault = json.load(f)
        except Exception:
            vault = {}

    report_id = report_vault_id or str(uuid.uuid4())
    
    report_data = {
        "report_id": report_id,
        "domain": domain,
        "business_type": biz_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall_score,
        "surface_metrics": {
            "overall_score": overall_score,
            "seo_health_index": max(10.0, round(overall_score * 0.9, 1)),
            "conversion_efficiency": overall_score,
            "competitor_gap_score": round(max(10.0, 100.0 - overall_score), 1),
            "online_presence_index": round(max(10.0, min(95.0, overall_score * 0.95)), 1)
        },
        "revenue_leak": f"${int((100 - overall_score) * 120)}/mo",
        "dev_handoff_kit": {
            "status": "Ready",
            "checkpoints_count": len(checkpoint_results)
        },
        "checkpoints_summary": checkpoint_results,
        "top_10_conversion_leaks": top_10_solutions
    }

    vault[report_id] = report_data

    try:
        with open(REPORT_VAULT_FILE, "w") as f:
            json.dump(vault, f, indent=2)
    except Exception as e:
        print(f"Failed to write report to vault: {e}")

    return report_id