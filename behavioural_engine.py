import math
from typing import Dict, Any, List


class BehaviouralEngine:
    """
    Trilloka Behavioural Engine:
    Evaluates user psychology, visual friction, hero clarity, 
    and estimated visitor bounce risk probability from telemetry.
    """

    def analyze_behavioral_friction(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """Runs behavioral heuristics analysis on scraped page telemetry."""
        title = scraped_data.get("title", "")
        meta_desc = scraped_data.get("meta_description", "")
        h1_tags = scraped_data.get("h1_tags", [])
        perf_score = scraped_data.get("performance_score", 65.0)
        has_ssl = scraped_data.get("has_ssl", False)
        page_len = scraped_data.get("page_content_len", 0)
        img_count = scraped_data.get("image_count", 0)
        missing_alt = scraped_data.get("missing_alt_images", 0)

        # 1. Cognitive Load & Readability Friction Score (0-100)
        cognitive_load_score = self._calc_cognitive_load(page_len, img_count)

        # 2. Hero & Value Proposition Prominence Score (0-100)
        value_prop_score = self._calc_value_prop_prominence(title, meta_desc, h1_tags)

        # 3. Psychological Trust Anchor Score (0-100)
        trust_anchor_score = self._calc_trust_anchors(has_ssl, missing_alt, img_count)

        # 4. Behavioral Bounce Risk Probability (0% - 100%)
        bounce_risk_percentage = self._estimate_bounce_risk(perf_score, cognitive_load_score)

        # 5. Aggregate Behavioral Score
        behavioral_score = round(
            (value_prop_score * 0.35) + 
            (trust_anchor_score * 0.35) + 
            (cognitive_load_score * 0.30), 
            1
        )

        return {
            "behavioral_score": behavioral_score,
            "bounce_risk_percentage": f"{bounce_risk_percentage}%",
            "heuristics": {
                "cognitive_load_score": cognitive_load_score,
                "value_prop_prominence": value_prop_score,
                "trust_anchor_score": trust_anchor_score
            },
            "behavioral_friction_leaks": self._extract_behavioral_leaks(
                value_prop_score, trust_anchor_score, cognitive_load_score, bounce_risk_percentage
            )
        }

    def _calc_cognitive_load(self, page_len: int, img_count: int) -> float:
        if page_len == 0:
            return 20.0
        if page_len < 2000:
            return 60.0  # Thin content friction
        if page_len > 150000:
            return 55.0  # Overly bloated DOM causes scanning friction
        return 88.0

    def _calc_value_prop_prominence(self, title: str, meta_desc: str, h1_tags: List[str]) -> float:
        score = 0.0
        if len(title) >= 10:
            score += 30.0
        if len(meta_desc) >= 30:
            score += 30.0
        if len(h1_tags) == 1:
            score += 40.0  # Clear single focused primary heading
        elif len(h1_tags) > 1:
            score += 20.0  # Multiple H1s dilute hero messaging focus
        return min(100.0, score)

    def _calc_trust_anchors(self, has_ssl: bool, missing_alt: int, total_img: int) -> float:
        score = 0.0
        if has_ssl:
            score += 50.0
        if total_img > 0:
            alt_ratio = (total_img - missing_alt) / total_img
            score += alt_ratio * 50.0
        else:
            score += 25.0
        return round(score, 1)

    def _estimate_bounce_risk(self, perf_score: float, cognitive_load: float) -> float:
        base_bounce = max(10.0, (100.0 - perf_score) * 0.75)
        if cognitive_load < 50.0:
            base_bounce += 15.0
        return round(min(89.0, base_bounce), 1)

    def _extract_behavioral_leaks(self, value_prop: float, trust: float, cog_load: float, bounce_risk: float) -> List[str]:
        leaks = []
        if value_prop < 70.0:
            leaks.append("Weak Above-the-Fold Hero Clarity: Missing a single focused H1 heading or primary offer tag.")
        if trust < 70.0:
            leaks.append("Psychological Trust Friction: Unsecured connection or missing image accessibility attributes.")
        if cog_load < 60.0:
            leaks.append("High Cognitive Clutter: Layout complexity increases user scanning friction.")
        if bounce_risk > 40.0:
            leaks.append(f"Critical Latency Bounce Risk: Estimated {bounce_risk}% visitor abandonment before taking action.")
        return leaks