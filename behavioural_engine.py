"""Trilloka behavioural-risk heuristics (v7.0 Journey + Context).

These outputs are modeled diagnostic indices, not observed analytics. They supplement the
observable architecture scan and never pretend to be real conversion/bounce telemetry.
"""
from __future__ import annotations

from typing import Any, Dict, List


class BehaviouralEngine:
    def analyze_behavioral_friction(self, scraped_data: Dict[str, Any], business_type: str = "general") -> Dict[str, Any]:
        """Analyze generic friction with a light customer-journey sensitivity.

        ``business_type`` is retained for call compatibility but v7 treats it as a journey model.
        """
        journey = str(business_type or "general")
        title = str(scraped_data.get("title") or "")
        meta_desc = str(scraped_data.get("meta_description") or "")
        h1_tags = scraped_data.get("h1_tags") or []
        perf_score = scraped_data.get("performance_score")
        has_ssl = scraped_data.get("has_ssl")
        word_count = int(scraped_data.get("visible_word_count") or 0)
        img_count = int(scraped_data.get("image_count") or 0)
        missing_alt = int(scraped_data.get("missing_alt_images") or 0)

        cognitive_load_score = self._calc_cognitive_load(word_count, img_count)
        value_prop_score = self._calc_value_prop_prominence(title, meta_desc, h1_tags, scraped_data.get("h1_status"))
        trust_anchor_score = self._calc_trust_anchors(has_ssl, missing_alt, img_count)
        estimated_bounce_risk_index = self._estimate_bounce_risk_index(perf_score, cognitive_load_score, journey)

        behavioral_score = round(
            (value_prop_score * 0.35) + (trust_anchor_score * 0.35) + (cognitive_load_score * 0.30), 1
        )
        leaks = self._extract_behavioral_leaks(
            value_prop_score, trust_anchor_score, cognitive_load_score,
            estimated_bounce_risk_index, journey, scraped_data,
        )
        return {
            "status": "modeled",
            "model_basis": "journey_sensitive_heuristic_v1",
            "journey_model": journey,
            "behavioral_score": behavioral_score,
            "estimated_bounce_risk_index": estimated_bounce_risk_index,
            "bounce_risk_percentage": f"{estimated_bounce_risk_index}%",  # legacy key
            "bounce_risk_kind": "MODELED_ESTIMATE",
            "heuristics": {
                "cognitive_load_score": cognitive_load_score,
                "value_prop_prominence": value_prop_score,
                "trust_anchor_score": trust_anchor_score,
            },
            "behavioral_friction_leaks": leaks,
            "note": "Heuristic behavioral indicators are not observed visitor analytics and do not replace real funnel/session data.",
        }

    @staticmethod
    def _calc_cognitive_load(word_count: int, img_count: int) -> float:
        if word_count <= 0:
            return 40.0
        if word_count < 120:
            return 68.0
        if word_count > 2200:
            return 62.0
        if img_count > 80:
            return 65.0
        return 86.0

    @staticmethod
    def _calc_value_prop_prominence(title: str, meta_desc: str, h1_tags: List[str], h1_status: Any) -> float:
        score = 0.0
        if len(title.strip()) >= 10:
            score += 25.0
        if len(meta_desc.strip()) >= 30:
            score += 25.0
        if str(h1_status or "").lower() == "present" and len(h1_tags) == 1:
            score += 50.0
        elif str(h1_status or "").lower() == "present" and len(h1_tags) > 1:
            score += 35.0
        elif str(h1_status or "").lower() == "unknown":
            score += 25.0
        return min(100.0, score)

    @staticmethod
    def _calc_trust_anchors(has_ssl: Any, missing_alt: int, total_img: int) -> float:
        score = 55.0 if has_ssl is True else (30.0 if has_ssl is None else 0.0)
        if total_img > 0:
            alt_ratio = max(0.0, min(1.0, (total_img - missing_alt) / total_img))
            score += alt_ratio * 45.0
        else:
            score += 30.0
        return round(min(100.0, score), 1)

    @staticmethod
    def _estimate_bounce_risk_index(perf_score: Any, cognitive_load: float, journey: str) -> float:
        try:
            perf = float(perf_score) if perf_score is not None else None
        except (TypeError, ValueError):
            perf = None
        base = 25.0 if perf is None else max(8.0, (100.0 - perf) * 0.55)
        if cognitive_load < 60.0:
            base += 12.0
        if journey in {"appointment_consultation", "direct_purchase", "demo_sales", "reservation_event"}:
            base *= 1.04
        return round(min(85.0, max(5.0, base)), 1)

    def _extract_behavioral_leaks(
        self, value_prop: float, trust: float, cog_load: float, bounce_index: float,
        journey: str, scraped_data: Dict[str, Any],
    ) -> List[str]:
        leaks: List[str] = []
        data = scraped_data or {}
        if data.get("browser_loaded") and not data.get("has_qualitative_analytics"):
            leaks.append("Blind Qualitative Telemetry: no supported session-replay/qualitative-analytics signal was detected; server-side or unsupported tools may still exist.")
        if data.get("real_user_speed_grade") == "POOR":
            leaks.append(f"CrUX Real-User Speed Warning: field telemetry is poor (LCP {data.get('crux_lcp_ms')} ms where available).")
        if value_prop < 65.0 and data.get("h1_status") != "unknown":
            journey_copy = {
                "lead_quote": "the quote/enquiry value proposition",
                "appointment_consultation": "the appointment/consultation value proposition",
                "reservation_event": "the reservation/event value proposition",
                "direct_purchase": "the purchase value proposition",
                "demo_sales": "the demo/sales value proposition",
                "membership_subscription": "the membership/subscription value proposition",
            }.get(journey, "the primary customer value proposition")
            leaks.append(f"Weak Above-the-Fold Journey Clarity: verified title/meta/H1 signals do not strongly support {journey_copy}.")
        if trust < 65.0:
            leaks.append("Modeled Trust Friction: verified security/accessibility signals are weaker than the diagnostic baseline.")
        if cog_load < 60.0:
            leaks.append("Modeled Cognitive-Load Risk: page density may increase scanning friction.")
        if bounce_index > 40.0:
            leaks.append(f"Modeled Latency/Clutter Risk Index: {bounce_index}/100. This is a heuristic risk index, not observed visitor abandonment.")
        return leaks
