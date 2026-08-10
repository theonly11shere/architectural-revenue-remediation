"""Trilloka report/vault engine.

Keeps the existing report presentation and sales architecture while replacing
hard-coded passes and title-substring remediation with evidence-backed logic.
"""

from __future__ import annotations

import base64
import datetime
import html
import json
import os
import re
from typing import Any, Dict, List, Optional

import requests

from checkpoint_engine import PASS, FAIL, UNKNOWN, NA, build_50_checkpoints, checkpoint_summary


class ReportGenerator:
    def __init__(self):
        self.resend_api_key = os.environ.get("RESEND_API_KEY", "")
        self.from_email = os.environ.get("FROM_EMAIL", "alerts@trilloka.com")
        self.admin_email = os.environ.get("ADMIN_EMAIL", "arpitt22@trilloka.com")
        self.vault_dir = os.environ.get("VAULT_DIR", "./vault_archives")

    def generate_admin_master_report(self, audit_data: Dict[str, Any], scan_data: Dict[str, Any]) -> Dict[str, Any]:
        audit = audit_data or {}
        scan = scan_data or {}
        business_profile = audit.get("business_profile") or scan.get("business_profile") or {"vertical": audit.get("business_type", "general")}

        checkpoints = audit.get("full_50_checkpoint_basis") or build_50_checkpoints(scan, audit)
        summary = audit.get("checkpoint_summary") or checkpoint_summary(checkpoints)

        packages = audit.get("tiered_remediation_packages") or {}
        leaks = packages.get("all_scoring_leaks") or packages.get("tier_10_arch10") or []
        sorted_leaks = sorted(
            [item for item in leaks if isinstance(item, dict)],
            key=lambda item: float(item.get("severity_score") or item.get("final_score_loss") or 0.0),
            reverse=True,
        )

        enriched: List[Dict[str, Any]] = []
        for leak in sorted_leaks[:10]:
            severity_factor = leak.get("severity_factor")
            enriched.append(
                {
                    **leak,
                    "finding_type": "VERIFIED_LEAK",
                    "severity_label": self._get_severity_label(severity_factor),
                    "solutions_3_angles": self._build_3_angle_solutions(
                        str(leak.get("rule_key") or ""),
                        leak,
                        scan,
                        business_profile,
                    ),
                }
            )

        # The attachment always contains 10 actionable priorities. Never fabricate a failure:
        # if fewer than 10 verified leaks exist, fill remaining slots with explicitly-labelled
        # optimization opportunities selected from verified PASS checkpoints.
        findings = self._fill_to_ten_findings(enriched, checkpoints, scan, business_profile)

        overall = audit.get("overall_health_score", audit.get("overall_score", 0.0))
        revenue_display = (audit.get("revenue_leak") or {}).get("est_annual_revenue_leak") or "Not measured"

        return {
            "report_type": "ADMIN_LEAD_ALERT",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "target_domain": audit.get("target_domain", scan.get("domain", "Unknown")),
            "business_type": str(audit.get("business_type", business_profile.get("vertical", "general"))).upper(),
            "business_profile": business_profile,
            "overall_health_score": overall,
            "score_rating": audit.get("score_rating", ""),
            "vault_id": audit.get("vault_id", ""),
            "estimated_revenue_leak": revenue_display,
            "revenue_exposure": audit.get("revenue_leak") or {},
            "scoring_methodology": self._build_scoring_methodology_explanation(audit),
            "score_level_impact": self._build_score_level_impact_explanation(float(overall or 0.0)),
            "top_10_financial_leaks": findings,
            # Backward-compatible alias for any old template/client code.
            "top_6_financial_leaks": findings[:6],
            "verified_financial_leak_count": len(enriched),
            "full_50_checkpoint_basis": checkpoints,
            "checkpoint_summary": summary,
            "behavioral_diagnostics": audit.get("behavioral_diagnostics", {}),
            "ai_spectrum_pct": audit.get("ai_spectrum_pct"),
            "ai_spectrum_status": audit.get("ai_spectrum_status", scan.get("ai_spectrum_status", "unknown")),
            "cms_platform": scan.get("cms_platform", "Not confidently identified"),
            "cms_confidence": scan.get("cms_confidence", "low"),
            "scan_quality": audit.get("scan_quality") or scan.get("scan_quality") or {},
            "scoring_ledger": audit.get("scoring_ledger") or [],
            "overlap_adjustments": audit.get("overlap_adjustments") or [],
            "score_formula": audit.get("score_formula") or {},
        }

    def _fill_to_ten_findings(
        self,
        verified_leaks: List[Dict[str, Any]],
        checkpoints: List[Dict[str, Any]],
        scan: Dict[str, Any],
        business_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        findings = list(verified_leaks[:10])
        if len(findings) >= 10:
            return findings

        used_names = {str(item.get("leak_name") or "") for item in findings}
        # Prefer verified PASS checks that represent mature commercial dimensions. They are not
        # reclassified as failures; they simply become next-step opportunities in the action file.
        preferred_ids = [26, 28, 29, 30, 32, 33, 35, 11, 14, 21, 27, 44, 45, 46, 47, 48, 13, 10, 9, 15]
        by_id = {int(cp.get("id")): cp for cp in checkpoints if isinstance(cp, dict) and cp.get("id") is not None}
        for cp_id in preferred_ids:
            if len(findings) >= 10:
                break
            cp = by_id.get(cp_id)
            if not cp or cp.get("status") != PASS:
                continue
            name = str(cp.get("check") or "Verified strength")
            display = f"Optimization Opportunity — {name}"
            if display in used_names:
                continue
            leak = {
                "rule_key": f"opportunity_{cp_id:02d}",
                "checkpoint_id": cp_id,
                "leak_name": display,
                "impact_summary": "This checkpoint passed the minimum readiness test. It is included as a next-step optimization opportunity, not as a verified failure or score deduction.",
                "category": cp.get("category", ""),
                "evidence": cp.get("evidence"),
                "source": "Verified 50-point checkpoint evidence",
                "confidence": "high",
                "severity_factor": 0.0,
                "severity_score": 0.0,
                "final_score_loss": 0.0,
                "finding_type": "OPTIMIZATION_OPPORTUNITY",
                "severity_label": "VERIFIED STRENGTH — NEXT OPTIMIZATION",
            }
            leak["solutions_3_angles"] = self._build_opportunity_solution(cp, scan, business_profile)
            findings.append(leak)
            used_names.add(display)

        # If there still are not ten items, use UNKNOWNs only as verification actions, never as
        # revenue failures. This keeps the file complete while preserving evidence integrity.
        for cp in checkpoints:
            if len(findings) >= 10:
                break
            if cp.get("status") != UNKNOWN:
                continue
            name = str(cp.get("check") or "Telemetry")
            display = f"Verification Priority — {name}"
            if display in used_names:
                continue
            leak = {
                "rule_key": f"verification_{int(cp.get('id') or 0):02d}",
                "checkpoint_id": cp.get("id"),
                "leak_name": display,
                "impact_summary": "The scanner could not verify this checkpoint from available evidence. It is not scored as a failure; the action is to improve/verifiably expose the signal before making a revenue claim.",
                "category": cp.get("category", ""),
                "evidence": cp.get("evidence"),
                "source": "Unresolved checkpoint telemetry",
                "confidence": "unknown",
                "severity_factor": None,
                "severity_score": 0.0,
                "final_score_loss": 0.0,
                "finding_type": "VERIFICATION_PRIORITY",
                "severity_label": "NOT SCORED — VERIFICATION REQUIRED",
                "solutions_3_angles": {
                    "technical": "Expose or verify this signal through accessible markup, browser-rendered evidence, Google telemetry or the relevant platform integration; do not hard-code a PASS/FAIL value.",
                    "cro_ux": "Do not redesign the customer journey solely because this signal is unknown. Preserve working conversion paths until evidence confirms a real issue.",
                    "systems": "Add a repeatable validation check so future scans can classify this checkpoint as PASS, FAIL or N/A with confidence.",
                    "why_recommend": "This item is included to complete the 10-priority action file, but it is explicitly not treated as a leak because evidence is incomplete.",
                    "cadence_title": "Next verification cycle",
                    "cadence_text": "Resolve the evidence source, re-scan, and only then decide whether remediation is required.",
                },
            }
            findings.append(leak)
            used_names.add(display)
        return findings[:10]

    @staticmethod
    def _build_opportunity_solution(checkpoint: Dict[str, Any], scan: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, str]:
        name = str(checkpoint.get("check") or "verified strength")
        return {
            "technical": f"Preserve the implementation that allowed '{name}' to pass, then benchmark it against the stronger/elite threshold where one exists.",
            "cro_ux": "Use controlled iteration rather than redesign: improve clarity, prominence or response time only if analytics show a customer-friction opportunity.",
            "systems": "Track the relevant event/metric over time so optimization is based on observed change rather than a one-time scan score.",
            "why_recommend": "This checkpoint is already a verified strength. It is presented only as a next optimization priority and contributes zero score loss.",
            "cadence_title": "After verified leaks",
            "cadence_text": "Fix genuine leaks first, establish a baseline, then test incremental improvement without weakening the passing implementation.",
        }

    @staticmethod
    def _get_severity_label(severity_factor: Optional[float]) -> str:
        if severity_factor is None:
            return "SEVERITY UNKNOWN"
        factor = max(0.0, min(1.0, float(severity_factor)))
        if factor >= 0.85:
            return "CRITICAL LEAK"
        if factor >= 0.65:
            return "HIGH-IMPACT LEAK"
        if factor >= 0.40:
            return "MODERATE FRICTION"
        if factor > 0.0:
            return "MINOR OPTIMIZATION"
        return "OPTIMIZED"

    @staticmethod
    def _build_scoring_methodology_explanation(audit_data: Dict[str, Any]) -> Dict[str, str]:
        biz = str(audit_data.get("business_type", "general")).upper()
        return {
            "core_philosophy": "Trilloka measures Revenue Readiness, not literal conversion percentage. A functioning site begins from an operating baseline and must earn higher scores through verified strengths while verified leaks subtract weighted points.",
            "graded_continuum": "Every deduction is scaled by implementation severity, evidence confidence and business relevance. Unknown telemetry earns no strength and creates no penalty.",
            "vertical_weighting": f"Conversion relevance is weighted for the {biz} model, with substitution credit when another strong conversion path already serves the customer.",
            "hygiene_gatekeeping": "Ordinary good websites are intentionally calibrated around the upper-60s to mid-70s. Scores above 80 require advanced verified maturity across performance, conversion, trust, measurement and technical execution; no raw finding-count clamp forces a rating.",
        }

    @staticmethod
    def _build_score_level_impact_explanation(score: float) -> Dict[str, str]:
        if score >= 90:
            return {
                "level": "ARCHITECT / REFERENCE LEVEL (90–100)",
                "impact_summary": "Reference-grade verified architecture. This band should be extraordinarily rare and does not mean 90–100% of visitors convert.",
                "severity_behavior": "Requires exceptional evidence across performance, conversion, trust, measurement and technical execution with essentially no material verified leaks.",
            }
        if score >= 85:
            return {
                "level": "ELITE ARCHITECTURE (85–89)",
                "impact_summary": "Elite verified architecture with unusually few observable structural or conversion weaknesses.",
                "severity_behavior": "Advanced maturity points are earned only after strong fundamentals are already verified.",
            }
        if score >= 80:
            return {
                "level": "WORLD-CLASS COMMERCIAL ARCHITECTURE (80–84)",
                "impact_summary": "An unusually mature commercial website. Ordinary professional sites should not casually reach this band.",
                "severity_behavior": "The score requires advanced verified strengths beyond normal technical hygiene and a low burden of meaningful leaks.",
            }
        if score >= 75:
            return {
                "level": "EXCEPTIONAL (75–79)",
                "impact_summary": "A very strong commercial website with comparatively low observable friction, while still leaving room for meaningful optimization.",
                "severity_behavior": "Strong fundamentals have been earned and verified; remaining leaks continue to reduce the score.",
            }
        if score >= 65:
            return {
                "level": "GOOD — LEAKS REMAIN (65–74)",
                "impact_summary": "A good functioning website with credible strengths, while meaningful revenue or conversion opportunities still remain.",
                "severity_behavior": "This is the intended normal range for a professionally built site that is good but not unusually optimized.",
            }
        if score >= 50:
            return {
                "level": "NEEDS REMEDIATION (50–64)",
                "impact_summary": "The site functions, but verified weaknesses materially limit its commercial readiness.",
                "severity_behavior": "Insufficient earned strengths and/or accumulated verified leaks are holding the score near the operating baseline.",
            }
        if score >= 35:
            return {
                "level": "CRITICAL RISK (35–49)",
                "impact_summary": "Multiple verified high-severity weaknesses create substantial architectural or conversion risk.",
                "severity_behavior": "The critical rating is produced by the evidence-weighted scoring ledger, not by the raw number of findings.",
            }
        return {
            "level": "SEVERE STRUCTURAL RISK (0–34)",
            "impact_summary": "Severe verified structural, performance or conversion failures materially compromise the site's ability to capture demand.",
            "severity_behavior": "This band requires significant evidence-backed deductions beyond the operating baseline.",
        }

    def _build_3_angle_solutions(
        self,
        rule_key: str,
        leak: Dict[str, Any],
        scan_data: Dict[str, Any],
        business_profile: Dict[str, Any],
    ) -> Dict[str, str]:
        vertical = str(business_profile.get("inferred_subtype") or business_profile.get("vertical") or "general")
        evidence = leak.get("evidence") or {}

        if rule_key == "core_web_vitals":
            return {
                "technical": "Trace the specific PageSpeed/CrUX bottleneck before changing assets: optimize the critical rendering path, compress oversized media, defer non-critical scripts and retest the same mobile URL.",
                "cro_ux": "Protect the primary conversion action from delayed rendering; keep the first meaningful value proposition and action usable while heavier content loads.",
                "systems": "Record baseline and post-fix LCP/INP/CLS or PageSpeed evidence in the Vault and schedule regression checks after major deployments.",
                "why_recommend": "This finding is tied to measured Google performance evidence, so remediation should target the measured bottleneck rather than apply generic speed advice blindly.",
                "cadence_title": "Week 1",
                "cadence_text": "Fix the highest measured bottleneck first, retest after deployment, then address secondary resource costs only if telemetry still shows material latency.",
            }

        if rule_key == "unsecured_ssl":
            return {
                "technical": "Install/repair the TLS certificate, force HTTP-to-HTTPS redirects at the server or edge, then verify the final URL and certificate chain.",
                "cro_ux": "Remove browser security warnings from every conversion path; do not add decorative security claims as a substitute for a valid secure connection.",
                "systems": "Automate certificate renewal and monitor expiry/redirect failures.",
                "why_recommend": "The scanner verified an insecure final connection, making this a foundational trust and transport problem rather than a cosmetic issue.",
                "cadence_title": "Immediate",
                "cadence_text": "Correct TLS and redirect behavior before CRO experiments or paid-traffic expansion.",
            }

        if rule_key == "diluted_h1":
            if str(scan_data.get("h1_status")) == "missing":
                technical = "Add one semantically appropriate page-level H1 that represents the primary page topic, then verify the rendered DOM and source both expose it."
            else:
                technical = "Review the verified H1 hierarchy and keep the page's primary semantic heading unambiguous; do not delete additional H1s blindly if the document structure intentionally requires them."
            return {
                "technical": technical,
                "cro_ux": self._h1_cro_copy(vertical, scan_data),
                "systems": "Track engagement with the primary hero action before and after the heading/value-proposition change so the copy change is evaluated against behavior rather than opinion.",
                "why_recommend": "The recommendation is limited to the verified hero/H1 evidence; unrelated publishing schedules, redirects or infographic work are not prescribed unless separately detected.",
                "cadence_title": "Week 1",
                "cadence_text": "Correct the hero semantic/value-proposition issue, verify the rendered result, then measure primary-action engagement before making further copy changes.",
            }

        if rule_key == "click_to_call":
            if vertical == "restaurant":
                return {
                    "technical": "Keep the displayed restaurant phone number and wrap it in a valid tel: link on mobile. Use generous mobile touch sizing; 48×48 CSS px is a Trilloka usability target, not a claimed WCAG minimum.",
                    "cro_ux": "Keep Order Now / View Menu as the primary restaurant action when appropriate and add Tap to Call as a secondary high-intent action rather than replacing ordering.",
                    "systems": "Track order clicks and call clicks as separate conversion events so the restaurant can see which path customers actually use.",
                    "why_recommend": "Calling is useful for restaurant intent, but the scanner credits stronger existing order/reservation paths instead of treating the missing tel: link as a total conversion failure.",
                    "cadence_title": "Week 1",
                    "cadence_text": "Add touch-enabled calling, preserve the stronger ordering path, then verify both events are measurable.",
                }
            if vertical in {"legal", "medspa", "local_service", "professional_service"}:
                return {
                    "technical": "Wrap verified phone numbers in tel: links and ensure the mobile target is comfortably tappable. A 48×48 CSS px target may be used as Trilloka's usability recommendation.",
                    "cro_ux": "Place the call action near the highest-intent service/consultation path without obscuring the primary form or booking action.",
                    "systems": "Track call-click and completed-lead events. Use a call-tracking system only if the business actually needs source attribution and the tracking setup preserves number consistency.",
                    "why_recommend": "For this business model, direct calling can be a high-value conversion path, so a verified missing tap action deserves more weight than it would for ecommerce or SaaS.",
                    "cadence_title": "Week 1",
                    "cadence_text": "Enable the direct mobile call action, verify routing, then measure call engagement before changing the surrounding funnel.",
                }
            return {
                "technical": "If calling is a supported conversion path, expose the verified phone number through a tel: link and use a comfortably sized mobile touch target.",
                "cro_ux": "Keep the site's stronger primary action dominant; add calling only as a secondary path where it matches user intent.",
                "systems": "Track call-click events separately from the primary conversion path.",
                "why_recommend": "The scanner separates phone visibility from touch-to-call functionality and discounts the finding when another strong conversion path already exists.",
                "cadence_title": "Week 1",
                "cadence_text": "Implement and measure the secondary call path without displacing the site's primary action.",
            }

        if rule_key == "mobile_sticky_cta":
            labels = self._vertical_cta_labels(vertical)
            return {
                "technical": f"Create a genuinely visible fixed/sticky mobile action for the primary journey ({labels['primary']}) with safe-area spacing and no overlap with consent/chat controls.",
                "cro_ux": f"Keep the persistent action aligned to the business model: prioritize {labels['primary']} and use {labels['secondary']} only as supporting actions.",
                "systems": "Track sticky-action impressions and clicks separately from non-sticky CTA clicks so lift can be measured instead of assumed.",
                "why_recommend": "The scanner verified the difference between a normal CTA and a persistent mobile CTA and overlap-adjusts this finding against related direct-action failures.",
                "cadence_title": "Weeks 1–2",
                "cadence_text": "Deploy the persistent primary action, verify it remains accessible after scroll, then compare engagement against the existing non-sticky action.",
            }

        if rule_key == "missing_alt_images":
            return {
                "technical": "Add meaningful alt text to informative images and appropriate empty/decorative treatment to non-informative images; preserve existing WAI-ARIA treatment where valid.",
                "cro_ux": "Prioritize images that explain products, services, proof or instructions so accessibility improvements also preserve comprehension.",
                "systems": "Add an image-publishing checklist or CMS validation so new uploads do not recreate the same accessibility gap.",
                "why_recommend": "The scanner counted rendered images lacking alt/WAI-ARIA treatment; the remediation is limited to that verified accessibility evidence.",
                "cadence_title": "Weeks 1–2",
                "cadence_text": "Correct high-value images first, then close the remaining verified accessibility gaps and add publishing safeguards.",
            }

        if rule_key == "measurement_telemetry":
            return {
                "technical": "Implement an appropriate analytics/tagging layer and verify that key conversion events fire once, with consent handling appropriate to the site's jurisdiction and stack.",
                "cro_ux": "Define the few actions that represent real customer progress rather than tracking every click as a conversion.",
                "systems": "Create a measurement map for primary CTA, form/booking/order starts and completed conversions, then review data quality after deployment.",
                "why_recommend": "No GA4/GTM-style or Meta Pixel signal was detected in the rendered page source. This is a measurement blind spot, not proof that the site is losing a specific dollar amount.",
                "cadence_title": "Week 1",
                "cadence_text": "Deploy the measurement layer, validate event integrity, then use observed conversion data to refine later revenue estimates.",
            }

        if rule_key == "form_architecture":
            return {
                "technical": "Repair the verified form structure so each form has a valid server action or a complete SPA submission path with usable inputs, submit handling and error states.",
                "cro_ux": "Keep required fields minimal and make success/error feedback explicit without changing the surrounding offer until the form works reliably.",
                "systems": "Add safe automated form validation in staging/monitoring. Do not use destructive live submissions for routine scanner checks.",
                "why_recommend": "The finding is based on a structurally incomplete rendered form, so the first priority is reliable execution rather than copy experimentation.",
                "cadence_title": "Immediate",
                "cadence_text": "Repair the submission architecture, test safely in staging or with a non-destructive endpoint, then monitor successful completions.",
            }

        if rule_key in {"favicon_present", "html_lang_attribute"}:
            return {
                "technical": "Correct the verified document-head/HTML hygiene issue and re-scan the rendered page to confirm the signal is present.",
                "cro_ux": "Do not redesign the page for this issue; preserve the current interface while restoring the missing baseline metadata.",
                "systems": "Add the requirement to the base template so future pages inherit it automatically.",
                "why_recommend": "This is a small verified hygiene issue, so it receives a small score deduction rather than a critical conversion penalty.",
                "cadence_title": "Next deployment",
                "cadence_text": "Correct it with the next safe production release and verify it through the scanner.",
            }

        if rule_key == "ai_template_similarity":
            return {
                "technical": "Do not rewrite code solely because it uses a common framework. Review the specific template-pattern signals and keep only those that correlate with generic presentation or duplicated structure.",
                "cro_ux": "Replace generic value-proposition language with business-specific proof, terminology and customer outcomes where the report identifies templated messaging.",
                "systems": "Treat the AI / Template Pattern Spectrum as a heuristic trend signal, not authorship proof; compare it with engagement and brand-review evidence before major rewrites.",
                "why_recommend": "Framework/tooling signals can indicate templated construction but cannot prove AI authorship, so remediation focuses on distinctiveness rather than accusing the content source.",
                "cadence_title": "Weeks 2–4",
                "cadence_text": "Prioritize verified generic messaging first, then re-scan after meaningful brand-specific content changes.",
            }

        checkpoint_solution = self._checkpoint_specific_solution(rule_key, leak, vertical)
        if checkpoint_solution:
            return checkpoint_solution

        return {
            "technical": f"Verify the evidence attached to {leak.get('leak_name') or rule_key} and correct the affected implementation without changing unrelated systems.",
            "cro_ux": "Preserve working conversion paths and change only the user-facing friction supported by the evidence.",
            "systems": "Record the before/after evidence and add a regression check so the same issue does not return.",
            "why_recommend": "Trilloka remediation follows the exact rule key and evidence rather than guessing from words in the leak title.",
            "cadence_title": "Weeks 1–2",
            "cadence_text": "Fix the verified issue, re-scan, then evaluate any remaining dependent findings.",
        }

    @staticmethod
    def _checkpoint_specific_solution(rule_key: str, leak: Dict[str, Any], vertical: str) -> Optional[Dict[str, str]]:
        plans: Dict[str, tuple[str, str, str]] = {
            "https_redirect": (
                "Force every HTTP request to the equivalent HTTPS URL at the CDN/server layer and verify there is no redirect loop or mixed final destination.",
                "Keep every landing and conversion URL on the secure canonical path so visitors never see inconsistent secure/non-secure variants.",
                "Add redirect/TLS monitoring and recheck after DNS, CDN or hosting changes.",
            ),
            "retargeting_telemetry": (
                "Install the appropriate advertising/retargeting pixel only for channels the business actually uses and validate consent-aware event firing.",
                "Track high-intent actions rather than firing conversion events on generic page views.",
                "Document pixel IDs, consent conditions and conversion-event ownership so duplicate tags do not accumulate.",
            ),
            "phone_visibility": (
                "Expose the primary business phone number in accessible text/schema where calling is a supported customer path.",
                "Place the phone signal near contact/location intent without displacing the stronger primary conversion action.",
                "Keep the number consistent across the site, business listings and call routing.",
            ),
            "location_visibility": (
                "Expose the service/location address or service-area signal in visible content and valid LocalBusiness/PostalAddress schema where appropriate.",
                "Put location/directions information where local-intent visitors naturally look for it.",
                "Keep address/service-area data consistent across the site and Google Business Profile.",
            ),
            "trust_credentials": (
                "Add only real, verifiable licence/certification/security/association credentials and link to validation where possible.",
                "Place proof next to the decision it supports instead of creating a decorative badge wall.",
                "Create an owner/renewal process so expired credentials are removed or updated.",
            ),
            "reviews_social_proof": (
                "Surface real review/testimonial evidence with source attribution or structured AggregateRating data when valid.",
                "Place the strongest relevant proof near the offer/CTA it supports.",
                "Create a review collection and moderation workflow so proof remains current.",
            ),
            "guarantee_refund_clarity": (
                "Publish the actual guarantee/refund terms in a clearly linked policy; do not promise terms the business cannot honour.",
                "Summarize the reassurance near purchase/booking intent and link to the full conditions.",
                "Keep checkout, support and policy language synchronized when terms change.",
            ),
            "about_team_signal": (
                "Add a clear About/Team path with real business identity, ownership/team information and relevant credentials.",
                "Use the page to answer 'who am I buying from?' rather than filling it with generic company language.",
                "Maintain team/ownership details as staff and roles change.",
            ),
            "social_proof_signal": (
                "Expose at least one verifiable proof source such as reviews, credentials, client outcomes or transaction trust signals.",
                "Position proof beside the highest-friction decision point.",
                "Define which proof source is authoritative and keep it current.",
            ),
            "instant_query_channel": (
                "Add chat/WhatsApp only if the business can reliably respond; otherwise strengthen the existing contact path rather than installing an unattended widget.",
                "Make the instant-query option secondary to the primary conversion action and avoid covering mobile content/CTAs.",
                "Set response ownership, hours and event tracking before launch.",
            ),
            "meta_description_missing": (
                "Add a unique meta description that accurately summarizes the page and primary offer without keyword stuffing.",
                "Write it as search-result persuasion: clear service/product, differentiator and intent match.",
                "Add metadata validation to the publishing template so new pages cannot ship blank descriptions.",
            ),
            "meta_description_length": (
                "Rewrite the description into the scanner's concise range while preserving the strongest offer information.",
                "Put the differentiator and intent match early so truncation does not remove the key message.",
                "Validate metadata length automatically during publishing.",
            ),
            "h1_topic_relevance": (
                "Align the verified H1 to the page's primary topic/service/product without creating duplicate keyword headings.",
                "State the customer outcome/value clearly before secondary messaging.",
                "Measure hero CTA engagement after the wording change.",
            ),
            "title_length": (
                "Tighten or expand the title so the main topic and brand remain clear within the preferred search-result range.",
                "Front-load the page's strongest intent term instead of filler text.",
                "Add title-length validation to the page template/CMS.",
            ),
            "structured_data_missing": (
                "Add valid schema types that describe the actual entity/page and validate the JSON-LD; do not add irrelevant rich-result markup.",
                "Use structured data to reinforce business/entity clarity rather than as a substitute for visible content.",
                "Revalidate schema after theme, CMS or product-template deployments.",
            ),
            "canonical_missing": (
                "Add a self-referential or intentionally consolidated rel=canonical URL and verify it resolves to the preferred indexable page.",
                "Avoid exposing visitors/search engines to competing URL variants for the same offer.",
                "Enforce canonical generation in templates and test parameterized URLs.",
            ),
            "sitemap_missing": (
                "Generate a valid XML sitemap containing canonical indexable URLs and expose it at a standard URL and/or in robots.txt.",
                "Keep non-indexable utility URLs out so search discovery focuses on revenue-bearing content.",
                "Regenerate/update the sitemap automatically as pages are published or removed.",
            ),
            "robots_missing": (
                "Publish a syntactically valid robots.txt that does not accidentally block important crawling and declare the sitemap where useful.",
                "Protect search visibility by keeping revenue pages crawlable.",
                "Version-control and test robots changes before deployment.",
            ),
            "pagespeed_below_60": (
                "Use the PageSpeed audit to remove the largest blocking/script/media bottlenecks first; do not optimize blindly.",
                "Keep the primary value proposition and CTA usable before secondary visual assets finish loading.",
                "Set a mobile performance budget and test major releases against it.",
            ),
            "pagespeed_below_90": (
                "Work through the highest remaining PageSpeed opportunities until gains become low-value or risk functionality.",
                "Protect conversion clarity while reducing non-critical visual/interaction cost.",
                "Treat 90+ as an elite optimization target, not a reason to break working functionality.",
            ),
            "seo_score_below_80": (
                "Open the Lighthouse SEO audit and correct the specific failed audits rather than chasing the aggregate number.",
                "Preserve human-readable navigation and page intent while fixing technical discoverability.",
                "Add the failed SEO audits to release QA.",
            ),
            "lcp_poor": (
                "Identify the LCP element, optimize its asset/server delivery and remove work blocking its render.",
                "Ensure the LCP element contains useful above-the-fold value rather than decorative weight.",
                "Track field/lab LCP after deployment and enforce a performance budget.",
            ),
            "inp_poor": (
                "Profile long main-thread tasks and event handlers, split heavy JavaScript work and reduce blocking third-party code.",
                "Keep primary buttons/forms responsive under real mobile load.",
                "Monitor INP field data where CrUX/analytics coverage exists.",
            ),
            "cls_poor": (
                "Reserve dimensions for images/embeds/ads, avoid late layout injection and stabilize web-font/component sizing.",
                "Prevent buttons, forms and primary copy from shifting while a user is trying to act.",
                "Add CLS checks to visual/performance regression testing.",
            ),
            "viewport_missing": (
                "Add a valid responsive viewport meta tag and test actual mobile breakpoints.",
                "Verify text, controls and forms remain readable/tappable without horizontal zoom.",
                "Make viewport configuration part of the shared document template.",
            ),
            "tap_target_friction": (
                "Fix the exact Lighthouse-flagged controls by increasing target area/spacing without claiming a fabricated universal size requirement.",
                "Prioritize high-intent buttons, navigation and form controls first.",
                "Add mobile tap-target QA to component regression tests.",
            ),
            "render_blocking": (
                "Defer/inline/split only the resources identified as blocking above-the-fold rendering and verify no functional regression.",
                "Protect first-view copy and conversion controls from delayed rendering.",
                "Track bundle/third-party growth in release performance budgets.",
            ),
            "lazy_loading_gap": (
                "Lazy-load below-the-fold images/embeds while keeping the real LCP/hero asset eager enough to render quickly.",
                "Avoid blank content jumps by reserving image dimensions/placeholders.",
                "Bake loading behavior into reusable image components/CMS templates.",
            ),
            "author_bylines_missing": (
                "Add real author identity to relevant editorial/expert content and connect it to an author profile where appropriate.",
                "Show expertise where it helps trust; do not add fake personas to commercial copy.",
                "Make authorship a publishing requirement for applicable content types.",
            ),
            "publication_dates_missing": (
                "Expose publication/updated dates on applicable editorial content using visible markup and machine-readable dates.",
                "Help users judge freshness where timeliness affects trust.",
                "Update dates only when content materially changes and keep CMS date fields consistent.",
            ),
            "thin_visible_content": (
                "Add only the missing decision-support content: offer clarity, proof, objections, process, pricing/context or next steps.",
                "Increase useful information density rather than padding the page to satisfy a word count.",
                "Measure whether added sections improve engagement/conversion before expanding further.",
            ),
            "generic_headline": (
                "Replace generic/template language with a concrete business-specific outcome, audience and differentiator.",
                "Use customer language and proof rather than broad claims such as 'innovative solutions'.",
                "Test the new headline against primary CTA engagement and qualified lead/order behavior.",
            ),
            "unlinked_form_structure": (
                "Connect the form to a valid server action or complete SPA submit handler with validation, success and error states.",
                "Keep fields minimal and make the post-submit outcome obvious.",
                "Test the form safely in staging and monitor successful submissions in production.",
            ),
            "faq_missing": (
                "Add a concise FAQ only for real recurring objections/questions and mark up FAQ schema only when eligible/appropriate.",
                "Place answers near the decision stage they unblock instead of creating filler content.",
                "Update FAQs from actual sales/support/search-query data.",
            ),
            "case_studies_missing": (
                "Publish verifiable proof-of-work with problem, work performed and outcome where confidentiality permits.",
                "Link the most relevant case study near the corresponding service/solution CTA.",
                "Create a process for collecting outcomes and approvals from future clients/projects.",
            ),
            "content_hub_missing": (
                "Create a focused expertise/resource hub only if the business model benefits from ongoing informational demand.",
                "Organize content around customer questions and buying stages rather than generic posting cadence.",
                "Track assisted conversions/search demand so the content program is accountable.",
            ),
            "social_links_missing": (
                "Link only maintained official social profiles with correct rel/security attributes.",
                "Keep social links secondary to onsite conversion so users are not unnecessarily sent away.",
                "Remove abandoned channels and keep profile branding/contact data consistent.",
            ),
            "privacy_terms_missing": (
                "Publish accessible Privacy and Terms pages appropriate to the site's actual data collection/commerce behavior and link them consistently.",
                "Expose policy links near forms/checkout/footer without overwhelming the primary action.",
                "Review policies when tracking, payment, data collection or service terms change.",
            ),
        }
        plan = plans.get(rule_key)
        if not plan:
            return None
        technical, cro, systems = plan
        return {
            "technical": technical,
            "cro_ux": cro,
            "systems": systems,
            "why_recommend": f"This recommendation is tied to the verified '{leak.get('checkpoint_name') or leak.get('leak_name') or rule_key}' evidence and is ranked by its weighted revenue-readiness impact.",
            "cadence_title": "Weeks 1–2",
            "cadence_text": "Implement the technical correction, verify the customer-facing result, then re-scan and compare the scoring ledger before further optimization.",
        }

    @staticmethod
    def _vertical_cta_labels(vertical: str) -> Dict[str, str]:
        if vertical == "restaurant":
            return {"primary": "Order Now / Reserve", "secondary": "View Menu / Directions / Call"}
        if vertical == "ecommerce":
            return {"primary": "Add to Cart / Checkout", "secondary": "Product Question / Chat"}
        if vertical == "saas":
            return {"primary": "Start Trial / Book Demo / Sign Up", "secondary": "Contact / Chat"}
        if vertical == "legal":
            return {"primary": "Consultation / Contact", "secondary": "Call"}
        if vertical == "medspa":
            return {"primary": "Book / Consultation", "secondary": "Call"}
        if vertical in {"local_service", "professional_service"}:
            return {"primary": "Get Quote / Contact / Book", "secondary": "Call / Chat"}
        return {"primary": "Primary Conversion", "secondary": "Contact / Secondary Action"}

    @staticmethod
    def _h1_cro_copy(vertical: str, scan: Dict[str, Any]) -> str:
        current = " / ".join(scan.get("h1_tags") or [])
        prefix = f"The current verified H1 is '{current}'. " if current else ""
        if vertical == "restaurant":
            return prefix + "Make the hero immediately identify the cuisine/restaurant value and keep Order Now, Reserve or View Menu aligned beneath it."
        if vertical == "legal":
            return prefix + "Make the hero clearly communicate the core legal service/jurisdiction and align it to the consultation path."
        if vertical == "medspa":
            return prefix + "Make the hero clearly communicate the primary treatment/value proposition and align it to booking or consultation."
        if vertical == "ecommerce":
            return prefix + "Make the hero state the product/category value clearly and align it to shopping or product discovery."
        if vertical == "saas":
            return prefix + "Make the hero explain the software outcome and align it to trial, signup or demo intent."
        return prefix + "Make the hero communicate the primary customer outcome and align it to the site's verified primary action."

    def _build_50_checkpoints(self, scan_data: Dict[str, Any], audit_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return build_50_checkpoints(scan_data, audit_data)

    @staticmethod
    def _checkpoint_summary(checkpoints: List[Dict[str, Any]]) -> Dict[str, int]:
        return checkpoint_summary(checkpoints)

    def send_admin_alert_email(self, admin_report: Dict[str, Any]) -> bool:
        if not self.resend_api_key:
            print("[Email] RESEND_API_KEY not configured — skipping email")
            return False
        html_body = self._build_email_html(admin_report)
        domain_safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(admin_report.get("target_domain") or "site")).strip("_") or "site"
        attachment_name = f"Trilloka_Revenue_Audit_{domain_safe}.html"
        attachment_content = base64.b64encode(html_body.encode("utf-8")).decode("ascii")
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.from_email,
                    "to": self.admin_email,
                    "subject": f"🚨 New Lead Alert — {admin_report.get('target_domain', 'Unknown')} scored {admin_report.get('overall_health_score', 'N/A')}",
                    "html": html_body,
                    "attachments": [
                        {
                            "filename": attachment_name,
                            "content": attachment_content,
                        }
                    ],
                },
                timeout=15,
            )
            if response.status_code in (200, 202):
                print(f"[Email] Admin alert sent to {self.admin_email}")
                return True
            print(f"[Email] Resend API error: {response.status_code} — {response.text}")
        except Exception as exc:
            print(f"[Email] Failed to send: {exc}")
        return False

    def _build_email_html(self, report: Dict[str, Any]) -> str:
        report = report or {}
        domain = html.escape(str(report.get("target_domain", "Unknown")))
        score = float(report.get("overall_health_score") or 0.0)
        rating = html.escape(str(report.get("score_rating", "")))
        vault_id = html.escape(str(report.get("vault_id", "")))
        biz_type = html.escape(str(report.get("business_type", "GENERAL")))
        revenue_exposure = html.escape(str(report.get("estimated_revenue_leak", "Not measured")))
        cms = html.escape(str(report.get("cms_platform") or "Not confidently identified"))
        ai_pct = report.get("ai_spectrum_pct")
        ai_display = "Unknown" if ai_pct is None else f"{float(ai_pct):.1f}/100"
        methodology = report.get("scoring_methodology") or {}
        score_impact = report.get("score_level_impact") or {}
        summary = report.get("checkpoint_summary") or self._checkpoint_summary(report.get("full_50_checkpoint_basis") or [])

        score_color = "#22C55E" if score >= 75 else "#D8B66A" if score >= 50 else "#EF4444"
        leaks_html = ""
        for idx, leak in enumerate(report.get("top_10_financial_leaks") or report.get("top_6_financial_leaks") or [], 1):
            if not isinstance(leak, dict):
                continue
            angles = leak.get("solutions_3_angles") or {}
            factor = leak.get("severity_factor")
            factor_display = "Unknown" if factor is None else str(factor)
            leaks_html += f"""
            <div style="margin-bottom:32px; border-left:4px solid #D8B66A; padding-left:16px;">
                <h3 style="font-family:Georgia,serif; font-size:18px; color:#090B12; margin:0 0 6px 0; font-weight:700;">{idx}. {html.escape(str(leak.get('leak_name','')))}</h3>
                <p style="font-family:Inter,sans-serif; font-size:13px; color:#555; margin:0 0 8px 0; line-height:1.5;">{html.escape(str(leak.get('impact_summary','')))}</p>
                <p style="font-family:Inter,sans-serif; font-size:10px; color:#6B7280; margin:0 0 6px 0; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">{html.escape(str(leak.get('finding_type','VERIFIED_LEAK')).replace('_',' '))}</p>
                <p style="font-family:Inter,sans-serif; font-size:11px; color:#C85A5A; margin:0 0 12px 0; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">{html.escape(str(leak.get('severity_label','SEVERITY UNKNOWN')))} &nbsp;|&nbsp; Severity Scale: {factor_display} &nbsp;|&nbsp; Score Loss: -{float(leak.get('severity_score') or 0):.2f} pts</p>
                <div style="background:#fdfdfd; border:1px solid #f0f0f0; border-radius:8px; padding:16px; margin-top:10px;">
                    <p style="font-family:Inter,sans-serif; font-size:12px; color:#111; font-weight:700; margin:0 0 10px 0; text-transform:uppercase; letter-spacing:0.5px;">The 3-Angle Remediation Plan:</p>
                    <p style="font-family:Inter,sans-serif; font-size:13px; color:#222; margin:0 0 8px 0; line-height:1.6;"><strong>Technical Angle:</strong> {html.escape(str(angles.get('technical','')))}</p>
                    <p style="font-family:Inter,sans-serif; font-size:13px; color:#222; margin:0 0 8px 0; line-height:1.6;"><strong>UX / CRO Angle:</strong> {html.escape(str(angles.get('cro_ux','')))}</p>
                    <p style="font-family:Inter,sans-serif; font-size:13px; color:#222; margin:0 0 12px 0; line-height:1.6;"><strong>Systems Angle:</strong> {html.escape(str(angles.get('systems','')))}</p>
                    <p style="font-family:Inter,sans-serif; font-size:13px; color:#111; margin:0 0 8px 0; line-height:1.6;"><strong>Why We Recommend This:</strong> {html.escape(str(angles.get('why_recommend','')))}</p>
                    <p style="font-family:Inter,sans-serif; font-size:13px; color:#111; margin:0; line-height:1.6;"><strong>Implementation Cadence ({html.escape(str(angles.get('cadence_title','Week 1')))}):</strong> {html.escape(str(angles.get('cadence_text','')))}</p>
                </div>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f5f5f5; font-family:Inter, -apple-system, sans-serif;">
<div style="max-width:640px; margin:0 auto; background:#fff; padding:32px 28px;">
    <h1 style="font-family:Georgia, serif; font-size:28px; color:#090B12; margin:0 0 8px 0; line-height:1.2;">Trilloka Telemetry & Executive Audit</h1>
    <p style="font-family:Inter,sans-serif; font-size:14px; color:#5A7A9E; margin:0 0 20px 0;"><strong>Report Vault ID:</strong> {vault_id}<br><strong>Target Domain:</strong> {domain}<br><strong>Business Model:</strong> {biz_type}<br><strong>CMS Detected:</strong> {cms}<br><strong>AI / Template Pattern Spectrum:</strong> {ai_display}</p>

    <div style="background:#121621; color:#F2F0E8; border-radius:12px; padding:24px; margin:20px 0; text-align:center;">
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#A9A7A0; text-transform:uppercase; letter-spacing:2px; margin:0 0 8px 0;">Overall Performance Score</p>
        <p style="font-family:Georgia,serif; font-size:48px; color:{score_color}; margin:0; line-height:1;">{score:.1f}</p>
        <p style="font-family:Inter,sans-serif; font-size:14px; color:#D8B66A; margin:8px 0 0 0; font-weight:600;">{rating}</p>
    </div>

    <div style="background:rgba(200,90,90,0.08); border:1px solid rgba(200,90,90,0.25); border-radius:12px; padding:20px; margin:16px 0; text-align:center;">
        <p style="font-family:Inter,sans-serif; font-size:11px; color:#C85A5A; text-transform:uppercase; letter-spacing:1.5px; margin:0 0 6px 0; font-weight:700;">REVENUE EXPOSURE</p>
        <p style="font-family:Georgia,serif; font-size:28px; color:#C85A5A; margin:0; font-weight:700;">{revenue_exposure}</p>
    </div>

    <div style="margin:24px 0 28px 0; padding:0 4px;"><p style="font-family:Georgia,serif; font-size:14px; font-style:italic; color:#333333; margin:0; line-height:1.6;">According to the Architect, these are the strongest evidence-backed ways to address the verified issues from technical, conversion and operational angles. Unknown telemetry is not treated as failure.</p></div>

    <div style="background:#F9FAFB; border:1px solid #E5E7EB; border-radius:12px; padding:18px; margin:24px 0;">
        <h3 style="font-family:Georgia,serif; font-size:16px; color:#090B12; margin:0 0 8px 0;">📐 Score Rating Impact: {html.escape(str(score_impact.get('level','N/A')))}</h3>
        <p style="font-family:Inter,sans-serif; font-size:13px; color:#4B5563; margin:0 0 8px 0; line-height:1.5;"><strong>Business Impact:</strong> {html.escape(str(score_impact.get('impact_summary','')))}</p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#6B7280; margin:0; line-height:1.5;"><strong>Engine Behavior:</strong> {html.escape(str(score_impact.get('severity_behavior','')))}</p>
    </div>

    <div style="background:#121621; color:#F2F0E8; border-radius:12px; padding:20px; margin:24px 0;">
        <h3 style="font-family:Georgia,serif; font-size:16px; color:#D8B66A; margin:0 0 10px 0;">🧠 Scoring Methodology & Reasonability</h3>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#D1D5DB; margin:0 0 8px 0; line-height:1.5;">• <strong>Graded Continuum:</strong> {html.escape(str(methodology.get('graded_continuum','')))}</p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#D1D5DB; margin:0 0 8px 0; line-height:1.5;">• <strong>Vertical Weighting:</strong> {html.escape(str(methodology.get('vertical_weighting','')))}</p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#D1D5DB; margin:0; line-height:1.5;">• <strong>Hygiene:</strong> {html.escape(str(methodology.get('hygiene_gatekeeping','')))}</p>
    </div>

    <h2 style="font-family:Georgia,serif; font-size:22px; color:#090B12; margin:32px 0 20px 0; font-weight:700;">🎯 10 Highest-Priority Revenue Findings & 3-Angle Fixes</h2>
    {leaks_html}

    <div style="background:#121621; color:#F2F0E8; border-radius:12px; padding:20px; margin:24px 0;">
        <h3 style="font-family:Georgia,serif; font-size:16px; color:#D8B66A; margin:0 0 12px 0;">📊 Full 50-Point Checkpoint Basis</h3>
        <p style="font-family:Inter,sans-serif; font-size:14px; margin:0 0 8px 0;">Verified: <strong>{summary.get('verified',0)}</strong> &nbsp;|&nbsp; Passed: <span style="color:#22C55E; font-weight:700;">{summary.get('passed',0)}</span> &nbsp;|&nbsp; Failed: <span style="color:#EF4444; font-weight:700;">{summary.get('failed',0)}</span></p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#A9A7A0; margin:0 0 5px 0;">Unknown: {summary.get('unknown',0)} &nbsp;|&nbsp; N/A: {summary.get('not_applicable',0)}</p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#A9A7A0; margin:0;">Trust & Conversion: 15 checks | SEO & Technical: 20 checks | Content & E-E-A-T: 15 checks</p>
    </div>

    <div style="text-align:center; margin:28px 0 20px 0;"><a href="#" style="font-family:Inter,sans-serif; font-size:13px; color:#2563EB; text-decoration:none; font-weight:600;">Access Complete Raw Vault Telemetry Entry</a></div>

    <div style="border-top:1px solid #e0e0e0; margin-top:24px; padding-top:20px;"><p style="font-family:Inter,sans-serif; font-size:11px; color:#555555; line-height:1.6; margin:0;"><strong>DISCLAIMER & TERMS OF SALE:</strong> This diagnostic report reflects evidence available to the scanner at the recorded time. Unknown or inaccessible telemetry is not treated as a failure. Revenue exposure labels are model-based unless the business supplied validated traffic, conversion and transaction-value inputs. Results and performance improvements depend on correct implementation and later platform changes.</p></div>
</div>
</body>
</html>"""

    def archive_to_vault(self, target_domain: str, admin_report: Dict[str, Any], raw_scan_data: Dict[str, Any]) -> str:
        os.makedirs(self.vault_dir, exist_ok=True)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        sanitized = (target_domain or "unknown").replace("https://", "").replace("http://", "").replace("/", "_")
        filename = f"{self.vault_dir}/{sanitized}_{timestamp}.json"
        vault_entry = {
            "vault_id": (admin_report or {}).get("vault_id", f"VAULT-{timestamp}"),
            "domain": target_domain,
            "archived_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "admin_report": admin_report,
            "raw_telemetry": raw_scan_data,
            "scoring_ledger": (admin_report or {}).get("scoring_ledger", []),
            "overlap_adjustments": (admin_report or {}).get("overlap_adjustments", []),
            "score_formula": (admin_report or {}).get("score_formula", {}),
            "checkpoint_basis": (admin_report or {}).get("full_50_checkpoint_basis", []),
        }
        with open(filename, "w", encoding="utf-8") as handle:
            json.dump(vault_entry, handle, indent=2, ensure_ascii=False, default=str)

        # Also persist the customer-readable action report as a standalone HTML file.
        html_filename = f"{self.vault_dir}/{sanitized}_{timestamp}_report.html"
        with open(html_filename, "w", encoding="utf-8") as handle:
            handle.write(self._build_email_html(admin_report))

        print(f"[Vault] Archived scan snapshot to {filename}")
        print(f"[Vault] Archived customer-readable report to {html_filename}")
        return filename
