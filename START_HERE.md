# Trilloka V7.8.1 — Reviewed Merge Resolution

Engine: `v7.8.1-universal-path-refinement`  
API: `7.8.1`

This ten-file overlay resolves the four merge conflicts supplied in your review ZIP. Apply it to your existing backend with the V7.8.1 Compatibility Repair already installed and the merge still pending. It retains the V7.8.0 correction, V7.8.1 refinements, Windows offline-test fix and matching commercial-architecture prerequisites. It is not a standalone repository. Keep your other backend files. See `MERGE_NOTES.md` for the comparison and exact Git commands.

The original seven-file upgrade assumed a complete V7.7.1 baseline. This repair also supplies `commercial_contracts.py`, `scan_execution_protocol.py` and `scorer.py`, unchanged from the validated V7.7.1 baseline used to test V7.8.1. The release manifest now checks those files as well. No new scoring formula or weight adjustment was introduced in this repair.

## Manual installation

1. Keep the review ZIP as a backup of the supplied merge state. If you edited any conflicted file after creating it, save that edit before replacing files.
2. Extract this ZIP and copy all ten files into `C:\Users\curti\Downloads\trilloka_scanner`, beside `main.py`. Replace matching files. This overlay contains four resolved production files; the manifest still verifies all ten production files in the full release.
3. Run `.\.venv-curti\Scripts\python.exe verify_v781.py`. The verifier checks missing backend modules, release hashes and commercial workflow compatibility for all 19 business categories, then runs the scanner/report suite. It accepts Git CRLF checkout line endings while still rejecting code edits. Pytest and existing backend dependencies must be installed. Keep `tzdata; sys_platform == 'win32'` in `requirements.txt`.
4. After all 650 tests pass, follow `MERGE_NOTES.md` to stage the named files, review staged frontend changes, complete the pending merge and push it yourself. Do not start another pull during the pending merge.
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

The original release had 646 offline checks. The compatibility repair added two integration tests covering commercial workflow and scoring context across all 19 business categories. This overlay adds two verifier regression cases: a simulated Windows CRLF checkout must pass, and a source edit in that checkout must fail. The release therefore expects 650 passing tests. Existing coverage includes all nine path grammars, static extraction, mocked deep crawling/rendered collection, resolver ranking, scoring, customer reports and serialization. See `BUSINESS_COVERAGE.md` in the full compatibility release and `VALIDATION_RESULTS.txt` here.

No new scanner feature or external service was added. The package preserves the validated V7.7.1 scoring formulas/weights and the 0–90 public scale. Access/authentication modules, environment configuration, email configuration and databases are not included. Existing learning/remediation/scoring regression tests remain in the suite. conftest.py permits numeric loopback connections needed by Windows asyncio, blocks remote socket connections and removes the email API key during tests; it is test-only.

Live-site accessibility and deployment have not been tested. Run the verifier in your own backend environment before deployment; this build's dependency environment was not an exact reproduction of your production lockfile. A truthful 0/3 remains possible when no usable path evidence is collected. The report retains the candidate and describes the uncertainty.

The full release contains ten production files: the seven V7.8 upgrade modules and three matching commercial-architecture prerequisites. This overlay replaces only the four conflicted production files, plus verifier, tests, manifest and documentation. Production code is unchanged from the validated V7.8.1 compatibility release after line-ending normalization.

Use the explicit staging list in `MERGE_NOTES.md`. The uploaded merge status also shows an `index.html` change and a `disclaimer.html` deletion; inspect those existing staged changes before committing. This overlay does not include frontend files. Leave virtual environments, databases and unrelated files out of the release commit.
