"""Trilloka report/vault engine.

V7.1: reports a universal Common Foundation layer plus adaptive Journey + Context architecture.
It exposes score scope, Evidence Confidence and maturity-band eligibility so a high
Revenue Readiness number cannot be mistaken for product-market fit, sales performance or revenue.

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
from architecture_model import JOURNEY_LABELS, CONTEXT_LABELS


class ReportGenerator:
    def __init__(self):
        self.resend_api_key = os.environ.get("RESEND_API_KEY", "")
        self.from_email = os.environ.get("FROM_EMAIL", "alerts@trilloka.com")
        self.admin_email = os.environ.get("ADMIN_EMAIL", "arpitt22@trilloka.com")
        self.vault_dir = os.environ.get("VAULT_DIR", "./vault_archives")

    def generate_admin_master_report(self, audit_data: Dict[str, Any], scan_data: Dict[str, Any]) -> Dict[str, Any]:
        audit = audit_data or {}
        scan = scan_data or {}
        business_profile = audit.get("architecture_profile") or audit.get("business_profile") or scan.get("architecture_profile") or scan.get("business_profile") or {"journey_model": audit.get("business_type", "general")}

        checkpoints = audit.get("full_50_checkpoint_basis") or build_50_checkpoints(scan, audit)
        summary = audit.get("checkpoint_summary") or checkpoint_summary(checkpoints)

        packages = audit.get("tiered_remediation_packages") or {}
        # V5 customer report prefers the family-consolidated Top-10 package.
        # all_scoring_leaks remains raw/backward-compatible for integrations and Vault analysis.
        leaks = packages.get("tier_10_arch10") or packages.get("all_scoring_leaks") or []
        # The scorer has already ordered tier_10_arch10 by commercial/revenue priority.
        # Preserve that order here; re-sorting by raw severity would let ordinary technical
        # hygiene jump above higher-consequence conversion friction.
        ordered_leaks = [item for item in leaks if isinstance(item, dict)]

        enriched: List[Dict[str, Any]] = []
        for leak in ordered_leaks[:10]:
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

        overall = audit.get("overall_health_score")
        if overall is None:
            overall = audit.get("overall_score")
        revenue_display = (audit.get("revenue_leak") or {}).get("est_annual_revenue_leak") or "Not measured"

        return {
            "report_type": "ADMIN_LEAD_ALERT",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "target_domain": audit.get("target_domain", scan.get("domain", "Unknown")),
            "business_type": str(audit.get("business_type", business_profile.get("journey_model", "general"))).upper(),
            "business_profile": business_profile,
            "architecture_profile": business_profile,
            "journey_model": str(business_profile.get("journey_model") or audit.get("business_type") or "general"),
            "journey_label": str(business_profile.get("journey_label") or JOURNEY_LABELS.get(str(business_profile.get("journey_model") or "general"), "General / Unresolved Journey")),
            "context_tags": list(business_profile.get("context_tags") or []),
            "context_labels": list(business_profile.get("context_labels") or []),
            "analysis_layers": audit.get("analysis_layers") or {},
            "overall_health_score": overall,
            "score_rating": audit.get("score_rating", ""),
            "score_scope": audit.get("score_scope", ""),
            "evidence_confidence": audit.get("evidence_confidence") or {},
            "maturity_gate": audit.get("maturity_gate") or {},
            "vault_id": audit.get("vault_id", ""),
            "estimated_revenue_leak": revenue_display,
            "revenue_exposure": audit.get("revenue_leak") or {},
            "financial_exposure": audit.get("financial_exposure") or audit.get("revenue_leak") or {},
            "scoring_methodology": self._build_scoring_methodology_explanation(audit),
            "score_level_impact": (
                self._build_score_level_impact_explanation(float(overall), audit)
                if overall is not None
                else {
                    "level": "SCORE UNAVAILABLE",
                    "impact_summary": "The scoring engine did not supply an overall score.",
                    "severity_behavior": "No synthetic zero was substituted.",
                }
            ),
            "top_10_financial_leaks": findings,
            # Backward-compatible alias for any old template/client code.
            "top_6_financial_leaks": findings[:6],
            "verified_financial_leak_count": len(enriched),
            "full_50_checkpoint_basis": checkpoints,
            "checkpoint_summary": summary,
            "verification_coverage_note": self._verification_coverage_note(summary),
            "behavioral_diagnostics": audit.get("behavioral_diagnostics", {}),
            "ai_spectrum_pct": audit.get("ai_spectrum_pct"),
            "ai_spectrum_status": audit.get("ai_spectrum_status", scan.get("ai_spectrum_status", "unknown")),
            "cms_platform": scan.get("cms_platform", "Not confidently identified"),
            "cms_confidence": scan.get("cms_confidence", "low"),
            "scanner_engine_version": scan.get("scanner_engine_version", "unknown"),
            "scan_quality": audit.get("scan_quality") or scan.get("scan_quality") or {},
            "scoring_ledger": audit.get("scoring_ledger") or [],
            "overlap_adjustments": audit.get("overlap_adjustments") or [],
            "score_formula": audit.get("score_formula") or {},
            "evidence_receipts": audit.get("evidence_receipts") or [],
            "high_impact_confirmation": audit.get("high_impact_confirmation") or scan.get("high_impact_confirmation") or {},
            "foundation_omission_signal": audit.get("foundation_omission_signal") or {},
            "foundation_omission_report_filename": "",
            "unconfirmed_high_impact_observations": audit.get("unconfirmed_high_impact_observations") or [],
            "rescan_comparison": audit.get("rescan_comparison") or {},
            "browser_journey_probe": scan.get("browser_journey_probe") or {},
            "external_booking_provider_health": scan.get("external_booking_provider_health") or {},
            "business_type_validation": scan.get("business_type_validation") or {},
        }


    def build_implementation_roadmap(
        self,
        findings: List[Dict[str, Any]],
        days: int,
    ) -> List[Dict[str, Any]]:
        """Build a deterministic plan-specific roadmap without changing finding structure.

        14-day plans use four short execution phases. 30-day plans use four weekly
        phases. Every unlocked finding appears exactly once, in ranked order.
        """
        items = [item for item in (findings or []) if isinstance(item, dict)]
        days = int(days or 0)
        if days <= 0 or not items:
            return []

        if days <= 14:
            phases = [
                ("Days 1–3", "Stabilize the highest-value blockers"),
                ("Days 4–7", "Repair conversion-path and trust friction"),
                ("Days 8–11", "Improve measured experience and supporting systems"),
                ("Days 12–14", "Verify, re-scan and close regressions"),
            ]
        else:
            phases = [
                ("Week 1", "Fix critical commercial blockers"),
                ("Week 2", "Repair conversion, form and trust architecture"),
                ("Week 3", "Improve measured performance and supporting experience"),
                ("Week 4", "Re-test, validate evidence and lock in gains"),
            ]

        # Split ranked findings as evenly as possible while keeping the highest
        # impact work earliest.
        n = len(items)
        phase_count = len(phases)
        base = n // phase_count
        remainder = n % phase_count
        roadmap: List[Dict[str, Any]] = []
        cursor = 0

        for idx, (label, objective) in enumerate(phases):
            take = base + (1 if idx < remainder else 0)
            phase_items = items[cursor: cursor + take]
            cursor += take
            actions: List[Dict[str, Any]] = []
            for finding in phase_items:
                angles = finding.get("solutions_3_angles") or {}
                actions.append(
                    {
                        "rank": len(actions) + 1,
                        "rule_key": finding.get("rule_key"),
                        "finding": finding.get("leak_name"),
                        "finding_type": finding.get("finding_type", "VERIFIED_LEAK"),
                        "score_loss": finding.get("final_score_loss", finding.get("severity_score", 0.0)),
                        "technical_action": angles.get("technical", ""),
                        "cro_ux_action": angles.get("cro_ux", ""),
                        "systems_action": angles.get("systems", ""),
                        "verification": "Re-scan the affected page/flow and compare the evidence ledger after implementation.",
                    }
                )
            roadmap.append(
                {
                    "phase": label,
                    "objective": objective,
                    "actions": actions,
                }
            )

        return roadmap

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
        used_families = {str(item.get("family") or "") for item in findings if item.get("family")}
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
            cp_family = str(cp.get("family") or "")
            # Do not fill the action list with another member of a family already represented
            # by a verified leak (e.g. performance or trust proof).
            if cp_family and cp_family in used_families:
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
            if cp_family:
                used_families.add(cp_family)

        # If there still are not ten items, use UNKNOWNs only as verification actions, never as
        # revenue failures. This keeps the file complete while preserving evidence integrity.
        for cp in checkpoints:
            if len(findings) >= 10:
                break
            if cp.get("status") != UNKNOWN:
                continue
            cp_family = str(cp.get("family") or "")
            if cp_family and cp_family in used_families:
                continue
            name = str(cp.get("check") or "Telemetry")
            display = f"Verification Priority — {name}"
            if display in used_names:
                continue
            leak = {
                "rule_key": f"verification_{int(cp.get('id') or 0):02d}",
                "checkpoint_id": cp.get("id"),
                "leak_name": display,
                "impact_summary": str(cp.get("customer_note") or "The scanner could not verify this checkpoint from available public evidence. It is not scored as a failure."),
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
            if cp_family:
                used_families.add(cp_family)
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
        profile = audit_data.get("architecture_profile") or audit_data.get("business_profile") or {}
        journey = str(profile.get("journey_label") or profile.get("journey_model") or audit_data.get("business_type") or "General")
        contexts = ", ".join(str(x) for x in (profile.get("context_labels") or [])) or "No special context tags verified"
        return {
            "core_philosophy": "Trilloka measures observable website Revenue Readiness, not literal conversion percentage, product-market fit, demand, sales-team performance or actual revenue. Readiness is earned across three unequal layers—Foundation, Revenue/User Architecture and Elite Architecture—while verified leaks retain separate score impact, severity and evidence confidence.",
            "graded_continuum": "Every deduction is scaled by implementation severity, evidence confidence and journey/context relevance. Unknown telemetry earns no strength and creates no penalty. Severe deductions require independent confirmation or corroboration.",
            "architecture_model": f"Primary customer journey: {journey}. Context tags: {contexts}. Legacy industry selections are only weak hints; the score is driven by observed customer actions and context evidence.",
            "two_layer_model": "Three earned canonical layers are used: Common Foundation (22 points), Revenue/User Architecture (60 points), and Elite Architecture (18 points). The 60-point Revenue/User layer is split into fixed conversion-execution, trust/decision-support, measurement/policy and supporting-experience pillars so low-value content/SEO passes cannot compensate for a weak primary customer path. Elite points require strong verified core architecture first. The canonical 0–100 strength is then mapped monotonically onto the stricter public 0–90 commercial-readiness blueprint; this is not a percentile curve or forced distribution.",
            "vertical_weighting": "Journey + Context weighting replaces broad industry scoring. The same technical condition can have different commercial importance depending on the verified customer action, substitution paths and contextual obligations; legacy industry labels are weak hints only.",
            "hygiene_gatekeeping": "Verified conversion friction and customer-path blockers are prioritized ahead of ordinary SEO hygiene. Ecommerce checkout weighting is Baymard-informed only when purchase-context evidence exists and does not claim full Baymard certification; measured performance uses Google/web.dev evidence. Research percentages are never copied directly into site-specific deductions.",
            "financial_exposure_model": "Potential commercial exposure uses an expected-value scenario: annual digital opportunity pool × combined verified path impairment. Overlapping findings are compounded by family instead of added blindly, alternate conversion paths reduce exposure, and score deductions are never converted directly into dollars. Business-supplied economic inputs replace scenario priors when available.",
        }

    @staticmethod
    def _build_score_level_impact_explanation(score: float, audit_data: Dict[str, Any] | None = None) -> Dict[str, str]:
        audit = audit_data or {}
        rating = str(audit.get("score_rating") or "")
        penalty = float((audit.get("score_formula") or {}).get("total_final_penalty") or audit.get("total_severity_index") or 0.0)
        maturity = audit.get("maturity_gate") if isinstance(audit.get("maturity_gate"), dict) else {}
        if "PROVISIONAL" in rating or bool(maturity.get("journey_provisional")):
            return {
                "level": rating or "PROVISIONAL READINESS — CUSTOMER JOURNEY NOT YET RESOLVED",
                "impact_summary": "The scanner verified useful website evidence but has not resolved the primary customer journey strongly enough to present the result as a mature commercial model.",
                "severity_behavior": f"Verified penalty burden is {penalty:.2f} canonical points. UNKNOWN evidence remains neutral; the unresolved journey limits what can be earned, rather than creating a hidden deduction.",
            }
        if score >= 80:
            return {"level":"NEAR-PERFECT VERIFIED OBSERVABLE ARCHITECTURE (80–90)","impact_summary":"The observable customer journey, trust, measurement and supporting architecture are near-complete, with almost no verified commercial leakage. The score still does not claim 100% visitor conversion or guaranteed revenue performance.","severity_behavior":"This band is reserved for near-perfect canonical 22/60/18 strength after the transparent 0–90 blueprint calibration; ordinary technical hygiene cannot reach it."}
        if score >= 70:
            return {"level":"GENUINELY EXCEPTIONAL OBSERVABLE ARCHITECTURE (70–79)","impact_summary":"The website demonstrates unusually complete, evidence-backed commercial architecture with only limited observable headroom.","severity_behavior":"Exceptional scores require strong Revenue/User Architecture plus difficult-to-earn Elite evidence; UNKNOWN completion evidence still withholds readiness points."}
        if score >= 59:
            return {"level":"STRONG COMMERCIAL WEBSITE (59–69)","impact_summary":"The website supports its primary customer journey well, with strong commercial architecture and only bounded material headroom.","severity_behavior":f"Verified penalty burden is {penalty:.2f} canonical points; score separation comes primarily from what was earned in conversion execution, trust, measurement and Elite maturity."}
        if score >= 46:
            return {"level":"FUNCTIONAL COMMERCIAL WEBSITE (46–58)","impact_summary":"The website is commercially functional and supports a usable customer path, but enough journey, trust, measurement, performance or completion evidence is missing to call it strong.","severity_behavior":"Functional sites can pass many basics, but the non-compensatory commercial pillars prevent those basics from manufacturing a strong score."}
        if score >= 35:
            return {"level":"MATERIAL COMMERCIAL WEAKNESSES (35–45)","impact_summary":"The website may look polished or credible, but material observable weaknesses remain in the revenue/user architecture.","severity_behavior":"This is the intended band for Hasler-like polished sites whose technical/trust surface is stronger than their verified end-to-end commercial readiness."}
        if score >= 26:
            return {"level":"BROKEN / HIGH-RISK COMMERCIAL ARCHITECTURE (26–34)","impact_summary":"The customer path has substantial structural, conversion, trust, performance or measurement weakness and cannot be considered reliably commercial-ready.","severity_behavior":"A score in this range requires weak earned architecture and/or verified customer-path failures; the engine does not force sites into a target distribution."}
        return {"level":"CRITICAL REVENUE ARCHITECTURE WEAKNESS (0–25)","impact_summary":"Severe observable architecture weaknesses materially compromise the website's ability to support a dependable customer journey.","severity_behavior":"The canonical score is earned from zero across the three layers and then mapped to the 0–90 public blueprint; there is no operating baseline protecting a severely weak site."}

    def _build_3_angle_solutions(
        self,
        rule_key: str,
        leak: Dict[str, Any],
        scan_data: Dict[str, Any],
        business_profile: Dict[str, Any],
    ) -> Dict[str, str]:
        vertical = str(business_profile.get("journey_model") or business_profile.get("vertical") or "general")
        context_tags = {str(x) for x in (business_profile.get("context_tags") or []) if x}
        evidence = leak.get("evidence") or {}
        family = str(leak.get("family") or "")
        supporting = set(str(x) for x in (leak.get("supporting_rule_keys") or []) if x)

        if family == "performance" or rule_key == "core_web_vitals":
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

        if family == "mobile_direct_action" and len(supporting) > 1:
            labels = self._vertical_cta_labels(vertical)
            return {
                "technical": f"Consolidate the verified mobile direct-action gaps into one clean action system: keep {labels['primary']} prominent, make any supported call/contact action directly tappable, and add persistence only where it improves the primary journey without covering content or consent controls.",
                "cro_ux": f"Prioritize {labels['primary']} and treat {labels['secondary']} as supporting paths. Avoid stacking multiple competing buttons simply to satisfy individual checks.",
                "systems": "Track the primary action, sticky-action engagement and secondary direct-contact actions as separate events so the business can measure which path actually creates progression.",
                "why_recommend": "Multiple related mobile-action signals were detected, but Trilloka consolidates them into one commercial finding so the same underlying friction is not reported or scored as several separate leaks.",
                "cadence_title": "Weeks 1–2",
                "cadence_text": "Fix the primary mobile action architecture once, verify it after scrolling and on common viewport sizes, then compare action engagement before adding further controls.",
            }

        if rule_key == "click_to_call":
            if "local_location_dependent" in context_tags and vertical in {"lead_quote", "appointment_consultation", "reservation_event"}:
                return {
                    "technical": "Wrap verified phone numbers in tel: links and ensure the mobile target is comfortably tappable. A 48×48 CSS px target may be used as Trilloka's usability recommendation, not as a claimed universal standard.",
                    "cro_ux": "Place calling near the highest-intent quote, appointment or reservation path without obscuring the primary form/booking action.",
                    "systems": "Track call-click and completed customer-journey events separately so the business can measure whether calling actually contributes to progression.",
                    "why_recommend": "The observed journey is local/direct-contact dependent, so a verified missing tap action matters more here than it would in a direct-purchase or subscription journey.",
                    "cadence_title": "Week 1",
                    "cadence_text": "Enable the direct mobile call path, verify routing, then measure it without displacing the stronger primary action.",
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
                "cro_ux": f"Keep the persistent action aligned to the observed customer journey: prioritize {labels['primary']} and use {labels['secondary']} only as supporting actions.",
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
                "technical": "If the business intends to measure website outcomes, implement or expose a suitable analytics layer and verify that key conversion events fire once, with consent handling appropriate to the jurisdiction and stack. Do not replace an existing valid first-party/server-side system merely to satisfy a vendor-specific check.",
                "cro_ux": "Define the small number of actions that represent real customer progress rather than treating every click as a conversion.",
                "systems": "Create a measurement map for the primary CTA, form/booking/order starts and completed conversions, then validate data quality after deployment.",
                "why_recommend": "The scanner did not detect a common public measurement platform in the rendered/static evidence. It recognizes multiple major analytics systems, so this is a cautious public-evidence gap—not proof that no private or server-side measurement exists.",
                "cadence_title": "Week 1",
                "cadence_text": "Verify whether measurement already exists first; if not, deploy the appropriate layer, validate event integrity, then use observed conversion data to refine later revenue estimates.",
            }

        if rule_key == "conversion_path_error":
            signals = (leak.get("evidence") or {}).get("error_signals") or []
            signal_keys = {str(item.get("key") or "") for item in signals if isinstance(item, dict)}
            captcha_related = any(key.startswith("recaptcha_") for key in signal_keys)
            external_booking = "external_booking_destination_error" in signal_keys
            if captcha_related:
                technical = "Repair the exposed CAPTCHA configuration on the affected conversion page: verify the reCAPTCHA site key/secret pairing, allowed production domains, key type/version and plugin/widget configuration. Re-test the public page after the fix without relying on an admin session."
            elif external_booking:
                technical = "Repair or replace the verified broken external booking destination. Confirm the public booking URL still belongs to the intended provider/account, resolves without a 404/5xx response, and that every Book/Reserve link points to the healthy destination. Do not create a test appointment simply to verify availability."
            else:
                technical = "Repair the specific public-facing form/booking/widget error captured in the attached evidence and verify the affected conversion page loads a usable customer action end-to-end without exposing an error state."
            return {
                "technical": technical,
                "cro_ux": "Until the primary path is verified healthy, expose a clear fallback action such as tap-to-call, email or an alternate booking/contact route so interested visitors are not stranded by the broken path.",
                "systems": "Add a lightweight recurring health check for primary contact/booking/checkout pages and alert on known error strings, 4xx/5xx responses or missing conversion widgets so failures are discovered before customers report them.",
                "why_recommend": "Trilloka observed an explicit error state on a public customer conversion page. This is stronger evidence than a generic best-practice suggestion, and the scanner did not submit the form or mutate customer data.",
                "cadence_title": "Immediate / Week 1",
                "cadence_text": "Repair and verify the broken customer path first, keep a fallback contact route visible during the fix, then re-scan the same page before changing lower-priority CRO elements.",
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
        if rule_key == "privacy_terms_missing":
            outer = leak.get("evidence") if isinstance(leak.get("evidence"), dict) else {}
            detail = outer.get("evidence") if isinstance(outer.get("evidence"), dict) else {}
            privacy_only = detail.get("requirement") == "privacy_only"
            if privacy_only:
                return {
                    "technical": "Publish an accessible Privacy policy appropriate to the data actually collected by forms, tracking or the professional service, and link it consistently from the footer/form context.",
                    "cro_ux": "Place the Privacy link where users provide information without cluttering the primary action. Terms are not being prescribed by this finding.",
                    "systems": "Review the Privacy policy whenever forms, analytics, booking, health/professional data handling or third-party processors change.",
                    "why_recommend": "This recommendation is limited to the policy requirement the scanner could justify from the verified data-collection/business context.",
                    "cadence_title": "Weeks 1–2",
                    "cadence_text": "Publish the applicable policy, verify the link on the live conversion path, then re-scan.",
                }
        plans: Dict[str, tuple[str, str, str]] = {
            "primary_conversion_path": (
                "Expose one clear primary conversion action that matches the customer journey/context and works on mobile before adding secondary CTAs.",
                "Make the main next step unmistakable: purchase, book, request a quote, start a trial, or contact — whichever represents real customer progress.",
                "Track the primary action separately from secondary navigation so completion and drop-off can be measured.",
            ),
            "lead_form_friction": (
                "Remove nonessential lead-form inputs, defer qualification questions until after the first conversion where possible, and preserve validation/error handling.",
                "Ask only for information needed to continue the sales or booking process; move nice-to-have questions to a later step.",
                "Measure form starts, validation errors and successful submissions so field reductions are evaluated against qualified-lead quality.",
            ),
            "checkout_cost_transparency": (
                "Surface shipping, tax and unavoidable fee estimates as early as technically possible and keep the order total synchronized throughout checkout.",
                "Avoid surprising shoppers with material costs at the final step; make total-cost expectations visible before commitment.",
                "Regression-test pricing, shipping and tax calculations across common regions and cart states.",
            ),
            "guest_checkout_barrier": (
                "Provide a guest checkout path when the customer journey/context permits it and offer account creation after purchase rather than making registration a prerequisite.",
                "Keep sign-in useful for returning customers without blocking first-time buyers who want to complete the order quickly.",
                "Track guest vs. account checkout completion and post-purchase account creation separately.",
            ),
            "checkout_complexity": (
                "Reduce the number of customer-input fields to those needed to process the order, use address/payment autofill where appropriate, and hide optional fields until needed.",
                "Lower perceived effort by grouping only necessary information and keeping the path to payment obvious.",
                "Monitor checkout field errors and abandonment by stage so complexity fixes target the actual friction points.",
            ),
            "delivery_expectation_clarity": (
                "Expose a concrete delivery-date or delivery-window expectation when it can be calculated, rather than relying only on vague shipping-speed labels.",
                "Help buyers understand when the order will arrive before they commit.",
                "Keep delivery estimates synchronized with inventory, fulfillment method, destination and carrier data.",
            ),
            "return_policy_discoverability": (
                "Link the real return/refund policy from predictable shopping and footer locations and ensure the policy page is accessible on mobile.",
                "Make return conditions easy to find before purchase without crowding the primary buying action.",
                "Keep policy copy synchronized with support and fulfillment processes as terms change.",
            ),
            "shipping_info_discoverability": (
                "Provide a clearly discoverable shipping/delivery information path with regions, methods, cost rules and timing where applicable.",
                "Let shoppers resolve shipping uncertainty before they reach the final checkout step.",
                "Keep shipping content synchronized with fulfillment configuration and checkout calculations.",
            ),
            "b2b_pricing_transparency": (
                "Expose usable pricing context where possible: published pricing, starting ranges, plan bands, or a clearly explained quote process.",
                "Give B2B researchers enough commercial context to judge fit before asking them to surrender contact information.",
                "Keep pricing/quote logic synchronized with sales qualification rules so the website and sales team communicate the same buying expectations.",
            ),
            "saas_ui_proof_gap": (
                "Add authentic product-interface screenshots, annotated workflows, video, or an interactive preview that shows the actual software experience.",
                "Help prospects understand what they will use after signup instead of relying only on abstract feature claims.",
                "Keep product visuals current with major UI releases and link important plan-matrix features to explanatory product evidence.",
            ),
            "copy_readability_friction": (
                "Simplify sentence structure and terminology in the highest-intent page copy while preserving necessary technical accuracy.",
                "Use clear customer language, shorter sentences and scannable sections so visitors can understand the offer without unnecessary cognitive effort.",
                "A/B test simplified copy against qualified conversion outcomes; treat the scanner readability grade as a heuristic, not a universal target.",
            ),
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
                "Create a focused expertise/resource hub only if the customer journey/context benefits from ongoing informational demand.",
                "Organize content around customer questions and buying stages rather than generic posting cadence.",
                "Track assisted conversions/search demand so the content program is accountable.",
            ),
            "social_links_missing": (
                "Link only maintained official social profiles with correct rel/security attributes.",
                "Keep social links secondary to onsite conversion so users are not unnecessarily sent away.",
                "Remove abandoned channels and keep profile branding/contact data consistent.",
            ),
            "privacy_terms_missing": (
                "Publish the Privacy and Terms policies required by the verified transaction/account/checkout context and link them consistently.",
                "Expose the applicable policy links near forms/checkout/footer without overwhelming the primary action.",
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
        labels = {
            "lead_quote": {"primary": "Request Quote / Enquire / Contact", "secondary": "Call / Chat"},
            "appointment_consultation": {"primary": "Book Appointment / Consultation", "secondary": "Call / Contact"},
            "reservation_event": {"primary": "Reserve / Book / Event Enquiry", "secondary": "Call / Directions / Contact"},
            "direct_purchase": {"primary": "Add to Cart / Buy / Order Now / Checkout", "secondary": "Product Question / Call / Chat"},
            "demo_sales": {"primary": "Request Demo / Start Trial / Contact Sales", "secondary": "Contact / Chat"},
            "membership_subscription": {"primary": "Join / Subscribe / Membership", "secondary": "Contact / Community"},
            "general": {"primary": "Primary Customer Action", "secondary": "Contact / Secondary Action"},
        }
        return labels.get(str(vertical or "general"), labels["general"])

    @staticmethod
    def _h1_cro_copy(vertical: str, scan: Dict[str, Any]) -> str:
        current = " / ".join(scan.get("h1_tags") or [])
        prefix = f"The current verified H1 is '{current}'. " if current else ""
        journey_copy = {
            "lead_quote": "Make the hero state the customer problem/outcome clearly and align it to quote or enquiry intent.",
            "appointment_consultation": "Make the hero state the service/outcome clearly and align it to appointment or consultation intent.",
            "reservation_event": "Make the hero identify the experience/event/availability value clearly and align it to reservation or enquiry intent.",
            "direct_purchase": "Make the hero state the product/category value clearly and align it to shopping or purchase intent.",
            "demo_sales": "Make the hero explain the business outcome clearly and align it to demo, trial or sales-contact intent.",
            "membership_subscription": "Make the hero explain the ongoing member/subscriber value and align it to join or subscribe intent.",
            "general": "Make the hero communicate the primary customer outcome and align it to the site's verified primary action.",
        }
        return prefix + journey_copy.get(str(vertical or "general"), journey_copy["general"])

    def _build_50_checkpoints(self, scan_data: Dict[str, Any], audit_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return build_50_checkpoints(scan_data, audit_data)

    @staticmethod
    def _checkpoint_summary(checkpoints: List[Dict[str, Any]]) -> Dict[str, int]:
        return checkpoint_summary(checkpoints)

    @staticmethod
    def _verification_coverage_note(summary: Dict[str, Any]) -> str:
        verified = int(summary.get("verified") or 0)
        applicable = int(summary.get("applicable") or max(0, 50 - int(summary.get("not_applicable") or 0)))
        unknown = int(summary.get("unknown") or 0)
        ratio = float(summary.get("verified_applicable_ratio") or (verified / applicable if applicable else 0.0))
        if ratio >= 0.80:
            level = "High public-evidence coverage"
        elif ratio >= 0.60:
            level = "Moderate public-evidence coverage"
        else:
            level = "Limited public-evidence coverage"
        breakdown = summary.get("unknown_breakdown") or {}
        reason_labels = {
            "FIELD_DATA_UNAVAILABLE": "real-user field data unavailable",
            "PUBLIC_PROVENANCE_LIMIT": "public provenance cannot be proven",
            "JURISDICTION_CONTEXT_REQUIRED": "jurisdiction/consent context required",
            "SAFE_SUBMISSION_LIMIT": "safe live submission intentionally not performed",
            "GOOGLE_TELEMETRY_UNAVAILABLE": "Google/Lighthouse telemetry unavailable",
            "PUBLIC_VERIFICATION_GAP": "public evidence could not independently verify the signal",
        }
        parts = [f"{count} {reason_labels.get(code, code.lower().replace('_', ' '))}" for code, count in breakdown.items() if int(count or 0) > 0]
        breakdown_text = (" Reasons: " + "; ".join(parts) + ".") if parts else ""
        return (
            f"{level}: {verified}/{applicable} applicable checkpoints were independently verified. "
            f"The remaining {unknown} checkpoint(s) are UNKNOWN. UNKNOWN does not mean FAILED and causes no score deduction. "
            "These are transparent public-verification limits, not hidden failures."
            + breakdown_text
        )

    def send_admin_alert_email(self, admin_report: Dict[str, Any]) -> bool:
        if not self.resend_api_key:
            print("[Email] RESEND_API_KEY not configured — skipping email")
            return False
        domain_safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(admin_report.get("target_domain") or "site")).strip("_") or "site"
        attachment_name = f"Trilloka_Revenue_Audit_{domain_safe}.html"
        foundation_name = f"Trilloka_Foundation_Omissions_{domain_safe}.html"
        report_for_email = dict(admin_report or {})
        report_for_email["foundation_omission_report_filename"] = foundation_name
        html_body = self._build_email_html(report_for_email)
        attachment_content = base64.b64encode(html_body.encode("utf-8")).decode("ascii")
        foundation_html = self._build_foundation_omissions_html(report_for_email)
        foundation_content = base64.b64encode(foundation_html.encode("utf-8")).decode("ascii")
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
                        },
                        {
                            "filename": foundation_name,
                            "content": foundation_content,
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
        journey_label = html.escape(str(report.get("journey_label") or report.get("business_type", "GENERAL")).replace("_", " "))
        context_display = html.escape(", ".join(str(x) for x in (report.get("context_labels") or [])) or "No special context tags verified")
        business_profile = report.get("business_profile") or {}
        provisional_journey = bool(business_profile.get("provisional"))
        journey_confidence = business_profile.get("confidence")
        journey_confidence_text = "N/A" if journey_confidence is None else f"{float(journey_confidence)*100:.0f}%"
        revenue_exposure = html.escape(str(report.get("estimated_revenue_leak", "Not measured")))
        cms = html.escape(str(report.get("cms_platform") or "Not confidently identified"))
        ai_pct = report.get("ai_spectrum_pct")
        ai_display = "Unknown" if ai_pct is None else f"{float(ai_pct):.1f}/100"
        methodology = report.get("scoring_methodology") or {}
        score_impact = report.get("score_level_impact") or {}
        summary = report.get("checkpoint_summary") or self._checkpoint_summary(report.get("full_50_checkpoint_basis") or [])
        coverage_note = html.escape(str(report.get("verification_coverage_note") or self._verification_coverage_note(summary)))
        evidence_confidence = report.get("evidence_confidence") if isinstance(report.get("evidence_confidence"), dict) else {}
        maturity_gate = report.get("maturity_gate") if isinstance(report.get("maturity_gate"), dict) else {}
        score_scope = html.escape(str(report.get("score_scope") or "Observable website Revenue Readiness only; not product-market fit, demand, traffic quality, pricing, sales execution or actual revenue."))
        foundation_signal = report.get("foundation_omission_signal") if isinstance(report.get("foundation_omission_signal"), dict) else {}
        foundation_triggered = bool(foundation_signal.get("triggered"))
        foundation_count = int(foundation_signal.get("count") or 0)
        foundation_level = html.escape(str(foundation_signal.get("highest_level") or "NONE"))
        foundation_href = html.escape(str(report.get("foundation_omission_report_filename") or "#foundation-omissions"), quote=True)
        foundation_notice = ""
        if foundation_triggered:
            plural = "s" if foundation_count != 1 else ""
            foundation_notice = (
                '<div style="border:1px solid #8B5E3C; background:#FFF7ED; border-radius:14px; padding:20px; margin:0 0 24px 0;">'
                f'<p style="font-family:Inter,sans-serif; font-size:11px; color:#9A3412; text-transform:uppercase; letter-spacing:1.5px; margin:0 0 7px 0; font-weight:800;">MOST IMPORTANTLY — {foundation_level} FOUNDATION NOTICE</p>'
                f'<p style="font-family:Georgia,serif; font-size:23px; color:#1F2937; margin:0 0 10px 0; line-height:1.25;">{foundation_count} verified basic website omission{plural} should be corrected before advanced optimization.</p>'
                '<p style="font-family:Inter,sans-serif; font-size:13px; color:#4B5563; line-height:1.6; margin:0 0 14px 0;">These are foundational implementation requirements, not automatically the site\'s largest revenue leaks. They are surfaced separately so small point values do not hide obvious basics.</p>'
                f'<a href="{foundation_href}" style="font-family:Inter,sans-serif; font-size:13px; color:#7C2D12; text-decoration:underline; font-weight:700;">Review Foundation Omissions →</a>'
                '</div>'
            )

        evidence_level = html.escape(str(evidence_confidence.get("level") or "UNKNOWN"))
        evidence_score = evidence_confidence.get("score")
        evidence_score_text = "N/A" if evidence_score is None else f"{float(evidence_score):.1f}/100"
        maturity_band = html.escape(str(maturity_gate.get("band") or "UNAVAILABLE").replace("_", " "))
        maturity_threshold = maturity_gate.get("advisory_score_threshold", maturity_gate.get("score_cap"))
        maturity_threshold_text = "N/A" if maturity_threshold is None else f"{float(maturity_threshold):.0f}"
        failed_gate_names = [str(x).replace("_", " ") for x in (maturity_gate.get("failed_gate_names") or [])]
        failed_gate_text = html.escape(", ".join(failed_gate_names[:6]) if failed_gate_names else "None at the active maturity tier")
        analysis_layers = report.get("analysis_layers") if isinstance(report.get("analysis_layers"), dict) else {}
        common_layer = analysis_layers.get("common_foundation") if isinstance(analysis_layers.get("common_foundation"), dict) else {}
        adaptive_layer = analysis_layers.get("adaptive_architecture") if isinstance(analysis_layers.get("adaptive_architecture"), dict) else {}
        common_summary = common_layer.get("checkpoint_summary") if isinstance(common_layer.get("checkpoint_summary"), dict) else {}
        adaptive_summary = adaptive_layer.get("checkpoint_summary") if isinstance(adaptive_layer.get("checkpoint_summary"), dict) else {}
        common_verified = int(common_summary.get("verified") or 0)
        common_applicable = int(common_summary.get("applicable") or common_summary.get("total") or common_layer.get("checkpoint_count") or 0)
        adaptive_verified = int(adaptive_summary.get("verified") or 0)
        adaptive_applicable = int(adaptive_summary.get("applicable") or adaptive_layer.get("checkpoint_count") or 0)
        common_strength = float(common_layer.get("strength_awarded") or 0.0)
        adaptive_strength = float(adaptive_layer.get("strength_awarded") or 0.0)
        common_penalty = float(common_layer.get("verified_penalty") or 0.0)
        adaptive_penalty = float(adaptive_layer.get("verified_penalty") or 0.0)
        rescan = report.get("rescan_comparison") if isinstance(report.get("rescan_comparison"), dict) else {}
        confirmation = report.get("high_impact_confirmation") if isinstance(report.get("high_impact_confirmation"), dict) else {}
        confirmation_results = confirmation.get("results") if isinstance(confirmation.get("results"), dict) else {}
        confirmed_count = sum(1 for x in confirmation_results.values() if isinstance(x, dict) and str(x.get("status") or "").upper() == "CONFIRMED")
        corroborated_count = sum(1 for x in confirmation_results.values() if isinstance(x, dict) and str(x.get("status") or "").upper() == "CORROBORATED")
        unresolved_count = sum(1 for x in confirmation_results.values() if isinstance(x, dict) and str(x.get("status") or "").upper() in {"DISPUTED", "UNCONFIRMED", ""})

        score_color = "#22C55E" if score >= 70 else "#D8B66A" if score >= 46 else "#EF4444"
        findings = report.get("top_10_financial_leaks") or report.get("top_6_financial_leaks") or []
        findings_count = len([item for item in findings if isinstance(item, dict)])
        leaks_html = ""
        for idx, leak in enumerate(findings, 1):
            if not isinstance(leak, dict):
                continue
            angles = leak.get("solutions_3_angles") or {}
            factor = leak.get("severity_factor")
            factor_display = "Unknown" if factor is None else str(factor)
            research = leak.get("research_basis") or {}
            research_source = html.escape(str(research.get("source") or "Trilloka verified evidence model"))
            research_class = html.escape(str(research.get("class") or "evidence-weighted diagnostic"))
            receipt = leak.get("evidence_receipt") if isinstance(leak.get("evidence_receipt"), dict) else {}
            receipt_confirmation = receipt.get("confirmation") if isinstance(receipt.get("confirmation"), dict) else {}
            receipt_status = html.escape(str(receipt_confirmation.get("status") or "single-pass / below severe threshold"))
            receipt_url = html.escape(str(receipt.get("url") or domain))
            receipt_signal = html.escape(str(receipt.get("observed_signal") or "Evidence attached in telemetry ledger"))
            receipt_method = html.escape(str(receipt.get("collection_method") or leak.get("source") or "public evidence inspection"))
            receipt_time = html.escape(str(receipt.get("observed_at") or report.get("generated_at") or ""))
            receipt_conf = html.escape(str(receipt.get("confidence") or leak.get("confidence") or "unknown"))
            screenshot_html = ""
            if receipt.get("screenshot_available") and receipt.get("screenshot_data_uri"):
                screenshot_html = (
                    '<div style="margin-top:10px;">'
                    '<p style="font-family:Inter,sans-serif;font-size:10px;color:#6B7280;margin:0 0 5px 0;"><strong>Rendered evidence screenshot:</strong> SHA-256 ' + html.escape(str(receipt.get("screenshot_sha256") or "")) + '</p>'
                    '<img src="' + html.escape(str(receipt.get("screenshot_data_uri") or ""), quote=True) + '" alt="Public page evidence" style="max-width:100%;border:1px solid #E5E7EB;border-radius:8px;">'
                    '</div>'
                )
            receipt_html = (
                '<div style="background:#F8FAFC;border:1px solid #DCE3EA;border-radius:8px;padding:12px;margin:10px 0 12px 0;">'
                '<p style="font-family:Inter,sans-serif;font-size:10px;color:#5A7A9E;margin:0 0 5px 0;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Evidence Receipt</p>'
                '<p style="font-family:Inter,sans-serif;font-size:11px;color:#374151;margin:0;line-height:1.55;"><strong>URL:</strong> ' + receipt_url + '<br><strong>Observed:</strong> ' + receipt_signal + '<br><strong>Method:</strong> ' + receipt_method + '<br><strong>Timestamp:</strong> ' + receipt_time + '<br><strong>Confidence:</strong> ' + receipt_conf + '<br><strong>Severe-finding confirmation:</strong> ' + receipt_status + '</p>'
                + screenshot_html + '</div>'
            )
            leaks_html += f"""
            <div style="margin-bottom:32px; border-left:4px solid #D8B66A; padding-left:16px;">
                <h3 style="font-family:Georgia,serif; font-size:18px; color:#090B12; margin:0 0 6px 0; font-weight:700;">{idx}. {html.escape(str(leak.get('leak_name','')))}</h3>
                <p style="font-family:Inter,sans-serif; font-size:13px; color:#555; margin:0 0 8px 0; line-height:1.5;">{html.escape(str(leak.get('impact_summary','')))}</p>
                <p style="font-family:Inter,sans-serif; font-size:10px; color:#6B7280; margin:0 0 6px 0; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">{html.escape(str(leak.get('finding_type','VERIFIED_LEAK')).replace('_',' '))}</p>
                <p style="font-family:Inter,sans-serif; font-size:11px; color:#C85A5A; margin:0 0 6px 0; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">{html.escape(str(leak.get('severity_label','SEVERITY UNKNOWN')))} &nbsp;|&nbsp; Severity Scale: {factor_display} &nbsp;|&nbsp; Score Loss: -{float(leak.get('severity_score') or 0):.2f} pts</p>
                <p style="font-family:Inter,sans-serif; font-size:10px; color:#6B7280; margin:0 0 12px 0;"><strong>Evidence basis:</strong> {research_source} — {research_class}. Research affects relative priority only after this site-specific condition is verified.</p>
                {receipt_html}
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


        roadmap_html = ""
        roadmap = report.get("implementation_roadmap") or []
        if roadmap:
            phase_html = ""
            for phase in roadmap:
                actions_html = ""
                for action in phase.get("actions") or []:
                    actions_html += (
                        "<li style=\"margin:0 0 8px 0; line-height:1.5;\">"
                        f"<strong>{html.escape(str(action.get('finding') or 'Action'))}:</strong> "
                        f"{html.escape(str(action.get('technical_action') or action.get('cro_ux_action') or 'Implement the verified correction and re-scan.'))}"
                        "</li>"
                    )
                phase_html += f"""
                <div style="margin:0 0 18px 0;">
                    <h3 style="font-family:Georgia,serif; font-size:16px; color:#090B12; margin:0 0 6px 0;">{html.escape(str(phase.get('phase') or 'Phase'))} — {html.escape(str(phase.get('objective') or 'Implementation'))}</h3>
                    <ul style="font-family:Inter,sans-serif; font-size:12px; color:#4B5563; padding-left:20px; margin:0;">{actions_html}</ul>
                </div>
                """
            roadmap_html = f"""
            <div style="background:#F9FAFB; border:1px solid #E5E7EB; border-radius:12px; padding:20px; margin:28px 0;">
                <h2 style="font-family:Georgia,serif; font-size:20px; color:#090B12; margin:0 0 16px 0;">Implementation Roadmap</h2>
                {phase_html}
            </div>
            """

        if rescan.get("has_previous_snapshot"):
            delta = rescan.get("score_delta")
            try:
                delta_number = float(delta) if delta is not None else None
            except Exception:
                delta_number = None
            delta_text = "N/A" if delta_number is None else (f"+{delta_number:.1f}" if delta_number > 0 else f"{delta_number:.1f}")
            fixed = len(rescan.get("fixed_findings") or [])
            new_count = len(rescan.get("new_findings") or [])
            improved_cp = len(rescan.get("checkpoint_improvements") or [])
            regressed_cp = len(rescan.get("checkpoint_regressions") or [])
            methodology_changed = bool(rescan.get("methodology_changed"))
            comparison_note = html.escape(str(rescan.get("comparison_basis") or ""))
            rescan_html = (
                '<div style="background:#ECFDF5;border:1px solid #A7F3D0;border-radius:12px;padding:18px;margin:20px 0;">'
                '<h3 style="font-family:Georgia,serif;font-size:17px;color:#065F46;margin:0 0 8px 0;">Before / After Verification</h3>'
                '<p style="font-family:Inter,sans-serif;font-size:13px;color:#065F46;margin:0;line-height:1.6;"><strong>Previous:</strong> ' + html.escape(str(rescan.get("score_before"))) + ' &nbsp;→&nbsp; <strong>Current:</strong> ' + html.escape(str(rescan.get("score_after"))) + ' &nbsp;(<strong>' + html.escape(delta_text) + '</strong>)<br><strong>Previously flagged findings no longer present:</strong> ' + str(fixed) + '<br><strong>Newly flagged findings:</strong> ' + str(new_count) + '<br><strong>Checkpoint improvements:</strong> ' + str(improved_cp) + ' &nbsp;|&nbsp; <strong>Regressions:</strong> ' + str(regressed_cp) + '</p>'
                '<p style="font-family:Inter,sans-serif;font-size:10px;color:#047857;margin:8px 0 0 0;line-height:1.5;">' + comparison_note + '</p>'
                '</div>'
            )
        else:
            rescan_html = (
                '<div style="background:#F8FAFC;border:1px solid #E5E7EB;border-radius:12px;padding:16px;margin:20px 0;">'
                '<h3 style="font-family:Georgia,serif;font-size:16px;color:#111827;margin:0 0 6px 0;">Baseline Snapshot Created</h3>'
                '<p style="font-family:Inter,sans-serif;font-size:11px;color:#4B5563;margin:0;line-height:1.5;">A future forced re-scan can compare this domain against the current evidence to show verified architectural changes.</p>'
                '</div>'
            )

        confirmation_html = (
            '<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:12px;padding:16px;margin:20px 0;">'
            '<h3 style="font-family:Georgia,serif;font-size:16px;color:#1E3A8A;margin:0 0 6px 0;">High-Impact Confirmation Guardrail</h3>'
            '<p style="font-family:Inter,sans-serif;font-size:11px;color:#1E40AF;margin:0;line-height:1.55;">Potential deductions at or above ' + html.escape(str(confirmation.get("threshold_points") or "3.5")) + ' points require independent passive confirmation. Confirmed: <strong>' + str(confirmed_count) + '</strong>. Corroborated with reduced score effect: <strong>' + str(corroborated_count) + '</strong>. Disputed/unconfirmed and therefore unscored: <strong>' + str(unresolved_count) + '</strong>.</p>'
            '</div>'
        )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f5f5f5; font-family:Inter, -apple-system, sans-serif;">
