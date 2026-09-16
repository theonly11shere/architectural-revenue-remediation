"""Human Architect escalation layer for evidence that automation should not overclaim."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping


def _item(severity: str, category: str, title: str, reason: str, evidence: Mapping[str, Any], inspect: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "severity": severity,
        "category": category,
        "title": title,
        "reason": reason,
        "evidence": dict(evidence or {}),
        "architect_should_inspect": dict(inspect or {}),
        "machine_policy": "Not scored as a new failure solely because human judgment is requested.",
    }


def build_architect_review_queue(scan: Mapping[str, Any], audit: Mapping[str, Any], require_final_proof: bool = True) -> List[Dict[str, Any]]:
    reviews: List[Dict[str, Any]] = []
    profile = scan.get("architecture_profile") if isinstance(scan.get("architecture_profile"), Mapping) else {}
    journey = str(profile.get("journey_model") or "general")
    business_type = str(profile.get("business_type") or "general")
    diagnostics = scan.get("commercial_architecture_diagnostics") if isinstance(scan.get("commercial_architecture_diagnostics"), Mapping) else {}
    decision = diagnostics.get("decision_point_evidence") if isinstance(diagnostics, Mapping) else {}
    # Backward-compatible fallback for archived/pre-patch snapshots that used the older key.
    if not isinstance(decision, Mapping):
        decision = diagnostics.get("decision_evidence") if isinstance(diagnostics, Mapping) else {}
    if not isinstance(decision, Mapping):
        decision = {}

    # 0) A specialized but provisional journey should be explicitly confirmed by the Architect
    # before journey-dependent recommendations or financial interpretation are treated as mature.
    if bool(profile.get("provisional")) and journey != "general":
        reviews.append(_item(
            "IMPORTANT", "journey_resolution", "Primary customer journey requires Architect confirmation",
            "Automation found a likely customer journey but confidence remains below the resolution threshold. Journey-dependent failures and financial scenario modeling stay guarded until this is confirmed.",
            {
                "business_type": business_type,
                "journey_model": journey,
                "journey_confidence": profile.get("confidence"),
                "journey_signals": list(profile.get("journey_signals") or [])[:10],
                "secondary_journeys": list(profile.get("secondary_journeys") or [])[:3],
            },
            {"check": "Confirm the real primary conversion path from the live site and distinguish primary versus secondary journeys before approving journey-dependent priorities."},
        ))

    # 1) Visual prominence cannot be proven from DOM existence alone.
    primary_present = scan.get("mobile_primary_cta_present") is True
    sticky = scan.get("mobile_sticky_cta_present")
    if primary_present and sticky is not True and journey in {"lead_quote","appointment_consultation","reservation_event","direct_purchase","demo_sales"}:
        reviews.append(_item(
            "IMPORTANT", "visual_hierarchy", "Primary action prominence on the real page",
            "Automation verified that a primary action exists, but DOM presence alone cannot establish whether visual hierarchy, contrast and surrounding content make it sufficiently obvious at the decision point.",
            {"mobile_primary_cta_present": True, "mobile_sticky_cta_present": sticky, "journey_model": journey},
            {"check": "Open the primary decision page on desktop and mobile; judge whether the main action is visually dominant without being obstructive.", "page": scan.get("browser_journey_url") or scan.get("final_url")},
        ))

    # 2) Complex interactive states.
    text = (str(scan.get("page_text") or "") + " " + str(scan.get("journey_text_sample") or "")).lower()
    complex_terms = [term for term in ("quiz","assessment","configurator","calculator","calendar","step 1","step 2","recommendation","finder") if term in text]
    if len(complex_terms) >= 2:
        reviews.append(_item(
            "IMPORTANT", "interactive_journey", "Complex interactive journey requires human walkthrough",
            "The scanner found a multi-step or stateful customer experience. Passive inspection can verify structure and public evidence, but it should not pretend to know every conditional state.",
            {"signals": complex_terms[:8], "browser_journey_rendered": bool(scan.get("browser_journey_rendered"))},
            {"check": "Walk the interaction end-to-end without submitting destructive customer data; note unclear states, recommendation logic, errors and dead ends.", "page": scan.get("browser_journey_url") or scan.get("final_url")},
        ))

    # 3) External booking/payment/application continuation.
    external = scan.get("booking_provider_links") or []
    if external:
        reviews.append(_item(
            "IMPORTANT", "external_conversion", "External conversion handoff",
            "A commercially relevant path continues on a third-party provider. Trilloka can verify the public handoff and destination health, but the complete external experience may require Architect inspection.",
            {"providers": external[:4], "provider_health": scan.get("external_booking_provider_health") or {}},
            {"check": "Open the handoff on desktop and mobile; inspect continuity of offer, price/expectations, trust, error handling and return path without completing a live transaction."},
        ))

    # 4) Proof placement is structurally detectable, but visual relevance/credibility can remain
    # qualitative. Route medium-confidence placement findings to the Architect even when the
    # structural sitewide-present/decision-point-absent condition was detected.
    scoring_ledger = [x for x in (audit.get("scoring_ledger") or []) if isinstance(x, Mapping)]
    proof_finding = next((x for x in scoring_ledger if str(x.get("rule_key") or "") == "proof_placement_gap"), None)
    structural_proof_uncertain = bool(
        (decision.get("proof_exists_sitewide") or decision.get("proof_sitewide"))
        and (int(decision.get("decision_pages_verified") or 0) > 0 or decision.get("decision_pages"))
        and decision.get("proof_visible_at_decision_point", decision.get("proof_at_decision")) is None
    )
    if structural_proof_uncertain or (proof_finding and str(proof_finding.get("confidence") or "").lower() != "high"):
        reviews.append(_item(
            "IMPORTANT", "proof_quality", "Proof relevance at the decision point",
            "Structural evidence indicates a proof-placement concern, but automation should not pretend that DOM proximity alone establishes visual relevance, credibility or persuasive connection to the decision.",
            {"decision_evidence": dict(decision), "scored_finding": dict(proof_finding or {})},
            {"check": "Inspect the affected decision page visually. Confirm whether the existing proof actually answers the customer's concern at the high-consideration point before recommending a substantial change."},
        ))

    # 5) Novel learned subtype / unresolved archetype.
    overlay = scan.get("learning_overlay") if isinstance(scan.get("learning_overlay"), Mapping) else {}
    archetype = overlay.get("archetype") if isinstance(overlay.get("archetype"), Mapping) else None
    if archetype and float(archetype.get("similarity") or 0) < 0.50:
        reviews.append(_item(
            "OPTIONAL", "novel_archetype", "Emerging business subtype",
            "The site resembles a learned business archetype only partially. An Architect can confirm whether this represents a distinct subtype worth teaching Trilloka.",
            {"business_type": business_type, "archetype_hint": archetype},
            {"check": "Confirm the actual commercial model, the primary buyer concern and whether this should become a named subtype in the Knowledge Vault."},
        ))

    # 6) Potentially material but unconfirmed automated findings.
    unconfirmed = [x for x in (audit.get("unconfirmed_high_impact_observations") or []) if isinstance(x, Mapping)]
    if unconfirmed:
        reviews.append(_item(
            "CRITICAL", "high_impact_uncertain", "Potential high-impact issue needs Architect verification",
            "The first pass observed a potentially material issue, but the independent confirmation phase did not provide enough evidence to score it automatically.",
            {"candidate_count": len(unconfirmed), "candidates": [{"rule_key": x.get("rule_key"), "name": x.get("leak_name"), "reason": x.get("confirmation_reason")} for x in unconfirmed[:6]]},
            {"check": "Inspect the affected path manually before recommending expensive remediation. Confirm or dismiss each candidate and record the decision in the Vault."},
        ))

    # 7) Safe non-destructive scanners cannot prove final submissions.
    cps = [x for x in (audit.get("full_50_checkpoint_basis") or []) if isinstance(x, Mapping)]
    cp50 = next((x for x in cps if int(x.get("id") or 0) == 50), None)
    if cp50 and str(cp50.get("status")) == "UNKNOWN" and journey != "general":
        reviews.append(_item(
            "IMPORTANT", "conversion_completion", "End-to-end conversion completion",
            "Trilloka intentionally does not submit real customer forms, orders, donations or paid subscriptions, so completion/delivery state cannot always be verified automatically.",
            {"checkpoint": cp50.get("check"), "status": cp50.get("status"), "note": cp50.get("customer_note")},
            {"check": "Use a safe test/staging path or owner-approved test submission to verify success state, confirmation messaging and operational delivery."},
        ))

    # 8) Every paid/master report receives a final human proof step. This is not a second
    # scoring engine; it is a quality-control check that the machine's highest priorities and
    # proposed remedies make practical sense in the site's real context.
    if require_final_proof:
        verified_findings = [x for x in (audit.get("scoring_ledger") or []) if isinstance(x, Mapping) and x.get("rule_key")]
        reviews.append(_item(
            "IMPORTANT", "final_proof", "Final Architect proof of priorities and recommendations",
            "Trilloka's automated evidence and score remain reproducible, but the final customer report is held for a human Architect proof so subtle visual/contextual issues or impractical remedies can be called out before delivery.",
            {"business_type": business_type, "journey_model": journey, "verified_finding_count": len(verified_findings), "score": audit.get("overall_score", audit.get("overall_health_score"))},
            {"check": "Review the top verified findings, their order, the three-angle remedies and any escalated machine limitations. Record any confirmation, dismissal or missed finding before final report delivery."},
        ))

    # Dedupe by category/title and cap operational workload.
    out: List[Dict[str, Any]] = []
    seen = set()
    order = {"CRITICAL": 0, "IMPORTANT": 1, "OPTIONAL": 2}
    for item in sorted(reviews, key=lambda x: order.get(str(x.get("severity")), 9)):
        key = (item.get("category"), item.get("title"))
        if key in seen: continue
        seen.add(key); out.append(item)
    return out[:8]
