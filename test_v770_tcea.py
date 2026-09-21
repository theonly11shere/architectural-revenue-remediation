from commercial_contracts import COMMERCIAL_CONTRACTS, build_commercial_contract, commercial_minimum_gap_map, commercial_priority_metadata
from scan_execution_protocol import BUSINESS_TYPES, build_production_workflow, validate_protocol
from pathway_markers import resolve_journeys

def test_all_19_types_have_commercial_contracts():
    assert set(BUSINESS_TYPES) == set(COMMERCIAL_CONTRACTS)
    for b in BUSINESS_TYPES:
        c=build_commercial_contract(b)
        assert c['economic_outcome']
        assert c['commercial_minimums']
        for m in c['commercial_minimums']:
            assert m['tier'] in {'REQUIRED','EXPECTED','ENHANCER'}
            assert m['leak_class']
            assert m['decision_point']
            assert m['causal_mechanism']

def test_subtype_is_modifier_not_gate():
    p=build_production_workflow({'business_type':'restaurant','business_type_confidence':.91,'business_subtype':'cafe_bakery','business_subtype_confidence':.8,'journey_model':'general','journey_resolved':False})
    assert p['commercial_contract']['business_type']=='restaurant'
    assert p['commercial_contract']['business_subtype']=='cafe_bakery'
    assert p['commercial_contract']['subtype_modifier']['surfaces']
    assert 'direct_purchase' in p['candidate_journeys']

def test_minimum_absence_never_scores_without_coverage():
    c=build_commercial_contract('ecommerce')
    gaps=commercial_minimum_gap_map(c, [])
    assert all(x['gap_status']=='UNKNOWN' for x in gaps)
    assert all('No deduction' in x['scoring_policy'] for x in gaps)

def test_generic_checkout_text_does_not_verify_purchase():
    r=resolve_journeys({'page_text':'Our consulting platform helps teams improve checkout and payment strategy.'},'ecommerce')
    assert r['journey_model']=='general'
    assert r['status']=='UNVERIFIED'

def test_payment_interface_is_not_terminal_outcome():
    data={'journey_action_types':['order'],'journey_pages_scanned':[{'verified':True,'url':'https://example.com/checkout','page_role':'commerce_conversion','page_text_sample':'shopping cart secure checkout payment card number billing address'}]}
    r=resolve_journeys(data,'ecommerce')
    assert r['journey_model']=='direct_purchase'
    assert r['status']=='STRONGLY_SUPPORTED'
    assert r['path_completeness']=='2/3'

def test_confirmation_copy_is_not_terminal_outcome():
    data={'journey_action_types':['order'],'journey_pages_scanned':[{'verified':True,'url':'https://example.com/checkout','page_role':'commerce_conversion','page_text_sample':'shopping cart secure checkout thank you for your order order confirmation'}]}
    r=resolve_journeys(data,'ecommerce')
    assert r['status']=='STRONGLY_SUPPORTED'
    assert r['path_completeness']=='2/3'

def test_protocol_valid_with_19_types_and_aliases():
    v=validate_protocol()
    assert v['valid'] is True
    assert v['business_types']==19
    assert not v['bad_alias_targets']

def test_commercial_priority_is_explanatory_not_revenue_claim():
    c=build_commercial_contract('saas')
    m=commercial_priority_metadata({'rule_key':'primary_conversion_path','category':'trust_conversion','analysis_layer':'adaptive_architecture','confidence':'high','severity_factor':1.0},c,'demo_sales')
    assert 0 <= m['commercial_leak_priority_index'] <= 100
    assert m['leak_class']=='completion'
    assert 'not measured financial loss' in m['policy']


def test_all_business_workflows_return_commercial_context():
    for business in BUSINESS_TYPES:
        plan = build_production_workflow({
            'business_type': business,
            'business_type_confidence': .91,
            'journey_model': 'general',
            'journey_resolved': False,
        })
        assert plan['commercial_contract']['business_type'] == business
        assert plan['commercial_contract']['commercial_minimums']
        assert isinstance(plan['commercial_minimum_gap_map'], list)


def test_scored_audit_preserves_commercial_context_and_causality():
    from scorer import RevenueScorer
    from test_regressions import base_scan

    for business in BUSINESS_TYPES:
        scan = base_scan()
        scan['has_ssl'] = False
        audit = RevenueScorer().audit_and_score(scan, business_type=business)
        commercial = audit['commercial_evidence_architecture']
        assert commercial['commercial_contract']['business_type'] == audit['architecture_profile']['business_type']
        assert commercial['commercial_contract']['commercial_minimums']
        assert isinstance(commercial['commercial_minimum_gap_map'], list)
        leaks = audit['tiered_remediation_packages']['all_scoring_leaks']
        assert leaks
        for leak in leaks:
            assert leak['leak_class']
            assert leak['decision_point']
            assert leak['evidence_roles']['site_evidence']
            assert 0 <= leak['commercial_leak_priority_index'] <= 100
