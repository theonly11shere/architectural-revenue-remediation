import json
import pytest
from hybrid_scanner import HybridScanner
from architecture_model import infer_architecture_profile
from pathway_markers import resolve_journeys, BUSINESS_JOURNEY_CANDIDATES
from journey_presentation import build_journey_summary, render_journey_card, customer_action
from architect_review import build_architect_review_queue
from report_engine import ReportGenerator
from scorer import RevenueScorer
from test_regressions import base_scan

CASES = [
 ('restaurant','Order','direct_purchase'),('ecommerce','Buy now','direct_purchase'),
 ('marketplace','Buy now','direct_purchase'),('local_service','Request a quote','lead_quote'),
 ('professional_service','Get a quote','lead_quote'),('healthcare','Book appointment','appointment_consultation'),
 ('medspa','Book consultation','appointment_consultation'),('legal','Request a quote','lead_quote'),
 ('financial_services','Apply now','application_enrollment'),('real_estate','Request a quote','lead_quote'),
 ('hospitality_event','Reserve a room','reservation_event'),('saas','Request a demo','demo_sales'),
 ('b2b','Request a quote','lead_quote'),('agency','Request a demo','demo_sales'),
 ('membership_creator','Become a member','membership_subscription'),('education','Enroll now','application_enrollment'),
 ('nonprofit','Donate now','donation_support'),('automotive','Book appointment','appointment_consultation'),
 ('general','Buy now','direct_purchase')]

def extract(label,destination='https://provider.example/start'):
    return HybridScanner()._extract_static_html_evidence(
        f'<html><head><title>Example business</title></head><body><h1>Example business</h1><a href="{destination}">{label}</a></body></html>',
        'https://business.example/',True)

@pytest.mark.parametrize('business,label,journey', CASES)
def test_crawler_to_profile_report_all_19_types(business,label,journey):
    data=extract(label)
    data['final_url']='https://business.example/'
    r=resolve_journeys(data,business)
    assert r['journey_model']==journey
    assert r['path_completeness']=='2/3'
    assert r['status']=='STRONGLY_SUPPORTED'
    assert not r['proof']['terminal']
    p=infer_architecture_profile(data,business)
    assert p['journey_model']==(journey if business != 'general' else 'general')
    summary=build_journey_summary(p)
    assert summary['path_evidence']=='2/3'
    assert 'primary_site_action' not in render_journey_card(p)
    report=ReportGenerator().generate_admin_master_report({'architecture_profile':p},data)
    assert report['journey_summary']==summary
    assert summary['best_supported_candidate'] in ReportGenerator()._build_email_html(report)

@pytest.mark.parametrize('action', ['Order','Buy now','Book appointment','Reserve a table','Request a quote','Request a demo','Subscribe now','Donate now','Apply now'])
@pytest.mark.parametrize('destination',['#','', 'javascript:void(0)','/next'])
def test_dead_anchors_and_unvisited_internal_links_do_not_prove_progression(action,destination):
    r=resolve_journeys(extract(action,destination),'general')
    assert r['path_completeness']=='1/3'
    assert r['architect_review_required'] is True

@pytest.mark.parametrize('business',BUSINESS_JOURNEY_CANDIDATES)
def test_missing_evidence_preserves_candidate_and_escalates(business):
    p=infer_architecture_profile({'title':'Example business','page_text':'Services and products'},business)
    p['weighted_journey_candidate']='direct_purchase'
    p['weighted_journey_candidate_confidence']=.69
    summary=build_journey_summary(p)
    assert summary['candidate_confidence_percent']==69
    assert summary['best_supported_candidate']=='Direct Purchase'
    assert summary['authority_confirmed_primary_path']=='Still being verified'
    assert summary['path_evidence']=='0/3'
    assert summary['architect_review_required']
    assert any(x['category']=='journey_resolution' for x in build_architect_review_queue({'architecture_profile':p},{}))

@pytest.mark.parametrize('role,text', [('contact_or_lead','Your name email address Submit request sent'),('application','application form Submit application application submitted'),('commerce_conversion','shopping cart thank you for your order order confirmation'),('booking','select date booking confirmed')])
def test_confirmation_copy_cannot_prove_outcome(role,text):
    d={'journey_action_types':['order','apply','reserve','contact'], 'journey_pages_scanned':[{'url':'https://business.example/next','role':role,'verified':True,'page_text_sample':text}]}
    r=resolve_journeys(d,'general')
    assert not any(x['markers']['terminal'] for x in r['ranked_paths'])

@pytest.mark.parametrize('verified,status',[(False,200),(True,404),(True,503)])
def test_failed_pages_supply_no_markers(verified,status):
    d={'journey_action_types':['order'],'journey_pages_scanned':[{'url':'https://business.example/cart','role':'commerce_conversion','verified':verified,'status_code':status,'page_text_sample':'shopping cart secure checkout'}]}
    assert resolve_journeys(d,'ecommerce')['path_completeness']=='1/3'

def test_unrelated_donation_payment_does_not_advance_purchase():
    d={'journey_action_types':['order'],'journey_pages_scanned':[{'url':'https://business.example/donate','role':'donation','verified':True,'page_text_sample':'payment donation amount'}]}
    r=resolve_journeys(d,'ecommerce')
    assert r['path_completeness']=='1/3'

def test_secondary_path_can_escape_business_prior():
    assert resolve_journeys(extract('Buy now'),'healthcare')['journey_model']=='direct_purchase'

def test_tied_paths_do_not_arbitrarily_choose_primary():
    d=extract('Buy now'); other=extract('Request a demo')
    d['static_cta_evidence']+=other['static_cta_evidence'];d['mobile_cta_types']+=other['mobile_cta_types']
    r=resolve_journeys(d,'saas')
    assert r['primary_ordering_ambiguous'] and not r['resolved']
    assert r['path_completeness']=='2/3'

