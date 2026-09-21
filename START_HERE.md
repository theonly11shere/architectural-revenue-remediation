# Trilloka V7.8.1 — Universal Engine Refinement and Compatibility Repair

Engine: `v7.8.1-universal-path-refinement`  
API: `7.8.1`

This package includes the V7.8.0 correction, V7.8.1 refinements, Windows offline-test fix and the matching commercial-architecture prerequisite files. It corrects a mixed backend in which the workflow or scorer predates the commercial-contract module. It is a drop-in update for an existing backend, not a standalone repository. Keep your other backend files.

The original seven-file upgrade assumed a complete V7.7.1 baseline. This repair also supplies `commercial_contracts.py`, `scan_execution_protocol.py` and `scorer.py`, unchanged from the validated V7.7.1 baseline used to test V7.8.1. The release manifest now checks those files as well. No new scoring formula or weight adjustment was introduced in this repair.

## Manual installation

1. Back up or commit your existing backend.
2. Extract this ZIP and copy all 29 files into your existing backend root, beside `main.py` and `scorer.py`. Replace matching files. The ten production files are listed in RELEASE_MANIFEST.json.
3. In your backend's Python environment, run `python verify_v781.py`. On the transferred Windows computer, use `.\.venv-curti\Scripts\python.exe verify_v781.py`. This lists any missing backend modules, checks release hashes, checks commercial workflow compatibility for all 19 business categories, then runs the scanner/report regression suite. Pytest and your existing backend dependencies must be installed. Windows also needs `tzdata`; retain the earlier `tzdata; sys_platform == 'win32'` entry in your existing requirements.txt.
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

The original release had 646 offline checks. This repair adds two integration tests that exercise all 19 business categories: the workflow must return commercial-contract context, and scored audits must retain commercial context and causal metadata. The repair therefore expects 648 passing tests. Existing coverage includes all nine path grammars, static extraction, mocked deep crawling/rendered collection, resolver ranking, scoring, customer reports and serialization. See BUSINESS_COVERAGE.md and VALIDATION_RESULTS.txt.

No new scanner feature or external service was added. The package preserves the validated V7.7.1 scoring formulas/weights and the 0–90 public scale. Access/authentication modules, environment configuration, email configuration and databases are not included. Existing learning/remediation/scoring regression tests remain in the suite. conftest.py permits numeric loopback connections needed by Windows asyncio, blocks remote socket connections and removes the email API key during tests; it is test-only.

Live-site accessibility and deployment have not been tested. Run the verifier in your own backend environment before deployment; this build's dependency environment was not an exact reproduction of your production lockfile. A truthful 0/3 remains possible when no usable path evidence is collected. The report retains the candidate and describes the uncertainty.

This package contains ten production files: the seven V7.8 upgrade modules and the three matching commercial-architecture prerequisites. Baseline file hashes help identify later local edits that need merging. No automatic uploader or account sign-in mechanism is included.

After verification passes, stage the files named by the release manifest plus `requirements.txt`, review the staged changes, then commit and push your current branch through your existing Git remote. The virtual environment and unrelated image deletions are not release files.
