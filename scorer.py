"""Trilloka evidence-weighted Revenue Readiness scorer.

Scoring philosophy:
- A functioning site begins from a 50-point operating baseline, not 100.
- Verified strengths must be earned from real telemetry.
- Verified leaks subtract weighted points.
- Unknown evidence is neutral: it earns no strength and creates no penalty.
- Ordinary good sites should typically land around 65-75.
- Scores above 80 require unusually mature, verified architecture.
- 90+ is intentionally rare and requires elite evidence across performance, conversion, trust, measurement and technical execution.

This score is Revenue Readiness, NOT a literal visitor conversion percentage.
"""

from __future__ import annotations

import secrets
import string
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from behavioural_engine import BehaviouralEngine
from checkpoint_engine import FAIL, build_50_checkpoints, checkpoint_summary


CATEGORY_WEIGHTS_BY_BIZ: Dict[str, Dict[str, float]] = {
    "general": {"seo_technical": 1.00, "trust_conversion": 1.00, "content_eeat": 0.90, "measurement": 0.90},
    "restaurant": {"seo_technical": 0.95, "trust_conversion": 1.15, "content_eeat": 0.75, "measurement": 0.85},
    "local_service": {"seo_technical": 1.00, "trust_conversion": 1.30, "content_eeat": 0.90, "measurement": 1.00},
    "professional_service": {"seo_technical": 1.05, "trust_conversion": 1.25, "content_eeat": 1.05, "measurement": 1.00},
    "medspa": {"seo_technical": 1.00, "trust_conversion": 1.40, "content_eeat": 1.20, "measurement": 1.05},
    "legal": {"seo_technical": 1.05, "trust_conversion": 1.45, "content_eeat": 1.25, "measurement": 1.05},
    "ecommerce": {"seo_technical": 1.30, "trust_conversion": 1.30, "content_eeat": 0.90, "measurement": 1.10},
    "saas": {"seo_technical": 1.20, "trust_conversion": 1.15, "content_eeat": 1.05, "measurement": 1.10},
}

BUSINESS_MODEL_MATRIX: Dict[str, Dict[str, float]] = {
    "general": {"trust": 1.00, "conversion": 1.00, "seo": 1.00, "measurement": 1.00},
    "restaurant": {"trust": 1.00, "conversion": 1.05, "seo": 0.90, "measurement": 0.90},
    "local_service": {"trust": 1.15, "conversion": 1.25, "seo": 1.00, "measurement": 1.00},
    "professional_service": {"trust": 1.20, "conversion": 1.20, "seo": 1.05, "measurement": 1.00},
    "medspa": {"trust": 1.35, "conversion": 1.35, "seo": 1.05, "measurement": 1.05},
    "legal": {"trust": 1.40, "conversion": 1.40, "seo": 1.05, "measurement": 1.05},
    "ecommerce": {"trust": 1.20, "conversion": 1.30, "seo": 1.25, "measurement": 1.10},
    "saas": {"trust": 1.15, "conversion": 1.15, "seo": 1.20, "measurement": 1.10},
}

RULE_BASE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "unsecured_ssl": {"default": 10.0},
    "core_web_vitals": {"default": 7.0, "ecommerce": 9.0, "saas": 8.0, "restaurant": 6.0},
    "click_to_call": {
        "default": 4.5,
        "restaurant": 4.0,
        "local_service": 7.0,
        "professional_service": 6.0,
        "medspa": 8.0,
        "legal": 9.0,
        "ecommerce": 2.0,
        "saas": 1.5,
    },
    "mobile_sticky_cta": {
        "default": 5.0,
        "restaurant": 5.5,
        "local_service": 6.0,
        "professional_service": 5.5,
        "medspa": 7.0,
        "legal": 6.5,
        "ecommerce": 8.0,
        "saas": 6.0,
    },
    "diluted_h1": {"default": 4.5, "legal": 5.5, "saas": 5.5},
    "missing_alt_images": {"default": 2.0, "ecommerce": 2.5},
    "favicon_present": {"default": 1.0},
    "html_lang_attribute": {"default": 1.0},
    "ai_template_similarity": {"default": 2.5, "legal": 3.5, "medspa": 3.0},
    "measurement_telemetry": {"default": 3.5, "ecommerce": 4.5, "saas": 4.0},
    "form_architecture": {"default": 5.0, "legal": 7.0, "medspa": 7.0, "local_service": 6.5},
}

CONFIDENCE_MULTIPLIERS = {"high": 1.0, "medium": 0.65, "low": 0.30, "unknown": 0.0}

TIER_PREFIXES = {3: "IFYB3", 6: "MBTB6", 8: "NOLY8", 10: "ARCH10"}


# Revenue Readiness calibration.
# Standard strengths represent strong but attainable website fundamentals.
# Elite bonus points are deliberately gated so 80+ cannot be reached merely by
# having SSL, a clean H1 and decent PageSpeed.
OPERATING_BASELINE_SCORE = 50.0
STANDARD_STRENGTH_CAP = 30.0
ELITE_BONUS_CAP = 18.0
REFERENCE_COMPLETENESS_BONUS = 2.0

LEAK_FAMILY = {
    "click_to_call": "mobile_direct_action",
    "mobile_sticky_cta": "mobile_direct_action",
    "form_architecture": "conversion_execution",
    "unsecured_ssl": "foundation_security",
    "core_web_vitals": "performance",
    "diluted_h1": "hero_clarity",
    "missing_alt_images": "accessibility_content",
    "favicon_present": "technical_hygiene",
    "html_lang_attribute": "technical_hygiene",
    "ai_template_similarity": "content_distinctiveness",
    "measurement_telemetry": "measurement",
}


# V5 commercial ranking: conversion/revenue consequences outrank ordinary SEO hygiene.
# This does not alter whether a checkpoint is measured; it changes which verified
# issues are surfaced first in customer-facing findings.
COMMERCIAL_PRIORITY_BY_FAMILY = {
    "conversion_execution": 5.0,
    "mobile_direct_action": 5.0,
    "mobile_foundation": 4.8,
    "mobile_usability": 4.6,
    "trust_proof": 4.2,
    "trust_local": 4.1,
    "trust_policy": 3.8,
    "trust_identity": 3.6,
    "measurement": 3.8,
    "performance": 3.7,
    "hero_clarity": 3.7,
    "accessibility_content": 3.2,
    "content_support": 3.1,
    "content_depth": 2.8,
    "content_distinctiveness": 2.8,
    "content_eeat": 2.7,
    "search_structure": 2.2,
    "search_snippet": 1.8,
    "crawlability": 1.7,
    "technical_hygiene": 1.5,
    "foundation_security": 5.0,
}

DEDUP_SUPERFAMILY = {
    # All performance threshold/audit signals describe one performance architecture problem.
    "performance": "performance_architecture",
    # Phone visibility, tap-to-call, sticky CTA and instant contact are one direct-action family.
    "mobile_direct_action": "mobile_direct_action",
    # H1 dedicated and topic-relevance checkpoint are one hero-clarity family.
    "hero_clarity": "hero_clarity",
    # AI/template and generic headline are one distinctiveness family.
    "content_distinctiveness": "content_distinctiveness",
    # Form dedicated and unlinked-form checkpoint are one conversion execution family.
    "conversion_execution": "conversion_execution",
    # Review/testimonial/social-proof/case-study signals can support one trust-proof finding.
    "trust_proof": "trust_proof",
}


