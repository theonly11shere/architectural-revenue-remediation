# V7.2.1 — Fairweather-style production correction

The first V7.2 production scan exposed a diversified-service classification edge case: a secondary medical service line could self-confirm an initial Appointment / Consultation guess during the bounded journey crawl.

V7.2.1 fixes this generically rather than hardcoding any domain:

- primary homepage/company proposition outranks secondary service-page terminology;
- global contact/quote/call actions reinforce B2B lead/project inquiry journeys;
- secondary journey text is corroborating evidence and is weighted below primary-page text;
- appointment classification requires primary appointment/service evidence or a verified booking action/provider when competing B2B signals exist;
- a single secondary regulated service phrase cannot create a company-wide regulated/high-trust context;
- B2B project/operations/support-service language can establish enterprise/considered-purchase context;
- corrected journey/context automatically drives the financial scenario prior.

Using the original scan's verified financial findings (Privacy Policy Trust Gap, Structured Data Gap, Search Description Length Outlier) but the corrected `lead_quote` + `enterprise_considered_purchase` profile gives:

- annual digital opportunity scenario: $18,750–$324,000;
- modeled combined path impairment: 4.4%;
- central modeled exposure: $7,500/year;
- displayed range: $500–$16,500/year — LOW scenario exposure;
- confidence: SCENARIO / SCENARIO_PRIOR, not measured revenue loss.

This correction is a model replay against the original verified findings, not a fresh live network scan. Run the site again after deployment to confirm the production result.
