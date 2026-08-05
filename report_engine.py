import os
import json
import datetime
from typing import Dict, Any, List

class ReportGenerator:
    """
    Trilloka Architect Engine:
    - Generates 1 Master Admin Report (Top 15 Leaks, 3-Angle Solutions, 50 Checkpoints, Roadmap).
    - Archives 1 Raw Telemetry Snapshot to the Vault.
    """

    def generate_admin_master_report(self, audit_data: Dict[str, Any], scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generates the master Admin Report for Architect review."""
        leaks = audit_data.get("tiered_remediation_packages", {}).get("tier_10_arch10", [])
        
        # Take Top 15 Leaks for the Admin
        top_15_leaks = leaks[:15]
        
        # Build 3-Angle Solutions for each leak
        enriched_leaks = []
        for leak in top_15_leaks:
            enriched_leaks.append({
                "id": leak.get("id"),
                "severity_score": leak.get("severity_score"),
                "leak_name": leak.get("leak_name"),
                "impact_summary": leak.get("impact_summary"),
                "solutions_3_angles": {
                    "angle_1_technical": f"Fix server/code infrastructure for {leak.get('leak_name')}.",
                    "angle_2_cro_ux": f"Optimize user visual flow and reduce friction related to {leak.get('leak_name')}.",
                    "angle_3_copy_strategy": f"Adjust messaging & value proposition around {leak.get('leak_name')}."
                }
            })

        admin_payload = {
            "report_type": "ADMIN_MASTER_ARCHITECT_REPORT",
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "target_domain": audit_data.get("target_domain"),
            "business_type": audit_data.get("business_type"),
            "overall_health_score": audit_data.get("overall_health_score"),
            "score_rating": audit_data.get("score_rating"),
            "top_15_financial_leaks": enriched_leaks,
            "full_50_checkpoint_basis": {
                "total_checkpoints_assessed": 50,
                "passed": 50 - audit_data.get("total_leaks_found", 0),
                "failed": audit_data.get("total_leaks_found", 0),
                "behavioral_diagnostics": audit_data.get("behavioral_diagnostics", {})
            },
            "one_month_implementation_roadmap": [
                {"week": 1, "focus": "Critical Trust & SSL/Security Patches"},
                {"week": 2, "focus": "Mobile CTA & Click-To-Call Conversion Friction"},
                {"week": 3, "focus": "Core Web Vitals & Mobile Latency Optimization"},
                {"week": 4, "focus": "E-E-A-T Anchors & Copywriting Alignment"}
            ]
        }
        return admin_payload

    def archive_to_vault(self, target_domain: str, admin_report: Dict[str, Any], raw_scan_data: Dict[str, Any]) -> str:
        """Stores immutable snapshot in local vault directory or DB."""
        vault_dir = "./vault_archives"
        os.makedirs(vault_dir, exist_ok=True)
        
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        sanitized_domain = target_domain.replace("https://", "").replace("http://", "").replace("/", "_")
        filename = f"{vault_dir}/{sanitized_domain}_{timestamp}.json"
        
        vault_entry = {
            "vault_id": f"VAULT-{timestamp}",
            "domain": target_domain,
            "archived_at": datetime.datetime.utcnow().isoformat(),
            "admin_report": admin_report,
            "raw_telemetry": raw_scan_data
        }
        
        with open(filename, "w") as f:
            json.dump(vault_entry, f, indent=2)
            
        print(f"[Vault] Archived scan snapshot to {filename}")
        return filename