class RevenueScorer:
    """Evidence-backed Trilloka scoring engine."""

    def __init__(self):
        self.behavioral_engine = BehaviouralEngine()

    def generate_tier_id(self, tier_level: int) -> str:
        prefix = TIER_PREFIXES.get(tier_level, "IFYB3")
        rand = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        return f"{prefix}-{rand}"

    def audit_and_score(
        self,
        scan_data: Dict[str, Any],
        business_type: str = "auto",
        competitor_data_present: Optional[bool] = None,
    ) -> Dict[str, Any]:
        if not isinstance(scan_data, dict):
            raise TypeError("scan_data must be a dictionary")

        profile, biz_type = self._resolve_business_profile(scan_data, business_type)
        scan_quality = scan_data.get("scan_quality") or {}
        coverage = scan_data.get("evidence_coverage") or {}

        if not scan_data.get("browser_loaded") and not scan_data.get("response_ok"):
            raise ValueError("Insufficient evidence: neither browser nor HTTP preflight produced usable telemetry")

        checkpoints = build_50_checkpoints(
            scan_data,
            {"business_profile": profile, "business_type": biz_type},
        )
        cp_summary = checkpoint_summary(checkpoints)
        # Do not issue a confident commercial score when almost nothing was actually inspected.
        # Static HTML + browser fallback should normally push verified coverage well above this floor.
        if int(cp_summary.get("verified") or 0) < 10:
            raise ValueError(
                f"Insufficient evidence coverage: only {cp_summary.get('verified', 0)} of 50 checkpoints were verified after fallback extraction"
            )

        try:
            behavioral = self.behavioral_engine.analyze_behavioral_friction(scan_data, biz_type)
        except Exception as exc:
            behavioral = {"status": "unavailable", "error": str(exc)}

        raw_leaks = self._evaluate_leaks(
            scan_data,
            biz_type,
            profile,
            competitor_data_present is True,
        )
        raw_leaks.extend(
            self._checkpoint_failure_leaks(
                checkpoints=checkpoints,
                existing_leaks=raw_leaks,
                biz_type=biz_type,
            )
        )
        leaks, overlap_adjustments = self._apply_family_deduplication(raw_leaks)

        # Harsh-but-defensible calibration:
        # 50 operating baseline + earned verified strengths + gated elite maturity - verified leaks.
        strength_ledger = self._evaluate_strengths(scan_data, biz_type, profile)
        raw_standard_strength = round(sum(float(item.get("points") or 0.0) for item in strength_ledger), 2)
        standard_strength = round(min(STANDARD_STRENGTH_CAP, raw_standard_strength), 2)

        total_loss = round(sum(float(leak.get("final_score_loss") or 0.0) for leak in leaks), 2)
        elite_ledger, elite_bonus = self._evaluate_elite_bonus(
            scan_data=scan_data,
            biz_type=biz_type,
            profile=profile,
            leaks=leaks,
            standard_strength=standard_strength,
        )

        reference_bonus = self._reference_completeness_bonus(
            scan_data=scan_data,
            standard_strength=standard_strength,
            elite_bonus=elite_bonus,
            total_loss=total_loss,
        )

        pre_clamp = (
            OPERATING_BASELINE_SCORE
            + standard_strength
            + elite_bonus
            + reference_bonus
            - total_loss
        )
        overall = round(max(0.0, min(100.0, pre_clamp)), 1)

        sorted_leaks = sorted(leaks, key=lambda item: item.get("final_score_loss", 0.0), reverse=True)
        report_leaks = self._consolidate_report_families(sorted_leaks)
        report_leaks = sorted(report_leaks, key=self._commercial_sort_key, reverse=True)
        key_friction = {}
        if report_leaks:
            top = report_leaks[0]
            key_friction = {
                "reason": top.get("description", ""),
                # Legacy key retained for frontend compatibility; value is score-loss points, not a measured revenue percentage.
                "revenue_loss_pct": round(float(top.get("final_score_loss") or 0.0), 1),
                "score_loss_points": round(float(top.get("final_score_loss") or 0.0), 1),
                "rule_key": top.get("rule_key"),
            }

        ai_pct = scan_data.get("ai_spectrum_pct")
        perf = scan_data.get("performance_score")
        seo = scan_data.get("google_seo_score")
        exposure = self._revenue_exposure(overall, biz_type, total_loss)

        # Preserve existing public surface metric keys. Add availability flags so unknown data is never scored as zero.
        surface_metrics = {
            "mobile_performance_score": round(float(perf)) if perf is not None else 0,
            "seo_health_index": round(float(seo)) if seo is not None else 0,
            "ai_spectrum_pct": round(float(ai_pct), 1) if ai_pct is not None else 0.0,
            "online_presence_index": round(overall, 1),
            "conversion_efficiency": round(overall, 1),
            "competitor_gap_score": max(0, round(100 - overall)),
            "classification": self._classify_template_spectrum(ai_pct, str(scan_data.get("cms_platform") or "Not confidently identified")),
            "mobile_performance_available": perf is not None,
            "seo_health_available": seo is not None,
            "ai_spectrum_available": ai_pct is not None,
        }

        tiered = {
            "tier_3_ifyb3": [self._format_leak_item(leak, 3) for leak in report_leaks[:3]],
            "tier_6_mbtb6": [self._format_leak_item(leak, 6) for leak in report_leaks[:6]],
            "tier_8_noly8": [self._format_leak_item(leak, 8) for leak in report_leaks[:8]],
            "tier_10_arch10": [self._format_leak_item(leak, 10) for leak in report_leaks[:10]],
            # Backward-compatible raw leak list. Customer report uses tier_10_arch10, which is family-consolidated.
            "all_scoring_leaks": [self._format_leak_item(leak, 10) for leak in sorted_leaks],
        }

        return {
            "target_domain": str(scan_data.get("domain") or ""),
            "business_type": biz_type,
            "business_profile": profile,
            "overall_health_score": overall,
            "overall_score": overall,
            "score_status": "available",
            "score_rating": self._get_score_rating(overall),
            "surface_metrics": surface_metrics,
            "key_friction_insight": key_friction,
            "revenue_leak": {
                # Legacy key retained; the customer again receives a dollar range, explicitly model-based.
                "est_annual_revenue_leak": exposure["display"],
                "estimated_annual_range": exposure["range"],
                "estimated_annual_min": exposure["min"],
                "estimated_annual_max": exposure["max"],
                "exposure_level": exposure["level"],
                "method_note": exposure["method_note"],
                "model_based": True,
                "measured_revenue_loss": False,
            },
            "ai_spectrum_pct": ai_pct,
            "ai_spectrum_status": scan_data.get("ai_spectrum_status", "unknown"),
            "behavioral_diagnostics": behavioral,
            "total_leaks_found": len(report_leaks),
            "raw_scoring_signal_count": len(sorted_leaks),
            "total_severity_index": total_loss,
            "tiered_remediation_packages": tiered,
            "vault_id": self._get_vault_id(overall),
            "cms_platform": str(scan_data.get("cms_platform") or "Not confidently identified"),
            "scan_quality": scan_quality,
            "checkpoint_summary": cp_summary,
            "full_50_checkpoint_basis": checkpoints,
            "scoring_ledger": [self._ledger_row(leak) for leak in sorted_leaks],
            "strength_ledger": strength_ledger,
            "elite_strength_ledger": elite_ledger,
            "overlap_adjustments": overlap_adjustments,
            "score_semantics": "Revenue Readiness score; not a literal visitor conversion percentage.",
            "score_formula": {
                "operating_baseline": OPERATING_BASELINE_SCORE,
                "raw_verified_strength_points": raw_standard_strength,
                "standard_strength_cap": STANDARD_STRENGTH_CAP,
                "verified_strength_points_awarded": standard_strength,
                "elite_bonus_points": elite_bonus,
                "reference_completeness_bonus": reference_bonus,
                "total_final_penalty": total_loss,
                "pre_clamp_score": round(pre_clamp, 2),
                "final_score": overall,
            },
        }

    def _resolve_business_profile(self, scan_data: Dict[str, Any], requested: str) -> Tuple[Dict[str, Any], str]:
        automatic = dict(scan_data.get("business_profile") or {})
        auto_vertical = self._normalize_business_type(automatic.get("vertical"))
        auto_conf = float(automatic.get("confidence") or 0.0)

        requested_norm = self._normalize_business_type(requested)
        requested_raw = str(requested or "auto").strip().lower()

        # Explicit known types win. If the frontend intentionally sends GENERAL, preserve it.
        if requested_raw == "general":
            profile = automatic
            inferred_subtype = auto_vertical if auto_vertical != "general" and auto_conf >= 0.55 else "general"
            profile.update(
                {
                    "vertical": "general",
                    "inferred_subtype": inferred_subtype,
                    "inferred_subtype_confidence": auto_conf if inferred_subtype != "general" else 0.0,
                    "confidence": 1.0,
                    "source": "explicit_request",
                }
            )
            return profile, "general"
        if requested_raw not in {"", "auto", "unknown", "none"} and requested_norm != "general":
            profile = automatic
            profile.update({"vertical": requested_norm, "confidence": 1.0, "source": "explicit_request"})
            return profile, requested_norm

        if auto_vertical != "general" and auto_conf >= 0.55:
            automatic["source"] = "automatic_classifier"
            return automatic, auto_vertical

        fallback = automatic or {}
        fallback.update({"vertical": "general", "confidence": max(auto_conf, 0.4), "source": "general_fallback"})
        return fallback, "general"

    @staticmethod
    def _normalize_business_type(raw: Any) -> str:
        value = str(raw or "general").lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "restaurant": "restaurant",
            "cafe": "restaurant",
            "café": "restaurant",
            "food_service": "restaurant",
            "local_service": "local_service",
            "home_service": "local_service",
            "professional_service": "professional_service",
            "professional_services": "professional_service",
            "consulting": "professional_service",
            "medspa": "medspa",
            "aesthetics": "medspa",
            "legal": "legal",
            "law": "legal",
            "ecommerce": "ecommerce",
            "e_commerce": "ecommerce",
            "store": "ecommerce",
            "saas": "saas",
            "software": "saas",
            "general": "general",
            "auto": "general",
        }
        return aliases.get(value, "general")

    def _evaluate_strengths(
        self,
        data: Dict[str, Any],
        biz_type: str,
        profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Award only verified strengths. Unknown evidence earns zero points.

        The standard strength pool is intentionally capped at 30 points. A normal
        professional site can therefore reach the upper 60s / 70s by proving good
        fundamentals, but cannot drift into the 90s simply because nothing obvious
        failed.
        """
        strengths: List[Dict[str, Any]] = []

        def add(key: str, points: float, category: str, evidence: Dict[str, Any], source: str) -> None:
            if points <= 0:
                return
            strengths.append({
                "strength_key": key,
                "points": round(float(points), 2),
                "category": category,
                "evidence": evidence,
                "source": source,
            })

        # 1. Secure, reachable foundation.
        if data.get("response_ok") is True and data.get("has_ssl") is True:
            add("secure_reachable_foundation", 3.0, "seo_technical", {
                "status_code": data.get("status_code"),
                "final_url": data.get("final_url"),
                "has_ssl": True,
            }, "HTTP preflight")

        # 2. Google mobile performance quality. Only real PageSpeed data earns points.
        perf = self._safe_float(data.get("performance_score"))
        if data.get("pagespeed_api_status") == "success" and perf is not None:
            perf_points = 3.0 if perf >= 90 else (2.0 if perf >= 75 else (1.0 if perf >= 60 else 0.0))
            add("mobile_performance_quality", perf_points, "seo_technical", {"performance_score": perf}, "Google PageSpeed")

        # 3. Lighthouse SEO quality.
        seo = self._safe_float(data.get("google_seo_score"))
        if data.get("pagespeed_api_status") == "success" and seo is not None:
            seo_points = 2.0 if seo >= 90 else (1.25 if seo >= 80 else (0.5 if seo >= 70 else 0.0))
            add("seo_technical_quality", seo_points, "seo_technical", {"google_seo_score": seo}, "Google Lighthouse SEO")

        # 4. Mobile conversion access.
        if str(data.get("mobile_cta_status") or "unknown").lower() == "verified":
            if data.get("mobile_primary_cta_present") is True:
                add("mobile_primary_conversion_action", 2.0, "trust_conversion", {
                    "cta_types": data.get("mobile_cta_types") or [],
                }, "Rendered mobile DOM")
            if data.get("mobile_sticky_cta_present") is True:
                add("persistent_mobile_conversion_access", 1.5, "trust_conversion", {
                    "cta_types": data.get("mobile_cta_types") or [],
                }, "Rendered mobile DOM after scroll")

        # 5. Business-specific primary conversion path.
        business_conversion_points, business_conversion_evidence = self._business_conversion_strength(data, biz_type, profile)
        add("business_specific_conversion_path", business_conversion_points, "trust_conversion", business_conversion_evidence, "Rendered conversion architecture")

        # 6. Direct contact readiness when it actually matters to the vertical.
        if biz_type in {"restaurant", "local_service", "professional_service", "medspa", "legal"}:
            if data.get("click_to_call_status") == "verified" and data.get("click_to_call_present") is True:
                add("direct_mobile_contact", 1.0, "trust_conversion", {"click_to_call_present": True}, "Rendered mobile DOM")
        elif biz_type in {"ecommerce", "saas"}:
            if data.get("live_chat_present") or data.get("whatsapp_present"):
                add("instant_query_channel", 1.0, "trust_conversion", {
                    "live_chat_present": bool(data.get("live_chat_present")),
                    "whatsapp_present": bool(data.get("whatsapp_present")),
                }, "Rendered DOM")

        # 7. Hero semantics. One verified H1 earns the full standard strength.
        h1_tags = data.get("h1_tags") or []
        if str(data.get("h1_status") or "unknown").lower() == "present":
            if len(h1_tags) == 1:
                add("single_primary_h1", 1.5, "content_eeat", {"h1": h1_tags[0]}, "Rendered DOM + source")
            elif len(h1_tags) > 1:
                add("h1_present_but_multiple", 0.4, "content_eeat", {"h1_count": len(h1_tags)}, "Rendered DOM")

        # 8. Metadata.
        meta_desc = str(data.get("meta_description") or "").strip()
        title = str(data.get("title") or "").strip()
        metadata_points = 0.0
        if title:
            metadata_points += 0.25
        if meta_desc:
            metadata_points += 0.50 if 80 <= len(meta_desc) <= 170 else 0.25
        add("search_snippet_metadata", metadata_points, "seo_technical", {
            "title_present": bool(title), "meta_description_length": len(meta_desc),
        }, "Rendered document head")

        # 9. Structured technical foundation: each item is independently verified.
        structured_items = {
            "schema": data.get("schema_present"),
            "canonical": data.get("canonical_present"),
            "sitemap": data.get("sitemap_present"),
            "robots": data.get("robots_valid"),
        }
        structured_points = 0.75 * sum(value is True for value in structured_items.values())
        add("structured_search_foundation", structured_points, "seo_technical", structured_items, "DOM + HTTP discovery")

        # 10. Mobile/accessibility hygiene.
        mobile_hygiene_points = 0.0
        hygiene_evidence: Dict[str, Any] = {}
        if data.get("mobile_viewport_configured") is True:
            mobile_hygiene_points += 0.5
            hygiene_evidence["mobile_viewport_configured"] = True
        if data.get("html_lang_present") is True:
            mobile_hygiene_points += 0.5
            hygiene_evidence["html_lang_present"] = True
        total_images = int(data.get("total_images") or data.get("image_count") or 0)
        missing_alt = int(data.get("missing_alt_images") or 0)
        if data.get("browser_loaded") and total_images > 0 and missing_alt == 0:
            mobile_hygiene_points += 0.75
            hygiene_evidence["all_rendered_images_accessible"] = True
        if data.get("pagespeed_api_status") == "success" and not data.get("tap_targets_flagged"):
            mobile_hygiene_points += 0.25
            hygiene_evidence["tap_targets_flagged"] = 0
        add("mobile_accessibility_hygiene", mobile_hygiene_points, "seo_technical", hygiene_evidence, "Rendered DOM + PageSpeed")

        # 11. Trust proof. No hardcoded passes.
        trust_points = 0.0
        trust_evidence: Dict[str, Any] = {}
        if data.get("reviews_visible") is True:
            trust_points += 1.0
            trust_evidence["reviews_visible"] = True
        if data.get("social_proof_present") is True:
            trust_points += 0.75
            trust_evidence["social_proof_present"] = True
        if data.get("privacy_terms_linked") is True or (data.get("privacy_policy_linked") is True and data.get("terms_linked") is True):
            trust_points += 0.75
            trust_evidence["privacy_terms_linked"] = True
        if biz_type in {"restaurant", "local_service", "medspa", "legal", "professional_service"}:
            if data.get("address_location_visible") is True:
                trust_points += 0.5
                trust_evidence["address_location_visible"] = True
        elif data.get("about_team_linked") is True:
            trust_points += 0.5
            trust_evidence["about_team_linked"] = True
        add("trust_and_proof_foundation", trust_points, "content_eeat", trust_evidence, "Rendered DOM / Places evidence")

        # 12. Measurement foundation. This is deliberately modest: analytics is useful, not conversion itself.
        measurement_points = 0.0
        measurement_evidence: Dict[str, Any] = {}
        if data.get("has_ga4") is True:
            measurement_points += 1.25
            measurement_evidence["has_ga4_or_gtm"] = True
        if data.get("retargeting_pixel_installed") is True:
            measurement_points += 0.50
            measurement_evidence["retargeting_pixel_installed"] = True
        if data.get("has_qualitative_analytics") is True:
            measurement_points += 0.25
            measurement_evidence["qualitative_analytics"] = True
        add("measurement_foundation", measurement_points, "measurement", measurement_evidence, "Rendered script inspection")

        # 13. Form / contact execution when relevant.
        if data.get("forms_present") is True and data.get("form_action_valid") is True:
            add("valid_form_architecture", 1.0, "trust_conversion", {"form_action_valid": True}, "Rendered form DOM")

        # 14. Basic brand/identity hygiene.
        identity_points = 0.0
        identity_evidence: Dict[str, Any] = {}
        if data.get("favicon_present") is True:
            identity_points += 0.25
            identity_evidence["favicon_present"] = True
        if data.get("custom_photography_status") == "PASS":
            identity_points += 0.50
            identity_evidence["custom_photography_status"] = "PASS"
        add("brand_identity_hygiene", identity_points, "content_eeat", identity_evidence, "Rendered DOM")

        return strengths

    def _business_conversion_strength(
        self, data: Dict[str, Any], biz_type: str, profile: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """Score whether the site exposes the conversion path that matters for its business model."""
        evidence: Dict[str, Any] = {"primary_conversion": profile.get("primary_conversion")}
        points = 0.0
        if biz_type == "restaurant":
            if data.get("order_online_present"):
                points = 2.5
                evidence["order_online_present"] = True
            elif data.get("reservation_present"):
                points = 2.0
                evidence["reservation_present"] = True
            elif data.get("mobile_primary_cta_present"):
                points = 1.25
                evidence["mobile_primary_cta_present"] = True
        elif biz_type == "ecommerce":
            if data.get("add_to_cart_visible"):
                points = 2.5
                evidence["add_to_cart_visible"] = True
            elif data.get("mobile_primary_cta_present"):
                points = 1.25
                evidence["mobile_primary_cta_present"] = True
        elif biz_type in {"legal", "medspa", "local_service", "professional_service"}:
            if data.get("mobile_primary_cta_present") and (data.get("click_to_call_present") or data.get("forms_present")):
                points = 2.5
                evidence["qualified_primary_action"] = True
            elif data.get("mobile_primary_cta_present"):
                points = 1.5
                evidence["mobile_primary_cta_present"] = True
        elif biz_type == "saas":
            if data.get("mobile_primary_cta_present"):
                points = 2.5
                evidence["mobile_primary_cta_present"] = True
        else:
            if data.get("mobile_primary_cta_present"):
                points = 1.75
                evidence["mobile_primary_cta_present"] = True
        return points, evidence

    def _evaluate_elite_bonus(
        self,
        scan_data: Dict[str, Any],
        biz_type: str,
        profile: Dict[str, Any],
        leaks: List[Dict[str, Any]],
        standard_strength: float,
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Award rare maturity points needed to move above ordinary-good territory.

        Elite points are gated behind at least 24 standard strength points. This is
        not a hidden score cap: it means advanced credit cannot be earned until the
        verified fundamentals are already strong.
        """
        if standard_strength < 24.0:
            return [], 0.0

        elite: List[Dict[str, Any]] = []

        def add(key: str, points: float, evidence: Dict[str, Any], source: str) -> None:
            if points <= 0:
                return
            elite.append({
                "strength_key": key,
                "points": round(float(points), 2),
                "category": "elite_maturity",
                "evidence": evidence,
                "source": source,
            })

        perf = self._safe_float(scan_data.get("performance_score"))
        seo = self._safe_float(scan_data.get("google_seo_score"))
        if scan_data.get("pagespeed_api_status") == "success" and perf is not None and perf >= 95:
            add("elite_mobile_performance", 1.5, {"performance_score": perf}, "Google PageSpeed")
        if scan_data.get("pagespeed_api_status") == "success" and seo is not None and seo >= 95:
            add("elite_lighthouse_seo", 1.0, {"google_seo_score": seo}, "Google Lighthouse SEO")

        # Current Core Web Vitals: LCP, INP, CLS. Field data gets preference; lab fallback is accepted where applicable.
        lcp = self._safe_float(scan_data.get("crux_lcp_ms"))
        if lcp is None:
            lcp = self._safe_float(scan_data.get("psi_lcp_ms"))
        inp = self._safe_float(scan_data.get("crux_inp_ms"))
        cls = self._safe_float(scan_data.get("crux_cls"))
        if cls is None:
            cls = self._safe_float(scan_data.get("psi_cls"))
        if lcp is not None and lcp <= 2500:
            add("good_lcp", 0.5, {"lcp_ms": lcp}, "CrUX / PageSpeed")
        if inp is not None and inp <= 200:
            add("good_inp", 1.0, {"inp_ms": inp}, "CrUX")
        if cls is not None and cls <= 0.1:
            add("good_cls", 0.25, {"cls": cls}, "CrUX / PageSpeed")

        coverage = self._safe_float((scan_data.get("evidence_coverage") or {}).get("ratio")) or 0.0
        if coverage >= 0.85:
            add("high_evidence_coverage", 0.25, {"coverage_ratio": coverage}, "Scanner evidence coverage")

        conversion_mature = bool(scan_data.get("mobile_primary_cta_present") and scan_data.get("mobile_sticky_cta_present"))
        if biz_type == "restaurant":
            conversion_mature = conversion_mature and bool(scan_data.get("order_online_present") or scan_data.get("reservation_present"))
        elif biz_type == "ecommerce":
            conversion_mature = conversion_mature and bool(scan_data.get("add_to_cart_visible"))
        if conversion_mature:
            add("mature_conversion_architecture", 1.0, {
                "mobile_primary_cta_present": True,
                "mobile_sticky_cta_present": True,
                "primary_conversion": profile.get("primary_conversion"),
            }, "Rendered conversion architecture")

        if scan_data.get("has_ga4") and scan_data.get("retargeting_pixel_installed") and scan_data.get("has_qualitative_analytics"):
            add("mature_measurement_stack", 2.0, {
                "ga4_or_gtm": True, "retargeting": True, "qualitative_analytics": True,
            }, "Rendered script inspection")

        if scan_data.get("reviews_visible") and scan_data.get("social_proof_present") and (
            scan_data.get("privacy_terms_linked") or (scan_data.get("privacy_policy_linked") and scan_data.get("terms_linked"))
        ):
            add("mature_trust_architecture", 0.75, {
                "reviews_visible": True, "social_proof_present": True, "privacy_terms_linked": True,
            }, "Rendered DOM / Places evidence")

        technical_complete = all(scan_data.get(key) is True for key in (
            "schema_present", "canonical_present", "sitemap_present", "robots_valid",
            "mobile_viewport_configured", "html_lang_present", "favicon_present",
        ))
        if technical_complete:
            add("mature_technical_foundation", 0.75, {"all_core_technical_signals_verified": True}, "DOM + HTTP discovery")

        total_images = int(scan_data.get("total_images") or scan_data.get("image_count") or 0)
        no_alt_failures = scan_data.get("browser_loaded") and total_images > 0 and int(scan_data.get("missing_alt_images") or 0) == 0
        no_tap_failures = scan_data.get("pagespeed_api_status") == "success" and not scan_data.get("tap_targets_flagged")
        if no_alt_failures and no_tap_failures:
            add("mature_mobile_accessibility", 0.25, {"alt_coverage": "complete", "tap_targets": "clear"}, "DOM + PageSpeed")

        high_impact = [leak for leak in leaks if float(leak.get("severity_factor") or 0.0) >= 0.65]
        if not high_impact:
            add("no_high_impact_verified_leaks", 0.5, {"high_impact_leaks": 0}, "Scoring ledger")

        raw = sum(float(item.get("points") or 0.0) for item in elite)
        return elite, round(min(ELITE_BONUS_CAP, raw), 2)

    @staticmethod
    def _reference_completeness_bonus(
        scan_data: Dict[str, Any], standard_strength: float, elite_bonus: float, total_loss: float
    ) -> float:
        """Make 100 theoretically possible but exceptionally difficult."""
        try:
            coverage = float((scan_data.get("evidence_coverage") or {}).get("ratio") or 0.0)
        except (TypeError, ValueError):
            coverage = 0.0
        if (
            standard_strength >= 29.5
            and elite_bonus >= 9.0
            and total_loss <= 0.01
            and coverage >= 0.95
        ):
            return REFERENCE_COMPLETENESS_BONUS
        return 0.0

    def _evaluate_leaks(
        self,
        data: Dict[str, Any],
        biz_type: str,
        profile: Dict[str, Any],
        competitor_verified: bool,
    ) -> List[Dict[str, Any]]:
        leaks: List[Dict[str, Any]] = []
        quality_conf = str((data.get("scan_quality") or {}).get("confidence") or "unknown").lower()

        # 1. HTTPS / SSL
        if data.get("response_ok") and data.get("has_ssl") is False:
            leaks.append(
                self._build_leak(
                    "unsecured_ssl",
                    "Unsecured HTTPS/SSL Foundation",
                    "Site is reachable without an HTTPS-secured final URL.",
                    "seo_technical",
                    biz_type,
                    severity_factor=1.0,
                    confidence="high",
                    substitution_factor=1.0,
                    competitor_verified=competitor_verified,
                    evidence={"final_url": data.get("final_url"), "status_code": data.get("status_code")},
                    source="HTTP preflight",
                )
            )

        # 2. Performance / Core Web Vitals
        perf = self._safe_float(data.get("performance_score"))
        crux_grade = str(data.get("real_user_speed_grade") or "UNKNOWN")
        if perf is not None and perf < 60:
            severity = max(0.30, min(1.0, (60.0 - perf) / 40.0 + 0.25))
            if crux_grade == "POOR":
                severity = min(1.0, severity + 0.20)
            leaks.append(
                self._build_leak(
                    "core_web_vitals",
                    "Severe Mobile Performance Latency" if severity >= 0.75 else "Sub-optimal Mobile Performance Latency",
                    f"Google mobile performance telemetry returned {perf:.1f}/100.",
                    "seo_technical",
                    biz_type,
                    severity_factor=severity,
                    confidence="high" if data.get("pagespeed_api_status") == "success" else "unknown",
                    substitution_factor=1.0,
                    competitor_verified=competitor_verified,
                    evidence={
                        "performance_score": perf,
                        "crux_grade": crux_grade,
                        "crux_lcp_ms": data.get("crux_lcp_ms"),
                        "crux_inp_ms": data.get("crux_inp_ms"),
                        "crux_cls": data.get("crux_cls"),
                    },
                    source="Google PageSpeed / CrUX",
                )
            )
        elif crux_grade == "POOR":
            leaks.append(
                self._build_leak(
                    "core_web_vitals",
                    "Poor Real-User Core Web Vitals",
                    "Google CrUX field telemetry indicates poor real-user Core Web Vitals.",
                    "seo_technical",
                    biz_type,
                    severity_factor=0.8,
                    confidence="high",
                    substitution_factor=1.0,
                    competitor_verified=competitor_verified,
                    evidence={
                        "crux_lcp_ms": data.get("crux_lcp_ms"),
                        "crux_inp_ms": data.get("crux_inp_ms"),
                        "crux_cls": data.get("crux_cls"),
                    },
                    source="Google CrUX",
                )
            )

        # 3. Phone visibility vs click-to-call
        call_status = str(data.get("click_to_call_status") or "unknown").lower()
        phone_status = str(data.get("phone_visibility_status") or "unknown").lower()
        if call_status == "verified" and phone_status == "verified" and not bool(data.get("click_to_call_present")):
            phone_visible = bool(data.get("phone_number_visible"))
            severity = 0.40 if phone_visible else 0.85
            substitution = self._conversion_substitution("click_to_call", biz_type, data, profile)
            description = (
                "A phone number is visible, but no explicit touch-optimized tel: action was detected."
                if phone_visible
                else "No verified tap-to-call action was detected in the rendered mobile experience."
            )
            leaks.append(
                self._build_leak(
                    "click_to_call",
                    "Sub-optimal Mobile Click-to-Call" if phone_visible else "Missing Mobile Click-to-Call / Instant Call Action",
                    description,
                    "trust_conversion",
                    biz_type,
                    severity_factor=severity,
                    confidence="high" if quality_conf == "high" else "medium",
                    substitution_factor=substitution,
                    competitor_verified=competitor_verified,
                    evidence={
                        "phone_number_visible": phone_visible,
                        "detected_phone_numbers": data.get("detected_phone_numbers") or [],
                        "tel_link_present": bool(data.get("click_to_call_present")),
                        "primary_conversion": profile.get("primary_conversion"),
                    },
                    source="Rendered mobile DOM",
                )
            )

        # 4. Sticky CTA, distinct from normal CTA
        if str(data.get("mobile_cta_status") or "unknown").lower() == "verified" and not bool(data.get("mobile_sticky_cta_present")):
            primary_present = bool(data.get("mobile_primary_cta_present"))
            severity = 0.45 if primary_present else 0.90
            substitution = self._conversion_substitution("mobile_sticky_cta", biz_type, data, profile)
            leaks.append(
                self._build_leak(
                    "mobile_sticky_cta",
                    "Absence of Mobile Sticky Call-to-Action (CTA)",
                    (
                        "Primary actions exist, but no verified fixed/sticky conversion action remains accessible after mobile scrolling."
                        if primary_present
                        else "No verified persistent mobile conversion action was detected after scrolling."
                    ),
                    "trust_conversion",
                    biz_type,
                    severity_factor=severity,
                    confidence="high" if quality_conf == "high" else "medium",
                    substitution_factor=substitution,
                    competitor_verified=competitor_verified,
                    evidence={
                        "mobile_primary_cta_present": primary_present,
                        "mobile_sticky_cta_present": False,
                        "cta_types": data.get("mobile_cta_types") or [],
                    },
                    source="Rendered mobile DOM after scroll",
                )
            )

        # 5. H1 / hero semantics - unknown never fails
        h1_status = str(data.get("h1_status") or "unknown").lower()
        h1_tags = data.get("h1_tags") or []
        if h1_status == "missing":
            leaks.append(
                self._build_leak(
                    "diluted_h1",
                    "Missing Primary H1 / Hero Semantic Anchor",
                    "Rendered DOM and serialized page source both confirmed no H1 element.",
                    "content_eeat",
                    biz_type,
                    severity_factor=0.75,
                    confidence="high",
                    substitution_factor=1.0,
                    competitor_verified=competitor_verified,
                    evidence={"h1_dom_count": data.get("h1_dom_count"), "h1_source_count": data.get("h1_source_count")},
                    source="Rendered DOM + serialized source",
                )
            )
        elif h1_status == "present" and len(h1_tags) > 1:
            leaks.append(
                self._build_leak(
                    "diluted_h1",
                    "Multiple Primary H1 Signals",
                    f"{len(h1_tags)} rendered H1 elements were detected; review whether the hero hierarchy is intentional.",
                    "content_eeat",
                    biz_type,
                    severity_factor=0.25,
                    confidence="high",
                    substitution_factor=1.0,
                    competitor_verified=competitor_verified,
                    evidence={"h1_tags": h1_tags},
                    source="Rendered DOM",
                )
            )
        elif h1_status == "present" and bool((data.get("ai_flags") or {}).get("generic_headline")):
            leaks.append(
                self._build_leak(
                    "diluted_h1",
                    "Generic Hero Value Proposition",
                    "A primary heading exists, but the template-pattern heuristic detected generic positioning language.",
                    "content_eeat",
                    biz_type,
                    severity_factor=0.25,
                    confidence="medium",
                    substitution_factor=1.0,
                    competitor_verified=competitor_verified,
                    evidence={"h1_tags": h1_tags},
                    source="Rendered headings",
                )
            )

        # 6. Alt accessibility
        total_images = int(data.get("total_images") or data.get("image_count") or 0)
        missing_alt = int(data.get("missing_alt_images") or 0)
        if data.get("browser_loaded") and total_images > 0 and missing_alt > 0:
            ratio = missing_alt / max(1, total_images)
            severity = 0.25 if ratio < 0.30 else (0.50 if ratio < 0.75 else 0.80)
            leaks.append(
                self._build_leak(
                    "missing_alt_images",
                    "Missing Image Accessibility Text",
                    f"{missing_alt} of {total_images} rendered images lacked alt/WAI-ARIA accessibility treatment.",
                    "content_eeat",
                    biz_type,
                    severity_factor=severity,
                    confidence="high",
                    substitution_factor=1.0,
                    competitor_verified=competitor_verified,
                    evidence={"missing_alt_images": missing_alt, "total_images": total_images},
                    source="Rendered DOM",
                )
            )

        # 7. Favicon - small hygiene penalty only when verified.
        if data.get("favicon_present") is False and data.get("browser_loaded"):
            leaks.append(
                self._build_leak(
                    "favicon_present",
                    "Missing Website Favicon",
                    "No favicon link was detected in the rendered document head.",
                    "seo_technical",
                    biz_type,
                    severity_factor=0.35,
                    confidence="high",
                    substitution_factor=1.0,
                    competitor_verified=False,
                    evidence={"favicon_present": False},
                    source="Rendered document head",
                )
            )

        # 8. HTML language
        if data.get("html_lang_present") is False and data.get("browser_loaded"):
            leaks.append(
                self._build_leak(
                    "html_lang_attribute",
                    "Missing HTML Language Attribute",
                    "The root HTML element has no verified lang attribute.",
                    "seo_technical",
                    biz_type,
                    severity_factor=0.35,
                    confidence="high",
                    substitution_factor=1.0,
                    competitor_verified=False,
                    evidence={"html_lang_present": False},
                    source="Rendered DOM",
                )
            )

        # 9. AI/template pattern index - only when measured, and kept modest.
        ai_pct = self._safe_float(data.get("ai_spectrum_pct"))
        if data.get("ai_spectrum_status") == "heuristic" and ai_pct is not None and ai_pct > 50:
            severity = min(0.70, max(0.20, (ai_pct - 50.0) / 70.0))
            leaks.append(
                self._build_leak(
                    "ai_template_similarity",
                    "High AI / Template Pattern Spectrum",
                    f"Template-pattern heuristic measured {ai_pct:.1f}/100. This is a pattern index, not proof of AI authorship.",
                    "content_eeat",
                    biz_type,
                    severity_factor=severity,
                    confidence="medium",
                    substitution_factor=1.0,
                    competitor_verified=False,
                    evidence={"ai_template_pattern_index": ai_pct, "ai_flags": data.get("ai_flags") or {}},
                    source="Rendered DOM/template heuristic",
                )
            )

        # 10. Measurement telemetry - evidence-backed absence, not universal catastrophe.
        if data.get("browser_loaded") and not data.get("has_ga4") and not data.get("has_meta_pixel"):
            leaks.append(
                self._build_leak(
                    "measurement_telemetry",
                    "Measurement Telemetry Blind Spot",
                    "No GA4/GTM-style analytics or Meta Pixel signal was detected in the rendered page source.",
                    "measurement",
                    biz_type,
                    severity_factor=0.45,
                    confidence="medium",
                    substitution_factor=1.0,
                    competitor_verified=False,
                    evidence={"has_ga4": False, "has_meta_pixel": False},
                    source="Rendered source/script inspection",
                )
            )

        # 11. Form architecture - only when a form is actually present and structurally invalid.
        if data.get("forms_present") and data.get("form_action_valid") is False:
            leaks.append(
                self._build_leak(
                    "form_architecture",
                    "Broken / Unresolved Form Submission Architecture",
                    "At least one rendered form lacked both a valid action target and a complete SPA-style input/submit structure.",
                    "trust_conversion",
                    biz_type,
                    severity_factor=0.80,
                    confidence="high",
                    substitution_factor=1.0,
                    competitor_verified=competitor_verified,
                    evidence={"form_action_valid": False, "unlinked_forms": (data.get("ai_flags") or {}).get("unlinked_forms")},
                    source="Rendered form DOM",
                )
            )

        return leaks

    def _checkpoint_failure_leaks(
        self,
        checkpoints: List[Dict[str, Any]],
        existing_leaks: List[Dict[str, Any]],
        biz_type: str,
    ) -> List[Dict[str, Any]]:
        """Promote verified checkpoint failures into scoring/report leaks without duplicating dedicated rules."""
        existing_rules = {str(item.get("rule_key") or "") for item in existing_leaks}
        promoted: List[Dict[str, Any]] = []
        for checkpoint in checkpoints:
            if checkpoint.get("status") != FAIL or checkpoint.get("dedicated_rule"):
                continue
            rule_key = str(checkpoint.get("rule_key") or "")
            if not rule_key or rule_key in existing_rules:
                continue
            base_weight = float(checkpoint.get("report_weight") or 0.0)
            severity = float(checkpoint.get("severity_factor") or 0.0)
            if base_weight <= 0 or severity <= 0:
                continue

            category = str(checkpoint.get("category") or "seo_technical")
            category_multiplier = CATEGORY_WEIGHTS_BY_BIZ[biz_type].get(category, 1.0)
            matrix = BUSINESS_MODEL_MATRIX[biz_type]
            business_multiplier = {
                "trust_conversion": matrix["conversion"],
                "seo_technical": matrix["seo"],
                "content_eeat": matrix["trust"],
                "measurement": matrix["measurement"],
            }.get(category, 1.0)
            pre_dedupe = base_weight * category_multiplier * business_multiplier * severity
            title, impact = self._checkpoint_failure_copy(checkpoint)
            promoted.append(
                {
                    "rule_key": rule_key,
                    "family": str(checkpoint.get("family") or rule_key),
                    "checkpoint_id": checkpoint.get("id"),
                    "checkpoint_name": checkpoint.get("check"),
                    "title": title,
                    "description": impact,
                    "category": category,
                    "base_impact_weight": round(base_weight, 2),
                    "category_multiplier": round(category_multiplier, 3),
                    "business_multiplier": round(business_multiplier, 3),
                    "severity_factor": round(severity, 2),
                    "confidence": "high",
                    "confidence_multiplier": 1.0,
                    "substitution_factor": 1.0,
                    "competitor_advantage_bonus": 0.0,
                    "pre_dedupe_penalty": round(pre_dedupe, 2),
                    "family_adjustment": 1.0,
                    "final_score_loss": round(pre_dedupe, 2),
                    "final_severity_score": round(pre_dedupe, 2),
                    "evidence": {
                        "checkpoint_id": checkpoint.get("id"),
                        "checkpoint": checkpoint.get("check"),
                        "evidence": checkpoint.get("evidence"),
                    },
                    "source": "Verified 50-point checkpoint evidence",
                }
            )
            existing_rules.add(rule_key)
        return promoted

    @staticmethod
    def _checkpoint_failure_copy(checkpoint: Dict[str, Any]) -> Tuple[str, str]:
        rule_key = str(checkpoint.get("rule_key") or "")
        name = str(checkpoint.get("check") or "Verified checkpoint failure")
        copy_map = {
            "https_redirect": ("HTTPS Redirect Gap", "The secure site is available, but HTTP-to-HTTPS enforcement was not verified as correctly implemented."),
            "retargeting_telemetry": ("Retargeting Measurement Gap", "No verified retargeting/marketing pixel signal was found, limiting campaign attribution and remarketing readiness."),
            "phone_visibility": ("Phone Visibility Gap", "A visible phone contact signal was not detected even though the page was successfully inspected."),
            "location_visibility": ("Location Confidence Gap", "The page did not expose a clear address/location signal, which can weaken local intent and trust."),
            "trust_credentials": ("Credential / Trust Signal Gap", "No clear credential, certification, secure-purchase or comparable trust signal was detected."),
            "reviews_social_proof": ("Review Proof Gap", "No clear testimonial/review proof was detected in the inspected page evidence."),
            "guarantee_refund_clarity": ("Guarantee / Refund Clarity Gap", "A relevant guarantee/refund reassurance signal was not found for this business model."),
            "about_team_signal": ("Identity / About Signal Gap", "No clear About/Team identity path was detected, reducing business transparency."),
            "social_proof_signal": ("Social Proof Gap", "The inspected page did not expose a strong review, credential or comparable proof signal."),
            "instant_query_channel": ("Instant Query Channel Gap", "No live-chat or WhatsApp-style instant query option was detected."),
            "meta_description_missing": ("Missing Search Description", "The page did not expose a meta description, weakening search-result message control."),
            "meta_description_length": ("Weak Search Snippet Length", "The verified meta description exists but falls outside the scanner's preferred concise search-snippet range."),
            "h1_topic_relevance": ("Hero Topic Relevance Gap", "The verified H1 does not strongly support the inferred primary topic/value proposition."),
            "title_length": ("Title Tag Clarity Gap", "The verified title length falls outside the scanner's preferred search-title range."),
            "structured_data_missing": ("Structured Data Gap", "No verified Schema.org structured-data signal was detected."),
            "canonical_missing": ("Canonical Signal Missing", "No canonical URL declaration was detected in the verified document evidence."),
            "sitemap_missing": ("XML Sitemap Gap", "The scanner could not find a valid XML sitemap at the standard/declarative locations it checked."),
            "robots_missing": ("Robots.txt Gap", "A valid robots.txt file was not found at the standard site location."),
            "pagespeed_below_60": ("Severe Mobile Performance Drag", "Google PageSpeed mobile performance measured below the scanner's minimum readiness threshold."),
            "pagespeed_below_90": ("Performance Headroom Remaining", "Google PageSpeed performance is usable but remains below the scanner's elite-performance threshold."),
            "seo_score_below_80": ("Technical SEO Readiness Gap", "Google Lighthouse SEO evidence measured below the scanner's readiness threshold."),
            "lcp_poor": ("Slow Largest Contentful Paint", "Measured LCP exceeded the scanner's good-performance threshold."),
            "inp_poor": ("Interaction Responsiveness Gap", "Measured INP exceeded the scanner's good responsiveness threshold."),
            "cls_poor": ("Layout Stability Gap", "Measured CLS exceeded the scanner's good visual-stability threshold."),
            "viewport_missing": ("Mobile Viewport Foundation Missing", "A valid mobile viewport configuration was not detected."),
            "tap_target_friction": ("Mobile Tap-Target Friction", "Google telemetry flagged one or more tap-target sizing/spacing issues."),
            "render_blocking": ("Render-Blocking Resource Drag", "Google telemetry identified resources that materially block rendering."),
            "lazy_loading_gap": ("Image Loading Efficiency Gap", "Relevant image loading behavior did not meet the scanner's optimization requirement."),
            "author_bylines_missing": ("Content Authorship Signal Gap", "Relevant editorial content lacks a verified author/byline signal."),
            "publication_dates_missing": ("Content Freshness Signal Gap", "Relevant editorial content lacks a visible publication/date signal."),
            "thin_visible_content": ("Thin Visible Content Depth", "The verified visible page content is below the scanner's minimum depth threshold for this business model."),
            "generic_headline": ("Generic Template Headline", "The verified headline language matched generic/template-style phrasing that can weaken differentiation."),
            "unlinked_form_structure": ("Structurally Unlinked Form", "A verified form lacks a complete action or SPA-style submission structure."),
            "faq_missing": ("FAQ / Objection-Handling Gap", "No FAQ-style objection-handling section was detected where it is relevant to the business model."),
            "case_studies_missing": ("Proof-of-Work Gap", "No case-study/portfolio proof path was detected for a business model where proof-of-work is commercially relevant."),
            "content_hub_missing": ("Content Authority Gap", "No blog/content-hub path was detected for a model where ongoing expertise content is relevant."),
            "social_links_missing": ("Social Identity Link Gap", "No verified outbound social-profile links were detected."),
            "privacy_terms_missing": ("Policy Trust Gap", "Privacy and Terms links were not both detected in the verified site evidence."),
        }
        return copy_map.get(rule_key, (name, f"Verified checkpoint failure: {name}."))

    def _build_leak(
        self,
        rule_key: str,
        title: str,
        description: str,
        category: str,
        biz_type: str,
        severity_factor: float,
        confidence: str,
        substitution_factor: float,
        competitor_verified: bool,
        evidence: Dict[str, Any],
        source: str,
    ) -> Dict[str, Any]:
        severity = max(0.0, min(1.0, float(severity_factor)))
        confidence_key = confidence if confidence in CONFIDENCE_MULTIPLIERS else "unknown"
        conf_mult = CONFIDENCE_MULTIPLIERS[confidence_key]
        substitution = max(0.0, min(1.0, float(substitution_factor)))
        base_weight = self._get_base_weight(rule_key, biz_type)
        category_multiplier = CATEGORY_WEIGHTS_BY_BIZ[biz_type].get(category, 1.0)

        matrix = BUSINESS_MODEL_MATRIX[biz_type]
        business_multiplier = {
            "trust_conversion": matrix["conversion"],
            "seo_technical": matrix["seo"],
            "content_eeat": matrix["trust"],
            "measurement": matrix["measurement"],
        }.get(category, 1.0)

        weighted = base_weight * category_multiplier * business_multiplier
        competitor_bonus = 1.0 if competitor_verified and rule_key in {"click_to_call", "mobile_sticky_cta", "core_web_vitals", "form_architecture"} else 0.0
        pre_dedupe = (weighted * severity * conf_mult * substitution) + (competitor_bonus * severity * conf_mult)

        return {
            "rule_key": rule_key,
            "family": LEAK_FAMILY.get(rule_key, rule_key),
            "title": title,
            "description": description,
            "category": category,
            "base_impact_weight": round(base_weight, 2),
            "category_multiplier": round(category_multiplier, 3),
            "business_multiplier": round(business_multiplier, 3),
            "severity_factor": round(severity, 2),
            "confidence": confidence_key,
            "confidence_multiplier": conf_mult,
            "substitution_factor": round(substitution, 3),
            "competitor_advantage_bonus": round(competitor_bonus, 2),
            "pre_dedupe_penalty": round(pre_dedupe, 2),
            "family_adjustment": 1.0,
            "final_score_loss": round(pre_dedupe, 2),
            # Legacy field retained; now equals the actual post-dedupe score contribution after dedupe.
            "final_severity_score": round(pre_dedupe, 2),
            "evidence": evidence,
            "source": source,
        }

    def _apply_family_deduplication(self, leaks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for leak in leaks:
            grouped[str(leak.get("family") or leak.get("rule_key"))].append(leak)

        adjustments: List[Dict[str, Any]] = []
        for family, family_leaks in grouped.items():
            ordered = sorted(family_leaks, key=lambda item: item.get("pre_dedupe_penalty", 0.0), reverse=True)
            multipliers = [1.0, 0.35] + [0.15] * max(0, len(ordered) - 2)
            before = 0.0
            after = 0.0
            for idx, leak in enumerate(ordered):
                factor = multipliers[idx] if idx < len(multipliers) else 0.15
                before += float(leak.get("pre_dedupe_penalty") or 0.0)
                final = round(float(leak.get("pre_dedupe_penalty") or 0.0) * factor, 2)
                leak["family_adjustment"] = factor
                leak["final_score_loss"] = final
                leak["final_severity_score"] = final
                after += final
            if len(ordered) > 1 and round(before - after, 2) > 0:
                adjustments.append(
                    {
                        "family": family,
                        "pre_dedupe_total": round(before, 2),
                        "post_dedupe_total": round(after, 2),
                        "overlap_reduction": round(before - after, 2),
                        "rules": [item.get("rule_key") for item in ordered],
                    }
                )
        return leaks, adjustments

    @staticmethod
    def _commercial_sort_key(leak: Dict[str, Any]) -> tuple:
        family = str(leak.get("family") or leak.get("rule_key") or "")
        priority = float(leak.get("commercial_priority") or COMMERCIAL_PRIORITY_BY_FAMILY.get(family, 2.5))
        loss = float(leak.get("final_score_loss") or 0.0)
        severity = float(leak.get("severity_factor") or 0.0)
        # Revenue consequence is primary; score contribution and severity break ties.
        return (priority, loss, severity)

    def _consolidate_report_families(self, leaks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collapse related scoring signals into one customer-facing commercial finding.

        The full raw signals remain in scoring_ledger and overlap_adjustments. The customer
        should not see PageSpeed<60, PageSpeed<90, LCP, and render-blocking as four separate
        revenue problems when they are evidence for one performance-architecture issue.
        """
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for leak in leaks:
            family = str(leak.get("family") or leak.get("rule_key") or "uncategorized")
            superfamily = DEDUP_SUPERFAMILY.get(family, family)
            groups[superfamily].append(leak)

        consolidated: List[Dict[str, Any]] = []
        for superfamily, items in groups.items():
            ordered = sorted(items, key=lambda x: float(x.get("final_score_loss") or 0.0), reverse=True)
            primary = dict(ordered[0])
            family_total = round(sum(float(x.get("final_score_loss") or 0.0) for x in ordered), 2)
            primary["final_score_loss"] = family_total
            primary["final_severity_score"] = family_total
            primary["severity_score"] = family_total
            primary["family"] = superfamily
            primary["commercial_priority"] = COMMERCIAL_PRIORITY_BY_FAMILY.get(
                str(ordered[0].get("family") or superfamily),
                COMMERCIAL_PRIORITY_BY_FAMILY.get(superfamily, 2.5),
            )
            primary["supporting_rule_keys"] = [str(x.get("rule_key") or "") for x in ordered]
            primary["supporting_findings"] = [
                {
                    "rule_key": x.get("rule_key"),
                    "title": x.get("title"),
                    "score_loss": x.get("final_score_loss"),
                    "evidence": x.get("evidence"),
                    "source": x.get("source"),
                }
                for x in ordered
            ]
            if len(ordered) > 1:
                primary["description"] = (
                    str(primary.get("description") or "")
                    + f" Supporting telemetry from {len(ordered) - 1} related check(s) was consolidated into this finding rather than reported as duplicate leaks."
                )
            consolidated.append(primary)
        return consolidated

    def _conversion_substitution(
        self, rule_key: str, biz_type: str, data: Dict[str, Any], profile: Dict[str, Any]
    ) -> float:
        primary_present = bool(data.get("mobile_primary_cta_present"))
        order_present = bool(data.get("order_online_present"))
        cart_present = bool(data.get("add_to_cart_visible"))
        chat_present = bool(data.get("live_chat_present") or data.get("whatsapp_present"))

        if rule_key == "click_to_call":
            if biz_type == "restaurant" and order_present:
                return 0.45
            if biz_type == "ecommerce" and (cart_present or primary_present):
                return 0.20
            if biz_type == "saas" and primary_present:
                return 0.30
            if biz_type in {"legal", "medspa", "local_service"}:
                return 1.0
            if primary_present or chat_present:
                return 0.65
            return 0.85

        if rule_key == "mobile_sticky_cta":
            if primary_present:
                if biz_type == "restaurant" and order_present:
                    return 0.65
                if biz_type == "ecommerce" and cart_present:
                    return 0.75
                return 0.80
            return 1.0
        return 1.0

    def _get_base_weight(self, rule_key: str, biz_type: str) -> float:
        weights = RULE_BASE_WEIGHTS.get(rule_key, {"default": 4.0})
        return float(weights.get(biz_type, weights.get("default", 4.0)))

    def _format_leak_item(self, leak: Dict[str, Any], tier_level: int) -> Dict[str, Any]:
        return {
            "id": self.generate_tier_id(tier_level),
            "rule_key": leak.get("rule_key"),
            "family": leak.get("family"),
            "severity_score": float(leak.get("final_score_loss") or 0.0),
            "severity_factor": leak.get("severity_factor"),
            "leak_name": str(leak.get("title") or ""),
            "impact_summary": str(leak.get("description") or ""),
            "category": str(leak.get("category") or ""),
            "evidence": leak.get("evidence") or {},
            "confidence": leak.get("confidence", "unknown"),
            "source": leak.get("source", ""),
            "base_impact_weight": leak.get("base_impact_weight"),
            "category_multiplier": leak.get("category_multiplier"),
            "business_multiplier": leak.get("business_multiplier"),
            "confidence_multiplier": leak.get("confidence_multiplier"),
            "substitution_factor": leak.get("substitution_factor"),
            "competitor_advantage_bonus": leak.get("competitor_advantage_bonus"),
            "pre_dedupe_penalty": leak.get("pre_dedupe_penalty"),
            "family_adjustment": leak.get("family_adjustment"),
            "final_score_loss": leak.get("final_score_loss"),
            "commercial_priority": leak.get("commercial_priority", COMMERCIAL_PRIORITY_BY_FAMILY.get(str(leak.get("family") or ""), 2.5)),
            "supporting_rule_keys": leak.get("supporting_rule_keys") or [leak.get("rule_key")],
            "supporting_findings": leak.get("supporting_findings") or [],
        }

    @staticmethod
    def _ledger_row(leak: Dict[str, Any]) -> Dict[str, Any]:
        keys = (
            "rule_key",
            "family",
            "base_impact_weight",
            "category_multiplier",
            "business_multiplier",
            "severity_factor",
            "confidence",
            "confidence_multiplier",
            "substitution_factor",
            "competitor_advantage_bonus",
            "pre_dedupe_penalty",
            "family_adjustment",
            "final_score_loss",
            "evidence",
            "source",
        )
        return {key: leak.get(key) for key in keys}

    @staticmethod
    def _get_score_rating(score: float) -> str:
        if score >= 90:
            return "ARCHITECT / REFERENCE LEVEL"
        if score >= 85:
            return "ELITE ARCHITECTURE"
        if score >= 80:
            return "WORLD-CLASS COMMERCIAL ARCHITECTURE"
        if score >= 75:
            return "EXCEPTIONAL"
        if score >= 65:
            return "GOOD — LEAKS REMAIN"
        if score >= 50:
            return "NEEDS REMEDIATION"
        if score >= 35:
            return "CRITICAL RISK"
        return "SEVERE STRUCTURAL RISK"

    def _get_vault_id(self, score: float) -> str:
        if score >= 90:
            return self.generate_tier_id(10)
        if score >= 75:
            return self.generate_tier_id(8)
        if score >= 50:
            return self.generate_tier_id(6)
        return self.generate_tier_id(3)

    @staticmethod
    def _classify_template_spectrum(ai_pct: Optional[float], cms: str) -> str:
        if ai_pct is None:
            return f"Template Pattern Unknown — {cms}"
        if ai_pct > 60:
            return f"High Template Pattern — {cms}"
        if ai_pct > 30:
            return f"Mixed Pattern Stack — {cms}"
        return f"Low Template Pattern — {cms}"

    @staticmethod
    def _revenue_exposure(score: float, biz_type: str, total_loss: float) -> Dict[str, Any]:
        """Return a transparent model-based annual dollar exposure range.

        This is intentionally an exposure model, not a claim about measured revenue loss.
        It gives prospects a financially legible range while preserving the disclaimer that
        traffic, conversion rate and customer value were not supplied.
        """
        if score >= 90:
            level = "VERY LOW"
        elif score >= 80:
            level = "LOW"
        elif score >= 65:
            level = "MODERATE"
        elif score >= 50:
            level = "HIGH"
        else:
            level = "CRITICAL"

        multipliers = {
            "general": (280.0, 650.0),
            "restaurant": (220.0, 520.0),
            "local_service": (420.0, 950.0),
            "professional_service": (500.0, 1150.0),
            "medspa": (650.0, 1450.0),
            "legal": (800.0, 1800.0),
            "ecommerce": (450.0, 1100.0),
            "saas": (550.0, 1300.0),
        }
        low_mult, high_mult = multipliers.get(biz_type, multipliers["general"])
        readiness_gap = max(0.0, 82.0 - float(score))
        exposure_units = max(0.0, readiness_gap + min(18.0, float(total_loss) * 0.55))
        annual_min = int(round(exposure_units * low_mult / 100.0) * 100)
        annual_max = int(round(exposure_units * high_mult / 100.0) * 100)
        if score >= 90:
            annual_min = 0
        annual_max = max(annual_max, annual_min)
        range_text = f"${annual_min:,} – ${annual_max:,} / year"
        return {
            "level": level,
            "min": annual_min,
            "max": annual_max,
            "range": range_text,
            "display": f"{range_text} — {level} model-based exposure",
            "method_note": "Model-based exposure derived from Revenue Readiness gap and verified weighted leak severity; not measured accounting loss.",
        }

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
