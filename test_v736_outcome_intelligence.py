from remediation_intelligence import (
    CATEGORY_OUTCOME_PROFILES,
    JOURNEY_OUTCOME_PROFILES,
    RULE_REMEDIATION_BASE,
    build_outcome_remediation,
    remediation_knowledge_stats,
)
from scorer import RevenueScorer, RESEARCH_MULTIPLIER_BY_RULE
from report_engine import ReportGenerator


def test_all_business_types_have_outcome_profiles():
    expected = {
        'ecommerce','marketplace','local_service','professional_service','healthcare','medspa','legal',
        'financial_services','real_estate','restaurant','hospitality_event','saas','b2b','agency',
        'membership_creator','education','nonprofit','automotive'
    }
    assert expected.issubset(CATEGORY_OUTCOME_PROFILES)


def test_all_commercial_journeys_have_outcome_profiles():
    expected = {'lead_quote','appointment_consultation','reservation_event','direct_purchase','demo_sales',
                'membership_subscription','donation_support','application_enrollment'}
    assert expected.issubset(JOURNEY_OUTCOME_PROFILES)


def test_remediation_library_is_not_a_tiny_fallback_table():
    stats = remediation_knowledge_stats()
    assert stats['rule_remediation_profiles'] >= 30
    assert stats['category_rule_refinements'] >= 40
    assert stats['business_outcome_profiles'] == 18
    assert stats['journey_outcome_profiles'] == 8


def test_ecommerce_delivery_is_research_and_outcome_grounded():
    r = build_outcome_remediation('delivery_expectation_clarity','ecommerce','direct_purchase',['commerce_payment'])
    assert r
    assert 'Baymard' in r['research_basis_summary']
    assert 'product, cart and checkout' in r['technical'].lower()
    assert 'purchase' in r['journey_goal'].lower()
    assert 'How' not in r  # no accidental display-only keys
    assert r['success_check']
    assert r['outcome_measure']


def test_cranberry_style_proof_gap_is_placement_not_absence():
    r = build_outcome_remediation('proof_placement_gap','ecommerce','direct_purchase',['commerce_payment'])
    assert r
    combined = (r['technical'] + ' ' + r['cro_ux'] + ' ' + r['success_check']).lower()
    assert 'existing verified proof' in combined
    assert 'decision' in combined
    assert 'generic homepage testimonials' in combined or 'product-specific' in combined
    assert 'add testimonials everywhere' not in combined


def test_public_unfinished_content_gets_release_control_solution():
    r = build_outcome_remediation('public_unfinished_content','ecommerce','direct_purchase',['commerce_payment'])
    assert r
    combined = (r['technical'] + ' ' + r['systems']).lower()
    assert 'unpublish' in combined or 'noindex' in combined
    assert 'cms' in combined or 'release' in combined


def test_sensitive_data_policy_solution_is_context_aware_without_legal_claim():
    r = build_outcome_remediation('policy_content_consistency','healthcare','appointment_consultation',['sensitive_data','regulated_high_trust'])
    assert r
    combined = (r['technical'] + ' ' + r['systems'] + ' ' + r['why_recommend']).lower()
    assert 'sensitive-data' in combined or 'privacy' in combined
    assert 'legal review' in combined or 'review' in combined
    assert 'noncompliant' not in combined
    assert 'illegal' not in combined


def test_specialist_research_does_not_bleed_into_unrelated_category_solution():
    legal = build_outcome_remediation('b2b_pricing_transparency','legal','appointment_consultation',['regulated_high_trust'])
    assert legal
    assert 'Baymard' not in legal['research_basis_summary']
    assert 'M+R' not in legal['research_basis_summary']
    assert 'Zillow' not in legal['research_basis_summary']


def test_category_changes_actual_solution_not_only_metadata():
    keys = ['ecommerce','restaurant','saas','legal','nonprofit','automotive','b2b','education']
    cro = []
    for business in keys:
        journey = {
            'ecommerce':'direct_purchase','restaurant':'reservation_event','saas':'demo_sales','legal':'appointment_consultation',
            'nonprofit':'donation_support','automotive':'appointment_consultation','b2b':'lead_quote','education':'application_enrollment'
        }[business]
        r = build_outcome_remediation('primary_conversion_path',business,journey,[])
        cro.append(r['cro_ux'])
    assert len(set(cro)) == len(cro)


def test_context_weighting_only_enriches_existing_verified_leaks():
    scorer = RevenueScorer()
    assert scorer._apply_business_type_weighting([], 'ecommerce','direct_purchase',['commerce_payment']) == []
    leak = {
        'rule_key':'delivery_expectation_clarity','category':'trust_conversion',
        'intrinsic_severity_score':1.0,'economic_severity':1.0,'pre_dedupe_penalty':1.0,
        'final_score_loss':1.0,'score_impact_points':1.0,'final_severity_score':1.0,
    }
    out = scorer._apply_business_type_weighting([leak], 'ecommerce','direct_purchase',['commerce_payment'])
    assert len(out) == 1
    assert out[0]['context_importance_multiplier'] > 1.0
    assert out[0]['study_context_multiplier'] > 1.0


def test_commercial_architecture_rules_are_no_longer_generically_suppressed():
    # Category/journey/context/research now decides relevance after verification.
    for key in ('delivery_expectation_clarity','shipping_info_discoverability','proof_placement_gap',
                'cross_page_consistency','public_unfinished_content','policy_content_consistency'):
        assert RESEARCH_MULTIPLIER_BY_RULE[key] >= 1.0


def test_cranberry_like_commercial_issue_gets_more_post_verification_emphasis_than_minor_seo_when_equal_raw_loss():
    scorer = RevenueScorer()
    proof = {
        'rule_key':'proof_placement_gap','category':'trust_conversion',
        'intrinsic_severity_score':1.0,'economic_severity':1.0,'pre_dedupe_penalty':1.0,
        'final_score_loss':1.0,'score_impact_points':1.0,'final_severity_score':1.0,
    }
    meta = dict(proof, rule_key='meta_description_missing', category='seo_technical')
    out = scorer._apply_business_type_weighting([proof, meta], 'ecommerce','direct_purchase',['commerce_payment'])
    by = {x['rule_key']:x for x in out}
    assert by['proof_placement_gap']['final_score_loss'] > by['meta_description_missing']['final_score_loss']


def test_report_solution_includes_success_check_and_category_outcome():
    gen = ReportGenerator()
    profile = {'business_type':'restaurant','journey_model':'reservation_event','context_tags':['local_location_dependent','hospitality_event']}
    r = gen._build_3_angle_solutions('primary_conversion_path', {'rule_key':'primary_conversion_path','leak_name':'Path'}, {}, profile)
    assert r['success_check']
    assert 'reservation' in (r['journey_goal'] + ' ' + r['outcome_measure']).lower()
    assert r['remediation_engine'].startswith('v7.5')

def test_guided_selection_pages_are_treated_as_evaluation_evidence():
    from hybrid_scanner import HybridScanner
    assert HybridScanner._journey_role('https://example.com/assessment/results') == 'evaluation'
    assert HybridScanner._journey_role('https://example.com/product-finder/quiz') == 'evaluation'
