# Trilloka V7.4.1 — Reliability Patch

V7.4.1 does **not** add a new scoring philosophy, new checklist, or Valmont-specific exception. It corrects general reliability defects exposed by real-site validation while preserving:

**Business Type + Customer Journey + Context + Verified Evidence → Applicability → Scoring/Priority → 3-angle remediation.**

## Reliability corrections

- **Cross-page commercial evidence propagation** — verified actions found on deeper pages (Order, Add to Cart, Quote, Demo, Apply, Book, etc.) now reach site-level journey inference and conversion-strength reasoning. They remain separate from homepage/mobile-prominence evidence, so Trilloka does not pretend a deeper action was sticky or visible on the landing page.
- **Cross-page location/contact/context propagation** — verified address, phone, directions, order/checkout and related positive evidence discovered deeper in the site can inform the final context model.
- **Stronger site-wide absence claims** — a missing primary customer journey action is not promoted as a site-wide scored finding from homepage/mobile evidence alone; bounded journey coverage must also be verified.
- **UNKNOWN preservation across required evidence families** — policy, credential, refund/reassurance, broad proof and proof-of-work compound checks use tri-state evidence. `None` cannot silently become `False` and therefore cannot become FAIL.
- **Privacy/Terms correction** — unresolved policy evidence remains UNKNOWN. Explicit verified absence is required for FAIL.
- **Sticky CTA correction** — absence of a persistent/sticky CTA is an optimization/Architect judgment, not a universal automatic failure. Verified presence can still count positively.
- **Provisional-journey financial guardrail** — journey-specific dollar exposure is deferred until the primary journey is resolved/confirmed. Verified findings remain visible and scored independently.
- **Direct Purchase ≠ retail goods** — restaurant/service purchase paths are no longer forced into ecommerce return, shipping or delivery-policy expectations merely because the journey is transactional. Goods-specific expectations remain scoped to ecommerce/marketplace evidence.
- **Selective category remediation** — business/journey context is added only where it materially changes the fix. Pure infrastructure/SEO remedies no longer receive unrelated menu/reservation/category boilerplate.
- **Architect escalation** — specialized provisional journeys and medium-confidence proof-placement judgments are explicitly routed to Architect Review.
- **Diagnostic/report cleanup** — “AI / Template Pattern Index Measured” remains a diagnostic checkpoint but is no longer presented as a customer website strength.
- **HTTPS evidence auditability** — redirect findings retain the attempted HTTP URL, final URL/status, redirect chain and reason where available. A redirect FAIL now requires verified evidence rather than a generic inability to verify.

## What did not change

- 50-point evidence basis.
- Three-layer readiness architecture.
- Business Type + Journey + Context reasoning model.
- Research cannot manufacture a finding.
- UNKNOWN ≠ FAIL.
- Only verified problems affect problem scoring.
- Three-angle Technical / UX-CRO / Systems remediation.
- Learning cannot rewrite scoring weights or create failures.

## Real-world acceptance target

After deployment, re-run the exact Valmont URL. The patch is designed so verified Order Online / purchase evidence can outrank a generic restaurant reservation prior; verified local/location evidence can reach context inference; policy evidence cannot fail when unresolved; sticky CTA absence does not become a scored leak; and unresolved journeys do not generate strong dollar-exposure headlines.
