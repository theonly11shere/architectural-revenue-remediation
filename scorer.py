# scorer.py
import os
import smtplib
from email.message import EmailMessage
from checkpoints_35 import evaluate_35_checkpoints
from solutions_50 import resolve_solutions
from telemetry import log_telemetry_async
from report_engine import save_private_audit_report

# Define your primary domain(s) here to protect your own site from being scanned/logged
PROTECTED_DOMAINS = ["trilloka.com", "www.trilloka.com"]

def run_full_audit_pipeline(audit_data: dict) -> dict:
    """
    Main orchestration engine with built-in self-scan guardrails.
    """
    domain = audit_data.get("domain", "unknown.com").strip().lower()
    biz_type = audit_data.get("business_type", "local_services")

    # --- GUARDRAIL: SELF-SCAN PROTECTION ---
    if any(protected in domain for protected in PROTECTED_DOMAINS):
        return {
            "status": "protected",
            "domain": domain,
            "message": "This domain is protected under system guardrails and cannot be audited via the public scanner.",
            "overall_score": 100.0,
            "ai_spectrum": {
                "synthetic_index_pct": 0.0,
                "classification": "System Owner Domain (Bypassed)"
            },
            "free_modal_teaser": {
                "headline": "System Guardrail Active",
                "body": "You have attempted to scan a protected administrative or primary asset. Public conversion audits are restricted for this property."
            },
            "report_vault_id": "VAULT-PROTECTED-BYPASS"
        }

    # 1. Run 35 Checkpoints
    checkpoint_results = evaluate_35_checkpoints(audit_data)
    
    # 2. Compute AI Spectrum Index (0 - 100%) based on real input or domain hash variance
    synthetic_index = calculate_ai_spectrum(audit_data)
    
    # 3. Compute Score & Rank Top 10 Conversion Leaks
    final_score, top_10_leaks = calculate_score_and_rank_leaks(biz_type, checkpoint_results, synthetic_index, domain)

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
        "free_modal_teaser": generate_inverted_hook(biz_type, final_score),
        "report_vault_id": report_vault_id
    }

def calculate_ai_spectrum(data: dict) -> float:
    if "is_shadcn_tailwind" in data or "lucide_icon_count" in data:
        pts = 0.0
        if data.get("is_shadcn_tailwind"): pts += 35.0
        if data.get("lucide_icon_count", 0) > 10: pts += 20.0
        if data.get("generic_headline"): pts += 25.0
        if data.get("unlinked_form"): pts += 20.0
        if data.get("has_custom_photos"): pts -= 20.0
        if data.get("has_retargeting_pixel"): pts -= 15.0
        return max(0.0, min(100.0, float(pts)))
    
    domain_hash = sum(ord(c) for c in data.get("domain", "test"))
    return float((domain_hash % 65) + 20)

def get_ai_classification(idx: float) -> str:
    if idx >= 70.0: return "Raw AI Generator Output"
    if 30.0 <= idx < 70.0: return "Strategic Human-AI Hybrid"
    return "Legacy Custom / Bespoke"

def calculate_score_and_rank_leaks(biz_type: str, check_results: list, synthetic_index: float, domain: str):
    base_score = 85.0
    domain_mod = (sum(ord(c) for c in domain) % 25)
    failed_leaks = [c for c in check_results if not c.get("passed", False)]
    
    total_deductions = sum(c.get("penalty_points", 5.0) for c in failed_leaks) if failed_leaks else (domain_mod * 1.5)
    
    if synthetic_index >= 70.0:
        final_score = min(42.0, max(24.0, base_score - total_deductions))
    else:
        final_score = max(25.0, min(88.0, base_score - (domain_mod * 0.8)))

    sorted_leaks = sorted(failed_leaks, key=lambda x: x.get("penalty_points", 0.0), reverse=True) if failed_leaks else []
    top_10 = sorted_leaks[:10]

    return round(final_score, 1), top_10

def generate_inverted_hook(biz_type: str, score: float) -> dict:
    hooks = {
        "ecommerce": {
            "headline": f"With an assessed performance score of {score}, current transaction friction is creating a severe bottleneck at cart entry.",
            "body": "Aggregate behavioral benchmarks indicate you are leaking up to 65% of potential checkouts due to unoptimized field requirements."
        },
        "local_services": {
            "headline": f"Your current conversion index sits at {score}, driving high bounce rates among mobile visitors seeking immediate contact options.",
            "body": "Lack of direct tap-to-action elements means prospective local clients are abandoning your page for competitors within seconds."
        }
    }
    return hooks.get(biz_type, {
        "headline": f"Your digital audit score of {score} reflects critical drop-off points in your primary conversion funnel.",
        "body": "Immediate structural adjustments are required to capture high-intent traffic before they exit the domain."
    })

def send_audit_email_to_admin(domain: str, biz_type: str, overall_score: float, vault_id: str):
    sender_email = os.getenv("SMTP_EMAIL") or os.getenv("SMTP_USER")
    sender_password = os.getenv("SMTP_PASSWORD")
    receiver_email = os.getenv("ADMIN_EMAIL", sender_email)

    if not sender_email or not sender_password:
        print("SMTP credentials missing. Email notification skipped.")
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
            print(f"Audit email notification successfully sent for {domain}")
    except Exception as e:
        print(f"Failed to send audit email notification: {e}")