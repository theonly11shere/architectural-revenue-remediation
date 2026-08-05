# scorer.py
import os
import random
import string
import resend
from hybrid_scanner import collect_scan_data
from checkpoints_35 import evaluate_35_checkpoints
from solutions_50 import resolve_solutions
from telemetry import log_telemetry_async
from report_engine import save_private_audit_report

PROTECTED_DOMAINS = ["trilloka.com", "www.trilloka.com"]

# --- MATRIX CONFIGURATIONS ---
BUSINESS_MODEL_MULTIPLIERS = {
    "local": {"Trust": 1.5, "Conversion": 1.5, "SEO": 0.9},
    "local_services": {"Trust": 1.5, "Conversion": 1.5, "SEO": 0.9},
    "ecommerce": {"Trust": 1.4, "Conversion": 1.5, "SEO": 1.2},
    "shopify": {"Trust": 1.4, "Conversion": 1.5, "SEO": 1.2},
    "saas": {"Trust": 1.3, "Conversion": 1.4, "SEO": 1.1},
    "agency": {"Trust": 1.4, "Conversion": 1.3, "SEO": 1.0},
    "b2b": {"Trust": 1.4, "Conversion": 1.2, "SEO": 1.0},
    "creator": {"Trust": 1.0, "Conversion": 1.1, "SEO": 1.3},
    "general": {"Trust": 1.0, "Conversion": 1.0, "SEO": 1.0}
}

CATEGORY_WEIGHTS = {
    "Trust": 1.25,
    "Conversion": 1.25,
    "SEO": 1.0,
    "Technical": 1.0,
    "Content": 0.9,
    "E-E-A-T": 0.9
}

TIER_PREFIXES = {
    3: "IFYB3",   # Tier 3: Important for your business
    6: "MBTB6",   # Tier 6: Making your business the best
    8: "NOLY8",   # Tier 8: No one like you
    10: "ARCH10"  # Tier 10: The Architect
}


def generate_vault_id(score: float) -> str:
    if score >= 90:
        tier = 10
    elif score >= 75:
        tier = 8
    elif score >= 50:
        tier = 6
    else:
        tier = 3

    prefix = TIER_PREFIXES.get(tier, "IFYB3")
    rand_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{rand_suffix}"


