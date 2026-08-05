import secrets
import string
import math
from typing import Dict, Any, List
from behavioural_engine import BehaviouralEngine

# 1. Exact Category Multipliers
CATEGORY_WEIGHTS = {
    "trust_conversion": 1.25,
    "seo_technical": 1.0,
    "content_eeat": 0.9
}

# 2. Exact Business Model Multipliers Matrix
BUSINESS_MODEL_MATRIX = {
    "local": {"trust": 1.5, "conversion": 1.5, "seo": 0.9},
    "ecommerce": {"trust": 1.4, "conversion": 1.5, "seo": 1.2},
    "saas": {"trust": 1.3, "conversion": 1.4, "seo": 1.1},
    "agency": {"trust": 1.4, "conversion": 1.3, "seo": 1.0},
    "b2b": {"trust": 1.4, "conversion": 1.2, "seo": 1.0},
    "creator": {"trust": 1.0, "conversion": 1.1, "seo": 1.3}
}

# 3. Tier ID Prefix Strategy
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

    def generate_tier_id(self, tier_level: int) -> str:
        """Generates structured IDs like ARCH10-X79B2P."""
        prefix = TIER_PREFIXES.get(tier_level, "IFYB3")
        rand_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        return f"{prefix}-{rand_str}"

    def audit_and_score(self, scan_data: Dict[str, Any], business_type: str = "ecommerce", competitor_data_present: bool = True) -> Dict[str, Any]:
        """Runs the complete harsh scoring pipeline with real formulas."""
        biz_type = business_type.lower()
        if biz_type not in BUSINESS_MODEL_MATRIX:
            biz_type = "ecommerce"

        # Step 1: Execute Behavioral Engine Diagnostics
        behavioral_insights = self.behavioral_engine.analyze_behavioral_friction(scan_data)

        # Step 2: Evaluate Failed Checkpoints & Generate Weighted Severity Scores
        detected_leaks = self._evaluate_checkpoints(scan_data, biz_type, competitor_data_present)

        # Step 3: Calculate REAL AI Spectrum Index from scan data
        ai_spectrum_pct = scan_data.get("ai_spectrum_pct", 0.0)

        # Step 4: Calculate Harsh Overall Health Score (12 - 96 scale)
        # Formula: 100 - (Total Severity Loss * 1.35) - AI Penalty
        total_severity_loss = sum(leak["final_severity_score"] for leak in detected_leaks)
        ai_penalty = min(15.0, (ai_spectrum_pct / 100.0) * 15.0) if ai_spectrum_pct > 60.0 else 0.0

        raw_score = 100.0 - (total_severity_loss * 1.35) - ai_penalty
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

        # Step 7: Calculate Revenue Leak Estimate
        revenue_leak = {}
        if harsh_overall_score < 70:
            gap = 70 - harsh_overall_score
            revenue_leak = {
                "est_annual_revenue_leak": f"${round(gap * 420)} — ${round(gap * 850)}"
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

        # Step 10: Construct Final Unified Response
        return {
            "target_domain": scan_data.get("domain", ""),
            "business_type": biz_type,
            "overall_health_score": harsh_overall_score,
            "overall_score": round(harsh_overall_score),  # Frontend alias
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

    def _evaluate_checkpoints(self, data: Dict[str, Any], biz_type: str, competitor_has_feature: bool) -> List[Dict[str, Any]]:
        """Evaluates compliance rules and applies harsh vertical weighting formulas."""
        biz_matrix = BUSINESS_MODEL_MATRIX[biz_type]
        leaks = []

        # Rule 1: Missing SSL Security Anchor
        if not data.get("has_ssl", False):
            leaks.append(self._build_leak(
                title="Unsecured HTTPS/SSL Tunnel",
                base_weight=10,
                category="trust_conversion",
                category_mult=CATEGORY_WEIGHTS["trust_conversion"],
                biz_mult=biz_matrix["trust"],
                competitor_bonus=3 if competitor_has_feature else 0,
                relevance_bonus=4 if biz_type in ["ecommerce", "saas", "local"] else 3,
                description="Browsers mark site as Unsecure, severely degrading customer conversion trust."
            ))

        # Rule 2: Missing Mobile Click-to-Call
        if not data.get("click_to_call_present", False):
            leaks.append(self._build_leak(
                title="Missing Mobile Click-to-Call / WhatsApp Action",
                base_weight=9,
                category="trust_conversion",
                category_mult=CATEGORY_WEIGHTS["trust_conversion"],
                biz_mult=biz_matrix["conversion"],
                competitor_bonus=3 if competitor_has_feature else 0,
                relevance_bonus=4 if biz_type in ["local", "agency"] else 3,
                description="Mobile users cannot tap-to-dial, causing direct conversion drop-offs."
            ))

        # Rule 3: Mobile Sticky CTA Absence
        if not data.get("mobile_cta_visible", False):
            leaks.append(self._build_leak(
                title="Absence of Mobile Sticky Call-to-Action (CTA)",
                base_weight=9,
                category="trust_conversion",
                category_mult=CATEGORY_WEIGHTS["trust_conversion"],
                biz_mult=biz_matrix["conversion"],
                competitor_bonus=3 if competitor_has_feature else 0,
                relevance_bonus=4 if biz_type in ["ecommerce", "local"] else 3,
                description="Visitors scrolling on mobile lose access to primary buy/book actions."
            ))

        # Rule 4: Critical Latency Core Web Vitals Failure
        perf_score = data.get("performance_score", 100.0)
        if perf_score < 60.0:
            leaks.append(self._build_leak(
                title="Severe Mobile Core Web Vitals Latency",
                base_weight=8,
                category="seo_technical",
                category_mult=CATEGORY_WEIGHTS["seo_technical"],
                biz_mult=biz_matrix["seo"],
                competitor_bonus=3 if competitor_has_feature else 0,
                relevance_bonus=3,
                description=f"Performance rating dropped to {perf_score}/100, triggering search penalties."
            ))

        # Rule 5: Unstructured Heading / Diluted Hero Messaging
        h1_tags = data.get("h1_tags", [])
        if len(h1_tags) != 1:
            leaks.append(self._build_leak(
                title="Diluted Hero Heading (H1) Value Proposition",
                base_weight=7,
                category="content_eeat",
                category_mult=CATEGORY_WEIGHTS["content_eeat"],
                biz_mult=biz_matrix["conversion"],
                competitor_bonus=3 if competitor_has_feature else 0,
                relevance_bonus=3,
                description=f"Found {len(h1_tags)} H1 tags, confusing search crawlers and visual scanners."
            ))

        # Rule 6: Missing Image Accessibility Anchors
        missing_alt = data.get("missing_alt_images", 0)
        if missing_alt > 0:
            leaks.append(self._build_leak(
                title="Missing Alt Accessibility & E-E-A-T Anchors",
                base_weight=6,
                category="content_eeat",
                category_mult=CATEGORY_WEIGHTS["content_eeat"],
                biz_mult=biz_matrix["seo"],
                competitor_bonus=3 if competitor_has_feature else 0,
                relevance_bonus=3,
                description=f"{missing_alt} images are missing alternative text attributes."
            ))

        # Rule 7: High AI Spectrum (AI-generated template)
        ai_pct = data.get("ai_spectrum_pct", 0.0)
        if ai_pct > 50.0:
            leaks.append(self._build_leak(
                title="High AI Template Similarity Detected",
                base_weight=7,
                category="content_eeat",
                category_mult=CATEGORY_WEIGHTS["content_eeat"],
                biz_mult=biz_matrix["trust"],
                competitor_bonus=2 if competitor_has_feature else 0,
                relevance_bonus=3,
                description=f"{ai_pct}% AI similarity erodes brand trust and differentiation."
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