<div style="max-width:640px; margin:0 auto; background:#fff; padding:32px 28px;">
    <h1 style="font-family:Georgia, serif; font-size:28px; color:#090B12; margin:0 0 8px 0; line-height:1.2;">Trilloka Telemetry & Executive Audit</h1>
    <p style="font-family:Inter,sans-serif; font-size:14px; color:#5A7A9E; margin:0 0 20px 0;"><strong>Report Vault ID:</strong> {vault_id}<br><strong>Target Domain:</strong> {domain}<br><strong>Customer Journey:</strong> {journey_label}<br><strong>Journey Confidence:</strong> {journey_confidence_text}{' — PROVISIONAL' if provisional_journey else ''}<br><strong>Context Tags:</strong> {context_display}<br><strong>CMS Detected:</strong> {cms}<br><strong>AI / Template Pattern Spectrum:</strong> {ai_display}</p>

    <div style="background:#121621; color:#F2F0E8; border-radius:12px; padding:24px; margin:20px 0; text-align:center;">
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#A9A7A0; text-transform:uppercase; letter-spacing:2px; margin:0 0 8px 0;">Revenue Readiness Index</p>
        <p style="font-family:Georgia,serif; font-size:48px; color:{score_color}; margin:0; line-height:1;">{score:.1f}<span style="font-size:20px;color:#A9A7A0;"> / 90</span></p>
        <p style="font-family:Inter,sans-serif; font-size:14px; color:#D8B66A; margin:8px 0 0 0; font-weight:600;">{rating}</p>
    </div>

    <div style="background:#F8FAFC;border:1px solid #DCE3EA;border-radius:12px;padding:16px;margin:16px 0;">
        <p style="font-family:Inter,sans-serif;font-size:11px;color:#5A7A9E;text-transform:uppercase;letter-spacing:1px;margin:0 0 6px 0;font-weight:700;">Evidence & Score Scope</p>
        <p style="font-family:Inter,sans-serif;font-size:12px;color:#374151;margin:0;line-height:1.6;"><strong>Evidence Confidence:</strong> {evidence_level} ({html.escape(evidence_score_text)})<br><strong>Maturity Band:</strong> {maturity_band}<br><strong>Advisory maturity threshold:</strong> {html.escape(maturity_threshold_text)} / 90 <span style="color:#6B7280;">(not a score cap)</span><br><strong>Unmet gate(s) at next band:</strong> {failed_gate_text}</p>
        <p style="font-family:Inter,sans-serif;font-size:10px;color:#6B7280;margin:8px 0 0 0;line-height:1.5;"><strong>Scope:</strong> {score_scope}</p>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:16px 0;">
        <div style="background:#F8FAFC;border:1px solid #DCE3EA;border-radius:12px;padding:14px;">
            <p style="font-family:Inter,sans-serif;font-size:10px;color:#5A7A9E;text-transform:uppercase;letter-spacing:1px;margin:0 0 6px 0;font-weight:700;">Common Foundation</p>
            <p style="font-family:Inter,sans-serif;font-size:12px;color:#374151;margin:0;line-height:1.55;"><strong>Verified:</strong> {common_verified}/{common_applicable}<br><strong>Strength earned:</strong> {common_strength:.2f}<br><strong>Verified penalty:</strong> {common_penalty:.2f}</p>
            <p style="font-family:Inter,sans-serif;font-size:9px;color:#6B7280;margin:6px 0 0 0;line-height:1.45;">Universal HTTPS, SEO/search structure, performance, mobile and accessibility hygiene. Visible in the analysis but deliberately lower-weight.</p>
        </div>
        <div style="background:#FFFDF7;border:1px solid #E8D9B6;border-radius:12px;padding:14px;">
            <p style="font-family:Inter,sans-serif;font-size:10px;color:#8A6A2F;text-transform:uppercase;letter-spacing:1px;margin:0 0 6px 0;font-weight:700;">Adaptive Architecture</p>
            <p style="font-family:Inter,sans-serif;font-size:12px;color:#374151;margin:0;line-height:1.55;"><strong>Verified:</strong> {adaptive_verified}/{adaptive_applicable}<br><strong>Strength earned:</strong> {adaptive_strength:.2f}<br><strong>Verified penalty:</strong> {adaptive_penalty:.2f}</p>
            <p style="font-family:Inter,sans-serif;font-size:9px;color:#6B7280;margin:6px 0 0 0;line-height:1.45;">Higher-value conversion, trust, policy, proof and completion checks selected from the observed journey + context, not an industry checklist.</p>
        </div>
    </div>

    {rescan_html}
    {confirmation_html}

    {foundation_notice}

    <div style="background:rgba(200,90,90,0.08); border:1px solid rgba(200,90,90,0.25); border-radius:12px; padding:20px; margin:16px 0; text-align:center;">
        <p style="font-family:Inter,sans-serif; font-size:11px; color:#C85A5A; text-transform:uppercase; letter-spacing:1.5px; margin:0 0 6px 0; font-weight:700;">MODELED COMMERCIAL EXPOSURE</p>
        <p style="font-family:Georgia,serif; font-size:28px; color:#C85A5A; margin:0; font-weight:700;">{revenue_exposure}</p>
        <p style="font-family:Inter,sans-serif; font-size:10px; color:#6B7280; margin:7px 0 0 0; line-height:1.45;">Scenario estimate from verified customer-journey issues and explicit economic assumptions; not measured accounting loss or guaranteed uplift.</p>
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
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#D1D5DB; margin:0 0 8px 0; line-height:1.5;">• <strong>Journey + Context Weighting:</strong> {html.escape(str(methodology.get('vertical_weighting','')))}</p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#D1D5DB; margin:0; line-height:1.5;">• <strong>Hygiene:</strong> {html.escape(str(methodology.get('hygiene_gatekeeping','')))}</p>
    </div>

    <h2 style="font-family:Georgia,serif; font-size:22px; color:#090B12; margin:32px 0 20px 0; font-weight:700;">🎯 {findings_count} Highest-Priority Revenue Findings & 3-Angle Fixes</h2>
    {leaks_html}
    {roadmap_html}

    <div style="background:#121621; color:#F2F0E8; border-radius:12px; padding:20px; margin:24px 0;">
        <h3 style="font-family:Georgia,serif; font-size:16px; color:#D8B66A; margin:0 0 12px 0;">📊 Full 50-Point Checkpoint Basis</h3>
        <p style="font-family:Inter,sans-serif; font-size:14px; margin:0 0 8px 0;">Verified: <strong>{summary.get('verified',0)}</strong> &nbsp;|&nbsp; Passed: <span style="color:#22C55E; font-weight:700;">{summary.get('passed',0)}</span> &nbsp;|&nbsp; Failed: <span style="color:#EF4444; font-weight:700;">{summary.get('failed',0)}</span></p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#A9A7A0; margin:0 0 5px 0;">Unknown: {summary.get('unknown',0)} &nbsp;|&nbsp; N/A: {summary.get('not_applicable',0)}</p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#D1D5DB; margin:8px 0 5px 0; line-height:1.5;"><strong>Verification Coverage:</strong> {coverage_note}</p>
        <p style="font-family:Inter,sans-serif; font-size:12px; color:#A9A7A0; margin:0;">Trust & Conversion: 15 checks | SEO & Technical: 20 checks | Content & E-E-A-T: 15 checks</p>
    </div>

    <div style="text-align:center; margin:28px 0 20px 0;"><a href="#" style="font-family:Inter,sans-serif; font-size:13px; color:#2563EB; text-decoration:none; font-weight:600;">Access Complete Raw Vault Telemetry Entry</a></div>

    <div style="border-top:1px solid #e0e0e0; margin-top:24px; padding-top:20px;"><p style="font-family:Inter,sans-serif; font-size:11px; color:#555555; line-height:1.6; margin:0;"><strong>DISCLAIMER & TERMS OF SALE:</strong> This diagnostic report reflects evidence available to the scanner at the recorded time. Unknown or inaccessible telemetry is not treated as a failure. Revenue exposure labels are model-based unless the business supplied validated traffic, conversion and transaction-value inputs. Maturity-band thresholds are advisory diagnostics only; they do not clamp the earned score and do not represent measured lost revenue. The Revenue Readiness Index evaluates observable website architecture only; product-market fit, demand, traffic quality, pricing, sales follow-up and offline operations are outside its scope. Results and performance improvements depend on correct implementation and later platform changes.</p></div>
