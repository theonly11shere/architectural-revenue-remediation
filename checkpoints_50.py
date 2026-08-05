from typing import Dict, Any

CHECKPOINT_CATALOG: Dict[str, Dict[str, Any]] = {
    # SECURITY & INFRASTRUCTURE
    "SEC-01": {"category": "Security", "name": "HTTPS Encryption Protocol", "weight": 10.0, "desc": "Valid SSL/TLS certificate enabled."},
    "SEC-02": {"category": "Security", "name": "HTTP 200 OK Server Response", "weight": 10.0, "desc": "Primary domain returns valid status code."},
    "SEC-03": {"category": "Security", "name": "Canonical Host Redirects", "weight": 5.0, "desc": "Proper redirect handling between WWW and non-WWW."},
    "SEC-04": {"category": "Security", "name": "Strict Transport Security (HSTS)", "weight": 4.0, "desc": "HSTS response header enforcement."},
    "SEC-05": {"category": "Security", "name": "Content Security Policy (CSP)", "weight": 4.0, "desc": "XSS attack prevention headers."},
    "SEC-06": {"category": "Security", "name": "X-Frame-Options Header", "weight": 3.0, "desc": "Clickjacking protection enabled."},
    "SEC-07": {"category": "Security", "name": "X-Content-Type-Options", "weight": 3.0, "desc": "MIME sniffing prevention."},
    "SEC-08": {"category": "Security", "name": "Referrer-Policy Header", "weight": 3.0, "desc": "Privacy compliance on outgoing request headers."},
    "SEC-09": {"category": "Security", "name": "Mixed Content Audit", "weight": 4.0, "desc": "Zero HTTP resources loaded over HTTPS."},
    "SEC-10": {"category": "Security", "name": "TLS Protocol Version", "weight": 4.0, "desc": "Modern TLS 1.2 or 1.3 protocol requirement."},

    # SEO FOUNDATIONS
    "SEO-01": {"category": "SEO", "name": "Title Tag Existence", "weight": 8.0, "desc": "Document title element present."},
    "SEO-02": {"category": "SEO", "name": "Title Tag Length Optimization", "weight": 6.0, "desc": "Title length between 30 and 60 characters."},
    "SEO-03": {"category": "SEO", "name": "Meta Description Existence", "weight": 8.0, "desc": "Meta description tag present."},
    "SEO-04": {"category": "SEO", "name": "Meta Description Length", "weight": 5.0, "desc": "Meta description length between 50 and 160 characters."},
    "SEO-05": {"category": "SEO", "name": "H1 Heading Tag Presence", "weight": 8.0, "desc": "At least one H1 tag present in DOM."},
    "SEO-06": {"category": "SEO", "name": "Single Primary H1 Enforcement", "weight": 4.0, "desc": "Exactly one H1 tag present per page."},
    "SEO-07": {"category": "SEO", "name": "Google SEO Score >= 80", "weight": 10.0, "desc": "Google PageSpeed API SEO audit threshold met."},
    "SEO-08": {"category": "SEO", "name": "Open Graph Meta Tags", "weight": 3.0, "desc": "Social share metadata present."},
    "SEO-09": {"category": "SEO", "name": "Robots.txt Availability", "weight": 4.0, "desc": "Crawler access instructions available at /robots.txt."},
    "SEO-10": {"category": "SEO", "name": "Sitemap Indexing Link", "weight": 4.0, "desc": "XML Sitemap endpoint detected."},

    # PERFORMANCE & WEB VITALS
    "PRF-01": {"category": "Performance", "name": "Google Lighthouse Performance >= 90", "weight": 15.0, "desc": "Top-tier speed score."},
    "PRF-02": {"category": "Performance", "name": "Google Lighthouse Performance >= 70", "weight": 10.0, "desc": "Baseline acceptable speed score."},
    "PRF-03": {"category": "Performance", "name": "Live PageSpeed API Response", "weight": 5.0, "desc": "Successful real-time execution via Google API."},
    "PRF-04": {"category": "Performance", "name": "First Contentful Paint (FCP)", "weight": 5.0, "desc": "Visual content loads within fast threshold."},
    "PRF-05": {"category": "Performance", "name": "Largest Contentful Paint (LCP)", "weight": 5.0, "desc": "Main content rendered within 2.5s."},
    "PRF-06": {"category": "Performance", "name": "Cumulative Layout Shift (CLS)", "weight": 4.0, "desc": "Minimal visual shifts during render."},
    "PRF-07": {"category": "Performance", "name": "Total Blocking Time (TBT)", "weight": 4.0, "desc": "Low main thread processing delays."},
    "PRF-08": {"category": "Performance", "name": "DOM Size Optimization", "weight": 4.0, "desc": "Total DOM elements under recommended threshold."},
    "PRF-09": {"category": "Performance", "name": "Asset Compression (Gzip/Brotli)", "weight": 4.0, "desc": "Text-based assets compressed in flight."},
    "PRF-10": {"category": "Performance", "name": "Cache Control Headers", "weight": 4.0, "desc": "Static asset caching policies set."},

    # CONTENT & UX
    "UX-01": {"category": "UX & Content", "name": "Image Alt Attribute Coverage", "weight": 10.0, "desc": "All img tags possess non-empty alt text."},
    "UX-02": {"category": "UX & Content", "name": "Accessibility Compliance Rate >= 80%", "weight": 6.0, "desc": "Majority of media contains fallback text."},
    "UX-03": {"category": "UX & Content", "name": "DOM Content Volume", "weight": 8.0, "desc": "Sufficient textual content for indexation."},
    "UX-04": {"category": "UX & Content", "name": "Mobile Viewport Meta Tag", "weight": 5.0, "desc": "Responsive layout declaration present."},
    "UX-05": {"category": "UX & Content", "name": "Font Display Optimization", "weight": 3.0, "desc": "Custom fonts set to font-display: swap."},
    "UX-06": {"category": "UX & Content", "name": "Favicon Presence", "weight": 3.0, "desc": "Icon asset declared for browser tabs."},
    "UX-07": {"category": "UX & Content", "name": "Broken Link Auditing", "weight": 4.0, "desc": "No dead internal hyperlinking detected."},
    "UX-08": {"category": "UX & Content", "name": "HTML Language Attribute", "weight": 3.0, "desc": "lang attribute defined on html tag."},
    "UX-09": {"category": "UX & Content", "name": "Interactive Touch Targets", "weight": 4.0, "desc": "Clickable elements padded appropriately for mobile."},
    "UX-10": {"category": "UX & Content", "name": "Text Contrast Standards", "weight": 4.0, "desc": "Sufficient contrast ratio between text and background."},

    # CONVERSION READINESS
    "CONV-01": {"category": "Conversion", "name": "Secure Transaction Foundation", "weight": 10.0, "desc": "Trust indicators and SSL present."},
    "CONV-02": {"category": "Conversion", "name": "Speed Retain Threshold", "weight": 10.0, "desc": "Load speed optimized to prevent user drop-off."},
    "CONV-03": {"category": "Conversion", "name": "CTA Visibility Above the Fold", "weight": 5.0, "desc": "Primary action button visible immediately."},
    "CONV-04": {"category": "Conversion", "name": "Lead Capture Form Presence", "weight": 5.0, "desc": "Input forms detected for lead generation."},
    "CONV-05": {"category": "Conversion", "name": "Analytics Tracking Tag", "weight": 4.0, "desc": "Google Analytics or tracking snippet integrated."},
    "CONV-06": {"category": "Conversion", "name": "Social Proof Indicators", "weight": 4.0, "desc": "Testimonials or trust badges detected."},
    "CONV-07": {"category": "Conversion", "name": "Clear Value Proposition", "weight": 4.0, "desc": "H1/Hero text contains descriptive offer."},
    "CONV-08": {"category": "Conversion", "name": "Contact Information Access", "weight": 3.0, "desc": "Phone, email, or contact link in header/footer."},
    "CONV-09": {"category": "Conversion", "name": "Page Speed Bounce Risk", "weight": 5.0, "desc": "Estimated bounce risk from load latency below 15%."},
    "CONV-10": {"category": "Conversion", "name": "Niche Flow Optimization", "weight": 4.0, "desc": "Layout matches business model best practices."}
}