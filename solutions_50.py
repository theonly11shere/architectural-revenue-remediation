# solutions_50.py
"""
Trilloka Multi-Angle Solution Engine
Provides targeted, industry-aware remediation strategies across 3 angles:
1. Technical Angle (Performance, Code, Infrastructure)
2. UX / CRO Angle (User Experience, Friction Removal, Conversion)
3. Systems Angle (Automation, Cadence, Operations)
"""

SOLUTION_MATRIX = {
    "mobile_speed": {
        "medspa": {
            "technical": "Compress high-resolution before/after hero gallery images to WebP format to drop mobile LCP below 2.0s.",
            "ux_cro": "Add a sticky 'Book Consultation' bottom-bar widget on mobile so users can convert instantly while media components finish rendering.",
            "systems": "Implement an automated CDN optimization rule on your host server so newly uploaded treatment photos compress automatically."
        },
        "ecommerce": {
            "technical": "Defer non-critical store tracking apps and third-party scripts clogging main-thread execution time (INP).",
            "ux_cro": "Implement a 1-click 'Buy Now' instant drawer cart to eliminate extra page load steps on slow cellular networks.",
            "systems": "Establish a monthly app audit protocol to purge uninstalled or redundant tracking scripts."
        },
        "legal": {
            "technical": "Pre-connect external font and map API servers to eliminate layout shift (CLS) during initial mobile render.",
            "ux_cro": "Place a prominent 'Tap-to-Call / 24/7 Case Evaluation' sticky button above the fold for immediate contact.",
            "systems": "Migrate hosting to a dedicated edge-cached server to handle peak local search traffic without execution lag."
        },
        "saas": {
            "technical": "Strip unused CSS frameworks and split JavaScript bundles so core landing page assets execute in under 1.5 seconds.",
            "ux_cro": "Simplify the interactive demo or sign-up form into a single-field email capture on mobile viewports.",
            "systems": "Setup automated Core Web Vitals monitoring alerts in your CI/CD deployment pipeline."
        },
        "general": {
            "technical": "Optimize critical rendering path assets, convert legacy JPEGs to WebP/AVIF, and defer render-blocking JavaScript.",
            "ux_cro": "Ensure primary value propositions and direct CTAs appear in the first 300px of mobile viewport space.",
            "systems": "Set up automated image pipeline compression on all server uploads."
        }
    },
    
    "trust_social_proof": {
        "medspa": {
            "technical": "Embed asynchronous review widgets that load dynamically without penalizing Google PageSpeed scores.",
            "ux_cro": "Display verified client outcome badges and practitioner credentials directly adjacent to the booking calendar button.",
            "systems": "Set up automated post-appointment SMS triggers to request client reviews within 2 hours of treatment."
        },
        "legal": {
            "technical": "Structure case result markup using JSON-LD schema so recent settlements display directly in Google Search snippets.",
            "ux_cro": "Feature total dollars recovered and client video testimonials prominently right below the primary headline.",
            "systems": "Implement an automated intake follow-up sequence that sends past client success stories every 3 days to warm leads."
        },
        "ecommerce": {
            "technical": "Integrate lightweight star-rating micro-data (AggregateRating schema) across all product listing templates.",
            "ux_cro": "Show real-time purchase popups or verified buyer photos on high-margin product pages.",
            "systems": "Automate post-delivery review request emails offering a micro-discount for photo or video reviews."
        },
        "saas": {
            "technical": "Add verified G2/Capterra review badges via asynchronous embeds to preserve interactive performance.",
            "ux_cro": "Display recognizable client logo banners and real-time customer usage metrics above the fold.",
            "systems": "Establish an automated trigger that prompts active power users for a review on day 14 post-onboarding."
        },
        "general": {
            "technical": "Load third-party review widgets using lazy-loading protocols to preserve page interactive timing.",
            "ux_cro": "Place real customer quotes and trust seals within arm's reach of your main lead collection forms.",
            "systems": "Establish a process to collect and publish 3 to 5 new customer feedback highlights every week."
        }
    },

    "content_authority": {
        "medspa": {
            "technical": "Inject FAQ Schema (JSON-LD) on all treatment pages to capture voice search and featured snippet real estate.",
            "ux_cro": "Create bite-sized 15-second treatment explainer videos directly on service landing pages.",
            "systems": "Maintain a strict content cadence: post 3 treatment highlights or educational breakdowns every 3 days across core channels."
        },
        "legal": {
            "technical": "Build structured practice-area hub pages with internal linking architecture to pass domain authority.",
            "ux_cro": "Offer downloadable 'Know Your Rights' PDF guides in exchange for prospective client contact details.",
            "systems": "Publish 2 detailed case analysis articles per week, alternating between legal tips, client FAQs, and firm news."
        },
        "ecommerce": {
            "technical": "Implement dynamic canonical tags and fix duplicate content parameters across product variation filters.",
            "ux_cro": "Add user-generated video shorts directly to product galleries to increase time-on-site.",
            "systems": "Post 3 short-form video demonstrations every 3 days across active social channels."
        },
        "saas": {
            "technical": "Build automated programmatic SEO landing page templates targeting long-tail integration keywords.",
            "ux_cro": "Include interactive ROI/savings calculators directly on pricing and feature pages.",
            "systems": "Publish 1 deep-dive technical case study per week while syndicating micro-insights every 3 days."
        },
        "general": {
            "technical": "Add structured organization schema and clean up broken internal redirects.",
            "ux_cro": "Diversify content formats into digestible micro-content (infographics, short text, bulleted guides).",
            "systems": "Publish content on a disciplined schedule: 3 updates every 3 days, varying topics between technical value, proof, and updates."
        }
    }
}

def get_tailored_solutions(biz_type: str = "general") -> dict:
    """
    Dynamically fetches multi-angle solutions tailored to the business type.
    Returns structured data for Speed, Trust, and Content Authority.
    """
    industry = biz_type.lower() if biz_type.lower() in ["medspa", "legal", "ecommerce", "saas"] else "general"
    
    return {
        "mobile_speed": SOLUTION_MATRIX["mobile_speed"].get(industry, SOLUTION_MATRIX["mobile_speed"]["general"]),
        "trust_social_proof": SOLUTION_MATRIX["trust_social_proof"].get(industry, SOLUTION_MATRIX["trust_social_proof"]["general"]),
        "content_authority": SOLUTION_MATRIX["content_authority"].get(industry, SOLUTION_MATRIX["content_authority"]["general"])
    }

def get_top_solutions_list(biz_type: str = "general") -> list:
    """
    Returns a flat list of solutions to maintain backward compatibility with report generators.
    """
    tailored = get_tailored_solutions(biz_type)
    return [
        tailored["mobile_speed"]["technical"],
        tailored["trust_social_proof"]["ux_cro"],
        tailored["content_authority"]["systems"],
        tailored["mobile_speed"]["ux_cro"],
        tailored["trust_social_proof"]["systems"],
        tailored["content_authority"]["technical"]
    ]