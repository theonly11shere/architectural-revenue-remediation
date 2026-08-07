import secrets
import string
import math
from typing import Dict, Any, List
from behavioural_engine import BehaviouralEngine

# 1. Dynamic Category Weight Matrix per Vertical
CATEGORY_WEIGHTS_BY_BIZ = {
    "general":   {"seo_technical": 1.15, "trust_conversion": 1.10, "content_eeat": 1.00},
    "medspa":    {"seo_technical": 1.00, "trust_conversion": 1.40, "content_eeat": 1.25},
    "legal":     {"seo_technical": 1.05, "trust_conversion": 1.45, "content_eeat": 1.30},
    "ecommerce": {"seo_technical": 1.40, "trust_conversion": 1.20, "content_eeat": 0.90},
    "saas":      {"seo_technical": 1.30, "trust_conversion": 1.15, "content_eeat": 1.10}
}

# 2. Business Model Multipliers Matrix
BUSINESS_MODEL_MATRIX = {
    "general":   {"trust": 1.2, "conversion": 1.2, "seo": 1.2},
    "medspa":    {"trust": 1.5, "conversion": 1.5, "seo": 1.1},
    "legal":     {"trust": 1.6, "conversion": 1.4, "seo": 1.1},
    "ecommerce": {"trust": 1.4, "conversion": 1.3, "seo": 1.4},
    "saas":      {"trust": 1.4, "conversion": 1.1, "seo": 1.3}
}

# 3. Dynamic Check Base Weights Matrix by Business Type (1 to 10 Scale)
RULE_BASE_WEIGHTS = {
    "unsecured_ssl": {
        "general": 9, "medspa": 10, "legal": 10, "ecommerce": 10, "saas": 10
    },
    "core_web_vitals": {
        "general": 8, "medspa": 6, "legal": 5, "ecommerce": 10, "saas": 9
    },
    "click_to_call": {
        "general": 5, "medspa": 10, "legal": 10, "ecommerce": 3, "saas": 2
    },
    "mobile_sticky_cta": {
        "general": 5, "medspa": 9, "legal": 8, "ecommerce": 9, "saas": 7
    },
    "diluted_h1": {
        "general": 6, "medspa": 7, "legal": 8, "ecommerce": 6, "saas": 9
    },
    "missing_alt_images": {
        "general": 5, "medspa": 6, "legal": 4, "ecommerce": 8, "saas": 4
    },
    "ai_template_similarity": {
        "general": 5, "medspa": 8, "legal": 9, "ecommerce": 5, "saas": 7
    }
}

# 4. Vertical Financial Leak Multipliers (Est. Annual Value lost per score gap point)
REVENUE_LEAK_MULTIPLIERS = {
    "general":   {"min": 350, "max": 700},
    "medspa":    {"min": 850, "max": 1800},
    "legal":     {"min": 1200, "max": 2500},
    "ecommerce": {"min": 500, "max": 1100},
    "saas":      {"min": 600, "max": 1400}
}

# 5. Tier ID Prefix Strategy
TIER_PREFIXES = {
    3: "IFYB3",
    6: "MBTB6",
    8: "NOLY8",
    10: "ARCH10"
}


