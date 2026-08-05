import secrets
import string
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
    3: "IFYB3",    # "Important for your business"
    6: "MBTB6",    # "Making your business the best"
    8: "NOLY8",    # "No one like you"
    10: "ARCH10"   # "The Architect"
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
        """Runs the complete harsh scoring pipeline."""
        biz_type = business_type.lower()
        if biz_type not in BUSINESS_MODEL_MATRIX:
            biz_type = "ecommerce"

        # Step 1: Execute Behavioral Engine Diagnostics
        behavioral_insights = self.behavioral_engine.analyze_behavioral_friction(scan_data)

        # Step 2: Evaluate Failed Checkpoints & Generate Weighted Severity Scores
        detected_leaks = self._evaluate_checkpoints(scan_data, biz_type, competitor_data_present)

        # Step 3: Calculate Harsh Overall Health Score (0 - 100)
        total_severity_loss = sum(leak["final_severity_score"] for leak in detected_leaks)
        bounce_penalty = float(behavioral_insights["bounce_risk_percentage"].replace("%", "")) * 0.4
        
        # Harsh Score Formula: 100 minus severity penalty and bounce probability penalty
        raw_score = 100.0 - (total_severity_loss * 0.85) - bounce_penalty
        harsh_overall_score = max(5.0, round(raw_score, 1))  # Cap floor at 5.0

        # Step 4: Tier Leaks into Priority Packages (Top 3, 6, 8, 10)
        sorted_leaks = sorted(detected_leaks, key=lambda x: x["final_severity_score"], reverse=True)
        tiered_reports = {
            "tier_3_ifyb3": [self._format_leak_item(leak, 3) for leak in sorted_leaks[:3]],
            "tier_6_mbtb6": [self._format_leak_item(leak, 6) for leak in sorted_leaks[:6]],
            "tier_8_noly8": [self._format_leak_item(leak, 8) for leak in sorted_leaks[:8]],
            "tier_10_arch10": [self._format_leak_item(leak, 10) for leak in sorted_leaks[:10]]
        }

        # Step 5: Construct Final Unified Response
        return {
            "target_domain": scan_data.get("domain", ""),
            "business_type": biz_type,
            "overall_health_score": harsh_overall_score,
            "score_rating": "CRITICAL RISK" if harsh_overall_score < 50 else ("NEEDS REMEDIATION" if harsh_overall_score < 75 else "OPTIMAL"),
            "behavioral_diagnostics": behavioral_insights,
            "total_leaks_found": len(detected_leaks),
            "total_severity_index": round(total_severity_loss, 2),
            "tiered_remediation_packages": tiered_reports
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

        # Rule 2: Missing Mobile Click-to-Call (Local / Agency Friction)
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

        return leaks

    def _build_leak(self, title: str, base_weight: int, category: str, category_mult: float, biz_mult: float, competitor_bonus: int, relevance_bonus: int, description: str) -> Dict[str, Any]:
        """Calculates final severity score using screenshot formulas."""
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
            "impact_summary": leak["description"]
        }