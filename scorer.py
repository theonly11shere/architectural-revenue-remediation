# scorer.py
import os
import random
import string
import resend
from hybrid_scanner import collect_scan_data
from checkpoints_35 import evaluate_35_checkpoints
from solutions_50 import resolve_solutions, get_tailored_solutions
from telemetry import log_telemetry_async
from report_engine import save_private_audit_report

PROTECTED_DOMAINS = ["trilloka.com", "www.trilloka.com"]

# --- MATRIX CONFIGURATIONS ---
BUSINESS_MODEL_MULTIPLIERS = {
    "local": {"Trust": 1.5, "Conversion": 1.5, "SEO": 0.9},
    "local_services": {"Trust": 1.5, "Conversion": 1.5, "SEO": 0.9},
    "medspa": {"Trust": 1.5, "Conversion": 1.5, "SEO": 0.9},
    "legal": {"Trust": 1.5, "Conversion": 1.4, "SEO": 1.1},
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
    
    # 4. Compute Score & Rank Top 10 Leaks
    final_score, top_10_leaks = calculate_harsh_score_and_rank_leaks(biz_type, checkpoint_results, synthetic_index)

    # 5. Map Solutions via solutions_50 module
    mapped_solutions = resolve_solutions(top_10_leaks)

    report_vault_id = generate_vault_id(final_score)

    log_telemetry_async(domain, biz_type, audit_data, final_score, synthetic_index)

    save_private_audit_report(
        domain=domain,
        biz_type=biz_type,
        overall_score=final_score,
        checkpoint_results=checkpoint_results,
        top_10_solutions=mapped_solutions,
        report_vault_id=report_vault_id
    )

    # Calculate estimated revenue leak for notification
    est_annual_leak_num = round((100.0 - final_score) * 250 * 12)
    formatted_annual_leak = f"${est_annual_leak_num:,}"

    # FIX: Explicit Keyword Arguments to prevent positional argument swapping
    send_audit_email_to_admin(
        domain=domain, 
        biz_type=biz_type, 
        overall_score=final_score, 
        vault_id=report_vault_id, 
        annual_leak=formatted_annual_leak, 
        solutions=mapped_solutions
    )

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


def send_audit_email_to_admin(domain: str, biz_type: str, overall_score: float, vault_id: str, annual_leak: str = "$35,000", solutions: list = None):
    resend_key = os.getenv("RESEND_API_KEY")
    receiver_email = os.getenv("ADMIN_EMAIL") or os.getenv("ALERT_EMAIL") or "arpitt22@trilloka.com"
    sender_email = os.getenv("FROM_EMAIL") or os.getenv("EMAIL_FROM") or "arpitt22@trilloka.com"

    if not resend_key:
        print("⚠️ [Resend] Skipping email notification: RESEND_API_KEY environment variable is not set.")
        return

    resend.api_key = resend_key

    # Fetch industry-tailored solution matrix
    matrix = get_tailored_solutions(biz_type)

    # FIX: Extract technical_fix string if solutions is a list of dicts from resolve_solutions
    if solutions and len(solutions) > 0:
        first = solutions[0]
        primary_tech_fix = first.get("technical_fix", matrix["mobile_speed"]["technical"]) if isinstance(first, dict) else first
    else:
        primary_tech_fix = matrix["mobile_speed"]["technical"]

    subject = f"📊 Executive Audit Report: {domain} (Score: {overall_score}/100)"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; color: #1a1a1a; background-color: #f4f6f8; margin: 0; padding: 20px; }}
        .container {{ max-width: 700px; margin: 0 auto; background: #ffffff; padding: 35px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        .header {{ border-bottom: 2px solid #1a202c; padding-bottom: 15px; margin-bottom: 25px; }}
        .title {{ font-size: 22px; font-weight: 700; color: #1a202c; margin: 0; text-transform: uppercase; letter-spacing: 0.5px; }}
        .meta-box {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 18px; border-radius: 6px; margin-bottom: 25px; }}
        .meta-line {{ font-size: 14px; color: #2d3748; margin-bottom: 6px; }}
        .meta-line:last-child {{ margin-bottom: 0; }}
        .intro-text {{ font-style: italic; font-size: 14.5px; color: #2c5282; background: #ebf8ff; border-left: 4px solid #3182ce; padding: 14px 16px; margin-bottom: 30px; border-radius: 0 6px 6px 0; }}
        .section-title {{ font-size: 18px; font-weight: 700; color: #2d3748; margin-top: 30px; border-bottom: 2px solid #edf2f7; padding-bottom: 8px; }}
        .problem-card {{ background: #ffffff; border: 1px solid #e2e8f0; padding: 22px; border-radius: 6px; margin-bottom: 25px; margin-top: 15px; }}
        .problem-title {{ font-size: 17px; font-weight: 700; color: #c53030; margin-top: 0; margin-bottom: 12px; border-bottom: 1px solid #fed7d7; padding-bottom: 6px; }}
        
        .angles-header {{ font-weight: 700; font-size: 13.5px; text-transform: uppercase; letter-spacing: 0.5px; color: #4a5568; margin-top: 10px; margin-bottom: 8px; }}
        .angle-item {{ background: #f7fafc; border: 1px solid #edf2f7; padding: 10px 14px; border-radius: 5px; margin-bottom: 8px; font-size: 13.5px; color: #2d3748; }}
        .angle-tag {{ font-weight: 700; color: #2b6cb0; text-transform: uppercase; font-size: 11px; margin-right: 5px; background: #e2e8f0; padding: 2px 6px; border-radius: 3px; }}
        
        .why-box {{ font-size: 13px; color: #4a5568; background: #fffaf0; border: 1px solid #feebc8; padding: 10px 14px; border-radius: 5px; margin-top: 12px; margin-bottom: 10px; }}
        .timeline-box {{ font-size: 13px; color: #22543d; background: #f0fff4; border: 1px solid #c6f6d5; padding: 10px 14px; border-radius: 5px; }}
        
        .cta-btn {{ background: #1a202c; color: #ffffff !important; padding: 14px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px; display: inline-block; margin-top: 15px; text-align: center; }}
        .disclaimer {{ margin-top: 40px; padding-top: 20px; border-top: 1px dashed #cbd5e0; font-size: 11.5px; color: #718096; line-height: 1.6; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1 class="title">Trilloka Telemetry & Executive Audit</h1>
          <p style="margin: 5px 0 0 0; color: #718096; font-size: 13px;">Report Vault ID: {vault_id}</p>
        </div>

        <div class="meta-box">
          <div class="meta-line"><strong>Target Domain:</strong> {domain}</div>
          <div class="meta-line"><strong>Business Model:</strong> {biz_type.upper()}</div>
          <div class="meta-line"><strong>Overall Performance Score:</strong> {overall_score} / 100</div>
          <div class="meta-line"><strong>Estimated Annual Revenue Leak:</strong> {annual_leak}</div>
        </div>

        <div class="intro-text">
          "According to the Architect, these are the best ways to fix the issues you have from all angles. If you do not think so, try your or any other way—however, these multi-angle strategies are structured specifically to eliminate immediate conversion bottlenecks and build long-term dominance."
        </div>

        <div class="section-title">Diagnostic Breakdown & 3-Angle Solutions</div>

        <!-- Issue 1 -->
        <div class="problem-card">
          <h3 class="problem-title">1. Mobile Core Web Vitals & Technical Latency</h3>
          
          <div class="angles-header">The 3-Angle Remediation Plan:</div>
          <div class="angle-item">
            <span class="angle-tag">Technical Angle</span> {primary_tech_fix}
          </div>
          <div class="angle-item">
            <span class="angle-tag">UX / CRO Angle</span> {matrix["mobile_speed"]["ux_cro"]}
          </div>
          <div class="angle-item">
            <span class="angle-tag">Systems Angle</span> {matrix["mobile_speed"]["systems"]}
          </div>

          <div class="why-box">
            <strong>Why We Recommend This:</strong> Over 60% of high-intent traffic hits your platform on mobile devices. Fixing speed from technical, UX, and pipeline angles ensures immediate retention and prevents future speed degradation.
          </div>
          <div class="timeline-box">
            <strong>Implementation Cadence (Week 1):</strong> Execute technical script deferral and image compression immediately. Test mobile rendering performance every 3 days during initial rollout.
          </div>
        </div>

        <!-- Issue 2 -->
        <div class="problem-card">
          <h3 class="problem-title">2. Conversion Social Proof & Trust Loops</h3>
          
          <div class="angles-header">The 3-Angle Remediation Plan:</div>
          <div class="angle-item">
            <span class="angle-tag">Technical Angle</span> {matrix["trust_social_proof"]["technical"]}
          </div>
          <div class="angle-item">
            <span class="angle-tag">UX / CRO Angle</span> {matrix["trust_social_proof"]["ux_cro"]}
          </div>
          <div class="angle-item">
            <span class="angle-tag">Systems Angle</span> {matrix["trust_social_proof"]["systems"]}
          </div>

          <div class="why-box">
            <strong>Why We Recommend This:</strong> Cold or warm traffic validates trust within 3 seconds. Approaching proof from technical, placement, and system angles keeps your sales funnel constantly refreshed with social proof.
          </div>
          <div class="timeline-box">
            <strong>Implementation Cadence (Weeks 1–3):</strong> Launch review collection triggers. Aim to feature 3 to 5 new customer reviews or highlight updates every week or every 3 days. Do not dump static reviews once a year.
          </div>
        </div>

        <!-- Issue 3 -->
        <div class="problem-card">
          <h3 class="problem-title">3. Organic Presence & Content Distribution Rhythm</h3>
          
          <div class="angles-header">The 3-Angle Remediation Plan:</div>
          <div class="angle-item">
            <span class="angle-tag">Technical Angle</span> {matrix["content_authority"]["technical"]}
          </div>
          <div class="angle-item">
            <span class="angle-tag">UX / CRO Angle</span> {matrix["content_authority"]["ux_cro"]}
          </div>
          <div class="angle-item">
            <span class="angle-tag">Systems Angle</span> {matrix["content_authority"]["systems"]}
          </div>

          <div class="why-box">
            <strong>Why We Recommend This:</strong> Algorithms penalize irregular posting spikes and reward steady output. Tackling content from schema, format, and scheduling angles builds compound traffic growth.
          </div>
          <div class="timeline-box">
            <strong>Implementation Cadence (Weeks 2–8):</strong> Maintain a disciplined distribution rhythm by publishing 3 times every 3 days. Diversify your content mix—do not over-saturate a single topic or pitch constantly; alternate between technical value, customer case studies, and brand updates.
          </div>
        </div>

        <p style="text-align: center; margin-top: 30px;">
          <a href="https://api.trilloka.com/admin/vault/{vault_id}" class="cta-btn">Access Complete Raw Vault Telemetry Entry</a>
        </p>

        <div class="disclaimer">
          <strong>DISCLAIMER & TERMS OF SALE:</strong><br>
          This custom diagnostic report and its associated strategic findings are non-refundable under any circumstances. The fee paid ($350) covers the automated technical telemetry execution, deep-layer diagnostic scan, revenue leak calculation, and the proprietary strategic remediation blueprint. Results and performance improvements depend entirely on proper implementation by your development and marketing teams. Trilloka guarantees the identification of existing performance leaks, but failure to execute recommendations or changes made by external platform providers do not qualify for refunds.
        </div>
      </div>
    </body>
    </html>
    """

    try:
        response = resend.Emails.send({
            "from": f"Trilloka Audit <{sender_email}>",
            "to": [receiver_email],
            "subject": subject,
            "html": html_body
        })
        print(f"✅ [Resend] Executive report dispatched successfully! ID: {response.get('id')}")
    except Exception as e:
        print(f"❌ [Resend] Failed to send executive email via Resend API: {e}")