def run_full_audit_pipeline(audit_data: dict) -> dict:
    domain = audit_data.get("domain", "unknown.com").strip().lower()
    biz_type = audit_data.get("business_type", "local_services").strip().lower()

    # --- GUARDRAIL: SELF-SCAN PROTECTION ---
    if any(protected in domain for protected in PROTECTED_DOMAINS):
        return {
            "status": "protected",
            "domain": domain,
            "message": "This domain is protected under system guardrails and cannot be audited via the public scanner.",
            "overall_score": 100.0,
            "surface_metrics": {
                "seo_health_index": 100.0,
                "conversion_efficiency": 100.0,
                "competitor_gap_score": 0.0,
                "ai_spectrum_pct": 0.0,
                "online_presence_index": 100.0,
                "classification": "System Owner Domain (Bypassed)"
            },
            "free_modal_teaser": {
                "headline": "System Guardrail Active",
                "body": "You have attempted to scan a protected administrative or primary asset."
            },
            "report_vault_id": "ARCH10-PROTECTED"
        }

    # 1. Collect live Google PSI + Playwright Behavioral Data
    live_findings = collect_scan_data(domain)
    audit_data.update(live_findings.get("behavioral", {}))
    audit_data["psi_raw"] = live_findings.get("psi_raw", {})

    # 2. Evaluate 35 Checkpoints
    checkpoint_results = evaluate_35_checkpoints(audit_data)
    
    # 3. Compute AI Spectrum Index
    synthetic_index = calculate_ai_spectrum(audit_data)
    
    # 4. Compute Score & Rank Top 10 Leaks (Harsh & Industry-Weighted)
    final_score, top_10_leaks = calculate_harsh_score_and_rank_leaks(biz_type, checkpoint_results, synthetic_index)

    # 5. Map Solutions
    mapped_solutions = resolve_solutions(top_10_leaks)

    report_vault_id = generate_vault_id(final_score)

    log_telemetry_async(domain, biz_type, audit_data, final_score, synthetic_index)

    save_private_audit_report(
        domain=domain,
        biz_type=biz_type,
        overall_score=final_score,
        checkpoint_results=checkpoint_results,
        top_10_solutions=mapped_solutions
    )

    send_audit_email_to_admin(domain, biz_type, final_score, report_vault_id)

    second_leak = top_10_leaks[1] if len(top_10_leaks) > 1 else (top_10_leaks[0] if top_10_leaks else {})
    second_leak_reason = second_leak.get("description", second_leak.get("name", "Suboptimal mobile conversion path."))
    second_leak_severity = second_leak.get("financial_leak_score", 12.0)
    revenue_loss_pct = round(min(75.0, max(8.0, second_leak_severity * 2.8)), 1)
    
    online_presence_index = round(max(10.0, min(95.0, final_score * 0.95)), 1)

    return {
        "status": "success",
        "domain": domain,
        "business_type": biz_type,
        "surface_metrics": {
            "overall_score": final_score,
            "seo_health_index": max(10.0, round(final_score * 0.9, 1)),
            "conversion_efficiency": final_score,
            "competitor_gap_score": round(max(10.0, 100.0 - final_score), 1),
            "ai_spectrum_pct": synthetic_index,
            "online_presence_index": online_presence_index,
            "classification": get_ai_classification(synthetic_index)
        },
        "key_friction_insight": {
            "target_leak_rank": 2,
            "reason": second_leak_reason,
            "revenue_loss_pct": revenue_loss_pct
        },
        "free_modal_teaser": generate_inverted_hook(biz_type, final_score),
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


def calculate_harsh_score_and_rank_leaks(biz_type: str, check_results: list, synthetic_index: float):
    biz_multipliers = BUSINESS_MODEL_MULTIPLIERS.get(biz_type, BUSINESS_MODEL_MULTIPLIERS["general"])
    failed_leaks = [c for c in check_results if not c.get("passed", False)]
    
    total_weighted_deduction = 0.0

    for leak in failed_leaks:
        category = leak.get("category", "Conversion")
        base_weight = leak.get("base_impact_weight", leak.get("penalty_points", 5.0))
        
        competitor_bonus = 3.0 if leak.get("competitor_advantage", False) else 0.0
        vertical_bonus = leak.get("vertical_relevance_bonus", 0.0)
        
        raw_severity = base_weight + competitor_bonus + vertical_bonus

        cat_weight = CATEGORY_WEIGHTS.get(category, 1.0)
        biz_cat_multiplier = biz_multipliers.get(category, 1.0)

        financial_leak_score = raw_severity * cat_weight * biz_cat_multiplier
        leak["financial_leak_score"] = round(financial_leak_score, 2)
        
        total_weighted_deduction += financial_leak_score

    ai_penalty = (synthetic_index / 100.0) * 15.0 if synthetic_index > 60.0 else 0.0

    starting_score = 100.0
    harsh_score = starting_score - (total_weighted_deduction * 1.35) - ai_penalty
    
    final_score = round(max(12.0, min(96.0, harsh_score)), 1)

    sorted_leaks = sorted(failed_leaks, key=lambda x: x.get("financial_leak_score", 0.0), reverse=True)
    top_10 = sorted_leaks[:10]

    return final_score, top_10


def generate_inverted_hook(biz_type: str, score: float) -> dict:
    hooks = {
        "ecommerce": {
            "headline": f"Assessed conversion efficiency is currently at {score}/100, leaving substantial revenue at cart exit.",
            "body": "Your store exhibits critical checkout friction, causing high-intent prospective buyers to abandon transactions."
        },
        "local_services": {
            "headline": f"Your current conversion score of {score}/100 is driving high bounce rates among mobile visitors.",
            "body": "Lack of immediate click-to-call triggers and local Trust signals causes local clients to click back to competitors."
        }
    }
    return hooks.get(biz_type, {
        "headline": f"Your digital audit score of {score}/100 reflects critical conversion friction.",
        "body": "Immediate structural fixes are required to capture high-intent traffic before they exit the site."
    })


def send_audit_email_to_admin(domain: str, biz_type: str, overall_score: float, vault_id: str):
    resend_key = os.getenv("RESEND_API_KEY")
    
    # Resolves from Railway variables in order of priority, with a sensible default fallback
    receiver_email = os.getenv("ADMIN_EMAIL") or os.getenv("ALERT_EMAIL") or "arpitt22@trilloka.com"
    sender_email = os.getenv("FROM_EMAIL") or os.getenv("EMAIL_FROM") or "arpitt22@trilloka.com"

    if not resend_key:
        print("⚠️ [Resend] Skipping email notification: RESEND_API_KEY environment variable is not set.")
        return

    resend.api_key = resend_key

    try:
        response = resend.Emails.send({
            "from": f"Trilloka Audit <{sender_email}>",
            "to": [receiver_email],
            "subject": f"🚨 New Audit Completed: {domain} (Score: {overall_score})",
            "html": f"""
                <h2>New Website Audit Completed</h2>
                <ul>
                    <li><strong>Target Domain:</strong> {domain}</li>
                    <li><strong>Business Model:</strong> {biz_type}</li>
                    <li><strong>Overall Score:</strong> {overall_score}/100</li>
                    <li><strong>Report Vault ID:</strong> {vault_id}</li>
                </ul>
            """
        })
        print(f"✅ [Resend] Audit email dispatched successfully! ID: {response.get('id')}")
    except Exception as e:
        print(f"❌ [Resend] Failed to send email via Resend API: {e}")