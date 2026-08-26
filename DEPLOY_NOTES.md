# Trilloka V7.2.1 — Deployment Notes

This package contains the Blueprint90 scorer, real-world financial calibration, and V7.1.1 network/SSRF hardening carried forward into V7.2.1.

## Install

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Verify

```powershell
python run_all_tests.py
```

Expected result for this exact build after packaging:

- 77 regression tests passed
- 29/29 integrity checks passed
- 36/36 synthetic Blueprint90 cases passed across 6 customer-journey models and 6 maturity bands
- warnings-as-errors compilation passed
- runtime import reports FastAPI 7.2.1 / scanner v7.2.1

## Public score blueprint

The internal three-layer method remains 22 / 60 / 18 canonical points. Public `overall_score` is a transparent monotonic 0–90 calibration. Frontends should use the API `score_ceiling`/`score_formula.public_score_ceiling` value rather than hardcoding `/100`.

## Important environment values

Keep secrets in the hosting environment, never in Git.

Google / scanning:
- `GOOGLE_API_KEY` or `GOOGLE_PLACES_API_KEY`
- `PAGESPEED_API_KEY` where used
- `TRILLOKA_COMPETITOR_RADIUS_METERS`
- `TRILLOKA_COMPETITOR_MAX_RESULTS`
- `TRILLOKA_JOURNEY_MAX_PAGES`
- `TRILLOKA_CONFIRMATION_THRESHOLD_POINTS`

Network security:
- `TRILLOKA_ALLOWED_TARGET_PORTS` — optional, defaults to `80,443`
- `TRILLOKA_BROWSER_TRUSTED_HOSTS` — optional additional trusted browser provider suffixes

Access / admin:
- `SCAN_ACCESS_SECRET`
- `SCAN_ACCESS_DB_PATH`
- `TRILLOKA_PLAN_ACTIVATION_KEY`
- `TRILLOKA_PROTECTED_DOMAINS`
- `TRILLOKA_ALLOWED_ORIGINS`
- `TRILLOKA_ADMIN_EMAIL`
- `TRILLOKA_ADMIN_FROM_EMAIL`
- `TRILLOKA_ADMIN_SESSION_SECRET`
- `RESEND_API_KEY`

Browser:
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE` only if the host requires it.

## Post-deploy smoke test

Confirm `/health` reports V7.2.1, then run one real lead/quote site, one direct-purchase site and one deliberately weak site. Also confirm localhost, RFC1918, metadata/link-local and non-http(s) targets remain blocked.

The local validation suite is offline. Live Google APIs, production DNS/networking, Chromium installation, Render credentials and frontend wiring still require deployment smoke testing.

## V7.2.1 journey-classification correction

This patch adds a diversified multi-service B2B guardrail discovered during the first V7.2 production scan. A secondary medical/service page can no longer overpower a company-level B2B lead/project inquiry journey without primary-surface or booking corroboration.

For the Fairweather-style regression fixture, the corrected model resolves to `lead_quote` with `enterprise_considered_purchase`; secondary medical-service language does not create a company-wide `regulated_high_trust` tag by itself. Reusing the same three verified leak families from the original scan produces a lead/quote scenario of `$500 – $16,500 / year — LOW scenario exposure` with a `$7,500` central estimate. A fresh production scan must still confirm the live site evidence.
