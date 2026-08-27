# Trilloka V7.2.2 — Final Revenue Readiness Blueprint

## Architecture

The scanner keeps the evidence-weighted three-layer method:

- Common Foundation: 22 canonical points
- Revenue/User Architecture: 60 canonical points
- Elite Architecture: 18 canonical points

The 60-point commercial layer remains non-compensatory: conversion execution, trust/decision support, measurement/policy and supporting experience each have fixed point banks. UNKNOWN is never a failure or deduction, but unverified evidence earns no readiness points.

## Public score scale

The canonical 0–100 earned-strength score is mapped monotonically to a public 0–90 Revenue Readiness Index. This is a transparent piecewise-linear calibration, not a percentile curve and not a forced distribution. The canonical score, public mapping formula and anchors are exposed in `score_formula`.

Intended public interpretation:

- 0–25: Critical architecture weakness
- approximately 26–32: Broken / high-risk commercial architecture
- approximately 35–44: Material commercial weaknesses / polished-but-incomplete sites
- approximately 46–57: Functional commercial website
- approximately 59–69: Strong commercial website
- 70–79: Genuinely exceptional observable architecture
- 80–90: Near-perfect verified observable architecture

The small numerical transition gaps are handled continuously by the monotonic mapping; they do not create artificial jumps or a forced distribution.

## Completion verification

Checkout and subscription journeys no longer receive NOT_APPLICABLE for checkpoint 50 merely because Trilloka refuses to place a live order or paid subscription. They remain `UNKNOWN / SAFE_SUBMISSION_LIMIT` unless a customer-visible error is passively observed or explicit non-destructive/business-supplied completion evidence is supplied.

A SAFE_SUBMISSION_LIMIT UNKNOWN earns zero completion points, but it only withholds the explicit completion-evidence weight. It is not treated as if a conversion-path failure had been verified. Verified completion evidence can earn checkpoint 50 PASS without Trilloka itself performing a destructive transaction.

Elite customer-journey points now distinguish verified completion from passive architecture: verified completion can earn the highest customer-journey Elite component; a safely unsubmitted path earns less.

## Financial performance calibration

A weak Lighthouse/PageSpeed lab score remains a visible readiness/performance finding. However, when eligible CrUX field evidence is GOOD, the causal financial-exposure ceiling for the performance finding is reduced from the generic `core_web_vitals` ceiling to 3.5% before severity/substitution scaling.

For the Hasler-style example (severity factor 0.4), this changes the performance family impairment from roughly 4.0% to roughly 1.4%. Field evidence therefore outranks a single lab run economically without hiding the lab-performance weakness.

## Important semantic guardrail

The 0–90 Revenue Readiness Index is not a conversion-rate percentage. Even a score in the 80–90 band does not mean 80–90% of visitors convert. Actual conversion rate, demand, pricing, sales execution and revenue remain outside the public website score unless separately supplied as business data for the financial model.

## V7.2.1 diversified-service journey guardrail

V7.2.1 added primary-surface precedence for journey inference. Homepage/company proposition, global CTA/action evidence and repeated company-level B2B/project language outrank incidental terminology found only on a secondary service page. This prevents a diversified operator from being classified as Appointment / Consultation merely because one crawled service page contains terms such as `medical clinic` or `consultation`.

Secondary journey-page language still contributes evidence, but at a reduced corroborating weight. A genuine clinic/legal/appointment business remains Appointment / Consultation when the primary surface or verified booking action/provider supports that path.

The same corrected journey profile flows into the financial scenario model. Financial priors are never domain-specific overrides; they follow the resolved customer journey and context tags.


## V7.2.2 launch-hardening semantics

V7.2.2 preserves the scoring blueprint and makes three output/discovery corrections only: unsupported typed Nearby searches force specific Text Search peer discovery; verified missing image accessibility text can trigger the generic Foundation Omission Signal; and weak Lighthouse/PageSpeed lab performance is labeled `mobile_lab_performance` when field CrUX is not poor, reserving `core_web_vitals` for real-user field evidence. These changes do not alter the public score anchors.
