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
from architecture_model import BUSINESS_TYPE_LABELS, JOURNEY_LABELS, CONTEXT_LABELS


class ReportGenerator:
    def __init__(self):
        self.resend_api_key = os.environ.get("RESEND_API_KEY", "")
        self.from_email = os.environ.get("FROM_EMAIL", "alerts@trilloka.com")
        self.admin_email = (os.environ.get("TRILLOKA_OWNER_EMAIL") or os.environ.get("TRILLOKA_REPORT_EMAIL") or "onlyonearpit@gmail.com").strip() or "onlyonearpit@gmail.com"
        self.vault_dir = os.environ.get("VAULT_DIR", "./vault_archives")

    def generate_admin_master_report(self, audit_data: Dict[str, Any], scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create the V7.3.1 plain-language, evidence-first master report.

        Verified leaks are never padded to a fixed count. Unknowns, strengths and optional future
        optimization ideas are stored in separate sections so a passing checkpoint cannot be
        mistaken for a revenue problem.
        """
        audit = audit_data or {}
        scan = scan_data or {}
        business_profile = (
            audit.get("architecture_profile") or audit.get("business_profile")
            or scan.get("architecture_profile") or scan.get("business_profile")
            or {"business_type": audit.get("business_type", "general"), "journey_model": audit.get("journey_model", "general")}
        )
        if not isinstance(business_profile, dict):
            business_profile = {}

        checkpoints = audit.get("full_50_checkpoint_basis") or build_50_checkpoints(scan, audit)
        summary = audit.get("checkpoint_summary") or checkpoint_summary(checkpoints)

        packages = audit.get("tiered_remediation_packages") or {}
        # Architect/master report shows up to the genuine Top 10 family-consolidated verified findings.
        # It does NOT manufacture ten items when the site has fewer verified problems.
        leaks = packages.get("tier_10_arch10") or packages.get("all_scoring_leaks") or []
        ordered_leaks = [item for item in leaks if isinstance(item, dict)]

        verified_findings: List[Dict[str, Any]] = []
        for leak in ordered_leaks[:10]:
            severity_factor = leak.get("severity_factor")
            item = {
                **leak,
                "finding_type": "VERIFIED_LEAK",
                "report_class": "VERIFIED_REVENUE_FINDING",
                "severity_label": self._get_severity_label(severity_factor),
                "solutions_3_angles": self._build_3_angle_solutions(
                    str(leak.get("rule_key") or ""), leak, scan, business_profile
                ),
            }
            verified_findings.append(self._enrich_plain_language_finding(item, scan, business_profile))

        verification_priorities = self._build_verification_priorities(checkpoints)
        verified_strengths = self._build_verified_strengths(checkpoints)
        future_optimizations = self._build_future_optimizations(scan, checkpoints, business_profile)
        at_a_glance = self._build_at_a_glance(
            verified_findings, verification_priorities, verified_strengths, future_optimizations
        )

        overall = audit.get("overall_health_score")
        if overall is None:
            overall = audit.get("overall_score")
        revenue_display = (audit.get("revenue_leak") or {}).get("est_annual_revenue_leak") or "Not measured"
        business_type = str(audit.get("business_type") or business_profile.get("business_type") or "general")
        business_type_label = str(
            audit.get("business_type_label") or business_profile.get("business_type_label")
            or BUSINESS_TYPE_LABELS.get(business_type.lower(), business_type.replace("_", " ").title())
        )
        journey_model = str(business_profile.get("journey_model") or audit.get("journey_model") or "general")

        return {
            "report_type": "ADMIN_LEAD_ALERT_V7_3_1",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "target_domain": audit.get("target_domain", scan.get("domain", "Unknown")),
            "business_type": business_type,
            "business_type_label": business_type_label,
            "business_type_confidence": business_profile.get("business_type_confidence"),
            "business_profile": business_profile,
            "architecture_profile": business_profile,
            "journey_model": journey_model,
            "journey_label": str(business_profile.get("journey_label") or JOURNEY_LABELS.get(journey_model, "General / Unresolved Journey")),
            "secondary_journeys": list(business_profile.get("secondary_journeys") or []),
            "public_journey_map": {
                "entry": "Visitor arrives from search, ads, social, referral or direct navigation.",
                "path": str(business_profile.get("journey_label") or JOURNEY_LABELS.get(journey_model, "Customer journey")),
                "primary_action": str(business_profile.get("primary_conversion") or "Primary customer action"),
                "decision_points": ["clarity", "trust", "proof", "friction", "technical reliability"],
                "outcome": "The business outcome the public website is trying to create.",
                "note": "Public-safe journey explanation only; proprietary inference signals and exact weighting remain private.",
            },
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
                if overall is not None else {
                    "level": "SCORE UNAVAILABLE",
                    "impact_summary": "The scoring engine did not supply an overall score.",
                    "severity_behavior": "No synthetic zero was substituted.",
                }
            ),
            "at_a_glance": at_a_glance,
            "verified_revenue_findings": verified_findings,
            "verification_priorities": verification_priorities,
            "verified_strengths": verified_strengths,
            "future_optimizations": future_optimizations,
            # Backward-compatible aliases: actual verified findings only, never padded with passes/unknowns.
            "top_10_financial_leaks": verified_findings,
            "top_6_financial_leaks": verified_findings[:6],
            "verified_financial_leak_count": len(verified_findings),
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
            "commercial_architecture_diagnostics": scan.get("commercial_architecture_diagnostics") or {},
            "public_content_hygiene": scan.get("public_content_hygiene") or {},
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
    def _priority_for_finding(finding: Dict[str, Any]) -> str:
        """Business priority is distinct from raw score loss or intrinsic severity."""
        try:
            loss = float(finding.get("final_score_loss") or finding.get("severity_score") or 0.0)
        except (TypeError, ValueError):
            loss = 0.0
        try:
            severity = float(finding.get("severity_factor") or 0.0)
        except (TypeError, ValueError):
            severity = 0.0
        try:
            commercial = float(finding.get("commercial_priority") or finding.get("commercial_priority_score") or 0.0)
        except (TypeError, ValueError):
            commercial = 0.0
        if loss >= 4.0 or (commercial >= 5.0 and severity >= 0.65):
            return "CRITICAL"
        if loss >= 2.0 or commercial >= 4.25 or severity >= 0.75:
            return "HIGH"
        if loss >= 0.75 or commercial >= 3.0 or severity >= 0.40:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _finding_url(finding: Dict[str, Any], scan: Dict[str, Any]) -> str:
        receipt = finding.get("evidence_receipt") if isinstance(finding.get("evidence_receipt"), dict) else {}
        evidence = finding.get("evidence") if isinstance(finding.get("evidence"), dict) else {}
        for candidate in (
            receipt.get("url"), evidence.get("url"), evidence.get("observed_url"),
            finding.get("url"), scan.get("final_url"), scan.get("url"), scan.get("domain"),
        ):
            if candidate:
                return str(candidate)
        urls = evidence.get("affected_urls") if isinstance(evidence.get("affected_urls"), list) else []
        return str(urls[0]) if urls else "Site-wide / inspected customer journey"

    @staticmethod
    def _financial_mechanism_for_family(family: str, rule_key: str) -> str:
        key = str(rule_key or "")
        fam = str(family or "")
        if key in {"checkout_cost_transparency", "guest_checkout_barrier", "checkout_complexity", "delivery_expectation_clarity", "shipping_info_discoverability", "return_policy_discoverability"}:
            return "Checkout or purchase abandonment: customers who are already close to paying may hesitate, postpone or leave before completing the order."
        if fam in {"conversion_execution", "mobile_direct_action"} or key in {"primary_conversion_path", "conversion_path_error", "form_architecture", "lead_form_friction"}:
            return "Lost conversion opportunity: fewer visitors may complete the intended call, form, booking, quote, trial, donation, application or purchase path."
        if fam in {"trust_proof", "trust_policy", "trust_identity", "trust_local"} or key in {"proof_placement_gap", "policy_content_consistency"}:
            return "Lower decision confidence: uncertainty can reduce the share of qualified visitors who continue to the next commercial step and can increase support questions or hesitation."
        if fam == "performance" or key in {"core_web_vitals", "mobile_lab_performance", "pagespeed_below_90"}:
            return "Experience abandonment: slower or unstable pages can cause visitors to leave before reaching or completing the commercial action."
        if fam == "measurement" or "telemetry" in key:
            return "Measurement inefficiency: the business may spend on traffic or changes without reliably knowing which channels and journey steps create qualified outcomes."
        if fam in {"search_snippet", "search_structure", "crawlability"}:
            return "Search acquisition efficiency: weaker search presentation or crawlability can reduce qualified organic visibility or clicks, although the direct revenue effect is usually indirect."
        if fam == "commercial_consistency" or key == "cross_page_consistency":
            return "Commercial uncertainty: conflicting promises can create hesitation, extra support contact, cancellations or disputes and can weaken completion rates."
        if fam in {"content_quality_control", "content_distinctiveness"} or key == "public_unfinished_content":
            return "Credibility risk: customers or search engines discovering unfinished or contradictory public content can reduce trust and progression through the site."
        return "Commercial friction: this condition can make the relevant customer decision harder or less certain, which may reduce progression or increase avoidable operating effort."

    def _enrich_plain_language_finding(
        self,
        finding: Dict[str, Any],
        scan: Dict[str, Any],
        business_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Turn one evidence-backed scoring record into a customer-readable explanation."""
        item = dict(finding or {})
        key = str(item.get("rule_key") or "")
        family = str(item.get("family") or "")
        title = str(item.get("leak_name") or item.get("title") or key.replace("_", " ").title() or "Revenue finding")
        impact = str(item.get("impact_summary") or item.get("reason") or "A verified condition may create friction in the website's commercial architecture.")
        url = self._finding_url(item, scan)
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        receipt = item.get("evidence_receipt") if isinstance(item.get("evidence_receipt"), dict) else {}

        templates: Dict[str, Dict[str, str]] = {
            "delivery_expectation_clarity": {
                "problem": "Customers may reach the buying stage without a clear, concrete expectation for when their order should arrive.",
                "why": "Delivery timing is part of the purchase decision. A buyer who cannot tell when the product will arrive has one more reason to delay or abandon the order.",
                "action": "Show a consistent delivery date or delivery window at the relevant product/cart/checkout decision point and keep it synchronized with fulfilment reality.",
            },
            "shipping_info_discoverability": {
                "problem": "Important shipping information is not easy enough to find before a customer commits to the purchase.",
                "why": "Customers want to understand fulfilment conditions before paying. Buried shipping information increases uncertainty late in the journey.",
                "action": "Surface the most important shipping terms before commitment and link clearly to the full policy.",
            },
            "return_policy_discoverability": {
                "problem": "Customers may have to search too hard to understand the return/refund rules before buying.",
                "why": "Return uncertainty increases perceived purchase risk, especially for considered or unfamiliar purchases.",
                "action": "Make the applicable return/refund promise clear near the purchase decision and keep the detailed policy easy to reach.",
            },
            "proof_placement_gap": {
                "problem": "Trust or customer proof exists on the site, but it is weak or absent near an important decision point.",
                "why": "Proof is most useful when the visitor is deciding whether to act. Evidence buried on another page cannot reassure every visitor at the moment of hesitation.",
                "action": "Bring the strongest relevant and verifiable proof closer to the high-consideration CTA without inventing or overstating outcomes.",
            },
            "cross_page_consistency": {
                "problem": "Important commercial information is not fully consistent across the pages a customer may use to make a decision.",
                "why": "Conflicting prices, delivery promises, refund periods, guarantees or other terms force customers to decide which statement to trust.",
                "action": "Create one authoritative source for the affected commercial information and make all relevant pages use the same current value or policy wording.",
            },
            "public_unfinished_content": {
                "problem": "The public site exposes content that appears unfinished, internal, test-oriented or placeholder-like.",
                "why": "A polished main page can still lose credibility if a customer or search engine discovers a public page that looks accidental or incomplete.",
                "action": "Finish the page, remove it from public access, or apply the appropriate noindex/unpublish controls if it is not customer-facing.",
            },
            "policy_content_consistency": {
                "problem": "A public policy contains wording that appears inconsistent, stale, placeholder-like or mismatched with the observed website/business model.",
                "why": "Policies are trust documents. Inconsistent wording can make customers uncertain about terms or data handling even when the policy link itself exists.",
                "action": "Review the policy against current operations, tools and customer journeys; update inaccurate or legacy wording and obtain qualified legal review where appropriate. Trilloka is not making a legal-compliance determination.",
            },
            "primary_conversion_path": {
                "problem": "The website does not expose a sufficiently clear or usable primary action for the business's intended customer journey.",
                "why": "Visitors can understand the offer and still fail to become leads or customers if the next step is unclear, hidden or unsuitable for the business type.",
                "action": "Make the highest-intent action clear, usable and appropriate to this business type and journey, with secondary actions kept subordinate.",
            },
            "conversion_path_error": {
                "problem": "A key conversion path showed a verified technical or visible failure.",
                "why": "A broken booking, form, checkout, external provider or CTA can block an otherwise willing customer at the point of action.",
                "action": "Repair the exact failed destination or interaction, provide a sensible fallback, and re-test the same path after deployment.",
            },
            "form_architecture": {
                "problem": "The form architecture is incomplete, broken or creates avoidable friction in a journey where forms matter.",
                "why": "A form is often the handoff from website interest to a real lead, booking, application or sale. Friction or technical failure directly weakens that handoff.",
                "action": "Repair the verified form problem, collect only information needed at that stage, and provide visible success/error states and response expectations.",
            },
            "lead_form_friction": {
                "problem": "The lead or enquiry form asks for more effort than appears necessary at this stage of the journey.",
                "why": "Each high-effort field increases the amount of work a prospect must do before receiving value or speaking with the business.",
                "action": "Reduce or defer non-essential fields, explain sensitive/high-effort questions, and preserve the information the business genuinely needs to qualify the lead.",
            },
            "unsecured_ssl": {
                "problem": "The site is not providing a fully verified secure HTTPS foundation.",
                "why": "Browser security warnings or insecure transmission can immediately undermine trust and can compromise forms or transactions.",
                "action": "Repair TLS/certificate and redirect configuration, then verify all important pages and assets load securely.",
            },
            "measurement_telemetry": {
                "problem": "The scanner could not verify a dependable measurement layer for key website actions.",
                "why": "Without trustworthy measurement, the business may not know which campaigns, pages or changes actually produce qualified outcomes.",
                "action": "First verify whether private/server-side measurement already exists; if not, implement appropriate analytics and validate the important conversion events with suitable consent handling.",
            },
            "b2b_pricing_transparency": {
                "problem": "Pricing expectations are not sufficiently clear for a considered/demo-led buying journey.",
                "why": "B2B pricing does not always need to be fully public, but visitors still need enough information to understand fit, scale or the reason a quote/demo is required.",
                "action": "Provide an appropriate pricing frame—exact price, starting point, package logic or a clear explanation of what determines the quote.",
            },
        }
        tpl = templates.get(key, {})
        if family == "performance" and not tpl:
            tpl = {
                "problem": "Measured page performance is weaker than the readiness threshold on a commercially relevant part of the site.",
                "why": "Slow loading, delayed interaction or layout movement makes it harder for visitors to consume information and complete the next step.",
                "action": "Use the captured performance evidence to fix the measured bottleneck and re-test the same page rather than applying generic speed changes blindly.",
            }
        if family == "trust_proof" and not tpl:
            tpl = {
                "problem": "The inspected customer journey does not expose enough relevant proof or trust evidence for the decision being asked of the visitor.",
                "why": "Visitors need reasons to believe the business, offer or outcome before committing money, personal information or time.",
                "action": "Expose genuine, relevant and current proof close to the decision it supports, with an authoritative source where practical.",
            }
        if family == "search_snippet" and not tpl:
            tpl = {
                "problem": "The page's search-result metadata can be clearer or more complete.",
                "why": "Search snippets help qualified searchers decide whether the result matches their need, although search engines may rewrite them.",
                "action": "Improve the metadata naturally for the page's real intent; treat length ranges as Trilloka readability heuristics, not hard ranking rules.",
            }

        plain_problem = tpl.get("problem") or impact
        observed = impact
        if evidence:
            # Keep a short human-readable summary while preserving the full receipt separately.
            interesting = {k: v for k, v in evidence.items() if k not in {"html", "page_text", "raw"} and v not in (None, "", [], {})}
            if interesting:
                observed = f"{impact} Evidence captured: {json.dumps(interesting, ensure_ascii=False, default=str)[:700]}."
        why = tpl.get("why") or "This matters because the condition occurs in, or supports, a customer decision path rather than being treated as an isolated technical checkbox."
        action = tpl.get("action") or "Correct the verified condition at the affected page or journey stage, then re-scan the same path to confirm the evidence changed."
        priority = self._priority_for_finding(item)
        effort = "LOW" if key in {"meta_description_length", "meta_description_missing", "title_length", "diluted_h1", "public_unfinished_content"} else ("HIGH" if key in {"conversion_path_error", "core_web_vitals", "mobile_lab_performance"} else "MEDIUM")
        financial = self._financial_mechanism_for_family(family, key)

        item.update({
            "plain_problem": plain_problem,
            "what_we_found": observed,
            "where_it_happens": url,
            "why_it_matters": why,
            "financial_effect": financial,
            "financial_mechanism": financial,
            "what_should_be_done": action,
            "priority": priority,
            "implementation_effort": effort,
            "evidence_receipt": receipt or item.get("evidence_receipt") or {
                "url": url,
                "observed": evidence or item.get("observed") or item.get("impact_summary"),
                "method": item.get("source") or "Trilloka evidence-weighted diagnostic",
                "confidence": item.get("confidence") or "unknown",
            },
        })
        return item

    @staticmethod
    def _build_verification_priorities(checkpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for cp in checkpoints or []:
            if not isinstance(cp, dict) or str(cp.get("status") or "").upper() != UNKNOWN:
                continue
            name = str(cp.get("check") or f"Checkpoint {cp.get('id')}")
            note = str(cp.get("customer_note") or cp.get("reason") or "The scanner could not independently verify this signal from the available public evidence.")
            out.append({
                "checkpoint_id": cp.get("id"),
                "title": name,
                "finding": name,
                "type": "VERIFICATION_REQUIRED",
                "priority": "VERIFY",
                "simple_explanation": note,
                "confidence": "unknown",
                "where": "Public website evidence",
                "evidence": cp.get("evidence"),
                "unknown_reason_code": cp.get("unknown_reason_code"),
                "score_loss": 0.0,
                "note": "UNKNOWN is not FAIL and creates no direct score deduction.",
            })
        return out

    @staticmethod
    def _build_verified_strengths(checkpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for cp in checkpoints or []:
            if not isinstance(cp, dict) or str(cp.get("status") or "").upper() != PASS:
                continue
            name = str(cp.get("check") or f"Checkpoint {cp.get('id')}")
            out.append({
                "checkpoint_id": cp.get("id"),
                "title": name,
                "finding": name,
                "type": "VERIFIED_STRENGTH",
                "priority": "STRENGTH",
                "simple_explanation": f"The scanner found positive evidence that '{name}' is working at the minimum verified readiness level.",
                "confidence": "high",
                "where": "Inspected public evidence",
                "evidence": cp.get("evidence"),
                "preserve": "Preserve the working implementation and re-check it after material site changes.",
            })
        return out

    @staticmethod
    def _build_future_optimizations(
        scan: Dict[str, Any], checkpoints: List[Dict[str, Any]], business_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        diagnostics = scan.get("commercial_architecture_diagnostics") if isinstance(scan.get("commercial_architecture_diagnostics"), dict) else {}
        cta = diagnostics.get("cta_competition") if isinstance(diagnostics.get("cta_competition"), dict) else {}
        if cta.get("detected"):
            out.append({
                "title": "Review Competing Calls to Action",
                "finding": "Review Competing Calls to Action",
                "type": "FUTURE_OPTIMIZATION",
                "priority": "OPTIONAL",
                "simple_explanation": "The inspected page exposes several similarly prominent actions. This is not automatically a failure, but analytics or user testing can verify whether the choices compete with the primary journey.",
                "confidence": str(cta.get("confidence") or "medium"),
                "where": str(cta.get("url") or scan.get("final_url") or scan.get("domain") or "Primary journey"),
            })
        # A small set of passed advanced checks can be monitored without being relabelled as defects.
        monitor_ids = {21, 29, 44, 47}
        for cp in checkpoints or []:
            if not isinstance(cp, dict) or str(cp.get("status") or "").upper() != PASS or int(cp.get("id") or 0) not in monitor_ids:
                continue
            name = str(cp.get("check") or "Verified capability")
            out.append({
                "title": f"Preserve & Monitor — {name}",
                "finding": f"Preserve & Monitor — {name}",
                "type": "FUTURE_OPTIMIZATION",
                "priority": "OPTIONAL",
                "simple_explanation": "This already passed. Future optimization should be driven by real analytics or a stronger benchmark, not by treating the current implementation as broken.",
                "confidence": "high",
                "where": "Relevant public pages",
            })
        return out

    @staticmethod
    def _build_at_a_glance(
        findings: List[Dict[str, Any]],
        verification: List[Dict[str, Any]],
        strengths: List[Dict[str, Any]],
        optimizations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in findings or []:
            rows.append({
                "priority": item.get("priority") or "MEDIUM",
                "finding": item.get("leak_name") or item.get("title"),
                "type": "WHERE CUSTOMERS MAY BE LOST",
                "where": item.get("where_it_happens") or "Relevant customer journey",
                "simple_explanation": item.get("plain_problem") or item.get("impact_summary"),
                "confidence": item.get("confidence") or (item.get("evidence_receipt") or {}).get("confidence") or "unknown",
            })
        for source, type_label in ((verification, "VERIFICATION REQUIRED"), (strengths, "VERIFIED STRENGTH"), (optimizations, "FUTURE OPTIMIZATION")):
            for item in source or []:
                rows.append({
                    "priority": item.get("priority") or ("VERIFY" if type_label.startswith("VERIFICATION") else "STRENGTH"),
                    "finding": item.get("finding") or item.get("title"),
                    "type": type_label,
                    "where": item.get("where") or "Relevant public evidence",
                    "simple_explanation": item.get("simple_explanation") or "",
                    "confidence": item.get("confidence") or "unknown",
                })
        return rows

    @staticmethod
    def _get_severity_label(severity_factor: Optional[float]) -> str:
        if severity_factor is None:
            return "SEVERITY UNKNOWN"
        factor = max(0.0, min(1.0, float(severity_factor)))
        if factor >= 0.85:
            return "CRITICAL CUSTOMER-LOSS RISK"
        if factor >= 0.65:
            return "HIGH CUSTOMER-LOSS RISK"
        if factor >= 0.40:
            return "MODERATE FRICTION"
        if factor > 0.0:
            return "MINOR OPTIMIZATION"
        return "OPTIMIZED"

    @staticmethod
    def _build_scoring_methodology_explanation(audit_data: Dict[str, Any]) -> Dict[str, str]:
        profile = audit_data.get("architecture_profile") or audit_data.get("business_profile") or {}
        journey = str(profile.get("journey_label") or profile.get("journey_model") or "General / Unresolved Journey")
        business = str(profile.get("business_type_label") or audit_data.get("business_type_label") or profile.get("business_type") or audit_data.get("business_type") or "General")
        contexts = ", ".join(str(x) for x in (profile.get("context_labels") or [])) or "No special context tags verified"
        return {
            "core_philosophy": "Trilloka measures observable website Revenue Readiness, not literal conversion percentage, product-market fit, demand, sales-team performance or actual revenue. Readiness is earned across three unequal layers—Foundation, Revenue/User Architecture and Elite Architecture—while verified findings retain separate score impact, severity and evidence confidence.",
            "graded_continuum": "Every scored issue is scaled by implementation severity, evidence confidence, business-type importance and journey/context relevance. Unknown telemetry creates no failure or deduction. Severe deductions require independent confirmation or corroboration.",
            "architecture_model": f"Business type: {business}. Primary customer journey: {journey}. Context tags: {contexts}. Business type changes the importance of relevant checks, while observed website actions determine the actual journey and context obligations.",
            "two_layer_model": "Three earned canonical layers are used: Common Foundation (22 points), Revenue/User Architecture (60 points), and Elite Architecture (18 points). The 60-point Revenue/User layer is split into fixed conversion-execution, trust/decision-support, measurement/policy and supporting-experience pillars so low-value content/SEO passes cannot compensate for a weak primary customer path. Elite points require strong verified core architecture first. The canonical 0–100 strength is then mapped monotonically onto the stricter public 0–90 commercial-readiness blueprint; this is not a percentile curve or forced distribution.",
            "vertical_weighting": "Business Type + Journey + Context weighting work together. Business type defines the commercial importance of relevant evidence, journey identifies where value is created, and context adds obligations such as local, regulated, commerce, enterprise, recurring or sensitive-data trust. The same technical condition can therefore carry different importance on different businesses without becoming a rigid checklist.",
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
            return {"level":"NEAR-PERFECT VERIFIED OBSERVABLE ARCHITECTURE (80–90)","impact_summary":"The observable customer journey, trust, measurement and supporting architecture are near-complete, with almost no verified customer-path weakness. The score still does not claim 100% visitor conversion or guaranteed revenue performance.","severity_behavior":"This band is reserved for near-perfect canonical 22/60/18 strength after the transparent 0–90 blueprint calibration; ordinary technical hygiene cannot reach it."}
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

        if rule_key == "proof_placement_gap":
            return {
                "technical": "Surface the existing verified proof component on the relevant decision page or section without creating duplicate, stale or unverifiable review widgets.",
                "cro_ux": "Place the strongest relevant proof close to the high-consideration CTA so the visitor sees reassurance at the moment of decision, not only on a separate testimonials page.",
                "systems": "Define an authoritative proof source, ownership and refresh cadence so testimonials, reviews, credentials or case studies remain genuine and current.",
                "why_recommend": "The scanner found proof somewhere on the site but weaker proof at an important decision point; the recommendation improves placement rather than falsely claiming proof is absent everywhere.",
                "cadence_title": "Weeks 1–2",
                "cadence_text": "Move or surface the strongest existing proof first, verify the decision-point experience, then measure progression before adding more proof volume.",
            }

        if rule_key == "cross_page_consistency":
            return {
                "technical": "Centralize the affected commercial value or policy in one source of truth and make templates/components read the same current value wherever practical.",
                "cro_ux": "Use one clear promise across the pages a customer compares so they do not have to decide which price, delivery window, refund term or guarantee is correct.",
                "systems": "Add publishing/QA checks for material commercial fields and assign ownership so policy, fulfilment and offer changes are propagated across all relevant pages.",
                "why_recommend": "The recommendation is based on conflicting or materially inconsistent public statements found across the inspected site, not on a generic content preference.",
                "cadence_title": "Weeks 1–2",
                "cadence_text": "Resolve the highest-commercial-impact inconsistency first, publish one authoritative value, then re-scan the affected pages together.",
            }

        if rule_key == "public_unfinished_content":
            return {
                "technical": "Finish, unpublish, restrict or noindex the verified test/internal/placeholder page according to its real intended audience; remove it from public navigation and sitemap exposure where appropriate.",
                "cro_ux": "Prevent customers from encountering unfinished or internal-looking content that can make an otherwise credible website appear accidental or unreliable.",
                "systems": "Add a release checklist or CMS guard so draft/test/internal pages cannot become publicly discoverable without an explicit publication decision.",
                "why_recommend": "The scanner detected public content with unfinished, placeholder or internal-use signals. This is a quality-control finding, not an assumption about the rest of the website.",
                "cadence_title": "Immediate / Week 1",
                "cadence_text": "Remove accidental public exposure first, then verify sitemap/internal-link cleanup and rescan the known URL.",
            }

        if rule_key == "policy_content_consistency":
            return {
                "technical": "Update the public policy content so names, processors/tools, addresses, business model references and linked terms reflect the current operation; preserve version/date controls where used.",
                "cro_ux": "Use clear current wording around the customer decision or data-entry point so visitors understand what the policy means without reading contradictory legacy text.",
                "systems": "Trigger policy review when data processors, forms, fulfilment, subscriptions, locations or business terms materially change, and obtain qualified legal review where appropriate.",
                "why_recommend": "The scanner found wording that appears inconsistent with the observed site or with other public policy text. Trilloka is flagging a review need, not making a legal-compliance determination.",
                "cadence_title": "Review priority",
                "cadence_text": "Confirm the current operational facts with the business owner, update the public wording, obtain appropriate legal review, and re-scan for internal consistency.",
            }

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
        """Render the V7.3.1 plain-language report used in email and the HTML attachment."""
        report = report or {}

        def esc(value: Any) -> str:
            return html.escape(str(value if value is not None else ""))

        def fmt_num(value: Any, digits: int = 1, default: str = "N/A") -> str:
            try:
                return f"{float(value):.{digits}f}"
            except (TypeError, ValueError):
                return default

        def badge(text: str, tone: str = "neutral") -> str:
            tones = {
                "high": ("#FEE2E2", "#991B1B"), "critical": ("#FEE2E2", "#991B1B"),
                "medium": ("#FEF3C7", "#92400E"), "low": ("#E0F2FE", "#075985"),
                "verify": ("#F3E8FF", "#6B21A8"), "strength": ("#DCFCE7", "#166534"),
                "optional": ("#EDE9FE", "#5B21B6"), "neutral": ("#F3F4F6", "#374151"),
            }
            bg, fg = tones.get(str(tone).lower(), tones["neutral"])
            return f'<span style="display:inline-block;background:{bg};color:{fg};font:700 10px Inter,sans-serif;padding:4px 8px;border-radius:999px;letter-spacing:.4px;">{esc(text)}</span>'

        domain = esc(report.get("target_domain") or "Unknown")
        score = report.get("overall_health_score")
        score_text = fmt_num(score, 1)
        rating = esc(report.get("score_rating") or "")
        vault_id = esc(report.get("vault_id") or "")
        business_type = esc(report.get("business_type_label") or report.get("business_type") or "General / unresolved")
        bt_conf = report.get("business_type_confidence")
        if bt_conf is None:
            bt_conf = (report.get("business_profile") or {}).get("business_type_confidence")
        bt_conf_text = "N/A" if bt_conf is None else f"{float(bt_conf)*100:.0f}%"
        journey = esc(report.get("journey_label") or report.get("journey_model") or "General / unresolved")
        profile = report.get("business_profile") if isinstance(report.get("business_profile"), dict) else {}
        journey_conf = profile.get("confidence")
        journey_conf_text = "N/A" if journey_conf is None else f"{float(journey_conf)*100:.0f}%"
        secondaries = report.get("secondary_journeys") or []
        secondary_text = esc(", ".join(
            str((x or {}).get("label") or (x or {}).get("journey_label") or (x or {}).get("journey_model") or x)
            if isinstance(x, dict) else str(x) for x in secondaries
        ) or "None strongly verified")
        context_text = esc(", ".join(str(x) for x in (report.get("context_labels") or [])) or "No special context tags verified")
        cms = esc(report.get("cms_platform") or "Not confidently identified")
        ai_pct = report.get("ai_spectrum_pct")
        ai_display = "Unknown" if ai_pct is None else f"{float(ai_pct):.1f}/100"
        evidence_conf = report.get("evidence_confidence") if isinstance(report.get("evidence_confidence"), dict) else {}
        evidence_text = f"{esc(evidence_conf.get('level') or 'UNKNOWN')} ({fmt_num(evidence_conf.get('score'),1)}/100)"
        scope = esc(report.get("score_scope") or "Observable website Revenue Readiness only; not product-market fit, demand, traffic quality, pricing, sales execution or actual revenue.")
        revenue = esc(report.get("estimated_revenue_leak") or "Not measured")
        methodology = report.get("scoring_methodology") if isinstance(report.get("scoring_methodology"), dict) else {}
        score_impact = report.get("score_level_impact") if isinstance(report.get("score_level_impact"), dict) else {}
        summary = report.get("checkpoint_summary") or self._checkpoint_summary(report.get("full_50_checkpoint_basis") or [])
        coverage_note = esc(report.get("verification_coverage_note") or self._verification_coverage_note(summary))
        formula = report.get("score_formula") if isinstance(report.get("score_formula"), dict) else {}

        glance_rows = []
        for row in report.get("at_a_glance") or []:
            if not isinstance(row, dict):
                continue
            priority = str(row.get("priority") or "")
            tone = "strength" if priority == "STRENGTH" else ("verify" if priority == "VERIFY" else ("optional" if priority == "OPTIONAL" else priority.lower()))
            glance_rows.append(
                '<tr>'
                f'<td style="padding:9px;border-bottom:1px solid #E5E7EB;vertical-align:top;">{badge(priority or "—", tone)}</td>'
                f'<td style="padding:9px;border-bottom:1px solid #E5E7EB;vertical-align:top;font:600 12px Inter,sans-serif;color:#111827;">{esc(row.get("finding"))}</td>'
                f'<td style="padding:9px;border-bottom:1px solid #E5E7EB;vertical-align:top;font:11px Inter,sans-serif;color:#4B5563;">{esc(row.get("type"))}</td>'
                f'<td style="padding:9px;border-bottom:1px solid #E5E7EB;vertical-align:top;font:11px Inter,sans-serif;color:#4B5563;">{esc(row.get("where"))}</td>'
                f'<td style="padding:9px;border-bottom:1px solid #E5E7EB;vertical-align:top;font:12px/1.5 Inter,sans-serif;color:#374151;">{esc(row.get("simple_explanation"))}</td>'
                f'<td style="padding:9px;border-bottom:1px solid #E5E7EB;vertical-align:top;font:11px Inter,sans-serif;color:#4B5563;">{esc(row.get("confidence"))}</td>'
                '</tr>'
            )
        at_glance_html = (
            '<table role="presentation" style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;">'
            '<thead><tr style="background:#111827;color:#fff;">'
            '<th style="padding:10px;text-align:left;font:700 10px Inter,sans-serif;">PRIORITY</th>'
            '<th style="padding:10px;text-align:left;font:700 10px Inter,sans-serif;">FINDING</th>'
            '<th style="padding:10px;text-align:left;font:700 10px Inter,sans-serif;">TYPE</th>'
            '<th style="padding:10px;text-align:left;font:700 10px Inter,sans-serif;">WHERE</th>'
            '<th style="padding:10px;text-align:left;font:700 10px Inter,sans-serif;">SIMPLE EXPLANATION</th>'
            '<th style="padding:10px;text-align:left;font:700 10px Inter,sans-serif;">CONFIDENCE</th>'
            '</tr></thead><tbody>' + ''.join(glance_rows) + '</tbody></table>'
        ) if glance_rows else '<p style="font:13px Inter,sans-serif;color:#6B7280;">No material summary rows were available.</p>'

        f_score = formula.get("foundation_layer_score")
        f_max = formula.get("foundation_layer_max")
        r_score = formula.get("revenue_user_architecture_score")
        r_max = formula.get("revenue_user_architecture_max")
        e_score = formula.get("elite_architecture_score")
        e_max = formula.get("elite_architecture_max")
        canonical = formula.get("canonical_three_layer_score")
        penalty = formula.get("total_final_penalty")
        if formula.get("proprietary_calibration_withheld"):
            scoring_math = (
                '<div style="background:#F8FAFC;border:1px solid #CBD5E1;border-radius:12px;padding:16px;margin:16px 0;">'
                '<p style="font:700 13px Inter,sans-serif;color:#0F172A;margin:0 0 8px;">Score transparency</p>'
                '<p style="font:12px/1.65 Inter,sans-serif;color:#334155;margin:0;">'
                f'Foundation: <strong>{fmt_num(f_score,2)} / {fmt_num(f_max,0)}</strong><br>'
                f'Revenue/User Architecture: <strong>{fmt_num(r_score,2)} / {fmt_num(r_max,0)}</strong><br>'
                f'Elite Architecture: <strong>{fmt_num(e_score,2)} / {fmt_num(e_max,0)}</strong><br>'
                f'Final Revenue Readiness Index: <strong>{score_text} / 90</strong><br>'
                'The report shows the earned architecture layers and final result. Exact rule weights, calibration constants, tie-break logic and ranking equations are proprietary and remain inside the Architect/Vault system.'
                '</p></div>'
            )
        else:
            scoring_math = (
                '<div style="background:#F8FAFC;border:1px solid #CBD5E1;border-radius:12px;padding:16px;margin:16px 0;">'
                '<p style="font:700 13px Inter,sans-serif;color:#0F172A;margin:0 0 8px;">Score arithmetic — internal Architect view</p>'
                '<p style="font:12px/1.65 Inter,sans-serif;color:#334155;margin:0;">'
                f'Foundation: <strong>{fmt_num(f_score,2)} / {fmt_num(f_max,0)}</strong><br>'
                f'Revenue/User Architecture: <strong>{fmt_num(r_score,2)} / {fmt_num(r_max,0)}</strong><br>'
                f'Elite Architecture: <strong>{fmt_num(e_score,2)} / {fmt_num(e_max,0)}</strong><br>'
                f'Canonical three-layer strength: <strong>{fmt_num(canonical,2)} / 100</strong><br>'
                f'Public blueprint calibration: <strong>{fmt_num(canonical,2)} canonical → {score_text} / 90</strong><br>'
                f'Verified penalty ledger: <strong>{fmt_num(penalty,2)}</strong> canonical points — already reflected in the layer scores above, not subtracted again.'
                '</p></div>'
            )

        public_map = report.get("public_journey_map") if isinstance(report.get("public_journey_map"), dict) else {}
        if public_map:
            journey_map_html = (
                '<div style="background:#111827;border-radius:14px;padding:18px;margin:18px 0;color:#F8FAFC;">'
                '<div style="font:700 10px Inter,sans-serif;color:#D8B66A;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:10px;">HOW TRILLOKA READ THIS WEBSITE</div>'
                '<div style="font:700 20px Georgia,serif;margin-bottom:12px;">Public customer-journey map</div>'
                '<div style="font:12px/1.7 Inter,sans-serif;color:#D1D5DB;">'
                f'<strong style="color:#fff;">1. Entry:</strong> {esc(public_map.get("entry"))}<br>'
                f'<strong style="color:#fff;">2. Journey:</strong> {esc(public_map.get("path"))}<br>'
                f'<strong style="color:#fff;">3. Primary action:</strong> {esc(public_map.get("primary_action"))}<br>'
                '<strong style="color:#fff;">4. Decision points:</strong> clarity, trust, proof, friction and technical reliability<br>'
                f'<strong style="color:#fff;">5. Outcome:</strong> {esc(public_map.get("outcome"))}'
                '</div>'
                '<p style="font:11px/1.55 Inter,sans-serif;color:#9CA3AF;margin:12px 0 0;">This shows the public logic used to explain the audit. Exact inference signals, weights and calibration rules remain proprietary.</p>'
                '</div>'
            )
        else:
            journey_map_html = ''

        finding_cards = []
        for idx, item in enumerate(report.get("verified_revenue_findings") or [], 1):
            if not isinstance(item, dict):
                continue
            title = esc(item.get("leak_name") or item.get("title") or "Customer-loss finding")
            priority = str(item.get("priority") or "MEDIUM")
            angles = item.get("solutions_3_angles") if isinstance(item.get("solutions_3_angles"), dict) else {}
            receipt = item.get("evidence_receipt") if isinstance(item.get("evidence_receipt"), dict) else {}
            receipt_text = esc(json.dumps(receipt, ensure_ascii=False, default=str)[:1800])
            finding_cards.append(f'''
            <section style="background:#FFFFFF;border:1px solid #D1D5DB;border-radius:14px;padding:22px;margin:0 0 22px;">
              <div style="margin-bottom:8px;">{badge(f"{idx:02d} — {priority}", priority.lower())}</div>
              <h3 style="font:700 22px Georgia,serif;color:#111827;margin:8px 0 14px;">{title}</h3>
              <p style="font:13px/1.65 Inter,sans-serif;color:#374151;"><strong>What is the problem?</strong><br>{esc(item.get('plain_problem'))}</p>
              <p style="font:13px/1.65 Inter,sans-serif;color:#374151;"><strong>What did we find?</strong><br>{esc(item.get('what_we_found'))}</p>
              <p style="font:13px/1.65 Inter,sans-serif;color:#374151;"><strong>Where does it happen?</strong><br>{esc(item.get('where_it_happens'))}</p>
              <p style="font:13px/1.65 Inter,sans-serif;color:#374151;"><strong>Why does it matter?</strong><br>{esc(item.get('why_it_matters'))}</p>
              <div style="background:#FFF7ED;border-left:4px solid #EA580C;padding:12px 14px;margin:12px 0;">
                <p style="font:13px/1.6 Inter,sans-serif;color:#7C2D12;margin:0;"><strong>How can this affect the business financially?</strong><br>{esc(item.get('financial_effect'))}</p>
              </div>
              <p style="font:12px/1.6 Inter,sans-serif;color:#6B7280;"><strong>Evidence receipt:</strong><br>{receipt_text}</p>
              <p style="font:13px/1.65 Inter,sans-serif;color:#111827;"><strong>What should be done?</strong><br>{esc(item.get('what_should_be_done'))}</p>
              <div style="background:#F8FAFC;border-radius:10px;padding:14px;margin-top:14px;">
                <p style="font:700 13px Inter,sans-serif;color:#0F172A;margin:0 0 8px;">3-Angle Remediation Plan</p>
                <p style="font:12px/1.6 Inter,sans-serif;color:#334155;"><strong>Technical Angle:</strong> {esc(angles.get('technical'))}</p>
                <p style="font:12px/1.6 Inter,sans-serif;color:#334155;"><strong>UX / CRO Angle:</strong> {esc(angles.get('cro_ux'))}</p>
                <p style="font:12px/1.6 Inter,sans-serif;color:#334155;"><strong>Systems Angle:</strong> {esc(angles.get('systems'))}</p>
                <p style="font:12px/1.6 Inter,sans-serif;color:#475569;margin-bottom:0;"><strong>Why Trilloka recommends this:</strong> {esc(angles.get('why_recommend'))}</p>
              </div>
              <p style="font:12px Inter,sans-serif;color:#6B7280;margin:12px 0 0;"><strong>Priority:</strong> {esc(priority)} &nbsp;•&nbsp; <strong>Estimated effort:</strong> {esc(item.get('implementation_effort'))} &nbsp;•&nbsp; <strong>Cadence:</strong> {esc(angles.get('cadence_title'))} — {esc(angles.get('cadence_text'))}</p>
            </section>''')
        findings_html = ''.join(finding_cards) or '<p style="font:13px Inter,sans-serif;color:#166534;">No verified customer-loss findings were produced in the unlocked report scope.</p>'

        verification_cards = []
        for item in report.get("verification_priorities") or []:
            if not isinstance(item, dict):
                continue
            verification_cards.append(
                '<div style="border:1px solid #E9D5FF;background:#FAF5FF;border-radius:10px;padding:14px;margin:0 0 10px;">'
                f'{badge("VERIFY", "verify")} <strong style="font:13px Inter,sans-serif;color:#3B0764;">{esc(item.get("title"))}</strong>'
                f'<p style="font:12px/1.55 Inter,sans-serif;color:#6B21A8;margin:8px 0 0;">{esc(item.get("simple_explanation"))}</p>'
                '<p style="font:11px/1.5 Inter,sans-serif;color:#7E22CE;margin:6px 0 0;">Not scored as a failure. Verify the evidence source before deciding whether remediation is required.</p>'
                '</div>'
            )
        verification_html = ''.join(verification_cards) or '<p style="font:13px Inter,sans-serif;color:#166534;">No unresolved applicable verification priorities were recorded.</p>'

        strength_cards = []
        for item in report.get("verified_strengths") or []:
            if not isinstance(item, dict):
                continue
            strength_cards.append(
                '<div style="border-bottom:1px solid #DCFCE7;padding:9px 0;">'
                f'{badge("STRENGTH", "strength")} <strong style="font:12px Inter,sans-serif;color:#14532D;">{esc(item.get("title"))}</strong>'
                f'<p style="font:11px/1.5 Inter,sans-serif;color:#3F6212;margin:5px 0 0;">{esc(item.get("simple_explanation"))}</p>'
                '</div>'
            )
        strengths_html = ''.join(strength_cards) or '<p style="font:13px Inter,sans-serif;color:#6B7280;">No verified strengths were recorded.</p>'

        optional_cards = []
        for item in report.get("future_optimizations") or []:
            if not isinstance(item, dict):
                continue
            optional_cards.append(
                '<div style="border-bottom:1px solid #EDE9FE;padding:9px 0;">'
                f'{badge("OPTIONAL", "optional")} <strong style="font:12px Inter,sans-serif;color:#4C1D95;">{esc(item.get("title"))}</strong>'
                f'<p style="font:11px/1.5 Inter,sans-serif;color:#5B21B6;margin:5px 0 0;">{esc(item.get("simple_explanation"))}</p>'
                '</div>'
            )
        optional_html = ''.join(optional_cards) or '<p style="font:13px Inter,sans-serif;color:#6B7280;">No separate future optimizations were promoted in this scan.</p>'

        foundation = report.get("foundation_omission_signal") if isinstance(report.get("foundation_omission_signal"), dict) else {}
        foundation_notice = ""
        if foundation.get("triggered"):
            count = int(foundation.get("count") or 0)
            foundation_notice = f'''<div style="border:1px solid #FDBA74;background:#FFF7ED;border-radius:12px;padding:16px;margin:18px 0;">
            <p style="font:700 11px Inter,sans-serif;color:#9A3412;margin:0 0 6px;text-transform:uppercase;">Foundation Notice</p>
            <p style="font:13px/1.6 Inter,sans-serif;color:#7C2D12;margin:0;">{count} verified basic implementation omission(s) were detected. These are reported separately because a basic omission is not automatically the largest customer-loss risk.</p></div>'''

        checkpoint_rows = []
        for cp in report.get("full_50_checkpoint_basis") or []:
            if not isinstance(cp, dict):
                continue
            status = str(cp.get("status") or "UNKNOWN")
            tone = "strength" if status == PASS else ("high" if status == FAIL else ("verify" if status == UNKNOWN else "neutral"))
            checkpoint_rows.append(
                '<tr>'
                f'<td style="padding:7px;border-bottom:1px solid #E5E7EB;font:11px Inter,sans-serif;color:#6B7280;">{esc(cp.get("id"))}</td>'
                f'<td style="padding:7px;border-bottom:1px solid #E5E7EB;font:11px Inter,sans-serif;color:#111827;">{esc(cp.get("check"))}</td>'
                f'<td style="padding:7px;border-bottom:1px solid #E5E7EB;">{badge(status, tone)}</td>'
                f'<td style="padding:7px;border-bottom:1px solid #E5E7EB;font:10px/1.45 Inter,sans-serif;color:#6B7280;">{esc(cp.get("customer_note") or cp.get("reason") or "")}</td>'
                '</tr>'
            )
        checkpoint_html = '<table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#F3F4F6;"><th style="padding:7px;text-align:left;">#</th><th style="padding:7px;text-align:left;">Checkpoint</th><th style="padding:7px;text-align:left;">Status</th><th style="padding:7px;text-align:left;">Evidence note</th></tr></thead><tbody>' + ''.join(checkpoint_rows) + '</tbody></table>'

        return f'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trilloka Revenue Readiness Audit — {domain}</title></head>
<body style="margin:0;background:#F4F1EB;padding:0;">
<main style="max-width:920px;margin:0 auto;background:#FCFBF8;padding:32px 24px 60px;">
  <div style="font:700 11px Inter,sans-serif;color:#9A7A31;letter-spacing:1.5px;text-transform:uppercase;">TRILLOKA TELEMETRY & EXECUTIVE AUDIT — V7.3.1</div>
  <h1 style="font:700 34px Georgia,serif;color:#111827;margin:8px 0 8px;">Revenue Readiness Audit</h1>
  <p style="font:13px Inter,sans-serif;color:#6B7280;margin:0 0 22px;">Target: <strong>{domain}</strong> &nbsp;•&nbsp; Vault ID: <strong>{vault_id}</strong></p>

  <div style="display:flex;flex-wrap:wrap;gap:12px;margin:0 0 20px;">
    <div style="flex:1;min-width:180px;background:#111827;color:#fff;border-radius:12px;padding:18px;"><div style="font:700 10px Inter,sans-serif;color:#D1D5DB;">REVENUE READINESS INDEX</div><div style="font:700 34px Georgia,serif;margin-top:6px;">{score_text} / 90</div><div style="font:11px/1.4 Inter,sans-serif;color:#D1D5DB;margin-top:5px;">{rating}</div></div>
    <div style="flex:1;min-width:220px;background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:18px;"><div style="font:700 10px Inter,sans-serif;color:#6B7280;">BUSINESS TYPE</div><div style="font:700 18px Georgia,serif;color:#111827;margin-top:5px;">{business_type}</div><div style="font:11px Inter,sans-serif;color:#6B7280;margin-top:5px;">Type confidence: {esc(bt_conf_text)}</div></div>
    <div style="flex:1;min-width:220px;background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:18px;"><div style="font:700 10px Inter,sans-serif;color:#6B7280;">PRIMARY CUSTOMER JOURNEY</div><div style="font:700 18px Georgia,serif;color:#111827;margin-top:5px;">{journey}</div><div style="font:11px Inter,sans-serif;color:#6B7280;margin-top:5px;">Journey confidence: {esc(journey_conf_text)}</div></div>
  </div>
  <p style="font:12px/1.6 Inter,sans-serif;color:#475569;"><strong>Secondary journeys:</strong> {secondary_text}<br><strong>Context:</strong> {context_text}<br><strong>CMS:</strong> {cms}<br><strong>AI / Template Pattern Spectrum:</strong> {esc(ai_display)}<br><strong>Evidence confidence:</strong> {evidence_text}</p>

  <div style="background:#F8FAFC;border:1px solid #CBD5E1;border-radius:12px;padding:16px;margin:18px 0 24px;">
    <p style="font:700 12px Inter,sans-serif;color:#0F172A;margin:0 0 6px;">What this one scan covers</p>
    <p style="font:12px/1.6 Inter,sans-serif;color:#475569;margin:0;">Commercial path, trust and proof, technical foundation, mobile usability, performance, SEO/discoverability, measurement, policy signals, cross-page consistency, public-content hygiene and local competitor context where verifiable.</p>
  </div>
  {journey_map_html}

  <h2 style="font:700 24px Georgia,serif;color:#111827;margin:30px 0 12px;">At a Glance</h2>
  <p style="font:12px/1.6 Inter,sans-serif;color:#6B7280;">This table integrates the report's verified problems, unresolved verification items, verified strengths and optional future opportunities. It deliberately does <strong>not</strong> include solutions; detailed remediation appears later.</p>
  {at_glance_html}

  <h2 style="font:700 24px Georgia,serif;color:#111827;margin:30px 0 12px;">What the score means</h2>
  <p style="font:13px/1.65 Inter,sans-serif;color:#374151;">{esc(score_impact.get('impact_summary'))}</p>
  <p style="font:12px/1.6 Inter,sans-serif;color:#6B7280;"><strong>Scope:</strong> {scope}</p>
  {scoring_math}
  <p style="font:12px/1.6 Inter,sans-serif;color:#475569;"><strong>Evidence coverage:</strong> {coverage_note}</p>
  <p style="font:12px/1.6 Inter,sans-serif;color:#475569;"><strong>Advisory maturity threshold:</strong> {esc((report.get('maturity_gate') or {}).get('advisory_score_threshold', (report.get('maturity_gate') or {}).get('score_cap', 'N/A')))} / 90 — diagnostic reference only, not a score cap.</p>
  <p style="font:12px/1.6 Inter,sans-serif;color:#475569;"><strong>Trilloka Commercial Architecture Methodology:</strong> Business type, customer journey, context and verified evidence determine what matters most. The report explains the reasoning at a useful business level; exact weights, inference signals and calibration constants remain proprietary.</p>
  {foundation_notice}

  <div style="background:#FFF1F2;border:1px solid #FECDD3;border-radius:12px;padding:18px;margin:24px 0;">
    <div style="font:700 10px Inter,sans-serif;color:#9F1239;letter-spacing:1px;">MODELED COMMERCIAL EXPOSURE</div>
    <div style="font:700 25px Georgia,serif;color:#BE123C;margin-top:5px;">{revenue}</div>
    <p style="font:11px/1.55 Inter,sans-serif;color:#881337;margin:7px 0 0;">Scenario estimate from verified issues and explicit assumptions; not measured accounting loss, guaranteed uplift or proof that this amount has been lost.</p>
  </div>

  <h2 style="font:700 24px Georgia,serif;color:#111827;margin:32px 0 16px;">Where You Might Be Losing Customers</h2>
  <p style="font:12px/1.6 Inter,sans-serif;color:#6B7280;">Only verified scored findings appear here. These are evidence-backed places where the website may create friction or lose customers; the list is never padded with passing checkpoints simply to reach a fixed count.</p>
  {findings_html}

  <h2 style="font:700 24px Georgia,serif;color:#111827;margin:32px 0 12px;">Verification Required</h2>
  {verification_html}

  <h2 style="font:700 24px Georgia,serif;color:#111827;margin:32px 0 12px;">Verified Strengths</h2>
  <p style="font:12px/1.6 Inter,sans-serif;color:#6B7280;">These items passed. They are not problems and should generally be preserved while higher-priority customer-loss risks are addressed.</p>
  {strengths_html}

  <h2 style="font:700 24px Georgia,serif;color:#111827;margin:32px 0 12px;">Future Optimization Opportunities</h2>
  {optional_html}

  <h2 style="font:700 24px Georgia,serif;color:#111827;margin:32px 0 12px;">Full 50-Point Checkpoint Basis</h2>
  <p style="font:12px/1.6 Inter,sans-serif;color:#475569;">Verified: <strong>{esc(summary.get('verified',0))}</strong> &nbsp;•&nbsp; Passed: <strong>{esc(summary.get('passed',0))}</strong> &nbsp;•&nbsp; Failed: <strong>{esc(summary.get('failed',0))}</strong> &nbsp;•&nbsp; Unknown: <strong>{esc(summary.get('unknown',0))}</strong> &nbsp;•&nbsp; N/A: <strong>{esc(summary.get('not_applicable',0))}</strong></p>
  {checkpoint_html}

  <div style="margin-top:30px;padding-top:18px;border-top:1px solid #D1D5DB;">
    <p style="font:11px/1.6 Inter,sans-serif;color:#6B7280;"><strong>Disclaimer:</strong> This diagnostic reflects evidence available at the recorded scan time. UNKNOWN does not mean FAILED. Revenue exposure is modeled unless validated business inputs are supplied. Trilloka evaluates observable website commercial architecture; it does not determine product-market fit, market demand, legal/medical compliance, offline operations or actual accounting loss. Recommendations should be verified after implementation and specialist legal/security/medical advice should be obtained where relevant.</p>
  </div>
</main></body></html>'''

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
            '<p style="font:14px/1.7 Inter,sans-serif;color:#4B5563;margin:0 0 28px;">These items are intentionally separated from the main Revenue Readiness findings. They are basic implementation omissions, not automatically the largest customer-loss risks, and UNKNOWN evidence is never included here.</p>'
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