def test_verified_outcome_requires_receipt():
    d=extract('Buy now')
    d['verified_outcome_receipts']=[{'journey_model':'direct_purchase','marker':'order_confirmation','verified':True,'outcome_observed':True,'source_url':'https://business.example/result','collection_method':'architect_verified_outcome'}]
    assert resolve_journeys(d,'ecommerce')['path_completeness']=='3/3'
    assert resolve_journeys(d,'ecommerce')['status']=='VERIFIED'

def test_local_visit_requires_corroboration():
    d={'address_location_visible':True}
    assert resolve_journeys(d,'restaurant')['path_completeness']=='0/3'
    d['journey_pages_scanned']=[{'url':'https://business.example/menu','role':'evaluation','verified':True,'page_text_sample':'Our menu. Opening hours.'}]
    assert resolve_journeys(d,'restaurant')['journey_model']=='local_visit'

def test_summary_escapes_html_and_hides_internal_names():
    html=render_journey_card({'business_type_label':'<script>alert(1)</script>','primary_conversion':'primary_site_action'})
    assert '<script>' not in html and 'primary_site_action' not in html
    assert customer_action('primary_site_action')=='Still being verified'

def test_public_profile_retains_safe_summary():
    from main import _public_architecture_profile
    p=infer_architecture_profile(extract('Buy now'),'ecommerce')
    safe=_public_architecture_profile(p)
    assert build_journey_summary(safe)==build_journey_summary(p)
    assert 'observed_markers' not in json.dumps(safe)
    assert 'primary_site_action' not in json.dumps(_public_architecture_profile({'primary_conversion':'primary_site_action'}))

@pytest.mark.parametrize('path,role', [('/apply','application'),('/donate','donation'),('/membership','membership'),('/menu','location'),('/products/item','product'),('/pricing','pricing'),('/demo','contact_or_lead')])
def test_crawler_routes_all_decision_surfaces(path,role):
    assert HybridScanner._journey_role('https://example.com'+path)==role

@pytest.mark.parametrize('path,label,text,journey', [
 ('/apply','Apply now','application form supporting documents','application_enrollment'),
 ('/donate','Donate now','donation amount donor information','donation_support'),
 ('/membership','Subscribe now','choose plan billing cycle','membership_subscription'),
 ('/demo','Request a demo','company name work email','demo_sales'),
 ('/book','Book appointment','select service select date','appointment_consultation'),
 ('/cart','Buy now','shopping cart secure checkout','direct_purchase'),
 ('/quote','Get a quote','project details budget','lead_quote')])
def test_actual_deep_crawl_merge_to_resolver(path,label,text,journey,monkeypatch):
    from types import SimpleNamespace
    scanner=HybridScanner()
    url='https://business.example'+path
    monkeypatch.setattr(scanner,'_select_priority_journey_urls',lambda *a,**k:[url])
    monkeypatch.setattr(scanner.safe_http,'get',lambda *a,**k:SimpleNamespace(status_code=200,url=url,text=f'<html><body><a href="#">{label}</a><p>{text}</p></body></html>'))
    deep=scanner._scan_priority_journey_pages('https://business.example/',[url],journey)
    target={};scanner._merge_journey_evidence(target,deep)
    r=resolve_journeys(target,'general')
    assert r['journey_model']==journey and r['path_completeness']=='2/3'

@pytest.mark.parametrize('label,journey', [('Order','direct_purchase'),('Donate now','donation_support'),('Apply now','application_enrollment'),('Become a member','membership_subscription')])
def test_rendered_crawler_uses_same_classifier(label,journey):
    import asyncio
    class Page:
        url='https://business.example/'
        async def evaluate(self,script):
            return [{'text':label,'href':'https://provider.example/start','visible':True,'type':'other'}]
    receipts=asyncio.run(HybridScanner()._collect_action_candidates(Page()))
    assert resolve_journeys({'mobile_cta_evidence':receipts},'general')['journey_model']==journey

def test_rendered_page_progression_survives_merge():
    target={'journey_action_types':['demo']}
    HybridScanner._merge_browser_journey_evidence(target,{'browser_loaded':True,'dom_complete':True,'page_text':'company name work email','mobile_cta_types':['demo']},'https://example.com/demo')
    assert resolve_journeys(target,'saas')['path_completeness']=='2/3'

@pytest.mark.parametrize('business,label,journey',CASES)
def test_scoring_customer_report_and_saved_state_roundtrip(business,label,journey):
    from main import _protect_methodology_for_customer
    data=base_scan();data.update(extract(label));data['final_url']='https://business.example/'
    audit=RevenueScorer().audit_and_score(data,business_type=business)
    report=ReportGenerator().generate_admin_master_report(audit,data)
    saved=json.loads(json.dumps(report,default=str))
    customer=_protect_methodology_for_customer(saved)
    assert customer['journey_summary']==report['journey_summary']
    html=ReportGenerator()._build_email_html(customer)
    assert 'primary_site_action' not in html
    assert 'HOW TRILLOKA READ THIS WEBSITE' in html
    assert '2/3' in html
    assert 0 <= audit['overall_score'] <= 90

def test_terminal_receipt_alone_cannot_resolve_path():
    d={'verified_outcome_receipts':[{'journey_model':'direct_purchase','marker':'order_confirmation','verified':True,'outcome_observed':True,'source_url':'https://business.example/result','collection_method':'architect_verified_outcome'}]}
    assert not resolve_journeys(d,'ecommerce')['resolved']
