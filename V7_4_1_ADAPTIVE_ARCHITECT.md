# Trilloka V7.4.1 — Adaptive Architect Reliability Patch

V7.4.1 keeps Trilloka's existing evidence/scoring philosophy intact:

**Business Type + Customer Journey + Context + Verified Evidence → Applicability → Priority → Remediation**

The upgrade adds experience and human escalation around that fixed core instead of allowing scans to rewrite scoring logic.

## What is new

- **Adaptive Knowledge Memory** — confirmed business-category corrections can create candidate recognition knowledge and emerging business subtypes/archetypes. Only validated/active recognition memory is allowed back into business inference, with a strict bounded influence. Learned knowledge cannot create findings or rewrite scoring weights.
- **Knowledge provenance** — scanner observations, user-confirmed classification corrections, Architect decisions, missed findings and Architect-confirmed remediation outcomes are stored as different evidence types.
- **Commercial Eligibility Gate** — primarily informational/government/archive sites are recognized but are not given a normal Revenue Readiness score unless a real commercial path is visible. Mixed sites can still be audited around tickets, bookings, sales, applications or another measurable path.
- **Architect Review Queue** — visual hierarchy, complex interactive states, third-party conversion handoffs, qualitative proof relevance, novel archetypes, unconfirmed high-impact candidates and safe-submission limits are escalated rather than turned into invented failures.
- **Real Architect proof before paid report delivery** — paid customer reports are held until open Architect review items are resolved. Automated evidence/scoring is retained separately for reproducibility.
- **Learning from outcomes** — Architect-confirmed remediation outcomes can improve future Technical / UX-CRO / Systems guidance for the same business/journey/finding context. Outcome memory does not guarantee uplift and does not create findings.
- **Public-safe explanation** — the frontend animation now explains business understanding, customer journey, relevant expertise, evidence verification, commercial friction, Architect review and the improvement loop without exposing exact formulas, weights or proprietary inference rules.

## Learning safety

A single customer correction does not alter production classification. New vocabulary begins as candidate knowledge. Repeated independent support and low conflict can validate/activate low-risk classification recognition; new archetypes remain Architect-controlled. Scoring weights, failure rules and financial logic do not self-modify.

## Persistence

Use a persistent disk for `TRILLOKA_LEARNING_DB_PATH`. The current SQLite implementation is appropriate for a single Render application instance. If the service is later horizontally scaled across multiple writers, migrate the knowledge/review store to a shared transactional database before enabling multi-instance writes.

## Public positioning

Recommended public language:

**Research-informed. Evidence-verified. Architect-reviewed.**

**A website scanner should understand the business before it judges the website.**

Avoid public disclosure of exact category signals, research multipliers, tie-break rules, scoring constants, candidate activation thresholds or other proprietary calibration details.
