# Trilloka V7.2.2 — Launch Candidate Deployment Notes

V7.2.2 is a narrow launch-hardening patch on top of V7.2.1. It does **not** recalibrate Blueprint90 or replace the Journey + Context architecture.

## Launch corrections

1. **Competitor discovery fallback**
   - A typed Google Nearby Search that returns HTTP 400 now forces a specific Google Text Search even if an untyped Nearby retry returns results.
   - The untyped retry can remain broader reputation context, but specific Text Search results are preferred for peer discovery.
   - This prevents unrelated hospitals, malls, retailers, transit, or attractions from suppressing the correct contractor/service peer search.

2. **Foundation Omission Signal**
   - A verified accessibility-text failure (checkpoint 34) is once again eligible to trigger the generic Foundation Notice.
   - The public notice remains non-disclosing; exact issue/evidence/fix stays in the detailed report.
   - UNKNOWN and NOT_APPLICABLE still never trigger the notice.

3. **Performance semantics**
   - Weak PageSpeed/Lighthouse lab performance with CrUX GOOD is now reported as `mobile_lab_performance` / **Mobile Lab Performance Headroom**.
   - `core_web_vitals` is reserved for poor real-user CrUX evidence.
   - The existing financial field-data override remains: GOOD CrUX reduces the modeled causal exposure of a weak lab score without hiding the lab finding.

## Preserved architecture

- Canonical score: 22 Foundation + 60 Revenue/User + 18 Elite = 100 internal strength points.
- Public Blueprint90: transparent monotonic 0–90 calibration.
- UNKNOWN is not FAIL; it earns no readiness points and causes no deduction.
- Journey/context weighting and V7.2.1 diversified-B2B guardrails are preserved.
- SAFE_SUBMISSION_LIMIT behavior is preserved.
- Competitor benchmark remains non-scoring and requires verified comparable peers.
- Commercial exposure remains decoupled from score loss and labeled scenario/business-input appropriately.
- V7.1.1 SSRF/network protections remain in place.

## Verify locally

```powershell
python run_all_tests.py
python synthetic_blueprint_validation.py
```

Expected for this exact package:

- 84/84 regression tests passed
- 33/33 integrity checks passed
- 36/36 synthetic Blueprint90 cases passed
- warnings-as-errors compile passed
- runtime import: FastAPI 7.2.2 / scanner v7.2.2

## Post-deploy smoke test

Confirm the health/version output reports V7.2.2, then rescan Hasler Homes and at least one direct-purchase site.

For a Hasler-style result with PageSpeed weak + CrUX GOOD, confirm:
- performance finding is **Mobile Lab Performance Headroom**, not a Core Web Vitals failure;
- a verified missing-alt omission triggers the generic Foundation Notice;
- if Google rejects `general_contractor` as a Nearby type, `text_search_status` is attempted rather than `not_needed`.

Local validation is not a substitute for production smoke testing of Google APIs, DNS/network behavior, Chromium, hosting environment variables, and frontend wiring.
