import json
import pytest
from pathway_markers import resolve_journeys, BUSINESS_JOURNEY_CANDIDATES, JOURNEY_GRAMMAR
from architecture_model import infer_architecture_profile
from journey_presentation import build_journey_summary
from test_v780_universal_paths import extract, CASES

@pytest.mark.parametrize('business',BUSINESS_JOURNEY_CANDIDATES)
@pytest.mark.parametrize('status',['timeout','',{},0,False,404,503])
def test_bad_page_status_stays_unknown_across_businesses(business,status):
    data={'journey_pages_scanned':[{'verified':True,'status_code':status,'role':'commerce_conversion','page_text_sample':'shopping cart checkout'}]}
    assert resolve_journeys(data,business)['path_completeness']=='0/3'

@pytest.mark.parametrize('business',BUSINESS_JOURNEY_CANDIDATES)
def test_stronger_authority_outranks_more_action_words(business,monkeypatch):
    import pathway_markers
    obs={m:[{'source':'observed_action'}] for m in JOURNEY_GRAMMAR['reservation_event']['action']}
    obs['order']=[{'source':'observed_action'}]
    obs['external_handoff']=[{'source':'observed_conversion_handoff','journey_model':'direct_purchase'}]
    monkeypatch.setattr(pathway_markers,'_observed_markers',lambda _:obs)
    r=resolve_journeys({},business)
    assert r['journey_model']=='direct_purchase'
    assert r['path_completeness']=='2/3'

@pytest.mark.parametrize('business',BUSINESS_JOURNEY_CANDIDATES)
def test_more_cta_synonyms_do_not_establish_primary_ordering(business):
    a=extract('Buy now');b=extract('Order');c=extract('Request a demo')
    a['static_cta_evidence']+=b['static_cta_evidence']+c['static_cta_evidence']
    a['mobile_cta_types']+=b['mobile_cta_types']+c['mobile_cta_types']
    r=resolve_journeys(a,business)
    assert r['primary_ordering_ambiguous'] and not r['resolved']
    assert r['architect_review_required']
    assert r['status']=='STRONGLY_SUPPORTED'

@pytest.mark.parametrize('business,label,journey',CASES)
def test_secondary_paths_have_own_observed_stages(business,label,journey):
    data=extract(label);data['page_text']='Book appointment subscribe now contact sales order online request quote'
    p=infer_architecture_profile(data,business)
    paths={r['journey_model']:r for r in p['journey_marker_resolution']['ranked_paths']}
    for secondary in p['secondary_journeys']:
        r=paths[secondary['journey_model']]
        assert r['markers']['action'] and r['markers']['progression']
        assert secondary['journey_model']!=p['journey_model']
    if p['provisional']:assert not p['secondary_journeys']

@pytest.mark.parametrize('confidence',[float('nan'),float('inf'),float('-inf'),'n/a',{},None])
def test_invalid_confidence_does_not_claim_a_percentage(confidence):
    s=build_journey_summary({'weighted_journey_candidate_confidence':confidence})
    assert s['candidate_confidence_percent'] is None

def test_fresh_evidence_replaces_cached_summary():
    p=infer_architecture_profile({},'ecommerce')
    old=build_journey_summary(p)
    p=infer_architecture_profile(extract('Buy now'),'ecommerce');p['journey_summary']=old
    assert build_journey_summary(p)['path_evidence']=='2/3'

def test_unknown_outcome_review_flag_matches_customer_wording():
    p=infer_architecture_profile(extract('Buy now'),'ecommerce')
    s=build_journey_summary(p)
    assert s['architect_review_required']
    assert s['architect_review'].startswith('Required')

def test_complete_path_does_not_require_path_review():
    data=extract('Buy now');data['verified_outcome_receipts']=[{'journey_model':'direct_purchase','marker':'order_confirmation','verified':True,'outcome_observed':True,'source_url':'https://business.example/result','collection_method':'architect_verified_outcome'}]
    s=build_journey_summary(infer_architecture_profile(data,'ecommerce'))
    assert not s['architect_review_required']
    assert s['architect_review'].startswith('No unresolved')

def test_safe_receipts_omit_url_credentials_and_query():
    data={'static_cta_evidence':[{'type':'order','source_url':'https://user:secret@business.example/','href':'https://provider.example/start?token=private#secret'}]}
    r=resolve_journeys(data,'ecommerce')
    text=json.dumps(r['observed_markers'])
    assert 'user:secret' not in text and 'token=' not in text and '#secret' not in text

def test_malformed_url_does_not_crash_resolver():
    d={'static_cta_evidence':[{'type':'order','source_url':'https://[broken/','href':'https://[broken/'}]}
    assert resolve_journeys(d,'ecommerce')['path_completeness']=='1/3'

def test_string_action_type_is_not_split_into_characters():
    d={'journey_action_evidence':[{'source_url':'https://business.example/','destination_url':'https://provider.example/start','action_types':'order'}]}
    assert resolve_journeys(d,'ecommerce')['path_completeness']=='2/3'


@pytest.mark.parametrize('tamper', [False, True], ids=['windows-crlf', 'reject-code-change'])
def test_release_verifier_handles_windows_checkout(tmp_path, monkeypatch, tamper):
    import pathlib
    import runpy
    import subprocess

    root = pathlib.Path(__file__).resolve().parent
    manifest = json.loads((root / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    names = set(manifest['release_sha256']) | set(manifest['required_backend_files'])
    names.add('RELEASE_MANIFEST.json')
    for name in names:
        data = (root / name).read_bytes().replace(b'\r\n', b'\n')
        (tmp_path / name).write_bytes(data.replace(b'\n', b'\r\n'))

    # The same Windows checkout must reject a genuine code change before
    # importing or running it. Do not rewrite the expected release hashes.
    if tamper:
        changed = tmp_path / 'hybrid_scanner.py'
        data = changed.read_bytes()
        assert b'v7.8.1-universal-path-refinement' in data
        changed.write_bytes(data.replace(b'v7.8.1-universal-path-refinement',
                                        b'v7.7.1-stale-engine'))

    calls = []
    def record_test_run(command, cwd):
        calls.append((command, cwd))
        return 0

    # Exercise the real verifier preflight, without recursively starting pytest.
    monkeypatch.setattr(subprocess, 'call', record_test_run)
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(tmp_path / 'verify_v781.py'), run_name='__main__')
    if tamper:
        assert 'hybrid_scanner.py' in str(result.value)
        assert not calls
    else:
        assert result.value.code == 0
        assert len(calls) == 1
        assert calls[0][0][1:4] == ['-m', 'pytest', '-q']
        assert calls[0][1] == tmp_path
