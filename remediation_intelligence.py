"""Trilloka V7.4.1 adaptive, research-grounded remediation & outcome intelligence.

This module deliberately does NOT change detection, applicability, scoring, or the
UNKNOWN/FAIL boundary. It improves only what Trilloka does after a finding has
already been verified by the existing V7.3.x engine.

Selection order:
  verified rule -> business category -> customer journey -> context -> research scope
  -> evidence-aware 3-angle remediation -> outcome/verification check.

Research is used as background knowledge and prioritization context. It never proves
that a website has a problem and never licenses unsupported legal/compliance claims.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence

from architecture_model import BUSINESS_TYPE_LABELS, JOURNEY_LABELS
from research_knowledge import research_basis_for_rule
from learning_intelligence import learning_memory


# Category knowledge describes the outcome the website is normally trying to produce,
# the customer concern that should shape remediation, and the measurements that can
# validate improvement. These are guidance lenses, not requirements/failures.
CATEGORY_OUTCOME_PROFILES: Dict[str, Dict[str, Any]] = {
    "ecommerce": {
        "outcome": "completed purchase with clear product, cost, fulfilment and post-purchase expectations",
        "customer_focus": "reduce uncertainty immediately before purchase without hiding material cost, delivery, availability or return information",
        "measurement": "product-view → add-to-cart → checkout-start → purchase completion, plus checkout error and abandonment by stage",
        "systems": "catalog, inventory, shipping, tax, checkout and policy data should remain synchronized",
        "decision_surface": "product, cart and checkout",
    },
    "marketplace": {
        "outcome": "successful buyer/seller or customer/provider match and completed transaction or enquiry",
        "customer_focus": "make identity, reputation, fees, availability, protection and transaction expectations clear on both sides",
        "measurement": "search/listing view → provider/listing selection → contact/transaction start → completed transaction or qualified enquiry",
        "systems": "listing/provider data, reputation, fees, payment/protection and dispute information should remain synchronized",
        "decision_surface": "listing, provider profile and transaction/contact path",
    },
    "local_service": {
        "outcome": "qualified call, quote request or booking from a customer in the service area",
        "customer_focus": "confirm service fit, location/service area, availability, reputation and an easy next step",
        "measurement": "service-page engagement → call/quote/booking start → qualified lead or booked job",
        "systems": "service areas, phone routing, appointment availability, lead ownership and review sources should remain current",
        "decision_surface": "service, location/service-area and contact/quote pages",
    },
    "professional_service": {
        "outcome": "qualified consultation or enquiry from a prospect who understands expertise, process and commercial fit",
        "customer_focus": "reduce uncertainty about expertise, proof, process, pricing expectations and what happens after contact",
        "measurement": "service/expertise view → proof/process engagement → consultation/contact start → qualified opportunity",
        "systems": "service positioning, team credentials, case evidence, lead qualification and response ownership should stay aligned",
        "decision_surface": "service/expertise, proof and consultation/contact pages",
    },
    "healthcare": {
        "outcome": "appropriate appointment or patient enquiry with clear provider/service fit and safe handling expectations",
        "customer_focus": "clarify provider qualifications, treatment/service fit, location, appointment expectations, payment/insurance and sensitive-data trust",
        "measurement": "service/provider view → appointment start → completed booking or qualified patient enquiry",
        "systems": "provider, location, appointment, intake, payment/insurance and privacy information should remain synchronized",
        "decision_surface": "treatment/service, provider and appointment/intake pages",
    },
    "medspa": {
        "outcome": "qualified treatment consultation or booking with realistic expectations and strong practitioner trust",
        "customer_focus": "make treatment fit, practitioner qualifications, expected process, price expectations, proof and booking clarity easy to assess",
        "measurement": "treatment view → proof/practitioner engagement → consultation/booking start → completed appointment",
        "systems": "treatment claims, practitioner credentials, pricing, booking, before/after governance and privacy information should stay current",
        "decision_surface": "treatment, practitioner/proof and booking pages",
    },
    "legal": {
        "outcome": "qualified legal consultation or intake from a prospective client who understands practice fit and next steps",
        "customer_focus": "establish practice-area fit, lawyer identity, jurisdiction, credibility, fee/process expectations and a low-friction confidential contact path",
        "measurement": "practice-area view → lawyer/proof engagement → consultation/intake start → qualified matter",
        "systems": "practice areas, lawyer credentials, intake routing, response expectations and privacy/confidentiality information should stay aligned",
        "decision_surface": "practice-area, lawyer/about and consultation/intake pages",
    },
    "financial_services": {
        "outcome": "qualified advisory/product enquiry or application with clear trust, fit and process expectations",
        "customer_focus": "make adviser/firm credibility, product/service fit, fees, process, assistance and sensitive-data handling understandable before commitment",
        "measurement": "service/product view → trust/process engagement → consultation/application start → qualified client/application",
        "systems": "service/product disclosures, adviser identity, fees, application/consultation routing and policy information should stay synchronized",
        "decision_surface": "service/product, trust/disclosure and consultation/application pages",
    },
    "real_estate": {
        "outcome": "qualified property enquiry, showing, valuation request or agent contact",
        "customer_focus": "make property/market information, agent trust, location, availability and contact/showing actions easy to evaluate",
        "measurement": "listing/service view → property/agent engagement → enquiry/showing/valuation start → qualified lead",
        "systems": "listing inventory, availability/status, agent/contact data, location and lead routing should remain current",
        "decision_surface": "listing/property, agent and enquiry/showing pages",
    },
    "restaurant": {
        "outcome": "reservation, order, call/direction action or confident in-person visit",
        "customer_focus": "make menu/price, hours, location, availability, reputation and reservation/order options obvious on mobile",
        "measurement": "menu/location view → reservation/order/call/directions action → completed booking/order or visit-intent signal",
        "systems": "menu/pricing, hours, location, reservation/order providers and availability should stay synchronized",
        "decision_surface": "menu, location/hours and reservation/order pages",
    },
    "hospitality_event": {
        "outcome": "completed reservation, event enquiry or booking with clear rate/availability and guest expectations",
        "customer_focus": "reduce uncertainty about availability, price/rate, inclusions, location, policies and the booking/enquiry path",
        "measurement": "property/event view → availability/rate interaction → booking/enquiry start → completed reservation/qualified event lead",
        "systems": "availability, rates, inventory, policies, booking provider and event enquiry routing should remain synchronized",
        "decision_surface": "room/event/package, availability/rates and booking/enquiry pages",
    },
    "saas": {
        "outcome": "qualified trial, signup or demo/sales opportunity from a prospect who understands product fit and adoption requirements",
        "customer_focus": "make use case, product reality, pricing, proof, integrations/security and implementation expectations clear before signup or sales contact",
        "measurement": "solution/product view → proof/pricing engagement → trial/demo/signup start → activated trial or qualified sales opportunity",
        "systems": "product capabilities, pricing/plans, integrations, security claims, demo/trial routing and lifecycle measurement should stay aligned",
        "decision_surface": "product/use-case, pricing/proof and demo/trial/signup pages",
    },
    "b2b": {
        "outcome": "qualified RFQ, sales enquiry or procurement conversation from a buyer who can establish technical/commercial fit",
        "customer_focus": "surface capabilities, specifications, industries, proof, certifications, capacity/lead-time and commercial expectations before forcing contact",
        "measurement": "capability/product view → technical/proof engagement → RFQ/contact start → qualified sales/procurement opportunity",
        "systems": "product/capability data, certifications, case evidence, quoting, lead routing and sales qualification should stay aligned",
        "decision_surface": "capability/product, specifications/proof and RFQ/contact pages",
    },
    "agency": {
        "outcome": "qualified project enquiry from a prospect who understands specialty, proof, process and commercial fit",
        "customer_focus": "show relevant work/results, explain process and scope, provide enough pricing/engagement context and make contact low-friction",
        "measurement": "service/work view → case-study engagement → enquiry/start-project action → qualified project opportunity",
        "systems": "service positioning, portfolio/case evidence, pricing/engagement model, intake and follow-up should stay current",
        "decision_surface": "service, work/case-study and enquiry pages",
    },
    "membership_creator": {
        "outcome": "completed membership/subscription signup with clear value, billing and cancellation expectations",
        "customer_focus": "clarify member value, access, billing cadence, renewal/cancellation, trial terms and signup/payment effort",
        "measurement": "offer/pricing view → signup start → completed subscription → activation/retention signal",
        "systems": "offer access, billing, renewal/cancellation, member onboarding and lifecycle measurement should remain synchronized",
        "decision_surface": "offer/pricing, signup/payment and member-expectation pages",
    },
    "education": {
        "outcome": "qualified application, enrollment or advisor enquiry from a learner who understands fit, cost, requirements and outcomes",
        "customer_focus": "make program fit, requirements, cost, outcomes, deadlines, application steps and advisor help easy to understand",
        "measurement": "program view → requirements/cost engagement → application/enquiry start → completed application or qualified prospective student",
        "systems": "program details, tuition/fees, deadlines, admissions requirements, forms and advisor routing should remain synchronized",
        "decision_surface": "program, admissions/cost and application/enquiry pages",
    },
    "nonprofit": {
        "outcome": "completed donation or support action with clear impact, trust and payment expectations",
        "customer_focus": "connect the ask to impact and trust while minimizing donation friction and clearly handling recurring giving/payment choices",
        "measurement": "impact/campaign view → donation start → completed gift, including recurring/mobile completion where relevant",
        "systems": "campaign/impact content, donation forms, payment methods, recurring-gift settings, receipts and donor measurement should stay aligned",
        "decision_surface": "impact/campaign, donation form and payment/confirmation pages",
    },
    "automotive": {
        "outcome": "qualified service booking, vehicle enquiry, test drive, trade-in or parts/contact action",
        "customer_focus": "clarify vehicle/service fit, inventory/availability, price/estimate, location, reputation and the correct next action",
        "measurement": "vehicle/service view → booking/enquiry/call start → completed appointment or qualified sales/service lead",
        "systems": "inventory/service information, pricing/estimates, location, appointment availability and lead routing should remain current",
        "decision_surface": "vehicle/service, pricing/availability and booking/enquiry pages",
    },
    "general": {
        "outcome": "successful completion of the website's verified primary customer action",
        "customer_focus": "remove only evidence-backed friction while preserving working paths",
        "measurement": "primary-action progression and completion",
        "systems": "keep the verified customer path and its supporting information consistent",
        "decision_surface": "verified decision and conversion pages",
    },
}


JOURNEY_OUTCOME_PROFILES: Dict[str, Dict[str, str]] = {
    "lead_quote": {
        "goal": "qualified lead or quote request",
        "friction": "unnecessary qualification effort before the visitor receives value or response expectations",
        "measure": "CTA click → form start → successful submission → qualified lead",
    },
    "appointment_consultation": {
        "goal": "completed appointment or consultation request",
        "friction": "unclear availability, provider/service fit, preparation or booking effort",
        "measure": "booking CTA → scheduler/form start → confirmed appointment or qualified request",
    },
    "reservation_event": {
        "goal": "completed reservation or event booking/enquiry",
        "friction": "availability, date/time/guest requirements, price/location uncertainty or provider handoff failure",
        "measure": "reserve/book action → availability selection → confirmed reservation or qualified event enquiry",
    },
    "direct_purchase": {
        "goal": "completed purchase",
        "friction": "late cost, delivery, trust, account, payment, error or return uncertainty",
        "measure": "product → cart → checkout → completed order, with stage-level abandonment/errors",
    },
    "demo_sales": {
        "goal": "qualified demo or sales conversation",
        "friction": "insufficient product/commercial proof before requiring contact or an overly demanding demo form",
        "measure": "product/pricing → demo CTA → form/scheduler start → qualified meeting/opportunity",
    },
    "membership_subscription": {
        "goal": "completed subscription/membership and successful activation",
        "friction": "unclear value, billing, renewal/cancellation, trial or payment expectations",
        "measure": "offer/pricing → signup → payment → activation/early retention",
    },
    "donation_support": {
        "goal": "completed donation/support action",
        "friction": "weak impact/trust connection, mobile form effort, payment limitations or recurring-gift confusion",
        "measure": "donate CTA → form start → completed gift, including recurring/mobile completion",
    },
    "application_enrollment": {
        "goal": "completed application/enrollment or qualified advisor enquiry",
        "friction": "unclear eligibility, cost, requirements, deadline, document or form expectations",
        "measure": "program/application CTA → application start → completion or qualified advisor handoff",
    },
    "general": {
        "goal": "verified primary customer action",
        "friction": "evidence-backed uncertainty or execution failure",
        "measure": "progression through the verified primary path",
    },
}


# Base solution knowledge. The same verified rule can be executed differently by
# business/journey because the category and journey lenses are added below.
RULE_REMEDIATION_BASE: Dict[str, Dict[str, str]] = {
    "primary_conversion_path": {
        "technical": "Make the verified primary action reliably reachable in the rendered mobile and desktop experience, with a valid destination and no dead-end state.",
        "cro_ux": "Give one dominant next step enough visual and copy clarity to match the visitor's current decision stage; keep secondary actions subordinate rather than removing useful alternatives blindly.",
        "systems": "Define the authoritative primary conversion event, its owner and measurement event, then regression-test the destination after releases.",
        "success": "The intended customer can identify and complete the primary action on the relevant mobile/desktop path, and the completion event can be verified without a new competing-path regression.",
    },
    "conversion_path_error": {
        "technical": "Repair the exact verified broken destination, widget, form, provider handoff or visible error state; add a safe fallback only where the normal path can genuinely fail.",
        "cro_ux": "Preserve the customer's intent through the failure point with clear recovery language instead of sending them back to generic navigation.",
        "systems": "Add synthetic or staging checks for the affected path and monitor provider/API/endpoint health where the conversion depends on an external service.",
        "success": "The same previously failing path reaches its intended completion or safe confirmation state on re-test, with no customer-visible error.",
    },
    "form_architecture": {
        "technical": "Repair the verified form structure/submission path, validation and success/error state before changing unrelated page content.",
        "cro_ux": "Collect only the information needed at this stage and make required fields, validation and what happens next explicit.",
        "systems": "Track form starts, validation failures, successful submissions and downstream routing so the form can be judged by qualified outcomes, not field count alone.",
        "success": "The form submits safely, shows a clear completion/error state, routes correctly, and no longer exhibits the verified structural defect.",
    },
    "lead_form_friction": {
        "technical": "Remove or defer fields that are not needed to begin the verified lead journey, while keeping required validation and routing intact.",
        "cro_ux": "Reduce perceived effort, explain sensitive/high-effort questions and avoid asking for information the visitor cannot reasonably provide yet.",
        "systems": "Compare form-start, completion and qualified-lead rates before/after so reducing friction does not silently reduce lead quality.",
        "success": "The form requires less unnecessary effort and completion improves or holds without degrading qualified downstream outcomes.",
    },
    "checkout_cost_transparency": {
        "technical": "Expose unavoidable shipping, tax, fee or duty information as early as the commerce stack can calculate it and keep totals synchronized through checkout.",
        "cro_ux": "Reduce late surprises by making material total-cost expectations visible before final commitment without crowding the product decision.",
        "systems": "Regression-test total calculations across representative regions, carts, discounts, shipping methods and taxes.",
        "success": "A buyer can understand the material total-cost expectation before the final order step and observed totals remain consistent through checkout.",
    },
    "guest_checkout_barrier": {
        "technical": "Where the commerce model permits it, support a guest completion path and move optional account creation after purchase rather than making registration the technical prerequisite.",
        "cro_ux": "Keep sign-in useful for returning customers while making first-purchase completion obvious for people who do not want an account yet.",
        "systems": "Measure guest vs account checkout completion and post-purchase account creation separately.",
        "success": "Eligible first-time buyers can complete purchase without unnecessary account creation and the checkout still supports returning-account users.",
    },
    "checkout_complexity": {
        "technical": "Remove or conditionally reveal nonessential checkout inputs, preserve autofill and use reliable address/payment controls where supported.",
        "cro_ux": "Group required information into a clear sequence and keep progress/payment expectations visible so the buyer knows what remains.",
        "systems": "Instrument field/stage errors and abandonment so future simplification targets observed friction rather than arbitrary field-count goals.",
        "success": "The verified unnecessary complexity is reduced and checkout-stage completion/error evidence improves or remains healthy.",
    },
    "delivery_expectation_clarity": {
        "technical": "Surface the most specific fulfilment/delivery expectation the operation can actually support at the relevant purchase decision point and keep it driven by current inventory, destination and fulfilment rules where possible.",
        "cro_ux": "Answer 'when should I expect this?' before commitment using a clear date/window or honest dispatch expectation rather than vague speed language.",
        "systems": "Keep the displayed promise synchronized with inventory, cut-off times, fulfilment method, destination and carrier/service rules.",
        "success": "The relevant product/cart/checkout path exposes a consistent, supportable delivery expectation before payment and it matches fulfilment reality.",
    },
    "shipping_info_discoverability": {
        "technical": "Create a reliable, mobile-accessible shipping/delivery information path and surface key regions, methods, cost rules and timing where they affect purchase decisions.",
        "cro_ux": "Let buyers resolve common shipping uncertainty before checkout while linking to full details for edge cases.",
        "systems": "Keep policy content and checkout configuration synchronized so published shipping guidance does not drift from actual calculations.",
        "success": "A buyer can find the applicable shipping conditions from the purchase journey without searching the site, and published terms match checkout behavior.",
    },
    "return_policy_discoverability": {
        "technical": "Expose the real return/refund policy from predictable purchase and footer locations and ensure the policy is readable on mobile.",
        "cro_ux": "Summarize the material reassurance before purchase and link to the detailed conditions without implying broader rights than the business actually offers.",
        "systems": "Synchronize policy, support, checkout and fulfilment language whenever return/refund rules change.",
        "success": "The applicable return/refund conditions are discoverable from the buying path and match the operational policy used by support/fulfilment.",
    },
    "proof_placement_gap": {
        "technical": "Reuse or reference the strongest existing verified proof component on the decision page/section without duplicating stale widgets or changing its source attribution.",
        "cro_ux": "Match proof to the decision it supports and place it close enough to answer the likely hesitation at that point, instead of merely increasing testimonial volume site-wide.",
        "systems": "Define an authoritative proof source, ownership, freshness rule and approval process so moved proof remains genuine and current.",
        "success": "Relevant verified proof is visible at the affected high-consideration decision point and the site no longer exhibits the sitewide-present/decision-point-absent condition.",
    },
    "cross_page_consistency": {
        "technical": "Centralize the affected commercial fact or policy in one source of truth and make templates/components reuse it wherever practical.",
        "cro_ux": "Present one consistent promise across pages the customer is likely to compare so they do not have to decide which value is correct.",
        "systems": "Assign ownership and add publishing QA for material prices, delivery windows, hours, guarantees, fees, policies or other repeated commercial facts.",
        "success": "The conflicting fact is consistent across the previously affected pages and has a clear authoritative source for future changes.",
    },
    "public_unfinished_content": {
        "technical": "Finish, unpublish, restrict or noindex the verified internal/test/placeholder-like page according to its intended audience and remove accidental public navigation/sitemap exposure.",
        "cro_ux": "Prevent customers from encountering content that looks unfinished, internal or accidental while preserving any legitimate customer-facing information elsewhere.",
        "systems": "Add CMS/release safeguards so draft, staging, test or internal pages require an explicit publication decision.",
        "success": "The known accidental page is no longer publicly discoverable or has been completed intentionally, and the scanner can no longer reproduce the hygiene signal.",
    },
    "policy_content_consistency": {
        "technical": "Update the observable policy text so names, processors/tools, addresses, business-model references and linked terms match current operations; preserve version/date controls where used.",
        "cro_ux": "Use clear current policy wording around the relevant data-entry or transaction point without turning the page into legal advice or cluttering the primary action.",
        "systems": "Trigger policy review when forms, processors, fulfilment, subscriptions, locations or material business terms change and obtain qualified legal review where appropriate.",
        "success": "The specific stale/placeholder/inconsistent wording is resolved across the affected public policy surfaces and current operational facts have an owner/review process.",
    },
    "b2b_pricing_transparency": {
        "technical": "Expose the pricing information the business can responsibly publish—exact pricing, ranges, starting points, plan bands or quote drivers—without hard-coding values that sales cannot honor.",
        "cro_ux": "Give researchers enough commercial context to judge fit before demanding contact, while explaining why custom quoting is necessary when it genuinely is.",
        "systems": "Keep website pricing/quote logic aligned with sales qualification and update rules so published expectations do not diverge from proposals.",
        "success": "A qualified buyer can understand the likely commercial model or why a quote is required before contact, and sales/web expectations match.",
    },
    "trust_credentials": {
        "technical": "Expose only real, verifiable licences, certifications, associations, security attestations or professional credentials and link to validation where practical.",
        "cro_ux": "Place the credential where it resolves a relevant trust question rather than creating a decorative badge wall.",
        "systems": "Assign ownership and renewal/expiry checks so outdated credentials are removed or updated.",
        "success": "The relevant decision point exposes current verifiable credentials and expired/unverifiable claims are not relied upon.",
    },
    "reviews_social_proof": {
        "technical": "Surface authentic review/testimonial/customer evidence with stable attribution or valid structured data where appropriate.",
        "cro_ux": "Use the proof most relevant to the offer and customer concern near the decision it supports, rather than maximizing review count alone.",
        "systems": "Maintain a review/proof collection and moderation workflow with freshness/source ownership.",
        "success": "Relevant verifiable proof is discoverable in the affected decision path and remains current/traceable to its source.",
    },
    "about_team_signal": {
        "technical": "Expose a stable About/Team identity path with real people/organization information and relevant credentials where identity matters to the transaction.",
        "cro_ux": "Answer who the customer will trust or work with, using specific expertise and role information rather than generic company language.",
        "systems": "Keep team/ownership/role information current as staff and responsibilities change.",
        "success": "Visitors can verify who is behind the service and the identity information matches the current organization.",
    },
    "privacy_terms_missing": {
        "technical": "Publish and reliably link the applicable public privacy/policy information justified by the site's actual data collection and transaction context; do not add unrelated terms simply to satisfy a checklist.",
        "cro_ux": "Place the policy link where users provide data or transact without obstructing the main action.",
        "systems": "Review the policy when forms, analytics, booking/payment providers, sensitive-data handling or processors change.",
        "success": "The applicable policy is accessible from the relevant data-entry/transaction path and accurately reflects the current observable operation after appropriate review.",
    },
    "phone_visibility": {
        "technical": "Expose the verified business phone number in accessible text and a valid tel: action where calling is a supported customer path.",
        "cro_ux": "Place the number where call-intent users need it without displacing the stronger primary action for visitors who should book, buy or submit online.",
        "systems": "Keep phone routing and public listings synchronized and verify call ownership/hours.",
        "success": "Call-intent users can find and use the correct number on mobile and public phone information remains consistent.",
    },
    "click_to_call": {
        "technical": "Make the relevant verified phone number a valid tel: target with an accessible tappable control on mobile.",
        "cro_ux": "Use click-to-call where calling is a normal decision path, keeping it secondary when another action is commercially primary.",
        "systems": "Monitor routing/hours and keep call tracking from changing the visible canonical business number inconsistently.",
        "success": "The mobile call action launches correctly and routes to the intended business line from the relevant customer path.",
    },
    "location_visibility": {
        "technical": "Expose the real location or service-area information in visible content and appropriate structured data where applicable.",
        "cro_ux": "Put location/directions information where local-intent visitors naturally need it before visiting or booking.",
        "systems": "Synchronize address/service-area/hours information with primary business listings and internal location data.",
        "success": "Visitors can verify where the business serves/operates from the relevant path and public location information is consistent.",
    },
    "measurement_telemetry": {
        "technical": "Verify existing private/server-side measurement first; if absent, instrument the business's actual high-intent events rather than counting generic page views as conversions.",
        "cro_ux": "Keep analytics implementation invisible to the customer experience and avoid unnecessary scripts/events that slow or distract the primary path.",
        "systems": "Define event ownership, naming, consent conditions and validation so measurement remains trustworthy after releases.",
        "success": "The primary journey has validated start/completion events with no duplicate firing and the business can reconcile them with downstream outcomes where possible.",
    },
    "core_web_vitals": {
        "technical": "Use the measured LCP/INP/CLS evidence to isolate the actual rendering, interaction, layout or server bottleneck and fix the highest-impact cause first.",
        "cro_ux": "Protect the first meaningful value proposition and primary action from delayed rendering or layout movement while heavier content loads.",
        "systems": "Store baseline/post-fix field or lab evidence and add performance regression checks after major releases.",
        "success": "The same page improves on the measured failing metric without breaking the primary journey; field data is preferred when available.",
    },
    "mobile_lab_performance": {
        "technical": "Trace the measured mobile bottleneck before optimizing assets; prioritize critical rendering, oversized media, blocking scripts and server response based on evidence.",
        "cro_ux": "Keep the key mobile action and decision information usable before noncritical content finishes loading.",
        "systems": "Retest the same mobile URL and monitor regressions after theme, tag or content deployments.",
        "success": "The measured mobile bottleneck improves on re-test and the key action remains stable/usable during load.",
    },
    "cta_competition": {
        "technical": "Preserve valid secondary actions but ensure the intended primary action has a stable destination, hierarchy and component treatment across the relevant page state.",
        "cro_ux": "Reduce equal-weight competing choices at the key decision point; group secondary actions according to intent rather than deleting them indiscriminately.",
        "systems": "Track the primary and secondary CTA outcomes separately so hierarchy changes are judged by qualified progression rather than click volume alone.",
        "success": "The page has a clear dominant action for the intended journey without removing legitimate alternatives and progression can be measured separately.",
    },
    "diluted_h1": {
        "technical": "Correct the verified page-level heading structure in the rendered document without blindly forcing a single-H1 rule where document structure legitimately differs.",
        "cro_ux": "Make the primary heading communicate the page's real topic/value in the customer's language and support the next decision.",
        "systems": "Add heading/content checks to page templates so future publishing does not recreate the same ambiguity.",
        "success": "The rendered page has an unambiguous primary topic signal and the heading aligns with the page's actual customer intent.",
    },
    "missing_alt_images": {
        "technical": "Add meaningful alternative text to informative images and empty alt attributes to decorative images rather than copying filenames or stuffing keywords.",
        "cro_ux": "Ensure critical product/service/proof information is not communicated only through imagery.",
        "systems": "Add alt-text requirements to the publishing workflow for image types that convey customer-relevant information.",
        "success": "Relevant informative images expose useful text alternatives and decorative images no longer create unnecessary screen-reader noise.",
    },
    "structured_data_missing": {
        "technical": "Add only schema types that accurately describe the observed entity/page and validate the JSON-LD; avoid irrelevant rich-result markup.",
        "cro_ux": "Treat structured data as support for clear visible information, not a replacement for customer-facing content.",
        "systems": "Revalidate schema after CMS/theme/template changes and keep entity details synchronized with visible content.",
        "success": "Valid relevant structured data is present, matches visible content and passes appropriate validation without unsupported claims.",
    },
    "meta_description_missing": {
        "technical": "Add a unique meta description that accurately summarizes the page's real offer/topic without keyword stuffing.",
        "cro_ux": "Write the snippet to help a qualified searcher understand why the page matches their intent, recognizing that search engines may rewrite it.",
        "systems": "Add metadata checks to the publishing template so important pages do not ship blank descriptions.",
        "success": "The important page has an accurate unique description and publishing controls prevent repeat omissions.",
    },
    "https_redirect": {
        "technical": "Force every HTTP request to the equivalent canonical HTTPS destination at the edge/server and verify no redirect loop or inconsistent endpoint remains.",
        "cro_ux": "Keep landing and conversion URLs on one secure canonical path so users never encounter inconsistent secure/non-secure variants.",
        "systems": "Monitor certificate/redirect behavior after DNS, CDN and hosting changes.",
        "success": "HTTP requests consistently reach the intended HTTPS canonical URL and the redirect chain remains healthy.",
    },
}


# High-value category refinements. These alter the execution lens, not whether the
# finding exists. Missing combinations safely fall back to the category profile.
CATEGORY_RULE_REFINEMENTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "ecommerce": {
        "proof_placement_gap": {"ux": "Prefer product-specific ratings/reviews, fit evidence or purchase reassurance near product/cart commitment rather than generic homepage testimonials."},
        "delivery_expectation_clarity": {"technical": "Prioritize product, cart and checkout delivery surfaces in that order according to where the promise becomes knowable."},
        "primary_conversion_path": {"ux": "Keep product selection/add-to-cart/checkout progression visually dominant over newsletter, account and discovery actions at purchase stages."},
    },
    "marketplace": {
        "proof_placement_gap": {"ux": "Use provider/listing-specific reputation and transaction-protection evidence at the selection/contact/transaction stage."},
        "primary_conversion_path": {"systems": "Measure both sides of the marketplace where relevant so improving buyer progression does not create seller/provider dead ends."},
    },
    "local_service": {
        "primary_conversion_path": {"ux": "Prioritize the action customers actually use to secure service—call, quote or booking—near service and local-intent content."},
        "proof_placement_gap": {"ux": "Use recent relevant local/service proof near quote/booking decisions rather than relying on a remote testimonials page."},
    },
    "professional_service": {
        "proof_placement_gap": {"ux": "Match case evidence, credentials or client proof to the specific service/expertise decision before consultation."},
        "b2b_pricing_transparency": {"ux": "Use ranges, engagement models or quote drivers when exact pricing would be misleading for bespoke work."},
    },
    "healthcare": {
        "proof_placement_gap": {"ux": "Favor provider qualifications, appropriate patient/service evidence and clear expectations near appointment decisions; avoid outcome claims that exceed the evidence."},
        "form_architecture": {"systems": "Treat intake and sensitive-data collection as a controlled operational handoff, not merely a marketing form."},
        "policy_content_consistency": {"systems": "Prioritize review when observable policy wording conflicts with current intake, processors or sensitive-data handling; qualified legal/privacy review may be appropriate."},
    },
    "medspa": {
        "proof_placement_gap": {"ux": "Use treatment-relevant practitioner credentials and authentic outcome/proof material close to consultation/booking decisions, with appropriate claim controls."},
        "primary_conversion_path": {"ux": "Make consultation/booking the clear next step after treatment-fit and expectation information, not before essential trust information."},
    },
    "legal": {
        "proof_placement_gap": {"ux": "Use lawyer/practice-area credentials, relevant experience and appropriately framed client evidence close to consultation/intake decisions."},
        "b2b_pricing_transparency": {"ux": "Where exact fees cannot responsibly be published, explain fee structure, consultation terms or the factors that determine cost."},
        "form_architecture": {"systems": "Keep intake routing, confidentiality expectations and matter qualification aligned with the firm workflow."},
    },
    "financial_services": {
        "proof_placement_gap": {"ux": "Use adviser/firm credentials and service-specific trust evidence near consultation/application decisions without implying guarantees."},
        "policy_content_consistency": {"systems": "Review policy/disclosure content when advisers, products, processors, forms or data practices change; escalate legal/compliance review where appropriate."},
    },
    "real_estate": {
        "primary_conversion_path": {"ux": "Match the action to property intent—showing, property enquiry, valuation or agent contact—rather than forcing every visitor into one generic form."},
        "proof_placement_gap": {"ux": "Use agent/property-market credibility and relevant client evidence near enquiry/showing/valuation actions."},
    },
    "restaurant": {
        "primary_conversion_path": {"ux": "Keep menu, reserve/order, hours/location and directions hierarchy appropriate to the restaurant's actual service model, especially on mobile."},
        "proof_placement_gap": {"ux": "Use recent dining/customer proof where a diner is comparing menu/location/reservation choices, not only on a separate reviews page."},
        "location_visibility": {"systems": "Keep hours, address, phone, directions and ordering/reservation destinations aligned with primary local listings."},
    },
    "hospitality_event": {
        "primary_conversion_path": {"ux": "Preserve rate/availability context before booking and route complex event intent to an enquiry path rather than forcing a consumer booking flow."},
        "checkout_cost_transparency": {"ux": "Surface mandatory rate/fee expectations before final reservation commitment while distinguishing optional extras."},
    },
    "saas": {
        "proof_placement_gap": {"ux": "Use product evidence, customer outcomes, security/integration proof or use-case case studies next to pricing/demo/trial decisions."},
        "b2b_pricing_transparency": {"ux": "Use plan/pricing context or clearly explain enterprise/custom pricing triggers before the demo gate."},
        "primary_conversion_path": {"systems": "Separate self-serve signup/trial and sales-assisted demo events so the scanner's recommendation does not collapse distinct acquisition motions."},
    },
    "b2b": {
        "proof_placement_gap": {"ux": "Place capability, certification, case evidence or technical proof beside RFQ/contact decisions for the relevant industry/use case."},
        "b2b_pricing_transparency": {"ux": "Use commercial ranges, minimums, lead-time/capacity or quote drivers when exact unit pricing is not meaningful."},
        "primary_conversion_path": {"systems": "Connect RFQ/contact routing to the appropriate product/region/sales owner so the website handoff does not lose procurement context."},
    },
    "agency": {
        "proof_placement_gap": {"ux": "Link the most relevant work/case study and outcome evidence beside the service/project enquiry that it supports."},
        "b2b_pricing_transparency": {"ux": "Use starting budgets, engagement models or scope drivers when project pricing is bespoke."},
    },
    "membership_creator": {
        "primary_conversion_path": {"ux": "Make join/subscribe progression clear only after value, access, billing and cancellation expectations are understandable."},
        "policy_content_consistency": {"systems": "Keep billing, renewal, cancellation and access language synchronized with the actual subscription platform."},
    },
    "education": {
        "primary_conversion_path": {"ux": "Separate program exploration/advisor help from application submission so prospective students are not pushed into applying before fit is clear."},
        "form_architecture": {"systems": "Preserve application state, requirement/document rules and admissions routing so form simplification does not remove necessary enrollment data."},
    },
    "nonprofit": {
        "primary_conversion_path": {"ux": "Connect the donation/support action directly to clear impact and trust information without burying the giving path."},
        "form_architecture": {"systems": "Measure mobile/desktop and one-time/recurring donation completion separately where the platform supports it."},
        "proof_placement_gap": {"ux": "Use impact evidence, accountability/trust signals and campaign-specific proof near the donation decision."},
    },
    "automotive": {
        "primary_conversion_path": {"ux": "Match the action to intent—service booking, vehicle enquiry, test drive, trade-in or parts—rather than forcing one generic contact path."},
        "proof_placement_gap": {"ux": "Use service/dealer reputation, technician/dealer credentials or vehicle-specific reassurance near booking/enquiry decisions."},
    },
}


CONTEXT_REFINEMENTS: Dict[str, Dict[str, str]] = {
    "regulated_high_trust": {
        "systems": "Preserve a review/approval path for trust, credential, disclosure and policy changes; avoid unsupported claims.",
    },
    "sensitive_data": {
        "technical": "Minimize unnecessary sensitive-data collection at early stages and keep the public data-handling explanation aligned with the actual collection path.",
        "systems": "Treat changes to sensitive-data forms/processors as a trigger for privacy/security review.",
    },
    "commerce_payment": {
        "systems": "Keep pricing, payment, fulfilment and policy data synchronized with the live transaction stack.",
    },
    "local_location_dependent": {
        "systems": "Keep location, hours, phone and service-area information synchronized across the website and primary listings.",
    },
    "enterprise_considered_purchase": {
        "cro_ux": "Give buyers enough evidence to evaluate fit before forcing a sales conversation; preserve deeper proof for later buying stages.",
    },
    "hospitality_event": {
        "systems": "Keep availability, date/time, guest/party and provider data synchronized across the reservation/event path.",
    },
    "recurring_commitment": {
        "cro_ux": "Make billing cadence, renewal, cancellation and ongoing-value expectations clear before commitment.",
    },
    "donation_public_trust": {
        "cro_ux": "Connect the action to credible impact/accountability evidence without overstating outcomes.",
    },
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _append_once(base: str, addition: str) -> str:
    base = _clean(base)
    addition = _clean(addition)
    if not addition:
        return base
    if addition.lower() in base.lower():
        return base
    return f"{base} {addition}".strip()


def _research_summary(basis: Mapping[str, Any]) -> str:
    sources = basis.get("sources") if isinstance(basis, Mapping) else None
    names = []
    if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)):
        for item in sources:
            if isinstance(item, Mapping):
                name = _clean(item.get("source"))
                if name and name not in names:
                    names.append(name)
    return ", ".join(names[:3])


# Category context is intentionally selective. A business type should change a remedy only
# when the actual implementation/decision surface differs by business or journey. Pure
# infrastructure/metadata fixes keep their technical meaning instead of receiving boilerplate
# restaurant/SaaS/etc. sentences that do not help execute the fix.
CATEGORY_DECISION_SURFACE_RULES = {
    "conversion_path_error", "primary_conversion_path", "form_architecture", "lead_form_friction",
    "mobile_sticky_cta", "click_to_call", "proof_placement_gap", "location_visibility",
    "reviews_social_proof", "trust_credentials", "b2b_pricing_transparency",
    "checkout_cost_transparency", "guest_checkout_barrier", "checkout_complexity",
    "delivery_expectation_clarity", "shipping_info_discoverability", "return_policy_discoverability",
    "cross_page_consistency", "public_unfinished_content",
}
CATEGORY_CUSTOMER_FOCUS_RULES = set(CATEGORY_DECISION_SURFACE_RULES)
CATEGORY_OUTCOME_LINK_RULES = {
    "conversion_path_error", "primary_conversion_path", "form_architecture", "lead_form_friction",
    "mobile_sticky_cta", "click_to_call", "proof_placement_gap", "location_visibility",
    "reviews_social_proof", "b2b_pricing_transparency",
    "checkout_cost_transparency", "guest_checkout_barrier", "checkout_complexity",
    "delivery_expectation_clarity", "shipping_info_discoverability", "return_policy_discoverability",
    "cross_page_consistency",
}


def build_outcome_remediation(
    rule_key: str,
    business_type: str,
    journey_model: str,
    context_tags: Iterable[str] | None,
    leak: Mapping[str, Any] | None = None,
    scan_data: Mapping[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """Return category/journey/research-conditioned remediation for a verified finding.

    The caller is responsible for invoking this only after the finding is verified by
    the existing scanner. No failure or score is created here.
    """
    key = _clean(rule_key).lower()
    base = RULE_REMEDIATION_BASE.get(key)
    if not base:
        return None

    business = _clean(business_type).lower() or "general"
    journey = _clean(journey_model).lower() or "general"
    contexts = {_clean(x).lower() for x in (context_tags or []) if _clean(x)}
    category = CATEGORY_OUTCOME_PROFILES.get(business, CATEGORY_OUTCOME_PROFILES["general"])
    jprof = JOURNEY_OUTCOME_PROFILES.get(journey, JOURNEY_OUTCOME_PROFILES["general"])
    research = research_basis_for_rule(key, business, journey, list(contexts))
    research_names = _research_summary(research)

    technical = base["technical"]
    cro = base["cro_ux"]
    systems = base["systems"]
    success = base["success"]

    ref = CATEGORY_RULE_REFINEMENTS.get(business, {}).get(key, {})
    technical = _append_once(technical, ref.get("technical", ""))
    cro = _append_once(cro, ref.get("ux", ""))
    systems = _append_once(systems, ref.get("systems", ""))

    # Apply generic category context only when it materially changes execution. Pure technical
    # foundation/SEO fixes (HTTPS, canonical, schema, metadata, etc.) retain focused remedies.
    if key in CATEGORY_DECISION_SURFACE_RULES:
        technical = _append_once(technical, f"Apply and verify this first on the relevant {category['decision_surface']}.")
    if key in CATEGORY_CUSTOMER_FOCUS_RULES:
        cro = _append_once(cro, f"For this business type, keep the customer decision focused on this need: {category['customer_focus']}.")
    if key in CATEGORY_OUTCOME_LINK_RULES:
        systems = _append_once(systems, f"Validate the change against this outcome path: {category['measurement']}.")

    # Context refinement stays bounded and never turns a missing/unknown observation into a claim.
    for ctx in sorted(contexts):
        cmod = CONTEXT_REFINEMENTS.get(ctx, {})
        if key in {"privacy_terms_missing", "policy_content_consistency", "form_architecture", "lead_form_friction", "trust_credentials"}:
            technical = _append_once(technical, cmod.get("technical", ""))
        if key in {"proof_placement_gap", "primary_conversion_path", "form_architecture", "lead_form_friction", "policy_content_consistency", "checkout_cost_transparency"}:
            cro = _append_once(cro, cmod.get("cro_ux", ""))
        if key in {"privacy_terms_missing", "policy_content_consistency", "form_architecture", "primary_conversion_path", "cross_page_consistency", "checkout_cost_transparency", "delivery_expectation_clarity", "location_visibility"}:
            systems = _append_once(systems, cmod.get("systems", ""))

    business_label = BUSINESS_TYPE_LABELS.get(business, business.replace("_", " ").title())
    journey_label = JOURNEY_LABELS.get(journey, journey.replace("_", " ").title())
    arch = {}
    if isinstance(scan_data, Mapping):
        raw_arch = scan_data.get("architecture_profile") or scan_data.get("business_profile") or {}
        arch = raw_arch if isinstance(raw_arch, Mapping) else {}
    subtype_label = _clean(arch.get("business_subtype_label"))
    marker_resolution = arch.get("journey_marker_resolution") if isinstance(arch.get("journey_marker_resolution"), Mapping) else {}
    path_status = _clean(marker_resolution.get("status"))
    path_completeness = _clean(marker_resolution.get("path_completeness"))

    if research_names:
        why = (
            f"The issue was already verified from this website. For a {business_label} using a {journey_label} journey, "
            f"Trilloka uses scoped research from {research_names} only to sharpen importance and remediation choice; "
            "the research is not treated as proof that the problem exists."
        )
    else:
        why = (
            f"The issue was already verified from this website. The remediation is adapted to the {business_label} "
            f"and its {journey_label} journey rather than applying a generic website fix."
        )

    if subtype_label and subtype_label.lower() != "unresolved":
        why = _append_once(why, f"The identified subtype is {subtype_label}; subtype evidence narrows where the fix should be validated but does not manufacture a finding.")
    if path_status:
        why = _append_once(why, f"Customer-path authority is {path_status}" + (f" with {path_completeness} stage coverage." if path_completeness else "."))

    implementation_method = (
        "1) preserve the evidence/baseline; 2) correct the smallest root cause that explains the verified finding; "
        "3) re-test the same marker-backed customer path; 4) compare the relevant business outcome before expanding the change."
    )
    success_check = success
    if key in CATEGORY_OUTCOME_LINK_RULES:
        success_check = _append_once(success_check, f"Primary outcome to watch: {category['measurement']}.")

    # V7.4 can reuse Architect-confirmed remediation outcomes from earlier scans. This memory
    # never creates the finding and never replaces the research/category baseline; it only sharpens
    # implementation after a human-confirmed outcome has been recorded.
    learned_outcome = {}
    try:
        learned_outcome = learning_memory.outcome_guidance(business, journey, key)
    except Exception:
        learned_outcome = {}
    if learned_outcome:
        technical = _append_once(technical, learned_outcome.get("technical_note", ""))
        cro = _append_once(cro, learned_outcome.get("cro_note", ""))
        systems = _append_once(systems, learned_outcome.get("systems_note", ""))
        success_check = _append_once(success_check, learned_outcome.get("verification_note", ""))
        why = _append_once(why, "Where available, Architect-confirmed outcome history is used as implementation guidance; it is not treated as proof that the same outcome is guaranteed here.")

    return {
        "technical": technical,
        "cro_ux": cro,
        "systems": systems,
        "why_recommend": why,
        "cadence_title": "Evidence-led implementation",
        "cadence_text": implementation_method,
        "success_check": success_check,
        "outcome_measure": category["measurement"],
        "customer_decision_focus": category["customer_focus"],
        "decision_surface": category["decision_surface"],
        "journey_goal": jprof["goal"],
        "journey_measure": jprof["measure"],
        "research_basis": research,
        "research_basis_summary": research_names,
        "remediation_engine": "v7.5_hierarchical_marker_research_outcome",
        "business_subtype": subtype_label or None,
        "journey_path_status": path_status or None,
        "journey_path_completeness": path_completeness or None,
        "learned_outcome_guidance": learned_outcome,
    }


def contextualize_finding(
    rule_key: str,
    business_type: str,
    journey_model: str,
    context_tags: Iterable[str] | None,
) -> Dict[str, str]:
    """Return safe business/journey context for report prose without changing verdicts."""
    business = _clean(business_type).lower() or "general"
    journey = _clean(journey_model).lower() or "general"
    category = CATEGORY_OUTCOME_PROFILES.get(business, CATEGORY_OUTCOME_PROFILES["general"])
    jprof = JOURNEY_OUTCOME_PROFILES.get(journey, JOURNEY_OUTCOME_PROFILES["general"])
    return {
        "business_outcome": category["outcome"],
        "customer_focus": category["customer_focus"],
        "decision_surface": category["decision_surface"],
        "outcome_measure": category["measurement"],
        "journey_goal": jprof["goal"],
        "journey_friction": jprof["friction"],
        "journey_measure": jprof["measure"],
    }


def remediation_knowledge_stats() -> Dict[str, int]:
    category_rule_refinements = sum(len(v) for v in CATEGORY_RULE_REFINEMENTS.values())
    base_fields = sum(len(v) for v in RULE_REMEDIATION_BASE.values())
    return {
        "business_outcome_profiles": len(CATEGORY_OUTCOME_PROFILES) - (1 if "general" in CATEGORY_OUTCOME_PROFILES else 0),
        "journey_outcome_profiles": len(JOURNEY_OUTCOME_PROFILES) - (1 if "general" in JOURNEY_OUTCOME_PROFILES else 0),
        "rule_remediation_profiles": len(RULE_REMEDIATION_BASE),
        "rule_solution_fields": base_fields,
        "category_rule_refinements": category_rule_refinements,
        "context_refinement_profiles": len(CONTEXT_REFINEMENTS),
    }
