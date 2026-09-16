import os
from pathlib import Path

from architect_review import build_architect_review_queue
from commercial_eligibility import evaluate_commercial_eligibility
from category_intelligence import public_business_type_options
from learning_intelligence import LearningMemory


def _memory(tmp_path, monkeypatch, min_support=3):
    monkeypatch.setenv('TRILLOKA_LEARNING_DB_PATH', str(tmp_path/'learn.db'))
    monkeypatch.setenv('TRILLOKA_LEARNING_AUTO_ACTIVATE_MIN_DOMAINS', str(min_support))
    monkeypatch.setenv('TRILLOKA_LEARNING_AUTO_ACTIVATE_CLASSIFICATION', 'true')
    return LearningMemory()


def _scan(title='Vertical analytics software', h1='Analytics platform', meta='Free trial integrations API'):
    return {
        'title': title, 'h1_tags':[h1], 'meta_description':meta,
        'architecture_profile': {'business_type':'saas','journey_model':'demo_sales','context_tags':[]},
        'mobile_cta_types':['demo'], 'schema_types':['SoftwareApplication'],
    }


def test_public_selector_excludes_noncommercial_nonprofit():
    values={x['value'] for x in public_business_type_options()}
    assert 'nonprofit' not in values
    assert 'ecommerce' in values and 'saas' in values and 'restaurant' in values


def test_information_only_site_is_declined_but_museum_ticket_path_is_mixed():
    info={'title':'National Research Archive','page_text':'government public information digital collection historical archive research library'}
    profile={'business_type':'nonprofit','journey_model':'general'}
    r=evaluate_commercial_eligibility(info,profile,'auto')
    assert r['allow_scan'] is False and r['status']=='not_commercial_target'
    mixed={'title':'City Museum','page_text':'museum exhibitions tickets admission buy tickets membership gift shop'}
    r2=evaluate_commercial_eligibility(mixed,{'business_type':'nonprofit','journey_model':'direct_purchase'},'auto')
    assert r2['allow_scan'] is True and r2['status']=='mixed_commercial_path'


def test_generic_contact_form_does_not_make_archive_commercial():
    scan={'title':'Heritage Archive','page_text':'historical society public information archive contact us','form_present':True}
    r=evaluate_commercial_eligibility(scan,{'business_type':'nonprofit','journey_model':'lead_quote'},'auto')
    assert r['allow_scan'] is False


def test_one_confirmation_is_candidate_not_active(tmp_path, monkeypatch):
    m=_memory(tmp_path,monkeypatch,3)
    m.record_classification_confirmation(domain='one.example',selected_business_type='saas',scan=_scan())
    overlay=m.inference_overlay(_scan())
    assert overlay['scores']=={}
    stats=m.stats()
    assert stats['events']>=1


def test_repeated_confirmations_can_activate_bounded_recognition(tmp_path, monkeypatch):
    m=_memory(tmp_path,monkeypatch,3)
    for i in range(3):
        m.record_classification_confirmation(domain=f'{i}.example',selected_business_type='saas',scan=_scan())
    overlay=m.inference_overlay(_scan())
    assert overlay['scores'].get('saas',0)>0
    assert overlay['scores']['saas'] <= m.max_inference_boost


def test_architect_queue_always_contains_final_proof_and_does_not_make_failure():
    q=build_architect_review_queue(
        {'architecture_profile':{'business_type':'ecommerce','journey_model':'direct_purchase'},'final_url':'https://x.test'},
        {'scoring_ledger':[{'rule_key':'meta_description_missing'}], 'overall_score':60, 'full_50_checkpoint_basis':[]}
    )
    assert any(x['category']=='final_proof' for x in q)
    assert all('machine_policy' in x for x in q)


def test_pending_report_blocked_until_architect_reviews_resolved(tmp_path, monkeypatch):
    m=_memory(tmp_path,monkeypatch,3)
    ids=m.add_architect_reviews(domain='x.test',vault_id='VAULT-X',reviews=[{
        'severity':'IMPORTANT','category':'final_proof','title':'Final proof','reason':'review','evidence':{},'architect_should_inspect':{}
    }])
    m.queue_pending_report(vault_id='VAULT-X',domain='x.test',customer_email='customer@example.com',report={'vault_id':'VAULT-X'},review_ids=ids)
    try:
        m.prepare_pending_report_delivery('VAULT-X')
        assert False, 'should block while review is open'
    except ValueError as exc:
        assert 'still open' in str(exc)
    m.resolve_architect_review(ids[0],'resolved',notes='checked')
    prepared=m.prepare_pending_report_delivery('VAULT-X')
    assert prepared['report']['architect_review']['status']=='completed'


def test_successful_architect_outcome_can_improve_solution_knowledge(tmp_path, monkeypatch):
    m=_memory(tmp_path,monkeypatch,3)
    m.record_remediation_outcome({
        'domain':'shop.test','business_type':'ecommerce','journey_model':'direct_purchase',
        'rule_key':'proof_placement_gap','outcome_status':'improved',
        'technical_note':'Keep proof module data attached to the product template.',
        'cro_note':'Place product-specific proof next to the purchase decision.',
        'systems_note':'Regression-check proof placement after template releases.',
        'verification_note':'Re-scan product to cart progression.'
    })
    g=m.outcome_guidance('ecommerce','direct_purchase','proof_placement_gap')
    assert g['supporting_outcomes']>=1
    assert 'product-specific proof' in g['cro_note']

def test_architect_report_workflow_survives_learning_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv('TRILLOKA_LEARNING_DB_PATH', str(tmp_path/'ops.db'))
    monkeypatch.setenv('TRILLOKA_LEARNING_ENABLED', 'false')
    m=LearningMemory()
    ids=m.add_architect_reviews(domain='x.test',vault_id='VAULT-OFF',reviews=[{
        'severity':'IMPORTANT','category':'final_proof','title':'Final proof','reason':'review','evidence':{},'architect_should_inspect':{}
    }])
    assert ids
    queued=m.queue_pending_report(vault_id='VAULT-OFF',domain='x.test',customer_email='customer@example.com',report={'vault_id':'VAULT-OFF'},review_ids=ids)
    assert queued['queued'] is True
    assert m.stats()['enabled'] is False
    assert m.stats()['open_architect_reviews'] == 1
