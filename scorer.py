"""Trilloka evidence-weighted Revenue Readiness scorer.

V7.0 real-world Journey + Context score-calibration guardrails:
- High score bands are gated by verified commercial maturity; ordinary strengths cannot accumulate into high-readiness bands by themselves.
- Evidence Confidence is published separately from website quality.
- Revenue Readiness explicitly excludes demand, product-market fit, traffic quality, pricing and sales-team execution.
- Auxiliary Presence/Conversion surfaces are computed from their own applicable checkpoint evidence instead of copying the overall score.

Proof guardrails preserved from v6.8/v6.9:
- High-impact candidates at/above the configured threshold must survive a second passive confirmation pass.
- Disputed/unconfirmed severe candidates become unscored observations rather than deductions.
- Every scored finding receives an evidence receipt with URL, signal, method, timestamp and confidence.

Scoring philosophy:
- Revenue Readiness is earned across three unequal layers rather than starting every functioning site at 50.
- Foundation is deliberately low-value (22 points), Revenue/User Architecture carries the majority (60), and Elite Architecture is hard-earned (18).
- Unknown evidence is neutral: it is never a failure, but unverified evidence cannot manufacture earned readiness points.
- Score impact, intrinsic severity, evidence confidence and financial exposure are distinct outputs.
- Business/journey relevance changes checkpoint importance; basic SEO hygiene cannot outweigh a verified conversion-path failure.
- No target distribution or forced average is used. Sites earn whatever score their verified architecture supports.

This score is a Revenue Readiness INDEX, NOT a literal visitor conversion percentage or revenue forecast.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import string
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from behavioural_engine import BehaviouralEngine
from checkpoint_engine import FAIL, PASS, UNKNOWN, NA, build_50_checkpoints, checkpoint_summary, build_foundation_omission_signal
from architecture_model import COMMON_FOUNDATION_IDS, ARCHITECTURAL_CHECKPOINT_IDS, context_has, infer_architecture_profile


# -------------------------------
# Research-informed calibration
# -------------------------------
# Baymard's current avoidable cart/checkout abandonment reasons are used only
# to set RELATIVE ecommerce-checkout importance. Survey percentages are never
# copied directly into score deductions. The anchor maps the average reported
# reason to a 7.5-point commercial weight before evidence/severity/confidence.
BAYMARD_AVOIDABLE_CHECKOUT_PCTS: Dict[str, float] = {
    "extra_costs": 40.0,
    "delivery_slow": 20.0,
    "payment_trust": 19.0,
    "forced_account": 18.0,
    "checkout_complexity": 17.0,
    "site_errors": 17.0,
    "returns_policy": 13.0,
    "total_cost_visibility": 12.0,
    "card_declined": 10.0,
    "payment_methods": 9.0,
}
BAYMARD_REASON_MEAN = sum(BAYMARD_AVOIDABLE_CHECKOUT_PCTS.values()) / len(BAYMARD_AVOIDABLE_CHECKOUT_PCTS)
BAYMARD_COMMERCIAL_ANCHOR = 7.5


def _baymard_weight(*reason_keys: str) -> float:
    values = [
        BAYMARD_AVOIDABLE_CHECKOUT_PCTS[key]
        for key in reason_keys
        if key in BAYMARD_AVOIDABLE_CHECKOUT_PCTS
    ]
    if not values:
        return BAYMARD_COMMERCIAL_ANCHOR
    relative = (sum(values) / len(values)) / BAYMARD_REASON_MEAN
    # Population prevalence informs relative importance, but is deliberately
    # bounded so one survey item cannot dominate a site-specific diagnosis.
    relative = max(0.55, min(1.35, relative))
    return round(BAYMARD_COMMERCIAL_ANCHOR * relative, 2)


CATEGORY_WEIGHTS_BY_BIZ: Dict[str, Dict[str, float]] = {
    # V7: journey model, not industry. SEO/common-foundation influence is deliberately modest.
    "general": {"seo_technical": 0.55, "trust_conversion": 1.00, "content_eeat": 0.80, "measurement": 0.85},
    "lead_quote": {"seo_technical": 0.60, "trust_conversion": 1.35, "content_eeat": 1.00, "measurement": 1.00},
    "appointment_consultation": {"seo_technical": 0.60, "trust_conversion": 1.40, "content_eeat": 1.10, "measurement": 1.00},
    "reservation_event": {"seo_technical": 0.55, "trust_conversion": 1.30, "content_eeat": 0.90, "measurement": 0.90},
    "direct_purchase": {"seo_technical": 0.70, "trust_conversion": 1.40, "content_eeat": 0.90, "measurement": 1.10},
    "demo_sales": {"seo_technical": 0.60, "trust_conversion": 1.30, "content_eeat": 1.10, "measurement": 1.10},
    "membership_subscription": {"seo_technical": 0.55, "trust_conversion": 1.20, "content_eeat": 1.00, "measurement": 1.00},
}

BUSINESS_MODEL_MATRIX: Dict[str, Dict[str, float]] = {
    "general": {"trust": 1.00, "conversion": 1.00, "seo": 0.60, "measurement": 0.90},
    "lead_quote": {"trust": 1.10, "conversion": 1.30, "seo": 0.65, "measurement": 1.00},
    "appointment_consultation": {"trust": 1.20, "conversion": 1.35, "seo": 0.65, "measurement": 1.00},
    "reservation_event": {"trust": 1.05, "conversion": 1.30, "seo": 0.60, "measurement": 0.90},
    "direct_purchase": {"trust": 1.15, "conversion": 1.35, "seo": 0.75, "measurement": 1.10},
    "demo_sales": {"trust": 1.20, "conversion": 1.30, "seo": 0.65, "measurement": 1.10},
    "membership_subscription": {"trust": 1.05, "conversion": 1.20, "seo": 0.60, "measurement": 1.00},
}

RULE_BASE_WEIGHTS: Dict[str, Dict[str, float]] = {
    # Major architectural blockers. Journey-specific weights are intentionally stronger than hygiene checks.
    "unsecured_ssl": {"default": 8.0},
    "core_web_vitals": {"default": 5.5, "direct_purchase": 7.0, "demo_sales": 6.0},
    "form_architecture": {
        "default": 6.0, "lead_quote": 8.0, "appointment_consultation": 8.5,
        "reservation_event": 8.0, "direct_purchase": 7.5, "demo_sales": 8.0, "membership_subscription": 6.0,
    },
    "primary_conversion_path": {
        "default": 7.0, "lead_quote": 9.0, "appointment_consultation": 9.5,
        "reservation_event": 9.5, "direct_purchase": 11.0, "demo_sales": 9.5, "membership_subscription": 7.5,
    },
    "conversion_path_error": {
        "default": 8.0, "lead_quote": 10.0, "appointment_consultation": 10.5,
        "reservation_event": 10.5, "direct_purchase": 11.0, "demo_sales": 10.0, "membership_subscription": 8.5,
    },
    "lead_form_friction": {
        "default": 4.0, "lead_quote": 6.0, "appointment_consultation": 6.0,
        "reservation_event": 5.5, "demo_sales": 6.5, "membership_subscription": 4.0,
    },

    # Commerce-only rules. Baymard percentages calibrate relative importance only after site evidence exists.
    "checkout_cost_transparency": {"default": 0.0, "direct_purchase": _baymard_weight("extra_costs", "total_cost_visibility")},
    "guest_checkout_barrier": {"default": 0.0, "direct_purchase": _baymard_weight("forced_account")},
    "checkout_complexity": {"default": 0.0, "direct_purchase": _baymard_weight("checkout_complexity")},
    "return_policy_discoverability": {"default": 0.0, "direct_purchase": _baymard_weight("returns_policy")},
    "delivery_expectation_clarity": {"default": 0.0, "direct_purchase": 3.5},
    "shipping_info_discoverability": {"default": 0.0, "direct_purchase": 3.0},

    # Considered/demo-sales pricing evidence remains medium-confidence when pricing can legitimately be quote-based.
    "b2b_pricing_transparency": {"default": 0.0, "demo_sales": 4.0},

    # Supporting conversion signals.
    "click_to_call": {
        "default": 1.5, "lead_quote": 3.5, "appointment_consultation": 3.5,
        "reservation_event": 3.0, "direct_purchase": 0.5, "demo_sales": 1.0, "membership_subscription": 0.5,
    },
    "mobile_sticky_cta": {
        "default": 1.5, "lead_quote": 2.0, "appointment_consultation": 2.25,
        "reservation_event": 2.25, "direct_purchase": 1.75, "demo_sales": 1.75, "membership_subscription": 1.25,
    },

    # Common foundation / supporting hygiene: deliberately low weight in Revenue Readiness.
    "diluted_h1": {"default": 1.0},
    "missing_alt_images": {"default": 0.75},
    "favicon_present": {"default": 0.25},
    "html_lang_attribute": {"default": 0.35},
    "ai_template_similarity": {"default": 0.75},
    "measurement_telemetry": {"default": 2.5, "direct_purchase": 3.0, "demo_sales": 3.0},
}

# Research multipliers apply only AFTER the scanner has verified a failure.
# They adjust the relative commercial importance; they do not create failures.
RESEARCH_MULTIPLIER_BY_RULE: Dict[str, Any] = {
    "unsecured_ssl": 1.10,
    "core_web_vitals": 1.15,
    "form_architecture": 1.15,
    "conversion_path_error": 1.00,
    "primary_conversion_path": 1.20,
    "lead_form_friction": 1.10,
    "checkout_cost_transparency": 1.00,
    "guest_checkout_barrier": 1.00,
    "checkout_complexity": 1.00,
    "return_policy_discoverability": 1.00,
    "delivery_expectation_clarity": 0.90,
    "shipping_info_discoverability": 0.85,
    "b2b_pricing_transparency": 1.00,
    "click_to_call": {
        "default": 0.55, "lead_quote": 0.90, "appointment_consultation": 0.95,
        "reservation_event": 0.90, "direct_purchase": 0.25, "demo_sales": 0.45,
        "membership_subscription": 0.25,
    },
    "mobile_sticky_cta": 0.55,
    "diluted_h1": 0.65,
    "missing_alt_images": 0.65,
    "favicon_present": 0.35,
    "html_lang_attribute": 0.50,
    "ai_template_similarity": 0.60,
    "measurement_telemetry": 0.80,

    # 50-checkpoint rules.
    "https_redirect": 0.90,
    "retargeting_telemetry": 0.70,
    "phone_visibility": {
        "default": 0.55, "lead_quote": 0.90, "appointment_consultation": 0.95,
        "reservation_event": 0.90, "demo_sales": 0.40,
    },
    "location_visibility": {
        "default": 0.60, "lead_quote": 0.85, "appointment_consultation": 0.95,
        "reservation_event": 0.95,
    },
    "trust_credentials": 0.90,
    "reviews_social_proof": 0.90,
    "guarantee_refund_clarity": 0.85,
    "about_team_signal": 0.65,
    "social_proof_signal": 0.85,
    "instant_query_channel": 0.45,
    "meta_description_missing": 0.45,
    "meta_description_length": 0.35,
    "h1_topic_relevance": 0.60,
    "title_length": 0.35,
    "structured_data_missing": 0.55,
    "canonical_missing": 0.55,
    "sitemap_missing": 0.50,
    "robots_missing": 0.50,
    "pagespeed_below_60": 1.10,
    "pagespeed_below_90": 0.75,
    "seo_score_below_80": 0.60,
    "lcp_poor": 1.10,
    "inp_poor": 1.10,
    "cls_poor": 1.05,
    "viewport_missing": 0.90,
    "tap_target_friction": 0.80,
    "render_blocking": 0.95,
    "lazy_loading_gap": 0.70,
    "author_bylines_missing": 0.55,
    "publication_dates_missing": 0.45,
    "thin_visible_content": 0.60,
    "generic_headline": 0.60,
    "unlinked_form_structure": 1.05,
    "faq_missing": 0.55,
    "case_studies_missing": 0.80,
    "content_hub_missing": 0.50,
    "social_links_missing": 0.35,
    "privacy_terms_missing": 0.75,
}

RESEARCH_BASIS_BY_RULE: Dict[str, Dict[str, str]] = {
    "conversion_path_error": {"source": "Site-specific passive journey evidence", "class": "direct observed customer-path error", "scope": "same-origin conversion pages"},
    "checkout_cost_transparency": {"source": "Baymard Institute", "class": "quantitative checkout abandonment", "scope": "ecommerce checkout"},
    "guest_checkout_barrier": {"source": "Baymard Institute", "class": "quantitative checkout abandonment", "scope": "ecommerce checkout"},
    "checkout_complexity": {"source": "Baymard Institute", "class": "quantitative checkout abandonment + usability testing", "scope": "ecommerce checkout"},
    "return_policy_discoverability": {"source": "Baymard Institute", "class": "quantitative checkout abandonment", "scope": "ecommerce"},
    "form_architecture": {"source": "Nielsen Norman Group", "class": "form usability / conversion research", "scope": "lead and transaction forms"},
    "lead_form_friction": {"source": "Nielsen Norman Group", "class": "form usability / conversion research", "scope": "lead-generation forms"},
    "primary_conversion_path": {"source": "Nielsen Norman Group", "class": "conversion-event / task-success research", "scope": "business-specific primary action"},
    "b2b_pricing_transparency": {"source": "Nielsen Norman Group", "class": "B2B usability research", "scope": "B2B research journey"},
    "core_web_vitals": {"source": "Google web.dev", "class": "real-world performance case studies", "scope": "measured user experience"},
    "pagespeed_below_60": {"source": "Google Lighthouse / web.dev", "class": "measured performance", "scope": "mobile performance"},
    "lcp_poor": {"source": "Google CrUX / web.dev", "class": "field/lab performance", "scope": "Core Web Vitals"},
    "inp_poor": {"source": "Google CrUX / web.dev", "class": "field performance", "scope": "Core Web Vitals"},
    "cls_poor": {"source": "Google CrUX / web.dev", "class": "field/lab performance", "scope": "Core Web Vitals"},
    "click_to_call": {"source": "Google mobile/local research", "class": "local intent research", "scope": "call-relevant local/service businesses"},
    "phone_visibility": {"source": "Google mobile/local research", "class": "local intent research", "scope": "local/service businesses"},
    "location_visibility": {"source": "Google mobile/local research", "class": "local intent research", "scope": "location-relevant businesses"},
}


def _research_multiplier(rule_key: str, biz_type: str) -> float:
    value = RESEARCH_MULTIPLIER_BY_RULE.get(rule_key, 0.75)
    if isinstance(value, dict):
        return float(value.get(biz_type, value.get("default", 0.75)))
    return float(value)


def _research_basis(rule_key: str) -> Dict[str, str]:
    if rule_key in RESEARCH_BASIS_BY_RULE:
        return dict(RESEARCH_BASIS_BY_RULE[rule_key])
    if rule_key in {
        "meta_description_missing", "meta_description_length", "title_length",
        "structured_data_missing", "canonical_missing", "sitemap_missing",
        "robots_missing", "seo_score_below_80",
    }:
        return {"source": "Google/Lighthouse technical evidence", "class": "search/discovery hygiene", "scope": "SEO/technical"}
    return {"source": "Trilloka verified evidence model", "class": "evidence-weighted diagnostic", "scope": "site-specific"}

CONFIDENCE_MULTIPLIERS = {"high": 1.0, "medium": 0.65, "low": 0.30, "unknown": 0.0}

TIER_PREFIXES = {
    4: "IFYB4",
    8: "NOLY8",
    10: "ARCH10",
    # Legacy aliases remain accepted so older integrations do not break.
    3: "IFYB3",
    6: "MBTB6",
}


# Revenue Readiness three-layer calibration.
# The point banks deliberately reflect commercial importance rather than giving every
# checkpoint equal value.  A polished template can earn the basics, but cannot reach
# a high readiness score without strong journey/user architecture.
FOUNDATION_LAYER_MAX = 22.0
REVENUE_ARCHITECTURE_LAYER_MAX = 60.0
ELITE_BONUS_CAP = 18.0
MAX_REVENUE_READINESS_SCORE = 100.0

# Legacy constants remain exported for compatibility with older report/integration code,
# but the operating baseline is no longer used to calculate the score.
OPERATING_BASELINE_SCORE = 0.0
STANDARD_STRENGTH_CAP = FOUNDATION_LAYER_MAX + REVENUE_ARCHITECTURE_LAYER_MAX
COMMON_FOUNDATION_STRENGTH_CAP = FOUNDATION_LAYER_MAX
ADAPTIVE_ARCHITECTURE_STRENGTH_CAP = REVENUE_ARCHITECTURE_LAYER_MAX
COMMON_FOUNDATION_PENALTY_CAP = 8.0
REFERENCE_COMPLETENESS_BONUS = 0.0
SOFT_CEILING_START_SCORE = 100.0
SOFT_CEILING_SCALE = 10.0

# Maturity caps prevent weak evidence from claiming elite readiness, but they no longer
# compress ordinary sites into a narrow 60-70 band.
PROVISIONAL_JOURNEY_CAP = 64.0
FOUNDATIONAL_MATURITY_CAP = 78.0
STRONG_MATURITY_CAP = 90.0
EXCEPTIONAL_MATURITY_CAP = 96.0
REFERENCE_MATURITY_CAP = 100.0

LEAK_FAMILY = {
    "click_to_call": "mobile_direct_action",
    "mobile_sticky_cta": "mobile_direct_action",
    "primary_conversion_path": "conversion_execution",
    "form_architecture": "conversion_execution",
    "conversion_path_error": "conversion_execution",
    "lead_form_friction": "conversion_execution",
    "checkout_cost_transparency": "checkout_cost",
    "guest_checkout_barrier": "checkout_account",
    "checkout_complexity": "checkout_complexity",
    "delivery_expectation_clarity": "checkout_delivery",
    "return_policy_discoverability": "commerce_policy",
    "shipping_info_discoverability": "commerce_policy",
    "b2b_pricing_transparency": "b2b_evaluation",
    "unsecured_ssl": "foundation_security",
    "core_web_vitals": "performance",
    "diluted_h1": "hero_clarity",
    "missing_alt_images": "accessibility_content",
    "favicon_present": "technical_hygiene",
    "html_lang_attribute": "technical_hygiene",
    "ai_template_similarity": "content_distinctiveness",
    "measurement_telemetry": "measurement",
}

# Commercial priority is a tie-breaker only; actual evidence-weighted score loss
# is the primary ranking signal.
COMMERCIAL_PRIORITY_BY_FAMILY = {
    "checkout_cost": 5.0,
    "checkout_account": 4.9,
    "checkout_complexity": 4.9,
    "conversion_execution": 4.9,
    "performance": 4.8,
    "foundation_security": 4.8,
    "checkout_delivery": 4.2,
    "b2b_evaluation": 4.2,
    "commerce_policy": 4.0,
    "trust_proof": 4.0,
    "trust_local": 4.0,
    "measurement": 3.6,
    "mobile_direct_action": 3.3,
    "mobile_foundation": 3.3,
    "mobile_usability": 3.2,
    "trust_policy": 3.2,
    "trust_identity": 3.0,
    "hero_clarity": 2.8,
    "accessibility_content": 2.6,
    "content_support": 2.4,
    "content_depth": 2.2,
    "content_distinctiveness": 2.2,
    "content_eeat": 2.1,
    "search_structure": 1.6,
    "search_snippet": 1.3,
    "crawlability": 1.2,
    "technical_hygiene": 1.0,
}

# Family caps stop many small signals from collectively outweighing a verified
# commercial blocker.
FAMILY_SCORE_CAPS = {
    "technical_hygiene": 0.8,
    "search_snippet": 1.0,
    "search_structure": 1.8,
    "crawlability": 1.0,
    "hero_clarity": 2.0,
    "accessibility_content": 2.0,
    "content_support": 1.6,
    "content_depth": 2.0,
    "content_distinctiveness": 2.0,
    "content_eeat": 2.0,
    "mobile_direct_action": 3.5,
    "measurement": 3.5,
    "trust_identity": 2.5,
    "trust_policy": 3.5,
    "trust_proof": 4.5,
    "trust_local": 4.0,
    "performance": 16.0,
    "foundation_security": 14.0,
    "conversion_execution": 17.0,
    "checkout_cost": 12.0,
    "checkout_account": 9.0,
    "checkout_complexity": 9.0,
    "checkout_delivery": 4.0,
    "commerce_policy": 4.0,
    "b2b_evaluation": 4.0,
    "mobile_foundation": 3.0,
    "mobile_usability": 3.0,
}

# Combined cap across ordinary SEO/discovery hygiene. Performance is explicitly
# excluded even though it is technically measured by Lighthouse.
SEO_HYGIENE_FAMILIES = {
    "search_snippet", "search_structure", "crawlability", "technical_hygiene"
}
SEO_HYGIENE_TOTAL_CAP = 3.0

DEDUP_SUPERFAMILY = {
    "performance": "performance_architecture",
    "mobile_direct_action": "mobile_direct_action",
    "hero_clarity": "hero_clarity",
    "content_distinctiveness": "content_distinctiveness",
    "conversion_execution": "conversion_execution",
    "trust_proof": "trust_proof",
    "commerce_policy": "commerce_policy",
}

CONSOLIDATED_FAMILY_LABELS = {
    "performance_architecture": "Mobile Performance Architecture Drag",
    "mobile_direct_action": "Mobile Direct-Action Friction",
    "hero_clarity": "Hero Clarity / Primary Message Gap",
    "content_distinctiveness": "Content Distinctiveness Gap",
    "conversion_execution": "Conversion Execution Friction",
    "trust_proof": "Trust & Social Proof Gap",
    "commerce_policy": "Ecommerce Policy / Fulfilment Clarity",
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
        scan_quality_raw = scan_data.get("scan_quality")
        scan_quality = scan_quality_raw if isinstance(scan_quality_raw, dict) else {}
        coverage_raw = scan_data.get("evidence_coverage")
        coverage = coverage_raw if isinstance(coverage_raw, dict) else {}

        if not scan_data.get("browser_loaded") and not scan_data.get("response_ok"):
            raise ValueError("Insufficient evidence: neither browser nor HTTP preflight produced usable telemetry")

        checkpoints = build_50_checkpoints(
            scan_data,
            {"business_profile": profile, "architecture_profile": profile, "business_type": biz_type},
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
        raw_leaks, unconfirmed_high_impact = self._apply_high_impact_confirmation_guardrail(
            raw_leaks, scan_data
        )
        leaks, overlap_adjustments = self._apply_family_deduplication(raw_leaks)
        leaks, layer_penalty_adjustments = self._apply_layer_penalty_caps(leaks)
        overlap_adjustments.extend(layer_penalty_adjustments)
        self._attach_evidence_receipts(leaks, scan_data)

        # Three unequal point banks: Foundation 22, Revenue/User Architecture 60, Elite 18.
        # The existing strength ledger is retained for diagnostics/maturity evidence, but the
        # public score is now earned from weighted checkpoint outcomes rather than a 50-point baseline.
        strength_ledger = self._evaluate_strengths(scan_data, biz_type, profile)
        raw_common_strength = round(sum(float(item.get("points") or 0.0) for item in strength_ledger if item.get("analysis_layer") == "common_foundation"), 2)
        raw_adaptive_strength = round(sum(float(item.get("points") or 0.0) for item in strength_ledger if item.get("analysis_layer") != "common_foundation"), 2)

        common_loss = round(sum(float(leak.get("final_score_loss") or 0.0) for leak in leaks if leak.get("analysis_layer") == "common_foundation"), 2)
        adaptive_loss = round(sum(float(leak.get("final_score_loss") or 0.0) for leak in leaks if leak.get("analysis_layer") != "common_foundation"), 2)
        total_loss = round(common_loss + adaptive_loss, 2)

        foundation_score, foundation_detail = self._score_checkpoint_layer(
            checkpoints, set(COMMON_FOUNDATION_IDS), FOUNDATION_LAYER_MAX, biz_type, leaks
        )
        revenue_architecture_score, revenue_detail = self._score_checkpoint_layer(
            checkpoints, set(ARCHITECTURAL_CHECKPOINT_IDS), REVENUE_ARCHITECTURE_LAYER_MAX, biz_type, leaks
        )
        standard_strength = round(foundation_score + revenue_architecture_score, 2)
        common_strength = foundation_score
        adaptive_strength = revenue_architecture_score
        raw_standard_strength = standard_strength

        elite_ledger, elite_bonus = self._evaluate_elite_bonus(
            scan_data=scan_data,
            biz_type=biz_type,
            profile=profile,
            leaks=leaks,
            standard_strength=standard_strength,
        )
        elite_bonus = round(min(ELITE_BONUS_CAP, elite_bonus), 2)
        reference_bonus = 0.0

        pre_clamp = foundation_score + revenue_architecture_score + elite_bonus
        raw_readiness = max(0.0, min(MAX_REVENUE_READINESS_SCORE, pre_clamp))
        preliminary_public_score = round(raw_readiness, 3)

        evidence_confidence = self._build_evidence_confidence(
            cp_summary=cp_summary,
            scan_quality=scan_quality,
            coverage=coverage,
            browser_loaded=bool(scan_data.get("browser_loaded")),
            unconfirmed_high_impact=unconfirmed_high_impact,
        )
        maturity_gate = self._evaluate_maturity_gate(
            scan_data=scan_data,
            biz_type=biz_type,
            profile=profile,
            checkpoints=checkpoints,
            leaks=leaks,
            cp_summary=cp_summary,
            evidence_confidence=evidence_confidence,
            standard_strength=standard_strength,
            elite_bonus=elite_bonus,
            total_loss=total_loss,
            unconfirmed_high_impact=unconfirmed_high_impact,
        )
        overall = round(min(preliminary_public_score, float(maturity_gate["score_cap"])), 1)
        maturity_gate["pre_gate_score"] = round(preliminary_public_score, 1)
        maturity_gate["final_score"] = overall
        maturity_gate["cap_applied"] = bool(preliminary_public_score > float(maturity_gate["score_cap"]) + 1e-9)

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

        ai_pct = self._safe_float(scan_data.get("ai_spectrum_pct"))
        perf = self._safe_float(scan_data.get("performance_score"))
        seo = self._safe_float(scan_data.get("google_seo_score"))
        # Maturity caps express unverified readiness; they must not create extra modeled dollar exposure.
        exposure = self._revenue_exposure(biz_type, report_leaks, evidence_confidence)
        foundation_omission_signal = build_foundation_omission_signal(checkpoints, scan_data)

        # Preserve the public keys, but do not represent unavailable telemetry as a
        # real score of zero. Availability flags remain explicit for the frontend.
        competitor_benchmark_raw = scan_data.get("competitor_benchmark")
        competitor_benchmark = competitor_benchmark_raw if isinstance(competitor_benchmark_raw, dict) else {}
        measured_competitor = bool(competitor_benchmark.get("available"))
        if measured_competitor:
            competitor_gap = self._safe_float(competitor_benchmark.get("gap_to_local_leader"))
            if competitor_gap is None:
                competitor_gap = self._safe_float(competitor_benchmark.get("gap_to_local_avg"))
            competitor_gap = round(max(0.0, competitor_gap or 0.0), 1)
            competitor_gap_kind = "MEASURED_LOCAL_COMPETITOR_GAP"
        else:
            competitor_gap = max(0, round(MAX_REVENUE_READINESS_SCORE - overall))
            competitor_gap_kind = "MODELED_READINESS_GAP_PROXY"

        surface_metrics = {
            "mobile_performance_score": round(perf) if perf is not None else None,
            "seo_health_index": round(seo) if seo is not None else None,
            "ai_spectrum_pct": round(ai_pct, 1) if ai_pct is not None else None,
            "online_presence_index": self._checkpoint_surface_index(
                checkpoints,
                checkpoint_ids={1, 2, 6, 9, 10, 11, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24, 27, 34, 39, 40, 41, 42, 45, 46, 47, 48},
            ),
            "conversion_efficiency": self._checkpoint_surface_index(
                checkpoints,
                checkpoint_ids={3, 4, 5, 7, 8, 10, 11, 13, 14, 43, 48, 50},
            ),
            "common_foundation_index": self._checkpoint_surface_index(checkpoints, checkpoint_ids=set(COMMON_FOUNDATION_IDS)),
            "adaptive_architecture_index": self._checkpoint_surface_index(checkpoints, checkpoint_ids=set(ARCHITECTURAL_CHECKPOINT_IDS)),
            "competitor_gap_score": competitor_gap,
            "competitor_gap_kind": competitor_gap_kind,
            "competitor_data_available": measured_competitor or bool(competitor_data_present),
            "competitor_sample_count": int(competitor_benchmark.get("sample_count") or 0),
            "competitor_target_index": competitor_benchmark.get("target_local_index"),
            "competitor_local_avg_index": competitor_benchmark.get("local_avg_index"),
            "competitor_local_top_index": competitor_benchmark.get("local_top_index"),
            "competitor_benchmark": competitor_benchmark,
            "classification": self._classify_template_spectrum(ai_pct, str(scan_data.get("cms_platform") or "Not confidently identified")),
            "mobile_performance_available": perf is not None,
            "seo_health_available": seo is not None,
            "ai_spectrum_available": ai_pct is not None,
            "pagespeed_api_status": str(scan_data.get("pagespeed_api_status") or "unavailable"),
            "surface_metric_notes": {
                "online_presence_index": "Checkpoint-based public presence/trust/technical surface; not traffic, demand or brand awareness.",
                "conversion_efficiency": "Checkpoint-based observable conversion-path readiness; not measured conversion rate.",
                "common_foundation_index": "Universal HTTPS/SEO/performance/mobile/accessibility checks. Useful hygiene, intentionally lower-weight in Revenue Readiness.",
                "adaptive_architecture_index": "Journey/context-specific conversion, trust, policy, proof and completion checks; this is the higher-value architectural layer.",
            },
        }

        tiered = {
            # Current commercial products: 4 / 8 / 10 highest-value findings.
            "tier_4_ifyb4": [self._format_leak_item(leak, 4) for leak in report_leaks[:4]],
            "tier_8_noly8": [self._format_leak_item(leak, 8) for leak in report_leaks[:8]],
            "tier_10_arch10": [self._format_leak_item(leak, 10) for leak in report_leaks[:10]],
            # Legacy aliases retained so existing frontend/backend integrations keep working.
            "tier_3_ifyb3": [self._format_leak_item(leak, 4) for leak in report_leaks[:4]],
            "tier_6_mbtb6": [self._format_leak_item(leak, 8) for leak in report_leaks[:8]],
            "all_scoring_leaks": [self._format_leak_item(leak, 10) for leak in sorted_leaks],
        }

        return {
            "target_domain": str(scan_data.get("domain") or ""),
            "business_type": biz_type,
            "business_profile": profile,
            "architecture_profile": profile,
            "overall_health_score": overall,
            "overall_score": overall,
            "score_status": "available",
            "score_rating": self._get_score_rating(overall, evidence_confidence, total_loss, cp_summary, maturity_gate),
            "score_scope": "Observable website Revenue Readiness only. It does not measure product-market fit, market demand, traffic quality, pricing, sales-team performance, offline operations or actual revenue.",
            "evidence_confidence": evidence_confidence,
            "maturity_gate": maturity_gate,
            "analysis_layers": {
                "model": "three_layer_revenue_readiness",
                "common_foundation": {
                    "checkpoint_ids": sorted(COMMON_FOUNDATION_IDS),
                    "checkpoint_count": len(COMMON_FOUNDATION_IDS),
                    "strength_raw": raw_common_strength,
                    "strength_awarded": foundation_score,
                    "strength_cap": FOUNDATION_LAYER_MAX,
                    "layer_score": foundation_score,
                    "layer_max": FOUNDATION_LAYER_MAX,
                    "weighted_checkpoint_detail": foundation_detail,
                    "verified_penalty": common_loss,
                    "checkpoint_summary": ((cp_summary.get("layers") or {}).get("common_foundation") or {}),
                    "note": "Universal SEO, HTTPS, performance, mobile and accessibility foundations remain visible but intentionally carry less Revenue Readiness weight than the customer journey.",
                },
                "adaptive_architecture": {
                    "checkpoint_ids": sorted(ARCHITECTURAL_CHECKPOINT_IDS),
                    "checkpoint_count": len(ARCHITECTURAL_CHECKPOINT_IDS),
                    "strength_raw": raw_adaptive_strength,
                    "strength_awarded": revenue_architecture_score,
                    "strength_cap": REVENUE_ARCHITECTURE_LAYER_MAX,
                    "layer_score": revenue_architecture_score,
                    "layer_max": REVENUE_ARCHITECTURE_LAYER_MAX,
                    "weighted_checkpoint_detail": revenue_detail,
                    "verified_penalty": adaptive_loss,
                    "checkpoint_summary": ((cp_summary.get("layers") or {}).get("adaptive_architecture") or {}),
                    "journey_model": biz_type,
                    "journey_label": profile.get("journey_label"),
                    "context_tags": profile.get("context_tags") or [],
                    "provisional": bool(profile.get("provisional")),
                    "note": "High-value scoring adapts to the observed customer journey and context tags rather than an expanding industry taxonomy.",
                },
                "elite_architecture": {
                    "layer_score": elite_bonus,
                    "layer_max": ELITE_BONUS_CAP,
                    "verified_elite_signals": elite_ledger,
                    "note": "Elite points are intentionally difficult to earn and require advanced verified commercial/measurement maturity."
                },
            },
            "foundation_omission_signal": foundation_omission_signal,
            "surface_metrics": surface_metrics,
            "competitor_benchmark": competitor_benchmark,
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
                "verified_penalty_basis": exposure.get("verified_penalty_basis"),
                "economic_severity_basis": exposure.get("economic_severity_basis"),
                "exposure_confidence": exposure.get("confidence"),
                "exposure_confidence_score": exposure.get("confidence_score"),
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
            "scanner_engine_version": scan_data.get("scanner_engine_version", "unknown"),
            "scan_quality": scan_quality,
            "checkpoint_summary": cp_summary,
            "full_50_checkpoint_basis": checkpoints,
            "scoring_ledger": [self._ledger_row(leak) for leak in sorted_leaks],
            "evidence_receipts": [dict(leak.get("evidence_receipt") or {}) for leak in report_leaks if leak.get("evidence_receipt")],
            "high_impact_confirmation": scan_data.get("high_impact_confirmation") or {},
            "unconfirmed_high_impact_observations": unconfirmed_high_impact,
            "strength_ledger": strength_ledger,
            "elite_strength_ledger": elite_ledger,
            "overlap_adjustments": overlap_adjustments,
            "score_semantics": "Revenue Readiness index for observable website architecture; not a literal visitor conversion percentage, sales forecast or business-quality score.",
            "score_scope_exclusions": ["product-market fit", "market demand", "traffic quality", "pricing", "sales-team execution", "offline operations", "actual revenue"],
            "score_ceiling": MAX_REVENUE_READINESS_SCORE,
            "score_ceiling_note": "100/100 is theoretically available only by earning all three layers; the score is not a visitor conversion percentage.",
            "research_calibration": {
                "model": "mixed-evidence commercial-priority calibration",
                "baymard_basis": "Ecommerce checkout only: relative weights are normalized against the mean of Baymard's current avoidable abandonment reasons; survey percentages are never copied directly into deductions.",
                "nng_basis": "Primary conversion paths, B2B information needs and form friction are calibrated with Nielsen Norman Group usability/conversion research.",
                "google_basis": "Core Web Vitals/performance and local mobile-intent signals use Google/web.dev or Google mobile/local evidence where applicable.",
                "seo_policy": "SEO and discovery hygiene remain measured and visible, but low-value SEO families are capped so they cannot collectively outrank a verified commercial blocker.",
                "guardrail": "Research changes relative priority only after the scanner verifies a site-specific condition. Unknown evidence remains neutral.",
            },
            "score_formula": {
                "method": "three_unequal_earned_layers",
                "operating_baseline": 0.0,
                "foundation_layer_score": foundation_score,
                "foundation_layer_max": FOUNDATION_LAYER_MAX,
                "revenue_user_architecture_score": revenue_architecture_score,
                "revenue_user_architecture_max": REVENUE_ARCHITECTURE_LAYER_MAX,
                "elite_architecture_score": elite_bonus,
                "elite_architecture_max": ELITE_BONUS_CAP,
                "elite_bonus_points": elite_bonus,
                "raw_verified_strength_points": raw_standard_strength,
                "verified_strength_points_awarded": standard_strength,
                "reference_completeness_bonus": 0.0,
                "total_final_penalty": total_loss,
                "common_foundation_penalty": common_loss,
                "adaptive_architecture_penalty": adaptive_loss,
                "pre_clamp_score": round(pre_clamp, 2),
                "raw_pre_ceiling_score": round(raw_readiness, 2),
                "pre_maturity_gate_public_score": round(preliminary_public_score, 2),
                "maturity_band_cap": maturity_gate.get("score_cap"),
                "maturity_band": maturity_gate.get("band"),
                "maturity_cap_applied": maturity_gate.get("cap_applied"),
                "public_score_ceiling": MAX_REVENUE_READINESS_SCORE,
                "soft_ceiling_starts_at": SOFT_CEILING_START_SCORE,
                "ceiling_method": "three earned point banks plus evidence-backed maturity caps; no forced mean or target distribution",
                "final_score": overall,
            },
        }

    def _score_checkpoint_layer(
        self,
        checkpoints: List[Dict[str, Any]],
        checkpoint_ids: set[int],
        layer_max: float,
        biz_type: str,
        leaks: List[Dict[str, Any]],
    ) -> Tuple[float, Dict[str, Any]]:
        """Earn a layer score from weighted PASS/FAIL evidence without treating UNKNOWN as failure.

        PASS vs FAIL determines verified quality. Evidence coverage controls how much of the
        layer can be *earned*; UNKNOWN therefore creates no deduction but cannot manufacture
        readiness. Journey-specific rule weights make revenue-path checks worth more than
        generic hygiene. Extra verified rules not represented by a checkpoint can reduce the
        relevant layer without changing their intrinsic severity.
        """
        applicable_weight = known_weight = pass_weight = 0.0
        layer_rules = set()
        for cp in checkpoints or []:
            if not isinstance(cp, dict) or int(cp.get("id") or 0) not in checkpoint_ids:
                continue
            status = str(cp.get("status") or UNKNOWN).upper()
            if status == NA:
                continue
            rule = str(cp.get("rule_key") or "")
            layer_rules.add(rule)
            generic = max(0.25, float(cp.get("report_weight") or 0.0))
            journey_weight = self._get_base_weight(rule, biz_type) if rule in RULE_BASE_WEIGHTS else generic
            weight = max(generic, min(12.0, journey_weight))
            applicable_weight += weight
            if status in {PASS, FAIL}:
                known_weight += weight
                if status == PASS:
                    pass_weight += weight
        if known_weight <= 0 or applicable_weight <= 0:
            return 0.0, {"pass_quality": 0.0, "evidence_coverage": 0.0, "extra_verified_penalty": 0.0}
        pass_quality = pass_weight / known_weight
        coverage = known_weight / applicable_weight
        earned = float(layer_max) * pass_quality * math.sqrt(max(0.0, min(1.0, coverage)))
        extra_penalty = 0.0
        for leak in leaks or []:
            if not isinstance(leak, dict):
                continue
            rule = str(leak.get("rule_key") or "")
            is_common = str(leak.get("analysis_layer") or "") == "common_foundation"
            target_common = checkpoint_ids == set(COMMON_FOUNDATION_IDS)
            if is_common != target_common or rule in layer_rules:
                continue
            extra_penalty += float(leak.get("final_score_loss") or 0.0) * 0.55
        extra_penalty = min(float(layer_max) * 0.20, extra_penalty)
        final = max(0.0, min(float(layer_max), earned - extra_penalty))
        return round(final, 2), {
            "pass_quality": round(pass_quality, 4),
            "evidence_coverage": round(coverage, 4),
            "applicable_weight": round(applicable_weight, 2),
            "verified_weight": round(known_weight, 2),
            "passed_weight": round(pass_weight, 2),
            "extra_verified_penalty": round(extra_penalty, 2),
            "method": "weighted pass quality × sqrt(public evidence coverage), minus verified non-checkpoint rule impact",
        }

    def _resolve_business_profile(self, scan_data: Dict[str, Any], requested: str) -> Tuple[Dict[str, Any], str]:
        """Resolve the v7 Journey + Context profile.

        Legacy ``business_type`` input is retained only as a weak inference hint for API/backward
        compatibility. It never overrides stronger public page/action evidence.
        """
        profile_raw = scan_data.get("architecture_profile") if isinstance(scan_data, dict) else {}
        if not isinstance(profile_raw, dict) or not profile_raw.get("journey_model"):
            legacy_raw = scan_data.get("business_profile") if isinstance(scan_data, dict) else {}
            profile_raw = legacy_raw if isinstance(legacy_raw, dict) else {}
        if isinstance(profile_raw, dict) and profile_raw.get("journey_model"):
            profile = dict(profile_raw)
        else:
            profile = infer_architecture_profile(scan_data, requested)
        journey = self._normalize_business_type(profile.get("journey_model") or profile.get("vertical"))
        if journey == "general" and not profile.get("model_basis"):
            profile = infer_architecture_profile(scan_data, requested)
            journey = self._normalize_business_type(profile.get("journey_model"))
        profile["journey_model"] = journey
        profile["journey_label"] = profile.get("journey_label") or journey.replace("_", " ").title()
        profile["vertical"] = journey  # legacy compatibility alias
        profile["inferred_subtype"] = ""
        profile["model_basis"] = profile.get("model_basis") or "journey_context_v1"
        return profile, journey

    @staticmethod
    def _normalize_business_type(raw: Any) -> str:
        """Normalize either a v7 journey model or a legacy business hint to a journey model."""
        value = str(raw or "general").lower().replace("-", "_").replace(" ", "_")
        journeys = {
            "lead_quote", "appointment_consultation", "reservation_event", "direct_purchase",
            "demo_sales", "membership_subscription", "general",
        }
        if value in journeys:
            return value
        legacy = {
            "restaurant": "reservation_event", "cafe": "reservation_event", "café": "reservation_event",
            "food_service": "reservation_event", "local_service": "lead_quote", "home_service": "lead_quote",
            "professional_service": "lead_quote", "professional_services": "lead_quote", "consulting": "lead_quote",
            "medspa": "appointment_consultation", "aesthetics": "appointment_consultation",
            "legal": "appointment_consultation", "law": "appointment_consultation",
            "ecommerce": "direct_purchase", "e_commerce": "direct_purchase", "store": "direct_purchase",
            "saas": "demo_sales", "software": "demo_sales", "b2b": "demo_sales",
            "business_to_business": "demo_sales", "enterprise": "demo_sales", "wholesale": "demo_sales",
            "agency": "lead_quote", "marketing_agency": "lead_quote", "design_agency": "lead_quote",
            "creative_agency": "lead_quote", "creator": "membership_subscription",
            "content_creator": "membership_subscription", "newsletter": "membership_subscription",
            "auto": "general", "unknown": "general", "none": "general", "": "general",
        }
        return legacy.get(value, "general")

    def _evaluate_strengths(
        self,
        data: Dict[str, Any],
        biz_type: str,
        profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Award verified strengths with a hard split between common basics and adaptive architecture.

        Common technical/SEO foundations remain visible but can contribute at most 9 standard points.
        The adaptive customer-journey/context layer can contribute at most 21. This prevents metadata,
        schema and Lighthouse hygiene from overpowering the actual revenue path.
        """
        strengths: List[Dict[str, Any]] = []
        common_keys = {
            "secure_reachable_foundation", "mobile_performance_quality", "seo_technical_quality",
            "single_primary_h1", "h1_present_but_multiple", "search_snippet_metadata",
            "structured_search_foundation", "mobile_accessibility_hygiene", "brand_identity_hygiene",
        }

        def add(key: str, points: float, category: str, evidence: Dict[str, Any], source: str, layer: str | None = None) -> None:
            if points <= 0:
                return
            strengths.append({
                "strength_key": key,
                "points": round(float(points), 2),
                "category": category,
                "analysis_layer": layer or ("common_foundation" if key in common_keys else "adaptive_architecture"),
                "evidence": evidence,
                "source": source,
            })

        # Universal low-value foundation layer.
        if data.get("response_ok") is True and data.get("has_ssl") is True:
            add("secure_reachable_foundation", 2.0, "seo_technical", {
                "status_code": data.get("status_code"), "final_url": data.get("final_url"), "has_ssl": True,
            }, "HTTP preflight")

        perf = self._safe_float(data.get("performance_score"))
        if data.get("pagespeed_api_status") == "success" and perf is not None:
            perf_points = 2.0 if perf >= 90 else (1.35 if perf >= 75 else (0.65 if perf >= 60 else 0.0))
            add("mobile_performance_quality", perf_points, "seo_technical", {"performance_score": perf}, "Google PageSpeed")

        seo = self._safe_float(data.get("google_seo_score"))
        if data.get("pagespeed_api_status") == "success" and seo is not None:
            seo_points = 0.55 if seo >= 90 else (0.30 if seo >= 80 else (0.12 if seo >= 70 else 0.0))
            add("seo_technical_quality", seo_points, "seo_technical", {"google_seo_score": seo}, "Google Lighthouse SEO")

        h1_tags = data.get("h1_tags") if isinstance(data.get("h1_tags"), list) else []
        if str(data.get("h1_status") or "unknown").lower() == "present":
            if len(h1_tags) == 1:
                add("single_primary_h1", 0.7, "content_eeat", {"h1": h1_tags[0]}, "Rendered DOM + source")
            elif len(h1_tags) > 1:
                add("h1_present_but_multiple", 0.15, "content_eeat", {"h1_count": len(h1_tags)}, "Rendered DOM")

        meta_desc = str(data.get("meta_description") or "").strip()
        title = str(data.get("title") or "").strip()
        metadata_points = (0.12 if title else 0.0) + (0.18 if meta_desc else 0.0)
        add("search_snippet_metadata", metadata_points, "seo_technical", {
            "title_present": bool(title), "meta_description_length": len(meta_desc),
        }, "Rendered document head")

        structured_items = {
            "schema": data.get("schema_present"), "canonical": data.get("canonical_present"),
            "sitemap": data.get("sitemap_present"), "robots": data.get("robots_valid"),
        }
        add("structured_search_foundation", 0.18 * sum(v is True for v in structured_items.values()),
            "seo_technical", structured_items, "DOM + HTTP discovery")

        hygiene_points = 0.0
        hygiene_evidence: Dict[str, Any] = {}
        if data.get("mobile_viewport_configured") is True:
            hygiene_points += 0.35; hygiene_evidence["mobile_viewport_configured"] = True
        if data.get("html_lang_present") is True:
            hygiene_points += 0.25; hygiene_evidence["html_lang_present"] = True
        total_images = self._safe_int(data.get("total_images"), self._safe_int(data.get("image_count"), 0)) or 0
        missing_alt = self._safe_int(data.get("missing_alt_images"), 0) or 0
        if data.get("browser_loaded") and total_images > 0 and missing_alt == 0:
            hygiene_points += 0.35; hygiene_evidence["all_rendered_images_accessible"] = True
        if data.get("pagespeed_api_status") == "success" and not data.get("tap_targets_flagged"):
            hygiene_points += 0.25; hygiene_evidence["tap_targets_flagged"] = 0
        add("mobile_accessibility_hygiene", hygiene_points, "seo_technical", hygiene_evidence, "Rendered DOM + PageSpeed")

        identity_points = 0.0
        identity_evidence: Dict[str, Any] = {}
        if data.get("favicon_present") is True:
            identity_points += 0.12; identity_evidence["favicon_present"] = True
        if data.get("custom_photography_status") == "PASS":
            identity_points += 0.25; identity_evidence["custom_photography_status"] = "PASS"
        add("brand_identity_hygiene", identity_points, "content_eeat", identity_evidence, "Rendered DOM")

        # Adaptive architecture layer.
        if str(data.get("mobile_cta_status") or "unknown").lower() == "verified":
            if data.get("mobile_primary_cta_present") is True:
                add("mobile_primary_conversion_action", 2.0, "trust_conversion", {"cta_types": data.get("mobile_cta_types") or []}, "Rendered mobile DOM")
            if data.get("mobile_sticky_cta_present") is True and biz_type in {"lead_quote", "appointment_consultation", "reservation_event", "direct_purchase"}:
                add("persistent_mobile_conversion_access", 0.8, "trust_conversion", {"cta_types": data.get("mobile_cta_types") or []}, "Rendered mobile DOM after scroll")

        conversion_points, conversion_evidence = self._business_conversion_strength(data, biz_type, profile)
        add("journey_conversion_path", conversion_points, "trust_conversion", conversion_evidence, "Rendered conversion architecture")

        if context_has(profile, "local_location_dependent") and biz_type in {"lead_quote", "appointment_consultation", "reservation_event"}:
            if data.get("click_to_call_status") == "verified" and data.get("click_to_call_present") is True:
                add("direct_mobile_contact", 0.75, "trust_conversion", {"click_to_call_present": True}, "Rendered mobile DOM")
        elif data.get("live_chat_present") or data.get("whatsapp_present"):
            add("instant_query_channel", 0.35, "trust_conversion", {
                "live_chat_present": bool(data.get("live_chat_present")), "whatsapp_present": bool(data.get("whatsapp_present")),
            }, "Rendered DOM")

        trust_points = 0.0
        trust_evidence: Dict[str, Any] = {}
        if data.get("reviews_visible") is True:
            trust_points += 1.2; trust_evidence["reviews_visible"] = True
        if data.get("social_proof_present") is True:
            trust_points += 1.0; trust_evidence["social_proof_present"] = True
        if data.get("credential_signals_present") is True and context_has(profile, "regulated_high_trust"):
            trust_points += 1.1; trust_evidence["regulated_credentials"] = True
        if data.get("case_studies_portfolio_present") is True and context_has(profile, "enterprise_considered_purchase"):
            trust_points += 1.1; trust_evidence["proof_of_work"] = True
        if context_has(profile, "local_location_dependent") and data.get("address_location_visible") is True:
            trust_points += 0.55; trust_evidence["address_location_visible"] = True
        if data.get("about_team_linked") is True:
            trust_points += 0.45; trust_evidence["about_team_linked"] = True
        policy_ok = bool(data.get("privacy_policy_linked"))
        if context_has(profile, "commerce_payment") and data.get("checkout_context_detected"):
            policy_ok = bool(data.get("privacy_policy_linked") and data.get("terms_linked"))
        if policy_ok:
            trust_points += 0.45; trust_evidence["applicable_policy_path"] = True
        add("contextual_trust_architecture", min(4.5, trust_points), "content_eeat", trust_evidence, "Rendered/journey/Places evidence")

        measurement_present = bool(data.get("measurement_layer_present") or data.get("has_ga4") or data.get("has_meta_pixel") or data.get("has_other_measurement") or data.get("has_qualitative_analytics"))
        if measurement_present:
            add("measurement_foundation", 1.3, "measurement", {"measurement_platforms": data.get("measurement_platforms") or []}, "Rendered/source measurement inspection")
        if data.get("forms_present") is True and data.get("form_action_valid") is True:
            add("valid_form_architecture", 1.3, "trust_conversion", {"form_action_valid": True}, "Rendered form DOM")

        return strengths

    def _business_conversion_strength(
        self, data: Dict[str, Any], biz_type: str, profile: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """Score the observed customer journey rather than an asserted industry category."""
        ctas = {str(x).lower() for x in (data.get("mobile_cta_types") or []) if x}
        evidence: Dict[str, Any] = {
            "journey_model": biz_type,
            "journey_label": profile.get("journey_label"),
            "primary_conversion": profile.get("primary_conversion"),
        }
        primary = bool(data.get("mobile_primary_cta_present"))
        forms = bool(data.get("forms_present") and data.get("form_action_valid") is not False)
        call = bool(data.get("click_to_call_present"))
        booking = bool(data.get("reservation_present") or data.get("booking_provider_links"))

        if biz_type == "lead_quote":
            qualified = bool(({"quote", "contact", "book"} & ctas) or forms or call)
        elif biz_type == "appointment_consultation":
            qualified = bool(({"book", "reserve", "contact"} & ctas) or booking or forms or call)
        elif biz_type == "reservation_event":
            qualified = bool(({"reserve", "book", "contact", "order"} & ctas) or data.get("reservation_present") or forms or call)
        elif biz_type == "direct_purchase":
            qualified = bool(data.get("add_to_cart_visible") or data.get("checkout_context_detected") or {"buy", "order", "add_to_cart"} & ctas)
        elif biz_type == "demo_sales":
            qualified = bool(({"demo", "trial", "contact", "quote", "book"} & ctas) or forms)
        elif biz_type == "membership_subscription":
            qualified = bool(({"subscribe", "join", "buy", "contact"} & ctas) or forms)
        else:
            qualified = primary

        if qualified and primary:
            points = 3.5
        elif qualified:
            points = 2.6
        elif primary:
            points = 1.4
        else:
            points = 0.0
        evidence.update({
            "qualified_primary_action": qualified,
            "mobile_primary_cta_present": primary,
            "cta_types": sorted(ctas),
            "forms_present": bool(data.get("forms_present")),
        })
        return points, evidence

    def _evaluate_elite_bonus(
        self,
        scan_data: Dict[str, Any],
        biz_type: str,
        profile: Dict[str, Any],
        leaks: List[Dict[str, Any]],
        standard_strength: float,
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Award rare maturity points only after the core customer architecture is credible."""
        perf = self._safe_float(scan_data.get("performance_score"))
        psi_success = scan_data.get("pagespeed_api_status") == "success" and perf is not None
        crux_good = str(scan_data.get("real_user_speed_grade") or "UNKNOWN").upper() == "GOOD"
        performance_mature = bool((psi_success and perf >= 75) or crux_good)
        conversion_points, conversion_evidence = self._business_conversion_strength(scan_data, biz_type, profile)
        secure = bool(scan_data.get("response_ok") and scan_data.get("has_ssl") is True)
        trust_state = self._maturity_trust_state(scan_data, biz_type, profile)
        measurement = bool(scan_data.get("measurement_layer_present") or scan_data.get("has_ga4") or scan_data.get("has_meta_pixel") or scan_data.get("has_other_measurement") or scan_data.get("has_qualitative_analytics"))
        form_clear = bool(scan_data.get("forms_present") is not True or scan_data.get("form_action_valid") is True)
        if bool(profile.get("provisional")) or sum((secure, performance_mature, conversion_points >= 2.0, bool(trust_state["passed"]), measurement, form_clear)) < 5:
            return [], 0.0

        elite: List[Dict[str, Any]] = []
        def add(key: str, points: float, evidence: Dict[str, Any], source: str) -> None:
            if points > 0:
                elite.append({"strength_key": key, "points": round(float(points), 2), "category": "elite_maturity", "analysis_layer": "adaptive_architecture", "evidence": evidence, "source": source})

        if conversion_points >= 3.5:
            add("mature_customer_journey", 1.75, conversion_evidence, "Rendered customer-journey architecture")
        elif conversion_points >= 2.6:
            add("strong_customer_journey", 0.9, conversion_evidence, "Rendered customer-journey architecture")

        if measurement:
            platforms = scan_data.get("measurement_platforms") or []
            add("mature_measurement_layer", 1.0, {"measurement_platforms": platforms}, "Rendered/source measurement inspection")
        if scan_data.get("retargeting_pixel_installed") and scan_data.get("has_qualitative_analytics"):
            add("multi_layer_measurement_stack", 0.75, {"retargeting": True, "qualitative_analytics": True}, "Rendered script inspection")

        if bool(trust_state["passed"]) and int(trust_state.get("signal_count") or 0) >= 2:
            add("mature_contextual_trust", 1.25, trust_state, "Rendered/journey/Places evidence")

        if performance_mature:
            add("strong_measured_performance", 0.75, {"performance_score": perf, "crux_grade": scan_data.get("real_user_speed_grade")}, "Google PageSpeed / CrUX")
        if psi_success and perf is not None and perf >= 95:
            add("elite_mobile_performance", 0.75, {"performance_score": perf}, "Google PageSpeed")

        lcp = self._safe_float(scan_data.get("crux_lcp_ms")) or self._safe_float(scan_data.get("psi_lcp_ms"))
        inp = self._safe_float(scan_data.get("crux_inp_ms"))
        cls = self._safe_float(scan_data.get("crux_cls"))
        if cls is None:
            cls = self._safe_float(scan_data.get("psi_cls"))
        cwv_good = sum((lcp is not None and lcp <= 2500, inp is not None and inp <= 200, cls is not None and cls <= 0.1))
        if cwv_good >= 2:
            add("mature_core_web_vitals", 0.6, {"lcp_ms": lcp, "inp_ms": inp, "cls": cls}, "CrUX / PageSpeed")

        coverage_raw = scan_data.get("evidence_coverage") if isinstance(scan_data.get("evidence_coverage"), dict) else {}
        coverage = self._safe_float(coverage_raw.get("ratio")) or 0.0
        if coverage >= 0.85:
            add("high_evidence_coverage", 0.35, {"coverage_ratio": coverage}, "Scanner evidence coverage")

        major = [x for x in leaks if float(x.get("final_score_loss") or 0.0) >= 3.5]
        if not major:
            add("no_major_verified_leaks", 0.6, {"major_verified_leaks": 0}, "Scoring ledger")

        raw = sum(float(item.get("points") or 0.0) for item in elite)
        return elite, round(min(ELITE_BONUS_CAP, raw), 2)

    @staticmethod
    def _reference_completeness_bonus(
        scan_data: Dict[str, Any], standard_strength: float, elite_bonus: float, total_loss: float
    ) -> float:
        """Award the tiny final completeness increment only to unusually complete evidence sets."""
        coverage_raw = scan_data.get("evidence_coverage") if isinstance(scan_data, dict) else {}
        coverage_dict = coverage_raw if isinstance(coverage_raw, dict) else {}
        coverage = RevenueScorer._safe_float(coverage_dict.get("ratio")) or 0.0
        if (
            standard_strength >= 29.5
            and elite_bonus >= 9.0
            and total_loss <= 0.01
            and coverage >= 0.95
        ):
            return REFERENCE_COMPLETENESS_BONUS
        return 0.0

    @staticmethod
    def _build_evidence_confidence(
        cp_summary: Dict[str, Any],
        scan_quality: Dict[str, Any],
        coverage: Dict[str, Any],
        browser_loaded: bool,
        unconfirmed_high_impact: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Describe confidence in the score separately from the site's quality."""
        verified_ratio = RevenueScorer._safe_float(cp_summary.get("verified_applicable_ratio")) or 0.0
        coverage_ratio = RevenueScorer._safe_float(coverage.get("ratio")) or 0.0
        quality_label = str(scan_quality.get("confidence") or "unknown").lower()
        quality_factor = {"high": 1.0, "medium": 0.78, "moderate": 0.72, "low": 0.52, "unknown": 0.45}.get(quality_label, 0.45)
        blended = (0.58 * verified_ratio) + (0.27 * coverage_ratio) + (0.15 * quality_factor)
        unresolved_count = len([x for x in (unconfirmed_high_impact or []) if isinstance(x, dict)])
        if unresolved_count:
            blended = min(blended, 0.79)
        if not browser_loaded:
            blended = min(blended, 0.72)
        score = round(max(0.0, min(1.0, blended)) * 100.0, 1)
        level = "HIGH" if score >= 82 else ("MEDIUM" if score >= 65 else "LIMITED")
        return {
            "level": level,
            "score": score,
            "verified_applicable_ratio": round(verified_ratio, 3),
            "scanner_coverage_ratio": round(coverage_ratio, 3),
            "scan_quality_confidence": quality_label,
            "verified_checkpoints": int(cp_summary.get("verified") or 0),
            "applicable_checkpoints": int(cp_summary.get("applicable") or 0),
            "unknown_checkpoints": int(cp_summary.get("unknown") or 0),
            "not_applicable_checkpoints": int(cp_summary.get("not_applicable") or 0),
            "unresolved_high_impact_observations": unresolved_count,
            "note": "Evidence Confidence describes how much applicable public evidence was independently verified. It is not a grade for the business.",
        }

    @staticmethod
    def _checkpoint_surface_index(checkpoints: List[Dict[str, Any]], checkpoint_ids: set[int]) -> Optional[float]:
        relevant = [cp for cp in (checkpoints or []) if int(cp.get("id") or 0) in checkpoint_ids and str(cp.get("status") or "") != NA]
        if not relevant:
            return None
        verified = [cp for cp in relevant if str(cp.get("status") or "") in {PASS, FAIL}]
        if len(verified) < 2:
            return None
        passed = sum(1 for cp in verified if str(cp.get("status") or "") == PASS)
        pass_ratio = passed / len(verified)
        verification_ratio = len(verified) / len(relevant)
        index = 100.0 * ((0.90 * pass_ratio) + (0.10 * verification_ratio))
        return round(max(0.0, min(100.0, index)), 1)

    @staticmethod
    def _maturity_trust_state(scan_data: Dict[str, Any], biz_type: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        credentials = bool(scan_data.get("credential_signals_present"))
        reviews = bool(scan_data.get("reviews_visible"))
        social = bool(scan_data.get("social_proof_present"))
        badges = bool(scan_data.get("trust_badges_present"))
        about = bool(scan_data.get("about_team_linked"))
        proof_work = bool(scan_data.get("case_studies_portfolio_present"))
        signal_count = sum((credentials, reviews, social, badges, about, proof_work))
        regulated = context_has(profile, "regulated_high_trust")
        enterprise = context_has(profile, "enterprise_considered_purchase")
        commerce = context_has(profile, "commerce_payment")
        local = context_has(profile, "local_location_dependent")
        hospitality = context_has(profile, "hospitality_event")

        if regulated:
            passed = credentials and bool(reviews or social or about)
            rationale = "regulated/high-trust context requires verified credentials plus an independent proof or identity signal"
        elif enterprise or biz_type == "demo_sales":
            passed = bool(proof_work or reviews or social) and about
            rationale = "considered-purchase/demo journeys require proof-of-work/customer proof plus clear organization identity"
        elif commerce or biz_type == "direct_purchase":
            passed = bool(reviews or social or badges)
            rationale = "commerce journeys require at least one independently verified customer/trust signal"
        elif local or hospitality:
            passed = bool(reviews or social)
            rationale = "local/hospitality journeys require at least one public reputation or customer-proof signal for elite readiness"
        else:
            passed = signal_count >= 1
            rationale = "at least one independently verified trust, proof or identity signal is required for elite readiness"
        return {
            "passed": passed, "signal_count": signal_count, "credentials": credentials, "reviews": reviews,
            "social_proof": social, "trust_badges": badges, "about_team": about, "proof_of_work": proof_work,
            "rationale": rationale,
        }

    def _evaluate_maturity_gate(
        self, scan_data: Dict[str, Any], biz_type: str, profile: Dict[str, Any],
        checkpoints: List[Dict[str, Any]], leaks: List[Dict[str, Any]], cp_summary: Dict[str, Any],
        evidence_confidence: Dict[str, Any], standard_strength: float, elite_bonus: float,
        total_loss: float, unconfirmed_high_impact: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        by_id = {int(cp.get("id") or 0): cp for cp in (checkpoints or [])}
        def status(cp_id: int) -> str:
            return str((by_id.get(cp_id) or {}).get("status") or UNKNOWN)

        provisional = bool(profile.get("provisional"))
        conversion_points, conversion_evidence = self._business_conversion_strength(scan_data, biz_type, profile)
        secure = bool(scan_data.get("response_ok") and scan_data.get("has_ssl") is True)
        conversion = bool((conversion_points >= 2.0 or status(7) == PASS) and status(50) != FAIL)
        trust_state = self._maturity_trust_state(scan_data, biz_type, profile)
        measurement = bool(scan_data.get("measurement_layer_present") or scan_data.get("has_ga4") or scan_data.get("has_meta_pixel") or scan_data.get("has_other_measurement") or scan_data.get("has_qualitative_analytics"))

        perf = self._safe_float(scan_data.get("performance_score"))
        psi_success = scan_data.get("pagespeed_api_status") == "success" and perf is not None
        crux_grade = str(scan_data.get("real_user_speed_grade") or "UNKNOWN").upper()
        performance_foundation = bool((psi_success and perf >= 60) or crux_grade == "GOOD")
        performance_exceptional = bool((psi_success and perf >= 75 and crux_grade != "POOR") or (not psi_success and crux_grade == "GOOD"))
        performance_reference = bool((psi_success and perf >= 90 and crux_grade != "POOR") or (not psi_success and crux_grade == "GOOD"))

        evidence_score = float(evidence_confidence.get("score") or 0.0)
        unresolved = len([x for x in (unconfirmed_high_impact or []) if isinstance(x, dict) and str(x.get("status") or "").upper() not in {"CORROBORATED", "CONFIRMED"}])
        confirmed_major = [leak for leak in (leaks or []) if float(leak.get("pre_dedupe_penalty") or leak.get("final_score_loss") or 0.0) >= 3.5]

        # Critical architecture requirements come from journey + context, not industry names.
        critical_ids = {1, 7, 31}
        if context_has(profile, "local_location_dependent"):
            critical_ids.add(9)
        if context_has(profile, "regulated_high_trust"):
            critical_ids |= {10, 48}
        if context_has(profile, "hospitality_event"):
            critical_ids.add(11)
        if context_has(profile, "enterprise_considered_purchase") or biz_type == "demo_sales":
            critical_ids |= {13, 45}
        if context_has(profile, "commerce_payment") or biz_type == "direct_purchase":
            critical_ids.add(48)
        critical_failures = [
            {"id": cp_id, "check": (by_id.get(cp_id) or {}).get("check")}
            for cp_id in sorted(critical_ids) if status(cp_id) == FAIL
        ]

        foundational_gates = {
            "journey_model_not_provisional": not provisional,
            "secure_foundation": secure,
            "customer_conversion_path": conversion,
            "context_appropriate_trust": bool(trust_state["passed"]),
            "performance_foundation": performance_foundation,
            "measurement_layer": measurement,
            "evidence_confidence_at_least_70": evidence_score >= 70.0,
            "no_confirmed_major_leak": len(confirmed_major) == 0,
            "no_unresolved_major_observation": unresolved == 0,
            "no_context_critical_checkpoint_failure": len(critical_failures) == 0,
        }
        foundational_pass = all(foundational_gates.values())
        policy_clear = status(48) in {PASS, NA}
        form_clear = status(5) in {PASS, NA}
        exceptional_gates = {
            "foundational_maturity": foundational_pass,
            "performance_at_least_strong": performance_exceptional,
            "high_evidence_confidence": evidence_score >= 82.0,
            "policy_context_clear": policy_clear,
            "form_architecture_clear_when_applicable": form_clear,
            "no_more_than_two_applicable_failures": int(cp_summary.get("failed") or 0) <= 2,
            "verified_penalty_burden_at_most_4": total_loss <= 4.0,
            "adaptive_architecture_verified_ratio_at_least_80": float(((cp_summary.get("layers") or {}).get("adaptive_architecture") or {}).get("verified_applicable_ratio") or 0.0) >= 0.80,
        }
        exceptional_pass = all(exceptional_gates.values())
        reference_gates = {
            "exceptional_maturity": exceptional_pass,
            "reference_performance": performance_reference,
            "evidence_confidence_at_least_90": evidence_score >= 90.0,
            "at_most_one_applicable_failure": int(cp_summary.get("failed") or 0) <= 1,
            "verified_penalty_burden_at_most_1_5": total_loss <= 1.5,
            "strongest_customer_conversion_path": conversion_points >= 3.5,
            "at_least_two_trust_proof_signals": int(trust_state["signal_count"]) >= 2,
            "substantial_standard_strength": standard_strength >= 70.0,
            "meaningful_elite_strength": elite_bonus >= 4.0,
        }
        reference_pass = all(reference_gates.values())

        if provisional:
            band, cap = "PROVISIONAL_CUSTOMER_JOURNEY", PROVISIONAL_JOURNEY_CAP
        elif not foundational_pass:
            band, cap = "FOUNDATIONAL_MATURITY_NOT_FULLY_VERIFIED", FOUNDATIONAL_MATURITY_CAP
        elif not exceptional_pass:
            band, cap = "STRONG_VERIFIED_MATURITY", STRONG_MATURITY_CAP
        elif not reference_pass:
            band, cap = "EXCEPTIONAL_VERIFIED_MATURITY", EXCEPTIONAL_MATURITY_CAP
        else:
            band, cap = "REFERENCE_LEVEL_ELIGIBLE", REFERENCE_MATURITY_CAP

        if provisional:
            active = [("journey_model_not_provisional", False)]
        elif not foundational_pass:
            active = list(foundational_gates.items())
        elif not exceptional_pass:
            active = list(exceptional_gates.items())
        elif not reference_pass:
            active = list(reference_gates.items())
        else:
            active = []
        failed_gate_names = [name for name, passed in active if not passed]
        return {
            "band": band, "score_cap": cap, "foundational_pass": foundational_pass,
            "exceptional_pass": exceptional_pass, "reference_pass": reference_pass,
            "journey_model": biz_type, "journey_confidence": profile.get("confidence"), "journey_provisional": provisional,
            "context_tags": list(profile.get("context_tags") or []),
            "foundational_gates": foundational_gates, "exceptional_gates": exceptional_gates, "reference_gates": reference_gates,
            "failed_gate_names": failed_gate_names, "critical_checkpoint_failures": critical_failures, "trust_state": trust_state,
            "performance": {"pagespeed_score": perf, "crux_grade": crux_grade, "foundation": performance_foundation, "exceptional": performance_exceptional, "reference": performance_reference},
            "conversion_strength_points": conversion_points, "conversion_evidence": conversion_evidence,
            "policy_checkpoint_status": status(48), "form_checkpoint_status": status(5),
            "confirmed_major_leak_count": len(confirmed_major), "unresolved_major_observation_count": unresolved,
            "note": "Score-band caps are eligibility guardrails, not deductions. Basic SEO/technical strengths cannot accumulate into elite Revenue Readiness unless the actual customer journey, trust, evidence and performance maturity are verified.",
        }

    def _evaluate_leaks(
        self,
        data: Dict[str, Any],
        biz_type: str,
        profile: Dict[str, Any],
        competitor_verified: bool,
    ) -> List[Dict[str, Any]]:
        """Evaluate dedicated high-value rules using Journey + Context applicability.

        Common SEO/technical failures are mostly promoted from the 50-checkpoint ledger at low
        weight; this method focuses on blockers that can materially change a real customer path.
        """
        leaks: List[Dict[str, Any]] = []
        quality = data.get("scan_quality") if isinstance(data.get("scan_quality"), dict) else {}
        quality_conf = str(quality.get("confidence") or "unknown").lower()
        provisional = bool(profile.get("provisional"))
        local = context_has(profile, "local_location_dependent")
        commerce = context_has(profile, "commerce_payment") or biz_type == "direct_purchase"
        enterprise = context_has(profile, "enterprise_considered_purchase") or biz_type == "demo_sales"

        # Universal foundations with real commercial implications.
        if data.get("response_ok") and data.get("has_ssl") is False:
            leaks.append(self._build_leak(
                "unsecured_ssl", "Unsecured HTTPS/SSL Foundation",
                "The reachable final site URL was not HTTPS-secured.", "seo_technical", biz_type,
                1.0, "high", 1.0, competitor_verified,
                {"final_url": data.get("final_url"), "status_code": data.get("status_code")}, "HTTP preflight"))

        perf = self._safe_float(data.get("performance_score"))
        crux_grade = str(data.get("real_user_speed_grade") or "UNKNOWN").upper()
        if data.get("pagespeed_api_status") == "success" and perf is not None and perf < 60:
            severity = max(0.30, min(1.0, (60.0 - perf) / 40.0 + 0.25))
            if crux_grade == "POOR":
                severity = min(1.0, severity + 0.20)
            leaks.append(self._build_leak(
                "core_web_vitals", "Critical Mobile Performance Drag",
                f"Google PageSpeed measured mobile performance at {perf:.0f}/100.", "seo_technical", biz_type,
                severity, "high", 1.0, competitor_verified,
                {"performance_score": perf, "crux_grade": crux_grade}, "Google PageSpeed / CrUX"))
        elif crux_grade == "POOR":
            leaks.append(self._build_leak(
                "core_web_vitals", "Poor Real-User Core Web Vitals",
                "Google CrUX field telemetry indicates poor real-user Core Web Vitals.", "seo_technical", biz_type,
                0.8, "high", 1.0, competitor_verified,
                {"crux_lcp_ms": data.get("crux_lcp_ms"), "crux_inp_ms": data.get("crux_inp_ms"), "crux_cls": data.get("crux_cls")}, "Google CrUX"))

        # Journey-supporting call action only when local direct contact is a normal path.
        call_relevant = bool(local and biz_type in {"lead_quote", "appointment_consultation", "reservation_event"})
        call_status = str(data.get("click_to_call_status") or "unknown").lower()
        phone_status = str(data.get("phone_visibility_status") or "unknown").lower()
        if call_relevant and call_status == "verified" and phone_status == "verified" and not data.get("click_to_call_present"):
            phone_visible = bool(data.get("phone_number_visible"))
            leaks.append(self._build_leak(
                "click_to_call",
                "Sub-optimal Mobile Click-to-Call" if phone_visible else "Missing Mobile Click-to-Call / Instant Call Action",
                "A phone number is visible, but no explicit touch-optimized tel: action was detected." if phone_visible else "No verified tap-to-call action was detected in the rendered mobile experience.",
                "trust_conversion", biz_type, 0.40 if phone_visible else 0.80,
                "high" if quality_conf == "high" else "medium",
                self._conversion_substitution("click_to_call", biz_type, data, profile), competitor_verified,
                {"phone_visible": phone_visible, "click_to_call_present": False}, "Rendered mobile DOM"))

        # Sticky/direct action continuity is adaptive; missing sticky is never treated like a broken form.
        final_url = str(data.get("final_url") or data.get("url") or "").lower()
        product_context = bool(data.get("add_to_cart_visible") or data.get("checkout_context_detected") or any(x in final_url for x in ("/product/", "/products/", "/item/")))
        sticky_relevant = bool(
            (biz_type in {"appointment_consultation", "reservation_event"} and (local or context_has(profile, "hospitality_event")))
            or (biz_type == "lead_quote" and local)
            or (biz_type == "direct_purchase" and product_context)
        )
        if sticky_relevant and str(data.get("mobile_cta_status") or "unknown").lower() == "verified" and not data.get("mobile_sticky_cta_present"):
            severity = 0.45 if data.get("mobile_primary_cta_present") else 0.72
            leaks.append(self._build_leak(
                "mobile_sticky_cta", "Absence of Mobile Sticky Call-to-Action (CTA)",
                "Primary actions exist, but no verified fixed/sticky conversion action remains accessible after mobile scrolling." if data.get("mobile_primary_cta_present") else "No verified persistent mobile conversion action was detected after scrolling.",
                "trust_conversion", biz_type, severity, "high",
                self._conversion_substitution("mobile_sticky_cta", biz_type, data, profile), competitor_verified,
                {"mobile_primary_cta_present": bool(data.get("mobile_primary_cta_present")), "mobile_sticky_cta_present": False, "cta_types": data.get("mobile_cta_types") or []}, "Rendered mobile DOM after scroll"))

        # Primary journey path. Provisional models never fail this rule.
        conversion_points, conversion_evidence = self._business_conversion_strength(data, biz_type, profile)
        if not provisional and str(data.get("mobile_cta_status") or "unknown").lower() == "verified" and conversion_points <= 0.0:
            labels = {
                "lead_quote": "No verified quote, enquiry, contact-form or equivalent qualified lead action was found.",
                "appointment_consultation": "No verified appointment, consultation, booking or equivalent customer action was found.",
                "reservation_event": "No verified reservation, event enquiry, booking or equivalent action was found.",
                "direct_purchase": "No verified Add-to-Cart, Buy, Order or checkout action was found in the inspected purchase context.",
                "demo_sales": "No verified demo, trial, sales-contact or equivalent evaluation action was found.",
                "membership_subscription": "No verified subscribe, join, membership or equivalent conversion action was found.",
                "general": "No verified primary customer action was found, but the journey model is unresolved.",
            }
            leaks.append(self._build_leak(
                "primary_conversion_path", "Primary Customer Journey Action Missing", labels.get(biz_type, labels["general"]),
                "trust_conversion", biz_type, 0.78, "high" if quality_conf == "high" else "medium", 1.0,
                competitor_verified, conversion_evidence, "Rendered customer-journey architecture"))

        # Form architecture only when a real form exists.
        ai_flags = data.get("ai_flags") if isinstance(data.get("ai_flags"), dict) else {}
        if data.get("forms_present") and data.get("form_action_valid") is False:
            leaks.append(self._build_leak(
                "form_architecture", "Broken / Unresolved Form Submission Architecture",
                "At least one rendered form lacked both a valid action target and a complete SPA-style input/submit structure.",
                "trust_conversion", biz_type, 0.82, "high", 1.0, competitor_verified,
                {"form_action_valid": False, "unlinked_forms": ai_flags.get("unlinked_forms")}, "Rendered form DOM"))

        # Explicit visible customer-path errors. The confirmation guardrail decides final score effect.
        error_signals = data.get("conversion_error_signals") or []
        if data.get("conversion_path_error_detected") and isinstance(error_signals, list) and error_signals:
            high_conf = [item for item in error_signals if isinstance(item, dict) and str(item.get("confidence") or "").lower() == "high"]
            chosen = high_conf or [x for x in error_signals if isinstance(x, dict)]
            if chosen:
                severity = max(0.50, min(1.0, max(self._safe_float(item.get("severity")) or 0.75 for item in chosen)))
                affected_urls = sorted({str(item.get("url") or "") for item in chosen if item.get("url")})[:5]
                observed = str(chosen[0].get("message") or "A public customer conversion path exposes a verified error state.")
                leaks.append(self._build_leak(
                    "conversion_path_error", "Broken Customer Conversion Path",
                    observed + " The scanner observed this passively; it did not submit a live form, make a booking, or mutate customer data.",
                    "trust_conversion", biz_type, severity, "high", 1.0, False,
                    {"error_signals": chosen[:6], "affected_urls": affected_urls, "journey_pages_verified": data.get("journey_pages_verified")},
                    "Passive multi-page journey and allow-listed booking-destination inspection"))

        # Measurement is a maturity signal. Missing common measurement stays small and is not failed on a provisional journey.
        measurement_present = data.get("measurement_layer_present")
        if measurement_present is None:
            measurement_present = bool(data.get("has_ga4") or data.get("has_meta_pixel") or data.get("has_qualitative_analytics") or data.get("has_other_measurement"))
        tracking_verified = str(data.get("tracking_evidence_status") or "").lower() == "verified" or bool(data.get("browser_loaded"))
        if not provisional and tracking_verified and not measurement_present:
            leaks.append(self._build_leak(
                "measurement_telemetry", "Common Measurement Layer Not Detected",
                "No supported common analytics/measurement platform was detected in the verified rendered/source evidence. This does not prove the business has no server-side or proprietary analytics.",
                "measurement", biz_type, 0.40, "medium", 1.0, False,
                {"measurement_platforms": data.get("measurement_platforms") or [], "measurement_layer_present": False}, "Rendered/source measurement-platform inspection"))

        # Direct-purchase checkout architecture only when checkout context is actually observed.
        if biz_type == "direct_purchase" and commerce and bool(data.get("checkout_context_detected")):
            if data.get("checkout_costs_disclosed_before_final_step") is False:
                leaks.append(self._build_leak("checkout_cost_transparency", "Late Checkout Cost Visibility", "Additional costs were not clearly disclosed before the final checkout step in the inspected checkout context.", "trust_conversion", biz_type, 0.72, "high", 1.0, False, {"checkout_costs_disclosed_before_final_step": False}, "Observed checkout content"))
            if data.get("guest_checkout_available") is False:
                leaks.append(self._build_leak("guest_checkout_barrier", "Account Creation Required Before Purchase", "The inspected checkout appears to require account creation rather than offering a verified guest path.", "trust_conversion", biz_type, 0.68, "medium", 1.0, False, {"guest_checkout_available": False}, "Observed checkout structure"))
            checkout_fields = self._safe_float(data.get("checkout_form_field_count"))
            if checkout_fields is not None and checkout_fields > 8:
                severity = min(0.90, 0.35 + (checkout_fields - 8.0) * 0.08)
                leaks.append(self._build_leak("checkout_complexity", "High Checkout Form Burden", f"The inspected checkout exposes about {int(checkout_fields)} customer-input fields. This is treated as effort, not a claim that every field is unnecessary.", "trust_conversion", biz_type, severity, "medium", 1.0, False, {"checkout_form_field_count": int(checkout_fields)}, "Observed checkout form structure"))
            if data.get("delivery_date_visible") is False:
                leaks.append(self._build_leak("delivery_expectation_clarity", "Delivery Expectation Clarity Gap", "No clear estimated-delivery or arrival-date wording was detected in the inspected checkout context.", "trust_conversion", biz_type, 0.35, "medium", 1.0, False, {"delivery_date_visible": False}, "Observed checkout content"))

        if biz_type == "direct_purchase" and str(data.get("content_signal_status") or "").lower() == "verified":
            if data.get("return_policy_linked") is False:
                leaks.append(self._build_leak("return_policy_discoverability", "Return Policy Hard to Find", "No clear return/refund policy link was detected in the verified purchase-path evidence.", "trust_conversion", biz_type, 0.45, "medium", 1.0, False, {"return_policy_linked": False}, "Verified rendered/static navigation evidence"))
            if data.get("shipping_info_linked") is False:
                leaks.append(self._build_leak("shipping_info_discoverability", "Shipping Information Hard to Find", "No clear shipping/delivery information link was detected in the verified purchase-path evidence.", "trust_conversion", biz_type, 0.35, "medium", 1.0, False, {"shipping_info_linked": False}, "Verified rendered/static navigation evidence"))

        # Considered-purchase/demo journeys can legitimately hide pricing, so this remains modest/medium confidence.
        if enterprise and biz_type == "demo_sales" and str(data.get("content_signal_status") or "").lower() == "verified" and data.get("pricing_linked") is False:
            leaks.append(self._build_leak(
                "b2b_pricing_transparency", "Commercial Context / Pricing Path Gap",
                "No clear pricing, plans, packages, budget guidance, or commercial-context path was detected in the verified evaluation journey. Quote-only pricing may still be legitimate.",
                "trust_conversion", biz_type, 0.42, "medium", 1.0, False, {"pricing_linked": False}, "Verified evaluation/navigation evidence"))

        # Form length is a conservative friction heuristic for form-led journeys.
        if biz_type in {"lead_quote", "appointment_consultation", "reservation_event", "demo_sales", "membership_subscription"} and data.get("forms_present") and data.get("form_action_valid") is not False:
            max_fields = self._safe_float(data.get("form_max_field_count"))
            if max_fields is not None and max_fields > 8:
                severity = min(0.80, 0.30 + (max_fields - 8.0) * 0.07)
                leaks.append(self._build_leak(
                    "lead_form_friction", "High Lead / Enquiry Form Effort",
                    f"At least one customer form exposes about {int(max_fields)} input fields, increasing completion effort on the observed journey.",
                    "trust_conversion", biz_type, severity, "medium", 1.0, False,
                    {"form_max_field_count": int(max_fields), "form_max_required_field_count": data.get("form_max_required_field_count")}, "Rendered form structure"))

        # Low-value common presentation/accessibility signals remain visible and score lightly.
        h1_status = str(data.get("h1_status") or "unknown").lower()
        h1_tags = data.get("h1_tags") if isinstance(data.get("h1_tags"), list) else []
        if h1_status == "missing":
            leaks.append(self._build_leak("diluted_h1", "Missing Primary H1 / Hero Semantic Anchor", "No primary H1 heading was detected in the rendered document.", "content_eeat", biz_type, 0.45, "high", 1.0, False, {"h1_tags": h1_tags}, "Rendered DOM"))
        elif h1_status == "present" and len(h1_tags) > 1:
            leaks.append(self._build_leak("diluted_h1", "Multiple Primary H1 Signals", f"{len(h1_tags)} rendered H1 elements were detected; review whether the hero hierarchy is intentional.", "content_eeat", biz_type, 0.25, "high", 1.0, False, {"h1_tags": h1_tags}, "Rendered DOM"))

        total_images = self._safe_int(data.get("total_images"), self._safe_int(data.get("image_count"), 0)) or 0
        missing_alt = self._safe_int(data.get("missing_alt_images"), 0) or 0
        if data.get("browser_loaded") and total_images > 0 and missing_alt > 0:
            ratio = missing_alt / max(1, total_images)
            severity = 0.20 if ratio < 0.30 else (0.38 if ratio < 0.75 else 0.55)
            leaks.append(self._build_leak("missing_alt_images", "Missing Image Accessibility Text", f"{missing_alt} of {total_images} rendered images lacked alt/WAI-ARIA accessibility treatment.", "content_eeat", biz_type, severity, "high", 1.0, False, {"missing_alt_images": missing_alt, "total_images": total_images}, "Rendered DOM"))

        ai_pct = self._safe_float(data.get("ai_spectrum_pct"))
        if data.get("ai_spectrum_status") == "heuristic" and ai_pct is not None and ai_pct > 60:
            severity = min(0.55, max(0.18, (ai_pct - 60.0) / 80.0))
            leaks.append(self._build_leak("ai_template_similarity", "High AI / Template Pattern Spectrum", f"Template-pattern heuristic measured {ai_pct:.1f}/100. This is a sameness/pattern index, not proof of AI authorship.", "content_eeat", biz_type, severity, "medium", 1.0, False, {"ai_template_pattern_index": ai_pct, "ai_flags": ai_flags}, "Rendered DOM/template heuristic"))

        return leaks

    def _checkpoint_failure_leaks(
        self,
        checkpoints: List[Dict[str, Any]],
        existing_leaks: List[Dict[str, Any]],
        biz_type: str,
    ) -> List[Dict[str, Any]]:
        """Promote verified checkpoint failures without duplicating dedicated rules."""
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
            category_multiplier = CATEGORY_WEIGHTS_BY_BIZ.get(biz_type, CATEGORY_WEIGHTS_BY_BIZ["general"]).get(category, 1.0)
            matrix = BUSINESS_MODEL_MATRIX.get(biz_type, BUSINESS_MODEL_MATRIX["general"])
            business_multiplier = {
                "trust_conversion": matrix["conversion"], "seo_technical": matrix["seo"],
                "content_eeat": matrix["trust"], "measurement": matrix["measurement"],
            }.get(category, 1.0)
            research_multiplier = _research_multiplier(rule_key, biz_type)
            pre_dedupe = base_weight * category_multiplier * business_multiplier * severity * research_multiplier
            title, impact = self._checkpoint_failure_copy(checkpoint)
            promoted.append({
                "rule_key": rule_key, "family": str(checkpoint.get("family") or rule_key),
                "checkpoint_id": checkpoint.get("id"), "checkpoint_name": checkpoint.get("check"),
                "analysis_layer": checkpoint.get("analysis_layer") or "adaptive_architecture",
                "title": title, "description": impact, "category": category,
                "base_impact_weight": round(base_weight, 2), "category_multiplier": round(category_multiplier, 3),
                "business_multiplier": round(business_multiplier, 3), "research_multiplier": round(research_multiplier, 3),
                "research_basis": _research_basis(rule_key), "severity_factor": round(severity, 2),
                "confidence": "high", "confidence_multiplier": 1.0, "substitution_factor": 1.0,
                "competitor_advantage_bonus": 0.0, "intrinsic_severity_score": round(pre_dedupe, 2), "economic_severity": round(pre_dedupe, 2),
                "pre_dedupe_penalty": round(pre_dedupe, 2),
                "family_adjustment": 1.0, "final_score_loss": round(pre_dedupe, 2), "score_impact_points": round(pre_dedupe, 2), "final_severity_score": round(pre_dedupe, 2),
                "evidence": {"checkpoint_id": checkpoint.get("id"), "checkpoint": checkpoint.get("check"), "evidence": checkpoint.get("evidence")},
                "source": "Verified 50-point checkpoint evidence",
            })
            existing_rules.add(rule_key)
        return promoted

    @staticmethod
    def _checkpoint_failure_copy(checkpoint: Dict[str, Any]) -> Tuple[str, str]:
        rule_key = str(checkpoint.get("rule_key") or "")
        name = str(checkpoint.get("check") or "Verified checkpoint failure")
        evidence = checkpoint.get("evidence") if isinstance(checkpoint.get("evidence"), dict) else {}
        if rule_key == "privacy_terms_missing":
            if evidence.get("requirement") == "privacy_only":
                return ("Privacy Policy Trust Gap", "A Privacy policy link was not detected even though the verified site context collects data or operates in a sensitive professional/healthcare context. Terms are not being required by this finding.")
            return ("Policy Trust Gap", "Privacy and Terms links were not both detected where transaction/account or checkout context makes both policies applicable.")
        copy_map = {
            "https_redirect": ("HTTPS Redirect Gap", "The secure site is available, but HTTP-to-HTTPS enforcement was not verified as correctly implemented."),
            "retargeting_telemetry": ("Retargeting Measurement Gap", "No verified retargeting/marketing pixel signal was found, limiting campaign attribution and remarketing readiness."),
            "phone_visibility": ("Phone Visibility Gap", "A visible phone contact signal was not detected even though the page was successfully inspected."),
            "location_visibility": ("Location Confidence Gap", "The page did not expose a clear address/location signal, which can weaken local intent and trust."),
            "trust_credentials": ("Credential / Trust Signal Gap", "No clear credential, certification, secure-purchase or comparable trust signal was detected."),
            "reviews_social_proof": ("Review Proof Gap", "No clear testimonial/review proof was detected in the inspected page evidence."),
            "guarantee_refund_clarity": ("Guarantee / Refund Clarity Gap", "A relevant guarantee/refund reassurance signal was not found for this customer journey/context."),
            "about_team_signal": ("Identity / About Signal Gap", "No clear About/Team identity path was detected, reducing business transparency."),
            "social_proof_signal": ("Social Proof Gap", "The inspected page did not expose a strong review, credential or comparable proof signal."),
            "instant_query_channel": ("Instant Query Channel Gap", "No live-chat or WhatsApp-style instant query option was detected."),
            "meta_description_missing": ("Missing Search Description", "The page did not expose a meta description, weakening search-result message control."),
            "meta_description_length": ("Search Description Length Outlier", "The verified meta description falls outside the scanner's broad readability/snippet heuristic range; this is not treated as an exact ranking cutoff."),
            "h1_topic_relevance": ("Hero Topic Relevance Gap", "The verified H1 does not strongly support the inferred primary topic/value proposition."),
            "title_length": ("Title Tag Length Outlier", "The verified title falls outside the scanner's broad title-length heuristic range; this is not treated as an exact ranking cutoff."),
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
            "thin_visible_content": ("Thin Visible Content Depth", "The verified visible page content is below the scanner's minimum depth threshold for this customer journey/context."),
            "generic_headline": ("Generic Template Headline", "The verified headline language matched generic/template-style phrasing that can weaken differentiation."),
            "unlinked_form_structure": ("Structurally Unlinked Form", "A verified form lacks a complete action or SPA-style submission structure."),
            "faq_missing": ("FAQ / Objection-Handling Gap", "No FAQ-style objection-handling section was detected where it is relevant to the verified customer journey/context."),
            "case_studies_missing": ("Proof-of-Work Gap", "No case-study/portfolio proof path was detected for a journey/context where proof-of-work is commercially relevant."),
            "content_hub_missing": ("Content Authority Gap", "No blog/content-hub path was detected for a model where ongoing expertise content is relevant."),
            "social_links_missing": ("Social Identity Link Gap", "No verified outbound social-profile links were detected."),
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
        category_multiplier = CATEGORY_WEIGHTS_BY_BIZ.get(biz_type, CATEGORY_WEIGHTS_BY_BIZ["general"]).get(category, 1.0)
        matrix = BUSINESS_MODEL_MATRIX.get(biz_type, BUSINESS_MODEL_MATRIX["general"])
        business_multiplier = {
            "trust_conversion": matrix["conversion"], "seo_technical": matrix["seo"],
            "content_eeat": matrix["trust"], "measurement": matrix["measurement"],
        }.get(category, 1.0)
        research_multiplier = _research_multiplier(rule_key, biz_type)
        weighted = base_weight * category_multiplier * business_multiplier * research_multiplier
        competitor_bonus = 1.0 if competitor_verified and rule_key in {"click_to_call", "mobile_sticky_cta", "core_web_vitals", "form_architecture", "primary_conversion_path"} else 0.0
        intrinsic_impact = (weighted * severity * substitution) + (competitor_bonus * severity)
        pre_dedupe = intrinsic_impact * conf_mult
        common_rule_keys = {"unsecured_ssl", "core_web_vitals", "diluted_h1", "missing_alt_images", "favicon_present", "html_lang_attribute"}
        return {
            "rule_key": rule_key, "family": LEAK_FAMILY.get(rule_key, rule_key),
            "analysis_layer": "common_foundation" if rule_key in common_rule_keys else "adaptive_architecture",
            "title": title, "description": description, "category": category,
            "base_impact_weight": round(base_weight, 2), "category_multiplier": round(category_multiplier, 3),
            "business_multiplier": round(business_multiplier, 3), "research_multiplier": round(research_multiplier, 3),
            "research_basis": _research_basis(rule_key), "severity_factor": round(severity, 2),
            "confidence": confidence_key, "confidence_multiplier": conf_mult, "substitution_factor": round(substitution, 3),
            "competitor_advantage_bonus": round(competitor_bonus, 2),
            "intrinsic_severity_score": round(intrinsic_impact, 2), "economic_severity": round(intrinsic_impact, 2),
            "pre_dedupe_penalty": round(pre_dedupe, 2),
            "family_adjustment": 1.0, "final_score_loss": round(pre_dedupe, 2), "score_impact_points": round(pre_dedupe, 2),
            "final_severity_score": round(intrinsic_impact, 2),
            "evidence": evidence, "source": source,
        }

    def _apply_high_impact_confirmation_guardrail(
        self,
        leaks: List[Dict[str, Any]],
        scan_data: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Require independent support for severe deductions.

        CONFIRMED = full score effect.
        CORROBORATED = exact signal independently supported but not fully browser-reproduced; 55% score effect.
        DISPUTED/UNCONFIRMED = zero score effect and retained as transparent observation only.
        """
        confirmation = scan_data.get("high_impact_confirmation") if isinstance(scan_data, dict) else {}
        if not isinstance(confirmation, dict) or not confirmation.get("completed"):
            return leaks, []
        threshold = self._safe_float(confirmation.get("threshold_points")) or 3.5
        result_map = confirmation.get("results") if isinstance(confirmation.get("results"), dict) else {}
        kept: List[Dict[str, Any]] = []
        unscored: List[Dict[str, Any]] = []
        for leak in leaks:
            potential = self._safe_float(leak.get("pre_dedupe_penalty"))
            if potential is None:
                potential = self._safe_float(leak.get("final_score_loss")) or 0.0
            rule = str(leak.get("rule_key") or "")
            if potential < threshold:
                kept.append(leak); continue
            record = result_map.get(rule) if isinstance(result_map.get(rule), dict) else {}
            status = str(record.get("status") or "UNCONFIRMED").upper()
            if status == "CONFIRMED":
                leak["confirmation"] = dict(record); kept.append(leak); continue
            if status == "CORROBORATED":
                factor = 0.55
                leak["confirmation"] = dict(record)
                leak["confirmation_score_factor"] = factor
                leak["pre_dedupe_penalty"] = round(float(potential) * factor, 2)
                leak["final_score_loss"] = round(float(leak.get("final_score_loss") or potential) * factor, 2)
                leak["score_impact_points"] = leak["final_score_loss"]
                leak["confidence"] = "medium"
                leak["confidence_multiplier"] = CONFIDENCE_MULTIPLIERS["medium"]
                leak["description"] = str(leak.get("description") or "") + " The exact public signal was independently corroborated, but not fully reproduced in the rendered confirmation pass; the score effect is intentionally reduced."
                kept.append(leak); continue
            unscored.append({
                "rule_key": rule, "title": leak.get("title"), "potential_pre_dedupe_points": round(float(potential), 2),
                "status": status, "confirmation": dict(record), "evidence": leak.get("evidence") or {}, "source": leak.get("source"),
                "score_effect": 0.0,
                "customer_note": "This first-pass signal could have produced a large deduction, but independent confirmation was insufficient or contradictory. It is therefore UNKNOWN/unscored.",
            })
        return kept, unscored

    def _apply_layer_penalty_caps(self, leaks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Cap the combined low-level foundation burden without hiding individual findings.

        The findings remain visible at their original evidence/severity. Only their aggregate score
        contribution is proportionally compressed when common technical/SEO issues would otherwise
        overwhelm the adaptive revenue architecture.
        """
        common = [x for x in leaks if x.get("analysis_layer") == "common_foundation"]
        raw = sum(float(x.get("final_score_loss") or 0.0) for x in common)
        if raw <= COMMON_FOUNDATION_PENALTY_CAP or raw <= 0:
            return leaks, []
        factor = COMMON_FOUNDATION_PENALTY_CAP / raw
        adjustments: List[Dict[str, Any]] = []
        for leak in common:
            before = float(leak.get("final_score_loss") or 0.0)
            after = round(before * factor, 2)
            leak["layer_penalty_adjustment"] = round(factor, 4)
            leak["final_score_loss"] = after
            leak["final_severity_score"] = after
        adjustments.append({
            "type": "common_foundation_penalty_cap",
            "raw_common_penalty": round(raw, 2),
            "capped_common_penalty": COMMON_FOUNDATION_PENALTY_CAP,
            "proportional_factor": round(factor, 4),
            "note": "Common technical/SEO issues remain visible but their combined Revenue Readiness deduction is capped so they cannot outweigh verified customer-journey architecture.",
        })
        return leaks, adjustments

    def _attach_evidence_receipts(self, leaks: List[Dict[str, Any]], scan_data: Dict[str, Any]) -> None:
        scan_time = str(scan_data.get("scan_completed_at") or scan_data.get("scan_started_at") or "")
        primary_url = str(scan_data.get("final_url") or scan_data.get("url") or scan_data.get("domain") or "")
        browser_journey = scan_data.get("browser_journey_probe") if isinstance(scan_data.get("browser_journey_probe"), dict) else {}
        screenshot_url = str(browser_journey.get("url") or "")
        screenshot_b64 = str(browser_journey.get("evidence_screenshot_b64") or "")
        screenshot_mime = str(browser_journey.get("evidence_screenshot_mime") or "")
        screenshot_sha = str(browser_journey.get("evidence_screenshot_sha256") or "")

        for leak in leaks:
            evidence = leak.get("evidence") if isinstance(leak.get("evidence"), dict) else {}
            error_signals = evidence.get("error_signals") if isinstance(evidence.get("error_signals"), list) else []
            first_error = next((x for x in error_signals if isinstance(x, dict)), {})
            affected = evidence.get("affected_urls") if isinstance(evidence.get("affected_urls"), list) else []
            evidence_url = str(
                first_error.get("url")
                or (affected[0] if affected else "")
                or evidence.get("final_url")
                or evidence.get("url")
                or primary_url
            )
            if first_error:
                observed = str(first_error.get("observed_text") or first_error.get("message") or "")[:360]
                method = str(first_error.get("evidence_surface") or leak.get("source") or "public evidence inspection")
            else:
                # Keep a compact, explainable evidence excerpt rather than dumping the whole telemetry object.
                preferred_keys = (
                    "performance_score", "crux_grade", "crux_lcp_ms", "crux_inp_ms", "crux_cls",
                    "form_action_valid", "form_max_field_count", "mobile_cta_types", "mobile_sticky_cta_present",
                    "click_to_call_present", "privacy_policy_linked", "terms_linked", "credential_signal_types",
                    "detected_phone_numbers", "ai_template_pattern_index", "checkpoint", "checkpoint_id",
                )
                compact = {k: evidence.get(k) for k in preferred_keys if k in evidence and evidence.get(k) not in (None, [], "")}
                if not compact:
                    compact = {k: v for k, v in list(evidence.items())[:5] if v not in (None, [], "")}
                try:
                    observed = json.dumps(compact, ensure_ascii=False, default=str)[:360]
                except Exception:
                    observed = str(compact)[:360]
                method = str(leak.get("source") or "public evidence inspection")

            receipt = {
                "rule_key": leak.get("rule_key"),
                "url": evidence_url,
                "observed_signal": observed,
                "observed_at": scan_time,
                "collection_method": method,
                "confidence": leak.get("confidence", "unknown"),
                "confirmation": leak.get("confirmation") or {},
                "evidence_hash": hashlib.sha256(
                    (str(leak.get("rule_key")) + "|" + evidence_url + "|" + observed + "|" + scan_time).encode("utf-8", errors="ignore")
                ).hexdigest(),
                "screenshot_available": False,
            }
            if screenshot_b64 and screenshot_url and evidence_url and screenshot_url.rstrip("/") == evidence_url.rstrip("/"):
                receipt.update({
                    "screenshot_available": True,
                    "screenshot_mime": screenshot_mime or "image/jpeg",
                    "screenshot_sha256": screenshot_sha,
                    "screenshot_data_uri": f"data:{screenshot_mime or 'image/jpeg'};base64,{screenshot_b64}",
                })
            leak["evidence_receipt"] = receipt

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

            cap = FAMILY_SCORE_CAPS.get(family)
            if cap is not None and after > cap and after > 0:
                scale = float(cap) / after
                after = 0.0
                for leak in ordered:
                    capped = round(float(leak.get("final_score_loss") or 0.0) * scale, 2)
                    leak["family_adjustment"] = round(float(leak.get("family_adjustment") or 1.0) * scale, 4)
                    leak["final_score_loss"] = capped
                    leak["final_severity_score"] = capped
                    after += capped
                after = round(after, 2)

            if round(before - after, 2) > 0:
                adjustments.append(
                    {
                        "family": family,
                        "pre_dedupe_total": round(before, 2),
                        "post_dedupe_total": round(after, 2),
                        "overlap_reduction": round(before - after, 2),
                        "rules": [item.get("rule_key") for item in ordered],
                    }
                )

        # Cross-family cap for ordinary SEO/discovery hygiene. This is applied
        # after the family-level caps so numerous small SEO issues cannot add up
        # to a larger penalty than a verified checkout/form/performance blocker.
        seo_items = [
            leak for leak in leaks
            if str(leak.get("family") or "") in SEO_HYGIENE_FAMILIES
        ]
        seo_total = round(sum(float(x.get("final_score_loss") or 0.0) for x in seo_items), 2)
        if seo_total > SEO_HYGIENE_TOTAL_CAP and seo_total > 0:
            scale = SEO_HYGIENE_TOTAL_CAP / seo_total
            for leak in seo_items:
                capped = round(float(leak.get("final_score_loss") or 0.0) * scale, 2)
                leak["family_adjustment"] = round(float(leak.get("family_adjustment") or 1.0) * scale, 4)
                leak["final_score_loss"] = capped
                leak["final_severity_score"] = capped
            adjustments.append(
                {
                    "family": "seo_hygiene_total",
                    "pre_dedupe_total": seo_total,
                    "post_dedupe_total": round(sum(float(x.get("final_score_loss") or 0.0) for x in seo_items), 2),
                    "overlap_reduction": round(seo_total - sum(float(x.get("final_score_loss") or 0.0) for x in seo_items), 2),
                    "rules": [x.get("rule_key") for x in seo_items],
                }
            )

        return leaks, adjustments

    @staticmethod
    def _commercial_sort_key(leak: Dict[str, Any]) -> tuple:
        family = str(leak.get("family") or leak.get("rule_key") or "")
        priority = float(leak.get("commercial_priority") or COMMERCIAL_PRIORITY_BY_FAMILY.get(family, 2.5))
        loss = float(leak.get("final_score_loss") or 0.0)
        severity = float(leak.get("severity_factor") or 0.0)
        # The evidence-weighted score loss is the primary ranking signal.
        # Commercial family priority is a tie-breaker, not an override that can
        # place a tiny cosmetic issue above a much larger verified revenue risk.
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
            intrinsic_total = round(sum(float(x.get("economic_severity") or x.get("intrinsic_severity_score") or 0.0) for x in ordered), 2)
            primary["final_score_loss"] = family_total
            primary["score_impact_points"] = family_total
            primary["economic_severity"] = intrinsic_total
            primary["intrinsic_severity_score"] = intrinsic_total
            primary["final_severity_score"] = intrinsic_total
            primary["severity_score"] = intrinsic_total
            # Keep the public/report family stable (e.g. "performance") while separately
            # recording the broader deduplication superfamily used to collapse supporting signals.
            original_family = str(ordered[0].get("family") or superfamily)
            primary["family"] = original_family
            primary["dedup_superfamily"] = superfamily
            primary["commercial_priority"] = COMMERCIAL_PRIORITY_BY_FAMILY.get(
                original_family,
                COMMERCIAL_PRIORITY_BY_FAMILY.get(superfamily, 2.5),
            )
            if len(ordered) > 1 and superfamily in CONSOLIDATED_FAMILY_LABELS:
                label = CONSOLIDATED_FAMILY_LABELS[superfamily]
                if superfamily == "trust_proof":
                    rules = {str(x.get("rule_key") or "") for x in ordered}
                    credential_failed = "trust_credentials" in rules
                    social_failed = bool(rules & {"reviews_social_proof", "social_proof_signal", "case_studies_missing"})
                    if credential_failed and not social_failed:
                        label = "Professional Credential / Trust Signal Gap"
                    elif social_failed and not credential_failed:
                        label = "Review / Social Proof Gap"
                primary["title"] = label
                primary["leak_name"] = label
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
        primary = bool(data.get("mobile_primary_cta_present"))
        cart = bool(data.get("add_to_cart_visible"))
        chat = bool(data.get("live_chat_present") or data.get("whatsapp_present"))
        if rule_key == "click_to_call":
            if biz_type in {"direct_purchase", "membership_subscription"} and (cart or primary):
                return 0.20
            if biz_type == "demo_sales" and (primary or chat):
                return 0.35
            if context_has(profile, "local_location_dependent") and biz_type in {"lead_quote", "appointment_consultation", "reservation_event"}:
                return 1.0
            return 0.50 if (primary or chat) else 0.70
        if rule_key == "mobile_sticky_cta":
            if primary:
                return 0.75 if biz_type in {"reservation_event", "direct_purchase", "appointment_consultation"} else 0.80
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
            "analysis_layer": leak.get("analysis_layer") or "adaptive_architecture",
            "severity_score": float(leak.get("intrinsic_severity_score") or leak.get("final_severity_score") or 0.0),
            "intrinsic_severity_score": leak.get("intrinsic_severity_score"),
            "economic_severity": leak.get("economic_severity"),
            "score_impact_points": leak.get("final_score_loss"),
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
            "research_multiplier": leak.get("research_multiplier"),
            "research_basis": leak.get("research_basis") or {},
            "confidence_multiplier": leak.get("confidence_multiplier"),
            "substitution_factor": leak.get("substitution_factor"),
            "competitor_advantage_bonus": leak.get("competitor_advantage_bonus"),
            "pre_dedupe_penalty": leak.get("pre_dedupe_penalty"),
            "family_adjustment": leak.get("family_adjustment"),
            "final_score_loss": leak.get("final_score_loss"),
            "commercial_priority": leak.get("commercial_priority", COMMERCIAL_PRIORITY_BY_FAMILY.get(str(leak.get("family") or ""), 2.5)),
            "supporting_rule_keys": leak.get("supporting_rule_keys") or [leak.get("rule_key")],
            "supporting_findings": leak.get("supporting_findings") or [],
            "evidence_receipt": leak.get("evidence_receipt") or {},
            "confirmation": leak.get("confirmation") or {},
        }

    @staticmethod
    def _ledger_row(leak: Dict[str, Any]) -> Dict[str, Any]:
        keys = (
            "rule_key",
            "family",
            "analysis_layer",
            "base_impact_weight",
            "category_multiplier",
            "business_multiplier",
            "research_multiplier",
            "research_basis",
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
            "confirmation",
            "evidence_receipt",
        )
        return {key: leak.get(key) for key in keys}

    @staticmethod
    def _apply_readiness_ceiling(raw_score: float) -> float:
        """Compatibility helper: the three-layer model already has a natural 0-100 ceiling."""
        return max(0.0, min(MAX_REVENUE_READINESS_SCORE, float(raw_score)))

    @staticmethod
    def _get_score_rating(
        score: float,
        evidence_confidence: Dict[str, Any] | None = None,
        total_loss: float = 0.0,
        cp_summary: Dict[str, Any] | None = None,
        maturity_gate: Dict[str, Any] | None = None,
    ) -> str:
        maturity_gate = maturity_gate or {}
        if bool(maturity_gate.get("journey_provisional")):
            return "PROVISIONAL READINESS — CUSTOMER JOURNEY NOT YET RESOLVED"
        if score >= 90:
            return "ELITE VERIFIED REVENUE ARCHITECTURE"
        if score >= 80:
            return "EXCEPTIONAL VERIFIED WEBSITE READINESS"
        if score >= 70:
            return "STRONG REVENUE ARCHITECTURE"
        if score >= 55:
            return "FUNCTIONAL FOUNDATION — MATERIAL COMMERCIAL HEADROOM"
        if score >= 40:
            return "MATERIAL REVENUE / EXPERIENCE WEAKNESSES"
        if score >= 25:
            return "SIGNIFICANT STRUCTURAL / CONVERSION RISK"
        return "CRITICAL REVENUE ARCHITECTURE WEAKNESS"

    def _get_vault_id(self, score: float) -> str:
        if score >= 77:
            return self.generate_tier_id(10)
        if score >= 72:
            return self.generate_tier_id(8)
        if score >= 50:
            return self.generate_tier_id(4)
        return self.generate_tier_id(4)

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
    def _revenue_exposure(
        biz_type: str,
        leaks: List[Dict[str, Any]],
        evidence_confidence: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Model plausible financial exposure independently from score deductions.

        Economic magnitude uses intrinsic verified issue severity + journey economics.
        Evidence confidence changes the confidence label/range width, not the website's
        intrinsic issue severity.  No claim of measured loss is made without business data.
        """
        items = [x for x in (leaks or []) if isinstance(x, dict)]
        economic_units = 0.0
        confidence_weighted = 0.0
        conf_map = {"high": 1.0, "medium": 0.65, "low": 0.35, "unknown": 0.0}
        for leak in items:
            intrinsic = float(leak.get("economic_severity") or leak.get("intrinsic_severity_score") or 0.0)
            if intrinsic <= 0:
                sev = max(0.0, min(1.0, float(leak.get("severity_factor") or 0.0)))
                base = max(0.0, float(leak.get("base_impact_weight") or 0.0))
                intrinsic = sev * base
            # Bound one issue so a single heuristic cannot dominate the whole model.
            intrinsic = min(12.0, max(0.0, intrinsic))
            economic_units += intrinsic
            confidence_weighted += intrinsic * conf_map.get(str(leak.get("confidence") or "unknown").lower(), 0.0)
        economic_units = min(28.0, economic_units)
        issue_conf = (confidence_weighted / economic_units) if economic_units > 0 else 0.0
        scan_conf = float((evidence_confidence or {}).get("score") or 0.0) / 100.0
        combined_conf = max(0.0, min(1.0, issue_conf * 0.75 + scan_conf * 0.25)) if economic_units else 0.0

        # Journey-specific economics represent relative customer-value/transaction stakes,
        # not claimed client revenue.  High-ticket lead/demo journeys therefore produce
        # materially different ranges from low-value/general sites for the same architecture issue.
        unit_ranges = {
            "general": (700.0, 2200.0),
            "lead_quote": (1800.0, 6000.0),
            "appointment_consultation": (1300.0, 4200.0),
            "reservation_event": (900.0, 3000.0),
            "direct_purchase": (1400.0, 4500.0),
            "demo_sales": (2200.0, 7500.0),
            "membership_subscription": (800.0, 2600.0),
        }
        low_unit, high_unit = unit_ranges.get(biz_type, unit_ranges["general"])
        # Confidence narrows/lowers the floor but does not erase the plausible upper economic
        # magnitude simply because public telemetry is incomplete.
        lower_factor = 0.30 + 0.70 * combined_conf
        upper_factor = 0.70 + 0.30 * combined_conf
        annual_min = int(round((economic_units * low_unit * lower_factor) / 100.0) * 100)
        annual_max = int(round((economic_units * high_unit * upper_factor) / 100.0) * 100)
        annual_max = max(annual_max, annual_min)
        if economic_units <= 0.10:
            level = "VERY LOW"
        elif economic_units <= 2.0:
            level = "LOW"
        elif economic_units <= 5.0:
            level = "MODERATE"
        elif economic_units <= 10.0:
            level = "HIGH"
        else:
            level = "VERY HIGH"
        confidence_label = "HIGH" if combined_conf >= 0.80 else ("MODERATE" if combined_conf >= 0.55 else ("LOW" if combined_conf > 0 else "NONE"))
        range_text = f"${annual_min:,} – ${annual_max:,} / year"
        return {
            "level": level, "min": annual_min, "max": annual_max, "range": range_text,
            "economic_severity_basis": round(economic_units, 2),
            "verified_penalty_basis": round(sum(float(x.get("final_score_loss") or 0.0) for x in items), 2),
            "confidence": confidence_label, "confidence_score": round(combined_conf * 100.0, 1),
            "display": f"{range_text} — {level} model-based exposure",
            "method_note": (
                "Model-based potential exposure derived from intrinsic verified issue severity and journey-specific economic stakes, "
                "not from the final score deduction. Evidence confidence controls the confidence/range calibration separately. "
                "This is not measured accounting loss, a traffic forecast, or proof that remediation will produce this amount."
            ),
        }

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            parsed = float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
        if parsed is None or not math.isfinite(parsed):
            return None
        return parsed

    @staticmethod
    def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
        parsed = RevenueScorer._safe_float(value)
        return int(parsed) if parsed is not None else default
