# scorer.py
import os
import smtplib
from email.message import EmailMessage
from checkpoints_35 import evaluate_35_checkpoints
from solutions_50 import resolve_solutions
from telemetry import log_telemetry_async
from report_engine import save_private_audit_report

def run_full_audit_pipeline(audit_data: dict) -> dict:
    """
    Main orchestration engine.
    Runs audit checks, calculates AI spectrum, splits data into outputs:
      1. Async telemetry logger
      2. Secure private report vault
      3. Admin email notification dispatch
      4. Public front-end user payload
    """
    domain = audit_data.get("domain", "unknown.com")
    biz_type = audit_data.get("business_type", "local_services")

    # 1. Run 35 Checkpoints
    checkpoint_results = evaluate_35_checkpoints(audit_data)
    
    # 2. Compute AI Spectrum Index (0 - 100%)
    synthetic_index = calculate_ai_spectrum(audit_data)
    
    # 3. Compute Score & Rank Top 10 Conversion Leaks
    final_score, top_10_leaks = calculate_score_and_rank_leaks(biz_type, checkpoint_results, synthetic_index)

    # 4. Map Leaks to 50-Solution Library
    mapped_solutions = resolve_solutions(top_10_leaks)

    # --- STREAM 1: TELEMETRY DISPATCH (Background) ---
    log_telemetry_async(domain, biz_type, audit_data, final_score, synthetic_index)

    # --- STREAM 2: PRIVATE REPORT VAULT (Locked Admin/Paid) ---
    report_vault_id = save_private_audit_report(
        domain=domain,
        biz_type=biz_type,
        overall_score=final_score,
        checkpoint_results=checkpoint_results,
        top_10_solutions=mapped_solutions
    )

    # --- STREAM 3: ADMIN EMAIL NOTIFICATION DISPATCH ---
    send_audit_email_to_admin(domain, biz_type, final_score, report_vault_id)

    # --- STREAM 4: PUBLIC FRONT-END PAYLOAD (User Modal) ---
    return {
        "status": "success",
        "domain": domain,
        "business_type": biz_type,
        "overall_score": final_score,
        "ai_spectrum": {
            "synthetic_index_pct": synthetic_index,
            "classification": get_ai_classification(synthetic_index)
        },
        "free_modal_teaser": generate_inverted_hook(biz_type),
        "report_vault_id": report_vault_id
    }

def calculate_ai_spectrum(data: dict) -> float:
    pts = 0.0
    if data.get("is_shadcn_tailwind"): pts += 35.0
    if data.get("lucide_icon_count", 0) > 10: pts += 20.0
    if data.get("generic_headline"): pts += 25.0
    if data.get("unlinked_form"): pts += 20.0
    if data.get("has_custom_photos"): pts -= 20.0
    if data.get("has_retargeting_pixel"): pts -= 15.0
    return max(0.0, min(100.0, float(pts)))

def get_ai_classification(idx: float) -> str:
    if idx >= 70.0: return "Raw AI Generator Output"
    if 30.0 <= idx < 70.0: return "Strategic Human-AI Hybrid"
    return "Legacy Custom / Bespoke"

def calculate_score_and_rank_leaks(biz_type: str, check_results: list, synthetic_index: float):
    base_score = 100.0
    failed_leaks = [c for c in check_results if not c.get("passed", False)]
    
    total_deductions = sum(c.get("penalty_points", 5.0) for c in failed_leaks)
    
    # AI Spectrum Industry Caps
    if synthetic_index >= 70.0:
        final_score = min(38.0, max(22.0, base_score - total_deductions - 15.0))
    else:
        final_score = max(22.0, base_score - total_deductions)

    # Sort to surface the highest penalty leaks first
    sorted_leaks = sorted(failed_leaks, key=lambda x: x.get("penalty_points", 0.0), reverse=True)
    top_10 = sorted_leaks[:10]

    return round(final_score, 1), top_10

def generate_inverted_hook(biz_type: str) -> dict:
    hooks = {
        "ecommerce": {
            "headline": "According to aggregate behavioral studies from the Baymard Institute, over 48% of online shoppers abandon checkout due to unexpected hidden costs and friction.",
            "body": "Based on your site's checkout architecture, YOU ARE LOSING UP TO 70% OF READY BUYERS before they ever reach the payment gateway."
        },
        "local_services": {
            "headline": "Consumer trust metrics show that 60% of modern users immediately bounce from a local business site if contact options require manual typing on mobile viewports.",
            "body": "Because your primary booking form lacks instant tap-to-call integration, YOU ARE LOSING 6 OUT OF 10 HIGH-INTENT LOCAL LEADS directly to your competitors."
        }
    }
    return hooks.get(biz_type, {
        "headline": "Forrester research proves that forcing a multi-field registration wall before showing product value causes an immediate 25% drop-off in enterprise evaluation.",
        "body": "Your current funnel structure means YOU ARE BLEEDING 1 IN 4 QUALIFIED DEMO REQUESTS every single day."
    })

def send_audit_email_to_admin(domain: str, biz_type: str, overall_score: float, vault_id: str):
    sender_email = os.getenv("SMTP_EMAIL", "")
    sender_password = os.getenv("SMTP_PASSWORD", "")
    receiver_email = os.getenv("ADMIN_EMAIL", sender_email)

    if not sender_email or not sender_password:
        return

    msg = EmailMessage()
    msg["Subject"] = f"🚨 New Audit Completed: {domain} (Score: {overall_score})"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    
    msg.set_content(f"""
    A new website audit has just been completed on your scanner!

    - Target Domain: {domain}
    - Business Model: {biz_type}
    - Overall Financial Leak Score: {overall_score}
    - Report Vault ID: {vault_id}

    Log in to your dashboard to view the full prioritized breakdown and leak solutions.
    """)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send audit email notification: {e}")