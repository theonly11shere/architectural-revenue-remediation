# Trilloka V7.8.1 — Universal Engine Refinement

Engine: `v7.8.1-universal-path-refinement`  
API: `7.8.1`

This package includes the V7.8.0 correction and its V7.8.1 refinements. Apply it over your existing V7.7.1 backend (including its previous public-API/version-label corrections) or V7.8.0 backend. It is a drop-in update, not a standalone repository. Keep your other backend files.

## Manual installation

1. Back up or commit your existing backend.
2. Extract this ZIP and copy its contents into your existing backend root, beside `scorer.py`. Replace the seven production modules listed in RELEASE_MANIFEST.json. `journey_presentation.py` is required.
3. In your backend's Python environment, run `python verify_v781.py`. This checks file hashes, runtime version and the offline scanner/report regression suite. Pytest and your existing backend dependencies must be installed.
4. Review and upload/commit the changes yourself through your usual repository process. Deploy through your existing hosting workflow yourself.
5. Confirm the deployed version is `7.8.1` before spending your planned live scan.

No account login, repository access, deployment, live scan or email delivery was performed for this refinement. No account credentials are required to use this ZIP. The Cloudflare frontend files, environment settings and databases are not included or replaced.

## Refinements to the existing engines

- Evidence ranking now compares authority tier first, then stage coverage, then the existing strength measure. Extra action wording cannot outrank stronger stage evidence.
- Competing paths with equal authority and coverage require primary-ordering review, even if one has more synonymous CTAs. Both paths remain available for investigation.
- Secondary journeys require their own action and progression evidence. Weighted hypotheses remain internal discovery candidates rather than confirmed secondary paths. The final primary cannot also appear as a secondary.
- Fresh resolver evidence supersedes a stale cached report summary. Public-safe summaries still survive serialization without private marker receipts.
- Architect-review flags and customer wording agree for unresolved outcomes and fully confirmed paths. Non-finite/malformed candidate confidence displays as unavailable rather than a fabricated percentage.
- Malformed HTTP status metadata and malformed destination URLs do not crash path resolution. Failed pages do not supply progression. Receipt URLs omit URL credentials, query parameters and fragments.

The V7.8.0 fixes remain included: static/deep/rendered evidence bridge, one classifier for static and browser actions, broader decision-page routing, preserved weighted candidate, explicit partial stage counts, no completed-outcome claims from payment or confirmation wording, and customer-safe action labels.

## Validation and boundaries

646 offline tests passed: the prior 444-test suite plus 202 refinement checks. Coverage spans all 19 business categories and all nine existing path grammars, with static extraction, mocked deep crawling/rendered collection, resolver ranking, scoring, customer reports and serialization. See BUSINESS_COVERAGE.md and VALIDATION_RESULTS.txt.

No new scanner feature or external service was added. Scoring formulas/weights, the 0–90 public scale, access rules, authentication configuration and email configuration were not changed by these refinements. Existing learning/remediation/scoring regression tests remain in the suite. conftest.py blocks outbound socket connections and removes the email API key during tests; it is test-only.

Live-site accessibility and deployment have not been tested. Run the verifier in your own backend environment before deployment; this build's dependency environment was not an exact reproduction of your production lockfile. A truthful 0/3 remains possible when no usable path evidence is collected. The report retains the candidate and describes the uncertainty.

This package contains all seven production replacements required for the V7.8 upgrade. Baseline file hashes for V7.7.1 and V7.8.0 are included to help identify any later local edits that need merging. No automatic uploader or account sign-in mechanism is included.
