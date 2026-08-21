"""Trilloka V6.8 remediation catalog.

The report engine can apply more business-specific wording, while this module provides
safe integration-level fallbacks keyed to the scorer's descriptive rule keys.
Recommendations are verification-first and avoid claiming a specific revenue lift.
"""

from typing import Dict, Any


SOLUTIONS_MATRIX = {
    "SEC-01": {
        "issue": "HTTPS / SSL Encryption Missing",
        "angles": {
            "developer_fix": "Repair TLS/certificate configuration and enforce the intended HTTPS canonical destination. Verify the certificate chain and HTTP-to-HTTPS redirect after deployment.",
            "cro_copy_angle": "Remove browser security warnings from customer journeys. Only display security/compliance claims that are real and independently supportable.",
            "infrastructure_angle": "Automate certificate renewal and monitor expiry, redirect loops and mixed-content regressions.",
        },
    },
    "SEO-01": {
        "issue": "Missing Primary Title Tag",
        "angles": {
            "developer_fix": "Add one descriptive page title in the document head and verify the rendered/source title is present on the affected page.",
            "cro_copy_angle": "Use concise language that identifies the page topic and differentiating value without forcing an arbitrary exact character target.",
            "infrastructure_angle": "Add CMS/build validation so important pages cannot publish with an empty title.",
        },
    },
    "SEO-03": {
        "issue": "Missing Meta Description",
        "angles": {
            "developer_fix": "Add a useful meta description for the affected page and verify it is present in the final rendered/source HTML.",
            "cro_copy_angle": "Summarize the page's real offer and likely search intent naturally; search engines may rewrite snippets, so treat length as a broad readability heuristic rather than a guarantee.",
            "infrastructure_angle": "Add CMS/template validation for missing descriptions on commercially important indexable pages.",
        },
    },
    "PRF-01": {
        "issue": "Measured Mobile Performance Bottleneck",
        "angles": {
            "developer_fix": "Use the captured PageSpeed/CrUX evidence to identify the actual bottleneck before changing assets. Optimize only the resources contributing materially to LCP, INP, CLS or blocking time, then re-test the same URL.",
            "cro_copy_angle": "Keep the primary value proposition and conversion action usable while heavier content loads; do not solve performance by removing useful decision information blindly.",
            "infrastructure_angle": "Record baseline and post-fix measurements and add regression checks after major releases.",
        },
    },
    "UX-01": {
        "issue": "Images Missing Accessibility Text",
        "angles": {
            "developer_fix": "Add meaningful alt text to informative images and appropriate empty/decorative treatment to decorative images. Do not auto-generate alt text from filenames as a blanket fix.",
            "cro_copy_angle": "Prioritize images that explain products, services, proof or instructions so accessibility and comprehension improve together.",
            "infrastructure_angle": "Add a publishing/CMS check that requires authors to classify new images as informative or decorative before publication.",
        },
    },
    "CONV-01": {
        "issue": "Primary Conversion Path Gap",
        "angles": {
            "developer_fix": "Expose a technically usable primary action appropriate to the business model—book, buy, order, request a quote, start a trial, subscribe or contact—and verify the destination resolves.",
            "cro_copy_angle": "Make the highest-intent action visually and verbally clear while keeping secondary actions subordinate.",
            "infrastructure_angle": "Track starts and completed outcomes for the primary path separately so later changes can be evaluated with real behavior data.",
        },
    },
    "CONV-02": {
        "issue": "High Latency Conversion Leak",
        "angles": {
            "developer_fix": "Trace the measured latency source before optimizing. Reduce only verified rendering, script, media or server bottlenecks and re-test the same journey.",
            "cro_copy_angle": "Protect the primary action and decision information from delayed rendering rather than simplifying the funnel based on speed assumptions alone.",
            "infrastructure_angle": "Monitor the measured performance metric over time and alert on material regressions after deployments.",
        },
    },
    "CONV-03": {
        "issue": "Broken / Unresolved Form Submission Architecture",
        "angles": {
            "developer_fix": "Repair the verified form structure so it has a valid server action or complete client-side submission path with usable inputs, submit handling and visible error/success states.",
            "cro_copy_angle": "Keep the form focused on information genuinely needed to start the customer journey and explain why sensitive/high-effort fields are required.",
            "infrastructure_angle": "Add non-destructive form health monitoring and review delivery logs separately; the scanner itself does not submit live customer forms.",
        },
    },
    "CONV-04": {
        "issue": "Broken Customer Conversion Path",
        "angles": {
            "developer_fix": "Repair the exact public error recorded in the evidence receipt—CAPTCHA, booking widget, form rendering, dead destination or external booking URL—and re-check the same URL after the fix.",
            "cro_copy_angle": "Provide a clear fallback action while the primary path is unhealthy so interested visitors are not stranded.",
            "infrastructure_angle": "Monitor critical booking/contact/checkout destinations for known visible error states and 4xx/5xx failures.",
        },
    },
    "CONV-05": {
        "issue": "Mobile Click-to-Call Gap",
        "angles": {
            "developer_fix": "Where calling is relevant to the business model, make the verified public phone number a valid tel: action with a comfortably tappable mobile target.",
            "cro_copy_angle": "Use calling as the primary or secondary action only where customer intent supports it; do not displace a stronger booking/order/quote path.",
            "infrastructure_angle": "Track call-click events separately from completed leads or bookings if attribution is useful to the business.",
        },
    },
    "CONV-06": {
        "issue": "Persistent Mobile Action Gap",
        "angles": {
            "developer_fix": "Where persistence is business-appropriate, implement a fixed/sticky primary action with safe-area spacing and no overlap with consent/chat controls.",
            "cro_copy_angle": "Keep one dominant persistent action aligned to the business's real customer journey rather than stacking competing buttons.",
            "infrastructure_angle": "Track sticky-action impressions/clicks separately and remove it if behavior data shows no useful progression benefit.",
        },
    },
    "MEAS-01": {
        "issue": "Common Measurement Layer Not Detected",
        "angles": {
            "developer_fix": "First verify whether a private/server-side or less common measurement system already exists. If not, implement an appropriate analytics layer and validate key conversion events with suitable consent handling.",
            "cro_copy_angle": "Define a small set of meaningful progression events rather than labelling every click a conversion.",
            "infrastructure_angle": "Maintain an event/measurement map and periodically validate that events still fire once after site changes.",
        },
    },
    "TRUST-01": {
        "issue": "Credential / Trust Signal Gap",
        "angles": {
            "developer_fix": "Publish only real, current professional/licensing/security credentials and link to authoritative validation where practical.",
            "cro_copy_angle": "Place relevant proof near the decision it supports rather than building a decorative badge wall.",
            "infrastructure_angle": "Assign ownership and renewal review so expired or misleading credentials are removed promptly.",
        },
    },
    "TRUST-02": {
        "issue": "Relevant Proof Gap",
        "angles": {
            "developer_fix": "Expose an appropriate proof path for the business model—reviews, testimonials, credentials, customer evidence or case studies—using verifiable source material.",
            "cro_copy_angle": "Place proof close to high-consideration decisions and make it specific enough to reduce uncertainty.",
            "infrastructure_angle": "Create a process for collecting, permissioning, updating and retiring proof so it remains genuine and current.",
        },
    },
    "TRUST-03": {
        "issue": "Required Policy Link Gap",
        "angles": {
            "developer_fix": "Publish and link the privacy/terms/return policies actually required by the site's data, account or commerce behavior. Avoid boilerplate that does not match real practices.",
            "cro_copy_angle": "Make relevant policy reassurance discoverable near forms, checkout or account creation without overwhelming the primary action.",
            "infrastructure_angle": "Review policies when tracking, payment, data collection, subscription or service terms change.",
        },
    },
    "ECOM-01": {
        "issue": "Checkout Cost Transparency Risk",
        "angles": {
            "developer_fix": "Expose material mandatory costs as early and accurately as the commerce stack permits; verify totals and calculation behavior across the checkout journey.",
            "cro_copy_angle": "Set clear expectations about shipping, taxes or fees before the final commitment step where possible.",
            "infrastructure_angle": "Regression-test pricing/fee rules after shipping, tax or promotion configuration changes.",
        },
    },
    "ECOM-02": {
        "issue": "Guest Checkout Barrier",
        "angles": {
            "developer_fix": "Where the platform/business allows it, let customers complete checkout without creating an account or explain why an account is genuinely required.",
            "cro_copy_angle": "Avoid making account creation feel like an unrelated commitment before purchase completion.",
            "infrastructure_angle": "Measure checkout completion by account path so the business can validate whether account requirements create real friction.",
        },
    },
    "ECOM-03": {
        "issue": "Checkout Complexity",
        "angles": {
            "developer_fix": "Remove duplicate/unnecessary fields only after verifying which data the order, payment, tax and fulfilment systems actually require.",
            "cro_copy_angle": "Group fields logically and explain unusual requests rather than optimizing to an arbitrary universal field count.",
            "infrastructure_angle": "Track field-level errors and abandonment to identify real friction before redesigning the checkout.",
        },
    },
    "ECOM-04": {
        "issue": "Return / Refund Discoverability Gap",
        "angles": {
            "developer_fix": "Publish the actual return/refund/cancellation policy and link it consistently from relevant shopping and checkout surfaces.",
            "cro_copy_angle": "Surface the policy where it reduces purchase uncertainty without making unsupported guarantees.",
            "infrastructure_angle": "Keep storefront wording synchronized with operational fulfilment/refund rules.",
        },
    },
    "B2B-01": {
        "issue": "B2B Evaluation / Pricing Information Gap",
        "angles": {
            "developer_fix": "Expose enough qualification information—pricing, ranges, packaging, quote path or buying criteria—for the intended sales model without forcing a pricing page when negotiated sales genuinely require discovery.",
            "cro_copy_angle": "Tell prospects what happens next and what information they need before requesting a quote/demo.",
            "infrastructure_angle": "Track qualified demo/quote progression so the amount of public pricing information can be adjusted using observed lead quality rather than assumption.",
        },
    },
    "CONTENT-01": {
        "issue": "Generic Hero / Template Positioning",
        "angles": {
            "developer_fix": "Keep one clear primary semantic heading and verify it renders consistently across key viewports.",
            "cro_copy_angle": "Replace interchangeable claims with specific customer outcomes, service/product scope and verifiable differentiators.",
            "infrastructure_angle": "Use a content review checklist that requires concrete proof/examples before publishing generic value claims.",
        },
    },
}


