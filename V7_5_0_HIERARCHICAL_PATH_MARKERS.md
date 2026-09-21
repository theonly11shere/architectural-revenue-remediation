# Trilloka V7.5.0 — Hierarchical Business/Subtype + Path Marker Engine

V7.5.0 changes journey identification from a weighted-clue contest into a staged identification process:

1. infer broad business type;
2. infer a narrower subtype;
3. build a business-specific differentiation/search plan;
4. perform a neutral category-wide evidence crawl rather than allowing an early journey guess to steer the crawler;
5. collect action, progression and terminal-outcome markers;
6. assemble competing customer paths;
7. resolve the primary journey by evidence authority/path completeness;
8. run the existing applicability, scoring, confirmation, financial and reporting pipeline using that resolved architecture;
9. adapt 3-angle remediation to business type, subtype and marker-backed journey status.

## Authority policy
- Terminal outcome: authority 5 — VERIFIED.
- Explicit action + progression: authority 4 — STRONGLY_SUPPORTED.
- Explicit commercial action only: authority 3 — SUPPORTED, but remains provisional for financial modeling.
- Semantic/context evidence without an action: hypothesis/search hint only.
- Business type/subtype is never proof of a journey.

Lower-authority semantic evidence cannot overturn a higher-authority path. Restaurant/menu/dining language therefore cannot beat an observed Order → Cart → Checkout path.

## Business families/subtypes
The marker registry covers every current Trilloka business family: ecommerce, marketplace, local service, professional service, healthcare, medspa, legal, financial services, real estate, restaurant/food service, hospitality/event/tourism, SaaS/software, B2B/industrial, agency, membership/creator/community, education/training, nonprofit/charity, automotive, plus general/unresolved. Each has subtype discriminators and a bounded set of plausible journeys to investigate.

## Feedback-loop correction
The first deeper crawl now uses the resolved broad category but `general` journey discovery. The category deep-dive also remains journey-neutral. The final journey is selected only after evidence has been gathered across competing paths.

## Compatibility
- Existing API routes/request fields remain intact.
- Existing 50-checkpoint architecture, UNKNOWN semantics, high-impact confirmation, Blueprint90 scoring, commercial eligibility, learning boundaries, access control, protected self-scan and reporting pipeline remain intact.
- Frontend visuals are unchanged.
