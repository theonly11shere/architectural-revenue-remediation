# report_engine.py
import json
import uuid
import os
from datetime import datetime

# Automatically uses the Railway volume mount path if present, otherwise defaults to local root
vault_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")
REPORT_VAULT_FILE = os.path.join(vault_dir, "private_reports_vault.json")

ADMIN_TOKEN_ENV_VAR = "TRILLOKA_ADMIN_TOKEN"

def _verify_admin_access(token_provided: str) -> bool:
    """Verifies master admin token against environment variables."""
    master_token = os.environ.get(ADMIN_TOKEN_ENV_VAR, "SM65J3J34H34I34B34U")
    return token_provided == master_token

def save_private_audit_report(domain: str, biz_type: str, overall_score: float, checkpoint_results: list, top_10_solutions: list) -> str:
    """
    Saves the complete detailed audit report to a secure vault file.
    User only sees this report upon unlock/payment.
    """
    report_id = f"rpt_{uuid.uuid4().hex[:12]}"
    
    report_payload = {
        "report_id": report_id,
        "created_at": datetime.utcnow().isoformat(),
        "domain": domain,
        "business_type": biz_type,
        "overall_score": overall_score,
        "total_checkpoints_evaluated": len(checkpoint_results),
        "checkpoints_summary": checkpoint_results,
        "top_10_conversion_leaks": top_10_solutions,
        "is_unlocked": False
    }

    vault = {}
    if os.path.exists(REPORT_VAULT_FILE):
        try:
            with open(REPORT_VAULT_FILE, "r") as f:
                vault = json.load(f)
        except (json.JSONDecodeError, IOError):
            vault = {}

    vault[report_id] = report_payload

    try:
        with open(REPORT_VAULT_FILE, "w") as f:
            json.dump(vault, f, indent=2)
        print(f" [VAULT SECURED] Saved private report [{report_id}] for {domain}")
    except IOError as e:
        print(f" [VAULT ERROR] Could not save private report: {e}")

    return report_id

# =====================================================================
#                 ADMIN BACKDOOR / EMERGENCY VAULT ACCESS
# =====================================================================

def get_report_by_id_admin(report_id: str, admin_token: str) -> dict:
    """
    ADMIN BACKDOOR: Retrieve a specific private report from the vault.
    Bypasses paywalls using administrative verification.
    """
    if not _verify_admin_access(admin_token):
        print(" [SECURITY ALERT] Unauthorized access attempt to Vault Report.")
        return {"error": "ACCESS_DENIED: Invalid Admin Verification Token"}

    if not os.path.exists(REPORT_VAULT_FILE):
        return {"error": "Vault file does not exist yet."}

    try:
        with open(REPORT_VAULT_FILE, "r") as f:
            vault = json.load(f)
        
        report = vault.get(report_id)
        if not report:
            return {"error": f"Report ID '{report_id}' not found in vault."}

        print(f" [ADMIN ACCESS GRANTED] Retrieved report [{report_id}] for domain: {report.get('domain')}")
        return report
    except Exception as e:
        return {"error": f"Failed reading vault: {str(e)}"}

def force_unlock_report_admin(report_id: str, admin_token: str) -> dict:
    """
    ADMIN BACKDOOR: Force unlocks any report in the vault without payment.
    """
    if not _verify_admin_access(admin_token):
        return {"error": "ACCESS_DENIED: Invalid Admin Verification Token"}

    if not os.path.exists(REPORT_VAULT_FILE):
        return {"error": "Vault file does not exist."}

    try:
        with open(REPORT_VAULT_FILE, "r") as f:
            vault = json.load(f)

        if report_id in vault:
            vault[report_id]["is_unlocked"] = True
            with open(REPORT_VAULT_FILE, "w") as f:
                json.dump(vault, f, indent=2)
            print(f" [ADMIN ACTION] Force-unlocked report [{report_id}]")
            return vault[report_id]
        else:
            return {"error": "Report ID not found."}
    except Exception as e:
        return {"error": f"Failed unlocking report: {str(e)}"}