RULE_KEY_TO_SOLUTION_CODE = {
    "unsecured_ssl": "SEC-01",
    "https_redirect": "SEC-01",
    "meta_description_missing": "SEO-03",
    "core_web_vitals": "PRF-01",
    "pagespeed_below_60": "PRF-01",
    "pagespeed_below_90": "PRF-01",
    "lcp_poor": "PRF-01",
    "inp_poor": "PRF-01",
    "cls_poor": "PRF-01",
    "render_blocking": "PRF-01",
    "lazy_loading_gap": "PRF-01",
    "missing_alt_images": "UX-01",
    "primary_conversion_path": "CONV-01",
    "form_architecture": "CONV-03",
    "unlinked_form_structure": "CONV-03",
    "conversion_path_error": "CONV-04",
    "click_to_call": "CONV-05",
    "mobile_sticky_cta": "CONV-06",
    "measurement_telemetry": "MEAS-01",
    "retargeting_telemetry": "MEAS-01",
    "trust_credentials": "TRUST-01",
    "reviews_social_proof": "TRUST-02",
    "social_proof_signal": "TRUST-02",
    "privacy_terms_missing": "TRUST-03",
    "checkout_cost_transparency": "ECOM-01",
    "guest_checkout_barrier": "ECOM-02",
    "checkout_complexity": "ECOM-03",
    "return_policy_discoverability": "ECOM-04",
    "b2b_pricing_transparency": "B2B-01",
    "diluted_h1": "CONTENT-01",
    "generic_headline": "CONTENT-01",
}


