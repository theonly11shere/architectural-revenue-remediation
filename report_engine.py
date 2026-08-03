import json
import uuid
import os
from datetime import datetime

# Automatically checks Railway volume mount path, standard /data path, or defaults to local root[cite: 1]
vault_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/data" if os.path.exists("/data") else ".")
REPORT_VAULT_FILE = os.path.join(vault_dir, "private_reports_vault.json")

ADMIN_TOKEN_ENV_VAR = "TRILLOKA_ADMIN_TOKEN"

def _verify_admin_access(token_provided: str) -> bool:
    """Verifies master admin token against environment variables."""[cite: 1]
    master_token = os.environ.get(ADMIN_TOKEN_ENV_VAR, "SM65J3J34H34I34B34U")[cite: 1]
    return token_provided == master_token[cite: 1]

def save_private_audit_report(domain: str, biz_type: str, overall_score: float, checkpoint_results: list, top_10_solutions: list) -> str:
    """
    Saves the complete detailed audit report to a secure vault file.
    User only sees this report upon unlock/payment.
    """[cite: 1]
    report_id = f"rpt_{uuid.uuid4().hex[:12]}"[cite: 1]
    
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
    }[cite: 1]

    vault = {}
    if os.path.exists(REPORT_VAULT_FILE):
        try:
            with open(REPORT_VAULT_FILE, "r") as f:
                vault = json.load(f)
        except (json.JSONDecodeError, IOError):
            vault = {}[cite: 1]

    vault[report_id] = report_payload[cite: 1]

    try:
        with open(REPORT_VAULT_FILE, "w") as f:
            json.dump(vault, f, indent=2)
        print(f" [VAULT SECURED] Saved private report [{report_id}] for {domain}")
    except IOError as e:
        print(f" [VAULT ERROR] Could not save private report: {e}")[cite: 1]

    return report_id[cite: 1]

# =====================================================================
#                 ADMIN BACKDOOR / EMERGENCY VAULT ACCESS
# =====================================================================

def get_report_by_id_admin(report_id: str, admin_token: str) -> dict:
    """
    ADMIN BACKDOOR: Retrieve a specific private report from the vault.
    Bypasses paywalls using administrative verification.
    """[cite: 1]
    if not _verify_admin_access(admin_token):
        print(" [SECURITY ALERT] Unauthorized access attempt to Vault Report.")
        return {"error": "ACCESS_DENIED: Invalid Admin Verification Token"}[cite: 1]

    if not os.path.exists(REPORT_VAULT_FILE):
        return {"error": "Vault file does not exist yet."}[cite: 1]

    try:
        with open(REPORT_VAULT_FILE, "r") as f:
            vault = json.load(f)
        
        report = vault.get(report_id)
        if not report:
            return {"error": f"Report ID '{report_id}' not found in vault."}

        print(f" [ADMIN ACCESS GRANTED] Retrieved report [{report_id}] for domain: {report.get('domain')}")
        return report
    except Exception as e:
        return {"error": f"Failed reading vault: {str(e)}"}[cite: 1]

def force_unlock_report_admin(report_id: str, admin_token: str) -> dict:
    """
    ADMIN BACKDOOR: Force unlocks any report in the vault without payment.
    """[cite: 1]
    if not _verify_admin_access(admin_token):
        return {"error": "ACCESS_DENIED: Invalid Admin Verification Token"}[cite: 1]

    if not os.path.exists(REPORT_VAULT_FILE):
        return {"error": "Vault file does not exist."}[cite: 1]

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
        return {"error": f"Failed unlocking report: {str(e)}"}[cite: 1]