</div>
</body>
</html>"""

    def _build_foundation_omissions_html(self, report: Dict[str, Any]) -> str:
        signal = report.get("foundation_omission_signal") if isinstance(report.get("foundation_omission_signal"), dict) else {}
        omissions = [x for x in (signal.get("omissions") or []) if isinstance(x, dict)]
        domain = html.escape(str(report.get("target_domain") or "Unknown"))
        cards: List[str] = []
        for index, item in enumerate(omissions, 1):
            title = html.escape(str(item.get("title") or item.get("check") or "Foundational omission"))
            level = html.escape(str(item.get("level") or "BASIC"))
            url = html.escape(str(item.get("observed_url") or report.get("target_domain") or ""))
            why = html.escape(str(item.get("why_it_matters") or ""))
            solution = html.escape(str(item.get("recommended_change") or ""))
            evidence = html.escape(str(item.get("evidence") or "Verified public checkpoint failure."))
            cards.append(
                '<section style="background:#FFFFFF;border:1px solid #D9D4CC;border-radius:14px;padding:20px;margin:0 0 18px 0;">'
                f'<div style="font:700 11px Inter,sans-serif;color:#9A3412;letter-spacing:1.2px;text-transform:uppercase;">{index:02d} — {level} FOUNDATIONAL OMISSION</div>'
                f'<h2 style="font:700 24px Georgia,serif;color:#1F2937;margin:8px 0 12px;">{title}</h2>'
                f'<p style="font:13px/1.6 Inter,sans-serif;color:#4B5563;"><strong>Observed page:</strong> {url}</p>'
                f'<p style="font:13px/1.6 Inter,sans-serif;color:#4B5563;"><strong>Why this matters:</strong> {why}</p>'
                f'<p style="font:13px/1.6 Inter,sans-serif;color:#111827;"><strong>Correct this:</strong> {solution}</p>'
                f'<p style="font:12px/1.55 Inter,sans-serif;color:#6B7280;"><strong>Evidence:</strong> {evidence}</p>'
                '</section>'
            )
        if not cards:
            cards.append('<p style="font:14px Inter,sans-serif;color:#4B5563;">No verified foundational omissions were detected in this scan.</p>')
        return (
            '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Trilloka Foundation Omissions — {domain}</title></head><body style="margin:0;background:#F4F1EB;">'
            '<main style="max-width:820px;margin:0 auto;padding:32px 18px 60px;">'
            '<div style="font:700 11px Inter,sans-serif;color:#9A3412;letter-spacing:1.5px;text-transform:uppercase;">TRILLOKA — FOUNDATION OMISSIONS</div>'
            '<h1 style="font:700 34px Georgia,serif;color:#111827;margin:8px 0 10px;">Basic website requirements detected as missing</h1>'
            '<p style="font:14px/1.7 Inter,sans-serif;color:#4B5563;margin:0 0 28px;">These items are intentionally separated from the main Revenue Readiness findings. They are basic implementation omissions, not automatically the largest financial leaks, and UNKNOWN evidence is never included here.</p>'
            + ''.join(cards) + '</main></body></html>'
        )

    def build_vault_rescan_comparison(self, target_domain: str, current_audit: Dict[str, Any]) -> Dict[str, Any]:
        """Compare a fresh audit with the newest prior Vault snapshot for the same public domain.

        This is a fallback when the protected scan cache has no previous result. Durability depends on
        VAULT_DIR using persistent storage; if no prior snapshot exists, the caller keeps baseline mode.
        """
        try:
            if not os.path.isdir(self.vault_dir):
                return {"status": "NO_VAULT_BASELINE", "has_previous_snapshot": False}
            sanitized = (target_domain or "unknown").replace("https://", "").replace("http://", "").replace("/", "_")
            candidates = []
            for name in os.listdir(self.vault_dir):
                if not name.startswith(sanitized + "_") or not name.endswith(".json"):
                    continue
                path = os.path.join(self.vault_dir, name)
                try:
                    candidates.append((os.path.getmtime(path), path))
                except OSError:
                    continue
            for _, path in sorted(candidates, reverse=True):
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        entry = json.load(handle)
                    previous = entry.get("admin_report") if isinstance(entry, dict) else {}
                    if not isinstance(previous, dict) or not previous:
                        continue
                    previous_score = previous.get("overall_health_score")
                    current_score = current_audit.get("overall_score")
                    if current_score is None:
                        current_score = current_audit.get("overall_health_score")
                    prev_ledger = [x for x in (previous.get("scoring_ledger") or []) if isinstance(x, dict)]
                    curr_ledger = [x for x in (current_audit.get("scoring_ledger") or []) if isinstance(x, dict)]
                    if prev_ledger:
                        prev_rules = {str(x.get("rule_key") or "") for x in prev_ledger if x.get("rule_key")}
                    else:
                        prev_rules = {str(x.get("rule_key") or "") for x in (previous.get("top_10_financial_leaks") or []) if isinstance(x, dict) and x.get("rule_key")}
                    if curr_ledger:
                        curr_rules = {str(x.get("rule_key") or "") for x in curr_ledger if x.get("rule_key")}
                    else:
                        packages = current_audit.get("tiered_remediation_packages") or {}
                        curr_rules = {str(x.get("rule_key") or "") for x in (packages.get("tier_10_arch10") or []) if isinstance(x, dict) and x.get("rule_key")}
                    prev_cp = {int(x.get("id")): str(x.get("status")) for x in (previous.get("full_50_checkpoint_basis") or []) if isinstance(x, dict) and x.get("id") is not None}
                    curr_cp = {int(x.get("id")): str(x.get("status")) for x in (current_audit.get("full_50_checkpoint_basis") or []) if isinstance(x, dict) and x.get("id") is not None}
                    improvements=[]; regressions=[]
                    for cp_id,before in prev_cp.items():
                        after=curr_cp.get(cp_id)
                        if before=="FAIL" and after=="PASS": improvements.append({"checkpoint_id":cp_id,"before":before,"after":after})
                        elif before=="PASS" and after=="FAIL": regressions.append({"checkpoint_id":cp_id,"before":before,"after":after})
                    delta=None
                    try:
                        if previous_score is not None and current_score is not None:
                            delta=round(float(current_score)-float(previous_score),1)
                    except Exception:
                        pass
                    previous_engine = previous.get("scanner_engine_version")
                    current_engine = current_audit.get("scanner_engine_version")
                    methodology_changed = bool(previous_engine and current_engine and previous_engine != current_engine)
                    return {
                        "status":"COMPARISON_AVAILABLE",
                        "has_previous_snapshot":True,
                        "source":"vault_archive",
                        "previous_vault_id":previous.get("vault_id"),
                        "score_before":previous_score,
                        "score_after":current_score,
                        "score_delta":delta,
                        "fixed_findings":sorted(prev_rules-curr_rules),
                        "new_findings":sorted(curr_rules-prev_rules),
                        "persistent_findings":sorted(prev_rules&curr_rules),
                        "checkpoint_improvements":improvements,
                        "checkpoint_regressions":regressions,
                        "previous_engine_version": previous_engine,
                        "current_engine_version": current_engine,
                        "methodology_changed": methodology_changed,
                        "comparison_confidence": "directional_only" if methodology_changed else "same_engine_comparison",
                        "comparison_basis": (
                            "The scanner version changed between Vault snapshots, so score/finding deltas may reflect methodology as well as website changes."
                            if methodology_changed
                            else "Previous Vault snapshot vs fresh scan using the same engine generation; architecture/evidence delta only, not measured revenue delta."
                        ),
                    }
                except Exception:
                    continue
        except Exception as exc:
            return {"status": "VAULT_COMPARISON_UNAVAILABLE", "has_previous_snapshot": False, "error": str(exc)[:180]}
        return {"status": "NO_VAULT_BASELINE", "has_previous_snapshot": False}

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
            "evidence_receipts": (admin_report or {}).get("evidence_receipts", []),
            "high_impact_confirmation": (admin_report or {}).get("high_impact_confirmation", {}),
            "rescan_comparison": (admin_report or {}).get("rescan_comparison", {}),
        }
        with open(filename, "w", encoding="utf-8") as handle:
            json.dump(vault_entry, handle, indent=2, ensure_ascii=False, default=str)

        # Also persist the customer-readable action report plus a separate foundation-omissions page.
        html_filename = f"{self.vault_dir}/{sanitized}_{timestamp}_report.html"
        foundation_basename = f"{sanitized}_{timestamp}_foundation_omissions.html"
        foundation_filename = f"{self.vault_dir}/{foundation_basename}"
        report_for_archive = dict(admin_report or {})
        report_for_archive["foundation_omission_report_filename"] = foundation_basename
        with open(html_filename, "w", encoding="utf-8") as handle:
            handle.write(self._build_email_html(report_for_archive))
        with open(foundation_filename, "w", encoding="utf-8") as handle:
            handle.write(self._build_foundation_omissions_html(report_for_archive))

        print(f"[Vault] Archived scan snapshot to {filename}")
        print(f"[Vault] Archived customer-readable report to {html_filename}")
        print(f"[Vault] Archived foundation-omissions page to {foundation_filename}")
        return filename