class RevenueScorer:
    """
    Trilloka Harsh Revenue Diagnostic Scorer:
    Combines hybrid scan data, behavioral engine heuristics, weighted severity index,
    and business vertical matrices to calculate financial leaks.
    """

    def __init__(self):
        self.behavioral_engine = BehaviouralEngine()

    def _normalize_business_type(self, raw_biz_type: str) -> str:
        """Normalizes frontend dropdown strings to internal keys."""
        val = str(raw_biz_type).lower()
        if "medspa" in val or "aesthetics" in val:
            return "medspa"
        elif "legal" in val or "law" in val:
            return "legal"
        elif "e-commerce" in val or "ecommerce" in val or "store" in val:
            return "ecommerce"
        elif "saas" in val or "software" in val:
            return "saas"
        else:
            return "general"

    def generate_tier_id(self, tier_level: int) -> str:
        """Generates structured IDs like ARCH10-X79B2P."""
        prefix = TIER_PREFIXES.get(tier_level, "IFYB3")
        rand_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        return f"{prefix}-{rand_str}"

    def audit_and_score(self, scan_data: Dict[str, Any], business_type: str = "general", competitor_data_present: bool = True) -> Dict[str, Any]:
        """Runs the complete harsh scoring pipeline with vertical-aware formulas."""
        biz_type = self._normalize_business_type(business_type)

        # Step 1: Execute Behavioral Engine Diagnostics
        behavioral_insights = self.behavioral_engine.analyze_behavioral_friction(scan_data, biz_type)

        # Step 2: Evaluate Failed Checkpoints & Generate Contextual Weighted Severity Scores
        detected_leaks = self._evaluate_checkpoints(scan_data, biz_type, competitor_data_present)

        # Step 3: Calculate Dynamic AI Spectrum Penalty based on Business Type
        ai_spectrum_pct = scan_data.get("ai_spectrum_pct", 0.0)

        # Check ALL common text keys your scraper might be using
        raw_page_text = str(
            scan_data.get("page_text") or 
            scan_data.get("raw_text") or 
            scan_data.get("text_content") or 
            scan_data.get("content") or 
            ""
        ).strip()

        # ADJUSTED FALLBACK: If the scraper completely failed to extract text, 
        # cap the fallback profile default at 45.0% instead of 65.0%.
        if ai_spectrum_pct == 0.0 and len(raw_page_text) < 50:
            ai_spectrum_pct = 45.0 
            
        ai_severity_mult = 1.5 if biz_type in ["medspa", "legal"] else 1.0

        ai_penalty = min(25.0, (ai_spectrum_pct / 100.0) * 20.0 * ai_severity_mult) if ai_spectrum_pct > 40.0 else 0.0

        # Step 4: Calculate Harsh Overall Health Score
        total_severity_loss = sum(leak["final_severity_score"] for leak in detected_leaks)
        
        raw_score = 100.0 - (total_severity_loss * 1.15) - ai_penalty
        
        # HARSH CLAMPING LOGIC: If a business has 3 or more financial leaks,
        # they lose the privilege of a "passing" score. Force clamp into 35-50% range.
        if len(detected_leaks) >= 3:
            harsh_overall_score = max(35.0, min(49.5, round(raw_score, 1)))
        else:
            harsh_overall_score = max(12.0, min(96.0, round(raw_score, 1)))

        # Step 5: Calculate Surface Metrics
        perf_score = scan_data.get("performance_score", 65.0)
        seo_score = scan_data.get("google_seo_score", 65.0)

        surface_metrics = {
            "mobile_performance_score": round(perf_score),
            "seo_health_index": round(seo_score),
            "ai_spectrum_pct": round(ai_spectrum_pct, 1),
            "online_presence_index": round(max(0, min(100, harsh_overall_score * 0.85)), 1),
            "conversion_efficiency": round(max(0, min(100, harsh_overall_score * 0.8)), 1),
            "competitor_gap_score": max(10, 100 - round(harsh_overall_score)),
            "classification": self._classify_ai_spectrum(ai_spectrum_pct, scan_data.get("cms_platform", "Modern Stack"))
        }

        # Step 6: Build Key Friction Insight (Target Rank #2 Leak)
        sorted_leaks = sorted(detected_leaks, key=lambda x: x["final_severity_score"], reverse=True)
        key_friction = {}
        if len(sorted_leaks) >= 2:
            rank2 = sorted_leaks[1]
            key_friction = {
                "reason": rank2["description"],
                "revenue_loss_pct": round(rank2["final_severity_score"], 1)
            }
        elif len(sorted_leaks) == 1:
            rank1 = sorted_leaks[0]
            key_friction = {
                "reason": rank1["description"],
                "revenue_loss_pct": round(rank1["final_severity_score"], 1)
            }

        # Step 7: Calculate Niche-Specific Revenue Leak Estimate
        revenue_leak = {}
        if harsh_overall_score < 75:
            gap = 75 - harsh_overall_score
            mults = REVENUE_LEAK_MULTIPLIERS.get(biz_type, REVENUE_LEAK_MULTIPLIERS["general"])
            min_loss = round(gap * mults["min"])
            max_loss = round(gap * mults["max"])
            revenue_leak = {
                "est_annual_revenue_leak": f"${min_loss:,} — ${max_loss:,}"
            }

        # Step 8: Tier Leaks into Priority Packages
        tiered_reports = {
            "tier_3_ifyb3": [self._format_leak_item(leak, 3) for leak in sorted_leaks[:3]],
            "tier_6_mbtb6": [self._format_leak_item(leak, 6) for leak in sorted_leaks[:6]],
            "tier_8_noly8": [self._format_leak_item(leak, 8) for leak in sorted_leaks[:8]],
            "tier_10_arch10": [self._format_leak_item(leak, 10) for leak in sorted_leaks[:10]]
        }

        # Step 9: Vault ID based on score bracket
        vault_id = self._get_vault_id(harsh_overall_score)

        # Step 10: Construct Final Response
        return {
            "target_domain": scan_data.get("domain", ""),
            "business_type": biz_type,
            "overall_health_score": harsh_overall_score,
            "overall_score": round(harsh_overall_score),
            "score_rating": self._get_score_rating(harsh_overall_score),
            "surface_metrics": surface_metrics,
            "key_friction_insight": key_friction,
            "revenue_leak": revenue_leak,
            "ai_spectrum_pct": round(ai_spectrum_pct, 1),
            "ai_penalty": round(ai_penalty, 1),
            "behavioral_diagnostics": behavioral_insights,
            "total_leaks_found": len(detected_leaks),
            "total_severity_index": round(total_severity_loss, 2),
            "tiered_remediation_packages": tiered_reports,
            "vault_id": vault_id,
            "cms_platform": scan_data.get("cms_platform", "")
        }

    def _get_base_weight(self, rule_key: str, biz_type: str) -> int:
        """Retrieves vertical-specific base weight for a given rule."""
        rule_weights = RULE_BASE_WEIGHTS.get(rule_key, {})
        return rule_weights.get(biz_type, 5)

    def _evaluate_checkpoints(self, data: Dict[str, Any], biz_type: str, competitor_has_feature: bool) -> List[Dict[str, Any]]:
        """Evaluates compliance rules dynamically weighted by business model and category weights."""
        biz_matrix = BUSINESS_MODEL_MATRIX[biz_type]
        cat_weights = CATEGORY_WEIGHTS_BY_BIZ[biz_type]
        leaks = []

        # Rule 1: Missing SSL Security Anchor
        if not data.get("has_ssl", False):
            base_w = self._get_base_weight("unsecured_ssl", biz_type)
            leaks.append(self._build_leak(
                title="Unsecured HTTPS/SSL Tunnel",
                base_weight=base_w,
                category="seo_technical",
                category_mult=cat_weights["seo_technical"],
                biz_mult=biz_matrix["trust"],
                competitor_bonus=3 if competitor_has_feature else 0,
                relevance_bonus=3,
                description="Browsers mark site as Unsecure, severely degrading customer conversion trust."
            ))

        # Rule 2: Critical Latency Core Web Vitals Failure
        perf_score = data.get("performance_score", 100.0)
        if perf_score < 60.0:
            base_w = self._get_base_weight("core_web_vitals", biz_type)
            desc = f"Performance rating dropped to {perf_score}/100. "
            if biz_type == "ecommerce":
                desc += "High mobile checkout latency causes immediate cart abandonment."
            else:
                desc += "Triggers search ranking penalties and bounce rate spikes."

            leaks.append(self._build_leak(
                title="Severe Mobile Core Web Vitals Latency",
                base_weight=base_w,
                category="seo_technical",
                category_mult=cat_weights["seo_technical"],
                biz_mult=biz_matrix["seo"],
                competitor_bonus=3 if competitor_has_feature else 0,
                relevance_bonus=3,
                description=desc
            ))

        # Rule 3: Missing Mobile Click-to-Call
        if not data.get("click_to_call_present", False):
            base_w = self._get_base_weight("click_to_call", biz_type)
            desc = "Mobile users cannot tap-to-dial, "
            if biz_type in ["medspa", "legal"]:
                desc += "causing prospective high-value clients to abandon consultation requests."
            else:
                desc += "causing direct conversion drop-offs."

            leaks.append(self._build_leak(
                title="Missing Mobile Click-to-Call / Instant Action",
                base_weight=base_w,
                category="trust_conversion",
                category_mult=cat_weights["trust_conversion"],
                biz_mult=biz_matrix["conversion"],
                competitor_bonus=2 if competitor_has_feature else 0,
                relevance_bonus=3 if biz_type in ["medspa", "legal"] else 1,
                description=desc
            ))

        # Rule 4: Mobile Sticky CTA Absence
        if not data.get("mobile_cta_visible", False):
            base_w = self._get_base_weight("mobile_sticky_cta", biz_type)
            leaks.append(self._build_leak(
                title="Absence of Mobile Sticky Call-to-Action (CTA)",
                base_weight=base_w,
                category="trust_conversion",
                category_mult=cat_weights["trust_conversion"],
                biz_mult=biz_matrix["conversion"],
                competitor_bonus=2 if competitor_has_feature else 0,
                relevance_bonus=2,
                description="Visitors scrolling on mobile lose access to primary booking/buy actions."
            ))

        # Rule 5: Unstructured Heading / Diluted Hero Messaging
        h1_tags = data.get("h1_tags", [])
        if len(h1_tags) != 1:
            base_w = self._get_base_weight("diluted_h1", biz_type)
            leaks.append(self._build_leak(
                title="Diluted Hero Heading (H1) Value Proposition",
                base_weight=base_w,
                category="content_eeat",
                category_mult=cat_weights["content_eeat"],
                biz_mult=biz_matrix["conversion"],
                competitor_bonus=2 if competitor_has_feature else 0,
                relevance_bonus=2,
                description=f"Found {len(h1_tags)} H1 tags, weakening clear positioning and visual structure."
            ))

        # Rule 6: Missing Image Accessibility Anchors
        missing_alt = data.get("missing_alt_images", 0)
        if missing_alt > 0:
            base_w = self._get_base_weight("missing_alt_images", biz_type)
            leaks.append(self._build_leak(
                title="Missing Alt Accessibility & E-E-A-T Anchors",
                base_weight=base_w,
                category="content_eeat",
                category_mult=cat_weights["content_eeat"],
                biz_mult=biz_matrix["seo"],
                competitor_bonus=2 if competitor_has_feature else 0,
                relevance_bonus=2,
                description=f"{missing_alt} images are missing alternative text attributes."
            ))

        # Rule 7: High AI Spectrum
        ai_pct = data.get("ai_spectrum_pct", 0.0)
        if ai_pct > 50.0:
            base_w = self._get_base_weight("ai_template_similarity", biz_type)
            desc = f"{ai_pct}% AI similarity detected. "
            if biz_type in ["medspa", "legal"]:
                desc += "Generic template content severely weakens clinical/legal authority and trust."
            else:
                desc += "Erodes brand trust and differentiation."

            leaks.append(self._build_leak(
                title="High AI Template & Generic Content Match",
                base_weight=base_w,
                category="content_eeat",
                category_mult=cat_weights["content_eeat"],
                biz_mult=biz_matrix["trust"],
                competitor_bonus=2 if competitor_has_feature else 0,
                relevance_bonus=3 if biz_type in ["medspa", "legal"] else 1,
                description=desc
            ))

        return leaks

    def _build_leak(self, title: str, base_weight: int, category: str, category_mult: float, biz_mult: float, competitor_bonus: int, relevance_bonus: int, description: str) -> Dict[str, Any]:
        """Calculates final severity score using exact formulas."""
        raw_weighted_base = base_weight * category_mult * biz_mult
        final_severity = raw_weighted_base + competitor_bonus + relevance_bonus
        return {
            "title": title,
            "base_impact_weight": base_weight,
            "category": category,
            "category_multiplier": category_mult,
            "business_multiplier": biz_mult,
            "competitor_advantage_bonus": competitor_bonus,
            "vertical_relevance_bonus": relevance_bonus,
            "final_severity_score": round(final_severity, 2),
            "description": description
        }

    def _format_leak_item(self, leak: Dict[str, Any], tier_level: int) -> Dict[str, Any]:
        """Formats individual leak dict with exact Tier ID prefix."""
        return {
            "id": self.generate_tier_id(tier_level),
            "severity_score": leak["final_severity_score"],
            "leak_name": leak["title"],
            "impact_summary": leak["description"],
            "category": leak["category"]
        }

    def _get_score_rating(self, score: float) -> str:
        if score >= 90:
            return "ARCHITECT LEVEL"
        elif score >= 75:
            return "OPTIMAL"
        elif score >= 50:
            return "NEEDS REMEDIATION"
        else:
            return "CRITICAL RISK"

    def _get_vault_id(self, score: float) -> str:
        if score >= 90:
            return self.generate_tier_id(10)
        elif score >= 75:
            return self.generate_tier_id(8)
        elif score >= 50:
            return self.generate_tier_id(6)
        else:
            return self.generate_tier_id(3)

    def _classify_ai_spectrum(self, ai_pct: float, cms: str) -> str:
        if ai_pct > 60:
            return f"AI Template — {cms}"
        elif ai_pct > 30:
            return f"Hybrid Stack — {cms}"
        else:
            return f"Custom Build — {cms}"