from typing import Dict, Any

SOLUTIONS_MATRIX = {
    "SEC-01": {
        "issue": "HTTPS / SSL Encryption Missing",
        "angles": {
            "developer_fix": "Issue an SSL/TLS certificate via Let's Encrypt / Certbot and enforce 301 redirects from HTTP to HTTPS in Nginx/Apache.",
            "cro_copy_angle": "Display security badges (e.g., '256-Bit Encrypted Checkout') near CTA buttons to restore user trust.",
            "infrastructure_angle": "Proxy traffic through Cloudflare with 'Full (Strict)' SSL mode and HSTS enabled."
        }
    },
    "SEO-01": {
        "issue": "Missing Primary Title Tag",
        "angles": {
            "developer_fix": "Inject dynamic `<title>` tag into document `<head>`: `<title>{Page_Name} | {Brand_Name}</title>`.",
            "cro_copy_angle": "Craft high-intent title copy incorporating your main unique value proposition (UVP) to boost Search CTR.",
            "infrastructure_angle": "Set up automated CI/CD SEO linting scripts to fail builds if title tags are missing from layout templates."
        }
    },
    "SEO-03": {
        "issue": "Missing Meta Description",
        "angles": {
            "developer_fix": "Add `<meta name='description' content='...'>` tag inside header components.",
            "cro_copy_angle": "Write a 145-character offer summary ending with a clear CTA (e.g., 'Get a free audit in 60 seconds').",
            "infrastructure_angle": "Implement Open Graph meta fallback scripts at the edge server level."
        }
    },
    "PRF-01": {
        "issue": "Critical Core Web Vitals / Speed Bottlenecks",
        "angles": {
            "developer_fix": "Convert images to WebP/AVIF format, implement lazy loading (`loading='lazy'`), and inline critical CSS.",
            "cro_copy_angle": "Reduce initial visual clutter above the fold so users consume primary value propositions in under 1 second.",
            "infrastructure_angle": "Deploy asset delivery via a global CDN (e.g., Cloudflare/Fastly) with aggressive HTTP/3 caching."
        }
    },
    "UX-01": {
        "issue": "Images Missing Alt Attributes",
        "angles": {
            "developer_fix": "Audit `<img>` elements and add descriptive `alt` tags to all media components.",
            "cro_copy_angle": "Use descriptive image captions and alt text aligned with user intent for visual context.",
            "infrastructure_angle": "Add an automated CMS filter to auto-populate alt fields from image filenames during upload."
        }
    },
    "CONV-02": {
        "issue": "High Latency Conversion Leak",
        "angles": {
            "developer_fix": "Minify JavaScript bundles and defer non-essential third-party analytics scripts.",
            "cro_copy_angle": "Simplify lead capture forms to 2-3 fields to minimize friction caused by slow page response times.",
            "infrastructure_angle": "Scale server memory/CPU or utilize Edge Functions/Serverless rendering to drop Server Response Time under 200ms."
        }
    }
}


def get_3_angle_solutions(code: str, default_name: str, default_rec: str) -> Dict[str, Any]:
    """Returns 3 distinct solution angles (Dev, CRO, Infrastructure) for a given leak."""
    if code in SOLUTIONS_MATRIX:
        entry = SOLUTIONS_MATRIX[code]
        return {
            "leak_code": code,
            "issue": entry["issue"],
            "angles": entry["angles"]
        }
    
    # Generic 3-angle fallback generator
    return {
        "leak_code": code,
        "issue": default_name,
        "angles": {
            "developer_fix": f"Technical Action: {default_rec}",
            "cro_copy_angle": f"Conversion Action: Refine page messaging and CTA layout related to {default_name}.",
            "infrastructure_angle": f"Infrastructure Action: Ensure server policies and hosting setup support {default_name} rules."
        }
    }