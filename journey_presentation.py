"""Public-safe path summary shared by reports and API. No scoring/routing decisions."""
from html import escape
import math
from typing import Mapping

PATH_LABELS = {
    'general': 'Not yet established', 'direct_purchase': 'Direct Purchase',
    'local_visit': 'Local Visit', 'reservation_event': 'Reservation / Event',
    'appointment_consultation': 'Appointment / Consultation', 'lead_quote': 'Enquiry / Quote',
    'demo_sales': 'Demo / Sales', 'membership_subscription': 'Membership / Subscription',
    'donation_support': 'Donation / Support', 'application_enrollment': 'Application / Enrollment',
}
ACTION_LABELS = {'primary_site_action':'Still being verified', 'contact':'Contact the business',
    'order':'Place an order', 'buy':'Make a purchase', 'book':'Make a booking',
    'quote':'Request a quote', 'demo':'Request a demo', 'trial':'Start a trial',
    'subscribe':'Subscribe', 'apply':'Apply', 'donate':'Donate', 'visit':'Plan a visit'}
MARKER_LABELS = {'external_handoff':'External action destination observed', 'add_to_cart':'Add to cart',
    'contact_fields':'Contact form fields', 'visit_location':'Visit location', 'order':'Order',
    'reserve':'Reserve', 'book':'Book', 'buy':'Purchase'}

def customer_action(value):
    value = str(value or '')
    return ACTION_LABELS.get(value, value.replace('_', ' ').capitalize() if value else 'Still being verified')

def build_journey_summary(profile):
    p = profile if isinstance(profile, Mapping) else {}
    if 'journey_marker_resolution' not in p and isinstance(p.get('journey_summary'), Mapping): return dict(p['journey_summary'])
    r = p.get('journey_marker_resolution') or {}
    candidate = p.get('weighted_journey_candidate') or 'general'
    confirmed = bool(p.get('journey_resolved')) and bool(r.get('resolved')) and not r.get('primary_ordering_ambiguous') and not r.get('architect_review_required')
    # Evidence belongs to one path. Never combine a weighted candidate's label with another path's count.
    evidence_path = r.get('best_supported_journey') or next((x.get('journey_model') for x in r.get('ranked_paths', []) if x.get('authority')), 'general')
    proof = r.get('proof') or {}
    stages = []
    for key, label in [('action','Action'),('progression','Progression'),('terminal','Confirmed outcome')]:
        markers = proof.get(key) or []
        stages.append({'stage':label, 'observed':bool(markers),
                       'description': ', '.join(MARKER_LABELS.get(m, m.replace('_',' ').capitalize()) for m in markers)
                       if markers else ('Not safely tested' if key == 'terminal' else 'Not yet observed')})
    confidence = p.get('weighted_journey_candidate_confidence')
    try:
        confidence = float(confidence) if confidence is not None else None
        confidence = round(max(0,min(1,confidence))*100) if confidence is not None and math.isfinite(confidence) else None
    except (ValueError,TypeError,OverflowError): confidence = None
    outcome_unknown = not bool(proof.get('terminal'))
    review_required = not confirmed or outcome_unknown
    paths = r.get('candidate_journeys') or (p.get('differentiation_plan') or {}).get('candidate_journeys') or []
    return {
        'business': p.get('business_type_label') or 'Not confidently resolved',
        'subtype': p.get('business_subtype_label') or 'Not confidently resolved',
        'commercial_context': ' / '.join(p.get('context_labels') or []) or 'Not yet established',
        'paths_under_investigation': [PATH_LABELS.get(j,'Other customer path') for j in paths],
        'best_supported_candidate': PATH_LABELS.get(candidate,'Not yet established'),
        'candidate_confidence_percent': confidence,
        'authority_confirmed_primary_path': PATH_LABELS.get(p.get('journey_model'),'Still being verified') if confirmed else 'Still being verified',
        'evidence_path': PATH_LABELS.get(evidence_path,'Not yet established'),
        'path_evidence': r.get('path_completeness') or '0/3',
        'evidence_status': str(r.get('status') or 'UNVERIFIED').replace('_',' '),
        'stages': stages,
        'architect_review_required': review_required,
        'architect_review': ('Required before journey-dependent scoring or primary/secondary ordering is approved.' if not confirmed else 'Required for any unresolved outcome that affects scoring.' if outcome_unknown else 'No unresolved path evidence requires review; other findings may still require it.'),
    }

def render_journey_card(profile):
    s = build_journey_summary(profile)
    rows = [('Business',s['business']),('Subtype',s['subtype']),('Commercial context',s['commercial_context']),
            ('Commercial paths being investigated',', '.join(s['paths_under_investigation']) or 'Discovery in progress'),
            ('Best-supported candidate (weighted)',s['best_supported_candidate']),
            ('Candidate confidence',f"{s['candidate_confidence_percent']}%" if s['candidate_confidence_percent'] is not None else 'Not available'),
            ('Authority-confirmed primary path',s['authority_confirmed_primary_path']),('Evidence shown for',s['evidence_path'])]
    rows += [(x['stage'], ('✓ ' if x['observed'] else '? ') + x['description']) for x in s['stages']]
    rows += [('Current path evidence',s['path_evidence']+' — '+s['evidence_status']),('Architect review',s['architect_review'])]
    body=''.join('<div style="margin:8px 0"><strong style="color:#fff">'+escape(k)+'</strong><br>'+escape(str(v))+'</div>' for k,v in rows)
    return '<section style="background:#111827;color:#D1D5DB;border-radius:14px;padding:20px;margin:18px 0;font:13px/1.6 Arial,sans-serif"><h2 style="color:#D8B66A;font-size:15px">HOW TRILLOKA READ THIS WEBSITE</h2>'+body+'<p style="font-size:11px">Paths under investigation are search candidates, not confirmed observations. An action handoff does not prove completion. Unknown evidence is not a verified failure.</p></section>'