def _resolve_solution_code(code: str) -> str:
    raw = str(code or "").strip()
    if not raw:
        return raw
    upper = raw.upper()
    if upper in SOLUTIONS_MATRIX:
        return upper
    return RULE_KEY_TO_SOLUTION_CODE.get(raw.lower(), raw)


def get_3_angle_solutions(code: str, default_name: str, default_rec: str) -> Dict[str, Any]:
    """Return safe 3-angle fallback remediation for a catalog code or descriptive rule_key."""
    original_code = str(code or "").strip()
    resolved_code = _resolve_solution_code(original_code)
    if resolved_code in SOLUTIONS_MATRIX:
        entry = SOLUTIONS_MATRIX[resolved_code]
        return {
            "leak_code": original_code or resolved_code,
            "solution_code": resolved_code,
            "issue": entry["issue"],
            "angles": entry["angles"],
        }
    return {
        "leak_code": original_code,
        "solution_code": None,
        "issue": default_name,
        "angles": {
            "developer_fix": f"Technical Action: Verify the attached evidence for {default_name}, correct only the observed condition, then re-scan the same URL.",
            "cro_copy_angle": f"Conversion Action: Improve the customer-facing decision/action affected by {default_name} without changing unrelated page elements.",
            "infrastructure_angle": f"Systems Action: Add monitoring or publishing safeguards appropriate to {default_name} so the verified issue is less likely to recur.",
        },
    }
